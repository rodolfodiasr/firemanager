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

## Fases implementadas

| Fase | Descrição | Status |
|---|---|---|
| 1 | Scaffold MVP — devices, operações, agente IA | ✅ |
| 2 | Multi-tenant/MSSP com roles | ✅ |
| 3 | Integrações externas (Nmap, Shodan, Wazuh, OpenVAS) | ✅ |
| 4 | Dashboard cross-tenant Super Admin | ✅ |
| 5 | Convites por email + self-service | ✅ |
| 6 | pfSense, OPNsense, MikroTik, Endian | ✅ |
| 7 | Bulk Jobs em lote | ✅ |
| 8 | Inspetor de dispositivo ao vivo | ✅ |
| 9 | Bulk jobs por categoria | ✅ |
| 10 | Grupos de dispositivos | ✅ |
| 11 | Dell N-Series (DNOS6) | ✅ |
| 12 | HP V1910 (Comware) | ✅ |
| 13 | Variáveis de template (herança tenant→device) | ✅ |
| 14 | Módulo Analista de Servidores (SSH Linux, WinRM, Zabbix, Wazuh) | ✅ |
| 15 | Migração de Switches + BookStack + Zabbix v6/v7 + Snapshot scheduling + Segmentação inventário | ✅ |
| 16 | Migração de Regras de Firewall (Fortinet, SonicWall, Sophos) | ✅ |
| 17 | Golden Config: Templates, Padronização e Divergência | ✅ |
| 18 | Análise de Conectividade de Rede (rotas, BGP/OSPF, SD-WAN, anomalias, IA) | ✅ |
| 19 | Base de Conhecimento IA — RAG avançado (upload PDF/DOCX/MD, pgvector, agent injection) | ✅ |
| 20 | Conectores de Banco de Dados (PostgreSQL, MySQL, MariaDB, SQL Server, Oracle) + auditoria de usuários/privilégios + IA | ✅ |
| 21 | Gestão de Ciclo de Vida de Usuários — Azure AD, Google Workspace, offboarding coordenado SSH/WinRM/DB, contas órfãs, webhook RH | ✅ |

---

## Roadmap — Próximas Fases

### Fase 18 — Análise de Conectividade de Rede
*Análise de rotas + Nmap internet exposure*

- Coleta de tabelas de roteamento via SSH em todos os firewalls (`show route`, `show ip route`)
- Coleta de status: SD-WAN, BGP/OSPF, rotas estáticas
- Detector de anomalias: rotas assimétricas, redundantes sem failover, conflitos estático×dinâmico
- Cruzamento Nmap: regras que expõem serviços a IPs públicos destacadas com exposição real
- Mapa de topologia visual interativo
- AI: explica anomalias, sugere correções

---

### Fase 19 — Base de Conhecimento IA (RAG Avançado)
*Infraestrutura transversal — melhora todos os módulos*

- Upload de documentos por tenant: PDF, Markdown, DOCX (manuais, runbooks, contratos)
- Chunking + embeddings com pgvector (já na stack)
- Biblioteca embutida: docs dos vendors principais + CIS Benchmarks + ISO 27001 + LGPD
- Agente IA injeta contexto relevante automaticamente antes de responder

---

### Fase 20 — Conectores de Banco de Dados
*Alimenta Fase 21*

- SQL Server (aioodbc), Oracle (cx_Oracle), MySQL/MariaDB (aiomysql), PostgreSQL (asyncpg — já disponível)
- Auditoria: usuários, último acesso, roles/privileges, senhas sem expiração
- Detecção: privilégios excessivos, contas sem login há X dias
- Relatório de compliance por política do tenant
- Integração com Fase 14 (servidor lista os DBs que rodam nele)
- WinRM CIS Windows: checklist CIS benchmark para Windows Server

---

### Fase 21 — Gestão de Ciclo de Vida de Usuários e Identidade SaaS
*Maior diferenciador MSSP — on-premise + cloud unificados*

