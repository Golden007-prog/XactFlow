"""Tests for the first slice of SCR rules (xactflow.SCR.rules), built from IP-XACT object
model instances constructed directly in Python rather than XML fixtures, since these are
meant to isolate one rule violation at a time.
"""

from pathlib import Path

import ipxact

from xactflow import SCR
from xactflow.link import link
from xactflow.library import Library, LibraryEntry


def _vlnv_ref(vlnv: ipxact.VLNV) -> ipxact.VLNVRef:
    return ipxact.VLNVRef(vlnv.vendor, vlnv.library, vlnv.name, vlnv.version)


def _bus_interface(name, bus_type, mode, abstraction_ref=None):
    abstraction_types = []
    if abstraction_ref is not None:
        abstraction_types = [ipxact.AbstractionType(abstraction_ref=_vlnv_ref(abstraction_ref))]
    return ipxact.BusInterface(
        name=name, bus_type=_vlnv_ref(bus_type), mode=mode, abstraction_types=abstraction_types
    )


def _component(vlnv, *bus_interfaces):
    return ipxact.Component(vlnv=vlnv, bus_interfaces=list(bus_interfaces))


def _bus_definition(vlnv, extends=None):
    return ipxact.BusDefinition(
        vlnv=vlnv,
        direct_connection=True,
        is_addressable=False,
        extends=_vlnv_ref(extends) if extends is not None else None,
    )


def _instance(name, component_vlnv):
    return ipxact.ComponentInstance(instance_name=name, component_ref=_vlnv_ref(component_vlnv))


def _active_interface(instance_name, bus_ref):
    return ipxact.ActiveInterface(component_instance_ref=instance_name, bus_ref=bus_ref)


def _interconnection(name, *active_interfaces):
    return ipxact.Interconnection(
        name=name, active_interface=active_interfaces[0], other_active_interfaces=list(active_interfaces[1:])
    )


def _design(vlnv, instances, interconnections):
    return ipxact.Design(
        vlnv=vlnv, component_instances=list(instances), interconnections=list(interconnections)
    )


def _make_library(*documents):
    library = Library()
    for document in documents:
        library.entries[document.vlnv] = LibraryEntry(
            path=Path(f"<test:{document.vlnv}>"), document=document
        )
    return library


BUS_A = ipxact.VLNV("example.org", "bus", "bus_a", "1.0")
BUS_B = ipxact.VLNV("example.org", "bus", "bus_b", "1.0")  # unrelated to BUS_A
BUS_C_EXTENDS_A = ipxact.VLNV("example.org", "bus", "bus_c", "1.0")  # extends BUS_A


def test_scr_1_2_reports_unresolvable_bus_type():
    component_vlnv = ipxact.VLNV("example.org", "ip", "orphan", "1.0")
    component = _component(component_vlnv, _bus_interface("bif", BUS_A, ipxact.InterfaceMode.INITIATOR))
    library = _make_library(component)  # note: BUS_A's busDefinition is deliberately absent

    design = _design(
        ipxact.VLNV("example.org", "soc", "top", "1.0"),
        [_instance("i0", component_vlnv)],
        [],
    )
    linked = link(design, library)

    scr_1_2 = [d for d in linked.diagnostics if d.rule_id == "SCR 1.2"]
    assert len(scr_1_2) == 1
    assert "bif" in scr_1_2[0].message


def test_scr_2_1_reports_bus_ref_typo_on_an_otherwise_resolved_instance():
    a_vlnv = ipxact.VLNV("example.org", "ip", "a", "1.0")
    b_vlnv = ipxact.VLNV("example.org", "ip", "b", "1.0")
    bus_def = _bus_definition(BUS_A)
    a = _component(a_vlnv, _bus_interface("bif", BUS_A, ipxact.InterfaceMode.INITIATOR))
    b = _component(b_vlnv, _bus_interface("bif", BUS_A, ipxact.InterfaceMode.TARGET))
    library = _make_library(bus_def, a, b)

    design = _design(
        ipxact.VLNV("example.org", "soc", "top", "1.0"),
        [_instance("a0", a_vlnv), _instance("b0", b_vlnv)],
        [_interconnection("conn0", _active_interface("a0", "bif"), _active_interface("b0", "wrong_name"))],
    )
    linked = link(design, library)

    # the interconnection keeps its one resolved endpoint (a0) rather than being dropped
    # entirely; SCR 2.1 reports the typo on b0's side.
    assert len(linked.interconnections) == 1
    resolved_names = {e.instance.instance_name for e in linked.interconnections[0].endpoints}
    assert resolved_names == {"a0"}
    scr_2_1 = [d for d in linked.diagnostics if d.rule_id == "SCR 2.1"]
    assert len(scr_2_1) == 1
    assert "wrong_name" in scr_2_1[0].message


