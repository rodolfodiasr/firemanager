# Architecture Decision Records (ADRs)

Decisões técnicas importantes do FireManager, com contexto e anti-patterns documentados.

| ADR | Título | Componentes |
|-----|--------|-------------|
| [ADR-001](ADR-001-sonicwall-ssh-antes-rest.md) | SonicWall — SSH deve rodar antes do REST | bookstack_service, sonicwall_ssh, sonicwall |
| [ADR-002](ADR-002-sonicwall-digest-auth.md) | SonicWall — Digest Auth obrigatório | sonicwall.py |
| [ADR-003](ADR-003-sonicwall-version-detection.md) | SonicWall — Detecção automática de versão SonicOS | sonicwall.py |
| [ADR-004](ADR-004-cli-vendors-ssh-only.md) | Vendors CLI — SSH exclusivo via CLI_VENDORS | factory.py, health_check.py |
| [ADR-005](ADR-005-multi-tenant-row-level.md) | Multi-tenant — Isolamento por tenant_id | models, api, services |
| [ADR-006](ADR-006-windows-linux-workflow.md) | Workflow Windows → Linux VM | Infra de desenvolvimento |
| [ADR-007](ADR-007-sqlalchemy-missinggreenlet.md) | SQLAlchemy — refresh obrigatório após flush() | Todos os services async |
| [ADR-008](ADR-008-structlog-obrigatorio.md) | Logging — usar structlog, não logging padrão | Todos os módulos backend |

## Como usar estes ADRs

Antes de implementar algo novo que envolva um dos componentes acima, leia o ADR correspondente. Os arquivos `CLAUDE.md` na raiz e em `backend/` referenciam as mesmas regras de forma mais compacta para consulta rápida.

## Como adicionar um novo ADR

```
ADR-NNN-titulo-curto.md
```

Estrutura obrigatória: Contexto → Decisão → Consequências → NÃO faça.
