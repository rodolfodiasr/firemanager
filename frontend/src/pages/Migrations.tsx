import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRightLeft,
  CheckCircle2,
  ChevronRight,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  Terminal,
  Trash2,
  X,
  XCircle,
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

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function vendorLabel(v: string) {
  return VENDOR_LABEL[v] ?? v;
}

// ── New Migration Modal ───────────────────────────────────────────────────────

function NewMigrationModal({
  devices,
  onClose,
  onCreate,
}: {
  devices: Device[];
  onClose: () => void;
  onCreate: (sourceId: string, targetId: string) => void;
}) {
  const [sourceId, setSourceId] = useState("");
  const [targetId, setTargetId] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourceId || !targetId) return;
    onCreate(sourceId, targetId);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold">Nova Migração de Configuração</h2>
          <button onClick={onClose}><X size={20} /></button>
        </div>
        <p className="text-sm text-gray-500 mb-4">
          O FireManager irá buscar a configuração do switch de origem, analisar com IA e gerar
          os comandos equivalentes para o switch de destino.
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
              {devices.map((d) => (
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
              {devices
                .filter((d) => d.id !== sourceId)
                .map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} — {vendorLabel(d.vendor)} ({d.host})
                  </option>
                ))}
            </select>
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
  onChange,
}: {
  interfaces: ParsedInterface[];
  portMapping: Record<string, string>;
  onChange: (mapping: Record<string, string>) => void;
}) {
  const handleChange = (srcPort: string, tgtPort: string) => {
    onChange({ ...portMapping, [srcPort]: tgtPort });
  };

  if (interfaces.length === 0) {
    return <p className="text-xs text-gray-400">Nenhuma interface encontrada no parser.</p>;
  }

  return (
    <table className="w-full text-sm border-collapse">
      <thead>
        <tr className="bg-gray-50 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
          <th className="px-3 py-2 border-b">Porta origem</th>
          <th className="px-3 py-2 border-b">Modo</th>
          <th className="px-3 py-2 border-b">PVID</th>
          <th className="px-3 py-2 border-b">VLANs Tagged</th>
          <th className="px-3 py-2 border-b">Porta destino</th>
        </tr>
      </thead>
      <tbody>
        {interfaces.map((iface) => (
          <tr key={iface.name} className="border-b last:border-0 hover:bg-gray-50">
            <td className="px-3 py-2 font-mono text-xs">{iface.name}</td>
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
            <td className="px-3 py-2 font-mono text-xs text-gray-400 max-w-[140px]">
              {iface.tagged_vlans.length > 0
                ? iface.tagged_vlans.slice(0, 8).join(", ") + (iface.tagged_vlans.length > 8 ? "…" : "")
                : "—"}
            </td>
            <td className="px-3 py-2">
              <input
                value={portMapping[iface.name] ?? ""}
                onChange={(e) => handleChange(iface.name, e.target.value)}
                placeholder={iface.name}
                className="w-full border rounded px-2 py-1 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
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
  const [mappingDirty, setMappingDirty] = useState(false);

  const { data: migration, isLoading } = useQuery({
    queryKey: ["migration-detail", migrationId],
    queryFn: () => migrationApi.get(migrationId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "analyzing" || status === "applying" ? 3000 : false;
    },
  });

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

  const applyMut = useMutation({
    mutationFn: () => migrationApi.apply(migrationId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["migration-detail", migrationId] });
      qc.invalidateQueries({ queryKey: ["migrations"] });
      toast.success("Migração iniciada — aguarde conclusão");
    },
    onError: () => toast.error("Erro ao iniciar aplicação"),
  });

  const currentMapping = portMapping ?? migration?.port_mapping ?? {};
  const interfaces = migration?.migration_plan?.interfaces ?? [];
  const vlans = migration?.migration_plan?.vlans ?? {};
  const vlanCount = Object.keys(vlans).length;

  const handleMappingChange = (m: Record<string, string>) => {
    setPortMapping(m);
    setMappingDirty(true);
  };

  const srcDevice = migration ? devicesById[migration.source_device_id] : null;
  const tgtDevice = migration ? devicesById[migration.target_device_id] : null;

  return (
    <div className="fixed inset-0 z-40 flex">
      <div className="flex-1 bg-black/30" onClick={onClose} />
      <div className="w-[680px] bg-white shadow-2xl flex flex-col overflow-hidden">
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
            {/* Route */}
            <div className="flex items-center gap-2 text-sm">
              <span className="font-medium">
                {srcDevice?.name ?? migration.source_device_id.slice(0, 8)}
              </span>
              <span className="text-gray-400">({vendorLabel(migration.source_vendor)})</span>
              <ArrowRightLeft size={14} className="text-gray-400" />
              <span className="font-medium">
                {tgtDevice?.name ?? migration.target_device_id.slice(0, 8)}
              </span>
              <span className="text-gray-400">({vendorLabel(migration.target_vendor)})</span>
              <span className={`ml-auto text-xs px-2 py-1 rounded-full font-medium ${STATUS_STYLE[migration.status]}`}>
                {STATUS_LABEL[migration.status]}
              </span>
            </div>

            {/* Analyzing / Applying spinner */}
            {(migration.status === "analyzing" || migration.status === "applying") && (
              <div className="flex items-center gap-3 bg-blue-50 text-blue-700 rounded-lg px-4 py-3 text-sm">
                <Loader2 className="animate-spin" size={16} />
                {migration.status === "analyzing"
                  ? "Buscando configuração e analisando com IA…"
                  : "Aplicando comandos no dispositivo de destino…"}
              </div>
            )}

            {/* Error */}
            {migration.status === "failed" && migration.error_message && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
                <div className="flex items-center gap-2 font-medium mb-1">
                  <XCircle size={14} /> Erro
                </div>
                <p className="text-xs font-mono">{migration.error_message}</p>
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
              <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
                <div className="flex items-center gap-2 text-amber-700 font-medium text-xs mb-2">
                  <AlertTriangle size={13} /> Avisos ({migration.warnings!.length})
                </div>
                <ul className="space-y-1">
                  {migration.warnings!.map((w, i) => (
                    <li key={i} className="text-xs text-amber-800">• {w}</li>
                  ))}
                </ul>
              </div>
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
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-gray-700">Mapeamento de portas</h3>
                  {mappingDirty && (
                    <button
                      onClick={() => saveMapping.mutate(currentMapping)}
                      disabled={saveMapping.isPending}
                      className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50"
                    >
                      {saveMapping.isPending ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                      Salvar mapeamento
                    </button>
                  )}
                </div>
                <p className="text-xs text-gray-400 mb-3">
                  Edite a coluna "Porta destino" para mapear cada porta da origem ao nome correto
                  no switch de destino. Clique em "Salvar mapeamento" para regenerar os comandos.
                </p>
                <div className="border rounded-lg overflow-hidden">
                  <PortMappingTable
                    interfaces={interfaces}
                    portMapping={currentMapping}
                    onChange={handleMappingChange}
                  />
                </div>
              </div>
            )}

            {/* Commands preview */}
            {migration.commands_preview && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Terminal size={14} className="text-gray-500" />
                  <h3 className="text-sm font-semibold text-gray-700">Preview de comandos</h3>
                </div>
                <pre className="bg-gray-900 text-green-400 text-xs font-mono rounded-lg p-4 overflow-x-auto max-h-64 overflow-y-auto leading-relaxed">
                  {migration.commands_preview}
                </pre>
              </div>
            )}

            {/* Apply button */}
            {migration.status === "ready" && (
              <div className="flex justify-end pt-2">
                <button
                  onClick={() => applyMut.mutate()}
                  disabled={applyMut.isPending || mappingDirty}
                  className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 text-sm font-medium"
                >
                  {applyMut.isPending ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Play size={16} />
                  )}
                  Aplicar no switch de destino
                </button>
              </div>
            )}
            {migration.status === "ready" && mappingDirty && (
              <p className="text-xs text-amber-600 text-right -mt-3">
                Salve o mapeamento antes de aplicar
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
    mutationFn: ({ sourceId, targetId }: { sourceId: string; targetId: string }) =>
      migrationApi.create({ source_device_id: sourceId, target_device_id: targetId }),
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

  return (
    <PageWrapper
      title="Migração de Configuração"
      subtitle="Migre configurações de VLAN e interfaces entre switches de diferentes fabricantes."
    >
      {/* Header actions */}
      <div className="flex justify-end mb-4">
        <button
          onClick={() => setShowNew(true)}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700"
        >
          <Plus size={16} />
          Nova Migração
        </button>
      </div>

      {/* List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="animate-spin text-brand-600" size={28} />
        </div>
      ) : migrations.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
          <ArrowRightLeft size={40} className="mb-3 opacity-30" />
          <p className="text-sm">Nenhuma migração criada ainda.</p>
          <p className="text-xs mt-1">Clique em "Nova Migração" para começar.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide border-b">
                <th className="px-5 py-3">Rota</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Criado em</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody>
              {migrations.map((m: MigrationListItem) => {
                const src = devicesById[m.source_device_id];
                const tgt = devicesById[m.target_device_id];
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

      {/* New migration modal */}
      {showNew && (
        <NewMigrationModal
          devices={devices}
          onClose={() => setShowNew(false)}
          onCreate={(sourceId, targetId) => createMut.mutate({ sourceId, targetId })}
        />
      )}

      {/* Detail slide-over */}
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
