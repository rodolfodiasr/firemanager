# Guia de Rollback — Eternity SecOps

Referência rápida para reverter a plataforma a um estado anterior.  
Sempre execute o downgrade do banco **antes** de trocar o código.

---

## Mapa de Commits por Fase

| Commit    | Descrição                                              | Migration head |
|-----------|--------------------------------------------------------|----------------|
| `8d44c0a` | Security Hardening P1–P6 (redes, guardrails, multi-sig) | 0018          |
| `60f83a1` | Conector Sophos Firewall (SFOS XML API)                 | 0017          |
| `739a473` | P4 — métodos estruturados Cisco IOS e Juniper JunOS     | 0017          |
| `8ce1e23` | P3 — SNAT MikroTik, DPI-SSL SonicWall, security status  | 0017          |
| `5fad3ec` | P2 — security services, VPN status, routing protocols   | 0017          |
| `88ae982` | P1 — pfSense/OPNsense routes + Endian SSH               | 0017          |

---

## Procedimento Padrão de Rollback

### Passo 1 — Identificar o commit alvo

```bash
git log --oneline -10
```

Anote o hash do commit para o qual quer voltar (coluna "Commit" na tabela acima).

### Passo 2 — Reverter o banco (OBRIGATÓRIO antes de trocar o código)

```bash
cd /home/admeternity/firemanager
docker compose -f infra/docker-compose.yml exec api alembic downgrade <migration_head_do_alvo>
```

**Exemplo:** voltar para o estado anterior ao hardening (commit `60f83a1`, migration head `0017`):
```bash
docker compose -f infra/docker-compose.yml exec api alembic downgrade 0017
```

### Passo 3a — Reverter sem apagar histórico (recomendado em produção)

Cria um novo commit que desfaz as mudanças, mantendo o histórico intacto:

```bash
git revert <hash_do_commit_a_desfazer> --no-edit
git push origin main
```

No Linux:
```bash
git pull origin main
docker compose -f infra/docker-compose.yml up -d --force-recreate
docker compose -f infra/docker-compose.yml restart nginx
```

### Passo 3b — Resetar o branch para o ponto exato (apaga o histórico)

> Use apenas se tiver certeza de que ninguém fez `git pull` do commit a ser descartado.

```bash
git reset --hard <hash_do_commit_alvo>
git push origin main --force
```

No Linux:
```bash
git pull origin main --force
docker compose -f infra/docker-compose.yml up -d --force-recreate
docker compose -f infra/docker-compose.yml restart nginx
```

---

## Rollbacks Específicos por Fase

### Voltar para antes do Security Hardening (P1–P6)

**O que é revertido:** redes Docker, guardrails, rate limiting, multi-sig, RLS, trigger audit_log.

```bash
# 1. Downgrade do banco (remove colunas P6 + triggers P3 + RLS P2)
docker compose -f infra/docker-compose.yml exec api alembic downgrade 0017

# 2. Revert do código
git revert 8d44c0a --no-edit
git push origin main

# 3. Atualizar e reiniciar
git pull origin main
docker compose -f infra/docker-compose.yml up -d --force-recreate
docker compose -f infra/docker-compose.yml restart nginx
```

### Voltar para antes do conector Sophos

```bash
docker compose -f infra/docker-compose.yml exec api alembic downgrade 0016
git revert 60f83a1 --no-edit
git push origin main
git pull origin main
docker compose -f infra/docker-compose.yml up -d --force-recreate
docker compose -f infra/docker-compose.yml restart nginx
```

---

## Regras de Ouro

1. **Banco primeiro, código depois.** Nunca troque o código sem fazer o downgrade — a aplicação sobe com erro de coluna/tabela faltando.
2. **`git revert` é mais seguro que `git reset --hard`** em produção. O revert preserva histórico e é rastreável.
3. **Após qualquer restart de container de backend, reiniciar nginx.** O nginx faz cache de DNS e aponta para o IP antigo sem o restart.
4. **Verificar se as mudanças chegaram ao Linux** antes de reiniciar:
   ```bash
   git log --oneline -3
   ```
5. **Migrations são cumulativas.** Para voltar 3 commits, o `downgrade` precisa ir até a migration correspondente — não basta reverter só o último.

---

## Verificar estado atual das migrations

```bash
docker compose -f infra/docker-compose.yml exec api alembic current
docker compose -f infra/docker-compose.yml exec api alembic history --verbose | head -20
```
