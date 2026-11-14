# Zabbix — items e triggers (Fase 4)

A configuração do Zabbix vive na base de dados do servidor (UI/API), não
em ficheiros versionáveis — este documento é a referência textual usada
para recriar os items/triggers manualmente ou via `zabbix_sender`/API,
consolidada a partir do relatório (`relatorio-ssle-projeto1.md`, Secções
5.1.1, 5.2.1, 5.3.1).

Host: `ssle-k3s-cluster` · Agente: `Zabbix agent (active)`, `ServerActive`
configurado no agente em `k3s-master`.

## Ameaça 1 — Hijacking

- **Item:** `log[/var/log/registry-stream.log,"\\[\\+\\].*storage-service",,,skip]`
  (Update interval: 10s)
- **Trigger:** dispara quando o log mostra um registo de `storage-service`
  fora dos nós conhecidos — problema "Possivel hijacking do Service
  Registry", severidade **High**.

## Ameaça 2 — DDoS

- **Item:** `log[/var/log/ingestion-stream.log,"POST \\/ingest",,,skip]`
  (Update interval: 2s)
- **Trigger:** `count(/ssle-k3s-cluster/log[...],10s)>20` — problema
  "Ingestion: request rate", severidade **High**.
- **Achado documentado:** uma primeira tentativa usou CPU do pod
  (`kubectl top pods` via `UserParameter`) — abandonada por não produzir
  variação mensurável sob flood curto (ver relatório 5.2.1).

## Ameaça 3 — Fraude de dados

- **Item:** `log[/var/log/analytics-poll.log,"\\[ANOMALY\\]",,,skip]`
  (Update interval: 2s)
- **Trigger:** `find(/ssle-k3s-cluster/log[...],300,"iregexp","ANOMALY")=1`
  — problema "Possivel fraude de dados — valor fora da gama física",
  severidade **High**.

Capturas de ecrã reais de cada um destes problemas em
`evidencias/evidencias-detecao/`.
