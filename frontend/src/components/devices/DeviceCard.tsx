import { Server, RefreshCw, Trash2, Pencil } from "lucide-react";
import type { Device } from "../../types/device";
import { HealthBadge } from "./HealthBadge";

interface DeviceCardProps {
  device: Device;
  onSelect: (id: string) => void;
  onHealthCheck: (id: string) => void;
  onEdit: (device: Device) => void;
  onDelete: (id: string) => void;
  isSelected?: boolean;
}

const vendorColors: Record<string, string> = {
  fortinet: "bg-red-50 border-red-200",
  sonicwall: "bg-blue-50 border-blue-200",
  pfsense: "bg-purple-50 border-purple-200",
  mikrotik: "bg-orange-50 border-orange-200",
  endian: "bg-green-50 border-green-200",
};

export function DeviceCard({
  device,
  onSelect,
  onHealthCheck,
  onEdit,
  onDelete,
  isSelected = false,
}: DeviceCardProps) {
  const cardColor = vendorColors[device.vendor] ?? "bg-gray-50 border-gray-200";

  return (
    <div
      className={`border rounded-xl p-4 cursor-pointer transition-all ${cardColor} ${
        isSelected ? "ring-2 ring-brand-500" : ""
      }`}
      onClick={() => onSelect(device.id)}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <Server size={18} className="text-gray-600" />
          <div>
            <p className="font-medium text-gray-900">{device.name}</p>
            <p className="text-xs text-gray-500 uppercase">{device.vendor}</p>
          </div>
        </div>
        <HealthBadge status={device.status} />
      </div>

      <div className="text-xs text-gray-500 space-y-0.5 mb-3">
        <p>{device.host}:{device.port}</p>
        {device.firmware_version && <p>v{device.firmware_version}</p>}
        {device.last_seen && (
          <p>Visto: {new Date(device.last_seen).toLocaleString("pt-BR")}</p>
        )}
      </div>

      <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
        <button
          onClick={() => onHealthCheck(device.id)}
          className="flex items-center gap-1 text-xs text-gray-600 hover:text-blue-600 transition-colors"
        >
          <RefreshCw size={12} />
          Verificar
        </button>
        <button
          onClick={() => onEdit(device)}
          className="flex items-center gap-1 text-xs text-gray-600 hover:text-brand-600 transition-colors"
        >
          <Pencil size={12} />
          Editar
        </button>
        <button
          onClick={() => onDelete(device.id)}
          className="flex items-center gap-1 text-xs text-gray-600 hover:text-red-600 transition-colors ml-auto"
        >
          <Trash2 size={12} />
          Remover
        </button>
      </div>
    </div>
  );
}
