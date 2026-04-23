import { useQuery } from "@tanstack/react-query";
import { PageWrapper } from "../components/layout/PageWrapper";
import { StatusBadge } from "../components/shared/StatusBadge";
import { EmptyState } from "../components/shared/EmptyState";
import { operationsApi } from "../api/operations";

export function Operations() {
  const { data: operations = [], isLoading } = useQuery({
    queryKey: ["operations"],
    queryFn: operationsApi.list,
    refetchInterval: 5000,
  });

  return (
    <PageWrapper title="Operações">
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">Histórico de Operações</h2>
        </div>

        {isLoading ? (
          <p className="text-sm text-gray-400 px-6 py-8">Carregando...</p>
        ) : operations.length === 0 ? (
          <EmptyState title="Nenhuma operação ainda" description="As operações executadas pelo agente aparecerão aqui." />
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-6 py-3 text-left">Solicitação</th>
                <th className="px-6 py-3 text-left">Intenção</th>
                <th className="px-6 py-3 text-left">Status</th>
                <th className="px-6 py-3 text-left">Data</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {operations.map((op) => (
                <tr key={op.id} className="hover:bg-gray-50">
                  <td className="px-6 py-3 max-w-xs">
                    <p className="truncate text-gray-900">{op.natural_language_input}</p>
                  </td>
                  <td className="px-6 py-3 text-gray-500">{op.intent ?? "—"}</td>
                  <td className="px-6 py-3">
                    <StatusBadge status={op.status} />
                  </td>
                  <td className="px-6 py-3 text-gray-400">
                    {new Date(op.created_at).toLocaleString("pt-BR")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </PageWrapper>
  );
}
