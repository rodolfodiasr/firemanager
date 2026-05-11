# FireManager — Guia de Contexto para Claude Code

## O que é este projeto

FireManager é uma plataforma MSSP (Managed Security Service Provider) para gestão centralizada de firewalls com IA. Backend FastAPI/Python, frontend React/TypeScript, PostgreSQL + pgvector, Celery/Redis, Docker Compose.

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
| 25 | Plataforma Enterprise | API Keys, White-label branding, Cisco ASA + Palo Alto + Check Point connectors; migração 0038 | ✅ |
| 26 | Golden Config Bundles REST | GoldenBundle + BundleSection + BundleApply; BundleRenderer; FortinetRestApply; Celery worker; migração 0039 | ✅ |
| 27 | VM Migration Planner | VMware vCenter + Proxmox read-only; inventory sync; runbook IA (Claude); migração 0040 | ✅ |
| 28 | Segurança Avançada e Resiliência | Denylist catastróficos, pre-snapshot, preview CLI, read_only_agent, JWT 15 min, audit hash-chain, SSRF guard | ✅ (parcial) |

---

### Próximas Fases

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

#### Análise de qualidade de regras — Alta
Celery task `analyze_rule_quality(device_id)` executa após cada snapshot e detecta: regras duplicadas (mesmo src/dst/svc/action), shadow rules (regra nunca alcançada porque outra mais ampla vem antes na lista), regras `any/any allow` (abre tudo), regras disabled há >90 dias (candidatas a remoção), regras sem hit count em 30 dias (se vendor reporta hit count). Resultado salvo em campo `quality_issues: JSONB` no snapshot. Dashboard: badge "X issues" na listagem de devices; modal com lista de problemas e sugestão de correção textual.

#### Diagnóstico de qualidade de link — Média
Celery beat ICMP probe a cada 5 min para cada device: registra RTT e packet loss em `link_quality_history` (device_id, timestamp, rtt_ms, packet_loss_pct). Alerta automático (canal F23) se RTT > 3× média dos últimos 7 dias ou packet loss > 5%. Exporta métricas para Prometheus (gauge `device_rtt_ms`, counter `device_packet_loss_pct`) → visível no Grafana existente (F24). Gráfico histórico no detalhe do device: 24h, 7d, 30d.

---

### Fase 30 — Compliance Enterprise e Continuidade de Negócio
*Pacotes regulatórios, documentação legal, SLA formal e disaster recovery*

**Origem:** Mesa Redonda Rounds 1, 2 e 3 — Flávia (Compliance), Patrícia (Privacidade), Augusto (LGPD), Eduardo (BC/DR), Mônica (SLA)

#### Compliance packs por vertical — Alta
Modelo `ComplianceCheck`: framework (CIS/PCI-DSS/BACEN/LGPD), check_id, description, check_function, severity (critical/high/medium). `ComplianceResult`: tenant_id, device_id, check_id, status (pass/fail/warn/na), evidence (JSON), checked_at. Cada pack tem ~50–100 checks automatizados que cruzam snapshots, audit logs e configurações do tenant. Exemplos CIS: "Nenhuma regra `any/any allow` ativa", "Acesso SSH restrito a IPs internos", "Senha de admin com complexidade mínima". Exemplos BACEN 4.658: "Logs de acesso retidos por 5 anos no audit log", "MFA habilitado para todos os admins". Dashboard: score 0–100% por framework, drill-down por check individual, evolução histórica mensal. API exporta resultados em JSON/CSV para GRC tools (ServiceNow, Archer).

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
Operações de gestão que exigem segundo aprovador: promover usuário para admin, revogar convite já enviado, alterar configuração SSO, adicionar/remover device crítico, alterar plano para downgrade, resetar MFA de outro usuário. `ManagementApprovalRequest`: action_type (enum), requested_by, payload (JSON com snapshot da mudança proposta), approved_by, rejected_by, created_at, expires_at (1h). Fluxo: admin solicita → todos os outros admins do tenant recebem notificação → primeiro a aprovar desbloqueia a ação → se rejeitado, ação cancelada e log registrado com motivo. Ambos os usuários (solicitante + aprovador) registrados no audit log da ação final.

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
Modelo `PlaybookRule`: name, tenant_id, trigger_type (risk_score_drop/anomaly_detected/guardrail_block/device_unreachable), trigger_condition (JSON: `{"metric": "risk_score", "operator": "<", "threshold": 20, "window_minutes": 5}`), actions (JSON array de `{type, params}`), cooldown_minutes (evita loops), enabled. Actions disponíveis: `set_device_read_only`, `notify_slack`, `notify_email`, `create_ticket_jira`, `run_snapshot`, `escalate_to_n2`, `isolate_device`. Celery beat task `evaluate_playbooks`: a cada minuto, avalia todas as rules ativas de todos os tenants; se trigger satisfeito, executa actions em sequência. `PlaybookExecution`: rule_id, triggered_at, trigger_context (JSON snapshot do estado que disparou), actions_taken (JSONB), status (success/partial/failed). Frontend: editor visual de playbooks com cards de condição + ação conectados por setas.

