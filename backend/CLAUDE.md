# FireManager Backend — Contexto Técnico

## Estrutura principal

```
backend/app/
├── api/           # Routers FastAPI (devices, operations, audit, inspect, bookstack, ...)
├── agent/         # Agente IA (Claude) — geração de planos e documentação
├── connectors/    # Um arquivo por vendor (sonicwall, fortinet, sonicwall_ssh, ssh, ...)
│   └── factory.py # get_connector() e get_ssh_connector() — porta de entrada
├── models/        # SQLAlchemy ORM
├── schemas/       # Pydantic v2
├── services/      # Lógica de negócio (operation_service, bookstack_service, ...)
└── workers/       # Celery tasks (health_check, snapshot)
```

---

## Conectores — Regras por Vendor

### factory.py — como usar

```python
from app.connectors.factory import get_connector, get_ssh_connector, CLI_VENDORS

# REST vendors (SonicWall, Fortinet, pfSense, OPNsense, MikroTik, Endian)
connector = get_connector(device)

# SSH/CLI vendors (HP Comware, Dell N, Cisco, Juniper, Aruba, Ubiquiti)
connector = get_ssh_connector(device)

# Verificar se vendor é CLI-only:
if device.vendor in CLI_VENDORS:
    # use get_ssh_connector
```

**`CLI_VENDORS`** = hp_comware, dell_n, cisco_ios, cisco_nxos, juniper, aruba, dell, ubiquiti

---

### SonicWall (sonicwall.py + sonicwall_ssh.py)

**REGRA MAIS IMPORTANTE:** SonicWall permite apenas **UMA sessão de gerenciamento por vez**.
- REST com `override=True` ocupa a sessão e **bloqueia SSH**
- SSH deve rodar SEMPRE **antes** de abrir a sessão REST
- Ver `bookstack_service._collect_live_data` — SSH roda antes do `get_connector()`

**Auth:** Digest Auth obrigatório (não Basic). `POST /api/sonicos/auth` com `--digest`.

**Versionamento:**
- SonicOS 6.x e 7.x têm **formatos de payload completamente diferentes**
- Detectar versão no `test_connection`, salvar em `device.firmware_version`
- `int(firmware_version.split(" ")[1].split(".")[0])` extrai major version

**Fluxo de sessão REST:**
1. `POST /api/sonicos/auth` (Digest) → cookie
2. Operações com cookie
3. `POST /api/sonicos/config/pending` → commit obrigatório (especialmente v7, config fica pendente)
4. `DELETE /api/sonicos/auth` → logout

**Endpoints que retornam HTTP 400 (não existem via REST — usar SSH):**
- `show content-filter` → `sonicwall_ssh.execute_show_commands_full(["show content-filter"])`
- `show app-rules` → `sonicwall_ssh.execute_show_commands(["show app-rules"])`
- `show gateway-antivirus`, `show anti-spyware`, `show intrusion-prevention`, etc.

**Paginação SSH:** `show content-filter` tem múltiplas páginas com `--MORE--`.
Usar `execute_show_commands_full()` que envia espaço a cada `--MORE--`.

**SonicOS 7 — formato de rules:**
```python
# v7 — access_rules tem wrapper
{"access_rules": [{"ipv4": {"name": "...", "action": "allow", ...}}]}
# v6 — direto
{"access_rules": [{"name": "...", "action": "allow", ...}]}
```

**Address objects (v7):**
- Para host /32: `{"host": {"ip": "x.x.x.x"}}` (não `network`)
- Para rede: `{"network": {"subnet": "x.x.x.x", "mask": "255.255.255.0"}}`

**CFS Policy source:**
- Só aceita `any` ou `address-group` — nunca address-object direto
- Palavra `group` obrigatória: `source address included group fm-grp-X`

**Normalização de ações:**
```python
ACTION_MAP = {"accept": "allow", "permit": "allow", "drop": "discard", "reject": "deny"}
```

---

### Fortinet (fortinet.py)

**Auth:** API token no header. Credenciais: `{"token": "...", "vdom": "root"}`.

**VDOM null:** Usar `creds.get("vdom") or "root"` — nunca `creds.get("vdom", "root")` pois se a chave existe com valor `null`, o default não é usado.

**Campos obrigatórios em toda policy:**
- `"schedule": "always"` — sem esse campo, HTTP 400

