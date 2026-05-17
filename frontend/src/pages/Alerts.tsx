import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Bell, Zap, Clock, CheckCircle, XCircle, Loader2, ToggleLeft, ToggleRight, Play, X, GitBranch, Shield } from "lucide-react";
import toast from "react-hot-toast";
import apiClient from "../api/client";
import { alertsApi } from "../api/alerts";
import { playbooksApi, type PlaybookRule } from "../api/playbooks";
import type { AlertChannel, AlertRule } from "../types/alerts";

type Tab = "channels" | "rules" | "events" | "sla";

const CHANNEL_LABELS: Record<string, string> = {
  slack: "Slack", teams: "Microsoft Teams", email: "Email (SMTP)", webhook: "Webhook HTTP", jira: "Jira",
};
const CHANNEL_COLORS: Record<string, string> = {
  slack: "bg-yellow-100 text-yellow-700",
  teams: "bg-indigo-100 text-indigo-700",
  email: "bg-blue-100 text-blue-700",
  webhook: "bg-gray-100 text-gray-700",
  jira: "bg-sky-100 text-sky-700",
};

const TRIGGER_LABELS: Record<string, string> = {
  offboard_completed: "Offboarding Concluído",
  onboard_completed: "Onboarding Concluído",
  task_failed: "Tarefa Falhou",
  health_check_failed: "Health Check Falhou",
  orphan_detected: "Contas Órfãs Detectadas",
};

const SEVERITY_COLORS: Record<string, string> = {
  info: "bg-blue-100 text-blue-700",
  warning: "bg-yellow-100 text-yellow-700",
  critical: "bg-red-100 text-red-700",
};

