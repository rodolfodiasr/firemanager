import React, { useState, useMemo } from "react";
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
  Plug,
  MapPin,
  ListChecks,
  Key,
  Settings2,
  TestTube2,
  Zap,
} from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { allModules, sectionOrder, type ModuleHelp, type ModuleStatus } from "../data/helpContent";
import {
  integrationGuides,
  integrationsByCategory,
  integrationCategoryOrder,
  type IntegrationGuide,
} from "../data/integrationGuides";

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

type IntegrationSection = "prerequisites" | "credentials" | "config" | "test" | "provides";

const integrationSectionConfig: Record<IntegrationSection, { label: string; icon: typeof Plug }> = {
  prerequisites: { label: "Pré-requisitos",                    icon: ListChecks },
  credentials:   { label: "Como obter as credenciais",          icon: Key        },
  config:        { label: "Como configurar no FireManager",      icon: Settings2  },
  test:          { label: "Como testar a integração",            icon: TestTube2  },
  provides:      { label: "O que esta integração fornece",       icon: Zap        },
};

function IntegrationCard({ guide }: { guide: IntegrationGuide }) {
  const [open, setOpen]         = useState(false);
  const [activeSection, setActiveSection] = useState<IntegrationSection | null>(null);
  const status = statusConfig[guide.status];
  const StatusIcon = status.icon;

  const toggleSection = (s: IntegrationSection) =>
    setActiveSection((prev) => (prev === s ? null : s));

  return (
    <div id={guide.slug} className="border border-gray-200 rounded-xl bg-white overflow-hidden">
      {/* Header row */}
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
          <span className="font-medium text-gray-900 truncate">{guide.title}</span>
          <span className="hidden sm:inline-flex items-center gap-1 text-xs text-gray-400 flex-shrink-0">
            <MapPin size={10} aria-hidden="true" />
            {guide.configLocation}
          </span>
        </div>
        {open ? (
          <ChevronDown size={16} className="text-gray-400 flex-shrink-0 ml-3" aria-hidden="true" />
        ) : (
          <ChevronRight size={16} className="text-gray-400 flex-shrink-0 ml-3" aria-hidden="true" />
        )}
      </button>

      {open && (
        <div className="border-t border-gray-100">
          {/* Description + location */}
          <div className="px-5 py-4 bg-gray-50 border-b border-gray-100">
            <p className="text-sm text-gray-700 leading-relaxed mb-2">{guide.description}</p>
            <p className="text-xs text-gray-400 flex items-center gap-1.5">
              <MapPin size={11} aria-hidden="true" />
              <span className="font-medium">Onde configurar:</span> {guide.configLocation}
            </p>
          </div>

          {/* Subsection tabs */}
          <div className="divide-y divide-gray-100">
            {(Object.keys(integrationSectionConfig) as IntegrationSection[]).map((key) => {
              const cfg = integrationSectionConfig[key];
              const Icon = cfg.icon;
              const isOpen = activeSection === key;

              // Build content for each section
              const content: React.ReactNode = (() => {
                if (key === "prerequisites") {
                  return (
                    <ul className="space-y-1.5">
                      {guide.prerequisites.map((p, i) => (
                        <li key={i} className="flex gap-2 text-sm text-gray-700">
                          <span className="text-gray-400 mt-0.5 flex-shrink-0">•</span>
                          <span>{p}</span>
                        </li>
                      ))}
                    </ul>
                  );
                }
                if (key === "credentials") {
                  return (
                    <ol className="space-y-2">
                      {guide.credentialSteps.map((s, i) => (
                        <li key={i} className="flex gap-3 text-sm text-gray-700">
                          <span className="flex-shrink-0 w-5 h-5 rounded-full bg-indigo-600 text-white text-xs font-bold flex items-center justify-center mt-0.5">
                            {i + 1}
                          </span>
                          <span className="leading-relaxed">{s}</span>
                        </li>
                      ))}
                    </ol>
                  );
                }
                if (key === "config") {
                  return (
                    <ol className="space-y-2">
                      {guide.configSteps.map((s, i) => (
                        <li key={i} className="flex gap-3 text-sm text-gray-700">
                          <span className="flex-shrink-0 w-5 h-5 rounded-full bg-brand-600 text-white text-xs font-bold flex items-center justify-center mt-0.5">
                            {i + 1}
                          </span>
                          <span className="leading-relaxed">{s}</span>
                        </li>
                      ))}
                    </ol>
                  );
                }
                if (key === "test") {
                  return (
                    <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800 leading-relaxed">
                      {guide.testStep}
                    </div>
                  );
                }
                if (key === "provides") {
                  return (
                    <ul className="space-y-1.5">
                      {guide.provides.map((p, i) => (
                        <li key={i} className="flex gap-2 text-sm text-gray-700">
                          <Zap size={13} className="text-amber-500 mt-0.5 flex-shrink-0" aria-hidden="true" />
                          <span>{p}</span>
                        </li>
                      ))}
                    </ul>
                  );
                }
                return null;
              })();

              return (
                <div key={key}>
                  <button
                    onClick={() => toggleSection(key)}
                    aria-expanded={isOpen}
                    className="w-full flex items-center justify-between px-5 py-3 text-left hover:bg-gray-50 transition-colors"
                  >
                    <span className="flex items-center gap-2 text-xs font-semibold text-gray-600 uppercase tracking-wide">
                      <Icon size={13} aria-hidden="true" />
                      {cfg.label}
                    </span>
                    {isOpen ? (
                      <ChevronDown size={14} className="text-gray-400" aria-hidden="true" />
                    ) : (
                      <ChevronRight size={14} className="text-gray-400" aria-hidden="true" />
                    )}
                  </button>
                  {isOpen && (
                    <div className="px-5 pb-4">
                      {content}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Tip */}
          {guide.tip && (
            <div className="mx-5 mb-5 bg-amber-50 border border-amber-200 rounded-lg p-4">
              <div className="flex gap-2">
                <Lightbulb size={16} className="text-amber-500 flex-shrink-0 mt-0.5" aria-hidden="true" />
                <div>
                  <p className="text-xs font-semibold text-amber-700 mb-1">Dica</p>
                  <p className="text-xs text-amber-700 leading-relaxed">{guide.tip}</p>
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

  const filteredModules = useMemo(() => {
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

  const filteredIntegrations = useMemo(() => {
    const q = query.toLowerCase().trim();
    if (!q) return null;
    return integrationGuides.filter(
      (g) =>
        g.title.toLowerCase().includes(q) ||
        g.description.toLowerCase().includes(q) ||
        g.category.toLowerCase().includes(q) ||
        g.credentialSteps.some((s) => s.toLowerCase().includes(q)) ||
        g.configSteps.some((s) => s.toLowerCase().includes(q)) ||
        g.provides.some((s) => s.toLowerCase().includes(q))
    );
  }, [query]);

  const filtered = useMemo(() => {
    if (filteredModules === null && filteredIntegrations === null) return null;
    return { modules: filteredModules ?? [], integrations: filteredIntegrations ?? [] };
  }, [filteredModules, filteredIntegrations]);

  const bySection = useMemo(() => {
    const map: Record<string, ModuleHelp[]> = {};
    for (const m of allModules) {
      if (!map[m.section]) map[m.section] = [];
      map[m.section].push(m);
    }
    return map;
  }, []);

  const sections = sectionOrder.filter((s) => bySection[s]);

  const totalResults =
    filtered !== null
      ? filtered.modules.length + filtered.integrations.length
      : 0;

  return (
    <PageWrapper
      title="Central de Ajuda"
      subtitle="Documentação de todos os módulos e integrações da plataforma"
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
            placeholder="Buscar módulo, integração, funcionalidade ou dúvida..."
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
              {totalResults === 0
                ? "Nenhum resultado encontrado"
                : `${totalResults} ${totalResults === 1 ? "resultado" : "resultados"} para "${query}"`}
            </span>
          </div>

          {totalResults === 0 ? (
            <div className="text-center py-16">
              <Search size={40} className="text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500 text-sm">
                Nenhum resultado encontrado para "{query}".
              </p>
              <p className="text-gray-400 text-xs mt-1">
                Tente termos como "firewall", "zabbix", "identidade", "alertas" ou "compliance".
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {filtered.modules.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                    Módulos ({filtered.modules.length})
                  </h3>
                  <div className="space-y-3">
                    {filtered.modules.map((m) => (
                      <ModuleCard key={m.slug} module={m} defaultOpen />
                    ))}
                  </div>
                </div>
              )}
              {filtered.integrations.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                    Integrações ({filtered.integrations.length})
                  </h3>
                  <div className="space-y-3">
                    {filtered.integrations.map((g) => (
                      <IntegrationCard key={g.slug} guide={g} />
                    ))}
                  </div>
                </div>
              )}
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

          {/* ── Integrações ─────────────────────────────────────────────────── */}
          <section aria-labelledby="section-integrations">
            <h2
              id="section-integrations"
              className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2"
            >
              <Plug size={13} aria-hidden="true" />
              Integrações
              <div className="flex-1 h-px bg-gray-200" aria-hidden="true" />
            </h2>

            <p className="text-sm text-gray-500 mb-6 max-w-2xl">
              Guias passo a passo para configurar cada integração — como obter as credenciais no
              sistema externo e como configurar no FireManager.
            </p>

            <div className="space-y-8">
              {integrationCategoryOrder
                .filter((cat) => integrationsByCategory[cat]?.length)
                .map((cat) => (
                  <div key={cat}>
                    <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                      {cat}
                      <div className="flex-1 h-px bg-gray-100" aria-hidden="true" />
                    </h3>
                    <div className="space-y-2">
                      {integrationsByCategory[cat].map((g) => (
                        <IntegrationCard key={g.slug} guide={g} />
                      ))}
                    </div>
                  </div>
                ))}
            </div>
          </section>

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
