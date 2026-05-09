#!/usr/bin/env bash
# deploy-staging.sh — sobe ou atualiza o frontend de homologação
#
# Uso:
#   ./scripts/deploy-staging.sh          # build + sobe
#   ./scripts/deploy-staging.sh down     # derruba o container de staging
#   ./scripts/deploy-staging.sh logs     # acompanha os logs do staging
#   ./scripts/deploy-staging.sh status   # mostra o estado dos serviços
#
# Pré-requisito: rodar na VM Linux dentro de /home/admeternity/firemanager/

set -euo pipefail

COMPOSE="docker compose -f infra/docker-compose.yml"
SERVICE="frontend-staging"
STAGING_PORT=8080

# Detecta IP da VM para exibir a URL ao final
VM_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "IP_DA_VM")

# ── Funções auxiliares ────────────────────────────────────────────────────────

print_step() { echo -e "\n\033[1;34m▶ $1\033[0m"; }
print_ok()   { echo -e "\033[1;32m✔ $1\033[0m"; }
print_warn() { echo -e "\033[1;33m⚠ $1\033[0m"; }

# ── Subcomandos ───────────────────────────────────────────────────────────────

case "${1:-up}" in

  down)
    print_step "Derrubando frontend de homologação..."
    $COMPOSE --profile staging stop $SERVICE
    $COMPOSE --profile staging rm -f $SERVICE
    print_ok "frontend-staging removido."
    exit 0
    ;;

  logs)
    exec $COMPOSE --profile staging logs -f $SERVICE
    ;;

  status)
    $COMPOSE --profile staging ps
    exit 0
    ;;

  up|"")
    # Segue para o bloco de build abaixo
    ;;

  *)
    echo "Uso: $0 [up|down|logs|status]"
    exit 1
    ;;

esac

# ── Build + up ────────────────────────────────────────────────────────────────

print_step "Garantindo que o nginx tem a porta $STAGING_PORT exposta..."
if ! $COMPOSE ps nginx | grep -q "Up"; then
  print_warn "nginx não está rodando — iniciando..."
  $COMPOSE up -d nginx
fi

print_step "Fazendo build do frontend-staging (pode levar ~2 min)..."
$COMPOSE --profile staging build --no-cache $SERVICE

print_step "Subindo frontend-staging..."
$COMPOSE --profile staging up -d $SERVICE

print_step "Reiniciando nginx para atualizar upstream DNS..."
$COMPOSE restart nginx

# Aguarda o container ficar healthy
print_step "Aguardando container inicializar..."
for i in $(seq 1 15); do
  if $COMPOSE --profile staging ps $SERVICE | grep -q "Up"; then
    break
  fi
  sleep 2
done

echo ""
print_ok "Homologação disponível em: http://${VM_IP}:${STAGING_PORT}"
print_ok "Produção continua em:      http://${VM_IP}:80"
echo ""
print_warn "Lembrete: este frontend compartilha a API de produção."
print_warn "Dados criados/modificados aqui afetam o banco de produção."
echo ""