// ── Channel Modal ──────────────────────────────────────────────────────────────
function ChannelModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [type, setType] = useState("slack");
  const [slack, setSlack] = useState({ webhook_url: "" });
  const [teams, setTeams] = useState({ webhook_url: "" });
  const [email, setEmail] = useState({ host: "", port: "587", username: "", password: "", from_address: "", to_addresses: "", use_tls: true });
  const [webhook, setWebhook] = useState({ url: "", method: "POST", headers: "" });
  const [jira, setJira] = useState({ url: "", email: "", api_token: "", project_key: "", issue_type: "Task" });

  const createMut = useMutation({
    mutationFn: alertsApi.createChannel,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["alert-channels"] }); onClose(); },
  });

  const getConfig = (): Record<string, unknown> => {
    if (type === "slack") return { webhook_url: slack.webhook_url };
    if (type === "teams") return { webhook_url: teams.webhook_url };
    if (type === "email") return {
      host: email.host, port: parseInt(email.port), username: email.username,
      password: email.password, from_address: email.from_address,
      to_addresses: email.to_addresses.split(",").map(s => s.trim()),
      use_tls: email.use_tls,
    };
    if (type === "webhook") {
      let headers: Record<string, string> = {};
      try { headers = JSON.parse(webhook.headers || "{}"); } catch { /* ignore parse errors */ }
      return { url: webhook.url, method: webhook.method, headers };
    }
    return { url: jira.url, email: jira.email, api_token: jira.api_token, project_key: jira.project_key, issue_type: jira.issue_type };
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg max-h-[90vh] flex flex-col">
        <div className="px-6 py-4 border-b flex items-center justify-between flex-shrink-0">
          <h2 className="text-lg font-semibold">Novo Canal de Alerta</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
        </div>
        <div className="p-6 space-y-4 overflow-y-auto">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Nome</label>
              <input className="w-full border rounded-lg px-3 py-2 text-sm" value={name}
                onChange={e => setName(e.target.value)} placeholder="ex: Slack #alertas" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Tipo</label>
              <select className="w-full border rounded-lg px-3 py-2 text-sm" value={type} onChange={e => setType(e.target.value)}>
                {Object.entries(CHANNEL_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
          </div>

          {type === "slack" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Webhook URL</label>
              <input className="w-full border rounded-lg px-3 py-2 text-sm" value={slack.webhook_url}
                onChange={e => setSlack({ webhook_url: e.target.value })} placeholder="https://hooks.slack.com/services/..." />
            </div>
          )}

          {type === "teams" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Webhook URL</label>
              <input className="w-full border rounded-lg px-3 py-2 text-sm" value={teams.webhook_url}
                onChange={e => setTeams({ webhook_url: e.target.value })} placeholder="https://outlook.office.com/webhook/..." />
            </div>
          )}

          {type === "email" && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Servidor SMTP</label>
                  <input className="w-full border rounded-lg px-3 py-2 text-sm" value={email.host}
                    onChange={e => setEmail(em => ({ ...em, host: e.target.value }))} placeholder="smtp.gmail.com" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Porta</label>
                  <input className="w-full border rounded-lg px-3 py-2 text-sm" value={email.port}
                    onChange={e => setEmail(em => ({ ...em, port: e.target.value }))} />
                </div>
              </div>
              <input className="w-full border rounded-lg px-3 py-2 text-sm" value={email.username}
                onChange={e => setEmail(em => ({ ...em, username: e.target.value }))} placeholder="Usuário" />
              <input type="password" className="w-full border rounded-lg px-3 py-2 text-sm" value={email.password}
                onChange={e => setEmail(em => ({ ...em, password: e.target.value }))} placeholder="Senha" />
              <input className="w-full border rounded-lg px-3 py-2 text-sm" value={email.to_addresses}
                onChange={e => setEmail(em => ({ ...em, to_addresses: e.target.value }))} placeholder="Destinatários (separados por vírgula)" />
            </div>
          )}

          {type === "webhook" && (
            <div className="space-y-3">
              <input className="w-full border rounded-lg px-3 py-2 text-sm" value={webhook.url}
                onChange={e => setWebhook(w => ({ ...w, url: e.target.value }))} placeholder="https://seu-endpoint.com/webhook" />
              <select className="w-full border rounded-lg px-3 py-2 text-sm" value={webhook.method}
                onChange={e => setWebhook(w => ({ ...w, method: e.target.value }))}>
                <option>POST</option><option>GET</option>
              </select>
              <textarea className="w-full border rounded-lg px-3 py-2 text-sm font-mono" rows={3}
                value={webhook.headers} onChange={e => setWebhook(w => ({ ...w, headers: e.target.value }))}
                placeholder={'Headers JSON (opcional): {"Authorization": "Bearer ..."}'}/>
            </div>
          )}

          {type === "jira" && (
            <div className="space-y-3">
              <input className="w-full border rounded-lg px-3 py-2 text-sm" value={jira.url}
                onChange={e => setJira(j => ({ ...j, url: e.target.value }))} placeholder="https://sua-empresa.atlassian.net" />
              <input className="w-full border rounded-lg px-3 py-2 text-sm" value={jira.email}
                onChange={e => setJira(j => ({ ...j, email: e.target.value }))} placeholder="email@empresa.com" />
              <input className="w-full border rounded-lg px-3 py-2 text-sm" value={jira.api_token}
                onChange={e => setJira(j => ({ ...j, api_token: e.target.value }))} placeholder="API Token Jira" />
              <div className="grid grid-cols-2 gap-3">
                <input className="w-full border rounded-lg px-3 py-2 text-sm" value={jira.project_key}
                  onChange={e => setJira(j => ({ ...j, project_key: e.target.value }))} placeholder="Chave do Projeto (ex: IT)" />
                <input className="w-full border rounded-lg px-3 py-2 text-sm" value={jira.issue_type}
                  onChange={e => setJira(j => ({ ...j, issue_type: e.target.value }))} placeholder="Tipo (Task, Bug...)" />
              </div>
            </div>
          )}
        </div>
        <div className="px-6 py-4 border-t flex justify-end gap-3 flex-shrink-0">
          <button onClick={onClose} className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50">Cancelar</button>
          <button onClick={() => createMut.mutate({ name, channel_type: type, config: getConfig() })}
            disabled={createMut.isPending || !name}
            className="px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2">
            {createMut.isPending && <Loader2 size={14} className="animate-spin" />}
            Salvar
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Rule Modal ─────────────────────────────────────────────────────────────────
function RuleModal({ rule, channels, onClose }: { rule: AlertRule | null; channels: AlertChannel[]; onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState(rule?.name ?? "");
  const [trigger, setTrigger] = useState(rule?.trigger ?? "offboard_completed");
  const [severity, setSeverity] = useState(rule?.severity ?? "warning");
  const [selectedChannels, setSelectedChannels] = useState<string[]>(rule?.channel_ids ?? []);

  const saveMut = useMutation({
    mutationFn: (data: { name: string; trigger: string; severity: string; channel_ids: string[] }) =>
      rule ? alertsApi.updateRule(rule.id, data) : alertsApi.createRule(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["alert-rules"] }); onClose(); },
  });

  const toggleChannel = (id: string) =>
    setSelectedChannels(cs => cs.includes(id) ? cs.filter(x => x !== id) : [...cs, id]);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <h2 className="text-lg font-semibold">{rule ? "Editar Regra" : "Nova Regra de Alerta"}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nome</label>
            <input className="w-full border rounded-lg px-3 py-2 text-sm" value={name}
              onChange={e => setName(e.target.value)} placeholder="ex: Notificar offboarding crítico" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Gatilho</label>
              <select className="w-full border rounded-lg px-3 py-2 text-sm" value={trigger} onChange={e => setTrigger(e.target.value as typeof trigger)}>
                {Object.entries(TRIGGER_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Severidade</label>
              <select className="w-full border rounded-lg px-3 py-2 text-sm" value={severity} onChange={e => setSeverity(e.target.value as typeof severity)}>
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="critical">Critical</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Canais de Notificação</label>
            {channels.length === 0 ? (
              <p className="text-sm text-gray-400">Nenhum canal configurado.</p>
            ) : (
              <div className="space-y-2">
                {channels.map(c => (
                  <label key={c.id} className="flex items-center gap-3 p-2 border rounded-lg cursor-pointer hover:bg-gray-50">
                    <input type="checkbox" checked={selectedChannels.includes(c.id)} onChange={() => toggleChannel(c.id)} />
                    <span className={`text-xs px-2 py-0.5 rounded-full ${CHANNEL_COLORS[c.channel_type]}`}>{CHANNEL_LABELS[c.channel_type]}</span>
                    <span className="text-sm">{c.name}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="px-6 py-4 border-t flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50">Cancelar</button>
          <button onClick={() => saveMut.mutate({ name, trigger, severity, channel_ids: selectedChannels })}
            disabled={saveMut.isPending || !name}
            className="px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2">
            {saveMut.isPending && <Loader2 size={14} className="animate-spin" />}
            Salvar
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Playbook Trigger Modal ─────────────────────────────────────────────────────
function TriggerPlaybookModal({
  alertTitle,
  alertBody,
  onClose,
}: {
  alertTitle: string;
  alertBody: string;
  onClose: () => void;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: playbooks = [], isLoading } = useQuery({
    queryKey: ["playbooks"],
    queryFn: playbooksApi.list,
  });

  const triggerMut = useMutation({
    mutationFn: (id: string) =>
      playbooksApi.trigger(id, { alert_title: alertTitle, alert_body: alertBody, source: "manual" }),
    onSuccess: () => { toast.success("Playbook disparado com sucesso"); onClose(); },
    onError: () => toast.error("Erro ao disparar playbook"),
  });

  const activePlaybooks = playbooks.filter((p: PlaybookRule) => p.enabled);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <h2 className="text-base font-semibold flex items-center gap-2">
            <Play size={16} className="text-brand-600" /> Disparar Playbook
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>
        <div className="p-5 space-y-3">
          <div className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2.5">
            <p className="text-xs font-medium text-gray-700">{alertTitle}</p>
            <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{alertBody}</p>
          </div>

          {isLoading ? (
            <div className="flex justify-center py-6"><Loader2 size={20} className="animate-spin text-gray-400" /></div>
          ) : activePlaybooks.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-4">Nenhum playbook ativo. Ative um em SOAR Playbooks.</p>
          ) : (
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {activePlaybooks.map((p: PlaybookRule) => (
                <button
                  key={p.id}
                  onClick={() => setSelectedId(p.id)}
                  className={`w-full flex items-start gap-3 p-3 rounded-lg border text-left transition-colors ${
                    selectedId === p.id
                      ? "border-brand-500 bg-brand-50"
                      : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"
                  }`}
                >
                  <GitBranch size={14} className={`shrink-0 mt-0.5 ${selectedId === p.id ? "text-brand-600" : "text-gray-400"}`} />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-800">{p.name}</p>
                    <p className="text-xs text-purple-600 mt-0.5">{p.trigger_type}</p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="px-5 py-4 border-t flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50">Cancelar</button>
          <button
            onClick={() => selectedId && triggerMut.mutate(selectedId)}
            disabled={!selectedId || triggerMut.isPending}
            className="px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2"
          >
            {triggerMut.isPending && <Loader2 size={14} className="animate-spin" />}
            Disparar
          </button>
        </div>
      </div>
    </div>
  );
}

// ── SLA Config Tab ────────────────────────────────────────────────────────────
function SlaConfigTab() {
  const [targets, setTargets] = useState({ critical: 15, high: 30, medium: 120, low: 480 });
  const [escalation, setEscalation] = useState({
    tier1_minutes: 30, tier1_action: "notify_channel",
    tier2_minutes: 60, tier2_action: "escalate_n2",
  });
  const [windows, setWindows] = useState<Array<{ days: number[]; start: string; end: string }>>([]);
  const [saving, setSaving] = useState(false);

  const DAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

  function toggleDay(winIdx: number, day: number) {
    setWindows(prev => prev.map((w, i) =>
      i === winIdx ? { ...w, days: w.days.includes(day) ? w.days.filter(d => d !== day) : [...w.days, day] } : w
    ));
  }

  async function handleSave() {
    setSaving(true);
    try {
      await apiClient.put("/alerts/sla-config", { targets, escalation, maintenance_windows: windows });
      toast.success("Configuração de SLA salva");
    } catch {
      toast.error("Erro ao salvar configuração");
    } finally {
      setSaving(false);
    }
  }

  const SEV_COLORS: Record<string, string> = {
    critical: "bg-red-100 text-red-700",
    high: "bg-orange-100 text-orange-700",
    medium: "bg-yellow-100 text-yellow-700",
    low: "bg-blue-100 text-blue-700",
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Metas de Resposta por Severidade</h3>
        <div className="grid grid-cols-2 gap-3">
          {(["critical", "high", "medium", "low"] as const).map(sev => (
            <div key={sev} className="bg-white border rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${SEV_COLORS[sev]}`}>{sev}</span>
              </div>
              <div className="flex items-center gap-2">
                <input type="number" min={1} value={targets[sev]}
                  onChange={e => setTargets(t => ({ ...t, [sev]: parseInt(e.target.value) || 0 }))}
                  className="w-20 border rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-brand-400" />
                <span className="text-sm text-gray-500">minutos</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Tiers de Escalação</h3>
        <div className="space-y-3">
          {([1, 2] as const).map(tier => (
            <div key={tier} className="bg-white border rounded-xl p-4 flex items-center gap-4 flex-wrap">
              <span className="text-xs font-medium text-gray-500 w-12">Tier {tier}</span>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-gray-600">Após</span>
                <input type="number" min={1}
                  value={tier === 1 ? escalation.tier1_minutes : escalation.tier2_minutes}
                  onChange={e => setEscalation(es => tier === 1
                    ? { ...es, tier1_minutes: parseInt(e.target.value) || 0 }
                    : { ...es, tier2_minutes: parseInt(e.target.value) || 0 })}
                  className="w-16 border rounded px-2 py-1 text-sm" />
                <span className="text-xs text-gray-600">min sem resposta:</span>
                <select
                  value={tier === 1 ? escalation.tier1_action : escalation.tier2_action}
                  onChange={e => setEscalation(es => tier === 1
                    ? { ...es, tier1_action: e.target.value }
                    : { ...es, tier2_action: e.target.value })}
                  className="border rounded px-2 py-1 text-sm">
                  <option value="notify_channel">Notificar canal</option>
                  <option value="escalate_n2">Escalar para N2</option>
                  <option value="escalate_n3">Escalar para N3</option>
                  <option value="notify_ciso">Notificar CISO</option>
                </select>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-700">Janelas de Manutenção</h3>
          <button
            onClick={() => setWindows(w => [...w, { days: [1, 2, 3, 4, 5], start: "22:00", end: "06:00" }])}
            className="flex items-center gap-1 text-xs text-brand-600 border border-brand-200 px-2 py-1 rounded hover:bg-brand-50">
            <Plus size={12} /> Adicionar Janela
          </button>
        </div>
        {windows.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-4 bg-white border rounded-xl">
            Nenhuma janela configurada. Alertas e escalações ocorrem em todos os horários.
          </p>
        ) : (
          <div className="space-y-3">
            {windows.map((win, idx) => (
              <div key={idx} className="bg-white border rounded-xl p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-medium text-gray-600">Janela {idx + 1}</span>
                  <button onClick={() => setWindows(w => w.filter((_, i) => i !== idx))}
                    className="text-gray-400 hover:text-red-500"><X size={14} /></button>
                </div>
                <div className="flex flex-wrap gap-1 mb-3">
                  {DAYS.map((d, i) => (
                    <button key={i} onClick={() => toggleDay(idx, i)}
                      className={`text-xs px-2 py-0.5 rounded border font-medium ${
                        win.days.includes(i) ? "bg-brand-600 text-white border-brand-600" : "border-gray-300 text-gray-500"
                      }`}>{d}</button>
                  ))}
                </div>
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <label className="text-xs text-gray-600">Início</label>
                    <input type="time" value={win.start}
                      onChange={e => setWindows(w => w.map((ww, i) => i === idx ? { ...ww, start: e.target.value } : ww))}
                      className="border rounded px-2 py-1 text-xs" />
                  </div>
                  <div className="flex items-center gap-2">
                    <label className="text-xs text-gray-600">Fim</label>
                    <input type="time" value={win.end}
                      onChange={e => setWindows(w => w.map((ww, i) => i === idx ? { ...ww, end: e.target.value } : ww))}
                      className="border rounded px-2 py-1 text-xs" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="flex justify-end">
        <button onClick={handleSave} disabled={saving}
          className="flex items-center gap-2 px-5 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 text-sm disabled:opacity-50">
          {saving && <Loader2 size={14} className="animate-spin" />}
          Salvar Configuração
        </button>
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────
export function Alerts() {
  const [tab, setTab] = useState<Tab>("channels");
  const [showChannelModal, setShowChannelModal] = useState(false);
  const [editingRule, setEditingRule] = useState<AlertRule | null | "new">(null);
  const [triggerEvent, setTriggerEvent] = useState<{ title: string; body: string } | null>(null);

  const qc = useQueryClient();

  const { data: channels = [], isLoading: loadingChannels } = useQuery({ queryKey: ["alert-channels"], queryFn: alertsApi.listChannels });
  const { data: rules = [] } = useQuery({ queryKey: ["alert-rules"], queryFn: alertsApi.listRules });
  const { data: events = [] } = useQuery({ queryKey: ["alert-events"], queryFn: alertsApi.listEvents });

  const deleteChannel = useMutation({ mutationFn: alertsApi.deleteChannel, onSuccess: () => qc.invalidateQueries({ queryKey: ["alert-channels"] }) });
  const deleteRule = useMutation({ mutationFn: alertsApi.deleteRule, onSuccess: () => qc.invalidateQueries({ queryKey: ["alert-rules"] }) });
  const toggleRule = useMutation({ mutationFn: alertsApi.toggleRule, onSuccess: () => qc.invalidateQueries({ queryKey: ["alert-rules"] }) });
  const testChannel = useMutation({ mutationFn: alertsApi.testChannel });

  return (
    <div className="ml-64 min-h-screen bg-gray-50">
      <div className="px-8 py-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Alertas & Integrações</h1>
          <p className="text-sm text-gray-500 mt-1">Configure canais de notificação e regras de disparo automático</p>
        </div>

        <div className="flex gap-1 mb-6 border-b">
          {([["channels", "Canais", Bell], ["rules", "Regras", Zap], ["events", "Histórico", Clock], ["sla", "SLA & Manutenção", Shield]] as const).map(([key, label, Icon]) => (
            <button key={key} onClick={() => setTab(key as Tab)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${tab === key ? "border-brand-600 text-brand-600" : "border-transparent text-gray-500 hover:text-gray-700"}`}>
              <Icon size={16} />{label}
              {key === "events" && events.length > 0 && (
                <span className="bg-gray-200 text-gray-600 text-xs px-1.5 py-0.5 rounded-full">{events.length}</span>
              )}
            </button>
          ))}
        </div>

        {tab === "channels" && (
          <div>
            <div className="flex justify-end mb-4">
              <button onClick={() => setShowChannelModal(true)} className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 text-sm">
                <Plus size={16} /> Novo Canal
              </button>
            </div>
            {loadingChannels ? <div className="flex justify-center py-12"><Loader2 className="animate-spin text-brand-600" size={24} /></div> :
             channels.length === 0 ? (
               <div className="text-center py-16 text-gray-400">
                 <Bell size={40} className="mx-auto mb-3 opacity-30" />
                 <p>Nenhum canal configurado</p>
               </div>
             ) : (
               <div className="grid grid-cols-1 gap-3">
                 {channels.map(c => (
                   <div key={c.id} className="bg-white border rounded-xl p-4 flex items-center justify-between">
                     <div className="flex items-center gap-3">
                       <span className={`text-xs px-2 py-1 rounded-full font-medium ${CHANNEL_COLORS[c.channel_type]}`}>{CHANNEL_LABELS[c.channel_type]}</span>
                       <span className="font-medium text-sm">{c.name}</span>
                     </div>
                     <div className="flex items-center gap-2">
                       <button onClick={() => testChannel.mutate(c.id)}
                         className="text-xs px-3 py-1.5 border rounded-lg hover:bg-gray-50 text-gray-600" disabled={testChannel.isPending}>
                         Testar
                       </button>
                       <button onClick={() => deleteChannel.mutate(c.id)} className="p-1.5 text-gray-400 hover:text-red-600 rounded">
                         <Trash2 size={15} />
                       </button>
                     </div>
                   </div>
                 ))}
               </div>
             )}
          </div>
        )}

        {tab === "rules" && (
          <div>
            <div className="flex justify-end mb-4">
              <button onClick={() => setEditingRule("new")} className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 text-sm">
                <Plus size={16} /> Nova Regra
              </button>
            </div>
            {rules.length === 0 ? (
              <div className="text-center py-16 text-gray-400">
                <Zap size={40} className="mx-auto mb-3 opacity-30" />
                <p>Nenhuma regra criada</p>
              </div>
            ) : (
              <div className="space-y-3">
                {rules.map(r => (
                  <div key={r.id} className={`bg-white border rounded-xl p-4 ${!r.is_active ? "opacity-60" : ""}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${SEVERITY_COLORS[r.severity]}`}>{r.severity}</span>
                        <span className="font-medium text-sm">{r.name}</span>
                        <span className="text-xs text-gray-500">{TRIGGER_LABELS[r.trigger]}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={() => toggleRule.mutate(r.id)} className="text-gray-400 hover:text-brand-600">
                          {r.is_active ? <ToggleRight size={20} className="text-brand-600" /> : <ToggleLeft size={20} />}
                        </button>
                        <button onClick={() => setEditingRule(r)} className="p-1.5 text-gray-400 hover:text-brand-600 rounded">
                          <Bell size={15} />
                        </button>
                        <button onClick={() => deleteRule.mutate(r.id)} className="p-1.5 text-gray-400 hover:text-red-600 rounded">
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>
                    {r.channel_ids.length > 0 && (
                      <div className="mt-2 flex gap-1 flex-wrap">
                        {r.channel_ids.map(cid => {
                          const ch = channels.find(c => c.id === cid);
                          return ch ? (
                            <span key={cid} className={`text-xs px-2 py-0.5 rounded-full ${CHANNEL_COLORS[ch.channel_type]}`}>{ch.name}</span>
                          ) : null;
                        })}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === "events" && (
          <div className="space-y-2">
            {events.length === 0 ? (
              <div className="text-center py-16 text-gray-400">
                <Clock size={40} className="mx-auto mb-3 opacity-30" />
                <p>Nenhum evento de alerta registrado</p>
              </div>
            ) : events.map(e => (
              <div key={e.id} className="bg-white border rounded-xl p-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${SEVERITY_COLORS[e.severity]}`}>{e.severity}</span>
                    <span className="text-sm font-medium">{e.title}</span>
                  </div>
                  <span className="text-xs text-gray-400">{new Date(e.created_at).toLocaleString("pt-BR")}</span>
                </div>
                <p className="text-xs text-gray-600 mt-1">{e.body}</p>
                <div className="mt-2 flex items-center justify-between gap-2">
                <button
                  onClick={() => setTriggerEvent({ title: e.title, body: e.body })}
                  className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800 border border-brand-200 hover:border-brand-400 px-2 py-0.5 rounded transition-colors shrink-0"
                >
                  <Play size={10} /> Disparar Playbook
                </button>
                <div className="flex gap-2 flex-wrap">
                  {Object.entries(e.channels_result).map(([cid, status]) => {
                    const ch = channels.find(c => c.id === cid);
                    return (
                      <span key={cid} className={`text-xs flex items-center gap-1 px-2 py-0.5 rounded-full ${status === "success" || status === "True" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                        {status === "success" || status === "True" ? <CheckCircle size={10} /> : <XCircle size={10} />}
                        {ch?.name || cid.slice(0, 8)}
                      </span>
                    );
                  })}
                </div>
                </div>
              </div>
            ))}
          </div>
        )}
        {tab === "sla" && <SlaConfigTab />}
      </div>

      {showChannelModal && <ChannelModal onClose={() => setShowChannelModal(false)} />}
      {editingRule !== null && (
        <RuleModal rule={editingRule === "new" ? null : editingRule} channels={channels} onClose={() => setEditingRule(null)} />
      )}
      {triggerEvent && (
        <TriggerPlaybookModal
          alertTitle={triggerEvent.title}
          alertBody={triggerEvent.body}
          onClose={() => setTriggerEvent(null)}
        />
      )}
    </div>
  );
}
