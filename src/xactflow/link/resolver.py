from __future__ import annotations

from typing import Optional

import ipxact

from .. import SCR
from ..library import Library
from .model import (
    LinkedDesign,
    LinkedInstance,
    LinkedInterconnection,
    LinkedMonitorInterconnection,
    ResolvedInterfaceEndpoint,
    ResolvedPortReference,
)


def link(
    design: ipxact.Design,
    library: Library,
    design_configuration: Optional[ipxact.DesignConfiguration] = None,
) -> LinkedDesign:
    """Resolve a Design (and optional DesignConfiguration) against a Library.

    Builds the best-effort resolved object graph first (every reference that can be resolved
    is), then runs the SCR rule registry to explain what could not be: single-doc rules run
    here against the design (and design configuration) directly, since the top-level design
    passed to this function is typically not itself part of a scanned library, then post-config
    rules run against the linked result. Callers that did get this design from a
    Library.scan already got its single-doc diagnostics from that scan; running them again here
    is deliberate, since a rule like SCR 2.3 only needs the design regardless of where it came
    from.
    """

    linked = LinkedDesign(
        vlnv=design.vlnv,
        design=design,
        library=library,
        design_configuration=design_configuration,
    )

    _resolve_instances(linked)
    _resolve_interconnections(linked)
    _resolve_monitor_interconnections(linked)
    _resolve_ad_hoc_connections(linked)

    linked.diagnostics.extend(SCR.run_single_doc_checks(design))
    if design_configuration is not None:
        linked.diagnostics.extend(SCR.run_single_doc_checks(design_configuration))
    linked.diagnostics.extend(SCR.run_post_config_checks(linked))

    return linked


def _resolve_instances(linked: LinkedDesign) -> None:
    for instance_ref in linked.design.component_instances:
        component = linked.library.get_component(instance_ref.component_ref.vlnv)
        if component is None:
            continue  # scr.rules._check_component_ref_is_component (SCR 1.9) reports why
        linked.instances[instance_ref.instance_name] = LinkedInstance(
            instance_name=instance_ref.instance_name,
            component=component,
            component_vlnv=instance_ref.component_ref.vlnv,
            source=instance_ref,
        )


def _resolve_bus_interface_endpoint(
    linked: LinkedDesign, component_instance_ref: str, bus_ref: str, source
) -> Optional[ResolvedInterfaceEndpoint]:
    instance = linked.instances.get(component_instance_ref)
    if instance is None:
        return None
    bus_interface = next(
        (bi for bi in instance.component.bus_interfaces if bi.name == bus_ref), None
    )
    if bus_interface is None:
        return None
    return ResolvedInterfaceEndpoint(instance=instance, bus_interface=bus_interface, source=source)


def _resolve_interconnections(linked: LinkedDesign) -> None:
    for interconnection in linked.design.interconnections:
        active_interfaces = [
            interconnection.active_interface,
            *interconnection.other_active_interfaces,
        ]
        endpoints = [
            _resolve_bus_interface_endpoint(
                linked, ai.component_instance_ref, ai.bus_ref, ai
            )
            for ai in active_interfaces
        ]
        # Keep whatever endpoints did resolve rather than dropping the whole interconnection:
        # scr.rules._check_active_interfaces_exist (SCR 2.1) reports each one that didn't, but
        # SCR 2.2/2.4/2.5 still need to see the ones that did, e.g. two valid-but-incompatible
        # endpoints alongside a third with an unrelated typo.
        resolved_endpoints = [endpoint for endpoint in endpoints if endpoint is not None]
        linked.interconnections.append(
            LinkedInterconnection(
                name=interconnection.name,
                endpoints=resolved_endpoints,
                hier_interfaces=list(interconnection.hier_interfaces),
                source=interconnection,
            )
        )


def _resolve_monitor_interconnections(linked: LinkedDesign) -> None:
    # No SCR rule covers monitor interconnections in this first slice (Table B.4 is not yet
    # implemented); resolution here is best-effort so the graph is complete when those rules
    # are added later, but nothing reports why a monitor endpoint failed to resolve yet.
    for monitor_interconnection in linked.design.monitor_interconnections:
        active_ref = monitor_interconnection.monitored_active_interface
        active_endpoint = _resolve_bus_interface_endpoint(
            linked, active_ref.component_instance_ref, active_ref.bus_ref, active_ref
        )
        if active_endpoint is None:
            continue
        monitor_endpoints = [
            _resolve_bus_interface_endpoint(
                linked, ref.component_instance_ref, ref.bus_ref, ref
            )
            for ref in monitor_interconnection.monitor_interfaces
        ]
        if any(endpoint is None for endpoint in monitor_endpoints):
            continue
        linked.monitor_interconnections.append(
            LinkedMonitorInterconnection(
                name=monitor_interconnection.name,
                monitored_active_interface=active_endpoint,
                monitor_interfaces=monitor_endpoints,
                source=monitor_interconnection,
            )
        )


def _resolve_ad_hoc_connections(linked: LinkedDesign) -> None:
    # Same caveat as monitor interconnections: best-effort resolution, no SCR rule (Table B.2's
    # ad hoc coverage) implemented yet to explain a reference that failed to resolve.
    for ad_hoc in linked.design.ad_hoc_connections:
        resolved = [
            reference
            for reference in (
                _resolve_internal_port_reference(linked, ref)
                for ref in ad_hoc.internal_port_references
            )
            if reference is not None
        ]
        if resolved:
            linked.ad_hoc_connections[ad_hoc.name] = resolved


def _resolve_internal_port_reference(
    linked: LinkedDesign, ref: ipxact.InternalPortReference
) -> Optional[ResolvedPortReference]:
    instance = linked.instances.get(ref.component_instance_ref)
    if instance is None or instance.component.model is None:
        return None
    port = next((p for p in instance.component.model.ports if p.name == ref.port_ref), None)
    if port is None:
        return None
    return ResolvedPortReference(instance=instance, port=port, source=ref)
