# FireManager — Roadmap & Decisões de Projeto

## O que é

Plataforma MSSP multivendor de gestão centralizada de firewalls com IA. Permite criar, editar e auditar regras de firewall via linguagem natural (Agente IA), modo técnico direto (SSH/REST), templates pré-definidos, inspeção ao vivo do dispositivo e documentação automática via BookStack.

---

## Status atual — v0.15 (Fase 15 em andamento)

### Fases implementadas

| Fase | Módulo | Descrição |
|------|--------|-----------|
| 1 | Scaffold MVP | Devices, operações, Agente IA (SonicWall Gen6/7), auth JWT, modo técnico SSH, templates, auditoria, inspetor ao vivo, recomendações de segurança |
| 2 | Multi-tenant/MSSP | Isolamento por `tenant_id`, roles `admin / analyst / readonly`, `analyst_n1` (só envia para revisão) / `analyst_n2` (executa com aprovação), super admin cross-tenant |
| 3 | Integrações externas | Nmap, Shodan, Wazuh, OpenVAS — análise de vulnerabilidades e exposição externa |
| 4 | Dashboard Super Admin | Visão cross-tenant para suporte MSSP, métricas globais |
| 5 | Convites por e-mail | Self-service de cadastro via convite, confirmação por e-mail |
| 6 | Novos vendors (firewalls) | pfSense, OPNsense, MikroTik, Endian |
| 7 | Bulk Jobs | Operações em lote: mesma instrução aplicada a N dispositivos via Agente IA |
| 8 | Inspetor ao vivo | Abas: Regras, NAT, Rotas, Content Filter, App Rules, Serviços de Segurança — consulta em tempo real |
| 9 | Bulk jobs por categoria | Agrupamento de dispositivos por categoria para lote |
| 10 | Grupos de dispositivos | Tags e grupos manuais para organização |
| 11 | Dell N-Series (DNOS6) | Conector SSH para Dell N-Series com CLI própria |
| 12 | HP Comware (V1910) | Conector SSH Netmiko (`hp_comware`), `display current-configuration`, `save force` |
| 13 | Variáveis de template | Herança tenant → device, substituição em tempo de execução, `resolve_and_substitute()` |
| 14 | Módulo de servidores | Análise read-only: SSH Linux, WinRM Windows, Zabbix JSON-RPC v6/v7, Wazuh REST v4/v5 |
| 15 | BookStack + IA | Snapshot incremental, documentação automática, changelog, contexto IA opcional (em andamento) |

---

### Módulos ativos (v0.15)

| Módulo | Descrição |
|--------|-----------|
| Auth | JWT + refresh, MFA (TOTP), roles multi-tenant, convites por e-mail |
| Dispositivos | CRUD multivendor, health-check periódico, credenciais criptografadas |
| Agente IA | Chat LLM (Claude Sonnet), geração de plano de ação, execução REST/SSH, toggle de contexto BookStack |
| Modo Técnico | Execução direta de comandos SSH sem IA, templates com parâmetros |
| Bulk Jobs | Operação em lote N dispositivos, plano gerado por IA replicado |
| Operações | Histórico completo, rastreio de edições (`parent_operation_id`), risk level, multi-sig |
| Auditoria | Fila N2, aprovação/rejeição, log imutável, `check_requires_approval()` por policy |
| Inspetor | Visualização ao vivo: regras, NAT, rotas, content filter, app rules, serviços de segurança |
| Recomendações | Análise automática de segurança da política do firewall (ver seção abaixo) |
| Servidores | Análise read-only de servidores Linux/Windows + Zabbix + Wazuh |
| BookStack | Snapshot incremental (hash), documentação IA, changelog, vinculação de páginas |
| GLPI | Integração de followup com análise IA formatada em HTML |
| Variáveis | Templates com herança tenant→device, substituição automática no input do agente |

---

### Recomendações de segurança — checks implementados

- **Shadow rules** — regras inatingíveis por sobreposição de regra anterior mais genérica (com detecção de IP subnet overlap)
- **Origem Any para zonas internas** — regras que expõem LAN/DMZ a qualquer IP
- **Serviço Any para WAN** — regras que abrem todas as portas para a internet
- **DPI-SSL desativado** — regras WAN sem inspeção TLS (`dpi_ssl_client` / `dpi_ssl_server`)
- **WAN→LAN sem inspeção** — regras permissivas cruzando WAN com serviços de segurança desligados globalmente
- **Oportunidades de agrupamento** — regras com mesmo destino/serviço que poderiam usar address groups
- **Regras desativadas** — candidatas à remoção com hit count exibido

---

### Vendors suportados

