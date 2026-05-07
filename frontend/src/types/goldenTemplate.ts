export interface TemplateVariable {
  key: string;
  type: "ip" | "cidr" | "string" | "integer" | "hostname";
  label: string;
  required: boolean;
  default?: string;
  hint?: string;
}

export interface GoldenTemplateSummary {
  id: string;
  tenant_id: string | null;
  name: string;
  description: string | null;
  vendor: string;
  category: string;
  variable_count: number;
  version: number;
  is_system: boolean;
  created_at: string;
  updated_at: string;
}

export interface GoldenTemplateRead {
  id: string;
  tenant_id: string | null;
  name: string;
  description: string | null;
  vendor: string;
  category: string;
  variables: TemplateVariable[];
  content: string;
  version: number;
  is_active: boolean;
  is_system: boolean;
  created_at: string;
  updated_at: string;
}

export interface GoldenTemplateVersionRead {
  id: string;
  version: number;
  change_note: string | null;
  created_at: string;
}

export interface GoldenTemplateCreate {
  name: string;
  description?: string;
  vendor: string;
  category: string;
  variables: TemplateVariable[];
  content: string;
  change_note?: string;
}

export interface GoldenTemplateUpdate {
  name?: string;
  description?: string;
  vendor?: string;
  category?: string;
  variables?: TemplateVariable[];
  content?: string;
  change_note?: string;
}

export interface RenderResponse {
  content: string;
  unresolved: string[];
}

export interface ApplyResponse {
  status: "applied" | "manual" | "error";
  message: string;
  output?: string;
  commands?: string;
}

export interface DivergenceItem {
  section: string;
  value: string;
  status: "missing" | "extra";
}

export interface DivergenceResponse {
  device_id: string;
  template_id: string;
  vendor: string;
  items: DivergenceItem[];
  summary: { missing: number; extra: number; total: number };
  rendered_preview: string;
  supported: boolean;
  message?: string;
}