- **Workflow de offboarding:** 1 clique revoga acesso em SSH Linux, WinRM, firewalls VPN, DBs, Wazuh
- **Workflow de onboarding:** cria usuários com permissões por cargo/papel em todos os sistemas
- **Office 365 / Azure AD:** monitor de logins anômalos, criação e revogação de usuários via Graph API
- **Google Workspace:** mesmo padrão — conector base comum com Azure AD (OAuth2 + Directory API)
- **Offboarding por webhook de RH:** sistema de RH (ticket/webhook) sinaliza desligamento → plataforma lista todos os acessos do usuário → analista aprova revogação com 1 clique
- Execução coordenada e auditada em N sistemas simultaneamente (on-premise + cloud)
- Relatório de contas órfãs: usuários que existem no AD/365/Workspace mas não deveriam mais ter acesso
- Registro de auditoria imutável: quem, quando, quais sistemas, resultado

---

### Fase 22 — Planejamento de Migração de Infraestrutura
*Planejamento assistido por IA — sem execução automatizada*

- Conectores read-only: VMware vCenter API, Proxmox API, Hyper-V (WinRM)
- Inventário de VMs: OS, recursos, serviços, dependências de rede
- Análise de dependências: quais VMs se comunicam, ordem de migração
- AI gera runbook: sequência, janelas de manutenção, rollback plan
- Export automático para BookStack

---

### Fase 23 — Alertas, Integrações e Automação de Monitoramento
*Fechar o loop: detectar → notificar → ticketar → correlacionar*

- **Webhooks de saída:** SIEM (Splunk, Elastic, Wazuh via API), chat (Slack, Microsoft Teams)
- **Notificações por e-mail** configuráveis por tenant (SMTP próprio ou SendGrid)
- **Integração com ticketing:** cria ticket automaticamente no Jira/ServiceNow/Freshdesk ao detectar anomalia crítica
- **Diff visual entre snapshots** de configuração + rollback com 1 clique
- **Agendamento de auditorias recorrentes:** cron configurável por dispositivo/grupo/tenant
- **Correlação de regras com CVEs:** integração NVD/OSV — regras que expõem serviços com CVEs conhecidos são destacadas no inspetor
- **Motor de alertas:** canal configurável por tipo de evento (anomalia crítica → email + Slack; drift de template → ticket Jira)
- **Correlação identidade↔rede:** usuário bloqueado no Azure AD/365 → sugestão automática de bloquear IP no firewall (requer aprovação humana)
- **Gatilhos cloud híbridos:** Azure Monitor / AWS CloudWatch disparam ações em infra local (ex: spike de tráfego na cloud → auditoria automática no firewall on-premise)

---

### Fase 24 — Relatório Executivo, SLA e Compliance Avançado
*Visibilidade C-level + frameworks enterprise*

- **Dashboard executivo:** postura de segurança consolidada do ambiente inteiro (extends Trust Score)
- **SLA de disponibilidade:** histórico de uptime por dispositivo, relatório mensal por tenant
- **Relatório executivo em PDF:** resumo não-técnico — riscos, tendências, comparativo mês a mês
- **Conformidade NIST SP 800-41** (firewall policy framework)
- **Análise de superfície de ataque completa:** mapa de risco cross-vendor do ambiente inteiro
- **Análise de movimento lateral entre zonas:** detecta paths entre DMZ/LAN/WAN que violam princípio de menor privilégio
- **Atualização de firmware via plataforma:** Fortinet e SonicWall (com janela de manutenção e rollback)

---

### Fase 25 — Plataforma Enterprise e Marketplace
*Escala MSSP: white-label, billing, SSO, API pública, grandes vendors*

- **SSO** via SAML 2.0 / OIDC (Azure AD, Okta, Google Workspace)
- **RBAC granular** por cliente/dispositivo/operação (além dos 3 papéis atuais)
- **API pública** do FireManager com documentação OpenAPI 3.1 — permite integrações externas
- **White-label:** tenant customiza logo, cores e domínio (parceiros MSSP que vendem sob marca própria)
- **Multi-idioma:** i18n/l10n — pt-BR ✅, en-US, es-LA
- **Billing/subscription por tenant:** planos, limites de dispositivos, cobrança automatizada
- **Grandes vendors enterprise:** Cisco ASA/FTD, Palo Alto PAN-OS, Check Point R80+, Juniper SRX
- **Marketplace de plugins:** extensões de vendor contribuídas pela comunidade / parceiros

