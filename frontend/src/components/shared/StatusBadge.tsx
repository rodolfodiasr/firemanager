const statusConfig = {
  online: { color: "bg-green-100 text-green-800", label: "Online" },
  offline: { color: "bg-red-100 text-red-800", label: "Offline" },
  unknown: { color: "bg-gray-100 text-gray-800", label: "Desconhecido" },
  error: { color: "bg-orange-100 text-orange-800", label: "Erro" },
  pending: { color: "bg-yellow-100 text-yellow-800", label: "Pendente" },
  approved: { color: "bg-blue-100 text-blue-800", label: "Aprovado" },
  executing: { color: "bg-indigo-100 text-indigo-800", label: "Executando" },
  completed: { color: "bg-green-100 text-green-800", label: "Concluído" },
  failed: { color: "bg-red-100 text-red-800", label: "Falhou" },
  rejected: { color: "bg-red-100 text-red-800", label: "Rejeitado" },
  awaiting_approval: { color: "bg-yellow-100 text-yellow-800", label: "Aguardando" },
} as const;

interface StatusBadgeProps {
  status: string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status as keyof typeof statusConfig] ?? {
    color: "bg-gray-100 text-gray-800",
    label: status,
  };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.color}`}>
      {config.label}
    </span>
  );
}
