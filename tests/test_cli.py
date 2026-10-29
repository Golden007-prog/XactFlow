from pathlib import Path

import pytest

from xactflow.cli import main
from xactflow.exporter import Exporter
from xactflow.importer import Importer

FIXTURES = Path(__file__).parent / "fixtures"


def test_link_happy_path_exits_zero(capsys):
    exit_code = main(
        [
            "link",
            str(FIXTURES / "basic" / "top_design.xml"),
            "--lib",
            str(FIXTURES / "basic"),
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "linked 'example.org:soc:top:1.0'" in out
    assert "no errors" in out


def test_link_with_missing_lib_dir_exits_nonzero(capsys, tmp_path):
    exit_code = main(
        [
            "link",
            str(FIXTURES / "basic" / "top_design.xml"),
            "--lib",
            str(tmp_path / "does_not_exist"),
        ]
    )

    assert exit_code == 1
    assert "library scan root does not exist" in capsys.readouterr().err


def test_link_reports_unresolvable_component_ref_and_exits_nonzero(capsys):
    exit_code = main(
        [
            "link",
            str(FIXTURES / "cli" / "broken_design.xml"),
            "--lib",
            str(FIXTURES / "basic"),
        ]
    )

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "SCR 1.9" in err


def test_link_does_not_duplicate_diagnostics_when_design_is_also_inside_lib(capsys):
    # Library.scan already single-doc-checks every file it scans, including the top design
    # itself when --lib points at (or includes) the directory it lives in; link() checks
    # the same design again independently. The two diagnostic lists must be deduped when
    # combined, not just concatenated.
    exit_code = main(
        [
            "link",
            str(FIXTURES / "cli" / "duplicate_interface_design.xml"),
            "--lib",
            str(FIXTURES / "cli"),
        ]
    )

    assert exit_code == 1
    err = capsys.readouterr().err
    assert err.count("SCR 2.3") == 2  # one per (instance, bus interface) pair, not doubled


def test_check_happy_path_exits_zero(capsys):
    exit_code = main(["check", str(FIXTURES / "basic" / "top_design.xml")])

    assert exit_code == 0
    assert "no single-document SCR violations" in capsys.readouterr().out


def test_check_reports_duplicate_interface_and_exits_nonzero(capsys):
    exit_code = main(["check", str(FIXTURES / "cli" / "duplicate_interface_design.xml")])

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "SCR 2.3" in err


def test_main_reports_a_clean_error_for_a_missing_file(capsys):
    exit_code = main(["check", str(FIXTURES / "does_not_exist.xml")])

    assert exit_code == 1
    assert capsys.readouterr().err.startswith("error: ")


@pytest.mark.parametrize("group", ["exporter", "importer"])
@pytest.mark.parametrize("command", ["check", "link"])
def test_a_broken_installed_plugin_does_not_crash_unrelated_commands(
    monkeypatch, capsys, group, command
):
    # discover_exporters()/discover_importers() run during _build_parser(), before any
    # subcommand is even chosen, so a plugin that fails to load must not crash commands (like
    # check, used here) that have nothing to do with that plugin.
    class BrokenEntryPoint:
        name = "broken"

        def load(self):
            raise ImportError("no module named 'xactflow_broken_plugin'")

    monkeypatch.setattr(
        f"xactflow.{group}._entry_points_for_group", lambda _: [BrokenEntryPoint()]
    )
    args = [command, str(FIXTURES / "basic" / "top_design.xml")]
    if command == "link":
        args.extend(["--lib", str(FIXTURES / "basic")])
    exit_code = main(args)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "warning:" in captured.err
    assert "broken" in captured.err
    assert f"xactflow.{group}s" in captured.err
    assert "error:" not in captured.err
    assert "no errors" in captured.out or "no single-document SCR violations" in captured.out


def test_no_plugin_subcommands_when_none_are_installed(capsys):
    # with no exporters/importers registered (the real state of this repo, which ships none),
    # only the built-in link/check subcommands should exist.
    with pytest.raises(SystemExit):
        main(["fake-exporter", str(FIXTURES / "basic" / "top_design.xml")])
    assert "invalid choice" in capsys.readouterr().err


class _FakeExporter(Exporter):
    name = "fake"
    exported: list = []

    def export(self, subject, output_dir, **options):
        type(self).exported.append((subject.vlnv, output_dir, options))


def test_installed_exporter_becomes_its_own_top_level_subcommand(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("xactflow.cli.discover_exporters", lambda: {"fake-exporter": _FakeExporter})
    _FakeExporter.exported.clear()

    exit_code = main(
        [
            "fake-exporter",
            str(FIXTURES / "basic" / "top_design.xml"),
            "--lib",
            str(FIXTURES / "basic"),
            "--output",
            str(tmp_path),
            "--option",
            "flavor=minimal",
        ]
    )

    assert exit_code == 0
    assert len(_FakeExporter.exported) == 1
    vlnv, output_dir, options = _FakeExporter.exported[0]
    assert str(vlnv) == "example.org:soc:top:1.0"
    assert output_dir == tmp_path
    assert options == {"flavor": "minimal"}
    assert "exported 'example.org:soc:top:1.0' via 'fake-exporter'" in capsys.readouterr().out


def test_installed_exporter_does_not_run_when_linking_has_errors(monkeypatch, tmp_path):
    monkeypatch.setattr("xactflow.cli.discover_exporters", lambda: {"fake-exporter": _FakeExporter})
    _FakeExporter.exported.clear()

    exit_code = main(
        [
            "fake-exporter",
            str(FIXTURES / "cli" / "broken_design.xml"),
            "--lib",
            str(FIXTURES / "basic"),
            "--output",
            str(tmp_path),
        ]
    )

    assert exit_code == 1
    assert _FakeExporter.exported == []


class _FakeImporter(Importer):
    name = "fake"
    imported: list = []

    def import_(self, source_path, **options):
        type(self).imported.append((source_path, options))
        return "fake-object-model"


def test_installed_importer_becomes_its_own_top_level_subcommand(monkeypatch, capsys):
    monkeypatch.setattr("xactflow.cli.discover_importers", lambda: {"fake-importer": _FakeImporter})
    _FakeImporter.imported.clear()

    exit_code = main(["fake-importer", str(FIXTURES / "basic" / "top_design.xml"), "--option", "mode=strict"])

    assert exit_code == 0
    assert _FakeImporter.imported == [
        (Path(str(FIXTURES / "basic" / "top_design.xml")), {"mode": "strict"})
    ]
    out = capsys.readouterr().out
    assert "imported" in out
    assert "via 'fake-importer': str" in out


class _ChainableFakeExporter(Exporter):
    name = "chainable"
    calls: list = []

    def export(self, subject, output_dir, **options):
        type(self).calls.append((subject, output_dir, options))


class _TypeRejectingFakeExporter(Exporter):
    name = "picky"

    def export(self, subject, output_dir, **options):
        raise TypeError(f"picky only supports Component, got {type(subject).__name__}")


def test_then_chains_importer_output_straight_into_an_exporter(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("xactflow.cli.discover_exporters", lambda: {"chainable": _ChainableFakeExporter})
    monkeypatch.setattr("xactflow.cli.discover_importers", lambda: {"fake-importer": _FakeImporter})
    _ChainableFakeExporter.calls.clear()
    _FakeImporter.imported.clear()

    exit_code = main(
        [
            "fake-importer",
            str(FIXTURES / "basic" / "top_design.xml"),
            "--option",
            "mode=strict",
            "--then",
            "chainable",
            "--output",
            str(tmp_path),
            "--then-option",
            "flavor=minimal",
        ]
    )

    assert exit_code == 0
    assert _FakeImporter.imported == [
        (Path(str(FIXTURES / "basic" / "top_design.xml")), {"mode": "strict"})
    ]
    assert len(_ChainableFakeExporter.calls) == 1
    subject, output_dir, options = _ChainableFakeExporter.calls[0]
    assert subject == "fake-object-model"  # exactly what _FakeImporter.import_ returned, unserialized
    assert output_dir == tmp_path
    assert options == {"flavor": "minimal"}
    out = capsys.readouterr().out
    assert "imported" in out
    assert "exported via 'chainable'" in out


def test_then_with_unknown_exporter_name_is_an_argparse_error(monkeypatch, capsys):
    monkeypatch.setattr("xactflow.cli.discover_exporters", lambda: {"chainable": _ChainableFakeExporter})
    monkeypatch.setattr("xactflow.cli.discover_importers", lambda: {"fake-importer": _FakeImporter})

    with pytest.raises(SystemExit):
        main(
            [
                "fake-importer",
                str(FIXTURES / "basic" / "top_design.xml"),
                "--then",
                "does-not-exist",
            ]
        )
    assert "invalid choice" in capsys.readouterr().err


def test_then_surfaces_a_clear_error_when_the_exporter_rejects_the_type(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("xactflow.cli.discover_exporters", lambda: {"picky": _TypeRejectingFakeExporter})
    monkeypatch.setattr("xactflow.cli.discover_importers", lambda: {"fake-importer": _FakeImporter})
    _FakeImporter.imported.clear()

    exit_code = main(
        [
            "fake-importer",
            str(FIXTURES / "basic" / "top_design.xml"),
            "--then",
            "picky",
            "--output",
            str(tmp_path),
        ]
    )

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "'picky' cannot export the output of 'fake-importer'" in err
    assert "str" in err  # names the rejected type, not just a bare traceback
    assert "Traceback" not in err


class _MisbehavingFakeExporter(Exporter):
    name = "misbehaving"

    def export(self, subject, output_dir, **options):
        # a non-compliant exporter that doesn't follow the TypeError-for-rejection convention,
        # e.g. unguarded attribute access on a subject it doesn't actually support.
        subject.instances


def test_then_contextualizes_a_non_type_error_from_the_exporter_too(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("xactflow.cli.discover_exporters", lambda: {"misbehaving": _MisbehavingFakeExporter})
    monkeypatch.setattr("xactflow.cli.discover_importers", lambda: {"fake-importer": _FakeImporter})
    _FakeImporter.imported.clear()

    exit_code = main(
        [
            "fake-importer",
            str(FIXTURES / "basic" / "top_design.xml"),
            "--then",
            "misbehaving",
            "--output",
            str(tmp_path),
        ]
    )

    assert exit_code == 1
    err = capsys.readouterr().err
    # still names both plugins and the type, unlike main()'s bare "error: ..." fallback, even
    # though this exporter didn't raise the documented TypeError convention.
    assert "'misbehaving' failed while exporting the output of 'fake-importer'" in err
    assert "str" in err
    assert not err.startswith("error: ")
    assert "Traceback" not in err


def test_then_option_without_then_is_a_clear_error(monkeypatch, capsys):
    monkeypatch.setattr("xactflow.cli.discover_exporters", lambda: {})
    monkeypatch.setattr("xactflow.cli.discover_importers", lambda: {"fake-importer": _FakeImporter})

    exit_code = main(
        [
            "fake-importer",
            str(FIXTURES / "basic" / "top_design.xml"),
            "--then-option",
            "flavor=minimal",
        ]
    )

    assert exit_code == 1
    assert "--then-option requires --then" in capsys.readouterr().err


def test_plugin_name_colliding_with_a_builtin_command_is_skipped(monkeypatch, capsys):
    monkeypatch.setattr("xactflow.cli.discover_exporters", lambda: {"check": _FakeExporter})
    monkeypatch.setattr("xactflow.cli.discover_importers", lambda: {})

    # "check" stays the real built-in command, not the fake exporter.
    exit_code = main(["check", str(FIXTURES / "basic" / "top_design.xml")])

    assert exit_code == 0
    assert "conflicts with an existing xactflow subcommand" in capsys.readouterr().err
