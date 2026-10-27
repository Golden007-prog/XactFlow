from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Type

import ipxact

from . import SCR
from .diagnostics import Diagnostic, Severity
from .link import link
from .exporter import Exporter, discover_exporters
from .importer import Importer, discover_importers
from .library import Library

_BUILTIN_COMMANDS = {"link", "check"}


def _print_diagnostics(diagnostics: List[Diagnostic]) -> None:
    for diagnostic in diagnostics:
        print(str(diagnostic), file=sys.stderr)


def _has_errors(diagnostics: List[Diagnostic]) -> bool:
    return any(diagnostic.severity is Severity.ERROR for diagnostic in diagnostics)


def _parse_option(value: str) -> Tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(f"expected KEY=VALUE, got {value!r}")
    key, _, val = value.partition("=")
    return key, val


def _dedupe_diagnostics(diagnostics: List[Diagnostic]) -> List[Diagnostic]:
    # library.diagnostics and linked.diagnostics can both contain single-doc SCR checks for
    # a same design, since Library.scan and link() each run single-doc checks independently.
    # Diagnostic is a frozen dataclass, so exact-duplicate findings can be collapsed by value
    # while preserving first-seen order.
    seen: set = set()
    deduped = []
    for diagnostic in diagnostics:
        if diagnostic in seen:
            continue
        seen.add(diagnostic)
        deduped.append(diagnostic)
    return deduped


def _link_from_args(args: argparse.Namespace):
    library = Library.scan(*args.lib)
    design = ipxact.parse_file(args.design)
    design_configuration = ipxact.parse_file(args.config) if args.config else None
    linked = link(design, library, design_configuration)
    diagnostics = _dedupe_diagnostics(library.diagnostics + linked.diagnostics)
    return linked, diagnostics


def _cmd_link(args: argparse.Namespace) -> int:
    linked, diagnostics = _link_from_args(args)
    _print_diagnostics(diagnostics)
    if _has_errors(diagnostics):
        return 1
    print(
        f"linked '{linked.vlnv}' with no errors "
        f"({len(linked.instances)} instances, {len(linked.interconnections)} interconnections)"
    )
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    document = ipxact.parse_file(args.file)
    diagnostics = SCR.run_single_doc_checks(document)
    _print_diagnostics(diagnostics)
    if _has_errors(diagnostics):
        return 1
    print(f"no single-document SCR violations found in {args.file}")
    return 0


def _cmd_run_exporter(args: argparse.Namespace) -> int:
    linked, diagnostics = _link_from_args(args)
    _print_diagnostics(diagnostics)
    if _has_errors(diagnostics):
        print("not exporting: linking reported errors", file=sys.stderr)
        return 1

    options = dict(args.option or [])
    args.exporter_class().export(linked, Path(args.output), **options)
    print(f"exported '{linked.vlnv}' via '{args.command}' to {args.output}")
    return 0