**Interfaces:** Case-sensitive. `"LAN"` ≠ `"lan"`. Fazer lookup case-insensitive antes de enviar payload.

**`spec.extra`:** Não usar `payload.update(spec.extra)` diretamente. Campos inválidos causam HTTP 403.

**Métodos abstratos:** Se `BaseConnector` ganhar novos métodos abstratos, implementar em TODOS os connectors (Fortinet foi o que mais sofreu com isso).

---

### HP Comware (ssh.py — HPComwareConnector)

- CLI: `system-view` (não `configure terminal`), `quit` (não `exit`)
- Salvar config: `save force`
- Display: `display current-configuration`
- Netmiko driver: `hp_comware`
- **CRÍTICO:** `send_config_set(exit_config_mode=False)` — Netmiko usa `exit` por padrão, mas Comware usa `quit`

---

### Dell N-Series DNOS6 (ssh.py — DellNConnector)

- Vendor separado de `dell` (OS10) — implementado como `dell_n`
- CLI diferente de Dell OS10
- STP: `spanning-tree mode rstp`, `spanning-tree bpdu-protection`

---

### Fortinet vs SonicWall — health check

**SonicWall:** `GET /api/sonicos` (raiz pública, não requer auth)
**Fortinet:** `GET /api/v2/monitor/system/status` com token

**Não usar** `/api/sonicos/version` sem auth para health check — retorna E_UNAUTHORIZED sem info útil.

---

## SQLAlchemy — Armadilhas

### MissingGreenlet após flush()

```python
# ❌ Causa MissingGreenlet
await db.flush()
return schema_from_orm(objeto)  # acessa updated_at → lazy load fora do contexto

# ✅ Correto
await db.flush()
await db.refresh(objeto)  # recarrega atributos expirados
return schema_from_orm(objeto)
```

Campos `onupdate=func.now()` são **expirados** pelo SQLAlchemy após flush. Sempre fazer `refresh` antes de serializar.

---

## Celery Workers

```
celery_worker: executa tasks (health_check, snapshots)
celery_beat: agenda tasks periódicas
```

Health check usa `get_ssh_connector` para CLI vendors e `get_connector` para REST vendors.
Ver `app/workers/health_check.py` — `CLI_VENDORS` check obrigatório.

---

## BookStack Integration (bookstack_service.py)

**Ordem de coleta para SonicWall** (SSH antes do REST — regra da sessão única):
1. `_collect_ssh_resources(device, data)` → security_services, content_filter_ssh, app_rules_ssh
2. `get_connector(device)` → rules, nats, routes, extended_snapshot

**Rendering em `_build_snapshot_md`:** Chaves SSH (`content_filter_ssh`, `app_rules_ssh`, `security_services`) têm prioridade sobre chaves REST (`content_filter`, `app_rules`, `security_settings`).

---

## Servidores — Módulo de Análise (read-only)

O módulo de servidores é analítico — NÃO executa comandos de modificação. Apenas leitura:
- SSH Linux: ps, df, free, journalctl, netstat, uptime
- WinRM: Windows Server
- Zabbix JSON-RPC: v6.x (token no body) vs v7.x (Bearer header) — versão por tenant
- Wazuh REST API: v4.x/v5.x com JWT

---

## Importações circulares

Evitar imports no nível de módulo entre services. Usar imports lazy (dentro da função) quando há risco de circular import. Exemplo em `bookstack_service.py`:
```python
async def _collect_ssh_resources(device, data):
    from app.connectors.factory import get_ssh_connector      # import lazy
    from app.api.inspect import _parse_named_blocks           # import lazy
    from app.services.operation_service import _parse_security_status  # import lazy
```

---

## Fases implementadas

### Cadeia de migrations completa
`0051` → `0052` → `0053` → `0054` → `0055` → `0056` → `0057` → `0058` → `0059` → `0060` → `0061` (F30) → `0062` (F33) → `0063` (F39.cont) → `0064` (F34) → `0065` (F31) → `0066` (F32) → `0067` (F28.1 DLP) → `0068` (F23.ext RMM) → `0069` (F31.cont SSO role mapping) → `0070` (F36.ext file share) → `0071` (F37.ext CEF syslog) → `0072` (F49 GLPI widget) → `0073` (F32.cont Stripe)

