import { useState } from "react";
import { useForm } from "react-hook-form";
import { ShieldAlert, Eye, EyeOff, Building2, ArrowRight } from "lucide-react";
import { useAuth } from "../hooks/useAuth";

interface LoginForm {
  email: string;
  password: string;
  totp_code?: string;
}

export function Login() {
  const { signIn, selectTenant, pendingTenants } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectingTenant, setSelectingTenant] = useState(false);
  const { register, handleSubmit, formState: { isSubmitting } } = useForm<LoginForm>();

  const onSubmit = async (data: LoginForm) => {
    setError(null);
    try {
      await signIn(data.email, data.password, data.totp_code);
      // If pendingTenants is set after signIn, show tenant picker (handled below)
    } catch (err: unknown) {
      const raw = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      const msg = typeof raw === "string" ? raw : "Credenciais inválidas";
      setError(msg);
    }
  };

  const handleSelectTenant = async (tenantId: string) => {
    setSelectingTenant(true);
    setError(null);
    try {
      await selectTenant(tenantId);
    } catch {
      setError("Erro ao selecionar tenant. Tente novamente.");
      setSelectingTenant(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center h-16 w-16 bg-brand-600 rounded-2xl mb-4">
            <ShieldAlert size={32} className="text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white">Eternity SecOps</h1>
          <p className="text-gray-400 mt-1">Plataforma de Segurança e Gestão de Infraestrutura com IA</p>
        </div>

        <div className="bg-gray-900 rounded-2xl p-8 shadow-xl">
          {/* Tenant selection step */}
          {pendingTenants ? (
            <div>
              <p className="text-sm font-semibold text-gray-300 mb-4 text-center">
                Selecione o tenant para acessar:
              </p>
              <div className="space-y-2">
                {pendingTenants.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => handleSelectTenant(t.id)}
                    disabled={selectingTenant}
                    className="w-full flex items-center justify-between px-4 py-3 bg-gray-800 border border-gray-700 hover:border-brand-500 rounded-xl text-white text-sm font-medium transition-colors disabled:opacity-50"
                  >
                    <span className="flex items-center gap-2">
                      <Building2 size={16} className="text-brand-400" />
                      {t.name}
                    </span>
                    <ArrowRight size={14} className="text-gray-400" />
                  </button>
                ))}
              </div>
              {error && (
                <p className="text-red-400 text-sm bg-red-900/20 border border-red-900 rounded-lg px-3 py-2 mt-4">
                  {error}
                </p>
              )}
            </div>
          ) : (
            /* Login form */
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">E-mail</label>
                <input
                  type="email"
                  {...register("email", { required: true })}
                  className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  placeholder="admin@eternity.local"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Senha</label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    {...register("password", { required: true })}
                    className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 pr-10"
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400"
                    onClick={() => setShowPassword((p) => !p)}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Código MFA <span className="text-gray-500">(opcional)</span>
                </label>
                <input
                  {...register("totp_code")}
                  className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  placeholder="123456"
                  maxLength={6}
                />
              </div>

              {error && (
                <p className="text-red-400 text-sm bg-red-900/20 border border-red-900 rounded-lg px-3 py-2">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full bg-brand-600 hover:bg-brand-700 text-white font-medium py-2.5 rounded-lg transition-colors disabled:opacity-50 mt-2"
              >
                {isSubmitting ? "Entrando..." : "Entrar"}
              </button>
            </form>
          )}
        </div>

        <p className="text-center text-xs text-gray-600 mt-6">
          Eternity SecOps v0.1.0
        </p>
      </div>
    </div>
  );
}
