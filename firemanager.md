# FireManager — Roadmap & Decisões de Projeto

## O que é

Plataforma multivendor de gestão de firewalls com IA. Permite criar, editar e auditar regras de firewall via linguagem natural (Agente IA), modo técnico direto (SSH/REST), templates pré-definidos e inspeção ao vivo do dispositivo.

---

## Status atual — v0.1 MVP

### Implementado

| Módulo | Descrição |
|--------|-----------|
| Auth | JWT + refresh, roles admin/operator |
| Dispositivos | CRUD, health-check, suporte SonicWall Gen7 |
| Agente IA | Chat com LLM, geração de plano de ação, execução via REST/SSH |
| Modo Técnico | Execução direta de comandos SSH sem IA |
| Templates | Biblioteca de templates SonicWall reutilizáveis com parâmetros |
| Operações | Histórico de todas as operações, rastreio de edições (parent_operation_id) |
| Auditoria | Aprovação/rejeição de operações por admins, log imutável |
| Inspetor | Visualização ao vivo de regras, NAT, rotas, Content Filter, App Rules, serviços de segurança |
| Recomendações | Análise automática de segurança da política do firewall (ver seção abaixo) |

### Recomendações de segurança — checks implementados

- **Shadow rules** — regras inatingíveis por sobreposição de regra anterior mais genérica (com detecção de IP subnet overlap)
- **Origem Any para zonas internas** — regras que expõem LAN/DMZ a qualquer IP
- **Serviço Any para WAN** — regras que abrem todas as portas para a internet
- **DPI-SSL desativado** — regras WAN sem inspeção TLS (`dpi_ssl_client` / `dpi_ssl_server`)
- **WAN→LAN sem inspeção** — regras permissivas cruzando WAN com serviços de segurança desligados globalmente
- **Oportunidades de agrupamento** — regras com mesmo destino/serviço que poderiam usar address groups
- **Regras desativadas** — candidatas à remoção com hit count exibido (Fase 1)

---

## Roadmap

### Fase 2 — Rastreio de tempo de regras (planejado)

**Motivação:** Saber há quanto tempo uma regra está desativada e há quanto tempo não recebe tráfego permite identificar regras mortas com certeza, não só suspeita.

**Abordagem — tabela de estado atual (tamanho fixo):**

```sql
CREATE TABLE rule_states (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id   UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    rule_id     TEXT NOT NULL,                  -- UUID ou ID da regra no firewall
    rule_name   TEXT NOT NULL,
    disabled_since  TIMESTAMPTZ,               -- quando ficou desativada (NULL = ativa)
    last_hit_at     TIMESTAMPTZ,               -- quando o hit count mudou pela última vez
    last_hit_count  BIGINT DEFAULT 0,          -- último contador observado
    checked_at      TIMESTAMPTZ NOT NULL,      -- última vez que o job verificou
    UNIQUE (device_id, rule_id)
);
```

**Comportamento:**
- Uma linha por regra — nunca cresce além do número de regras × dispositivos
- Job periódico (APScheduler integrado ao FastAPI, intervalo configurável) faz UPSERT:
  - `enabled` mudou true → false: salva `disabled_since = NOW()`
  - `enabled` mudou false → true: zera `disabled_since`
  - `hit_count` aumentou: salva `last_hit_at = NOW()`
- Resultado: "Desativada há 12 dias", "Sem match há 8 dias"

**Arquivos a criar:**
- `backend/app/models/rule_state.py` — modelo SQLAlchemy
- `backend/migrations/versions/XXXX_rule_states.py` — migration Alembic
- `backend/app/workers/rule_state_poller.py` — job APScheduler
- `backend/app/api/rule_states.py` — endpoint `GET /devices/{id}/rule-states`
- Integração na aba Recomendações: enriquecer card de regras desativadas com "desativada há X dias / sem match há Y dias"

**Impacto no banco:** Zero crescimento com o tempo — apenas UPSERTs. Ex: 10 dispositivos × 100 regras = 1.000 linhas fixas.

---

### Outras features planejadas

- **Suporte Fortinet FortiGate** — conector REST + SSH (estrutura já existe em `fortinet.py`)
- **Diff de política** — comparar snapshot atual com snapshot anterior e destacar mudanças
- **Exportação de relatório** — PDF/CSV da análise de recomendações por dispositivo
- **Alertas** — notificar via e-mail/Slack quando nova recomendação de severidade Alta for detectada
- **Multi-tenant** — isolamento por organização (hoje é single-tenant)
