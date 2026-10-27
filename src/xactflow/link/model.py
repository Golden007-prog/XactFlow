from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

import ipxact

from ..diagnostics import Diagnostic
from ..library import Library


@dataclass
class LinkedInstance:
    """One ipxact:componentInstance resolved to its actual Component object."""

    instance_name: str
    component: ipxact.Component
    component_vlnv: ipxact.VLNV
    source: ipxact.ComponentInstance


@dataclass
class ResolvedInterfaceEndpoint:
    """One interface endpoint (of an interconnection or a monitorInterconnection), resolved to
    its instance and bus interface."""

    instance: LinkedInstance
    bus_interface: ipxact.BusInterface
    source: Union[ipxact.ActiveInterface, ipxact.MonitorInterfaceRef]


@dataclass
class LinkedInterconnection:
    """One ipxact:interconnection with every active interface endpoint resolved.

    hier_interfaces are left as-is (unresolved): they refer to a bus interface exposed by this
    design one level up, which only makes sense in the context of a parent design XactFlow does
    not have when linking this design on its own.
    """

    name: str
    endpoints: List[ResolvedInterfaceEndpoint] = field(default_factory=list)
    hier_interfaces: List[ipxact.HierInterface] = field(default_factory=list)
    source: Optional[ipxact.Interconnection] = None


@dataclass
class LinkedMonitorInterconnection:
    """One ipxact:monitorInterconnection with its active and monitor endpoints resolved."""

    name: str
    monitored_active_interface: ResolvedInterfaceEndpoint
    monitor_interfaces: List[ResolvedInterfaceEndpoint] = field(default_factory=list)
    source: Optional[ipxact.MonitorInterconnection] = None


@dataclass
class ResolvedPortReference:
    """One ipxact:internalPortReference resolved to its instance and physical Port."""

    instance: LinkedInstance
    port: ipxact.Port
    source: ipxact.InternalPortReference


@dataclass
class LinkedDesign:
    """The result of resolving one Design (and optional DesignConfiguration) against a Library.

    Every reference that could be resolved now points at the real object instead of a VLNV or
    name string. References that could not be resolved are simply absent here;
    scr.runner.run_post_config_checks(linked) is what explains why, by comparing this
    against the raw design in the `design` field.
    """

    vlnv: ipxact.VLNV
    design: ipxact.Design
    library: Library
    instances: Dict[str, LinkedInstance] = field(default_factory=dict)
    interconnections: List[LinkedInterconnection] = field(default_factory=list)
    monitor_interconnections: List[LinkedMonitorInterconnection] = field(default_factory=list)
    ad_hoc_connections: Dict[str, List[ResolvedPortReference]] = field(default_factory=dict)
    design_configuration: Optional[ipxact.DesignConfiguration] = None
    diagnostics: List[Diagnostic] = field(default_factory=list)
