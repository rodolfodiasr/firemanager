import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Pencil, Layers, Square, CheckSquare, AlertCircle, Loader2 } from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { ChatWindow } from "../components/agent/ChatWindow";
import { useDevices } from "../hooks/useDevices";
import { useAgent } from "../hooks/useAgent";
import { operationsApi } from "../api/operations";
import { bulkJobsApi } from "../api/bulk_jobs";
import type { Device } from "../types/device";

// ── Bulk panel ────────────────────────────────────────────────────────────────

function BulkPanel({ devices }: { devices: Device[] }) {
  const navigate = useNavigate();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [input, setInput] = useState("");

  const toggle = (id: string) =>
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const selectedDevices = devices.filter((d) => selectedIds.has(d.id));
  const uniqueVendors = [...new Set(selectedDevices.map((d) => d.vendor))];

  const createMut = useMutation({
    mutationFn: () =>
      bulkJobsApi.create({
        device_ids: selectedDevices.map((d) => d.id),
        natural_language_input: input,
      }),
    onSuccess: (job) => navigate(`/bulk-jobs/${job.id}`),
  });

  return (
    <div className="flex-1 flex gap-4 min-h-0">
      {/* Device checklist */}
      <div className="w-64 bg-white rounded-xl border border-gray-200 p-4 flex flex-col gap-2 overflow-y-auto">
        <div className="flex items-center justify-between mb-1">
          <p className="text-xs font-semibold text-gray-500 uppercase">Dispositivos</p>
          <button
            onClick={() =>
              setSelectedIds(
                selectedIds.size === devices.length
                  ? new Set()
                  : new Set(devices.map((d) => d.id))
              )
            }
            className="text-xs text-brand-600 hover:underline"
          >
            {selectedIds.size === devices.length ? "Desmarcar" : "Todos"}
          </button>
        </div>
        {devices.map((device) => {
          const checked = selectedIds.has(device.id);
          return (
            <button
              key={device.id}
              onClick={() => toggle(device.id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-start gap-2 transition-colors ${
                checked ? "bg-brand-50 border border-brand-300" : "hover:bg-gray-50 border border-transparent"
              }`}
            >
              {checked
                ? <CheckSquare size={14} className="text-brand-600 shrink-0 mt-0.5" />
                : <Square size={14} className="text-gray-300 shrink-0 mt-0.5" />}
              <div className="min-w-0">
                <p className="font-medium text-gray-800 truncate">{device.name}</p>
                <p className="text-xs text-gray-400">{device.vendor}</p>
              </div>
            </button>
          );
        })}
      </div>

      {/* Bulk input area */}
      <div className="flex-1 bg-white rounded-xl border border-gray-200 flex flex-col p-5 gap-4">
        <div className="flex items-center gap-2">
          <Layers size={16} className="text-brand-500" />
          <p className="text-sm font-semibold text-gray-800">Operação em Lote — Agente IA</p>
          {selectedIds.size >= 2 && (
            <span className="ml-auto text-xs bg-brand-100 text-brand-700 px-2 py-0.5 rounded-full font-medium">
              {selectedIds.size} selecionados
            </span>
          )}
        </div>

        {selectedIds.size < 2 ? (
          <p className="text-sm text-gray-400 mt-2">
            Selecione pelo menos 2 dispositivos na lista ao lado para criar uma operação em lote.
          </p>
        ) : (
          <>
            {uniqueVendors.length > 1 && (
              <div className="flex items-start gap-1.5 text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs">
                <AlertCircle size={13} className="mt-0.5 shrink-0" />
                <span>
                  Vendors diferentes selecionados ({uniqueVendors.join(", ")}). A IA gerará o plano
                  com base no primeiro dispositivo.
                </span>
              </div>
            )}

            <div className="flex-1 flex flex-col gap-2">
              <label className="text-sm font-medium text-gray-700">
                O que deseja fazer em todos estes dispositivos?
              </label>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                rows={6}
                placeholder="Ex: Liberar acesso HTTPS para o IP 192.168.1.50 vindo da rede interna"
                className="flex-1 border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
              />
              <p className="text-xs text-gray-400">
                A IA processa o primeiro dispositivo e replica o plano para os demais.
              </p>
            </div>

            {createMut.isError && (
              <p className="text-red-600 text-xs">
                {(createMut.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
                  ?? "Erro ao criar o job."}
              </p>
            )}

            <button
              onClick={() => createMut.mutate()}
              disabled={!input.trim() || createMut.isPending}
              className="self-end flex items-center gap-2 px-5 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50"
            >
              {createMut.isPending && <Loader2 size={14} className="animate-spin" />}
              {createMut.isPending ? "Processando IA..." : `Aplicar em ${selectedIds.size} dispositivos`}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function Agent() {
  const [searchParams] = useSearchParams();
  const editId = searchParams.get("edit");
  const deviceParam = searchParams.get("device");
  const seedParam = searchParams.get("seed");

  const { devices } = useDevices();
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(deviceParam ?? null);
  const [bulkMode, setBulkMode] = useState(false);

  const { data: editOp } = useQuery({
    queryKey: ["operation", editId],
    queryFn: () => operationsApi.get(editId!),
    enabled: !!editId,
    staleTime: Infinity,
  });

  const { messages, readyToExecute, requiresApproval, loading, send, execute, submitForReview, reset } =
    useAgent(selectedDeviceId, editOp?.id ?? null);

  useEffect(() => {
    if (!editOp) return;
    setSelectedDeviceId(editOp.device_id);
    reset();
  }, [editOp?.id]);

  const selectedDevice = devices.find((d) => d.id === selectedDeviceId);

  const editSeedInput = editOp
    ? `${editOp.natural_language_input} — Quero ajustar: `
    : seedParam
    ? decodeURIComponent(seedParam)
    : undefined;

  const canBulk = !editOp && devices.length >= 2;

  return (
    <PageWrapper title={editOp ? "Editar Operação" : "Agente de IA"}>
      <div className="h-[calc(100vh-7rem)] flex flex-col gap-3">
        {/* Mode toggle */}
        {canBulk && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => setBulkMode(false)}
              className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                !bulkMode
                  ? "bg-brand-50 border-brand-300 text-brand-700 font-medium"
                  : "border-gray-200 text-gray-500 hover:border-gray-300"
              }`}
            >
              Dispositivo único
            </button>
            <button
              onClick={() => setBulkMode(true)}
              className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                bulkMode
                  ? "bg-amber-50 border-amber-300 text-amber-700 font-medium"
                  : "border-gray-200 text-gray-500 hover:border-gray-300"
              }`}
            >
              <Layers size={12} />
              Operação em lote
            </button>
          </div>
        )}

        {bulkMode ? (
          <BulkPanel devices={devices} />
        ) : (
          <div className="flex-1 flex gap-4 min-h-0">
            {/* Device selector panel */}
            <div className="w-64 bg-white rounded-xl border border-gray-200 p-4 flex flex-col gap-3 overflow-y-auto">
              <h3 className="text-sm font-semibold text-gray-700">Dispositivo alvo</h3>
              {devices.length === 0 ? (
                <p className="text-xs text-gray-400">Nenhum dispositivo cadastrado</p>
              ) : (
                <div className="space-y-2">
                  {devices.map((device) => (
                    <button
                      key={device.id}
                      onClick={() => {
                        setSelectedDeviceId(device.id);
                        reset();
                      }}
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                        selectedDeviceId === device.id
                          ? "bg-brand-600 text-white"
                          : "hover:bg-gray-50 text-gray-700"
                      }`}
                    >
                      <p className="font-medium">{device.name}</p>
                      <p className={`text-xs ${selectedDeviceId === device.id ? "text-red-200" : "text-gray-400"}`}>
                        {device.vendor} · {device.status}
                      </p>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Chat area */}
            <div className="flex-1 bg-white rounded-xl border border-gray-200 flex flex-col overflow-hidden">
              {editOp && (
                <div className="px-4 py-2.5 border-b border-amber-200 bg-amber-50 flex items-start gap-2">
                  <Pencil size={14} className="text-amber-600 shrink-0 mt-0.5" />
                  <p className="text-xs text-amber-800">
                    <span className="font-semibold">Editando operação:</span>{" "}
                    {editOp.natural_language_input}
                  </p>
                </div>
              )}
              {!editOp && selectedDevice ? (
                <div className="px-4 py-3 border-b border-gray-100 bg-gray-50 flex items-center gap-2">
                  <span className="text-xs text-gray-500">Operando em:</span>
                  <span className="text-sm font-medium">{selectedDevice.name}</span>
                  <span className="text-xs text-gray-400">({selectedDevice.vendor})</span>
                </div>
              ) : !editOp ? (
                <div className="px-4 py-3 border-b border-gray-100 bg-yellow-50">
                  <p className="text-xs text-yellow-700">Selecione um dispositivo para iniciar</p>
                </div>
              ) : null}
              <ChatWindow
                messages={messages}
                readyToExecute={readyToExecute}
                requiresApproval={requiresApproval}
                loading={loading}
                onSend={send}
                onExecute={execute}
                onSubmitForReview={submitForReview}
                onCancel={reset}
                defaultInput={editSeedInput}
              />
            </div>
          </div>
        )}
      </div>
    </PageWrapper>
  );
}
