import { useQuery } from "@tanstack/react-query";
import {
  Server, ClipboardList, Shield, Activity,
  HardDrive, Monitor, Terminal, Database,
  CheckCircle2, XCircle, AlertCircle, Brain,
  ArrowRight,
} from "lucide-react";
import { Link } from "react-router-dom";
import { PageWrapper } from "../components/layout/PageWrapper";
import { StatusBadge } from "../components/shared/StatusBadge";
import { devicesApi } from "../api/devices";
import { operationsApi } from "../api/operations";
import { serversApi } from "../api/servers";
import { integrationsApi } from "../api/integrations";

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({
  icon, label, value, sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  sub: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center gap-3 mb-3">
        <div className="h-10 w-10 rounded-lg bg-gray-50 flex items-center justify-center">{icon}</div>
        <span className="text-sm text-gray-500">{label}</span>
      </div>
      <p className="text-3xl font-bold text-gray-900">{value}</p>
      <p className="text-xs text-gray-400 mt-1">{sub}</p>
    </div>
  );
}

// ── Server health card ────────────────────────────────────────────────────────

function ServersHealthCard() {
  const { data: servers = [], isLoading } = useQuery({
    queryKey: ["servers"],
    queryFn: serversApi.list,
  });

  const active   = servers.filter((s) => s.is_active);
  const inactive = servers.filter((s) => !s.is_active);
  const linux    = servers.filter((s) => s.os_type === "linux");
  const windows  = servers.filter((s) => s.os_type === "windows");

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <HardDrive size={16} className="text-gray-500" />
          <h3 className="font-semibold text-gray-900 text-sm">Servidores</h3>
        </div>
        <Link to="/servers"
          className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800 font-medium">
          Ver todos <ArrowRight size={12} />
        </Link>
      </div>

      {isLoading ? (
        <p className="text-xs text-gray-400">Carregando...</p>
      ) : servers.length === 0 ? (
        <div className="flex flex-col items-center py-4 text-center">
          <p className="text-xs text-gray-400">Nenhum servidor cadastrado.</p>
          <Link to="/servers" className="text-xs text-brand-600 font-medium mt-1 hover:underline">
            Adicionar servidor
          </Link>
        </div>
      ) : (
        <>
          {/* Counters */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <p className="text-xl font-bold text-gray-900">{active.length}</p>
              <p className="text-xs text-gray-500 mt-0.5">Ativos</p>
            </div>
            <div className={`rounded-lg p-3 text-center ${inactive.length > 0 ? "bg-red-50" : "bg-gray-50"}`}>
              <p className={`text-xl font-bold ${inactive.length > 0 ? "text-red-600" : "text-gray-900"}`}>
                {inactive.length}
              </p>
              <p className="text-xs text-gray-500 mt-0.5">Inativos</p>
            </div>
          </div>

          {/* OS breakdown */}
          <div className="flex gap-3">
            {linux.length > 0 && (
              <div className="flex items-center gap-1.5 text-xs text-gray-500">
                <Terminal size={12} className="text-green-500" />
                {linux.length} Linux
              </div>
            )}
            {windows.length > 0 && (
              <div className="flex items-center gap-1.5 text-xs text-gray-500">
                <Monitor size={12} className="text-blue-500" />
                {windows.length} Windows
              </div>
            )}
          </div>

          {/* Server list */}
          <div className="space-y-1.5">
            {servers.slice(0, 5).map((s) => {
              const OsIcon = s.os_type === "windows" ? Monitor : Terminal;
              return (
                <div key={s.id} className="flex items-center gap-2">
                  <OsIcon size={13} className="text-gray-400 shrink-0" />
                  <span className="text-xs text-gray-700 flex-1 truncate">{s.name}</span>
                  <span className="text-xs text-gray-400">{s.host}</span>
                  {s.is_active
                    ? <CheckCircle2 size={13} className="text-green-500 shrink-0" />
                    : <XCircle size={13} className="text-gray-300 shrink-0" />}
                </div>
              );
            })}
            {servers.length > 5 && (
              <p className="text-xs text-gray-400 text-center pt-1">
                +{servers.length - 5} mais
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ── Integrations health card ──────────────────────────────────────────────────

const INTG_META: Record<string, { label: string; color: string }> = {
  zabbix:  { label: "Zabbix",      color: "text-orange-500" },
  wazuh:   { label: "Wazuh",       color: "text-blue-500"   },
  shodan:  { label: "Shodan",      color: "text-red-500"    },
  openvas: { label: "OpenVAS",     color: "text-green-500"  },
  nmap:    { label: "Nmap",        color: "text-purple-500" },
};

function IntegrationsHealthCard() {
  const { data: integrations = [], isLoading } = useQuery({
    queryKey: ["integrations"],
    queryFn: integrationsApi.list,
  });

  const active   = integrations.filter((i) => i.is_active);
  const inactive = integrations.filter((i) => !i.is_active);

  // Group by type — show one per type (tenant overrides global)
  const byType = integrations.reduce((acc, i) => {
    if (!acc[i.type] || i.scope === "tenant") acc[i.type] = i;
    return acc;
  }, {} as Record<string, typeof integrations[0]>);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database size={16} className="text-gray-500" />
          <h3 className="font-semibold text-gray-900 text-sm">Integrações</h3>
        </div>
        <Link to="/settings"
          className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800 font-medium">
          Configurar <ArrowRight size={12} />
        </Link>
      </div>

      {isLoading ? (
        <p className="text-xs text-gray-400">Carregando...</p>
      ) : integrations.length === 0 ? (
        <div className="flex flex-col items-center py-4 text-center">
          <p className="text-xs text-gray-400">Nenhuma integração configurada.</p>
          <Link to="/settings" className="text-xs text-brand-600 font-medium mt-1 hover:underline">
            Configurar integrações
          </Link>
        </div>
      ) : (
        <>
          {/* Counters */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <p className="text-xl font-bold text-gray-900">{active.length}</p>
              <p className="text-xs text-gray-500 mt-0.5">Ativas</p>
            </div>
            <div className={`rounded-lg p-3 text-center ${inactive.length > 0 ? "bg-amber-50" : "bg-gray-50"}`}>
              <p className={`text-xl font-bold ${inactive.length > 0 ? "text-amber-600" : "text-gray-900"}`}>
                {inactive.length}
              </p>
              <p className="text-xs text-gray-500 mt-0.5">Inativas</p>
            </div>
          </div>

          {/* Integration list */}
          <div className="space-y-2">
            {Object.entries(byType).map(([type, intg]) => {
              const meta = INTG_META[type] ?? { label: type, color: "text-gray-500" };
              return (
                <div key={type} className="flex items-center gap-2">
                  <Database size={13} className={`${meta.color} shrink-0`} />
                  <span className="text-xs text-gray-700 flex-1">{meta.label}</span>
                  <span className="text-xs text-gray-400">{intg.scope}</span>
                  {intg.is_active
                    ? <CheckCircle2 size={13} className="text-green-500 shrink-0" />
                    : <AlertCircle  size={13} className="text-amber-400 shrink-0" />}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

// ── Analysis sessions summary ─────────────────────────────────────────────────

function AnalysisSummaryCard() {
  const { data: sessions = [] } = useQuery({
    queryKey: ["analysis-sessions"],
    queryFn: () => serversApi.listSessions(5),
  });

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain size={16} className="text-purple-500" />
          <h3 className="font-semibold text-gray-900 text-sm">Últimas Análises N3</h3>
        </div>
        <Link to="/server-analysis"
          className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800 font-medium">
          Analisar <ArrowRight size={12} />
        </Link>
      </div>

      {sessions.length === 0 ? (
        <div className="flex flex-col items-center py-4 text-center">
          <p className="text-xs text-gray-400">Nenhuma análise realizada ainda.</p>
          <Link to="/server-analysis" className="text-xs text-brand-600 font-medium mt-1 hover:underline">
            Iniciar análise
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {sessions.map((s) => (
            <div key={s.id} className="flex items-start gap-2">
              <Brain size={12} className="text-purple-300 mt-0.5 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-gray-700 truncate">{s.question}</p>
                <p className="text-xs text-gray-400">
                  {new Date(s.created_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function Dashboard() {
  const devicesQuery    = useQuery({ queryKey: ["devices"],    queryFn: devicesApi.list });
  const operationsQuery = useQuery({ queryKey: ["operations"], queryFn: operationsApi.list });

  const devices    = devicesQuery.data    ?? [];
  const operations = operationsQuery.data ?? [];

  const onlineDevices = devices.filter((d) => d.status === "online").length;
  const recentOps     = operations.slice(0, 5);

  return (
    <PageWrapper title="Dashboard">
      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard
          icon={<Server className="text-blue-600" />}
          label="Dispositivos"
          value={devices.length}
          sub={`${onlineDevices} online`}
        />
        <StatCard
          icon={<ClipboardList className="text-purple-600" />}
          label="Operações"
          value={operations.length}
          sub="total"
        />
        <StatCard
          icon={<Activity className="text-green-600" />}
          label="Online"
          value={onlineDevices}
          sub={`de ${devices.length}`}
        />
        <StatCard
          icon={<Shield className="text-orange-600" />}
          label="Erros"
          value={devices.filter((d) => d.status === "error").length}
          sub="dispositivos"
        />
      </div>

      {/* Main content — two columns */}
      <div className="grid grid-cols-3 gap-6">
        {/* Left: últimas operações (2/3) */}
        <div className="col-span-2">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 h-full">
            <div className="px-6 py-4 border-b border-gray-100">
              <h2 className="font-semibold text-gray-900">Últimas Operações</h2>
            </div>
            <div className="divide-y divide-gray-100">
              {recentOps.length === 0 && (
                <p className="px-6 py-8 text-sm text-gray-400 text-center">Nenhuma operação ainda.</p>
              )}
              {recentOps.map((op) => (
                <div key={op.id} className="px-6 py-3 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-900 truncate max-w-md">
                      {op.natural_language_input}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {new Date(op.created_at).toLocaleString("pt-BR")}
                    </p>
                  </div>
                  <StatusBadge status={op.status} />
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: health widgets (1/3) */}
        <div className="col-span-1 flex flex-col gap-4">
          <ServersHealthCard />
          <IntegrationsHealthCard />
          <AnalysisSummaryCard />
        </div>
      </div>
    </PageWrapper>
  );
}
