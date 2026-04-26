import { Fragment, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, XCircle, ChevronDown, ChevronRight } from "lucide-react";
import toast from "react-hot-toast";
import { PageWrapper } from "../components/layout/PageWrapper";
import { StatusBadge } from "../components/shared/StatusBadge";
import { auditApi } from "../api/audit";
import { AUDIT_INTENTS, type AuditPolicy, type UserForPolicy } from "../types/audit";

type Tab = "pending" | "direct" | "history" | "policy";

const ROLES = ["operator", "viewer"] as const;
const ROLE_LABELS: Record<string, string> = {
  operator: "Operador (N1)",
  viewer: "Visualizador",
};

const intentLabel = (key: string) => AUDIT_INTENTS.find((i) => i.key === key)?.label ?? key;
const fmtDate = (s: string | null) => (s ? new Date(s).toLocaleString("pt-BR") : "—");
const GROUPS = Array.from(new Set(AUDIT_INTENTS.map((i) => i.group)));
const DEFAULT_APPROVAL: Record<string, boolean> = Object.fromEntries(
  AUDIT_INTENTS.map((i) => [i.key, i.defaultApproval])
);

function policyValue(
  policies: AuditPolicy[],
  scopeType: string,
  scopeId: string,
  intent: string
): boolean | null {
  const p = policies.find(
    (p) => p.scope_type === scopeType && p.scope_id === scopeId && p.intent === intent
  );
  return p !== undefined ? p.requires_approval : null;
}

function effectiveValue(
  policies: AuditPolicy[],
  scopeType: string,
  scopeId: string,
  intent: string
): boolean {
  const v = policyValue(policies, scopeType, scopeId, intent);
  return v !== null ? v : (DEFAULT_APPROVAL[intent] ?? false);
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

  if (isLoading) {
    return <div className="py-10 text-center text-gray-400">Carregando...</div>;
  }

  if (ops.length === 0) {
    return (
      <div className="py-14 text-center text-gray-400">
        <CheckCircle2 size={40} className="mx-auto mb-3 text-green-300" />
        <p className="text-sm">Nenhuma operação aguardando revisão.</p>
      </div>
    );
  }

  return (
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
              <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
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

// ── History Tab ───────────────────────────────────────────────────────────────
function HistoryTab() {
  const { data: ops = [], isLoading } = useQuery({
    queryKey: ["audit-history"],
    queryFn: auditApi.getHistory,
  });
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (isLoading) return <div className="py-10 text-center text-gray-400">Carregando...</div>;
  if (ops.length === 0)
    return <div className="py-10 text-center text-gray-400 text-sm">Nenhuma operação no histórico.</div>;

  return (
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
              </div>
            </div>
          )}
        </Fragment>
      ))}
    </div>
  );
}

