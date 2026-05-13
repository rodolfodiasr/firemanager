import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus, Trash2, RefreshCw, Cloud, AlertTriangle, CheckCircle,
  Loader2, X, ChevronDown, ShieldAlert, Shield,
} from "lucide-react";
import toast from "react-hot-toast";
import { cspmApi } from "../api/cspm";
import type { CloudAccount, CloudAccountCreate, CloudFinding } from "../api/cspm";

type Tab = "accounts" | "findings";

const PROVIDER_LABELS: Record<string, string> = {
  aws: "Amazon Web Services",
  azure: "Microsoft Azure",
  gcp: "Google Cloud Platform",
};

const PROVIDER_COLORS: Record<string, string> = {
  aws: "bg-orange-100 text-orange-700",
  azure: "bg-blue-100 text-blue-700",
  gcp: "bg-green-100 text-green-700",
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-700",
  high:     "bg-orange-100 text-orange-700",
  medium:   "bg-yellow-100 text-yellow-700",
  low:      "bg-blue-100 text-blue-700",
  info:     "bg-gray-100 text-gray-600",
};

const STATUS_COLORS: Record<string, string> = {
  open:     "bg-red-50 text-red-600",
  accepted: "bg-yellow-50 text-yellow-700",
  resolved: "bg-green-50 text-green-700",
};

