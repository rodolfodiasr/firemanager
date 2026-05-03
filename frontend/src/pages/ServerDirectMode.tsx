import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useAuthStore } from "../store/authStore";
import {
  Terminal, Play, Send, ChevronRight, CheckCircle2, XCircle,
  Loader2, AlertCircle, Server,
} from "lucide-react";
import toast from "react-hot-toast";
import { PageWrapper } from "../components/layout/PageWrapper";
import { serversApi } from "../api/servers";
import type { ServerOperation } from "../types/server_operation";

type Step = "compose" | "result";

export function ServerDirectMode() {
  const [step, setStep] = useState<Step>("compose");
  const [serverId, setServerId] = useState("");
  const [description, setDescription] = useState("");
  const [rawCommands, setRawCommands] = useState("");
  const [result, setResult] = useState<ServerOperation | null>(null);

  const tenantRole = useAuthStore((s) => s.tenantRole);
  const isN1 = tenantRole === "analyst_n1";

  const { data: servers = [], isLoading: loadingServers } = useQuery({
    queryKey: ["servers"],
    queryFn: serversApi.list,
  });

  const commands = rawCommands.split("\n").map((l) => l.trim()).filter(Boolean);
  const selectedServer = servers.find((s) => s.id === serverId);
  const canSubmit = serverId && description.trim() && commands.length > 0;

  const execMut = useMutation({
    mutationFn: () => serversApi.exec(serverId, { description, commands }),
    onSuccess: (data) => {
      setResult(data);
      setStep("result");
      if (data.status === "completed") toast.success("Comandos executados com sucesso!");
      else toast.error("Execução com erros — verifique o output.");
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg ?? "Erro ao executar comandos.");
    },
  });

  const reviewMut = useMutation({
    mutationFn: () => serversApi.submitForReview(serverId, { description, commands }),
    onSuccess: (data) => {
      setResult(data);
      setStep("result");
      toast.success("Enviado para revisão N2.");
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg ?? "Erro ao enviar para revisão.");
    },
  });

  const reset = () => {
    setStep("compose");
    setServerId("");
    setDescription("");
    setRawCommands("");
    setResult(null);
  };

  return (
    <PageWrapper title="Modo Técnico — Servidores">
      <div className="max-w-3xl">
        {/* Step indicator */}
        <div className="flex items-center gap-2 mb-6 text-sm">
          {(["compose", "result"] as Step[]).map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              {i > 0 && <ChevronRight size={14} className="text-gray-300" />}
              <span className={`font-medium ${step === s ? "text-brand-600" : "text-gray-400"}`}>
                {s === "compose" ? "Compor" : "Resultado"}
              </span>
            </div>
          ))}
        </div>

        {/* ── Compose ── */}
        {step === "compose" && (
          <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
            <div className="flex items-center gap-2">
              <Terminal size={18} className="text-brand-600" />
              <h2 className="text-base font-semibold text-gray-900">Inserir Comandos</h2>
            </div>
            <p className="text-sm text-gray-500">
              Digite comandos Shell (Linux) ou PowerShell (Windows) para executar diretamente no servidor via SSH/WinRM.
              Os comandos são executados em sequência e o output completo é registrado.
            </p>

            {/* Server selector */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Servidor</label>
              {loadingServers ? (
                <p className="text-sm text-gray-400">Carregando servidores...</p>
              ) : (
                <select
                  value={serverId}
                  onChange={(e) => setServerId(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  <option value="">Selecione um servidor...</option>
                  {servers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} — {s.os_type === "windows" ? "Windows" : "Linux"} ({s.host})
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* OS hint */}
            {selectedServer && (
              <div className="flex items-center gap-2 text-xs text-gray-500 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
                <Server size={13} />
                <span>
                  {selectedServer.os_type === "windows"
                    ? "PowerShell — comandos serão executados via WinRM"
                    : "Bash/Shell — comandos serão executados via SSH"}
                </span>
              </div>
            )}

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Descrição da operação</label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="ex: Verificar uso de disco — ticket #456"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>

            {/* Commands */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Comandos{" "}
                <span className="font-normal text-gray-400">(um por linha)</span>
              </label>
              <textarea
                value={rawCommands}
                onChange={(e) => setRawCommands(e.target.value)}
                rows={12}
                spellCheck={false}
                placeholder={
                  selectedServer?.os_type === "windows"
                    ? "Get-Disk\nGet-Volume\nGet-Service | Where-Object Status -eq Stopped"
                    : "df -h\nfree -m\nsystemctl status nginx"
                }
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
              />
              {commands.length > 0 && (
                <p className="text-xs text-gray-400 mt-1">{commands.length} comando(s)</p>
              )}
            </div>

            {/* Warning / N1 banner */}
            {isN1 ? (
              <div className="flex items-start gap-2 text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5">
                <AlertCircle size={15} className="mt-0.5 shrink-0 text-amber-500" />
                <span>
                  Analistas N1 não executam diretamente. Use <strong>Enviar para N2</strong> para enviar para revisão.
                </span>
              </div>
            ) : (
              commands.length > 0 && serverId && (
                <div className="flex items-start gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5">
                  <AlertCircle size={13} className="mt-0.5 shrink-0" />
                  <span>
                    Os comandos serão executados diretamente em{" "}
                    <strong>{selectedServer?.name}</strong>. Use "Enviar para N2" para operações
                    que exijam aprovação antes de executar.
                  </span>
                </div>
              )
            )}

            <div className="flex gap-3 pt-1">
              {!isN1 && (
                <button
                  onClick={() => execMut.mutate()}
                  disabled={!canSubmit || execMut.isPending || reviewMut.isPending}
                  className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50"
                >
                  {execMut.isPending ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
                  Executar agora
                </button>
              )}
              <button
                onClick={() => reviewMut.mutate()}
                disabled={!canSubmit || execMut.isPending || reviewMut.isPending}
                className="flex items-center gap-2 px-5 py-2.5 bg-yellow-500 text-white text-sm font-medium rounded-lg hover:bg-yellow-600 disabled:opacity-50"
              >
                {reviewMut.isPending ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
                Enviar para N2
              </button>
            </div>
          </div>
        )}

        {/* ── Result ── */}
        {step === "result" && result && (
          <div className="space-y-4">
            {/* Status header */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center gap-3 mb-3">
                {result.status === "completed" && <CheckCircle2 size={22} className="text-green-500" />}
                {result.status === "failed"    && <XCircle size={22} className="text-red-400" />}
                {result.status === "pending_review" && <Loader2 size={22} className="text-yellow-500" />}
                <div>
                  <p className="text-base font-semibold text-gray-900">
                    {result.status === "completed"     && "Executado com sucesso"}
                    {result.status === "failed"        && "Execução com erros"}
                    {result.status === "pending_review" && "Aguardando revisão N2"}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {result.server_name} · {new Date(result.created_at).toLocaleString("pt-BR")}
                  </p>
                </div>
              </div>

              <div className="text-sm text-gray-700">
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Descrição: </span>
                {result.description}
              </div>

              <div className="mt-3">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Comandos ({result.commands.length})</p>
                <pre className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-xs font-mono text-gray-700 overflow-x-auto">
                  {result.commands.join("\n")}
                </pre>
              </div>
            </div>

            {/* Output (only for executed ops) */}
            {result.output && (
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Output</p>
                <pre className={`text-xs rounded-lg p-4 overflow-auto max-h-96 whitespace-pre-wrap font-mono border ${
                  result.status === "failed"
                    ? "bg-red-50 border-red-200 text-red-800"
                    : "bg-gray-900 border-gray-700 text-green-300"
                }`}>
                  {result.output}
                </pre>
              </div>
            )}

            {result.status === "pending_review" && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-sm text-yellow-800">
                A operação foi registrada e aguarda aprovação de um revisor N2 na aba <strong>Auditoria → Pendentes</strong>.
              </div>
            )}

            <button
              onClick={reset}
              className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700"
            >
              Nova operação
            </button>
          </div>
        )}
      </div>
    </PageWrapper>
  );
}
