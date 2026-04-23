import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Bot,
  Server,
  ClipboardList,
  Shield,
  FileText,
  Settings,
  Flame,
} from "lucide-react";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/agent", icon: Bot, label: "Agente IA" },
  { to: "/devices", icon: Server, label: "Dispositivos" },
  { to: "/operations", icon: ClipboardList, label: "Operações" },
  { to: "/audit", icon: Shield, label: "Auditoria" },
  { to: "/logs", icon: FileText, label: "Logs" },
  { to: "/settings", icon: Settings, label: "Configurações" },
];

export function Sidebar() {
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
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="px-6 py-4 border-t border-gray-700 text-xs text-gray-500">
        FireManager v0.1.0
      </div>
    </aside>
  );
}
