# ADR-003: SonicWall — Detecção automática de versão SonicOS

**Status:** Ativo  
**Data:** 2026-05-02  
**Componentes:** `sonicwall.py`

## Contexto

SonicOS 6.x e 7.x têm **formatos de payload completamente diferentes** para as mesmas operações. Por exemplo, access rules:

```python
# SonicOS 7 — access_rules com wrapper
{"access_rules": [{"ipv4": {"name": "...", "action": "allow", ...}}]}

# SonicOS 6 — direto
{"access_rules": [{"name": "...", "action": "allow", ...}}
```

Sem detectar a versão, qualquer operação de escrita falha silenciosamente ou retorna HTTP 400.

## Decisão

Detectar a versão no `test_connection()` e salvar em `device.firmware_version`:

```python
async def test_connection(self) -> ConnectionResult:
    response = await client.get("/api/sonicos/version")
    version_str = response.json().get("firmware_version", "")
    # Exemplo: "SonicOS 7.1.1-7058-R3906"
    major = int(version_str.split(" ")[1].split(".")[0])  # → 7
    device.firmware_version = version_str
    return ConnectionResult(success=True, firmware_version=version_str)
```

Em operações que diferem por versão, verificar:

```python
major = int((device.firmware_version or "SonicOS 6").split(" ")[1].split(".")[0])
if major >= 7:
    payload = {"ipv4": {...}}
else:
    payload = {...}
```

## Consequências

- ✅ Operações funcionam corretamente independente da versão do firmware
- ✅ `firmware_version` fica salvo no banco e aparece na UI
- ⚠️ Se `firmware_version` for `None` (dispositivo nunca passou pelo `test_connection`), usar SonicOS 6 como fallback seguro
- ⚠️ Health check já atualiza `firmware_version` via `getattr(check_result, "firmware_version", None)`

## NÃO faça

- ❌ Hardcodar formato de payload sem verificar versão
- ❌ `creds.get("vdom", "root")` — padrão do dict não funciona se a chave existe com valor `null`; usar `creds.get("vdom") or "root"` (padrão Fortinet, mas o mesmo princípio se aplica)
- ❌ Usar `/api/sonicos/version` para health check sem auth — retorna `E_UNAUTHORIZED` sem info útil
