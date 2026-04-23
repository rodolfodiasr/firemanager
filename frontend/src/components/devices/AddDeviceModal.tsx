import { useState } from "react";
import { useForm } from "react-hook-form";
import { X } from "lucide-react";
import type { DeviceCreate } from "../../types/device";

interface AddDeviceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: DeviceCreate) => Promise<void>;
}

export function AddDeviceModal({ isOpen, onClose, onSubmit }: AddDeviceModalProps) {
  const { register, handleSubmit, watch, formState: { errors, isSubmitting } } = useForm<DeviceCreate>({
    defaultValues: { port: 443, use_ssl: true, verify_ssl: false },
  });
  const authType = watch("credentials.auth_type", "token");

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 max-h-screen overflow-y-auto">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold">Adicionar Dispositivo</h2>
          <button onClick={onClose}><X size={20} /></button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nome</label>
            <input
              {...register("name", { required: "Nome obrigatório" })}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="FW-Sede-01"
            />
            {errors.name && <p className="text-red-600 text-xs mt-1">{errors.name.message}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Vendor</label>
            <select
              {...register("vendor", { required: true })}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="fortinet">Fortinet</option>
              <option value="sonicwall">SonicWall</option>
              <option value="pfsense">pfSense</option>
              <option value="opnsense">OPNsense</option>
              <option value="mikrotik">MikroTik</option>
              <option value="endian">Endian</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Host / IP</label>
              <input
                {...register("host", { required: "Host obrigatório" })}
                className="w-full border rounded-lg px-3 py-2 text-sm"
                placeholder="192.168.1.1"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Porta</label>
              <input
                type="number"
                {...register("port", { valueAsNumber: true })}
                className="w-full border rounded-lg px-3 py-2 text-sm"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Autenticação</label>
            <select
              {...register("credentials.auth_type")}
              className="w-full border rounded-lg px-3 py-2 text-sm mb-2"
            >
              <option value="token">API Token</option>
              <option value="user_pass">Usuário / Senha</option>
            </select>

            {authType === "token" ? (
              <input
                {...register("credentials.token", { required: true })}
                className="w-full border rounded-lg px-3 py-2 text-sm"
                placeholder="API Token"
                type="password"
              />
            ) : (
              <div className="space-y-2">
                <input
                  {...register("credentials.username")}
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                  placeholder="Usuário"
                />
                <input
                  {...register("credentials.password")}
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                  placeholder="Senha"
                  type="password"
                />
              </div>
            )}
          </div>

          <div className="flex gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" {...register("use_ssl")} />
              Usar SSL/HTTPS
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" {...register("verify_ssl")} />
              Verificar certificado
            </label>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 text-sm text-white bg-brand-600 rounded-lg hover:bg-brand-700 disabled:opacity-50"
            >
              {isSubmitting ? "Salvando..." : "Adicionar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
