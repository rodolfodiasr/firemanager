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
