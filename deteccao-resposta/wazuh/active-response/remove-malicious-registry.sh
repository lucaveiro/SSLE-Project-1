#!/bin/bash
# Ameaça 1 (Route/Signals Hijacking) — active-response do Wazuh, regra 100102.
# Remove do Service Registry qualquer instância de storage-service registada
# por um nó fora da whitelist (k3s-node1 / k3s-master).
# Cópia verbatim de /var/ossec/active-response/bin/remove-malicious-registry.sh
# em wazuh-container.

MASTER="10.255.255.42"
ALL=$(curl -s "http://$MASTER:30050/services")

IDS=$(echo "$ALL" | grep -oE "\"[^\"]*storage-service[^\"]*\":\{" | grep -oE "\"[^\"]*\"" | tr -d "\"")

for ID in $IDS; do
  if ! echo "$ID" | grep -qE "k3s-node1\.storage-service|k3s-master\.storage-service"; then
    curl -s -X DELETE "http://$MASTER:30050/unregister" \
      -H "Content-Type: application/json" \
      -d "{\"name\":\"storage-service\",\"instance_id\":\"$ID\"}" \
      >> /var/ossec/logs/active-responses.log 2>&1
    echo "removed instance: $ID" >> /var/ossec/logs/active-responses.log
  fi
done
