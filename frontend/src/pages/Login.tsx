import { useState } from "react";
import { useForm } from "react-hook-form";
import {
  ShieldAlert, Eye, EyeOff, Building2, ArrowRight,
  MessageSquare, BookOpen, Bot, Server, ShieldCheck, FileCheck, Users, Zap,
} from "lucide-react";
import { useAuth } from "../hooks/useAuth";

interface LoginForm {
  email: string;
  password: string;
  totp_code?: string;
}

const FEATURES = [
  {
    icon: MessageSquare,
    color: "bg-sky-500/20 text-sky-400",
    title: "Chat IA Contextual",
    desc: "RAG + memória de sessão, Claude ou GPT-4o",
  },
  {
    icon: BookOpen,
    color: "bg-emerald-500/20 text-emerald-400",
    title: "Planos de Ação e Remediação",
    desc: "Conversa → doc sanitizado → BookStack → RAG",
  },
  {
    icon: Bot,
    color: "bg-indigo-500/20 text-indigo-400",
    title: "IA Agentic Multi-agente",
    desc: "Orquestrador + 5 sub-agentes especializados",
  },
  {
    icon: Server,
    color: "bg-violet-500/20 text-violet-400",
    title: "Multi-vendor · Multi-cloud",
    desc: "50+ vendors + AWS / Azure / GCP",
  },
  {
    icon: ShieldCheck,
    color: "bg-amber-500/20 text-amber-400",
    title: "Governança & Audit",
    desc: "Hash-chain, aprovação dupla, maintenance windows",
  },
  {
    icon: FileCheck,
    color: "bg-yellow-500/20 text-yellow-400",
    title: "Compliance CIS/PCI/BACEN",
    desc: "Score 0–100, checks automáticos, PDF executivo",
  },
  {
    icon: Users,
    color: "bg-orange-500/20 text-orange-400",
    title: "Identidade AD + M365",
    desc: "JIT, SoD, revisão de acesso, licenças",
  },
  {
    icon: Zap,
    color: "bg-brand-600/20 text-brand-300",
    title: "SOAR & Playbooks",
    desc: "Resposta automática, feeds IoC, MTTR tracking",
  },
] as const;

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
    <div className="min-h-screen flex">

      {/* ── Painel esquerdo — formulário ─────────────────────────────── */}
      <div className="w-full lg:w-[440px] xl:w-[480px] shrink-0 bg-gray-950 flex flex-col justify-between px-10 py-12">

        {/* Logo + branding */}
        <div>
          <div className="flex items-center gap-3 mb-10">
            <div className="w-10 h-10 rounded-xl bg-brand-600 flex items-center justify-center shrink-0">
              <ShieldAlert size={22} className="text-white" />
            </div>
            <div>
              <p className="text-white font-bold text-base leading-tight">Eternity SecOps</p>
              <p className="text-gray-500 text-[11px] leading-tight">Enterprise MSSP Platform</p>
            </div>
          </div>

          <h2 className="text-2xl font-bold text-white mb-1">Bem-vindo de volta</h2>
          <p className="text-sm text-gray-400 mb-8">
            Opere sua infraestrutura de segurança em linguagem natural.
          </p>

          {/* Seleção de tenant */}
          {pendingTenants ? (
            <div>
              <p className="text-sm font-semibold text-gray-300 mb-4">
                Selecione o tenant para acessar:
              </p>
              <div className="space-y-2">
                {pendingTenants.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => handleSelectTenant(t.id)}
                    disabled={selectingTenant}
                    className="w-full flex items-center justify-between px-4 py-3 bg-gray-900 border border-gray-800 hover:border-brand-600 rounded-xl text-white text-sm font-medium transition-colors disabled:opacity-50"
                  >
                    <span className="flex items-center gap-2">
                      <Building2 size={15} className="text-brand-500" />
                      {t.name}
                    </span>
                    <ArrowRight size={14} className="text-gray-500" />
                  </button>
                ))}
              </div>
              {error && (
                <p className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-xl px-3 py-2 mt-4">
                  {error}
                </p>
              )}
            </div>
          ) : (
            /* Formulário de login */
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">E-mail</label>
                <input
                  type="email"
                  {...register("email", { required: true })}
                  className="w-full bg-gray-900 border border-gray-800 text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-600 focus:border-transparent placeholder-gray-600"
                  placeholder="admin@eternity.local"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">Senha</label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    {...register("password", { required: true })}
                    className="w-full bg-gray-900 border border-gray-800 text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-600 focus:border-transparent pr-11"
                  />
                  <button
                    type="button"
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
                    onClick={() => setShowPassword((p) => !p)}
                  >
                    {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">
                  Código MFA{" "}
                  <span className="text-gray-600">(opcional)</span>
                </label>
                <input
                  {...register("totp_code")}
                  className="w-full bg-gray-900 border border-gray-800 text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-600 focus:border-transparent placeholder-gray-600"
                  placeholder="123456"
                  maxLength={6}
                />
              </div>

              {error && (
                <p className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-xl px-3 py-2">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full bg-brand-600 hover:bg-brand-700 text-white font-semibold py-3 rounded-xl transition-colors disabled:opacity-50 mt-2 text-sm"
              >
                {isSubmitting ? "Entrando..." : "Entrar"}
              </button>
            </form>
          )}
        </div>

        <p className="text-xs text-gray-700">
          Eternity SecOps v0.1.0 · Plataforma Enterprise para MSSPs
        </p>
      </div>

      {/* ── Painel direito — features ─────────────────────────────────── */}
      <div className="hidden lg:flex flex-1 border-l border-gray-800 bg-gradient-to-br from-gray-900 via-gray-900 to-gray-950 flex-col justify-center px-12 py-12">
        <div className="max-w-xl mx-auto w-full">

          <p className="text-[11px] font-semibold text-brand-500 uppercase tracking-widest mb-2">
            Plataforma Completa
          </p>
          <h3 className="text-xl font-bold text-white mb-1">
            Tudo que sua equipe de segurança precisa
          </h3>
          <p className="text-sm text-gray-400 mb-7">
            Da operação de firewalls à governança de identidade — em linguagem
            natural, com rastreabilidade completa.
          </p>

          {/* Grid 2×4 de features */}
          <div className="grid grid-cols-2 gap-3">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="flex flex-col items-center text-center p-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.06] hover:border-white/[0.10] transition-colors"
              >
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center mb-3 ${f.color}`}
                >
                  <f.icon size={20} />
                </div>
                <p className="text-white text-[13px] font-semibold leading-tight mb-1">
                  {f.title}
                </p>
                <p className="text-gray-500 text-[11px] leading-relaxed">
                  {f.desc}
                </p>
              </div>
            ))}
          </div>

          {/* Rodapé */}
          <div className="mt-7 flex items-center gap-3">
            <div className="h-px flex-1 bg-gray-800" />
            <span className="text-[10px] text-gray-600 font-medium tracking-widest whitespace-nowrap">
              POWERED BY CLAUDE AI · ANTHROPIC
            </span>
            <div className="h-px flex-1 bg-gray-800" />
          </div>
        </div>
      </div>

    </div>
  );
}
