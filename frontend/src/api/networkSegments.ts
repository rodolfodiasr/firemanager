import apiClient from "./client";

export interface DeviceInSegment {
  id: string;
  name: string;
  vendor: string;
  category: string;
}

export interface NetworkSegmentRead {
  id: string;
  tenant_id: string;
  created_by: string | null;
  name: string;
  description: string | null;
  cidr: string | null;
  device_count: number;
  created_at: string;
  updated_at: string;
}

export interface NetworkSegmentDetail extends NetworkSegmentRead {
  devices: DeviceInSegment[];
}

export interface NetworkSegmentCreate {
  name: string;
  description?: string;
  cidr?: string;
  device_ids?: string[];
}

export interface NetworkSegmentUpdate {
  name?: string;
  description?: string;
  cidr?: string;
  device_ids?: string[];
}

export interface SegmentAnalysisEntry {
  device_id: string;
  device_name: string;
  analysis_id: string;
}

export interface SegmentAnalysisResult {
  segment_name: string;
  device_count: number;
  analyses: SegmentAnalysisEntry[];
}

export const networkSegmentsApi = {
  list: () =>
    apiClient.get<NetworkSegmentRead[]>("/network-segments").then((r) => r.data),

  create: (data: NetworkSegmentCreate) =>
    apiClient.post<NetworkSegmentDetail>("/network-segments", data).then((r) => r.data),

  get: (id: string) =>
    apiClient.get<NetworkSegmentDetail>(`/network-segments/${id}`).then((r) => r.data),

  update: (id: string, data: NetworkSegmentUpdate) =>
    apiClient.put<NetworkSegmentDetail>(`/network-segments/${id}`, data).then((r) => r.data),

  remove: (id: string) =>
    apiClient.delete(`/network-segments/${id}`),

  analyze: (id: string) =>
    apiClient
      .post<SegmentAnalysisResult>(`/network-segments/${id}/analyze`)
      .then((r) => r.data),
};
