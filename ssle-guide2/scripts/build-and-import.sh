#!/usr/bin/env bash
# Parte 5.2 — constrói as imagens no container "docker" e importa-as nos nós k3s (correr na VM)
set -euo pipefail
cd "$(dirname "$0")/.."

SERVICES="registry storage ingestion analytics sensor"
TAG=v1
NODES="k3s-master k3s-node1"

echo ">> A copiar o código para o container docker"
incus exec docker -- rm -rf /root/app
incus file push -r app docker/root/

IMAGES=""
for s in $SERVICES; do
  echo ">> docker build ssle/$s:$TAG"
  incus exec docker -- docker build --build-arg SERVICE="$s" -t "ssle/$s:$TAG" /root/app
  IMAGES+=" ssle/$s:$TAG"
done

echo ">> A exportar imagens"
incus exec docker -- docker save -o /root/ssle-images.tar $IMAGES
incus file pull docker/root/ssle-images.tar /tmp/ssle-images.tar

for n in $NODES; do
  echo ">> A importar em $n"
  incus file push /tmp/ssle-images.tar "$n/root/ssle-images.tar"
  incus exec "$n" -- k3s ctr images import /root/ssle-images.tar
  incus exec "$n" -- rm -f /root/ssle-images.tar
done
rm -f /tmp/ssle-images.tar

echo ">> Imagens no k3s:"
incus exec k3s-master -- k3s crictl images | grep ssle || true
