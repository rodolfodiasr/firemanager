export interface AuditLog {
  id: string;
  user_id: string | null;
  device_id: string | null;
  operation_id: string | null;
  action: string;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  record_hash: string;
  created_at: string;
}

export interface AuditOperation {
  id: string;
  natural_language_input: string;
  intent: string | null;
  action_plan: Record<string, unknown> | null;
  status: string;
  error_message: string | null;
  review_comment: string | null;
  reviewed_at: string | null;
  executed_direct: boolean;
  created_at: string;
  updated_at: string;
  requester_name: string | null;
  requester_email: string | null;
  device_name: string | null;
  device_vendor: string | null;
  reviewer_name: string | null;
}

export interface AuditPolicy {
  id: string;
  scope_type: "role" | "user";
  scope_id: string;
  intent: string;
  requires_approval: boolean;
  updated_at: string;
}

export interface AuditPolicyUpsert {
  scope_type: "role" | "user";
  scope_id: string;
  intent: string;
  requires_approval: boolean;
}

export interface ReviewRequest {
  approved: boolean;
  comment: string;
}

export interface UserForPolicy {
  id: string;
  name: string;
  email: string;
  role: string;
}

export const AUDIT_INTENTS: { key: string; label: string; group: string; defaultApproval: boolean }[] = [
  { key: "create_rule",              label: "Criar Regra de Firewall",          group: "Firewall",  defaultApproval: true  },
  { key: "edit_rule",                label: "Editar Regra de Firewall",          group: "Firewall",  defaultApproval: true  },
  { key: "delete_rule",              label: "Excluir Regra de Firewall",         group: "Firewall",  defaultApproval: true  },
  { key: "create_nat_policy",        label: "Criar Política NAT",                group: "NAT",       defaultApproval: true  },
  { key: "delete_nat_policy",        label: "Excluir Política NAT",              group: "NAT",       defaultApproval: true  },
  { key: "create_route_policy",      label: "Criar Rota Estática",               group: "Rotas",     defaultApproval: true  },
  { key: "delete_route_policy",      label: "Excluir Rota Estática",             group: "Rotas",     defaultApproval: true  },
  { key: "create_group",             label: "Criar Grupo de Endereços",          group: "Objetos",   defaultApproval: true  },
  { key: "configure_content_filter", label: "Configurar Content Filter",         group: "Segurança", defaultApproval: true  },
  { key: "configure_app_rules",      label: "Configurar App Rules",              group: "Segurança", defaultApproval: true  },
  { key: "add_security_exclusion",   label: "Adicionar Exclusão de Segurança",   group: "Segurança", defaultApproval: false },
  { key: "toggle_gateway_av",        label: "Toggle Gateway Anti-Virus",         group: "Serviços",  defaultApproval: false },
  { key: "toggle_anti_spyware",      label: "Toggle Anti-Spyware",               group: "Serviços",  defaultApproval: false },
  { key: "toggle_ips",               label: "Toggle IPS",                        group: "Serviços",  defaultApproval: false },
  { key: "toggle_app_control",       label: "Toggle App Control",                group: "Serviços",  defaultApproval: false },
  { key: "toggle_geo_ip",            label: "Toggle Geo-IP Filter",              group: "Serviços",  defaultApproval: false },
  { key: "toggle_botnet",            label: "Toggle Botnet Filter",              group: "Serviços",  defaultApproval: false },
  { key: "toggle_dpi_ssl",           label: "Toggle DPI-SSL",                    group: "Serviços",  defaultApproval: false },
  { key: "direct_ssh",               label: "Comando SSH Direto",                 group: "Técnico",   defaultApproval: true  },
];
