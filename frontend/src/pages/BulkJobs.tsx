import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, Link } from "react-router-dom";
import {
  Layers, CheckCircle2, XCircle, Loader2, Clock,
  ChevronDown, ChevronUp, Play, Trash2, ArrowLeft,
  Shield, Route, Network,
} from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { bulkJobsApi } from "../api/bulk_jobs";
import type { BulkJob, BulkJobDetail, BulkJobStatus, CategoryPlanSummary } from "../types/bulk_job";
import type { Operation } from "../types/operation";

// ── Status helpers ────────────────────────────────────────────────────────────

const JOB_STATUS_CONFIG: Record<BulkJobStatus, { label: string; color: string; icon: React.ElementType }> = {
  pending:   { label: "Processando",  color: "bg-gray-100 text-gray-600",    icon: Loader2 },
  ready:     { label: "Pronto",       color: "bg-blue-100 text-blue-700",    icon: Clock },
  executing: { label: "Executando",   color: "bg-amber-100 text-amber-700",  icon: Loader2 },
  partial:   { label: "Parcial",      color: "bg-orange-100 text-orange-700",icon: XCircle },
  completed: { label: "Concluído",    color: "bg-green-100 text-green-700",  icon: CheckCircle2 },
  failed:    { label: "Falhou",       color: "bg-red-100 text-red-700",      icon: XCircle },
};

const OP_STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  pending:           { label: "Aguardando",  color: "text-gray-500" },
  approved:          { label: "Pronto",      color: "text-blue-600" },
  awaiting_approval: { label: "Em revisão",  color: "text-amber-600" },
  executing:         { label: "Executando",  color: "text-amber-600" },
  completed:         { label: "Concluído",   color: "text-green-600" },
  failed:            { label: "Falhou",      color: "text-red-600" },
  rejected:          { label: "Rejeitado",   color: "text-red-600" },
};

