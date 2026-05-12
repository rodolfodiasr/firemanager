import { ShieldAlert } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { firmwareApi } from "../../api/firmware";

const SEVERITY_STYLE: Record<string, { bg: string; text: string }> = {
  CRITICAL: { bg: "bg-red-100",    text: "text-red-700" },
  HIGH:     { bg: "bg-orange-100", text: "text-orange-700" },
  MEDIUM:   { bg: "bg-yellow-100", text: "text-yellow-700" },
  LOW:      { bg: "bg-blue-100",   text: "text-blue-700" },
  UNKNOWN:  { bg: "bg-gray-100",   text: "text-gray-500" },
};

interface FirmwareBadgeProps {
  deviceId: string;
}

export function FirmwareBadge({ deviceId }: FirmwareBadgeProps) {
  const { data } = useQuery({
    queryKey: ["firmware-summary", deviceId],
    queryFn: () => firmwareApi.getSummary(deviceId),
    staleTime: 5 * 60 * 1000,
  });

  if (!data || data.open_cves === 0) return null;

  const style = SEVERITY_STYLE[data.worst_severity] ?? SEVERITY_STYLE.UNKNOWN;

  return (
    <span
      className={`inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${style.bg} ${style.text}`}
      title={`${data.open_cves} CVE(s) aberta(s) — pior severidade: ${data.worst_severity}`}
    >
      <ShieldAlert size={10} />
      {data.open_cves} CVE{data.open_cves > 1 ? "s" : ""}
    </span>
  );
}
