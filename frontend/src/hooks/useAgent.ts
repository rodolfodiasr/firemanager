import { useCallback } from "react";
import toast from "react-hot-toast";
import { operationsApi } from "../api/operations";
import { useAgentStore } from "../store/agentStore";

export function useAgent(deviceId: string | null) {
  const {
    messages,
    currentOperationId,
    readyToExecute,
    loading,
    addMessage,
    setOperationId,
    setReadyToExecute,
    setLoading,
    resetSession,
    reset,
  } = useAgentStore();

  const send = useCallback(
    async (content: string) => {
      if (!deviceId) {
        toast.error("Selecione um dispositivo primeiro");
        return;
      }

      addMessage("user", content);
      setLoading(true);

      try {
        let response;
        if (!currentOperationId) {
          response = await operationsApi.startChat(deviceId, content);
          setOperationId(response.operation_id);
        } else {
          response = await operationsApi.continueChat(currentOperationId, content);
        }

        addMessage("assistant", response.agent_message);
        setReadyToExecute(response.ready_to_execute);
      } catch (err) {
        toast.error("Erro ao comunicar com o agente");
        addMessage("assistant", "Desculpe, ocorreu um erro. Tente novamente.");
      } finally {
        setLoading(false);
      }
    },
    [deviceId, currentOperationId, addMessage, setOperationId, setReadyToExecute, setLoading]
  );

  const execute = useCallback(async () => {
    if (!currentOperationId) return;
    setLoading(true);
    try {
      const operation = await operationsApi.execute(currentOperationId);
      if (operation.status === "completed") {
        const rules = operation.action_plan?.result as Array<{
          rule_id: string; name: string; src: string; dst: string;
          service: string; action: string; enabled: boolean;
        }> | undefined;

        if (rules && rules.length > 0) {
          const lines = rules.map(
            (r) => `• [${r.enabled ? "ON" : "OFF"}] **${r.name || r.rule_id}** — ${r.src} → ${r.dst} (${r.service}) [${r.action}]`
          );
          addMessage("assistant", `Encontrei ${rules.length} regra(s):\n\n${lines.join("\n")}`);
        } else if (rules && rules.length === 0) {
          addMessage("assistant", "Nenhuma regra encontrada.");
        } else {
          addMessage("assistant", "Operação executada com sucesso! Documentos sendo gerados...");
        }
        toast.success("Operação concluída!");
      } else {
        addMessage("assistant", `Erro na execução: ${operation.error_message}`);
        toast.error("Falha na execução");
      }
      // Keep messages visible — only reset the active operation context
      resetSession();
    } catch {
      toast.error("Erro ao executar operação");
    } finally {
      setLoading(false);
    }
  }, [currentOperationId, addMessage, setLoading, resetSession]);

  return { messages, readyToExecute, loading, send, execute, reset };
}
