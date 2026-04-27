import apiClient from "./client";

export interface InviteInfo {
  token: string;
  email: string;
  tenant_id: string;
  tenant_name: string;
  role: string;
  expires_at: string;
}

export interface InviteCreate {
  email: string;
  tenant_id: string;
  role?: string;
  frontend_url?: string;
}

export interface AcceptInvitePayload {
  name: string;
  password: string;
}

export const inviteApi = {
  create: (data: InviteCreate) =>
    apiClient.post<InviteInfo>("/invite", data).then((r) => r.data),

  get: (token: string) =>
    apiClient.get<InviteInfo>(`/invite/${token}`).then((r) => r.data),

  accept: (token: string, data: AcceptInvitePayload) =>
    apiClient.post<{ message: string }>(`/invite/${token}/accept`, data).then((r) => r.data),
};
