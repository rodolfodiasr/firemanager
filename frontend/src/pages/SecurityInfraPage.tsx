import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  securityInfraApi,
  type OpaPolicy,
  type PentestSchedule,
  type SecurityProfile,
  type VaultConfig,
} from "../api/securityInfra";
import {
  Database, Shield, ShieldCheck, ClipboardList, Plus, Trash2,
  Play, CheckCircle, XCircle,
} from "lucide-react";

type Tab = "vault" | "opa" | "profiles" | "pentest";

export function SecurityInfraPage() {
  const [tab, setTab] = useState<Tab>("vault");

  const tabs: { id: Tab; label: string; icon: React.ComponentType<{ size?: number | string }> }[] = [
    { id: "vault", label: "HashiCorp Vault", icon: Database },
    { id: "opa", label: "OPA Políticas", icon: Shield },
    { id: "profiles", label: "Perfis de Hardening", icon: ShieldCheck },
    { id: "pentest", label: "Pentest Tracker", icon: ClipboardList },
  ];

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Infraestrutura de Segurança</h1>
        <p className="text-gray-400 text-sm mt-1">Vault, OPA, hardening e rastreamento de pentests</p>
      </div>

      <div className="flex gap-2 border-b border-gray-700">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === id
                ? "border-brand-500 text-brand-400"
                : "border-transparent text-gray-400 hover:text-white"
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {tab === "vault" && <VaultTab />}
      {tab === "opa" && <OpaTab />}
      {tab === "profiles" && <ProfilesTab />}
      {tab === "pentest" && <PentestTab />}
    </div>
  );
}

// ── Vault Tab ────────────────────────────────────────────────────────────────

function VaultTab() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", vault_url: "", auth_method: "token", token: "", default_mount: "secret" });

  const { data: configs = [] } = useQuery({ queryKey: ["vault-configs"], queryFn: securityInfraApi.listVaultConfigs });

  const createMut = useMutation({
    mutationFn: () => securityInfraApi.createVaultConfig(form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["vault-configs"] }); setShowForm(false); setForm({ name: "", vault_url: "", auth_method: "token", token: "", default_mount: "secret" }); },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => securityInfraApi.deleteVaultConfig(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["vault-configs"] }),
  });

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-gray-400 text-sm">Configurações de HashiCorp Vault para gestão de secrets</p>
        <button onClick={() => setShowForm(v => !v)} className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium">
          <Plus size={14} /> Nova Configuração
        </button>
      </div>

      {showForm && (
        <div className="bg-gray-800 rounded-lg p-4 space-y-3 border border-gray-700">
          <h3 className="font-semibold text-white text-sm">Nova Configuração Vault</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Nome</label>
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Vault URL</label>
              <input value={form.vault_url} onChange={e => setForm(f => ({ ...f, vault_url: e.target.value }))} placeholder="https://vault.example.com" className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Método Auth</label>
              <select value={form.auth_method} onChange={e => setForm(f => ({ ...f, auth_method: e.target.value }))} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm">
                <option value="token">Token</option>
                <option value="approle">AppRole</option>
                <option value="kubernetes">Kubernetes</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Token</label>
              <input value={form.token} onChange={e => setForm(f => ({ ...f, token: e.target.value }))} type="password" className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowForm(false)} className="px-3 py-1.5 text-sm text-gray-400 hover:text-white">Cancelar</button>
            <button onClick={() => createMut.mutate()} disabled={!form.name || !form.vault_url} className="px-4 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded text-sm disabled:opacity-50">Salvar</button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {configs.map((c: VaultConfig) => (
          <div key={c.id} className="bg-gray-800 rounded-lg p-4 flex items-center justify-between border border-gray-700">
            <div>
              <div className="flex items-center gap-2">
                <Database size={16} className="text-brand-400" />
                <span className="font-medium text-white">{c.name}</span>
                <span className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded">{c.auth_method}</span>
                {c.last_verified_ok === true && <CheckCircle size={14} className="text-green-400" />}
                {c.last_verified_ok === false && <XCircle size={14} className="text-red-400" />}
              </div>
              <p className="text-xs text-gray-400 mt-0.5">{c.vault_url} · mount: {c.default_mount}</p>
            </div>
            <button onClick={() => deleteMut.mutate(c.id)} className="p-2 text-gray-500 hover:text-red-400 transition-colors">
              <Trash2 size={14} />
            </button>
          </div>
        ))}
        {configs.length === 0 && <p className="text-gray-500 text-sm text-center py-8">Nenhuma configuração Vault cadastrada.</p>}
      </div>
    </div>
  );
}

