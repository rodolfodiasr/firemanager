import { CheckCircle, XCircle } from "lucide-react";

interface ActionPlanCardProps {
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}

export function ActionPlanCard({ onConfirm, onCancel, loading }: ActionPlanCardProps) {
  return (
    <div className="border border-green-200 bg-green-50 rounded-xl p-4 flex items-center justify-between">
      <p className="text-sm font-medium text-green-800">
        Plano de ação pronto. Confirme para executar no dispositivo.
      </p>
      <div className="flex gap-2 ml-4">
        <button
          onClick={onConfirm}
          disabled={loading}
          className="flex items-center gap-1 px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
        >
          <CheckCircle size={14} />
          Executar
        </button>
        <button
          onClick={onCancel}
          disabled={loading}
          className="flex items-center gap-1 px-3 py-1.5 text-sm bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50"
        >
          <XCircle size={14} />
          Cancelar
        </button>
      </div>
    </div>
  );
}
