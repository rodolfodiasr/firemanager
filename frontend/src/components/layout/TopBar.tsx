import { LogOut, User } from "lucide-react";
import { useAuth } from "../../hooks/useAuth";
import { TenantSwitcher } from "./TenantSwitcher";

interface TopBarProps {
  title: string;
}

export function TopBar({ title }: TopBarProps) {
  const { user, signOut } = useAuth();

  return (
    <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6">
      <h1 className="text-lg font-semibold text-gray-900">{title}</h1>
      <div className="flex items-center gap-5">
        <TenantSwitcher />
        <span className="flex items-center gap-2 text-sm text-gray-600">
          <User size={16} />
          {user?.name ?? "Usuário"}
        </span>
        <button
          onClick={signOut}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-red-600 transition-colors"
        >
          <LogOut size={16} />
          Sair
        </button>
      </div>
    </header>
  );
}
