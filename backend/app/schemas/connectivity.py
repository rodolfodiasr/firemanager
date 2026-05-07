"""Pydantic schemas for Fase 18 — Network Connectivity Analysis."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RouteEntry(BaseModel):
    destination: str
    prefix_len:  int
    next_hop:    str
    interface:   str | None = None
    protocol:    str        = "static"
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
    type:        str
    severity:    str
    description: str
    details:     dict[str, Any] | None = None


class PairAnalysisRequest(BaseModel):
    device_b_id: UUID


class ConnectivityAnalysisSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:            str
    tenant_id:     str | None
    device_id:     str
    mode:          str = "single"
    device_b_id:   str | None = None
    status:        str
    anomaly_count: int = 0
    route_count:   int = 0
    created_at:    str
    completed_at:  str | None = None
    error:         str | None = None


class ConnectivityAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:           str
    tenant_id:    str | None
    device_id:    str
    mode:         str = "single"
    device_b_id:  str | None = None
    status:       str

    # Dispositivo A (ou único em modo single)
    routes:             list[dict] | None = None
    bgp_peers:          list[dict] | None = None
    ospf_neighbors:     list[dict] | None = None
    sdwan_services:     list[dict] | None = None

    # Dispositivo B — apenas mode="pair"
    device_b_routes:          list[dict] | None = None
    device_b_bgp_peers:       list[dict] | None = None
    device_b_ospf_neighbors:  list[dict] | None = None
    device_b_sdwan_services:  list[dict] | None = None

    anomalies:          list[dict] | None = None
    ai_summary:         str | None = None
    ai_recommendations: list[str] | None = None
    error:              str | None = None
    created_at:         str
    completed_at:       str | None = None
