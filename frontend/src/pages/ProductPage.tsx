import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  productApi,
  type BillingInvoice,
  type BillingPlan,
  type HelpArticle,
  type OnboardingChecklist,
} from "../api/product";
import {
  Coins, BookOpen, Settings, CheckCircle, Circle, CreditCard,
  FileText, Globe, ArrowRight, Sparkles, ExternalLink, Download,
} from "lucide-react";

type Tab = "billing" | "onboarding" | "help" | "preferences";

export function ProductPage() {
  const [tab, setTab] = useState<Tab>("billing");

  const tabs: { id: Tab; label: string; icon: React.ComponentType<{ size?: number | string }> }[] = [
    { id: "billing", label: "Billing & Planos", icon: Coins },
    { id: "onboarding", label: "Onboarding", icon: Sparkles },
    { id: "help", label: "Central de Ajuda", icon: BookOpen },
    { id: "preferences", label: "Preferências", icon: Settings },
  ];

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Produto & UX</h1>
        <p className="text-gray-400 text-sm mt-1">Billing, planos, onboarding, documentação e preferências</p>
      </div>

      <div className="flex gap-2 border-b border-gray-700">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === id
                ? "border-brand-500 text-brand-400"
                : "border-transparent text-gray-400 hover:text-white"
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {tab === "billing" && <BillingTab />}
      {tab === "onboarding" && <OnboardingTab />}
      {tab === "help" && <HelpTab />}
      {tab === "preferences" && <PreferencesTab />}
    </div>
  );
}

// ── Billing Tab ───────────────────────────────────────────────────────────────

