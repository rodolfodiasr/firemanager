import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Radar, RefreshCw, Bot, Terminal, ChevronDown, ChevronRight,
  ShieldCheck, ShieldOff, CheckCircle2, XCircle, AlertCircle,
} from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { devicesApi } from "../api/devices";
import type { Device } from "../types/device";

type Resource = "rules" | "nat" | "routes" | "security" | "content_filter" | "app_rules";

const TABS: { key: Resource; label: string }[] = [
  { key: "rules", label: "Regras de Acesso" },
  { key: "nat", label: "NAT" },
  { key: "routes", label: "Rotas" },
  { key: "content_filter", label: "Content Filter" },
  { key: "app_rules", label: "App Rules" },
  { key: "security", label: "Serviços de Segurança" },
];

const COLUMNS: Record<Resource, { key: string; label: string }[]> = {
  rules: [
    { key: "name", label: "Nome" },
    { key: "src", label: "Origem" },
    { key: "dst", label: "Destino" },
    { key: "service", label: "Serviço" },
    { key: "action", label: "Ação" },
    { key: "enabled", label: "Status" },
  ],
  nat: [
    { key: "name", label: "Nome" },
    { key: "inbound", label: "Entrada" },
    { key: "outbound", label: "Saída" },
    { key: "source", label: "Origem" },
    { key: "translated_source", label: "Orig. Traduzida" },
    { key: "destination", label: "Destino" },
    { key: "translated_destination", label: "Dest. Traduzido" },
  ],
  routes: [
    { key: "name", label: "Nome" },
    { key: "interface", label: "Interface" },
    { key: "destination", label: "Destino" },
    { key: "gateway", label: "Gateway" },
    { key: "metric", label: "Métrica" },
    { key: "route_type", label: "Tipo" },
    { key: "enabled", label: "Status" },
  ],
  content_filter: [
    { key: "type", label: "Tipo" },
    { key: "name", label: "Nome" },
  ],
  app_rules: [
    { key: "type", label: "Tipo" },
    { key: "name", label: "Nome" },
  ],
  security: [
    { key: "service", label: "Serviço" },
    { key: "enabled", label: "Status" },
  ],
};

function EnabledBadge({ value }: { value: unknown }) {
  if (value === true)
    return <span className="inline-flex items-center gap-1 text-green-700 text-xs font-medium"><CheckCircle2 size={13} />Ativo</span>;
  if (value === false)
    return <span className="inline-flex items-center gap-1 text-red-500 text-xs font-medium"><XCircle size={13} />Inativo</span>;
  return <span className="inline-flex items-center gap-1 text-gray-400 text-xs"><AlertCircle size={13} />—</span>;
}

function CellValue({ col, value }: { col: string; value: unknown }) {
  if (col === "enabled") return <EnabledBadge value={value} />;
  if (col === "action") {
    const v = String(value ?? "").toLowerCase();
    const cls = v === "allow" ? "text-green-700" : v === "deny" ? "text-red-600" : "text-gray-600";
    return <span className={`text-xs font-semibold uppercase ${cls}`}>{String(value ?? "—")}</span>;
  }
  return <span className="text-xs text-gray-700 truncate max-w-[180px] block">{String(value ?? "—")}</span>;
}

function buildSeed(resource: Resource, item: Record<string, unknown>): string {
  if (resource === "rules")
    return `Quero editar a regra de acesso "${item.name}" — `;
  if (resource === "nat")
    return `Quero editar a política NAT "${item.name}" — `;
  if (resource === "routes")
    return `Quero editar a rota "${item.name}" (destino: ${item.destination}) — `;
  if (resource === "content_filter")
    return `Quero ajustar o ${item.type} de Content Filter "${item.name}" — `;
  if (resource === "app_rules")
    return `Quero ajustar a ${item.type} App Rules "${item.name}" — `;
  if (resource === "security")
    return `Quero ${item.enabled ? "desativar" : "ativar"} o serviço de segurança "${item.service}" — `;
  return "";
}