// ── OPA Tab ──────────────────────────────────────────────────────────────────

function OpaTab() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [evalModal, setEvalModal] = useState<OpaPolicy | null>(null);
  const [evalInput, setEvalInput] = useState('{"user": {"role": "admin"}, "action": "read", "resource": "device"}');
  const [evalResult, setEvalResult] = useState<{ allowed: boolean | null } | null>(null);
  const [form, setForm] = useState({ name: "", package_name: "eternity", rego_source: "", description: "", category: "" });

  const { data: policies = [] } = useQuery({ queryKey: ["opa-policies"], queryFn: securityInfraApi.listPolicies });

  const seedMut = useMutation({
    mutationFn: securityInfraApi.seedPolicies,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["opa-policies"] }),
  });

  const createMut = useMutation({
    mutationFn: () => securityInfraApi.createPolicy(form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["opa-policies"] }); setShowForm(false); },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => securityInfraApi.deletePolicy(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["opa-policies"] }),
  });

  const evalMut = useMutation({
    mutationFn: (policy: OpaPolicy) => {
      const input = JSON.parse(evalInput);
      return securityInfraApi.evaluatePolicy(policy.id, input);
    },
    onSuccess: (data) => setEvalResult({ allowed: data.allowed }),
  });

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-gray-400 text-sm">Políticas OPA (Rego) para autorização centralizada</p>
        <div className="flex gap-2">
          <button onClick={() => seedMut.mutate()} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-sm">Seed Políticas</button>
          <button onClick={() => setShowForm(v => !v)} className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm">
            <Plus size={14} /> Nova Política
          </button>
        </div>
      </div>

      {showForm && (
        <div className="bg-gray-800 rounded-lg p-4 space-y-3 border border-gray-700">
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Nome</label>
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Package</label>
              <input value={form.package_name} onChange={e => setForm(f => ({ ...f, package_name: e.target.value }))} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Categoria</label>
              <input value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Rego Source</label>
            <textarea value={form.rego_source} onChange={e => setForm(f => ({ ...f, rego_source: e.target.value }))} rows={6} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm font-mono" />
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowForm(false)} className="px-3 py-1.5 text-sm text-gray-400 hover:text-white">Cancelar</button>
            <button onClick={() => createMut.mutate()} disabled={!form.name || !form.rego_source} className="px-4 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded text-sm disabled:opacity-50">Salvar</button>
          </div>
        </div>
      )}

      {evalModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg p-6 w-full max-w-lg border border-gray-700 space-y-4">
            <h3 className="font-semibold text-white">Avaliar: {evalModal.name}</h3>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Input JSON</label>
              <textarea value={evalInput} onChange={e => setEvalInput(e.target.value)} rows={4} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm font-mono" />
            </div>
            {evalResult && (
              <div className={`flex items-center gap-2 p-3 rounded ${evalResult.allowed ? "bg-green-900/30 border border-green-700" : "bg-red-900/30 border border-red-700"}`}>
                {evalResult.allowed ? <CheckCircle size={16} className="text-green-400" /> : <XCircle size={16} className="text-red-400" />}
                <span className="font-medium text-white">{evalResult.allowed ? "PERMITIDO" : "NEGADO"}</span>
              </div>
            )}
            <div className="flex justify-end gap-2">
              <button onClick={() => { setEvalModal(null); setEvalResult(null); }} className="px-3 py-1.5 text-sm text-gray-400 hover:text-white">Fechar</button>
              <button onClick={() => evalMut.mutate(evalModal)} className="flex items-center gap-2 px-4 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded text-sm">
                <Play size={12} /> Avaliar
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {policies.map((p: OpaPolicy) => (
          <div key={p.id} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-white">{p.name}</span>
                  <span className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded">{p.package_name}</span>
                  {p.category && <span className="text-xs bg-blue-900/50 text-blue-300 px-2 py-0.5 rounded">{p.category}</span>}
                  <span className="text-xs text-gray-500">v{p.version}</span>
                </div>
                {p.description && <p className="text-xs text-gray-400 mt-0.5">{p.description}</p>}
              </div>
              <div className="flex gap-2">
                <button onClick={() => { setEvalModal(p); setEvalResult(null); }} className="p-2 text-gray-500 hover:text-brand-400 transition-colors" title="Avaliar">
                  <Play size={14} />
                </button>
                <button onClick={() => deleteMut.mutate(p.id)} className="p-2 text-gray-500 hover:text-red-400 transition-colors">
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          </div>
        ))}
        {policies.length === 0 && <p className="text-gray-500 text-sm text-center py-8">Nenhuma política OPA. Use "Seed Políticas" para criar as políticas padrão.</p>}
      </div>
    </div>
  );
}