### F29 — Multi-Agent Orchestrator
| Arquivo | Descrição |
|---|---|
| `migrations/0052_f29_ai_observability.py` | `ai_interactions`, `ai_token_usage`, `orchestration_runs`, `confidence_score` em operations |
| `app/agent/sub_agents/base.py` | `AgentHandoff` dataclass + `BaseSubAgent` ABC |
| `app/agent/sub_agents/identity_agent.py` | `IdentityAgent` — tool registry, write/read dispatch, LLM intent parsing |
| `app/agent/sub_agents/firewall_agent.py` | `FirewallAgent` — delega ao agente IA existente |
| `app/agent/sub_agents/network_agent.py` | `NetworkAgent` — análise de conectividade |
| `app/agent/orchestrator.py` | `MultiAgentOrchestrator` — confidence threshold 0.70, parallel execution |
| `app/api/orchestrator.py` | `POST /orchestrate` |

### F36 — Identity Governance
| Arquivo | Descrição |
|---|---|
| `migrations/0053_f36_identity_governance.py` | 9 tabelas: connectors, ad_users, ad_groups, memberships, sod_rules, violations, campaigns, review_tasks, jit_requests |
| `app/models/identity_governance.py` | ORM models para todas as tabelas F36 |
| `app/services/ad_governance_service.py` | AD Tool Kit: read + write tools, JIT, SoD, seed_builtin_sod_rules |
| `app/services/local_ad_service.py` | Adicionado: enable_user, reset_password, remove_user_from_group, get_group_members, list_groups |
| `app/api/identity_governance.py` | CRUD connectors, AD ops, SoD, JIT, campanhas |
| `app/workers/identity_sync.py` | `identity_sync.sync_connector`, `identity_sync.expire_jit`, `identity_sync.check_sod_all` |

**5 regras SoD embutidas:** Contas a Pagar + Aprovação Financeira (critical), Domain Admins + sistema financeiro (critical), Help Desk + Domain Admins (high), Auditoria + Admins (high), RH Folha + Global Admin (critical).

### F39 — Self-Service de Identidade
| Arquivo | Descrição |
|---|---|
| `migrations/0054_f39_self_service.py` | Tabela `otp_requests` |
| `app/services/self_service_identity.py` | OTP SHA-256, TTL 10min, reset_password, unlock_account |
| `app/api/self_service.py` | `POST /identity/self-service/otp/request`, `/password/reset`, `/account/unlock` |
| `app/workers/expiry_reminders.py` | `expiry_reminders.check_password_expiry` — lembretes 14/7/1 dias |

### F35 — SOAR Playbooks
| Arquivo | Descrição |
|---|---|
| `migrations/0055_f35_soar.py` | Tabelas `playbook_rules`, `playbook_executions`, `threat_indicators` |
| `app/models/playbook.py` | ORM: `PlaybookRule`, `PlaybookExecution`, `ThreatIndicator` |
| `app/services/soar_service.py` | `evaluate_trigger`, `_condition_matches`, `_in_cooldown`, `get_mttr_stats`, `seed_ad_templates` |
| `app/api/playbooks.py` | CRUD + `/templates/seed` + `/{id}/trigger` + `/{id}/executions` + `/stats/mttr` |
| `app/workers/playbook_evaluator.py` | `soar.execute_playbook_actions`, `soar.evaluate_scheduled_triggers` |

**5 templates AD:** offboarding_imediato, conta_comprometida, jit_abuso, violacao_sod, device_unreachable_ad.

**7 action types:** notify_slack, notify_email, escalate_to_n2, ad_disable_user, revoke_jit_access, run_snapshot, create_ticket_jira.

### Celery beat tasks registradas (celery_app.py)
| Task name | Schedule | Descrição |
|---|---|---|
| `soar.evaluate_scheduled_triggers` | `* * * * *` | Avalia triggers agendados |
| `identity_sync.expire_jit` | `* * * * *` | Revoga JIT expirados |
| `identity_sync.check_sod_all` | `0 1 * * *` | Scan SoD todos os tenants |
| `expiry_reminders.check_password_expiry` | `0 8 * * *` | Lembretes de senha expirando |

### F34 — Infraestrutura de Segurança Avançada (config store)
| Arquivo | Descrição |
|---|---|
| `migrations/0064_f34_security_infra.py` | `vault_configs`, `vault_secret_refs`, `opa_policies`, `opa_evaluations`, `security_profiles`, `pentest_schedules` |
| `app/models/security_infra.py` | ORM: `VaultConfig`, `VaultSecretRef`, `OpaPolicy`, `OpaEvaluation`, `SecurityProfile`, `PentestSchedule` |
| `app/services/security_infra_service.py` | `seed_builtin_policies` (3 políticas Rego), `evaluate_policy`, `_evaluate_rego_simple` (simulação local) |
| `app/api/security_infra.py` | CRUD vault-configs + secrets, opa-policies (+ /seed + /{id}/evaluate), security-profiles (+ /{id}/apply), pentest-schedules |

