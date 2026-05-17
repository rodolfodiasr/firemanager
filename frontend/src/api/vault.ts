import apiClient from "./client";

export type SecretType = "api_key" | "password" | "token" | "oauth2" | "certificate";

export interface VaultSecret {
  id: string;
  name: string;
  type: SecretType;
  description: string | null;
  references: string[];
  created_at: string;
  last_rotated: string | null;
  expires_at: string | null;
}

export interface VaultSecretCreate {
  name: string;
  type: SecretType;
  value: string;
  description?: string;
  expires_at?: string;
}

export interface VaultAuditEntry {
  id: string;
  secret_id: string;
  secret_name: string;
  action: "created" | "rotated" | "deleted" | "accessed";
  actor_name: string;
  actor_email: string;
  created_at: string;
}

export const vaultApi = {
  list: () =>
    apiClient.get<VaultSecret[]>("/vault/secrets").then((r) => r.data),

  create: (data: VaultSecretCreate) =>
    apiClient.post<VaultSecret>("/vault/secrets", data).then((r) => r.data),

  rotate: (id: string, newValue: string) =>
    apiClient.patch<VaultSecret>(`/vault/secrets/${id}/rotate`, { value: newValue }).then((r) => r.data),

  delete: (id: string) =>
    apiClient.delete(`/vault/secrets/${id}`),

  listAudit: () =>
    apiClient.get<VaultAuditEntry[]>("/vault/audit").then((r) => r.data),
};
