# ADR-010 — BookStack: snapshot incremental com hash SHA-256

## Contexto

O worker de snapshot sobrescrevia a página BookStack a cada execução, mesmo quando o estado do dispositivo não havia mudado. Isso gerava histórico de revisões desnecessário no BookStack e requisições REST evitáveis.

## Decisão

Antes de escrever no BookStack, calcular `sha256` do markdown gerado e comparar com `Snapshot.config_hash` do último snapshot salvo para o dispositivo:

- Se hash igual: skip da escrita (log `snapshot_unchanged_skip`)
- Se hash diferente (ou sem snapshot anterior): escrever no BookStack e salvar novo `Snapshot` com o hash

O modelo `Snapshot` tem campo `config_hash: str | None`.

## NÃO faça

- ❌ Comparar timestamps em vez de hash — timestamp muda sempre, hash reflete conteúdo real
- ❌ Pular o registro do `Snapshot` mesmo no skip — o registro é a fonte da verdade do último estado conhecido

## Consequências

- BookStack não acumula revisões idênticas
- Reduz carga de requisições em ambientes com muitos dispositivos estáticos
- `Snapshot.config_hash` serve de referência para futuro diff de política
