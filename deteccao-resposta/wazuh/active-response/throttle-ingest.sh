#!/bin/bash
# Ameaça 2 (DDoS) — active-response do Wazuh, location=server.
# Limita-se a notificar o responder.py (porta 9100 em k3s-master), que
# aplica o throttle e agenda a sua propria remocao 60s depois (ver
# deteccao-resposta/responder/responder.py). O campo "command" enviado
# pelo wazuh-execd (add/delete) seria usado aqui se o Wazuh alguma vez
# invocasse este script em modo delete — mas nao invoca, porque a regra
# 100200/100201 nao tem decoder a extrair alert keys (relatorio, Secção
# 5.2.1). Por isso a expiracao foi movida para o responder.py.
read -r INPUT_JSON
COMMAND=$(echo "$INPUT_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('command','add'))" 2>/dev/null)

if [ "$COMMAND" = "delete" ]; then
    curl -s -m 5 -X POST "http://10.255.255.42:9100/delete" -d "{}" >> /var/ossec/logs/active-responses.log 2>&1
else
    curl -s -m 5 -X POST "http://10.255.255.42:9100/add" -d "{}" >> /var/ossec/logs/active-responses.log 2>&1
fi
