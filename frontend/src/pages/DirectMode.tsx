import { useState, useEffect } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useAuthStore } from "../store/authStore";
import {
  Terminal, Play, Send, ChevronRight, CheckCircle2, XCircle, Loader2, Pencil,
  Layers, Square, CheckSquare, AlertCircle,
} from "lucide-react";
import toast from "react-hot-toast";
import { PageWrapper } from "../components/layout/PageWrapper";
import { devicesApi } from "../api/devices";
import { operationsApi } from "../api/operations";
import type { Device } from "../types/device";

type Step = "compose" | "review" | "done";
type Mode = "single" | "bulk";

interface BulkResult {
  deviceName: string;
  operationId: string;
  status: "pending" | "executing" | "done" | "failed";
}

export function DirectMode() {
  const [searchParams] = useSearchParams();
  const editId = searchParams.get("edit");
  const deviceParam = searchParams.get("device");

  const [mode, setMode] = useState<Mode>("single");
  const [step, setStep] = useState<Step>("compose");

  // single-device state
  const [deviceId, setDeviceId] = useState(deviceParam ?? "");
  const [operationId, setOperationId] = useState<string | null>(null);
  const [opStatus, setOpStatus] = useState<"idle" | "executing" | "done" | "failed">("idle");

  // bulk state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkResults, setBulkResults] = useState<BulkResult[]>([]);
  const [bulkRunning, setBulkRunning] = useState(false);

  // shared state
  const [description, setDescription] = useState("");
  const [rawCommands, setRawCommands] = useState("");

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

  const tenantRole = useAuthStore((s) => s.tenantRole);
  const isN1 = tenantRole === "analyst_n1";

  const { data: devices = [] } = useQuery({
    queryKey: ["devices"],
    queryFn: devicesApi.list,
  });

  const commands = rawCommands
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);

  // ── Single-device mutations ──────────────────────────────────────────────────

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
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setOpStatus("failed");
      setStep("done");
      toast.error(msg ?? "Erro ao executar operação.");
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

  // ── Bulk execution ───────────────────────────────────────────────────────────

  const runBulk = async () => {
    const ids = [...selectedIds];
    const results: BulkResult[] = ids.map((id) => ({
      deviceName: devices.find((d: Device) => d.id === id)?.name ?? id,
      operationId: "",
      status: "pending",
    }));
    setBulkResults(results);
    setBulkRunning(true);
    setStep("review");

    for (let i = 0; i < ids.length; i++) {
      results[i] = { ...results[i], status: "executing" };
      setBulkResults([...results]);
      try {
        const op = await operationsApi.createDirectSSH({
          device_id: ids[i],
          description,
          ssh_commands: commands,
        });
        const executed = await operationsApi.execute(op.id);
        results[i] = {
          ...results[i],
          operationId: op.id,
          status: executed.status === "completed" ? "done" : "failed",
        };
      } catch {
        results[i] = { ...results[i], status: "failed" };
      }
      setBulkResults([...results]);
    }

    setBulkRunning(false);
    setStep("done");
    const failed = results.filter((r) => r.status === "failed").length;
    if (failed === 0) toast.success("Todos os dispositivos executados com sucesso!");
    else toast.error(`${failed} dispositivo(s) com falha.`);
  };

  const toggleBulkId = (id: string) =>
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  // ── Derived ──────────────────────────────────────────────────────────────────

  const selectedDevice = devices.find((d: Device) => d.id === deviceId);
  const canSubmitSingle = deviceId && description.trim() && commands.length > 0;
  const canSubmitBulk = selectedIds.size >= 2 && description.trim() && commands.length > 0;
  const canBulk = !editId && devices.length >= 2;

  const resetAll = () => {
    setStep("compose");
    setDeviceId("");
    setDescription("");
    setRawCommands("");
    setOperationId(null);
    setOpStatus("idle");
    setSelectedIds(new Set());
    setBulkResults([]);
  };

  // ── Render ───────────────────────────────────────────────────────────────────

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

        {/* Mode toggle */}
        {canBulk && step === "compose" && (
          <div className="flex items-center gap-2 mb-5">
            <button
              onClick={() => setMode("single")}
              className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                mode === "single"
                  ? "bg-brand-50 border-brand-300 text-brand-700 font-medium"
                  : "border-gray-200 text-gray-500 hover:border-gray-300"
              }`}
            >
              Dispositivo único
            </button>
            <button
              onClick={() => setMode("bulk")}
              className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                mode === "bulk"
                  ? "bg-amber-50 border-amber-300 text-amber-700 font-medium"
                  : "border-gray-200 text-gray-500 hover:border-gray-300"
              }`}
            >
              <Layers size={12} />
              Operação em lote
            </button>
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

        {/* ── Compose ── */}
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

            {/* Device selector — single */}
            {mode === "single" && (
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
            )}

            {/* Device selector — bulk */}
            {mode === "bulk" && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium text-gray-700">Dispositivos</label>
                  <button
                    onClick={() =>
                      setSelectedIds(
                        selectedIds.size === devices.length
                          ? new Set()
                          : new Set(devices.map((d: Device) => d.id))
                      )
                    }
                    className="text-xs text-brand-600 hover:underline"
                  >
                    {selectedIds.size === devices.length ? "Desmarcar todos" : "Selecionar todos"}
                  </button>
                </div>
                <div className="border border-gray-200 rounded-lg overflow-hidden divide-y divide-gray-100">
                  {devices.map((d: Device) => {
                    const checked = selectedIds.has(d.id);
                    return (
                      <button
                        key={d.id}
                        onClick={() => toggleBulkId(d.id)}
                        className={`w-full flex items-center gap-3 px-3 py-2.5 text-sm text-left transition-colors ${
                          checked ? "bg-amber-50" : "hover:bg-gray-50"
                        }`}
                      >
                        {checked
                          ? <CheckSquare size={14} className="text-amber-600 shrink-0" />
                          : <Square size={14} className="text-gray-300 shrink-0" />}
                        <span className="font-medium text-gray-800">{d.name}</span>
                        <span className="text-gray-400 text-xs">{d.vendor} · {d.host}</span>
                      </button>
                    );
                  })}
                </div>
                {selectedIds.size >= 2 && (
                  <div className="flex items-start gap-1.5 mt-2 text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-2.5 text-xs">
                    <AlertCircle size={13} className="mt-0.5 shrink-0" />
                    <span>
                      Os mesmos {commands.length || "N"} comando(s) serão aplicados nos {selectedIds.size} dispositivos selecionados.
                    </span>
                  </div>
                )}
                {selectedIds.size === 1 && (
                  <p className="text-xs text-gray-400 mt-1">Selecione pelo menos 2 dispositivos para o modo em lote.</p>
                )}
              </div>
            )}

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

            {mode === "single" ? (
              <button
                onClick={() => createMutation.mutate()}
                disabled={!canSubmitSingle || createMutation.isPending}
                className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50"
              >
                {createMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <ChevronRight size={15} />}
                Avançar para Revisão
              </button>
            ) : (
              <button
                onClick={runBulk}
                disabled={!canSubmitBulk}
                className="flex items-center gap-2 px-5 py-2.5 bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium rounded-lg disabled:opacity-50"
              >
                <Layers size={15} />
                Executar em {selectedIds.size || "N"} dispositivos
              </button>
            )}
          </div>
        )}

        {/* ── Review (single) ── */}
        {step === "review" && mode === "single" && operationId && (
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

            {isN1 && (
              <div className="flex items-start gap-2 text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5">
                <AlertCircle size={15} className="mt-0.5 shrink-0 text-amber-500" />
                <span>
                  Analistas N1 não executam diretamente. Use <strong>Enviar para N2</strong> para enviar para revisão.
                </span>
              </div>
            )}

            <div className="flex gap-3 pt-1">
              {!isN1 && (
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
              )}
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

        {/* ── Review (bulk) — live progress ── */}
        {step === "review" && mode === "bulk" && (
          <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
            <div className="flex items-center gap-2">
              <Layers size={16} className="text-amber-500" />
              <h2 className="text-base font-semibold text-gray-900">Executando em lote...</h2>
              {bulkRunning && <Loader2 size={14} className="animate-spin text-amber-500" />}
            </div>
            <div className="space-y-2">
              {bulkResults.map((r, i) => (
                <div key={i} className="flex items-center gap-3 px-3 py-2.5 border border-gray-100 rounded-lg">
                  {r.status === "pending" && <div className="w-4 h-4 rounded-full border-2 border-gray-200" />}
                  {r.status === "executing" && <Loader2 size={14} className="animate-spin text-amber-500" />}
                  {r.status === "done" && <CheckCircle2 size={14} className="text-green-500" />}
                  {r.status === "failed" && <XCircle size={14} className="text-red-400" />}
                  <span className="text-sm text-gray-800">{r.deviceName}</span>
                  <span className={`text-xs ml-auto ${
                    r.status === "done" ? "text-green-600" :
                    r.status === "failed" ? "text-red-500" :
                    r.status === "executing" ? "text-amber-600" : "text-gray-400"
                  }`}>
                    {r.status === "pending" ? "Aguardando" :
                     r.status === "executing" ? "Executando..." :
                     r.status === "done" ? "Concluído" : "Falhou"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Done (single) ── */}
        {step === "done" && mode === "single" && (
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
              onClick={resetAll}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700"
            >
              Nova operação
            </button>
          </div>
        )}

        {/* ── Done (bulk) ── */}
        {step === "done" && mode === "bulk" && (
          <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
            {(() => {
              const done = bulkResults.filter((r) => r.status === "done").length;
              const failed = bulkResults.filter((r) => r.status === "failed").length;
              return (
                <>
                  <div className="flex items-center gap-3">
                    {failed === 0
                      ? <CheckCircle2 size={24} className="text-green-500" />
                      : <AlertCircle size={24} className="text-amber-500" />}
                    <div>
                      <p className="text-base font-semibold text-gray-900">
                        {done} de {bulkResults.length} dispositivos concluídos
                      </p>
                      {failed > 0 && (
                        <p className="text-xs text-red-500">{failed} com falha</p>
                      )}
                    </div>
                  </div>

                  <div className="space-y-2">
                    {bulkResults.map((r, i) => (
                      <div key={i} className="flex items-center gap-3 px-3 py-2 border border-gray-100 rounded-lg">
                        {r.status === "done"
                          ? <CheckCircle2 size={13} className="text-green-500" />
                          : <XCircle size={13} className="text-red-400" />}
                        <span className="text-sm text-gray-800 flex-1">{r.deviceName}</span>
                        {r.operationId && (
                          <Link
                            to={`/operations?id=${r.operationId}`}
                            className="text-xs text-brand-600 hover:underline"
                          >
                            Ver operação
                          </Link>
                        )}
                      </div>
                    ))}
                  </div>

                  <button
                    onClick={resetAll}
                    className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700"
                  >
                    Nova operação
                  </button>
                </>
              );
            })()}
          </div>
        )}
      </div>
    </PageWrapper>
  );
}
