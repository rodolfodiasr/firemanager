import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Server as ServerIcon, Plus, Trash2, Pencil, CheckCircle2, XCircle,
  Loader2, Terminal, Monitor,
} from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { serversApi } from "../api/servers";
import type { Server, ServerCreate } from "../types/server";

// ── Credential fields ─────────────────────────────────────────────────────────

function LinuxCredentials({ register, initial }: {
  register: ReturnType<typeof useForm<ServerCreate>>["register"];
  initial?: Server;
}) {
  return (
    <>
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Usuário *</label>
        <input
          {...register("credentials.username", { required: !initial ? "Obrigatório" : false })}
          placeholder="root"
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Senha</label>
        <input
          type="password"
          {...register("credentials.password")}
          placeholder="••••••••"
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">
          Chave Privada RSA (PEM) — alternativa à senha
        </label>
        <textarea
          {...register("credentials.private_key")}
          rows={3}
          placeholder={"-----BEGIN RSA PRIVATE KEY-----\n..."}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
        />
      </div>
    </>
  );
}

function WindowsCredentials({ register, initial }: {
  register: ReturnType<typeof useForm<ServerCreate>>["register"];
  initial?: Server;
}) {
  return (
    <>
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Usuário *</label>
        <input
          {...register("credentials.username", { required: !initial ? "Obrigatório" : false })}
          placeholder="Administrator"
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        <p className="text-xs text-gray-400 mt-1">Para domínio use: DOMINIO\usuario</p>
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Senha *</label>
        <input
          type="password"
          {...register("credentials.password", { required: !initial ? "Obrigatório" : false })}
          placeholder="••••••••"
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Autenticação WinRM</label>
        <select
          {...register("credentials.auth_type")}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="ntlm">NTLM — workgroup / conta local (padrão)</option>
          <option value="ssl">SSL/Basic — HTTPS com certificado</option>
          <option value="kerberos">Kerberos — domínio Active Directory</option>
        </select>
      </div>
      <div className="bg-blue-50 border border-blue-200 rounded-lg px-3 py-2.5 text-xs text-blue-700 space-y-1">
        <p className="font-medium">Pré-requisito no servidor Windows:</p>
        <p>Execute no PowerShell como Administrador:</p>
        <code className="block bg-blue-100 rounded px-2 py-1 font-mono mt-1">
          Enable-PSRemoting -Force
        </code>
        <p className="mt-1">Para NTLM via HTTP também adicione:</p>
        <code className="block bg-blue-100 rounded px-2 py-1 font-mono">
          Set-Item WSMan:\localhost\Service\Auth\Basic $true{"\n"}
          Set-Item WSMan:\localhost\Service\AllowUnencrypted $true
        </code>
      </div>
    </>
  );
}

// ── Modal ─────────────────────────────────────────────────────────────────────

interface ModalProps {
  initial?: Server;
  onClose: () => void;
}

