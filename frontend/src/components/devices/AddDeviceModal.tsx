import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { X, Info } from "lucide-react";
import type { DeviceCategory, DeviceCreate, VendorEnum } from "../../types/device";

interface AddDeviceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: DeviceCreate) => Promise<void>;
}

type ConnProtocol = "rest" | "ssh";

interface VendorConfig {
  label: string;
  authType: "token" | "user_pass";
  connProtocol: ConnProtocol;
  tokenLabel?: string;
  tokenPlaceholder?: string;
  usernameLabel?: string;
  usernamePlaceholder?: string;
  passwordLabel?: string;
  defaultPort: number;
  hint: string;
  extraFields?: "vdom" | "os_version" | "cmdline_password";
}

const VENDOR_CONFIG: Record<VendorEnum, VendorConfig> = {
  // ── Firewalls ────────────────────────────────────────────────────────────
  fortinet: {
    label: "Fortinet FortiGate",
    authType: "token",
    connProtocol: "rest",
    tokenLabel: "API Token",
    tokenPlaceholder: "Cole o token gerado em System > Admin > REST API Admin",
    defaultPort: 443,
    hint: "FortiOS 7.x+ · System > Admin > REST API Admin > Create",
    extraFields: "vdom",
  },
  sonicwall: {
    label: "SonicWall",
    authType: "user_pass",
    connProtocol: "rest",
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
    connProtocol: "rest",
    tokenLabel: "API Key",
    tokenPlaceholder: "Chave gerada pelo pacote pfSense-API",
    defaultPort: 443,
    hint: "Requer pacote pfSense-API (jaredhendrickson13) · System > Package Manager",
  },
  opnsense: {
    label: "OPNsense",
    authType: "user_pass",
    connProtocol: "rest",
    usernameLabel: "API Key",
    usernamePlaceholder: "API Key (System > Access > Users > API Keys)",
    passwordLabel: "API Secret",
    defaultPort: 443,
    hint: "OPNsense 21+ · System > Access > Users > Edit > API Keys > Add",
  },
  mikrotik: {
    label: "MikroTik",
    authType: "user_pass",
    connProtocol: "rest",
    usernameLabel: "Usuário",
    usernamePlaceholder: "admin",
    passwordLabel: "Senha",
    defaultPort: 443,
    hint: "RouterOS 7+ · IP > Services > api-ssl deve estar habilitado",
  },
  endian: {
    label: "Endian Firewall",
    authType: "user_pass",
    connProtocol: "rest",
    usernameLabel: "Usuário",
    usernamePlaceholder: "admin",
    passwordLabel: "Senha",
    defaultPort: 10443,
    hint: "Endian 3.x — suporte básico (teste de conectividade)",
  },

  // ── Routers / Switches ───────────────────────────────────────────────────
  cisco_ios: {
    label: "Cisco IOS / IOS-XE",
    authType: "user_pass",
    connProtocol: "ssh",
    usernameLabel: "Usuário",
    usernamePlaceholder: "admin",
    passwordLabel: "Senha (enable)",
    defaultPort: 22,
    hint: "IOS 15.x+ / IOS-XE · SSH habilitado + nível de privilégio 15",
  },
  cisco_nxos: {
    label: "Cisco NX-OS (Nexus)",
    authType: "user_pass",
    connProtocol: "ssh",
    usernameLabel: "Usuário",
    usernamePlaceholder: "admin",
    passwordLabel: "Senha",
    defaultPort: 22,
    hint: "NX-OS · SSH habilitado ou NX-API REST (feature nxapi)",
  },
  juniper: {
    label: "Juniper JunOS",
    authType: "user_pass",
    connProtocol: "ssh",
    usernameLabel: "Usuário",
    usernamePlaceholder: "admin",
    passwordLabel: "Senha",
    defaultPort: 22,
    hint: "JunOS · SSH + NETCONF (set system services netconf ssh)",
  },
  aruba: {
    label: "Aruba / HPE ProCurve",
    authType: "user_pass",
    connProtocol: "ssh",
    usernameLabel: "Usuário",
    usernamePlaceholder: "admin",
    passwordLabel: "Senha (enable)",
    defaultPort: 22,
    hint: "Aruba OS-CX / AOS-Switch (HPE ProCurve) · SSH habilitado",
  },
  ubiquiti: {
    label: "Ubiquiti EdgeOS / EdgeSwitch",
    authType: "user_pass",
    connProtocol: "ssh",
    usernameLabel: "Usuário",
    usernamePlaceholder: "admin",
    passwordLabel: "Senha",
    defaultPort: 22,
    hint: "EdgeOS / EdgeSwitch · SSH habilitado",
  },
  dell: {
    label: "DELL PowerSwitch (OS10)",
    authType: "user_pass",
    connProtocol: "ssh",
    usernameLabel: "Usuário",
    usernamePlaceholder: "admin",
    passwordLabel: "Senha",
    defaultPort: 22,
    hint: "DELL EMC PowerSwitch S/Z-series (OS10) · SSH habilitado",
  },
  dell_n: {
    label: "DELL N-Series (DNOS6)",
    authType: "user_pass",
    connProtocol: "ssh",
    usernameLabel: "Usuário",
    usernamePlaceholder: "admin",
    passwordLabel: "Senha (enable)",
    defaultPort: 22,
    hint: "DELL EMC Networking N1524P / N1548P / N2000 / N3000 · Firmware 6.x · SSH habilitado",
  },
  hp_comware: {
    label: "HP / H3C Comware (V1910, V3600)",
    authType: "user_pass",
    connProtocol: "ssh",
    usernameLabel: "Usuário",
    usernamePlaceholder: "admin",
    passwordLabel: "Senha",
    defaultPort: 22,
    extraFields: "cmdline_password",
    hint: "HP V1910 / V3600 / A-Series · Comware 5.x · SSH habilitado (ip ssh server enable)",
  },
};

