import { useQuery } from "@tanstack/react-query";
import {
  Shield, HardDrive, Database, Brain,
  AlertTriangle, Terminal, Monitor, Globe,
  Server as ServerIcon, Layers, ArrowRight, Activity,
} from "lucide-react";
import { Link } from "react-router-dom";
import { PageWrapper } from "../components/layout/PageWrapper";
import { StatusBadge } from "../components/shared/StatusBadge";
import { devicesApi } from "../api/devices";
import { operationsApi } from "../api/operations";
import { serversApi } from "../api/servers";
import { integrationsApi } from "../api/integrations";
import type { Device, DeviceCategory, VendorEnum } from "../types/device";

// ── Static label maps ─────────────────────────────────────────────────────────

const VENDOR_LABEL: Record<VendorEnum, string> = {
  fortinet:    "FortiGate",
  sonicwall:   "SonicWall",
  pfsense:     "pfSense",
  opnsense:    "OPNsense",
  mikrotik:    "MikroTik",
  endian:      "Endian",
  cisco_ios:   "Cisco IOS",
  cisco_nxos:  "Cisco NX-OS",
  juniper:     "Juniper",
  aruba:       "Aruba",
  ubiquiti:    "Ubiquiti",
  dell:        "Dell",
  dell_n:      "Dell N-Series",
  hp_comware:  "HP Comware",
};

const CAT_LABEL: Record<DeviceCategory, string> = {
  firewall:  "Firewall",
  router:    "Roteador",
  switch:    "Switch",
  l3_switch: "Switch L3",
};

const INTG_META: Record<string, { label: string; dot: string }> = {
  zabbix:  { label: "Zabbix",  dot: "bg-orange-500" },
  wazuh:   { label: "Wazuh",   dot: "bg-blue-500"   },
  shodan:  { label: "Shodan",  dot: "bg-red-500"    },
  openvas: { label: "OpenVAS", dot: "bg-green-500"  },
  nmap:    { label: "Nmap",    dot: "bg-purple-500" },
};

const STATUS_ORDER: Record<Device["status"], number> = {
  error: 0, offline: 1, unknown: 2, online: 3,
};

// ── Shared micro-components ───────────────────────────────────────────────────

function StatusDot({ status }: { status: Device["status"] }) {
  const cls =
    status === "online"  ? "bg-green-500" :
    status === "error"   ? "bg-red-500"   :
    status === "offline" ? "bg-gray-400"  : "bg-yellow-400";
  return <span className={`h-2 w-2 rounded-full shrink-0 ${cls}`} />;
}

function CategoryIcon({ cat, size = 14 }: { cat: DeviceCategory; size?: number }) {
  if (cat === "firewall")  return <Shield     size={size} className="text-orange-400 shrink-0" />;
  if (cat === "router")    return <Globe      size={size} className="text-blue-400 shrink-0" />;
  if (cat === "l3_switch") return <Layers     size={size} className="text-purple-400 shrink-0" />;
  return                          <ServerIcon size={size} className="text-gray-400 shrink-0" />;
}

// ── Offline alert banner ──────────────────────────────────────────────────────

function OfflineAlertBanner({ devices }: { devices: Device[] }) {
  const offline = devices.filter((d) => d.status === "offline" || d.status === "error");
  if (offline.length === 0) return null;

  return (
    <div className="flex items-center gap-3 bg-red-50 border border-red-200 rounded-xl px-4 py-3 mb-6">
      <AlertTriangle size={16} className="text-red-500 shrink-0" />
      <div className="flex-1 min-w-0">
        <span className="text-sm font-semibold text-red-800">
          {offline.length === 1
            ? "1 dispositivo fora do ar"
            : `${offline.length} dispositivos fora do ar`}
          {" — "}
        </span>
        <span className="text-sm text-red-600 truncate">
          {offline.map((d) => d.name).join(" · ")}
        </span>
      </div>
      <Link
        to="/devices"
        className="text-xs text-red-700 font-medium hover:text-red-900 shrink-0 whitespace-nowrap"
      >
        Ver detalhes →
      </Link>
    </div>
  );
}

// ── Hero card: Dispositivos de Rede ───────────────────────────────────────────

