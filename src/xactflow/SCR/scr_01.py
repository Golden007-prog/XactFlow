"""IEEE 1685-2022 Annex B, Table B.1: Cross-references and VLNVs (43 rules, SCR 1.1-1.43).

SCR 1.2 and SCR 1.9 are implemented, exercised by elaborate.resolver. Every other rule in
this table is registered via stub() so it is tracked and discoverable through
SCR.all_rules(), with no check logic yet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from ..diagnostics import Diagnostic, Severity
from .registry import rule, stub

if TYPE_CHECKING:
    from ..elaborate.model import ElaboratedDesign


stub(
    id="SCR 1.1",
    table="B.1",
    name="uniqueVLNV",
    single_doc_check=False,
    post_config=False,
    description=(
        "Every IP-XACT document visible to a tool at one time shall have a unique VLNV. "
        "Enforced separately in xactflow.library.Library.add, which every document indexed in "
        "a library goes through, since detecting a duplicate needs the whole set at once; not "
        "expressible as a single-document or single-elaborated-design check, so this entry "
        "exists only for discoverability via SCR.all_rules()."
    ),
)


@rule(
    id="SCR 1.9",
    table="B.1",
    name="compRefVLNVisComp",
    single_doc_check=False,
    post_config=False,
    description=(
        "The VLNV in a componentInstanceRef element in a design shall be a reference to a "
        "component."
    ),
)
def _check_component_ref_is_component(elaborated: "ElaboratedDesign") -> Iterator[Diagnostic]:
    for instance_ref in elaborated.design.component_instances:
        resolved = elaborated.instances.get(instance_ref.instance_name)
        # Identity, not just name presence: two componentInstance elements can share a name,
        # elaborated.instances only has room for one entry per name.
        if resolved is not None and resolved.source is instance_ref:
            continue
        vlnv = instance_ref.component_ref.vlnv
        existing = elaborated.library.get(vlnv)
        if existing is None:
            detail = f"no document with VLNV {vlnv} was found in the library"
        else:
            detail = f"VLNV {vlnv} resolves to a {type(existing).__name__}, not a component"
        yield Diagnostic(
            message=(
                f"componentInstance '{instance_ref.instance_name}' componentRef does not "
                f"resolve to a component: {detail}"
            ),
            severity=Severity.ERROR,
            location=f"{elaborated.vlnv}/{instance_ref.instance_name}",
            rule_id="SCR 1.9",
            rule_name="compRefVLNVisComp",
        )


@rule(
    id="SCR 1.2",
    table="B.1",
    name="anyVLNVRefMustExist",
    single_doc_check=False,
    post_config=False,
    description=(
        "Any VLNV in an IP-XACT document used to reference another IP-XACT document shall "
        "precisely match the identifying VLNV of an existing IP-XACT document. Checked here "
        "for the busType and abstractionRef of every resolved instance's bus interfaces."
    ),
)
def _check_bus_interface_vlnv_refs_exist(elaborated: "ElaboratedDesign") -> Iterator[Diagnostic]:
    for instance in elaborated.instances.values():
        for bus_interface in instance.component.bus_interfaces:
            bus_vlnv = bus_interface.bus_type.vlnv
            if elaborated.library.get_bus_definition(bus_vlnv) is None:
                yield Diagnostic(
                    message=(
                        f"busInterface '{bus_interface.name}' busType references VLNV "
                        f"{bus_vlnv}, which does not resolve to a busDefinition in the library"
                    ),
                    severity=Severity.ERROR,
                    location=f"{instance.instance_name}/{bus_interface.name}",
                    rule_id="SCR 1.2",
                    rule_name="anyVLNVRefMustExist",
                )
            for abstraction_type in bus_interface.abstraction_types:
                abstraction_vlnv = abstraction_type.abstraction_ref.vlnv
                if elaborated.library.get_abstraction_definition(abstraction_vlnv) is None:
                    yield Diagnostic(
                        message=(
                            f"busInterface '{bus_interface.name}' abstractionRef references "
                            f"VLNV {abstraction_vlnv}, which does not resolve to an "
                            f"abstractionDefinition in the library"
                        ),
                        severity=Severity.ERROR,
                        location=f"{instance.instance_name}/{bus_interface.name}",
                        rule_id="SCR 1.2",
                        rule_name="anyVLNVRefMustExist",
                    )


stub(
    id="SCR 1.3",
    table="B.1",
    name="busDefExtendsVLNVIsBusDef",
    single_doc_check=False,
    post_config=False,
    description="The VLNV in an extends element in a bus definition shall be a reference to a busDefinition.",
)

stub(
    id="SCR 1.4",
    table="B.1",
    name="busTypeVLNVIsBusDef",
    single_doc_check=False,
    post_config=False,
    description=(
        "The VLNV in a busType element in a bus interface or abstraction definition shall be a "
        "reference to a busDefinition."
    ),
)

stub(
    id="SCR 1.5",
    table="B.1",
    name="designRefVLNVIsDesign",
    single_doc_check=False,
    post_config=False,
    description=(
        "The VLNV in a designRef element in a designConfiguration or designInstantiation "
        "element in a component shall be a reference to a design."
    ),
)

stub(
    id="SCR 1.6",
    table="B.1",
    name="designCfgRefVLNVisDesignCfg",
    single_doc_check=False,
    post_config=False,
    description=(
        "The VLNV in a designConfigurationRef element in a designConfigurationInstantiation "
        "element in a component shall be a reference to a designConfiguration."
    ),
)

stub(
    id="SCR 1.7",
    table="B.1",
    name="cfgChainRefVLNVIsGenChain",
    single_doc_check=False,
    post_config=False,
    description=(
        "The VLNV in a generatorChainRef element in a designConfiguration shall be a "
        "reference to a generator chain."
    ),
)

stub(
    id="SCR 1.8",
    table="B.1",
    name="selChainRefVLNVIsGenChain",
    single_doc_check=False,
    post_config=False,
    description=(
        "The VLNV in a generatorChainRef subelement of the generatorChainSelector element in "
        "a generator chain shall be a reference to a generator chain."
    ),
)

stub(
    id="SCR 1.10",
    table="B.1",
    name="legalTopDocTypes",
    single_doc_check=True,
    post_config=False,
    description=(
        "The XML document element of an IP-XACT document shall be an abstractor, "
        "abstractionDefinition, busDefinition, component, design, designConfiguration, "
        "generatorChain, typeDefinitions, or catalog element."
    ),
)

stub(
    id="SCR 1.11",
    table="B.1",
    name="absTypeVLNVIsAbsDef",
    single_doc_check=False,
    post_config=False,
    description=(
        "The VLNV in an abstractionType element in a component or abstractor shall reference "
        "an abstractionDefinition."
    ),
)

stub(
    id="SCR 1.12",
    table="B.1",
    name="busTypeMustMatch",
    single_doc_check=False,
    post_config=False,
    description=(
        "If a bus interface contains an abstractionType subelement, the abstraction "
        "definition's busType element and the bus interface's busType element shall "
        "reference the same bus definition."
    ),
)

stub(
    id="SCR 1.13",
    table="B.1",
    name="absRefVLNVIsAbstractor",
    single_doc_check=False,
    post_config=False,
    description="The VLNV in an abstractorRef in a designConfiguration shall reference an abstractor.",
)

stub(
    id="SCR 1.14",
    table="B.1",
    name="absDefExtendsVLNVIsAbsDef",
    single_doc_check=False,
    post_config=False,
    description=(
        "The VLNV in an extends element in an abstraction definition shall be a reference to "
        "an abstraction definition."
    ),
)

stub(
    id="SCR 1.15",
    table="B.1",
    name="CatalogVLNVReference",
    single_doc_check=False,
    post_config=False,
    description=(
        "The VLNV within an ipxactFile/vlnv element in a catalog shall refer to an IP-XACT "
        "file whose file type matches the container of the ipxactFile/vlnv element."
    ),
)

stub(
    id="SCR 1.16",
    table="B.1",
    name="viewDesignConfigurationInstantiationReference",
    single_doc_check=False,
    post_config=True,
    description=(
        "If a view contains a designConfigurationInstantiationRef and does not also contain a "
        "designInstantiationRef, then the referenced design configuration document shall "
        "contain a designRef element."
    ),
)

stub(
    id="SCR 1.17",
    table="B.1",
    name="DesignRefsMatch",
    single_doc_check=False,
    post_config=True,
    description=(
        "If a view contains a designConfigurationInstantiationRef and a "
        "designInstantiationRef and the design configuration contains a designRef, then the "
        "referenced design VLNVs shall match."
    ),
)

stub(
    id="SCR 1.18",
    table="B.1",
    name="typeDefinitionsRefVLNVisTypeDefinition",
    single_doc_check=False,
    post_config=False,
    description=(
        "The VLNV in a typeDefinitionsRef element in a component or typeDefinition shall be a "
        "reference to a typeDefinitions element."
    ),
)

stub(
    id="SCR 1.19",
    table="B.1",
    name="externalModeReference",
    single_doc_check=False,
    post_config=False,
    description=(
        "The modeRef attribute in an externalModeReference element shall reference a mode "
        "that exists in the typeDefinitions referenced in the typeDefinitionsRef element."
    ),
)

stub(
    id="SCR 1.20",
    table="B.1",
    name="modeReference",
    single_doc_check=True,
    post_config=False,
    description=(
        "The modeRef attribute in a modeReference element shall reference a mode that exists "
        "in the encapsulating component or typeDefinitions."
    ),
)

stub(
    id="SCR 1.21",
    table="B.1",
    name="externalResetTypeReference",
    single_doc_check=False,
    post_config=False,
    description=(
        "The resetTypeRef attribute in an externalResetTypeReference element shall reference "
        "a resetType that exists in the typeDefinitions referenced in the typeDefinitionsRef "
        "element."
    ),
)

stub(
    id="SCR 1.22",
    table="B.1",
    name="resetTypeReference",
    single_doc_check=True,
    post_config=False,
    description=(
        "The resetTypeRef attribute in a resetTypeReference element shall reference a "
        "resetType that exists in the encapsulating component or typeDefinitions."
    ),
)

stub(
    id="SCR 1.23",
    table="B.1",
    name="externalViewReference",
    single_doc_check=False,
    post_config=False,
    description=(
        "The viewRef attribute in an externalViewReference element shall reference a view "
        "that exists in the typeDefinitions referenced in the typeDefinitionsRef element."
    ),
)

stub(
    id="SCR 1.24",
    table="B.1",
    name="viewReference",
    single_doc_check=True,
    post_config=False,
    description=(
        "The viewRef attribute in a viewReference element shall reference a view that exists "
        "in the encapsulating component or typeDefinitions."
    ),
)

stub(
    id="SCR 1.25",
    table="B.1",
    name="fieldAccessPolicyDefinitionNameRefMustExist",
    single_doc_check=False,
    post_config=False,
    description=(
        "A fieldAccessPolicyDefinitionRef shall reference a name of a "
        "fieldAccessPolicyDefinition in the referenced typeDefinitions."
    ),
)

stub(
    id="SCR 1.26",
    table="B.1",
    name="enumerationDefinitionNameRefMustExist",
    single_doc_check=False,
    post_config=False,
    description=(
        "An enumerationDefinitionRef shall reference a name of an enumerationDefinition in "
        "the referenced typeDefinitions."
    ),
)

stub(
    id="SCR 1.27",
    table="B.1",
    name="fieldDefinitionNameRefMustExist",
    single_doc_check=False,
    post_config=False,
    description=(
        "A fieldDefinitionRef shall reference a name of a fieldDefinition in the referenced "
        "typeDefinitions."
    ),
)

stub(
    id="SCR 1.28",
    table="B.1",
    name="registerDefinitionNameRefMustExist",
    single_doc_check=False,
    post_config=False,
    description=(
        "A registerDefinitionRef shall reference a name of a registerDefinition in the "
        "referenced typeDefinitions."
    ),
)

stub(
    id="SCR 1.29",
    table="B.1",
    name="registerFileDefinitionNameRefMustExist",
    single_doc_check=False,
    post_config=False,
    description=(
        "A registerFileDefinitionRef shall reference a name of a registerFileDefinition in "
        "the referenced typeDefinitions."
    ),
)

stub(
    id="SCR 1.30",
    table="B.1",
    name="addressBlockDefinitionNameRefMustExist",
    single_doc_check=False,
    post_config=False,
    description=(
        "An addressBlockDefinitionRef shall reference a name of an addressBlockDefinition in "
        "the referenced typeDefinitions."
    ),
)

stub(
    id="SCR 1.31",
    table="B.1",
    name="memoryMapDefinitionNameRefMustExist",
    single_doc_check=False,
    post_config=False,
    description=(
        "A memoryMapDefinitionRef shall reference a name of a memoryMapDefinition in the "
        "referenced typeDefinition."
    ),
)

stub(
    id="SCR 1.32",
    table="B.1",
    name="memoryRemapDefinitionNameRefMustExist",
    single_doc_check=False,
    post_config=False,
    description=(
        "A remapDefinitionRef shall reference a name of a memoryRemapDefinition in the "
        "referenced typeDefinition."
    ),
)

stub(
    id="SCR 1.33",
    table="B.1",
    name="modesMustBeLinked",
    single_doc_check=False,
    post_config=False,
    description=(
        "All modeRef element values in an element referenced by a fieldDefinitionRef, "
        "registerDefinitionRef, registerFileDefinitionRef, addressBlockDefinitionRef, "
        "bankDefinitionRef, memoryMapDefinitionRef, or memoryRemapDefinitionRef shall occur "
        "in externalModeReference element values of the corresponding externalTypeDefinitions "
        "element."
    ),
)

stub(
    id="SCR 1.34",
    table="B.1",
    name="resetTypesMustBeLinked",
    single_doc_check=False,
    post_config=False,
    description=(
        "All resetTypeRef element values in an element referenced by a fieldDefinitionRef, "
        "registerDefinitionRef, registerFileDefinitionRef, addressBlockDefinitionRef, "
        "bankDefinitionRef, memoryMapDefinitionRef, or memoryRemapDefinitionRef shall occur "
        "in externalResetTypeReference element values of the corresponding "
        "externalTypeDefinitions element."
    ),
)

stub(
    id="SCR 1.35",
    table="B.1",
    name="viewsMustBeLinked",
    single_doc_check=False,
    post_config=False,
    description=(
        "All view element values in an element referenced by a registerDefinitionRef, "
        "registerFileDefinitionRef, addressBlockDefinitionRef, bankDefinitionRef, "
        "memoryMapDefinitionRef, or memoryRemapDefinitionRef shall occur in "
        "externalViewReference element values of the corresponding externalTypeDefinitions "
        "element."
    ),
)

stub(
    id="SCR 1.36",
    table="B.1",
    name="fieldSliceReference",
    single_doc_check=False,
    post_config=True,
    description=(
        "A fieldSlice in a fieldMap or mode shall reference an existing slice of a field in "
        "the encapsulating component."
    ),
)

stub(
    id="SCR 1.37",
    table="B.1",
    name="portSliceReference",
    single_doc_check=False,
    post_config=True,
    description=(
        "A portSlice in a fieldMap or mode shall reference an existing slice of a port in the "
        "encapsulating component."
    ),
)

stub(
    id="SCR 1.38",
    table="B.1",
    name="PowerDomainIntRef",
    single_doc_check=False,
    post_config=False,
    description=(
        "In a powerDomainLink, the externalPowerDomainReference attribute shall reference a "
        "powerDomain defined on the component referenced by this instance."
    ),
)

stub(
    id="SCR 1.39",
    table="B.1",
    name="PowerDomainExtRef",
    single_doc_check=False,
    post_config=False,
    description=(
        "In a powerDomainLink, the externalPowerDomainRef attribute (resolved expression) "
        "shall reference a powerDomain defined on the component referencing this design, or "
        "referencing a designConfig that references this design."
    ),
)

stub(
    id="SCR 1.40",
    table="B.1",
    name="fieldMapNoAlias",
    single_doc_check=False,
    post_config=False,
    description="A fieldMap shall not reference a field that is an alias of another field.",
)

stub(
    id="SCR 1.41",
    table="B.1",
    name="NoPowDomRefInAbsDefPort",
    single_doc_check=True,
    post_config=False,
    description=(
        "An abstraction definition port shall not contain an isPowerEn qualifier with a "
        "powerDomainRef attribute."
    ),
)

stub(
    id="SCR 1.42",
    table="B.1",
    name="nonCircularVLNVReferences",
    single_doc_check=False,
    post_config=True,
    description="VLNV references in a design hierarchy shall not lead to circular referencing.",
)

stub(
    id="SCR 1.43",
    table="B.1",
    name="fieldReferenceArrayIndices",
    single_doc_check=False,
    post_config=False,
    description=(
        "In a fieldReferenceGroup, an indices element shall contain an index for each array "
        "dimension or shall not be present to reference the whole array; the total number of "
        "field elements referenced shall match the total number of field elements in the "
        "referencing field so both can be linearized and paired by linear index value."
    ),
)
