import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Shield, Users, AlertTriangle, Server, Database, TrendingUp, Download, Loader2, RefreshCw, CheckCircle, XCircle, Clock, Calendar, X } from "lucide-react";
import toast from "react-hot-toast";
import apiClient from "../api/client";
import { executiveApi } from "../api/executive";
import { FirmwareRiskCard } from "../components/dashboard/FirmwareRiskCard";

function ScheduleReportModal({ onClose }: { onClose: () => void }) {
  const [frequency, setFrequency] = useState<"weekly" | "monthly">("monthly");
  const [dayOfWeek, setDayOfWeek] = useState("1");
  const [dayOfMonth, setDayOfMonth] = useState("1");
  const [time, setTime] = useState("08:00");
  const [recipients, setRecipients] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await apiClient.post("/executive/schedule-report", {
        frequency,
        day_of_week: frequency === "weekly" ? parseInt(dayOfWeek) : null,
        day_of_month: frequency === "monthly" ? parseInt(dayOfMonth) : null,
        time,
        recipients: recipients.split(",").map(r => r.trim()).filter(Boolean),
      });
      toast.success("Relatório agendado com sucesso");
      onClose();
    } catch {
      toast.error("Erro ao agendar relatório");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Calendar size={18} className="text-brand-600" /> Agendar Relatório PDF
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Frequência</label>
            <div className="flex gap-2">
              {(["weekly", "monthly"] as const).map(f => (
                <button key={f} type="button" onClick={() => setFrequency(f)}
                  className={`flex-1 py-2 rounded-lg border text-sm font-medium transition-colors ${frequency === f ? "bg-brand-600 text-white border-brand-600" : "border-gray-300 text-gray-700 hover:bg-gray-50"}`}>
                  {f === "weekly" ? "Semanal" : "Mensal"}
                </button>
              ))}
            </div>
          </div>
          {frequency === "weekly" ? (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Dia da semana</label>
              <select value={dayOfWeek} onChange={e => setDayOfWeek(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400">
                {["Segunda", "Terça", "Quarta", "Quinta", "Sexta"].map((d, i) => (
                  <option key={i} value={i + 1}>{d}</option>
                ))}
              </select>
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Dia do mês</label>
              <select value={dayOfMonth} onChange={e => setDayOfMonth(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400">
                {Array.from({ length: 28 }, (_, i) => (
                  <option key={i + 1} value={i + 1}>Dia {i + 1}</option>
                ))}
              </select>
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Horário</label>
            <input type="time" value={time} onChange={e => setTime(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Destinatários</label>
            <input value={recipients} onChange={e => setRecipients(e.target.value)} required
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
              placeholder="email1@empresa.com, email2@empresa.com" />
            <p className="text-xs text-gray-400 mt-1">Separar múltiplos por vírgula</p>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50">Cancelar</button>
            <button type="submit" disabled={saving}
              className="px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2">
              {saving && <Loader2 size={14} className="animate-spin" />}
              Agendar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function RiskGauge({ score }: { score: number }) {
  const color = score < 30 ? "text-green-500" : score < 60 ? "text-yellow-500" : "text-red-500";
  const label = score < 30 ? "BAIXO" : score < 60 ? "MÉDIO" : "ALTO";
  const bgColor = score < 30 ? "bg-green-100" : score < 60 ? "bg-yellow-100" : "bg-red-100";
  return (
    <div className={`flex flex-col items-center justify-center p-6 rounded-xl ${bgColor}`}>
      <div className={`text-5xl font-bold ${color}`}>{score}</div>
      <div className={`text-sm font-semibold mt-1 ${color}`}>RISCO {label}</div>
      <div className="text-xs text-gray-500 mt-1">score de 0 a 100</div>
    </div>
  );
}

function MetricCard({ label, value, sub, icon: Icon, color }: {
  label: string; value: number | string; sub?: string; icon: React.ElementType; color: string;
}) {
  return (
    <div className="bg-white border rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-gray-500">{label}</span>
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${color}`}>
          <Icon size={16} className="text-white" />
        </div>
      </div>
      <div className="text-3xl font-bold text-gray-900">{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-1">{sub}</div>}
    </div>
  );
}

const STATUS_COLORS: Record<string, string> = {
  pending_discovery: "text-yellow-500",
  pending_approval: "text-blue-500",
  running: "text-indigo-500",
  completed: "text-green-500",
  failed: "text-red-500",
  cancelled: "text-gray-400",
};

const STATUS_ICONS: Record<string, React.ElementType> = {
  completed: CheckCircle,
  failed: XCircle,
};

export function Executive() {
  const [period, setPeriod] = useState(30);
  const [downloading, setDownloading] = useState(false);
  const [showSchedule, setShowSchedule] = useState(false);

  const { data: posture, isLoading, refetch } = useQuery({
    queryKey: ["executive-posture"],
    queryFn: executiveApi.getPosture,
    refetchInterval: 60000,
  });

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const blob = await executiveApi.downloadReport(period);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `relatorio-executivo-${period}d.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  };

    void Shield; void toast; // suppress unused warnings

  return (
    <div className="ml-64 min-h-screen bg-gray-50">
      <div className="px-8 py-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Dashboard Executivo</h1>
            <p className="text-sm text-gray-500 mt-1">Visão consolidada da postura de segurança</p>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={() => refetch()} className="p-2 text-gray-500 hover:text-brand-600 border rounded-lg">
              <RefreshCw size={16} />
            </button>
            <select className="border rounded-lg px-3 py-2 text-sm" value={period} onChange={e => setPeriod(Number(e.target.value))}>
              <option value={7}>Últimos 7 dias</option>
              <option value={30}>Últimos 30 dias</option>
              <option value={90}>Últimos 90 dias</option>
            </select>
            <button onClick={() => setShowSchedule(true)}
              className="flex items-center gap-2 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 text-sm">
              <Calendar size={16} />
              Agendar
            </button>
            <button onClick={handleDownload} disabled={downloading || isLoading}
              className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 text-sm disabled:opacity-50">
              {downloading ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
              Exportar PDF
            </button>
          </div>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-24"><Loader2 className="animate-spin text-brand-600" size={32} /></div>
        ) : !posture ? null : (
          <div className="space-y-6">
            {/* Top Row — Risk + Key Metrics */}
            <div className="grid grid-cols-4 gap-4">
              <RiskGauge score={posture.risk_score} />
              <MetricCard label="Usuários Monitorados" value={posture.identity.total_users} icon={Users} color="bg-blue-500"
                sub={`${posture.identity.orphan_accounts} contas inativas`} />
              <MetricCard label="Alertas Críticos (7d)" value={posture.alerts_7d.critical} icon={AlertTriangle} color="bg-red-500"
                sub={`${posture.alerts_7d.total} total`} />
              <MetricCard label="Ações Pendentes" value={posture.lifecycle_30d.pending_actions} icon={Clock} color="bg-yellow-500"
                sub="Offboardings aguardando" />
            </div>

            {/* Firmware Risk */}
            <div className="grid grid-cols-4 gap-4">
              <FirmwareRiskCard />
            </div>

            {/* Identity + Lifecycle */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white border rounded-xl p-5">
                <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Users size={16} className="text-brand-600" /> Identidade & Contas
                </h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Contas órfãs</span>
                    <div className="flex items-center gap-2">
                      <div className="w-32 h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full bg-red-400 rounded-full" style={{ width: `${posture.identity.orphan_percentage}%` }} />
                      </div>
                      <span className="text-sm font-medium">{posture.identity.orphan_percentage}%</span>
                    </div>
                  </div>
                  <div className="flex justify-between text-sm text-gray-600">
                    <span>Offboardings concluídos ({period}d)</span>
                    <span className="font-medium text-green-600">{posture.lifecycle_30d.offboards_completed}</span>
                  </div>
                  <div className="flex justify-between text-sm text-gray-600">
                    <span>Onboardings concluídos ({period}d)</span>
                    <span className="font-medium text-blue-600">{posture.lifecycle_30d.onboards_completed}</span>
                  </div>
                </div>
              </div>

              <div className="bg-white border rounded-xl p-5">
                <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Server size={16} className="text-brand-600" /> Infraestrutura
                </h3>
                <div className="space-y-3">
                  <div className="flex justify-between text-sm text-gray-600">
                    <span className="flex items-center gap-2"><Server size={14} /> Servidores monitorados</span>
                    <span className="font-medium">{posture.infrastructure.servers}</span>
                  </div>
                  <div className="flex justify-between text-sm text-gray-600">
                    <span className="flex items-center gap-2"><Database size={14} /> Bancos de dados</span>
                    <span className="font-medium">{posture.infrastructure.databases}</span>
                  </div>
                  <div className="flex justify-between text-sm text-gray-600">
                    <span className="flex items-center gap-2"><AlertTriangle size={14} /> Total de alertas (7d)</span>
                    <span className="font-medium">{posture.alerts_7d.total}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Recent Activity */}
            <div className="bg-white border rounded-xl p-5">
              <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <TrendingUp size={16} className="text-brand-600" /> Atividade Recente
              </h3>
              {posture.recent_actions.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-4">Nenhuma ação recente</p>
              ) : (
                <div className="space-y-2">
                  {posture.recent_actions.map(a => {
                    const Icon = STATUS_ICONS[a.status] || Clock;
                    const colorClass = STATUS_COLORS[a.status] || "text-gray-500";
                    return (
                      <div key={a.id} className="flex items-center justify-between py-2 border-b last:border-0">
                        <div className="flex items-center gap-3">
                          <Icon size={16} className={colorClass} />
                          <div>
                            <span className="text-sm font-medium">{a.target_username}</span>
                            <span className={`text-xs ml-2 px-2 py-0.5 rounded-full ${a.action_type === "onboard" ? "bg-green-100 text-green-700" : "bg-blue-100 text-blue-700"}`}>
                              {a.action_type}
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`text-xs ${colorClass}`}>{a.status}</span>
                          <span className="text-xs text-gray-400">{new Date(a.created_at).toLocaleDateString("pt-BR")}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="text-xs text-gray-400 text-right">
              Dados gerados em: {new Date(posture.generated_at).toLocaleString("pt-BR")}
            </div>
          </div>
        )}
      </div>
      {showSchedule && <ScheduleReportModal onClose={() => setShowSchedule(false)} />}
    </div>
  );
}
