import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ShieldAlert, RefreshCw, CheckCircle, ExternalLink, Loader2 } from "lucide-react";
import { firmwareApi, type FirmwareVulnRead, type FirmwareVersionRead } from "../../api/firmware";

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: "text-red-600 bg-red-50 border-red-200",
  HIGH:     "text-orange-600 bg-orange-50 border-orange-200",
  MEDIUM:   "text-yellow-600 bg-yellow-50 border-yellow-200",
  LOW:      "text-blue-600 bg-blue-50 border-blue-200",
  UNKNOWN:  "text-gray-500 bg-gray-50 border-gray-200",
};

interface FirmwareTabProps {
  deviceId: string;
}

function VulnRow({ vuln, onAccept }: { vuln: FirmwareVulnRead; onAccept: (v: FirmwareVulnRead) => void }) {
  const sev = vuln.cve?.severity ?? "UNKNOWN";
  const colorClass = SEVERITY_COLORS[sev] ?? SEVERITY_COLORS.UNKNOWN;
  const cvss = vuln.cve?.cvss_v3 ?? vuln.cve?.cvss_v2;

  return (
    <div className={`border rounded-lg p-4 ${colorClass}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-sm">{vuln.cve_id}</span>
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${colorClass}`}>{sev}</span>
            {cvss && <span className="text-xs text-gray-500">CVSS: {cvss.toFixed(1)}</span>}
          </div>
          <p className="text-xs text-gray-600 mt-1 line-clamp-2">{vuln.cve?.description}</p>
          <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
            <span>Versão afetada: {vuln.device_version}</span>
            <span>Detectado: {new Date(vuln.detected_at).toLocaleDateString("pt-BR")}</span>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {vuln.cve?.nvd_url && (
            <a href={vuln.cve.nvd_url} target="_blank" rel="noopener noreferrer"
              className="text-xs flex items-center gap-1 text-gray-500 hover:text-blue-600">
              <ExternalLink size={12} /> NVD
            </a>
          )}
          {vuln.status === "open" && (
            <button
              onClick={() => onAccept(vuln)}
              className="flex items-center gap-1 text-xs px-2 py-1 bg-white border rounded hover:bg-gray-50 text-gray-600"
            >
              <CheckCircle size={12} /> Aceitar risco
            </button>
          )}
          {vuln.status === "accepted" && (
            <span className="text-xs text-green-600 flex items-center gap-1">
              <CheckCircle size={12} /> Aceito
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function AcceptModal({ vuln, onClose, onSubmit }: {
  vuln: FirmwareVulnRead;
  onClose: () => void;
  onSubmit: (reason: string) => void;
}) {
  const [reason, setReason] = useState("");
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
        <h3 className="font-semibold text-gray-900 mb-1">Aceitar Risco</h3>
        <p className="text-sm text-gray-500 mb-4">{vuln.cve_id} — {vuln.cve?.severity}</p>
        <textarea
          className="w-full border rounded-lg p-3 text-sm resize-none h-24"
          placeholder="Justificativa para aceite de risco (obrigatória)..."
          value={reason}
          onChange={e => setReason(e.target.value)}
        />
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">
            Cancelar
          </button>
          <button
            disabled={reason.trim().length < 10}
            onClick={() => onSubmit(reason.trim())}
            className="px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-40"
          >
            Confirmar
          </button>
        </div>
      </div>
    </div>
  );
}

export function FirmwareTab({ deviceId }: FirmwareTabProps) {
  const qc = useQueryClient();
  const [acceptTarget, setAcceptTarget] = useState<FirmwareVulnRead | null>(null);
  const [statusFilter, setStatusFilter] = useState<"open" | "accepted">("open");
  const [refreshing, setRefreshing] = useState(false);

  const { data: summary } = useQuery({
    queryKey: ["firmware-summary", deviceId],
    queryFn: () => firmwareApi.getSummary(deviceId),
  });

  const { data: vulns, isLoading } = useQuery({
    queryKey: ["firmware-vulns", deviceId, statusFilter],
    queryFn: () => firmwareApi.getVulnerabilities(deviceId, statusFilter),
  });

  const { data: versions } = useQuery({
    queryKey: ["firmware-versions", deviceId],
    queryFn: () => firmwareApi.getVersions(deviceId),
  });

  const acceptMutation = useMutation({
    mutationFn: ({ vulnId, reason }: { vulnId: string; reason: string }) =>
      firmwareApi.acceptRisk(vulnId, reason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["firmware-vulns", deviceId] });
      qc.invalidateQueries({ queryKey: ["firmware-summary", deviceId] });
      setAcceptTarget(null);
    },
  });

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await firmwareApi.triggerRefresh(deviceId);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className="p-4 space-y-4">
      {/* Header summary */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            <ShieldAlert size={16} className="text-orange-500" /> Inteligência de Firmware
          </h3>
          {summary && (
            <p className="text-sm text-gray-500 mt-0.5">
              Versão atual: <span className="font-medium text-gray-700">{summary.current_version ?? "Desconhecida"}</span>
              {summary.open_cves > 0 && (
                <span className="ml-2 text-red-600 font-medium">
                  — {summary.open_cves} CVE{summary.open_cves > 1 ? "s" : ""} abertas
                  {summary.critical_cves > 0 && `, ${summary.critical_cves} críticas`}
                </span>
              )}
            </p>
          )}
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-1 text-xs px-3 py-1.5 border rounded-lg text-gray-600 hover:bg-gray-50 disabled:opacity-40"
        >
          <RefreshCw size={12} className={refreshing ? "animate-spin" : ""} />
          {refreshing ? "Consultando..." : "Atualizar firmware"}
        </button>
      </div>

      {/* Version history */}
      {versions && versions.length > 0 && (
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs font-medium text-gray-500 mb-2">Histórico de versões lidas</p>
          <div className="space-y-1">
            {versions.slice(0, 5).map((v: FirmwareVersionRead) => (
              <div key={v.id} className="flex items-center justify-between text-xs text-gray-600">
                <span className="font-medium">{v.version}</span>
                <span className="text-gray-400">{v.vendor_label} · {new Date(v.read_at).toLocaleString("pt-BR")}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Vulnerability list */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <button
            onClick={() => setStatusFilter("open")}
            className={`text-xs px-3 py-1 rounded-full border ${statusFilter === "open" ? "bg-red-100 text-red-700 border-red-200" : "text-gray-500 border-gray-200"}`}
          >
            Abertas {summary && summary.open_cves > 0 ? `(${summary.open_cves})` : ""}
          </button>
          <button
            onClick={() => setStatusFilter("accepted")}
            className={`text-xs px-3 py-1 rounded-full border ${statusFilter === "accepted" ? "bg-green-100 text-green-700 border-green-200" : "text-gray-500 border-gray-200"}`}
          >
            Aceitas
          </button>
        </div>

        {isLoading && <div className="flex justify-center py-8"><Loader2 className="animate-spin text-brand-600" size={20} /></div>}

        {!isLoading && (!vulns || vulns.length === 0) && (
          <div className="text-center py-8 text-sm text-gray-400">
            {statusFilter === "open"
              ? "Nenhuma vulnerabilidade aberta. Execute uma atualização de firmware para verificar."
              : "Nenhuma vulnerabilidade aceita."}
          </div>
        )}

        <div className="space-y-2">
          {vulns?.map((v: FirmwareVulnRead) => (
            <VulnRow key={v.id} vuln={v} onAccept={setAcceptTarget} />
          ))}
        </div>
      </div>

      {acceptTarget && (
        <AcceptModal
          vuln={acceptTarget}
          onClose={() => setAcceptTarget(null)}
          onSubmit={reason => acceptMutation.mutate({ vulnId: acceptTarget.id, reason })}
        />
      )}
    </div>
  );
}
