import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  KeyRound, Plus, Trash2, RefreshCw, Eye, EyeOff, Clock,
  ShieldCheck, AlertTriangle, Loader2, X, History, RotateCcw,
} from "lucide-react";
import toast from "react-hot-toast";
import { vaultApi, type VaultSecret, type VaultSecretCreate, type SecretType } from "../api/vault";
import { PageWrapper } from "../components/layout/PageWrapper";

const SECRET_TYPE_LABELS: Record<SecretType, string> = {
  api_key:     "API Key",
  password:    "Senha",
  token:       "Token",
  oauth2:      "OAuth2",
  certificate: "Certificado",
};

const SECRET_TYPE_COLORS: Record<SecretType, string> = {
  api_key:     "bg-blue-100 text-blue-700",
  password:    "bg-red-100 text-red-700",
  token:       "bg-green-100 text-green-700",
  oauth2:      "bg-purple-100 text-purple-700",
  certificate: "bg-amber-100 text-amber-700",
};

function maskValue(value: string): string {
  if (value.length <= 8) return "••••••••";
  return value.slice(0, 4) + "••••••••" + value.slice(-4);
}

// ── Create / Rotate Modal ──────────────────────────────────────────────────────

function SecretModal({
  mode,
  secret,
  onClose,
}: {
  mode: "create" | "rotate";
  secret?: VaultSecret;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState(secret?.name ?? "");
  const [type, setType] = useState<SecretType>(secret?.type ?? "api_key");
  const [value, setValue] = useState("");
  const [description, setDescription] = useState(secret?.description ?? "");
  const [expiresAt, setExpiresAt] = useState(secret?.expires_at?.slice(0, 10) ?? "");
  const [showValue, setShowValue] = useState(false);

  const createMut = useMutation({
    mutationFn: (data: VaultSecretCreate) => vaultApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["vault-secrets"] });
      toast.success("Segredo criado com sucesso");
      onClose();
    },
    onError: () => toast.error("Erro ao criar segredo"),
  });

  const rotateMut = useMutation({
    mutationFn: (v: string) => vaultApi.rotate(secret!.id, v),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["vault-secrets"] });
      toast.success("Segredo rotacionado com sucesso");
      onClose();
    },
    onError: () => toast.error("Erro ao rotacionar segredo"),
  });

  const isPending = createMut.isPending || rotateMut.isPending;

  function handleSubmit() {
    if (!value.trim()) { toast.error("Informe o valor do segredo"); return; }
    if (mode === "create") {
      createMut.mutate({ name, type, value, description: description || undefined, expires_at: expiresAt || undefined });
    } else {
      rotateMut.mutate(value);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-base font-semibold flex items-center gap-2">
            {mode === "create" ? <><Plus size={16} className="text-brand-600" /> Novo Segredo</> : <><RotateCcw size={16} className="text-amber-600" /> Rotacionar — {secret?.name}</>}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>
        <div className="p-6 space-y-4">
          {mode === "create" && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Nome</label>
                  <input
                    value={name} onChange={(e) => setName(e.target.value)}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    placeholder="ex: RMM API Key Prod"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Tipo</label>
                  <select
                    value={type} onChange={(e) => setType(e.target.value as SecretType)}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  >
                    {Object.entries(SECRET_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Descrição (opcional)</label>
                <input
                  value={description} onChange={(e) => setDescription(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  placeholder="Usado pela integração RMM NinjaOne"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Expira em (opcional)</label>
                <input
                  type="date" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
            </>
          )}

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              {mode === "create" ? "Valor do segredo" : "Novo valor"}
            </label>
            <div className="relative">
              <input
                type={showValue ? "text" : "password"}
                value={value} onChange={(e) => setValue(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 pr-10 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder={mode === "rotate" ? "Informe o novo valor seguro…" : "Cole o valor aqui…"}
                autoComplete="new-password"
              />
              <button
                type="button"
                onClick={() => setShowValue((v) => !v)}
                className="absolute right-2 top-2 text-gray-400 hover:text-gray-600"
              >
                {showValue ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            <p className="text-[11px] text-gray-400 mt-1">O valor é criptografado antes de ser armazenado.</p>
          </div>
        </div>

        <div className="px-6 py-4 border-t flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50">Cancelar</button>
          <button
            onClick={handleSubmit}
            disabled={isPending || !value.trim() || (mode === "create" && !name.trim())}
            className="px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2"
          >
            {isPending && <Loader2 size={14} className="animate-spin" />}
            {mode === "create" ? "Criar" : "Rotacionar"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Secret Row ─────────────────────────────────────────────────────────────────

function SecretRow({ secret, onRotate }: { secret: VaultSecret; onRotate: () => void }) {
  const qc = useQueryClient();
  const isExpired = secret.expires_at ? new Date(secret.expires_at) < new Date() : false;
  const isExpiringSoon = !isExpired && secret.expires_at
    ? (new Date(secret.expires_at).getTime() - Date.now()) < 7 * 24 * 3600 * 1000
    : false;

  const deleteMut = useMutation({
    mutationFn: () => vaultApi.delete(secret.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["vault-secrets"] }); toast.success("Segredo removido"); },
    onError: () => toast.error("Erro ao remover segredo"),
  });

  return (
    <div className={`bg-white border rounded-xl p-4 ${isExpired ? "border-red-300" : isExpiringSoon ? "border-amber-300" : "border-gray-200"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <KeyRound size={16} className={`shrink-0 mt-0.5 ${isExpired ? "text-red-500" : "text-gray-400"}`} />
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium text-sm text-gray-900">{secret.name}</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${SECRET_TYPE_COLORS[secret.type]}`}>
                {SECRET_TYPE_LABELS[secret.type]}
              </span>
              {isExpired && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-red-100 text-red-700 flex items-center gap-1">
                  <AlertTriangle size={9} /> Expirado
                </span>
              )}
              {isExpiringSoon && !isExpired && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-amber-100 text-amber-700 flex items-center gap-1">
                  <Clock size={9} /> Expira em breve
                </span>
              )}
            </div>
            {secret.description && (
              <p className="text-xs text-gray-500 mt-0.5">{secret.description}</p>
            )}
            <div className="flex items-center gap-4 mt-2 text-[11px] text-gray-400">
              <span className="font-mono">{maskValue("placeholder_masked_value")}</span>
              {secret.last_rotated && (
                <span className="flex items-center gap-1">
                  <RefreshCw size={9} /> Rotacionado {new Date(secret.last_rotated).toLocaleDateString("pt-BR")}
                </span>
              )}
              {secret.expires_at && (
                <span className="flex items-center gap-1">
                  <Clock size={9} /> Expira {new Date(secret.expires_at).toLocaleDateString("pt-BR")}
                </span>
              )}
            </div>
            {secret.references.length > 0 && (
              <div className="flex gap-1 mt-2 flex-wrap">
                {secret.references.map((ref) => (
                  <span key={ref} className="text-[10px] bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                    {ref}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={onRotate}
            title="Rotacionar segredo"
            className="p-1.5 text-gray-400 hover:text-amber-600 hover:bg-amber-50 rounded-lg transition-colors"
          >
            <RotateCcw size={14} />
          </button>
          <button
            onClick={() => { if (confirm(`Remover segredo "${secret.name}"?`)) deleteMut.mutate(); }}
            title="Remover"
            disabled={deleteMut.isPending}
            className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          >
            {deleteMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────

type Tab = "secrets" | "audit";

export function VaultPage() {
  const [tab, setTab] = useState<Tab>("secrets");
  const [showCreate, setShowCreate] = useState(false);
  const [rotateSecret, setRotateSecret] = useState<VaultSecret | null>(null);

  const { data: secrets = [], isLoading } = useQuery({
    queryKey: ["vault-secrets"],
    queryFn: vaultApi.list,
  });

  const { data: auditLog = [], isLoading: loadingAudit } = useQuery({
    queryKey: ["vault-audit"],
    queryFn: vaultApi.listAudit,
    enabled: tab === "audit",
  });

  const expiredCount = secrets.filter((s) =>
    s.expires_at && new Date(s.expires_at) < new Date()
  ).length;

  return (
    <PageWrapper
      title="Vault de Segredos"
      subtitle="Gerencie credenciais e tokens de forma segura e criptografada"
    >
      <div className="max-w-3xl mx-auto space-y-5">
        {/* Stats strip */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white border border-gray-200 rounded-xl p-4">
            <p className="text-xs text-gray-500">Total de segredos</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">{secrets.length}</p>
          </div>
          <div className={`border rounded-xl p-4 ${expiredCount > 0 ? "bg-red-50 border-red-200" : "bg-white border-gray-200"}`}>
            <p className="text-xs text-gray-500">Expirados</p>
            <p className={`text-2xl font-bold mt-1 ${expiredCount > 0 ? "text-red-600" : "text-gray-900"}`}>{expiredCount}</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-xl p-4">
            <p className="text-xs text-gray-500">Em uso por integrações</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">
              {secrets.filter((s) => s.references.length > 0).length}
            </p>
          </div>
        </div>

        {/* Security notice */}
        <div className="flex items-start gap-2 bg-brand-50 border border-brand-200 rounded-xl px-4 py-3">
          <ShieldCheck size={14} className="text-brand-600 shrink-0 mt-0.5" />
          <p className="text-xs text-brand-700">
            Todos os valores são criptografados em repouso (AES-256). Nenhum valor em texto simples é armazenado.
            Acesso a este módulo é restrito a administradores e registrado em auditoria.
          </p>
        </div>

        {/* Tabs + action */}
        <div className="flex items-center justify-between border-b border-gray-200">
          <div className="flex gap-0">
            {([
              ["secrets", "Segredos", KeyRound],
              ["audit",   "Auditoria", History],
            ] as const).map(([key, label, Icon]) => (
              <button
                key={key}
                onClick={() => setTab(key as Tab)}
                className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                  tab === key
                    ? "border-brand-600 text-brand-600"
                    : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                <Icon size={14} />{label}
              </button>
            ))}
          </div>
          {tab === "secrets" && (
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700"
            >
              <Plus size={15} /> Novo Segredo
            </button>
          )}
        </div>

        {/* Content */}
        {tab === "secrets" && (
          <>
            {isLoading ? (
              <div className="flex justify-center py-16"><Loader2 size={22} className="animate-spin text-brand-600" /></div>
            ) : secrets.length === 0 ? (
              <div className="text-center py-16 text-gray-400">
                <KeyRound size={36} className="mx-auto mb-3 opacity-30" />
                <p className="font-medium mb-1">Nenhum segredo cadastrado</p>
                <p className="text-xs">Adicione credenciais de integrações de forma segura.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {secrets.map((s) => (
                  <SecretRow key={s.id} secret={s} onRotate={() => setRotateSecret(s)} />
                ))}
              </div>
            )}
          </>
        )}

        {tab === "audit" && (
          <>
            {loadingAudit ? (
              <div className="flex justify-center py-16"><Loader2 size={22} className="animate-spin text-brand-600" /></div>
            ) : auditLog.length === 0 ? (
              <div className="text-center py-16 text-gray-400">
                <History size={36} className="mx-auto mb-3 opacity-30" />
                <p>Nenhum registro de auditoria ainda.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {auditLog.map((entry) => (
                  <div key={entry.id} className="bg-white border border-gray-200 rounded-xl p-3 flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full shrink-0 ${
                      entry.action === "deleted"  ? "bg-red-500" :
                      entry.action === "rotated"  ? "bg-amber-500" :
                      entry.action === "created"  ? "bg-green-500" :
                                                    "bg-gray-400"
                    }`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-800">
                        <span className="font-medium">{entry.actor_name}</span>
                        {" "}{entry.action === "created" ? "criou" : entry.action === "rotated" ? "rotacionou" : entry.action === "deleted" ? "removeu" : "acessou"}{" "}
                        <span className="font-medium">{entry.secret_name}</span>
                      </p>
                      <p className="text-xs text-gray-400">{entry.actor_email}</p>
                    </div>
                    <span className="text-xs text-gray-400 shrink-0">
                      {new Date(entry.created_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {showCreate && <SecretModal mode="create" onClose={() => setShowCreate(false)} />}
      {rotateSecret && <SecretModal mode="rotate" secret={rotateSecret} onClose={() => setRotateSecret(null)} />}
    </PageWrapper>
  );
}
