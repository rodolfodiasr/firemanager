# Eternity SecOps — Guia de Contexto para Claude Code

## Propósito Central

**O Eternity SecOps é a plataforma de operação de infraestrutura de segurança com IA agentic — permite que MSSPs e times de TI gerenciem, configurem, automatizem e governem firewalls, identidade e infraestrutura de rede de múltiplos vendors, em linguagem natural, com rastreabilidade completa e supervisão humana em cada ação crítica.**

**Tagline:** *"Opere sua infraestrutura de segurança em linguagem natural. Com governança."*

**Mercado primário:** MSSPs (Managed Security Service Providers) e times de TI/segurança que precisam de capacidade operacional de equipe grande sem ter equipe grande.

### O que NÃO é o Eternity SecOps

| Categoria | Decisão |
|---|---|
| **SIEM** | Integra com SIEMs (Wazuh, Log360, Splunk, Sentinel) via F37 — não coleta logs de tráfego, não é motor de correlação |
| **EDR/XDR** | Fora do escopo. Gerencia dispositivos de rede, não endpoints |
| **Scanner de vulnerabilidades** | Consome resultados (Nmap, OpenVAS, Shodan) — não produz scans |
| **FinOps Cloud** | Não gerencia custo de K8s/containers. Gerencia *segurança* de infraestrutura cloud (F38) |
| **ITSM/ServiceDesk** | Integra com Jira/ServiceNow para tickets — não é um ServiceDesk |
| **Plataforma de monitoramento** | Consome dados de Zabbix/Grafana/Prometheus — não substitui monitoramento |
| **Gerenciador de servidores** | Módulo de servidores é read-only analítico (F14) — não executa comandos de modificação |
| **DBA Tool** | Módulo de BD audita privilégios de acesso (F20) — não gerencia schemas ou dados |

---

## O que é este projeto

Eternity SecOps (anteriormente FireManager) é uma plataforma MSSP (Managed Security Service Provider) para operação centralizada de infraestrutura de segurança com IA agentic. Backend FastAPI/Python, frontend React/TypeScript, PostgreSQL + pgvector, Celery/Redis, Docker Compose.

**Stack:**
- Backend: FastAPI + SQLAlchemy async + asyncpg + Alembic
- Frontend: React 18 + TypeScript + Vite
- IA: Anthropic Claude (claude-sonnet-4-6) via SDK Python
- Workers: Celery + Redis
- DB: PostgreSQL 15 + pgvector
- Infra: Docker Compose em `infra/docker-compose.yml`

---

## Comandos essenciais

```bash
# O docker-compose.yml está em infra/ — SEMPRE usar -f
cd /home/admeternity/firemanager
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml build api
docker compose -f infra/docker-compose.yml logs -f api
docker compose -f infra/docker-compose.yml ps

# Serviços: api, celery_worker, celery_beat, postgres, redis, frontend, nginx, prometheus, grafana
# NUNCA usar: docker compose restart backend (serviço se chama "api", não "backend")

# Após qualquer restart de container de backend, reiniciar nginx:
docker compose -f infra/docker-compose.yml restart nginx
# Motivo: nginx faz cache de DNS — sem reiniciar, aponta para IP antigo e retorna 502

# Executar migrations no container
docker compose -f infra/docker-compose.yml exec api alembic upgrade head

# Executar SQL no PostgreSQL (flag -T obrigatória para pipar)
docker compose -f infra/docker-compose.yml exec -T postgres psql -U fm_user -d firemanager
# Usuário é fm_user, NÃO postgres
```

---

## Workflow de desenvolvimento (Windows → Linux VM)

