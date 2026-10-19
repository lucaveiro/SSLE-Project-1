#!/usr/bin/env bash
# Parte 5.1 — cada serviço num container Incus próprio (correr na VM, dentro da pasta ssle-guide2)
set -euo pipefail
cd "$(dirname "$0")/.."

REG="http://registry.incus:5050"

deploy() {   # deploy <container> <script> <VAR=valor ...>
  local name=$1 script=$2; shift 2

  if ! incus info "$name" >/dev/null 2>&1; then
    echo ">> A criar container $name"
    incus launch images:debian/trixie "$name"
  fi

  echo ">> À espera de rede em $name"
  until incus exec "$name" -- getent hosts deb.debian.org >/dev/null 2>&1; do sleep 2; done

  echo ">> A instalar Python/Flask em $name"
  incus exec "$name" -- apt-get update -qq
  incus exec "$name" -- env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-flask python3-requests

  incus exec "$name" -- mkdir -p /opt/app /data
  incus file push app/common.py "app/$script" "$name/opt/app/"

  local envlines=""
  for kv in "$@"; do envlines+="Environment=$kv"$'\n'; done

  incus exec "$name" -- sh -c 'cat > /etc/systemd/system/ssle-app.service' <<UNIT
[Unit]
Description=SSLE $script
After=network-online.target
Wants=network-online.target

[Service]
${envlines}Environment=BIND_HOST=0.0.0.0
Environment=PYTHONUNBUFFERED=1
Environment=LOC_DC=dc-incus
Environment=LOC_RACK=incusbr
Environment=LOC_NODE=$name
WorkingDirectory=/opt/app
ExecStart=/usr/bin/python3 /opt/app/$script
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

  incus exec "$name" -- systemctl daemon-reload
  incus exec "$name" -- systemctl enable ssle-app
  incus exec "$name" -- systemctl restart ssle-app
  echo ">> $name OK"
}

deploy registry  registry.py  PORT=5050
deploy storage   storage.py   PORT=5002 SERVICE_URL=http://storage.incus:5002   REGISTRY_URL=$REG DB_PATH=/data/temp_data.db
deploy ingestion ingestion.py PORT=5001 SERVICE_URL=http://ingestion.incus:5001 REGISTRY_URL=$REG
deploy analytics analytics.py PORT=5003 SERVICE_URL=http://analytics.incus:5003 REGISTRY_URL=$REG
deploy sensor    sensor.py    REGISTRY_URL=$REG

echo
incus list
