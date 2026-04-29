import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import {
  ShieldCheck, ShieldX, Play, Trash2, ChevronDown, ChevronUp,
  AlertTriangle, CheckCircle2, XCircle, Clock, Loader2, Plus,
  Terminal, Pencil, RotateCcw, Check, X,
} from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { remediationApi } from "../api/remediation";
import { serversApi } from "../api/servers";
import type { RemediationCommand, RemediationPlan, RemediationStatus, CommandStatus, RemediationRisk } from "../types/remediation";

// ── Helpers ───────────────────────────────────────────────────────────────────

const RISK_STYLES: Record<RemediationRisk, string> = {
  low:    "bg-green-100 text-green-700",
  medium: "bg-yellow-100 text-yellow-700",
  high:   "bg-red-100 text-red-700",
};

const PLAN_STATUS_LABEL: Record<RemediationStatus, string> = {
  pending_approval: "Aguardando aprovação",
  approved:         "Aprovado",
  executing:        "Executando",
  completed:        "Concluído",
  partial:          "Parcial",
  rejected:         "Rejeitado",
};

const PLAN_STATUS_CLASS: Record<RemediationStatus, string> = {
  pending_approval: "bg-yellow-100 text-yellow-700",
  approved:         "bg-blue-100 text-blue-700",
  executing:        "bg-purple-100 text-purple-700",
  completed:        "bg-green-100 text-green-700",
  partial:          "bg-orange-100 text-orange-700",
  rejected:         "bg-red-100 text-red-700",
};

const CMD_STATUS_ICON: Record<CommandStatus, React.ReactNode> = {
  pending:   <Clock size={14} className="text-gray-400" />,
  approved:  <CheckCircle2 size={14} className="text-blue-500" />,
  rejected:  <XCircle size={14} className="text-red-400" />,
  executing: <Loader2 size={14} className="text-purple-500 animate-spin" />,
  completed: <CheckCircle2 size={14} className="text-green-500" />,
  failed:    <XCircle size={14} className="text-red-500" />,
  skipped:   <Clock size={14} className="text-gray-300" />,
};

// ── New plan form ─────────────────────────────────────────────────────────────

interface NewPlanFormProps {
  onCreated: () => void;
  initialServerId?: string;
  initialRequest?: string;
}

function NewPlanForm({ onCreated, initialServerId, initialRequest }: NewPlanFormProps) {
  const [open, setOpen] = useState(false);
  const [serverId, setServerId] = useState(initialServerId ?? "");
  const [request, setRequest] = useState(initialRequest ?? "");

  useEffect(() => {
    if (initialServerId || initialRequest) setOpen(true);
  }, [initialServerId, initialRequest]);

  const { data: servers = [] } = useQuery({ queryKey: ["servers"], queryFn: serversApi.list });

  const qc = useQueryClient();
  const create = useMutation({
    mutationFn: () => remediationApi.create({ server_id: serverId, request }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["remediation"] });
      setServerId("");
      setRequest("");
      setOpen(false);
      onCreated();
    },
  });

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
      >
        <Plus size={16} />
        Novo plano de remediação
      </button>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
      <h3 className="font-semibold text-gray-900 mb-4">Novo plano de remediação</h3>
      <div className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Servidor</label>
          <select
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
            value={serverId}
            onChange={(e) => setServerId(e.target.value)}
          >
            <option value="">Selecione um servidor…</option>
            {servers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.host}) — {s.os_type.toUpperCase()}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">O que precisa ser corrigido?</label>
          <textarea
            rows={3}
            placeholder="Ex: O serviço nginx está falhando, preciso diagnósticar e reiniciar…"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-400"
            value={request}
            onChange={(e) => setRequest(e.target.value)}
          />
        </div>
        <div className="flex gap-2 justify-end">
          <button
            onClick={() => setOpen(false)}
            className="text-sm text-gray-500 px-4 py-2 rounded-lg hover:bg-gray-100 transition-colors"
          >
            Cancelar
          </button>
          <button
            disabled={!serverId || !request.trim() || create.isPending}
            onClick={() => create.mutate()}
            className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            {create.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
            {create.isPending ? "Gerando…" : "Gerar plano com IA"}
          </button>
        </div>
        {create.isError && (
          <p className="text-xs text-red-600 mt-1">
            Erro: {(create.error as Error).message}
          </p>
        )}
      </div>
    </div>
  );
}

// ── Command row ───────────────────────────────────────────────────────────────

