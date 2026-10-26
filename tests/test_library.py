from pathlib import Path

import ipxact
import pytest
from lxml import etree

from xactflow.diagnostics import Severity
from xactflow.library import Library

FIXTURES = Path(__file__).parent / "fixtures"


def test_scan_indexes_every_document_by_vlnv():
    library = Library.scan(FIXTURES / "basic")

    assert library.diagnostics == []
    assert library.get_component(ipxact.VLNV.parse("example.org:ip:initiator_comp:1.0")) is not None
    assert library.get_component(ipxact.VLNV.parse("example.org:ip:target_comp:1.0")) is not None
    assert library.get_design(ipxact.VLNV.parse("example.org:soc:top:1.0")) is not None
    assert (
        library.get_bus_definition(ipxact.VLNV.parse("example.org:bus:simplebus:1.0")) is not None
    )
    assert (
        library.get_abstraction_definition(ipxact.VLNV.parse("example.org:bus:simplebus_rtl:1.0"))
        is not None
    )


def test_get_returns_none_for_unknown_vlnv():
    library = Library.scan(FIXTURES / "basic")
    assert library.get_component(ipxact.VLNV.parse("example.org:ip:missing:1.0")) is None


def test_get_component_returns_none_for_wrong_document_type():
    library = Library.scan(FIXTURES / "basic")
    bus_vlnv = ipxact.VLNV.parse("example.org:bus:simplebus:1.0")
    assert library.get_component(bus_vlnv) is None
    assert library.get_bus_definition(bus_vlnv) is not None


def test_non_ipxact_xml_file_is_silently_skipped():
    """A well-formed XML file outside the IP-XACT namespace was never meant to be read by
    this library (e.g. unrelated tooling config sitting in a scanned directory), so it is
    skipped without a diagnostic rather than reported as broken.
    """
    library = Library.scan(FIXTURES / "not_ipxact")

    # the root itself is reported as holding no IP-XACT document, but the file gets nothing.
    assert [d.location for d in library.diagnostics] == [str(FIXTURES / "not_ipxact")]
    assert library.entries == {}


def test_unsupported_ipxact_document_type_is_recorded_as_a_warning_and_does_not_raise():
    """A file in the IP-XACT namespace whose root element ipxact-compiler does not support
    (e.g. ipxact:catalog) is a real gap worth surfacing, unlike a non-IP-XACT file.
    """
    library = Library.scan(FIXTURES / "broken")

    # one warning for the file itself, one for its root, from which nothing was indexed.
    assert [d.location for d in library.diagnostics] == [
        str(FIXTURES / "broken" / "unsupported_catalog.xml"),
        str(FIXTURES / "broken"),
    ]
    diagnostic = library.diagnostics[0]
    assert diagnostic.severity is Severity.WARNING
    assert diagnostic.rule_id is None


def test_duplicate_vlnv_is_recorded_as_an_scr_1_1_error():
    library = Library.scan(FIXTURES / "basic", FIXTURES / "duplicate")

    duplicates = [d for d in library.diagnostics if d.rule_id == "SCR 1.1"]
    assert len(duplicates) == 1
    assert duplicates[0].severity is Severity.ERROR
    assert duplicates[0].rule_name == "uniqueVLNV"

    # the first-scanned file wins; the real fixture (not the stub duplicate) stays indexed.
    component = library.get_component(ipxact.VLNV.parse("example.org:ip:initiator_comp:1.0"))
    assert component.bus_interfaces


_DESIGN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ipxact:design xmlns:ipxact="http://www.accellera.org/XMLSchema/IPXACT/1685-2022">
  <ipxact:vendor>example.org</ipxact:vendor>
  <ipxact:library>soc</ipxact:library>
  <ipxact:name>dup</ipxact:name>
  <ipxact:version>1.0</ipxact:version>
</ipxact:design>
"""

_DESIGN_XML_WITH_DUPLICATE_INTERFACE = """<?xml version="1.0" encoding="UTF-8"?>
<ipxact:design xmlns:ipxact="http://www.accellera.org/XMLSchema/IPXACT/1685-2022">
  <ipxact:vendor>example.org</ipxact:vendor>
  <ipxact:library>soc</ipxact:library>
  <ipxact:name>dup</ipxact:name>
  <ipxact:version>1.0</ipxact:version>
  <ipxact:interconnections>
    <ipxact:interconnection>
      <ipxact:name>conn0</ipxact:name>
      <ipxact:activeInterface componentInstanceRef="a0" busRef="bif"/>
      <ipxact:activeInterface componentInstanceRef="b0" busRef="bif"/>
    </ipxact:interconnection>
    <ipxact:interconnection>
      <ipxact:name>conn1</ipxact:name>
      <ipxact:activeInterface componentInstanceRef="a0" busRef="bif"/>
      <ipxact:activeInterface componentInstanceRef="b0" busRef="bif"/>
    </ipxact:interconnection>
  </ipxact:interconnections>
