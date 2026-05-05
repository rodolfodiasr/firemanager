import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ClipboardCheck, Plus, Loader2, ChevronDown, ChevronUp,
  CheckCircle2, XCircle, Minus, Trash2, FileDown, AlertTriangle,
  Wifi, Server as ServerIcon, Wrench, Shield, Router,
} from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { complianceApi, networkComplianceApi } from "../api/compliance";
import { devicesApi } from "../api/devices";
import { serversApi } from "../api/servers";
import type {
  ComplianceControl, ComplianceGenerateRequest,
  ComplianceReport, ComplianceReportSummary,
} from "../types/compliance";
import type { Device } from "../types/device";

// ── Helpers ───────────────────────────────────────────────────────────────────

function scoreColor(pct: number) {
  if (pct >= 75) return { text: "text-green-600", bg: "bg-green-600", ring: "ring-green-200" };
  if (pct >= 50) return { text: "text-yellow-600", bg: "bg-yellow-500", ring: "ring-yellow-200" };
  return { text: "text-red-600", bg: "bg-red-600", ring: "ring-red-200" };
}

const RISK_BADGE: Record<string, string> = {
  critical: "bg-red-100 text-red-700",
  high:     "bg-orange-100 text-orange-700",
  medium:   "bg-yellow-100 text-yellow-700",
  low:      "bg-gray-100 text-gray-600",
};

const RESULT_ICON: Record<string, React.ReactNode> = {
  passed:         <CheckCircle2 size={13} className="text-green-500 shrink-0" />,
  failed:         <XCircle size={13} className="text-red-500 shrink-0" />,
  not_applicable: <Minus size={13} className="text-gray-300 shrink-0" />,
};

const VENDOR_LABEL: Record<string, string> = {
  fortinet:   "FortiGate",
  sonicwall:  "SonicWall",
  cisco_ios:  "Cisco IOS",
  cisco_nxos: "Cisco NX-OS",
  hp_comware: "HP Comware",
  juniper:    "Juniper",
  aruba:      "Aruba",
  dell_n:     "Dell N-Series",
  ubiquiti:   "Ubiquiti",
};

// ── Score gauge ───────────────────────────────────────────────────────────────

function ScoreGauge({ pct }: { pct: number }) {
  const col = scoreColor(pct);
  return (
    <div className={`flex flex-col items-center justify-center w-24 h-24 rounded-full ring-4 ${col.ring} bg-white`}>
      <span className={`text-2xl font-bold ${col.text}`}>{pct.toFixed(1)}%</span>
      <span className="text-xs text-gray-400">score</span>
    </div>
  );
}

// ── Control table ─────────────────────────────────────────────────────────────

type FilterTab = "all" | "failed" | "passed" | "not_applicable";

