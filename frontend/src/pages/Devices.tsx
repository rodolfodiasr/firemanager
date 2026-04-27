import { useState } from "react";
import { Plus, Shield, Route, Network, Layers, LayoutGrid, CheckSquare, Square, Layers as LayersIcon } from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { DeviceCard } from "../components/devices/DeviceCard";
import { AddDeviceModal } from "../components/devices/AddDeviceModal";
import { EditDeviceModal } from "../components/devices/EditDeviceModal";
import { BulkOperationModal } from "../components/devices/BulkOperationModal";
import { ConfirmModal } from "../components/shared/ConfirmModal";
import { EmptyState } from "../components/shared/EmptyState";
import { useDevices } from "../hooks/useDevices";
import type { Device, DeviceCategory, DeviceCreate } from "../types/device";

type FilterCategory = DeviceCategory | "all";

const FILTER_TABS: { key: FilterCategory; label: string; icon: React.ElementType }[] = [
  { key: "all",       label: "Todos",     icon: LayoutGrid },
  { key: "firewall",  label: "Firewall",  icon: Shield },
  { key: "router",    label: "Roteador",  icon: Route },
  { key: "switch",    label: "Switch",    icon: Network },
  { key: "l3_switch", label: "Switch L3", icon: Layers },
];

export function Devices() {
  const { devices, isLoading, create, update, remove, healthCheck } = useDevices();
  const [showAdd, setShowAdd]       = useState(false);
  const [editDevice, setEditDevice] = useState<Device | null>(null);
  const [deleteId, setDeleteId]     = useState<string | null>(null);
  const [filter, setFilter]         = useState<FilterCategory>("all");

  // Multi-select state
  const [selectMode, setSelectMode]   = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [showBulk, setShowBulk]       = useState(false);

  const filtered = filter === "all"
    ? devices
    : devices.filter((d) => (d.category ?? "firewall") === filter);

  const countByCategory = (cat: DeviceCategory) =>
    devices.filter((d) => (d.category ?? "firewall") === cat).length;

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === filtered.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filtered.map((d) => d.id)));
    }
  };

  const exitSelectMode = () => {
    setSelectMode(false);
    setSelectedIds(new Set());
  };

  const selectedDevices = devices.filter((d) => selectedIds.has(d.id));

  const handleCreate = async (data: DeviceCreate) => {
    await create(data);
    setShowAdd(false);
  };

  return (
    <PageWrapper title="Dispositivos">
      {/* Tabs de filtro */}
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

      {/* Toolbar */}
      <div className="flex justify-between items-center mb-4">
        <div className="flex items-center gap-3">
          <p className="text-sm text-gray-500">
            {filtered.length} dispositivo(s)
            {filter !== "all" ? ` · ${FILTER_TABS.find(t => t.key === filter)?.label}` : ""}
          </p>

          {/* Select mode toggle */}
          {filtered.length >= 2 && (
            <button
              onClick={() => { selectMode ? exitSelectMode() : setSelectMode(true); }}
              className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border transition-colors ${
                selectMode
                  ? "bg-brand-50 border-brand-300 text-brand-700"
                  : "border-gray-200 text-gray-500 hover:border-gray-300"
              }`}
            >
              {selectMode ? <CheckSquare size={13} /> : <Square size={13} />}
              {selectMode ? "Cancelar seleção" : "Selecionar vários"}
            </button>
          )}

          {/* Select all when in select mode */}
          {selectMode && filtered.length > 0 && (
            <button
              onClick={toggleSelectAll}
              className="text-xs text-brand-600 hover:underline"
            >
              {selectedIds.size === filtered.length ? "Desmarcar todos" : "Selecionar todos"}
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Bulk action button */}
          {selectMode && selectedIds.size >= 2 && (
            <button
              onClick={() => setShowBulk(true)}
              className="flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white text-sm rounded-lg transition-colors font-medium"
            >
              <LayersIcon size={16} />
              Operação em lote ({selectedIds.size})
            </button>
          )}

          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700 transition-colors"
          >
            <Plus size={16} />
            Adicionar
          </button>
        </div>
      </div>

      {/* Selection hint */}
      {selectMode && selectedIds.size < 2 && (
        <p className="text-xs text-gray-400 mb-3">
          Selecione pelo menos 2 dispositivos para aplicar uma operação em lote.
        </p>
      )}

      {/* Device grid */}
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
            <div key={device.id} className="relative">
              {/* Checkbox overlay in select mode */}
              {selectMode && (
                <button
                  onClick={() => toggleSelect(device.id)}
                  className={`absolute top-2 right-2 z-10 w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                    selectedIds.has(device.id)
                      ? "bg-brand-600 border-brand-600"
                      : "bg-white border-gray-300 hover:border-brand-400"
                  }`}
                >
                  {selectedIds.has(device.id) && (
                    <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 12 12">
                      <path d="M10 3L5 8.5 2 5.5" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round"/>
                    </svg>
                  )}
                </button>
              )}
              <div
                className={selectedIds.has(device.id) ? "ring-2 ring-brand-500 rounded-xl" : ""}
                onClick={selectMode ? () => toggleSelect(device.id) : undefined}
              >
                <DeviceCard
                  device={device}
                  onSelect={selectMode ? () => {} : () => {}}
                  onHealthCheck={selectMode ? () => {} : healthCheck}
                  onEdit={selectMode ? () => {} : setEditDevice}
                  onDelete={selectMode ? () => {} : (id) => setDeleteId(id)}
                  isSelected={selectedIds.has(device.id)}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modals */}
      <AddDeviceModal isOpen={showAdd} onClose={() => setShowAdd(false)} onSubmit={handleCreate} />

      <BulkOperationModal
        isOpen={showBulk}
        devices={selectedDevices}
        onClose={() => setShowBulk(false)}
      />

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
        onConfirm={() => { if (deleteId) remove(deleteId); setDeleteId(null); }}
        onCancel={() => setDeleteId(null)}
        confirmLabel="Remover"
      />
    </PageWrapper>
  );
}
