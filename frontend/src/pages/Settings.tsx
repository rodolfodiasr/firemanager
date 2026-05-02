import { useForm } from "react-hook-form";
import { useState } from "react";
import { KeyRound, User } from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { useAuth } from "../hooks/useAuth";
import apiClient from "../api/client";

interface PasswordForm {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

function PasswordSection() {
  const [success, setSuccess] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const { register, handleSubmit, watch, reset, formState: { errors, isSubmitting } } = useForm<PasswordForm>();

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
      setApiError(raw ?? "Erro ao alterar senha");
    }
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-center gap-2 mb-1">
        <KeyRound size={16} className="text-brand-500" />
        <h2 className="font-semibold text-gray-900">Alterar senha</h2>
      </div>
      <p className="text-sm text-gray-500 mb-5">Mínimo de 8 caracteres.</p>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {(["current_password", "new_password", "confirm_password"] as const).map((field) => {
          const labels = {
            current_password: "Senha atual",
            new_password: "Nova senha",
            confirm_password: "Confirmar nova senha",
          };
          return (
            <div key={field}>
              <label className="block text-sm font-medium text-gray-700 mb-1">{labels[field]}</label>
              <input
                type="password"
                {...register(field, {
                  required: "Obrigatório",
                  ...(field === "new_password" ? { minLength: { value: 8, message: "Mínimo 8 caracteres" } } : {}),
                  ...(field === "confirm_password" ? { validate: (v) => v === watch("new_password") || "Senhas não coincidem" } : {}),
                })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              {errors[field] && <p className="text-xs text-red-600 mt-1">{errors[field]?.message}</p>}
            </div>
          );
        })}
        {apiError && <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{apiError}</p>}
        {success && <p className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">Senha alterada com sucesso!</p>}
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-5 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50 transition-colors"
        >
          {isSubmitting ? "Salvando..." : "Alterar senha"}
        </button>
      </form>
    </div>
  );
}

export function Settings() {
  const { user } = useAuth();

  return (
    <PageWrapper title="Configurações">
      <div className="max-w-lg space-y-6">
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center gap-3 mb-3">
            <div className="h-10 w-10 rounded-full bg-brand-100 flex items-center justify-center">
              <User size={18} className="text-brand-600" />
            </div>
            <div>
              <p className="font-semibold text-gray-900">{user?.name ?? "—"}</p>
              <p className="text-sm text-gray-500">{user?.email ?? "—"}</p>
            </div>
          </div>
          <div className="flex gap-2 text-xs text-gray-400">
            <span className="bg-gray-100 px-2 py-0.5 rounded-full">{user?.role}</span>
            {user?.is_super_admin && (
              <span className="bg-brand-100 text-brand-700 px-2 py-0.5 rounded-full">Super Admin</span>
            )}
            {user?.mfa_enabled && (
              <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded-full">MFA ativo</span>
            )}
          </div>
        </div>
        <PasswordSection />
      </div>
    </PageWrapper>
  );
}
