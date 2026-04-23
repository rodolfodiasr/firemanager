import { useQuery } from "@tanstack/react-query";
import { Server, ClipboardList, Shield, Activity } from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { StatusBadge } from "../components/shared/StatusBadge";
import { devicesApi } from "../api/devices";
import { operationsApi } from "../api/operations";

export function Dashboard() {
  const devicesQuery = useQuery({ queryKey: ["devices"], queryFn: devicesApi.list });
  const operationsQuery = useQuery({ queryKey: ["operations"], queryFn: operationsApi.list });

  const devices = devicesQuery.data ?? [];
  const operations = operationsQuery.data ?? [];

  const onlineDevices = devices.filter((d) => d.status === "online").length;
  const recentOps = operations.slice(0, 5);

  return (
    <PageWrapper title="Dashboard">
      <div className="grid grid-cols-4 gap-4 mb-8">
        <StatCard
          icon={<Server className="text-blue-600" />}
          label="Dispositivos"
          value={devices.length}
          sub={`${onlineDevices} online`}
        />
        <StatCard
          icon={<ClipboardList className="text-purple-600" />}
          label="Operações"
          value={operations.length}
          sub="total"
        />
        <StatCard
          icon={<Activity className="text-green-600" />}
          label="Online"
          value={onlineDevices}
          sub={`de ${devices.length}`}
        />
        <StatCard
          icon={<Shield className="text-orange-600" />}
          label="Erros"
          value={devices.filter((d) => d.status === "error").length}
          sub="dispositivos"
        />
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">Últimas Operações</h2>
        </div>
        <div className="divide-y divide-gray-100">
          {recentOps.length === 0 && (
            <p className="px-6 py-8 text-sm text-gray-400 text-center">Nenhuma operação ainda.</p>
          )}
          {recentOps.map((op) => (
            <div key={op.id} className="px-6 py-3 flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-900 truncate max-w-md">
                  {op.natural_language_input}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {new Date(op.created_at).toLocaleString("pt-BR")}
                </p>
              </div>
              <StatusBadge status={op.status} />
            </div>
          ))}
        </div>
      </div>
    </PageWrapper>
  );
}

function StatCard({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  sub: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center gap-3 mb-3">
        <div className="h-10 w-10 rounded-lg bg-gray-50 flex items-center justify-center">{icon}</div>
        <span className="text-sm text-gray-500">{label}</span>
      </div>
      <p className="text-3xl font-bold text-gray-900">{value}</p>
      <p className="text-xs text-gray-400 mt-1">{sub}</p>
    </div>
  );
}
