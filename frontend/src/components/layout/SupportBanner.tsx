import { Shield, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../../store/authStore";

export function SupportBanner() {
  const supportMode      = useAuthStore((s) => s.supportMode);
  const supportTenantName = useAuthStore((s) => s.supportTenantName);
  const exitSupportMode  = useAuthStore((s) => s.exitSupportMode);
  const navigate = useNavigate();

  if (!supportMode) return null;

  const handleExit = () => {
    exitSupportMode();
    navigate("/mssp");
  };

  return (
    <div className="fixed top-0 left-64 right-0 z-50 flex items-center justify-between bg-amber-500 text-amber-950 px-4 py-2 text-sm font-medium shadow-md">
      <div className="flex items-center gap-2">
        <Shield size={15} />
        <span>
          Modo Suporte — visualizando tenant{" "}
          <strong>{supportTenantName}</strong>{" "}
          em modo somente leitura
        </span>
      </div>
      <button
        onClick={handleExit}
        className="flex items-center gap-1.5 hover:bg-amber-600/30 rounded px-2 py-1 transition-colors"
      >
        <X size={14} />
        Sair do modo suporte
      </button>
    </div>
  );
}
