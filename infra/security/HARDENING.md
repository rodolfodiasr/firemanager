# FireManager — Security Hardening Guide

## Docker Network Isolation

| Rede | Serviços | Acesso Externo |
|---|---|---|
| frontend_net | nginx, frontend, grafana | Sim (nginx expõe 80/443) |
| backend_net | api, redis, postgres, prometheus | Não (internal) |
| worker_net | celery_worker, celery_beat, redis | Não (internal) |
| monitoring_net | prometheus, grafana | Não (acessado via grafana em frontend_net) |

## Seccomp

O profile `seccomp-default.json` aplica allowlist de syscalls.
Ativado via `security_opt: seccomp:./security/seccomp-default.json`.

Syscalls bloqueadas relevantes: `ptrace` (evita debugging/injection).

## AppArmor

O profile `apparmor-api.conf` deve ser carregado no host antes de usar:

```bash
sudo apparmor_parser -r -W infra/security/apparmor-api.conf
```

Depois descomentar `apparmor:firemanager-api` no docker-compose.yml.

## mTLS Interno

Ver `infra/scripts/setup-mtls.sh`. Requer step CLI no host.
Certificados ficam em `/etc/firemanager/ca/certs/`.
TTL: 8760h (1 ano). Renovar com `step certificate renew`.

## Checklist de Hardening

- [x] Redes Docker isoladas (internal: true para backend/worker)
- [x] no-new-privileges para api/celery_worker/celery_beat
- [x] cap_drop: ALL (remover todas as Linux capabilities desnecessárias)
- [x] Seccomp allowlist (syscalls mínimas)
- [ ] AppArmor (requer setup no host — ver acima)
- [ ] mTLS interno (requer step-ca — ver script)
- [ ] Vault HA (3 nodes) — ver F34 roadmap
- [ ] OPA sidecar real — ver F34 roadmap
