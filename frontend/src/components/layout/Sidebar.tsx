import { NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Bot,
  Server,
  Shield,
  KeyRound,
  Settings,
  ShieldAlert,
  Radar,
  Building2,
  Globe,
  Brain,
  Layers,
  HardDrive,
  ShieldCheck,
  ClipboardCheck,
  ArrowRightLeft,
  MessageSquare,
  FileInput,
  BookMarked,
  Network,
  Database,
  DatabaseZap,
  Users,
  Bell,
  Package2,
  Monitor,
  Laptop,
  Lock,
  ShieldHalf,
  Coins,
  Cpu,
  Store,
  Sparkles,
  HelpCircle,
  WifiOff,
  Terminal,
} from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { auditApi } from "../../api/audit";
import { rmmApi } from "../../api/rmm";

// Role rank — used to filter minRole items
const ROLE_RANK: Record<string, number> = {
  admin:       5,
  analyst_n2:  4,
  analyst_sec: 4, // same visibility as N2
  analyst:     3,
  analyst_n1:  2,
  readonly:    1,
};

interface NavItem {
  to: string;
  icon: LucideIcon;
  label: string;
  badge?: boolean;      // mostra contagem de auditoria pendente (admin only)
  rmmBadge?: boolean;   // mostra indicador de RMM desconectado
  upcoming?: string;    // ex: "F28" — renderiza como item bloqueado
  beta?: boolean;
  minRole?: string;     // oculta o item para ranks abaixo deste role
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const navSections: NavSection[] = [
  // ── Início ────────────────────────────────────────────────────────────────
  {
    title: "",
    items: [
      { to: "/",          icon: LayoutDashboard, label: "Dashboard" },
    ],
  },

  // ── Firewalls ─────────────────────────────────────────────────────────────
  {
    title: "Firewalls",
    items: [
      { to: "/devices",     icon: Server,   label: "Dispositivos"               },
      { to: "/inspector",   icon: Radar,    label: "Inspetor"                   },
      { to: "/agent",       icon: Bot,      label: "Agente · Firewall", minRole: "analyst_n1" },
      { to: "/direct-mode", icon: Terminal, label: "CLI Direto",        minRole: "analyst_n1" },
    ],
  },

  // ── Automação de Configuração ─────────────────────────────────────────────
  {
    title: "Automação",
    items: [
      { to: "/golden-templates",    icon: BookMarked, label: "Templates",       minRole: "analyst_n1" },
      { to: "/golden-bundles",      icon: Package2,   label: "Kits · Bundles",  minRole: "analyst_n2" },
      { to: "/firewall-migrations", icon: FileInput,  label: "Importar Regras", minRole: "analyst_n1" },
    ],
  },

  // ── Redes & Conectividade ─────────────────────────────────────────────────
  {
    title: "Redes & Conectividade",
    items: [
      { to: "/connectivity",  icon: Network,        label: "Topologia & Rotas"    },
      { to: "/migrations",    icon: ArrowRightLeft, label: "Migração de Switches", minRole: "analyst_n1" },
      { to: "/network-agent", icon: Bot,            label: "Agente · Redes",       minRole: "analyst_n1" },
    ],
  },

  // ── Infraestrutura ────────────────────────────────────────────────────────
  {
    title: "Infraestrutura",
    items: [
      { to: "/servers",             icon: HardDrive,   label: "Servidores"           },
      { to: "/server-analysis",     icon: Brain,       label: "Agente · Servidores",  minRole: "analyst_n1" },
      { to: "/server-direct",       icon: Terminal,    label: "Console SSH",          minRole: "analyst_n1" },
      { to: "/database-connectors", icon: DatabaseZap, label: "Bancos de Dados"      },
      { to: "/vm-migration",        icon: Monitor,     label: "Migração de VMs",      minRole: "analyst_n1" },
      { to: "/rmm-agent",           icon: Laptop,      label: "Agente · Estações",    beta: true, rmmBadge: true, minRole: "analyst_n1" },
      { to: "/cloud-posture",       icon: Globe,       label: "Cloud Posture"         },
    ],
  },

  // ── Identidade & Acesso ───────────────────────────────────────────────────
  {
    title: "Identidade & Acesso",
    items: [
      { to: "/identity",           icon: Users,    label: "Identidade"           },
      { to: "/selfservice-portal", icon: Store,    label: "Self-Service Portal",  beta: true, minRole: "analyst_n1" },
      { to: "/edge-agents",        icon: Cpu,      label: "Edge Agents & SSO",    beta: true, minRole: "analyst_n1" },
    ],
  },

  // ── Segurança & Resposta ──────────────────────────────────────────────────
  {
    title: "Segurança & Resposta",
    items: [
      { to: "/alerts",    icon: Bell,       label: "Alertas & SIEM"                },
      { to: "/remediation",icon: ShieldCheck,label: "Remediações",  minRole: "analyst_n2" },
      { to: "/playbooks", icon: ShieldHalf, label: "SOAR Playbooks", minRole: "analyst_n2" },
      { to: "#", icon: Brain, label: "Threat Intelligence", upcoming: "F35" },
    ],
  },

  // ── Conformidade ──────────────────────────────────────────────────────────
  {
    title: "Conformidade",
    items: [
      { to: "/compliance", icon: ClipboardCheck, label: "Compliance" },
    ],
  },

  // ── Inteligência IA ───────────────────────────────────────────────────────
  {
    title: "Inteligência IA",
    items: [
      { to: "/knowledge",               icon: Database,      label: "Base de Conhecimento"      },
      { to: "/assistant",               icon: Sparkles,      label: "Assistente IA"              },
      { to: "/multi-domain",             icon: Layers,        label: "Investigação Multi-domínio", beta: true, minRole: "analyst_n1" },
      { to: "/glpi",                    icon: MessageSquare, label: "Tickets IA"                },
      { to: "#", icon: Radar, label: "Análise de Regras IA", upcoming: "F29" },
    ],
  },

  // ── Plataforma ────────────────────────────────────────────────────────────
  {
    title: "Plataforma",
    items: [
      { to: "/audit",          icon: Shield,      label: "Auditoria",               badge: true, minRole: "analyst_n2" },
      { to: "/vault",          icon: KeyRound,    label: "Vault de Segredos",                    minRole: "admin"      },
      { to: "/rmm",            icon: Server,      label: "Integrações RMM",          beta: true,  minRole: "admin"      },
      { to: "/security-infra", icon: ShieldHalf,  label: "Segurança da Plataforma",  beta: true,  minRole: "admin"      },
      { to: "/settings",       icon: Settings,    label: "Configurações",                        minRole: "analyst_n2" },
      { to: "/product",        icon: Coins,       label: "Produto & Billing",        beta: true,  minRole: "admin"      },
    ],
  },

  // ── Em Breve ──────────────────────────────────────────────────────────────
  {
    title: "Em Breve",
    items: [
      { to: "#", icon: ShieldHalf, label: "Hardening Avançado", upcoming: "F28" },
      { to: "#", icon: Coins,      label: "IA FinOps",           upcoming: "F29" },
    ],
  },
];

function SectionLabel({ title }: { title: string }) {
  if (!title) return null;
  return (
    <div className="flex items-center gap-2 px-3 pt-4 pb-1">
      <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
        {title}
      </span>
      <div className="flex-1 h-px bg-gray-700/60" />
    </div>
  );
}

export function Sidebar() {
  const user = useAuthStore((s) => s.user);
  const tenantRole = useAuthStore((s) => s.tenantRole);
  const isAdmin = user?.role === "admin" || tenantRole === "admin";
  const showTenants = user?.is_super_admin || tenantRole === "admin";

  // User's effective rank for sidebar visibility
  // Super admins are cross-tenant and have no tenantRole — always grant rank 5
  const effectiveRole = user?.role ?? tenantRole ?? "readonly";
  const userRank = user?.is_super_admin ? 5 : (ROLE_RANK[effectiveRole] ?? 1);

  const { data: pendingCount = 0 } = useQuery({
    queryKey: ["audit-pending-count"],
    queryFn: auditApi.getPendingCount,
    refetchInterval: 30000,
    enabled: isAdmin,
  });

  // RMM connection status — only fetched when user can see the agent page
  const { data: rmmIntegrations = [] } = useQuery({
    queryKey: ["rmm-list-sidebar"],
    queryFn: rmmApi.list,
    staleTime: 60_000,
    refetchInterval: 120_000,
    enabled: userRank >= (ROLE_RANK["analyst_n1"] ?? 2),
  });
  const hasActiveRmm = rmmIntegrations.some((r: { is_active: boolean }) => r.is_active);

  const isVisible = (item: NavItem) => {
    if (!item.minRole) return true;
    return userRank >= (ROLE_RANK[item.minRole] ?? 0);
  };

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
      isActive
        ? "bg-brand-600 text-white"
        : "text-gray-400 hover:bg-gray-800 hover:text-white"
    }`;

  return (
    <aside className="w-64 bg-gray-900 text-white flex flex-col h-screen fixed left-0 top-0">
      {/* Logo */}
      <div className="flex items-center gap-2 px-6 py-5 border-b border-gray-700">
        <ShieldAlert className="text-brand-500" size={24} />
        <span className="text-xl font-bold">Eternity SecOps</span>
      </div>

      {/* Nav */}
      <nav aria-label="Navegação principal" className="flex-1 px-3 py-2 overflow-y-auto">
        {navSections.map((section) => {
          const visibleItems = section.items.filter(isVisible);
          if (visibleItems.length === 0) return null;
          return (
            <div key={section.title || "__root__"}>
              <SectionLabel title={section.title} />
              <div className="space-y-0.5">
                {visibleItems.map(({ to, icon: Icon, label, badge, upcoming, beta, rmmBadge }) =>
                  upcoming ? (
                    <div
                      key={label}
                      aria-label={`${label} — Disponível na ${upcoming}`}
                      aria-disabled="true"
                      title={`Disponível na ${upcoming}`}
                      className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-600 opacity-45 cursor-not-allowed select-none"
                    >
                      <Icon size={18} aria-hidden="true" />
                      <span className="flex-1">{label}</span>
                      <Lock size={11} aria-hidden="true" />
                      <span className="text-[10px] bg-gray-700 text-gray-400 px-1.5 py-0.5 rounded font-mono">
                        {upcoming}
                      </span>
                    </div>
                  ) : (
                    <NavLink
                      key={to}
                      to={to}
                      end={to === "/"}
                      className={navLinkClass}
                      aria-label={badge && isAdmin && pendingCount > 0 ? `${label} — ${pendingCount} pendentes` : label}
                    >
                      <Icon size={18} aria-hidden="true" />
                      <span className="flex-1">{label}</span>
                      {beta && (
                        <span className="text-[9px] font-bold bg-indigo-600/70 text-indigo-100 px-1.5 py-0.5 rounded uppercase tracking-wide">
                          Beta
                        </span>
                      )}
                      {rmmBadge && !hasActiveRmm && (
                        <span
                          title="Nenhuma integração RMM ativa — configure em Plataforma › Integrações RMM"
                          className="flex items-center gap-1 text-[9px] font-semibold text-amber-300 bg-amber-500/20 px-1.5 py-0.5 rounded"
                        >
                          <WifiOff size={9} />
                        </span>
                      )}
                      {badge && isAdmin && pendingCount > 0 && (
                        <span aria-hidden="true" className="bg-red-500 text-white text-xs font-bold rounded-full px-1.5 py-0.5 min-w-[20px] text-center leading-none">
                          {pendingCount > 99 ? "99+" : pendingCount}
                        </span>
                      )}
                    </NavLink>
                  )
                )}
              </div>
            </div>
          );
        })}

        {/* Organização e MSSP — itens condicionais ao final de Plataforma */}
        {(showTenants || user?.is_super_admin) && (
          <div className="space-y-0.5 mt-0.5">
            {showTenants && (
              <NavLink to="/organization" className={navLinkClass}>
                <Building2 size={18} />
                <span className="flex-1">Organização</span>
              </NavLink>
            )}
            {user?.is_super_admin && (
              <NavLink to="/mssp" className={navLinkClass}>
                <Globe size={18} />
                <span className="flex-1">Painel MSSP</span>
              </NavLink>
            )}
          </div>
        )}
      </nav>

      {/* Central de Ajuda */}
      <div className="px-3 pb-2 border-t border-gray-700 pt-2">
        <NavLink to="/help" className={navLinkClass}>
          <HelpCircle size={18} aria-hidden="true" />
          <span className="flex-1">Central de Ajuda</span>
        </NavLink>
      </div>

      {/* Footer */}
      <div className="px-6 py-3 border-t border-gray-700 text-xs text-gray-500">
        Eternity SecOps v0.1.0
      </div>
    </aside>
  );
}
