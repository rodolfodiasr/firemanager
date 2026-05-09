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
} from "lucide-react";
import { platformConfigApi } from "../api/platform_config";
import type { PlatformConfigKey } from "../types/platform_config";

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
    </div>
  );
}
