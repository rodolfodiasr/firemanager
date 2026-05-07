"""Pydantic schemas for Fase 18 — Network Connectivity Analysis."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class RouteEntry(BaseModel):
    destination: str
    prefix_len:  int
    next_hop:    str
    interface:   str | None = None
    protocol:    str        = "static"   # static, ospf, bgp, connected
    distance:    int        = 0
    metric:      int        = 0
    active:      bool       = True


class BgpPeer(BaseModel):
    peer_ip:  str
    asn:      str | None = None
    state:    str        = "unknown"
    uptime:   str | None = None
    prefixes_received: int = 0


class OspfNeighbor(BaseModel):
    neighbor_id: str
    state:       str        = "unknown"
    interface:   str | None = None
    address:     str | None = None


class ConnectivityAnomaly(BaseModel):
    type:        str   # no_default_route, static_dynamic_conflict, redundant_no_failover,
                       # unreachable_nexthop, bgp_not_established, ospf_not_full
    severity:    str   # high, medium, low
    description: str
    details:     dict[str, Any] | None = None


class ConnectivityAnalysisCreate(BaseModel):
    device_id: str


class ConnectivityAnalysisSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:           str
    tenant_id:    str | None
    device_id:    str
    status:       str
    anomaly_count: int = 0
    route_count:   int = 0
    created_at:   str
    completed_at: str | None = None
    error:        str | None = None


class ConnectivityAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                 str
    tenant_id:          str | None
    device_id:          str
    status:             str
    routes:             list[dict] | None = None
    bgp_peers:          list[dict] | None = None
    ospf_neighbors:     list[dict] | None = None
    sdwan_services:     list[dict] | None = None
    anomalies:          list[dict] | None = None
    ai_summary:         str | None = None
    ai_recommendations: list[str] | None = None
    error:              str | None = None
    created_at:         str
    completed_at:       str | None = None
