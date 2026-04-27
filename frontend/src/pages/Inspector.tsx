import React, { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Radar, RefreshCw, Bot, Terminal, ChevronDown, ChevronRight,
  ShieldCheck, ShieldOff, CheckCircle2, XCircle, AlertCircle, Search,
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
    { key: "src_zone", label: "Zona Orig." },
    { key: "dst_zone", label: "Zona Dest." },
    { key: "src", label: "Objeto Origem" },
    { key: "dst", label: "Objeto Destino" },
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
  content_filter: [{ key: "name", label: "Nome" }],
  app_rules:      [{ key: "name", label: "Nome" }],
  security:       [{ key: "service", label: "Serviço" }, { key: "enabled", label: "Status" }],
};

// Search fields per resource (for free-text filter)
const SEARCH_FIELDS: Partial<Record<Resource, string[]>> = {
  rules:  ["name", "src", "dst", "service"],
  nat:    ["name", "source", "destination", "translated_source", "translated_destination"],
  routes: ["name", "destination", "gateway", "interface"],
};

const TYPE_LABELS: Record<string, string> = {
  policy: "Política",
  profile: "Perfil",
  "uri-list-object": "URI List",
  "uri-list-group": "Grupo URI",
  action: "Ação CFS",
  "reputation-object": "Reputação",
  "match-object": "Match Object",
  "action-object": "Action Object",
  raw: "Raw",
};

const TYPE_COLORS: Record<string, { pill: string; badge: string; header: string }> = {
  policy:             { pill: "bg-blue-100 text-blue-700 border-blue-200",    badge: "bg-blue-50 text-blue-700",    header: "bg-blue-50 border-blue-100" },
  profile:            { pill: "bg-purple-100 text-purple-700 border-purple-200", badge: "bg-purple-50 text-purple-700", header: "bg-purple-50 border-purple-100" },
  "uri-list-object":  { pill: "bg-amber-100 text-amber-700 border-amber-200",  badge: "bg-amber-50 text-amber-700",  header: "bg-amber-50 border-amber-100" },
  "uri-list-group":   { pill: "bg-orange-100 text-orange-700 border-orange-200", badge: "bg-orange-50 text-orange-700", header: "bg-orange-50 border-orange-100" },
  action:             { pill: "bg-green-100 text-green-700 border-green-200",  badge: "bg-green-50 text-green-700",  header: "bg-green-50 border-green-100" },
  "reputation-object":{ pill: "bg-red-100 text-red-700 border-red-200",       badge: "bg-red-50 text-red-700",      header: "bg-red-50 border-red-100" },
  "match-object":     { pill: "bg-cyan-100 text-cyan-700 border-cyan-200",     badge: "bg-cyan-50 text-cyan-700",    header: "bg-cyan-50 border-cyan-100" },
  "action-object":    { pill: "bg-indigo-100 text-indigo-700 border-indigo-200", badge: "bg-indigo-50 text-indigo-700", header: "bg-indigo-50 border-indigo-100" },
  raw:                { pill: "bg-gray-100 text-gray-600 border-gray-200",     badge: "bg-gray-50 text-gray-600",    header: "bg-gray-50 border-gray-200" },
};

function typeColor(type: string) {
  const key = type.toLowerCase();
  return TYPE_COLORS[key] ?? { pill: "bg-gray-100 text-gray-600 border-gray-200", badge: "bg-gray-50 text-gray-600", header: "bg-gray-50 border-gray-200" };
}

const GROUPED_RESOURCES: Resource[] = ["content_filter", "app_rules"];

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

function itemKey(item: Record<string, unknown>): string {
  return `${String(item.type ?? "")}::${String(item.name ?? item.service ?? "")}`;
}

function groupByType(items: Record<string, unknown>[]): { type: string; rows: Record<string, unknown>[] }[] {
  const order: string[] = [];
  const map: Record<string, Record<string, unknown>[]> = {};
  for (const item of items) {
    const t = String(item.type ?? "other").toLowerCase();
    if (!map[t]) { map[t] = []; order.push(t); }
    map[t].push(item);
  }
  return order.map((t) => ({ type: t, rows: map[t] }));
}

