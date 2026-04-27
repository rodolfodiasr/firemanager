import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { ChatWindow } from "../components/agent/ChatWindow";
import { useDevices } from "../hooks/useDevices";
import { useAgent } from "../hooks/useAgent";
import { operationsApi } from "../api/operations";

export function Agent() {
  const [searchParams] = useSearchParams();
  const editId = searchParams.get("edit");

  const { devices } = useDevices();
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);

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
    : undefined;

  return (
    <PageWrapper title={editOp ? "Editar Operação" : "Agente de IA"}>
      <div className="h-[calc(100vh-7rem)] flex gap-4">
        {/* Device selector panel */}
        <div className="w-64 bg-white rounded-xl border border-gray-200 p-4 flex flex-col gap-3">
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
    </PageWrapper>
  );
}
