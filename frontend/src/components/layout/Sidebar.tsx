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
  Terminal,
  Radar,
  Building2,
  Globe,
  Brain,
  HardDrive,
  ShieldCheck,
  ClipboardCheck,
  ArrowRightLeft,
  BarChart3,
  MessageSquare,
  FileInput,
  BookMarked,
  Network,
  Database,
  DatabaseZap,
  Users,
  UserPlus,
  Bell,
  BarChart2,
  Package2,
  Monitor,
  KeyRound,
  Lock,
  ShieldHalf,
  Coins,
  FileCheck2,
  Cpu,
  Store,
} from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { auditApi } from "../../api/audit";

interface NavItem {
  to: string;
  icon: LucideIcon;
  label: string;
  badge?: boolean;
  upcoming?: string; // ex: "F28" — renderiza como item bloqueado
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
      { to: "/", icon: LayoutDashboard, label: "Dashboard" },
    ],
  },

  // ── Firewalls ─────────────────────────────────────────────────────────────
  {
    title: "Firewalls",
    items: [
      { to: "/devices",     icon: Server,   label: "Dispositivos"  },
      { to: "/inspector",   icon: Radar,    label: "Inspetor"      },
      { to: "/direct-mode", icon: Terminal, label: "CLI Direto"    },
      { to: "/agent",       icon: Bot,      label: "Agente de Firewall"},
    ],
  },

  // ── Automação de Configuração ─────────────────────────────────────────────
  {
    title: "Automação",
    items: [
      { to: "/golden-templates",    icon: BookMarked,  label: "Templates"       },
      { to: "/golden-bundles",      icon: Package2,    label: "Kits · Bundles"  },
      { to: "/firewall-migrations", icon: FileInput,   label: "Importar Regras" },
    ],
  },

  // ── Redes & Conectividade ─────────────────────────────────────────────────
  {
    title: "Redes & Conectividade",
    items: [
      { to: "/connectivity", icon: Network,        label: "Topologia & Rotas"    },
      { to: "/migrations",   icon: ArrowRightLeft, label: "Migração de Switches" },
      { to: "/network-agent", icon: Bot,            label: "Agente de Redes"      },
    ],
  },

  // ── Infraestrutura ────────────────────────────────────────────────────────
  {
    title: "Infraestrutura",
    items: [
      { to: "/servers",             icon: HardDrive,   label: "Servidores"      },
      { to: "/server-analysis",     icon: Brain,       label: "Agente N3"       },
      { to: "/server-direct",       icon: Terminal,    label: "Console SSH"     },
      { to: "/database-connectors", icon: DatabaseZap, label: "Bancos de Dados" },
      { to: "/vm-migration",        icon: Monitor,     label: "Migração de VMs" },
    ],
  },

  // ── Identidade & Acesso ───────────────────────────────────────────────────
  {
    title: "Identidade & Acesso",
    items: [
      { to: "/identity",   icon: Users,    label: "Identidade" },
      { to: "/onboarding", icon: UserPlus, label: "Onboarding" },
      { to: "#", icon: KeyRound, label: "SSO / OIDC", upcoming: "F31" },
    ],
  },

  // ── Segurança & Resposta ──────────────────────────────────────────────────
  {
    title: "Segurança & Resposta",
    items: [
      { to: "/alerts",      icon: Bell,        label: "Alertas"           },
      { to: "/remediation", icon: ShieldCheck, label: "Remediações"       },
      { to: "#", icon: ShieldHalf, label: "SOAR",               upcoming: "F33" },
      { to: "#", icon: Globe,      label: "Threat Intelligence", upcoming: "F33" },
    ],
  },

  // ── Conformidade & Governança ─────────────────────────────────────────────
  {
    title: "Conformidade & Governança",
    items: [
      { to: "/compliance", icon: ClipboardCheck, label: "Conformidade" },
      { to: "/governance", icon: BarChart3,      label: "Governança"   },
      { to: "#", icon: FileCheck2, label: "Packs CIS / PCI / LGPD", upcoming: "F30" },
    ],
  },

  // ── Inteligência IA ───────────────────────────────────────────────────────
  {
    title: "Inteligência IA",
    items: [
      { to: "/knowledge", icon: Database, label: "Base de Conhecimento"    },
      { to: "#", icon: Radar, label: "Análise de Regras IA", upcoming: "F29" },
    ],
  },

  // ── Relatórios ────────────────────────────────────────────────────────────
  {
    title: "Relatórios",
    items: [
      { to: "/executive", icon: BarChart2,     label: "Dashboard Executivo" },
      { to: "/glpi",      icon: MessageSquare, label: "Tickets IA"          },
    ],
  },

  // ── Plataforma ────────────────────────────────────────────────────────────
  {
    title: "Plataforma",
    items: [
      { to: "/audit",           icon: Shield,      label: "Auditoria",        badge: true },
      { to: "/enterprise",      icon: KeyRound,    label: "Enterprise"                    },
      { to: "/platform-config", icon: ShieldCheck, label: "Config. Plataforma"            },
      { to: "/settings",        icon: Settings,    label: "Configurações"                 },
      { to: "#", icon: Cpu,   label: "Edge Agents", upcoming: "F31" },
      { to: "#", icon: Store, label: "Marketplace",  upcoming: "F31" },
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
      <nav className="flex-1 px-3 py-2 overflow-y-auto">
        {navSections.map((section) => (
          <div key={section.title || "__root__"}>
            <SectionLabel title={section.title} />
            <div className="space-y-0.5">
              {section.items.map(({ to, icon: Icon, label, badge, upcoming }) =>
                upcoming ? (
                  // Item bloqueado — fase futura
                  <div
                    key={label}
                    title={`Disponível na ${upcoming}`}
                    className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-600 opacity-45 cursor-not-allowed select-none"
                  >
                    <Icon size={18} />
                    <span className="flex-1">{label}</span>
                    <Lock size={11} />
                    <span className="text-[10px] bg-gray-700 text-gray-400 px-1.5 py-0.5 rounded font-mono">
                      {upcoming}
                    </span>
                  </div>
                ) : (
                  <NavLink key={to} to={to} end={to === "/"} className={navLinkClass}>
                    <Icon size={18} />
                    <span className="flex-1">{label}</span>
                    {badge && isAdmin && pendingCount > 0 && (
                      <span className="bg-red-500 text-white text-xs font-bold rounded-full px-1.5 py-0.5 min-w-[20px] text-center leading-none">
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
