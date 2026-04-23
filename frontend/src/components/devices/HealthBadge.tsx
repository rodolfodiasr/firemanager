import type { DeviceStatus } from "../../types/device";

const config: Record<DeviceStatus, { dot: string; label: string }> = {
  online: { dot: "bg-green-500", label: "Online" },
  offline: { dot: "bg-red-500", label: "Offline" },
  unknown: { dot: "bg-gray-400", label: "Desconhecido" },
  error: { dot: "bg-orange-500", label: "Erro" },
};

interface HealthBadgeProps {
  status: DeviceStatus;
}

export function HealthBadge({ status }: HealthBadgeProps) {
  const { dot, label } = config[status];
  return (
    <span className="flex items-center gap-1.5 text-sm">
      <span className={`h-2 w-2 rounded-full ${dot} animate-pulse`} />
      {label}
    </span>
  );
}
