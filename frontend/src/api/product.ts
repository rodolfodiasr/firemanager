import apiClient from "./client";

export interface BillingPlan {
  id: string;
  name: string;
  slug: string;
  monthly_price_brl: number;
  max_devices: number | null;
  max_users: number | null;
  ai_token_quota: number | null;
  sla_target_pct: number | null;
  features: Record<string, boolean> | null;
  is_active: boolean;
}

export interface BillingSubscription {
  id: string;
  tenant_id: string;
  status: string;
  cancel_at_period_end: boolean;
  current_period_start: string | null;
  current_period_end: string | null;
  trial_end: string | null;
  created_at: string;
  plan: BillingPlan;
}

export interface BillingInvoice {
  id: string;
  amount_brl: number;
  status: string;
  period_start: string | null;
  period_end: string | null;
  paid_at: string | null;
  due_date: string | null;
  invoice_pdf_url: string | null;
  created_at: string;
}

export interface OnboardingChecklist {
  id: string;
  step_add_device: boolean;
  step_run_snapshot: boolean;
  step_ask_agent: boolean;
  step_configure_alert: boolean;
  completed: boolean;
  skipped: boolean;
  completed_at: string | null;
}

export interface HelpArticle {
  id: string;
  title: string;
  slug: string;
  category: string;
  persona: string | null;
  content_md: string;
  is_published: boolean;
  view_count: number;
  sort_order: number;
  created_at: string;
}

export interface UserPreferences {
  id: string;
  language: string;
  timezone: string;
  theme: string;
  notifications_enabled: boolean;
  onboarding_step: number;
  onboarding_completed: boolean;
}

const BASE = "/product";

export const productApi = {
  // Plans
  listPlans: () =>
    apiClient.get<BillingPlan[]>(`${BASE}/billing/plans`).then(r => r.data),
  seedPlans: () =>
    apiClient.post<BillingPlan[]>(`${BASE}/billing/plans/seed`).then(r => r.data),

  // Subscription
  getSubscription: () =>
    apiClient.get<BillingSubscription | null>(`${BASE}/billing/subscription`).then(r => r.data),
  startSubscription: (plan_slug = "starter") =>
    apiClient.post<BillingSubscription>(`${BASE}/billing/subscription/start`, null, { params: { plan_slug } }).then(r => r.data),

  // Invoices
  listInvoices: () =>
    apiClient.get<BillingInvoice[]>(`${BASE}/billing/invoices`).then(r => r.data),

  // Onboarding
  getChecklist: () =>
    apiClient.get<OnboardingChecklist>(`${BASE}/onboarding/checklist`).then(r => r.data),
  completeStep: (step: string) =>
    apiClient.post<OnboardingChecklist>(`${BASE}/onboarding/checklist/complete-step`, { step }).then(r => r.data),
  skipOnboarding: () =>
    apiClient.post<OnboardingChecklist>(`${BASE}/onboarding/checklist/skip`).then(r => r.data),

  // Help
  listArticles: (category?: string, persona?: string) =>
    apiClient.get<HelpArticle[]>(`${BASE}/help/articles`, { params: { ...(category ? { category } : {}), ...(persona ? { persona } : {}) } }).then(r => r.data),
  getArticle: (slug: string) =>
    apiClient.get<HelpArticle>(`${BASE}/help/articles/${slug}`).then(r => r.data),
  seedArticles: () =>
    apiClient.post<HelpArticle[]>(`${BASE}/help/articles/seed`).then(r => r.data),

  // Preferences
  getPreferences: () =>
    apiClient.get<UserPreferences>(`${BASE}/preferences`).then(r => r.data),
  updatePreferences: (data: { language?: string; timezone?: string; theme?: string; notifications_enabled?: boolean }) =>
    apiClient.patch<UserPreferences>(`${BASE}/preferences`, data).then(r => r.data),

  // Stripe Checkout
  createCheckout: (plan_id: string, success_url?: string, cancel_url?: string) =>
    apiClient.post<{ checkout_url: string }>(`${BASE}/billing/checkout`, {
      plan_id,
      ...(success_url ? { success_url } : {}),
      ...(cancel_url ? { cancel_url } : {}),
    }).then(r => r.data),

  // Invoice PDF URL
  invoicePdfUrl: (invoice_id: string) => `/api${BASE}/billing/invoices/${invoice_id}/pdf`,
};
