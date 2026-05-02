# ADR-008: Logging — usar structlog, não logging padrão

**Status:** Ativo  
**Data:** 2026-05-02  
**Componentes:** Todos os módulos do backend

## Contexto

O backend usa `structlog` para logging. Módulos que importam `logging` padrão do Python têm suas mensagens **silenciosamente descartadas** — não aparecem nos logs do container.

Isso causou um debugging longo na integração SSH do BookStack: o código SSH estava sendo executado e as funções chamadas, mas nenhuma mensagem de log aparecia, levando à conclusão errada de que o código não estava sendo executado.

## Decisão

Sempre usar structlog em todos os módulos do backend:

```python
# ✅ Correto
import structlog
log = structlog.get_logger()

log.info("sw_snapshot_ssh_security", device=device.name, count=len(data))
log.warning("sw_snapshot_ssh_exception", device=device.name, error=str(exc))

# ❌ Silenciosamente descartado
import logging
logger = logging.getLogger(__name__)
logger.info("mensagem")
```

Usar nomes de evento descritivos em snake_case com contexto como kwargs — facilita grep nos logs.

## Consequências

- ✅ Logs aparecem no `docker compose logs -f api`
- ✅ Contexto estruturado (kwargs) permite filtrar por device, tenant, etc.
- ⚠️ Em novos módulos, verificar que o import é `structlog` antes de depurar comportamento ausente
- ⚠️ Se um módulo não produz nenhum log mesmo com código aparentemente correto, verificar o import de logging primeiro

## NÃO faça

- ❌ `import logging` em qualquer módulo do backend
- ❌ `print()` para debugging — não aparece estruturado e não tem contexto
- ❌ Confundir ausência de logs com ausência de execução do código
