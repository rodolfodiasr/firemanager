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
        const intent = operation.intent;
        const ap = operation.action_plan as Record<string, unknown> | null;
        const rawResult = ap?.result;
        const resultArr = Array.isArray(rawResult) ? (rawResult as Record<string, unknown>[]) : null;

        let tableData: TableData | undefined;
        let summary = "";

        if (intent === "list_rules" && resultArr !== null) {
          if (resultArr.length === 0) {
            summary = "Nenhuma regra encontrada.";
          } else {
            summary = `${resultArr.length} regra(s) encontrada(s):`;
            tableData = {
              columns: [
                { key: "enabled", label: "Status" },
                { key: "name", label: "Nome" },
                { key: "src", label: "Origem" },
                { key: "dst", label: "Destino" },
                { key: "service", label: "Serviço" },
                { key: "action", label: "Ação" },
              ],
              rows: resultArr,
            };
          }
        } else if (intent === "list_nat_policies" && resultArr !== null) {
          if (resultArr.length === 0) {
            summary = "Nenhuma política NAT encontrada.";
          } else {
            summary = `${resultArr.length} política(s) NAT encontrada(s):`;
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
              rows: resultArr,
            };
          }
        } else if (intent === "list_route_policies" && resultArr !== null) {
          if (resultArr.length === 0) {
            summary = "Nenhuma rota encontrada.";
          } else {
            summary = `${resultArr.length} rota(s) encontrada(s):`;
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
              rows: resultArr,
            };
          }
        } else if (intent === "get_security_status" && resultArr !== null) {
          summary = "Status dos serviços de segurança:";
          tableData = {
            columns: [
              { key: "service", label: "Serviço" },
              { key: "enabled", label: "Status" },
            ],
            rows: resultArr,
          };
        } else if (intent === "add_security_exclusion" && resultArr !== null && resultArr.length > 0) {
          const ips = resultArr[0]?.ips;
          const ipList = Array.isArray(ips) ? (ips as string[]).join(", ") : String(ips ?? "");
          summary = `IP(s) ${ipList} adicionado(s) às exclusões:`;
          tableData = {
            columns: [
              { key: "service", label: "Serviço" },
              { key: "object", label: "Objeto" },
              { key: "group", label: "Grupo" },
              { key: "success", label: "Status" },
            ],
            rows: resultArr.map((r) => {
              const rIps = r.ips as string[] | undefined;
              const objName = rIps?.map((ip) => "fm-excl-" + ip.replace(/\./g, "-")).join(", ") ?? "";
              return { ...r, object: objName };
            }),
          };
        } else if (intent === "create_rule" || intent === "edit_rule") {
          const ruleSpec = ap?.rule_spec as Record<string, unknown> | undefined;
          summary = intent === "create_rule" ? "Regra criada com sucesso:" : "Regra editada com sucesso:";
          if (ruleSpec) {
            tableData = {
              columns: [
                { key: "name", label: "Nome" },
                { key: "src_address", label: "Origem" },
                { key: "src_zone", label: "Zona Orig." },
                { key: "dst_address", label: "Destino" },
                { key: "dst_zone", label: "Zona Dest." },
                { key: "service", label: "Serviço" },
                { key: "action", label: "Ação" },
              ],
              rows: [ruleSpec],
            };
          }
        } else if (intent === "delete_rule") {
          summary = "Regra excluída com sucesso!";
        } else if (intent === "create_nat_policy") {
          const natSpec = ap?.nat_spec as Record<string, unknown> | undefined;
          summary = "Política NAT criada com sucesso:";
          if (natSpec) {
            tableData = {
              columns: [
                { key: "name", label: "Nome" },
                { key: "inbound_interface", label: "Entrada" },
                { key: "outbound_interface", label: "Saída" },
                { key: "source", label: "Origem" },
                { key: "translated_source", label: "Orig. Traduzida" },
                { key: "destination", label: "Destino" },
                { key: "translated_destination", label: "Dest. Traduzido" },
              ],
              rows: [natSpec],
            };
          }
        } else if (intent === "delete_nat_policy") {
          summary = "Política NAT excluída com sucesso!";
        } else if (intent === "create_route_policy") {
          const routeSpec = ap?.route_spec as Record<string, unknown> | undefined;
          summary = "Rota criada com sucesso:";
          if (routeSpec) {
            tableData = {
              columns: [
                { key: "name", label: "Nome" },
                { key: "interface", label: "Interface" },
                { key: "destination", label: "Destino" },
                { key: "gateway", label: "Gateway" },
                { key: "metric", label: "Métrica" },
              ],
              rows: [routeSpec],
            };
          }
        } else if (intent === "delete_route_policy") {
          summary = "Rota excluída com sucesso!";
        } else if (intent === "create_group") {
          const groupSpec = ap?.group_spec as Record<string, unknown> | undefined;
          summary = "Grupo de endereços criado com sucesso:";
          if (groupSpec) {
            const members = groupSpec.members as string[] | undefined;
            tableData = {
              columns: [
                { key: "name", label: "Grupo" },
                { key: "members", label: "Membros" },
              ],
              rows: [{ ...groupSpec, members: members?.join(", ") ?? "" }],
            };
          }
        } else if (intent && intent.startsWith("toggle_")) {
          const svcSpec = ap?.security_service_spec as Record<string, unknown> | undefined;
          const svcLabel = svcSpec?.service
            ? String(svcSpec.service)
            : intent.replace("toggle_", "").replace(/_/g, " ");
          summary = `Serviço ${svcSpec?.enabled ? "ativado" : "desativado"} com sucesso:`;
          tableData = {
            columns: [
              { key: "service", label: "Serviço" },
              { key: "enabled", label: "Status" },
            ],
            rows: [{ service: svcLabel, enabled: svcSpec?.enabled }],
          };
        } else if (intent === "configure_content_filter") {
          const cfSpec = ap?.content_filter_spec as Record<string, unknown> | undefined;
          summary = "Filtro de conteúdo configurado com sucesso:";
          if (cfSpec) {
            tableData = {
              columns: [
                { key: "profile_name", label: "Perfil CFS" },
                { key: "policy_name", label: "Política CFS" },
                { key: "zones", label: "Zonas" },
                { key: "blocked_categories", label: "Categorias Bloqueadas" },
              ],
              rows: [
                {
                  ...cfSpec,
                  zones: (cfSpec.zones as string[] | undefined)?.join(", ") ?? "",
                  blocked_categories:
                    (cfSpec.blocked_categories as string[] | undefined)?.join(", ") || "(padrão)",
                },
              ],
            };
          }
        } else if (intent === "configure_app_rules") {
          const arSpec = ap?.app_rules_spec as Record<string, unknown> | undefined;
          summary = "Política App Rules configurada com sucesso:";
          if (arSpec) {
            tableData = {
              columns: [
                { key: "policy_name", label: "Política" },
                { key: "action_object", label: "Ação" },
                { key: "zone", label: "Zona" },
              ],
              rows: [arSpec],
            };
          }
        } else {
          summary = "Operação executada com sucesso!";
        }

        addMessage("assistant", summary || "Operação executada com sucesso!", tableData);
        toast.success("Operação concluída!");
      } else {
        addMessage("assistant", `Erro na execução: ${operation.error_message}`);
        toast.error("Falha na execução");
      }
      // Keep messages visible — only reset the active operation context
      resetSession();
    } catch (err) {
      toast.error("Erro ao executar operação");
      resetSession();
    } finally {
      setLoading(false);
    }
  }, [currentOperationId, addMessage, setLoading, resetSession]);

  return { messages, readyToExecute, loading, send, execute, reset };
}
