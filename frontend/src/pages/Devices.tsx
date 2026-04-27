import { useState } from "react";
import { Plus, Shield, Route, Network, Layers, LayoutGrid } from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { DeviceCard } from "../components/devices/DeviceCard";
import { AddDeviceModal } from "../components/devices/AddDeviceModal";
import { EditDeviceModal } from "../components/devices/EditDeviceModal";
import { ConfirmModal } from "../components/shared/ConfirmModal";
import { EmptyState } from "../components/shared/EmptyState";
import { useDevices } from "../hooks/useDevices";
import type { Device, DeviceCategory, DeviceCreate } from "../types/device";

type FilterCategory = DeviceCategory | "all";

const FILTER_TABS: { key: FilterCategory; label: string; icon: React.ElementType }[] = [
  { key: "all",      label: "Todos",      icon: LayoutGrid },
  { key: "firewall", label: "Firewall",   icon: Shield },
  { key: "router",   label: "Roteador",   icon: Route },
  { key: "switch",   label: "Switch",     icon: Network },
  { key: "l3_switch",label: "Switch L3",  icon: Layers },
];

export function Devices() {
  const { devices, isLoading, create, update, remove, healthCheck } = useDevices();
  const [showAdd, setShowAdd]     = useState(false);
  const [editDevice, setEditDevice] = useState<Device | null>(null);
  const [deleteId, setDeleteId]   = useState<string | null>(null);
  const [filter, setFilter]       = useState<FilterCategory>("all");

  const filtered = filter === "all"
    ? devices
    : devices.filter((d) => (d.category ?? "firewall") === filter);

  const countByCategory = (cat: DeviceCategory) =>
    devices.filter((d) => (d.category ?? "firewall") === cat).length;

  const handleCreate = async (data: DeviceCreate) => {
    await create(data);
    setShowAdd(false);
  };

  return (
    <PageWrapper title="Dispositivos">
      {/* Tabs de filtro por categoria */}
      <div className="flex items-center gap-1 mb-6 bg-gray-100 p-1 rounded-xl w-fit">
        {FILTER_TABS.map(({ key, label, icon: Icon }) => {
          const count = key === "all" ? devices.length : countByCategory(key as DeviceCategory);
          return (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                filter === key
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              <Icon size={14} />
              {label}
              {count > 0 && (
                <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${
                  filter === key ? "bg-brand-100 text-brand-700" : "bg-gray-200 text-gray-500"
                }`}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div className="flex justify-between items-center mb-4">
        <p className="text-sm text-gray-500">
          {filtered.length} dispositivo(s){filter !== "all" ? ` · ${FILTER_TABS.find(t => t.key === filter)?.label}` : ""}
        </p>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700 transition-colors"
        >
          <Plus size={16} />
          Adicionar
        </button>
      </div>

      {isLoading ? (
        <p className="text-sm text-gray-400">Carregando...</p>
      ) : filtered.length === 0 ? (
        <EmptyState
          title={filter === "all" ? "Nenhum dispositivo cadastrado" : `Nenhum ${FILTER_TABS.find(t => t.key === filter)?.label} cadastrado`}
          description="Adicione um dispositivo para começar."
          action={
            <button
              onClick={() => setShowAdd(true)}
              className="px-4 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700"
            >
              Adicionar dispositivo
            </button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map((device) => (
            <DeviceCard
              key={device.id}
              device={device}
              onSelect={() => {}}
              onHealthCheck={healthCheck}
              onEdit={setEditDevice}
              onDelete={(id) => setDeleteId(id)}
            />
          ))}
        </div>
      )}

      <AddDeviceModal isOpen={showAdd} onClose={() => setShowAdd(false)} onSubmit={handleCreate} />

      <EditDeviceModal
        isOpen={!!editDevice}
        device={editDevice}
        onClose={() => setEditDevice(null)}
        onSubmit={update}
      />

      <ConfirmModal
        isOpen={!!deleteId}
        title="Remover dispositivo"
        description="Tem certeza que deseja remover este dispositivo? Esta ação não pode ser desfeita."
        danger
        onConfirm={() => {
          if (deleteId) remove(deleteId);
          setDeleteId(null);
        }}
        onCancel={() => setDeleteId(null)}
        confirmLabel="Remover"
      />
    </PageWrapper>
  );
}
