import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRightLeft,
  CheckCircle2,
  ChevronRight,
  Loader2,
  Pencil,
  Play,
  Plus,
  Save,
  Shield,
  Terminal,
  Trash2,
  X,
  XCircle,
} from "lucide-react";
import toast from "react-hot-toast";
import { PageWrapper } from "../components/layout/PageWrapper";
import { firewallMigrationApi } from "../api/firewallMigration";
import { devicesApi } from "../api/devices";
import type {
  FirewallMigration,
  FirewallMigrationListItem,
  FirewallMigrationStatus,
} from "../types/firewallMigration";
import type { Device } from "../types/device";

// ── Helpers ───────────────────────────────────────────────────────────────────

const STATUS_LABEL: Record<FirewallMigrationStatus, string> = {
  pending:   "Aguardando",
  analyzing: "Analisando",
  ready:     "Pronto",
  applying:  "Aplicando",
  completed: "Concluído",
  failed:    "Falhou",
};

const STATUS_STYLE: Record<FirewallMigrationStatus, string> = {
  pending:   "bg-gray-100 text-gray-600",
  analyzing: "bg-blue-100 text-blue-700",
  ready:     "bg-amber-100 text-amber-700",
  applying:  "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  failed:    "bg-red-100 text-red-700",
};

const VENDOR_LABEL: Record<string, string> = {
  fortinet:  "Fortinet",
  sonicwall: "SonicWall",
  sophos:    "Sophos",
  pfsense:   "pfSense",
  opnsense:  "OPNsense",
  mikrotik:  "MikroTik",
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
  const fwDevices = devices.filter((d) => d.category === "firewall");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold">Nova Migração de Regras de Firewall</h2>
          <button onClick={onClose}><X size={20} /></button>
        </div>
        <p className="text-sm text-gray-500 mb-4">
          O FireManager irá buscar as regras do firewall de origem, analisar com IA e gerar
          os comandos equivalentes para o firewall de destino.
        </p>
        <form
          onSubmit={(e) => { e.preventDefault(); if (sourceId && targetId) onCreate(sourceId, targetId); }}
          className="space-y-4"
        >
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Firewall de origem <span className="text-gray-400">(atual)</span>
            </label>
            <select
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value)}
              required
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="">Selecione…</option>
              {fwDevices.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} — {vendorLabel(d.vendor)} ({d.host})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Firewall de destino <span className="text-gray-400">(novo)</span>
            </label>
            <select
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
              required
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="">Selecione…</option>
              {fwDevices
                .filter((d) => d.id !== sourceId)
                .map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} — {vendorLabel(d.vendor)} ({d.host})
                  </option>
                ))}
            </select>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200">
              Cancelar
            </button>
            <button type="submit" disabled={!sourceId || !targetId}
              className="px-4 py-2 text-sm text-white bg-brand-600 rounded-lg hover:bg-brand-700 disabled:opacity-50">
              Criar migração
            </button>
          </div>
        </form>
      </div>
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
  const [editingCmds, setEditingCmds] = useState(false);
  const [cmdsDraft, setCmdsDraft] = useState("");

  const { data: migration, isLoading } = useQuery({
    queryKey: ["fw-migration-detail", migrationId],
    queryFn: () => firewallMigrationApi.get(migrationId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "analyzing" || status === "applying" ? 3000 : false;
    },
  });

  const saveCommands = useMutation({
    mutationFn: (text: string) => firewallMigrationApi.updateCommands(migrationId, text),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fw-migration-detail", migrationId] });
      setEditingCmds(false);
      toast.success("Comandos salvos");
    },
    onError: () => toast.error("Erro ao salvar comandos"),
  });

  const applyMut = useMutation({
    mutationFn: () => firewallMigrationApi.apply(migrationId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fw-migration-detail", migrationId] });
      qc.invalidateQueries({ queryKey: ["fw-migrations"] });
      toast.success("Migração iniciada — aguarde conclusão");
    },
    onError: () => toast.error("Erro ao iniciar aplicação"),
  });

  const ir = migration?.migration_plan;
  const srcDevice = migration ? devicesById[migration.source_device_id ?? ""] : null;
  const tgtDevice = migration ? devicesById[migration.target_device_id ?? ""] : null;

  return (
    <div className="fixed inset-0 z-40 flex">
      <div className="flex-1 bg-black/30" onClick={onClose} />
      <div className="w-[700px] bg-white shadow-2xl flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-2">
            <Shield size={18} className="text-brand-600" />
            <span className="font-semibold">Migração de Regras de Firewall</span>
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
              <span className="font-medium">{srcDevice?.name ?? migration.source_device_id?.slice(0, 8) ?? "—"}</span>
              <span className="text-gray-400">({vendorLabel(migration.source_vendor)})</span>
              <ArrowRightLeft size={14} className="text-gray-400" />
              <span className="font-medium">{tgtDevice?.name ?? migration.target_device_id?.slice(0, 8) ?? "—"}</span>
              <span className="text-gray-400">({vendorLabel(migration.target_vendor)})</span>
              <span className={`ml-auto text-xs px-2 py-1 rounded-full font-medium ${STATUS_STYLE[migration.status]}`}>
                {STATUS_LABEL[migration.status]}
              </span>
            </div>

            {(migration.status === "analyzing" || migration.status === "applying") && (
              <div className="flex items-center gap-3 bg-blue-50 text-blue-700 rounded-lg px-4 py-3 text-sm">
                <Loader2 className="animate-spin" size={16} />
                {migration.status === "analyzing"
                  ? "Buscando regras e analisando com IA…"
                  : "Aplicando regras no firewall de destino…"}
              </div>
            )}

            {migration.status === "failed" && migration.error_message && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
                <div className="flex items-center gap-2 font-medium mb-1"><XCircle size={14} /> Erro</div>
                <p className="text-xs font-mono">{migration.error_message}</p>
              </div>
            )}

            {migration.status === "completed" && (
              <div className="flex items-center gap-2 bg-green-50 text-green-700 rounded-lg px-4 py-3 text-sm font-medium">
                <CheckCircle2 size={16} /> Migração aplicada com sucesso
              </div>
            )}

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

            {/* IR summary */}
            {ir && (
              <div className="grid grid-cols-4 gap-3 text-center">
                {[
                  { label: "Objetos de Endereço", value: ir.address_objects?.length ?? 0 },
                  { label: "Serviços",             value: ir.service_objects?.length ?? 0 },
                  { label: "Políticas",            value: ir.policies?.length ?? 0 },
                  { label: "Rotas",                value: ir.static_routes?.length ?? 0 },
                ].map(({ label, value }) => (
                  <div key={label} className="bg-gray-50 rounded-lg p-3">
                    <div className="text-xl font-bold text-gray-800">{value}</div>
                    <div className="text-xs text-gray-500">{label}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Policies preview table */}
            {ir && ir.policies.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-2">
                  Políticas ({ir.policies.length})
                </h3>
                <div className="border rounded-lg overflow-hidden">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-gray-50 text-left text-gray-500 uppercase tracking-wide">
                        <th className="px-3 py-2 border-b">ID</th>
                        <th className="px-3 py-2 border-b">Nome</th>
                        <th className="px-3 py-2 border-b">Ação</th>
                        <th className="px-3 py-2 border-b">Origem → Destino</th>
                        <th className="px-3 py-2 border-b">Serviços</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ir.policies.slice(0, 20).map((pol) => (
                        <tr key={pol.id} className="border-b last:border-0 hover:bg-gray-50">
                          <td className="px-3 py-1.5 font-mono text-gray-400">{pol.id}</td>
                          <td className="px-3 py-1.5 font-medium">{pol.name || "—"}</td>
                          <td className="px-3 py-1.5">
                            <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                              pol.action === "accept" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
                            }`}>
                              {pol.action}
                            </span>
                          </td>
                          <td className="px-3 py-1.5 text-gray-500">
                            {pol.src_addresses.slice(0, 2).join(", ")} →{" "}
                            {pol.dst_addresses.slice(0, 2).join(", ")}
                          </td>
                          <td className="px-3 py-1.5 text-gray-400">
                            {pol.services.slice(0, 3).join(", ")}
                            {pol.services.length > 3 ? "…" : ""}
                          </td>
                        </tr>
                      ))}
                      {ir.policies.length > 20 && (
                        <tr>
                          <td colSpan={5} className="px-3 py-2 text-xs text-center text-gray-400">
                            … e mais {ir.policies.length - 20} políticas
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Commands preview */}
            {migration.commands_preview && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Terminal size={14} className="text-gray-500" />
                    <h3 className="text-sm font-semibold text-gray-700">Preview de comandos</h3>
                  </div>
                  {migration.status === "ready" && !editingCmds && (
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
                      <button
                        onClick={() => saveCommands.mutate(cmdsDraft)}
                        disabled={saveCommands.isPending}
                        className="flex items-center gap-1.5 text-xs px-2.5 py-1 text-white bg-brand-600 rounded-lg hover:bg-brand-700 disabled:opacity-50"
                      >
                        {saveCommands.isPending ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                        Salvar
                      </button>
                    </div>
                  )}
                </div>
                {editingCmds ? (
                  <textarea
                    value={cmdsDraft}
                    onChange={(e) => setCmdsDraft(e.target.value)}
                    spellCheck={false}
                    className="w-full bg-gray-900 text-green-400 text-xs font-mono rounded-lg p-4 h-72 resize-y leading-relaxed focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                ) : (
                  <pre className="bg-gray-900 text-green-400 text-xs font-mono rounded-lg p-4 overflow-x-auto max-h-72 overflow-y-auto leading-relaxed">
                    {migration.commands_preview}
                  </pre>
                )}
              </div>
            )}

            {migration.status === "ready" && (
              <div className="flex justify-end pt-2">
                <button
                  onClick={() => applyMut.mutate()}
                  disabled={applyMut.isPending || editingCmds}
                  className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 text-sm font-medium"
                >
                  {applyMut.isPending ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
                  Aplicar no firewall de destino
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export function FirewallMigrations() {
  const qc = useQueryClient();
  const [showNew, setShowNew] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: migrations = [], isLoading } = useQuery({
    queryKey: ["fw-migrations"],
    queryFn: firewallMigrationApi.list,
    refetchInterval: 10000,
  });

  const { data: devices = [] } = useQuery({
    queryKey: ["devices"],
    queryFn: devicesApi.list,
  });

  const devicesById = Object.fromEntries(devices.map((d) => [d.id, d]));

  const createMut = useMutation({
    mutationFn: ({ sourceId, targetId }: { sourceId: string; targetId: string }) =>
      firewallMigrationApi.create({ source_device_id: sourceId, target_device_id: targetId }),
    onSuccess: (m) => {
      qc.invalidateQueries({ queryKey: ["fw-migrations"] });
      setShowNew(false);
      setSelectedId(m.id);
      toast.success("Migração criada — analisando regras…");
    },
    onError: () => toast.error("Erro ao criar migração"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => firewallMigrationApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fw-migrations"] });
      if (selectedId) setSelectedId(null);
      toast.success("Migração excluída");
    },
    onError: () => toast.error("Erro ao excluir migração"),
  });

  return (
    <PageWrapper
      title="Migração de Regras de Firewall"
      subtitle="Migre regras, objetos de endereço, serviços e NATs entre firewalls de diferentes fabricantes."
    >
      <div className="flex justify-end mb-4">
        <button
          onClick={() => setShowNew(true)}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700"
        >
          <Plus size={16} /> Nova Migração
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="animate-spin text-brand-600" size={28} />
        </div>
      ) : migrations.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
          <Shield size={40} className="mb-3 opacity-30" />
          <p className="text-sm">Nenhuma migração de firewall criada ainda.</p>
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
              {migrations.map((m: FirewallMigrationListItem) => {
                const src = devicesById[m.source_device_id ?? ""];
                const tgt = devicesById[m.target_device_id ?? ""];
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
          onCreate={(sourceId, targetId) => createMut.mutate({ sourceId, targetId })}
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
