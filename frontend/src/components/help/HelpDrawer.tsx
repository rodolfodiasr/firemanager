import { useEffect } from "react";
import { Link } from "react-router-dom";
import { X, CheckCircle2, FlaskConical, Clock, ChevronRight, Lightbulb } from "lucide-react";
import type { ModuleHelp } from "../../data/helpContent";

interface HelpDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  help: ModuleHelp;
}

const statusConfig = {
  ga: { label: "Disponível", color: "bg-green-100 text-green-700", icon: CheckCircle2 },
  beta: { label: "Beta", color: "bg-indigo-100 text-indigo-700", icon: FlaskConical },
  coming_soon: { label: "Em Breve", color: "bg-gray-100 text-gray-500", icon: Clock },
};

export function HelpDrawer({ isOpen, onClose, help }: HelpDrawerProps) {
  // Fecha com Escape
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  const status = statusConfig[help.status];
  const StatusIcon = status.icon;

  return (
    <>
      {/* Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/20"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Drawer */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Ajuda — ${help.title}`}
        className={`fixed right-0 top-0 h-full w-96 bg-white shadow-2xl z-50 flex flex-col transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-gray-100">
          <div className="flex-1 min-w-0 pr-3">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">
              {help.section}
            </p>
            <h2 className="text-lg font-semibold text-gray-900 leading-tight">
              {help.title}
            </h2>
            <span className={`inline-flex items-center gap-1 mt-2 text-xs font-medium px-2 py-0.5 rounded-full ${status.color}`}>
              <StatusIcon size={11} aria-hidden="true" />
              {status.label}
            </span>
          </div>
          <button
            onClick={onClose}
            aria-label="Fechar ajuda"
            className="text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg p-1.5 transition-colors flex-shrink-0"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {/* O que faz */}
          <section>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
              O que este módulo faz
            </h3>
            <p className="text-sm text-gray-700 leading-relaxed">
              {help.description}
            </p>
          </section>

          {/* Como usar */}
          <section>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
              Como usar
            </h3>
            <ol className="space-y-3">
              {help.howToUse.map((step, i) => (
                <li key={i} className="flex gap-3">
                  <span className="flex-shrink-0 w-5 h-5 rounded-full bg-brand-600 text-white text-xs font-bold flex items-center justify-center mt-0.5">
                    {i + 1}
                  </span>
                  <p className="text-sm text-gray-700 leading-relaxed">{step}</p>
                </li>
              ))}
            </ol>
          </section>

          {/* Dica */}
          {help.tip && (
            <section className="bg-amber-50 border border-amber-200 rounded-lg p-4">
              <div className="flex gap-2">
                <Lightbulb size={16} className="text-amber-500 flex-shrink-0 mt-0.5" aria-hidden="true" />
                <div>
                  <p className="text-xs font-semibold text-amber-700 mb-1">Dica</p>
                  <p className="text-xs text-amber-700 leading-relaxed">{help.tip}</p>
                </div>
              </div>
            </section>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-100 p-4">
          <Link
            to={`/help#${help.slug}`}
            onClick={onClose}
            className="flex items-center justify-between w-full text-sm text-brand-600 hover:text-brand-700 font-medium group"
          >
            <span>Ver documentação completa</span>
            <ChevronRight size={16} className="group-hover:translate-x-0.5 transition-transform" aria-hidden="true" />
          </Link>
        </div>
      </div>
    </>
  );
}
