import axios from "axios";

const api = axios.create({ baseURL: "/api" });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export interface LLMConfig {
  id: string;
  tenant_id: string | null;
  provider: string;
  display_name: string;
  model_name: string;
  api_base_url: string | null;
  has_key: boolean;
  is_enabled: boolean;
  is_default: boolean;
  priority: number;
  no_train_flag: boolean;
  scope: "global" | "tenant";
  created_at: string;
  updated_at: string;
}

export interface LLMProviderMeta {
  provider: string;
  label: string;
  default_model: string;
  needs_key: boolean;
  local: boolean;
  base_url: string | null;
}

export interface LLMConfigCreate {
  provider: string;
  model_name: string;
  api_key?: string | null;
  api_base_url?: string | null;
  is_default?: boolean;
  no_train_flag?: boolean;
}

export interface LLMConfigUpdate {
  model_name?: string | null;
  api_key?: string | null;
  api_base_url?: string | null;
  is_default?: boolean | null;
  is_enabled?: boolean | null;
  no_train_flag?: boolean | null;
}

export interface TestResult {
  ok: boolean;
  message: string;
  latency_ms: number;
}

// ── Metadados de providers (público) ─────────────────────────────────────────

export const llmProvidersApi = {
  listMeta: () =>
    api.get<LLMProviderMeta[]>("/llm-configs/providers").then((r) => r.data),
};

// ── Admin — config global (super admin) ──────────────────────────────────────

export const adminLlmConfigsApi = {
  list: () =>
    api.get<LLMConfig[]>("/admin/llm-configs").then((r) => r.data),

  create: (data: LLMConfigCreate) =>
    api.post<LLMConfig>("/admin/llm-configs", data).then((r) => r.data),

  update: (id: string, data: LLMConfigUpdate) =>
    api.put<LLMConfig>(`/admin/llm-configs/${id}`, data).then((r) => r.data),

  delete: (id: string) =>
    api.delete(`/admin/llm-configs/${id}`).then((r) => r.data),

  test: (id: string) =>
    api.post<TestResult>(`/admin/llm-configs/${id}/test`).then((r) => r.data),
};

// ── Tenant — config por tenant ────────────────────────────────────────────────

export const tenantLlmConfigsApi = {
  list: () =>
    api.get<LLMConfig[]>("/llm-configs").then((r) => r.data),

  create: (data: LLMConfigCreate) =>
    api.post<LLMConfig>("/llm-configs", data).then((r) => r.data),

  update: (id: string, data: LLMConfigUpdate) =>
    api.put<LLMConfig>(`/llm-configs/${id}`, data).then((r) => r.data),

  delete: (id: string) =>
    api.delete(`/llm-configs/${id}`).then((r) => r.data),

  test: (id: string) =>
    api.post<TestResult>(`/llm-configs/${id}/test`).then((r) => r.data),

  effective: () =>
    api.get<{ provider: string; resolved: boolean }>("/llm-configs/effective").then((r) => r.data),
};
