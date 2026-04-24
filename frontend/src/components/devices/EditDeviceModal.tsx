import { useState } from "react";
import { useForm } from "react-hook-form";
import { X } from "lucide-react";
import type { Device, DeviceCreate } from "../../types/device";

interface EditDeviceModalProps {
  isOpen: boolean;
  device: Device | null;
  onClose: () => void;
  onSubmit: (id: string, data: Partial<DeviceCreate>) => Promise<void>;
}

export function EditDeviceModal({ isOpen, device, onClose, onSubmit }: EditDeviceModalProps) {
  const [changeCredentials, setChangeCredentials] = useState(false);
  const { register, handleSubmit, watch, reset, formState: { isSubmitting } } = useForm<DeviceCreate>();
  const authType = watch("credentials.auth_type", "token");

  if (!isOpen || !device) return null;

  const handleClose = () => {
    reset();
    setChangeCredentials(false);
    onClose();
  };

  const handleFormSubmit = async (data: DeviceCreate) => {
    const payload: Partial<DeviceCreate> = {
      name: data.name,
      host: data.host,
      port: data.port,
      use_ssl: data.use_ssl,
      verify_ssl: data.verify_ssl,
      notes: data.notes,
    };
    if (changeCredentials) {
      payload.credentials = data.credentials;
    }
    await onSubmit(device.id, payload);
    handleClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 max-h-screen overflow-y-auto">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold">Editar Dispositivo</h2>
          <button onClick={handleClose}><X size={20} /></button>
        </div>

        <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nome</label>
            <input
              {...register("name", { required: "Nome obrigatório" })}
              defaultValue={device.name}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Vendor</label>
            <input
              value={device.vendor}
              disabled
              className="w-full border rounded-lg px-3 py-2 text-sm bg-gray-100 text-gray-500 cursor-not-allowed"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Host / IP</label>
              <input
                {...register("host", { required: "Host obrigatório" })}
                defaultValue={device.host}
                className="w-full border rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Porta</label>
              <input
                type="number"
                {...register("port", { valueAsNumber: true })}
                defaultValue={device.port}
                className="w-full border rounded-lg px-3 py-2 text-sm"
              />
            </div>
          </div>

          <div className="flex gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" {...register("use_ssl")} defaultChecked={device.use_ssl} />
              Usar SSL/HTTPS
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" {...register("verify_ssl")} defaultChecked={device.verify_ssl} />
              Verificar certificado
            </label>
          </div>

          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-gray-700 cursor-pointer">
              <input
                type="checkbox"
                checked={changeCredentials}
                onChange={(e) => setChangeCredentials(e.target.checked)}
              />
              Alterar credenciais
            </label>
          </div>

          {changeCredentials && (
            <div className="border rounded-lg p-3 bg-gray-50 space-y-2">
              <select
                {...register("credentials.auth_type")}
                className="w-full border rounded-lg px-3 py-2 text-sm mb-2"
              >
                <option value="token">API Token</option>
                <option value="user_pass">Usuário / Senha</option>
              </select>

              {authType === "token" ? (
                <input
                  {...register("credentials.token")}
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                  placeholder="API Token"
                  type="password"
                />
              ) : (
                <>
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
                </>
              )}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 text-sm text-white bg-brand-600 rounded-lg hover:bg-brand-700 disabled:opacity-50"
            >
              {isSubmitting ? "Salvando..." : "Salvar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
