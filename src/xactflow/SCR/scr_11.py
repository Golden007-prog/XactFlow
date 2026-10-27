"""IEEE 1685-2022 Annex B, Table B.11: Hierarchy and memory maps (4 rules, SCR 11.1-11.4).

None of these are implemented yet; every rule is registered via stub() so it is tracked and
discoverable through SCR.all_rules(). Same caveat as Table B.10: these need a hierarchical
family of bus interfaces concept link.resolver does not build yet.
"""

from __future__ import annotations

from .registry import stub

stub(
    id="SCR 11.1",
    table="B.11",
    name="hierMapSameAddresses",
    single_doc_check=False,
    post_config=True,
    description="In a hierarchical family of target or mirrored-initiator bus interfaces, all addressable bus interfaces shall define the same set of addresses to be visible.",
)

stub(
    id="SCR 11.2",
    table="B.11",
    name="hierMapSameLocations",
    single_doc_check=False,
    post_config=True,
    description="For any member of a hierarchical family of target or mirrored-initiator bus interfaces, if an address resolves to a location outside the containing hierarchical family of components, that address shall reference the same location in every addressable member of the family.",
)

stub(
    id="SCR 11.3",
    table="B.11",
    name="hierMapSameProperties",
    single_doc_check=False,
    post_config=True,
    description="If any bit address is resolved to a bit within an address block by any member of a hierarchical family of target bus interfaces, all addressable members of that family shall resolve that bit address to a bit with identical behavioral properties.",
)

stub(
    id="SCR 11.4",
    table="B.11",
    name="hierCpuSameLocations",
    single_doc_check=False,
    post_config=True,
    description="For any member of a hierarchical family of initiator bus interfaces, if an address initiated by a cpu resolves to a location outside the containing hierarchical family of components, that address shall reference the same location.",
)
