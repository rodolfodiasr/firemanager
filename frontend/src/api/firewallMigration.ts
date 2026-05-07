import apiClient from "./client";
import type {
  FirewallMigration,
  FirewallMigrationCreate,
  FirewallMigrationListItem,
} from "../types/firewallMigration";

export const firewallMigrationApi = {
  list: () =>
    apiClient.get<FirewallMigrationListItem[]>("/firewall-migrations").then((r) => r.data),

  get: (id: string) =>
    apiClient.get<FirewallMigration>(`/firewall-migrations/${id}`).then((r) => r.data),

  create: (data: FirewallMigrationCreate) =>
    apiClient.post<FirewallMigration>("/firewall-migrations", data).then((r) => r.data),

  updateCommands: (id: string, commands_preview: string) =>
    apiClient.patch<FirewallMigration>(`/firewall-migrations/${id}/commands`, { commands_preview }).then((r) => r.data),

  apply: (id: string) =>
    apiClient.post<{ queued: boolean; migration_id: string }>(`/firewall-migrations/${id}/apply`, {}).then((r) => r.data),

  remove: (id: string) =>
    apiClient.delete(`/firewall-migrations/${id}`),
};
