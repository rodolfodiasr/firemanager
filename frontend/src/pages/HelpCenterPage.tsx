import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Search,
  CheckCircle2,
  FlaskConical,
  Clock,
  ChevronDown,
  ChevronRight,
  Lightbulb,
  ArrowLeft,
} from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { allModules, sectionOrder, type ModuleHelp, type ModuleStatus } from "../data/helpContent";

const statusConfig: Record<ModuleStatus, { label: string; color: string; icon: typeof CheckCircle2 }> = {
  ga: { label: "Disponível", color: "bg-green-100 text-green-700", icon: CheckCircle2 },
  beta: { label: "Beta", color: "bg-indigo-100 text-indigo-700", icon: FlaskConical },
  coming_soon: { label: "Em Breve", color: "bg-gray-100 text-gray-500", icon: Clock },
};

function ModuleCard({ module, defaultOpen }: { module: ModuleHelp; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen ?? false);
  const status = statusConfig[module.status];
  const StatusIcon = status.icon;

  return (
    <div
      id={module.slug}
      className="border border-gray-200 rounded-xl bg-white overflow-hidden"
    >
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${status.color}`}>
            <StatusIcon size={11} aria-hidden="true" />
            {status.label}
          </span>
          <span className="font-medium text-gray-900 truncate">{module.title}</span>
        </div>
        {open ? (
          <ChevronDown size={16} className="text-gray-400 flex-shrink-0 ml-3" aria-hidden="true" />
        ) : (
          <ChevronRight size={16} className="text-gray-400 flex-shrink-0 ml-3" aria-hidden="true" />
        )}
      </button>

      {open && (
        <div className="px-5 pb-5 border-t border-gray-100 space-y-5">
          {/* O que faz */}
          <div className="pt-4">
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
              O que este módulo faz
            </h4>
            <p className="text-sm text-gray-700 leading-relaxed">{module.description}</p>
          </div>

          {/* Como usar */}
          <div>
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
              Como usar
            </h4>
            <ol className="space-y-2.5">
              {module.howToUse.map((step, i) => (
                <li key={i} className="flex gap-3">
                  <span className="flex-shrink-0 w-5 h-5 rounded-full bg-brand-600 text-white text-xs font-bold flex items-center justify-center mt-0.5">
                    {i + 1}
                  </span>
                  <p className="text-sm text-gray-700 leading-relaxed">{step}</p>
                </li>
              ))}
            </ol>
          </div>

          {/* Dica */}
          {module.tip && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
              <div className="flex gap-2">
                <Lightbulb size={16} className="text-amber-500 flex-shrink-0 mt-0.5" aria-hidden="true" />
                <div>
                  <p className="text-xs font-semibold text-amber-700 mb-1">Dica</p>
                  <p className="text-xs text-amber-700 leading-relaxed">{module.tip}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function HelpCenterPage() {
  const [query, setQuery] = useState("");
  const navigate = useNavigate();

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    if (!q) return null;
    return allModules.filter(
      (m) =>
        m.title.toLowerCase().includes(q) ||
        m.description.toLowerCase().includes(q) ||
        m.section.toLowerCase().includes(q) ||
        m.howToUse.some((s) => s.toLowerCase().includes(q))
    );
  }, [query]);

  const bySection = useMemo(() => {
    const map: Record<string, ModuleHelp[]> = {};
    for (const m of allModules) {
      if (!map[m.section]) map[m.section] = [];
      map[m.section].push(m);
    }
    return map;
  }, []);

  const sections = sectionOrder.filter((s) => bySection[s]);

  return (
    <PageWrapper
      title="Central de Ajuda"
      subtitle="Documentação de todos os módulos da plataforma"
    >
      {/* Search */}
      <div className="max-w-2xl mb-8">
        <div className="relative">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
            aria-hidden="true"
          />
          <input
            type="search"
            placeholder="Buscar módulo, funcionalidade ou dúvida..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent bg-white"
            aria-label="Buscar na Central de Ajuda"
          />
        </div>
      </div>

      {/* Resultados da busca */}
      {filtered !== null ? (
        <div>
          <div className="flex items-center gap-3 mb-4">
            <button
              onClick={() => setQuery("")}
              className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700"
            >
              <ArrowLeft size={14} aria-hidden="true" />
              Limpar busca
            </button>
            <span className="text-sm text-gray-500">
              {filtered.length === 0
                ? "Nenhum resultado encontrado"
                : `${filtered.length} ${filtered.length === 1 ? "resultado" : "resultados"} para "${query}"`}
            </span>
          </div>

          {filtered.length === 0 ? (
            <div className="text-center py-16">
              <Search size={40} className="text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500 text-sm">
                Nenhum módulo encontrado para "{query}".
              </p>
              <p className="text-gray-400 text-xs mt-1">
                Tente termos como "firewall", "identidade", "alertas" ou "compliance".
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {filtered.map((m) => (
                <ModuleCard key={m.slug} module={m} defaultOpen />
              ))}
            </div>
          )}
        </div>
      ) : (
        /* Listagem por seção */
        <div className="space-y-10">
          {sections.map((section) => (
            <section key={section} aria-labelledby={`section-${section}`}>
              <h2
                id={`section-${section}`}
                className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2"
              >
                {section}
                <div className="flex-1 h-px bg-gray-200" aria-hidden="true" />
              </h2>
              <div className="space-y-2">
                {bySection[section].map((m) => (
                  <ModuleCard key={m.slug} module={m} />
                ))}
              </div>
            </section>
          ))}

          {/* CTA de navegação */}
          <div className="bg-brand-50 border border-brand-200 rounded-xl p-6 text-center">
            <p className="text-sm font-medium text-brand-700 mb-1">
              Precisa de mais ajuda?
            </p>
            <p className="text-xs text-brand-600 mb-3">
              Use o Assistente IA para tirar dúvidas específicas sobre sua infraestrutura.
            </p>
            <button
              onClick={() => navigate("/assistant")}
              className="inline-flex items-center gap-2 text-sm font-medium bg-brand-600 text-white px-4 py-2 rounded-lg hover:bg-brand-700 transition-colors"
            >
              Abrir Assistente IA
            </button>
          </div>
        </div>
      )}
    </PageWrapper>
  );
}
