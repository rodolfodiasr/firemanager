import { useEffect, useState } from "react";
import { X, FolderOpen, Layers, Shield, Route, Network } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { devicesApi } from "../../api/devices";
import { deviceGroupsApi } from "../../api/device_groups";
import type { DeviceGroupDetail } from "../../types/device_group";
import type { Device } from "../../types/device";

interface GroupModalProps {
  isOpen: boolean;
  group?: DeviceGroupDetail | null;
  initialDeviceIds?: string[];
  onClose: () => void;
}

const CATEGORY_ICON: Record<string, React.ElementType> = {
  firewall: Shield,
  router: Route,
  switch: Network,
  l3_switch: Layers,
};

const CATEGORY_LABEL: Record<string, string> = {
  firewall: "Firewall",
  router: "Roteador",
  switch: "Switch",
  l3_switch: "Switch L3",
};

const VENDOR_LABEL: Record<string, string> = {
  fortinet: "Fortinet", sonicwall: "SonicWall", pfsense: "pfSense",
  opnsense: "OPNsense", mikrotik: "MikroTik", endian: "Endian",
  cisco_ios: "Cisco IOS", cisco_nxos: "Cisco NX-OS", juniper: "Juniper",
  aruba: "Aruba/HPE", ubiquiti: "Ubiquiti", dell: "DELL",
};

export function GroupModal({ isOpen, group, initialDeviceIds, onClose }: GroupModalProps) {
  const qc = useQueryClient();
  const isEdit = !!group;

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const { data: allDevices = [] } = useQuery<Device[]>({
    queryKey: ["devices"],
    queryFn: devicesApi.list,
    enabled: isOpen,
  });

  useEffect(() => {
    if (!isOpen) return;
    if (group) {
      setName(group.name);
      setDescription(group.description ?? "");
      setSelectedIds(new Set(group.devices.map((d) => d.id)));
    } else {
      setName("");
      setDescription("");
      setSelectedIds(new Set(initialDeviceIds ?? []));
    }
  }, [isOpen, group, initialDeviceIds]);

  const saveMut = useMutation({
    mutationFn: () =>
      isEdit
        ? deviceGroupsApi.update(group!.id, {
            name: name.trim(),
            description: description.trim() || null,
            device_ids: [...selectedIds],
          })
        : deviceGroupsApi.create({
            name: name.trim(),
            description: description.trim() || null,
            device_ids: [...selectedIds],
          }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["device-groups"] });
      onClose();
    },
  });

  const toggle = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  if (!isOpen) return null;

  // Group available devices by category
  const byCategory = allDevices.reduce<Record<string, Device[]>>((acc, d) => {
    const cat = d.category ?? "firewall";
    acc[cat] = [...(acc[cat] ?? []), d];
    return acc;
  }, {});

  const canSave = name.trim().length > 0 && selectedIds.size >= 1;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between mb-5 shrink-0">
          <div className="flex items-center gap-2">
            <FolderOpen size={20} className="text-brand-600" />
            <h2 className="text-lg font-semibold">
              {isEdit ? "Editar Grupo" : "Novo Grupo"}
            </h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>

        <div className="overflow-y-auto flex-1 space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nome do grupo</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ex: Filial São Paulo, Data Center Norte"
              maxLength={100}
              className="w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Descrição <span className="text-gray-400 font-normal">(opcional)</span>
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Ex: Equipamentos da filial SP – andar 3"
              className="w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          {/* Device selection */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">
                Dispositivos
                <span className="text-gray-400 font-normal ml-1">({selectedIds.size} selecionados)</span>
              </label>
            </div>

            {allDevices.length === 0 ? (
              <p className="text-xs text-gray-400">Nenhum dispositivo cadastrado.</p>
            ) : (
              <div className="border rounded-xl divide-y max-h-64 overflow-y-auto">
                {Object.entries(byCategory).map(([cat, devs]) => {
                  const Icon = CATEGORY_ICON[cat] ?? Layers;
                  return (
                    <div key={cat}>
                      <div className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-50">
                        <Icon size={11} className="text-gray-400" />
                        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                          {CATEGORY_LABEL[cat] ?? cat}
                        </span>
                      </div>
                      {devs.map((d) => (
                        <label
                          key={d.id}
                          className="flex items-center gap-3 px-3 py-2 hover:bg-gray-50 cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            checked={selectedIds.has(d.id)}
                            onChange={() => toggle(d.id)}
                            className="accent-brand-600"
                          />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-800 truncate">{d.name}</p>
                            <p className="text-xs text-gray-400">{VENDOR_LABEL[d.vendor] ?? d.vendor} · {d.host}</p>
                          </div>
                        </label>
                      ))}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Error */}
        {saveMut.isError && (
          <p className="text-red-600 text-sm mt-3 shrink-0">
            {(saveMut.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
              ?? "Erro ao salvar grupo."}
          </p>
        )}

        {/* Footer */}
        <div className="flex justify-end gap-3 mt-5 shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
          >
            Cancelar
          </button>
          <button
            onClick={() => saveMut.mutate()}
            disabled={!canSave || saveMut.isPending}
            className="px-4 py-2 text-sm text-white bg-brand-600 rounded-lg hover:bg-brand-700 disabled:opacity-50"
          >
            {saveMut.isPending ? "Salvando..." : isEdit ? "Salvar alterações" : "Criar grupo"}
          </button>
        </div>
      </div>
    </div>
  );
}