function ServerModal({ initial, onClose }: ModalProps) {
  const qc = useQueryClient();
  const { register, handleSubmit, control, formState: { errors, isSubmitting } } = useForm<ServerCreate>({
    defaultValues: initial
      ? {
          name: initial.name,
          host: initial.host,
          ssh_port: initial.ssh_port,
          os_type: initial.os_type,
          description: initial.description ?? "",
          credentials: { username: "", auth_type: "ntlm" } as ServerCreate["credentials"],
        }
      : { ssh_port: 22, os_type: "linux", credentials: { username: "", auth_type: "ntlm" } as ServerCreate["credentials"] },
  });

  const osType = useWatch({ control, name: "os_type" });
  const isWindows = osType === "windows";

  const mut = useMutation({
    mutationFn: async (data: ServerCreate) => {
      if (initial) {
        return serversApi.update(initial.id, {
          name: data.name,
          host: data.host,
          ssh_port: data.ssh_port,
          os_type: data.os_type,
          description: data.description,
          credentials: data.credentials.username ? data.credentials : undefined,
        });
      }
      return serversApi.create(data);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["servers"] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl w-full max-w-lg shadow-xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 sticky top-0 bg-white z-10">
          <h2 className="font-semibold text-gray-900">
            {initial ? "Editar Servidor" : "Registrar Servidor"}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">✕</button>
        </div>

        <form onSubmit={handleSubmit((d) => mut.mutate(d))} className="p-6 space-y-4">
          {/* Info básica */}
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-700 mb-1">Nome *</label>
              <input
                {...register("name", { required: "Obrigatório" })}
                placeholder="ex: Web Server 01"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              {errors.name && <p className="text-xs text-red-600 mt-1">{errors.name.message}</p>}
            </div>

            <div className="col-span-2 sm:col-span-1">
              <label className="block text-xs font-medium text-gray-700 mb-1">Sistema Operacional</label>
              <select
                {...register("os_type")}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="linux">Linux</option>
                <option value="windows">Windows Server</option>
              </select>
            </div>

            <div className="sm:col-span-1">
              <label className="block text-xs font-medium text-gray-700 mb-1">
                {isWindows ? "Porta WinRM" : "Porta SSH"}
              </label>
              <input
                type="number"
                {...register("ssh_port", { valueAsNumber: true, min: 1, max: 65535 })}
                placeholder={isWindows ? "5985" : "22"}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              {isWindows && (
                <p className="text-xs text-gray-400 mt-1">5985 = HTTP · 5986 = HTTPS</p>
              )}
            </div>

            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-700 mb-1">Host / IP *</label>
              <input
                {...register("host", { required: "Obrigatório" })}
                placeholder="192.168.1.100"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>

            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-700 mb-1">Descrição</label>
              <input
                {...register("description")}
                placeholder="ex: Servidor de banco de dados produção"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
          </div>

          {/* Credenciais — dinâmico por OS */}
          <div className="border-t border-gray-100 pt-4 space-y-3">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              {isWindows ? "Credenciais WinRM" : "Credenciais SSH"}
              {initial && " (deixe vazio para manter atual)"}
            </p>
            {isWindows
              ? <WindowsCredentials register={register} initial={initial} />
              : <LinuxCredentials register={register} initial={initial} />
            }
          </div>

          {mut.error && (
            <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {(mut.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erro ao salvar"}
            </p>
          )}

          <div className="flex gap-2 pt-2">
            <button
              type="submit"
              disabled={isSubmitting || mut.isPending}
              className="flex-1 bg-brand-600 text-white text-sm font-medium py-2 rounded-lg hover:bg-brand-700 disabled:opacity-50"
            >
              {mut.isPending ? "Salvando..." : initial ? "Salvar alterações" : "Registrar servidor"}
            </button>
            <button type="button" onClick={onClose}
              className="flex-1 border border-gray-300 text-gray-600 text-sm font-medium py-2 rounded-lg hover:bg-gray-50">
              Cancelar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Row ───────────────────────────────────────────────────────────────────────

interface RowProps {
  server: Server;
  onEdit: () => void;
}

function ServerRow({ server, onEdit }: RowProps) {
  const qc = useQueryClient();
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [testing, setTesting] = useState(false);

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await serversApi.test(server.id);
      setTestResult(res);
    } catch {
      setTestResult({ success: false, message: "Erro ao testar conexão" });
    } finally {
      setTesting(false);
    }
  };

  const deleteMut = useMutation({
    mutationFn: () => serversApi.remove(server.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["servers"] }),
  });

  const isWindows = server.os_type === "windows";
  const OsIcon = isWindows ? Monitor : Terminal;
  const proto = isWindows ? "WinRM" : "SSH";
  const osBadgeColor = isWindows
    ? "bg-blue-100 text-blue-700"
    : "bg-green-100 text-green-700";

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 flex items-start gap-4 hover:border-gray-300 transition-colors">
      <div className="h-10 w-10 rounded-lg bg-gray-100 flex items-center justify-center shrink-0">
        <OsIcon size={18} className="text-gray-500" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="font-medium text-gray-900 text-sm">{server.name}</p>
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${osBadgeColor}`}>
            {isWindows ? "Windows" : "Linux"}
          </span>
          {server.is_active
            ? <CheckCircle2 size={13} className="text-green-500" />
            : <XCircle size={13} className="text-gray-300" />}
        </div>
        <p className="text-xs text-gray-500 mt-0.5">
          {server.host}:{server.ssh_port}
          <span className="text-gray-300 ml-2">via {proto}</span>
        </p>
        {server.description && (
          <p className="text-xs text-gray-400 mt-0.5 truncate">{server.description}</p>
        )}
        {testResult && (
          <p className={`text-xs mt-1.5 font-medium ${testResult.success ? "text-green-600" : "text-red-600"}`}>
            {testResult.success ? "✓" : "✗"} {testResult.message}
          </p>
        )}
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <button onClick={handleTest} disabled={testing}
          className="text-xs text-gray-500 hover:text-gray-800 font-medium flex items-center gap-1 disabled:opacity-50">
          {testing ? <Loader2 size={12} className="animate-spin" /> : null}
          Testar
        </button>
        <button onClick={onEdit} className="text-gray-400 hover:text-brand-600 transition-colors">
          <Pencil size={14} />
        </button>
        <button
          onClick={() => { if (confirm(`Remover "${server.name}"?`)) deleteMut.mutate(); }}
          className="text-gray-300 hover:text-red-500 transition-colors"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function Servers() {
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<Server | undefined>();

  const { data: servers = [], isLoading } = useQuery({
    queryKey: ["servers"],
    queryFn: serversApi.list,
  });

  const openCreate = () => { setEditing(undefined); setShowModal(true); };
  const openEdit   = (s: Server) => { setEditing(s); setShowModal(true); };
  const closeModal = () => setShowModal(false);

  const linux   = servers.filter((s) => s.os_type === "linux");
  const windows = servers.filter((s) => s.os_type === "windows");

  return (
    <PageWrapper title="Servidores">
      <div className="flex items-start justify-between mb-6">
        <p className="text-sm text-gray-500 mt-1">
          Registre servidores Linux (SSH) e Windows (WinRM) para análise pelo Analista N3.
        </p>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 bg-brand-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-brand-700 transition-colors shrink-0"
        >
          <Plus size={16} />
          Adicionar
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-gray-400 py-8">
          <Loader2 size={16} className="animate-spin" /> Carregando...
        </div>
      ) : servers.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <ServerIcon size={40} className="text-gray-200 mb-3" />
          <p className="text-gray-500 font-medium">Nenhum servidor cadastrado</p>
          <p className="text-sm text-gray-400 mt-1 max-w-sm">
            Registre servidores Linux via SSH ou Windows via WinRM para coletar diagnósticos e analisar com IA.
          </p>
          <button onClick={openCreate}
            className="mt-4 flex items-center gap-2 bg-brand-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-brand-700">
            <Plus size={16} /> Adicionar servidor
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {linux.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Terminal size={14} className="text-green-600" />
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Linux — SSH ({linux.length})
                </p>
              </div>
              <div className="space-y-2">
                {linux.map((s) => (
                  <ServerRow key={s.id} server={s} onEdit={() => openEdit(s)} />
                ))}
              </div>
            </div>
          )}
          {windows.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Monitor size={14} className="text-blue-600" />
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Windows — WinRM ({windows.length})
                </p>
              </div>
              <div className="space-y-2">
                {windows.map((s) => (
                  <ServerRow key={s.id} server={s} onEdit={() => openEdit(s)} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {showModal && <ServerModal initial={editing} onClose={closeModal} />}
    </PageWrapper>
  );
}
