import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { X, Info } from "lucide-react";
import type { DeviceCreate, VendorEnum } from "../../types/device";

interface AddDeviceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: DeviceCreate) => Promise<void>;
}

const VENDOR_CONFIG: Record<VendorEnum, {
  label: string;
  authType: "token" | "user_pass";
  tokenLabel?: string;
  tokenPlaceholder?: string;
  usernameLabel?: string;
  usernamePlaceholder?: string;
  passwordLabel?: string;
  defaultPort: number;
  hint: string;
  extraFields?: "vdom" | "os_version";
}> = {
  fortinet: {
    label: "Fortinet FortiGate",
    authType: "token",
    tokenLabel: "API Token",
    tokenPlaceholder: "Cole o token gerado em System > Admin > REST API Admin",
    defaultPort: 443,
    hint: "FortiOS 7.x+ · System > Admin > REST API Admin > Create",
    extraFields: "vdom",
  },
  sonicwall: {
    label: "SonicWall",
    authType: "user_pass",
    usernameLabel: "Usuário admin",
    usernamePlaceholder: "admin",
    passwordLabel: "Senha",
    defaultPort: 443,
    hint: "SonicOS 6.x / 7.x · Manage > Administration > Enable API",
    extraFields: "os_version",
  },
  pfsense: {
    label: "pfSense",
    authType: "token",
    tokenLabel: "API Key",
    tokenPlaceholder: "Chave gerada pelo pacote pfSense-API",
    defaultPort: 443,
    hint: "Requer pacote pfSense-API (jaredhendrickson13) · System > Package Manager",
  },
  opnsense: {
    label: "OPNsense",
    authType: "user_pass",
    usernameLabel: "API Key",
    usernamePlaceholder: "API Key (System > Access > Users > API Keys)",
    passwordLabel: "API Secret",
    defaultPort: 443,
    hint: "OPNsense 21+ · System > Access > Users > Edit > API Keys > Add",
  },
  mikrotik: {
    label: "MikroTik",
    authType: "user_pass",
    usernameLabel: "Usuário",
    usernamePlaceholder: "admin",
    passwordLabel: "Senha",
    defaultPort: 443,
    hint: "RouterOS 7+ · IP > Services > api-ssl deve estar habilitado",
  },
  endian: {
    label: "Endian Firewall",
    authType: "user_pass",
    usernameLabel: "Usuário",
    usernamePlaceholder: "admin",
    passwordLabel: "Senha",
    defaultPort: 10443,
    hint: "Endian 3.x — suporte básico (teste de conectividade)",
  },
};

export function AddDeviceModal({ isOpen, onClose, onSubmit }: AddDeviceModalProps) {
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<DeviceCreate & { credentials: { vdom?: string; os_version?: number } }>({
    defaultValues: { vendor: "fortinet", port: 443, use_ssl: true, verify_ssl: false },
  });

  const vendor = watch("vendor") as VendorEnum;
  const cfg = VENDOR_CONFIG[vendor] ?? VENDOR_CONFIG.fortinet;

  useEffect(() => {
    setValue("credentials.auth_type", cfg.authType);
    setValue("port", cfg.defaultPort);
  }, [vendor, cfg.authType, cfg.defaultPort, setValue]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold">Adicionar Dispositivo</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {/* Nome */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nome</label>
            <input
              {...register("name", { required: "Nome obrigatório" })}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="FW-Sede-01"
            />
            {errors.name && <p className="text-red-600 text-xs mt-1">{errors.name.message}</p>}
          </div>

          {/* Vendor */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Vendor</label>
            <select
              {...register("vendor", { required: true })}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              {Object.entries(VENDOR_CONFIG).map(([v, c]) => (
                <option key={v} value={v}>{c.label}</option>
              ))}
            </select>
            {cfg.hint && (
              <p className="text-xs text-gray-400 mt-1 flex items-center gap-1">
                <Info size={11} />
                {cfg.hint}
              </p>
            )}
          </div>

          {/* Host + Port */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Host / IP</label>
              <input
                {...register("host", { required: "Host obrigatório" })}
                className="w-full border rounded-lg px-3 py-2 text-sm"
                placeholder="192.168.1.1"
              />
              {errors.host && <p className="text-red-600 text-xs mt-1">{errors.host.message}</p>}
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

          {/* Credentials — token */}
          {cfg.authType === "token" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {cfg.tokenLabel ?? "API Token"}
              </label>
              <input
                {...register("credentials.token", { required: true })}
                type="password"
                className="w-full border rounded-lg px-3 py-2 text-sm"
                placeholder={cfg.tokenPlaceholder ?? "Token"}
              />
            </div>
          )}

          {/* Credentials — user + password */}
          {cfg.authType === "user_pass" && (
            <div className="space-y-2">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {cfg.usernameLabel ?? "Usuário"}
                </label>
                <input
                  {...register("credentials.username", { required: true })}
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                  placeholder={cfg.usernamePlaceholder ?? "admin"}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {cfg.passwordLabel ?? "Senha"}
                </label>
                <input
                  {...register("credentials.password", { required: true })}
                  type="password"
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                  placeholder="••••••••"
                />
              </div>
            </div>
          )}

          {/* Fortinet extra: VDOM */}
          {cfg.extraFields === "vdom" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                VDOM <span className="text-gray-400 font-normal">(padrão: root)</span>
              </label>
              <input
                {...register("credentials.vdom")}
                className="w-full border rounded-lg px-3 py-2 text-sm"
                placeholder="root"
              />
            </div>
          )}

          {/* SonicWall extra: OS Version */}
          {cfg.extraFields === "os_version" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Versão do SonicOS</label>
              <select
                {...register("credentials.os_version", { valueAsNumber: true })}
                className="w-full border rounded-lg px-3 py-2 text-sm"
              >
                <option value={7}>SonicOS 7.x (padrão)</option>
                <option value={6}>SonicOS 6.x</option>
              </select>
            </div>
          )}

          {/* SSL */}
          <div className="flex gap-5">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" {...register("use_ssl")} className="rounded" />
              Usar HTTPS
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" {...register("verify_ssl")} className="rounded" />
              Verificar certificado SSL
            </label>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Observações <span className="text-gray-400 font-normal">(opcional)</span>
            </label>
            <textarea
              {...register("notes")}
              rows={2}
              className="w-full border rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="Ex: Firewall perimetral sede SP"
            />
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
