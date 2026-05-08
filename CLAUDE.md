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

---

### Próximas Fases

---

### Fase 25 — Plataforma Enterprise e Marketplace
*Escala MSSP: white-label, billing, SSO, API pública, grandes vendors*

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
```
