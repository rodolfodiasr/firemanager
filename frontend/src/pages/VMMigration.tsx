import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, RefreshCw, Wifi, WifiOff, Monitor, BookOpen, Loader2, CheckCircle, Clock } from "lucide-react";
import { vmMigrationApi } from "../api/vm_migration";
import type { VmHypervisor, VmInventoryItem, MigrationRunbook, HypervisorType } from "../types/vm_migration";

type Tab = "hypervisors" | "inventory" | "runbooks";

const HYPERVISOR_LABELS: Record<HypervisorType, string> = {
  vmware_vcenter: "VMware vCenter",
  proxmox: "Proxmox",
  hyper_v: "Hyper-V",
};

const POWER_STATE_COLORS: Record<string, string> = {
  poweredOn: "bg-green-900/40 text-green-300",
  poweredOff: "bg-red-900/40 text-red-300",
  suspended: "bg-yellow-900/40 text-yellow-300",
  running: "bg-green-900/40 text-green-300",
  stopped: "bg-red-900/40 text-red-300",
  paused: "bg-yellow-900/40 text-yellow-300",
};

const RUNBOOK_STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-700 text-gray-300",
  generating: "bg-blue-900/40 text-blue-300",
  ready: "bg-green-900/40 text-green-300",
  exported: "bg-purple-900/40 text-purple-300",
};