---

### Fase 26 — Golden Config Avançado: Template Bundles e Políticas REST-native
*Opção C: implantação completa de filial com 1 clique — base + regras + filtro + geo-IP*

#### Contexto e motivação
A Fase 17 implementou Golden Config para **configuração base** (CLI SSH: hostname, VLANs, interfaces, STP, rotas).
A Fase 26 estende isso para **políticas de segurança completas**, que nos firewalls modernos são gerenciadas via REST API (não CLI).

**Limitação atual:** Fortinet apply retorna `status: "manual"` — não há REST API call para push de configuração.
A Fase 26 adiciona o conector REST-native e o modelo de bundle que agrupa seções heterogêneas.

#### Modelo de dados — GoldenBundle

```
GoldenBundle (novo modelo)
├── id, tenant_id, name, description, vendor
├── variables: JSONB  (variáveis globais do bundle)
└── sections: List[BundleSection] (ordenadas por apply_order)

BundleSection
├── section_type: Enum("base_config" | "access_rules" | "content_filter" | "geo_ip" | "objects" | "vpn" | "sd_wan")
├── template_id: FK → GoldenTemplate  (templates CLI existentes da Fase 17)
├── rest_payload_template: Text  (template JSON para seções REST-native, com {VARIÁVEIS})
├── apply_strategy: Enum("cli_ssh" | "rest_api" | "manual_only")
├── apply_order: int  (ordem de execução — objects antes de rules)
└── rollback_strategy: Enum("snapshot_restore" | "delete_objects" | "none")
```

**Herança de variáveis (3 níveis):**
```
Bundle Variables → Tenant Variables → Device Variables
(device sempre sobrescreve)
```

#### Seções e estratégias por vendor

| section_type | Fortinet | SonicWall | pfSense | Sophos |
|---|---|---|---|---|
| base_config | CLI SSH | CLI SSH | CLI SSH | CLI SSH |
| objects (addr/svc) | REST `/api/v2/cmdb/firewall/address` | REST API | — | REST API |
| access_rules | REST `/api/v2/cmdb/firewall/policy` | REST API | pfctl rules | REST API |
| content_filter | REST `/api/v2/cmdb/webfilter/profile` | CFS REST | Squid/pfBlockerNG | REST API |
| geo_ip | REST `/api/v2/cmdb/firewall/country` | Geo-IP REST | pfBlockerNG | REST API |
| vpn | REST `/api/v2/cmdb/vpn.ipsec/phase1` | REST API | CLI SSH | REST API |
| sd_wan | REST `/api/v2/cmdb/system/virtual-wan-link` | — | — | — |

#### Fluxo de aplicação (BundleApplyJob)

```
1. Snapshot automático pré-apply (salva config atual como fallback)
2. Para cada BundleSection (ordenado por apply_order):
   a. Interpolar variáveis (device → tenant → bundle)
   b. apply_strategy == "cli_ssh"  → SSH + comandos CLI (usa executor Fase 17)
   c. apply_strategy == "rest_api" → REST call (novo FortinetRestConnector)
   d. apply_strategy == "manual_only" → gera preview + aguarda confirmação humana
3. Se qualquer seção falhar → rollback automático pela rollback_strategy da seção
4. Registro de audit log: seção, payload enviado, resposta do device, status
```

#### Novos componentes a implementar

**Backend:**
- `app/models/golden_bundle.py` — GoldenBundle + BundleSection (SQLAlchemy)
- `app/services/bundle_renderer.py` — interpola variáveis, resolve template_id → CLI ou rest_payload_template → JSON
- `app/services/fortinet_rest_connector.py` — autenticação via API key Fortinet, CRUD de objetos/políticas/webfilter/geo-ip
- `app/services/sonicwall_rest_connector.py` — SonicWall REST API (sessions + HTTPS)
- `app/workers/bundle_worker.py` — Celery task `apply_golden_bundle` com rollback automático
- `app/api/golden_bundle.py` — CRUD bundles/sections + endpoint `/apply`
- Migration Alembic `0031_golden_bundle.py`

