import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BookOpen,
  Bot,
  CheckCircle2,
  ChevronRight,
  Clock,
  ExternalLink,
  FileText,
  Loader2,
  MessageSquare,
  Play,
  RefreshCw,
  RotateCcw,
  Send,
  X,
  XCircle,
} from "lucide-react";
import toast from "react-hot-toast";
import { PageWrapper } from "../components/layout/PageWrapper";
import { glpiApi } from "../api/glpi";
import { RunAnalysisModal } from "../components/glpi/RunAnalysisModal";
import type { GlpiAnalysisStatus, GlpiAnalysisListItem, GlpiKrDraft, GlpiTicketAnalysis } from "../types/glpi";

// ── Helpers ───────────────────────────────────────────────────────────────────

const STATUS_LABEL: Record<GlpiAnalysisStatus, string> = {
  pending:        "Pendente",
  pending_manual: "Aguarda análise",
  analyzing:      "Analisando",
  completed:      "Concluído",
  failed:         "Falhou",
};

const STATUS_STYLE: Record<GlpiAnalysisStatus, string> = {
  pending:        "bg-gray-100 text-gray-600",
  pending_manual: "bg-amber-100 text-amber-700",
  analyzing:      "bg-blue-100 text-blue-700",
  completed:      "bg-green-100 text-green-700",
  failed:         "bg-red-100 text-red-700",
};

const ITEMTYPE_LABEL: Record<string, string> = {
  Ticket:  "Ticket",
  Problem: "Problema",
  Change:  "Mudança",
};

const ITEMTYPE_STYLE: Record<string, string> = {
  Ticket:  "bg-blue-50 text-blue-700",
  Problem: "bg-red-50 text-red-700",
  Change:  "bg-purple-50 text-purple-700",
};

const KB_STATUS_LABEL: Record<string, string> = {
  documentado:               "Documentado",
  parcialmente_documentado:  "Parcialmente doc.",
  sem_documentacao:          "Sem documentação",
  nao_verificado:            "Não verificado",
};

const KB_STATUS_STYLE: Record<string, string> = {
  documentado:               "bg-green-100 text-green-700",
  parcialmente_documentado:  "bg-amber-100 text-amber-700",
  sem_documentacao:          "bg-red-100 text-red-700",
  nao_verificado:            "bg-gray-100 text-gray-500",
};