function DevicesOverviewCard({ devices }: { devices: Device[] }) {
  const online  = devices.filter((d) => d.status === "online").length;
  const error   = devices.filter((d) => d.status === "error").length;
  const offline = devices.filter((d) => d.status === "offline" || d.status === "unknown").length;
  const hasIssues = error > 0 || devices.some((d) => d.status === "offline");

  const catCounts = {
    firewall: devices.filter((d) => d.category === "firewall").length,
    switch:   devices.filter((d) => d.category === "switch" || d.category === "l3_switch").length,
    router:   devices.filter((d) => d.category === "router").length,
  };

  const vendorCounts = Object.entries(
    devices.reduce((acc, d) => { acc[d.vendor] = (acc[d.vendor] ?? 0) + 1; return acc; }, {} as Record<string, number>)
  ).sort((a, b) => b[1] - a[1]).slice(0, 5);

  return (
    <div className={`bg-white rounded-xl border p-5 flex flex-col gap-4 ${hasIssues ? "border-red-200" : "border-gray-200"}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`h-8 w-8 rounded-lg flex items-center justify-center ${hasIssues ? "bg-red-50" : "bg-orange-50"}`}>
            <Shield size={16} className={hasIssues ? "text-red-500" : "text-orange-500"} />
          </div>
          <span className="text-sm font-medium text-gray-500">Dispositivos de Rede</span>
        </div>
        <Link to="/devices" className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800 font-medium">
          Gerenciar <ArrowRight size={12} />
        </Link>
      </div>

      <div className="flex items-end gap-3">
        <span className="text-4xl font-bold text-gray-900">{devices.length}</span>
        <div className="flex gap-2 mb-1 flex-wrap">
          {online  > 0 && <span className="text-xs text-green-600 font-medium">{online} online</span>}
          {error   > 0 && <span className="text-xs text-red-600 font-medium">{error} erro</span>}
          {offline > 0 && <span className="text-xs text-gray-400 font-medium">{offline} offline</span>}
        </div>
      </div>

      {devices.length > 0 && (
        <div className="flex gap-0.5 h-1.5 rounded-full overflow-hidden bg-gray-100">
          <div className="bg-green-500 transition-all" style={{ width: `${(online / devices.length) * 100}%` }} />
          <div className="bg-red-400 transition-all"   style={{ width: `${(error  / devices.length) * 100}%` }} />
        </div>
      )}

      <div className="flex gap-4 flex-wrap">
        {catCounts.firewall > 0 && (
          <div className="flex items-center gap-1 text-xs text-gray-500">
            <Shield size={11} className="text-orange-400" />
            {catCounts.firewall} {catCounts.firewall === 1 ? "firewall" : "firewalls"}
          </div>
        )}
        {catCounts.switch > 0 && (
          <div className="flex items-center gap-1 text-xs text-gray-500">
            <ServerIcon size={11} className="text-gray-400" />
            {catCounts.switch} {catCounts.switch === 1 ? "switch" : "switches"}
          </div>
        )}
        {catCounts.router > 0 && (
          <div className="flex items-center gap-1 text-xs text-gray-500">
            <Globe size={11} className="text-blue-400" />
            {catCounts.router} {catCounts.router === 1 ? "roteador" : "roteadores"}
          </div>
        )}
      </div>

      {vendorCounts.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {vendorCounts.map(([vendor, count]) => (
            <span
              key={vendor}
              className="inline-flex items-center gap-1 text-xs bg-gray-50 border border-gray-200 text-gray-600 rounded-full px-2 py-0.5"
            >
              {VENDOR_LABEL[vendor as VendorEnum] ?? vendor}
              <span className="text-gray-400">×{count}</span>
            </span>
          ))}
        </div>
      )}

      {devices.length === 0 && (
        <Link to="/devices" className="text-xs text-brand-600 hover:underline">
          Adicionar dispositivo →
        </Link>
      )}
    </div>
  );
}

// ── Hero card: Servidores ─────────────────────────────────────────────────────

function ServersOverviewCard() {
  const { data: servers = [], isLoading } = useQuery({
    queryKey: ["servers"],
    queryFn: serversApi.list,
  });

  const active   = servers.filter((s) => s.is_active).length;
  const inactive = servers.filter((s) => !s.is_active).length;
  const linux    = servers.filter((s) => s.os_type === "linux").length;
  const windows  = servers.filter((s) => s.os_type === "windows").length;
  const hasIssues = inactive > 0;

  return (
    <div className={`bg-white rounded-xl border p-5 flex flex-col gap-4 ${hasIssues ? "border-amber-200" : "border-gray-200"}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-blue-50 flex items-center justify-center">
            <HardDrive size={16} className="text-blue-500" />
          </div>
          <span className="text-sm font-medium text-gray-500">Servidores</span>
        </div>
        <Link to="/servers" className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800 font-medium">
          Gerenciar <ArrowRight size={12} />
        </Link>
      </div>

      {isLoading ? (
        <p className="text-xs text-gray-400">Carregando...</p>
      ) : (
        <>
          <div className="flex items-end gap-3">
            <span className="text-4xl font-bold text-gray-900">{servers.length}</span>
            <div className="flex gap-2 mb-1">
              {active   > 0 && <span className="text-xs text-green-600 font-medium">{active} ativos</span>}
              {inactive > 0 && <span className="text-xs text-amber-600 font-medium">{inactive} inativos</span>}
            </div>
          </div>

          {servers.length > 0 && (
            <div className="flex gap-0.5 h-1.5 rounded-full overflow-hidden bg-gray-100">
              <div className="bg-green-500 transition-all" style={{ width: `${(active / servers.length) * 100}%` }} />
              <div className="bg-amber-400 transition-all" style={{ width: `${(inactive / servers.length) * 100}%` }} />
            </div>
          )}

          <div className="flex gap-4">
            {linux > 0 && (
              <div className="flex items-center gap-1.5 text-xs text-gray-500">
                <Terminal size={11} className="text-green-500" />
                {linux} Linux
              </div>
            )}
            {windows > 0 && (
              <div className="flex items-center gap-1.5 text-xs text-gray-500">
                <Monitor size={11} className="text-blue-500" />
                {windows} Windows
              </div>
            )}
            {servers.length === 0 && (
              <Link to="/servers" className="text-xs text-brand-600 hover:underline">
                Cadastrar servidor →
              </Link>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ── Hero card: Integrações ────────────────────────────────────────────────────

function IntegrationsOverviewCard() {
  const { data: integrations = [], isLoading } = useQuery({
    queryKey: ["integrations"],
    queryFn: integrationsApi.list,
  });

  const active = integrations.filter((i) => i.is_active).length;

  const byType = integrations.reduce((acc, i) => {
    if (!acc[i.type] || i.scope === "tenant") acc[i.type] = i;
    return acc;
  }, {} as Record<string, (typeof integrations)[0]>);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-purple-50 flex items-center justify-center">
            <Database size={16} className="text-purple-500" />
          </div>
          <span className="text-sm font-medium text-gray-500">Integrações</span>
        </div>
        <Link to="/settings" className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800 font-medium">
          Configurar <ArrowRight size={12} />
        </Link>
      </div>

      {isLoading ? (
        <p className="text-xs text-gray-400">Carregando...</p>
      ) : integrations.length === 0 ? (
        <>
          <div className="flex items-end gap-3">
            <span className="text-4xl font-bold text-gray-300">0</span>
            <span className="text-xs text-gray-400 mb-1">configuradas</span>
          </div>
          <Link to="/settings" className="text-xs text-brand-600 hover:underline">
            Conectar ferramentas de segurança →
          </Link>
        </>
      ) : (
        <>
          <div className="flex items-end gap-3">
            <span className="text-4xl font-bold text-gray-900">{active}</span>
            <span className="text-xs text-gray-500 mb-1">de {integrations.length} ativas</span>
          </div>

          <div className="flex gap-0.5 h-1.5 rounded-full overflow-hidden bg-gray-100">
            <div
              className="bg-purple-500 transition-all"
              style={{ width: `${(active / integrations.length) * 100}%` }}
            />
          </div>

          <div className="flex flex-wrap gap-x-4 gap-y-1.5">
            {Object.entries(byType).map(([type, intg]) => {
              const meta = INTG_META[type] ?? { label: type, dot: "bg-gray-400" };
              return (
                <div key={type} className="flex items-center gap-1.5">
                  <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${intg.is_active ? meta.dot : "bg-gray-300"}`} />
                  <span className={`text-xs ${intg.is_active ? "text-gray-600" : "text-gray-400"}`}>
                    {meta.label}
                  </span>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

// ── Device inventory table ────────────────────────────────────────────────────

function DeviceInventoryPanel({ devices }: { devices: Device[] }) {
  const sorted = [...devices].sort(
    (a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status]
  );

  return (
    <div className="bg-white rounded-xl border border-gray-200 flex flex-col">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-gray-900">Inventário de Rede</h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Dispositivos monitorados em tempo real — firewalls, switches, roteadores
          </p>
        </div>
        <Link
          to="/devices"
          className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800 font-medium"
        >
          Gerenciar <ArrowRight size={12} />
        </Link>
      </div>

      {devices.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-14 text-center">
          <Shield size={32} className="text-gray-200 mb-3" />
          <p className="text-sm text-gray-400">Nenhum dispositivo cadastrado.</p>
          <Link to="/devices" className="text-sm text-brand-600 font-medium mt-1 hover:underline">
            Adicionar dispositivo
          </Link>
        </div>
      ) : (
        <div className="divide-y divide-gray-50">
          {sorted.map((d) => (
            <div
              key={d.id}
              className="px-5 py-3 flex items-center gap-3 hover:bg-gray-50 transition-colors"
            >
              <StatusDot status={d.status} />
              <CategoryIcon cat={d.category} size={14} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">{d.name}</p>
                <p className="text-xs text-gray-400">{d.host}</p>
              </div>
              <div className="text-right shrink-0">
                <p className="text-xs text-gray-600 font-medium">
                  {VENDOR_LABEL[d.vendor] ?? d.vendor}
                </p>
                <p className="text-xs text-gray-400">{CAT_LABEL[d.category]}</p>
              </div>
              <div className="w-28 text-right shrink-0 hidden lg:block">
                {d.last_seen ? (
                  <p className="text-xs text-gray-400">
                    {new Date(d.last_seen).toLocaleString("pt-BR", {
                      dateStyle: "short",
                      timeStyle: "short",
                    })}
                  </p>
                ) : (
                  <p className="text-xs text-gray-300">—</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Recent operations (right sidebar) ────────────────────────────────────────

function RecentOpsPanel() {
  const { data: operations = [] } = useQuery({
    queryKey: ["operations"],
    queryFn: operationsApi.list,
  });

  const recent = operations.slice(0, 6);

  return (
    <div className="bg-white rounded-xl border border-gray-200 flex flex-col">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={15} className="text-gray-400" />
          <h3 className="text-sm font-semibold text-gray-900">Operações Recentes</h3>
        </div>
        <Link to="/audit" className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800 font-medium">
          Ver todas <ArrowRight size={12} />
        </Link>
      </div>

      {recent.length === 0 ? (
        <p className="px-5 py-6 text-xs text-gray-400 text-center">Nenhuma operação ainda.</p>
      ) : (
        <div className="divide-y divide-gray-50">
          {recent.map((op) => (
            <div key={op.id} className="px-5 py-3 flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-gray-800 truncate">
                  {op.natural_language_input}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {new Date(op.created_at).toLocaleString("pt-BR", {
                    dateStyle: "short",
                    timeStyle: "short",
                  })}
                </p>
              </div>
              <div className="shrink-0">
                <StatusBadge status={op.status} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Analysis summary (right sidebar) ─────────────────────────────────────────

function AnalysisSummaryPanel() {
  const { data: sessions = [] } = useQuery({
    queryKey: ["analysis-sessions"],
    queryFn: () => serversApi.listSessions(4),
  });

  return (
    <div className="bg-white rounded-xl border border-gray-200 flex flex-col">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain size={15} className="text-purple-400" />
          <h3 className="text-sm font-semibold text-gray-900">Análises N3</h3>
        </div>
        <Link to="/server-analysis" className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800 font-medium">
          Analisar <ArrowRight size={12} />
        </Link>
      </div>

      {sessions.length === 0 ? (
        <div className="px-5 py-6 text-center">
          <p className="text-xs text-gray-400">Nenhuma análise realizada.</p>
          <Link to="/server-analysis" className="text-xs text-brand-600 mt-1 block hover:underline">
            Iniciar análise
          </Link>
        </div>
      ) : (
        <div className="divide-y divide-gray-50">
          {sessions.map((s) => (
            <div key={s.id} className="px-5 py-3">
              <p className="text-xs text-gray-800 truncate">{s.question}</p>
              <p className="text-xs text-gray-400 mt-0.5">
                {new Date(s.created_at).toLocaleString("pt-BR", {
                  dateStyle: "short",
                  timeStyle: "short",
                })}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function Dashboard() {
  const { data: devices = [] } = useQuery({
    queryKey: ["devices"],
    queryFn: devicesApi.list,
  });

  return (
    <PageWrapper
      title="Visão Geral da Infraestrutura"
      subtitle="Todos os dispositivos, servidores e integrações monitorados em tempo real"
    >
      {/* Offline alert banner */}
      <OfflineAlertBanner devices={devices} />

      {/* Hero stats row */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <DevicesOverviewCard devices={devices} />
        <ServersOverviewCard />
        <IntegrationsOverviewCard />
      </div>

      {/* Body: inventory + sidebar */}
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2">
          <DeviceInventoryPanel devices={devices} />
        </div>

        <div className="col-span-1 flex flex-col gap-4">
          <RecentOpsPanel />
          <AnalysisSummaryPanel />
        </div>
      </div>
    </PageWrapper>
  );
}
