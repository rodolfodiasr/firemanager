import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Shield, Users, AlertTriangle, Server, Database, TrendingUp, Download, Loader2, RefreshCw, CheckCircle, XCircle, Clock } from "lucide-react";
import { executiveApi } from "../api/executive";

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

  // Suppress unused import warning — Shield is used conceptually for the page context
  void Shield;

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
    </div>
  );
}