const CATEGORY_LABELS: Record<DeviceCategory, string> = {
  firewall:  "Firewall",
  router:    "Roteador",
  switch:    "Switch",
  l3_switch: "Switch L3",
};

const CATEGORY_VENDORS: Record<DeviceCategory, VendorEnum[]> = {
  firewall:  ["fortinet", "sonicwall", "pfsense", "opnsense", "mikrotik", "endian"],
  router:    ["cisco_ios", "juniper", "mikrotik", "ubiquiti"],
  switch:    ["cisco_ios", "cisco_nxos", "aruba", "dell", "dell_n", "hp_comware", "ubiquiti"],
  l3_switch: ["cisco_ios", "cisco_nxos", "juniper", "aruba", "dell", "dell_n", "hp_comware"],
};

export function AddDeviceModal({ isOpen, onClose, onSubmit }: AddDeviceModalProps) {
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<DeviceCreate>({
    defaultValues: {
      category: "firewall",
      vendor: "fortinet",
      port: 443,
      use_ssl: true,
      verify_ssl: false,
    },
  });

  const category = watch("category") as DeviceCategory;
  const vendor   = watch("vendor")   as VendorEnum;
  const cfg      = VENDOR_CONFIG[vendor] ?? VENDOR_CONFIG.fortinet;
  const isSSH    = cfg.connProtocol === "ssh";

  // When category changes → reset vendor to first in the new list
  useEffect(() => {
    const first = CATEGORY_VENDORS[category][0];
    setValue("vendor", first);
  }, [category, setValue]);

  // When vendor changes → update auth_type and port
  useEffect(() => {
    setValue("credentials.auth_type", isSSH ? "ssh" : cfg.authType);
    setValue("port", cfg.defaultPort);
    if (isSSH) setValue("use_ssl", false);
  }, [vendor, cfg.authType, cfg.defaultPort, isSSH, setValue]);

  if (!isOpen) return null;

  const availableVendors = CATEGORY_VENDORS[category] ?? [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold">Adicionar Dispositivo</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">

          {/* Categoria */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Categoria</label>
            <div className="grid grid-cols-4 gap-1.5">
              {(Object.keys(CATEGORY_LABELS) as DeviceCategory[]).map((cat) => (
                <label
                  key={cat}
                  className={`flex items-center justify-center text-xs font-medium py-2 rounded-lg border cursor-pointer transition-colors ${
                    category === cat
                      ? "bg-brand-600 text-white border-brand-600"
                      : "text-gray-600 border-gray-200 hover:border-brand-400"
                  }`}
                >
                  <input
                    type="radio"
                    value={cat}
                    {...register("category")}
                    className="sr-only"
                  />
                  {CATEGORY_LABELS[cat]}
                </label>
              ))}
            </div>
          </div>

          {/* Nome */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nome</label>
            <input
              {...register("name", { required: "Nome obrigatório" })}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder={category === "firewall" ? "FW-Sede-01" : category === "router" ? "RTR-Edge-01" : "SW-Andar2-01"}
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
              {availableVendors.map((v) => (
                <option key={v} value={v}>{VENDOR_CONFIG[v].label}</option>
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
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {isSSH ? "Porta SSH" : "Porta HTTPS"}
              </label>
              <input
                type="number"
                {...register("port", { valueAsNumber: true })}
                className="w-full border rounded-lg px-3 py-2 text-sm"
              />
            </div>
          </div>

          {/* Credentials — token */}
          {cfg.authType === "token" && !isSSH && (
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

          {/* Credentials — user + password (REST or SSH) */}
          {(cfg.authType === "user_pass" || isSSH) && (
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

          {/* HP Comware extra: cmdline-mode password */}
          {cfg.extraFields === "cmdline_password" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Senha cmdline-mode{" "}
                <span className="text-red-500 font-normal">(obrigatória para V1910 — necessária para todas as operações)</span>
              </label>
              <input
                {...register("credentials.cmdline_password")}
                type="password"
                className="w-full border rounded-lg px-3 py-2 text-sm"
                placeholder="Ex: 512900"
              />
              <p className="text-xs text-gray-400 mt-1">
                Usada no comando <code className="bg-gray-100 px-1 rounded">_cmdline-mode on</code> antes de entrar em system-view
              </p>
            </div>
          )}

          {/* SSL — só para conexões REST */}
          {!isSSH && (
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
          )}

          {/* Notes */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Observações <span className="text-gray-400 font-normal">(opcional)</span>
            </label>
            <textarea
              {...register("notes")}
              rows={2}
              className="w-full border rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder={`Ex: ${category === "firewall" ? "Firewall perimetral sede SP" : category === "router" ? "Roteador de borda ISP primário" : "Switch de distribuição 2º andar"}`}
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200">
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
