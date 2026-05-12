import { useQuery } from "@tanstack/react-query";
import { ShieldAlert, Loader2 } from "lucide-react";
import { firmwareApi } from "../../api/firmware";

export function FirmwareRiskCard() {
  const { data, isLoading } = useQuery({
    queryKey: ["firmware-risk-summary"],
    queryFn: firmwareApi.getRiskSummary,
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) {
    return (
      <div className="bg-white border rounded-xl p-5 flex items-center justify-center h-full">
        <Loader2 size={20} className="animate-spin text-gray-300" />
      </div>
    );
  }

  const hasCritical = (data?.critical_cves ?? 0) > 0;
  const hasHigh = (data?.high_cves ?? 0) > 0;
  const colorClass = hasCritical
    ? "text-red-600"
    : hasHigh
    ? "text-orange-600"
    : "text-green-600";
  const bgClass = hasCritical
    ? "bg-red-500"
    : hasHigh
    ? "bg-orange-500"
    : "bg-green-500";

  return (
    <div className="bg-white border rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-gray-500">CVEs de Firmware</span>
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${bgClass}`}>
          <ShieldAlert size={16} className="text-white" />
        </div>
      </div>
      <div className={`text-3xl font-bold ${colorClass}`}>
        {data?.total_open_cves ?? 0}
      </div>
      <div className="text-xs text-gray-400 mt-1">
        {data?.devices_with_vulns ?? 0} device(s) afetado(s)
        {hasCritical && ` · ${data!.critical_cves} crítica(s)`}
      </div>
    </div>
  );
}
