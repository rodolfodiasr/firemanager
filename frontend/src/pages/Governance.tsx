import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  RefreshCw,
  FileSpreadsheet,
  ChevronDown,
  ChevronUp,
  Loader2,
  ShieldCheck,
  AlertTriangle,
  TrendingUp,
  Clock,
} from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { governanceApi } from "../api/compliance";
import type {
  EternityBreakdown,
  Framework,
  FrameworkScoreItem,
  GovernanceSummary,
  IsoBreakdown,
  NistBreakdown,
} from "../types/governance";

// ── Helpers ───────────────────────────────────────────────────────────────────

function scoreColor(pct: number | null) {
  if (pct === null) return { text: "text-gray-400", bg: "bg-gray-300", ring: "ring-gray-100", label: "N/A" };
  if (pct >= 75) return { text: "text-green-600",  bg: "bg-green-500",  ring: "ring-green-100",  label: "Bom"  };
  if (pct >= 50) return { text: "text-yellow-600", bg: "bg-yellow-500", ring: "ring-yellow-100", label: "Médio" };
  return               { text: "text-red-600",     bg: "bg-red-500",    ring: "ring-red-100",    label: "Crítico" };
}

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function fmtFramework(fw: Framework) {
  return {
    cis_benchmark: "CIS Benchmark",
    nist_csf:      "NIST CSF",
    iso_27001:     "ISO 27001",
    eternity:      "Eternity",
  }[fw] ?? fw;
}

const COMPONENT_LABELS: Record<string, string> = {
  server_compliance:    "Conformidade de Servidores",
  operation_hygiene:    "Higiene de Operações",
  remediation_velocity: "Velocidade de Remediação",
  audit_integrity:      "Integridade de Auditoria",
  access_governance:    "Governança de Acesso",
};

const NIST_LABELS: Record<string, string> = {
  identify: "Identificar (ID)",
  protect:  "Proteger (PR)",
  detect:   "Detectar (DE)",
  respond:  "Responder (RS)",
  recover:  "Recuperar (RC)",
};

const ISO_LABELS: Record<string, string> = {
  "A.10_cryptography":   "A.10 — Criptografia",
  "A.9_access_control":  "A.9 — Controle de Acesso",
  "A.8.15_logging":      "A.8.15 — Logging",
  "A.8.6_operations":    "A.8.6 — Operações",
  "A.9.4_system_access": "A.9.4 — Acesso ao Sistema",
  "A.12_compliance":     "A.12 — Conformidade Técnica",
};

// ── Score gauge ───────────────────────────────────────────────────────────────

function ScoreGauge({ pct, size = "md" }: { pct: number | null; size?: "sm" | "md" | "lg" }) {
  const col = scoreColor(pct);
  const dims = { sm: "w-16 h-16", md: "w-24 h-24", lg: "w-32 h-32" };
  const text = { sm: "text-lg", md: "text-2xl", lg: "text-4xl" };
  return (
    <div className={`flex flex-col items-center justify-center ${dims[size]} rounded-full ring-4 ${col.ring} bg-white shrink-0`}>
      <span className={`${text[size]} font-bold ${col.text}`}>
        {pct !== null ? `${pct.toFixed(0)}` : "—"}
      </span>
      <span className="text-xs text-gray-400 leading-tight">
        {pct !== null ? "%" : "N/A"}
      </span>
    </div>
  );
}

// ── Bar row ───────────────────────────────────────────────────────────────────

function ScoreBar({ label, value, weight }: { label: string; value: number; weight?: number }) {
  const col = scoreColor(value);
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-gray-600 w-52 shrink-0">{label}</span>
      <div className="flex-1 bg-gray-100 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all ${col.bg}`}
          style={{ width: `${Math.min(value, 100)}%` }}
        />
      </div>
      <span className={`text-xs font-semibold w-10 text-right ${col.text}`}>
        {value.toFixed(0)}%
      </span>
      {weight !== undefined && (
        <span className="text-xs text-gray-400 w-12 text-right">
          ×{(weight * 100).toFixed(0)}%
        </span>
      )}
    </div>
  );
}

// ── Framework card ────────────────────────────────────────────────────────────

