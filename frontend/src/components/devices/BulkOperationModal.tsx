import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { X, Layers, Loader2, AlertCircle } from "lucide-react";
import { bulkJobsApi } from "../../api/bulk_jobs";
import type { Device } from "../../types/device";

interface BulkOperationModalProps {
  isOpen: boolean;
  devices: Device[];
  onClose: () => void;
}

const CATEGORY_LABELS: Record<string, string> = {
  firewall: "Firewall", router: "Roteador", switch: "Switch", l3_switch: "Switch L3",
};

const VENDOR_LABELS: Record<string, string> = {
  fortinet: "Fortinet", sonicwall: "SonicWall", pfsense: "pfSense",
  opnsense: "OPNsense", mikrotik: "MikroTik", endian: "Endian",
  cisco_ios: "Cisco IOS", cisco_nxos: "Cisco NX-OS", juniper: "Juniper",
  aruba: "Aruba", ubiquiti: "Ubiquiti",
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

  const uniqueVendors = [...new Set(devices.map((d) => d.vendor))];

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

        {/* Devices summary */}
        <div className="bg-gray-50 rounded-xl p-4 mb-5 border border-gray-200">
          <p className="text-xs font-semibold text-gray-500 uppercase mb-2">
            {devices.length} dispositivos selecionados
          </p>
          {Object.entries(byCategory).map(([cat, devs]) => (
            <div key={cat} className="mb-2 last:mb-0">
              <p className="text-xs font-medium text-gray-600 mb-1">{CATEGORY_LABELS[cat] ?? cat}</p>
              <div className="flex flex-wrap gap-1.5">
                {devs.map((d) => (
                  <span key={d.id} className="text-xs bg-white border border-gray-200 rounded-lg px-2 py-0.5 text-gray-700">
                    {d.name}
                    <span className="text-gray-400 ml-1">({VENDOR_LABELS[d.vendor] ?? d.vendor})</span>
                  </span>
                ))}
              </div>
            </div>
          ))}
          {uniqueVendors.length > 1 && (
            <div className="flex items-start gap-1.5 mt-3 text-amber-700 bg-amber-50 rounded-lg p-2 text-xs">
              <AlertCircle size={13} className="mt-0.5 shrink-0" />
              <span>
                Vendors diferentes selecionados ({uniqueVendors.map(v => VENDOR_LABELS[v] ?? v).join(", ")}).
                A IA gerará o plano com base no primeiro dispositivo e replicará para os demais.
              </span>
            </div>
          )}
        </div>

        {/* NL Input */}
        <div className="mb-5">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            O que deseja fazer em todos estes dispositivos?
          </label>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            rows={4}
            placeholder={
              devices[0]?.category === "switch"
                ? "Ex: Criar VLAN 100 com nome Câmeras e ativar nas portas Gi0/1 até Gi0/8"
                : "Ex: Liberar acesso HTTPS para o IP 192.168.1.50 vindo da rede interna"
            }
            className="w-full border rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
          />
          <p className="text-xs text-gray-400 mt-1">
            A IA gerará o plano a partir do primeiro dispositivo e aplicará o mesmo nos demais.
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
