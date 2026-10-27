"""IEEE 1685-2022 Annex B, Table B.10: Hierarchy (4 rules, SCR 10.1-10.4).

None of these are implemented yet; every rule is registered via stub() so it is tracked and
discoverable through SCR.all_rules(). These need a "hierarchical family of bus interfaces"
concept (bus interfaces linked across nested designs) that link.resolver does not build
yet: it links one Design flat, with no recursion into sub-designs.
"""

from __future__ import annotations

from .registry import stub

stub(
    id="SCR 10.1",
    table="B.10",
    name="HierFamilyBusIntfBusTypesMatch",
    single_doc_check=False,
    post_config=False,
    description="All members of a hierarchical family of bus interfaces shall reference the same busDefinition in their busType subelements. They need not reference the same abstraction definitions in their abstractionType elements.",
)

stub(
    id="SCR 10.2",
    table="B.10",
    name="HierFamilyBusIntfModesMatch",
    single_doc_check=False,
    post_config=False,
    description="All members of a hierarchical family of bus interfaces shall have the same interface mode (e.g. initiator, target, system).",
)

stub(
    id="SCR 10.3",
    table="B.10",
    name="HierFamilyBusIntfConnReqsMatch",
    single_doc_check=False,
    post_config=False,
    description="If any member of a hierarchical family of bus interfaces has a connectionRequired element with a value of true, they all shall have this value.",
)

stub(
    id="SCR 10.4",
    table="B.10",
    name="HierFamilyBusIntfSteeringMatch",
    single_doc_check=False,
    post_config=True,
    description="If any member of a hierarchical family of bus interfaces has a bitSteering element with a value of 1, they all shall have this value.",
)