</ipxact:design>
"""


def test_duplicate_vlnv_document_still_gets_its_own_single_doc_checks(tmp_path):
    # The rejected (duplicate) document can have its own independent SCR violations; being a
    # duplicate VLNV must not suppress checking its own content.
    (tmp_path / "a.xml").write_text(_DESIGN_XML)
    (tmp_path / "b.xml").write_text(_DESIGN_XML_WITH_DUPLICATE_INTERFACE)

    library = Library.scan(tmp_path)

    assert any(d.rule_id == "SCR 1.1" for d in library.diagnostics)
    scr_2_3 = [d for d in library.diagnostics if d.rule_id == "SCR 2.3"]
    assert len(scr_2_3) == 2  # one per (instance, bus interface) pair: a0/bif and b0/bif


def test_scan_raises_on_missing_root(tmp_path):
    # rglob on a missing path yields nothing, so without this check a wrong path would look
    # like an empty library with no diagnostic at all.
    with pytest.raises(FileNotFoundError, match="does_not_exist"):
        Library.scan(FIXTURES / "basic", tmp_path / "does_not_exist")


def test_scan_raises_on_root_that_is_a_file():
    with pytest.raises(NotADirectoryError):
        Library.scan(FIXTURES / "basic" / "top_design.xml")


def test_scan_warns_on_root_without_ipxact_documents(tmp_path):
    # An empty library folder can be intended, so this is a warning and the scan goes on.
    library = Library.scan(FIXTURES / "basic", tmp_path)

    assert len(library.diagnostics) == 1
    diagnostic = library.diagnostics[0]
    assert diagnostic.severity is Severity.WARNING
    assert diagnostic.location == str(tmp_path)
    assert library.get_design(ipxact.VLNV.parse("example.org:soc:top:1.0")) is not None


_IPXACT_2014_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ipxact:component xmlns:ipxact="http://www.accellera.org/XMLSchema/IPXACT/1685-2014">
  <ipxact:vendor>example.org</ipxact:vendor>
  <ipxact:library>ip</ipxact:library>
  <ipxact:name>old</ipxact:name>
  <ipxact:version>1.0</ipxact:version>
</ipxact:component>
"""


def test_other_ipxact_version_is_skipped_with_a_warning(tmp_path):
    (tmp_path / "old.xml").write_text(_IPXACT_2014_XML)

    library = Library.scan(FIXTURES / "basic", tmp_path)

    skipped = [d for d in library.diagnostics if d.location == str(tmp_path / "old.xml")]
    assert len(skipped) == 1
    assert skipped[0].severity is Severity.WARNING
    assert "1685-2014" in skipped[0].message
    assert library.get_component(ipxact.VLNV.parse("example.org:ip:old:1.0")) is None
    # the root held no 1685-2022 document, so it is also reported as empty.
    assert any(d.location == str(tmp_path) for d in library.diagnostics)


def _component(name):
    return ipxact.Component(vlnv=ipxact.VLNV("example.org", "ip", name, "1.0"))


def test_add_indexes_an_in_memory_document():
    library = Library.scan(FIXTURES / "basic")
    component = _component("generated")

    assert library.add(component) is True

    assert library.get_component(component.vlnv) is component
    assert library.entries[component.vlnv].path is None
    assert library.diagnostics == []


def test_add_runs_single_doc_checks():
    library = Library()
    design = ipxact.parse_element(etree.fromstring(_DESIGN_XML_WITH_DUPLICATE_INTERFACE.encode()))

    library.add(design)

    assert len([d for d in library.diagnostics if d.rule_id == "SCR 2.3"]) == 2


def test_add_duplicate_vlnv_is_an_scr_1_1_error_and_keeps_the_existing_entry():
    library = Library.scan(FIXTURES / "basic")
    vlnv = ipxact.VLNV.parse("example.org:ip:initiator_comp:1.0")
    scanned = library.get_component(vlnv)

    assert library.add(ipxact.Component(vlnv=vlnv)) is False

    assert library.get_component(vlnv) is scanned
    duplicates = [d for d in library.diagnostics if d.rule_id == "SCR 1.1"]
    assert len(duplicates) == 1
    assert duplicates[0].severity is Severity.ERROR
    assert "<in-memory>" in duplicates[0].message


def test_add_with_replace_overwrites_the_existing_entry_without_a_diagnostic():
    library = Library.scan(FIXTURES / "basic")
    vlnv = ipxact.VLNV.parse("example.org:ip:initiator_comp:1.0")
    regenerated = ipxact.Component(vlnv=vlnv)

    assert library.add(regenerated, Path("initiator_comp.sv"), replace=True) is True

    assert library.get_component(vlnv) is regenerated
    assert library.entries[vlnv].path == Path("initiator_comp.sv")
    assert not any(d.rule_id == "SCR 1.1" for d in library.diagnostics)


def test_add_file_indexes_one_file():
    library = Library()
    path = FIXTURES / "basic" / "top_design.xml"

    assert library.add_file(path) is True

    vlnv = ipxact.VLNV.parse("example.org:soc:top:1.0")
    assert library.get_design(vlnv) is not None
    assert library.entries[vlnv].path == path


def test_add_file_duplicate_vlnv_is_an_scr_1_1_error():
    library = Library.scan(FIXTURES / "basic")

    assert library.add_file(FIXTURES / "basic" / "top_design.xml") is False

    assert len([d for d in library.diagnostics if d.rule_id == "SCR 1.1"]) == 1


def test_add_file_applies_the_same_namespace_filtering_as_scan(tmp_path):
    (tmp_path / "old.xml").write_text(_IPXACT_2014_XML)
    library = Library()

    assert library.add_file(tmp_path / "old.xml") is False
    assert library.add_file(FIXTURES / "not_ipxact" / "not_ipxact.xml") is False

    assert library.entries == {}
    # only the other IP-XACT version is warned about, non-IP-XACT XML is skipped silently.
    assert [d.location for d in library.diagnostics] == [str(tmp_path / "old.xml")]


def test_add_file_raises_on_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="does_not_exist.xml"):
        Library().add_file(tmp_path / "does_not_exist.xml")
