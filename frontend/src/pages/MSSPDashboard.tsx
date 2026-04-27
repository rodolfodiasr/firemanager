import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Server,
  Wifi,
  ClipboardList,
  Clock,
  LogIn,
  RefreshCw,
  AlertTriangle,
} from "lucide-react";
import { adminApi, type TenantOverview } from "../api/admin";
import { useAuthStore } from "../store/authStore";

function formatLastSeen(iso: string | null): string {
  if (!iso) return "Nunca";
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 2) return "Agora";
  if (diffMin < 60) return `${diffMin}m atrás`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH}h atrás`;
  return `${Math.floor(diffH / 24)}d atrás`;
}

function TenantCard({ overview, onEnterSupport }: { overview: TenantOverview; onEnterSupport: () => void }) {
  const healthPct = overview.device_count > 0
    ? Math.round((overview.online_count / overview.device_count) * 100)
    : 0;

  const healthColor =
    healthPct >= 80 ? "text-green-400" :
    healthPct >= 50 ? "text-yellow-400" : "text-red-400";

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 flex flex-col gap-4 hover:border-brand-500 transition-colors">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-white font-semibold text-lg">{overview.name}</h3>
          <p className="text-gray-400 text-sm font-mono">{overview.slug}</p>
        </div>
        <button
          onClick={onEnterSupport}
          className="flex items-center gap-1.5 text-xs bg-brand-600 hover:bg-brand-700 text-white px-3 py-1.5 rounded-lg transition-colors"
        >
          <LogIn size={13} />
          Suporte
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Stat icon={<Server size={14} />} label="Dispositivos" value={overview.device_count} />
        <Stat
          icon={<Wifi size={14} />}
          label="Online"
          value={`${overview.online_count}/${overview.device_count}`}
          valueClass={healthColor}
        />
        <Stat
          icon={<ClipboardList size={14} />}
          label="Pendentes"
          value={overview.pending_ops}
          valueClass={overview.pending_ops > 0 ? "text-yellow-400" : undefined}
        />
      </div>

      {overview.device_count > 0 && (
        <div>
          <div className="flex justify-between text-xs text-gray-400 mb-1">
            <span>Saúde</span>
            <span className={healthColor}>{healthPct}%</span>
          </div>
          <div className="w-full bg-gray-700 rounded-full h-1.5">
            <div
              className={`h-1.5 rounded-full ${
                healthPct >= 80 ? "bg-green-500" :
                healthPct >= 50 ? "bg-yellow-500" : "bg-red-500"
              }`}
              style={{ width: `${healthPct}%` }}
            />
          </div>
        </div>
      )}

      <div className="flex items-center gap-1.5 text-xs text-gray-500">
        <Clock size={12} />
        <span>Último contato: {formatLastSeen(overview.last_seen)}</span>
      </div>
    </div>
  );
}

function Stat({
  icon,
  label,
  value,
  valueClass,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  valueClass?: string;
}) {
  return (
    <div className="bg-gray-700/50 rounded-lg p-3 text-center border border-gray-700">
      <div className="flex justify-center text-gray-400 mb-1">{icon}</div>
      <p className={`text-lg font-bold ${valueClass ?? "text-white"}`}>{value}</p>
      <p className="text-xs text-gray-500">{label}</p>
    </div>
  );
}

export function MSSPDashboard() {
  const navigate = useNavigate();
  const enterSupportMode = useAuthStore((s) => s.enterSupportMode);

  const { data: tenants = [], isLoading, isError, refetch } = useQuery({
    queryKey: ["mssp-overview"],
    queryFn: adminApi.getTenantsOverview,
    refetchInterval: 60000,
  });

  const handleEnterSupport = async (tenant: TenantOverview) => {
    try {
      const resp = await adminApi.getSupportToken(tenant.id);
      enterSupportMode(resp.access_token, resp.tenant_name);
      navigate("/");
    } catch {
      alert("Erro ao gerar token de suporte");
    }
  };

  const totalDevices = tenants.reduce((s, t) => s + t.device_count, 0);
  const totalOnline  = tenants.reduce((s, t) => s + t.online_count, 0);
  const totalPending = tenants.reduce((s, t) => s + t.pending_ops, 0);

  return (
    <main className="ml-64 flex-1 min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold">Painel MSSP</h1>
            <p className="text-gray-400 text-sm mt-1">Visão cross-tenant para o Super Admin</p>
          </div>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors"
          >
            <RefreshCw size={16} />
            Atualizar
          </button>
        </div>

        {/* Summary row */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          <SummaryCard label="Tenants" value={tenants.length} />
          <SummaryCard label="Dispositivos" value={totalDevices} />
          <SummaryCard label="Online" value={totalOnline} />
          <SummaryCard label="Ops Pendentes" value={totalPending} highlight={totalPending > 0} />
        </div>

        {/* Tenant cards */}
        {isLoading && (
          <p className="text-gray-400 text-center py-16">Carregando tenants...</p>
        )}
        {isError && (
          <div className="flex items-center gap-2 text-red-400 text-sm justify-center py-16">
            <AlertTriangle size={16} />
            Erro ao carregar dados. Verifique suas permissões.
          </div>
        )}
        {!isLoading && !isError && tenants.length === 0 && (
          <p className="text-gray-500 text-center py-16">Nenhum tenant ativo encontrado.</p>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {tenants.map((t) => (
            <TenantCard
              key={t.id}
              overview={t}
              onEnterSupport={() => handleEnterSupport(t)}
            />
          ))}
        </div>
      </div>
    </main>
  );
}

function SummaryCard({ label, value, highlight }: { label: string; value: number; highlight?: boolean }) {
  return (
    <div className={`rounded-xl border p-4 ${highlight ? "bg-yellow-900/20 border-yellow-700" : "bg-gray-800 border-gray-700"}`}>
      <p className="text-gray-400 text-xs mb-1">{label}</p>
      <p className={`text-2xl font-bold ${highlight ? "text-yellow-400" : "text-white"}`}>{value}</p>
    </div>
  );
}
