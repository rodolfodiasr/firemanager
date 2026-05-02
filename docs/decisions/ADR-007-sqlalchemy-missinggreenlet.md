# ADR-007: SQLAlchemy — refresh obrigatório após flush()

**Status:** Ativo  
**Data:** 2026-05-02  
**Componentes:** Qualquer service que usa SQLAlchemy async

## Contexto

Campos com `onupdate=func.now()` (como `updated_at`) são **expirados** pelo SQLAlchemy após `flush()`. Tentar acessá-los após o flush sem fazer `refresh` dispara um lazy load fora do contexto async, resultando em:

```
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; 
can't call await from the current thread
```

O erro é difícil de diagnosticar porque aparece na serialização (no schema Pydantic), não na linha do flush.

## Decisão

Sempre fazer `refresh` após `flush` antes de serializar:

```python
# ❌ Causa MissingGreenlet
await db.flush()
return schema_from_orm(objeto)  # acessa updated_at → lazy load fora do contexto

# ✅ Correto
await db.flush()
await db.refresh(objeto)  # recarrega atributos expirados
return schema_from_orm(objeto)
```

## Consequências

- ✅ Evita `MissingGreenlet` em operações de escrita
- ✅ Schema retorna valores atualizados (inclusive timestamps gerados pelo banco)
- ⚠️ `refresh` faz uma query adicional ao banco — custo aceitável para operações de escrita
- ⚠️ O erro só aparece em campos com `server_default` ou `onupdate` gerados pelo banco — campos Python puro não são afetados

## NÃO faça

- ❌ `flush()` seguido de acesso a atributos sem `refresh()`
- ❌ Assumir que `flush()` é equivalente a `commit()` para fins de leitura de campos gerados pelo banco
