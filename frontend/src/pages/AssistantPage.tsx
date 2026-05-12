import { useEffect, useRef, useState, useCallback } from "react";
import {
  Bot, Send, Loader2, Plus, Trash2, Sparkles, Database,
  Pin, PinOff, FolderOpen, Folder, Users, MoreHorizontal,
  Pencil, Share2, FolderInput, Check, X, ChevronRight, ChevronDown,
} from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import {
  useAssistantStore,
  type AssistantMessage,
  type AssistantSession,
  type AssistantFolder,
} from "../store/assistantStore";
import { assistantApi } from "../api/assistant";
import toast from "react-hot-toast";

// ── Paleta de cores para pastas ───────────────────────────────────────────────

const FOLDER_COLORS = [
  "#6366f1", "#3b82f6", "#10b981", "#f59e0b",
  "#ef4444", "#ec4899", "#8b5cf6", "#64748b",
];

// ── MessageBubble ─────────────────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: AssistantMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <div className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
        isUser ? "bg-brand-600" : "bg-gray-700"
      }`}>
        {isUser
          ? <span className="text-white text-xs font-bold">U</span>
          : <Bot size={15} className="text-white" />}
      </div>
      <div className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap break-words ${
        isUser
          ? "bg-brand-600 text-white rounded-tr-sm"
          : "bg-gray-100 text-gray-900 rounded-tl-sm"
      }`}>
        {msg.content}
        {!isUser && (
          <div className="mt-1.5 flex items-center gap-2 flex-wrap">
            {msg.model && (
              <span className="text-[10px] text-gray-400 font-medium">{msg.model}</span>
            )}
            {msg.ragContextUsed && (
              <span className="flex items-center gap-0.5 text-[10px] text-blue-500">
                <Database size={9} />RAG
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── SessionMenu (dropdown "...") ──────────────────────────────────────────────

interface SessionMenuProps {
  session: AssistantSession;
  folders: AssistantFolder[];
  onRename: () => void;
  onPin: () => void;
  onShare: () => void;
  onMove: (folderId: string | null) => void;
  onDelete: () => void;
  isOwn: boolean;
}

function SessionMenu({ session, folders, onRename, onPin, onShare, onMove, onDelete, isOwn }: SessionMenuProps) {
  const [open, setOpen] = useState(false);
  const [showFolders, setShowFolders] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setShowFolders(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  if (!isOwn) return null;

  const personalFolders = folders.filter((f) => !f.isTeam);
  const teamFolders = folders.filter((f) => f.isTeam);

  return (
    <div ref={ref} className="relative" onClick={(e) => e.stopPropagation()}>
      <button
        onClick={() => { setOpen(!open); setShowFolders(false); }}
        className="opacity-0 group-hover:opacity-100 p-0.5 rounded text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-all"
      >
        <MoreHorizontal size={13} />
      </button>

      {open && (
        <div className="absolute right-0 top-6 z-50 w-48 bg-white rounded-xl shadow-lg border border-gray-100 py-1 text-xs">
          <button
            onClick={() => { onRename(); setOpen(false); }}
            className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-50 text-gray-700"
          >
            <Pencil size={12} /> Renomear
          </button>

          <button
            onClick={() => { onPin(); setOpen(false); }}
            className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-50 text-gray-700"
          >
            {session.pinned ? <PinOff size={12} /> : <Pin size={12} />}
            {session.pinned ? "Desafixar" : "Fixar no topo"}
          </button>

          <button
            onClick={() => { onShare(); setOpen(false); }}
            className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-50 text-gray-700"
          >
            <Share2 size={12} />
            {session.isShared ? "Parar de compartilhar" : "Compartilhar com equipe"}
          </button>

          {/* Mover para pasta */}
          <div className="relative">
            <button
              onClick={() => setShowFolders(!showFolders)}
              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-50 text-gray-700"
            >
              <FolderInput size={12} />
              <span className="flex-1 text-left">Mover para pasta</span>
              <ChevronRight size={10} />
            </button>

            {showFolders && (
              <div className="absolute left-full top-0 ml-1 w-44 bg-white rounded-xl shadow-lg border border-gray-100 py-1 text-xs max-h-48 overflow-y-auto">
                <button
                  onClick={() => { onMove(null); setOpen(false); setShowFolders(false); }}
                  className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-50 text-gray-500 italic"
                >
                  Sem pasta
                </button>
                {personalFolders.length > 0 && (
                  <div className="px-3 py-1 text-[10px] text-gray-400 uppercase tracking-wider">Minhas pastas</div>
                )}
                {personalFolders.map((f) => (
                  <button
                    key={f.id}
                    onClick={() => { onMove(f.id); setOpen(false); setShowFolders(false); }}
                    className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-50 text-gray-700"
                  >
                    <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: f.color }} />
                    <span className="truncate">{f.name}</span>
                    {session.folderId === f.id && <Check size={10} className="text-brand-500 ml-auto" />}
                  </button>
                ))}
                {teamFolders.length > 0 && (
                  <div className="px-3 py-1 text-[10px] text-gray-400 uppercase tracking-wider">Equipe</div>
                )}
                {teamFolders.map((f) => (
                  <button
                    key={f.id}
                    onClick={() => { onMove(f.id); setOpen(false); setShowFolders(false); }}
                    className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-50 text-gray-700"
                  >
                    <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: f.color }} />
                    <span className="truncate">{f.name}</span>
                    {session.folderId === f.id && <Check size={10} className="text-brand-500 ml-auto" />}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="border-t border-gray-100 my-1" />
          <button
            onClick={() => { onDelete(); setOpen(false); }}
            className="w-full flex items-center gap-2 px-3 py-2 hover:bg-red-50 text-red-500"
          >
            <Trash2 size={12} /> Excluir
          </button>
        </div>
      )}
    </div>
  );
}

// ── SessionItem ───────────────────────────────────────────────────────────────

interface SessionItemProps {
  session: AssistantSession;
  isActive: boolean;
  isOwn: boolean;
  folders: AssistantFolder[];
  onClick: () => void;
  onRename: (id: string, newTitle: string) => void;
  onPin: (id: string) => void;
  onShare: (id: string) => void;
  onMove: (id: string, folderId: string | null) => void;
  onDelete: (id: string) => void;
}

function SessionItem({
  session, isActive, isOwn, folders, onClick,
  onRename, onPin, onShare, onMove, onDelete,
}: SessionItemProps) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(session.title ?? "");

  const commitRename = () => {
    const v = editValue.trim();
    if (v && v !== session.title) onRename(session.id, v);
    setEditing(false);
  };

  return (
    <div
      onClick={editing ? undefined : onClick}
      className={`group flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer transition-colors ${
        isActive ? "bg-brand-50 text-brand-700" : "hover:bg-gray-50 text-gray-600"
      }`}
    >
      {editing ? (
        <input
          autoFocus
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onBlur={commitRename}
          onKeyDown={(e) => {
            if (e.key === "Enter") commitRename();
            if (e.key === "Escape") setEditing(false);
          }}
          onClick={(e) => e.stopPropagation()}
          className="flex-1 text-xs border border-brand-300 rounded px-1.5 py-0.5 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
      ) : (
        <>
          <span className="flex-1 text-xs truncate">
            {session.title ?? "Sem título"}
          </span>
          {session.pinned && <Pin size={10} className="shrink-0 text-gray-400" />}
          {session.isShared && <Share2 size={10} className="shrink-0 text-blue-400" />}
          {session.userName && (
            <span className="text-[10px] text-gray-400 shrink-0 truncate max-w-[60px]">
              {session.userName.split(" ")[0]}
            </span>
          )}
          <SessionMenu
            session={session}
            folders={folders}
            isOwn={isOwn}
            onRename={() => { setEditing(true); setEditValue(session.title ?? ""); }}
            onPin={() => onPin(session.id)}
            onShare={() => onShare(session.id)}
            onMove={(fid) => onMove(session.id, fid)}
            onDelete={() => onDelete(session.id)}
          />
        </>
      )}
    </div>
  );
}

// ── FolderSection ─────────────────────────────────────────────────────────────

interface FolderSectionProps {
  folder: AssistantFolder;
  sessions: AssistantSession[];
  currentSessionId: string | null;
  folders: AssistantFolder[];
  onSelectSession: (id: string) => void;
  onRenameSession: (id: string, title: string) => void;
  onPinSession: (id: string) => void;
  onShareSession: (id: string) => void;
  onMoveSession: (id: string, folderId: string | null) => void;
  onDeleteSession: (id: string) => void;
  onRenameFolder: (id: string) => void;
  onDeleteFolder: (id: string) => void;
  currentUserId?: string;
}

function FolderSection({
  folder, sessions, currentSessionId, folders,
  onSelectSession, onRenameSession, onPinSession, onShareSession,
  onMoveSession, onDeleteSession, onRenameFolder, onDeleteFolder,
  currentUserId,
}: FolderSectionProps) {
  const [expanded, setExpanded] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  return (
    <div>
      <div className="group flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-gray-50">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1.5 flex-1 min-w-0"
        >
          {expanded ? <ChevronDown size={11} className="shrink-0 text-gray-400" /> : <ChevronRight size={11} className="shrink-0 text-gray-400" />}
          <span className="w-3 h-3 rounded-sm shrink-0" style={{ background: folder.color }} />
          {folder.isTeam
            ? <Users size={11} className="shrink-0 text-gray-500" />
            : <Folder size={11} className="shrink-0 text-gray-500" />}
          <span className="text-xs text-gray-600 truncate">{folder.name}</span>
          {sessions.length > 0 && (
            <span className="text-[10px] text-gray-400 ml-auto shrink-0">{sessions.length}</span>
          )}
        </button>

        <div ref={menuRef} className="relative shrink-0">
          <button
            onClick={(e) => { e.stopPropagation(); setMenuOpen(!menuOpen); }}
            className="opacity-0 group-hover:opacity-100 p-0.5 rounded text-gray-400 hover:text-gray-700 hover:bg-gray-100"
          >
            <MoreHorizontal size={12} />
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-5 z-50 w-36 bg-white rounded-xl shadow-lg border border-gray-100 py-1 text-xs">
              <button
                onClick={() => { onRenameFolder(folder.id); setMenuOpen(false); }}
                className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-50 text-gray-700"
              >
                <Pencil size={11} /> Renomear
              </button>
              <div className="border-t border-gray-100 my-1" />
              <button
                onClick={() => { onDeleteFolder(folder.id); setMenuOpen(false); }}
                className="w-full flex items-center gap-2 px-3 py-2 hover:bg-red-50 text-red-500"
              >
                <Trash2 size={11} /> Excluir pasta
              </button>
            </div>
          )}
        </div>
      </div>

      {expanded && (
        <div className="pl-5 space-y-0.5 mt-0.5">
          {sessions.length === 0 && (
            <p className="text-[10px] text-gray-400 px-2 py-1 italic">Pasta vazia</p>
          )}
          {sessions.map((s) => (
            <SessionItem
              key={s.id}
              session={s}
              isActive={s.id === currentSessionId}
              isOwn={!s.userName}
              folders={folders}
              onClick={() => onSelectSession(s.id)}
              onRename={onRenameSession}
              onPin={onPinSession}
              onShare={onShareSession}
              onMove={onMoveSession}
              onDelete={onDeleteSession}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── CreateFolderModal ─────────────────────────────────────────────────────────

interface CreateFolderModalProps {
  isTeam: boolean;
  onClose: () => void;
  onCreate: (name: string, color: string, isTeam: boolean) => void;
}

function CreateFolderModal({ isTeam, onClose, onCreate }: CreateFolderModalProps) {
  const [name, setName] = useState("");
  const [color, setColor] = useState(FOLDER_COLORS[0]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-2xl shadow-2xl w-80 p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-800">
            {isTeam ? "Nova pasta da equipe" : "Nova pasta"}
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={16} />
          </button>
        </div>

        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && name.trim()) onCreate(name.trim(), color, isTeam);
            if (e.key === "Escape") onClose();
          }}
          placeholder="Nome da pasta..."
          className="w-full text-sm border border-gray-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500 mb-4"
        />

        <div className="flex gap-2 flex-wrap mb-5">
          {FOLDER_COLORS.map((c) => (
            <button
              key={c}
              onClick={() => setColor(c)}
              className={`w-6 h-6 rounded-full transition-transform ${color === c ? "ring-2 ring-offset-1 ring-gray-400 scale-110" : ""}`}
              style={{ background: c }}
            />
          ))}
        </div>

        <div className="flex gap-2">
          <button
            onClick={onClose}
            className="flex-1 text-xs border border-gray-200 rounded-xl py-2 hover:bg-gray-50 text-gray-600"
          >
            Cancelar
          </button>
          <button
            onClick={() => name.trim() && onCreate(name.trim(), color, isTeam)}
            disabled={!name.trim()}
            className="flex-1 text-xs bg-brand-600 hover:bg-brand-700 text-white rounded-xl py-2 disabled:opacity-40"
          >
            Criar
          </button>
        </div>
      </div>
    </div>
  );
}

// ── RenameFolderModal ─────────────────────────────────────────────────────────

function RenameFolderModal({
  folder,
  onClose,
  onRename,
}: {
  folder: AssistantFolder;
  onClose: () => void;
  onRename: (name: string) => void;
}) {
  const [name, setName] = useState(folder.name);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-2xl shadow-2xl w-72 p-5">
        <h3 className="text-sm font-semibold text-gray-800 mb-3">Renomear pasta</h3>
        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && name.trim()) onRename(name.trim());
            if (e.key === "Escape") onClose();
          }}
          className="w-full text-sm border border-gray-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500 mb-4"
        />
        <div className="flex gap-2">
          <button onClick={onClose} className="flex-1 text-xs border border-gray-200 rounded-xl py-2 hover:bg-gray-50 text-gray-600">Cancelar</button>
          <button
            onClick={() => name.trim() && onRename(name.trim())}
            disabled={!name.trim()}
            className="flex-1 text-xs bg-brand-600 hover:bg-brand-700 text-white rounded-xl py-2 disabled:opacity-40"
          >Salvar</button>
        </div>
      </div>
    </div>
  );
}

// ── AssistantPage ─────────────────────────────────────────────────────────────

export function AssistantPage() {
  const {
    currentSessionId, messages, sessions, teamSessions, folders,
    loading, selectedModel, openaiAvailable,
    setModel, setLoading, setOpenaiAvailable,
    addMessage, setMessages, setSessions, setTeamSessions,
    setFolders, setCurrentSessionId, newSession,
    updateSession, removeSession, addFolder, updateFolder, removeFolder,
  } = useAssistantStore();

  const [input, setInput] = useState("");
  const [createFolderModal, setCreateFolderModal] = useState<{ isTeam: boolean } | null>(null);
  const [renameFolderTarget, setRenameFolderTarget] = useState<AssistantFolder | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Carregamento inicial
  useEffect(() => {
    assistantApi.capabilities().then((c) => setOpenaiAvailable(c.openai_available)).catch(() => {});
    assistantApi.listSessions().then(setSessions).catch(() => {});
    assistantApi.listTeamSessions().then(setTeamSessions).catch(() => {});
    assistantApi.listFolders().then(setFolders).catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // ── Session actions ─────────────────────────────────────────────────────────

  const loadSession = useCallback(async (id: string) => {
    setLoading(true);
    try {
      const { session, messages: msgs } = await assistantApi.getSession(id);
      setCurrentSessionId(session.id);
      setMessages(msgs);
    } catch {
      toast.error("Erro ao carregar sessão.");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleRenameSession = useCallback(async (id: string, title: string) => {
    try {
      const s = await assistantApi.renameSession(id, title);
      updateSession(id, { title: s.title });
    } catch {
      toast.error("Erro ao renomear.");
    }
  }, []);

  const handlePinSession = useCallback(async (id: string) => {
    const session = [...sessions, ...teamSessions].find((s) => s.id === id);
    if (!session) return;
    try {
      const s = await assistantApi.pinSession(id, !session.pinned);
      updateSession(id, { pinned: s.pinned });
    } catch {
      toast.error("Erro ao fixar sessão.");
    }
  }, [sessions, teamSessions]);

  const handleShareSession = useCallback(async (id: string) => {
    const session = sessions.find((s) => s.id === id);
    if (!session) return;
    try {
      const s = await assistantApi.shareSession(id, !session.isShared);
      updateSession(id, { isShared: s.isShared });
      toast.success(s.isShared ? "Sessão compartilhada com a equipe." : "Compartilhamento removido.");
      assistantApi.listTeamSessions().then(setTeamSessions).catch(() => {});
    } catch {
      toast.error("Erro ao compartilhar sessão.");
    }
  }, [sessions]);

  const handleMoveSession = useCallback(async (id: string, folderId: string | null) => {
    try {
      const s = await assistantApi.moveSession(id, folderId);
      updateSession(id, { folderId: s.folderId });
    } catch {
      toast.error("Erro ao mover sessão.");
    }
  }, []);

  const handleDeleteSession = useCallback(async (id: string) => {
    try {
      await assistantApi.deleteSession(id);
      removeSession(id);
      toast.success("Sessão removida.");
    } catch {
      toast.error("Erro ao remover sessão.");
    }
  }, []);

  // ── Folder actions ──────────────────────────────────────────────────────────

  const handleCreateFolder = useCallback(async (name: string, color: string, isTeam: boolean) => {
    setCreateFolderModal(null);
    try {
      const f = await assistantApi.createFolder({ name, color, is_team: isTeam });
      addFolder(f);
    } catch {
      toast.error("Erro ao criar pasta.");
    }
  }, []);

  const handleRenameFolder = useCallback(async (id: string, name: string) => {
    setRenameFolderTarget(null);
    try {
      const f = await assistantApi.updateFolder(id, { name });
      updateFolder(id, { name: f.name });
    } catch {
      toast.error("Erro ao renomear pasta.");
    }
  }, []);

  const handleDeleteFolder = useCallback(async (id: string) => {
    try {
      await assistantApi.deleteFolder(id);
      removeFolder(id);
      toast.success("Pasta removida. Conversas mantidas sem pasta.");
    } catch {
      toast.error("Erro ao remover pasta.");
    }
  }, []);

  // ── Send message ─────────────────────────────────────────────────────────────

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: AssistantMessage = {
      id: `user-${Date.now()}`,
      sessionId: currentSessionId ?? "",
      role: "user",
      content: text,
      ragContextUsed: false,
      createdAt: new Date().toISOString(),
    };
    addMessage(userMsg);
    setInput("");
    setLoading(true);

    try {
      const aiMsg = await assistantApi.chat({
        content: text,
        session_id: currentSessionId,
        model: selectedModel === "openai" ? "openai" : null,
      });
      if (!currentSessionId) {
        setCurrentSessionId(aiMsg.sessionId);
        assistantApi.listSessions().then(setSessions).catch(() => {});
      }
      addMessage(aiMsg);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Erro ao comunicar com o assistente.";
      toast.error(msg);
      addMessage({
        id: `err-${Date.now()}`,
        sessionId: currentSessionId ?? "",
        role: "assistant",
        content: "Desculpe, ocorreu um erro. Tente novamente.",
        ragContextUsed: false,
        createdAt: new Date().toISOString(),
      });
    } finally {
      setLoading(false);
    }
  };

  // ── Derived sidebar data ──────────────────────────────────────────────────────

  const pinnedSessions = sessions.filter((s) => s.pinned);
  const personalFolders = folders.filter((f) => !f.isTeam);
  const teamFolders = folders.filter((f) => f.isTeam);
  const unfiledSessions = sessions.filter((s) => !s.pinned && !s.folderId);

  const sessionsInFolder = (folderId: string) =>
    sessions.filter((s) => s.folderId === folderId);

  const teamSessionsInFolder = (folderId: string) =>
    teamSessions.filter((s) => s.folderId === folderId);

  const unfiledTeamSessions = teamSessions.filter((s) => !s.folderId);

  const currentSession = [...sessions, ...teamSessions].find((s) => s.id === currentSessionId);
  const allFolders = folders;

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <PageWrapper
      title="Assistente IA"
      subtitle="Somente leitura · consulte dispositivos, compliance e operações em linguagem natural"
    >
      <div className="flex gap-4 h-[calc(100vh-140px)] min-h-0">

        {/* ── Sidebar esquerda ──────────────────────────────────────────────── */}
        <div className="w-64 shrink-0 bg-white rounded-xl border border-gray-200 flex flex-col overflow-hidden">

          {/* Nova conversa */}
          <div className="p-3 shrink-0">
            <button
              onClick={() => newSession()}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-xs font-medium transition-colors"
            >
              <Plus size={14} /> Nova conversa
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-2 pb-3 space-y-3">

            {/* Fixadas */}
            {pinnedSessions.length > 0 && (
              <div>
                <div className="flex items-center gap-1 px-2 py-1">
                  <Pin size={10} className="text-gray-400" />
                  <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Fixadas</span>
                </div>
                <div className="space-y-0.5">
                  {pinnedSessions.map((s) => (
                    <SessionItem
                      key={s.id}
                      session={s}
                      isActive={s.id === currentSessionId}
                      isOwn
                      folders={allFolders}
                      onClick={() => loadSession(s.id)}
                      onRename={handleRenameSession}
                      onPin={handlePinSession}
                      onShare={handleShareSession}
                      onMove={handleMoveSession}
                      onDelete={handleDeleteSession}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Minhas pastas */}
            <div>
              <div className="flex items-center justify-between px-2 py-1">
                <div className="flex items-center gap-1">
                  <FolderOpen size={10} className="text-gray-400" />
                  <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Minhas pastas</span>
                </div>
                <button
                  onClick={() => setCreateFolderModal({ isTeam: false })}
                  title="Nova pasta"
                  className="text-gray-400 hover:text-brand-600 transition-colors"
                >
                  <Plus size={12} />
                </button>
              </div>
              {personalFolders.length === 0 && (
                <p className="text-[10px] text-gray-400 px-2 py-1 italic">Nenhuma pasta criada.</p>
              )}
              <div className="space-y-0.5">
                {personalFolders.map((f) => (
                  <FolderSection
                    key={f.id}
                    folder={f}
                    sessions={sessionsInFolder(f.id)}
                    currentSessionId={currentSessionId}
                    folders={allFolders}
                    onSelectSession={loadSession}
                    onRenameSession={handleRenameSession}
                    onPinSession={handlePinSession}
                    onShareSession={handleShareSession}
                    onMoveSession={handleMoveSession}
                    onDeleteSession={handleDeleteSession}
                    onRenameFolder={(id) => setRenameFolderTarget(folders.find((x) => x.id === id)!)}
                    onDeleteFolder={handleDeleteFolder}
                  />
                ))}
              </div>
            </div>

            {/* Recentes (sem pasta) */}
            {unfiledSessions.length > 0 && (
              <div>
                <div className="flex items-center gap-1 px-2 py-1">
                  <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Recentes</span>
                </div>
                <div className="space-y-0.5">
                  {unfiledSessions.map((s) => (
                    <SessionItem
                      key={s.id}
                      session={s}
                      isActive={s.id === currentSessionId}
                      isOwn
                      folders={allFolders}
                      onClick={() => loadSession(s.id)}
                      onRename={handleRenameSession}
                      onPin={handlePinSession}
                      onShare={handleShareSession}
                      onMove={handleMoveSession}
                      onDelete={handleDeleteSession}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Equipe */}
            <div>
              <div className="flex items-center justify-between px-2 py-1">
                <div className="flex items-center gap-1">
                  <Users size={10} className="text-gray-400" />
                  <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Equipe</span>
                </div>
                <button
                  onClick={() => setCreateFolderModal({ isTeam: true })}
                  title="Nova pasta da equipe"
                  className="text-gray-400 hover:text-brand-600 transition-colors"
                >
                  <Plus size={12} />
                </button>
              </div>

              {teamFolders.length === 0 && unfiledTeamSessions.length === 0 && (
                <p className="text-[10px] text-gray-400 px-2 py-1 italic">Nenhuma conversa compartilhada.</p>
              )}

              <div className="space-y-0.5">
                {teamFolders.map((f) => (
                  <FolderSection
                    key={f.id}
                    folder={f}
                    sessions={teamSessionsInFolder(f.id)}
                    currentSessionId={currentSessionId}
                    folders={allFolders}
                    onSelectSession={loadSession}
                    onRenameSession={handleRenameSession}
                    onPinSession={handlePinSession}
                    onShareSession={handleShareSession}
                    onMoveSession={handleMoveSession}
                    onDeleteSession={handleDeleteSession}
                    onRenameFolder={(id) => setRenameFolderTarget(folders.find((x) => x.id === id)!)}
                    onDeleteFolder={handleDeleteFolder}
                  />
                ))}
                {unfiledTeamSessions.map((s) => (
                  <SessionItem
                    key={s.id}
                    session={s}
                    isActive={s.id === currentSessionId}
                    isOwn={false}
                    folders={allFolders}
                    onClick={() => loadSession(s.id)}
                    onRename={handleRenameSession}
                    onPin={handlePinSession}
                    onShare={handleShareSession}
                    onMove={handleMoveSession}
                    onDelete={handleDeleteSession}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ── Área de chat ──────────────────────────────────────────────────── */}
        <div className="flex-1 bg-white rounded-xl border border-gray-200 flex flex-col min-w-0 overflow-hidden">

          {/* Header */}
          <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2 min-w-0">
              <Sparkles size={15} className="text-brand-500 shrink-0" />
              <span className="text-sm font-semibold text-gray-800 truncate">
                {currentSession?.title ?? "Nova conversa"}
              </span>
              {currentSession?.isShared && (
                <span className="text-[10px] bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full flex items-center gap-1 shrink-0">
                  <Share2 size={9} /> Compartilhada
                </span>
              )}
            </div>
            {openaiAvailable && (
              <button
                onClick={() => setModel(selectedModel === "claude" ? "openai" : "claude")}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 text-gray-600 transition-colors shrink-0"
              >
                <Bot size={12} />
                Modelo: {selectedModel === "claude" ? "Claude" : "GPT-4o"}
              </button>
            )}
          </div>

          {/* Mensagens */}
          <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4 min-h-0">
            {messages.length === 0 && (
              <div className="text-center text-gray-400 mt-20 select-none">
                <Sparkles size={40} className="mx-auto mb-3 opacity-20" />
                <p className="font-medium text-base">Como posso ajudar?</p>
                <p className="text-sm mt-1 text-gray-300 max-w-sm mx-auto">
                  Pergunte sobre dispositivos, compliance, operações recentes ou boas práticas de segurança.
                </p>
              </div>
            )}
            {messages.map((msg) => (
              <MessageBubble key={msg.id} msg={msg} />
            ))}
            {loading && (
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center shrink-0">
                  <Bot size={15} className="text-white" />
                </div>
                <div className="bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-3">
                  <Loader2 size={15} className="animate-spin text-gray-500" />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="px-5 py-4 border-t border-gray-100 shrink-0">
            <div className="flex gap-3">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
                }}
                placeholder="Pergunte sobre sua infraestrutura… (Enter para enviar)"
                disabled={loading}
                rows={2}
                className="flex-1 text-sm border border-gray-200 rounded-xl px-4 py-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:bg-gray-50"
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || loading}
                className="self-end w-10 h-10 bg-brand-600 hover:bg-brand-700 text-white rounded-xl flex items-center justify-center disabled:opacity-40 transition-colors shrink-0"
              >
                <Send size={16} />
              </button>
            </div>
            <p className="text-[11px] text-gray-400 mt-2">
              Este assistente não executa operações.
              {openaiAvailable && (
                <> Modelo: <strong>{selectedModel === "openai" ? "GPT-4o" : "Claude"}</strong>.</>
              )}
            </p>
          </div>
        </div>
      </div>

      {/* Modais */}
      {createFolderModal && (
        <CreateFolderModal
          isTeam={createFolderModal.isTeam}
          onClose={() => setCreateFolderModal(null)}
          onCreate={handleCreateFolder}
        />
      )}
      {renameFolderTarget && (
        <RenameFolderModal
          folder={renameFolderTarget}
          onClose={() => setRenameFolderTarget(null)}
          onRename={(name) => handleRenameFolder(renameFolderTarget.id, name)}
        />
      )}
    </PageWrapper>
  );
}
