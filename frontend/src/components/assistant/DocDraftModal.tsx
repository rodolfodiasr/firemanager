import { useState } from "react";
import {
  X, AlertTriangle, CheckCircle, BookOpen, Loader2, Edit2, XCircle, Copy,
} from "lucide-react";
import toast from "react-hot-toast";
import { assistantDocsApi, type DocDraft } from "../../api/assistant";

interface Props {
  draft: DocDraft;
  onClose: () => void;
  onUpdated: (draft: DocDraft) => void;
}

export function DocDraftModal({ draft: initialDraft, onClose, onUpdated }: Props) {
  const [draft, setDraft] = useState<DocDraft>(initialDraft);
  const [loading, setLoading] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(draft.title);
  const [editContent, setEditContent] = useState(draft.content);

  const act = async (action: () => Promise<DocDraft>, label: string) => {
    setLoading(label);
    try {
      const updated = await action();
      setDraft(updated);
      onUpdated(updated);
      toast.success(`${label} com sucesso.`);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        `Erro ao ${label.toLowerCase()}.`;
      toast.error(msg);
    } finally {
      setLoading(null);
    }
  };

  const handleSaveEdit = () =>
    act(
      () => assistantDocsApi.updateDoc(draft.id, { title: editTitle, content: editContent }),
      "Salvar"
    ).then(() => setEditing(false));

  const isPublished = draft.status === "published";
  const isRejected = draft.status === "rejected";
  const hasWarnings = draft.sanitizer_warnings.length > 0;
  const hasSimilar = (draft.similar_docs ?? []).length > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <BookOpen size={18} className="text-brand-600 shrink-0" />
            <h2 className="text-base font-semibold text-gray-900 truncate">
              {editing ? "Editando rascunho" : draft.title}
            </h2>
            <StatusBadge status={draft.status} />
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 shrink-0 ml-2">
            <X size={18} />
          </button>
        </div>

        {/* Warnings */}
        {hasWarnings && (
          <div className="px-6 py-3 bg-amber-50 border-b border-amber-200 shrink-0">
            <div className="flex items-start gap-2">
              <AlertTriangle size={15} className="text-amber-600 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-semibold text-amber-800">
                  {draft.sanitizer_warnings.length} dado(s) sensível(is) detectado(s) e mascarado(s)
                </p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {draft.sanitizer_warnings.map((w, i) => (
                    <span
                      key={i}
                      title={w.excerpt}
                      className="text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded"
                    >
                      {w.pattern}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Documentos similares */}
        {hasSimilar && (
          <div className="px-6 py-3 bg-orange-50 border-b border-orange-200 shrink-0">
            <div className="flex items-start gap-2">
              <Copy size={15} className="text-orange-500 mt-0.5 shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold text-orange-800">
                  {draft.similar_docs.length} documento(s) similar(es) já existe(m) no BookStack
                </p>
                <p className="text-[10px] text-orange-600 mt-0.5">
                  Considere atualizar um existente antes de publicar um novo.
                </p>
                <div className="mt-2 space-y-1">
                  {draft.similar_docs.map((doc) => (
                    <div key={doc.bs_page_id} className="flex items-center gap-2">
                      <span className="text-[10px] font-mono bg-orange-100 text-orange-700 px-1.5 py-0.5 rounded shrink-0">
                        {Math.round(doc.similarity * 100)}%
                      </span>
                      <a
                        href={doc.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[11px] text-orange-700 hover:text-orange-900 hover:underline truncate"
                      >
                        {doc.title}
                      </a>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Conteúdo */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {editing ? (
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Título</label>
                <input
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Conteúdo (Markdown)</label>
                <textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  rows={20}
                  className="w-full text-xs font-mono border border-gray-200 rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
            </div>
          ) : (
            <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono leading-relaxed">
              {draft.content}
            </pre>
          )}
        </div>

        {/* Rodapé — ações */}
        {!isPublished && !isRejected && (
          <div className="px-6 py-4 border-t border-gray-200 shrink-0 flex items-center justify-between gap-3">
            {editing ? (
              <>
                <button
                  onClick={() => setEditing(false)}
                  className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
                >
                  Cancelar
                </button>
                <button
                  onClick={handleSaveEdit}
                  disabled={loading === "Salvar"}
                  className="flex items-center gap-1.5 text-sm bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg disabled:opacity-50 transition-colors"
                >
                  {loading === "Salvar" && <Loader2 size={13} className="animate-spin" />}
                  Salvar alterações
                </button>
              </>
            ) : (
              <>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setEditing(true)}
                    className="flex items-center gap-1.5 text-xs text-gray-600 hover:text-gray-800 border border-gray-200 px-3 py-1.5 rounded-lg transition-colors"
                  >
                    <Edit2 size={12} />
                    Editar
                  </button>
                  <button
                    onClick={() => act(() => assistantDocsApi.rejectDoc(draft.id), "Rejeitar")}
                    disabled={!!loading}
                    className="flex items-center gap-1.5 text-xs text-red-600 hover:text-red-700 border border-red-200 px-3 py-1.5 rounded-lg disabled:opacity-50 transition-colors"
                  >
                    {loading === "Rejeitar" ? (
                      <Loader2 size={12} className="animate-spin" />
                    ) : (
                      <XCircle size={12} />
                    )}
                    Rejeitar
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  {draft.status === "draft" && (
                    <button
                      onClick={() => act(() => assistantDocsApi.approveDoc(draft.id), "Aprovar")}
                      disabled={!!loading}
                      className="flex items-center gap-1.5 text-xs text-green-700 hover:text-green-800 border border-green-300 px-3 py-1.5 rounded-lg disabled:opacity-50 transition-colors"
                    >
                      {loading === "Aprovar" ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : (
                        <CheckCircle size={12} />
                      )}
                      Aprovar
                    </button>
                  )}
                  <button
                    onClick={() => act(() => assistantDocsApi.publishDoc(draft.id), "Publicar")}
                    disabled={!!loading}
                    className="flex items-center gap-1.5 text-sm bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg disabled:opacity-50 transition-colors"
                  >
                    {loading === "Publicar" ? (
                      <Loader2 size={13} className="animate-spin" />
                    ) : (
                      <BookOpen size={13} />
                    )}
                    Publicar no BookStack
                  </button>
                </div>
              </>
            )}
          </div>
        )}

        {isPublished && draft.bookstack_page_url && (
          <div className="px-6 py-4 border-t border-gray-200 shrink-0 flex items-center gap-2">
            <CheckCircle size={15} className="text-green-600" />
            <span className="text-sm text-gray-700">Publicado no BookStack — </span>
            <a
              href={draft.bookstack_page_url}
              target="_blank"
              rel="noreferrer"
              className="text-sm text-brand-600 hover:underline truncate"
            >
              Ver página
            </a>
          </div>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: DocDraft["status"] }) {
  const map: Record<DocDraft["status"], { label: string; cls: string }> = {
    draft:     { label: "Rascunho",  cls: "bg-gray-100 text-gray-600" },
    approved:  { label: "Aprovado",  cls: "bg-green-100 text-green-700" },
    published: { label: "Publicado", cls: "bg-brand-100 text-brand-700" },
    rejected:  { label: "Rejeitado", cls: "bg-red-100 text-red-600" },
  };
  const { label, cls } = map[status] ?? map.draft;
  return (
    <span className={`shrink-0 text-[10px] font-medium px-2 py-0.5 rounded-full ${cls}`}>
      {label}
    </span>
  );
}