def test_scr_2_2_reports_incompatible_bus_definitions():
    a_vlnv = ipxact.VLNV("example.org", "ip", "a", "1.0")
    b_vlnv = ipxact.VLNV("example.org", "ip", "b", "1.0")
    a = _component(a_vlnv, _bus_interface("bif", BUS_A, ipxact.InterfaceMode.INITIATOR))
    b = _component(b_vlnv, _bus_interface("bif", BUS_B, ipxact.InterfaceMode.TARGET))
    library = _make_library(_bus_definition(BUS_A), _bus_definition(BUS_B), a, b)

    design = _design(
        ipxact.VLNV("example.org", "soc", "top", "1.0"),
        [_instance("a0", a_vlnv), _instance("b0", b_vlnv)],
        [_interconnection("conn0", _active_interface("a0", "bif"), _active_interface("b0", "bif"))],
    )
    linked = link(design, library)

    assert len(linked.interconnections) == 1  # both endpoints resolved, just incompatible
    scr_2_2 = [d for d in linked.diagnostics if d.rule_id == "SCR 2.2"]
    assert len(scr_2_2) == 1


def test_scr_2_2_still_fires_when_another_endpoint_in_the_same_interconnection_fails_to_resolve():
    # A 3-endpoint interconnection where two endpoints resolve but are bus-incompatible, and a
    # third has an unrelated busRef typo: the incompatibility must still be reported, not hidden
    # behind the one broken endpoint.
    a_vlnv = ipxact.VLNV("example.org", "ip", "a", "1.0")
    b_vlnv = ipxact.VLNV("example.org", "ip", "b", "1.0")
    c_vlnv = ipxact.VLNV("example.org", "ip", "c", "1.0")
    a = _component(a_vlnv, _bus_interface("bif", BUS_A, ipxact.InterfaceMode.INITIATOR))
    b = _component(b_vlnv, _bus_interface("bif", BUS_B, ipxact.InterfaceMode.TARGET))
    c = _component(c_vlnv, _bus_interface("bif", BUS_A, ipxact.InterfaceMode.TARGET))
    library = _make_library(_bus_definition(BUS_A), _bus_definition(BUS_B), a, b, c)

    design = _design(
        ipxact.VLNV("example.org", "soc", "top", "1.0"),
        [_instance("a0", a_vlnv), _instance("b0", b_vlnv), _instance("c0", c_vlnv)],
        [
            _interconnection(
                "conn0",
                _active_interface("a0", "bif"),
                _active_interface("b0", "bif"),
                _active_interface("c0", "wrong_name"),
            )
        ],
    )
    linked = link(design, library)

    resolved_names = {e.instance.instance_name for e in linked.interconnections[0].endpoints}
    assert resolved_names == {"a0", "b0"}
    scr_2_1 = [d for d in linked.diagnostics if d.rule_id == "SCR 2.1"]
    assert len(scr_2_1) == 1
    scr_2_2 = [d for d in linked.diagnostics if d.rule_id == "SCR 2.2"]
    assert len(scr_2_2) == 1


def test_scr_2_2_allows_bus_definitions_related_by_extends():
    a_vlnv = ipxact.VLNV("example.org", "ip", "a", "1.0")
    b_vlnv = ipxact.VLNV("example.org", "ip", "b", "1.0")
    a = _component(a_vlnv, _bus_interface("bif", BUS_A, ipxact.InterfaceMode.INITIATOR))
    b = _component(b_vlnv, _bus_interface("bif", BUS_C_EXTENDS_A, ipxact.InterfaceMode.TARGET))
    library = _make_library(
        _bus_definition(BUS_A), _bus_definition(BUS_C_EXTENDS_A, extends=BUS_A), a, b
    )

    design = _design(
        ipxact.VLNV("example.org", "soc", "top", "1.0"),
        [_instance("a0", a_vlnv), _instance("b0", b_vlnv)],
        [_interconnection("conn0", _active_interface("a0", "bif"), _active_interface("b0", "bif"))],
    )
    linked = link(design, library)

    assert [d for d in linked.diagnostics if d.rule_id == "SCR 2.2"] == []


