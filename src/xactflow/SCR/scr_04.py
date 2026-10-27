"""IEEE 1685-2022 Annex B, Table B.4: Monitor interfaces and monitor interconnections
(6 rules, SCR 4.1-4.6).

None of these are implemented yet; every rule is registered via stub() so it is tracked and
discoverable through SCR.all_rules(). link.resolver already resolves monitor
interconnections into the linked graph; these rules would check that resolved graph.
"""

from __future__ import annotations

from .registry import stub

stub(
    id="SCR 4.1",
    table="B.4",
    name="ActiveInterfaceCondition",
    single_doc_check=False,
    post_config=False,
    description=(
        "An activeInterface or monitoredActiveInterface element shall reference an "
        "initiator, target, system, mirroredInitiator, mirroredTarget, or mirroredSystem "
        "interface."
    ),
)

stub(
    id="SCR 4.2",
    table="B.4",
    name="MonitorInterfaceCondition",
    single_doc_check=False,
    post_config=False,
    description="The monitorInterface subelements of a monitorInterconnection element shall reference a monitor bus interface.",
)

stub(
    id="SCR 4.3",
    table="B.4",
    name="MonitorModeMustMatch",
    single_doc_check=False,
    post_config=False,
    description=(
        "In a monitorInterconnection element, the value of the interfaceMode of the monitor "
        "interfaces shall match the mode of the monitoredActiveInterface. As a result, all "
        "the monitor interfaces shall have the same interface mode."
    ),
)

stub(
    id="SCR 4.4",
    table="B.4",
    name="MonitorSystemGroupMatches",
    single_doc_check=False,
    post_config=False,
    description=(
        "A monitor interface shall be connected to a system or mirroredSystem interface only "
        "if it has a group subelement and the value of this element matches the value of the "
        "group subelement of the system or mirroredSystem interface."
    ),
)

stub(
    id="SCR 4.5",
    table="B.4",
    name="InterfaceAppearsOnce",
    single_doc_check=False,
    post_config=True,
    description=(
        "A particular componentInstanceRef/busRef combination shall appear in only one "
        "monitorInterconnection element. This applies to both monitor and active interfaces; "
        "however, a single monitorInterconnection element can connect an active interface to "
        "many monitor interfaces. The same active interface can also appear in at most one "
        "interconnection element."
    ),
)

stub(
    id="SCR 4.6",
    table="B.4",
    name="MonitorPortDirRequirement",
    single_doc_check=True,
    post_config=False,
    description=(
        "All ports mapped in a busInterface with a mode of monitor shall have a direction of "
        "in for wire type ports or provides for transactional type ports."
    ),
)
