import { useState, useCallback, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus, Play, Pause, Trash2, Zap, Clock, CheckCircle, XCircle,
  Loader2, X, ChevronDown, GitBranch, BarChart3, Settings2,
  ArrowRight, Circle, Square,
} from "lucide-react";
import toast from "react-hot-toast";
import { playbooksApi } from "../api/playbooks";
import type { PlaybookRule, PlaybookCreate, BuilderState } from "../api/playbooks";

type Tab = "playbooks" | "executions" | "mttr";

const EXEC_STATUS_COLORS: Record<string, string> = {
  running: "bg-blue-100 text-blue-700",
  success: "bg-green-100 text-green-700",
  partial: "bg-yellow-100 text-yellow-700",
  failed:  "bg-red-100 text-red-700",
};

const TRIGGER_LABELS: Record<string, string> = {
  risk_score_drop: "Risk Score Crítico",
  anomaly_detected: "Anomalia Detectada",
  guardrail_block: "Guardrail Bloqueado",
  device_unreachable: "Device Inacessível",
  siem_alert: "Alerta SIEM",
  identity_anomaly: "Anomalia de Identidade",
  jit_abuse: "Abuso de JIT",
  sod_violation: "Violação de SoD",
};

const ACTION_LABELS: Record<string, string> = {
  notify_slack: "Notificar Slack",
  notify_email: "Notificar Email",
  escalate_to_n2: "Escalar para N2",
  ad_disable_user: "Desabilitar Conta AD",
  revoke_jit_access: "Revogar JIT",
  run_snapshot: "Capturar Snapshot",
  create_ticket_jira: "Criar Ticket Jira",
  isolate_device: "Isolar Device",
};

const STATUS_COLORS: Record<string, string> = {
  running: "bg-blue-100 text-blue-700",
  success: "bg-green-100 text-green-700",
  partial: "bg-yellow-100 text-yellow-700",
  failed: "bg-red-100 text-red-700",
};

// ── Simple Canvas Builder ─────────────────────────────────────────────────────
type CanvasNode = {
  id: string;
  type: "trigger" | "action" | "condition";
  position: { x: number; y: number };
  data: Record<string, unknown>;
};

type CanvasEdge = { id: string; source: string; target: string };

const PALETTE_ITEMS = [
  { type: "trigger" as const, label: "Trigger", color: "bg-purple-100 border-purple-300 text-purple-800" },
  { type: "action" as const, label: "Ação", color: "bg-green-100 border-green-300 text-green-800" },
  { type: "condition" as const, label: "Condição", color: "bg-blue-100 border-blue-300 text-blue-800" },
];