// ── Profiles Tab ─────────────────────────────────────────────────────────────

function ProfilesTab() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", profile_type: "hardening", notes: "" });

  const { data: profiles = [] } = useQuery({ queryKey: ["security-profiles"], queryFn: securityInfraApi.listProfiles });

  const createMut = useMutation({
    mutationFn: () => securityInfraApi.createProfile(form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["security-profiles"] }); setShowForm(false); },
  });

  const applyMut = useMutation({
    mutationFn: (id: string) => securityInfraApi.applyProfile(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["security-profiles"] }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => securityInfraApi.deleteProfile(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["security-profiles"] }),
  });

  const statusColor: Record<string, string> = {
    draft: "bg-gray-700 text-gray-300",
    applied: "bg-green-900/50 text-green-300",
    archived: "bg-yellow-900/50 text-yellow-300",
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-gray-400 text-sm">Perfis de hardening e controles de segurança</p>
        <button onClick={() => setShowForm(v => !v)} className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm">
          <Plus size={14} /> Novo Perfil
        </button>
      </div>

      {showForm && (
        <div className="bg-gray-800 rounded-lg p-4 space-y-3 border border-gray-700">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Nome</label>
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Tipo</label>
              <select value={form.profile_type} onChange={e => setForm(f => ({ ...f, profile_type: e.target.value }))} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm">
                <option value="hardening">Hardening</option>
                <option value="compliance">Compliance</option>
                <option value="baseline">Baseline</option>
                <option value="custom">Custom</option>
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Notas</label>
            <textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} rows={2} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowForm(false)} className="px-3 py-1.5 text-sm text-gray-400 hover:text-white">Cancelar</button>
            <button onClick={() => createMut.mutate()} disabled={!form.name} className="px-4 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded text-sm disabled:opacity-50">Salvar</button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        {profiles.map((p: SecurityProfile) => (
          <div key={p.id} className="bg-gray-800 rounded-lg p-4 border border-gray-700 space-y-3">
            <div className="flex items-start justify-between">
              <div>
                <span className="font-medium text-white">{p.name}</span>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded">{p.profile_type}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${statusColor[p.status] || "bg-gray-700 text-gray-300"}`}>{p.status}</span>
                </div>
              </div>
              <button onClick={() => deleteMut.mutate(p.id)} className="p-1 text-gray-500 hover:text-red-400">
                <Trash2 size={14} />
              </button>
            </div>
            {p.notes && <p className="text-xs text-gray-400">{p.notes}</p>}
            {p.applied_at && <p className="text-xs text-gray-500">Aplicado: {new Date(p.applied_at).toLocaleString("pt-BR")}</p>}
            {p.status === "draft" && (
              <button onClick={() => applyMut.mutate(p.id)} className="w-full flex items-center justify-center gap-2 py-2 bg-green-800/50 hover:bg-green-700/50 text-green-300 rounded text-xs font-medium">
                <CheckCircle size={12} /> Aplicar Perfil
              </button>
            )}
          </div>
        ))}
      </div>
      {profiles.length === 0 && <p className="text-gray-500 text-sm text-center py-8">Nenhum perfil de hardening criado.</p>}
    </div>
  );
}