def _cmd_run_importer(args: argparse.Namespace) -> int:
    if args.then_option and not args.then:
        print("--then-option requires --then to also be given", file=sys.stderr)
        return 1

    options = dict(args.option or [])
    result = args.importer_class().import_(Path(args.source), **options)

    if not args.then:
        print(f"imported '{args.source}' via '{args.command}': {type(result).__name__}")
        return 0

    # --then chains straight into an installed exporter's .export(), in the same process, on
    # the object import_() just returned: no serialization, no intermediate file. args.then is
    # validated by argparse (choices=) against the exporters registered as their own subcommand,
    # so the lookup below always succeeds; what can still fail is the exporter rejecting this
    # particular result. Exporter.export()'s documented convention is to signal that with a
    # plain TypeError (subject is deliberately untyped, see exporter.py), which gets the precise
    # "cannot export" message below; a non-compliant exporter raising something else still gets
    # a contextualized message rather than main()'s bare "error: ..." fallback.
    then_options = dict(args.then_option or [])
    then_exporter_class = args.available_exporters[args.then]
    try:
        then_exporter_class().export(result, Path(args.output), **then_options)
    except TypeError as exc:
        print(
            f"'{args.then}' cannot export the output of '{args.command}' "
            f"({type(result).__name__}): {exc}",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(
            f"'{args.then}' failed while exporting the output of '{args.command}' "
            f"({type(result).__name__}): {exc}",
            file=sys.stderr,
        )
        return 1

    print(
        f"imported '{args.source}' via '{args.command}' and exported via '{args.then}' "
        f"to {args.output}"
    )
    return 0


def _add_builtin_subparsers(subparsers: "argparse._SubParsersAction") -> None:
    link_parser = subparsers.add_parser(
        "link", help="resolve a design against a library and report SCR diagnostics"
    )
    link_parser.add_argument("design", help="path to the top-level design XML file")
    link_parser.add_argument(
        "--lib",
        action="append",
        default=[],
        metavar="DIR",
        help="directory to scan for IP-XACT files; may be given multiple times",
    )
    link_parser.add_argument(
        "--config", default=None, metavar="FILE", help="path to the matching designConfiguration XML file"
    )
    link_parser.set_defaults(func=_cmd_link)

    check_parser = subparsers.add_parser(
        "check", help="run single-document SCR checks on one IP-XACT file, no library needed"
    )
    check_parser.add_argument("file", help="path to an IP-XACT XML file")
    check_parser.set_defaults(func=_cmd_check)


def _add_exporter_subparser(
    subparsers: "argparse._SubParsersAction", name: str, exporter_class: Type[Exporter]
) -> None:
    parser = subparsers.add_parser(name, help=f"link a design and run the '{name}' exporter on it")
    parser.add_argument("design", help="path to the top-level design XML file")
    parser.add_argument("--lib", action="append", default=[], metavar="DIR")
    parser.add_argument("--config", default=None, metavar="FILE")
    parser.add_argument("--output", default=".", metavar="DIR")
    parser.add_argument(
        "--option", action="append", type=_parse_option, metavar="KEY=VALUE",
        help="an exporter-specific option, may be given multiple times",
    )
    parser.set_defaults(func=_cmd_run_exporter, exporter_class=exporter_class)


def _add_importer_subparser(
    subparsers: "argparse._SubParsersAction",
    name: str,
    importer_class: Type[Importer],
    available_exporters: Dict[str, Type[Exporter]],
) -> None:
    parser = subparsers.add_parser(name, help=f"run the '{name}' importer on a non-IP-XACT source file")
    parser.add_argument("source", help="path to the source file to import")
    parser.add_argument(
        "--option", action="append", type=_parse_option, metavar="KEY=VALUE",
        help="an importer-specific option, may be given multiple times",
    )
    parser.add_argument(
        "--then",
        default=None,
        choices=sorted(available_exporters),
        metavar="EXPORTER",
        help=(
            "an installed exporter's registered name; if given, this importer's result is "
            "handed straight to that exporter's export() in the same process, no intermediate "
            "file involved"
        ),
    )
    parser.add_argument(
        "--output", default=".", metavar="DIR", help="output directory for --then's exporter"
    )
    parser.add_argument(
        "--then-option", action="append", type=_parse_option, metavar="KEY=VALUE",
        help="an option for --then's exporter, separate from --option; may be given multiple times",
    )
    parser.set_defaults(
        func=_cmd_run_importer, importer_class=importer_class, available_exporters=available_exporters
    )


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI. Every installed exporter or importer becomes its own top-level subcommand,
    so a plugin package is usable the moment it's installed with no separate registration step.
    Link and check are XactFlow's own built-in subcommands, not plugins.
    """
    parser = argparse.ArgumentParser(
        prog="xactflow",
        description="Multi-file IP-XACT linking and semantic consistency checking.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_builtin_subparsers(subparsers)

    registered_names = set(_BUILTIN_COMMANDS)
    registered_exporters: Dict[str, Type[Exporter]] = {}
    for name, exporter_class in sorted(discover_exporters().items()):
        if name in registered_names:
            print(
                f"warning: exporter '{name}' conflicts with an existing xactflow subcommand, skipping",
                file=sys.stderr,
            )
            continue
        _add_exporter_subparser(subparsers, name, exporter_class)
        registered_names.add(name)
        registered_exporters[name] = exporter_class

    for name, importer_class in sorted(discover_importers().items()):
        if name in registered_names:
            print(
                f"warning: importer '{name}' conflicts with an existing xactflow subcommand, skipping",
                file=sys.stderr,
            )
            continue
        # registered_exporters (not the raw discover_exporters() result) so --then only ever
        # offers exporters that actually made it onto the CLI as their own subcommand.
        _add_importer_subparser(subparsers, name, importer_class, registered_exporters)
        registered_names.add(name)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        parser = _build_parser()
        args = parser.parse_args(argv)
        return args.func(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
