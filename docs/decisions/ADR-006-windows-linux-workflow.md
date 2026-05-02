# ADR-006: Workflow de desenvolvimento — Windows (Claude Code) → Linux VM (Docker)

**Status:** Ativo  
**Data:** 2026-05-02  
**Componentes:** Infraestrutura de desenvolvimento

## Contexto

Claude Code (e o desenvolvedor) trabalha no Windows em `C:\Users\rodolfo.dias\firemanager\`. O Docker roda em uma VM Linux em `/home/admeternity/firemanager/`. São **filesystems completamente separados** — edições no Windows NÃO chegam automaticamente ao Linux.

Isso causou múltiplos incidentes onde mudanças foram aplicadas e verificadas no Windows, mas o comportamento em produção (container) não mudou porque o arquivo na VM estava intacto.

## Decisão

### Fluxo padrão

1. Editar arquivos no Windows (Claude Code edita aqui)
2. Sincronizar para VM Linux via git push + pull (caminho preferencial)
3. O volume mount `../backend:/app` + hot-reload do uvicorn detecta mudanças automaticamente

```bash
# Na VM Linux — verificar se mudança chegou
grep -n "texto_do_codigo_novo" /home/admeternity/firemanager/backend/app/services/arquivo.py
```

### Para patches urgentes direto na VM

Quando não dá para sincronizar via git, aplicar diretamente na VM:

```bash
# ✅ Python one-liner (sem heredoc — heredoc é corrompido pelo terminal SSH)
python3 -c "
content = open('/path/to/file.py').read()
content = content.replace('OLD_STRING', 'NEW_STRING')
open('/path/to/file.py', 'w').write(content)
print('OK')
"

# ✅ Nano para edições interativas
nano /home/admeternity/firemanager/backend/app/services/bookstack_service.py
```

### Heredoc — NUNCA usar para patches Python

```bash
# ❌ Heredoc single-quoted passa \n literal → Python interpreta como escape → código corrompido
python3 << 'X'
content = content.replace('OLD\nNEW', 'REPLACED')
X

# ✅ Usar python3 -c com string normal, ou nano
```

## Recorrência

Este problema causou pelo menos 3 ciclos de debugging onde código "correto" no Windows não funcionava porque a VM não tinha as mudanças. Verificar **sempre** que mudanças chegaram à VM antes de testar.

## Consequências

- ✅ Git é o mecanismo de sync mais confiável e auditável
- ⚠️ Hot-reload só funciona se o arquivo na VM foi modificado — não adianta editar no Windows
- ⚠️ Após restart do container `api`, reiniciar também o `nginx` (DNS cache):
  ```bash
  docker compose -f infra/docker-compose.yml restart nginx
  ```
- ⚠️ Python one-liners com `python3 -c` são robustos para patches simples; heredoc não é

## NÃO faça

- ❌ Assumir que edição no Windows chegou ao container
- ❌ Usar heredoc SSH para passar código Python com strings multilinhas
- ❌ Restart de `api` sem restart de `nginx` — retorna 502 silencioso por DNS cache
- ❌ `docker compose exec postgres psql -U postgres` — usuário é `fm_user`
