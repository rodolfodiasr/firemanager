import type { PlatformConfigKey, SetKeyPayload, TestResult } from "../types/platform_config";
import apiClient from "./client";

export const platformConfigApi = {
  list: () =>
    apiClient.get<PlatformConfigKey[]>("/platform-config").then((r) => r.data),

  set: (key: string, payload: SetKeyPayload) =>
    apiClient.put<{ status: string; key: string }>(`/platform-config/${key}`, payload).then((r) => r.data),

  clear: (key: string) =>
    apiClient.delete<{ status: string; key: string }>(`/platform-config/${key}`).then((r) => r.data),

  test: (key: string) =>
    apiClient.post<TestResult>(`/platform-config/${key}/test`).then((r) => r.data),
};
