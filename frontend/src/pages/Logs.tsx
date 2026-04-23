import { useQuery } from "@tanstack/react-query";
import { PageWrapper } from "../components/layout/PageWrapper";
import { EmptyState } from "../components/shared/EmptyState";
import { auditApi } from "../api/audit";

export function Logs() {
  const { data: logs = [], isLoading } = useQuery({
    queryKey: ["audit-logs"],
    queryFn: () => auditApi.getLogs({ limit: 100 }),
    refetchInterval: 10000,
  });

  return (
    <PageWrapper title="Logs de Auditoria">
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">Registros imutáveis (SHA-256)</h2>
          <span className="text-xs text-gray-400">{logs.length} registros</span>
        </div>

        {isLoading ? (
          <p className="text-sm text-gray-400 px-6 py-8">Carregando...</p>
        ) : logs.length === 0 ? (
          <EmptyState title="Nenhum log registrado ainda" />
        ) : (
          <div className="divide-y divide-gray-100 max-h-[70vh] overflow-y-auto">
            {logs.map((log) => (
              <div key={log.id} className="px-6 py-3">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-900">{log.action}</p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {new Date(log.created_at).toLocaleString("pt-BR")}
                      {log.ip_address && ` · ${log.ip_address}`}
                    </p>
                  </div>
                  <span className="text-xs font-mono text-gray-300 ml-4" title="SHA-256 hash">
                    {log.record_hash.substring(0, 12)}...
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </PageWrapper>
  );
}
