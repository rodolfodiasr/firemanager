# ADR-005: Multi-tenant — Isolamento por tenant_id em todas as queries

**Status:** Ativo  
**Data:** 2026-05-02  
**Componentes:** `models/`, `api/`, `services/`

## Contexto

FireManager é uma plataforma MSSP (Managed Security Service Provider) — múltiplos clientes (tenants) compartilham a mesma instância. Sem isolamento correto, um tenant pode acessar dados de outro.

O sistema tem dois tipos de usuário:
1. **Usuário normal** — tem `tenant_id` no JWT, vê apenas seus dados
2. **Super admin** (`is_super_admin: bool`) — acesso cross-tenant (suporte MSSP), **não tem** `tenant_id` no JWT

## Decisão

### Herança de variáveis

Tenant → Device: device sobrescreve configurações do tenant. Padrão `or`:

```python
timeout = device.timeout or tenant.timeout or DEFAULT_TIMEOUT
```

### Roles por tenant

`TenantRole`: `admin`, `analyst`, `readonly` — permissões dentro de um tenant.

### Queries com branch para super admin

```python
# ❌ Quebra para super admin — tenant_id é None
query = select(Device).where(Device.tenant_id == current_user.tenant_id)

# ✅ Branch explícita
if current_user.is_super_admin:
    query = select(Device)
else:
    query = select(Device).where(Device.tenant_id == current_user.tenant_id)
```

### JWT

Super admin não tem `tenant_id` no token — validação de `tenant_id` no JWT não funciona para eles.

## Consequências

- ✅ Tenants são completamente isolados por padrão
- ✅ Super admin tem visibilidade cross-tenant para suporte
- ⚠️ Todo novo endpoint deve ter branch explícita para super admin
- ⚠️ Toda nova query que filtra por `tenant_id` deve verificar `is_super_admin` primeiro

## NÃO faça

- ❌ `WHERE tenant_id = :tid` sem verificar se é super admin
- ❌ Assumir que `current_user.tenant_id` sempre existe — para super admin é `None`
- ❌ Misturar lógica de roles com lógica de super admin — são mecanismos separados
