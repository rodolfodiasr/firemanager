import { FlaskConical, X } from "lucide-react";
import { useState } from "react";

const IS_STAGING = import.meta.env.VITE_STAGING === "true";

export function StagingBanner() {
  const [dismissed, setDismissed] = useState(false);

  if (!IS_STAGING || dismissed) return null;

  return (
    <div className="flex items-center justify-between gap-3 bg-amber-400 px-4 py-2 text-amber-900 text-sm font-medium">
      <div className="flex items-center gap-2">
        <FlaskConical size={16} className="shrink-0" />
        <span>
          <strong>AMBIENTE DE HOMOLOGAÇÃO</strong> — alterações aqui não afetam
          a produção. API compartilhada com produção.
        </span>
      </div>
      <button
        onClick={() => setDismissed(true)}
        className="shrink-0 hover:text-amber-700 transition-colors"
        aria-label="Fechar aviso de homologação"
      >
        <X size={16} />
      </button>
    </div>
  );
}
