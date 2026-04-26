import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight } from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { StatusBadge } from "../components/shared/StatusBadge";
import { EmptyState } from "../components/shared/EmptyState";
import { operationsApi } from "../api/operations";
import type { Operation } from "../types/operation";

interface PlanField {
  label: string;
  value: string;
}

function getPlanFields(op: Operation): PlanField[] {
  const ap = op.action_plan;
  if (!ap) return [];
  const fields: PlanField[] = [];

  if (ap.rule_spec) {
    const r = ap.rule_spec as Record<string, unknown>;
    fields.push(
      { label: "Regra", value: String(r.name ?? "") },
      { label: "Origem", value: `${r.src_address} (${r.src_zone})` },
      { label: "Destino", value: `${r.dst_address} (${r.dst_zone})` },
      { label: "Serviço", value: String(r.service ?? "") },
      { label: "Ação", value: String(r.action ?? "") },
    );
    if (r.comment) fields.push({ label: "Comentário", value: String(r.comment) });
  }

  if (ap.nat_spec) {
    const n = ap.nat_spec as Record<string, unknown>;
    fields.push(
      { label: "NAT", value: String(n.name ?? "") },
      { label: "Entrada → Saída", value: `${n.inbound_interface} → ${n.outbound_interface}` },
      { label: "Origem", value: `${n.source} → ${n.translated_source}` },
      { label: "Destino", value: `${n.destination} → ${n.translated_destination}` },
      { label: "Serviço", value: `${n.service} → ${n.translated_service}` },
    );
  }

  if (ap.route_spec) {
    const rt = ap.route_spec as Record<string, unknown>;
    fields.push(
      { label: "Rota", value: String(rt.name || "(sem nome)") },
      { label: "Interface", value: String(rt.interface ?? "") },
      { label: "Destino", value: String(rt.destination ?? "") },
      { label: "Gateway", value: String(rt.gateway ?? "") },
      { label: "Métrica", value: String(rt.metric ?? "") },
    );
  }

  if (ap.group_spec) {
    const g = ap.group_spec as Record<string, unknown>;
    const members = g.members as string[] | undefined;
    fields.push(
      { label: "Grupo", value: String(g.name ?? "") },
      { label: "Membros", value: members?.join(", ") ?? "" },
    );
  }

  if (ap.security_exclusion_spec) {
    const exc = ap.security_exclusion_spec as Record<string, unknown>;
    const ips = exc.ip_addresses as string[] | undefined;
    const svcs = exc.services as string[] | undefined;
    fields.push(
      { label: "IPs", value: ips?.join(", ") ?? "" },
      { label: "Serviços", value: svcs?.length ? svcs.join(", ") : "todos" },
      { label: "Zona", value: String(exc.zone ?? "LAN") },
    );
  }

  if (ap.security_service_spec) {
    const svc = ap.security_service_spec as Record<string, unknown>;
    fields.push(
      { label: "Serviço", value: String(svc.service ?? "") },
      { label: "Ação", value: svc.enabled ? "Ativar" : "Desativar" },
    );
  }

  if (ap.content_filter_spec) {
    const cf = ap.content_filter_spec as Record<string, unknown>;
    const cats = cf.blocked_categories as string[] | undefined;
    const zones = cf.zones as string[] | undefined;
    fields.push(
      { label: "Perfil CFS", value: String(cf.profile_name ?? "") },
      { label: "Política CFS", value: String(cf.policy_name || "(automático)") },
      { label: "Zonas", value: zones?.join(", ") ?? "" },
      { label: "Categorias bloqueadas", value: cats?.join(", ") || "(padrão)" },
    );
  }

  if (ap.app_rules_spec) {
    const ar = ap.app_rules_spec as Record<string, unknown>;
    fields.push(
      { label: "Política App Rules", value: String(ar.policy_name ?? "") },
      { label: "Ação", value: String(ar.action_object ?? "") },
      { label: "Zona", value: String(ar.zone ?? "") },
    );
  }

  return fields;
}

