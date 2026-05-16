#!/bin/bash
# Setup step-ca para mTLS interno entre serviços FireManager
# Requer: step CLI instalado (https://smallstep.com/docs/step-cli/)

set -euo pipefail

CA_DIR="${1:-/etc/firemanager/ca}"
CA_NAME="FireManager Internal CA"
CA_DNS="ca.firemanager.internal"
CA_PORT=9000

echo "=== FireManager mTLS Setup ==="
echo "CA dir: $CA_DIR"

# 1. Criar diretório da CA
mkdir -p "$CA_DIR"

# 2. Inicializar CA
step ca init \
  --name "$CA_NAME" \
  --dns "$CA_DNS" \
  --address ":$CA_PORT" \
  --provisioner "firemanager-admin" \
  --root "$CA_DIR/root_ca.crt" \
  --key "$CA_DIR/root_ca_key" \
  --password-file <(echo "firemanager-ca-password") \
  --deployment-type standalone \
  --home "$CA_DIR"

# 3. Emitir certificados para cada serviço
for SERVICE in api celery_worker celery_beat nginx postgres redis; do
  echo "Emitindo certificado para $SERVICE..."
  step certificate create \
    "$SERVICE.firemanager.internal" \
    "$CA_DIR/certs/$SERVICE.crt" \
    "$CA_DIR/certs/$SERVICE.key" \
    --ca "$CA_DIR/root_ca.crt" \
    --ca-key "$CA_DIR/root_ca_key" \
    --ca-password-file <(echo "firemanager-ca-password") \
    --not-after 8760h \
    --san "$SERVICE" \
    --san "$SERVICE.firemanager.internal" \
    --san "localhost"
done

echo ""
echo "=== Certificados gerados em $CA_DIR/certs/ ==="
echo "Para usar com uvicorn:"
echo "  uvicorn app.main:app --ssl-keyfile=$CA_DIR/certs/api.key --ssl-certfile=$CA_DIR/certs/api.crt"
echo ""
echo "Próximo passo: montar os certs como volumes no docker-compose.yml"
