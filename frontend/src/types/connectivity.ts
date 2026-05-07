export type ConnectivityStatus = "pending" | "running" | "completed" | "failed";
export type ConnectivityMode   = "single" | "pair";

export interface ConnectivityAnomalySeverity {
  type: string;
  severity: "high" | "medium" | "low";
  description: string;
  details?: Record<string, unknown>;
  _scope?: "pair";      // cross-device anomalies
  _device?: string;     // which device originated this anomaly
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

export interface SdwanService {
  name: string;
  mode: string;
  destinations: string[];
  members: string[];
  status: string;
}

export interface ConnectivityAnalysisSummary {
  id: string;
  tenant_id: string | null;
  device_id: string;
  mode: ConnectivityMode;
  device_b_id: string | null;
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
  mode: ConnectivityMode;
  device_b_id: string | null;
  status: ConnectivityStatus;

  // Dispositivo A
  routes: RouteEntry[] | null;
  bgp_peers: BgpPeer[] | null;
  ospf_neighbors: OspfNeighbor[] | null;
  sdwan_services: SdwanService[] | null;

  // Dispositivo B (apenas mode="pair")
  device_b_routes: RouteEntry[] | null;
  device_b_bgp_peers: BgpPeer[] | null;
  device_b_ospf_neighbors: OspfNeighbor[] | null;
  device_b_sdwan_services: SdwanService[] | null;

  anomalies: ConnectivityAnomalySeverity[] | null;
  ai_summary: string | null;
  ai_recommendations: string[] | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
}