### F31 — Edge Agents, SSO, Marketplace, RBAC
| Arquivo | Descrição |
|---|---|
| `migrations/0065_f31_edge_agents.py` | `edge_agents`, `sso_configs`, `marketplace_plugins`, `tenant_plugins`, `rbac_custom_roles`, `rbac_role_assignments` |
| `app/models/edge_agents.py` | ORM: `EdgeAgent`, `SsoConfig`, `MarketplacePlugin`, `TenantPlugin`, `RbacCustomRole`, `RbacRoleAssignment` |
| `app/services/edge_agent_service.py` | `generate_agent_token` (SHA-256), `create_agent`, `seed_marketplace_plugins` (5 built-in), `install_plugin` |
| `app/api/edge_agents.py` | CRUD /agents, PUT /sso (upsert), /marketplace (+ /seed + /installed + /{id}/install + /{id}/uninstall), /rbac-roles, /rbac-assignments |

**5 plugins built-in:** fortinet-fortigate, sonicwall-sonicos, wazuh-siem, lgpd-compliance, executive-risk-dashboard.

### F32 — Produto: Billing, Onboarding, Help Center, Preferências
| Arquivo | Descrição |
|---|---|
| `migrations/0066_f32_product.py` | `billing_plans`, `billing_subscriptions`, `billing_invoices`, `onboarding_checklists`, `help_articles`, `user_preferences` |
| `app/models/product.py` | ORM: `BillingPlan`, `BillingSubscription`, `BillingInvoice`, `OnboardingChecklist`, `HelpArticle`, `UserPreference` |
| `app/services/product_service.py` | `seed_plans` (3 planos), `seed_articles` (4 artigos), `get_or_create_checklist`, `complete_step`, `get_or_create_preferences`, `create_subscription` |
| `app/api/product.py` | /billing/plans (+ /seed), /billing/subscription (+ /start), /billing/invoices, /onboarding/checklist (+ /complete-step + /skip), /help/articles (+ /seed + /{slug}), /preferences |

**3 planos:** Starter (R$490, 10 devices), Pro (R$1490, 50 devices), Enterprise (R$3490, unlimited).

### F28.1 — DLP ✅ (completo)
| Arquivo | Descrição |
|---|---|
| `migrations/0067_dlp.py` | `dlp_configs` (unique por tenant), `dlp_rules` (UniqueConstraint tenant+rule_key), `dlp_incidents` |
| `app/models/dlp.py` | ORM: `DLPConfig`, `DLPRule`, `DLPIncident` |
| `app/services/dlp_service.py` | 20 regras builtin (6 pii_br, 8 credentials, 6 infra_mssp) + validate_docbr CPF/CNPJ; `scan_text()`, `scan_message()`, `seed_builtin_rules()`, `log_incidents()`; mascaramento `[DLP:RULE:hash8]` |
| `app/api/dlp.py` | GET/PUT /config (compliance_mode), GET/POST /rules, PUT/DELETE /rules/{id} (builtin não deletável), GET /incidents |
| `app/api/operations.py` | Hook DLP em `chat_with_agent` e `continue_chat` |
| `app/api/assistant.py` | Hook DLP em `chat`; bloqueia (HTTP 400 type=dlp_block) se `has_blocks`; mascara texto se warns |
| `frontend/src/api/dlp.ts` | Client TypeScript tipado completo |
| `frontend/src/pages/Organisation.tsx` | Aba DLP: config/regras/incidentes integrados na página de Organização |

### Rotas registradas (main.py)
| Prefix | Router | Tags |
|---|---|---|
| `/orchestrate` | `orchestrator.router` | orchestrator |
| `/identity-governance` | `identity_governance.router` | identity-governance |
| `/identity/self-service` | `self_service.router` | self-service |
| `/playbooks` | `playbooks.router` | playbooks |
| `/security-infra` | `security_infra.router` | security-infra |
| `/platform` | `edge_agents.router` | edge-agents |
| `/product` | `product.router` | product |
