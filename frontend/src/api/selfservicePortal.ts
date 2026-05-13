import api from "./axios";

export interface CatalogItem {
  id: string;
  name: string;
  description: string | null;
  category: string;
  ad_group: string | null;
  access_type: string;
  approval_required: boolean;
  icon: string | null;
  tags: string[] | null;
  is_active: boolean;
  sort_order: number;
}

export interface AccessRequest {
  id: string;
  catalog_item_id: string | null;
  item_name: string;
  requester_email: string;
  requester_name: string | null;
  business_justification: string | null;
  status: "pending" | "approved" | "rejected";
  approved_at: string | null;
  rejection_reason: string | null;
  provisioned_at: string | null;
  created_at: string;
}

export interface AdReportRow {
  display_name: string;
  sam_account_name: string;
  email: string;
  is_enabled: boolean;
  last_logon?: string | null;
  password_last_set?: string | null;
  days_since_change?: number | null;
  days_inactive?: number | null;
  job_title?: string | null;
}

const BASE = "/selfservice-portal";

export const selfservicePortalApi = {
  // Catalog
  listCatalog: (category?: string) =>
    api.get<CatalogItem[]>(`${BASE}/catalog`, { params: category ? { category } : {} }).then(r => r.data),
  createCatalogItem: (data: Partial<CatalogItem> & { name: string }) =>
    api.post<CatalogItem>(`${BASE}/catalog`, data).then(r => r.data),
  updateCatalogItem: (id: string, data: Partial<CatalogItem>) =>
    api.patch<CatalogItem>(`${BASE}/catalog/${id}`, data).then(r => r.data),
  deleteCatalogItem: (id: string) => api.delete(`${BASE}/catalog/${id}`),

  // Access requests
  listAccessRequests: (status?: string) =>
    api.get<AccessRequest[]>(`${BASE}/access-requests`, { params: status ? { status } : {} }).then(r => r.data),
  submitRequest: (data: {
    catalog_item_id: string; requester_email: string;
    requester_name?: string; business_justification?: string;
  }) => api.post<AccessRequest>(`${BASE}/access-requests`, data).then(r => r.data),
  approveRequest: (id: string) =>
    api.post<AccessRequest>(`${BASE}/access-requests/${id}/approve`).then(r => r.data),
  rejectRequest: (id: string, reason: string) =>
    api.post<AccessRequest>(`${BASE}/access-requests/${id}/reject`, { reason }).then(r => r.data),

  // Reports
  reportExpiredPasswords: (maxAgeDays = 90) =>
    api.get<AdReportRow[]>(`${BASE}/reports/expired-passwords`, { params: { max_age_days: maxAgeDays } }).then(r => r.data),
  reportInactiveAccounts: (inactiveDays = 60) =>
    api.get<AdReportRow[]>(`${BASE}/reports/inactive-accounts`, { params: { inactive_days: inactiveDays } }).then(r => r.data),
  reportAdminsWithoutMfa: () =>
    api.get<AdReportRow[]>(`${BASE}/reports/admins-without-mfa`).then(r => r.data),
  reportGroupMembers: (groupName: string) =>
    api.get<AdReportRow[]>(`${BASE}/reports/group-members`, { params: { group_name: groupName } }).then(r => r.data),
};
