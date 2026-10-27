from pathlib import Path

import ipxact

from xactflow.link import link
from xactflow.library import Library, LibraryEntry

FIXTURES = Path(__file__).parent / "fixtures"


def _load_top_design(library: Library) -> ipxact.Design:
    return library.get_design(ipxact.VLNV.parse("example.org:soc:top:1.0"))


def test_link_resolves_instances_and_interconnections_with_no_diagnostics():
    library = Library.scan(FIXTURES / "basic")
    design = _load_top_design(library)

    linked = link(design, library)

    assert linked.diagnostics == []
    assert set(linked.instances) == {"init0", "tgt0"}
    assert linked.instances["init0"].component_vlnv == ipxact.VLNV.parse(
        "example.org:ip:initiator_comp:1.0"
    )

    assert len(linked.interconnections) == 1
    interconnection = linked.interconnections[0]
    assert interconnection.name == "conn0"
    endpoints = {
        (endpoint.instance.instance_name, endpoint.bus_interface.name)
        for endpoint in interconnection.endpoints
    }
    assert endpoints == {("init0", "bus_if"), ("tgt0", "bus_if")}


def test_link_reports_unresolvable_component_ref():
    library = Library.scan(FIXTURES / "basic")
    design = _load_top_design(library)
    # point one instance at a VLNV that does not exist in the library
    design.component_instances[0].component_ref = ipxact.VLNVRef(
        "example.org", "ip", "does_not_exist", "1.0"
    )

    linked = link(design, library)

    assert "init0" not in linked.instances
    scr_1_9 = [d for d in linked.diagnostics if d.rule_id == "SCR 1.9"]
    assert len(scr_1_9) == 1
    assert "does_not_exist" in scr_1_9[0].message or "init0" in scr_1_9[0].message

    # the interconnection keeps whatever endpoints did resolve (here, just tgt0; init0's
    # endpoint fails since its componentRef is now broken), and SCR 2.1 reports why.
    assert len(linked.interconnections) == 1
    resolved_names = {e.instance.instance_name for e in linked.interconnections[0].endpoints}
    assert resolved_names == {"tgt0"}
    scr_2_1 = [d for d in linked.diagnostics if d.rule_id == "SCR 2.1"]
    assert len(scr_2_1) == 1


def test_scr_1_9_still_fires_when_a_duplicate_instance_name_already_resolved():
    # Two componentInstance elements sharing a name, one resolving and one not: linked
    # .instances only has room for one entry per name, so SCR 1.9's check must not use bare
    # name-presence as a stand-in for "did *this* instance_ref resolve".
    library = Library.scan(FIXTURES / "basic")
    design = _load_top_design(library)
    good_ref = design.component_instances[0].component_ref
    design.component_instances = [
        ipxact.ComponentInstance(instance_name="dup", component_ref=good_ref),
        ipxact.ComponentInstance(
            instance_name="dup",
            component_ref=ipxact.VLNVRef("example.org", "ip", "does_not_exist", "1.0"),
        ),
    ]
    design.interconnections = []

    linked = link(design, library)

    scr_1_9 = [d for d in linked.diagnostics if d.rule_id == "SCR 1.9"]
    assert len(scr_1_9) == 1
    assert "does_not_exist" in scr_1_9[0].message


def _vref(vlnv: ipxact.VLNV) -> ipxact.VLNVRef:
    return ipxact.VLNVRef(vlnv.vendor, vlnv.library, vlnv.name, vlnv.version)


def test_link_resolves_ad_hoc_connections_and_drops_unresolvable_refs():
    component_vlnv = ipxact.VLNV("example.org", "ip", "withport", "1.0")
    component = ipxact.Component(
        vlnv=component_vlnv,
        model=ipxact.Model(ports=[ipxact.Port(name="clk", wire=ipxact.WirePort(direction=ipxact.Direction.IN))]),
    )
    library = Library()
    library.entries[component.vlnv] = LibraryEntry(path=Path("<test>"), document=component)

    design = ipxact.Design(
        vlnv=ipxact.VLNV("example.org", "soc", "top", "1.0"),
        component_instances=[
            ipxact.ComponentInstance(instance_name="i0", component_ref=_vref(component_vlnv)),
            ipxact.ComponentInstance(instance_name="i1", component_ref=_vref(component_vlnv)),
        ],
        ad_hoc_connections=[
            ipxact.AdHocConnection(
                name="clk_net",
                internal_port_references=[
                    ipxact.InternalPortReference(component_instance_ref="i0", port_ref="clk"),
                    ipxact.InternalPortReference(component_instance_ref="i1", port_ref="clk"),
                    # this instance/port combination does not exist and should be silently
                    # dropped: no SCR rule covers ad hoc connections yet in this first slice.
                    ipxact.InternalPortReference(component_instance_ref="i1", port_ref="does_not_exist"),
                ],
            )
        ],
    )

    linked = link(design, library)

    assert set(linked.ad_hoc_connections) == {"clk_net"}
    resolved = linked.ad_hoc_connections["clk_net"]
    assert [(r.instance.instance_name, r.port.name) for r in resolved] == [("i0", "clk"), ("i1", "clk")]


def test_link_resolves_monitor_interconnections():
    bus_vlnv = ipxact.VLNV("example.org", "bus", "a", "1.0")
    active_vlnv = ipxact.VLNV("example.org", "ip", "a", "1.0")
    monitor_vlnv = ipxact.VLNV("example.org", "ip", "mon", "1.0")
    active_component = ipxact.Component(
        vlnv=active_vlnv,
        bus_interfaces=[ipxact.BusInterface(name="bif", bus_type=_vref(bus_vlnv), mode=ipxact.InterfaceMode.INITIATOR)],
    )
    monitor_component = ipxact.Component(
        vlnv=monitor_vlnv,
        bus_interfaces=[ipxact.BusInterface(name="mbif", bus_type=_vref(bus_vlnv), mode=ipxact.InterfaceMode.MONITOR)],
    )
    library = Library()
    for component in (active_component, monitor_component):
        library.entries[component.vlnv] = LibraryEntry(path=Path("<test>"), document=component)

    design = ipxact.Design(
        vlnv=ipxact.VLNV("example.org", "soc", "top", "1.0"),
        component_instances=[
            ipxact.ComponentInstance(instance_name="a0", component_ref=_vref(active_vlnv)),
            ipxact.ComponentInstance(instance_name="mon0", component_ref=_vref(monitor_vlnv)),
        ],
        monitor_interconnections=[
            ipxact.MonitorInterconnection(
                name="mon_conn",
                monitored_active_interface=ipxact.MonitorInterfaceRef(
                    component_instance_ref="a0", bus_ref="bif"
                ),
                monitor_interfaces=[
                    ipxact.MonitorInterfaceRef(component_instance_ref="mon0", bus_ref="mbif")
                ],
            )
        ],
    )

    linked = link(design, library)

    assert len(linked.monitor_interconnections) == 1
    monitor_interconnection = linked.monitor_interconnections[0]
    assert monitor_interconnection.monitored_active_interface.instance.instance_name == "a0"
    assert [m.instance.instance_name for m in monitor_interconnection.monitor_interfaces] == ["mon0"]
