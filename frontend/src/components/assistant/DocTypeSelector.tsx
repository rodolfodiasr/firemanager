import { X, ClipboardList, Wrench, BookOpen } from "lucide-react";

type DocType = "action_plan" | "remediation" | "knowledge";

interface Props {
  onSelect: (docType: DocType) => void;
  onClose: () => void;
}

const DOC_TYPES: {
  type: DocType;
  icon: React.ReactNode;
  label: string;
  description: string;
  step: string;
  color: string;
}[] = [
  {
    type: "action_plan",
    icon: <ClipboardList size={20} />,
    label: "Plano de Ação",
    description: "Para problemas ainda não resolvidos. Documenta o que será feito, por quem e em quanto tempo.",
    step: "1 — Antes da execução",
    color: "border-blue-200 hover:border-blue-400 hover:bg-blue-50",
  },
  {
    type: "remediation",
    icon: <Wrench size={20} />,
    label: "Plano de Remediação",
    description: "Para incidentes já resolvidos e validados. Documenta causa raiz, solução aplicada e prevenção.",
    step: "2 — Após execução e validação",
    color: "border-orange-200 hover:border-orange-400 hover:bg-orange-50",
  },
  {
    type: "knowledge",
    icon: <BookOpen size={20} />,
    label: "Artigo de Conhecimento",
    description: "Documentação técnica final para a base de conhecimento. Sintoma, diagnóstico e solução consolidados.",
    step: "3 — Publicação final",
    color: "border-green-200 hover:border-green-400 hover:bg-green-50",
  },
];

export function DocTypeSelector({ onSelect, onClose }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Gerar documentação</h2>
            <p className="text-xs text-gray-500 mt-0.5">Selecione o tipo de documento a gerar desta conversa</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>

        <div className="p-4 space-y-3">
          {DOC_TYPES.map((dt) => (
            <button
              key={dt.type}
              onClick={() => onSelect(dt.type)}
              className={`w-full text-left p-4 rounded-xl border-2 transition-colors ${dt.color}`}
            >
              <div className="flex items-start gap-3">
                <div className="text-gray-600 mt-0.5 shrink-0">{dt.icon}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-gray-900">{dt.label}</span>
                    <span className="text-[10px] text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">{dt.step}</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-1 leading-relaxed">{dt.description}</p>
                </div>
              </div>
            </button>
          ))}
        </div>

        <div className="px-6 pb-4">
          <p className="text-[11px] text-gray-400 text-center">
            O ciclo recomendado é: Plano de Ação → executar → validar → Remediação → publicar → Artigo de Conhecimento
          </p>
        </div>
      </div>
    </div>
  );
}
