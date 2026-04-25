import { useCallback } from "react";
import toast from "react-hot-toast";
import { operationsApi } from "../api/operations";
import { useAgentStore, type TableData } from "../store/agentStore";

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
        const result = operation.action_plan?.result as Record<string, unknown>[] | undefined;
        const intent = operation.intent;

        if (result && result.length > 0) {
          let tableData: TableData | undefined;
          let summary = "";

          if (intent === "list_rules") {
            summary = `${result.length} regra(s) encontrada(s):`;
            tableData = {
              columns: [
                { key: "enabled", label: "Status" },
                { key: "name", label: "Nome" },
                { key: "src", label: "Origem" },
                { key: "dst", label: "Destino" },
                { key: "service", label: "Serviço" },
                { key: "action", label: "Ação" },
              ],
              rows: result,
            };
          } else if (intent === "list_nat_policies") {
            summary = `${result.length} política(s) NAT encontrada(s):`;
            tableData = {
              columns: [
                { key: "name", label: "Nome" },
                { key: "inbound", label: "Entrada" },
                { key: "outbound", label: "Saída" },
                { key: "source", label: "Origem" },
                { key: "translated_source", label: "Orig. Traduzida" },
                { key: "destination", label: "Destino" },
                { key: "translated_destination", label: "Dest. Traduzido" },
                { key: "service", label: "Serviço" },
              ],
              rows: result,
            };
          } else if (intent === "list_route_policies") {
            summary = `${result.length} rota(s) encontrada(s):`;
            tableData = {
              columns: [
                { key: "interface", label: "Interface" },
                { key: "destination", label: "Destino" },
                { key: "source", label: "Origem" },
                { key: "gateway", label: "Gateway" },
                { key: "metric", label: "Métrica" },
                { key: "route_type", label: "Tipo" },
                { key: "enabled", label: "Status" },
              ],
              rows: result,
            };
          } else if (intent === "get_security_status") {
            summary = "Status dos serviços de segurança:";
            tableData = {
              columns: [
                { key: "service", label: "Serviço" },
                { key: "enabled", label: "Status" },
              ],
              rows: result,
            };
          } else if (intent === "add_security_exclusion") {
            const ips = (result[0] as Record<string, unknown>)?.ips;
            const ipList = Array.isArray(ips) ? (ips as string[]).join(", ") : String(ips ?? "");
            summary = `IP(s) ${ipList} adicionado(s) às exclusões:`;
            tableData = {
              columns: [
                { key: "service", label: "Serviço" },
                { key: "group", label: "Grupo" },
                { key: "success", label: "Status" },
              ],
              rows: result.map((r) => ({
                ...r,
                success: (r as Record<string, unknown>).success,
              })),
            };
          } else {
            summary = "Operação executada com sucesso!";
          }

          addMessage("assistant", summary, tableData);
        } else if (result && result.length === 0) {
          addMessage("assistant", "Nenhum resultado encontrado.");
        } else {
          addMessage("assistant", "Operação executada com sucesso!");
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
