import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRightLeft,
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Cpu,
  EyeOff,
  Loader2,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Save,
  Terminal,
  Trash2,
  Wand2,
  X,
  XCircle,
  Zap,
} from "lucide-react";
import toast from "react-hot-toast";
import { PageWrapper } from "../components/layout/PageWrapper";
import { migrationApi } from "../api/migration";
import { devicesApi } from "../api/devices";
import type { Migration, MigrationListItem, MigrationStatus, ParsedInterface } from "../types/migration";
import type { Device } from "../types/device";

// ── Helpers ───────────────────────────────────────────────────────────────────

const STATUS_LABEL: Record<MigrationStatus, string> = {
  pending:   "Aguardando",
  analyzing: "Analisando",
  ready:     "Pronto",
  applying:  "Aplicando",
  completed: "Concluído",
  failed:    "Falhou",
};

const STATUS_STYLE: Record<MigrationStatus, string> = {
  pending:   "bg-gray-100 text-gray-600",
  analyzing: "bg-blue-100 text-blue-700",
  ready:     "bg-amber-100 text-amber-700",
  applying:  "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  failed:    "bg-red-100 text-red-700",
};

const VENDOR_LABEL: Record<string, string> = {
  edgeswitch: "EdgeSwitch",
  dell_n:     "Dell N-Series",
  cisco_ios:  "Cisco IOS",
  cisco_nxos: "Cisco NX-OS",
  hp_comware: "HP Comware",
  aruba:      "Aruba",
  fortinet:   "Fortinet",
  sonicwall:  "SonicWall",
  pfsense:    "pfSense",
  opnsense:   "OPNsense",
  mikrotik:   "MikroTik",
  ubiquiti:   "Ubiquiti EdgeOS",
  juniper:    "Juniper",
  dell:       "Dell OS10",
};

const AI_LEVELS = [
  {
    level: 1,
    label: "Determinístico",
    desc: "Parser + renderer — rápido, sem IA",
    icon: Cpu,
    color: "text-gray-600",
    border: "border-gray-300",
    bg: "bg-gray-50",
    activeBorder: "border-gray-500",
    activeBg: "bg-gray-100",
  },
  {
    level: 2,
    label: "Híbrido (padrão)",
    desc: "Renderer + revisão Claude — recomendado",
    icon: Zap,
    color: "text-brand-600",
    border: "border-brand-200",
    bg: "bg-brand-50",
    activeBorder: "border-brand-500",
    activeBg: "bg-brand-100",
  },
  {
    level: 3,
    label: "IA Completa",
    desc: "Claude gera tudo do zero — máxima qualidade",
    icon: Brain,
    color: "text-purple-600",
    border: "border-purple-200",
    bg: "bg-purple-50",
    activeBorder: "border-purple-500",
    activeBg: "bg-purple-100",
  },
];

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function vendorLabel(v: string) {
  return VENDOR_LABEL[v] ?? v;
}

function aiLevelBadge(level: number) {
  if (level === 1) return { label: "Determinístico", cls: "bg-gray-100 text-gray-600" };
  if (level === 3) return { label: "IA Completa", cls: "bg-purple-100 text-purple-700" };
  return { label: "Híbrido", cls: "bg-brand-100 text-brand-700" };
}

// ── Port type badges ──────────────────────────────────────────────────────────

const PORT_TYPE_BADGE: Record<string, { label: string; cls: string }> = {
  ethernet: { label: "Eth",   cls: "bg-gray-100 text-gray-600" },
  fiber:    { label: "Fibra", cls: "bg-purple-100 text-purple-700" },
  lag:      { label: "LAG",   cls: "bg-blue-100 text-blue-700" },
  vlan:     { label: "VLAN",  cls: "bg-green-100 text-green-700" },
  unknown:  { label: "?",     cls: "bg-gray-100 text-gray-400" },
};

// ── Warning categorization ────────────────────────────────────────────────────

type WarnCategory = "action" | "translation" | "feature" | "info";

const WARN_CATEGORIES: Record<WarnCategory, {
  label: string; countBg: string; border: string; textColor: string; headerBg: string;
}> = {
  action:      { label: "Ação obrigatória",      countBg: "bg-red-600",   border: "border-red-200",   textColor: "text-red-800",   headerBg: "bg-red-50"   },
  translation: { label: "Adaptação de tradução", countBg: "bg-amber-500", border: "border-amber-200", textColor: "text-amber-800", headerBg: "bg-amber-50" },
  feature:     { label: "Diferença de recurso",  countBg: "bg-blue-600",  border: "border-blue-200",  textColor: "text-blue-800",  headerBg: "bg-blue-50"  },
  info:        { label: "Informativo",            countBg: "bg-gray-400",  border: "border-gray-200",  textColor: "text-gray-600",  headerBg: "bg-gray-50"  },
};

const WARN_ORDER: WarnCategory[] = ["action", "translation", "feature", "info"];

function categorizeWarning(w: string): WarnCategory {
  const low = w.toLowerCase();
  if (/adicione manualmente|configure manualmente|ajuste manualmente|crie manualmente|criar manualmente|sem vlan de acesso|não foi migrada/.test(low))
    return "action";
  if (/poe|não tem equivalente direto|stp edged|verifique sint|não suportar|firmware comware/.test(low))
    return "feature";
  if (/traduzida como|classificou|incorretamente|participation|foram omitidas|trunk permit|foram permitidas|pvid|ignorada|mesma situação/.test(low))
    return "translation";
  return "info";
}

// ── New Migration Modal ───────────────────────────────────────────────────────

