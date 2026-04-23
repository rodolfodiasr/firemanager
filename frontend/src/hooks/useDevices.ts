import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { devicesApi } from "../api/devices";
import type { DeviceCreate } from "../types/device";

export function useDevices() {
  const qc = useQueryClient();

  const devicesQuery = useQuery({
    queryKey: ["devices"],
    queryFn: devicesApi.list,
  });

  const createMutation = useMutation({
    mutationFn: (data: DeviceCreate) => devicesApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["devices"] });
      toast.success("Dispositivo adicionado com sucesso");
    },
    onError: () => toast.error("Erro ao adicionar dispositivo"),
  });

  const deleteMutation = useMutation({
    mutationFn: devicesApi.delete,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["devices"] });
      toast.success("Dispositivo removido");
    },
  });

  const healthCheckMutation = useMutation({
    mutationFn: devicesApi.healthCheck,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["devices"] }),
  });

  return {
    devices: devicesQuery.data ?? [],
    isLoading: devicesQuery.isLoading,
    create: createMutation.mutateAsync,
    remove: deleteMutation.mutate,
    healthCheck: healthCheckMutation.mutate,
  };
}
