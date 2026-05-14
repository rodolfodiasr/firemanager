import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  KeyRound,
  Check,
  X,
  Loader2,
  ShieldCheck,
  AlertTriangle,
  Trash2,
  Eye,
  EyeOff,
  Zap,
  Plus,
  Play,
  Globe,
  ToggleLeft,
  ToggleRight,
} from "lucide-react";
import { platformConfigApi } from "../api/platform_config";
import type { PlatformConfigKey } from "../types/platform_config";
import { adminLlmConfigsApi, llmProvidersApi, type LLMConfig, type LLMConfigCreate, type LLMProviderMeta } from "../api/llm_configs";

const GROUP_LABELS: Record<string, string> = {
  anthropic_api_key: "Anthropic (IA)",
  anthropic_model: "Anthropic (IA)",
  anthropic_max_tokens: "Anthropic (IA)",
  openai_api_key: "OpenAI (Embeddings)",
  openai_embedding_model: "OpenAI (Embeddings)",
  smtp_host: "Email SMTP",
  smtp_port: "Email SMTP",
  smtp_user: "Email SMTP",
  smtp_password: "Email SMTP",
  email_from: "Email SMTP",
};

function groupKeys(keys: PlatformConfigKey[]): Record<string, PlatformConfigKey[]> {
  const groups: Record<string, PlatformConfigKey[]> = {};
  for (const k of keys) {
    const g = GROUP_LABELS[k.key] ?? "Outros";
    if (!groups[g]) groups[g] = [];
    groups[g].push(k);
  }
  return groups;
}