// ── Account Modal ─────────────────────────────────────────────────────────────
function AccountModal({
  account,
  onClose,
}: {
  account?: CloudAccount;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState(account?.name ?? "");
  const [provider, setProvider] = useState(account?.provider ?? "aws");
  const [region, setRegion] = useState(account?.region ?? "");
  const [awsKey, setAwsKey] = useState("");
  const [awsSecret, setAwsSecret] = useState("");
  const [awsRole, setAwsRole] = useState("");
  const [azureClientId, setAzureClientId] = useState("");
  const [azureSecret, setAzureSecret] = useState("");
  const [azureTenant, setAzureTenant] = useState("");
  const [azureSub, setAzureSub] = useState("");
  const [gcpJson, setGcpJson] = useState("");

  const createMut = useMutation({
    mutationFn: (d: CloudAccountCreate) => cspmApi.createAccount(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["cloud-accounts"] }); toast.success("Conta cloud adicionada"); onClose(); },
    onError: () => toast.error("Erro ao adicionar conta"),
  });

  const updateMut = useMutation({
    mutationFn: (d: CloudAccountCreate) => cspmApi.updateAccount(account!.id, d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["cloud-accounts"] }); toast.success("Conta atualizada"); onClose(); },
    onError: () => toast.error("Erro ao atualizar conta"),
  });

  const isLoading = createMut.isPending || updateMut.isPending;

  function buildCredentials(): Record<string, unknown> {
    if (provider === "aws") {
      const creds: Record<string, unknown> = {};
      if (awsRole) creds.role_arn = awsRole;
      else { creds.access_key_id = awsKey; creds.secret_access_key = awsSecret; }
      return creds;
    }
    if (provider === "azure") {
      return { client_id: azureClientId, client_secret: azureSecret, tenant_id: azureTenant, subscription_id: azureSub };
    }
    if (provider === "gcp") {
      try { return JSON.parse(gcpJson); } catch { return {}; }
    }
    return {};
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const payload: CloudAccountCreate = {
      name, provider, region: region || undefined,
      credentials: buildCredentials(),
    };
    account ? updateMut.mutate(payload) : createMut.mutate(payload);
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-5 border-b sticky top-0 bg-white">
          <h2 className="text-lg font-semibold text-gray-900">
            {account ? "Editar Conta Cloud" : "Nova Conta Cloud"}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nome</label>
            <input
              value={name} onChange={e => setName(e.target.value)} required
              placeholder="AWS Produção"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Provider</label>
            <div className="relative">
              <select
                value={provider} onChange={e => setProvider(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm appearance-none focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="aws">Amazon Web Services</option>
                <option value="azure">Microsoft Azure</option>
                <option value="gcp">Google Cloud Platform</option>
              </select>
              <ChevronDown size={14} className="absolute right-3 top-3 text-gray-400 pointer-events-none" />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Região <span className="text-gray-400 font-normal">(opcional)</span></label>
            <input
              value={region} onChange={e => setRegion(e.target.value)}
              placeholder={provider === "aws" ? "us-east-1" : provider === "azure" ? "eastus" : "us-central1"}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          {/* Credentials by provider */}
          {provider === "aws" && (
            <div className="space-y-3 p-3 bg-orange-50 rounded-lg border border-orange-100">
              <p className="text-xs font-semibold text-orange-700 uppercase">Credenciais AWS</p>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">IAM Role ARN <span className="text-gray-400">(recomendado)</span></label>
                <input value={awsRole} onChange={e => setAwsRole(e.target.value)} placeholder="arn:aws:iam::123456:role/EternitySecOps"
                  className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <p className="text-xs text-gray-500">— ou —</p>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Access Key ID</label>
                  <input value={awsKey} onChange={e => setAwsKey(e.target.value)} placeholder="AKIA..."
                    className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Secret Access Key</label>
                  <input type="password" value={awsSecret} onChange={e => setAwsSecret(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
              </div>
            </div>
          )}

          {provider === "azure" && (
            <div className="space-y-3 p-3 bg-blue-50 rounded-lg border border-blue-100">
              <p className="text-xs font-semibold text-blue-700 uppercase">Service Principal Azure</p>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { label: "Client ID", val: azureClientId, set: setAzureClientId, ph: "00000000-..." },
                  { label: "Client Secret", val: azureSecret, set: setAzureSecret, ph: "••••••••" },
                  { label: "Tenant ID", val: azureTenant, set: setAzureTenant, ph: "00000000-..." },
                  { label: "Subscription ID", val: azureSub, set: setAzureSub, ph: "00000000-..." },
                ].map(({ label, val, set, ph }) => (
                  <div key={label}>
                    <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
                    <input value={val} onChange={e => set(e.target.value)} placeholder={ph}
                      className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                  </div>
                ))}
              </div>
            </div>
          )}

          {provider === "gcp" && (
            <div className="p-3 bg-green-50 rounded-lg border border-green-100">
              <label className="block text-xs font-semibold text-green-700 uppercase mb-2">Service Account JSON</label>
              <textarea
                value={gcpJson} onChange={e => setGcpJson(e.target.value)} rows={4}
                placeholder='{"type": "service_account", "project_id": "...", ...}'
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancelar</button>
            <button type="submit" disabled={isLoading}
              className="px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2">
              {isLoading && <Loader2 size={14} className="animate-spin" />}
              {account ? "Salvar" : "Adicionar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Account Card ──────────────────────────────────────────────────────────────
function AccountCard({ account, onEdit }: { account: CloudAccount; onEdit: () => void }) {
  const qc = useQueryClient();

  const deleteMut = useMutation({
    mutationFn: () => cspmApi.deleteAccount(account.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["cloud-accounts"] }); toast.success("Conta desativada"); },
  });

  const syncMut = useMutation({
    mutationFn: () => cspmApi.syncAccount(account.id),
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ["cloud-accounts"] }); toast.success(`Sync concluído: ${r.resources_synced} recursos, ${r.findings_created} findings`); },
    onError: () => toast.error("Erro ao sincronizar conta"),
  });

  const statusColor = account.last_sync_status === "ok" ? "text-green-500" : account.last_sync_status === "error" ? "text-red-500" : "text-gray-400";

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Cloud size={16} className="text-gray-500" />
            <span className="font-semibold text-gray-900">{account.name}</span>
          </div>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${PROVIDER_COLORS[account.provider] ?? "bg-gray-100 text-gray-600"}`}>
            {PROVIDER_LABELS[account.provider] ?? account.provider}
          </span>
        </div>
        <div className="flex gap-1">
          <button onClick={() => syncMut.mutate()} disabled={syncMut.isPending}
            className="p-1.5 text-gray-400 hover:text-brand-600 hover:bg-gray-100 rounded-lg transition-colors" title="Sincronizar">
            <RefreshCw size={14} className={syncMut.isPending ? "animate-spin" : ""} />
          </button>
          <button onClick={onEdit} className="p-1.5 text-gray-400 hover:text-brand-600 hover:bg-gray-100 rounded-lg transition-colors" title="Editar">
            <Shield size={14} />
          </button>
          <button onClick={() => { if (confirm("Desativar esta conta?")) deleteMut.mutate(); }}
            className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors" title="Desativar">
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {account.region && <p className="text-xs text-gray-500 mb-2">Região: {account.region}</p>}

      <div className="flex items-center gap-1.5 text-xs">
        <span className={statusColor}>●</span>
        <span className="text-gray-500">
          {account.last_sync_status === "ok" ? "Sincronizado" : account.last_sync_status === "error" ? "Erro no sync" : account.last_sync_status === "syncing" ? "Sincronizando..." : "Não sincronizado"}
        </span>
        {account.last_sync_at && (
          <span className="text-gray-400">· {new Date(account.last_sync_at).toLocaleString("pt-BR")}</span>
        )}
      </div>
    </div>
  );
}

// ── Findings Tab ──────────────────────────────────────────────────────────────
function FindingsTab() {
  const qc = useQueryClient();
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("open");

  const { data: findings = [], isLoading } = useQuery({
    queryKey: ["cloud-findings", severity, status],
    queryFn: () => cspmApi.listFindings({ ...(severity ? { severity } : {}), ...(status ? { status } : {}), limit: 200 }),
  });

  const acceptMut = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => cspmApi.acceptFinding(id, reason),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["cloud-findings"] }); toast.success("Finding aceito como risco"); },
  });

  return (
    <div>
      <div className="flex items-center gap-3 mb-5">
        {[
          { label: "Severidade", value: severity, onChange: setSeverity, options: [["", "Todas"], ["critical", "Critical"], ["high", "High"], ["medium", "Medium"], ["low", "Low"]] },
          { label: "Status", value: status, onChange: setStatus, options: [["", "Todos"], ["open", "Abertos"], ["accepted", "Aceitos"], ["resolved", "Resolvidos"]] },
        ].map(({ label, value, onChange, options }) => (
          <div key={label} className="relative">
            <select value={value} onChange={e => onChange(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm appearance-none pr-8 focus:outline-none focus:ring-2 focus:ring-brand-500">
              {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <ChevronDown size={13} className="absolute right-2.5 top-2.5 text-gray-400 pointer-events-none" />
          </div>
        ))}
        <span className="ml-auto text-sm text-gray-500">{findings.length} finding{findings.length !== 1 ? "s" : ""}</span>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12"><Loader2 size={24} className="animate-spin text-gray-400" /></div>
      ) : findings.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <CheckCircle size={32} className="mx-auto mb-2 text-green-300" />
          <p className="text-sm">Nenhum finding encontrado com os filtros selecionados.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 uppercase border-b">
                <th className="pb-2 font-medium">Severidade</th>
                <th className="pb-2 font-medium">Check</th>
                <th className="pb-2 font-medium">Recurso</th>
                <th className="pb-2 font-medium">Tipo</th>
                <th className="pb-2 font-medium">Status</th>
                <th className="pb-2 font-medium">Detectado em</th>
                <th className="pb-2 font-medium">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {findings.map((f: CloudFinding) => (
                <tr key={f.id} className="hover:bg-gray-50">
                  <td className="py-3 pr-4">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${SEVERITY_COLORS[f.severity] ?? "bg-gray-100 text-gray-600"}`}>
                      {f.severity}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-gray-900 max-w-xs">
                    <span className="font-medium">{f.check_title}</span>
                  </td>
                  <td className="py-3 pr-4 text-gray-600 font-mono text-xs truncate max-w-[180px]">
                    {f.resource_name ?? f.resource_id}
                  </td>
                  <td className="py-3 pr-4 text-gray-500 text-xs">{f.resource_type}</td>
                  <td className="py-3 pr-4">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[f.status] ?? "bg-gray-100 text-gray-600"}`}>
                      {f.status}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-gray-500 whitespace-nowrap text-xs">
                    {new Date(f.detected_at).toLocaleDateString("pt-BR")}
                  </td>
                  <td className="py-3">
                    {f.status === "open" && (
                      <button
                        onClick={() => {
                          const reason = prompt("Motivo para aceitar o risco:");
                          if (reason) acceptMut.mutate({ id: f.id, reason });
                        }}
                        className="text-xs text-yellow-700 hover:underline"
                      >
                        Aceitar risco
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export function CloudPosture() {
  const [tab, setTab] = useState<Tab>("accounts");
  const [showModal, setShowModal] = useState(false);
  const [editAccount, setEditAccount] = useState<CloudAccount | undefined>();

  const { data: accounts = [], isLoading } = useQuery({
    queryKey: ["cloud-accounts"],
    queryFn: cspmApi.listAccounts,
  });

  const tabClass = (t: Tab) =>
    `px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
      tab === t ? "bg-brand-600 text-white" : "text-gray-600 hover:bg-gray-100"
    }`;

  return (
    <div className="ml-64 p-8 min-h-screen bg-gray-50">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Cloud size={24} className="text-brand-600" />
            Cloud Security Posture
          </h1>
          <p className="text-gray-500 text-sm mt-1">
            Gerencie a segurança de AWS Security Groups, Azure NSGs e GCP Firewall Rules em uma visão unificada.
          </p>
        </div>
        {tab === "accounts" && (
          <button
            onClick={() => { setEditAccount(undefined); setShowModal(true); }}
            className="flex items-center gap-2 bg-brand-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-brand-700 transition-colors"
          >
            <Plus size={16} />
            Nova Conta Cloud
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        <button className={tabClass("accounts")} onClick={() => setTab("accounts")}>
          <span className="flex items-center gap-1.5"><Cloud size={14} /> Contas ({accounts.length})</span>
        </button>
        <button className={tabClass("findings")} onClick={() => setTab("findings")}>
          <span className="flex items-center gap-1.5"><AlertTriangle size={14} /> Findings</span>
        </button>
      </div>

      {/* Content */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        {tab === "accounts" && (
          <>
            {isLoading ? (
              <div className="flex justify-center py-12"><Loader2 size={24} className="animate-spin text-gray-400" /></div>
            ) : accounts.length === 0 ? (
              <div className="text-center py-16 text-gray-500">
                <Cloud size={40} className="mx-auto mb-3 text-gray-300" />
                <p className="font-medium mb-1">Nenhuma conta cloud configurada</p>
                <p className="text-sm text-gray-400 mb-4">Adicione uma conta AWS, Azure ou GCP para analisar a postura de segurança.</p>
                <button onClick={() => setShowModal(true)}
                  className="inline-flex items-center gap-2 bg-brand-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-brand-700">
                  <Plus size={15} /> Adicionar Conta
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {accounts.map((a: CloudAccount) => (
                  <AccountCard key={a.id} account={a} onEdit={() => { setEditAccount(a); setShowModal(true); }} />
                ))}
              </div>
            )}
          </>
        )}
        {tab === "findings" && <FindingsTab />}
      </div>

      {showModal && (
        <AccountModal account={editAccount} onClose={() => { setShowModal(false); setEditAccount(undefined); }} />
      )}
    </div>
  );
}
