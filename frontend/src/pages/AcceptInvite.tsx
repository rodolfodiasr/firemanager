import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Flame, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { inviteApi } from "../api/invite";

export function AcceptInvite() {
  const { token = "" } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);

  const { data: invite, isLoading, isError } = useQuery({
    queryKey: ["invite", token],
    queryFn: () => inviteApi.get(token),
    retry: false,
  });

  const accept = useMutation({
    mutationFn: () => inviteApi.accept(token, { name, password }),
    onSuccess: () => setDone(true),
  });

  if (isLoading) {
    return <CenteredCard><Loader2 className="animate-spin text-brand-400 mx-auto" size={32} /></CenteredCard>;
  }

  if (isError || !invite) {
    return (
      <CenteredCard>
        <XCircle className="text-red-400 mx-auto mb-3" size={40} />
        <h2 className="text-white font-semibold text-lg text-center">Convite inválido ou expirado</h2>
        <p className="text-gray-400 text-sm text-center mt-1">
          Este link não existe, já foi utilizado ou expirou.
        </p>
        <Link to="/login" className="block text-center mt-4 text-brand-400 hover:underline text-sm">
          Ir para o login
        </Link>
      </CenteredCard>
    );
  }

  if (done) {
    return (
      <CenteredCard>
        <CheckCircle className="text-green-400 mx-auto mb-3" size={40} />
        <h2 className="text-white font-semibold text-lg text-center">Convite aceito!</h2>
        <p className="text-gray-400 text-sm text-center mt-1">
          Sua conta foi criada. Você já pode fazer login no FireManager.
        </p>
        <button
          onClick={() => navigate("/login")}
          className="w-full mt-5 bg-brand-600 hover:bg-brand-700 text-white py-2.5 rounded-lg font-medium transition-colors"
        >
          Ir para o login
        </button>
      </CenteredCard>
    );
  }

  const passwordMismatch = confirm.length > 0 && password !== confirm;
  const canSubmit = name.trim().length > 0 && password.length >= 8 && !passwordMismatch;

  return (
    <CenteredCard>
      <div className="flex items-center gap-2 justify-center mb-6">
        <Flame className="text-brand-500" size={28} />
        <span className="text-xl font-bold text-white">FireManager</span>
      </div>

      <h2 className="text-white font-semibold text-lg text-center mb-1">
        Aceitar convite
      </h2>
      <p className="text-gray-400 text-sm text-center mb-6">
        Você foi convidado para{" "}
        <span className="text-white font-medium">{invite.tenant_name}</span>{" "}
        como <span className="capitalize text-brand-400">{invite.role}</span>.
      </p>

      <div className="space-y-4">
        <div>
          <label className="block text-sm text-gray-400 mb-1">Email</label>
          <input
            value={invite.email}
            disabled
            className="w-full bg-gray-700 text-gray-400 rounded-lg px-3 py-2.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Seu nome</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Nome completo"
            className="w-full bg-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Senha</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Mínimo 8 caracteres"
            className="w-full bg-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Confirmar senha</label>
          <input
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="Repita a senha"
            className={`w-full bg-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ${
              passwordMismatch ? "focus:ring-red-500 ring-2 ring-red-500" : "focus:ring-brand-500"
            }`}
          />
          {passwordMismatch && (
            <p className="text-red-400 text-xs mt-1">As senhas não coincidem</p>
          )}
        </div>

        {accept.isError && (
          <p className="text-red-400 text-sm">
            Erro ao aceitar convite. Tente novamente.
          </p>
        )}

        <button
          onClick={() => accept.mutate()}
          disabled={!canSubmit || accept.isPending}
          className="w-full bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white py-2.5 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
        >
          {accept.isPending && <Loader2 size={16} className="animate-spin" />}
          Criar conta e entrar
        </button>
      </div>

      <p className="text-xs text-gray-500 text-center mt-4">
        Convite expira em {new Date(invite.expires_at).toLocaleDateString("pt-BR")}
      </p>
    </CenteredCard>
  );
}

function CenteredCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-gray-900 rounded-2xl border border-gray-700 p-8">
        {children}
      </div>
    </div>
  );
}