function getResultSummary(op: Operation): string | null {
  const result = op.action_plan?.result;
  if (!result) return null;
  if (!Array.isArray(result)) return null;
  const arr = result as Record<string, unknown>[];
  if (arr.length === 0) return "Nenhum resultado encontrado.";
  const intent = op.intent;
  if (intent === "list_rules") return `${arr.length} regra(s) encontrada(s)`;
  if (intent === "list_nat_policies") return `${arr.length} política(s) NAT encontrada(s)`;
  if (intent === "list_route_policies") return `${arr.length} rota(s) encontrada(s)`;
  if (intent === "get_security_status") return `${arr.length} serviço(s) verificado(s)`;
  if (intent === "add_security_exclusion") {
    const ok = arr.filter((r) => r.success).length;
    const fail = arr.length - ok;
    if (fail > 0) {
      const failedSvcs = arr.filter((r) => !r.success).map((r) => String(r.service)).join(", ");
      return `${ok} OK · ${fail} falha(s): ${failedSvcs}`;
    }
    const svcNames = arr.map((r) => String(r.service)).join(", ");
    return `${ok} serviço(s) configurado(s): ${svcNames}`;
  }
  return null;
}

function ExpandedRow({ op }: { op: Operation }) {
  const planFields = getPlanFields(op);
  const resultSummary = getResultSummary(op);

  return (
    <tr className="bg-gray-50 border-b border-gray-200">
      <td colSpan={5} className="px-6 py-4">
        <div className="space-y-4">
          {/* Full request */}
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
              Solicitação completa
            </p>
            <p className="text-sm text-gray-800 leading-relaxed">
              {op.natural_language_input}
            </p>
          </div>

          {/* Action plan fields */}
          {planFields.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                Plano de ação
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                {planFields.map((f) => (
                  <div
                    key={f.label}
                    className="bg-white border border-gray-200 rounded-lg px-3 py-2"
                  >
                    <p className="text-xs text-gray-400 mb-0.5">{f.label}</p>
                    <p
                      className="text-sm font-medium text-gray-800 truncate"
                      title={f.value}
                    >
                      {f.value || "—"}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Result summary */}
          {resultSummary && (
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
                Resultado
              </p>
              <p className="text-sm text-gray-700">{resultSummary}</p>
            </div>
          )}

          {/* Error message */}
          {op.error_message && (
            <div>
              <p className="text-xs font-semibold text-red-400 uppercase tracking-wide mb-1">
                Erro
              </p>
              <p className="text-sm text-red-600">{op.error_message}</p>
            </div>
          )}
        </div>
      </td>
    </tr>
  );
}

export function Operations() {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: operations = [], isLoading } = useQuery({
    queryKey: ["operations"],
    queryFn: operationsApi.list,
    refetchInterval: 5000,
  });

  const toggle = (id: string) => setExpandedId((prev) => (prev === id ? null : id));

  return (
    <PageWrapper title="Operações">
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">Histórico de Operações</h2>
        </div>

        {isLoading ? (
          <p className="text-sm text-gray-400 px-6 py-8">Carregando...</p>
        ) : operations.length === 0 ? (
          <EmptyState
            title="Nenhuma operação ainda"
            description="As operações executadas pelo agente aparecerão aqui."
          />
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
              <tr>
                <th className="w-8 px-3 py-3" />
                <th className="px-4 py-3 text-left">Solicitação</th>
                <th className="px-4 py-3 text-left whitespace-nowrap">Intenção</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left whitespace-nowrap">Data</th>
              </tr>
            </thead>
            <tbody>
              {operations.map((op) => (
                <Fragment key={op.id}>
                  <tr
                    className="border-t border-gray-100 hover:bg-gray-50 cursor-pointer"
                    onClick={() => toggle(op.id)}
                  >
                    <td className="px-3 py-3 text-gray-400">
                      {expandedId === op.id ? (
                        <ChevronDown size={15} />
                      ) : (
                        <ChevronRight size={15} />
                      )}
                    </td>
                    <td className="px-4 py-3 max-w-sm">
                      <p className="truncate text-gray-900">
                        {op.natural_language_input}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                      {op.intent ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={op.status} />
                    </td>
                    <td className="px-4 py-3 text-gray-400 whitespace-nowrap">
                      {new Date(op.created_at).toLocaleString("pt-BR")}
                    </td>
                  </tr>
                  {expandedId === op.id && <ExpandedRow op={op} />}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </PageWrapper>
  );
}