function PlaybookBuilder({
  playbook,
  onClose,
}: {
  playbook: PlaybookRule;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const { data: initialState } = useQuery({
    queryKey: ["builder", playbook.id],
    queryFn: () => playbooksApi.getBuilder(playbook.id),
  });

  const [nodes, setNodes] = useState<CanvasNode[]>(() => {
    if (initialState?.nodes?.length) return initialState.nodes as CanvasNode[];
    // Bootstrap from playbook data
    const boot: CanvasNode[] = [
      {
        id: "trigger-1",
        type: "trigger",
        position: { x: 80, y: 120 },
        data: { type: playbook.trigger_type, condition: playbook.trigger_condition },
      },
      ...playbook.actions.map((a, i) => ({
        id: `action-${i + 1}`,
        type: "action" as const,
        position: { x: 320 + i * 180, y: 120 },
        data: a,
      })),
    ];
    return boot;
  });

  const [edges, setEdges] = useState<CanvasEdge[]>(() => {
    if (initialState?.edges?.length) return initialState.edges;
    return playbook.actions.map((_, i) => ({
      id: `e-t-a${i + 1}`,
      source: "trigger-1",
      target: `action-${i + 1}`,
    }));
  });

  const [selectedNode, setSelectedNode] = useState<CanvasNode | null>(null);
  const [dragging, setDragging] = useState<{ id: string; dx: number; dy: number } | null>(null);
  const [connecting, setConnecting] = useState<string | null>(null);
  const canvasRef = useRef<SVGSVGElement>(null);

  const saveMut = useMutation({
    mutationFn: (state: BuilderState) => playbooksApi.saveBuilder(playbook.id, state),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["playbooks"] }); toast.success("Builder salvo"); },
    onError: () => toast.error("Erro ao salvar"),
  });

  // ── Drag nodes ───────────────────────────────────────────────────────────────
  const handleMouseDown = useCallback((e: React.MouseEvent, nodeId: string) => {
    e.stopPropagation();
    const node = nodes.find(n => n.id === nodeId)!;
    setDragging({ id: nodeId, dx: e.clientX - node.position.x, dy: e.clientY - node.position.y });
  }, [nodes]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragging) return;
    setNodes(prev => prev.map(n =>
      n.id === dragging.id
        ? { ...n, position: { x: e.clientX - dragging.dx, y: e.clientY - dragging.dy } }
        : n
    ));
  }, [dragging]);

  const handleMouseUp = useCallback(() => setDragging(null), []);

  // ── Add node from palette ────────────────────────────────────────────────────
  function addNode(type: "trigger" | "action" | "condition") {
    const id = `${type}-${Date.now()}`;
    const newNode: CanvasNode = {
      id, type,
      position: { x: 100 + Math.random() * 300, y: 80 + Math.random() * 200 },
      data: type === "trigger" ? { type: "siem_alert", condition: {} }
        : type === "action" ? { type: "notify_slack", params: {} }
        : { expression: "" },
    };
    setNodes(prev => [...prev, newNode]);
    setSelectedNode(newNode);
  }

  // ── Connect nodes ────────────────────────────────────────────────────────────
  function handleConnectStart(e: React.MouseEvent, nodeId: string) {
    e.stopPropagation();
    setConnecting(nodeId);
  }

  function handleConnectEnd(e: React.MouseEvent, nodeId: string) {
    if (connecting && connecting !== nodeId) {
      setEdges(prev => [...prev, { id: `e-${connecting}-${nodeId}`, source: connecting, target: nodeId }]);
    }
    setConnecting(null);
  }

  function deleteNode(id: string) {
    setNodes(prev => prev.filter(n => n.id !== id));
    setEdges(prev => prev.filter(e => e.source !== id && e.target !== id));
    if (selectedNode?.id === id) setSelectedNode(null);
  }

  const nodeColor = (type: string) => {
    if (type === "trigger") return "#7c3aed";
    if (type === "action") return "#16a34a";
    return "#2563eb";
  };

  const nodeBg = (type: string) => {
    if (type === "trigger") return "#f5f3ff";
    if (type === "action") return "#f0fdf4";
    return "#eff6ff";
  };

  const nodeLabel = (node: CanvasNode) => {
    if (node.type === "trigger") return TRIGGER_LABELS[node.data.type as string] ?? (node.data.type as string);
    if (node.type === "action") return ACTION_LABELS[node.data.type as string] ?? (node.data.type as string);
    return "Condição";
  };

  const canvasWidth = 900;
  const canvasHeight = 400;
  const nodeW = 160, nodeH = 52;

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <GitBranch size={18} className="text-brand-600" />
              Builder Visual — {playbook.name}
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">Arraste nós para reposicionar. Clique em ● para conectar.</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => saveMut.mutate({ nodes, edges })}
              disabled={saveMut.isPending}
              className="flex items-center gap-2 bg-brand-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
            >
              {saveMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
              Salvar
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Palette */}
          <div className="w-40 border-r p-3 flex flex-col gap-2 bg-gray-50 shrink-0">
            <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Paleta</p>
            {PALETTE_ITEMS.map(item => (
              <button
                key={item.type}
                onClick={() => addNode(item.type)}
                className={`w-full py-2 px-3 rounded-lg border text-xs font-medium text-left hover:opacity-80 transition-opacity ${item.color}`}
              >
                <Plus size={11} className="inline mr-1" />{item.label}
              </button>
            ))}
            <div className="border-t my-2" />
            <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Triggers</p>
            {Object.entries(TRIGGER_LABELS).slice(0, 4).map(([k, v]) => (
              <button key={k} onClick={() => {
                const id = `trigger-${Date.now()}`;
                setNodes(prev => [...prev, { id, type: "trigger", position: { x: 100, y: 80 }, data: { type: k, condition: {} } }]);
              }} className="w-full py-1.5 px-2 rounded text-left text-xs text-purple-800 bg-purple-50 hover:bg-purple-100 truncate">
                {v}
              </button>
            ))}
            <p className="text-xs font-semibold text-gray-500 uppercase mt-2 mb-1">Ações</p>
            {Object.entries(ACTION_LABELS).slice(0, 4).map(([k, v]) => (
              <button key={k} onClick={() => {
                const id = `action-${Date.now()}`;
                setNodes(prev => [...prev, { id, type: "action", position: { x: 300, y: 80 }, data: { type: k, params: {} } }]);
              }} className="w-full py-1.5 px-2 rounded text-left text-xs text-green-800 bg-green-50 hover:bg-green-100 truncate">
                {v}
              </button>
            ))}
          </div>

          {/* Canvas */}
          <div className="flex-1 overflow-auto relative bg-gray-50">
            <svg
              ref={canvasRef}
              width={canvasWidth} height={canvasHeight}
              className="block"
              style={{ background: "radial-gradient(circle, #e5e7eb 1px, transparent 1px)", backgroundSize: "20px 20px" }}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
            >
              {/* Edges */}
              {edges.map(edge => {
                const src = nodes.find(n => n.id === edge.source);
                const tgt = nodes.find(n => n.id === edge.target);
                if (!src || !tgt) return null;
                const x1 = src.position.x + nodeW;
                const y1 = src.position.y + nodeH / 2;
                const x2 = tgt.position.x;
                const y2 = tgt.position.y + nodeH / 2;
                const mx = (x1 + x2) / 2;
                return (
                  <g key={edge.id}>
                    <path
                      d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`}
                      fill="none" stroke="#6366f1" strokeWidth={2} strokeDasharray="6,3"
                    />
                    <polygon
                      points={`${x2},${y2} ${x2 - 8},${y2 - 4} ${x2 - 8},${y2 + 4}`}
                      fill="#6366f1"
                    />
                  </g>
                );
              })}

              {/* Nodes */}
              {nodes.map(node => (
                <g
                  key={node.id}
                  style={{ cursor: dragging?.id === node.id ? "grabbing" : "grab" }}
                  onMouseDown={e => handleMouseDown(e, node.id)}
                  onClick={() => setSelectedNode(node)}
                >
                  <rect
                    x={node.position.x} y={node.position.y}
                    width={nodeW} height={nodeH}
                    rx={8}
                    fill={nodeBg(node.type)}
                    stroke={selectedNode?.id === node.id ? "#6366f1" : nodeColor(node.type)}
                    strokeWidth={selectedNode?.id === node.id ? 2.5 : 1.5}
                  />
                  <text
                    x={node.position.x + 10} y={node.position.y + 20}
                    fontSize={10} fontWeight={600}
                    fill={nodeColor(node.type)} fontFamily="system-ui"
                  >
                    {node.type.toUpperCase()}
                  </text>
                  <text
                    x={node.position.x + 10} y={node.position.y + 36}
                    fontSize={11} fill="#374151" fontFamily="system-ui"
                  >
                    {nodeLabel(node).length > 18 ? nodeLabel(node).slice(0, 18) + "…" : nodeLabel(node)}
                  </text>
                  {/* Connect handle (right) */}
                  <circle
                    cx={node.position.x + nodeW} cy={node.position.y + nodeH / 2}
                    r={7} fill="white" stroke={nodeColor(node.type)} strokeWidth={2}
                    style={{ cursor: "crosshair" }}
                    onMouseDown={e => handleConnectStart(e, node.id)}
                    onMouseUp={e => handleConnectEnd(e, node.id)}
                  />
                  {/* Delete handle */}
                  <circle
                    cx={node.position.x + nodeW - 10} cy={node.position.y + 10}
                    r={8} fill="transparent"
                    onDoubleClick={e => { e.stopPropagation(); deleteNode(node.id); }}
                  />
                </g>
              ))}
            </svg>
            <p className="absolute bottom-2 right-3 text-xs text-gray-400">Duplo clique no nó para deletar · Clique em ● para conectar</p>
          </div>

          {/* Properties panel */}
          {selectedNode && (
            <div className="w-52 border-l p-4 bg-white shrink-0 overflow-y-auto">
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-semibold text-gray-700 uppercase">Propriedades</p>
                <button onClick={() => setSelectedNode(null)} className="text-gray-400 hover:text-gray-600"><X size={14} /></button>
              </div>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Tipo de nó</label>
                  <span className="text-xs text-gray-800">{selectedNode.type}</span>
                </div>
                {selectedNode.type === "trigger" && (
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Evento</label>
                    <select
                      value={selectedNode.data.type as string}
                      onChange={e => setNodes(prev => prev.map(n =>
                        n.id === selectedNode.id ? { ...n, data: { ...n.data, type: e.target.value } } : n
                      ))}
                      className="w-full border border-gray-300 rounded text-xs px-2 py-1"
                    >
                      {Object.entries(TRIGGER_LABELS).map(([k, v]) => (
                        <option key={k} value={k}>{v}</option>
                      ))}
                    </select>
                  </div>
                )}
                {selectedNode.type === "action" && (
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Ação</label>
                    <select
                      value={selectedNode.data.type as string}
                      onChange={e => setNodes(prev => prev.map(n =>
                        n.id === selectedNode.id ? { ...n, data: { ...n.data, type: e.target.value } } : n
                      ))}
                      className="w-full border border-gray-300 rounded text-xs px-2 py-1"
                    >
                      {Object.entries(ACTION_LABELS).map(([k, v]) => (
                        <option key={k} value={k}>{v}</option>
                      ))}
                    </select>
                  </div>
                )}
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">ID do nó</label>
                  <span className="text-xs font-mono text-gray-500">{selectedNode.id}</span>
                </div>
                <button
                  onClick={() => deleteNode(selectedNode.id)}
                  className="w-full text-xs text-red-600 hover:bg-red-50 py-1.5 rounded border border-red-200 mt-2"
                >
                  Deletar nó
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Playbook Create/Edit Modal ─────────────────────────────────────────────────
function PlaybookModal({ playbook, onClose }: { playbook?: PlaybookRule; onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState(playbook?.name ?? "");
  const [description, setDescription] = useState(playbook?.description ?? "");
  const [triggerType, setTriggerType] = useState(playbook?.trigger_type ?? "siem_alert");
  const [cooldown, setCooldown] = useState(String(playbook?.cooldown_minutes ?? 30));

  const createMut = useMutation({
    mutationFn: (d: PlaybookCreate) => playbooksApi.create(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["playbooks"] }); toast.success("Playbook criado"); onClose(); },
    onError: () => toast.error("Erro ao criar"),
  });

  const updateMut = useMutation({
    mutationFn: (d: PlaybookCreate) => playbooksApi.update(playbook!.id, d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["playbooks"] }); toast.success("Playbook atualizado"); onClose(); },
    onError: () => toast.error("Erro ao atualizar"),
  });

  const isLoading = createMut.isPending || updateMut.isPending;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const payload: PlaybookCreate = { name, description: description || undefined, trigger_type: triggerType, cooldown_minutes: parseInt(cooldown) };
    playbook ? updateMut.mutate(payload) : createMut.mutate(payload);
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between p-5 border-b">
          <h2 className="text-lg font-semibold">{playbook ? "Editar Playbook" : "Novo Playbook"}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nome</label>
            <input value={name} onChange={e => setName(e.target.value)} required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Descrição</label>
            <input value={description} onChange={e => setDescription(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Trigger</label>
            <div className="relative">
              <select value={triggerType} onChange={e => setTriggerType(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm appearance-none focus:outline-none focus:ring-2 focus:ring-brand-500">
                {Object.entries(TRIGGER_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              <ChevronDown size={14} className="absolute right-3 top-3 text-gray-400 pointer-events-none" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Cooldown (minutos)</label>
            <input type="number" value={cooldown} onChange={e => setCooldown(e.target.value)} min={1}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancelar</button>
            <button type="submit" disabled={isLoading}
              className="px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2">
              {isLoading && <Loader2 size={14} className="animate-spin" />}
              {playbook ? "Salvar" : "Criar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export function PlaybooksPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("playbooks");
  const [showCreate, setShowCreate] = useState(false);
  const [editPlaybook, setEditPlaybook] = useState<PlaybookRule | undefined>();
  const [builderPlaybook, setBuilderPlaybook] = useState<PlaybookRule | undefined>();
  const [execPlaybookId, setExecPlaybookId] = useState<string | null>(null);

  const { data: playbooks = [], isLoading } = useQuery({
    queryKey: ["playbooks"],
    queryFn: playbooksApi.list,
  });

  const { data: mttr } = useQuery({
    queryKey: ["playbooks-mttr"],
    queryFn: playbooksApi.getMttr,
    enabled: tab === "mttr",
  });

  const { data: executions = [], isLoading: loadingExecs } = useQuery({
    queryKey: ["playbook-executions", execPlaybookId],
    queryFn: () => playbooksApi.listExecutions(execPlaybookId!),
    enabled: tab === "executions" && !!execPlaybookId,
    refetchInterval: 5000,
  });

  const toggleMut = useMutation({
    mutationFn: (id: string) => playbooksApi.toggle(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["playbooks"] }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => playbooksApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["playbooks"] }); toast.success("Playbook removido"); },
  });

  const seedMut = useMutation({
    mutationFn: playbooksApi.seedTemplates,
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ["playbooks"] }); toast.success(`${r.seeded} templates carregados`); },
  });

  const tabClass = (t: Tab) =>
    `px-4 py-2 text-sm font-medium rounded-lg transition-colors ${tab === t ? "bg-brand-600 text-white" : "text-gray-600 hover:bg-gray-100"}`;

  return (
    <div className="ml-64 p-8 min-h-screen bg-gray-50">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <GitBranch size={24} className="text-brand-600" />
            SOAR Playbooks
          </h1>
          <p className="text-gray-500 text-sm mt-1">Automação de resposta a incidentes com builder visual.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => seedMut.mutate()} disabled={seedMut.isPending}
            className="flex items-center gap-2 border border-gray-300 text-gray-700 px-3 py-2 rounded-lg text-sm hover:bg-gray-50 transition-colors">
            {seedMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
            Carregar Templates AD
          </button>
          <button onClick={() => { setEditPlaybook(undefined); setShowCreate(true); }}
            className="flex items-center gap-2 bg-brand-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-brand-700">
            <Plus size={16} /> Novo Playbook
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        <button className={tabClass("playbooks")} onClick={() => setTab("playbooks")}>
          <span className="flex items-center gap-1.5"><GitBranch size={14} /> Playbooks ({playbooks.length})</span>
        </button>
        <button className={tabClass("executions")} onClick={() => setTab("executions")}>
          <span className="flex items-center gap-1.5"><Play size={14} /> Execuções</span>
        </button>
        <button className={tabClass("mttr")} onClick={() => setTab("mttr")}>
          <span className="flex items-center gap-1.5"><BarChart3 size={14} /> MTTR</span>
        </button>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6">
        {tab === "playbooks" && (
          <>
            {isLoading ? (
              <div className="flex justify-center py-12"><Loader2 size={24} className="animate-spin text-gray-400" /></div>
            ) : playbooks.length === 0 ? (
              <div className="text-center py-16 text-gray-500">
                <GitBranch size={40} className="mx-auto mb-3 text-gray-300" />
                <p className="font-medium mb-1">Nenhum playbook configurado</p>
                <p className="text-sm text-gray-400 mb-4">Crie um playbook ou carregue os templates AD pré-prontos.</p>
                <button onClick={() => seedMut.mutate()}
                  className="inline-flex items-center gap-2 bg-brand-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-brand-700">
                  <Zap size={15} /> Carregar Templates AD
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {playbooks.map((p: PlaybookRule) => (
                  <div key={p.id} className="flex items-center justify-between p-4 border border-gray-100 rounded-xl hover:shadow-sm transition-shadow">
                    <div className="flex items-center gap-4">
                      <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${p.enabled ? "bg-green-500" : "bg-gray-300"}`} />
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-gray-900 text-sm">{p.name}</span>
                          {p.is_template && (
                            <span className="text-xs bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded-full">Template</span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 mt-0.5">
                          <span className="text-xs text-purple-700 bg-purple-50 px-1.5 py-0.5 rounded">
                            {TRIGGER_LABELS[p.trigger_type] ?? p.trigger_type}
                          </span>
                          <span className="text-xs text-gray-400 flex items-center gap-1">
                            <Clock size={10} /> {p.cooldown_minutes}min cooldown
                          </span>
                          <span className="text-xs text-gray-400">
                            {p.actions.length} ação{p.actions.length !== 1 ? "ões" : ""}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <button onClick={() => setBuilderPlaybook(p)}
                        className="p-1.5 text-gray-400 hover:text-brand-600 hover:bg-gray-100 rounded-lg" title="Builder Visual">
                        <GitBranch size={14} />
                      </button>
                      <button onClick={() => { setEditPlaybook(p); setShowCreate(true); }}
                        className="p-1.5 text-gray-400 hover:text-brand-600 hover:bg-gray-100 rounded-lg" title="Editar">
                        <Settings2 size={14} />
                      </button>
                      <button onClick={() => toggleMut.mutate(p.id)}
                        className={`p-1.5 rounded-lg hover:bg-gray-100 transition-colors ${p.enabled ? "text-green-500 hover:text-green-700" : "text-gray-400 hover:text-gray-600"}`}
                        title={p.enabled ? "Pausar" : "Ativar"}>
                        {p.enabled ? <Pause size={14} /> : <Play size={14} />}
                      </button>
                      <button onClick={() => { if (confirm("Remover playbook?")) deleteMut.mutate(p.id); }}
                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg" title="Remover">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {tab === "executions" && (
          <div className="space-y-4">
            {/* Playbook selector */}
            <div className="flex items-center gap-3">
              <label className="text-sm text-gray-600 shrink-0">Playbook:</label>
              <select
                value={execPlaybookId ?? ""}
                onChange={(e) => setExecPlaybookId(e.target.value || null)}
                className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="">— Selecione um playbook —</option>
                {playbooks.map((p: PlaybookRule) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>

            {!execPlaybookId ? (
              <div className="text-center py-12 text-gray-400">
                <Play size={32} className="mx-auto mb-3 opacity-30" />
                <p className="text-sm">Selecione um playbook para ver o histórico de execuções.</p>
              </div>
            ) : loadingExecs ? (
              <div className="flex justify-center py-12"><Loader2 size={22} className="animate-spin text-gray-400" /></div>
            ) : executions.length === 0 ? (
              <div className="text-center py-12 text-gray-400">
                <Clock size={32} className="mx-auto mb-3 opacity-30" />
                <p className="text-sm">Nenhuma execução registrada para este playbook.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {executions.map((ex) => (
                  <div key={ex.id} className="border border-gray-200 rounded-xl p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${EXEC_STATUS_COLORS[ex.status] ?? STATUS_COLORS[ex.status] ?? "bg-gray-100 text-gray-600"}`}>
                            {ex.status}
                          </span>
                          <span className="text-xs text-gray-500">
                            {new Date(ex.triggered_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}
                          </span>
                          {ex.resolved_at && (
                            <span className="text-xs text-gray-400">
                              → {new Date(ex.resolved_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}
                            </span>
                          )}
                        </div>
                        {ex.actions_taken.length > 0 && (
                          <div className="flex gap-1 flex-wrap mt-1.5">
                            {ex.actions_taken.map((a, i) => (
                              <span key={i} className="text-[10px] bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                                {String(a.type ?? a.action ?? "ação")}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === "mttr" && (
          <div>
            {!mttr ? (
              <div className="flex justify-center py-12"><Loader2 size={24} className="animate-spin text-gray-400" /></div>
            ) : (
              <>
                <div className="mb-6 p-4 bg-brand-50 border border-brand-200 rounded-xl">
                  <p className="text-sm text-brand-800">
                    <strong>MTTR médio do tenant:</strong>{" "}
                    {mttr.tenant_avg_minutes != null
                      ? `${Math.round(mttr.tenant_avg_minutes)} min`
                      : "Sem dados"}
                  </p>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-500 uppercase border-b">
                      <th className="pb-2 font-medium">Playbook</th>
                      <th className="pb-2 font-medium">MTTR Médio</th>
                      <th className="pb-2 font-medium">Execuções</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {mttr.by_rule.map(r => (
                      <tr key={r.rule_id} className="hover:bg-gray-50">
                        <td className="py-3 font-medium text-gray-900">{r.rule_name}</td>
                        <td className="py-3 text-gray-600">{Math.round(r.avg_minutes)} min</td>
                        <td className="py-3 text-gray-500">{r.execution_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>
        )}
      </div>

      {showCreate && (
        <PlaybookModal playbook={editPlaybook} onClose={() => { setShowCreate(false); setEditPlaybook(undefined); }} />
      )}
      {builderPlaybook && (
        <PlaybookBuilder playbook={builderPlaybook} onClose={() => setBuilderPlaybook(undefined)} />
      )}
    </div>
  );
}
