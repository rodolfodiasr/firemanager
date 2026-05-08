import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  FileText,
  Info,
  Loader2,
  RefreshCw,
  Search,
  Trash2,
  Upload,
  XCircle,
  Zap,
} from "lucide-react";
import toast from "react-hot-toast";
import { PageWrapper } from "../components/layout/PageWrapper";
import { knowledgeApi } from "../api/knowledge";
import type { DocumentStatus, KnowledgeDocument } from "../types/knowledge";

// ── Helpers ───────────────────────────────────────────────────────────────────

const STATUS_LABEL: Record<DocumentStatus, string> = {
  pending:  "Na fila",
  indexing: "Indexando",
  indexed:  "Indexado",
  failed:   "Falhou",
};

const STATUS_STYLE: Record<DocumentStatus, string> = {
  pending:  "bg-gray-100 text-gray-600",
  indexing: "bg-blue-100 text-blue-700",
  indexed:  "bg-green-100 text-green-700",
  failed:   "bg-red-100 text-red-700",
};

const FILE_TYPE_ICON: Record<string, string> = {
  pdf:      "PDF",
  docx:     "DOCX",
  md:       "MD",
  markdown: "MD",
  txt:      "TXT",
};

function fmtSize(bytes: number | null): string {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function isInProgress(status: DocumentStatus) {
  return status === "pending" || status === "indexing";
}

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLE[status]}`}>
      {status === "indexing" && <Loader2 size={11} className="animate-spin" />}
      {status === "indexed"  && <CheckCircle2 size={11} />}
      {status === "failed"   && <XCircle size={11} />}
      {status === "pending"  && <Clock size={11} />}
      {STATUS_LABEL[status]}
    </span>
  );
}

// ── Upload zone ────────────────────────────────────────────────────────────────

function UploadZone({ onUpload }: { onUpload: (file: File, name?: string, desc?: string) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [docName, setDocName] = useState("");
  const [docDesc, setDocDesc] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  function handleFile(file: File) {
    setSelectedFile(file);
    if (!docName) setDocName(file.name.replace(/\.[^.]+$/, ""));
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  function handleSubmit() {
    if (!selectedFile) return;
    onUpload(selectedFile, docName || undefined, docDesc || undefined);
    setSelectedFile(null);
    setDocName("");
    setDocDesc("");
  }

  return (
    <div className="bg-white border rounded-xl p-5 space-y-4">
      <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
        <Upload size={16} className="text-brand-600" /> Adicionar Documento
      </h3>

      {/* Drop zone */}
      <div
        className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
          dragging ? "border-brand-400 bg-brand-50" : "border-gray-200 hover:border-brand-300 hover:bg-gray-50"
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.md,.txt"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        {selectedFile ? (
          <div className="flex flex-col items-center gap-1.5">
            <FileText size={28} className="text-brand-500" />
            <p className="text-sm font-medium text-gray-800">{selectedFile.name}</p>
            <p className="text-xs text-gray-500">{fmtSize(selectedFile.size)}</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 text-gray-500">
            <Upload size={28} />
            <p className="text-sm font-medium">Arraste um arquivo ou clique para selecionar</p>
            <p className="text-xs">PDF, DOCX, Markdown, TXT — máx. 20 MB</p>
          </div>
        )}
      </div>

      {/* Metadata */}
      {selectedFile && (
        <div className="space-y-2">
          <input
            type="text"
            value={docName}
            onChange={(e) => setDocName(e.target.value)}
            placeholder="Nome do documento"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <input
            type="text"
            value={docDesc}
            onChange={(e) => setDocDesc(e.target.value)}
            placeholder="Descrição (opcional)"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <div className="flex gap-2">
            <button
              onClick={handleSubmit}
              className="flex-1 flex items-center justify-center gap-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
            >
              <Upload size={15} /> Enviar e Indexar
            </button>
            <button
              onClick={() => setSelectedFile(null)}
              className="px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-500 hover:bg-gray-50"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Search panel ──────────────────────────────────────────────────────────────

function SearchPanel() {
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["knowledge-search", submitted],
    queryFn: () => knowledgeApi.search(submitted),
    enabled: submitted.length >= 3,
  });

  function handleSearch() {
    if (query.trim().length >= 3) setSubmitted(query.trim());
  }

  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white border rounded-xl p-5 space-y-3">
      <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
        <Search size={16} className="text-purple-600" /> Testar Busca Semântica
      </h3>
      <p className="text-xs text-gray-500">
        Simula a busca que o Agente IA usa ao responder — combina BookStack e documentos indexados.
      </p>
      <div className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="Ex: política de geo-IP, procedimento de onboarding..."
          className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
        />
        <button
          disabled={query.trim().length < 3 || isLoading || isFetching}
          onClick={handleSearch}
          className="flex items-center gap-1.5 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium rounded-lg disabled:opacity-50 transition-colors"
        >
          {isLoading || isFetching ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
          Buscar
        </button>
      </div>

      {data && submitted && (
        <div className="border border-gray-100 rounded-lg overflow-hidden">
          <div
            className="flex items-center justify-between px-4 py-2.5 bg-gray-50 cursor-pointer"
            onClick={() => setExpanded((v) => !v)}
          >
            <div className="flex items-center gap-2">
              <Zap size={14} className="text-purple-600" />
              <span className="text-sm font-medium text-gray-700">
                Resultado: {data.chunk_count} seções relevantes encontradas
              </span>
            </div>
            {expanded ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
          </div>
          {expanded && (
            <div className="px-4 py-3 bg-white max-h-80 overflow-y-auto">
              {data.context ? (
                <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono">{data.context}</pre>
              ) : (
                <p className="text-sm text-gray-400">Nenhum resultado encontrado.</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Stats card ────────────────────────────────────────────────────────────────

function StatsCard() {
  const { data } = useQuery({
    queryKey: ["knowledge-stats"],
    queryFn: knowledgeApi.stats,
  });

  if (!data) return null;

  return (
    <div className="grid grid-cols-3 gap-4">
      <div className="bg-white border rounded-xl p-4 text-center">
        <div className="text-2xl font-bold text-gray-800">{data.total_documents}</div>
        <div className="text-xs text-gray-500 mt-1">Documentos</div>
      </div>
      <div className="bg-white border rounded-xl p-4 text-center">
        <div className="text-2xl font-bold text-brand-700">{data.total_chunks}</div>
        <div className="text-xs text-gray-500 mt-1">Chunks indexados</div>
      </div>
      <div className="bg-white border rounded-xl p-4 text-center">
        <div className="text-2xl font-bold text-green-600">{data.by_status["indexed"] ?? 0}</div>
        <div className="text-xs text-gray-500 mt-1">Prontos para busca</div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function KnowledgeBase() {
  const qc = useQueryClient();

  const { data: documents = [], isLoading, refetch } = useQuery({
    queryKey: ["knowledge-documents"],
    queryFn: knowledgeApi.list,
    refetchInterval: (query) => {
      const docs = query.state.data ?? [];
      return docs.some((d) => isInProgress(d.status)) ? 4000 : false;
    },
  });

  const uploadMut = useMutation({
    mutationFn: ({ file, name, desc }: { file: File; name?: string; desc?: string }) =>
      knowledgeApi.upload(file, name, desc),
    onSuccess: () => {
      toast.success("Documento enviado — indexação em andamento");
      qc.invalidateQueries({ queryKey: ["knowledge-documents"] });
      qc.invalidateQueries({ queryKey: ["knowledge-stats"] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Falha ao enviar documento"),
  });

  const deleteMut = useMutation({
    mutationFn: knowledgeApi.remove,
    onSuccess: () => {
      toast.success("Documento removido");
      qc.invalidateQueries({ queryKey: ["knowledge-documents"] });
      qc.invalidateQueries({ queryKey: ["knowledge-stats"] });
    },
    onError: () => toast.error("Falha ao remover documento"),
  });

  const reindexMut = useMutation({
    mutationFn: knowledgeApi.reindex,
    onSuccess: () => {
      toast.success("Re-indexação iniciada");
      qc.invalidateQueries({ queryKey: ["knowledge-documents"] });
    },
    onError: () => toast.error("Falha ao re-indexar"),
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      knowledgeApi.toggleActive(id, is_active),
    onSuccess: (updated) => {
      toast.success(updated.is_active ? "Documento ativado" : "Documento desativado");
      qc.invalidateQueries({ queryKey: ["knowledge-documents"] });
    },
    onError: () => toast.error("Falha ao alterar status do documento"),
  });

  function handleUpload(file: File, name?: string, desc?: string) {
    uploadMut.mutate({ file, name, desc });
  }

  return (
    <PageWrapper
      title="Base de Conhecimento IA"
      subtitle="Documentos indexados para enriquecer o contexto do Agente IA (RAG)"
    >
      {/* Stats */}
      <StatsCard />

      <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Upload + Search */}
        <div className="space-y-5">
          <UploadZone onUpload={handleUpload} />
          <SearchPanel />

          {/* Info box */}
          <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 text-xs text-blue-700 space-y-1.5">
            <div className="flex items-center gap-1.5 font-semibold">
              <Info size={14} /> Como funciona
            </div>
            <p>Documentos enviados são divididos em chunks de ~1.500 caracteres, transformados em vetores via OpenAI e armazenados com pgvector.</p>
            <p>O <strong>Agente IA</strong> busca automaticamente os chunks mais relevantes para enriquecer suas respostas (RAG).</p>
            <p>Formatos suportados: <strong>PDF, DOCX, Markdown, TXT</strong></p>
          </div>
        </div>

        {/* Right: Document list */}
        <div className="lg:col-span-2 bg-white border rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b">
            <div className="flex items-center gap-2">
              <BookOpen size={16} className="text-gray-500" />
              <h3 className="text-sm font-semibold text-gray-700">Documentos</h3>
              <span className="text-xs text-gray-400">({documents.length})</span>
            </div>
            <button
              onClick={() => { refetch(); qc.invalidateQueries({ queryKey: ["knowledge-stats"] }); }}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700"
            >
              <RefreshCw size={13} /> Atualizar
            </button>
          </div>

          {isLoading && (
            <div className="flex items-center justify-center gap-2 py-12 text-gray-400">
              <Loader2 size={18} className="animate-spin" /> Carregando...
            </div>
          )}

          {!isLoading && documents.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-14 text-gray-400">
              <BookOpen size={32} />
              <p className="text-sm">Nenhum documento ainda.</p>
              <p className="text-xs">Envie um PDF, DOCX ou Markdown para começar.</p>
            </div>
          )}

          {!isLoading && documents.length > 0 && (
            <div className="divide-y">
              {documents.map((doc: KnowledgeDocument) => (
                <div key={doc.id} className={`px-5 py-3 hover:bg-gray-50 flex items-start gap-3 ${!doc.is_active ? "opacity-50" : ""}`}>
                  {/* Type badge */}
                  <div className="shrink-0 mt-0.5 w-10 h-10 rounded-lg bg-brand-50 flex items-center justify-center">
                    <span className="text-xs font-bold text-brand-700">
                      {FILE_TYPE_ICON[doc.file_type] ?? doc.file_type.toUpperCase()}
                    </span>
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-gray-800 truncate">{doc.name}</span>
                      <StatusBadge status={doc.status} />
                    </div>
                    {doc.description && (
                      <p className="text-xs text-gray-500 mt-0.5 truncate">{doc.description}</p>
                    )}
                    <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
                      <span>{fmtSize(doc.file_size)}</span>
                      {doc.status === "indexed" && (
                        <span className="text-green-600 font-medium">{doc.chunk_count} chunks</span>
                      )}
                      <span>{fmtDate(doc.created_at)}</span>
                    </div>
                    {doc.status === "failed" && doc.error && (
                      <div className="mt-1.5 flex items-start gap-1.5 text-xs text-red-600">
                        <AlertCircle size={12} className="mt-0.5 shrink-0" />
                        <span>{doc.error}</span>
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 shrink-0">
                    {/* Active toggle */}
                    <button
                      onClick={() => toggleMut.mutate({ id: doc.id, is_active: !doc.is_active })}
                      disabled={toggleMut.isPending}
                      title={doc.is_active ? "Clique para desativar (o agente não usará este doc)" : "Clique para ativar"}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none ${
                        doc.is_active ? "bg-green-500" : "bg-gray-300"
                      }`}
                    >
                      <span
                        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
                          doc.is_active ? "translate-x-4.5" : "translate-x-0.5"
                        }`}
                      />
                    </button>

                    {(doc.status === "indexed" || doc.status === "failed") && (
                      <button
                        onClick={() => reindexMut.mutate(doc.id)}
                        disabled={reindexMut.isPending}
                        className="p-1.5 text-gray-400 hover:text-brand-600 rounded"
                        title="Re-indexar"
                      >
                        <RefreshCw size={14} />
                      </button>
                    )}
                    <button
                      onClick={() => {
                        if (confirm(`Remover "${doc.name}"?`)) deleteMut.mutate(doc.id);
                      }}
                      className="p-1.5 text-gray-300 hover:text-red-500 rounded"
                      title="Remover"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </PageWrapper>
  );
}
