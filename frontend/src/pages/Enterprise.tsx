import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, RotateCcw, Copy, Check, KeyRound, Palette, Loader2 } from "lucide-react";
import { enterpriseApi } from "../api/enterprise";
import type { ApiKey, ApiKeyCreated, TenantBranding } from "../types/enterprise";

type Tab = "api-keys" | "white-label";

const ALL_PERMISSIONS = [
  "devices:read",
  "devices:write",
  "operations:read",
  "operations:write",
];

// ── Raw Key Modal ──────────────────────────────────────────────────────────────
function RawKeyModal({ rawKey, onClose }: { rawKey: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(rawKey).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 w-full max-w-lg">
        <h2 className="text-lg font-semibold text-white mb-1">Salve sua API Key</h2>
        <p className="text-sm text-yellow-400 mb-4">
          Esta chave não será exibida novamente. Copie e guarde em local seguro.
        </p>
        <div className="bg-gray-900 border border-gray-600 rounded-lg p-3 font-mono text-sm text-green-400 break-all mb-4">
          {rawKey}
        </div>
        <div className="flex justify-end gap-3">
          <button
            onClick={copy}
            className="flex items-center gap-2 bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
            {copied ? "Copiado!" : "Copiar"}
          </button>
          <button
            onClick={onClose}
            className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}

// ── New API Key Modal ──────────────────────────────────────────────────────────
function NewApiKeyModal({ onClose, onCreated }: { onClose: () => void; onCreated: (key: ApiKeyCreated) => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [permissions, setPermissions] = useState<string[]>([]);
  const [expiresAt, setExpiresAt] = useState("");

  const createMut = useMutation({
    mutationFn: enterpriseApi.createApiKey,
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["enterprise-api-keys"] });
      onCreated(data);
      onClose();
    },
  });

  const togglePerm = (p: string) =>
    setPermissions(ps => ps.includes(p) ? ps.filter(x => x !== p) : [...ps, p]);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 w-full max-w-lg">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-white">Nova API Key</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl leading-none">&times;</button>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Nome</label>
            <input
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="ex: Integração Zabbix"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Permissões</label>
            <div className="space-y-2">
              {ALL_PERMISSIONS.map(p => (
                <label key={p} className="flex items-center gap-3 p-2 border border-gray-700 rounded-lg cursor-pointer hover:bg-gray-700">
                  <input
                    type="checkbox"
                    checked={permissions.includes(p)}
                    onChange={() => togglePerm(p)}
                    className="accent-brand-600"
                  />
                  <span className="text-sm text-gray-300 font-mono">{p}</span>
                </label>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Expiração (opcional)</label>
            <input
              type="date"
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
              value={expiresAt}
              onChange={e => setExpiresAt(e.target.value)}
            />
          </div>
        </div>
        <div className="flex justify-end gap-3 mt-6">
          <button onClick={onClose} className="px-4 py-2 text-sm border border-gray-600 text-gray-300 rounded-lg hover:bg-gray-700">
            Cancelar
          </button>
          <button
            onClick={() => createMut.mutate({ name, permissions, expires_at: expiresAt || null })}
            disabled={createMut.isPending || !name || permissions.length === 0}
            className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 flex items-center gap-2"
          >
            {createMut.isPending && <Loader2 size={14} className="animate-spin" />}
            Criar
          </button>
        </div>
      </div>
    </div>
  );
}

// ── API Keys Tab ───────────────────────────────────────────────────────────────
function ApiKeysTab() {
  const qc = useQueryClient();
  const [showNew, setShowNew] = useState(false);
  const [revealedKey, setRevealedKey] = useState<ApiKeyCreated | null>(null);

  const { data: keys = [], isLoading } = useQuery({
    queryKey: ["enterprise-api-keys"],
    queryFn: enterpriseApi.listApiKeys,
  });

  const deleteMut = useMutation({
    mutationFn: enterpriseApi.deleteApiKey,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["enterprise-api-keys"] }),
  });

  const rotateMut = useMutation({
    mutationFn: enterpriseApi.rotateApiKey,
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["enterprise-api-keys"] });
      setRevealedKey(data);
    },
  });

  return (
    <div>
      <div className="flex justify-end mb-4">
        <button
          onClick={() => setShowNew(true)}
          className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
        >
          <Plus size={16} /> Nova API Key
        </button>
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="animate-spin text-brand-500" size={24} />
          </div>
        ) : keys.length === 0 ? (
          <div className="text-center py-16 text-gray-500">
            <KeyRound size={40} className="mx-auto mb-3 opacity-30" />
            <p>Nenhuma API key criada</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Nome</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Prefixo</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Permissões</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Último uso</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Expira</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Ações</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k: ApiKey) => (
                <tr key={k.id} className="border-b border-gray-700/50 hover:bg-gray-700/30">
                  <td className="py-2 px-3 text-white font-medium">{k.name}</td>
                  <td className="py-2 px-3">
                    <span className="font-mono text-xs bg-gray-700 px-2 py-0.5 rounded text-gray-300">
                      {k.key_prefix}...
                    </span>
                  </td>
                  <td className="py-2 px-3">
                    <div className="flex flex-wrap gap-1">
                      {k.permissions.map(p => (
                        <span key={p} className="px-2 py-0.5 rounded text-xs font-medium bg-blue-900/40 text-blue-300">
                          {p}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-2 px-3 text-gray-400 text-xs">
                    {k.last_used_at ? new Date(k.last_used_at).toLocaleString("pt-BR") : "—"}
                  </td>
                  <td className="py-2 px-3 text-gray-400 text-xs">
                    {k.expires_at ? new Date(k.expires_at).toLocaleDateString("pt-BR") : "Nunca"}
                  </td>
                  <td className="py-2 px-3">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => rotateMut.mutate(k.id)}
                        disabled={rotateMut.isPending}
                        title="Rotacionar"
                        className="p-1.5 text-gray-400 hover:text-blue-400 rounded transition-colors"
                      >
                        <RotateCcw size={14} />
                      </button>
                      <button
                        onClick={() => deleteMut.mutate(k.id)}
                        disabled={deleteMut.isPending}
                        title="Excluir"
                        className="text-red-400 hover:text-red-300 p-1.5 rounded transition-colors"
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

      {showNew && (
        <NewApiKeyModal
          onClose={() => setShowNew(false)}
          onCreated={(key) => setRevealedKey(key)}
        />
      )}
      {revealedKey && (
        <RawKeyModal rawKey={revealedKey.raw_key} onClose={() => setRevealedKey(null)} />
      )}
    </div>
  );
}

// ── White-label Tab ────────────────────────────────────────────────────────────
function WhiteLabelTab() {
  const qc = useQueryClient();
  const [form, setForm] = useState<Partial<TenantBranding>>({
    company_name: "",
    primary_color: "#3b82f6",
    logo_url: "",
    favicon_url: "",
  });

  const { data: branding, isLoading } = useQuery({
    queryKey: ["enterprise-branding"],
    queryFn: enterpriseApi.getBranding,
  });

  useEffect(() => {
    if (branding) {
      setForm({
        company_name: branding.company_name ?? "",
        primary_color: branding.primary_color ?? "#3b82f6",
        logo_url: branding.logo_url ?? "",
        favicon_url: branding.favicon_url ?? "",
      });
    }
  }, [branding]);

  const saveMut = useMutation({
    mutationFn: enterpriseApi.updateBranding,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["enterprise-branding"] }),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="animate-spin text-brand-500" size={24} />
      </div>
    );
  }

  return (
    <div className="max-w-xl">
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 space-y-5">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">Nome da Empresa</label>
          <input
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
            value={form.company_name ?? ""}
            onChange={e => setForm(f => ({ ...f, company_name: e.target.value }))}
            placeholder="ex: Acme Corp"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">Cor Principal</label>
          <div className="flex items-center gap-3">
            <input
              type="color"
              className="w-12 h-9 rounded-lg border border-gray-600 bg-gray-700 cursor-pointer p-0.5"
              value={form.primary_color ?? "#3b82f6"}
              onChange={e => setForm(f => ({ ...f, primary_color: e.target.value }))}
            />
            <span className="font-mono text-sm text-gray-400">{form.primary_color}</span>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">URL do Logo</label>
          <input
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
            value={form.logo_url ?? ""}
            onChange={e => setForm(f => ({ ...f, logo_url: e.target.value }))}
            placeholder="https://exemplo.com/logo.png"
          />
          {form.logo_url && (
            <div className="mt-3">
              <p className="text-xs text-gray-500 mb-1">Preview:</p>
              <img
                src={form.logo_url}
                alt="Logo preview"
                className="h-12 object-contain bg-gray-900 rounded-lg p-2 border border-gray-600"
                onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
              />
            </div>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">URL do Favicon</label>
          <input
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
            value={form.favicon_url ?? ""}
            onChange={e => setForm(f => ({ ...f, favicon_url: e.target.value }))}
            placeholder="https://exemplo.com/favicon.ico"
          />
        </div>

        <div className="flex justify-end pt-2">
          <button
            onClick={() => saveMut.mutate(form)}
            disabled={saveMut.isPending}
            className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 flex items-center gap-2"
          >
            {saveMut.isPending && <Loader2 size={14} className="animate-spin" />}
            Salvar
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────
export function Enterprise() {
  const [tab, setTab] = useState<Tab>("api-keys");

  return (
    <div className="ml-64 min-h-screen bg-gray-900">
      <div className="p-6 max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white">Enterprise</h1>
          <p className="text-sm text-gray-400 mt-1">Gerencie API keys e personalização white-label</p>
        </div>

        <div className="flex gap-1 mb-6 border-b border-gray-700">
          {([
            ["api-keys", "API Keys", KeyRound],
            ["white-label", "White-label", Palette],
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

        {tab === "api-keys" && <ApiKeysTab />}
        {tab === "white-label" && <WhiteLabelTab />}
      </div>
    </div>
  );
}