// ── Pentest Tab ───────────────────────────────────────────────────────────────

function PentestTab() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", scope: "", pentest_type: "external", vendor: "", scheduled_at: "" });

  const { data: pentests = [] } = useQuery({ queryKey: ["pentest-schedules"], queryFn: securityInfraApi.listPentests });

  const createMut = useMutation({
    mutationFn: () => securityInfraApi.createPentest({ ...form, scheduled_at: form.scheduled_at || undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["pentest-schedules"] }); setShowForm(false); },
  });

  const completeMut = useMutation({
    mutationFn: (pentest: PentestSchedule) =>
      securityInfraApi.updatePentest(pentest.id, { status: "completed", completed_at: new Date().toISOString() }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pentest-schedules"] }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => securityInfraApi.deletePentest(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pentest-schedules"] }),
  });

  const statusColor: Record<string, string> = {
    planned: "bg-blue-900/50 text-blue-300",
    in_progress: "bg-yellow-900/50 text-yellow-300",
    completed: "bg-green-900/50 text-green-300",
    cancelled: "bg-gray-700 text-gray-400",
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-gray-400 text-sm">Rastreamento de pentests externos e internos</p>
        <button onClick={() => setShowForm(v => !v)} className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm">
          <Plus size={14} /> Novo Pentest
        </button>
      </div>

      {showForm && (
        <div className="bg-gray-800 rounded-lg p-4 space-y-3 border border-gray-700">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Título</label>
              <input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Tipo</label>
              <select value={form.pentest_type} onChange={e => setForm(f => ({ ...f, pentest_type: e.target.value }))} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm">
                <option value="external">Externo</option>
                <option value="internal">Interno</option>
                <option value="web_app">Web App</option>
                <option value="red_team">Red Team</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Empresa / Vendor</label>
              <input value={form.vendor} onChange={e => setForm(f => ({ ...f, vendor: e.target.value }))} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Data Agendada</label>
              <input type="datetime-local" value={form.scheduled_at} onChange={e => setForm(f => ({ ...f, scheduled_at: e.target.value }))} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Escopo</label>
            <textarea value={form.scope} onChange={e => setForm(f => ({ ...f, scope: e.target.value }))} rows={2} placeholder="Descreva o escopo do pentest..." className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowForm(false)} className="px-3 py-1.5 text-sm text-gray-400 hover:text-white">Cancelar</button>
            <button onClick={() => createMut.mutate()} disabled={!form.title} className="px-4 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded text-sm disabled:opacity-50">Salvar</button>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {pentests.map((p: PentestSchedule) => (
          <div key={p.id} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-start justify-between">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-white">{p.title}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${statusColor[p.status] || "bg-gray-700 text-gray-300"}`}>{p.status}</span>
                  <span className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded">{p.pentest_type}</span>
                </div>
                {p.vendor && <p className="text-xs text-gray-400">Empresa: {p.vendor}</p>}
                {p.scheduled_at && <p className="text-xs text-gray-400">Agendado: {new Date(p.scheduled_at).toLocaleDateString("pt-BR")}</p>}
                {p.status === "completed" && (
                  <div className="flex items-center gap-3 mt-2">
                    <span className="text-xs text-red-400">C: {p.findings_critical}</span>
                    <span className="text-xs text-orange-400">H: {p.findings_high}</span>
                    <span className="text-xs text-yellow-400">M: {p.findings_medium}</span>
                    <span className="text-xs text-blue-400">L: {p.findings_low}</span>
                  </div>
                )}
              </div>
              <div className="flex gap-2">
                {p.status === "planned" && (
                  <button onClick={() => completeMut.mutate(p)} className="p-2 text-gray-500 hover:text-green-400 transition-colors" title="Marcar como concluído">
                    <CheckCircle size={14} />
                  </button>
                )}
                <button onClick={() => deleteMut.mutate(p.id)} className="p-2 text-gray-500 hover:text-red-400 transition-colors">
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          </div>
        ))}
        {pentests.length === 0 && <p className="text-gray-500 text-sm text-center py-8">Nenhum pentest agendado.</p>}
      </div>
    </div>
  );
}
