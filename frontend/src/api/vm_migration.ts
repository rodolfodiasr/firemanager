import apiClient from "./client";
import type { VmHypervisor, VmInventoryItem, MigrationRunbook } from "../types/vm_migration";

export const vmMigrationApi = {
  listHypervisors: () => apiClient.get<VmHypervisor[]>("/vm-migration/hypervisors").then(r => r.data),
  createHypervisor: (data: Partial<VmHypervisor> & { credentials: Record<string, string> }) =>
    apiClient.post<VmHypervisor>("/vm-migration/hypervisors", data).then(r => r.data),
  deleteHypervisor: (id: string) => apiClient.delete(`/vm-migration/hypervisors/${id}`),
  testHypervisor: (id: string) => apiClient.post<{ ok: boolean; error?: string }>(`/vm-migration/hypervisors/${id}/test`).then(r => r.data),
  syncHypervisor: (id: string) => apiClient.post<{ count: number }>(`/vm-migration/hypervisors/${id}/sync`).then(r => r.data),
  listVms: (hypervisorId?: string) =>
    apiClient.get<VmInventoryItem[]>("/vm-migration/inventory", { params: hypervisorId ? { hypervisor_id: hypervisorId } : {} }).then(r => r.data),
  listRunbooks: () => apiClient.get<MigrationRunbook[]>("/vm-migration/runbooks").then(r => r.data),
  createRunbook: (data: { title: string; vm_ids: string[]; source_hypervisor_id?: string; target_hypervisor_id?: string }) =>
    apiClient.post<MigrationRunbook>("/vm-migration/runbooks", data).then(r => r.data),
  getRunbook: (id: string) => apiClient.get<MigrationRunbook>(`/vm-migration/runbooks/${id}`).then(r => r.data),
};
