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

---

## Roadmap — Próximas Fases

### Fase 17 — Golden Config: Templates, Padronização e Divergência
*Unifica: template de filial + biblioteca de templates + relatório de divergência*

- Template com variáveis tipadas: `{BRANCH_LAN}`, `{GW_IP}`, `{BRANCH_NAME}`, `{TUNNEL_HQ}`
- Biblioteca pré-definida: filial padrão (Fortinet/SonicWall), matriz, switch de acesso
- Aplicação de template: wizard preenche variáveis, gera plano de operação
- Relatório de divergência: config live vs template — o que falta, difere ou está extra
- Versionamento de templates por tenant

---

### Fase 18 — Análise de Conectividade de Rede
*Item: análise de rotas + Nmap internet exposure*

- Coleta de tabelas de roteamento via SSH em todos os firewalls
- Coleta de status: SD-WAN, BGP/OSPF, rotas estáticas
- Detector de anomalias: rotas assimétricas, redundantes sem failover, conflitos estático×dinâmico
- Cruzamento Nmap: regras que expõem serviços a IPs públicos destacadas com exposição real
- Mapa de topologia visual interativo
- AI: explica anomalias, sugere correções

---

### Fase 19 — Base de Conhecimento IA (RAG Avançado)
*Infraestrutura transversal — melhora todos os módulos*

- Upload de documentos por tenant: PDF, Markdown, DOCX
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

### Fase 21 — Gestão de Ciclo de Vida de Usuários
*Maior diferenciador MSSP*

- Workflow de offboarding: 1 clique revoga acesso em SSH Linux, WinRM, firewalls VPN, DBs, Wazuh
- Workflow de onboarding: cria usuários com permissões por cargo/papel
- Execução coordenada e auditada em N sistemas simultaneamente
- Relatório de contas órfãs: usuários que não deveriam mais ter acesso em sistemas específicos
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

## Novos Vendors — Priorização

| Vendor | Categoria | Fase alvo | Prioridade | Status |
|--------|-----------|-----------|-----------|--------|
| Huawei USG | Firewall | 17+ | Média | Pendente |
| TP-Link | Switch | Futuro | Baixa | Pendente |
| D-Link | Switch | Futuro | Baixa | Pendente |

**Implementados:** Sophos (Fase 16 ✅), Intelbras/Juniper/Aruba (Fase 15 ✅)

---

## Mapa de Dependências

```
Fase 15 (switches)  ──► Fase 16 (Firewall Migration) ✅
Fase 13 (variáveis) ──► Fase 17 (Golden Config)
pgvector            ──► Fase 19 (RAG)
Fase 14 (servidores)──► Fase 20 (DB Connectors)
Fases 14 + 20       ──► Fase 21 (User Lifecycle)
Fase 14             ──► Fase 22 (VM Migration)
```
