"""IEEE 1685-2022 Annex B, Table B.2: Interconnections (19 rules, SCR 2.1-2.19).

SCR 2.1 through SCR 2.5 are implemented, exercised by link.resolver. Every other rule
in this table is registered via stub() so it is tracked and discoverable through
SCR.all_rules(), with no check logic yet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Iterator, List, Set, Tuple

import ipxact

from ..diagnostics import Diagnostic, Severity
from .registry import rule, stub

if TYPE_CHECKING:
    from ..link.model import LinkedDesign, LinkedInstance, LinkedInterconnection, ResolvedInterfaceEndpoint


def _active_interfaces(interconnection: ipxact.Interconnection) -> Iterator[ipxact.ActiveInterface]:
    yield interconnection.active_interface
    yield from interconnection.other_active_interfaces


def _find_bus_interface(instance: "LinkedInstance", bus_ref: str):
    return next((bi for bi in instance.component.bus_interfaces if bi.name == bus_ref), None)


def _unordered_endpoint_pairs(
    interconnection: "LinkedInterconnection",
) -> Iterator[Tuple["ResolvedInterfaceEndpoint", "ResolvedInterfaceEndpoint"]]:
    endpoints = interconnection.endpoints
    for i in range(len(endpoints)):
        for j in range(i + 1, len(endpoints)):
            yield endpoints[i], endpoints[j]


def _extends_ancestors(vlnv: ipxact.VLNV, library) -> Set[ipxact.VLNV]:
    ancestors: Set[ipxact.VLNV] = set()
    current = vlnv
    while True:
        bus_definition = library.get_bus_definition(current)
        if bus_definition is None or bus_definition.extends is None:
            break
        current = bus_definition.extends.vlnv
        if current in ancestors:
            break  # a circular extends chain is SCR 1.42's problem, not this rule's
        ancestors.add(current)
    return ancestors


def _bus_definitions_compatible(a: ipxact.VLNV, b: ipxact.VLNV, library) -> bool:
    if a == b:
        return True
    return b in _extends_ancestors(a, library) or a in _extends_ancestors(b, library)


@rule(
    id="SCR 2.1",
    table="B.2",
    name="connectedIntfsMustExist",
    single_doc_check=False,
    post_config=False,
    description=(
        "In the attributes of an activeInterface element, the value of the busRef attribute "
        "shall be the name of a busInterface in the component description referenced by the "
        "VLNV of the component instance named in componentInstanceRef."
    ),
)
def _check_active_interfaces_exist(linked: "LinkedDesign") -> Iterator[Diagnostic]:
    for interconnection in linked.design.interconnections:
        for active_interface in _active_interfaces(interconnection):
            instance = linked.instances.get(active_interface.component_instance_ref)
            if instance is None:
                yield Diagnostic(
                    message=(
                        f"interconnection '{interconnection.name}' activeInterface "
                        f"componentInstanceRef '{active_interface.component_instance_ref}' "
                        f"does not resolve to a component instance"
                    ),
                    severity=Severity.ERROR,
                    location=f"{linked.vlnv}/{interconnection.name}",
                    rule_id="SCR 2.1",
                    rule_name="connectedIntfsMustExist",
                )
                continue
            if _find_bus_interface(instance, active_interface.bus_ref) is None:
                yield Diagnostic(
                    message=(
                        f"interconnection '{interconnection.name}' activeInterface busRef "
                        f"'{active_interface.bus_ref}' does not match a busInterface on "
                        f"component instance '{instance.instance_name}'"
                    ),
                    severity=Severity.ERROR,
                    location=f"{linked.vlnv}/{interconnection.name}",
                    rule_id="SCR 2.1",
                    rule_name="connectedIntfsMustExist",
                )


@rule(
    id="SCR 2.2",
    table="B.2",
    name="connectedIntfsCompat",
    single_doc_check=False,
    post_config=True,
    description=(
        "In the subelements of an interconnection, the bus interfaces referenced by all "
        "activeInterface and hierInterface subelements shall be compatible, i.e. the busType "
        "elements within the busInterface elements shall reference compatible busDefinitions."
    ),
)
def _check_interconnection_bus_compat(linked: "LinkedDesign") -> Iterator[Diagnostic]:
    for interconnection in linked.interconnections:
        for a, b in _unordered_endpoint_pairs(interconnection):
            if not _bus_definitions_compatible(
                a.bus_interface.bus_type.vlnv, b.bus_interface.bus_type.vlnv, linked.library
            ):
                yield Diagnostic(
                    message=(
                        f"interconnection '{interconnection.name}' connects incompatible bus "
                        f"definitions: {a.instance.instance_name}/{a.bus_interface.name} "
                        f"({a.bus_interface.bus_type.vlnv}) and "
                        f"{b.instance.instance_name}/{b.bus_interface.name} "
                        f"({b.bus_interface.bus_type.vlnv})"
                    ),
                    severity=Severity.ERROR,
                    location=f"{linked.vlnv}/{interconnection.name}",
                    rule_id="SCR 2.2",
                    rule_name="connectedIntfsCompat",
                )


@rule(
    id="SCR 2.3",
    table="B.2",
    name="intfConnectedOnlyOnce",
    single_doc_check=True,
    post_config=True,
    description=(
        "A particular component/bus interface combination shall appear in only one "
        "interconnection element in a design."
    ),
)
def _check_interface_connected_once(document: object) -> Iterator[Diagnostic]:
    if not isinstance(document, ipxact.Design):
        return
    seen: Dict[Tuple[str, str], List[str]] = {}
    for interconnection in document.interconnections:
        for active_interface in _active_interfaces(interconnection):
            key = (active_interface.component_instance_ref, active_interface.bus_ref)
            seen.setdefault(key, []).append(interconnection.name)
    for (instance_ref, bus_ref), interconnection_names in seen.items():
        if len(interconnection_names) > 1:
            yield Diagnostic(
                message=(
                    f"component instance '{instance_ref}' bus interface '{bus_ref}' appears "
                    f"in more than one interconnection: {', '.join(interconnection_names)}"
                ),
                severity=Severity.ERROR,
                location=f"{document.vlnv}/{instance_ref}/{bus_ref}",
                rule_id="SCR 2.3",
                rule_name="intfConnectedOnlyOnce",
            )


@rule(
    id="SCR 2.4",
    table="B.2",
    name="activeMstConnect",
    single_doc_check=False,
    post_config=False,
    description=(
        "An active interface of type initiator shall connect only to active interfaces of "
        "type target or mirrored-initiator, or hierarchical interfaces of type initiator."
    ),
)
def _check_active_initiator_connects(linked: "LinkedDesign") -> Iterator[Diagnostic]:
    allowed = {ipxact.InterfaceMode.TARGET, ipxact.InterfaceMode.MIRRORED_INITIATOR}
    for interconnection in linked.interconnections:
        for a, b in _unordered_endpoint_pairs(interconnection):
            a_mode, b_mode = a.bus_interface.mode, b.bus_interface.mode
            violated = (a_mode is ipxact.InterfaceMode.INITIATOR and b_mode not in allowed) or (
                b_mode is ipxact.InterfaceMode.INITIATOR and a_mode not in allowed
            )
            if violated:
                yield Diagnostic(
                    message=(
                        f"interconnection '{interconnection.name}' connects "
                        f"{a.instance.instance_name}/{a.bus_interface.name} (mode "
                        f"'{a_mode.value}') to {b.instance.instance_name}/{b.bus_interface.name} "
                        f"(mode '{b_mode.value}'), but an initiator interface may only connect "
                        f"to target or mirroredInitiator interfaces"
                    ),
                    severity=Severity.ERROR,
                    location=f"{linked.vlnv}/{interconnection.name}",
                    rule_id="SCR 2.4",
                    rule_name="activeMstConnect",
                )


@rule(
    id="SCR 2.5",
    table="B.2",
    name="activeMSlvConnect",
    single_doc_check=False,
    post_config=False,
    description=(
        "An active interface of type mirrored-target shall connect only to active interfaces "
        "of type target, or hierarchical interfaces of type mirrored-target."
    ),
)
def _check_active_mirrored_target_connects(
    linked: "LinkedDesign",
) -> Iterator[Diagnostic]:
    for interconnection in linked.interconnections:
        for a, b in _unordered_endpoint_pairs(interconnection):
            a_mode, b_mode = a.bus_interface.mode, b.bus_interface.mode
            violated = (
                a_mode is ipxact.InterfaceMode.MIRRORED_TARGET
                and b_mode is not ipxact.InterfaceMode.TARGET
            ) or (
                b_mode is ipxact.InterfaceMode.MIRRORED_TARGET
                and a_mode is not ipxact.InterfaceMode.TARGET
            )
            if violated:
                yield Diagnostic(
                    message=(
                        f"interconnection '{interconnection.name}' connects "
                        f"{a.instance.instance_name}/{a.bus_interface.name} (mode "
                        f"'{a_mode.value}') to {b.instance.instance_name}/{b.bus_interface.name} "
                        f"(mode '{b_mode.value}'), but a mirrored-target interface may only "
                        f"connect to target interfaces"
                    ),
                    severity=Severity.ERROR,
                    location=f"{linked.vlnv}/{interconnection.name}",
                    rule_id="SCR 2.5",
                    rule_name="activeMSlvConnect",
                )


stub(
    id="SCR 2.6",
    table="B.2",
    name="hierSlvConnect",
    single_doc_check=False,
    post_config=False,
    description=(
        "A hierarchical interface of type target shall connect only to active interfaces of "
        "type target."
    ),
)

stub(
    id="SCR 2.7",
    table="B.2",
    name="hierMMstConnect",
    single_doc_check=False,
    post_config=False,
    description=(
        "A hierarchical interface of type mirrored-initiator shall connect only to active "
        "interfaces of type mirrored-initiator."
    ),
)

stub(
    id="SCR 2.8",
    table="B.2",
    name="systemConnect",
    single_doc_check=False,
    post_config=True,
    description=(
        "An active interface of type system shall connect only to active interfaces of type "
        "mirrored-system or hierarchical interfaces of type system."
    ),
)

stub(
    id="SCR 2.9",
    table="B.2",
    name="MstSystemConnect",
    single_doc_check=False,
    post_config=True,
    description=(
        "An active interface of type mirrored-system shall connect only to active interfaces "
        "of type system or hierarchical interfaces of type mirrored-system."
    ),
)

stub(
    id="SCR 2.10",
    table="B.2",
    name="interconnectionDriver",
    single_doc_check=False,
    post_config=True,
    description=(
        "An interconnection element without system interfaces or mirrored-system interfaces "
        "shall contain one driving interface, which is an active interface referencing an "
        "initiator, a mirrored-target, or a hierarchical interface referencing a target or "
        "mirrored-initiator."
    ),
)

stub(
    id="SCR 2.11",
    table="B.2",
    name="MstToSlvBitsLAUMatch",
    single_doc_check=False,
    post_config=False,
    description=(
        "In a direct initiator-to-target connection, the value of bitsInLAU in the "
        "initiator's bus interface shall match the value of bitsInLAU in the target's bus "
        "interface."
    ),
)

stub(
    id="SCR 2.12",
    table="B.2",
    name="MstToSlvIsDirectConnect",
    single_doc_check=False,
    post_config=False,
    description=(
        "In a direct initiator-to-target connection, the busDefinitions referenced by the "
        "busInterfaces shall have a directConnection element with the value true."
    ),
)

stub(
    id="SCR 2.13",
    table="B.2",
    name="SysToMSysGroupsMatch",
    single_doc_check=False,
    post_config=False,
    description=(
        "In a connection between a system interface and a mirrored-system interface, the "
        "values of the group elements of the two bus interfaces shall be identical."
    ),
)

stub(
    id="SCR 2.14",
    table="B.2",
    name="EndianessMustMatch",
    single_doc_check=False,
    post_config=False,
    description=(
        "The endianess in all bus interfaces shall match for any interconnection using an "
        "addressable bus. If the endianess is not specified at either bus interface, it is "
        "presumed to be little endian."
    ),
)

stub(
    id="SCR 2.15",
    table="B.2",
    name="ConnectionRequired",
    single_doc_check=False,
    post_config=False,
    description=(
        "If a design contains a component with a busInterface that has a "
        "connectionRequired element with the value true, that busInterface shall be included "
        "in an interconnection of the design."
    ),
)

stub(
    id="SCR 2.16",
    table="B.2",
    name="MonIntfPathMustExist",
    single_doc_check=False,
    post_config=True,
    description=(
        "A monitorInterconnection with interfaces that contain a path attribute with a "
        "componentInstanceRef and busRef shall exist in all hierarchical views."
    ),
)

stub(
    id="SCR 2.17",
    table="B.2",
    name="broadcastConstraint",
    single_doc_check=True,
    post_config=True,
    description=(
        "An interconnection may not contain more than two total activeInterface and "
        "hierInterface elements unless the underlying bus definition has the broadcast "
        "element set to true."
    ),
)

stub(
    id="SCR 2.18",
    table="B.2",
    name="excludePortExists",
    single_doc_check=False,
    post_config=False,
    description=(
        "A physical port name referenced in an excludePort element shall match the name of a "
        "port defined in the ports list of the component."
    ),
)

stub(
    id="SCR 2.19",
    table="B.2",
    name="physicalPortExists",
    single_doc_check=True,
    post_config=False,
    description=(
        "The component abstractionType viewRef elements shall reference views such that all "
        "component ports referenced by physicalPort elements exist."
    ),
)
