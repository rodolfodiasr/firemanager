import { Fragment, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronRight,
  BookOpen,
  X,
  Loader2,
  Pencil,
  Radio,
  Layers,
  Clock,
  Play,
  Trash2,
  ArrowLeft,
  Shield,
  Route,
  Network,
} from "lucide-react";
import toast from "react-hot-toast";
import { PageWrapper } from "../components/layout/PageWrapper";
import { StatusBadge } from "../components/shared/StatusBadge";
import { EmptyState } from "../components/shared/EmptyState";
import { auditApi } from "../api/audit";
import { operationsApi } from "../api/operations";
import { bulkJobsApi } from "../api/bulk_jobs";
import { serverOpsApi } from "../api/server_operations";
import { AUDIT_INTENTS } from "../types/audit";
import type { ServerOperation } from "../types/server_operation";
import type { Operation } from "../types/operation";
import type { BulkJob, BulkJobDetail, BulkJobStatus, CategoryPlanSummary } from "../types/bulk_job";

type Tab = "live" | "pending" | "direct" | "history" | "lote" | "logs";

const intentLabel = (key: string) => AUDIT_INTENTS.find((i) => i.key === key)?.label ?? key;
const fmtDate = (s: string | null) => (s ? new Date(s).toLocaleString("pt-BR") : "—");

// ── Ao Vivo Tab (from Operations) ─────────────────────────────────────────────

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
  if (!result || !Array.isArray(result)) return null;
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
    return `${ok} serviço(s) configurado(s): ${arr.map((r) => String(r.service)).join(", ")}`;
  }
  return null;
}

