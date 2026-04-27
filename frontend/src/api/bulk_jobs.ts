import type { BulkJobCreate, BulkJobDetail, BulkJob } from "../types/bulk_job";
import apiClient from "./client";

export const bulkJobsApi = {
  create: (data: BulkJobCreate) =>
    apiClient.post<BulkJobDetail>("/bulk-jobs", data).then((r) => r.data),

  list: () =>
    apiClient.get<BulkJob[]>("/bulk-jobs").then((r) => r.data),

  get: (id: string) =>
    apiClient.get<BulkJobDetail>(`/bulk-jobs/${id}`).then((r) => r.data),

  execute: (id: string) =>
    apiClient.post<BulkJobDetail>(`/bulk-jobs/${id}/execute`).then((r) => r.data),

  cancel: (id: string) =>
    apiClient.delete(`/bulk-jobs/${id}`),
};