function FrameworkCard({
  title, subtitle, score, extra,
}: {
  title: string;
  subtitle: string;
  score: number | null;
  extra?: React.ReactNode;
}) {
  const col = scoreColor(score);
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col gap-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-semibold text-gray-800">{title}</p>
          <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>
        </div>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
          score === null ? "bg-gray-100 text-gray-500" :
          score >= 75 ? "bg-green-100 text-green-700" :
          score >= 50 ? "bg-yellow-100 text-yellow-700" :
          "bg-red-100 text-red-700"
        }`}>
          {col.label}
        </span>
      </div>
      <div className="flex items-center gap-4">
        <ScoreGauge pct={score} size="md" />
        {extra}
      </div>
    </div>
  );
}

// ── Breakdown panel ───────────────────────────────────────────────────────────

function EternityBreakdownPanel({ breakdown }: { breakdown: EternityBreakdown }) {
  const { components, weights } = breakdown;
  return (
    <div className="flex flex-col gap-2.5">
      {Object.entries(components).map(([key, val]) => (
        <ScoreBar
          key={key}
          label={COMPONENT_LABELS[key] ?? key}
          value={val}
          weight={weights[key]}
        />
      ))}
    </div>
  );
}

function NistBreakdownPanel({ breakdown }: { breakdown: NistBreakdown }) {
  return (
    <div className="flex flex-col gap-2.5">
      {Object.entries(breakdown.nist_functions).map(([key, val]) => (
        <ScoreBar key={key} label={NIST_LABELS[key] ?? key} value={val} />
      ))}
    </div>
  );
}

function IsoBreakdownPanel({ breakdown }: { breakdown: IsoBreakdown }) {
  return (
    <div className="flex flex-col gap-2.5">
      {Object.entries(breakdown.iso_controls).map(([key, val]) => (
        <ScoreBar key={key} label={ISO_LABELS[key] ?? key} value={val} />
      ))}
    </div>
  );
}

// ── History table ─────────────────────────────────────────────────────────────

function HistoryPanel({ framework }: { framework: Framework }) {
  const { data = [], isLoading } = useQuery({
    queryKey: ["governance-history", framework],
    queryFn: () => governanceApi.history(framework, 10),
  });

  if (isLoading) return <p className="text-xs text-gray-400 py-4 text-center">Carregando…</p>;
  if (data.length === 0) return <p className="text-xs text-gray-400 py-4 text-center">Nenhum histórico disponível.</p>;

  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-left text-gray-500 border-b border-gray-100">
          <th className="pb-2 font-medium">Data</th>
          <th className="pb-2 font-medium text-right">Score</th>
          <th className="pb-2 font-medium text-right w-32">Barra</th>
        </tr>
      </thead>
      <tbody>
        {data.map((row: FrameworkScoreItem, i: number) => {
          const col = scoreColor(row.score_pct);
          return (
            <tr key={i} className="border-b border-gray-50 last:border-0">
              <td className="py-1.5 text-gray-600">{fmtDate(row.computed_at)}</td>
              <td className={`py-1.5 text-right font-semibold ${col.text}`}>
                {row.score_pct.toFixed(1)}%
              </td>
              <td className="py-1.5 pl-3">
                <div className="bg-gray-100 rounded-full h-1.5">
                  <div
                    className={`h-1.5 rounded-full ${col.bg}`}
                    style={{ width: `${Math.min(row.score_pct, 100)}%` }}
                  />
                </div>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function Governance() {
  const qc = useQueryClient();
  const [expandedBreakdown, setExpandedBreakdown] = useState<string | null>("eternity");
  const [historyFw, setHistoryFw]                 = useState<Framework | null>(null);

  const { data: summary, isLoading } = useQuery<GovernanceSummary>({
    queryKey: ["governance-summary"],
    queryFn: governanceApi.summary,
  });

  const compute = useMutation({
    mutationFn: governanceApi.compute,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["governance-summary"] });
      qc.invalidateQueries({ queryKey: ["governance-history"] });
    },
  });

  const handleExport = () => {
    const url = governanceApi.exportExcelUrl();
    const token = localStorage.getItem("access_token") ?? "";
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `governance_${new Date().toISOString().slice(0, 10)}.xlsx`;
        a.click();
      });
  };

  const scoreMap = Object.fromEntries(
    (summary?.scores ?? []).map((s) => [s.framework, s])
  );
  const eternity = scoreMap["eternity"];
  const cis      = scoreMap["cis_benchmark"];
  const nist     = scoreMap["nist_csf"];
  const iso      = scoreMap["iso_27001"];

  const toggleBreakdown = (key: string) =>
    setExpandedBreakdown((prev) => (prev === key ? null : key));

  return (
    <PageWrapper title="Compliance & Governança">
      {/* ── Action bar ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-6">
        <div>
          {summary?.computed_at ? (
            <p className="text-xs text-gray-400 flex items-center gap-1">
              <Clock size={11} />
              Calculado em {fmtDate(summary.computed_at)}
            </p>
          ) : (
            <p className="text-xs text-gray-400">Nenhum score computado ainda</p>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleExport}
            disabled={!summary?.computed_at}
            className="flex items-center gap-2 border border-gray-200 hover:border-gray-300 text-gray-700 text-sm font-medium px-3 py-2 rounded-lg transition-colors disabled:opacity-40"
          >
            <FileSpreadsheet size={15} />
            Exportar Excel
          </button>
          <button
            onClick={() => compute.mutate()}
            disabled={compute.isPending}
            className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors disabled:opacity-60"
          >
            {compute.isPending
              ? <Loader2 size={15} className="animate-spin" />
              : <RefreshCw size={15} />}
            {compute.isPending ? "Calculando…" : "Computar Scores"}
          </button>
        </div>
      </div>

      {compute.isError && (
        <div className="mb-4 flex items-center gap-2 text-sm text-red-700 bg-red-50 border border-red-100 rounded-lg px-4 py-3">
          <AlertTriangle size={15} />
          Erro ao computar. Verifique se há relatórios de conformidade cadastrados.
        </div>
      )}

      {isLoading && (
        <div className="flex items-center justify-center py-24 text-gray-400">
          <Loader2 size={28} className="animate-spin mr-3" />
          Carregando painel de governança…
        </div>
      )}

      {!isLoading && !summary?.computed_at && (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <ShieldCheck size={48} className="text-gray-200 mb-4" />
          <p className="text-gray-500 font-medium mb-1">Nenhum score calculado</p>
          <p className="text-sm text-gray-400 mb-6">
            Clique em "Computar Scores" para gerar o Eternity Trust Score e os scores por framework.
          </p>
          <button
            onClick={() => compute.mutate()}
            disabled={compute.isPending}
            className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors disabled:opacity-60"
          >
            {compute.isPending ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
            {compute.isPending ? "Calculando…" : "Computar Scores"}
          </button>
        </div>
      )}

      {!isLoading && summary?.computed_at && (
        <>
          {/* ── Top row: Eternity + CIS ────────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
            {/* Eternity — destaque */}
            <div className="lg:col-span-2 bg-gradient-to-br from-brand-600 to-brand-700 rounded-xl p-6 text-white">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <p className="text-brand-100 text-sm font-medium uppercase tracking-wider">
                    Eternity Trust Score
                  </p>
                  <p className="text-xs text-brand-200 mt-0.5">Índice composto C-Level</p>
                </div>
                <TrendingUp size={20} className="text-brand-200" />
              </div>
              <div className="flex items-center gap-6">
                <div className="flex flex-col items-center justify-center w-28 h-28 rounded-full bg-white/15 border-4 border-white/30">
                  <span className="text-5xl font-black text-white">
                    {summary.eternity_score?.toFixed(0) ?? "—"}
                  </span>
                  <span className="text-sm text-brand-100 font-medium">/ 100</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-brand-100 leading-relaxed line-clamp-4">
                    {summary.narrative || "Execute 'Computar Scores' para gerar a narrativa executiva."}
                  </p>
                  {eternity && (
                    <button
                      onClick={() => toggleBreakdown("eternity")}
                      className="mt-3 flex items-center gap-1 text-xs text-brand-200 hover:text-white transition-colors"
                    >
                      {expandedBreakdown === "eternity" ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                      {expandedBreakdown === "eternity" ? "Ocultar" : "Ver"} componentes
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* CIS Benchmark */}
            <FrameworkCard
              title="CIS Benchmark"
              subtitle="Média dos servidores"
              score={summary.cis_score}
              extra={
                cis && (
                  <div className="flex flex-col gap-1.5 text-xs text-gray-500 flex-1">
                    <p>{(cis.breakdown as { server_count?: number }).server_count ?? 0} servidor(es) analisado(s)</p>
                    <button
                      onClick={() => toggleBreakdown("cis")}
                      className="text-left flex items-center gap-1 text-brand-600 hover:underline"
                    >
                      {expandedBreakdown === "cis" ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                      Histórico
                    </button>
                  </div>
                )
              }
            />
          </div>

          {/* ── Second row: NIST + ISO ─────────────────────────────────────── */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <FrameworkCard
              title="NIST CSF"
              subtitle="5 funções: Identify, Protect, Detect, Respond, Recover"
              score={summary.nist_score}
              extra={
                nist && (
                  <button
                    onClick={() => toggleBreakdown("nist")}
                    className="text-xs text-brand-600 hover:underline flex items-center gap-1"
                  >
                    {expandedBreakdown === "nist" ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                    Funções
                  </button>
                )
              }
            />
            <FrameworkCard
              title="ISO 27001"
              subtitle="Evidências das fases de hardening P1–P6"
              score={summary.iso_score}
              extra={
                iso && (
                  <button
                    onClick={() => toggleBreakdown("iso")}
                    className="text-xs text-brand-600 hover:underline flex items-center gap-1"
                  >
                    {expandedBreakdown === "iso" ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                    Controles
                  </button>
                )
              }
            />
          </div>

          {/* ── Breakdown panels ──────────────────────────────────────────── */}
          {expandedBreakdown === "eternity" && eternity && (
            <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
              <p className="text-sm font-semibold text-gray-800 mb-4">
                Eternity — Componentes do Score
              </p>
              <EternityBreakdownPanel breakdown={eternity.breakdown as unknown as EternityBreakdown} />
            </div>
          )}

          {expandedBreakdown === "nist" && nist && (
            <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
              <p className="text-sm font-semibold text-gray-800 mb-4">
                NIST CSF — Funções
              </p>
              <NistBreakdownPanel breakdown={nist.breakdown as unknown as NistBreakdown} />
            </div>
          )}

          {expandedBreakdown === "iso" && iso && (
            <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
              <p className="text-sm font-semibold text-gray-800 mb-4">
                ISO 27001 — Controles (baseado em hardening P1–P6)
              </p>
              <IsoBreakdownPanel breakdown={iso.breakdown as unknown as IsoBreakdown} />
            </div>
          )}

          {expandedBreakdown === "cis" && (
            <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
              <p className="text-sm font-semibold text-gray-800 mb-4">
                CIS Benchmark — Histórico
              </p>
              <HistoryPanel framework="cis_benchmark" />
            </div>
          )}

          {/* ── Narrative completa ────────────────────────────────────────── */}
          {summary.narrative && (
            <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
              <p className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-brand-500 inline-block" />
                Narrativa Executiva — IA
              </p>
              <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-line">
                {summary.narrative}
              </p>
            </div>
          )}

          {/* ── Histórico por framework ───────────────────────────────────── */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm font-semibold text-gray-800">Histórico de Scores</p>
              <div className="flex gap-1">
                {(["eternity", "cis_benchmark", "nist_csf", "iso_27001"] as Framework[]).map((fw) => (
                  <button
                    key={fw}
                    onClick={() => setHistoryFw((prev) => (prev === fw ? null : fw))}
                    className={`text-xs px-2.5 py-1 rounded-lg transition-colors ${
                      historyFw === fw
                        ? "bg-brand-600 text-white"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                    }`}
                  >
                    {fmtFramework(fw)}
                  </button>
                ))}
              </div>
            </div>
            {historyFw ? (
              <HistoryPanel framework={historyFw} />
            ) : (
              <p className="text-xs text-gray-400 text-center py-6">
                Selecione um framework acima para ver o histórico de scores.
              </p>
            )}
          </div>
        </>
      )}
    </PageWrapper>
  );
}
