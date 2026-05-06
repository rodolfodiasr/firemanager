import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { X } from "lucide-react";
import type { Device, DeviceCreate } from "../../types/device";

// Vendors that connect via SSH username/password only (no API token option)
const SSH_VENDORS = new Set([
  "cisco_ios", "cisco_nxos", "juniper", "aruba",
  "dell", "dell_n", "ubiquiti", "hp_comware",
]);

interface EditDeviceModalProps {
  isOpen: boolean;
  device: Device | null;
  onClose: () => void;
  onSubmit: (id: string, data: Partial<DeviceCreate>) => Promise<unknown>;
}

export function EditDeviceModal({ isOpen, device, onClose, onSubmit }: EditDeviceModalProps) {
  const [changeCredentials, setChangeCredentials] = useState(false);
  const { register, handleSubmit, watch, reset, formState: { isSubmitting } } = useForm<DeviceCreate>();
  const authType = watch("credentials.auth_type", "token");

  useEffect(() => {
    if (isOpen && device) {
      reset({
        name: device.name,
        host: device.host,
        port: device.port,
        use_ssl: device.use_ssl,
        verify_ssl: device.verify_ssl,
        notes: device.notes ?? "",
        zabbix_host_name: device.zabbix_host_name ?? "",
        wazuh_agent_name: device.wazuh_agent_name ?? "",
      });
      setChangeCredentials(false);
    }
  }, [isOpen, device, reset]);

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
      zabbix_host_name: data.zabbix_host_name || null,
      wazuh_agent_name: data.wazuh_agent_name || null,
    };
    if (changeCredentials) {
      payload.credentials = {
        ...data.credentials,
        auth_type: SSH_VENDORS.has(device.vendor) ? "ssh" : data.credentials.auth_type,
      };
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
                className="w-full border rounded-lg px-3 py-2 text-sm"
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
              {/* SSH vendors always use username + password — no auth_type toggle */}
              {SSH_VENDORS.has(device.vendor) ? (
                <>
                  <input
                    {...register("credentials.username")}
                    className="w-full border rounded-lg px-3 py-2 text-sm"
                    placeholder="Usuário SSH"
                  />
                  <input
                    {...register("credentials.password")}
                    className="w-full border rounded-lg px-3 py-2 text-sm"
                    placeholder="Senha SSH"
                    type="password"
                  />
                  {device.vendor === "hp_comware" && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Senha cmdline-mode{" "}
                        <span className="text-red-500 font-normal">(obrigatória para V1910)</span>
                      </label>
                      <input
                        {...register("credentials.cmdline_password")}
                        className="w-full border rounded-lg px-3 py-2 text-sm"
                        placeholder="Ex: 512900"
                        type="password"
                      />
                      <p className="text-xs text-gray-400 mt-1">
                        Usada no <code className="bg-gray-100 px-1 rounded">_cmdline-mode on</code> — necessária para todas as operações
                      </p>
                    </div>
                  )}
                </>
              ) : (
                <>
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
                </>
              )}
            </div>
          )}

          {/* Correlação com sistemas externos */}
          <div className="border rounded-lg p-3 bg-gray-50 space-y-3">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Correlação — Zabbix / Wazuh</p>
            <p className="text-xs text-gray-400">
              Preencha somente se o nome do host no Zabbix ou o nome do agente no Wazuh difere do IP/nome deste dispositivo.
              Usado pelo módulo de análise de tickets GLPI para correlação precisa.
            </p>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Host name no Zabbix <span className="text-gray-400 font-normal">(opcional)</span>
              </label>
              <input
                {...register("zabbix_host_name")}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder="Ex: fw-sp-01.empresa.local"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Agent name no Wazuh <span className="text-gray-400 font-normal">(opcional)</span>
              </label>
              <input
                {...register("wazuh_agent_name")}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder="Ex: fw-sp-01"
              />
            </div>
          </div>

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
