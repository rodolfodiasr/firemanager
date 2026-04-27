import { NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  LayoutDashboard,
  Bot,
  Server,
  ClipboardList,
  Shield,
  FileText,
  Settings,
  Flame,
  Terminal,
  BookMarked,
  Radar,
  Building2,
  Globe,
  Layers,
  FolderOpen,
} from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { auditApi } from "../../api/audit";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/agent", icon: Bot, label: "Agente IA" },
  { to: "/direct-mode", icon: Terminal, label: "Modo Técnico" },
  { to: "/templates", icon: BookMarked, label: "Templates" },
  { to: "/inspector", icon: Radar, label: "Inspetor" },
  { to: "/devices", icon: Server, label: "Dispositivos" },
  { to: "/device-groups", icon: FolderOpen, label: "Grupos" },
  { to: "/bulk-jobs", icon: Layers, label: "Lote" },
  { to: "/operations", icon: ClipboardList, label: "Operações" },
  { to: "/audit", icon: Shield, label: "Auditoria" },
  { to: "/logs", icon: FileText, label: "Logs" },
  { to: "/settings", icon: Settings, label: "Configurações" },
];

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

  return (
    <aside className="w-64 bg-gray-900 text-white flex flex-col h-screen fixed left-0 top-0">
      <div className="flex items-center gap-2 px-6 py-5 border-b border-gray-700">
        <Flame className="text-brand-500" size={24} />
        <span className="text-xl font-bold">FireManager</span>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-brand-600 text-white"
                  : "text-gray-400 hover:bg-gray-800 hover:text-white"
              }`
            }
          >
            <Icon size={18} />
            <span className="flex-1">{label}</span>
            {label === "Auditoria" && isAdmin && pendingCount > 0 && (
              <span className="bg-red-500 text-white text-xs font-bold rounded-full px-1.5 py-0.5 min-w-[20px] text-center leading-none">
                {pendingCount > 99 ? "99+" : pendingCount}
              </span>
            )}
          </NavLink>
        ))}
        {showTenants && (
          <NavLink
            to="/tenants"
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-brand-600 text-white"
                  : "text-gray-400 hover:bg-gray-800 hover:text-white"
              }`
            }
          >
            <Building2 size={18} />
            <span className="flex-1">Tenants</span>
          </NavLink>
        )}
        {user?.is_super_admin && (
          <NavLink
            to="/mssp"
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-brand-600 text-white"
                  : "text-gray-400 hover:bg-gray-800 hover:text-white"
              }`
            }
          >
            <Globe size={18} />
            <span className="flex-1">Painel MSSP</span>
          </NavLink>
        )}
      </nav>
      <div className="px-6 py-4 border-t border-gray-700 text-xs text-gray-500">
        FireManager v0.1.0
      </div>
    </aside>
  );
}