function CommandRow({
  cmd,
  planId,
  planStatus,
  onAction,
}: {
  cmd: RemediationCommand;
  planId: string;
  planStatus: RemediationStatus;
  onAction: () => void;
}) {
  const [expanded, setExpanded] = useState(cmd.status === "failed" || cmd.status === "completed");
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(cmd.command);
  const qc = useQueryClient();

  const canReview = planStatus === "pending_approval" && cmd.status === "pending";
  const canEdit = canReview;

  const approve = useMutation({
    mutationFn: () => remediationApi.approveCommand(planId, cmd.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["remediation"] }); onAction(); },
  });

  const reject = useMutation({
    mutationFn: () => remediationApi.rejectCommand(planId, cmd.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["remediation"] }); onAction(); },
  });

  const edit = useMutation({
    mutationFn: () => remediationApi.updateCommand(planId, cmd.id, { command: editValue }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["remediation"] }); setEditing(false); },
  });

  const statusBg =
    cmd.status === "failed"    ? "bg-red-50 border-red-200" :
    cmd.status === "completed" ? "bg-green-50 border-green-200" :
    "bg-gray-50 border-gray-100";

  return (
    <div className={`border rounded-lg overflow-hidden ${statusBg}`}>
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-black/5 transition-colors"
        onClick={() => !editing && setExpanded((v) => !v)}
      >
        <span className="text-xs font-mono text-gray-400 w-5 text-right shrink-0">{cmd.order}</span>
        {CMD_STATUS_ICON[cmd.status]}
        <span className="flex-1 text-sm text-gray-700 truncate">{cmd.description}</span>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full shrink-0 ${RISK_STYLES[cmd.risk]}`}>
          {cmd.risk}
        </span>
        {canReview && (
          <div className="flex gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
            {canEdit && !editing && (
              <button
                onClick={() => { setEditing(true); setExpanded(true); }}
                title="Editar comando"
                className="p-1.5 rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-500 transition-colors"
              >
                <Pencil size={14} />
              </button>
            )}
            <button
              disabled={approve.isPending}
              onClick={() => approve.mutate()}
              title="Aprovar"
              className="p-1.5 rounded-lg bg-green-50 hover:bg-green-100 text-green-600 transition-colors disabled:opacity-50"
            >
              <ShieldCheck size={15} />
            </button>
            <button
              disabled={reject.isPending}
              onClick={() => reject.mutate()}
              title="Rejeitar"
              className="p-1.5 rounded-lg bg-red-50 hover:bg-red-100 text-red-500 transition-colors disabled:opacity-50"
            >
              <ShieldX size={15} />
            </button>
          </div>
        )}
        {expanded ? <ChevronUp size={14} className="text-gray-400 shrink-0" /> : <ChevronDown size={14} className="text-gray-400 shrink-0" />}
      </div>

      {expanded && (
        <div className="px-4 py-3 bg-white space-y-3 border-t border-inherit">
          <div>
            <p className="text-xs font-medium text-gray-500 mb-1">Comando</p>
            {editing ? (
              <div className="space-y-2">
                <textarea
                  rows={3}
                  className="w-full bg-gray-900 text-green-400 text-xs rounded-lg px-4 py-3 font-mono resize-y focus:outline-none focus:ring-2 focus:ring-brand-400"
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  autoFocus
                />
                <div className="flex gap-2">
                  <button
                    disabled={edit.isPending || !editValue.trim()}
                    onClick={() => edit.mutate()}
                    className="flex items-center gap-1.5 text-xs bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg transition-colors"
                  >
                    {edit.isPending ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                    Salvar
                  </button>
                  <button
                    onClick={() => { setEditing(false); setEditValue(cmd.command); }}
                    className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 px-3 py-1.5 rounded-lg hover:bg-gray-100 transition-colors"
                  >
                    <X size={12} /> Cancelar
                  </button>
                  {edit.isError && (
                    <span className="text-xs text-red-600 self-center">
                      {(edit.error as Error).message}
                    </span>
                  )}
                </div>
              </div>
            ) : (
              <pre className="bg-gray-900 text-green-400 text-xs rounded-lg px-4 py-3 overflow-x-auto font-mono whitespace-pre-wrap">
                {cmd.command}
              </pre>
            )}
          </div>
          {cmd.output && (
            <div>
              <p className={`text-xs font-medium mb-1 ${cmd.status === "failed" ? "text-red-500" : "text-gray-500"}`}>
                {cmd.status === "failed" ? "Erro / Saída" : "Saída"}
              </p>
              <pre className={`text-xs rounded-lg px-4 py-3 overflow-x-auto font-mono whitespace-pre-wrap border ${
                cmd.status === "failed"
                  ? "bg-red-50 text-red-700 border-red-200"
                  : "bg-gray-50 text-gray-700 border-gray-100"
              }`}>
                {cmd.output}
              </pre>
            </div>
          )}
          {cmd.executed_at && (
            <p className="text-xs text-gray-400">
              Executado em {new Date(cmd.executed_at).toLocaleString("pt-BR")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Plan card ─────────────────────────────────────────────────────────────────

function PlanCard({ plan }: { plan: RemediationPlan }) {
  const [expanded, setExpanded] = useState(false);
  const qc = useQueryClient();

  const approvedCount = plan.commands.filter((c) => c.status === "approved").length;
  const canExecute = plan.status === "pending_approval" && approvedCount > 0;

  const execute = useMutation({
    mutationFn: () => remediationApi.execute(plan.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["remediation"] }),
  });

  const retry = useMutation({
    mutationFn: () => remediationApi.retry(plan.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["remediation"] }),
  });

  const remove = useMutation({
    mutationFn: () => remediationApi.remove(plan.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["remediation"] }),
  });

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      {/* Header */}
      <div
        className="flex items-start gap-4 px-5 py-4 cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <Terminal size={18} className="text-brand-500 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">{plan.request}</p>
          <p className="text-xs text-gray-400 mt-0.5">
            {new Date(plan.created_at).toLocaleString("pt-BR")} · {plan.commands.length} comando(s)
          </p>
        </div>
        <span className={`shrink-0 text-xs font-medium px-2.5 py-1 rounded-full ${PLAN_STATUS_CLASS[plan.status]}`}>
          {PLAN_STATUS_LABEL[plan.status]}
        </span>
        {expanded ? <ChevronUp size={16} className="text-gray-400 shrink-0 mt-0.5" /> : <ChevronDown size={16} className="text-gray-400 shrink-0 mt-0.5" />}
      </div>

      {expanded && (
        <div className="px-5 pb-5 space-y-4 border-t border-gray-100">
          {/* Summary */}
          {plan.summary && (
            <p className="text-sm text-gray-600 pt-3">{plan.summary}</p>
          )}

          {/* Commands */}
          <div className="space-y-2">
            {plan.commands.map((cmd) => (
              <CommandRow
                key={cmd.id}
                cmd={cmd}
                planId={plan.id}
                planStatus={plan.status}
                onAction={() => {}}
              />
            ))}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 pt-2 flex-wrap">
            {canExecute && (
              <button
                disabled={execute.isPending}
                onClick={() => execute.mutate()}
                className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
              >
                {execute.isPending
                  ? <Loader2 size={15} className="animate-spin" />
                  : <Play size={15} />}
                {execute.isPending ? "Executando…" : `Executar ${approvedCount} aprovado(s)`}
              </button>
            )}
            {plan.status === "partial" && (
              <button
                disabled={retry.isPending}
                onClick={() => retry.mutate()}
                className="flex items-center gap-2 bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
              >
                {retry.isPending
                  ? <Loader2 size={15} className="animate-spin" />
                  : <RotateCcw size={15} />}
                {retry.isPending ? "Analisando erros…" : "Retentar com IA"}
              </button>
            )}
            {plan.status === "pending_approval" && approvedCount === 0 && (
              <p className="text-xs text-gray-400 flex items-center gap-1">
                <AlertTriangle size={12} /> Aprove pelo menos um comando para executar
              </p>
            )}
            <div className="flex-1" />
            <button
              disabled={remove.isPending || plan.status === "executing"}
              onClick={() => remove.mutate()}
              className="flex items-center gap-1.5 text-xs text-red-400 hover:text-red-600 disabled:opacity-40 transition-colors"
            >
              <Trash2 size={13} /> Excluir
            </button>
          </div>

          {execute.isError && (
            <p className="text-xs text-red-600">
              Erro: {(execute.error as Error).message}
            </p>
          )}
          {retry.isError && (
            <p className="text-xs text-red-600">
              Erro ao retentar: {(retry.error as Error).message}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function Remediation() {
  const location = useLocation();
  const navState = location.state as { server_id?: string; request?: string } | null;

  const { data: plans = [], isLoading } = useQuery({
    queryKey: ["remediation"],
    queryFn: remediationApi.list,
    refetchInterval: 5000,
  });

  return (
    <PageWrapper title="Remediações">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <p className="text-sm text-gray-500">
              A IA sugere comandos de correção; você aprova cada um antes da execução.
            </p>
          </div>
          <NewPlanForm
            onCreated={() => {}}
            initialServerId={navState?.server_id}
            initialRequest={navState?.request}
          />
        </div>

        {isLoading ? (
          <div className="text-center py-12 text-gray-400">Carregando…</div>
        ) : plans.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <Terminal size={40} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm">Nenhum plano de remediação ainda.</p>
            <p className="text-xs mt-1">Clique em "Novo plano" para começar.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {plans.map((plan) => (
              <PlanCard key={plan.id} plan={plan} />
            ))}
          </div>
        )}
      </div>
    </PageWrapper>
  );
}