// ── Key row ────────────────────────────────────────────────────────────────────
function KeyRow({ item }: { item: PlatformConfigKey }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const [showValue, setShowValue] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [testing, setTesting] = useState(false);

  const setMut = useMutation({
    mutationFn: () => platformConfigApi.set(item.key, { value }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["platform-config"] });
      setEditing(false);
      setValue("");
      setTestResult(null);
    },
  });

  const clearMut = useMutation({
    mutationFn: () => platformConfigApi.clear(item.key),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["platform-config"] });
      setTestResult(null);
    },
  });

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await platformConfigApi.test(item.key);
      setTestResult(res);
    } catch {
      setTestResult({ ok: false, message: "Erro ao testar conexão" });
    } finally {
      setTesting(false);
    }
  };

  const statusColor = item.is_set
    ? "text-green-400"
    : item.has_env_fallback
    ? "text-yellow-400"
    : "text-gray-500";

  const statusLabel = item.is_set
    ? "No banco"
    : item.has_env_fallback
    ? "Via .env"
    : "Não configurado";

  return (
    <div className="border border-gray-700 rounded-lg p-4 space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="font-mono text-sm text-gray-200">{item.key}</p>
          {item.description && (
            <p className="text-xs text-gray-400 mt-0.5">{item.description}</p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`text-xs font-medium ${statusColor}`}>{statusLabel}</span>
          {item.is_set && (
            <>
              <button
                onClick={handleTest}
                disabled={testing}
                title="Testar conexão"
                className="text-gray-400 hover:text-brand-400 transition-colors disabled:opacity-40"
              >
                {testing ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
              </button>
              <button
                onClick={() => clearMut.mutate()}
                disabled={clearMut.isPending}
                title="Remover do banco (volta a usar .env)"
                className="text-gray-400 hover:text-red-400 transition-colors disabled:opacity-40"
              >
                <Trash2 size={14} />
              </button>
            </>
          )}
          <button
            onClick={() => {
              setEditing((e) => !e);
              setValue("");
              setTestResult(null);
            }}
            className="text-xs bg-gray-700 hover:bg-gray-600 text-gray-200 px-2 py-1 rounded transition-colors"
          >
            {editing ? "Cancelar" : item.is_set ? "Alterar" : "Configurar"}
          </button>
        </div>
      </div>

      {testResult && (
        <div
          className={`flex items-start gap-2 text-xs rounded-lg px-3 py-2 ${
            testResult.ok ? "bg-green-900/40 text-green-300" : "bg-red-900/40 text-red-300"
          }`}
        >
          {testResult.ok ? <ShieldCheck size={13} className="mt-0.5 shrink-0" /> : <AlertTriangle size={13} className="mt-0.5 shrink-0" />}
          <span>{testResult.message}</span>
        </div>
      )}

      {editing && (
        <div className="space-y-2">
          <div className="relative">
            <input
              type={showValue || !item.is_sensitive ? "text" : "password"}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder={`Novo valor para ${item.key}…`}
              className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 pr-9 text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-brand-500"
              autoFocus
            />
            {item.is_sensitive && (
              <button
                type="button"
                onClick={() => setShowValue((v) => !v)}
                className="absolute right-2.5 top-2.5 text-gray-500 hover:text-gray-300"
              >
                {showValue ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setMut.mutate()}
              disabled={!value.trim() || setMut.isPending}
              className="flex items-center gap-1.5 bg-brand-600 hover:bg-brand-700 text-white text-xs font-medium px-3 py-1.5 rounded-lg disabled:opacity-40 transition-colors"
            >
              {setMut.isPending ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
              Salvar
            </button>
          </div>
          {setMut.isError && (
            <p className="text-xs text-red-400">Erro ao salvar. Tente novamente.</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────
export function PlatformConfig() {
  const { data: keys = [], isLoading } = useQuery({
    queryKey: ["platform-config"],
    queryFn: platformConfigApi.list,
  });

  const groups = groupKeys(keys);

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-8">
      <div className="flex items-center gap-3">
        <KeyRound size={24} className="text-brand-400" />
        <div>
          <h1 className="text-2xl font-bold text-white">Configurações de Plataforma</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            Chaves de API e credenciais armazenadas criptografadas no banco de dados.
          </p>
        </div>
      </div>

      <div className="bg-yellow-900/30 border border-yellow-700/50 rounded-lg px-4 py-3 text-sm text-yellow-300 flex gap-3">
        <AlertTriangle size={16} className="shrink-0 mt-0.5" />
        <div>
          <p className="font-medium">Valores no banco têm prioridade sobre o <code>.env</code></p>
          <p className="text-yellow-400/70 text-xs mt-0.5">
            Se uma chave estiver configurada aqui, o valor do <code>.env</code> é ignorado para essa chave.
            "Via .env" significa que o valor está no arquivo de variáveis de ambiente mas não no banco.
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="animate-spin text-brand-400" size={32} />
        </div>
      ) : (
        Object.entries(groups).map(([group, items]) => (
          <section key={group}>
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
              {group}
              <div className="flex-1 h-px bg-gray-700" />
            </h2>
            <div className="space-y-3">
              {items.map((item) => (
                <KeyRow key={item.key} item={item} />
              ))}
            </div>
          </section>
        ))
      )}

      <GlobalLLMSection />
    </div>
  );
}

// ── Global LLM Section ────────────────────────────────────────────────────────

const PROVIDER_COLORS: Record<string, string> = {
  anthropic: "bg-[#cc785c]", openai: "bg-[#10a37f]", google: "bg-[#4285f4]",
  deepseek: "bg-[#1a6efd]", moonshot: "bg-[#7c3aed]", xai: "bg-gray-900",
  perplexity: "bg-[#20b2aa]", nvidia: "bg-[#76b900]", zhipu: "bg-[#2563eb]",
  minimax: "bg-[#e11d48]", ollama: "bg-[#374151]",
};
const PROVIDER_INITIALS: Record<string, string> = {
  anthropic: "Cl", openai: "GP", google: "Gm", deepseek: "DS",
  moonshot: "Ki", xai: "Gr", perplexity: "Px", nvidia: "Nv",
  zhipu: "GL", minimax: "Mx", ollama: "Ol",
};

function GlobalLLMSection() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [testResults, setTestResults] = useState<Record<string, { ok: boolean; message: string; latency_ms: number }>>({});
  const [testing, setTesting] = useState<string | null>(null);

  const { data: configs = [], isLoading } = useQuery({
    queryKey: ["llm-configs-global"],
    queryFn: adminLlmConfigsApi.list,
  });
  const { data: providersMeta = [] } = useQuery({
    queryKey: ["llm-providers-meta"],
    queryFn: llmProvidersApi.listMeta,
  });

  const createMut = useMutation({
    mutationFn: (data: LLMConfigCreate) => adminLlmConfigsApi.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["llm-configs-global"] }); setShowForm(false); },
  });
  const deleteMut = useMutation({
    mutationFn: (id: string) => adminLlmConfigsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["llm-configs-global"] }),
  });
  const toggleMut = useMutation({
    mutationFn: ({ id, is_enabled }: { id: string; is_enabled: boolean }) =>
      adminLlmConfigsApi.update(id, { is_enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["llm-configs-global"] }),
  });
  const setDefaultMut = useMutation({
    mutationFn: (id: string) => adminLlmConfigsApi.update(id, { is_default: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["llm-configs-global"] }),
  });

  const handleTest = async (id: string) => {
    setTesting(id);
    try {
      const r = await adminLlmConfigsApi.test(id);
      setTestResults((p) => ({ ...p, [id]: r }));
    } catch {
      setTestResults((p) => ({ ...p, [id]: { ok: false, message: "Erro ao testar", latency_ms: 0 } }));
    } finally {
      setTesting(null);
    }
  };

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-2">
          <Globe size={13} /> Provedores de LLM — Global
          <div className="flex-1 h-px bg-gray-700 ml-2 w-20" />
        </h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1.5 text-xs bg-brand-600 hover:bg-brand-700 text-white px-3 py-1.5 rounded-lg"
        >
          <Plus size={12} /> Adicionar
        </button>
      </div>

      <p className="text-xs text-gray-500 mb-4">
        Providers configurados aqui ficam disponíveis como fallback para todos os tenants.
        Tenants podem sobrescrever com configurações próprias em Organização → Integrações.
      </p>

      {showForm && (
        <GlobalLLMForm
          providersMeta={providersMeta}
          onSubmit={(d) => createMut.mutate(d)}
          onCancel={() => setShowForm(false)}
          loading={createMut.isPending}
        />
      )}

      {isLoading && <p className="text-xs text-gray-400">Carregando...</p>}

      <div className="space-y-3">
        {configs.map((cfg) => (
          <div key={cfg.id} className={`border rounded-lg p-4 ${cfg.is_default ? "border-brand-500" : "border-gray-700"} ${!cfg.is_enabled ? "opacity-60" : ""}`}>
            <div className="flex items-center gap-3">
              <span className={`w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold text-white shrink-0 ${PROVIDER_COLORS[cfg.provider] ?? "bg-gray-600"}`}>
                {PROVIDER_INITIALS[cfg.provider] ?? cfg.provider.slice(0, 2).toUpperCase()}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-gray-200">{cfg.display_name}</p>
                  {cfg.is_default && <span className="text-xs bg-brand-900 text-brand-300 px-1.5 py-0.5 rounded">padrão</span>}
                  {cfg.no_train_flag && <span className="text-xs text-green-400" title="Não usar para treinamento">🔒</span>}
                  {!cfg.has_key && cfg.provider !== "ollama" && <span className="text-xs bg-amber-900/50 text-amber-300 px-1.5 py-0.5 rounded">sem key</span>}
                </div>
                <p className="text-xs text-gray-500 font-mono">{cfg.model_name}</p>
                {cfg.api_base_url && <p className="text-xs text-gray-600 font-mono truncate">{cfg.api_base_url}</p>}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button onClick={() => handleTest(cfg.id)} disabled={testing === cfg.id} title="Testar conexão"
                  className="text-gray-500 hover:text-brand-400 disabled:opacity-40">
                  {testing === cfg.id ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
                </button>
                <button onClick={() => toggleMut.mutate({ id: cfg.id, is_enabled: !cfg.is_enabled })} className="text-gray-500 hover:text-gray-300">
                  {cfg.is_enabled ? <ToggleRight size={16} className="text-green-400" /> : <ToggleLeft size={16} />}
                </button>
                {!cfg.is_default && (
                  <button onClick={() => setDefaultMut.mutate(cfg.id)} className="text-xs text-gray-500 hover:text-brand-400">padrão</button>
                )}
                <button onClick={() => { if (window.confirm("Remover?")) deleteMut.mutate(cfg.id); }}
                  className="text-gray-600 hover:text-red-400"><Trash2 size={14} /></button>
              </div>
            </div>
            {testResults[cfg.id] && (
              <div className={`mt-2 text-xs px-3 py-1.5 rounded flex items-center gap-2 ${testResults[cfg.id].ok ? "bg-green-900/30 text-green-300" : "bg-red-900/30 text-red-300"}`}>
                {testResults[cfg.id].ok ? <Check size={11} /> : <X size={11} />}
                {testResults[cfg.id].message}
                {testResults[cfg.id].ok && <span className="ml-auto text-gray-500">{testResults[cfg.id].latency_ms}ms</span>}
              </div>
            )}
          </div>
        ))}
        {!isLoading && configs.length === 0 && (
          <p className="text-xs text-gray-500 text-center py-4">Nenhum provider global configurado.</p>
        )}
      </div>
    </section>
  );
}

function GlobalLLMForm({ providersMeta, onSubmit, onCancel, loading }: {
  providersMeta: LLMProviderMeta[];
  onSubmit: (d: LLMConfigCreate) => void;
  onCancel: () => void;
  loading: boolean;
}) {
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [isDefault, setIsDefault] = useState(false);
  const [noTrain, setNoTrain] = useState(true);
  const meta = providersMeta.find((m) => m.provider === provider);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({ provider, model_name: model || meta?.default_model || "", api_key: apiKey || null, api_base_url: baseUrl || null, is_default: isDefault, no_train_flag: noTrain });
  };

  return (
    <form onSubmit={handleSubmit} className="border border-gray-700 rounded-lg p-4 mb-4 space-y-3 bg-gray-900/50">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Provider</label>
          <select value={provider} onChange={(e) => { setProvider(e.target.value); setModel(""); setBaseUrl(""); }}
            className="w-full text-sm bg-gray-800 border border-gray-600 rounded px-2 py-1.5 text-gray-200">
            {providersMeta.map((m) => <option key={m.provider} value={m.provider}>{m.label}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Modelo</label>
          <input value={model} onChange={(e) => setModel(e.target.value)} placeholder={meta?.default_model ?? ""}
            className="w-full text-sm bg-gray-800 border border-gray-600 rounded px-2 py-1.5 text-gray-200" />
        </div>
      </div>
      {meta?.needs_key && (
        <div>
          <label className="text-xs text-gray-400 mb-1 block">API Key</label>
          <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="sk-..."
            className="w-full text-sm bg-gray-800 border border-gray-600 rounded px-2 py-1.5 text-gray-200 font-mono" />
        </div>
      )}
      {(provider === "ollama" || !meta?.base_url) && (
        <div>
          <label className="text-xs text-gray-400 mb-1 block">URL Base</label>
          <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder={meta?.base_url ?? "https://..."}
            className="w-full text-sm bg-gray-800 border border-gray-600 rounded px-2 py-1.5 text-gray-200 font-mono" />
        </div>
      )}
      <div className="flex items-center gap-4 text-xs text-gray-400">
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} />
          Padrão global
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={noTrain} onChange={(e) => setNoTrain(e.target.checked)} />
          🔒 Não treinar
        </label>
      </div>
      <div className="flex gap-2 justify-end">
        <button type="button" onClick={onCancel} className="text-sm text-gray-500 hover:text-gray-300 px-3 py-1.5">Cancelar</button>
        <button type="submit" disabled={loading}
          className="text-sm bg-brand-600 hover:bg-brand-700 text-white px-4 py-1.5 rounded-lg disabled:opacity-50">
          {loading ? "Salvando..." : "Salvar"}
        </button>
      </div>
    </form>
  );
}
