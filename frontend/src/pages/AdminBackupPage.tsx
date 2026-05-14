import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Database, Plus, Trash2, Play, RefreshCw, CheckCircle2,
  XCircle, Clock, Loader2, HardDrive, Cloud, Server,
} from "lucide-react";
import toast from "react-hot-toast";
import { PageWrapper } from "../components/layout/PageWrapper";
import { adminBackupApi, type BackupConfig, type BackupConfigCreate } from "../api/backup";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatBytes(bytes: number | null): string {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" });
}

const DEST_ICONS = {
  local: HardDrive,
  s3:    Cloud,
  sftp:  Server,
};

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-700",
  running: "bg-blue-100 text-blue-700",
  success: "bg-green-100 text-green-700",
  failed:  "bg-red-100 text-red-700",
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  pending: <Clock size={12} />,
  running: <Loader2 size={12} className="animate-spin" />,
  success: <CheckCircle2 size={12} />,
  failed:  <XCircle size={12} />,
};

// ── New Config Form ───────────────────────────────────────────────────────────

function NewConfigForm({ onCreated }: { onCreated: () => void }) {
  const [dest, setDest] = useState<"local" | "s3" | "sftp">("local");
  const [form, setForm] = useState<BackupConfigCreate>({
    name: "",
    destination: "local",
    schedule_cron: null,
    retention_count: 7,
  });

  const qc = useQueryClient();
  const create = useMutation({
    mutationFn: () => adminBackupApi.createConfig({ ...form, destination: dest }),
    onSuccess: () => {
      toast.success("Configuração criada");
      qc.invalidateQueries({ queryKey: ["admin-backup-configs"] });
      onCreated();
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Erro ao criar"),
  });

  const set = (k: keyof BackupConfigCreate, v: any) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-xl p-5 space-y-4">
      <p className="text-sm font-semibold text-gray-700">Nova Configuração de Backup (Plataforma)</p>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Nome</label>
          <input
            value={form.name}
            onChange={(e) => set("name", e.target.value)}
            placeholder="Ex: Backup Diário"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Destino</label>
          <select
            value={dest}
            onChange={(e) => { setDest(e.target.value as any); set("destination", e.target.value); }}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="local">Local (volume Docker)</option>
            <option value="s3">Amazon S3</option>
            <option value="sftp">SFTP</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Agendamento (cron)</label>
          <input
            value={form.schedule_cron ?? ""}
            onChange={(e) => set("schedule_cron", e.target.value || null)}
            placeholder="Ex: 0 2 * * * (02h diário)"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Retenção (nº de cópias)</label>
          <input
            type="number" min={1} max={90}
            value={form.retention_count}
            onChange={(e) => set("retention_count", parseInt(e.target.value) || 7)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
      </div>

      {dest === "local" && (
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Caminho local</label>
          <input
            value={form.local_path ?? ""}
            onChange={(e) => set("local_path", e.target.value || null)}
            placeholder="/tmp/firemanager_backups"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
      )}

      {dest === "s3" && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Bucket</label>
            <input value={form.s3_bucket ?? ""} onChange={(e) => set("s3_bucket", e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Prefixo / pasta</label>
            <input value={form.s3_prefix ?? ""} onChange={(e) => set("s3_prefix", e.target.value)}
              placeholder="backups/firemanager"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Região</label>
            <input value={form.s3_region ?? ""} onChange={(e) => set("s3_region", e.target.value)}
              placeholder="us-east-1"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Access Key ID</label>
            <input value={form.s3_access_key ?? ""} onChange={(e) => set("s3_access_key", e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div className="col-span-2">
            <label className="block text-xs font-medium text-gray-600 mb-1">Secret Access Key</label>
            <input type="password" value={form.s3_secret_key ?? ""} onChange={(e) => set("s3_secret_key", e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
        </div>
      )}

      {dest === "sftp" && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Host</label>
            <input value={form.sftp_host ?? ""} onChange={(e) => set("sftp_host", e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Porta</label>
            <input type="number" value={form.sftp_port ?? 22} onChange={(e) => set("sftp_port", parseInt(e.target.value))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Usuário</label>
            <input value={form.sftp_user ?? ""} onChange={(e) => set("sftp_user", e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Senha</label>
            <input type="password" value={form.sftp_password ?? ""} onChange={(e) => set("sftp_password", e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div className="col-span-2">
            <label className="block text-xs font-medium text-gray-600 mb-1">Caminho remoto</label>
            <input value={form.sftp_path ?? ""} onChange={(e) => set("sftp_path", e.target.value)}
              placeholder="/backups"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
        </div>
      )}

      <div className="flex gap-2 pt-1">
        <button
          onClick={() => create.mutate()}
          disabled={!form.name || create.isPending}
          className="bg-brand-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-brand-700 disabled:opacity-50"
        >
          {create.isPending ? "Criando..." : "Criar configuração"}
        </button>
        <button
          onClick={onCreated}
          className="border border-gray-300 text-gray-600 text-sm font-medium px-4 py-2 rounded-lg hover:bg-gray-50"
        >
          Cancelar
        </button>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export function AdminBackupPage() {
  const [showForm, setShowForm] = useState(false);
  const qc = useQueryClient();

  const { data: configs = [], isLoading: loadingConfigs } = useQuery({
    queryKey: ["admin-backup-configs"],
    queryFn: adminBackupApi.listConfigs,
  });

  const { data: jobs = [], isLoading: loadingJobs, refetch: refetchJobs } = useQuery({
    queryKey: ["admin-backup-jobs"],
    queryFn: adminBackupApi.listJobs,
    refetchInterval: 5000,
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => adminBackupApi.deleteConfig(id),
    onSuccess: () => {
      toast.success("Configuração removida");
      qc.invalidateQueries({ queryKey: ["admin-backup-configs"] });
    },
  });

  const runMut = useMutation({
    mutationFn: (configId: string) => adminBackupApi.triggerBackup(configId),
    onSuccess: (d) => {
      toast.success(`Backup iniciado (job ${d.job_id.slice(0, 8)}…)`);
      qc.invalidateQueries({ queryKey: ["admin-backup-jobs"] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Erro ao iniciar backup"),
  });

  const restoreMut = useMutation({
    mutationFn: (jobId: string) => adminBackupApi.triggerRestore(jobId),
    onSuccess: () => toast.success("Restore iniciado — aguarde a conclusão"),
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Erro ao iniciar restore"),
  });

  const runningJobs = jobs.filter((j) => j.status === "pending" || j.status === "running");

  return (
    <PageWrapper title="Backup & Restore — Plataforma">
      {runningJobs.length > 0 && (
        <div className="mb-4 bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 flex items-center gap-2 text-sm text-blue-800">
          <Loader2 size={15} className="animate-spin shrink-0" />
          {runningJobs.length} job(s) em andamento — atualizando a cada 5s
        </div>
      )}

      {/* Configurations */}
      <div className="bg-white rounded-xl border border-gray-200 mb-6">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <Database size={16} className="text-brand-600" />
            <span className="font-semibold text-gray-800 text-sm">Configurações de Backup</span>
          </div>
          <button
            onClick={() => setShowForm((v) => !v)}
            className="flex items-center gap-1.5 bg-brand-600 text-white text-xs font-medium px-3 py-1.5 rounded-lg hover:bg-brand-700"
          >
            <Plus size={13} />
            Nova configuração
          </button>
        </div>

        <div className="p-5 space-y-4">
          {showForm && <NewConfigForm onCreated={() => setShowForm(false)} />}

          {loadingConfigs ? (
            <p className="text-sm text-gray-400">Carregando...</p>
          ) : configs.length === 0 ? (
            <p className="text-sm text-gray-400">Nenhuma configuração criada. Crie uma para habilitar backups agendados ou manuais.</p>
          ) : (
            <div className="space-y-2">
              {configs.map((cfg) => {
                const DestIcon = DEST_ICONS[cfg.destination] ?? HardDrive;
                return (
                  <div key={cfg.id} className="flex items-center justify-between bg-gray-50 rounded-lg px-4 py-3 border border-gray-100">
                    <div className="flex items-center gap-3">
                      <DestIcon size={16} className="text-gray-500 shrink-0" />
                      <div>
                        <p className="text-sm font-medium text-gray-800">{cfg.name}</p>
                        <p className="text-xs text-gray-500 mt-0.5">
                          {cfg.destination === "local" && (cfg.local_path || "/tmp/firemanager_backups")}
                          {cfg.destination === "s3" && `s3://${cfg.s3_bucket}/${cfg.s3_prefix || ""}`}
                          {cfg.destination === "sftp" && `sftp://${cfg.sftp_host}${cfg.sftp_path || "/backups"}`}
                          {" · "}
                          {cfg.schedule_cron ? `cron: ${cfg.schedule_cron}` : "manual"}
                          {" · "}
                          retenção: {cfg.retention_count} cópias
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => runMut.mutate(cfg.id)}
                        disabled={runMut.isPending}
                        className="flex items-center gap-1 text-xs text-brand-600 border border-brand-200 bg-brand-50 hover:bg-brand-100 px-2.5 py-1 rounded-lg font-medium"
                        title="Executar backup agora"
                      >
                        <Play size={11} />
                        Executar
                      </button>
                      <button
                        onClick={() => deleteMut.mutate(cfg.id)}
                        disabled={deleteMut.isPending}
                        className="text-gray-400 hover:text-red-500 transition-colors"
                        title="Remover configuração"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Job History */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <span className="font-semibold text-gray-800 text-sm">Histórico de Jobs</span>
          <button
            onClick={() => refetchJobs()}
            className="text-gray-400 hover:text-brand-600 transition-colors"
            title="Atualizar"
          >
            <RefreshCw size={14} />
          </button>
        </div>

        {loadingJobs ? (
          <p className="px-5 py-4 text-sm text-gray-400">Carregando...</p>
        ) : jobs.length === 0 ? (
          <p className="px-5 py-4 text-sm text-gray-400">Nenhum job executado ainda.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide border-b border-gray-100">
                <tr>
                  <th className="text-left px-5 py-3">Status</th>
                  <th className="text-left px-5 py-3">Destino</th>
                  <th className="text-left px-5 py-3">Arquivo</th>
                  <th className="text-left px-5 py-3">Tamanho</th>
                  <th className="text-left px-5 py-3">Iniciado em</th>
                  <th className="text-left px-5 py-3">Concluído em</th>
                  <th className="px-5 py-3 w-24" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-gray-50">
                    <td className="px-5 py-3">
                      <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_COLORS[job.status]}`}>
                        {STATUS_ICONS[job.status]}
                        {job.status}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-gray-600">{job.destination}</td>
                    <td className="px-5 py-3 font-mono text-xs text-gray-500 max-w-xs truncate" title={job.file_path ?? ""}>
                      {job.file_path ? job.file_path.split("/").pop() : "—"}
                    </td>
                    <td className="px-5 py-3 text-gray-600">{formatBytes(job.file_size_bytes)}</td>
                    <td className="px-5 py-3 text-gray-500 text-xs">{formatDate(job.started_at)}</td>
                    <td className="px-5 py-3 text-gray-500 text-xs">{formatDate(job.completed_at)}</td>
                    <td className="px-5 py-3">
                      {job.status === "success" && (
                        <button
                          onClick={() => {
                            if (confirm("⚠️ O restore de PLATAFORMA irá sobrescrever todos os dados. Confirma?")) {
                              restoreMut.mutate(job.id);
                            }
                          }}
                          disabled={restoreMut.isPending}
                          className="text-xs text-amber-700 border border-amber-200 bg-amber-50 hover:bg-amber-100 px-2 py-1 rounded font-medium"
                        >
                          Restaurar
                        </button>
                      )}
                      {job.status === "failed" && job.error_message && (
                        <span className="text-xs text-red-500 truncate max-w-[120px] block" title={job.error_message}>
                          {job.error_message.slice(0, 40)}…
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </PageWrapper>
  );
}