#### Threat Intelligence feed — Alta
Integrações com feeds públicos gratuitos: OTX AlienVault API (IoCs por categoria), AbuseIPDB (IPs com histórico de abuso, score > 75), CISA KEV (Known Exploited Vulnerabilities — CVEs com exploração ativa), URLhaus (URLs de malware), Feodo Tracker (C2 de botnets). Celery beat a cada 4h: baixa feeds, normaliza em `ThreatIndicator` (type: ip/domain/hash/cve, value, source, severity, tags, last_seen, confidence). Match automático após cada snapshot: cruza IPs das regras de firewall (src/dst das access rules, NAT policies, rotas) com `ThreatIndicator`. Alerta de match: se regra `allow` tem src/dst que é IoC com severity HIGH/CRITICAL → alerta imediato via canal configurado. Dashboard TI: timeline de matches por tenant, breakdown por feed/categoria, top-10 IoCs mais vistos nos tenants gerenciados.

#### NDR (Network Detection & Response) — Média
Baseline comportamental por device: calcula média e desvio padrão de conexões por hora (contagem de sessões nos snapshots) nos últimos 30 dias de dados históricos. Anomalia detectada se: contagem atual > média + 3σ, ou novo protocolo não visto antes nas últimas 4 semanas, ou conexão para IP nunca visto antes nas últimas 7 dias. `NetworkAnomaly`: device_id, detected_at, anomaly_type, baseline_value, observed_value, severity, context_json (IPs/portas envolvidos). Correlação: se anomalia simultânea em >3 devices do mesmo tenant na mesma janela de 30 min → severity escalada para CRITICAL e `CrossTenantCampaign` verificado (ver correlação cross-tenant). Dashboard NDR: timeline de anomalias, drill-down por device, heatmap de intensidade por hora×dia da semana.

#### Isolamento automático de device — Alta
Acionado por: action `isolate_device` em PlaybookRule, ou manualmente pelo Admin via botão "Isolar device" no painel. Isolamento técnico: connector do vendor aplica regra de segurança temporária "deny all inbound+outbound" com prioridade máxima (posição 0 na lista de políticas), preservando regras existentes (só adiciona a nova). Salva estado em `DeviceIsolation`: device_id, isolated_at, isolated_by (user_id ou `"automation:{playbook_id}"`), reason, pre_isolation_snapshot_id, restored_at, restored_by. Reativação: exige aprovação dupla (F33) + justificativa mínima de 50 chars registrada no audit. Notificação imediata: CISO do cliente via email + canal de alertas Slack/Teams. Timeout de segurança: se isolamento ativo por >24h sem reativação, alerta de escalação automático.

#### Correlação de alertas cross-tenant — Média
Celery task `correlate_cross_tenant_alerts` (a cada 15 min): agrega `ThreatIndicator` matches e `NetworkAnomaly` de todos os tenants na última hora. Detecta padrão: mesmo IoC (IP/domínio) encontrado em devices de >3 tenants distintos na mesma janela de 1h → cria `CrossTenantCampaign` (name, ioc_value, affected_tenant_count, affected_tenants: lista anonimizada, severity, started_at). Visível exclusivamente para Super Admin no dashboard de postura interna (F33). Permite notificação proativa ao CISO de cada tenant afetado: "Detectamos atividade relacionada ao IoC X em múltiplos clientes gerenciados. Recomendamos revisar suas regras para este IP." — sem expor dados de outros tenants (notificação genérica com o IoC, não menciona quais outros tenants foram afetados).

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
F31 (RBAC granular)          ──► F33 (four-eyes + aprovação dupla)
F34 (infra segurança)        pode rodar em paralelo com F33
F35 (SOAR) depende de F23 (alertas) + F33 (SIRP) + F34 (infra)
```
