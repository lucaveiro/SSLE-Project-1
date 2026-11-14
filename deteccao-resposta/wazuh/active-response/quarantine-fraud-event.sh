#!/bin/bash
# Ameaça 3 (Botnet/Fraude) — active-response do Wazuh, regra 100300.
# Resposta de auditoria, não de remediação: não existe no storage-service
# nenhum endpoint de eliminação seletiva de um registo forjado, por isso
# o script apenas regista o incidente de forma persistente e consultável
# (relatório, Secção 5.3.1).
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) FRAUD_DETECTED" >> /var/ossec/etc/lists/ssle-fraud-quarantine.log