function glpiItemUrl(baseUrl: string, itemtype: string, id: number): string {
  const paths: Record<string, string> = {
    Ticket:  "ticket",
    Problem: "problem",
    Change:  "change",
  };
  return `${baseUrl}/front/${paths[itemtype] ?? "ticket"}.form.php?id=${id}`;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function ConfidenceBadge({ value }: { value: number | null }) {
  if (value === null) return <span className="text-gray-300">—</span>;
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? "text-green-600" : pct >= 60 ? "text-yellow-600" : "text-red-500";
  return <span className={`font-medium ${color}`}>{pct}%</span>;
}

// ── Detail slide-over ─────────────────────────────────────────────────────────

function AnalysisSlideOver({
  analysisId,
  onClose,
  onRunAnalysis,
}: {
  analysisId: string;
  onClose: () => void;
  onRunAnalysis: () => void;
}) {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({
    queryKey: ["glpi-analysis", analysisId],
    queryFn: () => glpiApi.getAnalysis(analysisId),
  });

  const openChatMut = useMutation({
    mutationFn: () => glpiApi.openChatFromGlpi(analysisId),
    onSuccess: ({ session_id }) => {
      onClose();
      navigate(`/assistant?session=${session_id}`);
    },
    onError: () => toast.error("Erro ao abrir chat para este ticket"),
  });

  function Section({ title, content }: { title: string; content: string | null }) {
    if (!content) return null;
    return (
      <div>
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{title}</p>
        <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{content}</p>
      </div>
    );
  }

  const glpiLink = data?.glpi_url
    ? glpiItemUrl(data.glpi_url, data.glpi_itemtype, data.glpi_ticket_id)
    : null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-white shadow-2xl flex flex-col h-full overflow-hidden animate-slide-in-right">
        {/* Header */}
        <div className="flex items-start justify-between px-5 py-4 border-b border-gray-200 shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <MessageSquare size={18} className="text-brand-600 shrink-0" />
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-xs text-gray-400">#{data?.glpi_ticket_id}</p>
                {data?.glpi_itemtype && (
                  <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${ITEMTYPE_STYLE[data.glpi_itemtype] ?? "bg-gray-100 text-gray-600"}`}>
                    {ITEMTYPE_LABEL[data.glpi_itemtype] ?? data.glpi_itemtype}
                  </span>
                )}
              </div>
              <h2 className="text-sm font-semibold text-gray-900 truncate">
                {data?.glpi_ticket_title ?? "Carregando..."}
              </h2>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0 ml-3">
            {glpiLink && (
              <a
                href={glpiLink}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800 font-medium"
                title="Abrir no GLPI"
              >
                <ExternalLink size={13} />
                GLPI
              </a>
            )}
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Investigate CTA */}
        <div className="shrink-0 px-5 py-3 border-b border-gray-100 bg-brand-50">
          <button
            onClick={() => openChatMut.mutate()}
            disabled={openChatMut.isPending}
            className="flex items-center gap-2 w-full justify-center text-sm font-semibold text-white bg-brand-600 hover:bg-brand-700 disabled:opacity-60 px-4 py-2.5 rounded-lg transition-colors"
          >
            {openChatMut.isPending ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Bot size={15} />
            )}
            Investigar no Eternity SecOps
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {isLoading && (
            <div className="flex items-center justify-center h-48 text-gray-400 gap-2">
              <Loader2 size={20} className="animate-spin" />
              <span className="text-sm">Carregando análise...</span>
            </div>
          )}

          {data && (
            <div className="space-y-5">
              {/* Badges row */}
              <div className="flex flex-wrap gap-2">
                <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${STATUS_STYLE[data.status]}`}>
                  {STATUS_LABEL[data.status]}
                </span>
                {data.is_security_incident && (
                  <span className="flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-red-100 text-red-700">
                    <AlertTriangle size={11} /> Incidente de segurança
                  </span>
                )}
                {data.is_recurrent && (
                  <span className="flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-amber-100 text-amber-700">
                    <RotateCcw size={11} /> Recorrente ({data.recurrence_count}x)
                  </span>
                )}
                {data.confianca !== null && (
                  <span className="flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-gray-100 text-gray-600">
                    Confiança: {Math.round(data.confianca * 100)}%
                  </span>
                )}
              </div>

              {/* Analysis sections */}
              {data.status === "completed" ? (
                <div className="space-y-5 divide-y divide-gray-100">
                  <Section title="📋 Diagnóstico"                    content={data.diagnostico} />
                  <div className="pt-5"><Section title="⚡ Ação imediata — faça agora"      content={data.acoes_imediatas} /></div>
                  <div className="pt-5"><Section title="🔧 Ação definitiva — médio prazo"  content={data.plano_remediacao} /></div>
                  <div className="pt-5"><Section title="🔍 Causa raiz"                     content={data.causa_raiz} /></div>
                  <div className="pt-5"><Section title="🛡 Prevenção"                      content={data.prevencao} /></div>
                </div>
              ) : data.status === "pending_manual" ? (
                <div className="bg-amber-50 border border-amber-100 rounded-lg px-4 py-4 space-y-3">
                  <p className="text-sm font-medium text-amber-800">Aguardando análise manual</p>
                  <p className="text-xs text-amber-600">
                    Este ticket não foi analisado automaticamente. Clique em "Analisar agora" para
                    selecionar os dispositivos relacionados e iniciar a análise com IA.
                  </p>
                  <button
                    onClick={() => { onClose(); onRunAnalysis(); }}
                    className="flex items-center gap-2 text-sm font-medium text-white bg-brand-600 hover:bg-brand-700 px-4 py-2 rounded-lg transition-colors"
                  >
                    <Play size={14} />
                    Analisar agora
                  </button>
                </div>
              ) : data.status === "failed" ? (
                <div className="bg-red-50 border border-red-100 rounded-lg px-4 py-3 text-sm text-red-700">
                  <p className="font-medium mb-1">Falha na análise</p>
                  <p className="text-xs text-red-500">{data.error_message ?? "Erro desconhecido"}</p>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-sm text-gray-400 py-8 justify-center">
                  <Loader2 size={16} className="animate-spin" />
                  Análise em andamento...
                </div>
              )}

              {/* Ticket content */}
              {data.glpi_ticket_content && (
                <div className="pt-2 border-t border-gray-100">
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Descrição original</p>
                  <p className="text-xs text-gray-500 whitespace-pre-wrap leading-relaxed bg-gray-50 rounded-lg p-3">
                    {data.glpi_ticket_content}
                  </p>
                </div>
              )}

              {/* Meta */}
              <div className="flex items-center gap-3 text-xs text-gray-400 pt-2 border-t border-gray-100 flex-wrap">
                <span>Analisado em {fmtDate(data.created_at)}</span>
                {data.glpi_followup_id && (
                  glpiLink ? (
                    <a
                      href={glpiLink}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-green-600 hover:text-green-700 font-medium"
                    >
                      <CheckCircle2 size={11} />
                      Nota postada no GLPI (#{data.glpi_followup_id})
                      <ExternalLink size={10} />
                    </a>
                  ) : (
                    <span className="text-green-600">✓ Nota postada no GLPI (#{data.glpi_followup_id})</span>
                  )
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Filter pill ───────────────────────────────────────────────────────────────

function FilterPill({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full border transition-colors ${
        active
          ? "bg-brand-600 text-white border-brand-600"
          : "bg-white text-gray-600 border-gray-200 hover:border-brand-400 hover:text-brand-600"
      }`}
    >
      {children}
    </button>
  );
}

// ── Publish KR Modal ──────────────────────────────────────────────────────────

function PublishKrModal({
  draft,
  onClose,
  onPublished,
}: {
  draft: GlpiKrDraft;
  onClose: () => void;
  onPublished: (result: { bookstack_page_url: string | null }) => void;
}) {
  const { data: integration } = useQuery({
    queryKey: ["glpi-integration"],
    queryFn: glpiApi.getIntegration,
  });

  const [bookId, setBookId]       = useState<number | "">(integration?.kr_bookstack_book_id ?? "");
  const [chapterId, setChapterId] = useState<number | "">(integration?.kr_bookstack_chapter_id ?? "");

  // Sync integration defaults when they load
  const intgLoaded = !!integration;
  useState(() => {
    if (integration?.kr_bookstack_book_id) setBookId(integration.kr_bookstack_book_id);
    if (integration?.kr_bookstack_chapter_id) setChapterId(integration.kr_bookstack_chapter_id);
  });

  const { data: books = [], isLoading: loadingBooks } = useQuery({
    queryKey: ["bookstack-books"],
    queryFn: glpiApi.listBookstackBooks,
  });

  const { data: chapters = [], isLoading: loadingChapters } = useQuery({
    queryKey: ["bookstack-chapters", bookId],
    queryFn: () => glpiApi.listBookstackChapters(bookId as number),
    enabled: !!bookId,
  });

  const resolveMut = useMutation({
    mutationFn: () =>
      glpiApi.resolveKr(draft.glpi_analysis_id, {
        book_id:    bookId    || undefined,
        chapter_id: chapterId || undefined,
      }),
    onSuccess: (result) => {
      toast.success("Documentação publicada e chamado KR fechado.");
      onPublished(result);
      onClose();
    },
    onError: () => toast.error("Falha ao publicar a documentação"),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">Publicar no BookStack</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>

        <div className="bg-gray-50 rounded-lg px-3 py-2">
          <p className="text-xs font-medium text-gray-700 truncate">{draft.title}</p>
          <p className="text-xs text-gray-400 mt-0.5">Origem: #{draft.glpi_ticket_id} — {draft.glpi_ticket_title}</p>
        </div>

        {/* Book selector */}
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Livro de destino</label>
          {loadingBooks ? (
            <div className="flex items-center gap-2 text-xs text-gray-400 py-2">
              <Loader2 size={12} className="animate-spin" /> Carregando livros...
            </div>
          ) : books.length === 0 ? (
            <p className="text-xs text-amber-600">BookStack não configurado ou sem livros disponíveis.</p>
          ) : (
            <select
              value={bookId}
              onChange={(e) => { setBookId(e.target.value ? Number(e.target.value) : ""); setChapterId(""); }}
              className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="">— Selecionar livro —</option>
              {books.map((b) => (
                <option key={b.id} value={b.id}>{b.name}</option>
              ))}
            </select>
          )}
        </div>

        {/* Chapter selector */}
        {bookId && (
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Capítulo (opcional)</label>
            {loadingChapters ? (
              <div className="flex items-center gap-2 text-xs text-gray-400 py-2">
                <Loader2 size={12} className="animate-spin" /> Carregando capítulos...
              </div>
            ) : (
              <select
                value={chapterId}
                onChange={(e) => setChapterId(e.target.value ? Number(e.target.value) : "")}
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="">— Sem capítulo (raiz do livro) —</option>
                {chapters.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            )}
          </div>
        )}

        <div className="flex gap-2 pt-2">
          <button
            onClick={onClose}
            className="flex-1 border border-gray-300 text-gray-600 text-sm font-medium py-2 rounded-lg hover:bg-gray-50"
          >
            Cancelar
          </button>
          <button
            onClick={() => resolveMut.mutate()}
            disabled={resolveMut.isPending || books.length === 0}
            className="flex-1 flex items-center justify-center gap-2 bg-brand-600 text-white text-sm font-semibold py-2 rounded-lg hover:bg-brand-700 disabled:opacity-60"
          >
            {resolveMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            Publicar e Fechar KR
          </button>
        </div>
      </div>
    </div>
  );
}

// ── KR Drafts tab ─────────────────────────────────────────────────────────────

function KrDraftsTab() {
  const qc = useQueryClient();
  const [publishingDraft, setPublishingDraft] = useState<GlpiKrDraft | null>(null);

  const { data: drafts = [], isLoading } = useQuery({
    queryKey: ["glpi-kr-drafts"],
    queryFn: glpiApi.listKrDrafts,
    refetchInterval: 30_000,
  });

  function handlePublished(result: { bookstack_page_url: string | null }) {
    qc.invalidateQueries({ queryKey: ["glpi-kr-drafts"] });
    qc.invalidateQueries({ queryKey: ["glpi-analyses"] });
    if (result.bookstack_page_url) window.open(result.bookstack_page_url, "_blank");
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48 gap-2 text-gray-400">
        <Loader2 size={20} className="animate-spin" />
        <span className="text-sm">Carregando rascunhos KR...</span>
      </div>
    );
  }

  if (drafts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-48 gap-3 text-gray-400">
        <BookOpen size={36} className="opacity-25" />
        <p className="text-sm font-medium">Nenhum rascunho KR pendente</p>
        <p className="text-xs text-gray-300 text-center max-w-xs">
          Quando o agente detectar documentação ausente ou incompleta em chamados analisados,
          um rascunho aparecerá aqui para revisão.
        </p>
      </div>
    );
  }

  return (
    <>
    {publishingDraft && (
      <PublishKrModal
        draft={publishingDraft}
        onClose={() => setPublishingDraft(null)}
        onPublished={handlePublished}
      />
    )}
    <div className="space-y-3">
      {drafts.map((draft) => (
        <div
          key={draft.draft_id}
          className="bg-white border border-gray-200 rounded-xl p-4 flex items-start gap-4"
        >
          <div className="shrink-0 w-8 h-8 rounded-lg bg-brand-50 flex items-center justify-center">
            <FileText size={16} className="text-brand-600" />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <span className="text-sm font-semibold text-gray-900 truncate">{draft.title}</span>
              {draft.kb_status && (
                <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${KB_STATUS_STYLE[draft.kb_status] ?? "bg-gray-100 text-gray-500"}`}>
                  {KB_STATUS_LABEL[draft.kb_status] ?? draft.kb_status}
                </span>
              )}
            </div>

            <p className="text-xs text-gray-500 mb-2 truncate">
              Origem: {draft.glpi_ticket_title} (#{draft.glpi_ticket_id})
              {draft.kr_ticket_id && (
                <span className="ml-2 text-gray-400">· KR #{draft.kr_ticket_id}</span>
              )}
            </p>

            <div className="flex items-center gap-2 flex-wrap">
              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                draft.status === "approved" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"
              }`}>
                {draft.status === "approved" ? "Aprovado" : "Rascunho"}
              </span>
              <span className="text-xs text-gray-400">{fmtDate(draft.created_at)}</span>
            </div>
          </div>

          <div className="shrink-0 flex flex-col gap-2 items-end">
            <button
              onClick={() => setPublishingDraft(draft)}
              className="flex items-center gap-1.5 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-700 px-3 py-1.5 rounded-lg transition-colors whitespace-nowrap"
            >
              <Send size={12} />
              Publicar e Fechar Chamado
            </button>
          </div>
        </div>
      ))}
    </div>
    </>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function GlpiAnalyses() {
  const qc = useQueryClient();
  const [activeTab, setActiveTab]         = useState<"analyses" | "kr-drafts">("analyses");
  const [statusFilter, setStatusFilter]   = useState<GlpiAnalysisStatus | "">("");
  const [itemtypeFilter, setItemtypeFilter] = useState<string>("");
  const [securityOnly, setSecurityOnly]   = useState(false);
  const [recurrentOnly, setRecurrentOnly] = useState(false);
  const [selectedId, setSelectedId]       = useState<string | null>(null);
  const [runModalAnalysis, setRunModalAnalysis] = useState<GlpiAnalysisListItem | null>(null);

  const { data: integration } = useQuery({
    queryKey: ["glpi-integration"],
    queryFn: glpiApi.getIntegration,
  });

  const { data: analyses = [], isLoading, refetch } = useQuery({
    queryKey: ["glpi-analyses", statusFilter, itemtypeFilter, securityOnly, recurrentOnly],
    queryFn: () =>
      glpiApi.listAnalyses({
        status:         statusFilter || undefined,
        itemtype:       itemtypeFilter || undefined,
        security_only:  securityOnly || undefined,
        recurrent_only: recurrentOnly || undefined,
        limit: 200,
      }),
  });

  const syncMut = useMutation({
    mutationFn: () => glpiApi.triggerSync(integration!.id),
    onSuccess: () => {
      toast.success("Sincronização iniciada. Análises aparecerão em instantes.");
      setTimeout(() => refetch(), 5000);
    },
    onError: () => toast.error("Falha ao iniciar sincronização"),
  });

  const securityCount  = analyses.filter((a) => a.is_security_incident).length;
  const recurrentCount = analyses.filter((a) => a.is_recurrent).length;

  // Count by itemtype for badges
  const countByType = analyses.reduce<Record<string, number>>((acc, a) => {
    acc[a.glpi_itemtype] = (acc[a.glpi_itemtype] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <PageWrapper title="Tickets IA">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-gray-900">Tickets IA</h1>
          {activeTab === "analyses" && analyses.length > 0 && (
            <span className="text-xs bg-gray-100 text-gray-600 px-2.5 py-0.5 rounded-full font-medium">
              {analyses.length} {analyses.length === 1 ? "item" : "itens"}
            </span>
          )}
        </div>
        <button
          onClick={() => syncMut.mutate()}
          disabled={syncMut.isPending || !integration?.is_active}
          title={!integration ? "Nenhuma integração GLPI configurada" : undefined}
          className="flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <RefreshCw size={14} className={syncMut.isPending ? "animate-spin" : ""} />
          {syncMut.isPending ? "Sincronizando..." : "Sync agora"}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-5 border-b border-gray-200">
        <button
          onClick={() => setActiveTab("analyses")}
          className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
            activeTab === "analyses"
              ? "border-brand-600 text-brand-600"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          <MessageSquare size={14} />
          Análises
        </button>
        <button
          onClick={() => setActiveTab("kr-drafts")}
          className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
            activeTab === "kr-drafts"
              ? "border-brand-600 text-brand-600"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          <BookOpen size={14} />
          Registros KB
        </button>
      </div>

      {/* KR Drafts tab */}
      {activeTab === "kr-drafts" && <KrDraftsTab />}

      {activeTab === "analyses" && <>
      {/* No integration configured */}
      {!integration && !isLoading && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-4 text-sm text-amber-800 mb-5">
          Nenhuma integração GLPI configurada. Acesse{" "}
          <a href="/organization" className="font-semibold underline hover:text-amber-900">
            Organização → Integrações
          </a>{" "}
          para configurar.
        </div>
      )}

      {/* Status filters */}
      <div className="flex flex-wrap gap-2 mb-2">
        <FilterPill active={statusFilter === ""} onClick={() => setStatusFilter("")}>
          Todos
        </FilterPill>
        <FilterPill active={statusFilter === "completed"} onClick={() => setStatusFilter(statusFilter === "completed" ? "" : "completed")}>
          <CheckCircle2 size={11} /> Concluídos
        </FilterPill>
        <FilterPill active={statusFilter === "analyzing"} onClick={() => setStatusFilter(statusFilter === "analyzing" ? "" : "analyzing")}>
          <Clock size={11} /> Analisando
        </FilterPill>
        <FilterPill active={statusFilter === "pending_manual"} onClick={() => setStatusFilter(statusFilter === "pending_manual" ? "" : "pending_manual")}>
          <Clock size={11} /> Aguarda análise
        </FilterPill>
        <FilterPill active={statusFilter === "failed"} onClick={() => setStatusFilter(statusFilter === "failed" ? "" : "failed")}>
          <XCircle size={11} /> Falhou
        </FilterPill>
        <FilterPill active={securityOnly} onClick={() => setSecurityOnly((v) => !v)}>
          <AlertTriangle size={11} />
          Segurança {securityCount > 0 && <span className="bg-red-500 text-white rounded-full px-1 text-[10px]">{securityCount}</span>}
        </FilterPill>
        <FilterPill active={recurrentOnly} onClick={() => setRecurrentOnly((v) => !v)}>
          <RotateCcw size={11} />
          Recorrentes {recurrentCount > 0 && <span className="bg-amber-500 text-white rounded-full px-1 text-[10px]">{recurrentCount}</span>}
        </FilterPill>
      </div>

      {/* Type filters */}
      <div className="flex flex-wrap gap-2 mb-4">
        <FilterPill active={itemtypeFilter === ""} onClick={() => setItemtypeFilter("")}>
          Todos os tipos
        </FilterPill>
        {(["Ticket", "Problem", "Change"] as const).map((t) => (
          <FilterPill
            key={t}
            active={itemtypeFilter === t}
            onClick={() => setItemtypeFilter(itemtypeFilter === t ? "" : t)}
          >
            {ITEMTYPE_LABEL[t]}
            {countByType[t] != null && (
              <span className="bg-white/30 text-current rounded-full px-1 text-[10px] font-bold">
                {countByType[t]}
              </span>
            )}
          </FilterPill>
        ))}
      </div>

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center h-48 gap-2 text-gray-400">
            <Loader2 size={20} className="animate-spin" />
            <span className="text-sm">Carregando análises...</span>
          </div>
        ) : analyses.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 gap-2 text-gray-400">
            <MessageSquare size={32} className="opacity-30" />
            <p className="text-sm">Nenhuma análise encontrada</p>
            {integration && (
              <p className="text-xs text-gray-300">
                O worker processa novos itens a cada {integration.poll_interval_minutes} minutos
              </p>
            )}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-16">#</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-24">Tipo</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Título</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-28">Status</th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-16">Seg.</th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-24">Recorrente</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-20">Conf.</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-36">Data</th>
                <th className="w-8" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {analyses.map((a) => (
                <tr
                  key={a.id}
                  onClick={() => setSelectedId(a.id)}
                  className="hover:bg-gray-50 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 text-gray-400 font-mono text-xs">{a.glpi_ticket_id}</td>
                  <td className="px-4 py-3">
                    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${ITEMTYPE_STYLE[a.glpi_itemtype] ?? "bg-gray-100 text-gray-600"}`}>
                      {ITEMTYPE_LABEL[a.glpi_itemtype] ?? a.glpi_itemtype}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-gray-800 font-medium truncate max-w-xs">{a.glpi_ticket_title || "—"}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_STYLE[a.status]}`}>
                      {STATUS_LABEL[a.status]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    {a.is_security_incident
                      ? <AlertTriangle size={14} className="text-red-500 mx-auto" />
                      : <span className="text-gray-200">—</span>}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {a.is_recurrent
                      ? <span className="flex items-center justify-center gap-1 text-xs text-amber-600"><RotateCcw size={11} />{a.recurrence_count}x</span>
                      : <span className="text-gray-200">—</span>}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <ConfidenceBadge value={a.confianca} />
                  </td>
                  <td className="px-4 py-3 text-right text-xs text-gray-400 whitespace-nowrap">
                    {fmtDate(a.created_at)}
                  </td>
                  <td className="px-3 py-3 text-right">
                    {a.status === "pending_manual" ? (
                      <button
                        onClick={(e) => { e.stopPropagation(); setRunModalAnalysis(a); }}
                        className="flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-800 bg-brand-50 hover:bg-brand-100 px-2 py-1 rounded-lg transition-colors whitespace-nowrap"
                        title="Iniciar análise manual"
                      >
                        <Play size={11} />
                        Analisar
                      </button>
                    ) : (
                      <ChevronRight size={14} className="text-gray-300" />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      </>}

      {/* Slide-over detail */}
      {selectedId && (
        <AnalysisSlideOver
          analysisId={selectedId}
          onClose={() => setSelectedId(null)}
          onRunAnalysis={() => {
            const item = analyses.find((a) => a.id === selectedId);
            if (item) setRunModalAnalysis(item);
            setSelectedId(null);
          }}
        />
      )}

      {/* Manual analysis modal */}
      {runModalAnalysis && (
        <RunAnalysisModal
          analysis={runModalAnalysis}
          onClose={() => setRunModalAnalysis(null)}
        />
      )}
    </PageWrapper>
  );
}
