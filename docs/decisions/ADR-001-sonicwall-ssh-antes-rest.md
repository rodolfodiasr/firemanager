# ADR-001: SonicWall — SSH deve rodar antes do REST

**Status:** Ativo  
**Data:** 2026-05-02  
**Componentes:** `bookstack_service.py`, `sonicwall_ssh.py`, `sonicwall.py`

## Contexto

O SonicWall permite apenas **uma sessão de gerenciamento por vez**. Quando o conector REST abre sessão com `override: true` (`POST /api/sonicos/auth`), ele ocupa a sessão e **bloqueia qualquer conexão SSH simultânea**.

O BookStack snapshot precisa coletar:
- Via REST: rules, NATs, routes (funciona)
- Via SSH: security services, content filter, app rules (esses endpoints retornam HTTP 400 na REST API)

A primeira implementação tentou rodar SSH depois do REST (ou ao mesmo tempo). O SSH falhava silenciosamente porque a sessão REST estava aberta.

## Decisão

Em `_collect_live_data`, o SSH roda **antes** de abrir qualquer conexão REST:

```python
data: dict = {"status": "online"}

if device.vendor == VendorEnum.sonicwall:
    await _collect_ssh_resources(device, data)   # SSH primeiro

try:
    connector = get_connector(device)            # REST depois
    rules = await connector.list_rules()
    ...
```

O `_collect_ssh_resources` coleta via `SonicWallSSHConnector`:
- `execute_show_commands(_SECURITY_COMMANDS)` → `data["security_services"]`
- `execute_show_commands_full(["show content-filter"])` → `data["content_filter_ssh"]`
- `execute_show_commands(["show app-rules"])` → `data["app_rules_ssh"]`

## Consequências

- ✅ SSH completa antes da sessão REST bloquear o dispositivo
- ✅ `except Exception: return data` preserva dados SSH mesmo se REST falhar depois
- ⚠️ Se SSH falhar, o snapshot ainda roda via REST (dados parciais)
- ⚠️ O mesmo padrão deve ser aplicado em qualquer nova função que precise coletar dados SSH + REST do SonicWall

## NÃO faça

- ❌ Abrir sessão REST antes de coletar SSH para SonicWall
- ❌ Tentar usar endpoints REST para content-filter/app-rules/security-services (retornam HTTP 400)
- ❌ `asyncio.sleep()` após REST esperando que a sessão feche — o SSH precisa ser antes, não depois
