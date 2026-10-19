#!/usr/bin/env bash
# Aplica os manifestos no cluster k3s (correr na VM)
set -euo pipefail
cd "$(dirname "$0")/.."

incus exec k3s-master -- rm -rf /root/k8s
incus file push -r k8s k3s-master/root/
incus exec k3s-master -- k3s kubectl apply -f /root/k8s/
echo
incus exec k3s-master -- k3s kubectl -n ssle get pods,svc -o wide
