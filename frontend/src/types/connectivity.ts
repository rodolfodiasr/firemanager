export type ConnectivityStatus = "pending" | "running" | "completed" | "failed";

export interface ConnectivityAnomalySeverity {
  type: string;
  severity: "high" | "medium" | "low";
  description: string;
  details?: Record<string, unknown>;
}

export interface RouteEntry {
  destination: string;
  prefix_len: number;
  next_hop: string;
  interface?: string;
  protocol: string;
  active: boolean;
}

export interface BgpPeer {
  peer_ip: string;
  asn?: string;
  state: string;
  uptime?: string;
  prefixes_received: number;
}

export interface OspfNeighbor {
  neighbor_id: string;
  state: string;
  interface?: string;
  address?: string;
}

export interface ConnectivityAnalysisSummary {
  id: string;
  tenant_id: string | null;
  device_id: string;
  status: ConnectivityStatus;
  anomaly_count: number;
  route_count: number;
  created_at: string;
  completed_at: string | null;
  error: string | null;
}

export interface ConnectivityAnalysisRead {
  id: string;
  tenant_id: string | null;
  device_id: string;
  status: ConnectivityStatus;
  routes: RouteEntry[] | null;
  bgp_peers: BgpPeer[] | null;
  ospf_neighbors: OspfNeighbor[] | null;
  sdwan_services: unknown[] | null;
  anomalies: ConnectivityAnomalySeverity[] | null;
  ai_summary: string | null;
  ai_recommendations: string[] | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
}
