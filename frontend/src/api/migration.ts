import apiClient from "./client";
import type {
  InterfaceAdd,
  Migration,
  MigrationCreate,
  MigrationListItem,
  PortMappingUpdate,
  RegenerateRequest,
} from "../types/migration";

export const migrationApi = {
  list: () =>
    apiClient.get<MigrationListItem[]>("/config-migrations").then((r) => r.data),

  get: (id: string) =>
    apiClient.get<Migration>(`/config-migrations/${id}`).then((r) => r.data),

  create: (data: MigrationCreate) =>
    apiClient.post<Migration>("/config-migrations", data).then((r) => r.data),

  updatePortMapping: (id: string, data: PortMappingUpdate) =>
    apiClient.patch<Migration>(`/config-migrations/${id}/port-mapping`, data).then((r) => r.data),

  updateCommands: (id: string, commands_preview: string) =>
    apiClient.patch<Migration>(`/config-migrations/${id}/commands`, { commands_preview }).then((r) => r.data),

  regenerate: (id: string, data?: RegenerateRequest) =>
    apiClient.post<{ queued: boolean; migration_id: string }>(
      `/config-migrations/${id}/regenerate`,
      data ?? {},
    ).then((r) => r.data),

  addInterface: (id: string, data: InterfaceAdd) =>
    apiClient.post<Migration>(`/config-migrations/${id}/add-interface`, data).then((r) => r.data),

  apply: (id: string) =>
    apiClient.post<{ queued: boolean; migration_id: string }>(`/config-migrations/${id}/apply`, {}).then((r) => r.data),

  retry: (id: string) =>
    apiClient.post<{ queued: boolean; migration_id: string }>(`/config-migrations/${id}/retry`, {}).then((r) => r.data),

  remove: (id: string) =>
    apiClient.delete(`/config-migrations/${id}`),
};
