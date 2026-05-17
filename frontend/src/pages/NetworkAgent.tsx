import { useState } from "react";
import { useSearchParams, useNavigate, useLocation } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Layers, Square, CheckSquare, AlertCircle, Loader2, Search, MessageSquare, Microscope, Sparkles } from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { ChatWindow } from "../components/agent/ChatWindow";
import { useDevices } from "../hooks/useDevices";
import { useAgent } from "../hooks/useAgent";
import { bulkJobsApi } from "../api/bulk_jobs";
import type { Device } from "../types/device";
import { InvestigationPanel } from "../components/investigation/InvestigationPanel";

const NETWORK_CATEGORIES = ["switch", "routing"] as const;

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
                <p className="text-xs text-gray-400">{device.vendor} · {device.category}</p>
              </div>
            </button>
          );
        })}
      </div>

      {/* Bulk input */}
      <div className="flex-1 bg-white rounded-xl border border-gray-200 flex flex-col p-5 gap-4">
        <div className="flex items-center gap-2">
          <Layers size={16} className="text-brand-500" />
          <p className="text-sm font-semibold text-gray-800">Operação em Lote — Agente de Redes</p>
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
                placeholder="Ex: Configurar VLAN 100 com nome 'Produção' em todas as portas de acesso"
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

export function NetworkAgent() {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const handoffState = location.state as { context?: string; suggested_query?: string } | null;
  const deviceParam = searchParams.get("device");

  const { devices: allDevices } = useDevices();
  const devices = allDevices.filter((d) =>
    NETWORK_CATEGORIES.includes(d.category as typeof NETWORK_CATEGORIES[number])
  );

  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(deviceParam ?? null);
  const [bulkMode, setBulkMode] = useState(false);
  const [mode, setMode] = useState<"operate" | "investigate">(handoffState?.context ? "investigate" : "operate");

  const { messages, readyToExecute, requiresApproval, loading, intent, send, execute, submitForReview, reset } =
    useAgent(selectedDeviceId, null, false);

  const selectedDevice = devices.find((d) => d.id === selectedDeviceId);
  const canBulk = devices.length >= 2;

  return (
    <PageWrapper title="Agente de Redes">
      {handoffState?.context && (
        <div className="mb-3 flex items-start gap-2 bg-brand-50 border border-brand-200 rounded-xl px-4 py-2.5">
          <Sparkles size={13} className="text-brand-500 shrink-0 mt-0.5" />
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold text-brand-700">Contexto importado do Assistente IA</p>
            <p className="text-xs text-brand-600 truncate">{handoffState.context.slice(0, 120)}…</p>
          </div>
        </div>
      )}
      <div className="h-[calc(100vh-7rem)] flex flex-col gap-3">
        {/* Mode switcher */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => { setMode("operate"); setBulkMode(false); }}
            className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors ${
              mode === "operate" && !bulkMode
                ? "bg-brand-50 border-brand-300 text-brand-700 font-medium"
                : "border-gray-200 text-gray-500 hover:border-gray-300"
            }`}
          >
            <MessageSquare size={12} />
            Operar
          </button>
          {canBulk && (
            <button
              onClick={() => { setMode("operate"); setBulkMode(true); }}
              className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                mode === "operate" && bulkMode
                  ? "bg-amber-50 border-amber-300 text-amber-700 font-medium"
                  : "border-gray-200 text-gray-500 hover:border-gray-300"
              }`}
            >
              <Layers size={12} />
              Lote
            </button>
          )}
          <button
            onClick={() => { setMode("investigate"); setBulkMode(false); }}
            className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors ${
              mode === "investigate"
                ? "bg-violet-50 border-violet-300 text-violet-700 font-medium"
                : "border-gray-200 text-gray-500 hover:border-gray-300"
            }`}
          >
            <Search size={12} />
            Investigar
          </button>
        </div>

        {mode === "operate" && bulkMode ? (
          <BulkPanel devices={devices} />
        ) : (
          <div className="flex-1 flex gap-4 min-h-0">
            {/* Device selector */}
            <div className="w-64 bg-white rounded-xl border border-gray-200 p-4 flex flex-col gap-3 overflow-y-auto">
              <h3 className="text-sm font-semibold text-gray-700">Dispositivo alvo</h3>
              {devices.length === 0 ? (
                <div className="text-xs text-gray-400 space-y-1">
                  <p>Nenhum switch ou roteador encontrado.</p>
                  <p className="text-gray-300">
                    Cadastre um device com categoria <strong>Switch</strong> ou <strong>Routing</strong>.
                  </p>
                </div>
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
                        {device.vendor} · {device.category}
                      </p>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Main area — Operate or Investigate */}
            {mode === "operate" ? (
              <div className="flex-1 bg-white rounded-xl border border-gray-200 flex flex-col overflow-hidden">
                {selectedDevice ? (
                  <div className="px-4 py-2.5 border-b border-gray-100 bg-gray-50 flex items-center gap-2 flex-wrap">
                    <span className="text-xs text-gray-500">Operando em:</span>
                    <span className="text-sm font-medium">{selectedDevice.name}</span>
                    <span className="text-xs text-gray-400">
                      ({selectedDevice.vendor} · {selectedDevice.category})
                    </span>
                  </div>
                ) : (
                  <div className="px-4 py-3 border-b border-gray-100 bg-yellow-50">
                    <p className="text-xs text-yellow-700">Selecione um switch ou roteador para iniciar</p>
                  </div>
                )}
                {intent === "diagnose" && (
                  <div className="mx-4 mt-3 flex items-start gap-2.5 bg-violet-50 border border-violet-200 rounded-xl p-3">
                    <Microscope size={15} className="text-violet-600 shrink-0 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold text-violet-800">Solicitação de diagnóstico detectada</p>
                      <p className="text-xs text-violet-700 mt-0.5">
                        Use a aba Investigar para diagnósticos iterativos com execução de comandos de leitura e análise por fase.
                      </p>
                    </div>
                    <button
                      onClick={() => { setMode("investigate"); reset(); }}
                      className="shrink-0 flex items-center gap-1.5 text-xs px-3 py-1.5 bg-violet-600 text-white rounded-lg hover:bg-violet-700 font-medium"
                    >
                      <Search size={11} />
                      Investigar
                    </button>
                  </div>
                )}
                <ChatWindow
                  messages={messages}
                  readyToExecute={readyToExecute}
                  requiresApproval={requiresApproval}
                  loading={loading}
                  onSend={send}
                  onExecute={execute}
                  onSubmitForReview={submitForReview}
                  onCancel={reset}
                />
              </div>
            ) : (
              <div className="flex-1 bg-white rounded-xl border border-gray-200 p-5 overflow-y-auto">
                <InvestigationPanel
                  agentType="network"
                  target={{ device_id: selectedDeviceId ?? undefined }}
                  targetLabel={selectedDevice?.name}
                  availableDevices={devices}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </PageWrapper>
  );
}
