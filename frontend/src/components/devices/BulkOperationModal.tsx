import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { X, Layers, Loader2, AlertCircle, Shield, Route, Network, Sparkles } from "lucide-react";
import { bulkJobsApi } from "../../api/bulk_jobs";
import type { Device, DeviceCategory } from "../../types/device";

interface BulkOperationModalProps {
  isOpen: boolean;
  devices: Device[];
  onClose: () => void;
}

const CATEGORY_LABELS: Record<string, string> = {
  firewall: "Firewall", router: "Roteador", switch: "Switch", l3_switch: "Switch L3",
};

const CATEGORY_ICON: Record<string, React.ElementType> = {
  firewall:  Shield,
  router:    Route,
  switch:    Network,
  l3_switch: Layers,
};

const VENDOR_LABELS: Record<string, string> = {
  fortinet: "Fortinet", sonicwall: "SonicWall", pfsense: "pfSense",
  opnsense: "OPNsense", mikrotik: "MikroTik", endian: "Endian",
  cisco_ios: "Cisco IOS", cisco_nxos: "Cisco NX-OS", juniper: "Juniper",
  aruba: "Aruba/HPE", ubiquiti: "Ubiquiti", dell: "DELL",
};

export function BulkOperationModal({ isOpen, devices, onClose }: BulkOperationModalProps) {
  const navigate = useNavigate();
  const [input, setInput] = useState("");

  const createMut = useMutation({
    mutationFn: () =>
      bulkJobsApi.create({
        device_ids: devices.map((d) => d.id),
        natural_language_input: input,
      }),
    onSuccess: (job) => {
      onClose();
      setInput("");
      navigate(`/bulk-jobs/${job.id}`);
    },
  });

  if (!isOpen) return null;

  // Group devices by category for display
  const byCategory = devices.reduce<Record<string, Device[]>>((acc, d) => {
    const cat = d.category ?? "firewall";
    acc[cat] = [...(acc[cat] ?? []), d];
    return acc;
  }, {});

  const categoryCount = Object.keys(byCategory).length;
  const isCrossDevice = categoryCount > 1;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-xl p-6">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <Layers size={20} className="text-brand-600" />
            <h2 className="text-lg font-semibold">Operação em Lote</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>

        {/* Cross-device callout */}
        {isCrossDevice && (
          <div className="flex items-start gap-2 bg-blue-50 border border-blue-200 rounded-xl p-3 mb-4 text-xs text-blue-800">
            <Sparkles size={13} className="mt-0.5 shrink-0 text-blue-500" />
            <span>
              <strong>Operação cross-device detectada</strong> — {categoryCount} categorias selecionadas.
              A IA gerará um plano distinto e otimizado para cada categoria.
            </span>
          </div>
        )}

        {/* Devices summary grouped by category */}
        <div className="bg-gray-50 rounded-xl p-4 mb-5 border border-gray-200">
          <p className="text-xs font-semibold text-gray-500 uppercase mb-3">
            {devices.length} dispositivos · {categoryCount} {categoryCount === 1 ? "categoria" : "categorias"}
          </p>
          {Object.entries(byCategory).map(([cat, devs]) => {
            const Icon = CATEGORY_ICON[cat as DeviceCategory] ?? Layers;
            return (
              <div key={cat} className="mb-3 last:mb-0">
                <div className="flex items-center gap-1.5 mb-1.5">
                  <Icon size={12} className="text-gray-400" />
                  <p className="text-xs font-semibold text-gray-600">
                    {CATEGORY_LABELS[cat] ?? cat}
                    <span className="font-normal text-gray-400 ml-1">({devs.length})</span>
                  </p>
                </div>
                <div className="flex flex-wrap gap-1.5 pl-4">
                  {devs.map((d) => (
                    <span key={d.id} className="text-xs bg-white border border-gray-200 rounded-lg px-2 py-0.5 text-gray-700">
                      {d.name}
                      <span className="text-gray-400 ml-1">({VENDOR_LABELS[d.vendor] ?? d.vendor})</span>
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* NL Input */}
        <div className="mb-5">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            O que deseja fazer nestes dispositivos?
          </label>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            rows={4}
            placeholder={
              isCrossDevice
                ? "Ex: Bloquear redes sociais nos firewalls e criar VLAN 100 nos switches"
                : devices[0]?.category === "switch"
                ? "Ex: Criar VLAN 100 com nome Câmeras e ativar nas portas Gi0/1 até Gi0/8"
                : "Ex: Liberar acesso HTTPS para o IP 192.168.1.50 vindo da rede interna"
            }
            className="w-full border rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
          />
          <p className="text-xs text-gray-400 mt-1">
            {isCrossDevice
              ? "A IA analisará o contexto de cada categoria e gerará comandos otimizados para cada tipo de dispositivo."
              : "A IA gerará o plano a partir do primeiro dispositivo e replicará para os demais."}
          </p>
        </div>

        {createMut.isError && (
          <p className="text-red-600 text-sm mb-4">
            {(createMut.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
              ?? "Erro ao criar o job. Tente novamente."}
          </p>
        )}

        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
          >
            Cancelar
          </button>
          <button
            onClick={() => createMut.mutate()}
            disabled={!input.trim() || createMut.isPending}
            className="flex items-center gap-2 px-4 py-2 text-sm text-white bg-brand-600 rounded-lg hover:bg-brand-700 disabled:opacity-50"
          >
            {createMut.isPending && <Loader2 size={14} className="animate-spin" />}
            {createMut.isPending ? "Processando IA..." : `Aplicar em ${devices.length} dispositivos`}
          </button>
        </div>
      </div>
    </div>
  );
}
