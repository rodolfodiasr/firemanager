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
        addMessage("assistant", "Operação executada com sucesso! Documentos sendo gerados...");
        toast.success("Operação concluída!");
      } else {
        addMessage("assistant", `Erro na execução: ${operation.error_message}`);
        toast.error("Falha na execução");
      }
      reset();
    } catch {
      toast.error("Erro ao executar operação");
    } finally {
      setLoading(false);
    }
  }, [currentOperationId, addMessage, setLoading, reset]);

  return { messages, readyToExecute, loading, send, execute, reset };
}
