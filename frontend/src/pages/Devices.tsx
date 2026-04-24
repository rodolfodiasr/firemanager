import { useState } from "react";
import { Plus } from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { DeviceCard } from "../components/devices/DeviceCard";
import { AddDeviceModal } from "../components/devices/AddDeviceModal";
import { EditDeviceModal } from "../components/devices/EditDeviceModal";
import { ConfirmModal } from "../components/shared/ConfirmModal";
import { EmptyState } from "../components/shared/EmptyState";
import { useDevices } from "../hooks/useDevices";
import type { Device, DeviceCreate } from "../types/device";

export function Devices() {
  const { devices, isLoading, create, update, remove, healthCheck } = useDevices();
  const [showAdd, setShowAdd] = useState(false);
  const [editDevice, setEditDevice] = useState<Device | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const handleCreate = async (data: DeviceCreate) => {
    await create(data);
    setShowAdd(false);
  };

  return (
    <PageWrapper title="Dispositivos">
      <div className="flex justify-between items-center mb-6">
        <p className="text-sm text-gray-500">{devices.length} dispositivo(s) cadastrado(s)</p>
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
      ) : devices.length === 0 ? (
        <EmptyState
          title="Nenhum dispositivo cadastrado"
          description="Adicione seu primeiro firewall para começar."
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
          {devices.map((device) => (
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