function JobStatusBadge({ status }: { status: BulkJobStatus }) {
  const cfg = JOB_STATUS_CONFIG[status];
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${cfg.color}`}>
      <Icon size={12} className={status === "executing" || status === "pending" ? "animate-spin" : ""} />
      {cfg.label}
    </span>
  );
}

// ── Job card (in list) ────────────────────────────────────────────────────────

function JobCard({ job }: { job: BulkJob }) {
  const pct = job.device_count > 0
    ? Math.round(((job.completed_count + job.failed_count) / job.device_count) * 100)
    : 0;

  return (
    <Link
      to={`/bulk-jobs/${job.id}`}
      className="block bg-white rounded-xl border border-gray-200 p-4 hover:border-brand-400 hover:shadow-sm transition-all"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <Layers size={16} className="text-brand-500 shrink-0" />
          <p className="text-sm font-medium text-gray-900 truncate">{job.description}</p>
        </div>
        <JobStatusBadge status={job.status} />
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
            <div
              className="h-1.5 rounded-full bg-green-500"
              style={{ width: `${Math.round((job.completed_count / job.device_count) * 100)}%` }}
            />
          </div>
        </div>
      )}
    </Link>
  );
}

// ── Category icon helper ──────────────────────────────────────────────────────

const CATEGORY_ICON: Record<string, React.ElementType> = {
  firewall:  Shield,
  router:    Route,
  switch:    Network,
  l3_switch: Layers,
};

const CATEGORY_LABEL: Record<string, string> = {
  firewall:  "Firewall",
  router:    "Roteador",
  switch:    "Switch",
  l3_switch: "Switch L3",
};

// ── Operation row (in detail) ─────────────────────────────────────────────────

function OpRow({ op }: { op: Operation }) {
  const [expanded, setExpanded] = useState(false);
  const cfg = OP_STATUS_CONFIG[op.status] ?? { label: op.status, color: "text-gray-500" };

  const displayName = op.device_name ?? op.device_id;

  return (
    <div className="border border-gray-100 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className={`text-xs font-medium shrink-0 ${cfg.color}`}>{cfg.label}</span>
          <span className="text-sm font-medium text-gray-800 truncate">{displayName}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {op.intent && op.intent !== "cross_device" && (
            <span className="text-xs font-mono bg-gray-100 px-1.5 py-0.5 rounded text-gray-600">
              {op.intent}
            </span>
          )}
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 pt-0 border-t border-gray-100 bg-gray-50 space-y-2">
          {op.error_message && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-xs text-red-700">
              {op.error_message}
            </div>
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

// ── Cross-device category plans summary ───────────────────────────────────────

function CategoryPlanBanner({ plans }: { plans: CategoryPlanSummary[] }) {
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-5">
      <p className="text-xs font-semibold text-blue-700 uppercase mb-2">
        Operação cross-device — {plans.length} categorias
      </p>
      <div className="flex flex-wrap gap-2">
        {plans.map((p) => {
          const Icon = CATEGORY_ICON[p.category] ?? Layers;
          return (
            <div
              key={p.category}
              className="flex items-center gap-1.5 bg-white border border-blue-100 rounded-lg px-2.5 py-1.5"
            >
              <Icon size={12} className="text-blue-500" />
              <span className="text-xs font-medium text-gray-700">
                {CATEGORY_LABEL[p.category] ?? p.category}
              </span>
              <span className="text-xs text-gray-400">{p.device_count} dispositivo(s)</span>
              {p.intent && (
                <span className="text-xs font-mono bg-gray-100 px-1 rounded text-gray-500">
                  {p.intent}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Operations grouped by category ───────────────────────────────────────────

function OpsByCategory({ ops, isCrossDevice }: { ops: Operation[]; isCrossDevice: boolean }) {
  if (!isCrossDevice) {
    return (
      <div className="space-y-2">
        {ops.map((op) => <OpRow key={op.id} op={op} />)}
      </div>
    );
  }

  // Group by device_category
  const groups = ops.reduce<Record<string, Operation[]>>((acc, op) => {
    const cat = op.device_category ?? "unknown";
    acc[cat] = [...(acc[cat] ?? []), op];
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      {Object.entries(groups).map(([cat, catOps]) => {
        const Icon = CATEGORY_ICON[cat] ?? Layers;
        return (
          <div key={cat}>
            <div className="flex items-center gap-2 mb-2">
              <Icon size={13} className="text-gray-400" />
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                {CATEGORY_LABEL[cat] ?? cat} — {catOps.length} dispositivo(s)
              </p>
            </div>
            <div className="space-y-1.5">
              {catOps.map((op) => <OpRow key={op.id} op={op} />)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Detail view ───────────────────────────────────────────────────────────────

function BulkJobDetailView({ id }: { id: string }) {
  const qc = useQueryClient();

  const { data: job, isLoading } = useQuery<BulkJobDetail>({
    queryKey: ["bulk-job", id],
    queryFn: () => bulkJobsApi.get(id),
    refetchInterval: (q) =>
      q.state.data?.status === "executing" ? 3000 : false,
  });

  const executeMut = useMutation({
    mutationFn: () => bulkJobsApi.execute(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bulk-job", id] }),
  });

  const cancelMut = useMutation({
    mutationFn: () => bulkJobsApi.cancel(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bulk-jobs"] }),
  });

  if (isLoading) return <p className="text-sm text-gray-400 py-8 text-center">Carregando...</p>;
  if (!job) return <p className="text-sm text-red-400 py-8 text-center">Job não encontrado.</p>;

  const canExecute    = job.status === "ready" || job.status === "partial";
  const canCancel     = job.status === "ready" || job.status === "pending";
  const isCrossDevice = job.intent === "cross_device";

  return (
    <div className="max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Layers size={20} className="text-brand-500" />
            <h2 className="text-lg font-semibold text-gray-900 line-clamp-2">{job.description}</h2>
          </div>
          <div className="flex items-center gap-3 text-xs text-gray-500 flex-wrap">
            <JobStatusBadge status={job.status} />
            <span>{job.device_count} dispositivos</span>
            {isCrossDevice ? (
              <span className="font-medium bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">
                cross-device
              </span>
            ) : job.intent ? (
              <span className="font-mono bg-gray-100 px-1.5 py-0.5 rounded">{job.intent}</span>
            ) : null}
            <span>{new Date(job.created_at).toLocaleString("pt-BR")}</span>
          </div>
        </div>

        <div className="flex gap-2 shrink-0">
          {canCancel && (
            <button
              onClick={() => { if (confirm("Cancelar e remover este job?")) cancelMut.mutate(); }}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-red-600 border border-gray-200 px-3 py-1.5 rounded-lg transition-colors"
            >
              <Trash2 size={13} />
              Cancelar
            </button>
          )}
          {canExecute && (
            <button
              onClick={() => executeMut.mutate()}
              disabled={executeMut.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-sm rounded-lg disabled:opacity-50 transition-colors font-medium"
            >
              {executeMut.isPending
                ? <><Loader2 size={14} className="animate-spin" /> Executando...</>
                : <><Play size={14} /> Executar em {job.device_count} dispositivos</>
              }
            </button>
          )}
        </div>
      </div>

      {/* Cross-device category breakdown */}
      {job.category_plans && job.category_plans.length > 1 && (
        <CategoryPlanBanner plans={job.category_plans} />
      )}

      {/* Progress bar */}
      {(job.completed_count + job.failed_count) > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-5">
          <div className="flex justify-between text-sm font-medium mb-2">
            <span className="text-green-600">{job.completed_count} concluídos</span>
            <span className="text-red-500">{job.failed_count} com falha</span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-2.5 flex overflow-hidden">
            <div
              className="h-2.5 bg-green-500"
              style={{ width: `${(job.completed_count / job.device_count) * 100}%` }}
            />
            <div
              className="h-2.5 bg-red-400"
              style={{ width: `${(job.failed_count / job.device_count) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Operations list — grouped by category for cross-device jobs */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <p className="text-sm font-semibold text-gray-700 mb-3">Operações por dispositivo</p>
        <OpsByCategory ops={job.operations} isCrossDevice={isCrossDevice} />
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

// ── List view ─────────────────────────────────────────────────────────────────

function BulkJobsList() {
  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ["bulk-jobs"],
    queryFn: bulkJobsApi.list,
    refetchInterval: 15000,
  });

  return (
    <>
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
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} />
          ))}
        </div>
      )}
    </>
  );
}

// ── Page entry ────────────────────────────────────────────────────────────────

export function BulkJobs() {
  const { id } = useParams<{ id?: string }>();

  return (
    <PageWrapper title="Operações em Lote">
      {id ? (
        <>
          <Link
            to="/bulk-jobs"
            className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-5"
          >
            <ArrowLeft size={14} />
            Voltar para a lista
          </Link>
          <BulkJobDetailView id={id} />
        </>
      ) : (
        <BulkJobsList />
      )}
    </PageWrapper>
  );
}