function NewMigrationModal({
  devices,
  onClose,
  onCreate,
}: {
  devices: Device[];
  onClose: () => void;
  onCreate: (sourceId: string, targetId: string, aiLevel: number) => void;
}) {
  const [sourceId, setSourceId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [aiLevel, setAiLevel] = useState(2);
  const switchDevices = devices.filter((d) =>
    d.category === "switch" || d.category === "routing"
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourceId || !targetId) return;
    onCreate(sourceId, targetId, aiLevel);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold">Nova Migração de Configuração</h2>
          <button onClick={onClose}><X size={20} /></button>
        </div>
        <p className="text-sm text-gray-500 mb-4">
          O FireManager irá buscar a configuração do switch de origem e gerar os comandos
          equivalentes para o switch de destino.
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Switch de origem <span className="text-gray-400">(atual)</span>
            </label>
            <select
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value)}
              required
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="">Selecione…</option>
              {switchDevices.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} — {vendorLabel(d.vendor)} ({d.host})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Switch de destino <span className="text-gray-400">(novo)</span>
            </label>
            <select
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
              required
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="">Selecione…</option>
              {switchDevices
                .filter((d) => d.id !== sourceId)
                .map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} — {vendorLabel(d.vendor)} ({d.host})
                  </option>
                ))}
            </select>
          </div>

          {/* AI Level selector */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Modo de análise
            </label>
            <div className="grid grid-cols-3 gap-2">
              {AI_LEVELS.map(({ level, label, desc, icon: Icon, color, activeBorder, activeBg }) => (
                <button
                  key={level}
                  type="button"
                  onClick={() => setAiLevel(level)}
                  className={`flex flex-col items-center text-center p-2.5 rounded-lg border-2 transition-all ${
                    aiLevel === level
                      ? `${activeBorder} ${activeBg}`
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <Icon size={18} className={aiLevel === level ? color : "text-gray-400"} />
                  <span className={`text-xs font-semibold mt-1 ${aiLevel === level ? color : "text-gray-600"}`}>
                    {label}
                  </span>
                  <span className="text-[10px] text-gray-400 mt-0.5 leading-tight">{desc}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={!sourceId || !targetId}
              className="px-4 py-2 text-sm text-white bg-brand-600 rounded-lg hover:bg-brand-700 disabled:opacity-50"
            >
              Criar migração
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Port Mapping Table ────────────────────────────────────────────────────────

function PortMappingTable({
  interfaces,
  portMapping,
  excludedPorts,
  onChange,
  onToggleExclude,
}: {
  interfaces: ParsedInterface[];
  portMapping: Record<string, string>;
  excludedPorts: Set<string>;
  onChange: (mapping: Record<string, string>) => void;
  onToggleExclude: (portName: string) => void;
}) {
  const handleChange = (srcPort: string, tgtPort: string) => {
    onChange({ ...portMapping, [srcPort]: tgtPort });
  };

  if (interfaces.length === 0) {
    return <p className="text-xs text-gray-400">Nenhuma interface encontrada no parser.</p>;
  }

  // Group by port type; preserve original order within each group
  const groups: Array<{ label: string; type: string; ifaces: ParsedInterface[] }> = [
    { label: "Ethernet (cobre)",  type: "ethernet", ifaces: interfaces.filter((i) => (i.port_type ?? "ethernet") === "ethernet") },
    { label: "Fibra / SFP",       type: "fiber",    ifaces: interfaces.filter((i) => i.port_type === "fiber") },
    { label: "LAG / Agregação",   type: "lag",      ifaces: interfaces.filter((i) => i.port_type === "lag") },
    { label: "Outros",            type: "other",    ifaces: interfaces.filter((i) => !["ethernet","fiber","lag"].includes(i.port_type ?? "ethernet")) },
  ].filter((g) => g.ifaces.length > 0);

  return (
    <table className="w-full text-sm border-collapse">
      <thead>
        <tr className="bg-gray-50 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
          <th className="px-2 py-2 border-b w-8" title="Incluir na migração">
            <EyeOff size={11} className="text-gray-400" />
          </th>
          <th className="px-3 py-2 border-b">Porta origem</th>
          <th className="px-3 py-2 border-b">Modo</th>
          <th className="px-3 py-2 border-b">PVID</th>
          <th className="px-3 py-2 border-b">VLANs Tagged</th>
          <th className="px-3 py-2 border-b">Porta destino</th>
        </tr>
      </thead>
      <tbody>
        {groups.flatMap((group) => [
          // Group separator
          <tr key={`sep-${group.type}`}>
            <td
              colSpan={6}
              className="px-3 py-1.5 text-[10px] font-bold text-gray-400 uppercase tracking-widest bg-gray-50 border-t border-b"
            >
              {group.label}{" "}
              <span className="font-normal">({group.ifaces.length})</span>
            </td>
          </tr>,
          // Interface rows
          ...group.ifaces.map((iface) => {
            const badge = PORT_TYPE_BADGE[iface.port_type ?? "unknown"] ?? PORT_TYPE_BADGE.unknown;
            const excluded = excludedPorts.has(iface.name);
            return (
              <tr
                key={iface.name}
                className={`border-b last:border-0 transition-colors ${
                  excluded ? "bg-gray-50 opacity-50" : "hover:bg-gray-50"
                }`}
              >
                <td className="px-2 py-2 text-center">
                  <input
                    type="checkbox"
                    checked={!excluded}
                    onChange={() => onToggleExclude(iface.name)}
                    className="rounded border-gray-300 text-brand-600 cursor-pointer"
                    title={excluded ? "Incluir interface" : "Excluir interface"}
                  />
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-1.5">
                    <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded font-semibold ${badge.cls}`}>
                      {badge.label}
                    </span>
                    <span className={`font-mono text-xs ${excluded ? "line-through text-gray-400" : ""}`}>
                      {iface.name}
                    </span>
                  </div>
                  {iface.description && (
                    <div
                      className="text-[10px] text-gray-400 italic pl-0.5 mt-0.5 truncate max-w-[160px]"
                      title={iface.description}
                    >
                      {iface.description}
                    </div>
                  )}
                </td>
                <td className="px-3 py-2">
                  <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                    iface.mode === "trunk"
                      ? "bg-blue-50 text-blue-700"
                      : "bg-gray-100 text-gray-600"
                  }`}>
                    {iface.mode}
                  </span>
                </td>
                <td className="px-3 py-2 font-mono text-xs text-gray-500">{iface.pvid ?? "—"}</td>
                <td className="px-3 py-2 font-mono text-xs text-gray-400 max-w-[110px]">
                  {iface.tagged_vlans.length > 0
                    ? iface.tagged_vlans.slice(0, 6).join(", ") + (iface.tagged_vlans.length > 6 ? "…" : "")
                    : "—"}
                </td>
                <td className="px-3 py-2">
                  <input
                    value={excluded ? "" : (portMapping[iface.name] ?? "")}
                    onChange={(e) => handleChange(iface.name, e.target.value)}
                    disabled={excluded}
                    placeholder={excluded ? "Excluída" : iface.name}
                    className="w-full border rounded px-2 py-1 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-brand-500 disabled:bg-gray-100 disabled:text-gray-400"
                  />
                </td>
              </tr>
            );
          }),
        ])}
      </tbody>
    </table>
  );
}

// ── Auto-Fill Panel ───────────────────────────────────────────────────────────

function AutoFillPanel({
  interfaces,
  targetVendor,
  onApply,
  onClose,
}: {
  interfaces: ParsedInterface[];
  targetVendor: string;
  onApply: (mapping: Record<string, string>) => void;
  onClose: () => void;
}) {
  const isComware = targetVendor === "hp_comware";
  const isCisco   = targetVendor === "cisco_ios" || targetVendor === "cisco_nxos";
  const isDell    = targetVendor === "dell_n";

  const defaultEthPrefix   = isComware ? "GigabitEthernet1/0/" : isCisco ? "GigabitEthernet1/0/" : isDell ? "Gi1/0/" : "";
  const defaultFiberPrefix  = isComware ? "GigabitEthernet1/0/" : isCisco ? "TenGigabitEthernet1/0/" : isDell ? "Te1/0/" : "";
  const defaultFiberStart   = isComware ? 25 : 1;
  const defaultLagPrefix    = isComware ? "Bridge-Aggregation" : isCisco ? "port-channel" : isDell ? "port-channel" : "lag ";

  const [ethPrefix,   setEthPrefix]   = useState(defaultEthPrefix);
  const [ethStart,    setEthStart]    = useState(1);
  const [fiberPrefix, setFiberPrefix] = useState(defaultFiberPrefix);
  const [fiberStart,  setFiberStart]  = useState(defaultFiberStart);
  const [lagPrefix,   setLagPrefix]   = useState(defaultLagPrefix);
  const [lagStart,    setLagStart]    = useState(1);

  const ethPorts   = interfaces.filter((i) => (i.port_type ?? "ethernet") === "ethernet");
  const fiberPorts = interfaces.filter((i) => i.port_type === "fiber");
  const lagPorts   = interfaces.filter((i) => i.port_type === "lag");

  const hasEth   = ethPorts.length > 0;
  const hasFiber = fiberPorts.length > 0;
  const hasLag   = lagPorts.length > 0;

  const handleApply = () => {
    const mapping: Record<string, string> = {};
    if (hasEth && ethPrefix)
      ethPorts.forEach((iface, idx) => { mapping[iface.name] = `${ethPrefix}${ethStart + idx}`; });
    if (hasFiber && fiberPrefix)
      fiberPorts.forEach((iface, idx) => { mapping[iface.name] = `${fiberPrefix}${fiberStart + idx}`; });
    if (hasLag && lagPrefix)
      lagPorts.forEach((iface, idx) => { mapping[iface.name] = `${lagPrefix}${lagStart + idx}`; });
    onApply(mapping);
  };

  return (
    <div className="border border-brand-200 bg-brand-50/50 rounded-lg px-4 py-3 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-brand-700 flex items-center gap-1.5">
          <Wand2 size={13} /> Auto-mapear portas
        </span>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
          <X size={14} />
        </button>
      </div>

      <div className="grid grid-cols-[100px_1fr_56px] gap-x-2 text-[10px] font-semibold text-gray-400 uppercase tracking-wide px-0.5">
        <span>Tipo</span><span>Prefixo destino</span><span>Início</span>
      </div>

      {hasEth && (
        <div className="grid grid-cols-[100px_1fr_56px] gap-x-2 items-center">
          <span className="text-xs text-gray-600 font-medium">
            <span className="bg-gray-100 text-gray-600 text-[10px] px-1.5 py-0.5 rounded font-semibold mr-1">Eth</span>
            {ethPorts.length}x
          </span>
          <input value={ethPrefix} onChange={(e) => setEthPrefix(e.target.value)} placeholder="prefixo"
            className="border rounded px-2 py-1 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-brand-500" />
          <input type="number" value={ethStart} onChange={(e) => setEthStart(Number(e.target.value))}
            className="border rounded px-2 py-1 text-xs font-mono text-center focus:outline-none focus:ring-1 focus:ring-brand-500" />
        </div>
      )}
      {hasFiber && (
        <div className="grid grid-cols-[100px_1fr_56px] gap-x-2 items-center">
          <span className="text-xs text-gray-600 font-medium">
            <span className="bg-purple-100 text-purple-700 text-[10px] px-1.5 py-0.5 rounded font-semibold mr-1">Fibra</span>
            {fiberPorts.length}x
          </span>
          <input value={fiberPrefix} onChange={(e) => setFiberPrefix(e.target.value)} placeholder="prefixo"
            className="border rounded px-2 py-1 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-brand-500" />
          <input type="number" value={fiberStart} onChange={(e) => setFiberStart(Number(e.target.value))}
            className="border rounded px-2 py-1 text-xs font-mono text-center focus:outline-none focus:ring-1 focus:ring-brand-500" />
        </div>
      )}
      {hasLag && (
        <div className="grid grid-cols-[100px_1fr_56px] gap-x-2 items-center">
          <span className="text-xs text-gray-600 font-medium">
            <span className="bg-blue-100 text-blue-700 text-[10px] px-1.5 py-0.5 rounded font-semibold mr-1">LAG</span>
            {lagPorts.length}x
          </span>
          <input value={lagPrefix} onChange={(e) => setLagPrefix(e.target.value)} placeholder="prefixo"
            className="border rounded px-2 py-1 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-brand-500" />
          <input type="number" value={lagStart} onChange={(e) => setLagStart(Number(e.target.value))}
            className="border rounded px-2 py-1 text-xs font-mono text-center focus:outline-none focus:ring-1 focus:ring-brand-500" />
        </div>
      )}

      <p className="text-[10px] text-gray-400">
        Cada porta recebe <code className="font-mono">prefixo + número sequencial</code>. Ajuste conforme o modelo exato.
      </p>
      <div className="flex justify-end">
        <button onClick={handleApply}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-brand-600 text-white rounded-lg hover:bg-brand-700">
          <Wand2 size={12} /> Aplicar sugestão
        </button>
      </div>
    </div>
  );
}

// ── Add Interface Form ────────────────────────────────────────────────────────

function AddInterfaceForm({
  onAdd,
  onClose,
  isPending,
}: {
  onAdd: (data: { name: string; target_name: string; mode: string; pvid: string; tagged_vlans: string[]; port_type: string }) => void;
  onClose: () => void;
  isPending: boolean;
}) {
  const [name, setName]           = useState("");
  const [targetName, setTargetName] = useState("");
  const [mode, setMode]           = useState("access");
  const [pvid, setPvid]           = useState("");
  const [tagged, setTagged]       = useState("");
  const [portType, setPortType]   = useState("ethernet");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !targetName.trim()) return;
    onAdd({
      name: name.trim(),
      target_name: targetName.trim(),
      mode,
      pvid: pvid.trim() || "",
      tagged_vlans: tagged.split(",").map((v) => v.trim()).filter(Boolean),
      port_type: portType,
    });
  };

  return (
    <div className="border border-dashed border-gray-300 rounded-lg px-4 py-3 bg-gray-50 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-gray-600 flex items-center gap-1.5">
          <Plus size={13} /> Adicionar interface manualmente
        </span>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={14} /></button>
      </div>
      <form onSubmit={handleSubmit} className="space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">Nome (origem)</label>
            <input value={name} onChange={(e) => setName(e.target.value)} required placeholder="ex: 0/25"
              className="w-full border rounded px-2 py-1 text-xs font-mono mt-0.5 focus:outline-none focus:ring-1 focus:ring-brand-500" />
          </div>
          <div>
            <label className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">Nome (destino)</label>
            <input value={targetName} onChange={(e) => setTargetName(e.target.value)} required placeholder="ex: GigabitEthernet1/0/25"
              className="w-full border rounded px-2 py-1 text-xs font-mono mt-0.5 focus:outline-none focus:ring-1 focus:ring-brand-500" />
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2">
          <div>
            <label className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">Tipo</label>
            <select value={portType} onChange={(e) => setPortType(e.target.value)}
              className="w-full border rounded px-2 py-1 text-xs mt-0.5 focus:outline-none focus:ring-1 focus:ring-brand-500">
              <option value="ethernet">Ethernet</option>
              <option value="fiber">Fibra</option>
              <option value="lag">LAG</option>
            </select>
          </div>
          <div>
            <label className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">Modo</label>
            <select value={mode} onChange={(e) => setMode(e.target.value)}
              className="w-full border rounded px-2 py-1 text-xs mt-0.5 focus:outline-none focus:ring-1 focus:ring-brand-500">
              <option value="access">Access</option>
              <option value="trunk">Trunk</option>
              <option value="hybrid">Hybrid</option>
            </select>
          </div>
          <div>
            <label className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">PVID</label>
            <input value={pvid} onChange={(e) => setPvid(e.target.value)} placeholder="ex: 100"
              className="w-full border rounded px-2 py-1 text-xs font-mono mt-0.5 focus:outline-none focus:ring-1 focus:ring-brand-500" />
          </div>
        </div>
        {mode === "trunk" && (
          <div>
            <label className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">VLANs Tagged (separadas por vírgula)</label>
            <input value={tagged} onChange={(e) => setTagged(e.target.value)} placeholder="ex: 100,200,300"
              className="w-full border rounded px-2 py-1 text-xs font-mono mt-0.5 focus:outline-none focus:ring-1 focus:ring-brand-500" />
          </div>
        )}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose}
            className="text-xs px-3 py-1.5 text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200">
            Cancelar
          </button>
          <button type="submit" disabled={isPending || !name.trim() || !targetName.trim()}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50">
            {isPending ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
            Adicionar
          </button>
        </div>
      </form>
    </div>
  );
}

// ── Warnings Accordion ────────────────────────────────────────────────────────

function WarningsAccordion({ warnings }: { warnings: string[] }) {
  const [open, setOpen] = useState<Set<WarnCategory>>(new Set(["action", "translation"]));

  const toggle = (cat: WarnCategory) => {
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat); else next.add(cat);
      return next;
    });
  };

  const grouped: Record<WarnCategory, string[]> = { action: [], translation: [], feature: [], info: [] };
  warnings.forEach((w) => grouped[categorizeWarning(w)].push(w));
  const activeCategories = WARN_ORDER.filter((cat) => grouped[cat].length > 0);

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-medium text-gray-500 flex items-center gap-1.5">
          <AlertTriangle size={12} /> {warnings.length} avisos:
        </span>
        {activeCategories.map((cat) => {
          const meta = WARN_CATEGORIES[cat];
          return (
            <button key={cat} onClick={() => toggle(cat)}
              className={`text-[10px] px-2 py-0.5 rounded-full font-semibold text-white ${meta.countBg}`}>
              {grouped[cat].length} {meta.label}
            </button>
          );
        })}
      </div>
      {activeCategories.map((cat) => {
        const meta = WARN_CATEGORIES[cat];
        const isOpen = open.has(cat);
        return (
          <div key={cat} className={`border rounded-lg overflow-hidden ${meta.border}`}>
            <button onClick={() => toggle(cat)}
              className={`w-full flex items-center justify-between px-3 py-2 ${meta.headerBg} hover:brightness-95 transition-all`}>
              <div className="flex items-center gap-2">
                <span className={`text-xs font-semibold ${meta.textColor}`}>{meta.label}</span>
                <span className={`text-[10px] text-white px-1.5 py-0.5 rounded-full font-bold ${meta.countBg}`}>
                  {grouped[cat].length}
                </span>
              </div>
              <ChevronDown size={13} className={`text-gray-400 transition-transform duration-150 ${isOpen ? "rotate-180" : ""}`} />
            </button>
            {isOpen && (
              <ul className="px-3 py-2 space-y-1.5 bg-white">
                {grouped[cat].map((w, i) => (
                  <li key={i} className={`text-xs ${meta.textColor} flex gap-1.5`}>
                    <span className="mt-0.5 shrink-0">•</span>
                    <span>{w}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Detail Slide-Over ─────────────────────────────────────────────────────────

function MigrationDetail({
  migrationId,
  devicesById,
  onClose,
}: {
  migrationId: string;
  devicesById: Record<string, Device>;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [portMapping, setPortMapping] = useState<Record<string, string> | null>(null);
  const [excludedPorts, setExcludedPorts] = useState<Set<string>>(new Set());
  const [mappingDirty, setMappingDirty] = useState(false);
  const [editingCmds, setEditingCmds] = useState(false);
  const [cmdsDraft, setCmdsDraft] = useState("");
  const [showAutoFill, setShowAutoFill] = useState(false);
  const [showAddIface, setShowAddIface] = useState(false);
  // Track migration data initialization to reset local state on fresh loads
  const [initializedFor, setInitializedFor] = useState<string | null>(null);

  const { data: migration, isLoading } = useQuery({
    queryKey: ["migration-detail", migrationId],
    queryFn: () => migrationApi.get(migrationId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "analyzing" || status === "applying" ? 3000 : false;
    },
  });

  // Initialize local port mapping + excluded state from migration data
  if (migration && initializedFor !== migration.id) {
    const pm = migration.port_mapping ?? {};
    const excluded = new Set(
      Object.entries(pm)
        .filter(([, v]) => v === "")
        .map(([k]) => k)
    );
    setPortMapping(pm);
    setExcludedPorts(excluded);
    setMappingDirty(false);
    setInitializedFor(migration.id);
  }

  const saveMapping = useMutation({
    mutationFn: (mapping: Record<string, string>) =>
      migrationApi.updatePortMapping(migrationId, { port_mapping: mapping }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["migration-detail", migrationId] });
      setMappingDirty(false);
      toast.success("Mapeamento salvo — comandos atualizados");
    },
    onError: () => toast.error("Erro ao salvar mapeamento"),
  });

  const saveCommands = useMutation({
    mutationFn: (text: string) => migrationApi.updateCommands(migrationId, text),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["migration-detail", migrationId] });
      setEditingCmds(false);
      toast.success("Comandos salvos");
    },
    onError: () => toast.error("Erro ao salvar comandos"),
  });

  const regenerateMut = useMutation({
    mutationFn: () => {
      const mergedMapping = buildMergedMapping();
      return migrationApi.regenerate(migrationId, { port_mapping: mergedMapping });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["migration-detail", migrationId] });
      qc.invalidateQueries({ queryKey: ["migrations"] });
      setMappingDirty(false);
      setInitializedFor(null); // force re-init after regenerate
      toast.success("Regeneração iniciada — aguarde conclusão");
    },
    onError: () => toast.error("Erro ao iniciar regeneração"),
  });

  const addIfaceMut = useMutation({
    mutationFn: (data: Parameters<typeof migrationApi.addInterface>[1]) =>
      migrationApi.addInterface(migrationId, data),
    onSuccess: (updated) => {
      qc.setQueryData(["migration-detail", migrationId], updated);
      setShowAddIface(false);
      setInitializedFor(null); // force re-init with new interface
      toast.success("Interface adicionada — preview atualizado");
    },
    onError: () => toast.error("Erro ao adicionar interface"),
  });

  const applyMut = useMutation({
    mutationFn: () => migrationApi.apply(migrationId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["migration-detail", migrationId] });
      qc.invalidateQueries({ queryKey: ["migrations"] });
      toast.success("Migração iniciada — aguarde conclusão");
    },
    onError: () => toast.error("Erro ao iniciar aplicação"),
  });

  const retryMut = useMutation({
    mutationFn: () => migrationApi.retry(migrationId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["migration-detail", migrationId] });
      qc.invalidateQueries({ queryKey: ["migrations"] });
      toast.success("Tentando novamente — aguarde conclusão");
    },
    onError: () => toast.error("Erro ao tentar novamente"),
  });

  const currentMapping = portMapping ?? migration?.port_mapping ?? {};
  const interfaces = migration?.migration_plan?.interfaces ?? [];
  const vlans = migration?.migration_plan?.vlans ?? {};
  const vlanCount = Object.keys(vlans).length;

  const ethCount   = interfaces.filter((i) => (i.port_type ?? "ethernet") === "ethernet").length;
  const fiberCount = interfaces.filter((i) => i.port_type === "fiber").length;
  const lagCount   = interfaces.filter((i) => i.port_type === "lag").length;

  // Build merged mapping: excluded ports get "", included ports get their target
  const buildMergedMapping = (): Record<string, string> => {
    const merged = { ...currentMapping };
    interfaces.forEach((iface) => {
      if (excludedPorts.has(iface.name)) {
        merged[iface.name] = "";
      } else if (merged[iface.name] === "") {
        // Was excluded but now included — restore the auto-mapped name or clear for user
        delete merged[iface.name];
      }
    });
    return merged;
  };

  const handleMappingChange = (m: Record<string, string>) => {
    setPortMapping(m);
    setMappingDirty(true);
  };

  const handleToggleExclude = (portName: string) => {
    setExcludedPorts((prev) => {
      const next = new Set(prev);
      if (next.has(portName)) next.delete(portName); else next.add(portName);
      return next;
    });
    setMappingDirty(true);
  };

  const handleAutoFill = (mapping: Record<string, string>) => {
    handleMappingChange({ ...currentMapping, ...mapping });
    setShowAutoFill(false);
  };

  const handleSaveMapping = () => {
    saveMapping.mutate(buildMergedMapping());
  };

  const srcDevice = migration ? devicesById[migration.source_device_id] : null;
  const tgtDevice = migration ? devicesById[migration.target_device_id] : null;
  const aiLvl = migration?.ai_level ?? 2;
  const badge = aiLevelBadge(aiLvl);

  const isEditable = migration?.status === "ready" || migration?.status === "failed";
  const isBusy = migration?.status === "analyzing" || migration?.status === "applying";

  return (
    <div className="fixed inset-0 z-40 flex">
      <div className="flex-1 bg-black/30" onClick={onClose} />
      <div className="w-[760px] bg-white shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-2">
            <ArrowRightLeft size={18} className="text-brand-600" />
            <span className="font-semibold">Detalhes da Migração</span>
          </div>
          <button onClick={onClose}><X size={20} /></button>
        </div>

        {isLoading && (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="animate-spin text-brand-600" size={28} />
          </div>
        )}

        {migration && (
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-5">
            {/* Route + status + ai level */}
            <div className="flex items-center gap-2 text-sm flex-wrap">
              <span className="font-medium">
                {srcDevice?.name ?? migration.source_device_id.slice(0, 8)}
              </span>
              <span className="text-gray-400">({vendorLabel(migration.source_vendor)})</span>
              <ArrowRightLeft size={14} className="text-gray-400" />
              <span className="font-medium">
                {tgtDevice?.name ?? migration.target_device_id.slice(0, 8)}
              </span>
              <span className="text-gray-400">({vendorLabel(migration.target_vendor)})</span>
              <div className="ml-auto flex items-center gap-2">
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${badge.cls}`}>
                  {badge.label}
                </span>
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${STATUS_STYLE[migration.status]}`}>
                  {STATUS_LABEL[migration.status]}
                </span>
              </div>
            </div>

            {/* Analyzing / Applying spinner */}
            {isBusy && (
              <div className="flex items-center gap-3 bg-blue-50 text-blue-700 rounded-lg px-4 py-3 text-sm">
                <Loader2 className="animate-spin" size={16} />
                {migration.status === "analyzing"
                  ? "Buscando configuração e analisando…"
                  : "Aplicando comandos no dispositivo de destino…"}
              </div>
            )}

            {/* Error */}
            {migration.status === "failed" && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2 font-medium">
                    <XCircle size={14} /> Erro na aplicação
                  </div>
                  <button
                    onClick={() => retryMut.mutate()}
                    disabled={retryMut.isPending || mappingDirty || editingCmds}
                    className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
                  >
                    {retryMut.isPending ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                    Tentar novamente
                  </button>
                </div>
                {migration.error_message && (
                  <p className="text-xs font-mono mt-1">{migration.error_message}</p>
                )}
                <p className="text-[10px] text-red-500 mt-2">
                  Edite os comandos abaixo se necessário antes de tentar novamente.
                </p>
              </div>
            )}

            {/* Completed */}
            {migration.status === "completed" && (
              <div className="flex items-center gap-2 bg-green-50 text-green-700 rounded-lg px-4 py-3 text-sm font-medium">
                <CheckCircle2 size={16} /> Migração aplicada com sucesso
              </div>
            )}

            {/* Warnings */}
            {(migration.warnings ?? []).length > 0 && (
              <WarningsAccordion warnings={migration.warnings!} />
            )}

            {/* Parsed summary */}
            {migration.migration_plan && (
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-xl font-bold text-gray-800">{vlanCount}</div>
                  <div className="text-xs text-gray-500">VLANs</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-xl font-bold text-gray-800">{interfaces.length}</div>
                  <div className="text-xs text-gray-500">Interfaces</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-xl font-bold text-gray-800">
                    {interfaces.filter((i) => i.mode === "trunk").length}
                  </div>
                  <div className="text-xs text-gray-500">Trunks</div>
                </div>
              </div>
            )}

            {/* Port mapping */}
            {migration.migration_plan && migration.status !== "pending" && migration.status !== "analyzing" && (
              <div>
                {/* Header row */}
                <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
                  <h3 className="text-sm font-semibold text-gray-700">Mapeamento de portas</h3>
                  <div className="flex items-center gap-2 flex-wrap">
                    <button
                      onClick={() => setShowAutoFill((v) => !v)}
                      className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border transition-colors ${
                        showAutoFill
                          ? "bg-brand-100 text-brand-700 border-brand-300"
                          : "text-brand-700 bg-brand-50 border-brand-200 hover:bg-brand-100"
                      }`}
                    >
                      <Wand2 size={12} /> Auto-mapear
                    </button>
                    <button
                      onClick={() => setShowAddIface((v) => !v)}
                      className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border transition-colors ${
                        showAddIface
                          ? "bg-gray-200 text-gray-700 border-gray-400"
                          : "text-gray-600 bg-gray-100 border-gray-300 hover:bg-gray-200"
                      }`}
                    >
                      <Plus size={12} /> Adicionar
                    </button>
                    {mappingDirty && (
                      <button
                        onClick={handleSaveMapping}
                        disabled={saveMapping.isPending}
                        className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50"
                      >
                        {saveMapping.isPending ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                        Salvar mapeamento
                      </button>
                    )}
                  </div>
                </div>

                {/* Port type summary + excluded count */}
                <div className="flex items-center gap-1.5 flex-wrap mb-2">
                  <span className="text-[10px] text-gray-400 font-medium">Origem:</span>
                  {ethCount > 0 && (
                    <span className="text-[10px] bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded font-mono">
                      {ethCount}× Ethernet
                    </span>
                  )}
                  {fiberCount > 0 && (
                    <span className="text-[10px] bg-purple-50 text-purple-700 px-1.5 py-0.5 rounded font-mono">
                      {fiberCount}× Fibra
                    </span>
                  )}
                  {lagCount > 0 && (
                    <span className="text-[10px] bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded font-mono">
                      {lagCount}× LAG
                    </span>
                  )}
                  {excludedPorts.size > 0 && (
                    <span className="text-[10px] bg-gray-200 text-gray-500 px-1.5 py-0.5 rounded font-mono flex items-center gap-0.5">
                      <EyeOff size={9} /> {excludedPorts.size} excluída{excludedPorts.size > 1 ? "s" : ""}
                    </span>
                  )}
                  <span className="text-[10px] text-gray-300 mx-0.5">→</span>
                  <span className="text-[10px] text-gray-500 font-medium">{vendorLabel(migration.target_vendor)}</span>
                </div>

                {/* Auto-fill panel */}
                {showAutoFill && (
                  <div className="mb-3">
                    <AutoFillPanel
                      interfaces={interfaces}
                      targetVendor={migration.target_vendor}
                      onApply={handleAutoFill}
                      onClose={() => setShowAutoFill(false)}
                    />
                  </div>
                )}

                {/* Add interface form */}
                {showAddIface && (
                  <div className="mb-3">
                    <AddInterfaceForm
                      onAdd={(data) => addIfaceMut.mutate(data)}
                      onClose={() => setShowAddIface(false)}
                      isPending={addIfaceMut.isPending}
                    />
                  </div>
                )}

                <p className="text-xs text-gray-400 mb-2">
                  Use o checkbox para excluir interfaces da migração. Edite "Porta destino" para ajustar
                  nomes. Clique em "Salvar mapeamento" para re-renderizar sem IA, ou "Regenerar" para aplicar IA.
                </p>
                <div className="border rounded-lg overflow-hidden">
                  <PortMappingTable
                    interfaces={interfaces}
                    portMapping={currentMapping}
                    excludedPorts={excludedPorts}
                    onChange={handleMappingChange}
                    onToggleExclude={handleToggleExclude}
                  />
                </div>
              </div>
            )}

            {/* Commands preview */}
            {migration.commands_preview && (
              <div>
                <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <Terminal size={14} className="text-gray-500" />
                    <h3 className="text-sm font-semibold text-gray-700">Preview de comandos</h3>
                  </div>
                  <div className="flex items-center gap-2">
                    {/* Regenerate button */}
                    {isEditable && !editingCmds && (
                      <button
                        onClick={() => regenerateMut.mutate()}
                        disabled={regenerateMut.isPending || editingCmds}
                        className="flex items-center gap-1.5 text-xs px-2.5 py-1 text-purple-700 bg-purple-50 border border-purple-200 rounded-lg hover:bg-purple-100 disabled:opacity-50"
                        title={`Regenerar com ${aiLvl === 1 ? "renderer" : aiLvl === 2 ? "Claude (revisão)" : "Claude (completo)"}`}
                      >
                        {regenerateMut.isPending
                          ? <Loader2 size={12} className="animate-spin" />
                          : <Brain size={12} />}
                        Regenerar{aiLvl >= 2 ? " com IA" : ""}
                      </button>
                    )}
                    {isEditable && !editingCmds && (
                      <button
                        onClick={() => { setCmdsDraft(migration.commands_preview ?? ""); setEditingCmds(true); }}
                        className="flex items-center gap-1.5 text-xs px-2.5 py-1 text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200"
                      >
                        <Pencil size={12} /> Editar
                      </button>
                    )}
                    {editingCmds && (
                      <div className="flex items-center gap-2">
                        <button onClick={() => setEditingCmds(false)}
                          className="text-xs px-2.5 py-1 text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200">
                          Cancelar
                        </button>
                        <button onClick={() => saveCommands.mutate(cmdsDraft)} disabled={saveCommands.isPending}
                          className="flex items-center gap-1.5 text-xs px-2.5 py-1 text-white bg-brand-600 rounded-lg hover:bg-brand-700 disabled:opacity-50">
                          {saveCommands.isPending ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                          Salvar
                        </button>
                      </div>
                    )}
                  </div>
                </div>
                {editingCmds ? (
                  <textarea
                    value={cmdsDraft}
                    onChange={(e) => setCmdsDraft(e.target.value)}
                    spellCheck={false}
                    className="w-full bg-gray-900 text-green-400 text-xs font-mono rounded-lg p-4 h-64 resize-y leading-relaxed focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                ) : (
                  <pre className="bg-gray-900 text-green-400 text-xs font-mono rounded-lg p-4 overflow-x-auto max-h-64 overflow-y-auto leading-relaxed">
                    {migration.commands_preview}
                  </pre>
                )}
              </div>
            )}

            {/* Apply / hints */}
            {migration.status === "ready" && (
              <div className="flex justify-end pt-2">
                <button
                  onClick={() => applyMut.mutate()}
                  disabled={applyMut.isPending || mappingDirty || editingCmds}
                  className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 text-sm font-medium"
                >
                  {applyMut.isPending ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
                  Aplicar no switch de destino
                </button>
              </div>
            )}
            {migration.status === "ready" && mappingDirty && (
              <p className="text-xs text-amber-600 text-right -mt-3">
                Salve o mapeamento (ou Regenere) antes de aplicar
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export function Migrations() {
  const qc = useQueryClient();
  const [showNew, setShowNew] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  const { data: migrations = [], isLoading } = useQuery({
    queryKey: ["migrations"],
    queryFn: migrationApi.list,
    refetchInterval: 10000,
  });

  const { data: devices = [] } = useQuery({
    queryKey: ["devices"],
    queryFn: devicesApi.list,
  });

  const devicesById = Object.fromEntries(devices.map((d) => [d.id, d]));

  const createMut = useMutation({
    mutationFn: ({ sourceId, targetId, aiLevel }: { sourceId: string; targetId: string; aiLevel: number }) =>
      migrationApi.create({ source_device_id: sourceId, target_device_id: targetId, ai_level: aiLevel }),
    onSuccess: (m) => {
      qc.invalidateQueries({ queryKey: ["migrations"] });
      setShowNew(false);
      setSelectedId(m.id);
      toast.success("Migração criada — analisando configuração…");
    },
    onError: () => toast.error("Erro ao criar migração"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => migrationApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["migrations"] });
      if (selectedId) setSelectedId(null);
      toast.success("Migração excluída");
    },
    onError: () => toast.error("Erro ao excluir migração"),
  });

  const displayedMigrations = migrations.filter((m: MigrationListItem) =>
    showHistory
      ? ["completed", "failed"].includes(m.status)
      : !["completed", "failed"].includes(m.status)
  );

  return (
    <PageWrapper
      title="Migração de Configuração"
      subtitle="Migre configurações de VLAN e interfaces entre switches de diferentes fabricantes."
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          <button
            onClick={() => setShowHistory(false)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${!showHistory ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"}`}
          >
            Ativas
          </button>
          <button
            onClick={() => setShowHistory(true)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${showHistory ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"}`}
          >
            Histórico
          </button>
        </div>
        <button
          onClick={() => setShowNew(true)}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700"
        >
          <Plus size={16} />
          Nova Migração
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="animate-spin text-brand-600" size={28} />
        </div>
      ) : displayedMigrations.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
          <ArrowRightLeft size={40} className="mb-3 opacity-30" />
          <p className="text-sm">{showHistory ? "Nenhuma migração no histórico." : "Nenhuma migração ativa."}</p>
          {!showHistory && <p className="text-xs mt-1">Clique em "Nova Migração" para começar.</p>}
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide border-b">
                <th className="px-5 py-3">Rota</th>
                <th className="px-5 py-3">Modo IA</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Criado em</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody>
              {displayedMigrations.map((m: MigrationListItem) => {
                const src = devicesById[m.source_device_id];
                const tgt = devicesById[m.target_device_id];
                const lvlBadge = aiLevelBadge(m.ai_level);
                return (
                  <tr
                    key={m.id}
                    className="border-b last:border-0 hover:bg-gray-50 cursor-pointer"
                    onClick={() => setSelectedId(m.id)}
                  >
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{src?.name ?? "—"}</span>
                        <span className="text-xs text-gray-400">({vendorLabel(m.source_vendor)})</span>
                        <ArrowRightLeft size={13} className="text-gray-300" />
                        <span className="font-medium">{tgt?.name ?? "—"}</span>
                        <span className="text-xs text-gray-400">({vendorLabel(m.target_vendor)})</span>
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${lvlBadge.cls}`}>
                        {lvlBadge.label}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <span className={`text-xs px-2 py-1 rounded-full font-medium ${STATUS_STYLE[m.status]}`}>
                        {STATUS_LABEL[m.status]}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-gray-500">{fmtDate(m.created_at)}</td>
                    <td className="px-5 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            if (confirm("Excluir esta migração?")) deleteMut.mutate(m.id);
                          }}
                          className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded"
                          title="Excluir"
                        >
                          <Trash2 size={15} />
                        </button>
                        <ChevronRight size={16} className="text-gray-300" />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {showNew && (
        <NewMigrationModal
          devices={devices}
          onClose={() => setShowNew(false)}
          onCreate={(sourceId, targetId, aiLevel) => createMut.mutate({ sourceId, targetId, aiLevel })}
        />
      )}

      {selectedId && (
        <MigrationDetail
          migrationId={selectedId}
          devicesById={devicesById}
          onClose={() => setSelectedId(null)}
        />
      )}
    </PageWrapper>
  );
}