function LiveExpandedRow({ op }: { op: Operation }) {
  const planFields = getPlanFields(op);
  const resultSummary = getResultSummary(op);

  return (
    <tr className="bg-gray-50 border-b border-gray-200">
      <td colSpan={5} className="px-6 py-4">
        <div className="space-y-4">
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
              Solicitação completa
            </p>
            <p className="text-sm text-gray-800 leading-relaxed">{op.natural_language_input}</p>
          </div>

          {planFields.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                Plano de ação
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                {planFields.map((f) => (
                  <div key={f.label} className="bg-white border border-gray-200 rounded-lg px-3 py-2">
                    <p className="text-xs text-gray-400 mb-0.5">{f.label}</p>
                    <p className="text-sm font-medium text-gray-800 truncate" title={f.value}>
                      {f.value || "—"}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {resultSummary && (
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
                Resultado
              </p>
              <p className="text-sm text-gray-700">{resultSummary}</p>
            </div>
          )}

          {op.error_message && (
            <div>
              <p className="text-xs font-semibold text-red-400 uppercase tracking-wide mb-1">Erro</p>
              <p className="text-sm text-red-600">{op.error_message}</p>
            </div>
          )}
        </div>
      </td>
    </tr>
  );
}

function LiveTab() {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: operations = [], isLoading } = useQuery({
    queryKey: ["operations"],
    queryFn: operationsApi.list,
    refetchInterval: 5000,
  });

  const toggle = (id: string) => setExpandedId((prev) => (prev === id ? null : id));

  if (isLoading) return <div className="py-10 text-center text-gray-400">Carregando...</div>;
  if (operations.length === 0)
    return (
      <EmptyState
        title="Nenhuma operação ainda"
        description="As operações executadas pelo agente aparecerão aqui."
      />
    );

  return (
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
                {expandedId === op.id ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
              </td>
              <td className="px-4 py-3 max-w-sm">
                <p className="truncate text-gray-900">{op.natural_language_input}</p>
              </td>
              <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{op.intent ?? "—"}</td>
              <td className="px-4 py-3">
                <StatusBadge status={op.status} />
              </td>
              <td className="px-4 py-3 text-gray-400 whitespace-nowrap">
                {new Date(op.created_at).toLocaleString("pt-BR")}
              </td>
            </tr>
            {expandedId === op.id && <LiveExpandedRow op={op} />}
          </Fragment>
        ))}
      </tbody>
    </table>
  );
}

// ── Server Pending section ────────────────────────────────────────────────────
function ServerPendingSection() {
  const qc = useQueryClient();
  const { data: srvOps = [], isLoading } = useQuery({
    queryKey: ["server-ops-pending"],
    queryFn: serverOpsApi.getPending,
    refetchInterval: 30000,
  });
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [comment, setComment] = useState("");

  const reviewMut = useMutation({
    mutationFn: ({ id, approved, comment }: { id: string; approved: boolean; comment: string }) =>
      serverOpsApi.review(id, { approved, comment }),
    onSuccess: (_data, vars) => {
      toast.success(vars.approved ? "Operação aprovada e executada!" : "Operação rejeitada.");
      setExpandedId(null);
      setComment("");
      qc.invalidateQueries({ queryKey: ["server-ops-pending"] });
      qc.invalidateQueries({ queryKey: ["audit-pending-count"] });
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg ?? "Erro ao processar revisão.");
    },
  });

  if (isLoading || srvOps.length === 0) return null;

  return (
    <div className="border-t border-gray-200 pt-2">
      <p className="px-4 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wider bg-gray-50">
        Servidores — {srvOps.length} pendente(s)
      </p>
      <div className="divide-y divide-gray-100">
        {srvOps.map((op: ServerOperation) => (
          <Fragment key={op.id}>
            <button
              className="w-full text-left px-4 py-3 hover:bg-gray-50 flex items-start gap-3"
              onClick={() => { setExpandedId(expandedId === op.id ? null : op.id); setComment(""); }}
            >
              <span className="mt-1 shrink-0 text-gray-400">
                {expandedId === op.id ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              </span>
              <div className="flex-1 grid grid-cols-4 gap-4 items-center min-w-0">
                <div>
                  <p className="text-sm font-medium text-gray-900 truncate">{op.requester_name ?? "—"}</p>
                  <p className="text-xs text-gray-400 truncate">{op.requester_email}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-700 truncate">{op.server_name ?? "—"}</p>
                  <p className="text-xs text-gray-400">{op.server_host}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-700">{op.commands.length} comando(s)</p>
                  <p className="text-xs text-gray-400 truncate">{op.description}</p>
                </div>
                <div className="text-right">
                  <span className="inline-block text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full font-medium">Em revisão</span>
                  <p className="text-xs text-gray-400 mt-0.5">{new Date(op.created_at).toLocaleString("pt-BR")}</p>
                </div>
              </div>
            </button>

            {expandedId === op.id && (
              <div className="px-6 pb-5 bg-gray-50 border-t border-gray-100">
                <div className="pt-4 space-y-4 max-w-3xl">
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Descrição</p>
                    <p className="text-sm text-gray-800 bg-white border border-gray-200 rounded-lg p-3">{op.description}</p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                      Comandos ({op.commands.length})
                    </p>
                    <pre className="text-xs text-gray-700 bg-gray-900 text-green-300 rounded-lg p-3 overflow-auto max-h-48 whitespace-pre-wrap font-mono">
                      {op.commands.join("\n")}
                    </pre>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Parecer do Revisor</p>
                    <textarea
                      value={comment}
                      onChange={(e) => setComment(e.target.value)}
                      placeholder="Comentário de revisão (obrigatório para rejeição)"
                      rows={3}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                    />
                  </div>
                  <div className="flex gap-3">
                    <button
                      onClick={() => reviewMut.mutate({ id: op.id, approved: true, comment })}
                      disabled={reviewMut.isPending}
                      className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-50"
                    >
                      <CheckCircle2 size={15} /> Aprovar e Executar
                    </button>
                    <button
                      onClick={() => {
                        if (!comment.trim()) { toast.error("Informe o motivo da rejeição."); return; }
                        reviewMut.mutate({ id: op.id, approved: false, comment });
                      }}
                      disabled={reviewMut.isPending}
                      className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 disabled:opacity-50"
                    >
                      <XCircle size={15} /> Rejeitar
                    </button>
                  </div>
                </div>
              </div>
            )}
          </Fragment>
        ))}
      </div>
    </div>
  );
}

// ── Pending Tab ───────────────────────────────────────────────────────────────
function PendingTab() {
  const qc = useQueryClient();
  const { data: ops = [], isLoading } = useQuery({
    queryKey: ["audit-pending"],
    queryFn: auditApi.getPending,
    refetchInterval: 30000,
  });
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [comment, setComment] = useState("");

  const reviewMutation = useMutation({
    mutationFn: ({ id, approved, comment }: { id: string; approved: boolean; comment: string }) =>
      auditApi.review(id, { approved, comment }),
    onSuccess: (_data, vars) => {
      toast.success(vars.approved ? "Operação aprovada e executada!" : "Operação rejeitada.");
      setExpandedId(null);
      setComment("");
      qc.invalidateQueries({ queryKey: ["audit-pending"] });
      qc.invalidateQueries({ queryKey: ["audit-pending-count"] });
      qc.invalidateQueries({ queryKey: ["audit-history"] });
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg ?? "Erro ao processar revisão.");
    },
  });

  if (isLoading) return <div className="py-10 text-center text-gray-400">Carregando...</div>;

  if (ops.length === 0)
    return (
      <div>
        <div className="py-14 text-center text-gray-400">
          <CheckCircle2 size={40} className="mx-auto mb-3 text-green-300" />
          <p className="text-sm">Nenhuma operação de firewall aguardando revisão.</p>
        </div>
        <ServerPendingSection />
      </div>
    );

  return (
    <div>
    <div className="divide-y divide-gray-100">
      {ops.map((op) => (
        <Fragment key={op.id}>
          <button
            className="w-full text-left px-4 py-3 hover:bg-gray-50 flex items-start gap-3"
            onClick={() => {
              setExpandedId(expandedId === op.id ? null : op.id);
              setComment("");
            }}
          >
            <span className="mt-1 shrink-0 text-gray-400">
              {expandedId === op.id ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
            </span>
            <div className="flex-1 grid grid-cols-4 gap-4 items-center min-w-0">
              <div>
                <p className="text-sm font-medium text-gray-900 truncate">{op.requester_name ?? "—"}</p>
                <p className="text-xs text-gray-400 truncate">{op.requester_email}</p>
              </div>
              <div>
                <p className="text-sm text-gray-700 truncate">{op.device_name ?? "—"}</p>
                <p className="text-xs text-gray-400">{op.device_vendor}</p>
              </div>
              <div>
                <p className="text-sm text-gray-700">{op.intent ? intentLabel(op.intent) : "—"}</p>
              </div>
              <div className="text-right space-y-1">
                <StatusBadge status={op.status} />
                <p className="text-xs text-gray-400">{fmtDate(op.created_at)}</p>
              </div>
            </div>
          </button>

          {expandedId === op.id && (
            <div className="px-6 pb-5 bg-gray-50 border-t border-gray-100">
              <div className="pt-4 space-y-4 max-w-3xl">
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                    Solicitação Original
                  </p>
                  <p className="text-sm text-gray-800 bg-white border border-gray-200 rounded-lg p-3">
                    {op.natural_language_input}
                  </p>
                </div>

                {op.action_plan && (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                      Plano de Ação
                    </p>
                    <pre className="text-xs text-gray-700 bg-white border border-gray-200 rounded-lg p-3 overflow-auto max-h-48 whitespace-pre-wrap">
                      {JSON.stringify(
                        Object.fromEntries(
                          Object.entries(op.action_plan).filter(([k]) => k !== "result")
                        ),
                        null,
                        2
                      )}
                    </pre>
                  </div>
                )}

                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                    Parecer do Revisor
                  </p>
                  <textarea
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="Comentário de revisão (obrigatório para rejeição)"
                    rows={3}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                  />
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={() => reviewMutation.mutate({ id: op.id, approved: true, comment })}
                    disabled={reviewMutation.isPending}
                    className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-50"
                  >
                    <CheckCircle2 size={15} />
                    Aprovar e Executar
                  </button>
                  <button
                    onClick={() => {
                      if (!comment.trim()) {
                        toast.error("Informe o motivo da rejeição.");
                        return;
                      }
                      reviewMutation.mutate({ id: op.id, approved: false, comment });
                    }}
                    disabled={reviewMutation.isPending}
                    className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 disabled:opacity-50"
                  >
                    <XCircle size={15} />
                    Rejeitar
                  </button>
                </div>
              </div>
            </div>
          )}
        </Fragment>
      ))}
    </div>
    <ServerPendingSection />
    </div>
  );
}

// ── Direct Tab ────────────────────────────────────────────────────────────────
function DirectTab() {
  const { data: ops = [], isLoading } = useQuery({
    queryKey: ["audit-direct"],
    queryFn: auditApi.getDirect,
  });

  if (isLoading) return <div className="py-10 text-center text-gray-400">Carregando...</div>;
  if (ops.length === 0)
    return <div className="py-10 text-center text-gray-400 text-sm">Nenhuma operação registrada.</div>;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100">
            {["Solicitante", "Dispositivo", "Intenção", "Status", "Data"].map((h) => (
              <th
                key={h}
                className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {ops.map((op) => (
            <tr key={op.id} className="hover:bg-gray-50">
              <td className="px-4 py-3">
                <p className="font-medium text-gray-900">{op.requester_name ?? "—"}</p>
                <p className="text-xs text-gray-400">{op.requester_email}</p>
              </td>
              <td className="px-4 py-3 text-gray-700">{op.device_name ?? "—"}</td>
              <td className="px-4 py-3 text-gray-700">{op.intent ? intentLabel(op.intent) : "—"}</td>
              <td className="px-4 py-3">
                <StatusBadge status={op.status} />
              </td>
              <td className="px-4 py-3 text-xs text-gray-400">{fmtDate(op.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Markdown renderer ─────────────────────────────────────────────────────────
function inlineRender(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**"))
      return <strong key={i} className="font-semibold text-gray-900">{part.slice(2, -2)}</strong>;
    if (part.startsWith("*") && part.endsWith("*"))
      return <em key={i}>{part.slice(1, -1)}</em>;
    if (part.startsWith("`") && part.endsWith("`"))
      return <code key={i} className="bg-gray-100 px-1 rounded text-xs font-mono text-gray-800">{part.slice(1, -1)}</code>;
    return <span key={i}>{part}</span>;
  });
}

function renderMarkdown(text: string): React.ReactNode[] {
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];
  let i = 0;
  let listItems: string[] = [];
  let listType: "ul" | "ol" | null = null;

  const flushList = (key: number) => {
    if (!listItems.length) return;
    const Tag = listType === "ul" ? "ul" : "ol";
    const cls = listType === "ul" ? "list-disc" : "list-decimal";
    elements.push(
      <Tag key={`list-${key}`} className={`${cls} ml-5 space-y-0.5 my-2`}>
        {listItems.map((item, idx) => (
          <li key={idx} className="text-sm text-gray-700">{inlineRender(item)}</li>
        ))}
      </Tag>
    );
    listItems = [];
    listType = null;
  };

  while (i < lines.length) {
    const line = lines[i];

    if (line.startsWith("```")) {
      flushList(i);
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) { code.push(lines[i]); i++; }
      elements.push(
        <pre key={i} className="bg-gray-900 text-green-300 rounded-lg p-3 text-xs overflow-auto my-2 whitespace-pre-wrap">
          {code.join("\n")}
        </pre>
      );
    } else if (line.startsWith("### ")) {
      flushList(i);
      elements.push(<h3 key={i} className="text-sm font-bold text-gray-900 mt-4 mb-1">{inlineRender(line.slice(4))}</h3>);
    } else if (line.startsWith("## ")) {
      flushList(i);
      elements.push(<h2 key={i} className="text-base font-bold text-gray-800 mt-5 mb-2 border-b border-gray-200 pb-1">{inlineRender(line.slice(3))}</h2>);
    } else if (line.startsWith("# ")) {
      flushList(i);
      elements.push(<h1 key={i} className="text-lg font-bold text-gray-900 mt-4 mb-2">{inlineRender(line.slice(2))}</h1>);
    } else if (line.startsWith("> ")) {
      flushList(i);
      elements.push(
        <div key={i} className="bg-blue-50 border-l-4 border-blue-400 px-3 py-2 rounded text-sm text-blue-800 my-2">
          {inlineRender(line.slice(2))}
        </div>
      );
    } else if (line.match(/^[-*] /)) {
      if (listType !== "ul") { flushList(i); listType = "ul"; }
      listItems.push(line.slice(2));
    } else if (line.match(/^\d+\. /)) {
      if (listType !== "ol") { flushList(i); listType = "ol"; }
      listItems.push(line.replace(/^\d+\. /, ""));
    } else if (line.trim() === "") {
      flushList(i);
      elements.push(<div key={i} className="h-1" />);
    } else {
      flushList(i);
      elements.push(<p key={i} className="text-sm text-gray-700 leading-relaxed">{inlineRender(line)}</p>);
    }
    i++;
  }
  flushList(i);
  return elements;
}

// ── Tutorial Drawer ───────────────────────────────────────────────────────────
function TutorialDrawer({ operationId, onClose }: { operationId: string; onClose: () => void }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["tutorial", operationId],
    queryFn: () => operationsApi.getTutorial(operationId),
    staleTime: Infinity,
  });

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-white shadow-2xl flex flex-col h-full overflow-hidden animate-slide-in-right">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 shrink-0">
          <div className="flex items-center gap-2">
            <BookOpen size={18} className="text-brand-600" />
            <h2 className="text-base font-semibold text-gray-900">Tutorial Manual</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {isLoading && (
            <div className="flex flex-col items-center justify-center h-48 gap-3 text-gray-400">
              <Loader2 size={28} className="animate-spin" />
              <p className="text-sm">Gerando tutorial com IA...</p>
            </div>
          )}
          {isError && (
            <p className="text-sm text-red-500 text-center py-10">Erro ao gerar o tutorial. Tente novamente.</p>
          )}
          {data?.tutorial && (
            <div className="prose-sm max-w-none">{renderMarkdown(data.tutorial)}</div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── History Tab ───────────────────────────────────────────────────────────────
function HistoryTab() {
  const navigate = useNavigate();
  const { data: ops = [], isLoading } = useQuery({
    queryKey: ["audit-history"],
    queryFn: auditApi.getHistory,
  });
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [tutorialOpId, setTutorialOpId] = useState<string | null>(null);

  function editRoute(op: typeof ops[number]): string {
    const ap = op.action_plan as Record<string, unknown> | null;
    if (op.intent === "direct_ssh") {
      if (ap?.template_slug) return `/devices?edit=${op.id}`;
      return `/direct-mode?edit=${op.id}`;
    }
    return `/agent?edit=${op.id}`;
  }

  if (isLoading) return <div className="py-10 text-center text-gray-400">Carregando...</div>;
  if (ops.length === 0)
    return <div className="py-10 text-center text-gray-400 text-sm">Nenhuma operação no histórico.</div>;

  return (
    <>
      {tutorialOpId && (
        <TutorialDrawer operationId={tutorialOpId} onClose={() => setTutorialOpId(null)} />
      )}
      <div className="divide-y divide-gray-100">
        {ops.map((op) => (
          <Fragment key={op.id}>
            <button
              className="w-full text-left px-4 py-3 hover:bg-gray-50 flex items-start gap-3"
              onClick={() => setExpandedId(expandedId === op.id ? null : op.id)}
            >
              <span className="mt-1 shrink-0 text-gray-400">
                {expandedId === op.id ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              </span>
              <div className="flex-1 grid grid-cols-5 gap-4 items-center min-w-0">
                <div>
                  <p className="text-sm font-medium text-gray-900 truncate">{op.requester_name ?? "—"}</p>
                  <p className="text-xs text-gray-400 truncate">{op.requester_email}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-700 truncate">{op.device_name ?? "—"}</p>
                  <p className="text-xs text-gray-400">{op.device_vendor}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-700">{op.intent ? intentLabel(op.intent) : "—"}</p>
                  <p className="text-xs text-gray-400">{op.reviewer_name ? `Revisor: ${op.reviewer_name}` : ""}</p>
                </div>
                <div>
                  <StatusBadge status={op.status} />
                </div>
                <div className="text-right">
                  <p className="text-xs text-gray-400">{fmtDate(op.reviewed_at ?? op.created_at)}</p>
                </div>
              </div>
            </button>

            {expandedId === op.id && (
              <div className="px-6 pb-5 bg-gray-50 border-t border-gray-100">
                <div className="pt-4 space-y-4 max-w-3xl">
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                      Solicitação Original
                    </p>
                    <p className="text-sm text-gray-800 bg-white border border-gray-200 rounded-lg p-3">
                      {op.natural_language_input}
                    </p>
                  </div>

                  {op.action_plan && (
                    <div>
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                        Plano de Ação
                      </p>
                      <pre className="text-xs text-gray-700 bg-white border border-gray-200 rounded-lg p-3 overflow-auto max-h-64 whitespace-pre-wrap">
                        {JSON.stringify(
                          Object.fromEntries(
                            Object.entries(op.action_plan).filter(([k]) => k !== "result")
                          ),
                          null,
                          2
                        )}
                      </pre>
                    </div>
                  )}

                  {(() => {
                    const result = op.action_plan?.result as Record<string, unknown> | undefined;
                    const sshOutput = result?.output as string | undefined;
                    const sshCmds = result?.commands as string[] | undefined;
                    if (!sshOutput && !sshCmds) return null;
                    return (
                      <div>
                        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                          Output SSH do Dispositivo
                        </p>
                        {sshCmds && sshCmds.length > 0 && (
                          <p className="text-xs text-gray-500 mb-1">
                            Comandos enviados:{" "}
                            <code className="bg-gray-100 px-1 rounded">{sshCmds.join(" → ")}</code>
                          </p>
                        )}
                        <pre className={`text-xs rounded-lg p-3 overflow-auto max-h-64 whitespace-pre-wrap border ${
                          op.status === "failed"
                            ? "bg-red-50 border-red-200 text-red-800"
                            : "bg-gray-900 border-gray-700 text-green-300"
                        }`}>
                          {sshOutput ?? "(sem output)"}
                        </pre>
                      </div>
                    );
                  })()}

                  {op.review_comment && (
                    <div>
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                        Parecer do Revisor
                        {op.reviewer_name && (
                          <span className="ml-2 font-normal normal-case text-gray-400">
                            — {op.reviewer_name} em {fmtDate(op.reviewed_at)}
                          </span>
                        )}
                      </p>
                      <p className="text-sm text-gray-800 bg-white border border-gray-200 rounded-lg p-3">
                        {op.review_comment}
                      </p>
                    </div>
                  )}

                  <div className="pt-1 flex flex-wrap gap-2">
                    {op.status === "completed" && (
                      <button
                        onClick={(e) => { e.stopPropagation(); setTutorialOpId(op.id); }}
                        className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-brand-600 border border-brand-300 rounded-lg hover:bg-brand-50 transition-colors"
                      >
                        <BookOpen size={15} />
                        Ver como fazer manualmente
                      </button>
                    )}
                    <button
                      onClick={(e) => { e.stopPropagation(); navigate(editRoute(op)); }}
                      className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      <Pencil size={15} />
                      Editar / Repetir
                    </button>
                  </div>
                </div>
              </div>
            )}
          </Fragment>
        ))}
      </div>
    </>
  );
}

// ── Logs Tab ──────────────────────────────────────────────────────────────────
function LogsTab() {
  const { data: logs = [], isLoading } = useQuery({
    queryKey: ["audit-logs"],
    queryFn: () => auditApi.getLogs({ limit: 100 }),
    refetchInterval: 10000,
  });

  if (isLoading) return <div className="py-10 text-center text-gray-400">Carregando...</div>;
  if (logs.length === 0) return <EmptyState title="Nenhum log registrado ainda" />;

  return (
    <div className="divide-y divide-gray-100 max-h-[70vh] overflow-y-auto">
      {logs.map((log) => (
        <div key={log.id} className="px-6 py-3">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900">{log.action}</p>
              <p className="text-xs text-gray-400 mt-0.5">
                {new Date(log.created_at).toLocaleString("pt-BR")}
                {log.ip_address && ` · ${log.ip_address}`}
              </p>
            </div>
            <span className="text-xs font-mono text-gray-300 ml-4" title="SHA-256 hash">
              {log.record_hash.substring(0, 12)}...
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Lote Tab (from BulkJobs) ──────────────────────────────────────────────────

const JOB_STATUS_CONFIG: Record<BulkJobStatus, { label: string; color: string; icon: React.ElementType }> = {
  pending:   { label: "Processando",  color: "bg-gray-100 text-gray-600",    icon: Loader2 },
  ready:     { label: "Pronto",       color: "bg-blue-100 text-blue-700",    icon: Clock },
  executing: { label: "Executando",   color: "bg-amber-100 text-amber-700",  icon: Loader2 },
  partial:   { label: "Parcial",      color: "bg-orange-100 text-orange-700",icon: XCircle },
  completed: { label: "Concluído",    color: "bg-green-100 text-green-700",  icon: CheckCircle2 },
  failed:    { label: "Falhou",       color: "bg-red-100 text-red-700",      icon: XCircle },
};

const OP_STATUS_CFG: Record<string, { label: string; color: string }> = {
  pending:           { label: "Aguardando",  color: "text-gray-500" },
  approved:          { label: "Pronto",      color: "text-blue-600" },
  awaiting_approval: { label: "Em revisão",  color: "text-amber-600" },
  executing:         { label: "Executando",  color: "text-amber-600" },
  completed:         { label: "Concluído",   color: "text-green-600" },
  failed:            { label: "Falhou",      color: "text-red-600" },
  rejected:          { label: "Rejeitado",   color: "text-red-600" },
};

const BULK_CATEGORY_ICON: Record<string, React.ElementType> = {
  firewall: Shield, router: Route, switch: Network, l3_switch: Layers,
};
const BULK_CATEGORY_LABEL: Record<string, string> = {
  firewall: "Firewall", router: "Roteador", switch: "Switch", l3_switch: "Switch L3",
};

function LoteJobStatusBadge({ status }: { status: BulkJobStatus }) {
  const cfg = JOB_STATUS_CONFIG[status];
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${cfg.color}`}>
      <Icon size={12} className={status === "executing" || status === "pending" ? "animate-spin" : ""} />
      {cfg.label}
    </span>
  );
}

function LoteOpRow({ op }: { op: Operation }) {
  const [expanded, setExpanded] = useState(false);
  const cfg = OP_STATUS_CFG[op.status] ?? { label: op.status, color: "text-gray-500" };
  return (
    <div className="border border-gray-100 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className={`text-xs font-medium shrink-0 ${cfg.color}`}>{cfg.label}</span>
          <span className="text-sm font-medium text-gray-800 truncate">{op.device_name ?? op.device_id}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {op.intent && op.intent !== "cross_device" && (
            <span className="text-xs font-mono bg-gray-100 px-1.5 py-0.5 rounded text-gray-600">{op.intent}</span>
          )}
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </div>
      </button>
      {expanded && (
        <div className="px-4 pb-4 pt-0 border-t border-gray-100 bg-gray-50 space-y-2">
          {op.error_message && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-xs text-red-700">{op.error_message}</div>
          )}
          {op.action_plan && (
            <pre className="text-xs bg-white border border-gray-200 rounded-lg p-3 overflow-x-auto max-h-40 text-gray-700">
              {JSON.stringify(op.action_plan, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

function LoteCategoryPlanBanner({ plans }: { plans: CategoryPlanSummary[] }) {
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-5">
      <p className="text-xs font-semibold text-blue-700 uppercase mb-2">Operação cross-device — {plans.length} categorias</p>
      <div className="flex flex-wrap gap-2">
        {plans.map((p) => {
          const Icon = BULK_CATEGORY_ICON[p.category] ?? Layers;
          return (
            <div key={p.category} className="flex items-center gap-1.5 bg-white border border-blue-100 rounded-lg px-2.5 py-1.5">
              <Icon size={12} className="text-blue-500" />
              <span className="text-xs font-medium text-gray-700">{BULK_CATEGORY_LABEL[p.category] ?? p.category}</span>
              <span className="text-xs text-gray-400">{p.device_count} dispositivo(s)</span>
              {p.intent && <span className="text-xs font-mono bg-gray-100 px-1 rounded text-gray-500">{p.intent}</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function LoteJobDetail({ id, onBack }: { id: string; onBack: () => void }) {
  const qc = useQueryClient();
  const { data: job, isLoading } = useQuery<BulkJobDetail>({
    queryKey: ["bulk-job", id],
    queryFn: () => bulkJobsApi.get(id),
    refetchInterval: (q) => q.state.data?.status === "executing" ? 3000 : false,
  });
  const executeMut = useMutation({
    mutationFn: () => bulkJobsApi.execute(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bulk-job", id] }),
  });
  const cancelMut = useMutation({
    mutationFn: () => bulkJobsApi.cancel(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["bulk-jobs"] }); onBack(); },
  });

  if (isLoading) return <p className="text-sm text-gray-400 py-8 text-center">Carregando...</p>;
  if (!job) return <p className="text-sm text-red-400 py-8 text-center">Job não encontrado.</p>;

  const canExecute = job.status === "ready" || job.status === "partial";
  const canCancel  = job.status === "ready" || job.status === "pending";
  const isCrossDevice = job.intent === "cross_device";

  const groups = isCrossDevice
    ? job.operations.reduce<Record<string, Operation[]>>((acc, op) => {
        const cat = op.device_category ?? "unknown";
        acc[cat] = [...(acc[cat] ?? []), op];
        return acc;
      }, {})
    : null;

  return (
    <div className="max-w-3xl mx-auto">
      <button onClick={onBack} className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-5">
        <ArrowLeft size={14} /> Voltar para a lista
      </button>
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Layers size={20} className="text-brand-500" />
            <h2 className="text-lg font-semibold text-gray-900 line-clamp-2">{job.description}</h2>
          </div>
          <div className="flex items-center gap-3 text-xs text-gray-500 flex-wrap">
            <LoteJobStatusBadge status={job.status} />
            <span>{job.device_count} dispositivos</span>
            {isCrossDevice
              ? <span className="font-medium bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">cross-device</span>
              : job.intent ? <span className="font-mono bg-gray-100 px-1.5 py-0.5 rounded">{job.intent}</span>
              : null}
            <span>{new Date(job.created_at).toLocaleString("pt-BR")}</span>
          </div>
        </div>
        <div className="flex gap-2 shrink-0">
          {canCancel && (
            <button
              onClick={() => { if (confirm("Cancelar e remover este job?")) cancelMut.mutate(); }}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-red-600 border border-gray-200 px-3 py-1.5 rounded-lg transition-colors"
            >
              <Trash2 size={13} /> Cancelar
            </button>
          )}
          {canExecute && (
            <button
              onClick={() => executeMut.mutate()}
              disabled={executeMut.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-sm rounded-lg disabled:opacity-50 font-medium"
            >
              {executeMut.isPending
                ? <><Loader2 size={14} className="animate-spin" /> Executando...</>
                : <><Play size={14} /> Executar em {job.device_count} dispositivos</>}
            </button>
          )}
        </div>
      </div>
      {job.category_plans && job.category_plans.length > 1 && <LoteCategoryPlanBanner plans={job.category_plans} />}
      {(job.completed_count + job.failed_count) > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-5">
          <div className="flex justify-between text-sm font-medium mb-2">
            <span className="text-green-600">{job.completed_count} concluídos</span>
            <span className="text-red-500">{job.failed_count} com falha</span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-2.5 flex overflow-hidden">
            <div className="h-2.5 bg-green-500" style={{ width: `${(job.completed_count / job.device_count) * 100}%` }} />
            <div className="h-2.5 bg-red-400" style={{ width: `${(job.failed_count / job.device_count) * 100}%` }} />
          </div>
        </div>
      )}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <p className="text-sm font-semibold text-gray-700 mb-3">Operações por dispositivo</p>
        {groups ? (
          <div className="space-y-4">
            {Object.entries(groups).map(([cat, catOps]) => {
              const Icon = BULK_CATEGORY_ICON[cat] ?? Layers;
              return (
                <div key={cat}>
                  <div className="flex items-center gap-2 mb-2">
                    <Icon size={13} className="text-gray-400" />
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      {BULK_CATEGORY_LABEL[cat] ?? cat} — {catOps.length} dispositivo(s)
                    </p>
                  </div>
                  <div className="space-y-1.5">{catOps.map((op) => <LoteOpRow key={op.id} op={op} />)}</div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="space-y-2">{job.operations.map((op) => <LoteOpRow key={op.id} op={op} />)}</div>
        )}
      </div>
      {job.error_summary && (
        <div className="mt-4 bg-red-50 border border-red-200 rounded-xl p-4 text-xs text-red-700">
          <p className="font-semibold mb-1">Resumo de erros</p>
          <pre className="whitespace-pre-wrap">{job.error_summary}</pre>
        </div>
      )}
    </div>
  );
}

function LoteTab() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ["bulk-jobs"],
    queryFn: bulkJobsApi.list,
    refetchInterval: 15000,
  });

  if (selectedId) return <div className="p-4"><LoteJobDetail id={selectedId} onBack={() => setSelectedId(null)} /></div>;

  return (
    <div className="p-4">
      <p className="text-sm text-gray-500 mb-5">{jobs.length} job(s) registrado(s)</p>
      {isLoading ? (
        <p className="text-sm text-gray-400">Carregando...</p>
      ) : jobs.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <Layers size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">Nenhuma operação em lote criada ainda.</p>
          <p className="text-xs mt-1">Selecione dispositivos na tela de Dispositivos para começar.</p>
        </div>
      ) : (
        <div className="space-y-3 max-w-3xl">
          {jobs.map((job: BulkJob) => {
            const pct = job.device_count > 0
              ? Math.round(((job.completed_count + job.failed_count) / job.device_count) * 100)
              : 0;
            return (
              <button
                key={job.id}
                onClick={() => setSelectedId(job.id)}
                className="w-full text-left bg-white rounded-xl border border-gray-200 p-4 hover:border-brand-400 hover:shadow-sm transition-all"
              >
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <Layers size={16} className="text-brand-500 shrink-0" />
                    <p className="text-sm font-medium text-gray-900 truncate">{job.description}</p>
                  </div>
                  <LoteJobStatusBadge status={job.status} />
                </div>
                <div className="flex items-center gap-4 text-xs text-gray-500 mb-3">
                  <span>{job.device_count} dispositivos</span>
                  {job.intent && <span className="font-mono bg-gray-100 px-1.5 py-0.5 rounded">{job.intent}</span>}
                  <span className="ml-auto">{new Date(job.created_at).toLocaleString("pt-BR")}</span>
                </div>
                {pct > 0 && (
                  <div>
                    <div className="flex justify-between text-xs text-gray-400 mb-1">
                      <span>{job.completed_count} ok · {job.failed_count} falha</span>
                      <span>{pct}%</span>
                    </div>
                    <div className="w-full bg-gray-100 rounded-full h-1.5">
                      <div className="h-1.5 rounded-full bg-green-500"
                        style={{ width: `${Math.round((job.completed_count / job.device_count) * 100)}%` }} />
                    </div>
                  </div>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export function Audit() {
  const [tab, setTab] = useState<Tab>("live");

  const { data: firewallPending = 0 } = useQuery({
    queryKey: ["audit-pending-count"],
    queryFn: auditApi.getPendingCount,
    refetchInterval: 30000,
  });
  const { data: serverPending = 0 } = useQuery({
    queryKey: ["server-ops-pending-count"],
    queryFn: serverOpsApi.getPendingCount,
    refetchInterval: 30000,
  });
  const pendingCount = firewallPending + serverPending;

  const tabs: { id: Tab; label: string; icon?: React.ReactNode }[] = [
    { id: "live", label: "Ao Vivo", icon: <Radio size={13} className="text-green-500" /> },
    { id: "pending", label: pendingCount > 0 ? `Pendentes (${pendingCount})` : "Pendentes" },
    { id: "direct", label: "Realizadas" },
    { id: "history", label: "Histórico" },
    { id: "lote", label: "Lote" },
    { id: "logs", label: "Logs" },
  ];

  return (
    <PageWrapper title="Auditoria">
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="flex border-b border-gray-200 px-2 pt-2">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px mr-1 ${
                tab === t.id
                  ? "border-brand-600 text-brand-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>

        {tab === "live"    && <LiveTab />}
        {tab === "pending" && <PendingTab />}
        {tab === "direct"  && <DirectTab />}
        {tab === "history" && <HistoryTab />}
        {tab === "lote"    && <LoteTab />}
        {tab === "logs"    && <LogsTab />}
      </div>
    </PageWrapper>
  );
}