// ── Policy Tab ────────────────────────────────────────────────────────────────
function PolicyTab() {
  const qc = useQueryClient();
  const { data: policies = [] } = useQuery({
    queryKey: ["audit-policies"],
    queryFn: auditApi.getPolicies,
  });
  const { data: users = [] } = useQuery({
    queryKey: ["audit-users"],
    queryFn: auditApi.getUsers,
  });

  const [view, setView] = useState<"roles" | "users">("roles");
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);

  const upsertMutation = useMutation({
    mutationFn: auditApi.upsertPolicy,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["audit-policies"] }),
    onError: () => toast.error("Erro ao salvar política."),
  });

  const deleteMutation = useMutation({
    mutationFn: ({ scopeType, scopeId, intent }: { scopeType: string; scopeId: string; intent: string }) =>
      auditApi.deletePolicy(scopeType, scopeId, intent),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["audit-policies"] }),
    onError: () => toast.error("Erro ao remover override."),
  });

  const selectedUser = users.find((u: UserForPolicy) => u.id === selectedUserId);

  return (
    <div className="p-4">
      <div className="flex gap-1 mb-5 bg-gray-100 rounded-lg p-1 w-fit">
        {(["roles", "users"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              view === v ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {v === "roles" ? "Por Perfil" : "Por Usuário"}
          </button>
        ))}
      </div>

      {view === "roles" && (
        <>
          <p className="text-xs text-gray-500 mb-4">
            Checkboxes marcados = intenção requer aprovação N2. Admin sempre executa diretamente.
            Linhas sem "override" seguem o padrão do sistema.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase w-1/2">
                    Intenção
                  </th>
                  {ROLES.map((role) => (
                    <th key={role} className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase text-center">
                      {ROLE_LABELS[role]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {GROUPS.map((group) => (
                  <Fragment key={group}>
                    <tr className="bg-gray-50/70">
                      <td colSpan={ROLES.length + 1} className="px-4 py-1.5 text-xs font-semibold text-gray-600 uppercase tracking-wide">
                        {group}
                      </td>
                    </tr>
                    {AUDIT_INTENTS.filter((i) => i.group === group).map((intent) => (
                      <tr key={intent.key} className="border-t border-gray-100 hover:bg-gray-50">
                        <td className="px-4 py-2.5 text-gray-700">{intent.label}</td>
                        {ROLES.map((role) => {
                          const override = policyValue(policies, "role", role, intent.key);
                          const effective = override !== null ? override : (DEFAULT_APPROVAL[intent.key] ?? false);
                          return (
                            <td key={role} className="px-4 py-2.5 text-center">
                              <div className="flex flex-col items-center gap-0.5">
                                <input
                                  type="checkbox"
                                  checked={effective}
                                  onChange={(e) =>
                                    upsertMutation.mutate({
                                      scope_type: "role",
                                      scope_id: role,
                                      intent: intent.key,
                                      requires_approval: e.target.checked,
                                    })
                                  }
                                  disabled={upsertMutation.isPending}
                                  className="h-4 w-4 rounded border-gray-300 text-brand-600 cursor-pointer"
                                />
                                {override !== null && (
                                  <span className="text-[10px] text-brand-600 font-medium">override</span>
                                )}
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {view === "users" && (
        <>
          <div className="flex items-center gap-3 mb-5">
            <label className="text-sm font-medium text-gray-700 shrink-0">Usuário:</label>
            <select
              value={selectedUserId ?? ""}
              onChange={(e) => setSelectedUserId(e.target.value || null)}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 min-w-[280px]"
            >
              <option value="">Selecione um usuário...</option>
              {users
                .filter((u: UserForPolicy) => u.role !== "admin")
                .map((u: UserForPolicy) => (
                  <option key={u.id} value={u.id}>
                    {u.name} ({u.email}) — {u.role}
                  </option>
                ))}
            </select>
          </div>

          {!selectedUserId && (
            <p className="text-sm text-gray-400 text-center py-10">
              Selecione um usuário para ver e configurar seus overrides de política.
            </p>
          )}

          {selectedUserId && (
            <>
              <p className="text-xs text-gray-500 mb-4">
                Overrides individuais têm prioridade sobre o perfil do usuário. Remover um override
                faz a configuração voltar à política do perfil "{selectedUser?.role}".
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">
                        Intenção
                      </th>
                      <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase text-center">
                        Requer Aprovação
                      </th>
                      <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase text-center">
                        Override
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {GROUPS.map((group) => (
                      <Fragment key={group}>
                        <tr className="bg-gray-50/70">
                          <td colSpan={3} className="px-4 py-1.5 text-xs font-semibold text-gray-600 uppercase tracking-wide">
                            {group}
                          </td>
                        </tr>
                        {AUDIT_INTENTS.filter((i) => i.group === group).map((intent) => {
                          const userOverride = policyValue(policies, "user", selectedUserId, intent.key);
                          const roleEffective = effectiveValue(
                            policies,
                            "role",
                            selectedUser?.role ?? "",
                            intent.key
                          );
                          const effective = userOverride !== null ? userOverride : roleEffective;
                          const hasOverride = userOverride !== null;
                          return (
                            <tr key={intent.key} className="border-t border-gray-100 hover:bg-gray-50">
                              <td className="px-4 py-2.5 text-gray-700">{intent.label}</td>
                              <td className="px-4 py-2.5 text-center">
                                <input
                                  type="checkbox"
                                  checked={effective}
                                  onChange={(e) =>
                                    upsertMutation.mutate({
                                      scope_type: "user",
                                      scope_id: selectedUserId,
                                      intent: intent.key,
                                      requires_approval: e.target.checked,
                                    })
                                  }
                                  disabled={upsertMutation.isPending || deleteMutation.isPending}
                                  className="h-4 w-4 rounded border-gray-300 text-brand-600 cursor-pointer"
                                />
                              </td>
                              <td className="px-4 py-2.5 text-center">
                                {hasOverride ? (
                                  <button
                                    onClick={() =>
                                      deleteMutation.mutate({
                                        scopeType: "user",
                                        scopeId: selectedUserId,
                                        intent: intent.key,
                                      })
                                    }
                                    disabled={deleteMutation.isPending}
                                    className="text-xs text-red-500 hover:text-red-700 underline"
                                  >
                                    Remover
                                  </button>
                                ) : (
                                  <span className="text-xs text-gray-400">—</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export function Audit() {
  const [tab, setTab] = useState<Tab>("pending");

  const { data: pendingCount = 0 } = useQuery({
    queryKey: ["audit-pending-count"],
    queryFn: auditApi.getPendingCount,
    refetchInterval: 30000,
  });

  const tabs: { id: Tab; label: string }[] = [
    { id: "pending", label: pendingCount > 0 ? `Pendentes (${pendingCount})` : "Pendentes" },
    { id: "direct", label: "Realizadas" },
    { id: "history", label: "Histórico" },
    { id: "policy", label: "Política" },
  ];

  return (
    <PageWrapper title="Auditoria">
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="flex border-b border-gray-200 px-2 pt-2">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px mr-1 ${
                tab === t.id
                  ? "border-brand-600 text-brand-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === "pending" && <PendingTab />}
        {tab === "direct" && <DirectTab />}
        {tab === "history" && <HistoryTab />}
        {tab === "policy" && <PolicyTab />}
      </div>
    </PageWrapper>
  );
}