function BillingTab() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);

  const { data: plans = [] } = useQuery({ queryKey: ["billing-plans"], queryFn: productApi.listPlans });
  const { data: subscription } = useQuery({ queryKey: ["billing-subscription"], queryFn: productApi.getSubscription });
  const { data: invoices = [] } = useQuery({ queryKey: ["billing-invoices"], queryFn: productApi.listInvoices });

  const seedMut = useMutation({
    mutationFn: productApi.seedPlans,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["billing-plans"] }),
  });

  const startMut = useMutation({
    mutationFn: (slug: string) => productApi.startSubscription(slug),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["billing-subscription"] }),
  });

  const handleUpgrade = async (plan: BillingPlan) => {
    setCheckoutLoading(plan.id);
    try {
      const successUrl = `${window.location.origin}/billing?success=1`;
      const cancelUrl = `${window.location.origin}/billing?canceled=1`;
      const { checkout_url } = await productApi.createCheckout(plan.id, successUrl, cancelUrl);
      window.location.href = checkout_url;
    } catch (err) {
      console.error("Erro ao iniciar checkout Stripe:", err);
    } finally {
      setCheckoutLoading(null);
    }
  };

  const planBadge: Record<string, string> = {
    starter: "bg-gray-700 text-gray-300",
    pro: "bg-brand-900/50 text-brand-300",
    enterprise: "bg-purple-900/50 text-purple-300",
  };

  return (
    <div className="space-y-6">
      {subscription && (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-5 space-y-2">
          <div className="flex items-center gap-3">
            <CreditCard size={18} className="text-brand-400" />
            <span className="font-semibold text-white">{t("billing.current_plan")}: {subscription.plan.name}</span>
            <span className={`text-xs px-2 py-0.5 rounded ${planBadge[subscription.plan.slug] || "bg-gray-700 text-gray-300"}`}>{subscription.status}</span>
          </div>
          <div className="grid grid-cols-3 gap-4 mt-3 text-sm">
            <div className="text-center">
              <p className="text-2xl font-bold text-white">R$ {Number(subscription.plan.monthly_price_brl).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</p>
              <p className="text-gray-400 text-xs">/ mês</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-white">{subscription.plan.max_devices ?? "∞"}</p>
              <p className="text-gray-400 text-xs">dispositivos</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-white">{subscription.plan.max_users ?? "∞"}</p>
              <p className="text-gray-400 text-xs">usuários</p>
            </div>
          </div>
        </div>
      )}

      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-white font-semibold">Planos Disponíveis</h3>
          {plans.length === 0 && (
            <button onClick={() => seedMut.mutate()} className="px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-sm">Carregar Planos</button>
          )}
        </div>
        <div className="grid grid-cols-3 gap-4">
          {plans.map((p: BillingPlan) => (
            <div key={p.id} className={`bg-gray-800 border rounded-lg p-5 space-y-4 ${p.slug === "enterprise" ? "border-purple-700" : p.slug === "pro" ? "border-brand-700" : "border-gray-700"}`}>
              <div>
                <span className={`text-xs px-2 py-0.5 rounded ${planBadge[p.slug] || "bg-gray-700 text-gray-300"}`}>{p.name}</span>
                <p className="text-3xl font-bold text-white mt-2">
                  R$ {Number(p.monthly_price_brl).toLocaleString("pt-BR", { minimumFractionDigits: 0 })}
                  <span className="text-sm text-gray-400 font-normal">/mês</span>
                </p>
              </div>
              <ul className="space-y-1 text-sm">
                <li className="text-gray-300">{p.max_devices ?? "Ilimitados"} dispositivos</li>
                <li className="text-gray-300">{p.max_users ?? "Ilimitados"} usuários</li>
                <li className="text-gray-300">SLA {p.sla_target_pct ?? "99"}%</li>
                {p.features?.siem && <li className="text-green-400">✓ SIEM</li>}
                {p.features?.edge_agent && <li className="text-green-400">✓ Edge Agents</li>}
              </ul>
              {subscription?.plan.slug !== p.slug ? (
                <div className="space-y-2">
                  {/* Stripe Checkout — redirect para pagamento real */}
                  <button
                    onClick={() => handleUpgrade(p)}
                    disabled={checkoutLoading === p.id}
                    className="w-full flex items-center justify-center gap-2 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded text-sm font-medium disabled:opacity-60"
                  >
                    {checkoutLoading === p.id ? "Aguarde..." : (
                      <>{t("billing.upgrade")} <ExternalLink size={12} /></>
                    )}
                  </button>
                  {/* Fallback — iniciar sem Stripe (modo dev) */}
                  <button
                    onClick={() => startMut.mutate(p.slug)}
                    className="w-full flex items-center justify-center gap-2 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded text-xs"
                  >
                    Selecionar (sem pagamento) <ArrowRight size={11} />
                  </button>
                </div>
              ) : (
                <div className="text-center text-xs text-brand-400 py-2">Plano atual</div>
              )}
            </div>
          ))}
        </div>
      </div>

      {invoices.length > 0 && (
        <div>
          <h3 className="text-white font-semibold mb-3">{t("billing.invoices")}</h3>
          <div className="space-y-2">
            {invoices.map((inv: BillingInvoice) => (
              <div key={inv.id} className="bg-gray-800 rounded-lg p-4 flex items-center justify-between border border-gray-700">
                <div className="flex items-center gap-3">
                  <FileText size={16} className="text-gray-400" />
                  <div>
                    <span className="text-white text-sm font-medium">R$ {Number(inv.amount_brl).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</span>
                    <p className="text-xs text-gray-400">{new Date(inv.created_at).toLocaleDateString("pt-BR")}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-xs px-2 py-0.5 rounded ${inv.status === "paid" ? "bg-green-900/50 text-green-300" : inv.status === "open" ? "bg-yellow-900/50 text-yellow-300" : "bg-gray-700 text-gray-400"}`}>{inv.status}</span>
                  {/* Download PDF */}
                  <a
                    href={productApi.invoicePdfUrl(inv.id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-xs text-brand-400 hover:text-brand-300"
                    title={t("billing.download_pdf")}
                  >
                    <Download size={13} /> PDF
                  </a>
                  {/* Link para PDF do Stripe se disponível */}
                  {inv.invoice_pdf_url && (
                    <a
                      href={inv.invoice_pdf_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-300"
                      title="PDF Stripe"
                    >
                      <ExternalLink size={11} />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Onboarding Tab ────────────────────────────────────────────────────────────

function OnboardingTab() {
  const qc = useQueryClient();

  const { data: checklist } = useQuery<OnboardingChecklist>({ queryKey: ["onboarding-checklist"], queryFn: productApi.getChecklist });

  const stepMut = useMutation({
    mutationFn: (step: string) => productApi.completeStep(step),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["onboarding-checklist"] }),
  });

  const skipMut = useMutation({
    mutationFn: productApi.skipOnboarding,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["onboarding-checklist"] }),
  });

  if (!checklist) return <div className="text-gray-400 text-center py-12">Carregando...</div>;

  const steps = [
    { key: "add_device", label: "Adicionar dispositivo", desc: "Cadastre seu primeiro firewall em Firewalls > Dispositivos", done: checklist.step_add_device },
    { key: "run_snapshot", label: "Executar snapshot", desc: "Capture o estado atual do dispositivo em Inspetor", done: checklist.step_run_snapshot },
    { key: "ask_agent", label: "Fazer pergunta ao Agente", desc: 'Acesse o Assistente IA e pergunte "listar regras"', done: checklist.step_ask_agent },
    { key: "configure_alert", label: "Configurar alerta", desc: "Crie uma regra de alerta em Segurança > Alertas", done: checklist.step_configure_alert },
  ];

  const completed = steps.filter(s => s.done).length;
  const pct = Math.round((completed / steps.length) * 100);

  if (checklist.skipped) {
    return (
      <div className="text-center py-12">
        <CheckCircle size={40} className="text-green-400 mx-auto mb-4" />
        <p className="text-white font-medium">Onboarding ignorado</p>
        <p className="text-gray-400 text-sm mt-1">Você pode retomar quando quiser clicando em reiniciar.</p>
      </div>
    );
  }

  if (checklist.completed) {
    return (
      <div className="text-center py-12">
        <Sparkles size={40} className="text-yellow-400 mx-auto mb-4" />
        <p className="text-white font-medium text-lg">Parabéns! Onboarding concluído!</p>
        <p className="text-gray-400 text-sm mt-1">Você completou todas as etapas de configuração inicial.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <div className="flex justify-between items-center mb-2">
          <span className="text-white font-medium">Progresso</span>
          <span className="text-gray-400 text-sm">{completed}/{steps.length} etapas</span>
        </div>
        <div className="w-full bg-gray-700 rounded-full h-2">
          <div className="bg-brand-500 h-2 rounded-full transition-all" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <div className="space-y-3">
        {steps.map((step, i) => (
          <div key={step.key} className={`bg-gray-800 rounded-lg p-4 border flex items-start gap-4 ${step.done ? "border-green-700/50" : "border-gray-700"}`}>
            <div className={`mt-0.5 flex-shrink-0 ${step.done ? "text-green-400" : "text-gray-600"}`}>
              {step.done ? <CheckCircle size={20} /> : <Circle size={20} />}
            </div>
            <div className="flex-1">
              <p className={`font-medium ${step.done ? "text-green-300 line-through" : "text-white"}`}>
                {i + 1}. {step.label}
              </p>
              <p className="text-xs text-gray-400 mt-0.5">{step.desc}</p>
            </div>
            {!step.done && (
              <button onClick={() => stepMut.mutate(step.key)} className="text-xs bg-brand-600/30 hover:bg-brand-600/50 text-brand-300 px-3 py-1.5 rounded flex-shrink-0">
                Marcar concluído
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="flex justify-end">
        <button onClick={() => skipMut.mutate()} className="text-sm text-gray-400 hover:text-gray-300">Pular onboarding</button>
      </div>
    </div>
  );
}

// ── Help Tab ──────────────────────────────────────────────────────────────────

function HelpTab() {
  const qc = useQueryClient();
  const [selectedArticle, setSelectedArticle] = useState<HelpArticle | null>(null);
  const [filter, setFilter] = useState<string>("all");

  const { data: articles = [] } = useQuery({ queryKey: ["help-articles"], queryFn: () => productApi.listArticles() });

  const seedMut = useMutation({
    mutationFn: productApi.seedArticles,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["help-articles"] }),
  });

  const categories = ["all", ...Array.from(new Set(articles.map((a: HelpArticle) => a.category)))];
  const filtered = filter === "all" ? articles : articles.filter((a: HelpArticle) => a.category === filter);

  if (selectedArticle) {
    return (
      <div className="space-y-4 max-w-3xl">
        <button onClick={() => setSelectedArticle(null)} className="text-sm text-gray-400 hover:text-white flex items-center gap-1">
          ← Voltar
        </button>
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-bold text-white mb-2">{selectedArticle.title}</h2>
          <div className="flex items-center gap-2 mb-4">
            <span className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded">{selectedArticle.category}</span>
            {selectedArticle.persona && <span className="text-xs bg-blue-900/50 text-blue-300 px-2 py-0.5 rounded">{selectedArticle.persona}</span>}
            <span className="text-xs text-gray-500">{selectedArticle.view_count} visualizações</span>
          </div>
          <pre className="text-sm text-gray-300 whitespace-pre-wrap font-sans">{selectedArticle.content_md}</pre>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div className="flex gap-2">
          {categories.map(c => (
            <button key={c} onClick={() => setFilter(c)} className={`px-3 py-1.5 rounded text-xs font-medium ${filter === c ? "bg-brand-600 text-white" : "bg-gray-700 text-gray-300 hover:bg-gray-600"}`}>
              {c === "all" ? "Todos" : c}
            </button>
          ))}
        </div>
        {articles.length === 0 && (
          <button onClick={() => seedMut.mutate()} className="px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-sm">Carregar Artigos</button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        {filtered.map((a: HelpArticle) => (
          <button key={a.id} onClick={() => setSelectedArticle(a)} className="bg-gray-800 rounded-lg p-4 border border-gray-700 hover:border-brand-600 text-left transition-colors space-y-2">
            <div className="flex items-center gap-2">
              <BookOpen size={14} className="text-brand-400 flex-shrink-0" />
              <span className="font-medium text-white text-sm">{a.title}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded">{a.category}</span>
              {a.persona && <span className="text-xs bg-blue-900/50 text-blue-300 px-2 py-0.5 rounded">{a.persona}</span>}
            </div>
            <p className="text-xs text-gray-500">{a.view_count} visualizações</p>
          </button>
        ))}
      </div>
      {filtered.length === 0 && <p className="text-gray-500 text-sm text-center py-8">Nenhum artigo encontrado.</p>}
    </div>
  );
}

// ── Preferences Tab ───────────────────────────────────────────────────────────

function PreferencesTab() {
  const qc = useQueryClient();

  const { data: prefs } = useQuery({ queryKey: ["user-preferences"], queryFn: productApi.getPreferences });

  const saveMut = useMutation({
    mutationFn: (data: { language?: string; timezone?: string; theme?: string; notifications_enabled?: boolean }) =>
      productApi.updatePreferences(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["user-preferences"] }),
  });

  if (!prefs) return <div className="text-gray-400 text-center py-12">Carregando...</div>;

  return (
    <div className="space-y-6 max-w-lg">
      <div className="bg-gray-800 rounded-lg p-5 border border-gray-700 space-y-4">
        <h3 className="font-semibold text-white">Preferências do Usuário</h3>

        <div>
          <label className="text-xs text-gray-400 block mb-1">Idioma</label>
          <select
            value={prefs.language}
            onChange={e => saveMut.mutate({ language: e.target.value })}
            className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm"
          >
            <option value="pt-BR">Português (Brasil)</option>
            <option value="en-US">English (US)</option>
            <option value="es-LA">Español (LATAM)</option>
          </select>
        </div>

        <div>
          <label className="text-xs text-gray-400 block mb-1">Fuso Horário</label>
          <select
            value={prefs.timezone}
            onChange={e => saveMut.mutate({ timezone: e.target.value })}
            className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm"
          >
            <option value="America/Sao_Paulo">America/Sao_Paulo (BRT)</option>
            <option value="America/Manaus">America/Manaus (AMT)</option>
            <option value="America/Fortaleza">America/Fortaleza (BRT)</option>
            <option value="UTC">UTC</option>
          </select>
        </div>

        <div>
          <label className="text-xs text-gray-400 block mb-1">Tema</label>
          <select
            value={prefs.theme}
            onChange={e => saveMut.mutate({ theme: e.target.value })}
            className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm"
          >
            <option value="dark">Dark</option>
            <option value="light">Light</option>
            <option value="high_contrast">Alto Contraste</option>
          </select>
        </div>

        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={prefs.notifications_enabled}
            onChange={e => saveMut.mutate({ notifications_enabled: e.target.checked })}
            className="rounded"
          />
          <div>
            <p className="text-sm text-white">Notificações habilitadas</p>
            <p className="text-xs text-gray-400">Receber alertas e notificações do sistema</p>
          </div>
        </label>
      </div>

      <div className="bg-gray-800 rounded-lg p-5 border border-gray-700 space-y-3">
        <h3 className="font-semibold text-white flex items-center gap-2"><Globe size={16} /> Localização</h3>
        <p className="text-sm text-gray-400">
          Idioma atual: <span className="text-white">{prefs.language}</span><br />
          Fuso horário: <span className="text-white">{prefs.timezone}</span>
        </p>
        <p className="text-xs text-gray-500">As alterações são aplicadas imediatamente e sincronizadas em todos os dispositivos.</p>
      </div>
    </div>
  );
}
