# ADR-002: SonicWall — Digest Auth obrigatório (não Basic Auth)

**Status:** Ativo  
**Data:** 2026-05-02  
**Componentes:** `sonicwall.py`

## Contexto

A REST API do SonicWall requer autenticação **Digest** no endpoint `POST /api/sonicos/auth`. Se a requisição for enviada com Basic Auth (padrão do `httpx` quando se passa `auth=(user, pass)`), o servidor retorna HTTP 401 mesmo com credenciais corretas.

Esse problema causou horas de debugging porque o erro 401 sugeria credenciais inválidas, não método de auth incorreto.

## Decisão

Usar `httpx.DigestAuth` explicitamente em todas as requisições SonicWall:

```python
import httpx

auth = httpx.DigestAuth(username, password)
response = await client.post("/api/sonicos/auth", auth=auth, json={"override": True})
```

Nunca usar `auth=(username, password)` (que é Basic Auth) ou omitir auth.

## Consequências

- ✅ Auth funciona corretamente com SonicOS 6.x e 7.x
- ⚠️ O `httpx.DigestAuth` faz **dois roundtrips** (primeiro recebe 401 com o nonce, depois reenvia com hash) — isso é normal e esperado
- ⚠️ Fortinet usa token no header — não misturar padrões entre connectors

## NÃO faça

- ❌ `auth=(username, password)` em clientes httpx para SonicWall
- ❌ `Authorization: Basic ...` header manual
- ❌ Assumir que 401 significa credenciais erradas — verifique o método de auth primeiro