def test_scr_2_3_reports_an_interface_connected_twice_within_one_design():
    design = _design(
        ipxact.VLNV("example.org", "soc", "top", "1.0"),
        [_instance("a0", ipxact.VLNV("example.org", "ip", "a", "1.0")), _instance("b0", ipxact.VLNV("example.org", "ip", "b", "1.0"))],
        [
            _interconnection("conn0", _active_interface("a0", "bif"), _active_interface("b0", "bif")),
            _interconnection("conn1", _active_interface("a0", "bif"), _active_interface("b0", "bif2")),
        ],
    )

    diagnostics = SCR.run_single_doc_checks(design)

    scr_2_3 = [d for d in diagnostics if d.rule_id == "SCR 2.3"]
    assert len(scr_2_3) == 1
    assert "conn0" in scr_2_3[0].message and "conn1" in scr_2_3[0].message


def test_scr_2_4_reports_initiator_connected_to_initiator():
    a_vlnv = ipxact.VLNV("example.org", "ip", "a", "1.0")
    b_vlnv = ipxact.VLNV("example.org", "ip", "b", "1.0")
    a = _component(a_vlnv, _bus_interface("bif", BUS_A, ipxact.InterfaceMode.INITIATOR))
    b = _component(b_vlnv, _bus_interface("bif", BUS_A, ipxact.InterfaceMode.INITIATOR))
    library = _make_library(_bus_definition(BUS_A), a, b)

    design = _design(
        ipxact.VLNV("example.org", "soc", "top", "1.0"),
        [_instance("a0", a_vlnv), _instance("b0", b_vlnv)],
        [_interconnection("conn0", _active_interface("a0", "bif"), _active_interface("b0", "bif"))],
    )
    linked = link(design, library)

    scr_2_4 = [d for d in linked.diagnostics if d.rule_id == "SCR 2.4"]
    assert len(scr_2_4) == 1
    assert [d for d in linked.diagnostics if d.rule_id == "SCR 2.5"] == []


def test_scr_2_5_reports_mirrored_target_connected_to_something_other_than_target():
    a_vlnv = ipxact.VLNV("example.org", "ip", "a", "1.0")
    b_vlnv = ipxact.VLNV("example.org", "ip", "b", "1.0")
    a = _component(a_vlnv, _bus_interface("bif", BUS_A, ipxact.InterfaceMode.MIRRORED_TARGET))
    b = _component(b_vlnv, _bus_interface("bif", BUS_A, ipxact.InterfaceMode.INITIATOR))
    library = _make_library(_bus_definition(BUS_A), a, b)

    design = _design(
        ipxact.VLNV("example.org", "soc", "top", "1.0"),
        [_instance("a0", a_vlnv), _instance("b0", b_vlnv)],
        [_interconnection("conn0", _active_interface("a0", "bif"), _active_interface("b0", "bif"))],
    )
    linked = link(design, library)

    scr_2_5 = [d for d in linked.diagnostics if d.rule_id == "SCR 2.5"]
    assert len(scr_2_5) == 1


def test_initiator_to_target_connection_has_no_mode_diagnostics():
    a_vlnv = ipxact.VLNV("example.org", "ip", "a", "1.0")
    b_vlnv = ipxact.VLNV("example.org", "ip", "b", "1.0")
    a = _component(a_vlnv, _bus_interface("bif", BUS_A, ipxact.InterfaceMode.INITIATOR))
    b = _component(b_vlnv, _bus_interface("bif", BUS_A, ipxact.InterfaceMode.TARGET))
    library = _make_library(_bus_definition(BUS_A), a, b)

    design = _design(
        ipxact.VLNV("example.org", "soc", "top", "1.0"),
        [_instance("a0", a_vlnv), _instance("b0", b_vlnv)],
        [_interconnection("conn0", _active_interface("a0", "bif"), _active_interface("b0", "bif"))],
    )
    linked = link(design, library)

    assert linked.diagnostics == []
