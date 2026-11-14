#!/bin/bash
# Ameaça 3 (Botnet/Fraude de dados) — loop de polling ao endpoint /average
# do analytics, a cada 5s, com a saída filtrada por check_analytics.py
# (que emite "[ANOMALY] ..." quando o valor está fora da gama física válida,
# detetado pela regra 100300 do Wazuh via log[] do Zabbix em
# /var/log/analytics-poll.log).
# Cópia verbatim de /opt/analytics_poll.sh em k3s-master.

while true; do
  curl -s http://localhost:30003/average | python3 /opt/check_analytics.py
  sleep 5
done
