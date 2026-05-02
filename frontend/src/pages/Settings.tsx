import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  KeyRound, User, Globe, Building2,
  CheckCircle2, XCircle, Loader2, Trash2, ChevronDown, ChevronUp,
} from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { useAuth } from "../hooks/useAuth";
import apiClient from "../api/client";
import { integrationsApi } from "../api/integrations";
import type { Integration, IntegrationType } from "../types/integration";

// ── Senha ─────────────────────────────────────────────────────────────────────

interface PasswordForm {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

function PasswordSection() {
  const [success, setSuccess] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const { register, handleSubmit, watch, reset, formState: { errors, isSubmitting } } = useForm<PasswordForm>();

  const onSubmit = async (data: PasswordForm) => {
    setApiError(null);
    setSuccess(false);
    try {
      await apiClient.post("/auth/me/password", {
        current_password: data.current_password,
        new_password: data.new_password,
      });
      setSuccess(true);
      reset();
    } catch (err: unknown) {
      const raw = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setApiError(raw ?? "Erro ao alterar senha");
    }
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-center gap-2 mb-1">
        <KeyRound size={16} className="text-brand-500" />
        <h2 className="font-semibold text-gray-900">Alterar senha</h2>
      </div>
      <p className="text-sm text-gray-500 mb-5">Mínimo de 8 caracteres.</p>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {(["current_password", "new_password", "confirm_password"] as const).map((field) => {
          const labels = { current_password: "Senha atual", new_password: "Nova senha", confirm_password: "Confirmar nova senha" };
          return (
            <div key={field}>
              <label className="block text-sm font-medium text-gray-700 mb-1">{labels[field]}</label>
              <input
                type="password"
                {...register(field, {
                  required: "Obrigatório",
                  ...(field === "new_password" ? { minLength: { value: 8, message: "Mínimo 8 caracteres" } } : {}),
                  ...(field === "confirm_password" ? { validate: (v) => v === watch("new_password") || "Senhas não coincidem" } : {}),
                })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              {errors[field] && <p className="text-xs text-red-600 mt-1">{errors[field]?.message}</p>}
            </div>
          );
        })}
        {apiError && <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{apiError}</p>}
        {success && <p className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">Senha alterada com sucesso!</p>}
        <button type="submit" disabled={isSubmitting} className="px-5 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50 transition-colors">
          {isSubmitting ? "Salvando..." : "Alterar senha"}
        </button>
      </form>
    </div>
  );
}

// ── Integrações ───────────────────────────────────────────────────────────────

const INTEGRATION_META: Record<IntegrationType, {
  label: string;
  description: string;
  color: string;
  fields: { key: string; label: string; type?: string; placeholder?: string; defaultValue?: string; options?: { value: string; label: string }[] }[];
}> = {
  shodan: {
    label: "Shodan",
    description: "Varredura de ativos expostos na internet e CVEs por IP.",
    color: "bg-red-100 text-red-700",
    fields: [
      { key: "api_key", label: "API Key", type: "password", placeholder: "Sua API key do Shodan" },
    ],
  },
  wazuh: {
    label: "Wazuh",
    description: "SIEM open-source — correlação de eventos e alertas de segurança.",
    color: "bg-blue-100 text-blue-700",
    fields: [
      { key: "url", label: "URL", placeholder: "https://wazuh.empresa.com:55000" },
      { key: "username", label: "Usuário", placeholder: "wazuh-api" },
      { key: "password", label: "Senha", type: "password", placeholder: "••••••••" },
      {
        key: "version", label: "Versão", type: "select", defaultValue: "4",
        options: [{ value: "4", label: "Wazuh 4.x" }, { value: "5", label: "Wazuh 5.x" }],
      },
      { key: "verify_ssl", label: "Verificar SSL", type: "checkbox" },
    ],
  },
  openvas: {
    label: "OpenVAS / GVM",
    description: "Scanner de vulnerabilidades open-source (Greenbone).",
    color: "bg-green-100 text-green-700",
    fields: [
      { key: "host", label: "Host", placeholder: "192.168.1.100" },
      { key: "port", label: "Porta GMP", placeholder: "9390", defaultValue: "9390" },
      { key: "username", label: "Usuário", placeholder: "admin" },
      { key: "password", label: "Senha", type: "password", placeholder: "••••••••" },
    ],
  },
  nmap: {
    label: "Nmap",
    description: "Scanner de portas e serviços para descoberta de rede.",
    color: "bg-purple-100 text-purple-700",
    fields: [
      { key: "binary_path", label: "Caminho do binário", placeholder: "/usr/bin/nmap", defaultValue: "/usr/bin/nmap" },
      { key: "default_args", label: "Args padrão", placeholder: "-sS -T4", defaultValue: "-sS -T4" },
    ],
  },
  zabbix: {
    label: "Zabbix",
    description: "Monitoramento de infraestrutura — hosts, métricas, alertas e triggers.",
    color: "bg-orange-100 text-orange-700",
    fields: [
      { key: "url", label: "URL", placeholder: "https://zabbix.empresa.com" },
      { key: "token", label: "API Token", type: "password", placeholder: "Token gerado no Zabbix" },
      {
        key: "version", label: "Versão", type: "select", defaultValue: "7",
        options: [{ value: "6", label: "Zabbix 6.x" }, { value: "7", label: "Zabbix 7.x (7.2.5+)" }],
      },
      { key: "verify_ssl", label: "Verificar SSL", type: "checkbox" },
    ],
  },
  bookstack: {
    label: "BookStack",
    description: "Base de conhecimento — documentação de dispositivos, fluxos e políticas via RAG.",
    color: "bg-sky-100 text-sky-700",
    fields: [
      { key: "base_url", label: "URL do BookStack", placeholder: "https://bookstack.suaempresa.com" },
      { key: "token_id", label: "Token ID", placeholder: "ID do token de API" },
      { key: "token_secret", label: "Token Secret", type: "password", placeholder: "Secret do token de API" },
      { key: "book_id", label: "ID do Livro (book_id)", placeholder: "1" },
      { key: "chapter_id", label: "ID do Chapter (opcional)", placeholder: "Deixe vazio para indexar o livro inteiro" },
      { key: "snapshot_enabled", label: "Snapshot automático", type: "checkbox" },
      {
        key: "snapshot_hour", label: "Horário do snapshot (UTC)", type: "select", defaultValue: "2",
        options: Array.from({ length: 24 }, (_, i) => ({ value: String(i), label: `${String(i).padStart(2, "0")}:00 UTC` })),
      },
    ],
  },
};

interface IntegrationCardProps {
  type: IntegrationType;
  existing: Integration | undefined;
  tenantId: string | null;
  isSuperAdmin: boolean;
}

function IntegrationCard({ type, existing, tenantId, isSuperAdmin }: IntegrationCardProps) {
  const qc = useQueryClient();
  const meta = INTEGRATION_META[type];
  const [open, setOpen] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; latency_ms?: number } | null>(null);
  const [testing, setTesting] = useState(false);

  const { register, handleSubmit, reset, formState: { isSubmitting } } = useForm({
    defaultValues: meta.fields.reduce((acc, f) => ({ ...acc, [f.key]: f.defaultValue ?? "" }), {} as Record<string, string>),
  });

  useEffect(() => {
    if (!open) return;
    const preview = existing?.config_preview ?? {};
    const values: Record<string, string> = {};
    meta.fields.forEach((f) => {
      const v = preview[f.key];
      if (v === undefined || v === "__masked__") {
        values[f.key] = f.defaultValue ?? "";
      } else if (f.type === "checkbox") {
        values[f.key] = v ? "true" : "false";
      } else {
        values[f.key] = String(v);
      }
    });
    reset(values);
  }, [open]);

  const saveMut = useMutation({
    mutationFn: async (formData: Record<string, string>) => {
      const config: Record<string, unknown> = {};
      meta.fields.forEach((f) => {
        if (f.type === "checkbox") config[f.key] = formData[f.key] === "true" || formData[f.key] === "on";
        else if (f.key === "port") config[f.key] = parseInt(formData[f.key]) || 9390;
        else if (f.key === "book_id") config[f.key] = parseInt(formData[f.key]) || 1;
        else if (f.key === "chapter_id") { const v = parseInt(formData[f.key]); if (v) config[f.key] = v; }
        else if (f.key === "snapshot_hour") config[f.key] = parseInt(formData[f.key]) || 2;
        else config[f.key] = formData[f.key];
      });

      if (existing) {
        return integrationsApi.update(existing.id, { config });
      }
      return integrationsApi.create({
        type,
        name: meta.label,
        config,
        tenant_id: isSuperAdmin ? null : tenantId,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["integrations"] });
      setOpen(false);
    },
  });

  const deleteMut = useMutation({
    mutationFn: () => integrationsApi.remove(existing!.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["integrations"] }),
  });

  const handleTest = async () => {
    if (!existing) return;
    setTesting(true);
    setTestResult(null);
    try {
      const res = await integrationsApi.test(existing.id);
      setTestResult(res);
    } catch {
      setTestResult({ success: false, message: "Erro ao testar integração" });
    } finally {
      setTesting(false);
    }
  };

  const scopeBadge = existing
    ? existing.scope === "global"
      ? <span className="flex items-center gap-1 text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full"><Globe size={10} />Global</span>
      : <span className="flex items-center gap-1 text-xs bg-brand-100 text-brand-700 px-2 py-0.5 rounded-full"><Building2 size={10} />Tenant</span>
    : null;

  return (
    <div className={`bg-white rounded-xl border ${existing?.is_active ? "border-gray-200" : "border-gray-100 opacity-60"} p-5 flex flex-col gap-3`}>
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-0.5">
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${meta.color}`}>{meta.label}</span>
            {scopeBadge}
          </div>
          <p className="text-xs text-gray-500 mt-1">{meta.description}</p>
        </div>
        {existing ? (
          <CheckCircle2 size={18} className="text-green-500 shrink-0" />
        ) : (
          <XCircle size={18} className="text-gray-300 shrink-0" />
        )}
      </div>

      {/* Test result */}
      {testResult && (
        <div className={`text-xs rounded-lg px-3 py-2 ${testResult.success ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"}`}>
          {testResult.success ? "✓" : "✗"} {testResult.message}
          {testResult.latency_ms && <span className="ml-2 text-gray-400">{testResult.latency_ms.toFixed(0)}ms</span>}
        </div>
      )}

      {/* Config form */}
      {open && (
        <form onSubmit={handleSubmit((d) => saveMut.mutate(d as Record<string, string>))} className="space-y-3 pt-2 border-t border-gray-100">
          {meta.fields.map((f) =>
            f.type === "checkbox" ? (
              <label key={f.key} className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" {...register(f.key)} className="rounded" />
                {f.label}
              </label>
            ) : f.type === "select" ? (
              <div key={f.key}>
                <label className="block text-xs font-medium text-gray-600 mb-1">{f.label}</label>
                <select
                  {...register(f.key)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  {f.options?.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
            ) : (
              <div key={f.key}>
                <label className="block text-xs font-medium text-gray-600 mb-1">{f.label}</label>
                <input
                  type={f.type ?? "text"}
                  {...register(f.key)}
                  placeholder={f.placeholder}
                  className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
            )
          )}
          {saveMut.error && (
            <p className="text-xs text-red-600">
              {(saveMut.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erro ao salvar"}
            </p>
          )}
          <div className="flex gap-2">
            <button type="submit" disabled={isSubmitting || saveMut.isPending}
              className="flex-1 bg-brand-600 text-white text-xs font-medium py-1.5 rounded-lg hover:bg-brand-700 disabled:opacity-50">
              {saveMut.isPending ? "Salvando..." : "Salvar"}
            </button>
            <button type="button" onClick={() => setOpen(false)}
              className="flex-1 border border-gray-300 text-gray-600 text-xs font-medium py-1.5 rounded-lg hover:bg-gray-50">
              Cancelar
            </button>
          </div>
        </form>
      )}

      {/* Actions */}
      <div className="flex gap-2 pt-1">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-800 transition-colors"
        >
          {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          {existing ? "Editar" : "Configurar"}
        </button>

        {existing && (
          <>
            <button
              onClick={handleTest}
              disabled={testing}
              className="flex items-center gap-1 text-xs font-medium text-gray-600 hover:text-gray-900 transition-colors disabled:opacity-50"
            >
              {testing ? <Loader2 size={12} className="animate-spin" /> : null}
              Testar
            </button>
            {(isSuperAdmin || existing.scope === "tenant") && (
              <button
                onClick={() => { if (confirm("Remover integração?")) deleteMut.mutate(); }}
                className="ml-auto text-gray-300 hover:text-red-500 transition-colors"
              >
                <Trash2 size={13} />
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function IntegrationsSection() {
  const { user, tenant, tenantRole } = useAuth();
  const isSuperAdmin = user?.is_super_admin ?? false;
  const canManage = isSuperAdmin || tenantRole === "admin";

  const { data: integrations = [], isLoading } = useQuery({
    queryKey: ["integrations"],
    queryFn: integrationsApi.list,
    enabled: canManage,
  });

  if (!canManage) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 text-sm text-gray-500">
        Apenas administradores podem gerenciar integrações.
      </div>
    );
  }

  const types: IntegrationType[] = ["shodan", "wazuh", "zabbix", "openvas", "nmap", "bookstack"];

  return (
    <div>
      <div className="mb-4">
        <h2 className="font-semibold text-gray-900">Integrações</h2>
        <p className="text-sm text-gray-500 mt-0.5">
          {isSuperAdmin
            ? "Configurações globais ficam disponíveis para todos os tenants como fallback."
            : "Configurações deste tenant sobrepõem as globais."}
        </p>
      </div>

      {isLoading ? (
        <p className="text-sm text-gray-400">Carregando...</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {types.map((t) => {
            const tenantSpecific = integrations.find((i) => i.type === t && i.scope === "tenant");
            const global = integrations.find((i) => i.type === t && i.scope === "global");
            const effective = tenantSpecific ?? global;
            return (
              <IntegrationCard
                key={t}
                type={t}
                existing={effective}
                tenantId={tenant?.id ?? null}
                isSuperAdmin={isSuperAdmin}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function Settings() {
  const { user } = useAuth();
  const [tab, setTab] = useState<"conta" | "integracoes">("conta");

  return (
    <PageWrapper title="Configurações">
      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {(["conta", "integracoes"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t
                ? "border-brand-600 text-brand-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t === "conta" ? "Conta" : "Integrações"}
          </button>
        ))}
      </div>

      {tab === "conta" && (
        <div className="max-w-lg space-y-6">
          {/* Profile */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="h-10 w-10 rounded-full bg-brand-100 flex items-center justify-center">
                <User size={18} className="text-brand-600" />
              </div>
              <div>
                <p className="font-semibold text-gray-900">{user?.name ?? "—"}</p>
                <p className="text-sm text-gray-500">{user?.email ?? "—"}</p>
              </div>
            </div>
            <div className="flex gap-2 text-xs text-gray-400">
              <span className="bg-gray-100 px-2 py-0.5 rounded-full">{user?.role}</span>
              {user?.is_super_admin && <span className="bg-brand-100 text-brand-700 px-2 py-0.5 rounded-full">Super Admin</span>}
              {user?.mfa_enabled && <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded-full">MFA ativo</span>}
            </div>
          </div>
          <PasswordSection />
        </div>
      )}

      {tab === "integracoes" && <IntegrationsSection />}
    </PageWrapper>
  );
}