function ControlTable({ controls }: { controls: ComplianceControl[] }) {
  const [filter, setFilter] = useState<FilterTab>("failed");
  const [search, setSearch] = useState("");

  const filtered = controls.filter((c) => {
    if (filter !== "all" && c.result !== filter) return false;
    if (search && !c.title.toLowerCase().includes(search.toLowerCase()) &&
        !c.control_id.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const tabs: { key: FilterTab; label: string; count: number }[] = [
    { key: "all",            label: "Todos",  count: controls.length },
    { key: "failed",         label: "Falhou", count: controls.filter((c) => c.result === "failed").length },
    { key: "passed",         label: "Passou", count: controls.filter((c) => c.result === "passed").length },
    { key: "not_applicable", label: "N/A",    count: controls.filter((c) => c.result === "not_applicable").length },
  ];

  return (
    <div>
      <div className="flex items-center gap-4 mb-3">
        <div className="flex border border-gray-200 rounded-lg overflow-hidden">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setFilter(t.key)}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                filter === t.key
                  ? "bg-brand-600 text-white"
                  : "text-gray-500 hover:bg-gray-50"
              }`}
            >
              {t.label} ({t.count})
            </button>
          ))}
        </div>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar controle…"
          className="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-brand-400"
        />
      </div>

      <div className="border border-gray-100 rounded-lg overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-gray-50 text-gray-500 text-left">
              <th className="px-3 py-2 w-16">ID</th>
              <th className="px-3 py-2">Controle</th>
              <th className="px-3 py-2 w-20">Risco</th>
              <th className="px-3 py-2 w-16 text-center">Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-center text-gray-400">
                  Nenhum controle encontrado.
                </td>
              </tr>
            ) : (
              filtered.map((ctrl, i) => (
                <tr key={i} className="border-t border-gray-50 hover:bg-gray-50">
                  <td className="px-3 py-2 font-mono text-gray-400">{ctrl.control_id}</td>
                  <td className="px-3 py-2">
                    <p className="text-gray-800">{ctrl.title}</p>
                    {ctrl.result === "failed" && (ctrl.remediation || ctrl.evidence) && (
                      <p className="text-gray-400 mt-0.5 line-clamp-2">
                        {ctrl.evidence || ctrl.remediation}
                      </p>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <span className={`px-1.5 py-0.5 rounded-full text-xs font-medium ${RISK_BADGE[ctrl.risk_level] ?? RISK_BADGE.low}`}>
                      {ctrl.risk_level}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-center">
                    {RESULT_ICON[ctrl.result]}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Report detail ─────────────────────────────────────────────────────────────

function ReportDetail({ reportId, isNetwork = false }: { reportId: string; isNetwork?: boolean }) {
  const { data: report, isLoading } = useQuery({
    queryKey: ["compliance", reportId],
    queryFn: () => (isNetwork ? networkComplianceApi.get(reportId) : complianceApi.get(reportId)),
  });

  const [remediatingIdx, setRemediatingIdx] = useState<number | "all" | null>(null);
  const [remediatedIdxs, setRemediatedIdxs] = useState<Set<number | "all">>(new Set());
  const [remediateError, setRemediateError] = useState<string>("");
  const [controlsRemediating, setControlsRemediating] = useState(false);
  const [controlsRemediated, setControlsRemediated] = useState(false);
  const [controlsPlansCount, setControlsPlansCount] = useState(0);
  const [controlsError, setControlsError] = useState("");

  const remediateMutation = useMutation({
    mutationFn: ({ idx }: { idx: number | "all" }) =>
      complianceApi.remediate(reportId, idx === "all" ? undefined : idx),
    onMutate: ({ idx }) => { setRemediatingIdx(idx); setRemediateError(""); },
    onSuccess: (_, { idx }) => {
      setRemediatingIdx(null);
      setRemediatedIdxs((prev) => new Set([...prev, idx]));
    },
    onError: (err: unknown, { idx }) => {
      setRemediatingIdx(null);
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setRemediateError(detail ?? "Erro ao criar remediação");
      setRemediatedIdxs((prev) => { const s = new Set(prev); s.delete(idx); return s; });
    },
  });

  const remediateControlsMutation = useMutation({
    mutationFn: () => complianceApi.remediateControls(reportId),
    onMutate: () => { setControlsRemediating(true); setControlsError(""); },
    onSuccess: (plans) => {
      setControlsRemediating(false);
      setControlsRemediated(true);
      setControlsPlansCount(plans.length);
    },
    onError: (err: unknown) => {
      setControlsRemediating(false);
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setControlsError(detail ?? "Erro ao criar remediações");
    },
  });

  const handleExport = () => {
    if (!report) return;
    const url = complianceApi.exportPdfUrl(reportId);
    const token = localStorage.getItem("access_token") ?? "";
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `compliance_${report.created_at.slice(0, 10)}.pdf`;
        a.click();
      });
  };

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-8 text-gray-400 text-sm">
        <Loader2 size={16} className="animate-spin" /> Carregando…
      </div>
    );
  }
  if (!report) return null;

  const hasRecs = report.ai_recommendations.length > 0;

  return (
    <div className="space-y-6 pt-4">
      {/* Score + counters */}
      <div className="flex items-center gap-6">
        <ScoreGauge pct={report.score_pct} />
        <div className="flex gap-4">
          <div className="text-center">
            <p className="text-2xl font-bold text-green-600">{report.passed}</p>
            <p className="text-xs text-gray-500">Passou</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-red-500">{report.failed}</p>
            <p className="text-xs text-gray-500">Falhou</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-gray-400">{report.not_applicable}</p>
            <p className="text-xs text-gray-500">N/A</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-gray-700">{report.total_checks}</p>
            <p className="text-xs text-gray-500">Total</p>
          </div>
        </div>
        <div className="flex-1" />
        <button
          onClick={handleExport}
          className="flex items-center gap-1.5 text-sm text-brand-600 hover:text-brand-800 font-medium"
        >
          <FileDown size={15} /> Exportar PDF
        </button>
      </div>

      {/* AI Summary */}
      {report.ai_summary && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            Resumo executivo (IA)
          </p>
          <div className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 text-sm text-gray-700 whitespace-pre-wrap">
            {report.ai_summary}
          </div>
        </div>
      )}

      {/* Recommendations + remediation (server reports only) */}
      {!isNetwork && hasRecs && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Recomendações prioritárias
            </p>
            <button
              disabled={remediatingIdx !== null || remediatedIdxs.has("all")}
              onClick={() => remediateMutation.mutate({ idx: "all" })}
              className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border border-brand-300 text-brand-700 hover:bg-brand-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {remediatingIdx === "all" ? (
                <><Loader2 size={12} className="animate-spin" /> Gerando…</>
              ) : remediatedIdxs.has("all") ? (
                <><CheckCircle2 size={12} className="text-green-500" /> Remediações criadas</>
              ) : (
                <><Wrench size={12} /> Remediar todas ({report.ai_recommendations.length})</>
              )}
            </button>
          </div>

          {remediateError && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-2">
              {remediateError}
            </p>
          )}

          <div className="space-y-2">
            {report.ai_recommendations.map((rec, i) => {
              const isDone = remediatedIdxs.has(i) || remediatedIdxs.has("all");
              const isLoadingRec = remediatingIdx === i;
              const isAnyLoading = remediatingIdx !== null;

              return (
                <div key={i} className="border border-gray-100 rounded-lg px-4 py-3">
                  <div className="flex items-start gap-2 mb-1">
                    <span className="bg-brand-600 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center shrink-0 mt-0.5">
                      {rec.priority}
                    </span>
                    <span className="text-sm font-medium text-gray-800 flex-1">{rec.title}</span>
                    <button
                      disabled={isAnyLoading || isDone}
                      onClick={() => remediateMutation.mutate({ idx: i })}
                      className="flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-lg border border-gray-200 text-gray-600 hover:border-brand-300 hover:text-brand-700 hover:bg-brand-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shrink-0"
                    >
                      {isLoadingRec ? (
                        <><Loader2 size={11} className="animate-spin" /> Gerando…</>
                      ) : isDone ? (
                        <><CheckCircle2 size={11} className="text-green-500" /> Criada</>
                      ) : (
                        <><Wrench size={11} /> Remediar</>
                      )}
                    </button>
                  </div>
                  <p className="text-xs text-gray-500 mb-2 pl-7">{rec.description}</p>
                  {rec.remediation_steps && (
                    <pre className="bg-gray-900 text-green-400 text-xs rounded px-3 py-2 overflow-x-auto font-mono whitespace-pre-wrap">
                      {rec.remediation_steps}
                    </pre>
                  )}
                </div>
              );
            })}
          </div>

          {remediatedIdxs.size > 0 && (
            <p className="text-xs text-green-600 bg-green-50 border border-green-200 rounded-lg px-3 py-2 mt-2">
              Remediações criadas — acesse{" "}
              <a href="/remediation" className="underline font-medium">Remediações</a>{" "}
              para revisar e executar.
            </p>
          )}
        </div>
      )}

      {/* Network device AI recommendations (read-only, no automated remediation) */}
      {isNetwork && hasRecs && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            Recomendações prioritárias (IA)
          </p>
          <div className="space-y-2">
            {report.ai_recommendations.map((rec, i) => (
              <div key={i} className="border border-gray-100 rounded-lg px-4 py-3">
                <div className="flex items-start gap-2 mb-1">
                  <span className="bg-orange-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center shrink-0 mt-0.5">
                    {rec.priority}
                  </span>
                  <span className="text-sm font-medium text-gray-800">{rec.title}</span>
                </div>
                <p className="text-xs text-gray-500 mb-2 pl-7">{rec.description}</p>
                {rec.remediation_steps && (
                  <pre className="bg-gray-900 text-green-400 text-xs rounded px-3 py-2 overflow-x-auto font-mono whitespace-pre-wrap">
                    {rec.remediation_steps}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Controls */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Controles ({report.total_checks})
          </p>
          {!isNetwork && report.failed > 0 && (
            <button
              disabled={controlsRemediating || controlsRemediated}
              onClick={() => {
                if (confirm(
                  `Isso vai criar planos de remediação para os ${report.failed} controles falhos.\n\nContinuar?`
                )) {
                  remediateControlsMutation.mutate();
                }
              }}
              className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border border-orange-300 text-orange-700 hover:bg-orange-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {controlsRemediating ? (
                <><Loader2 size={12} className="animate-spin" /> Gerando planos…</>
              ) : controlsRemediated ? (
                <><CheckCircle2 size={12} className="text-green-500" /> {controlsPlansCount} planos criados</>
              ) : (
                <><Wrench size={12} /> Remediar todos os falhos ({report.failed})</>
              )}
            </button>
          )}
        </div>

        {controlsError && (
          <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-2">
            {controlsError}
          </p>
        )}
        {controlsRemediating && (
          <div className="text-xs text-orange-600 bg-orange-50 border border-orange-200 rounded-lg px-3 py-2 mb-2 flex items-center gap-2">
            <Loader2 size={12} className="animate-spin shrink-0" />
            Gerando planos de remediação via IA…
          </div>
        )}
        {controlsRemediated && (
          <div className="text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2 mb-2">
            <strong>{controlsPlansCount} planos criados</strong> — acesse{" "}
            <a href="/remediation" className="underline font-medium">Remediações</a>{" "}
            para revisar.
          </div>
        )}

        <ControlTable controls={report.controls} />
      </div>
    </div>
  );
}

// ── Server generate form ──────────────────────────────────────────────────────

function ServerGenerateForm({ onDone }: { onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [serverId, setServerId] = useState("");
  const [forceSource, setForceSource] = useState<"" | "wazuh" | "ssh">("");
  const [error, setError] = useState("");

  const { data: servers = [] } = useQuery({ queryKey: ["servers"], queryFn: serversApi.list });
  const linuxServers = servers.filter((s) => s.os_type === "linux");
  const windowsServers = servers.filter((s) => s.os_type === "windows");
  const selectedServer = servers.find((s) => s.id === serverId);
  const isWindows = selectedServer?.os_type === "windows";

  const qc = useQueryClient();
  const generate = useMutation({
    mutationFn: (req: ComplianceGenerateRequest) => complianceApi.generate(req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["compliance-server"] });
      setServerId(""); setForceSource(""); setOpen(false); setError(""); onDone();
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? "Erro desconhecido");
    },
  });

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
      >
        <Plus size={16} /> Novo relatório
      </button>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
      <h3 className="font-semibold text-gray-900 mb-4">Gerar relatório CIS Benchmark</h3>
      <div className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Servidor</label>
          <select
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
            value={serverId}
            onChange={(e) => { setServerId(e.target.value); setForceSource(""); }}
          >
            <option value="">Selecione um servidor…</option>
            {linuxServers.length > 0 && (
              <optgroup label="Linux — SSH">
                {linuxServers.map((s) => (
                  <option key={s.id} value={s.id}>{s.name} ({s.host})</option>
                ))}
              </optgroup>
            )}
            {windowsServers.length > 0 && (
              <optgroup label="Windows — WinRM">
                {windowsServers.map((s) => (
                  <option key={s.id} value={s.id}>{s.name} ({s.host})</option>
                ))}
              </optgroup>
            )}
          </select>
          {linuxServers.length === 0 && windowsServers.length === 0 && (
            <p className="text-xs text-amber-600 mt-1">Nenhum servidor cadastrado.</p>
          )}
        </div>

        {!isWindows && (
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Fonte de dados</label>
            <select
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
              value={forceSource}
              onChange={(e) => setForceSource(e.target.value as "" | "wazuh" | "ssh")}
            >
              <option value="">Automático (Wazuh se disponível, SSH como fallback)</option>
              <option value="wazuh">Forçar Wazuh SCA</option>
              <option value="ssh">Forçar SSH</option>
            </select>
          </div>
        )}

        {isWindows && (
          <p className="text-xs text-blue-600 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2">
            Servidor Windows: coleta via WinRM + análise CIS Windows Server Benchmark L1.
          </p>
        )}

        {error && (
          <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
            {error}
          </p>
        )}

        <div className="flex gap-2 justify-end">
          <button
            onClick={() => { setOpen(false); setError(""); }}
            className="text-sm text-gray-500 px-4 py-2 rounded-lg hover:bg-gray-100 transition-colors"
          >
            Cancelar
          </button>
          <button
            disabled={!serverId || generate.isPending}
            onClick={() =>
              generate.mutate({
                server_id: serverId,
                force_source: isWindows ? undefined : (forceSource || undefined),
              })
            }
            className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            {generate.isPending
              ? <><Loader2 size={14} className="animate-spin" /> Analisando…</>
              : <><ClipboardCheck size={14} /> Gerar relatório</>}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Network device generate form ──────────────────────────────────────────────

function NetworkGenerateForm({
  deviceType,
  onDone,
}: {
  deviceType: "firewall" | "switch";
  onDone: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [deviceId, setDeviceId] = useState("");
  const [error, setError] = useState("");

  const { data: devices = [] } = useQuery({ queryKey: ["devices"], queryFn: devicesApi.list });
  const filtered = devices.filter((d: Device) => {
    if (deviceType === "firewall") return d.category === "firewall";
    return ["switch", "routing", "l3_switch", "router"].includes(d.category);
  });

  const qc = useQueryClient();
  const generate = useMutation({
    mutationFn: (req: { device_id: string }) => networkComplianceApi.generate(req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["compliance-network"] });
      setDeviceId(""); setOpen(false); setError(""); onDone();
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? "Erro desconhecido");
    },
  });

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
      >
        <Plus size={16} /> Novo relatório
      </button>
    );
  }

  const typeLabel = deviceType === "firewall" ? "Firewall" : "Switch / Roteador";

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
      <h3 className="font-semibold text-gray-900 mb-4">
        Gerar relatório de conformidade — {typeLabel}
      </h3>
      <div className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">{typeLabel}</label>
          <select
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
            value={deviceId}
            onChange={(e) => setDeviceId(e.target.value)}
          >
            <option value="">Selecione um dispositivo…</option>
            {filtered.map((d: Device) => (
              <option key={d.id} value={d.id}>
                {d.name} — {VENDOR_LABEL[d.vendor] ?? d.vendor} ({d.host})
              </option>
            ))}
          </select>
          {filtered.length === 0 && (
            <p className="text-xs text-amber-600 mt-1">
              Nenhum {typeLabel.toLowerCase()} cadastrado.
            </p>
          )}
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-lg px-3 py-2">
          <p className="text-xs text-blue-700">
            <strong>Checks incluídos:</strong>{" "}
            {deviceType === "firewall"
              ? "SNMP communities, TLS, HTTPS mgmt, NTP, Syslog, regras any→any, logging de regras, contas admin, política de senha."
              : "SNMP communities, SSH v2, NTP, Syslog, timeout de VTY, política de senha, Telnet desabilitado."}
          </p>
        </div>

        {error && (
          <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
            {error}
          </p>
        )}

        <div className="flex gap-2 justify-end">
          <button
            onClick={() => { setOpen(false); setError(""); }}
            className="text-sm text-gray-500 px-4 py-2 rounded-lg hover:bg-gray-100 transition-colors"
          >
            Cancelar
          </button>
          <button
            disabled={!deviceId || generate.isPending}
            onClick={() => generate.mutate({ device_id: deviceId })}
            className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            {generate.isPending
              ? <><Loader2 size={14} className="animate-spin" /> Analisando…</>
              : <><Shield size={14} /> Gerar relatório</>}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Server report card ────────────────────────────────────────────────────────

function ServerReportCard({
  summary,
  serverName,
}: {
  summary: ComplianceReportSummary;
  serverName: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const qc = useQueryClient();
  const col = scoreColor(summary.score_pct);

  const remove = useMutation({
    mutationFn: () => complianceApi.remove(summary.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["compliance-server"] }),
  });

  const SourceIcon = summary.source === "wazuh" ? Wifi : ServerIcon;
  const sourceLabel =
    summary.source === "wazuh" ? "Wazuh SCA" :
    summary.source === "winrm" ? "WinRM" : "SSH";

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div
        className="flex items-center gap-4 px-5 py-4 cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className={`shrink-0 text-lg font-bold ${col.text} w-14 text-center`}>
          {summary.score_pct.toFixed(0)}%
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium text-gray-900 truncate">{serverName}</p>
            <span className="flex items-center gap-1 text-xs text-gray-400 shrink-0">
              <SourceIcon size={11} /> {sourceLabel}
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-0.5">
            {summary.policy_name} · {new Date(summary.created_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}
          </p>
        </div>
        <div className="flex gap-3 shrink-0">
          <span className="flex items-center gap-1 text-xs text-green-600">
            <CheckCircle2 size={12} /> {summary.passed}
          </span>
          <span className="flex items-center gap-1 text-xs text-red-500">
            <XCircle size={12} /> {summary.failed}
          </span>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (confirm("Remover relatório?")) remove.mutate();
          }}
          disabled={remove.isPending}
          className="shrink-0 text-gray-300 hover:text-red-500 transition-colors disabled:opacity-40"
        >
          <Trash2 size={14} />
        </button>
        {expanded
          ? <ChevronUp size={16} className="text-gray-400 shrink-0" />
          : <ChevronDown size={16} className="text-gray-400 shrink-0" />}
      </div>
      {expanded && (
        <div className="px-5 pb-6 border-t border-gray-100">
          <ReportDetail reportId={summary.id} isNetwork={false} />
        </div>
      )}
    </div>
  );
}

// ── Network report card ───────────────────────────────────────────────────────

function NetworkReportCard({
  summary,
  deviceName,
}: {
  summary: ComplianceReportSummary;
  deviceName: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const qc = useQueryClient();
  const col = scoreColor(summary.score_pct);

  const remove = useMutation({
    mutationFn: () => networkComplianceApi.remove(summary.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["compliance-network"] }),
  });

  const sourceLabel = summary.source === "rest" ? "REST API" : "SSH";
  const SourceIcon = summary.source === "rest" ? Shield : Router;

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div
        className="flex items-center gap-4 px-5 py-4 cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className={`shrink-0 text-lg font-bold ${col.text} w-14 text-center`}>
          {summary.score_pct.toFixed(0)}%
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium text-gray-900 truncate">{deviceName}</p>
            <span className="flex items-center gap-1 text-xs text-gray-400 shrink-0">
              <SourceIcon size={11} /> {sourceLabel}
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-0.5">
            {summary.policy_name} · {new Date(summary.created_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}
          </p>
        </div>
        <div className="flex gap-3 shrink-0">
          <span className="flex items-center gap-1 text-xs text-green-600">
            <CheckCircle2 size={12} /> {summary.passed}
          </span>
          <span className="flex items-center gap-1 text-xs text-red-500">
            <XCircle size={12} /> {summary.failed}
          </span>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (confirm("Remover relatório?")) remove.mutate();
          }}
          disabled={remove.isPending}
          className="shrink-0 text-gray-300 hover:text-red-500 transition-colors disabled:opacity-40"
        >
          <Trash2 size={14} />
        </button>
        {expanded
          ? <ChevronUp size={16} className="text-gray-400 shrink-0" />
          : <ChevronDown size={16} className="text-gray-400 shrink-0" />}
      </div>
      {expanded && (
        <div className="px-5 pb-6 border-t border-gray-100">
          <ReportDetail reportId={summary.id} isNetwork={true} />
        </div>
      )}
    </div>
  );
}

// ── Servers tab ───────────────────────────────────────────────────────────────

function ServersTab() {
  const { data: reports = [], isLoading } = useQuery({
    queryKey: ["compliance-server"],
    queryFn: complianceApi.list,
    select: (data) => data.filter((r) => r.device_id === null),
  });

  const { data: servers = [] } = useQuery({
    queryKey: ["servers"],
    queryFn: serversApi.list,
  });

  const serverMap = Object.fromEntries(servers.map((s) => [s.id, s.name]));

  return (
    <div>
      <div className="flex items-start justify-between mb-6">
        <p className="text-sm text-gray-500 max-w-xl">
          Relatórios CIS Benchmark gerados via Wazuh SCA, SSH (Linux) ou WinRM (Windows).
        </p>
        <ServerGenerateForm onDone={() => {}} />
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-gray-400">
          <Loader2 size={24} className="animate-spin mx-auto mb-2" />
          Carregando relatórios…
        </div>
      ) : reports.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <ClipboardCheck size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">Nenhum relatório gerado ainda.</p>
          <p className="text-xs mt-1">Clique em "Novo relatório" para iniciar uma análise CIS Benchmark.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {reports.map((r) => (
            <ServerReportCard
              key={r.id}
              summary={r}
              serverName={serverMap[r.server_id ?? ""] ?? r.server_id ?? r.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Network tab (shared by Firewalls + Switches) ──────────────────────────────

function NetworkTab({ deviceType }: { deviceType: "firewall" | "switch" }) {
  const { data: reports = [], isLoading } = useQuery({
    queryKey: ["compliance-network", deviceType],
    queryFn: () => networkComplianceApi.list(deviceType),
  });

  const { data: devices = [] } = useQuery({
    queryKey: ["devices"],
    queryFn: devicesApi.list,
  });

  const deviceMap = Object.fromEntries((devices as Device[]).map((d) => [d.id, d.name]));

  const typeLabel = deviceType === "firewall" ? "Firewalls" : "Switches / Roteadores";

  return (
    <div>
      <div className="flex items-start justify-between mb-6">
        <p className="text-sm text-gray-500 max-w-xl">
          Checks de conformidade CIS para {typeLabel.toLowerCase()} — SNMP, SSH, NTP, Syslog, regras e políticas.
        </p>
        <NetworkGenerateForm deviceType={deviceType} onDone={() => {}} />
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-gray-400">
          <Loader2 size={24} className="animate-spin mx-auto mb-2" />
          Carregando relatórios…
        </div>
      ) : reports.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <AlertTriangle size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">Nenhum relatório para {typeLabel.toLowerCase()}.</p>
          <p className="text-xs mt-1">Clique em "Novo relatório" para executar os checks.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {reports.map((r) => (
            <NetworkReportCard
              key={r.id}
              summary={r}
              deviceName={deviceMap[r.device_id ?? ""] ?? r.device_id ?? r.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type MainTab = "servers" | "firewalls" | "switches";

export function Compliance() {
  const [activeTab, setActiveTab] = useState<MainTab>("servers");

  const tabs: { key: MainTab; label: string; icon: React.ReactNode }[] = [
    { key: "servers",   label: "Servidores",  icon: <ServerIcon size={14} /> },
    { key: "firewalls", label: "Firewalls",   icon: <Shield size={14} /> },
    { key: "switches",  label: "Switches",    icon: <Router size={14} /> },
  ];

  return (
    <PageWrapper title="Conformidade CIS">
      <div className="max-w-4xl mx-auto">
        {/* Tab bar */}
        <div className="flex border-b border-gray-200 mb-6">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              className={`flex items-center gap-1.5 px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === t.key
                  ? "border-brand-600 text-brand-700"
                  : "border-transparent text-gray-500 hover:text-gray-800 hover:border-gray-300"
              }`}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>

        {activeTab === "servers"   && <ServersTab />}
        {activeTab === "firewalls" && <NetworkTab deviceType="firewall" />}
        {activeTab === "switches"  && <NetworkTab deviceType="switch" />}
      </div>
    </PageWrapper>
  );
}