| Vendor | Protocolo | Regras | NAT | Rotas | Snapshot |
|--------|-----------|--------|-----|-------|----------|
| SonicWall Gen6/7/8 | REST + SSH | ✅ | ✅ | ✅ | ✅ |
| Fortinet FortiGate | REST | ✅ | ✅ | ✅ | ✅ |
| pfSense | REST | ✅ | ✅ | ✅ | ✅ |
| OPNsense | REST | ✅ | ✅ | ✅ | ✅ |
| MikroTik | REST | ✅ | ✅ | ✅ | ✅ |
| Endian | REST | ✅ | — | — | ✅ |
| Cisco IOS | SSH | ✅ | — | ✅ | ✅ (running-config) |
| Cisco NXOS | SSH | ✅ | — | ✅ | ✅ (running-config) |
| Juniper | SSH | ✅ | — | ✅ | ✅ (running-config) |
| Aruba | SSH | ✅ | — | ✅ | ✅ (running-config) |
| Dell OS10 | SSH | ✅ | — | ✅ | ✅ (running-config) |
| Dell N-Series (DNOS6) | SSH | ✅ | — | ✅ | ✅ (running-config) |
| HP Comware | SSH | ✅ | — | ✅ | ✅ (display current-configuration) |
| Ubiquiti | SSH | ✅ | — | ✅ | ✅ (running-config) |

---

## Fase 15 — BookStack (detalhes)

### O que foi implementado

**Snapshot incremental com hash:**
- `sha256` do conteúdo markdown gerado é comparado com o último snapshot salvo (`Snapshot.config_hash`)
- Se conteúdo idêntico: skip da escrita no BookStack (evita poluição de histórico)
- Registrado via structlog: `snapshot_unchanged_skip`

**Snapshot de vendors CLI via SSH:**
- `CLI_VENDORS` (HP Comware, Dell N, Cisco IOS/NX-OS, Juniper, Aruba, Dell, Ubiquiti) coletam `running-config` via SSH antes do snapshot REST
- HP Comware usa `display current-configuration`; demais usam `show running-config`
- Limitado a 200 linhas (excedente indicado com `... [+N linhas omitidas]`)
- Renderizado em bloco de código no markdown do snapshot

**Validação de `bookstack_page_id`:**
- `GET /{device_id}/bookstack/validate-page?page_id=X` — valida existência da página antes de vincular
- `PATCH /{device_id}/bookstack` rejeita (422) se `bookstack_page_id` não existir no BookStack

**Contexto BookStack opcional no Agente IA:**
- Toggle checkbox visível no cabeçalho do chat sempre que um dispositivo está selecionado
- `use_bookstack_context: bool = True` propagado: `OperationCreate` → `start_or_continue_operation` → `fetch_bookstack_context`
- Com toggle desativado: agente responde sem snapshots/documentação como contexto

---

## Problemas conhecidos e resoluções

### SonicWall — `E_EXISTS` ao criar regra que já existe

**Sintoma:** Agente responde "Erro na execução" com JSON bruto `{"info":[{"code":"E_EXISTS","message":"Already exists."}]}` ao tentar criar uma regra já existente.

**Causa raiz:** O conector `create_rule()` tratava qualquer resposta não-200/201 como falha. O SonicWall retorna o `info` array dentro de `body["status"]["info"]` (não na raiz do JSON), o que enganava a primeira versão do fix.

**Resolução (commit `a6048c6`):**
```python
status_block = body.get("status") or {}
info_list = status_block.get("info") or body.get("info") or []
codes = [i.get("code", "") for i in info_list]
if "E_EXISTS" in codes:
    return ExecutionResult(success=True, raw_response=body, already_existed=True)
```
Quando `already_existed=True`, o `action_plan` recebe `"already_existed": True` e o frontend exibe:
> **Regra já existia no dispositivo — nenhuma alteração necessária:** [tabela com detalhes]

**Mesma lógica aplicável a:** `create_nat_policy`, `create_route_policy` (não implementado ainda — se aparecer, replicar o padrão).

---

### GLPI — followup com texto corrido (sem formatação)

**Sintoma:** Followup enviado ao GLPI aparecia como texto corrido, sem separação visual entre seções.

**Causa raiz:** `_build_followup()` usava `\n` para separar linhas. GLPI renderiza o campo como HTML — `\n` não gera quebra visual.

**Resolução:** Substituídas todas as separações por tags HTML:
- Seções: `<p><b>título</b><br>conteúdo</p>`
- Separador: `<hr/>`
- Listas numeradas: helper `_steps_to_html()` converte `"1. passo\n2. passo"` → `<ol><li>passo</li></ol>`

---

### BookStack — toggle "Contexto BookStack" não aparecia

**Sintoma (3 iterações):**
1. Toggle só aparecia quando `bookstack_page_id` estava preenchido no dispositivo → dispositivos de teste sem página vinculada ficavam sem toggle
2. Toggle aparecia sempre mas desativado com texto "(não vinculado)" → ainda confuso
3. Toggle aparecia sempre mas habilitado — backend lida com contexto vazio sem erro

