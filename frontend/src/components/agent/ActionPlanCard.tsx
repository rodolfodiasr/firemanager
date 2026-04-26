import { CheckCircle, XCircle, Send, ShieldAlert } from "lucide-react";

interface ActionPlanCardProps {
  requiresApproval: boolean;
  onConfirm: () => void;
  onSubmitForReview: () => void;
  onCancel: () => void;
  loading: boolean;
}

export function ActionPlanCard({
  requiresApproval,
  onConfirm,
  onSubmitForReview,
  onCancel,
  loading,
}: ActionPlanCardProps) {
  if (requiresApproval) {
    return (
      <div className="border border-yellow-200 bg-yellow-50 rounded-xl p-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldAlert size={18} className="text-yellow-600 shrink-0" />
          <p className="text-sm font-medium text-yellow-800">
            Esta operação requer aprovação de um analista N2.
          </p>
        </div>
        <div className="flex gap-2 ml-4">
          <button
            onClick={onSubmitForReview}
            disabled={loading}
            className="flex items-center gap-1 px-3 py-1.5 text-sm bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 disabled:opacity-50"
          >
            <Send size={14} />
            Enviar para N2
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
          onClick={onSubmitForReview}
          disabled={loading}
          className="flex items-center gap-1 px-3 py-1.5 text-sm bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50"
        >
          <Send size={14} />
          Enviar para N2
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