// ── Add Hypervisor Modal ───────────────────────────────────────────────────────
function AddHypervisorModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [type, setType] = useState<HypervisorType>("vmware_vcenter");
  const [host, setHost] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [verifySsl, setVerifySsl] = useState(true);

  const createMut = useMutation({
    mutationFn: vmMigrationApi.createHypervisor,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["vm-hypervisors"] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 w-full max-w-lg">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-white">Adicionar Hipervisor</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl leading-none">&times;</button>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Nome</label>
            <input
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="ex: vCenter Produção"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Tipo</label>
            <select
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
              value={type}
              onChange={e => setType(e.target.value as HypervisorType)}
            >
              {(Object.entries(HYPERVISOR_LABELS) as [HypervisorType, string][]).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Host / IP</label>
            <input
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
              value={host}
              onChange={e => setHost(e.target.value)}
              placeholder="vcenter.empresa.com ou 192.168.1.10"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Usuário</label>
              <input
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="administrator@vsphere.local"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Senha</label>
              <input
                type="password"
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
                value={password}
                onChange={e => setPassword(e.target.value)}
              />
            </div>
          </div>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={verifySsl}
              onChange={e => setVerifySsl(e.target.checked)}
              className="accent-brand-600"
            />
            <span className="text-sm text-gray-300">Verificar certificado SSL</span>
          </label>
        </div>
        <div className="flex justify-end gap-3 mt-6">
          <button onClick={onClose} className="px-4 py-2 text-sm border border-gray-600 text-gray-300 rounded-lg hover:bg-gray-700">
            Cancelar
          </button>
          <button
            onClick={() => createMut.mutate({
              name, hypervisor_type: type, host, verify_ssl: verifySsl,
              credentials: { username, password },
            })}
            disabled={createMut.isPending || !name || !host || !username}
            className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 flex items-center gap-2"
          >
            {createMut.isPending && <Loader2 size={14} className="animate-spin" />}
            Adicionar
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Hipervisores Tab ───────────────────────────────────────────────────────────
function HypervisorsTab() {
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [testResults, setTestResults] = useState<Record<string, { ok: boolean; error?: string } | null>>({});
  const [syncResults, setSyncResults] = useState<Record<string, number | null>>({});

  const { data: hypervisors = [], isLoading } = useQuery({
    queryKey: ["vm-hypervisors"],
    queryFn: vmMigrationApi.listHypervisors,
  });

  const deleteMut = useMutation({
    mutationFn: vmMigrationApi.deleteHypervisor,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["vm-hypervisors"] }),
  });

  const testMut = useMutation({
    mutationFn: (id: string) => vmMigrationApi.testHypervisor(id),
    onSuccess: (data, id) => setTestResults(r => ({ ...r, [id]: data })),
  });

  const syncMut = useMutation({
    mutationFn: (id: string) => vmMigrationApi.syncHypervisor(id),
    onSuccess: (data, id) => {
      setSyncResults(r => ({ ...r, [id]: data.count }));
      qc.invalidateQueries({ queryKey: ["vm-hypervisors"] });
      qc.invalidateQueries({ queryKey: ["vm-inventory"] });
    },
  });

  return (
    <div>
      <div className="flex justify-end mb-4">
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
        >
          <Plus size={16} /> Adicionar Hipervisor
        </button>
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700">
        {isLoading ? (
          <div className="flex justify-center py-12"><Loader2 className="animate-spin text-brand-500" size={24} /></div>
        ) : hypervisors.length === 0 ? (
          <div className="text-center py-16 text-gray-500">
            <Monitor size={40} className="mx-auto mb-3 opacity-30" />
            <p>Nenhum hipervisor configurado</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Nome</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Tipo</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Host</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Último Sync</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">VMs</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Status</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Ações</th>
              </tr>
            </thead>
            <tbody>
              {hypervisors.map((h: VmHypervisor) => (
                <tr key={h.id} className="border-b border-gray-700/50 hover:bg-gray-700/30">
                  <td className="py-2 px-3 text-white font-medium">{h.name}</td>
                  <td className="py-2 px-3">
                    <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-900/40 text-blue-300">
                      {HYPERVISOR_LABELS[h.hypervisor_type]}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-gray-300 font-mono text-xs">{h.host}</td>
                  <td className="py-2 px-3 text-gray-400 text-xs">
                    {h.last_sync_at ? new Date(h.last_sync_at).toLocaleString("pt-BR") : "—"}
                  </td>
                  <td className="py-2 px-3 text-gray-300 text-xs">
                    {syncResults[h.id] !== undefined ? (
                      <span className="text-green-400">{syncResults[h.id]} VMs sincronizadas</span>
                    ) : (
                      h.last_vm_count ?? "—"
                    )}
                  </td>
                  <td className="py-2 px-3">
                    {testResults[h.id] !== undefined ? (
                      testResults[h.id]?.ok ? (
                        <span className="flex items-center gap-1 text-green-400 text-xs">
                          <Wifi size={12} /> OK
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-red-400 text-xs" title={testResults[h.id]?.error}>
                          <WifiOff size={12} /> Falhou
                        </span>
                      )
                    ) : (
                      <span className={`w-2 h-2 rounded-full inline-block ${h.is_active ? "bg-green-500" : "bg-gray-500"}`} />
                    )}
                  </td>
                  <td className="py-2 px-3">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => testMut.mutate(h.id)}
                        disabled={testMut.isPending}
                        title="Testar conexão"
                        className="text-xs text-blue-400 hover:text-blue-300"
                      >
                        <Wifi size={14} />
                      </button>
                      <button
                        onClick={() => syncMut.mutate(h.id)}
                        disabled={syncMut.isPending}
                        title="Sincronizar VMs"
                        className="text-xs text-green-400 hover:text-green-300"
                      >
                        <RefreshCw size={14} className={syncMut.isPending ? "animate-spin" : ""} />
                      </button>
                      <button
                        onClick={() => { if (confirm("Excluir hipervisor?")) deleteMut.mutate(h.id); }}
                        className="text-red-400 hover:text-red-300"
                        title="Excluir"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showAdd && <AddHypervisorModal onClose={() => setShowAdd(false)} />}
    </div>
  );
}

// ── Create Runbook Modal ───────────────────────────────────────────────────────
function CreateRunbookModal({
  preselectedVmIds,
  hypervisors,
  vms,
  onClose,
}: {
  preselectedVmIds: string[];
  hypervisors: VmHypervisor[];
  vms: VmInventoryItem[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [selectedVms, setSelectedVms] = useState<string[]>(preselectedVmIds);
  const [sourceHv, setSourceHv] = useState("");
  const [targetHv, setTargetHv] = useState("");

  const createMut = useMutation({
    mutationFn: vmMigrationApi.createRunbook,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["vm-runbooks"] });
      onClose();
    },
  });

  const toggleVm = (id: string) =>
    setSelectedVms(vs => vs.includes(id) ? vs.filter(x => x !== id) : [...vs, id]);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between mb-5 flex-shrink-0">
          <h2 className="text-lg font-semibold text-white">Novo Runbook de Migração</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl leading-none">&times;</button>
        </div>
        <div className="flex-1 overflow-y-auto space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Título</label>
            <input
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="ex: Migração Cluster Produção"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Hipervisor Origem</label>
              <select
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
                value={sourceHv}
                onChange={e => setSourceHv(e.target.value)}
              >
                <option value="">Selecionar...</option>
                {hypervisors.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Hipervisor Destino</label>
              <select
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
                value={targetHv}
                onChange={e => setTargetHv(e.target.value)}
              >
                <option value="">Selecionar...</option>
                {hypervisors.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">VMs ({selectedVms.length} selecionadas)</label>
            <div className="max-h-48 overflow-y-auto border border-gray-700 rounded-lg divide-y divide-gray-700">
              {vms.map(vm => (
                <label key={vm.id} className="flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-gray-700/50">
                  <input
                    type="checkbox"
                    checked={selectedVms.includes(vm.id)}
                    onChange={() => toggleVm(vm.id)}
                    className="accent-brand-600"
                  />
                  <span className="text-sm text-gray-300">{vm.vm_name}</span>
                  <span className="text-xs text-gray-500 ml-auto">{vm.os_type ?? "—"}</span>
                </label>
              ))}
              {vms.length === 0 && (
                <div className="text-center text-gray-500 text-sm py-4">Nenhuma VM no inventário</div>
              )}
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-3 pt-4 mt-4 border-t border-gray-700 flex-shrink-0">
          <button onClick={onClose} className="px-4 py-2 text-sm border border-gray-600 text-gray-300 rounded-lg hover:bg-gray-700">
            Cancelar
          </button>
          <button
            onClick={() => createMut.mutate({
              title,
              vm_ids: selectedVms,
              source_hypervisor_id: sourceHv || undefined,
              target_hypervisor_id: targetHv || undefined,
            })}
            disabled={createMut.isPending || !title || selectedVms.length === 0}
            className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 flex items-center gap-2"
          >
            {createMut.isPending && <Loader2 size={14} className="animate-spin" />}
            Criar Runbook
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Inventory Tab ──────────────────────────────────────────────────────────────
function InventoryTab({
  hypervisors,
  onCreateRunbook,
}: {
  hypervisors: VmHypervisor[];
  onCreateRunbook: (vmIds: string[]) => void;
}) {
  const [filterHv, setFilterHv] = useState("");
  const [selectedVms, setSelectedVms] = useState<string[]>([]);

  const { data: vms = [], isLoading } = useQuery({
    queryKey: ["vm-inventory", filterHv],
    queryFn: () => vmMigrationApi.listVms(filterHv || undefined),
  });

  const toggleVm = (id: string) =>
    setSelectedVms(vs => vs.includes(id) ? vs.filter(x => x !== id) : [...vs, id]);

  const toggleAll = () =>
    setSelectedVms(vs => vs.length === vms.length ? [] : vms.map(v => v.id));

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <select
            className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
            value={filterHv}
            onChange={e => setFilterHv(e.target.value)}
          >
            <option value="">Todos os hipervisores</option>
            {hypervisors.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
          </select>
          <span className="text-sm text-gray-400">{vms.length} VMs</span>
        </div>
        {selectedVms.length > 0 && (
          <button
            onClick={() => onCreateRunbook(selectedVms)}
            className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            <BookOpen size={14} /> Criar Runbook ({selectedVms.length} VMs)
          </button>
        )}
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700">
        {isLoading ? (
          <div className="flex justify-center py-12"><Loader2 className="animate-spin text-brand-500" size={24} /></div>
        ) : vms.length === 0 ? (
          <div className="text-center py-16 text-gray-500">
            <Monitor size={40} className="mx-auto mb-3 opacity-30" />
            <p>Nenhuma VM no inventário</p>
            <p className="text-xs mt-1 text-gray-600">Sincronize um hipervisor na aba Hipervisores</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="py-2 px-3 text-left">
                  <input
                    type="checkbox"
                    checked={selectedVms.length === vms.length && vms.length > 0}
                    onChange={toggleAll}
                    className="accent-brand-600"
                  />
                </th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">VM</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Estado</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">OS</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">CPU</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">RAM (GB)</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Disco (GB)</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">IPs</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Sync</th>
              </tr>
            </thead>
            <tbody>
              {vms.map((vm: VmInventoryItem) => (
                <tr key={vm.id} className="border-b border-gray-700/50 hover:bg-gray-700/30">
                  <td className="py-2 px-3">
                    <input
                      type="checkbox"
                      checked={selectedVms.includes(vm.id)}
                      onChange={() => toggleVm(vm.id)}
                      className="accent-brand-600"
                    />
                  </td>
                  <td className="py-2 px-3 text-white font-medium">{vm.vm_name}</td>
                  <td className="py-2 px-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${POWER_STATE_COLORS[vm.power_state] ?? "bg-gray-700 text-gray-300"}`}>
                      {vm.power_state}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-gray-300 text-xs">{vm.os_type ?? "—"}</td>
                  <td className="py-2 px-3 text-gray-300 text-xs">{vm.cpu_count ?? "—"}</td>
                  <td className="py-2 px-3 text-gray-300 text-xs">
                    {vm.ram_mb != null ? (vm.ram_mb / 1024).toFixed(1) : "—"}
                  </td>
                  <td className="py-2 px-3 text-gray-300 text-xs">{vm.disk_gb ?? "—"}</td>
                  <td className="py-2 px-3 text-gray-300 text-xs">{vm.ip_addresses.join(", ") || "—"}</td>
                  <td className="py-2 px-3 text-gray-400 text-xs">
                    {new Date(vm.synced_at).toLocaleString("pt-BR")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ── Runbook View Modal ─────────────────────────────────────────────────────────
function RunbookViewModal({ runbook, onClose }: { runbook: MigrationRunbook; onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 w-full max-w-3xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between mb-4 flex-shrink-0">
          <div>
            <h2 className="text-lg font-semibold text-white">{runbook.title}</h2>
            {runbook.bookstack_page_url && (
              <a
                href={runbook.bookstack_page_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-blue-400 hover:text-blue-300 mt-0.5 inline-block"
              >
                Ver no BookStack
              </a>
            )}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl leading-none">&times;</button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {runbook.ai_runbook ? (
            <pre className="bg-gray-900 border border-gray-600 rounded-lg p-4 text-sm text-gray-300 whitespace-pre-wrap font-sans leading-relaxed">
              {runbook.ai_runbook}
            </pre>
          ) : (
            <div className="text-center text-gray-500 py-12">
              {runbook.status === "generating" ? (
                <div className="flex flex-col items-center gap-3">
                  <Loader2 size={32} className="animate-spin text-blue-400" />
                  <p>Gerando runbook com IA...</p>
                </div>
              ) : (
                <p>Runbook ainda não gerado.</p>
              )}
            </div>
          )}
        </div>
        <div className="flex justify-end mt-4 flex-shrink-0">
          <button onClick={onClose} className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium">
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Runbooks Tab ───────────────────────────────────────────────────────────────
function RunbooksTab({
  hypervisors,
  vms,
  onNewRunbook,
}: {
  hypervisors: VmHypervisor[];
  vms: VmInventoryItem[];
  onNewRunbook: () => void;
}) {
  const [viewingRunbook, setViewingRunbook] = useState<MigrationRunbook | null>(null);

  const { data: runbooks = [], isLoading } = useQuery({
    queryKey: ["vm-runbooks"],
    queryFn: vmMigrationApi.listRunbooks,
    refetchInterval: (query) => {
      const data = query.state.data as MigrationRunbook[] | undefined;
      return data?.some(r => r.status === "generating") ? 10000 : false;
    },
  });

  const hvName = (id: string | null) =>
    id ? (hypervisors.find(h => h.id === id)?.name ?? id.slice(0, 8)) : "—";

  return (
    <div>
      <div className="flex justify-end mb-4">
        <button
          onClick={onNewRunbook}
          className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
        >
          <Plus size={16} /> Novo Runbook
        </button>
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700">
        {isLoading ? (
          <div className="flex justify-center py-12"><Loader2 className="animate-spin text-brand-500" size={24} /></div>
        ) : runbooks.length === 0 ? (
          <div className="text-center py-16 text-gray-500">
            <BookOpen size={40} className="mx-auto mb-3 opacity-30" />
            <p>Nenhum runbook criado</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Título</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Status</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Origem → Destino</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">VMs</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Criado</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Ações</th>
              </tr>
            </thead>
            <tbody>
              {runbooks.map((r: MigrationRunbook) => (
                <tr key={r.id} className="border-b border-gray-700/50 hover:bg-gray-700/30">
                  <td className="py-2 px-3 text-white font-medium">{r.title}</td>
                  <td className="py-2 px-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium flex items-center gap-1 w-fit ${RUNBOOK_STATUS_COLORS[r.status]}`}>
                      {r.status === "generating" && <Loader2 size={10} className="animate-spin" />}
                      {r.status === "ready" && <CheckCircle size={10} />}
                      {r.status === "draft" && <Clock size={10} />}
                      {r.status}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-gray-300 text-xs">
                    {hvName(r.source_hypervisor_id)} → {hvName(r.target_hypervisor_id)}
                  </td>
                  <td className="py-2 px-3 text-gray-400 text-xs">{r.vm_ids.length} VMs</td>
                  <td className="py-2 px-3 text-gray-400 text-xs">
                    {new Date(r.created_at).toLocaleString("pt-BR")}
                  </td>
                  <td className="py-2 px-3">
                    <button
                      onClick={() => setViewingRunbook(r)}
                      className="text-xs text-blue-400 hover:text-blue-300"
                    >
                      Ver
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {viewingRunbook && (
        <RunbookViewModal runbook={viewingRunbook} onClose={() => setViewingRunbook(null)} />
      )}
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────
export function VMMigration() {
  const [tab, setTab] = useState<Tab>("hypervisors");
  const [showRunbookModal, setShowRunbookModal] = useState(false);
  const [preselectedVmIds, setPreselectedVmIds] = useState<string[]>([]);

  const { data: hypervisors = [] } = useQuery({
    queryKey: ["vm-hypervisors"],
    queryFn: vmMigrationApi.listHypervisors,
  });

  const { data: vms = [] } = useQuery({
    queryKey: ["vm-inventory", ""],
    queryFn: () => vmMigrationApi.listVms(),
  });

  const openRunbookModal = (vmIds: string[] = []) => {
    setPreselectedVmIds(vmIds);
    setShowRunbookModal(true);
  };

  return (
    <div className="ml-64 min-h-screen bg-gray-900">
      <div className="p-6 max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white">Migração de VMs</h1>
          <p className="text-sm text-gray-400 mt-1">Inventário de hipervisores e planejamento de migração assistido por IA</p>
        </div>

        <div className="flex gap-1 mb-6 border-b border-gray-700">
          {([
            ["hypervisors", "Hipervisores", Monitor],
            ["inventory", "Inventário de VMs", Monitor],
            ["runbooks", "Runbooks", BookOpen],
          ] as const).map(([key, label, Icon]) => (
            <button
              key={key}
              onClick={() => setTab(key as Tab)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                tab === key
                  ? "border-brand-500 text-brand-400"
                  : "border-transparent text-gray-400 hover:text-gray-200"
              }`}
            >
              <Icon size={16} />{label}
            </button>
          ))}
        </div>

        {tab === "hypervisors" && <HypervisorsTab />}
        {tab === "inventory" && (
          <InventoryTab
            hypervisors={hypervisors}
            onCreateRunbook={(vmIds) => { openRunbookModal(vmIds); setTab("runbooks"); }}
          />
        )}
        {tab === "runbooks" && (
          <RunbooksTab
            hypervisors={hypervisors}
            vms={vms}
            onNewRunbook={() => openRunbookModal()}
          />
        )}
      </div>

      {showRunbookModal && (
        <CreateRunbookModal
          preselectedVmIds={preselectedVmIds}
          hypervisors={hypervisors}
          vms={vms}
          onClose={() => setShowRunbookModal(false)}
        />
      )}
    </div>
  );
}