export function Inspector() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [deviceId, setDeviceId] = useState(searchParams.get("device") ?? "");
  const [resource, setResource] = useState<Resource>("rules");
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  const { data: devices = [] } = useQuery({ queryKey: ["devices"], queryFn: devicesApi.list });

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["inspect", deviceId, resource],
    queryFn: () => devicesApi.inspect(deviceId, resource),
    enabled: !!deviceId,
    staleTime: 30_000,
    retry: false,
  });

  const selectedDevice = devices.find((d: Device) => d.id === deviceId);
  const items = data?.items ?? [];
  const cols = COLUMNS[resource];

  function editWithAgent(item: Record<string, unknown>) {
    const seed = buildSeed(resource, item);
    navigate(`/agent?device=${deviceId}&seed=${encodeURIComponent(seed)}`);
  }

  return (
    <PageWrapper title="Inspetor de Dispositivo">
      <div className="space-y-5 max-w-full">

        {/* Device selector */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2 shrink-0">
            <Radar size={18} className="text-brand-600" />
            <span className="text-sm font-semibold text-gray-700">Dispositivo</span>
          </div>
          <select
            value={deviceId}
            onChange={(e) => { setDeviceId(e.target.value); setExpandedRow(null); }}
            className="flex-1 min-w-[260px] border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">Selecione um dispositivo...</option>
            {devices.map((d: Device) => (
              <option key={d.id} value={d.id}>
                {d.name} — {d.vendor} ({d.host})
              </option>
            ))}
          </select>
          {deviceId && (
            <button
              onClick={() => refetch()}
              disabled={isFetching}
              className="flex items-center gap-1.5 px-3 py-2 text-sm text-gray-500 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              <RefreshCw size={14} className={isFetching ? "animate-spin" : ""} />
              Atualizar
            </button>
          )}
        </div>

        {/* Tabs */}
        {deviceId && (
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => { setResource(tab.key); setExpandedRow(null); }}
                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  resource === tab.key
                    ? "bg-white shadow-sm text-gray-900"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        )}

        {/* Content */}
        {!deviceId && (
          <div className="py-20 text-center text-gray-400">
            <Radar size={40} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm">Selecione um dispositivo para inspecionar sua configuração ao vivo.</p>
          </div>
        )}

        {deviceId && isLoading && (
          <div className="py-16 text-center text-gray-400">
            <RefreshCw size={28} className="mx-auto mb-3 animate-spin text-brand-500" />
            <p className="text-sm">Consultando {selectedDevice?.name ?? "dispositivo"}...</p>
          </div>
        )}

        {deviceId && isError && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
            <XCircle size={32} className="mx-auto mb-2 text-red-400" />
            <p className="text-sm font-medium text-red-700">Falha ao conectar ao dispositivo</p>
            <p className="text-xs text-red-500 mt-1">
              {(error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Verifique as credenciais e a conectividade."}
            </p>
            <button
              onClick={() => refetch()}
              className="mt-4 px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700"
            >
              Tentar novamente
            </button>
          </div>
        )}

        {deviceId && !isLoading && !isError && items.length === 0 && (
          <div className="py-16 text-center text-gray-400 bg-white rounded-xl border border-gray-200">
            <p className="text-sm">Nenhum item encontrado nesta categoria.</p>
          </div>
        )}

        {deviceId && !isLoading && !isError && items.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            {/* Table header */}
            <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
              <p className="text-xs text-gray-500">
                <span className="font-semibold text-gray-700">{items.length}</span>{" "}
                {resource === "rules" ? "regra(s)" :
                 resource === "nat" ? "política(s) NAT" :
                 resource === "routes" ? "rota(s)" :
                 resource === "content_filter" ? "objeto(s) Content Filter" :
                 resource === "app_rules" ? "objeto(s) App Rules" :
                 "serviço(s)"}{" "}
                — ao vivo de <span className="font-medium">{selectedDevice?.name}</span>
              </p>
              <div className="flex items-center gap-1.5 text-xs text-gray-400">
                {resource === "security" ? (
                  <>
                    <ShieldCheck size={13} className="text-green-500" /> Ativo
                    <ShieldOff size={13} className="text-red-400 ml-2" /> Inativo
                  </>
                ) : (
                  <span>Clique na linha para ver detalhes e ações</span>
                )}
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    <th className="w-8 px-3 py-3" />
                    {cols.map((c) => (
                      <th key={c.key} className="text-left px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide whitespace-nowrap">
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {items.map((item, idx) => (
                    <>
                      <tr
                        key={idx}
                        className="hover:bg-gray-50 cursor-pointer"
                        onClick={() => setExpandedRow(expandedRow === idx ? null : idx)}
                      >
                        <td className="px-3 py-3 text-gray-400">
                          {expandedRow === idx ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                        </td>
                        {cols.map((c) => (
                          <td key={c.key} className="px-3 py-3">
                            <CellValue col={c.key} value={item[c.key]} />
                          </td>
                        ))}
                      </tr>

                      {expandedRow === idx && (
                        <tr key={`${idx}-detail`}>
                          <td colSpan={cols.length + 1} className="bg-gray-50 border-t border-gray-100">
                            <div className="px-6 py-4 space-y-4">
                              {/* Raw / CLI details */}
                              <div>
                                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Dados completos</p>
                                {item.details ? (
                                  <pre className="text-xs bg-gray-900 text-green-300 border border-gray-700 rounded-lg p-3 overflow-auto max-h-48 whitespace-pre-wrap font-mono">
                                    {String(item.details)}
                                  </pre>
                                ) : (
                                  <pre className="text-xs bg-white border border-gray-200 rounded-lg p-3 overflow-auto max-h-40 whitespace-pre-wrap text-gray-700">
                                    {JSON.stringify(
                                      Object.fromEntries(Object.entries(item).filter(([k]) => k !== "raw")),
                                      null,
                                      2
                                    )}
                                  </pre>
                                )}
                              </div>

                              {/* Action buttons */}
                              {resource === "security" ? (
                                <div className="flex gap-3">
                                  <button
                                    onClick={() => editWithAgent(item)}
                                    className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700"
                                  >
                                    <Bot size={15} />
                                    {item.enabled ? "Desativar via Agente" : "Ativar via Agente"}
                                  </button>
                                  <button
                                    onClick={() => navigate(`/templates?vendor=${selectedDevice?.vendor ?? ""}`)}
                                    className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
                                  >
                                    <Terminal size={15} />
                                    Usar Template
                                  </button>
                                </div>
                              ) : (
                                <div className="flex gap-3">
                                  <button
                                    onClick={() => editWithAgent(item)}
                                    className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700"
                                  >
                                    <Bot size={15} />
                                    Editar via Agente IA
                                  </button>
                                  <button
                                    onClick={() => navigate(`/direct-mode?device=${deviceId}`)}
                                    className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
                                  >
                                    <Terminal size={15} />
                                    Editar via Modo Técnico
                                  </button>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </PageWrapper>
  );
}