**Resolução final:** Toggle sempre visível e sempre habilitado quando um dispositivo está selecionado. O backend, quando não há páginas BookStack vinculadas, simplesmente não anexa contexto (sem erro).

---

### Docker — build cacheado não recompila frontend

**Sintoma:** Após `git pull` + `docker compose build frontend`, o container servia código antigo. O build mostrava `CACHED [builder 5/6] COPY . .`.

**Causa raiz:** Docker reutiliza layer cache mesmo com arquivos modificados quando os checksums coincidem com a camada anterior.

**Resolução:** Usar `--no-cache` para forçar recompilação completa:
```bash
docker compose -f infra/docker-compose.yml build --no-cache frontend
docker compose -f infra/docker-compose.yml up -d --force-recreate frontend
```

**Quando usar:** Sempre que uma mudança no frontend não aparecer após rebuild normal.

---

### Docker — nginx retorna 502 após restart do container `api`

**Sintoma:** API reiniciada, nginx retorna 502 Bad Gateway.

**Causa raiz:** nginx faz cache de DNS interno. Após restart, o container `api` recebe novo IP — nginx ainda aponta para o IP antigo.

**Resolução:** Sempre reiniciar nginx após recriar o container api:
```bash
docker compose -f infra/docker-compose.yml restart nginx
```

---

### SQLAlchemy — `MissingGreenlet` após `flush()`

**Sintoma:** `MissingGreenlet` ou `greenlet_spawn has not been called` ao serializar um objeto ORM após `db.flush()`.

**Causa raiz:** Campos com `onupdate=func.now()` (ex: `updated_at`) são **expirados** pelo SQLAlchemy após o flush. Qualquer acesso a esses campos fora do contexto async causa erro.

**Resolução:** Sempre fazer `await db.refresh(objeto)` após `await db.flush()` antes de serializar:
```python
await db.flush()
await db.refresh(objeto)   # recarrega campos expirados
return Schema.model_validate(objeto)
```

---

### Fortinet — campo `vdom` null no JSON de credenciais

**Sintoma:** Operações Fortinet usam VDOM `None` em vez de `"root"` quando o campo está presente mas nulo no JSON de credenciais.

**Causa raiz:** `creds.get("vdom", "root")` não usa o default quando a chave existe com valor `null` — o default só atua quando a chave não existe.

**Resolução:** `creds.get("vdom") or "root"` — o `or` garante fallback também para `null`/`None`.

---

### SonicWall — SSH deve rodar antes do REST (sessão única)

**Regra:** SonicWall permite apenas **uma sessão de gerenciamento ativa por vez**. A sessão REST com `override=True` bloqueia SSH.

**Impacto:** `bookstack_service._collect_live_data()` e qualquer operação que combine SSH + REST deve sempre executar SSH **antes** de abrir a sessão REST.

**Ver:** ADR-001.

---

## Roadmap

### Fase 16 — Rastreio de tempo de regras (planejado)

**Motivação:** Saber há quanto tempo uma regra está desativada e há quanto tempo não recebe tráfego permite identificar regras mortas com certeza, não só suspeita.

**Abordagem — tabela de estado atual (tamanho fixo):**

```sql
CREATE TABLE rule_states (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id       UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    rule_id         TEXT NOT NULL,
    rule_name       TEXT NOT NULL,
    disabled_since  TIMESTAMPTZ,
    last_hit_at     TIMESTAMPTZ,
    last_hit_count  BIGINT DEFAULT 0,
    checked_at      TIMESTAMPTZ NOT NULL,
    UNIQUE (device_id, rule_id)
);
```

**Comportamento:**
- Uma linha por regra — nunca cresce além do número de regras × dispositivos
- Job Celery periódico faz UPSERT:
  - `enabled` mudou true → false: salva `disabled_since = NOW()`
  - `enabled` mudou false → true: zera `disabled_since`
  - `hit_count` aumentou: salva `last_hit_at = NOW()`
- Resultado: "Desativada há 12 dias", "Sem match há 8 dias"

**Impacto no banco:** Zero crescimento com o tempo. Ex: 10 dispositivos × 100 regras = 1.000 linhas fixas.

---

### Outras features planejadas

- **E_EXISTS para NAT/Rotas** — replicar lógica idempotente do `create_rule` para `create_nat_policy` e `create_route_policy`
- **Diff de política** — comparar snapshot atual com snapshot anterior e destacar mudanças
- **Exportação de relatório** — PDF/CSV da análise de recomendações por dispositivo
- **Alertas** — notificar via e-mail/Slack quando nova recomendação de severidade Alta for detectada
- **Fase 15 pendente** — análise de impacto de mudanças antes da execução (preview)