**Frontend:**
- `BundleEditor` — wizard multi-step: escolhe vendor → configura seções → define variáveis → preview
- `BundleLibrary` — lista de bundles do tenant (templates de filial reutilizáveis)
- `BundleApplyModal` — seleciona device alvo, sobrescreve variáveis (IPs, VDOM, senhas), preview de cada seção, progresso em tempo real via polling
- `BundleDiffView` — compara estado atual do device vs. bundle (divergência por seção)

#### Templates de filial embutidos (biblioteca padrão)

```
"Filial Padrão Fortinet" (bundle)
├── [1] base_config     → template CLI: hostname, VLANs, interfaces, rotas estáticas
├── [2] objects         → REST: addr-objects padrão (RFC1918, trusted-nets, dns-servers)
├── [3] access_rules    → REST: LAN→WAN allow, LAN→LAN isolado, DMZ→LAN deny, WAN→all deny
├── [4] content_filter  → REST: webfilter profile (bloqueia P2P, adult, malware)
├── [5] geo_ip          → REST: bloqueia países de alto risco (lista configurável por tenant)
└── [6] vpn             → REST: IPSec site-to-site (template com {PEER_IP}, {PSK}, {SUBNET})
```

#### Milestones (Etapas internas da Fase 26)

| Etapa | Entregável | Pré-requisito |
|---|---|---|
| 26.1 | Modelos DB + migrations + CRUD API | — |
| 26.2 | FortinetRestConnector (objects + access_rules) | 26.1 |
| 26.3 | BundleRenderer + variáveis 3 níveis | 26.1 |
| 26.4 | bundle_worker + rollback automático | 26.2 + 26.3 |
| 26.5 | Frontend: BundleEditor + BundleLibrary | 26.1 |
| 26.6 | Frontend: BundleApplyModal + polling | 26.4 + 26.5 |
| 26.7 | Templates embutidos "Filial Padrão" (Fortinet + SonicWall) | 26.4 |
| 26.8 | BundleDiffView (divergência por seção) | 26.6 |
| 26.9 | SonicWallRestConnector | 26.2 |

---

## Novos Vendors — Priorização

| Vendor | Categoria | Fase alvo | Prioridade | Status |
|--------|-----------|-----------|-----------|--------|
| Huawei USG | Firewall | 18+ | Média | Pendente |
| Cisco ASA/FTD | Firewall | 25 | Alta | Pendente |
| Palo Alto PAN-OS | Firewall | 25 | Alta | Pendente |
| Check Point R80+ | Firewall | 25 | Alta | Pendente |
| Juniper SRX | Firewall | 25 | Média | Pendente |
| TP-Link | Switch | Futuro | Baixa | Pendente |
| D-Link | Switch | Futuro | Baixa | Pendente |

**Implementados:** Sophos (Fase 16 ✅), Intelbras/Juniper/Aruba (Fase 15 ✅)

---

## Mapa de Dependências

```
Fase 15 (switches)        ──► Fase 16 (Firewall Migration) ✅
Fase 13 (variáveis)       ──► Fase 17 (Golden Config) ✅
Fase 17 (Golden Config)   ──► Fase 26 (Template Bundles)
pgvector                  ──► Fase 19 (RAG)
Fase 14 (servidores)      ──► Fases 20 e 22
Fases 14 + 20             ──► Fase 21 (User Lifecycle + Identidade SaaS)
Fase 14                   ──► Fase 22 (VM Migration)
Fases 8 + 17 + 21         ──► Fase 23 (Alertas + Diff + Correlação identidade↔rede)
Fases 3 + 23              ──► Fase 24 (Relatório Executivo)
Fase 24                   ──► Fase 25 (Enterprise/Marketplace)
Fase 26 pode rodar em paralelo com Fases 18–25 (extensão vertical de Fase 17)
```
