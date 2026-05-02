# ADR-004: Vendors CLI — SSH exclusivo via CLI_VENDORS

**Status:** Ativo  
**Data:** 2026-05-02  
**Componentes:** `connectors/factory.py`, `workers/health_check.py`

## Contexto

Alguns vendors não têm REST API — gerenciamento é exclusivamente via SSH/CLI:
- HP Comware (V1910 e similares)
- Dell N-Series (DNOS6)
- Cisco IOS / NX-OS
- Juniper
- Aruba
- Dell OS10
- Ubiquiti

Chamar `get_connector()` para esses vendors levanta `NotImplementedError` porque o conector REST não está implementado. No health check original, isso fazia todos esses dispositivos aparecerem como `error` em vez de `online`/`offline`.

## Decisão

`factory.py` define `CLI_VENDORS` como frozenset:

```python
CLI_VENDORS: frozenset[str] = frozenset({
    "hp_comware", "dell_n", "cisco_ios", "cisco_nxos",
    "juniper", "aruba", "dell", "ubiquiti",
})
```

Em qualquer ponto que precise de um conector, verificar primeiro:

```python
from app.connectors.factory import CLI_VENDORS, get_connector, get_ssh_connector

if device.vendor in CLI_VENDORS:
    connector = get_ssh_connector(device)
else:
    connector = get_connector(device)
```

O health check (`workers/health_check.py`) já implementa esse padrão.

## Particularidades por vendor

### HP Comware (`ssh.py — HPComwareConnector`)
- CLI diferente de Cisco: `system-view` (não `configure terminal`), `quit` (não `exit`)
- Salvar config: `save force`
- Netmiko driver: `hp_comware`
- **CRÍTICO:** `send_config_set(exit_config_mode=False)` — Netmiko usa `exit` por padrão mas Comware usa `quit`, causando hang infinito

### Dell N-Series DNOS6 (`ssh.py — DellNConnector`)
- Vendor separado de `dell` (OS10) — são implementações distintas
- STP: `spanning-tree mode rstp`, `spanning-tree bpdu-protection`

## Consequências

- ✅ Health check retorna `online`/`offline` correto para dispositivos CLI
- ✅ `SSHResult` não tem `firmware_version` — usar `getattr(check_result, "firmware_version", None)` para não quebrar
- ⚠️ `CLI_VENDORS` deve ser atualizado ao adicionar novo vendor CLI-only
- ⚠️ Todo novo ponto de entrada que usa conector deve checar `CLI_VENDORS`

## NÃO faça

- ❌ Chamar `get_connector()` para vendors em `CLI_VENDORS` — levanta `NotImplementedError`
- ❌ `check_result.firmware_version` direto em `SSHResult` — atributo não existe
- ❌ Confundir `dell` (OS10) com `dell_n` (DNOS6) — conectores e CLIs completamente diferentes
