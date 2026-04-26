import { useState } from "react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { ChatWindow } from "../components/agent/ChatWindow";
import { useDevices } from "../hooks/useDevices";
import { useAgent } from "../hooks/useAgent";

export function Agent() {
  const { devices } = useDevices();
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const { messages, readyToExecute, requiresApproval, loading, send, execute, submitForReview, reset } =
    useAgent(selectedDeviceId);

  const selectedDevice = devices.find((d) => d.id === selectedDeviceId);

  return (
    <PageWrapper title="Agente de IA">
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
          {selectedDevice ? (
            <div className="px-4 py-3 border-b border-gray-100 bg-gray-50 flex items-center gap-2">
              <span className="text-xs text-gray-500">Operando em:</span>
              <span className="text-sm font-medium">{selectedDevice.name}</span>
              <span className="text-xs text-gray-400">({selectedDevice.vendor})</span>
            </div>
          ) : (
            <div className="px-4 py-3 border-b border-gray-100 bg-yellow-50">
              <p className="text-xs text-yellow-700">Selecione um dispositivo para iniciar</p>
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
      </div>
    </PageWrapper>
  );
}
