import { NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Bot,
  Server,
  Shield,
  Settings,
  ShieldAlert,
  Radar,
  Building2,
  Globe,
  Brain,
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
  BarChart2,
  Package2,
  Monitor,
  Lock,
  ShieldHalf,
  Coins,
  Cpu,
  Store,
  Sparkles,
} from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { auditApi } from "../../api/audit";

interface NavItem {
  to: string;
  icon: LucideIcon;
  label: string;
  badge?: boolean;
  upcoming?: string; // ex: "F28" — renderiza como item bloqueado
  beta?: boolean;    // módulo validado parcialmente — navegável mas em maturação
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
      { to: "/",          icon: LayoutDashboard, label: "Dashboard"           },
      { to: "/executive", icon: BarChart2,        label: "Dashboard Executivo" }, // Onda 1
    ],
  },

  // ── Firewalls ─────────────────────────────────────────────────────────────
  {
    title: "Firewalls",
    items: [
      { to: "/devices",   icon: Server, label: "Dispositivos"    },
      { to: "/inspector", icon: Radar,  label: "Inspetor"        },
      { to: "/agent",     icon: Bot,    label: "Agente · Firewall" }, // Onda 3: renomeado; CLI Direto removido
    ],
  },

  // ── Automação de Configuração ─────────────────────────────────────────────
  {
    title: "Automação",
    items: [
      { to: "/golden-templates",    icon: BookMarked, label: "Templates"       },
      { to: "/golden-bundles",      icon: Package2,   label: "Kits · Bundles"  },
      { to: "/firewall-migrations", icon: FileInput,  label: "Importar Regras" },
    ],
  },

  // ── Redes & Conectividade ─────────────────────────────────────────────────
  {
    title: "Redes & Conectividade",
    items: [
      { to: "/connectivity",  icon: Network,        label: "Topologia & Rotas"    },
      { to: "/migrations",    icon: ArrowRightLeft, label: "Migração de Switches" },
      { to: "/network-agent", icon: Bot,            label: "Agente · Redes"       }, // Onda 3: renomeado
    ],
  },

  // ── Infraestrutura ────────────────────────────────────────────────────────
  {
    title: "Infraestrutura",
    items: [
      { to: "/servers",             icon: HardDrive,   label: "Servidores"          },
      { to: "/server-analysis",     icon: Brain,       label: "Agente · Servidores" }, // Onda 1+3: era Agente N3; Console SSH removido
      { to: "/database-connectors", icon: DatabaseZap, label: "Bancos de Dados"     },
      { to: "/vm-migration",        icon: Monitor,     label: "Migração de VMs"     },
      { to: "/rmm",                 icon: Server,      label: "RMM",                 beta: true }, // Onda 1: movido de Segurança
      { to: "/cloud-posture",       icon: Globe,       label: "Cloud Posture"        },             // Onda 1: movido de Segurança
    ],
  },

  // ── Identidade & Acesso ───────────────────────────────────────────────────
  {
    title: "Identidade & Acesso",
    items: [
      { to: "/identity",           icon: Users,    label: "Identidade"           },
      { to: "/selfservice-portal", icon: Store,    label: "Self-Service Portal",  beta: true },
      { to: "/edge-agents",        icon: Cpu,      label: "Edge Agents & SSO",    beta: true },
    ],
  },

  // ── Segurança & Resposta ──────────────────────────────────────────────────
  {
    title: "Segurança & Resposta",
    items: [
      { to: "/alerts",     icon: Bell,       label: "Alertas & SIEM"  }, // Onda 2: unifica Alertas + SIEM
      { to: "/remediation", icon: ShieldCheck, label: "Remediações"   },
      { to: "/playbooks",  icon: ShieldHalf, label: "SOAR Playbooks"  },
      // RMM e Cloud Posture movidos para Infraestrutura — Onda 1
      // Integrações SIEM removido da sidebar — Onda 2 (redirect /siem → /alerts)
      { to: "#", icon: Brain, label: "Threat Intelligence", upcoming: "F35" },
    ],
  },

  // ── Conformidade ──────────────────────────────────────────────────────────
  {
    title: "Conformidade",  // Onda 2: era "Conformidade & Governança"
    items: [
      { to: "/compliance", icon: ClipboardCheck, label: "Compliance" }, // Onda 2: unifica 3→1
      // Governança removido da sidebar — Onda 2 (redirect /governance → /compliance)
      // Packs CIS removido da sidebar — Onda 2 (redirect /compliance-enterprise → /compliance)
    ],
  },

  // ── Inteligência IA ───────────────────────────────────────────────────────
  {
    title: "Inteligência IA",
    items: [
      { to: "/knowledge", icon: Database,      label: "Base de Conhecimento"  },
      { to: "/assistant", icon: Sparkles,      label: "Assistente IA"         },
      { to: "/glpi",      icon: MessageSquare, label: "Tickets IA"            }, // Onda 1: movido de Relatórios
      { to: "#", icon: Radar, label: "Análise de Regras IA", upcoming: "F29" },
    ],
  },

  // Relatórios removida — Onda 1: Dashboard Executivo → raiz; Tickets IA → Inteligência IA

  // ── Plataforma ────────────────────────────────────────────────────────────
  {
    title: "Plataforma",  // Onda 2: 7 → 4 itens
    items: [
      { to: "/audit",          icon: Shield,      label: "Auditoria",               badge: true },
      { to: "/security-infra", icon: ShieldHalf,  label: "Segurança da Plataforma", beta: true  }, // Onda 2: unifica IA Safety + Infra Seg
      { to: "/settings",       icon: Settings,    label: "Configurações"                         }, // Onda 2: unifica Config + Enterprise + Settings
      { to: "/product",        icon: Coins,       label: "Produto & Billing",        beta: true  },
      // Enterprise removido da sidebar — Onda 2 (redirect /enterprise → /settings)
      // IA Safety removido da sidebar — Onda 2 (redirect /ai-safety → /security-infra)
      // Config. Plataforma removido — Onda 2 (redirect /platform-config → /settings)
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
  const isAdmin = user?.role === "admin";
  const showTenants = user?.is_super_admin || tenantRole === "admin";

  const { data: pendingCount = 0 } = useQuery({
    queryKey: ["audit-pending-count"],
    queryFn: auditApi.getPendingCount,
    refetchInterval: 30000,
    enabled: isAdmin,
  });

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
        {navSections.map((section) => (
          <div key={section.title || "__root__"}>
            <SectionLabel title={section.title} />
            <div className="space-y-0.5">
              {section.items.map(({ to, icon: Icon, label, badge, upcoming, beta }) =>
                upcoming ? (
                  // Item bloqueado — fase futura
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
        ))}

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

      {/* Footer */}
      <div className="px-6 py-4 border-t border-gray-700 text-xs text-gray-500">
        Eternity SecOps v0.1.0
      </div>
    </aside>
  );
}
