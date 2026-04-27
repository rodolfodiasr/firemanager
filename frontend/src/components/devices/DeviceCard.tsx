import { Shield, Route, Network, Layers, RefreshCw, Trash2, Pencil } from "lucide-react";
import type { Device, DeviceCategory } from "../../types/device";
import { HealthBadge } from "./HealthBadge";

interface DeviceCardProps {
  device: Device;
  onSelect: (id: string) => void;
  onHealthCheck: (id: string) => void;
  onEdit: (device: Device) => void;
  onDelete: (id: string) => void;
  isSelected?: boolean;
}

const CATEGORY_ICON: Record<DeviceCategory, React.ElementType> = {
  firewall:  Shield,
  router:    Route,
  switch:    Network,
  l3_switch: Layers,
};

const CATEGORY_STYLE: Record<DeviceCategory, { card: string; icon: string; badge: string }> = {
  firewall:  { card: "bg-red-50 border-red-200",    icon: "text-red-500",    badge: "bg-red-100 text-red-700" },
  router:    { card: "bg-blue-50 border-blue-200",  icon: "text-blue-500",   badge: "bg-blue-100 text-blue-700" },
  switch:    { card: "bg-green-50 border-green-200",icon: "text-green-600",  badge: "bg-green-100 text-green-700" },
  l3_switch: { card: "bg-purple-50 border-purple-200", icon: "text-purple-500", badge: "bg-purple-100 text-purple-700" },
};

const CATEGORY_LABELS: Record<DeviceCategory, string> = {
  firewall:  "Firewall",
  router:    "Roteador",
  switch:    "Switch",
  l3_switch: "Switch L3",
};

const VENDOR_LABELS: Record<string, string> = {
  fortinet:   "Fortinet",
  sonicwall:  "SonicWall",
  pfsense:    "pfSense",
  opnsense:   "OPNsense",
  mikrotik:   "MikroTik",
  endian:     "Endian",
  cisco_ios:  "Cisco IOS",
  cisco_nxos: "Cisco NX-OS",
  juniper:    "Juniper",
  aruba:      "Aruba",
  ubiquiti:   "Ubiquiti",
};

export function DeviceCard({
  device,
  onSelect,
  onHealthCheck,
  onEdit,
  onDelete,
  isSelected = false,
}: DeviceCardProps) {
  const category = device.category ?? "firewall";
  const style    = CATEGORY_STYLE[category];
  const Icon     = CATEGORY_ICON[category];

  return (
    <div
      className={`border rounded-xl p-4 cursor-pointer transition-all ${style.card} ${
        isSelected ? "ring-2 ring-brand-500" : ""
      }`}
      onClick={() => onSelect(device.id)}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon size={18} className={style.icon} />
          <div>
            <p className="font-medium text-gray-900 leading-tight">{device.name}</p>
            <p className="text-xs text-gray-500">{VENDOR_LABELS[device.vendor] ?? device.vendor}</p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <HealthBadge status={device.status} />
          <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${style.badge}`}>
            {CATEGORY_LABELS[category]}
          </span>
        </div>
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
