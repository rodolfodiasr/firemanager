import { NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Bot,
  Server,
  Shield,
  Settings,
  Flame,
  Terminal,
  Radar,
  Building2,
  Globe,
  Brain,
  HardDrive,
  ShieldCheck,
  ClipboardCheck,
} from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { auditApi } from "../../api/audit";

interface NavItem {
  to: string;
  icon: LucideIcon;
  label: string;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const navSections: NavSection[] = [
  {
    title: "",
    items: [
      { to: "/", icon: LayoutDashboard, label: "Dashboard" },
    ],
  },
  {
    title: "Firewall & Rede",
    items: [
      { to: "/agent",       icon: Bot,     label: "Agente IA"    },
      { to: "/direct-mode", icon: Terminal,label: "Modo Técnico" },
      { to: "/inspector",   icon: Radar,   label: "Inspetor"     },
      { to: "/devices",     icon: Server,  label: "Dispositivos" },
    ],
  },
  {
    title: "Servidores & Análise",
    items: [
      { to: "/servers",         icon: HardDrive,     label: "Servidores"   },
      { to: "/server-analysis", icon: Brain,         label: "Analista N3"  },
      { to: "/remediation",     icon: ShieldCheck,   label: "Remediações"  },
      { to: "/compliance",      icon: ClipboardCheck, label: "Conformidade" },
    ],
  },
  {
    title: "Plataforma",
    items: [
      { to: "/audit",    icon: Shield,   label: "Auditoria"     },
      { to: "/settings", icon: Settings, label: "Configurações" },
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
        <Flame className="text-brand-500" size={24} />
        <span className="text-xl font-bold">FireManager</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-2 overflow-y-auto">
        {navSections.map((section) => (
          <div key={section.title || "__root__"}>
            <SectionLabel title={section.title} />
            <div className="space-y-0.5">
              {section.items.map(({ to, icon: Icon, label }) => (
                <NavLink key={to} to={to} end={to === "/"} className={navLinkClass}>
                  <Icon size={18} />
                  <span className="flex-1">{label}</span>
                  {label === "Auditoria" && isAdmin && pendingCount > 0 && (
                    <span className="bg-red-500 text-white text-xs font-bold rounded-full px-1.5 py-0.5 min-w-[20px] text-center leading-none">
                      {pendingCount > 99 ? "99+" : pendingCount}
                    </span>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}

        {/* Conditional items appended to Plataforma */}
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
        FireManager v0.1.0
      </div>
    </aside>
  );
}