export function Inspector() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [deviceId, setDeviceId]     = useState(searchParams.get("device") ?? "");
  const [resource, setResource]     = useState<Resource>("rules");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const [searchText, setSearchText] = useState("");
  const [actionFilter, setActionFilter] = useState<"allow" | "deny" | null>(null);
  const [srcZoneFilter, setSrcZoneFilter] = useState("");
  const [dstZoneFilter, setDstZoneFilter] = useState("");
  const [objectFilter, setObjectFilter] = useState("");

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
  const isGrouped = GROUPED_RESOURCES.includes(resource);
  const hasSearch = resource in SEARCH_FIELDS;

  // Attach original 1-based position before any filtering (preserves device order)
  const positionedItems: Record<string, unknown>[] = items.map((item, i) => ({
    ...item,
    _pos: i + 1,
  }));

  // Derive unique zone and object options from rules data
  const uniqueSrcZones = [...new Set(items.map((i) => String(i.src_zone ?? "")).filter(Boolean))].sort();
  const uniqueDstZones = [...new Set(items.map((i) => String(i.dst_zone ?? "")).filter(Boolean))].sort();
  const uniqueObjects  = [...new Set(
    items.flatMap((i) => [String(i.src ?? ""), String(i.dst ?? "")]).filter((v) => v && v.toLowerCase() !== "any")
  )].sort();

  // Apply free-text + action + zone + object filters (rules / nat / routes)
  const filteredItems: Record<string, unknown>[] = hasSearch
    ? positionedItems.filter((item) => {
        if (actionFilter && String(item.action ?? "").toLowerCase() !== actionFilter) return false;
        if (srcZoneFilter && String(item.src_zone ?? "") !== srcZoneFilter) return false;
        if (dstZoneFilter && String(item.dst_zone ?? "") !== dstZoneFilter) return false;
        if (objectFilter) {
          const src = String(item.src ?? "").toLowerCase();
          const dst = String(item.dst ?? "").toLowerCase();
          if (!src.includes(objectFilter.toLowerCase()) && !dst.includes(objectFilter.toLowerCase())) return false;
        }
        if (searchText) {
          const q = searchText.toLowerCase();
          const fields = SEARCH_FIELDS[resource] ?? [];
          if (!fields.some((f) => String(item[f] ?? "").toLowerCase().includes(q))) return false;
        }
        return true;
      })
    : positionedItems;

  // Grouped + type-pill logic (content_filter / app_rules)
  const typeCounts: Record<string, number> = {};
  if (isGrouped) {
    for (const item of items) {
      const t = String(item.type ?? "other").toLowerCase();
      typeCounts[t] = (typeCounts[t] ?? 0) + 1;
    }
  }

  const groupedDisplayItems = isGrouped && typeFilter
    ? positionedItems.filter((item) => String(item.type ?? "").toLowerCase() === typeFilter)
    : positionedItems;

  const groups = isGrouped && !typeFilter ? groupByType(positionedItems) : null;

  // Final display set
  const displayItems = isGrouped ? groupedDisplayItems : filteredItems;

  const activeCount = isGrouped
    ? (typeFilter ? (typeCounts[typeFilter] ?? 0) : items.length)
    : filteredItems.length;

  const hasActiveFilters = !!(searchText || actionFilter || srcZoneFilter || dstZoneFilter || objectFilter);

  function changeResource(r: Resource) {
    setResource(r);
    setExpandedRow(null);
    setTypeFilter(null);
    setSearchText("");
    setActionFilter(null);
    setSrcZoneFilter("");
    setDstZoneFilter("");
    setObjectFilter("");
  }

  function toggleRow(key: string) {
    setExpandedRow(expandedRow === key ? null : key);
  }

  function editWithAgent(item: Record<string, unknown>) {
    navigate(`/agent?device=${deviceId}&seed=${encodeURIComponent(buildSeed(resource, item))}`);
  }

  // Inner components defined here to close over cols, resource, selectedDevice, deviceId
  function ExpandedDetail({ item }: { item: Record<string, unknown> }) {
    return (
      <td colSpan={cols.length + (resource === "rules" ? 3 : 2)} className="bg-gray-50 border-t border-gray-100">
        <div className="px-6 py-4 space-y-4">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Dados completos</p>
            {item.details ? (
              <pre className="text-xs bg-gray-900 text-green-300 border border-gray-700 rounded-lg p-3 overflow-auto max-h-48 whitespace-pre-wrap font-mono">
                {String(item.details)}
              </pre>
            ) : (
              <pre className="text-xs bg-white border border-gray-200 rounded-lg p-3 overflow-auto max-h-40 whitespace-pre-wrap text-gray-700">
                {JSON.stringify(
                  Object.fromEntries(Object.entries(item).filter(([k]) => !k.startsWith("_") && k !== "raw")),
                  null,
                  2
                )}
              </pre>
            )}
          </div>
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
    );
  }

  function DataRow({ item }: { item: Record<string, unknown> }) {
    const key = itemKey(item);
    const expanded = expandedRow === key;
    const disabled = item.enabled === false;

    return (
      <>
        <tr
          className={`cursor-pointer transition-colors ${
            disabled ? "opacity-40 hover:opacity-60" : "hover:bg-gray-50"
          }`}
          onClick={() => toggleRow(key)}
        >
          {/* chevron */}
          <td className="px-3 py-3 text-gray-400 w-8">
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </td>

          {/* priority number — rules only */}
          {resource === "rules" && (
            <td className="px-2 py-3 w-10 text-center">
              <span className="text-xs font-mono text-gray-400 bg-gray-100 rounded px-1.5 py-0.5">
                #{String(item._pos)}
              </span>
            </td>
          )}

          {cols.map((c) => (
            <td key={c.key} className="px-3 py-3">
              <CellValue col={c.key} value={item[c.key]} />
            </td>
          ))}
        </tr>

        {expanded && (
          <tr>
            <ExpandedDetail item={item} />
          </tr>
        )}
      </>
    );
  }

  const actionCounts = {
    allow: items.filter((i) => String(i.action ?? "").toLowerCase() === "allow").length,
    deny:  items.filter((i) => String(i.action ?? "").toLowerCase() === "deny").length,
  };

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
            onChange={(e) => { setDeviceId(e.target.value); setExpandedRow(null); setTypeFilter(null); setSearchText(""); setActionFilter(null); setSrcZoneFilter(""); setDstZoneFilter(""); setObjectFilter(""); }}
            className="flex-1 min-w-[260px] border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">Selecione um dispositivo...</option>
            {devices.map((d: Device) => (
              <option key={d.id} value={d.id}>{d.name} — {d.vendor} ({d.host})</option>
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
                onClick={() => changeResource(tab.key)}
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

        {/* Rules toolbar: search + action + zone + object filters */}
        {deviceId && resource === "rules" && !isLoading && !isError && items.length > 0 && (
          <div className="space-y-2">
            {/* Row 1: search + action */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="relative flex-1 min-w-[220px] max-w-sm">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                <input
                  type="text"
                  value={searchText}
                  onChange={(e) => { setSearchText(e.target.value); setExpandedRow(null); }}
                  placeholder="Buscar por nome, objeto, serviço..."
                  className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 font-medium shrink-0">Ação:</span>
                {(["allow", "deny"] as const).map((a) => (
                  <button
                    key={a}
                    onClick={() => { setActionFilter(actionFilter === a ? null : a); setExpandedRow(null); }}
                    className={`px-3 py-1 rounded-full text-xs font-semibold border transition-colors ${
                      actionFilter === a
                        ? a === "allow" ? "bg-green-600 text-white border-green-600" : "bg-red-600 text-white border-red-600"
                        : a === "allow" ? "bg-green-50 text-green-700 border-green-200 hover:bg-green-100" : "bg-red-50 text-red-700 border-red-200 hover:bg-red-100"
                    }`}
                  >
                    {a === "allow" ? "Allow" : "Deny"} ({actionCounts[a]})
                  </button>
                ))}
              </div>
            </div>

            {/* Row 2: zone origin + zone dest + object */}
            <div className="flex flex-wrap items-center gap-3">
              {uniqueSrcZones.length > 0 && (
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-gray-500 font-medium shrink-0">Zona Origem:</span>
                  <select
                    value={srcZoneFilter}
                    onChange={(e) => { setSrcZoneFilter(e.target.value); setExpandedRow(null); }}
                    className="border border-gray-300 rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500"
                  >
                    <option value="">Todas</option>
                    {uniqueSrcZones.map((z) => <option key={z} value={z}>{z}</option>)}
                  </select>
                </div>
              )}

              {uniqueDstZones.length > 0 && (
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-gray-500 font-medium shrink-0">Zona Destino:</span>
                  <select
                    value={dstZoneFilter}
                    onChange={(e) => { setDstZoneFilter(e.target.value); setExpandedRow(null); }}
                    className="border border-gray-300 rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500"
                  >
                    <option value="">Todas</option>
                    {uniqueDstZones.map((z) => <option key={z} value={z}>{z}</option>)}
                  </select>
                </div>
              )}

              {uniqueObjects.length > 0 && (
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-gray-500 font-medium shrink-0">Objeto:</span>
                  <select
                    value={objectFilter}
                    onChange={(e) => { setObjectFilter(e.target.value); setExpandedRow(null); }}
                    className="border border-gray-300 rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500"
                  >
                    <option value="">Todos</option>
                    {uniqueObjects.map((o) => <option key={o} value={o}>{o}</option>)}
                  </select>
                </div>
              )}

              {(searchText || actionFilter || srcZoneFilter || dstZoneFilter || objectFilter) && (
                <button
                  onClick={() => { setSearchText(""); setActionFilter(null); setSrcZoneFilter(""); setDstZoneFilter(""); setObjectFilter(""); setExpandedRow(null); }}
                  className="text-xs text-gray-400 hover:text-gray-600 underline"
                >
                  Limpar filtros
                </button>
              )}
            </div>
          </div>
        )}

        {/* Generic search bar for NAT / Routes */}
        {deviceId && (resource === "nat" || resource === "routes") && !isLoading && !isError && items.length > 0 && (
          <div className="relative max-w-sm">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
            <input
              type="text"
              value={searchText}
              onChange={(e) => { setSearchText(e.target.value); setExpandedRow(null); }}
              placeholder={`Buscar ${resource === "nat" ? "políticas NAT" : "rotas"}...`}
              className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
        )}

        {/* Type filter pills — content_filter / app_rules */}
        {deviceId && isGrouped && !isLoading && !isError && items.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-gray-500 font-medium">Filtrar por tipo:</span>
            <button
              onClick={() => setTypeFilter(null)}
              className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                typeFilter === null
                  ? "bg-gray-800 text-white border-gray-800"
                  : "bg-white text-gray-600 border-gray-300 hover:border-gray-400"
              }`}
            >
              Todos ({items.length})
            </button>
            {Object.entries(typeCounts).map(([t, count]) => {
              const colors = typeColor(t);
              const active = typeFilter === t;
              return (
                <button
                  key={t}
                  onClick={() => { setTypeFilter(active ? null : t); setExpandedRow(null); }}
                  className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                    active ? `${colors.pill} ring-2 ring-offset-1 ring-current` : `${colors.pill} hover:opacity-80`
                  }`}
                >
                  {TYPE_LABELS[t] ?? t} ({count})
                </button>
              );
            })}
          </div>
        )}

        {/* States */}
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
            <button onClick={() => refetch()} className="mt-4 px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700">
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
            {/* Table header bar */}
            <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
              <p className="text-xs text-gray-500">
                <span className="font-semibold text-gray-700">{activeCount}</span>
                {hasActiveFilters && items.length !== activeCount && (
                  <span className="text-gray-400"> de {items.length}</span>
                )}{" "}
                {resource === "rules" ? "regra(s)" :
                 resource === "nat" ? "política(s) NAT" :
                 resource === "routes" ? "rota(s)" :
                 resource === "content_filter" ? "objeto(s) Content Filter" :
                 resource === "app_rules" ? "objeto(s) App Rules" : "serviço(s)"}
                {typeFilter && <span className="ml-1 text-gray-400">— {TYPE_LABELS[typeFilter] ?? typeFilter}</span>}
                {" "}— ao vivo de <span className="font-medium">{selectedDevice?.name}</span>
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
                    {resource === "rules" && (
                      <th className="w-10 px-2 py-3 text-center text-xs font-semibold text-gray-400 uppercase tracking-wide">#</th>
                    )}
                    {cols.map((c) => (
                      <th key={c.key} className="text-left px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide whitespace-nowrap">
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">

                  {/* Grouped view — content_filter / app_rules without type filter */}
                  {groups && groups.map(({ type, rows }) => {
                    const colors = typeColor(type);
                    const label = TYPE_LABELS[type] ?? type;
                    return (
                      <React.Fragment key={type}>
                        <tr className={`border-y ${colors.header}`}>
                          <td colSpan={cols.length + 2} className="px-4 py-2">
                            <div className="flex items-center gap-2">
                              <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${colors.badge}`}>{label}</span>
                              <span className="text-xs text-gray-400">{rows.length} {rows.length === 1 ? "item" : "itens"}</span>
                            </div>
                          </td>
                        </tr>
                        {rows.map((item) => <DataRow key={itemKey(item)} item={item} />)}
                      </React.Fragment>
                    );
                  })}

                  {/* Flat view — rules / nat / routes / filtered grouped */}
                  {!groups && displayItems.length === 0 && (
                    <tr>
                      <td colSpan={cols.length + (resource === "rules" ? 3 : 2)} className="py-12 text-center text-sm text-gray-400">
                        Nenhuma regra corresponde aos filtros aplicados.
                      </td>
                    </tr>
                  )}
                  {!groups && displayItems.map((item) => (
                    <DataRow key={itemKey(item)} item={item} />
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
