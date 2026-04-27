import { useState } from "react";
import { useForm } from "react-hook-form";
import { KeyRound, User } from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { useAuth } from "../hooks/useAuth";
import apiClient from "../api/client";

interface PasswordForm {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

export function Settings() {
  const { user } = useAuth();
  const [success, setSuccess] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    watch,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<PasswordForm>();

  const onSubmit = async (data: PasswordForm) => {
    setApiError(null);
    setSuccess(false);
    try {
      await apiClient.post("/auth/me/password", {
        current_password: data.current_password,
        new_password: data.new_password,
      });
      setSuccess(true);
      reset();
    } catch (err: unknown) {
      const raw = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setApiError(raw ?? "Erro ao alterar senha. Tente novamente.");
    }
  };

  return (
    <PageWrapper title="Configurações">
      <div className="max-w-lg space-y-6">
        {/* Profile info */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="h-10 w-10 rounded-full bg-brand-100 flex items-center justify-center">
              <User size={18} className="text-brand-600" />
            </div>
            <div>
              <p className="font-semibold text-gray-900">{user?.name ?? "—"}</p>
              <p className="text-sm text-gray-500">{user?.email ?? "—"}</p>
            </div>
          </div>
          <div className="flex gap-3 text-xs text-gray-400">
            <span className="bg-gray-100 px-2 py-0.5 rounded-full">{user?.role}</span>
            {user?.is_super_admin && (
              <span className="bg-brand-100 text-brand-700 px-2 py-0.5 rounded-full">Super Admin</span>
            )}
            {user?.mfa_enabled && (
              <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded-full">MFA ativo</span>
            )}
          </div>
        </div>

        {/* Password change */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center gap-2 mb-1">
            <KeyRound size={16} className="text-brand-500" />
            <h2 className="font-semibold text-gray-900">Alterar senha</h2>
          </div>
          <p className="text-sm text-gray-500 mb-5">A nova senha deve ter no mínimo 8 caracteres.</p>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Senha atual</label>
              <input
                type="password"
                {...register("current_password", { required: "Campo obrigatório" })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              {errors.current_password && (
                <p className="text-xs text-red-600 mt-1">{errors.current_password.message}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Nova senha</label>
              <input
                type="password"
                {...register("new_password", {
                  required: "Campo obrigatório",
                  minLength: { value: 8, message: "Mínimo de 8 caracteres" },
                })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              {errors.new_password && (
                <p className="text-xs text-red-600 mt-1">{errors.new_password.message}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Confirmar nova senha</label>
              <input
                type="password"
                {...register("confirm_password", {
                  required: "Campo obrigatório",
                  validate: (v) => v === watch("new_password") || "As senhas não coincidem",
                })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              {errors.confirm_password && (
                <p className="text-xs text-red-600 mt-1">{errors.confirm_password.message}</p>
              )}
            </div>

            {apiError && (
              <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {apiError}
              </p>
            )}
            {success && (
              <p className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
                Senha alterada com sucesso!
              </p>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50 transition-colors"
            >
              {isSubmitting ? "Salvando..." : "Alterar senha"}
            </button>
          </form>
        </div>
      </div>
    </PageWrapper>
  );
}
