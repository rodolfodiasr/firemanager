import { useState, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Play, Search, X } from "lucide-react";
import toast from "react-hot-toast";
import { glpiApi } from "../../api/glpi";
import { devicesApi } from "../../api/devices";
import type { GlpiAnalysisListItem } from "../../types/glpi";

interface RunAnalysisModalProps {
  analysis: GlpiAnalysisListItem;
  onClose: () => void;
}

export function RunAnalysisModal({ analysis, onClose }: RunAnalysisModalProps) {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const { data: devices = [], isLoading: loadingDevices } = useQuery({
    queryKey: ["devices"],
    queryFn: devicesApi.list,
  });

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    if (!q) return devices;
    return devices.filter(
      (d) =>
        d.name.toLowerCase().includes(q) ||
        d.host.toLowerCase().includes(q) ||
        d.vendor.toLowerCase().includes(q)
    );
  }, [devices, search]);

  const runMut = useMutation({
    mutationFn: () => glpiApi.runAnalysis(analysis.id, Array.from(selectedIds)),
    onSuccess: () => {
      toast.success("Análise iniciada. O resultado aparecerá em instantes.");
      qc.invalidateQueries({ queryKey: ["glpi-analyses"] });
      onClose();
    },
    onError: () => toast.error("Falha ao iniciar análise"),
  });

  function toggleDevice(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg p-6 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="min-w-0 pr-3">
            <h2 className="text-base font-semibold text-gray-900">Analisar ticket</h2>
            <p className="text-xs text-gray-500 mt-0.5 truncate">
              #{analysis.glpi_ticket_id} — {analysis.glpi_ticket_title}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 shrink-0">
            <X size={18} />
          </button>
        </div>

        {/* Explanation */}
        <p className="text-sm text-gray-600 mb-4">
          Selecione os dispositivos relacionados ao ticket para que o FireManager busque logs do
          Zabbix, Wazuh e SSH antes de chamar a IA.{" "}
          <span className="text-gray-400">Deixe em branco para analisar só com o conteúdo do ticket.</span>
        </p>

        {/* Search */}
        <div className="relative mb-3">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filtrar dispositivos..."
            className="w-full pl-9 pr-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        {/* Device list */}
        <div className="flex-1 overflow-y-auto border rounded-lg divide-y divide-gray-100 min-h-0 mb-4">
          {loadingDevices ? (
            <div className="flex items-center justify-center py-8 text-gray-400 gap-2">
              <Loader2 size={16} className="animate-spin" />
              <span className="text-sm">Carregando dispositivos...</span>
            </div>
          ) : filtered.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-6">
              {search ? "Nenhum dispositivo encontrado" : "Nenhum dispositivo cadastrado"}
            </p>
          ) : (
            filtered.map((d) => {
              const checked = selectedIds.has(d.id);
              return (
                <label
                  key={d.id}
                  className={`flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors ${checked ? "bg-brand-50" : ""}`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleDevice(d.id)}
                    className="rounded accent-brand-600"
                  />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate">{d.name}</p>
                    <p className="text-xs text-gray-400">{d.host} · {d.vendor}</p>
                  </div>
                </label>
              );
            })
          )}
        </div>

        {/* Selection count */}
        {selectedIds.size > 0 && (
          <p className="text-xs text-brand-600 font-medium mb-3">
            {selectedIds.size} dispositivo{selectedIds.size > 1 ? "s" : ""} selecionado{selectedIds.size > 1 ? "s" : ""}
          </p>
        )}

        {/* Footer */}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={() => runMut.mutate()}
            disabled={runMut.isPending}
            className="flex items-center gap-2 px-4 py-2 text-sm text-white bg-brand-600 rounded-lg hover:bg-brand-700 disabled:opacity-50"
          >
            {runMut.isPending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Play size={14} />
            )}
            {selectedIds.size === 0 ? "Analisar sem dispositivos" : "Analisar"}
          </button>
        </div>
      </div>
    </div>
  );
}
