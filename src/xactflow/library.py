from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Union

import ipxact
from lxml import etree

from . import SCR
from .diagnostics import Diagnostic, Severity

# Mirrors the parser configuration.
_XML_PARSER = etree.XMLParser(remove_comments=True)

# IEEE 1685-2022's XML namespace. Files outside this namespace are not IP-XACT at all.
_IPXACT_NAMESPACE = "http://www.accellera.org/XMLSchema/IPXACT/1685-2022"

# Namespace prefixes of the other IP-XACT versions (1685-2009/2014, SPIRIT 1.x).
_OTHER_IPXACT_NAMESPACE_PREFIXES = (
    "http://www.accellera.org/XMLSchema/IPXACT/",
    "http://www.spiritconsortium.org/XMLSchema/SPIRIT/",
)


@dataclass
class LibraryEntry:
    """One IP-XACT document indexed in the library.

    path is the file the document was parsed from, or None for a document added in memory
    through Library.add.
    """

    path: Optional[Path]
    document: object


@dataclass
class Library:
    """A VLNV-indexed collection of IP-XACT documents discovered by scanning directories.

    Every .xml file under the scanned roots is parsed with ipxact.parse_file, and
    documents that parse successfully are indexed by their VLNV. Files that fail to parse, and
    VLNV collisions (SCR 1.1 uniqueVLNV), are recorded as diagnostics instead of raising.
    Documents that only exist in memory (e.g. produced by an importer) go through Library.add,
    which applies the same checks.
    """

    entries: "dict[ipxact.VLNV, LibraryEntry]" = field(default_factory=dict)
    diagnostics: "list[Diagnostic]" = field(default_factory=list)

    @classmethod
    def scan(cls, *roots: Union[str, Path]) -> "Library":
        root_paths = [Path(root) for root in roots]
        for root in root_paths:
            if not root.exists():
                raise FileNotFoundError(f"library scan root does not exist: {root}")
            if not root.is_dir():
                raise NotADirectoryError(f"library scan root is not a directory: {root}")

        library = cls()
        for root in root_paths:
            indexed_any = False
            for path in sorted(root.rglob("*.xml")):
                indexed_any |= library.add_file(path)
            if not indexed_any:
                # An empty root can be intended (e.g. a library folder not populated yet), so this
                # is only a warning, unlike a root that does not exist at all.
                library.diagnostics.append(
                    Diagnostic(
                        message=f"no IEEE 1685-2022 IP-XACT document was indexed from {root}",
                        severity=Severity.WARNING,
                        location=str(root),
                    )
                )
        return library

    def add(self, document: object, path: Optional[Path] = None, *, replace: bool = False) -> bool:
        """Index an already-parsed IP-XACT document, e.g. one produced in memory by an importer.

        With replace=True the existing entry is overwritten, for when the document is regenerated
        from a source that changes the scanned one.

        Returns True if the document was indexed, False if it was rejected as a duplicate.
        """
        self.diagnostics.extend(SCR.run_single_doc_checks(document))

        vlnv = document.vlnv
        existing = self.entries.get(vlnv)
        if existing is not None and not replace:
            self.diagnostics.append(
                Diagnostic(
                    message=f"duplicate VLNV {vlnv}: already loaded from {_describe(existing.path)}, "
                    f"also found in {_describe(path)}",
                    severity=Severity.ERROR,
                    location=str(vlnv),
                    rule_id="SCR 1.1",
                    rule_name="uniqueVLNV",
                )
            )
            return False

        self.entries[vlnv] = LibraryEntry(path=path, document=document)
        return True

    def add_file(self, path: Union[str, Path], *, replace: bool = False) -> bool:
        """Parse one IP-XACT file and index it, with the namespace filtering and parse-failure warnings.

        Returns True if the document was indexed, False if it was skipped, failed to parse, or was
        rejected as a duplicate.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"library file does not exist: {path}")
        document = self._parse_file(path)
        return document is not None and self.add(document, path, replace=replace)

    def _parse_file(self, path: Path) -> Optional[object]:
        """Parse one file into an IP-XACT 1685-2022 document, or return None if it is not one.

        Other IP-XACT versions and parse failures are recorded as warnings; XML that is not
        IP-XACT at all is skipped silently.
        """
        try:
            root = etree.parse(str(path), parser=_XML_PARSER).getroot()
        except etree.XMLSyntaxError:
            return None  # not well-formed XML at all, not ours to report on.

        namespace = etree.QName(root).namespace
        if namespace != _IPXACT_NAMESPACE:
            if namespace is not None and namespace.startswith(_OTHER_IPXACT_NAMESPACE_PREFIXES):
                self.diagnostics.append(
                    Diagnostic(
                        message=f"skipped {path}: IP-XACT namespace {namespace} is not "
                        f"IEEE 1685-2022, the only version supported",
                        severity=Severity.WARNING,
                        location=str(path),
                    )
                )
            return None  # well-formed XML, but not IP-XACT 1685-2022, skip.

        try:
            document = ipxact.parse_element(root)
        except Exception as exc:
            self.diagnostics.append(
                Diagnostic(
                    message=f"failed to parse {path}: {exc}",
                    severity=Severity.WARNING,
                    location=str(path),
                )
            )
            return None

        return document

    def documents(self) -> Iterable[object]:
        return (entry.document for entry in self.entries.values())

    def get(self, vlnv: "ipxact.VLNV") -> Optional[object]:
        entry = self.entries.get(vlnv)
        return entry.document if entry is not None else None

    def get_component(self, vlnv: "ipxact.VLNV") -> Optional["ipxact.Component"]:
        document = self.get(vlnv)
        return document if isinstance(document, ipxact.Component) else None

    def get_design(self, vlnv: "ipxact.VLNV") -> Optional["ipxact.Design"]:
        document = self.get(vlnv)
        return document if isinstance(document, ipxact.Design) else None

    def get_design_configuration(self, vlnv: "ipxact.VLNV") -> Optional["ipxact.DesignConfiguration"]:
        document = self.get(vlnv)
        return document if isinstance(document, ipxact.DesignConfiguration) else None

    def get_bus_definition(self, vlnv: "ipxact.VLNV") -> Optional["ipxact.BusDefinition"]:
        document = self.get(vlnv)
        return document if isinstance(document, ipxact.BusDefinition) else None

    def get_abstraction_definition(self, vlnv: "ipxact.VLNV") -> Optional["ipxact.AbstractionDefinition"]:
        document = self.get(vlnv)
        return document if isinstance(document, ipxact.AbstractionDefinition) else None


def _describe(path: Optional[Path]) -> str:
    return str(path) if path is not None else "<in-memory>"
