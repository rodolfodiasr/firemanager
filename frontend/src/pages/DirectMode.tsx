import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Terminal, Play, Send, ChevronRight, CheckCircle2, XCircle, Loader2, Pencil } from "lucide-react";
import toast from "react-hot-toast";
import { PageWrapper } from "../components/layout/PageWrapper";
import { devicesApi } from "../api/devices";
import { operationsApi } from "../api/operations";
import type { Device } from "../types/device";

type Step = "compose" | "review" | "done";

export function DirectMode() {
  const [searchParams] = useSearchParams();
  const editId = searchParams.get("edit");

  const [step, setStep] = useState<Step>("compose");
  const [deviceId, setDeviceId] = useState("");
  const [description, setDescription] = useState("");
  const [rawCommands, setRawCommands] = useState("");
  const [operationId, setOperationId] = useState<string | null>(null);
  const [opStatus, setOpStatus] = useState<"idle" | "executing" | "done" | "failed">("idle");

  const { data: editOp } = useQuery({
    queryKey: ["operation", editId],
    queryFn: () => operationsApi.get(editId!),
    enabled: !!editId,
    staleTime: Infinity,
  });

  useEffect(() => {
    if (!editOp) return;
    setDeviceId(editOp.device_id);
    setDescription(editOp.natural_language_input);
    const cmds = (editOp.action_plan?.ssh_commands as string[] | undefined) ?? [];
    setRawCommands(cmds.join("\n"));
  }, [editOp?.id]);

  const { data: devices = [] } = useQuery({
    queryKey: ["devices"],
    queryFn: devicesApi.list,
  });

  const commands = rawCommands
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);

  const createMutation = useMutation({
    mutationFn: () =>
      operationsApi.createDirectSSH({
        device_id: deviceId,
        description,
        ssh_commands: commands,
        ...(editId ? { parent_operation_id: editId } : {}),
      }),
    onSuccess: (data) => {
      setOperationId(data.id);
      setStep("review");
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg ?? "Erro ao criar operação.");
    },
  });

  const executeMutation = useMutation({
    mutationFn: () => operationsApi.execute(operationId!),
    onMutate: () => setOpStatus("executing"),
    onSuccess: (data) => {
      setOpStatus(data.status === "completed" ? "done" : "failed");
      setStep("done");
      if (data.status === "completed") toast.success("Comandos executados com sucesso!");
      else toast.error("Execução falhou. Verifique o histórico.");
    },
    onError: () => {
      setOpStatus("failed");
      setStep("done");
      toast.error("Erro ao executar operação.");
    },
  });

  const reviewMutation = useMutation({
    mutationFn: () => operationsApi.submitForReview(operationId!),
    onSuccess: () => {
      toast.success("Enviado para revisão N2.");
      setStep("done");
      setOpStatus("done");
    },
    onError: () => toast.error("Erro ao enviar para revisão."),
  });

  const selectedDevice = devices.find((d: Device) => d.id === deviceId);
  const canSubmit = deviceId && description.trim() && commands.length > 0;

  return (
    <PageWrapper title={editOp ? "Editar Operação SSH" : "Modo Técnico"}>
      <div className="max-w-3xl">
        {/* Edit banner */}
        {editOp && (
          <div className="flex items-start gap-2 mb-4 px-4 py-3 bg-amber-50 border border-amber-200 rounded-xl">
            <Pencil size={14} className="text-amber-600 shrink-0 mt-0.5" />
            <p className="text-xs text-amber-800">
              <span className="font-semibold">Editando operação:</span>{" "}
              {editOp.natural_language_input}
            </p>
          </div>
        )}

        {/* Step indicator */}
        <div className="flex items-center gap-2 mb-6 text-sm">
          {(["compose", "review", "done"] as Step[]).map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              {i > 0 && <ChevronRight size={14} className="text-gray-300" />}
              <span className={`font-medium ${step === s ? "text-brand-600" : "text-gray-400"}`}>
                {s === "compose" ? "Compor" : s === "review" ? "Revisar" : "Resultado"}
              </span>
            </div>
          ))}
        </div>

        {step === "compose" && (
          <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
            <div className="flex items-center gap-2 mb-1">
              <Terminal size={18} className="text-brand-600" />
              <h2 className="text-base font-semibold text-gray-900">Inserir Comandos SSH</h2>
            </div>
            <p className="text-sm text-gray-500">
              Digite os comandos CLI diretamente. O sistema entrará em modo configure
              automaticamente — não inclua <code className="bg-gray-100 px-1 rounded">configure</code> ou{" "}
              <code className="bg-gray-100 px-1 rounded">end</code>.
            </p>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Dispositivo</label>
              <select
                value={deviceId}
                onChange={(e) => setDeviceId(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="">Selecione um dispositivo...</option>
                {devices.map((d: Device) => (
                  <option key={d.id} value={d.id}>
                    {d.name} — {d.vendor} ({d.host})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Descrição da operação</label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="ex: Ativar Gateway AV — solicitação #123"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Comandos SSH{" "}
                <span className="font-normal text-gray-400">(um por linha)</span>
              </label>
              <textarea
                value={rawCommands}
                onChange={(e) => setRawCommands(e.target.value)}
                rows={12}
                spellCheck={false}
                placeholder={"gateway-antivirus\nenable\nexit\ncommit"}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
              />
              {commands.length > 0 && (
                <p className="text-xs text-gray-400 mt-1">{commands.length} comando(s)</p>
              )}
            </div>

            <button
              onClick={() => createMutation.mutate()}
              disabled={!canSubmit || createMutation.isPending}
              className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50"
            >
              {createMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <ChevronRight size={15} />}
              Avançar para Revisão
            </button>
          </div>
        )}

        {step === "review" && operationId && (
          <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
            <h2 className="text-base font-semibold text-gray-900">Revisar antes de executar</h2>

            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Dispositivo</p>
              <p className="text-sm text-gray-800">{selectedDevice?.name} — {selectedDevice?.host}</p>
            </div>

            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Descrição</p>
              <p className="text-sm text-gray-800">{description}</p>
            </div>

            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                Comandos ({commands.length})
              </p>
              <pre className="bg-gray-900 text-green-300 rounded-lg p-4 text-xs font-mono overflow-auto max-h-64 whitespace-pre-wrap">
                {commands.join("\n")}
              </pre>
            </div>

            <div className="flex gap-3 pt-1">
              <button
                onClick={() => executeMutation.mutate()}
                disabled={executeMutation.isPending || reviewMutation.isPending}
                className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50"
              >
                {executeMutation.isPending
                  ? <Loader2 size={15} className="animate-spin" />
                  : <Play size={15} />}
                Executar
              </button>
              <button
                onClick={() => reviewMutation.mutate()}
                disabled={executeMutation.isPending || reviewMutation.isPending}
                className="flex items-center gap-2 px-5 py-2.5 bg-yellow-500 text-white text-sm font-medium rounded-lg hover:bg-yellow-600 disabled:opacity-50"
              >
                {reviewMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
                Enviar para N2
              </button>
              <button
                onClick={() => setStep("compose")}
                disabled={executeMutation.isPending || reviewMutation.isPending}
                className="px-4 py-2.5 text-sm text-gray-500 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >
                Voltar
              </button>
            </div>
          </div>
        )}

        {step === "done" && (
          <div className="bg-white rounded-xl border border-gray-200 p-8 text-center space-y-4">
            {opStatus === "done" ? (
              <CheckCircle2 size={48} className="mx-auto text-green-500" />
            ) : (
              <XCircle size={48} className="mx-auto text-red-400" />
            )}
            <h2 className="text-lg font-semibold text-gray-900">
              {opStatus === "done" ? "Operação concluída" : "Operação enviada / falhou"}
            </h2>
            <p className="text-sm text-gray-500">
              Consulte o <strong>Histórico de Auditoria</strong> para ver o output SSH completo.
            </p>
            <button
              onClick={() => {
                setStep("compose");
                setDeviceId("");
                setDescription("");
                setRawCommands("");
                setOperationId(null);
                setOpStatus("idle");
              }}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700"
            >
              Nova operação
            </button>
          </div>
        )}
      </div>
    </PageWrapper>
  );
}