**Problema crítico:** Claude Code roda no Windows (`C:\Users\rodolfo.dias\firemanager\`). O Docker roda em VM Linux (`/home/admeternity/firemanager/`). São filesystems SEPARADOS — edições no Windows NÃO chegam automaticamente ao Linux.

**Fluxo correto:**
1. Editar arquivos no Windows (Claude Code edita aqui)
2. Sincronizar para VM Linux (git push + pull, rsync, ou copiar manualmente)
3. O volume mount `../backend:/app` + hot-reload do uvicorn detecta mudanças na VM

**Verificar se mudanças chegaram ao Linux:**
```bash
grep -n "texto_do_codigo_novo" /home/admeternity/firemanager/backend/app/services/arquivo.py
```

**Para aplicar patches urgentes direto na VM sem sincronizar:**
- Usar Python one-liners com `python3 -c '...'` (sem heredoc — heredoc é corrompido pelo terminal SSH)
- Ou editar com `nano` diretamente na VM

---

## Anti-patterns críticos

### Docker
- ❌ `docker compose up` sem `-f infra/docker-compose.yml` → "no configuration file provided"
- ❌ `docker compose restart backend` → serviço se chama `api`
- ❌ Restart de `api` sem reiniciar `nginx` → 502 silencioso por DNS cache
- ❌ `docker compose exec postgres psql -U postgres` → usuário é `fm_user`
- ❌ Pipar SQL sem flag `-T`: `exec -T postgres psql ...`

### Python/Backend
- ❌ Esquecer `await db.refresh(objeto)` após `await db.flush()` → `MissingGreenlet` em campos `onupdate=func.now()`
- ❌ `creds.get("vdom", "root")` quando o valor pode ser `null` no JSON → usar `creds.get("vdom") or "root"`
- ❌ `payload.update(spec.extra)` direto → `spec.extra` pode ter campos inválidos para o vendor

### Segurança
- ❌ Gerar hash bcrypt em variável de shell e interpolar em SQL → `$` do hash é interpretado pelo bash
- ✅ Correto: gerar SQL completo via Python dentro do container, salvar em `/tmp/update.sql`, executar via pipe

### IA / Claude API
- ❌ Modelo `claude-sonnet-4-20250514` não existe → usar `claude-sonnet-4-6`
- Verificar API key: `docker exec api env | grep ANTHROPIC`

---

## Modelo de dados — Multi-tenant

- `is_super_admin: bool` no User → acesso cross-tenant (suporte MSSP)
- Super admin **não tem** `tenant_id` no JWT — queries devem ter branch explícita para super admin
- `TenantRole`: `admin`, `analyst`, `readonly`
- Herança de variáveis: Tenant → Device (device sobrescreve tenant)

---

## Roadmap Completo

### Fases Implementadas

| Fase | Descrição | Entregáveis principais | Status |
|---|---|---|---|
| 1 | Scaffold MVP | Devices, operações CRUD, agente IA (Claude), auth JWT | ✅ |
| 2 | Multi-tenant / MSSP | Tenants, roles (admin/analyst/readonly), super admin cross-tenant | ✅ |
| 3 | Integrações externas | Nmap, Shodan, Wazuh, OpenVAS | ✅ |
| 4 | Dashboard Super Admin | Painel cross-tenant, health status global | ✅ |
| 5 | Convites e self-service | Convite por email, accept invite, gestão de usuários por tenant | ✅ |
| 6 | Novos vendors firewall | pfSense, OPNsense, MikroTik, Endian | ✅ |
| 7 | Bulk Jobs | Operações em lote em múltiplos devices | ✅ |
| 8 | Inspetor ao vivo | Snapshot de device em tempo real (regras, NAT, rotas, interfaces) | ✅ |
| 9 | Bulk jobs por categoria | Roles de categoria, filtro de devices por grupo/função | ✅ |
| 10 | Grupos de dispositivos | Device groups, operações em grupo | ✅ |
| 11 | Dell N-Series (DNOS6) | Suporte CLI Dell N-Series via Netmiko | ✅ |
| 12 | HP V1910 (Comware) | Suporte CLI HP Comware via Netmiko | ✅ |
| 13 | Variáveis de template | Herança tenant → device, substituição em templates CLI | ✅ |
| 14 | Analista de Servidores | SSH Linux, WinRM Windows, Zabbix v6/v7, Wazuh — módulo analítico N3 | ✅ |
| 15 | Migração de Switches | Juniper EX, Aruba, Intelbras; BookStack; Zabbix dual-version; snapshot scheduling | ✅ |
| 16 | Migração de Regras | Parser + renderer Fortinet/SonicWall/Sophos; IR normalizado; Celery worker | ✅ |
| 17 | Golden Config | Templates com variáveis tipadas, biblioteca por vendor, divergência device×template | ✅ |
| 18 | Conectividade de Rede | Routing tables SSH, BGP/OSPF/SD-WAN, anomalias, cruzamento Nmap, mapa topologia, IA | ✅ |
| 19 | Base de Conhecimento IA | RAG: upload PDF/DOCX/MD, pgvector, embeddings, injeção automática no agente | ✅ |
| 20 | Conectores de Banco | PostgreSQL, MySQL/MariaDB, SQL Server, Oracle; auditoria usuários/privilégios; IA | ✅ |
| 21 | Ciclo de Vida — Offboarding | Azure AD, Google Workspace, AD Local (LDAP); offboard SSH/WinRM/DB; órfãs; webhook RH | ✅ |
| 22 | Ciclo de Vida — Onboarding | Perfis de cargo; grupos AD (GLPI/Docs/SysPass automáticos); Guacamole; Tactical RMM; Unifi | ✅ |
| 23 | Alertas & Integrações | Slack, Teams, Email SMTP, Webhook, Jira; regras por gatilho e severidade; histórico | ✅ |
| 24 | Dashboard Executivo | Score de risco 0–100, métricas agregadas, relatório PDF executivo (WeasyPrint) | ✅ |
| 25 | Plataforma Enterprise | API Keys, White-label branding, Cisco ASA + Palo Alto + Check Point connectors | ✅ |
| 26 | Golden Config Bundles REST | GoldenBundle + BundleSection + BundleApply; BundleRenderer; FortinetRestApply; Celery worker | ✅ |
| 27 | VM Migration Planner | VMware vCenter + Proxmox read-only; inventory sync; runbook IA (Claude) | ✅ |
| 28 | Segurança Avançada e Resiliência | Denylist catastróficos, pre-snapshot, preview CLI, read_only_agent, JWT 15 min, audit hash-chain, SSRF guard; suite 70 testes (JWT/guardrails/RBAC/tenant isolation/multi-sig) | ✅ |
| 43 | Integração GLPI com IA | `glpi_integrations` + `glpi_ticket_analyses`; GlpiClient 11.0.4; Celery worker análise Claude (diagnóstico/ações/causa_raiz); enriquecimento Zabbix/Wazuh/device logs; correlação automática com devices; bridge AI Assistant via `open-session` | ✅ |
| 44 | Firmware Intelligence e CVEs | `device_firmware_versions` (histórico); `firmware_cves` (NVD: CVSS v2/v3, CPE); `device_firmware_vulnerabilities` (device×CVE, status open/accepted/patched); `firmware_service` + `nvd_service` | ✅ |
| 45 | Clarification Loop | `clarification_questions` + `clarification_answers` (JSONB) + `confidence_score` (FLOAT) em operations; agente pede esclarecimento quando confiança < threshold antes de executar | ✅ |
| 46 | Auth Avançada — Refresh Tokens, MFA e Support Mode | Refresh token JWT 7 dias; pre-token 5 min (multi-tenant flow); MFA/TOTP via pyotp (`/mfa/setup`, `/mfa/verify`); `POST /auth/assume-tenant` (super admin entra no tenant); `SupportBanner` + `TenantSwitcher`; testes de fronteiras JWT (`test_auth_boundaries`) com gaps documentados via `pytest.xfail` | ✅ |
| 40-B | AI Assistant Panel — Chat IA | `assistant_sessions` + `assistant_messages`; RAG com Claude/GPT-4o; hash-chain de mensagens; `AssistantPanel` (widget lateral) + `AssistantPage` (página dedicada); seletor de modelo; indicadores RAG | ✅ |
| 41 | Organização do Assistant — Pastas, Pin e Compartilhamento | `assistant_folders` (cor, is_team); `folder_id`, `is_shared`, `pinned` em sessões; rename/move/share/pin; `GET /sessions/team`; sidebar colapsável com seções Pinned/Equipe/Pessoal | ✅ |
| 42 | Visibilidade de Pastas por Role | `min_role` em `assistant_folders`; pastas de equipe visíveis apenas para roles >= min_role | ✅ |
| 40-A | Motor de Conhecimento IA | `assistant_doc_drafts` (action_plan/remediation/knowledge); DocSanitizer; pgvector similarity vs BookStack; workflow draft→approved→published; chat mode Infra/Geral (VoIP/PABX/softphones); dropdowns inline | ✅ |
| 29 | IA Operacional: Observabilidade e Multi-agente | `ai_interactions` + `ai_token_usage` + `orchestration_runs`; orquestrador multi-agente (5 sub-agentes); `llm_provider.py` (Anthropic/OpenAI/Fallback); dry-run `POST /operations/{id}/dry-run`; circuit breaker Redis por device (`app/utils/circuit_breaker.py`); rotação Fernet `POST /admin/fernet/rotate`; SAST CI/CD `.github/workflows/security.yml`; rate limiting por API key plan (starter/pro/enterprise) com `X-RateLimit-*` headers | ✅ |
| 35 | SOAR & Threat Intelligence | `playbook_rules` + `playbook_executions` + `threat_indicators`; 5 templates AD pré-prontos; actions: notify_slack/email, escalate_to_n2, create_ticket_jira, ad_disable_user, revoke_jit_access, run_snapshot; Celery beat; MTTR; `/playbooks/stats/mttr` | ✅ |
| 35.cont | SOAR Builder Visual | `builder_state` JSONB em `playbook_rules` (migration 0060); `GET/PUT /playbooks/{id}/builder`; `PlaybooksPage.tsx` com canvas SVG drag-and-drop, paleta de nós, painel de propriedades; `PlaybookBuilder` salva estado no backend | ✅ |
| 36 | Governança de Identidade AD/M365 | `identity_connectors` (ad_ldap/azure_ad/google_workspace, config Fernet); `ad_users` + `ad_groups` + `ad_group_memberships`; `sod_rules` (5 built-in) + `sod_violations`; `access_campaigns` + `access_review_tasks`; `jit_requests` (aprovação obrigatória, Celery expiry a cada minuto); AD Tool Kit ldap3 + Microsoft Graph; 15+ endpoints REST | ✅ |
| 36.cont | Governança de Identidade Avançada | `identity_posture_snapshots` + `excessive_access_alerts` + `group_health_reports` + `role_profiles` (migration 0059); `identity_analytics_service.py` (posture score 0–100, role mining, privilege creep, group health); 8 novos endpoints em `/identity-governance/posture/*` | ✅ |
| 37 | Integrador de SIEM | `siem_connectors` + `siem_alerts` (migration 0057); normalização Wazuh/Splunk/Sentinel/Log360/QRadar; webhook público `/webhooks/siem/{secret}`; trigger SOAR via `evaluate_trigger`; `SiemPage.tsx` com CRUD de conectores e feed de alertas | ✅ |
| 38 | Cloud Security Posture (CSPM) | `cloud_accounts` + `cloud_security_findings` + `cloud_resources` (migration 0058); `cspm_service.py` (checks por provider, sync, upsert findings); API CRUD contas + findings; `CloudPosture.tsx` com grid de contas e tabela de findings | ✅ |
| 39 | Identidade Self-Service | `otp_requests` (SHA-256, TTL 10 min); `POST /self-service/otp/request`, `/password/reset`, `/account/unlock`; reset/unlock via ldap3 (AD) e Graph (Azure AD); Celery beat `expiry_reminders` (lembretes 14d/7d/1d antes da expiração) | ✅ (parcial — pendente: portal web separado, catálogo de acesso visual, relatórios AD pré-prontos) |
| 34 | Infraestrutura de Segurança Avançada | `vault_configs` + `vault_secret_refs` + `opa_policies` + `opa_evaluations` + `security_profiles` + `pentest_schedules` (migration 0064); `security_infra_service.py` (seed 3 políticas Rego built-in, `_evaluate_rego_simple`); API `/security-infra/*`; `SecurityInfraPage.tsx` (tabs: HashiCorp Vault, OPA Políticas, Perfis de Hardening, Pentest Tracker) | ✅ (parcial — CRUD config store; mTLS, microsegmentação Docker e container hardening real pendentes) |
| 31 | Edge Agents, SSO/OIDC, Marketplace, RBAC Granular | `edge_agents` (token SHA-256) + `sso_configs` + `marketplace_plugins` + `tenant_plugins` + `rbac_custom_roles` + `rbac_role_assignments` (migration 0065); `edge_agent_service.py` (5 plugins builtin, `generate_agent_token`); API `/platform/*`; `EdgeAgentsPage.tsx` (tabs: Edge Agents, SSO/OIDC, Marketplace, RBAC Granular) | ✅ (parcial — CRUD + registro de agentes; WebSocket on-premise, fluxo OIDC real e CGNAT pendentes) |
| 32 | Produto: Billing, Onboarding, Help Center, Preferências | `billing_plans` + `billing_subscriptions` + `billing_invoices` + `onboarding_checklists` + `help_articles` + `user_preferences` (migration 0066); `product_service.py` (3 planos seed, 4 artigos, checklist 4 etapas); API `/product/*`; `ProductPage.tsx` (tabs: Billing & Planos, Onboarding, Central de Ajuda, Preferências) | ✅ (parcial — CRUD completo; integração Stripe, i18n real e WCAG AA pendentes) |
| 28.1 | DLP — Prevenção de Perda de Dados no Chat | `dlp_configs` + `dlp_rules` + `dlp_incidents` (migration 0067); `dlp_service.py` (20 regras builtin: 6 pii_br CPF/CNPJ/PIS/TítuloEleitor/DadosBancários/PIX, 8 credentials SSH/JWT/AWS/conn-string/HTTP-Basic/API-token, 6 infra_mssp SNMP/VPN-PSK/TACACS+/LDAP/Enable/BGP); hook em `operations.py` + `assistant.py`; UI em `Organisation.tsx` (aba DLP: config por tenant, gestão de regras por categoria, regex custom, tabela de incidentes); `validate-docbr` para CPF/CNPJ com dígito verificador | ✅ |
| 47 | Chat IA — Guia da Plataforma (super admin) | Novo modo `"platform"` no AI Assistant; `_PLATFORM_GUIDE_TEMPLATE` com mapa completo de todos os 20+ módulos (caminho de navegação, funcionalidades, fluxos); guard 403 no `POST /assistant/chat` para não super admin; opção "Guia" visível no seletor de modo apenas para `is_super_admin`; ícone `BookOpen`; empty state e placeholder específicos | ✅ |

### Próximas Fases (resumo)

| Fase | Descrição | Entregáveis pendentes |
|---|---|---|
| 30 | Compliance Enterprise e BC/DR | Compliance packs (CIS/PCI/BACEN/LGPD + vertical Identidade), DPA/LGPD, RTO/RPO, SLA formal, relatório executivo |
| 31.cont | Edge Agent — WebSocket on-premise + OIDC real | Edge agent WebSocket sainte para ambientes CGNAT; fluxo PKCE OIDC completo (Azure AD/Okta/Google); provisionamento JIT de usuários via SSO |
| 32.cont | Produto — Stripe + i18n + Acessibilidade | Integração Stripe (checkout, webhooks `invoice.paid`/`payment_failed`); `react-i18next` (pt-BR/en-US); auditoria WCAG 2.1 AA com axe-core |
| 33 | IA Safety & Governança | Aprovação dupla, janelas de manutenção, SIRP, red team trimestral, four-eyes AD, direito ao esquecimento, RFC 3161 |
| 34.cont | Infra Segurança — mTLS + Microsegmentação | mTLS interno entre serviços (step-ca), redes Docker isoladas (frontend_net/backend_net/worker_net), AppArmor/Seccomp profiles, Vault HA real |
| 39.cont | Identidade Self-Service — Portal e Relatórios | Portal web separado (URL dedicada via white-label), catálogo de acesso visual com AccessReviewTask, relatórios AD pré-prontos (senha expirada, contas inativas, membros de grupo, admins sem MFA) |

---

### Próximas Fases (detalhe)

---

### Fase 28 — Segurança Avançada e Resiliência
*Hardening de autenticação, proteção de infraestrutura, tolerância a falhas e segurança do agente IA*

**Origem:** Mesa Redonda Segurança da Informação (20 profissionais) — Rafael (CISO), Ana (Red Team/AI), Eduardo (AI/ML), Thiago (Network), Vanessa (AppSec), Marcos (IR), Paulo (OT), Fernanda (Zero Trust), Sandra (Architecture), André (Bug Bounty)

| Funcionalidade | Detalhe | Prioridade | Status |
|---|---|---|---|
| **Preview CLI exato antes de executar** | Campo `preview_commands` no chat response — frontend exibe os comandos exatos antes do Executar; técnico aprova o comando, não a intenção | **Crítica** | ✅ |
| **Snapshot obrigatório antes de toda escrita** | `_take_pre_snapshot()` em `execute_operation` — toda escrita captura config antes de executar; rollback sempre disponível | **Crítica** | ✅ |
| **Denylist de comandos catastróficos por vendor** | ~20 regras em `guardrails.py`: Fortinet (`factoryreset`, `formatlogdisk`, `restore`), Sophos, pfSense (`pfctl -F all`), genérico (`wipe`, `delete all`); intent `unknown` bloqueado; mensagem com botão CLI Direto | **Crítica** | ✅ |
| **AI output schema validation** | `ActionPlan.model_validate()` rejeita output fora do schema antes de executar | Alta | ✅ |
| **Prompt injection detection** | Regex em `check_action_plan` e `check_ssh_commands`; bloqueia em user input, plano gerado e comandos SSH | Alta | ✅ |
| **JWT short-lived 15 min** | `access_token_expire_minutes = 15` em `config.py` | Alta | ✅ |
| **SSRF protection** | `app/utils/ssrf_guard.py` — bloqueia RFC1918, 169.254.x, loopback, IPv6 link-local; valida scheme http/https | Alta | ✅ |
| **Hash-chained audit log** | `app/services/audit_log_service.py` — `write_audit()` e `verify_chain()`; SHA-256(prev_hash + campos); wired em execute_operation | Alta | ✅ |
| **Modo read-only forçado por device** | Campo `read_only_agent: bool` no Device (migração 0042); bloqueia toda escrita via agente antes de abrir conexão | Alta | ✅ |
| **Token de convite único + expiração 24h** | Single-use enforced via `used_at`; TTL reduzido de 48h → 24h | Alta | ✅ |
| BOLA/IDOR checks | `_get_tenant_operation()` valida tenant em toda operação; `get_device(..., tenant_id)` em todos os endpoints | Alta | ✅ (existente) |
| Circuit breaker nos connectors | Padrão circuit breaker (tenacity) — vendor lento não bloqueia workers Celery | Alta | ⏳ F29 |
| CI/CD com SAST + secret scanning | GitHub Actions: Bandit, pip-audit, Trivy, semgrep, truffleHog; bloquear merge em findings críticos | Alta | ⏳ F29 |
| Supply chain security | Pinagem de dependências com hash; Dependabot/Renovate; versionamento de parsers por firmware | Média | ⏳ F29 |
| Rate limiting por API key | Limites configuráveis por tenant e rota; headers `X-RateLimit-*` | Média | ⏳ F29 |
| **Canal público de reporte de vuln** | E-mail `security@` com PGP key; SLA: crítico 24h, alto 7d, médio 30d | Média | ⏳ F33 |
| **Suite de testes de segurança** | `tests/security/`: test_auth_boundaries (16), test_guardrails_advanced (25), test_role_enforcement (8), test_tenant_isolation (9); `tests/integration/test_multisig` (12) — 70 testes no total; cobertura: JWT expirado/adulterado, bypass de guardrails com Unicode/encoding, RBAC ops, isolamento multi-tenant, multi-sig approval | Alta | ✅ |
| **DLP — Prevenção de Perda de Dados no Chat** | `dlp_configs` + `dlp_rules` (20 builtin: 6 pii_br, 8 credentials, 6 infra_mssp) + `dlp_incidents`; `dlp_service.scan_message()` integrado a `operations.py` (chat_with_agent, continue_chat) e `assistant.py`; mascara com `[DLP:RULE:hash8]`, bloqueia se `has_blocks`; UI em aba DLP de `Organisation.tsx`; `validate-docbr` para CPF/CNPJ | Alta | ✅ |

---

### Fase 34 — Infraestrutura de Segurança Avançada ✅ (parcial)
*Config store para Vault/OPA/hardening — CRUD completo; integração real com Vault HA e mTLS pendentes*

**Implementado (migration 0064):**

| Componente | Detalhe |
|---|---|
| `vault_configs` | Config HashiCorp Vault por tenant: vault_url, auth_method (token/approle), role_id, secret_id_encrypted, default_mount, namespace, last_verified_ok |
| `vault_secret_refs` | Referências a secrets no Vault: alias, vault_path, vault_key, category (per tenant; FK → vault_configs) |
| `opa_policies` | Políticas Rego por tenant: name, package_name, rego_source, version, is_active; 3 políticas built-in: `allow_read_devices`, `require_admin_for_write`, `block_critical_ops_without_approval` |
| `opa_evaluations` | Log de avaliações de política: input_data, result, allowed — `_evaluate_rego_simple()` é simulação local em Python (sem sidecar OPA real) |
| `security_profiles` | Perfis de hardening por tenant: profile_type (hardening/baseline/cis/pci), controls JSONB, status (draft/applied), applied_at |
| `pentest_schedules` | Tracker de pentests: title, scope, pentest_type (external/internal/red_team), vendor, scheduled_at, completed_at, findings C/H/M/L, report_url |
| API `/security-infra/*` | CRUD vault-configs, vault-configs/{id}/secrets, opa-policies (+ /seed + /{id}/evaluate), security-profiles (+ /{id}/apply), pentest-schedules |
| `SecurityInfraPage.tsx` | 4 tabs: HashiCorp Vault (form + list com badge last_verified_ok), OPA Políticas (seed + create + evaluate modal JSON), Perfis de Hardening (grid cards + Apply), Pentest Tracker (create + update findings C/H/M/L) |

**Pendente (F34.cont):** mTLS real entre serviços (step-ca), redes Docker isoladas (frontend_net/backend_net/worker_net), AppArmor/Seccomp profiles, Vault HA em 3 nodes, sidecar OPA real.

---

### Fase 31 — Edge Agents, SSO/OIDC, Marketplace e RBAC Granular ✅ (parcial)
*Registro de agentes e config store para SSO/RBAC — WebSocket on-premise e fluxo OIDC real pendentes*

**Implementado (migration 0065):**

| Componente | Detalhe |
|---|---|
| `edge_agents` | Agentes por tenant: name, token_hash (SHA-256 de `secrets.token_urlsafe(32)`), status (online/offline/stale), version, last_seen, ip_address, device_ids JSONB; token raw exibido UMA vez no registro |
| `sso_configs` | Config SSO por tenant (unique): provider (azure_ad/okta/google/custom_oidc), client_id, client_secret_encrypted, discovery_url, group_claim, group_mapping JSONB, sso_required |
| `marketplace_plugins` | Plugins globais: name, slug, version, category (connector/report/workflow/alert_rule), is_builtin, download_count, approved_at; 5 built-in: fortinet-fortigate, sonicwall-sonicos, wazuh-siem, lgpd-compliance, executive-risk-dashboard |
| `tenant_plugins` | Plugins instalados por tenant (UniqueConstraint tenant+plugin): installed_at, installed_by |
| `rbac_custom_roles` | Roles customizadas por tenant (UniqueConstraint tenant+name): name, description, permissions JSONB |
| `rbac_role_assignments` | Assignments: user_id × role_id por tenant, assigned_by |
| API `/platform/*` | CRUD /agents, PUT /sso (upsert), /marketplace (+ /seed + /installed + /{id}/install + /{id}/uninstall), /rbac-roles, /rbac-assignments |
| `EdgeAgentsPage.tsx` | 4 tabs: Edge Agents (token reveal one-time, online/offline badge), SSO/OIDC (upsert form Azure AD/Okta/Google/custom), Marketplace (install/uninstall com set tracking), RBAC Granular (custom roles CRUD) |

**Pendente (F31.cont):** Edge agent Python/Docker real com WebSocket sainte, suporte CGNAT com reconexão exponencial, fluxo PKCE OIDC completo, provisionamento JIT de usuários via SSO.

---

### Fase 32 — Produto: Billing, Onboarding, Help Center e Preferências ✅ (parcial)
*CRUD completo de billing e experiência do produto — integração Stripe e i18n real pendentes*

**Implementado (migration 0066):**

| Componente | Detalhe |
|---|---|
| `billing_plans` | Planos globais: name, slug, monthly_price_brl (Decimal), max_devices, max_users, ai_token_quota, sla_target_pct, features JSONB, is_active; 3 planos seed: Starter (R$490, 10 devices), Pro (R$1490, 50 devices), Enterprise (R$3490, unlimited) |
| `billing_subscriptions` | Assinatura por tenant (unique): plan_id, status (active/trialing/canceled/past_due), cancel_at_period_end, current_period_start/end, trial_end |
| `billing_invoices` | Faturas por tenant: amount_brl, status (draft/open/paid/void), period_start/end, paid_at, due_date, invoice_pdf_url |
| `onboarding_checklists` | Checklist por tenant+user (UniqueConstraint): step_add_device, step_run_snapshot, step_ask_agent, step_configure_alert (bools), completed, skipped, completed_at |
| `help_articles` | Artigos de ajuda globais: title, slug (unique), category, persona, content_md, is_published, view_count (incrementado no GET), sort_order; 4 artigos built-in |
| `user_preferences` | Prefs por user (unique): language (pt-BR/en-US/es-LA), timezone, theme (dark/light/system), notifications_enabled, onboarding_step, onboarding_completed |
| API `/product/*` | /billing/plans (+ /seed), /billing/subscription (+ /start), /billing/invoices, /onboarding/checklist (+ /complete-step + /skip), /help/articles (+ /seed + /{slug} com view_count++), /preferences |
| `ProductPage.tsx` | 4 tabs: Billing & Planos (subscription card + plan comparison grid + invoices list), Onboarding (4-step checklist com progress bar + skip), Central de Ajuda (listing com category filter + article detail), Preferências (language/timezone/theme dropdowns com save imediato) |

**Pendente (F32.cont):** Integração Stripe (`stripe.Customer`, `stripe.Subscription`, webhooks invoice.paid/payment_failed), `react-i18next` pt-BR/en-US, auditoria WCAG 2.1 AA com axe-core, geração de PDF de fatura (WeasyPrint).

---

### Fase 28.1 — DLP: Prevenção de Perda de Dados no Chat ✅
*Interceptação de PII e dados sensíveis antes do envio ao LLM — proteção em profundidade do chat do assistente IA e do agente de firewall*

**Implementado (migration 0067):**

| Componente | Detalhe |
|---|---|
| `dlp_configs` | Config global DLP por tenant (unique): enabled, compliance_mode (bloqueia desativação por não-superadmin quando ativo), incident_threshold_count/hours |
| `dlp_rules` | Regras por tenant (UniqueConstraint tenant+rule_key): builtin + custom; categorias: `pii_br`, `credentials`, `infra_mssp`, `custom`; action: block/warn; pattern (regex) |
| `dlp_incidents` | Log de incidentes SEM o dado original: pii_type, action_taken, source (chat/api), ip_address; indexes em tenant_id e created_at |
| `app/models/dlp.py` | ORM: `DLPConfig`, `DLPRule`, `DLPIncident` — SQLAlchemy 2.0 `Mapped[]` |
| `app/services/dlp_service.py` | 20 regras builtin compiladas no import; `scan_text()` com validate_docbr (CPF/CNPJ dígitos verificadores); mascaramento com token `[DLP:RULE_KEY:sha256[:8]]`; `scan_message()` = pipeline completo (load config → load/seed rules → scan → log incidents) |
| **20 regras builtin** | pii_br (6): CPF, CNPJ, PIS/PASEP, Título Eleitor, Dados Bancários, Chave PIX — credentials (8): Senha plain, SSH Private Key, PEM cert, AWS Access Key, JWT Token, Connection String (postgresql/mysql/mongo…), HTTP Basic Auth, API Token genérico — infra_mssp (6): SNMP Community, VPN PSK, TACACS+/RADIUS Key, LDAP Bind Password, Enable Secret (Cisco), BGP MD5 Password |
| `app/api/dlp.py` | GET/PUT `/dlp/config` (compliance_mode protege desativação), GET `/dlp/rules` (seed automático na 1ª chamada), PUT `/dlp/rules/{id}` (toggle action/enabled), POST `/dlp/rules` (custom com validação regex), DELETE `/dlp/rules/{id}` (só custom — builtin retorna 403), GET `/dlp/incidents` (limit 200) |
| Integração `operations.py` | `scan_message()` nos hooks `chat_with_agent` e `continue_chat` — agente de firewall também protegido |
| Integração `assistant.py` | `scan_message()` antes do envio ao Claude; se `has_blocks` → HTTP 400 com `type: dlp_block` + lista de findings; senão → envia `masked_text` ao LLM (warns não bloqueiam) |
| `frontend/src/api/dlp.ts` | Interfaces `DLPConfig`, `DLPRule`, `DLPIncident`; `dlpApi` com todos os endpoints; suporte a `tenantId` para super admin |
| `Organisation.tsx` — aba DLP | Config por tenant (enable/disable, compliance mode, thresholds); gestão de regras agrupadas por categoria (pii_br / credentials / infra_mssp / custom) com toggle builtin + formulário regex custom; tabela de incidentes com pii_type, action, source, ip_address |
| `validate-docbr>=1.10.0` | Adicionado ao `requirements.txt` — validação de dígitos verificadores de CPF/CNPJ para reduzir falsos positivos |

---

### Fase 43 — Integração GLPI com Análise de Chamados IA
*Análise automática de chamados GLPI com Claude AI, enriquecimento de dados e bridge com o AI Assistant*

**Tabelas:**
- `glpi_integrations` — configuração por tenant: URL, app_token, username, encrypted_password, filtros por prioridade/tipo/categoria, `poll_interval_minutes`, `lookback_hours`, `auto_analysis_enabled`, `enrich_zabbix`, `enrich_wazuh`, `enrich_device_logs`, `auto_correlate_devices`, `unmatched_to_manual_queue`, `force_analysis_on_security`, `force_analysis_on_recurrent`
- `glpi_ticket_analyses` — resultado de análise por chamado: `glpi_ticket_id`, `glpi_itemtype` (Ticket/Problem/Change), `glpi_ticket_title`, `glpi_ticket_content`, status (`pending`/`pending_manual`/`analyzing`/`completed`/`failed`), `diagnostico`, `acoes_imediatas`, `plano_remediacao`, `causa_raiz`, `prevencao`, `confianca` (0–1), `is_security_incident`, `is_recurrent`, `recurrence_count`, `related_ticket_ids`, `glpi_followup_id`

**Celery worker `glpi_sync.py`:**
1. Para cada `GlpiIntegration` ativa: busca chamados abertos via `GlpiClient` (status: new/assigned/planned/pending; filtro por prioridade >= `min_priority`)
2. Skip de tickets já analisados (unique constraint `tenant_id + glpi_ticket_id`)
3. Detecção de recorrência: busca chamados similares fechados (threshold: >= 2)
4. Correlação automática com devices: extrai IPs/hostnames do título+conteúdo; cruza com devices gerenciados
5. Enriquecimento (opcional): coleta logs Zabbix, alertas Wazuh, logs SSH do device correlacionado
6. Análise Claude: JSON estruturado com diagnostico, acoes_imediatas, plano_remediacao, causa_raiz, prevencao, confianca, is_security_incident
7. Post do resultado como nota de acompanhamento no GLPI (`glpi_followup_id`)
8. Persistência em `glpi_ticket_analyses`

**GlpiClient (`glpi_service.py`):** async context-manager para GLPI 11.0.4 REST API; auth com `initSession`; strip de HTML nos conteúdos de ticket; paginação automática.

**Bridge GLPI → AI Assistant (migration 0051):**
Colunas adicionadas em `assistant_sessions`: `glpi_ticket_id`, `glpi_integration_id`, `glpi_itemtype`, `glpi_ticket_title`.
Endpoint `POST /glpi/analyses/{id}/open-session` — cria ou reutiliza sessão do assistant pré-contextualizada com o chamado. Permite que o analista continue a investigação do chamado em linguagem natural dentro do Assistant.

**Endpoints REST:**
- `GET /glpi/integrations` — retorna config GLPI do tenant
- `POST /glpi/integrations` — cria config (uma por tenant)
- `PATCH /glpi/integrations/{id}` — atualiza config
- `DELETE /glpi/integrations/{id}` — remove config
- `POST /glpi/integrations/{id}/test` — testa conexão com GLPI
- `POST /glpi/integrations/{id}/run-analysis` — dispara análise manual
- `GET /glpi/analyses` — lista análises (com filtros de status, tipo)
- `GET /glpi/analyses/{id}` — detalhe de uma análise
- `POST /glpi/analyses/{id}/open-session` — abre sessão Assistant vinculada ao ticket

---

### Fase 44 — Firmware Intelligence e CVEs
*Rastreamento automático de versões de firmware e correlação com CVEs do NVD*

**Tabelas:**
- `device_firmware_versions` — histórico de versões lidas de cada device: `device_id`, `version`, `vendor_label`, `model`, `build`, `read_at`, `read_method` (rest/ssh), `raw_output`
- `firmware_cves` — banco de CVEs sincronizado do NVD: `cve_id` (único), `vendor`, `product`, `affected_versions` (JSONB), `cvss_v3`, `cvss_v2`, `severity`, `description`, `published_at`, `modified_at`, `cpe_uri`, `nvd_url`
- `device_firmware_vulnerabilities` — vínculo device × CVE detectada: `device_id`, `cve_id`, `device_version`, `detected_at`, status (`open`/`accepted`/`patched`), `accepted_by`, `accepted_reason`, `patched_at`; unique constraint `(device_id, cve_id)`

**Services:** `firmware_service.py` — lê versão de firmware de cada device via REST/SSH e persiste em `device_firmware_versions`; cruza com `firmware_cves` para gerar `device_firmware_vulnerabilities`. `nvd_service.py` — sincroniza CVEs do NVD por vendor/product; mapeia CPE para vendors do Eternity SecOps.

---

### Fase 45 — Clarification Loop (Confidence Score + Perguntas de Clarificação)
*O agente pede esclarecimentos quando não tem confiança suficiente para executar*

**Colunas adicionadas em `operations`:** `clarification_questions` (JSONB), `clarification_answers` (JSONB), `confidence_score` (FLOAT).

Quando `confidence_score < threshold` (configurável por tenant), o agente retorna `clarification_questions` ao invés de executar diretamente. O analista responde via `clarification_answers` e a operação é reprocessada com o contexto adicional. Operação fica em status `awaiting_clarification` até resposta.

---

### Fase 46 — Auth Avançada: Refresh Tokens, MFA e Support Mode
*Ciclo de vida completo de tokens JWT, autenticação de segundo fator e modo de suporte para super admin*

#### Refresh Token — 7 dias
`_create_refresh_token(user_id)` — JWT com claim `type: "refresh"` e expiração `refresh_token_expire_days = 7`. Emitido em todos os fluxos: `POST /login`, `POST /select-tenant`, `POST /assume-tenant`. Frontend armazena em `localStorage("refresh_token")`. **Gap documentado:** endpoint `POST /auth/refresh` (troca refresh → novo access token) ainda não existe — registrado em `test_auth_boundaries.py` via `pytest.xfail`.

#### Pre-token para seleção de tenant (multi-tenant flow)
Quando usuário pertence a múltiplos tenants, `POST /login` retorna `pre_token` (tipo `pre_tenant`, TTL 5 min) + lista de tenants. Frontend entra em estado `pendingTenants`. `POST /auth/select-tenant` consome `pre_token + tenant_id` → emite access token + refresh token. Testado: pre_token não pode ser usado como access token, não é revogado após primeiro uso (gap documentado com `xfail`).

#### MFA / TOTP (pyotp)
Campos no `User`: `mfa_secret`, `mfa_enabled`. Fluxo: `POST /mfa/setup` → gera secret + QR URI (compatível Google/Microsoft Authenticator) → `POST /mfa/verify` → valida `totp_code` com `valid_window=1` (±30s) → `mfa_enabled = True`. Login com MFA: `totp_code` opcional no `LoginRequest`; se ativo e ausente/inválido → HTTP 401. Frontend: campo "Código MFA" na página de Login; badge "MFA ativo" em Settings.

#### Support Mode — Super Admin entrando em tenant
`POST /auth/assume-tenant` (requer `is_super_admin`) — retorna access token escopado ao tenant sem precisar das credenciais do cliente. `TenantSwitcher` no header para trocar de tenant. `SupportBanner` — barra amarela indicando modo ativo com botão de sair. `_savedToken` no authStore restaura o token do super admin ao sair.

#### Testes de fronteiras JWT (16 testes — `test_auth_boundaries.py`)
Cobertura: token ausente, Bearer vazio, token lixo, expirado, chave errada, payload adulterado, algoritmo `none`, sem `tenant_id`, refresh token como access token, pre_token como access token, usuário inativo, senha errada. Gaps com `xfail`: brute force em `/login`, enumeração de email em `/register`, pre_token não revogado.

| Arquivo | Conteúdo |
|---|---|
| `backend/app/api/auth.py` | `_create_refresh_token`, `_create_pre_token`, `/mfa/setup`, `/mfa/verify`, `/assume-tenant`, `/select-tenant` |
| `backend/app/models/user.py` | `mfa_secret`, `mfa_enabled` |
| `backend/app/config.py` | `refresh_token_expire_days = 7` |
| `backend/tests/security/test_auth_boundaries.py` | 16 testes de fronteiras JWT |
| `frontend/src/store/authStore.ts` | `login`, `selectTenant`, `assumeTenant`, `enterSupportMode`, `exitSupportMode`, `_savedToken` |
| `frontend/src/pages/Login.tsx` | Campo `totp_code` |
| `frontend/src/components/layout/SupportBanner.tsx` | Barra de support mode |
| `frontend/src/components/layout/TenantSwitcher.tsx` | Dropdown de tenant para super admin |

---

### Fase 29 — IA Operacional: Observabilidade e Multi-agente ✅
*Rastreabilidade de IA, controle de custos, orquestrador multi-agente, resiliência e DevSecOps*

**Implementado (migrations 0052 + 0056):**

| Componente | Arquivo | Detalhe |
|---|---|---|
| `ai_interactions` | `migrations/0052` | Rastreio de cada chamada LLM: tenant_id, user_id, operation_id, model, tokens, injection_score, duration_ms |
| `ai_token_usage` | `migrations/0052` | Agregação mensal por tenant: month, input_tokens, output_tokens, cost_usd |
| `orchestration_runs` | `migrations/0052` | Execuções do orquestrador: agents_invoked[], result, status |
| `confidence_score` | `migrations/0052` | Float 0–1 em `operations`; threshold 0.70 → `awaiting_approval` automático |
| **Orquestrador multi-agente** | `agent/orchestrator.py` | `MultiAgentOrchestrator`; execução paralela de sub-agentes; consolidação via LLM |
| **5 sub-agentes** | `agent/sub_agents/` | FirewallAgent, IdentityAgent, NetworkAgent (+ ComplianceAgent, InfraAgent planejados) |
| `LLMProvider` | `services/llm_provider.py` | AnthropicProvider / OpenAIProvider / FallbackLLMProvider |
| `POST /orchestrate` | `api/orchestrator.py` | Query em linguagem natural → sub-agentes → resposta consolidada |
| **Dry-run** | `api/operations.py` | `POST /operations/{id}/dry-run` — preview de cmds SSH/REST + guardrail + risk sem executar |
| **Circuit breaker** | `utils/circuit_breaker.py` | Redis-backed: 3 falhas/60s → circuito aberto por 5 min; integrado em `execute_operation` |
| `GET/POST /admin/circuit-breaker/{id}` | `api/admin.py` | Status + reset manual (super admin) |
| **Fernet rotation** | `utils/fernet_rotation.py` | `MultiFernet` re-encripta devices + identity_connectors sem alterar valores reais |
| `POST /admin/fernet/rotate` | `api/admin.py` | Endpoint super-admin para rodar a rotação de chave |
| **SAST CI/CD** | `.github/workflows/security.yml` | Bandit + pip-audit + truffleHog + Trivy; bloqueia em CRITICAL/HIGH |
| **Supply chain** | `requirements.txt` | `tenacity==8.3.0` adicionado; todos os pacotes com versão pinada |
| **Rate limiting API key** | `middleware/api_key_rate_limit.py` + `migrations/0056` | `X-API-Key` → plano (starter/pro/enterprise) → Redis counter → `X-RateLimit-{Limit,Remaining,Reset}`; HTTP 429 + Retry-After |

---

### Fase 35 — SOAR & Threat Intelligence ✅ (parcial)
*Resposta automatizada a incidentes, playbooks com templates AD e métricas de MTTR*

**Implementado (migration 0055):**

| Componente | Detalhe |
|---|---|
| `playbook_rules` | tenant_id, name, trigger_type, trigger_condition (JSONB), actions (JSONB array), cooldown_minutes, enabled, is_template |
| `playbook_executions` | rule_id, triggered_at, trigger_context (JSONB), actions_taken (JSONB), status (running/success/partial/failed), resolved_at |
| `threat_indicators` | ioc_type, value, source, severity, confidence, last_seen, expires_at; unique (ioc_type, value, source) |
| **5 templates AD pré-prontos** | offboarding_imediato, conta_comprometida, jit_abuso, violacao_sod, device_unreachable |
| **Actions implementadas** | notify_slack, notify_email, escalate_to_n2, create_ticket_jira, ad_disable_user, revoke_jit_access, run_snapshot |
| **Celery beat** | `soar.evaluate_scheduled_triggers` — avalia todas as rules ativas a cada minuto |
| **MTTR** | `GET /playbooks/stats/mttr` — AVG(resolved_at − triggered_at) por rule e por tenant |
| **API** | GET/POST /playbooks, GET /{id}/executions, POST /{id}/trigger, POST /templates/seed |

**Pendente:**
- Builder visual drag-and-drop (canvas React, similar ao n8n)
- Biblioteca ampliada de templates (20+ templates além dos 5 AD)
- NDR baseline comportamental por device
- Isolamento automático de device via playbook
- Correlação cross-tenant de IoCs

---

### Fase 36 — Governança de Identidade AD/M365 ✅ (parcial)
*Inventário contínuo, SoD, campanhas de revisão de acesso e JIT — via ldap3 e Microsoft Graph*

**Implementado (migration 0053):**

| Componente | Detalhe |
|---|---|
| `identity_connectors` | source (ad_ldap/azure_ad/google_workspace), config_encrypted (Fernet), is_active, last_sync_at, last_sync_status |
| `ad_users` | upn, display_name, department, job_title, manager_upn, is_enabled, mfa_registered, last_sign_in, password_last_set, license_skus[] |
| `ad_groups` | display_name, member_count, owner_upns[], health_score, health_issues[] |
| `ad_group_memberships` | user_id × group_id snapshot; unique (user_id, group_id) |
| `sod_rules` | 5 built-in (Contas a Pagar + Aprovação; Domain Admins + sistema financeiro; Help Desk + Domain Admins; Auditoria + Admins; RH Folha + Global Admin); enabled flag |
| `sod_violations` | user_id, rule_id, detected_at, status (open/accepted_risk/remediated); Celery beat `check_sod_all` diariamente |
| `access_campaigns` | campaign_type (by_manager/by_group/by_system), deadline, recurrence (once/monthly/quarterly/annually), status |
| `access_review_tasks` | reviewer_id, subject_user_id, access_item_type, decision (pending/confirm/revoke/escalate), decided_at; auto-revoke no prazo |
| `jit_requests` | target_group_id, reason (min 50 chars), duration_hours, status, approver_id, expires_at; Celery beat `expire_jit` a cada minuto |
| **AD Tool Kit** | `ad_governance_service.py`: tools read (list_users, list_inactive, check_sod) + write (disable_user, reset_password, unlock_account, add/remove_group) via ldap3 + Graph |
| **Endpoints** | 15+ endpoints: /connectors, /ad-users, /sod-rules, /sod-violations/{id}/accept-risk, /campaigns, /campaigns/{id}/review-tasks, /jit-requests, /jit-requests/{id}/approve |

**Pendente:**
- Dashboard de postura de identidade score 0–100
- Role mining com IA (privilege creep, `ExcessiveAccessAlert`)
- Gestão de saúde de grupos (fantasmas, duplicados, sem owner)
- Otimização de licenças M365 (`LicenseWaste`, economia mensal)
- Auditoria de Conditional Access Policies (Azure)
- Integração com PIM Azure AD P2 (`PimActivity`)

---

### Fase 39 — Identidade Self-Service ✅ (parcial)
*Reset de senha e desbloqueio de conta self-service via OTP, com lembretes proativos de expiração*

**Implementado (migration 0054):**

| Componente | Detalhe |
|---|---|
| `otp_requests` | tenant_id, email, otp_hash (SHA-256), action (reset_password/unlock_account), used (bool), expires_at (TTL 10 min) |
| `POST /self-service/otp/request` | Gera OTP 6 dígitos, hash SHA-256, envia por email; retorna `{sent: true, expires_in_minutes: 10}` |
| `POST /self-service/password/reset` | Valida OTP + política de senha (min 8 chars) → `reset_password()` via ldap3 (AD) ou Graph (Azure AD) → audit hash-chain |
| `POST /self-service/account/unlock` | Valida OTP → `unlock_account()` (clear lockout AD) → audit hash-chain |
| `expiry_reminders.py` | Celery beat diário (08h): detecta `pwdLastSet + maxPwdAge < now + 14d` → envia lembretes em 14/7/1 dias |
| `self_service_identity.py` | `request_otp()`, `self_service_reset_password()`, `self_service_unlock_account()` |

**Pendente:**
- Portal web público separado (URL dedicada via white-label F31)
- Catálogo de acesso visual (solicitar grupo → cria `AccessReviewTask` de F36)
- Relatórios AD pré-prontos (senha expirada, contas inativas, membros de grupo, admins sem MFA)
- Notificação proativa ao manager por email tokenizado

---

### Fase 29 — Observabilidade, IA FinOps, Qualidade e Resiliência de IA
*Rastreabilidade de IA, controle de custos, qualidade de código, dry-run e resiliência de modelo*

**Origem:** Mesa Redonda Segurança — Dr. Eduardo (AI/ML), Felipe (Responsible AI), Diego (Threat Intel), Carlos (SOC)

#### AI observability (logs + anti-injection) — Alta
Tabela `ai_interactions`: tenant_id, user_id, operation_id, prompt_tokens, completion_tokens, model, raw_prompt (Fernet-cifrado), raw_response (Fernet-cifrado), prompt_hash (SHA-256), injection_score, duration_ms, created_at. Middleware intercepta toda chamada à Anthropic SDK e registra antes/depois. O `operation_id` liga cada interaction ao device, tenant, usuário e resultado final — rastreabilidade completa prompt→comando→resposta do device. Dashboard Admin: últimas N interações, tokens por dia/mês, picos de uso. Resultado de cada `check_action_plan` registrado junto à interaction.

#### AI dry-run / modo simulação — Alta
Novo endpoint `POST /operations/{id}/dry-run` executa `execute_operation` em modo preview sem gravar no device. Para vendors com suporte nativo (Fortinet: `action=check` na policy REST): executa o check real e retorna diff do vendor. Para vendors sem suporte (SonicWall, SSH): gera "config diff" mostrando exatamente quais linhas seriam adicionadas/removidas comparando os comandos gerados com o snapshot atual do device. Frontend: botão "Simular" ao lado de "Executar" no AgentChat — exibe resultado em modal antes de confirmar a execução real.

#### Confidence threshold + escalação — Alta
Claude retorna score de confiança 0–1 no plano baseado em quantas ambiguidades encontrou (campo `_confidence` no ActionPlan JSON). Se score < 0.7 (threshold configurável por tenant via `TenantConfig`): operação vai automaticamente para `awaiting_approval` em vez de `approved`, com mensagem ao usuário: "O agente não tem certeza suficiente (confiança: X%). Um analista N2 irá revisar." Campo `confidence_score: float` adicionado à tabela `operations`. Threshold configurável no painel de configurações do tenant.

#### Token tracking por tenant — Alta
Tabela `ai_token_usage`: tenant_id, month (YYYY-MM), input_tokens, output_tokens, total_tokens, cost_usd (calculado com pricing Anthropic: $3/M input, $15/M output para Sonnet 4). Celery beat job mensal agrega `ai_interactions` → `ai_token_usage`. API `GET /admin/tenants/{id}/token-usage?months=6` para Super Admin e Admin do tenant. Dashboard: gráfico barras por mês, breakdown por usuário, custo estimado em BRL e USD. Alerta automático quando uso atinge 80% da quota do plano (via canal de alertas configurado F23).

#### Quotas e billing IA — Alta
Campo `ai_token_quota_monthly: int | None` no modelo `Tenant` (null = ilimitado). Middleware em `start_or_continue_operation`: verifica `SUM(total_tokens)` do mês atual, bloqueia com HTTP 429 e mensagem clara se acima da quota. Throttle gracioso: nos últimos 20% da quota, adiciona aviso na resposta do agente ("X tokens restantes este mês"). Planos sugeridos: Starter 100k tokens/mês, Pro 1M, Enterprise ilimitado.

#### AI fallback (Anthropic → OpenAI → Ollama) — Alta
Abstração `LLMProvider` com método `async chat(messages, schema) -> dict`. Implementações: `AnthropicProvider` (claude-sonnet-4-6), `OpenAIProvider` (gpt-4o), `OllamaProvider` (llama3:8b local). `FallbackLLMProvider`: tenta em ordem, captura `APIConnectionError` e `RateLimitError`, loga fallback no audit log como evento de segurança. Config por tenant: `llm_provider_order: list[str]` (default: `["anthropic", "openai", "ollama"]`). Ollama endpoint: `OLLAMA_BASE_URL` no env. Alerta via canal de alertas (F23) quando fallback é acionado — indica indisponibilidade do provider primário.

#### Rotação da chave Fernet — Alta
Tabela `fernet_key_history`: id, key_id (UUID), key_value_encrypted (cifrado com KMS ou master key), created_at, rotated_at, active. Script `python -m app.cli rotate-fernet-key`: (1) gera nova chave Fernet, (2) re-encripta todos os `device.credentials` (JSONB) em batch de 100, (3) mantém chave antiga como fallback para decrypt de registros não migrados, (4) marca chave antiga como rotated_at. `MultiFernet` do cryptography lib tenta decrypt com todas as chaves ativas em ordem — zero downtime. Celery beat: alerta automático se última rotação > 365 dias.

#### Circuit breaker nos connectors — Alta
`tenacity` com pattern de circuit breaker por device: após 5 falhas em 60s, abre o circuit. Estado por device em Redis: `circuit:{device_id}:open` (TTL 5 min), `circuit:{device_id}:failures` (contador). Worker Celery health check: se circuit aberto, pula o device e registra como `unreachable` sem tentar conexão. API `GET /devices/{id}/circuit-status` para Admin ver estado e forçar reset. Circuit fecha automaticamente após TTL ou reset manual. Evita que vendor lento/fora do ar bloqueie workers Celery causando backlog.

#### CI/CD com SAST + secret scanning — Alta
`.github/workflows/security.yml` (roda em PRs e push para main): Bandit (Python SAST, bloqueia em HIGH), pip-audit (CVEs em deps, bloqueia em CRITICAL), Trivy (imagem Docker, bloqueia em CRITICAL), semgrep (rules OWASP Top 10), truffleHog (secrets no git history, bloqueia qualquer finding). `.github/workflows/build.yml`: build Docker + push para registry com tag de commit hash. Merge bloqueado automaticamente se qualquer check falhar. Badge de status no README.

#### Supply chain security — Média
`requirements.txt` com hashes SHA-256 (`pip install --require-hashes`). Dependabot ou Renovate configurado para PRs automáticos de atualização de dependências. Parsers de CLI versionados por firmware: classes `FortinetParser_7_4`, `FortinetParser_7_6` — `get_connector()` usa `device.firmware_version` para selecionar o parser correto. Alerta quando versão do firmware de um device muda inesperadamente (pode indicar comprometimento ou upgrade não autorizado).

#### Rate limiting por API key — Média
Middleware FastAPI: verifica header `X-API-Key`, identifica tenant, aplica limites via Redis (`INCR` + `EXPIRE` por janela de 1 min). Limites por plano e rota: Starter (100 req/min geral, 20 writes/min), Pro (1000/min, 200 writes/min), Enterprise (configurável). Headers de resposta: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`. HTTP 429 com body indicando quando retry é seguro.

#### Chunking semântico para RAG — Média
Parser de documento detecta headers Markdown/HTML e quebra por seção em vez de por tamanho fixo. Cada chunk carrega metadata: `document_title`, `section_title`, `page_number`, `heading_level`. Reranking: após busca por embeddings (top-20), aplica BM25 para rerankar e retorna top-5 — melhora recall de seções técnicas específicas. Sanitização no upload: strip de scripts, iframes, conteúdo binário embutido em PDF; rejeita arquivos com macro Office.

#### Arquitetura Multi-Agente — Alta
Evolução do agente único generalista para orquestrador + sub-agentes especializados por domínio:

| Sub-agente | Especialidade | Ferramentas disponíveis |
|---|---|---|
| `FirewallAgent` | Regras, NAT, rotas, golden config, migration | Conectores de firewall, snapshots, guardrails |
| `IdentityAgent` | AD, M365, onboarding, offboarding, JIT, SoD | azure_ad_service, google_workspace_service, ldap3 |
| `NetworkAgent` | Conectividade, BGP/OSPF, switches, topologia | SSH routing analysis, Nmap, switch connectors |
| `ComplianceAgent` | Checks CIS/PCI/BACEN, SoD violations, revisões | compliance_service, audit_log_service |
| `InfraAgent` | Servidores, VMs, DBs (read-only analítico) | SSH/WinRM, VMware/Proxmox APIs, DB audit |

**Orquestrador Claude:** recebe a pergunta em linguagem natural, identifica qual(is) sub-agente(s) acionar, coordena execução (paralela quando independentes) e consolida a resposta final. Exemplos: "isola o firewall de Campinas e revoga o João no AD" → `FirewallAgent` + `IdentityAgent` em paralelo. "verifica compliance do cliente X" → `ComplianceAgent` + `FirewallAgent` em paralelo.

`AgentHandoff`: protocolo estruturado de retorno de cada sub-agente ao orquestrador (resultado JSON tipado, confidence score, ações executadas, próximos passos sugeridos).

#### Análise de qualidade de regras — Alta
Celery task `analyze_rule_quality(device_id)` executa após cada snapshot e detecta: regras duplicadas (mesmo src/dst/svc/action), shadow rules (regra nunca alcançada porque outra mais ampla vem antes na lista), regras `any/any allow` (abre tudo), regras disabled há >90 dias (candidatas a remoção), regras sem hit count em 30 dias (se vendor reporta hit count). Resultado salvo em campo `quality_issues: JSONB` no snapshot. Dashboard: badge "X issues" na listagem de devices; modal com lista de problemas e sugestão de correção textual.

#### Diagnóstico de qualidade de link — Média
Celery beat ICMP probe a cada 5 min para cada device: registra RTT e packet loss em `link_quality_history` (device_id, timestamp, rtt_ms, packet_loss_pct). Alerta automático (canal F23) se RTT > 3× média dos últimos 7 dias ou packet loss > 5%. Exporta métricas para Prometheus (gauge `device_rtt_ms`, counter `device_packet_loss_pct`) → visível no Grafana existente (F24). Gráfico histórico no detalhe do device: 24h, 7d, 30d.

---

### Fase 30 — Compliance Enterprise e Continuidade de Negócio
*Pacotes regulatórios, documentação legal, SLA formal e disaster recovery*

**Origem:** Mesa Redonda Rounds 1, 2 e 3 — Flávia (Compliance), Patrícia (Privacidade), Augusto (LGPD), Eduardo (BC/DR), Mônica (SLA)

#### Compliance packs por vertical — Alta
Modelo `ComplianceCheck`: framework (CIS/PCI-DSS/BACEN/LGPD/CIS-AD), check_id, description, check_function, severity (critical/high/medium). `ComplianceResult`: tenant_id, device_id, check_id, status (pass/fail/warn/na), evidence (JSON), checked_at. Cada pack tem ~50–100 checks automatizados que cruzam snapshots, audit logs e configurações do tenant. Exemplos CIS Firewall: "Nenhuma regra `any/any allow` ativa", "Acesso SSH restrito a IPs internos". Exemplos BACEN 4.658: "Logs retidos por 5 anos", "MFA habilitado para todos os admins". **Vertical Identidade (depende de F36)**: Exemplos CIS AD Benchmark — "Zero contas admin com senha nunca expirada", "Domain Admins com ≤5 membros", "Contas de serviço sem login interativo habilitado", "Auditoria de logon habilitada em todos os DCs". Exemplos LGPD Art. 46 — "Revisão de acesso a dados pessoais realizada nos últimos 90 dias", "Contas com acesso a dados pessoais revisadas em campanha de certificação". Exemplos BACEN 4.658 Art. 4 — "Acesso a ambientes críticos controlado por grupos AD auditados", "Logs de acesso a sistemas financeiros retidos ≥5 anos". Dashboard: score 0–100% por framework, drill-down por check, evolução histórica mensal. API exporta em JSON/CSV para GRC tools (ServiceNow, Archer).

#### DPA / LGPD template — Alta
Template Jinja2 do DPA gerado como PDF (WeasyPrint) com dados do tenant: nome, CNPJ, DPO, finalidade do tratamento. Cláusula automática de transferência internacional: dados de prompts processados pela Anthropic Inc. (EUA) — base legal Art. 33 LGPD + ANPD Res. 19/2024. Fluxo: Admin aceita DPA via checkbox com confirmação de leitura → `TenantDPA` salvo com timestamp, IP, user_id. Apresentado no onboarding do tenant e disponível para download em Configurações → Documentos Legais. Campo `data_processing_purpose` por categoria de dado processado (credenciais, snapshots, prompts IA).

#### RTO/RPO documentados — Alta
`BackupPolicy` por tenant: frequência (daily/weekly), retenção (30/90/365 dias), destino (S3 com SSE-KMS / GCS / volume local). Celery beat task `run_backup(tenant_id)`: exporta devices (sem credentials plaintext), snapshots, audit logs → arquivo ZIP cifrado com Fernet. `BackupTestResult`: data do último teste de restore, duração do restore, sucesso/falha, hash de integridade verificado — exibido no dashboard de compliance. RTO documentado: 4h para restore completo. RPO documentado: 1h (backup hourly para Enterprise). Alerta automático se backup não rodou no prazo.

#### SLA formal com créditos automáticos — Média
Modelo `SLAPolicy` por plano: uptime_target_pct (99.9% Enterprise, 99.5% Pro, 99% Starter), credit_per_hour_pct (10% do valor mensal por hora de violação). `UptimeRecord` (tenant_id, period_start, period_end, uptime_pct): alimentado pelos health checks e alertas de indisponibilidade (F23). Celery beat mensal: calcula uptime real vs target, cria `SLACredit` se violado. SLACredit integra ao Stripe como desconto automático na próxima fatura. Dashboard de SLA por tenant e por device: timeline de incidentes, minutos de downtime, créditos acumulados.

#### Relatório executivo de compliance — Média
PDF gerado com WeasyPrint contendo: score por framework (CIS/PCI-DSS/BACEN/LGPD) em gauge visual, top-10 violações com severidade, evolução do score nos últimos 6 meses (gráfico linha), dispositivos críticos em não-conformidade, próximas ações recomendadas. Assinatura digital: hash SHA-256 do PDF + timestamp RFC 3161 embutido como metadado. Agendamento automático: enviado ao email do Admin do tenant todo dia 1 do mês. Logo e cores do tenant aplicados via white-label (F31).

#### Data residency — Baixa
Campo `data_region: str` no Tenant (ex: "BR", "EU", "US"). Metadado `data_region` em todo audit log entry. Documentação clara no DPA: quais dados ficam no servidor do cliente (snapshots, credenciais cifradas), quais passam pela Anthropic (prompts com contexto do device), e como configurar Ollama local (F29) para eliminar saída de dados de região. Flag `restrict_to_region: bool` no Tenant — bloqueia providers externos quando ativado, forçando uso de Ollama local.

---

### Fase 31 — Expansão de Plataforma e White-label Completo
*Edge agent, suporte CGNAT, revendas completas e estratégia open core*

**Origem:** Mesa Redonda Rounds 2 e 3 — Leonardo (Infra), Sérgio (Redes/ISP), Flávia (Revenda), Juliana (Produto)

#### Edge agent on-premise — Alta
Cliente leve Python + asyncio que roda no ambiente do cliente (VM Linux ou container Docker). Abre conexão WebSocket sainte para `wss://firemanager.io/edge-gateway/{agent_token}` — zero porta inbound necessária. O SaaS envia comandos em JSON pelo WebSocket; o edge agent executa SSH/REST localmente contra os devices da LAN interna e retorna resultado. Autenticação: JWT de longa duração (30 dias) gerado no onboarding do edge agent, armazenado em arquivo local cifrado. Instalação: `pip install firemanager-edge-agent` ou Docker: `docker run firemanager/edge-agent --token TOKEN`. Modelo `EdgeAgent` no DB: tenant_id, agent_token_hash, device_ids (array de devices gerenciáveis), last_seen, version, status (online/offline/stale).

#### Suporte a CGNAT — Alta
Problema: cliente com IP CGNAT do ISP não tem IP público fixo → impossível SSH/REST de fora → edge agent resolve. Reconexão automática com backoff exponencial (tenacity: 1s → 2s → 4s → máx 60s). Heartbeat a cada 30s pelo WebSocket; SaaS marca device como `unreachable` se sem heartbeat por 3 min. Multiplexação: um edge agent pode gerenciar N devices na mesma LAN interna (switch, firewall, servidor) via SSH/REST local. Dashboard: badge "via Edge Agent" no device com última reconexão, versão do agent e latência média da conexão WebSocket.

#### White-label completo — Alta
Modelo `TenantBranding`: logo_url, favicon_url, primary_color (hex), secondary_color, custom_domain, email_from_name, email_from_address, report_header_text, report_footer_text. CNAME: Admin configura `firemanager.minhaempresa.com.br` → nginx detecta pelo Host header e serve o frontend com branding do tenant (CSS vars injetadas dinamicamente, logo via CDN). Email transacional: templates Jinja2 de todos os emails (convite, alertas, relatórios) usam logo e cores do tenant. PDF executivo (WeasyPrint): logo do parceiro no cabeçalho, cores primárias, rodapé customizado. Favicon e title da aba (`<title>`) dinâmicos por tenant.

#### SSO / OIDC — Alta
Modelo `TenantSSO`: provider (azure_ad/okta/google/custom_oidc), client_id, client_secret (Fernet), discovery_url (ex: `https://login.microsoftonline.com/{tenant}/.well-known/openid-configuration`), group_claim, group_mapping (JSON: `{"Firewall-Admins": "admin", "SOC-Team": "analyst"}`). Fluxo PKCE: login page detecta domínio do email → redireciona para IdP → callback `/auth/sso/callback` cria sessão → JWT interno com role mapeada. Provisionamento JIT: usuário novo via SSO criado automaticamente com role do grupo. Flag `sso_required: bool` no tenant: bloqueia login local para forçar SSO corporativo.

#### RBAC granular — Média
Modelo `Permission`: resource (device/group/template/report/audit/billing), action (read/write/execute/approve/export), scope_type (tenant/group_id/device_id). `CustomRole` por tenant além dos 3 padrões: ex: "Firewall-RO" (lê devices, zero escrita), "Auditoria" (só audit logs + relatórios). API keys com scopes explícitos: `devices:read`, `operations:write`, `reports:read` — API key nunca herda mais permissões do que o usuário que a criou. Middleware de autorização consulta `Permission` em vez de comparar role string diretamente.

#### Open core — connectors OSS — Média
Repositório público `github.com/firemanager/connectors` com: interface `BaseConnector` documentada, connectors existentes como exemplos de referência, guia de contribuição (testes obrigatórios, formato de PR, processo de review). `firemanager/community-connectors`: connectors de terceiros aprovados mas não mantidos pelo time core. Licença: core SaaS (AGPL), connectors (Apache 2.0) para máxima adoção. CI do repositório público: testes de integração contra devices simulados (mock servers).

#### Programa de certificação parceiros — Média
Portal web (módulo no Super Admin para tenants `is_partner: bool`): trilha de certificação com módulos de treinamento (vídeo + quiz) + prova técnica em ambiente sandbox dedicado. Badge "FireManager Certified Partner" concedido após aprovação, visível no portal público. Dashboard de parceiro: clientes gerenciados, MRR gerado, leads indicados, comissões pendentes e pagas. Deal registration: parceiro registra oportunidade e fica protegido de venda direta.

#### Marketplace de plugins — Baixa
Modelo `Plugin`: name, version, author_tenant_id, category (connector/report/workflow/alert_rule), package_url, signature (Ed25519), approved_at, approved_by. Fluxo: parceiro faz upload de wheel Python assinado → review manual pelo time FireManager (segurança + funcionalidade) → publicação no marketplace. Instalação por tenant via UI: `pip install` do plugin dentro do container em virtualenv isolado. Sandbox de permissões: plugin só acessa sua própria DB namespace, não pode ler credenciais de outros tenants.

---

### Fase 32 — Produto, UX e Documentação
*Experiência do usuário, acessibilidade, documentação por persona e internacionalização*

**Origem:** Mesa Redonda Rounds 2 e 3 — André (Produto), Beatriz (UX/Acessibilidade), Juliana (GTM), Cristina (CS)

#### Documentação pública por persona — Alta
Site MkDocs Material (ou Docusaurus) em `docs.firemanager.io`, gerado automaticamente no CI e publicado via GitHub Pages ou CDN. Três trilhas com navegação lateral separada: **Admin MSSP** (criar tenant, adicionar device, configurar SSO, gestão de usuários, API keys, billing); **Analista N2** (usar o agente, revisar operações, bulk jobs, interpretar snapshots, Golden Config); **Cliente final** (ver dashboard, relatórios, abrir chamado, entender o que o agente fez no seu firewall). Swagger interativo embutido por módulo (gerado do OpenAPI 3.1 do FastAPI). Changelog versionado por release com data e breaking changes destacados.

#### Billing e planos — Alta
Modelo `Plan`: name, monthly_price_brl, max_devices, max_users, ai_token_quota, sla_target_pct, features (JSONB com flags de features). Integração Stripe: `stripe.Customer` por tenant, `stripe.Subscription` por plano, webhooks para `invoice.paid`, `invoice.payment_failed`, `customer.subscription.deleted`. Fatura PDF automática gerada com WeasyPrint no dia do vencimento e enviada por email. Portal de billing no painel do Admin do tenant: histórico de faturas (download PDF), troca de plano (upgrade imediato, downgrade no próximo ciclo), atualização de dados de cartão. Dunning: 3 tentativas de cobrança em 7 dias → tenant entra em read-only → após 30 dias sem pagamento → dados retidos 60 dias → purge automático com aviso.

#### Multi-idioma (i18n) — Média
Frontend: `react-i18next` com namespace por módulo (`devices`, `operations`, `compliance`, `billing`). Detecção automática via `navigator.language` com fallback para `pt-BR`. Seletor manual na navbar com cookie de preferência (persiste entre sessões). Ferramenta de extração: `i18next-scanner` no CI para auditar strings sem tradução (CI falha se >5% de strings não traduzidas). Backend: strings de resposta do agente IA no idioma do usuário — system prompt instrui Claude com `Respond in {user_language}`. Mensagens de erro da API retornadas em JSON com campo `message_pt` e `message_en`.

#### Acessibilidade (WCAG 2.1 AA) — Média
Auditoria automatizada com axe-core (CI bloqueia se encontrar violações de nível AA). Auditoria manual com Lighthouse e NVDA/VoiceOver antes de cada release. Palete de cores: contraste mínimo 4.5:1 para texto normal, 3:1 para texto grande — testado com Color Contrast Analyzer. Modo alto contraste opcional (toggle na navbar). Foco visível: `outline: 2px solid` em todos os elementos interativos; skip-link `"Pular para o conteúdo"` no topo da página. Tabelas de dados: `<caption>` descritivo, `scope="col"` nos `<th>`, `aria-sort` em colunas ordenáveis, `aria-live="polite"` em atualizações assíncronas. Toasts: `role="alert"` para erros, `role="status"` para confirmações.

#### Onboarding guiado — Média
Wizard React com checklist de 4 etapas na home (só aparece enquanto incompleto): (1) Adicionar device + testar conexão com badge de sucesso, (2) Rodar primeiro snapshot e ver resultado, (3) Fazer primeira pergunta ao agente ("listar regras"), (4) Configurar primeiro alerta. Estado persistido em `UserPreference.onboarding_completed: bool` e `onboarding_step: int` (permite retomar de onde parou). Checklist visível como card na home com progresso percentual e badges de conclusão por etapa. Botão "Pular onboarding" para usuários experientes que chegam via convite.

#### Feedback in-app — Baixa
Widget flutuante (bottom-right, botão "?" com badge) com rating 1–5 estrelas + campo de texto livre (max 500 chars). Contextual: detecta rota atual (`/devices`, `/operations/bulk`, `/compliance`) e última operação realizada para pré-preencher contexto no payload. Backend: tabela `UserFeedback` (tenant_id, user_id, page, rating, text, context JSON, created_at). Webhook configurável para Slack (canal `#feedback-interno`) e integração com Linear/Jira via API. Rate limit: máximo 3 feedbacks por usuário por dia para evitar spam.

---

### Fase 33 — IA Safety & Governança
*Controles formais de segurança do agente IA, aprovação avançada e framework de governança*

**Origem:** Mesa Redonda Segurança da Informação — Felipe (Responsible AI), Larissa (LGPD), Marcos (IR), Carlos (SOC), Paulo (OT), Mônica (SecOps), Rafael (CISO), Ana (Red Team)

#### Aprovação dupla para devices críticos — Alta
Campo `is_critical: bool` no Device, configurável pelo Admin do tenant. Para devices críticos: após agente gerar plano aprovado, status vai para `awaiting_dual_approval` em vez de `approved`. Modelo `OperationApproval`: operation_id, approver_id, approved_at, comment — necessário 2 registros de usuários distintos (nem o solicitante nem o mesmo aprovador duas vezes). Fila de aprovação: dashboard dedicado para analistas N2 e Admin com operações pendentes ordenadas por criticidade e tempo de espera. Timeout configurável por tenant (default: 4h): se não aprovado, status → `expired` + notificação ao solicitante. Auto-escalação: após 1h sem resposta, notifica canal de alertas configurado (Slack/Teams).

#### Janela de manutenção por device — Alta
Modelo `MaintenanceWindow`: device_id, day_of_week (0–6 ou null=diário), start_time, end_time, timezone (ex: `America/Sao_Paulo`), enabled. Verificação em `execute_operation`: se device tem janela configurada e horário atual está fora dela → operação vai para status `queued_maintenance` em vez de executar. Worker Celery beat `check_maintenance_queues` a cada minuto: quando janela abre, pega operações `queued_maintenance` daquele device e executa em ordem de criação. Frontend: calendário semanal visual de janelas no painel de configurações do device. Override por Admin: flag `force_execute: bool` no request de execução bypassa a janela (logado no audit com justificativa obrigatória).

#### Termos de Uso e política de IA — Alta
Documento Markdown versionado em `/terms` (ToS) e `/ai-policy` (política do agente). Seções da política de IA: o que o agente faz (gera planos, executa via API), o que nunca faz (executa sem aprovação humana em devices críticos, acessa sistemas além dos cadastrados), como é auditado (hash-chain + RFC 3161), limitação de responsabilidade (o FireManager é ferramenta, decisão final é do analista). `TenantTermsAcceptance`: tenant_id, admin_user_id, terms_version, ai_policy_version, accepted_at, ip_address. Gate no onboarding e no upgrade de plano: Admin deve aceitar versão atual dos termos. Nova versão de termos força nova aceitação na próxima abertura (redirect no middleware).

#### Security Incident Response Plan (SIRP) para IA — Alta
Documento público em `docs.firemanager.io/security/sirp`. Categorias de incidente: (1) operação executada sem autorização válida, (2) prompt injection confirmado, (3) acesso a device não autorizado pelo tenant, (4) dados de tenant A exibidos para tenant B. Para cada categoria: sequência de resposta, responsáveis, SLA de comunicação ao cliente (≤ 2h para crítico). Internamente: trigger automático quando audit log detecta `operation.executed_at` sem `operation.approved_by` válido → abre `SecurityIncident` com severity=critical. `SecurityIncident`: type, severity, affected_tenant_id, detected_at, notified_at, resolved_at, root_cause, remediation. Status page pública `status.firemanager.io` com histórico de incidentes.

#### Red team trimestral do agente — Alta
Processo documentado (não código de produção). Checklist de exercícios trimestrais: prompt injection via input do usuário, injeção via conteúdo do BookStack, via nome do device, via output do snapshot SSH, jailbreak de role do sistema, bypass de guardrail por ofuscação, data exfiltration via RAG (tentar extrair credenciais de outros tenants via perguntas ao agente), IDOR via operation_id. Resultado documentado em `RedTeamExercise` no DB: date, exerciser_name, scope, findings (JSONB com CVSS score), critical_count, fixed_at. Template de relatório padronizado. Celery beat: alerta interno se passou >95 dias sem `RedTeamExercise` registrado.

#### Four-eyes para operações de gestão — Alta
Operações de gestão que exigem segundo aprovador: promover usuário para admin, revogar convite já enviado, alterar configuração SSO, adicionar/remover device crítico, alterar plano para downgrade, resetar MFA de outro usuário. **Extensão F36**: `grant_ad_privileged_role` — concessão de Domain Admin, Enterprise Admin ou Global Admin M365 via UI do Eternity SecOps exige segundo aprovador; o payload inclui o objeto AD/M365 de destino, a role concedida e a justificativa de negócio; execução via Graph/ldap3 só ocorre após aprovação. `ManagementApprovalRequest`: action_type (enum com os tipos acima + `grant_ad_privileged_role`), requested_by, payload (JSON com snapshot da mudança proposta), approved_by, rejected_by, created_at, expires_at (1h). Fluxo: admin solicita → todos os outros admins do tenant recebem notificação → primeiro a aprovar desbloqueia a ação → se rejeitado, ação cancelada e log registrado com motivo. Ambos os usuários (solicitante + aprovador) registrados no audit hash-chain.

#### Validação de DPA com Anthropic — Alta
Não é código mas gera artefatos de produto. Aviso embutido na ativação do tenant: "Ao usar o agente IA, prompts contendo contexto do device são processados pela Anthropic Inc. (EUA). Veja nosso DPA para detalhes." DPA gerado (F30) já inclui cláusula específica ANPD Res. 19/2024 sobre transferência internacional. Campo `dpa_anthropic_acknowledged: bool` no `TenantTermsAcceptance`. Para tenants com `data_region = "BR"` e `restrict_to_region = true` (F30): sistema usa Ollama local (F29) e aviso é omitido pois dados não saem do país. Contato com time legal Anthropic para validar Data Processing Agreement para clientes brasileiros.

#### Direito ao esquecimento (data deletion) — Alta
Endpoint `DELETE /admin/tenants/{id}` (só Super Admin) com body `{"confirmation": "DELETE TENANT <nome_exato>", "reason": "LGPD Art. 18 solicitação do titular"}`. Cascade completo: usuários, devices, credenciais (decrypt + wipe do Fernet), snapshots, audit_logs, ai_interactions, embeddings pgvector, documentos BookStack, API keys, tokens de convite, backups automáticos (exceto cold storage retido 30 dias). Execução como Celery task assíncrona com progress tracking: status `purging` → `purged`. Antes do purge: backup final cifrado em cold storage com TTL 30 dias. Audit do próprio purge: `TenantPurgeLog` (tabela separada, sem FK para tenant, imutável): tenant_name, tenant_id, requested_by, reason, purged_at, backup_retained_until. Email de confirmação ao super admin e ao ex-admin do tenant após conclusão.

#### Ancoragem de audit log em RFC 3161 — Média
Celery task `anchor_audit_logs` a cada hora: coleta todos `audit_log` entries da última hora → serializa em JSON canônico → calcula SHA-256 do bloco → envia para TSA gratuita (`freetsa.org` ou `tsa.pki.gva.es`) via `TIMESTAMP REQUEST` RFC 3161. Salva `AuditLogAnchor`: period_start, period_end, block_hash, entry_count, tsa_response (base64 DER), tsa_timestamp, tsa_serial, tsa_cert_chain. Endpoint público `GET /audit/verify-anchor/{anchor_id}`: recalcula hash do bloco, verifica assinatura TSA, retorna `{valid: bool, entries_count, timestamp, tsa_authority}`. Prova em juízo: arquivo ZIP com bloco de logs + TSA response + cadeia de certificados da CA.

#### Dashboard de postura interna — Média
Painel exclusivo para Super Admin (`is_super_admin`), não visível para tenants. Métricas em tempo real: tentativas de login com falha nas últimas 24h por tenant e por IP (detecta força bruta), operações de escrita por tenant por dia (gráfico — detecta picos anômalos), guardrail blocks nas últimas 24h por tenant e tipo de violação, circuit breakers abertos agora (lista de devices), tokens de convite expirados não usados (indica processos de onboarding abandonados), tenants com compliance score < 50% (risco de churn + risco regulatório). Alertas internos automáticos: tenant com >10 logins falhos em 1h → flag para investigação de comprometimento de conta.

#### Canal público de reporte de vulnerabilidades — Média
Página pública `firemanager.io/security`: email `security@firemanager.io`, PGP key pública para download (para reports confidenciais cifrados), política de disclosure responsável (safe harbor, escopo, o que é elegível, recompensas). SLA publicado: crítico 24h acknowledge + 7d fix, alto 7d acknowledge + 30d fix, médio 30d acknowledge + 90d fix. Internamente: `VulnerabilityReport` (reporter_email, severity, title, description, proof_of_concept, status: new/triaging/fixing/fixed/wont_fix, fix_version, disclosed_at, bounty_paid). Template de resposta padrão PT/EN gerado automaticamente ao receber report. Após fix: coordena com reporter para disclosure responsável após 90 dias.

---

### Fase 34 — Infraestrutura de Segurança Avançada
*mTLS interno, KMS/HSM, microsegmentação, OPA e observabilidade de segurança*

**Origem:** Mesa Redonda Segurança — Sandra (Architecture), Roberto (Crypto), Juliana (Cloud), Fernanda (Zero Trust), Mônica (SecOps), Diego (Threat Intel)

#### mTLS entre serviços internos — Alta
CA interna gerada no bootstrap do Docker Compose com `step-ca` (ou `cfssl`): emite certificados client+server para api, celery, redis. Redis: `requirepass` + `tls-cert-file` + `tls-key-file` + `tls-ca-cert-file` — conexão recusada sem TLS mutual. FastAPI: `httpx.AsyncClient` com cert do client para callbacks internos. Celery: `kombu` configurado com SSL context. Script de renovação automática: certificados internos com validade 90 dias, renovados automaticamente via Celery beat 30 dias antes do vencimento. Monitoramento: Prometheus alerta se certificado vence em <15 dias.

#### KMS / HashiCorp Vault — Alta
Vault em container separado no Docker Compose (modo dev para local, prod usa Vault HA em 3 nodes ou AWS KMS). Secrets engine `kv-v2` para todos os secrets: `ANTHROPIC_API_KEY`, `DATABASE_URL`, `FERNET_KEY`, `SMTP_PASSWORD`, `STRIPE_SECRET_KEY`. App role auth: cada serviço (api, celery_worker, celery_beat) tem `role_id` + `secret_id` únicos com políticas Rego mínimas (api só pode ler `kv/api/*`). Audit log do Vault: quem acessou qual secret e quando — exportado para Prometheus. Fail-secure: se Vault indisponível no startup, API recusa inicializar (não falha aberta com secrets do `.env`). Rotação de secrets: script que gera novo valor, salva no Vault, e reinicia o serviço afetado.

#### Microsegmentação Docker — Alta
Redes Docker explícitas no `docker-compose.yml`: `frontend_net` (nginx↔api), `backend_net` (api↔postgres↔redis), `worker_net` (celery↔redis↔postgres), `monitoring_net` (prometheus↔grafana↔api:/metrics). `api` não está em `worker_net` — celery se comunica com api via Redis broker apenas, nunca direto. `postgres` e `redis` não têm portas expostas no host (sem `ports:` — só `expose:`). Nenhum serviço com `network_mode: host`. Nginx é o único com portas 80/443 expostas para o host. Testes de conectividade no CI: verifica que `api` não consegue alcançar `celery` diretamente.

#### Open Policy Agent (OPA) — Média
Sidecar OPA em container separado com `opa_policies/` versionadas em git. Políticas Rego: `allow_operation(user, device, action)`, `allow_read(user, resource)`, `can_approve(user, operation)`, `is_admin(user, tenant)`, `can_bulk_execute(user, device_ids)`. FastAPI dependency `Depends(opa_authorize("allow_write"))`: faz POST para `http://opa:8181/v1/data/firemanager/allow` com input `{user, resource, action}` → bool. Vantagem: todas as decisões de authz passam por ponto único com log estruturado; policy audit em auditoria externa sem precisar ler código Python. Deploy de políticas: `opa_policies/` no git → `docker cp` no startup do OPA container.

#### Container security hardening — Alta
Todas as imagens baseadas em `python:3.12-slim` com usuário `appuser` (UID 1000, GID 1000) no Dockerfile: `RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app`. `--read-only` no filesystem + `/tmp` como `tmpfs` no docker-compose. AppArmor profile customizado: bloqueia `ptrace`, `net_admin`, `sys_admin`, `sys_rawio`. Seccomp profile: whitelist das syscalls necessárias (open, read, write, socket, connect, epoll_wait, futex, clock_gettime). Trivy scan automático no CI em cada build: bloqueia push para registry se encontrar CVE com severity CRITICAL ou HIGH (com exceção documentada para CVEs sem fix disponível).

#### Gestão de vulnerabilidades formal — Alta
GitHub Actions scheduled (domingo 02:00 UTC): (1) Trivy scan na imagem Docker do registry, (2) Bandit scan no código Python (HIGH/CRITICAL bloqueiam), (3) pip-audit nas dependências (CRITICAL bloqueiam), (4) semgrep com ruleset `p/owasp-top-ten`. Resultados salvos como artefato da Action + criados automaticamente como `VulnerabilityReport` (F33) para findings críticos. SLA com alerta automático via Slack (#security-interno): crítico 24h sem PR → alerta + create GitHub Issue P0; alto 7d; médio 30d. Relatório mensal PDF para CISO interno: findings por severidade, tempo médio de correção (MTTR), trend de vulnerabilidades abertas vs fechadas.

#### Pentest externo anual — Média
Processo documentado com artefatos de produto. Escopo definido anualmente: API REST, autenticação, RBAC, injeção de comandos, SSRF, tenant isolation, prompt injection no agente IA. Empresa credenciada (CREST ou OWASP partner verificado). Findings públicos após 90 dias do fix (responsible disclosure no `firemanager.io/security`). `PentestRecord` no DB: date, company, scope_description, critical_count, high_count, medium_count, all_fixed_at. Bug bounty privado: HackerOne private program para clientes Enterprise que queiram testar com regras de engajamento formais.

#### Supply chain: parser versionado por firmware — Média
`ConnectorRegistry`: dicionário `{vendor: {firmware_prefix: ConnectorClass}}`. Exemplos: `{"fortinet": {"7.4": FortinetConnector_7_4, "7.6": FortinetConnector_7_6}, "sonicwall": {"6": SonicWall_v6, "7": SonicWall_v7}}`. `get_connector(device)` usa `device.firmware_version` para selecionar classe correta — sem if/else espalhados. Structural drift detection: cada connector define `expected_output_schema` (Pydantic model); após parsing, valida output; se divergir → cria `FirmwareDriftAlert` e usa parser de fallback mais permissivo. `FirmwareVersionHistory`: device_id, detected_version, detected_at — alerta quando versão muda inesperadamente (pode indicar upgrade não autorizado ou comprometimento).

---

### Fase 35 — SOAR & Threat Intelligence
*Resposta automatizada a incidentes, inteligência de ameaças e detecção avançada*

**Origem:** Mesa Redonda Segurança — Mônica (SecOps/SOAR), Diego (Threat Intel), Carlos (SOC), Leonardo (Pentester)

#### SOAR leve embutido — Alta
Modelo `PlaybookRule`: name, tenant_id, trigger_type (risk_score_drop/anomaly_detected/guardrail_block/device_unreachable/siem_alert/identity_anomaly/jit_abuse), trigger_condition (JSON: `{"metric": "risk_score", "operator": "<", "threshold": 20, "window_minutes": 5}`), actions (JSON array de `{type, params}`), cooldown_minutes (evita loops), enabled. Actions disponíveis: `set_device_read_only`, `notify_slack`, `notify_email`, `create_ticket_jira`, `run_snapshot`, `escalate_to_n2`, `isolate_device`, `revert_to_snapshot`, `notify_mssp_admin`, `run_compliance_check`. Celery beat task `evaluate_playbooks`: a cada minuto, avalia todas as rules ativas de todos os tenants; se trigger satisfeito, executa actions em sequência. `PlaybookExecution`: rule_id, triggered_at, trigger_context (JSON snapshot do estado que disparou), actions_taken (JSONB), status (success/partial/failed), resolved_at (para cálculo de MTTR). Frontend: editor visual de playbooks com cards de condição + ação conectados por setas (canvas drag-and-drop — ver Builder Visual abaixo).

#### Builder Visual de Playbooks (drag-and-drop) — Alta
UI React com canvas drag-and-drop (similar ao n8n mas focado em infraestrutura de segurança). Cards de Trigger → cards de Condição → cards de Ação conectados por setas visuais. Cada card tem formulário contextual: trigger card mostra campos do trigger_type selecionado, action card mostra parâmetros da action selecionada. Preview de execução: simula o playbook com dados históricos antes de ativar. Substituição da configuração via JSON/API por uma experiência visual acessível a analistas N1.

#### Biblioteca de Templates de Playbook — Alta
Templates pré-prontos ativados com 1 clique, adaptáveis por tenant:

| Template | Trigger | Ações |
|---|---|---|
| Device Unreachable Response | `device_unreachable` | snapshot + alerta Slack + ticket Jira + escalar N2 |
| Risk Score Crítico | `risk_score < 20` | isolar device + alerta CISO + requer aprovação dupla |
| Guardrail Block Alert | `guardrail_block` | alerta Slack + log auditoria + bloquear usuário 15min |
| SoD Violation Detected | `sod_violation` | alerta manager + criar access review task |
| IoC Match em Regras | `threat_intel_match` | snapshot + alerta + criar tarefa de revisão manual |
| Login Suspeito | `identity_anomaly` | suspender conta + revogar JIT + notificar CISO |
| SIEM Alert Crítico | `siem_alert` (severity=CRITICAL) | snapshot device + isolar se confirmed + fechar alerta no SIEM |

#### Métrica MTTR (Mean Time to Resolution) — Alta
Campo `resolved_at` em `PlaybookExecution` — preenchido quando a última action do playbook conclui com sucesso. `MTTR = AVG(resolved_at - triggered_at)` por playbook e por tenant. Dashboard de eficiência de automação: MTTR por tipo de playbook, por severidade, evolução histórica semanal/mensal. Permite ao MSSP demonstrar ao cliente: "tempo médio de resposta a incidentes caiu de 47min para 8min após ativar automação".

#### Threat Intelligence feed — Alta
Integrações com feeds públicos gratuitos: OTX AlienVault API (IoCs por categoria), AbuseIPDB (IPs com histórico de abuso, score > 75), CISA KEV (Known Exploited Vulnerabilities — CVEs com exploração ativa), URLhaus (URLs de malware), Feodo Tracker (C2 de botnets). Celery beat a cada 4h: baixa feeds, normaliza em `ThreatIndicator` (type: ip/domain/hash/cve, value, source, severity, tags, last_seen, confidence). Match automático após cada snapshot: cruza IPs das regras de firewall (src/dst das access rules, NAT policies, rotas) com `ThreatIndicator`. Alerta de match: se regra `allow` tem src/dst que é IoC com severity HIGH/CRITICAL → alerta imediato via canal configurado. Dashboard TI: timeline de matches por tenant, breakdown por feed/categoria, top-10 IoCs mais vistos nos tenants gerenciados.

#### NDR (Network Detection & Response) — Média
Baseline comportamental por device: calcula média e desvio padrão de conexões por hora (contagem de sessões nos snapshots) nos últimos 30 dias de dados históricos. Anomalia detectada se: contagem atual > média + 3σ, ou novo protocolo não visto antes nas últimas 4 semanas, ou conexão para IP nunca visto antes nas últimas 7 dias. `NetworkAnomaly`: device_id, detected_at, anomaly_type, baseline_value, observed_value, severity, context_json (IPs/portas envolvidos). Correlação: se anomalia simultânea em >3 devices do mesmo tenant na mesma janela de 30 min → severity escalada para CRITICAL e `CrossTenantCampaign` verificado (ver correlação cross-tenant). Dashboard NDR: timeline de anomalias, drill-down por device, heatmap de intensidade por hora×dia da semana.

#### Isolamento automático de device — Alta
Acionado por: action `isolate_device` em PlaybookRule, ou manualmente pelo Admin via botão "Isolar device" no painel. Isolamento técnico: connector do vendor aplica regra de segurança temporária "deny all inbound+outbound" com prioridade máxima (posição 0 na lista de políticas), preservando regras existentes (só adiciona a nova). Salva estado em `DeviceIsolation`: device_id, isolated_at, isolated_by (user_id ou `"automation:{playbook_id}"`), reason, pre_isolation_snapshot_id, restored_at, restored_by. Reativação: exige aprovação dupla (F33) + justificativa mínima de 50 chars registrada no audit. Notificação imediata: CISO do cliente via email + canal de alertas Slack/Teams. Timeout de segurança: se isolamento ativo por >24h sem reativação, alerta de escalação automático.

#### Correlação de alertas cross-tenant — Média
Celery task `correlate_cross_tenant_alerts` (a cada 15 min): agrega `ThreatIndicator` matches e `NetworkAnomaly` de todos os tenants na última hora. Detecta padrão: mesmo IoC (IP/domínio) encontrado em devices de >3 tenants distintos na mesma janela de 1h → cria `CrossTenantCampaign` (name, ioc_value, affected_tenant_count, affected_tenants: lista anonimizada, severity, started_at). Visível exclusivamente para Super Admin no dashboard de postura interna (F33). Permite notificação proativa ao CISO de cada tenant afetado: "Detectamos atividade relacionada ao IoC X em múltiplos clientes gerenciados. Recomendamos revisar suas regras para este IP." — sem expor dados de outros tenants (notificação genérica com o IoC, não menciona quais outros tenants foram afetados).

#### Anomalias de identidade como gatilho SOAR — Alta (integração com F36)
Após F36 ser implementada, os eventos de identidade alimentam os PlaybookRules existentes com dois novos trigger_types: `identity_anomaly` (login suspeito detectado pelo baseline do F36) e `jit_abuse` (usuário com JIT ativo fazendo volume anômalo de acessos). Actions adicionadas: `suspend_ad_account` (desabilita conta no AD via ldap3 ou Graph), `revoke_jit_access` (remove antecipadamente o acesso JIT), `force_mfa_reregistration` (revoga sessões MFA via Graph). Exemplo de playbook: login de país não reconhecido + acesso a >50 arquivos SharePoint em 10 min → suspender conta imediatamente + abrir ticket Jira P1 + notificar CISO.

---

### Fase 36 — Governança de Identidade AD/M365
*Inventário contínuo, revisão de acesso, SoD, role mining, JIT e gestão do ciclo de vida de identidades*

**Origem:** Análise do webinar "Maximizando a segurança e conformidade do Active Directory e Microsoft 365 com revisões de acesso automatizadas" — demanda de clientes MSSP com ambientes híbridos AD on-premise + M365

**O que é novo vs fases existentes:** F21/F22 são orientadas a eventos (disparam em contratação/demissão). Esta fase é orientada a **governança contínua** — inventário diário, campanhas periódicas, detecção de drift, sem depender de um evento de RH para agir.

#### Inventário contínuo de identidades — Alta
Sync diário via dois protocolos em paralelo. **AD on-premise**: ldap3 com bind de conta de serviço read-only; busca `objectClass=user` e `objectClass=group` pela base DN do tenant; atributos: displayName, userPrincipalName, distinguishedName, memberOf, lastLogon, pwdLastSet, userAccountControl (enabled/disabled/locked), manager, department, title, mail. **Azure AD / M365**: Microsoft Graph API com Application credentials (client_id + client_secret Fernet-cifrado por tenant): `GET /users`, `GET /groups`, `GET /directoryRoles/members`, `GET /subscribedSkus`, `GET /users/{id}/licenseDetails`, `GET /reports/getM365AppUserDetail(period='D90')`, `GET /signInActivity`, `GET /identity/conditionalAccess/policies`. Delta sync via Microsoft Graph delta queries para mudanças intraday (sem reprocessar tudo). `IdentitySnapshot` (tenant_id, source: ad_ldap/azure_ad, snapshot_date, user_count, group_count, data_hash). Objetos: `AdUser` (id, tenant_id, source, object_id, upn, display_name, department, job_title, manager_id, last_sign_in, created_at_ad, is_enabled, is_external, mfa_registered, license_skus[], groups[], roles[], synced_at), `AdGroup` (id, tenant_id, object_id, display_name, group_type, owner_ids[], member_count, created_at_ad, last_used, synced_at), `AdGroupMembership` (group_id, user_id, added_at, added_by).

#### Campanhas de revisão de acesso (Access Certification) — Alta
Motor completo de certificação de permissões com workflow configurável por tenant. **Tipos de campanha**: (1) **Por manager**: cada manager certifica os acessos de todos os seus subordinados diretos — para cada par (subordinado, grupo/role), manager decide Confirmar / Revogar / Escalar; (2) **Por grupo**: owner do grupo certifica cada membro — adequado para grupos de projeto e times; (3) **Por sistema**: responsável designado certifica quem tem acesso a um conjunto de grupos que representa um sistema (ex: "grupos do ERP"); (4) **Por privilegiados**: revisão mensal forçada de todos os Domain Admins, Global Admins M365, Exchange Admins — mais restrita, sem opção de skip. Modelos: `AccessCampaign` (id, tenant_id, name, campaign_type, scope_filter JSON, reviewer_type: manager/group_owner/designated, deadline, recurrence: once/monthly/quarterly/annually, status: draft/active/completed/expired, created_by, created_at). `AccessReviewTask` (campaign_id, reviewer_id, subject_user_id, access_item_type: group/role/license, access_item_id, access_item_name, decision: pending/confirm/revoke/escalate, decided_at, comment, auto_revoked_at). `AccessReviewAudit` (task_id, action, performer_id, timestamp, evidence_hash SHA-256). Fluxo: Admin cria campanha → sistema gera um `AccessReviewTask` para cada combinação reviewer × subject × access_item → notificação via F23 (email + Slack) com link para tela de revisão → reviewer vê lista com checkboxes Confirmar/Revogar/Escalar → decisões de Revogar executadas automaticamente no AD via ldap3 (remove memberOf) ou Graph (DELETE /groups/{id}/members/{userId}) → relatório final PDF com todas as decisões, timestamps e hash de cada decisão. Auto-escalação: sem resposta em 48h → lembrete. Sem resposta até 24h antes do prazo → acesso revogado automaticamente (configurável: revogar ou manter com flag "não revisado").

#### Segregação de Funções (SoD) — Alta
Detecta combinações de permissões que violam separação de funções — principal causa de fraude interna e achado de auditoria. `SoDRule` (tenant_id, name, role_a_type: group/ad_role/m365_role, role_a_id, role_b_type, role_b_id, risk_description, severity: critical/high/medium, remediation_suggestion, enabled). Biblioteca embutida ativada no onboarding do tenant:

| Conflito | Severidade | Risco |
|---|---|---|
| Grupo "Contas a Pagar" + Grupo "Aprovação Financeira" | Crítico | Cria e aprova próprio pagamento |
| Global Admin M365 + grupo "RH Folha de Pagamento" | Crítico | Acesso irrestrito a dados sensíveis de RH |
| Exchange Admin + Compliance Admin M365 | Alto | Pode ler emails alheios e suprimir evidências de e-Discovery |
| Domain Admin on-premise + acesso ao sistema financeiro | Crítico | Sem segregação entre infra e dados financeiros |
| Grupo "TI Help Desk" + Domain Admins | Alto | Help Desk com poder de alterar qualquer conta do AD |
| Grupo "Auditoria" + Grupo "Administração de Sistemas" | Alto | Auditor pode modificar os logs que ele mesmo auditará |

Celery task diária `check_sod_violations`: compara cada `AdUser` ativo com todas as `SoDRule` ativas do tenant. Gera `SoDViolation` (user_id, rule_id, detected_at, status: open/accepted_risk/remediated, accepted_by, remediated_at). Dashboard: lista por severidade, botão "Aceitar risco" com justificativa mínima obrigatória (logada no audit hash-chain), botão "Iniciar remediação" que cria AccessReviewTask pontual para o conflito. Admin cria regras customizadas: seleciona dois grupos/roles, define severidade — IA sugere remediação baseada no perfil do usuário e nos demais grupos que possui.

#### Análise de Acessos Excessivos e Role Mining com IA — Alta
Combate o "privilege creep" — acumulação silenciosa de permissões ao longo do tempo por promoções, mudanças de projeto e pedidos pontuais nunca revogados. **Role Mining**: para cada cargo/title com ≥3 usuários, calcula perfil de grupos via frequência relativa. Grupos presentes em >80% dos usuários do cargo = perfil padrão sugerido. Grupos presentes em <20% = excesso individual candidato a revisão. `RoleProfile` (tenant_id, job_title, department, standard_groups[], computed_at). `ExcessiveAccessAlert` (user_id, rule_type, details JSON, severity, created_at, status). **Indicadores configuráveis de excesso**: usuário com >25 grupos (amarelo) ou >50 grupos (vermelho); membro de grupos de >3 departamentos distintos; membro de grupo admin adicionado há >180 dias sem uso do sistema correspondente; admin local em workstations fora do próprio departamento. IA (Claude) gera sugestão textual por usuário: "João Silva (Analista de Suporte N1) tem 18 grupos a mais que a média do cargo. Candidatos a revisão: [lista com data de adição e sistema associado]." Resultado alimenta campanha de revisão automática ou alerta no canal configurado (F23).

#### Gestão do Ciclo de Vida de Grupos — Alta
Combate o acúmulo de grupos obsoletos que crescem a cada projeto e nunca são removidos. Celery task semanal `analyze_group_health` detecta: **grupos fantasmas** (0 membros ativos ou sem uso em 90 dias — nenhum login no sistema que o grupo autoriza); **grupos duplicados** (similaridade de Jaccard ≥ 0.85 nos conjuntos de membros → IA sugere fusão com lista de membros exclusivos de cada um); **grupos sem owner** (nenhum owner definido ou owner desligado); **aninhamento excessivo** (nesting >3 níveis — impede auditoria de acesso efetiva); **grupos temporários esquecidos** (nome contém "temp", "projeto", "2022", "2023" por regex configurável). `GroupHealthStatus` (group_id, issues: JSONB[], last_analyzed_at, health_score: 0–100). **Expiração automática M365**: grupos com data de expiração configurável (ex: 180 dias); owner recebe aviso 30 dias antes; sem renovação → soft delete por 30 dias → deleção permanente. Dashboard "Saúde dos Grupos": lista com filtro por issue, botão direto de ação (deletar, atribuir owner, iniciar revisão, arquivar).

#### Otimização de Licenças M365 — Alta
ROI financeiro imediato — média de R$ 80–200 desperdiçados por licença/mês sem uso real. Coleta via Graph: `subscribedSkus` (licenças compradas e usadas por SKU), `users/{id}/licenseDetails`, `reports/getM365AppUserDetail(period='D90')` (aplicativos usados por usuário nos últimos 90 dias). **Detecções**: licença E5 com usuário usando apenas Exchange + Teams básico → downgrade seguro para E1 economiza ~R$120/mês; conta desabilitada ainda com licença ativa (offboarding incompleto em F21); múltiplas licenças sobrepostas (E3 + Power BI Pro sendo que E5 já inclui Power BI); licença alocada há >30 dias sem primeiro login. `LicenseWaste` (tenant_id, user_id, current_sku, suggested_sku, monthly_saving_brl, detection_reason, detected_at, status: open/actioned/dismissed). Relatório "Oportunidades de economia": tabela com usuário + licença atual + sugestão + economia mensal em R$. Botão "Iniciar revisão": cria AccessReviewTask para o manager confirmar downgrade. Dashboard: total economizável/mês, total desperdiçado desde início do monitoramento, evolução histórica.

#### Auditoria de Conditional Access Policies — Média
Conditional Access mal configurado é um dos principais vetores de comprometimento em M365. Coleta via Graph `GET /identity/conditionalAccess/policies`. **Detecções de gap**: usuários não cobertos por nenhuma política de MFA (critical) — cruza todos os usuários com as condições de exclusão de cada política; aplicações M365 sem política CA associada (high); políticas em "report-only" há >30 dias (medium — criadas mas nunca ativadas); ausência de bloqueio geográfico quando tenant opera exclusivamente no Brasil (medium); break glass accounts não excluídos corretamente das políticas de MFA (critical — devem ser excluídos do MFA mas não de todas as políticas). `ConditionalAccessGap` (tenant_id, gap_type, affected_users[], affected_apps[], severity, recommendation, detected_at). Score de maturidade CA: 0–100 baseado nas melhores práticas Microsoft Secure Score. Sugestões de melhoria geradas por IA com base no estado atual do ambiente e no perfil de risco do tenant.

#### JIT Access — Acesso Temporário com Aprovação — Alta
Elimina contas com privilégios permanentes desnecessários. Reusa o padrão de aprovação da F33 (`ManagementApprovalRequest`) adaptado para identidade AD/M365. `JitRequest` (tenant_id, requester_id, target_group_id, target_group_name, reason: text min 50 chars, duration_hours: 1/2/4/8/24, status: pending/approved/rejected/active/expired/revoked, approver_id, approved_at, granted_at, expires_at, revoked_at, revoked_by). Fluxo: usuário solicita via UI selecionando grupo elegível + duração + justificativa → approver recebe notificação imediata (Slack + email via F23) com contexto completo → aprovação ou rejeição com comentário → se aprovado: adicionado ao grupo via Graph/ldap3 instantaneamente → Celery beat verifica expiração a cada minuto → ao expirar: remoção automática + notificação ao solicitante. Grupos elegíveis para JIT configuráveis por Admin: default = todos os grupos admin (Domain Admins, Global Admins, Exchange Admins). Grupos de negócio também elegíveis (acesso temporário a SharePoint de RH para investigação). Todo o ciclo hash-chained no audit log (F28). Limite de JIT simultâneos por usuário (default: 1) para evitar bypass por múltiplas solicitações.

#### Integração com PIM (Azure AD P2) — Média
Para tenants com Azure AD P2 ou M365 E5. PIM oferece JIT nativo do Azure — a integração centraliza o estado do PIM no dashboard do Eternity SecOps sem duplicar a funcionalidade. Coleta via Graph: `GET /privilegedAccess/azureAD/roleAssignments` (permanentes vs elegíveis), `GET /privilegedAccess/azureAD/roleAssignmentRequests` (histórico de ativações e suas durações). Detecções: admins com roles **permanentes** que deveriam ser **elegíveis** (best practice Microsoft: zero permanent Global Admins); ativações PIM fora do horário comercial do tenant (timezone configurável); ativações sem ação subsequente nos 30 min seguintes (usuário ativou, não fez nada — possível exploração ou acidente); duração de ativação sempre no máximo configurado (usuário que nunca usa menos → possível aversão ao processo de JIT). `PimActivity` (user_id, role_id, activation_requested_at, activation_justified_reason, duration_requested_h, activated_at, deactivated_at, actions_performed_count). Para tenants sem P2: o JIT nativo da seção anterior cobre a funcionalidade equivalente.

#### Dashboard de Postura de Identidade — Alta
Painel dedicado "Identidade" no menu principal ao lado de Firewall, Servidores e Compliance. Score de maturidade de identidade 0–100 com pesos: % usuários com MFA (25%), % admins sem roles permanentes (20%), campanhas de revisão concluídas no prazo (20%), zero SoD violations críticas abertas (20%), zero contas ativas sem login há >60 dias (15%). Score alimenta o risk score geral do Dashboard Executivo da F24. Cards de resumo: total usuários ativos, contas sem MFA (badge vermelho se qualquer admin), SoD violations abertas por severidade, licenças desperdiçadas em R$/mês, campanhas de revisão com prazo vencido, grupos sem owner. Drill-down: clique em qualquer card abre lista detalhada com ações diretas (revogar, escalar, iniciar campanha). Timeline de eventos de identidade nas últimas 24h: logins suspeitos, roles concedidas/revogadas, grupos modificados, JIT requests. Widget de integração com F35: anomalias de identidade que geraram playbooks SOAR nas últimas 24h.

#### Integração com fases existentes

| Fase | Como integra |
|---|---|
| **F21 — Offboarding** | Ao registrar demissão: revoga automaticamente todos os grupos AD e licenças M365; cria `AccessReviewTask` de verificação final para o manager confirmar que nada foi esquecido |
| **F22 — Onboarding** | Ao criar usuário: atribui `RoleProfile` do cargo como ponto de partida; agenda campanha de revisão de acesso em 90 dias para o manager confirmar que os acessos iniciais ainda fazem sentido |
| **F23 — Alertas** | Novos gatilhos de identidade: conta admin sem MFA, conta ativa sem login há >60 dias, SoD violation crítica detectada, campanha de revisão com prazo vencido, PIM ativado fora do horário |
| **F28 — Audit hash-chain** | Todo o ciclo de JIT, decisões de revisão de acesso e revogações de SoD são auditados com SHA-256 encadeado |
| **F30 — Compliance** | Novo vertical "Identidade" nos compliance packs: CIS AD Benchmark (controles de conta, senha, grupo, admin), BACEN 4.658 Art. 4 (controle de acesso a ambientes críticos), LGPD Art. 46 (medidas técnicas de proteção) |
| **F33 — Governança** | Four-eyes estendido: concessão de Domain Admin ou Global Admin via UI do Eternity SecOps exige segundo aprovador via `ManagementApprovalRequest` com action_type `grant_ad_privileged_role` |
| **F35 — SOAR** | Anomalias de identidade (login de país novo, viagem impossível, volume anômalo de acesso a arquivos) disparam PlaybookRules com actions `suspend_ad_account`, `revoke_jit_access`, `force_mfa_reregistration` |

---

### Fase 37 — Integrador de SIEM e Orquestração de Alertas
*Fechar o loop: SIEM detecta → Eternity SecOps age → SIEM registra resolução*

**Princípio:** O Eternity SecOps NÃO é um SIEM. O cliente já tem Wazuh, Log360, Splunk ou Sentinel. O SIEM detecta e alerta. O Eternity SecOps é a ferramenta que o analista usa DEPOIS do alerta para agir — isolar device, revogar acesso, capturar snapshot, abrir ticket. Esta fase fecha esse loop automaticamente.

#### Conectores de SIEM — Alta
Modelo `SiemConnector` (tenant_id, type: wazuh/splunk/sentinel/log360/qradar/elastic, endpoint, api_key/token Fernet-cifrado, webhook_secret, enabled). Cada conector implementa `normalize_alert(raw_payload) -> SiemAlert` — converte formato nativo do SIEM para schema comum. `SiemAlert` (connector_id, external_id, severity: info/low/medium/high/critical, source_ip, source_device_id, rule_name, description, raw_payload, received_at, status: new/triaging/actioned/closed).

#### Receptor de Webhooks de SIEM — Alta
Endpoint `POST /siem/webhook/{connector_id}` — recebe alertas em tempo real. Valida assinatura HMAC (Wazuh, Splunk HEC, Sentinel Logic Apps, Elastic alerting API). Normaliza para `SiemAlert` e persiste. Para Wazuh: usa integração nativa de webhook já existente no Wazuh Manager. Para Splunk: Splunk Webhook Alert Action apontando para o endpoint.

#### SiemAlert como Gatilho de PlaybookRule — Alta
Novo `trigger_type: siem_alert` nos PlaybookRules. Condições configuráveis: `severity >= HIGH`, `rule_name contains "brute_force"`, `source_ip in managed_devices`. Quando SIEM detecta → Eternity SecOps avalia playbooks → executa ações automaticamente. Exemplo de playbook gerado automaticamente no onboarding: "alerta Wazuh severity=CRITICAL para device gerenciado → snapshot + isolar device + abrir ticket Jira + notificar CISO".

#### Correlação SIEM × Infraestrutura Gerenciada — Alta
Ao receber `SiemAlert` com `source_ip`: cruza com devices gerenciados e identifica device_id, tenant_id, vendor, último snapshot. Enriquece o alerta com contexto: qual firewall, quais regras ativas, qual usuário tem acesso. Resultado exibido no dashboard de alertas com contexto completo em segundos.

#### Resposta de Volta ao SIEM — Alta
Após ação executada (isolamento, revogação, snapshot): posta resultado de volta ao SIEM via API. Fecha o alerta no Wazuh/Splunk com comentário automático incluindo link para o audit log do Eternity SecOps da ação tomada. Para Sentinel: cria comment no incident. Para Splunk: fecha notable event com comment.

#### Dashboard de Alertas SIEM — Média
Feed em tempo real de alertas recebidos de todos os SIEMs configurados. Status por alerta: new / triaging / actioned / closed. Tempo de resposta (triggered_at → actioned_at). MTTR por SIEM, por severidade, por tenant. Histórico pesquisável por device, IP, rule_name.

**SIEMs suportados na launch:** Wazuh (webhook nativo), Microsoft Sentinel (Logic Apps webhook), Elastic SIEM (alerting API), Log360 (webhook), Splunk (REST API HEC).

---

### Fase 38 — Cloud Security Posture Management (CSPM)
*Gerenciar segurança de rede on-premise E cloud em uma plataforma unificada*

**Princípio:** AWS Security Groups, Azure NSGs e GCP Firewall Rules são firewalls. O MSSP que gerencia um Fortinet on-premise do cliente também precisa gerenciar os Security Groups da AWS do mesmo cliente. Esta fase torna isso possível — mesma UX, mesmo agente IA, mesma auditoria.

**O que NÃO está nesta fase:** custo de cloud (FinOps), rightsizing de K8s, billing — esses pertencem a ferramentas FinOps especializadas (CloudSpend, Apptio). O Eternity SecOps gerencia *segurança* de infraestrutura cloud, não custo.

#### AWS Security Groups como Devices — Alta
Conector `aws_security_group.py` via boto3 (IAM Role com permissão mínima: `ec2:DescribeSecurityGroups`, `ec2:AuthorizeSecurityGroupIngress`, `ec2:RevokeSecurityGroupIngress`). Security Groups aparecem como devices no Eternity SecOps com `vendor = aws_security_group`. Agente IA pode consultar regras em linguagem natural ("quais Security Groups permitem SSH de 0.0.0.0/0?") e criar/remover regras ("bloqueia porta 3389 para o SG do servidor de aplicação"). Snapshot de SG = lista de inbound/outbound rules normalizada no mesmo schema das regras de firewall.

#### Azure NSG como Devices — Alta
Conector `azure_nsg.py` via azure-mgmt-network SDK (Service Principal: client_id + client_secret Fernet-cifrado por tenant). NSGs aparecem como devices com `vendor = azure_nsg`. Mesma operação de regras — agente fala "adiciona regra que bloqueia RDP de internet no NSG da subnet de produção".

#### GCP Firewall Rules como Devices — Alta
Conector `gcp_firewall.py` via google-cloud-python (Service Account JSON Fernet-cifrado por tenant). Regras de firewall VPC aparecem como devices com `vendor = gcp_firewall`. Operações via Compute API.

#### View Unificada On-Premise + Cloud — Alta
Dashboard "Infraestrutura" mostra todos os firewalls em uma lista: físicos (Fortinet, SonicWall, pfSense), virtuais (devices em VMware/Proxmox), e cloud (AWS SG, Azure NSG, GCP FW). Filtro por tipo, por vendor, por cloud provider. Busca de regra cross-device: "quais devices têm regra que permite tráfego para 10.0.5.0/24?" — responde cruzando todos os firewalls e SGs.

#### Cloud Misconfiguration Detection — Alta
Mesmos checks de qualidade de regras (F29) aplicados a cloud: SG com porta 22 aberta para 0.0.0.0/0 (CRITICAL), NSG sem logging habilitado (HIGH), GCP FW com `target = all` (HIGH), SG sem description (LOW). Resultados no mesmo dashboard de qualidade de regras. Integração com compliance packs F30: checks CIS AWS Foundations, CIS Azure, CIS GCP.

#### Golden Config para Cloud — Média
Bundles (F26) com suporte a `apply_strategy: cloud_api` além de `cli_ssh` e `rest_api`. Permite criar um bundle "Padrão de segurança de VPC" que aplica regras de baseline em AWS SG + Azure NSG + Fortinet on-premise do mesmo cliente em uma única operação.

---

### Fase 39 — Identidade Self-Service e Automação Proativa
*Extensão natural da governança de identidade (F36) para operações de baixo risco sem analista*

**Princípio:** Algumas operações de identidade são repetitivas, de baixo risco e consomem tempo de analista desnecessariamente (reset de senha, desbloqueio de conta). Automatizá-las dentro do escopo de governança de identidade já estabelecido em F21/F22/F36 é extensão natural do propósito. Esta fase NÃO cria um ServiceDesk — integra com o ServiceDesk existente via F23.

#### Reset de Senha Self-Service — Alta
Portal web leve e separado (não o app principal — URL dedicada como `reset.eternity.io` configurável por tenant via white-label F31). Fluxo: usuário informa email corporativo → OTP enviado por email (6 dígitos, válido 10 min) → usuário confirma OTP → define nova senha (validação de política: tamanho, complexidade) → Eternity SecOps aplica via `ldap3.MODIFY_REPLACE` (AD on-premise) ou `PATCH /users/{id}` (Azure AD Graph API). Evento registrado no audit hash-chain (F28): user_email, timestamp, source_ip, ad_source.

#### Desbloqueio de Conta Self-Service — Alta
Mesmo fluxo OTP → Eternity SecOps executa `userAccountControl` clear lock (AD) ou `POST /users/{id}/revokeSignInSessions` (Azure AD). Registrado no audit. Admin do tenant pode desativar por fonte (só on-premise, só Azure AD, ou ambos).

#### Lembretes Proativos de Expiração — Alta
Celery beat diário `check_password_expiry`: consulta `AdUser` onde `pwdLastSet + maxPwdAge < now + 14 dias`. Envia email personalizado ao usuário com template configurável por tenant: "Sua senha expira em X dias. Clique aqui para renovar antes de ser bloqueado." Link direciona para o portal de reset self-service. Configurable: 14 dias, 7 dias e 1 dia antes da expiração (3 lembretes).

#### Catálogo de Acesso Simplificado — Alta
Usuário final solicita acesso a grupo pré-aprovado (Admin configura quais grupos são elegíveis para solicitação self-service). Formulário: grupo desejado + justificativa mínima 30 chars + data de fim (opcional, para acesso temporário). Solicitação gera `AccessReviewTask` no fluxo F36 para o manager aprovar. Aprovação via email com link direto (sem precisar logar na plataforma). Rejeição com comentário notifica o solicitante por email.

#### Relatórios AD Pré-prontos — Média
Para o Admin do tenant (não usuário final). Relatórios exportáveis em CSV e PDF:

| Relatório | Dados | Frequência sugerida |
|---|---|---|
| Senha expirada | Usuários com senha expirada há >0 dias | Semanal |
| Senha expirando | Usuários com senha expirando em <30 dias | Semanal |
| Contas inativas | Usuários sem login há >60 dias (configurável) | Mensal |
| Membros do grupo | Lista completa de membros de um grupo AD/M365 | Sob demanda |
| Histórico de membros | Quem entrou/saiu de um grupo nos últimos N dias | Sob demanda |
| Admins sem MFA | Domain Admins e Global Admins sem MFA registrado | Semanal |

Complementa os compliance checks automáticos de F30 — esses relatórios são operacionais (para o Admin agir), não de auditoria (para o auditor verificar).

#### Notificação Proativa de Anomalias ao Manager — Média
Quando F36 detecta: conta sem uso há +60 dias, SoD violation, membro novo em grupo crítico — além de alertar via F23, envia email direto ao manager do usuário (campo `manager` do AdUser) com contexto e link para revisão. Manager não precisa logar na plataforma para tomar ação simples (aprovar/rejeitar via link tokenizado no email).

---

### Fase 40-B — AI Assistant Panel (Chat IA)
*Chat em linguagem natural sobre a infraestrutura com memória de sessão e suporte a múltiplos modelos LLM*

**Tabelas:** `assistant_sessions` — id (UUID), tenant_id, user_id, title, model_used, message_count, last_hash, created_at, updated_at. `assistant_messages` — id, session_id, role, content, model, input_tokens, output_tokens, rag_context_used, message_hash, created_at. Hash-chain de mensagens via SHA-256 para integridade do histórico.

**Backend — endpoints REST:**
- `GET /assistant/capabilities` — retorna `openai_available` e `default_model`; detecta se `OPENAI_API_KEY` está configurada
- `POST /assistant/chat` — envia mensagem, cria sessão se `session_id=null`, injeta contexto RAG (F19), retorna `AssistantMessageRead` com tokens e `rag_context_used`
- `GET /assistant/sessions` — lista sessões do usuário autenticado (incluindo pinned e por pasta)
- `GET /assistant/sessions/{id}` — retorna sessão + histórico completo de mensagens
- `DELETE /assistant/sessions/{id}` — remove sessão e mensagens
- `PUT /assistant/sessions/{id}/rename` — atualiza title

**Frontend — dois pontos de entrada:**
- `AssistantPanel` (`components/assistant/AssistantPanel.tsx`) — widget lateral fixo (`right-0 top-0 h-full w-[420px]`), abre via ícone global na navbar; header dark com controles inline
- `AssistantPage` (`pages/AssistantPage.tsx`) — página dedicada `/assistant` com sidebar de pastas + sessões e área de chat completa; suporte a renomear sessão inline

**Seletor de modelo:** Quando `openai_available = true`, exibe dropdown para escolher entre Claude (claude-sonnet-4-6) e GPT-4o. `LLMProvider` abstrato com `AnthropicProvider` e `OpenAIProvider`.

**Indicadores de mensagem:** Badge RAG (`<Database size={9} /> RAG`) quando contexto foi injetado; nome do modelo na bolha de resposta do assistente.

| Arquivo | Conteúdo |
|---|---|
| `backend/migrations/versions/0045_assistant_panel.py` | Tabelas assistant_sessions + assistant_messages |
| `backend/app/api/assistant.py` | Endpoints chat, sessions, capabilities |
| `backend/app/services/assistant_service.py` | `send_message()`, RAG injection, `_ASSISTANT_SYSTEM_TEMPLATE` |
| `backend/app/services/llm_provider.py` | `LLMProvider`, `AnthropicProvider`, `OpenAIProvider`, `openai_available()` |
| `frontend/src/store/assistantStore.ts` | Estado global: sessions, messages, loading, selectedModel |
| `frontend/src/api/assistant.ts` | Mappers + todos os endpoints REST |
| `frontend/src/components/assistant/AssistantPanel.tsx` | Widget lateral |
| `frontend/src/pages/AssistantPage.tsx` | Página dedicada |

---

### Fase 41 — Organização de Sessões: Pastas, Pin e Compartilhamento
*Organização de conversas em pastas pessoais e de equipe com pin e compartilhamento*

**Tabela `assistant_folders`:** id, tenant_id, user_id, name, color (hex #RRGGBB), is_team (boolean), created_at, updated_at.

**Colunas adicionadas em `assistant_sessions`:** `folder_id` (FK → assistant_folders, nullable), `is_shared` (bool default false), `shared_by` (FK → users, nullable), `pinned` (bool default false).

**Novos endpoints REST:**
- `PUT /assistant/sessions/{id}/rename` — atualiza title
- `PUT /assistant/sessions/{id}/move` — move sessão para pasta (`folder_id: uuid | null`)
- `PUT /assistant/sessions/{id}/share` — toggle `is_shared` (sessão aparece para toda a equipe)
- `PUT /assistant/sessions/{id}/pin` — toggle `pinned` (sessão aparece no topo da lista)
- `GET /assistant/sessions/team` — retorna sessões marcadas como `is_shared=true` de todo o tenant, com `user_name` do autor
- `GET /assistant/folders` — lista pastas do usuário + pastas de equipe visíveis
- `POST /assistant/folders` — cria pasta (personal ou team)
- `PUT /assistant/folders/{id}` — renomeia ou muda cor
- `DELETE /assistant/folders/{id}` — remove pasta (sessões ficam sem pasta, não são deletadas)

**Frontend — sidebar de `AssistantPage`:**
- Seções colapsáveis: "Pinned", pastas de equipe, pastas pessoais, "Sem pasta"
- Paleta de 8 cores para pastas (`FOLDER_COLORS`)
- Menu de contexto por sessão: renomear inline, mover para pasta, pin/unpin, compartilhar, excluir
- Sessões de equipe mostram o nome do autor (`user_name`)

---

### Fase 42 — Visibilidade de Pastas por Role
*Controle de visibilidade de pastas de equipe baseado em role RBAC*

**Coluna `min_role`** em `assistant_folders` (VARCHAR(20), NOT NULL, DEFAULT `analyst_n1`).

Pastas de equipe (`is_team = true`) só são retornadas para usuários com role >= `min_role`. Ordem de roles: `analyst_n1 < analyst_n2 < analyst_n3 < manager < admin`. Pastas pessoais não são afetadas — sempre visíveis ao dono.

Permite criar pastas de equipe restritas a N2/N3 (ex: "Investigações de Incidente") que não aparecem para analistas N1.

---

### Fase 40-A — Motor de Conhecimento IA (Knowledge Engine)
*Geração, revisão e publicação de documentação técnica a partir de conversas do assistente IA*

**Princípio:** Cada conversa de suporte contém conhecimento valioso que normalmente se perde. Esta fase captura esse conhecimento, sanitiza dados sensíveis, detecta duplicatas e publica documentação estruturada no BookStack — criando um ciclo contínuo de aprendizado organizacional.

**Ciclo recomendado:** Plano de Ação → executar → validar → Plano de Remediação → publicar → Artigo de Conhecimento

#### Tabela `assistant_doc_drafts` e workflow de estados — Alta

Modelo ORM `AssistantDocDraft` com campos: `id` (UUID), `session_id` (FK), `tenant_id`, `created_by` (user_id), `title`, `content` (Markdown), `status` (`draft` / `approved` / `published` / `rejected`), `doc_type` (`knowledge` / `action_plan` / `remediation`), `review_deadline`, `sanitizer_warnings` (JSONB), `similar_docs` (JSONB), `bookstack_page_id`, `bookstack_page_url`, `created_at`, `updated_at`.

Migrations: `0048_assistant_doc_drafts.py` (tabela base), `0049_doc_draft_similar.py` (campo `similar_docs`), `0050_doc_draft_type.py` (campo `doc_type` com server_default `knowledge`).

Endpoints REST:
- `POST /assistant/sessions/{id}/generate-doc` — gera rascunho com `doc_type` configurável
- `GET /assistant/docs` — lista rascunhos por status
- `PUT /assistant/docs/{id}` — edita título e conteúdo
- `POST /assistant/docs/{id}/approve` — transição draft → approved
- `POST /assistant/docs/{id}/reject` — transição qualquer → rejected
- `POST /assistant/docs/{id}/publish` — publica no BookStack e atualiza status para published; dispara re-indexação RAG

#### DocSanitizer — Alta

`app/services/doc_sanitizer.py` — sanitiza o conteúdo antes de salvar, mascarando dados que não devem aparecer na documentação pública. Padrões detectados: IPs RFC1918 (`10.x`, `192.168.x`, `172.16-31.x`), tokens/hashes hexadecimais longos (>16 chars), passwords em contexto (`password=`, `senha=`, `token=`, `secret=`, `apikey=`), credenciais em URLs (`://user:pass@`).

Cada ocorrência gera um `SanitizerWarning` com `pattern` (tipo detectado) e `excerpt` (trecho mascarado, máx 50 chars). Warnings exibidos no `DocDraftModal` com banner âmbar antes do conteúdo — técnico é avisado e pode editar antes de publicar.

#### Similaridade semântica vs. BookStack — Alta

`_find_similar_docs()` em `doc_publisher.py` — antes de salvar o rascunho, gera embedding do título+conteúdo e faz busca cosine no `bookstack_embeddings` (pgvector). Threshold: `0.75`, retorna top-3 matches.

Cada match retorna `bs_page_id`, `title`, `url` e `similarity` (0.0–1.0). Armazenado em `similar_docs` JSONB. `DocDraftModal` exibe banner laranja listando documentos existentes com percentual de similaridade e link para o BookStack — técnico decide se atualiza um existente ou publica um novo.

#### Extrator e renderizador por tipo de documento — Alta

`app/services/doc_extractor.py` — três prompts Claude distintos e três renderizadores Markdown segundo o `doc_type`:

| Tipo | Prompt foco | Seções Markdown |
|---|---|---|
| `knowledge` | Symptom, diagnosis, resolution, prevention | Sintoma, Diagnóstico, Solução, Prevenção, Referências |
| `action_plan` | Problem statement, scope, timeline, owners, steps | Problema, Escopo, Prazo, Responsáveis, Etapas, Critério de Sucesso |
| `remediation` | Root cause, fix applied, validation, recurrence prevention | Causa Raiz, Solução Aplicada, Validação, Prevenção de Recorrência |

`extract_knowledge(session, messages, doc_type)` retorna dict JSON; `render_markdown(data, session, doc_type)` gera Markdown final com cabeçalho padronizado (data, autor, device).

Títulos default por tipo: `"Documentação Técnica"` / `"Plano de Ação"` / `"Plano de Remediação"`.

#### DocDraftModal — Alta

`frontend/src/components/assistant/DocDraftModal.tsx` — modal de revisão completa do rascunho:

- Header com `DocTypeBadge` (ícone + label colorido por tipo) e `StatusBadge`
- Banner âmbar: warnings do DocSanitizer (padrão + excerpt por hover)
- Banner laranja: documentos similares no BookStack com score e link direto
- Visualização do conteúdo Markdown como `<pre>` monoespaçado
- Modo edição inline: campos título e textarea de conteúdo
- Rodapé de ações: **Editar**, **Rejeitar** (vermelho), **Aprovar** (verde, só no draft), **Publicar no BookStack** (brand)
- Estado publicado: link direto para a página no BookStack

#### Toggle de modo de chat: Infraestrutura vs. Tecnologia Geral — Alta

`backend/app/services/assistant_service.py` — novo parâmetro `mode: str = "infrastructure"` em `send_message()`:

- `"infrastructure"`: usa `_ASSISTANT_SYSTEM_TEMPLATE` com injeção RAG (contexto dos documentos indexados)
- `"general"`: usa `_GENERAL_SYSTEM_TEMPLATE` com cobertura ampla de TI — redes, servidores, telefonia IP (VoIP, PABX, ramais SIP, softphones como Mesa Virtual Intelbras), cloud, virtualização, segurança; sem injeção RAG (`rag_context_used = False`)

`frontend/src/store/assistantStore.ts` — campo `chatMode: "infrastructure" | "general"` e action `setChatMode`.

`AssistantChatRequest` aceita `mode: str = "infrastructure"` e repassa ao service.

#### Dropdowns inline nos painéis — Média

Componente `PanelSelect` em `AssistantPanel.tsx` (dark header) e `SelectControl` em `AssistantPage.tsx` (light header) — `<select>` nativo com `appearance-none`, ícone absoluto esquerdo e chevron SVG direito.

Três controles no header:
1. **Modo** (Infra / Geral) — roxo quando Geral, cinza quando Infra; ícone `Shield` / `Globe`
2. **Tipo de doc** (Artigo / Pl. Ação / Remediação) — visível apenas quando há sessão+mensagens; ícone `FileText`
3. **LLM** (Claude / GPT-4o) — visível apenas quando `openai_available`; ícone `Bot`

Botão **Gerar** ao lado do tipo de doc dispara `handleGenerateDoc(selectedDocType)` diretamente, sem modal intermediário de seleção.

| Arquivo | Alteração |
|---|---|
| `backend/app/services/assistant_service.py` | `_GENERAL_SYSTEM_TEMPLATE`, `mode` param, skip RAG |
| `backend/app/services/doc_publisher.py` | `generate_draft(doc_type)`, prompts e renderers por tipo |
| `backend/app/services/doc_extractor.py` | `extract_knowledge()`, `render_markdown()` por tipo |
| `backend/app/services/doc_sanitizer.py` | mascaramento + SanitizerWarning[] |
| `backend/app/api/assistant.py` | `AssistantChatRequest.mode` |
| `backend/app/api/assistant_docs.py` | `GenerateDocRequest`, `DocDraftRead.doc_type`, endpoints |
| `backend/migrations/versions/0048_*` | tabela base assistant_doc_drafts |
| `backend/migrations/versions/0049_*` | campo similar_docs |
| `backend/migrations/versions/0050_*` | campo doc_type |
| `frontend/src/store/assistantStore.ts` | `chatMode`, `setChatMode` |
| `frontend/src/api/assistant.ts` | `DocDraft.doc_type`, `generateDoc(docType)`, `chat(mode)` |
| `frontend/src/components/assistant/AssistantPanel.tsx` | `PanelSelect`, 3 dropdowns, `handleGenerateDoc` |
| `frontend/src/components/assistant/DocDraftModal.tsx` | modal completo, `DocTypeBadge`, `StatusBadge` |
| `frontend/src/components/assistant/DocTypeSelector.tsx` | seletor modal (criado, substituído por dropdown inline) |
| `frontend/src/pages/AssistantPage.tsx` | `SelectControl`, 3 dropdowns, `selectedDocType`, `chatMode` |

---

### Fase 25 (Histórico) — Plataforma Enterprise e Marketplace
*Implementado: white-label, API keys, Cisco ASA/Palo Alto/Check Point*

| Funcionalidade | Detalhe |
|---|---|
| SSO | SAML 2.0 / OIDC — Azure AD, Okta, Google Workspace |
| RBAC granular | Permissões por cliente/dispositivo/operação (além dos 3 roles atuais) |
| API pública | OpenAPI 3.1 documentada — permite integrações externas e automações |
| White-label | Logo, cores e domínio customizados por tenant (revenda MSSP) |
| Multi-idioma | i18n/l10n — pt-BR ✅, en-US, es-LA |
| Billing | Planos, limites de devices, cobrança automatizada por tenant |
| Vendors enterprise | Cisco ASA/FTD, Palo Alto PAN-OS, Check Point R80+, Juniper SRX |
| Marketplace | Plugins de vendor contribuídos por comunidade / parceiros |

---

### Fase 26 — Golden Config Avançado: Template Bundles REST-native
*Implantação completa de filial com 1 clique — base + regras + filtro web + geo-IP + VPN*

**Contexto:** A Fase 17 faz Golden Config via CLI SSH (hostname, VLANs, interfaces, rotas). A Fase 26 estende para políticas de segurança completas gerenciadas via REST API nos firewalls modernos.

#### Modelo de dados

```
GoldenBundle
├── id, tenant_id, name, description, vendor
├── variables: JSONB          (variáveis globais do bundle)
└── sections: [BundleSection] (ordenadas por apply_order)

BundleSection
├── section_type: base_config | objects | access_rules | content_filter | geo_ip | vpn | sd_wan
├── template_id → GoldenTemplate   (CLI — Fase 17)
├── rest_payload_template: Text    (JSON com {VARIÁVEIS} para REST-native)
├── apply_strategy: cli_ssh | rest_api | manual_only
├── apply_order: int
└── rollback_strategy: snapshot_restore | delete_objects | none
```

**Herança de variáveis:** Bundle → Tenant → Device (device sempre sobrescreve)

#### Estratégias por vendor e seção

| section_type | Fortinet | SonicWall | pfSense | Sophos |
|---|---|---|---|---|
| base_config | CLI SSH | CLI SSH | CLI SSH | CLI SSH |
| objects | REST `/cmdb/firewall/address` | REST API | — | REST API |
| access_rules | REST `/cmdb/firewall/policy` | REST API | pfctl | REST API |
| content_filter | REST `/cmdb/webfilter/profile` | CFS REST | pfBlockerNG | REST API |
| geo_ip | REST `/cmdb/firewall/country` | Geo-IP REST | pfBlockerNG | REST API |
| vpn | REST `/cmdb/vpn.ipsec/phase1` | REST API | CLI SSH | REST API |
| sd_wan | REST `/cmdb/system/virtual-wan-link` | — | — | — |

#### Fluxo de aplicação

```
1. Snapshot automático pré-apply (fallback garantido)
2. Para cada seção (order_by apply_order):
   cli_ssh     → SSH + comandos CLI (executor Fase 17)
   rest_api    → FortinetRestConnector / SonicWallRestConnector
   manual_only → gera preview + aguarda aprovação humana
3. Falha em qualquer seção → rollback pela rollback_strategy da seção
4. Audit log imutável: seção, payload, resposta, status
```

#### Componentes a implementar

**Backend:** `golden_bundle.py` (model), `bundle_renderer.py`, `fortinet_rest_connector.py`, `sonicwall_rest_connector.py`, `bundle_worker.py` (Celery), `api/golden_bundle.py`

**Frontend:** `BundleEditor` (wizard), `BundleLibrary`, `BundleApplyModal` (polling), `BundleDiffView`

**Biblioteca embutida "Filial Padrão Fortinet":**
```
[1] base_config   → CLI: hostname, VLANs, interfaces, rotas
[2] objects       → REST: addr-objects RFC1918, DNS, trusted-nets
[3] access_rules  → REST: LAN→WAN allow, LAN→LAN isolado, WAN→all deny
[4] content_filter→ REST: webfilter (bloqueia P2P, adult, malware)
[5] geo_ip        → REST: bloqueia países de alto risco (lista por tenant)
[6] vpn           → REST: IPSec site-to-site ({PEER_IP}, {PSK}, {SUBNET})
```

---

### Fase 27 — Planejamento de Migração de Infraestrutura (VM Migration Planner)
*Planejamento assistido por IA — read-only, sem execução automatizada*

- Conectores read-only: VMware vCenter API, Proxmox API, Hyper-V (WinRM)
- Inventário de VMs: OS, CPU/RAM/disco, serviços em execução, dependências de rede
- Análise de dependências: mapa de comunicação entre VMs, ordem de migração sugerida
- IA gera runbook: sequência, janelas de manutenção, estratégia de rollback
- Export automático para BookStack

---

### Fase 47 — Chat IA: Guia da Plataforma ✅
*Modo de chat dedicado para o super admin descobrir como usar qualquer módulo da plataforma*

**Princípio:** O Eternity SecOps tem 20+ módulos. Um super admin que quer entender como resolver um problema específico usando a plataforma precisa de um guia que conheça todos os caminhos — menu, aba, botão, formulário — sem precisar consultar documentação externa.

#### Implementado

| Componente | Detalhe |
|---|---|
| `_PLATFORM_GUIDE_TEMPLATE` | System prompt com mapa completo de todos os módulos: caminho de navegação exato, funcionalidades disponíveis, fluxos de trabalho. Cobre: Dispositivos, Operações, Snapshots, Migração de Regras, Golden Config, Base de Conhecimento IA, AI Assistant, DLP, GLPI, Firmware/CVEs, Governança de Identidade, Self-Service de Identidade, SOAR/Playbooks, Threat Intelligence, SIEM, Cloud Security (CSPM), Infraestrutura de Segurança, Edge Agents/SSO, Produto/Billing, Organização/Alertas, Dashboard Executivo, Painel MSSP |
| Guard 403 em `POST /assistant/chat` | `if data.mode == "platform" and not ctx.user.is_super_admin → HTTP 403` — não super admin recebe Forbidden |
| `send_message(mode="platform")` | Usa `_PLATFORM_GUIDE_TEMPLATE`, sem RAG (`rag_context_used = False`) |
| `chatMode: "platform"` | Adicionado ao tipo no `assistantStore.ts` |
| Seletor de modo — `AssistantPanel.tsx` | Opção "Guia" com ícone `BookOpen` visível apenas quando `user.is_super_admin = true` |
| Seletor de modo — `AssistantPage.tsx` | Opção "Guia da Plataforma" com ícone `BookOpen`, restrita a super admin |
| Empty state e placeholder | Textos específicos para o modo Guia: "Como faço para… na plataforma?" |

**Restrição de acesso:** Exclusivo para super admins. Para liberar para outros perfis, remover o `isSuperAdmin &&` no frontend e o guard 403 no backend.

**Sem migration:** Nenhuma tabela nova — reutiliza completamente a infraestrutura existente do AI Assistant (sessions + messages).

| Arquivo | Alteração |
|---|---|
| `backend/app/services/assistant_service.py` | `_PLATFORM_GUIDE_TEMPLATE` + `is_platform` branch em `send_message()` |
| `backend/app/api/assistant.py` | Guard 403 para `mode="platform"` sem `is_super_admin` |
| `frontend/src/store/assistantStore.ts` | `chatMode` type inclui `"platform"` |
| `frontend/src/components/assistant/AssistantPanel.tsx` | Opção "Guia" condicional a `isSuperAdmin`, ícone `BookOpen` |
| `frontend/src/pages/AssistantPage.tsx` | Opção "Guia da Plataforma" condicional, empty state e placeholder específicos |

---

## Novos Vendors — Priorização

| Vendor | Categoria | Fase alvo | Prioridade | Status |
|---|---|---|---|---|
| Cisco ASA/FTD | Firewall | 25 | Alta | Pendente |
| Palo Alto PAN-OS | Firewall | 25 | Alta | Pendente |
| Check Point R80+ | Firewall | 25 | Alta | Pendente |
| Juniper SRX | Firewall | 25 | Média | Pendente |
| Huawei USG | Firewall | 25+ | Média | Pendente |
| TP-Link | Switch | 27+ | Baixa | Pendente |
| D-Link | Switch | 27+ | Baixa | Pendente |

**Implementados:** Sophos ✅ (F16), Intelbras/Juniper EX/Aruba ✅ (F15), HP Comware ✅ (F12), Dell N-Series ✅ (F11)

---

## Mapa de Dependências

```
Fase 1-13 (base)         ──► todas as fases subsequentes
Fase 14 (servidores)     ──► F20 (DBs) ──► F21 (offboard) ──► F22 (onboard)
Fase 15 (switches)       ──► F16 (firewall migration)
Fase 13 (variáveis)      ──► F17 (golden config) ──► F26 (bundles REST)
pgvector                 ──► F19 (RAG)
F21 + F22 (identidade)   ──► F23 (alertas: gatilhos offboard/onboard)
F21-23                   ──► F24 (dashboard executivo)
F24                      ──► F25 (enterprise/marketplace)
F26 pode rodar em paralelo com F25 (extensão vertical de F17)
F27 pode rodar em paralelo com F25-26 (módulo independente)

F28 (segurança + IA safety)  ──► F33 (governança IA) ──► F35 (SOAR)
F28 (hash-chained audit)     ──► F33 (ancoragem RFC 3161)
F29 (AI observability)       ──► F33 (red team + SIRP)
F29 (multi-agente)           ──► F37 (agente SIEM usa IdentityAgent + FirewallAgent em resposta)
F31 (RBAC granular)          ──► F33 (four-eyes + aprovação dupla)
F34 (infra segurança)        pode rodar em paralelo com F33
F35 (SOAR) depende de F23 (alertas) + F33 (SIRP) + F34 (infra)
F35 (PlaybookRules)          ──► F37 (trigger_type: siem_alert alimenta os playbooks)

F21 + F22 (identidade)       ──► F36 (governança AD/M365: reutiliza conectores AD/Graph)
F23 (alertas)                ──► F36 (canal de notificação para campanhas e anomalias)
F28 (audit hash-chain)       ──► F36 (toda decisão de revisão e revogação auditada)
F33 (four-eyes)              ──► F36 (JIT approval e grant_ad_privileged_role)
F35 (SOAR)                   ──► F36 (playbooks disparam por anomalias de identidade)
F36 pode rodar em paralelo com F29-F35 (módulo independente de identidade)

F23 (alertas/webhook)        ──► F37 (SiemConnector reutiliza infra de webhook de F23)
F35 (PlaybookRules)          ──► F37 (siem_alert como novo trigger_type)
F37 pode rodar em paralelo com F36 (módulo independente de integração)

F6 + F25 (vendors firewall)  ──► F38 (mesmo padrão de connector, novos vendors cloud)
F17 + F26 (Golden Config)    ──► F38 (bundles com apply_strategy: cloud_api)
F29 (qualidade de regras)    ──► F38 (mesmos checks aplicados a SG/NSG/GCP FW)
F38 pode rodar em paralelo com F36-F37 (módulo independente de cloud)

F21 + F22 (lifecycle)        ──► F39 (reutiliza conectores AD/Graph para reset/unlock)
F36 (access certification)   ──► F39 (catálogo de acesso gera AccessReviewTask de F36)
F28 (audit hash-chain)       ──► F39 (reset/desbloqueio auditados)
F31 (white-label)            ──► F39 (portal self-service com domínio e branding do tenant)
F39 depende de F36 para catálogo de acesso (AccessReviewTask)
```
