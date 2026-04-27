export interface TemplateParameter {
  key: string;
  label: string;
  type: "string" | "ip" | "select" | "boolean";
  required?: boolean;
  options?: string[];
  default?: string;
  placeholder?: string;
}

export interface RuleTemplate {
  id: string;
  slug: string;
  name: string;
  description: string;
  category: string;
  vendor: string;
  firmware_pattern: string;
  parameters: TemplateParameter[];
  ssh_commands: string[];
  is_builtin: boolean;
  is_active: boolean;
}

export interface TemplateCreate {
  slug: string;
  name: string;
  description?: string;
  category: string;
  vendor: string;
  firmware_pattern?: string;
  parameters?: TemplateParameter[];
  ssh_commands: string[];
}
