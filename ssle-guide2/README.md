# SSLE — Guião 2, Secção 5

Os serviços do Guião 1 (registry, storage, ingestion, analytics, sensor) empacotados de duas formas:
**5.1** como containers Incus e **5.2** como imagens Docker no k3s.

## Estrutura
```
app/                         código dos serviços + Dockerfile único (uma imagem por serviço)
incus/deploy-incus.sh        5.1 — um container Incus por serviço
scripts/build-and-import.sh  5.2 — build no container docker + import nos nós k3s
scripts/deploy-k8s.sh        5.2 — kubectl apply
k8s/*.yaml                   manifestos (namespace ssle)
```

## Alterações ao código original (para correr em containers)
| Problema | Alteração |
|---|---|
| `app.run()` só escuta em 127.0.0.1 | `BIND_HOST` (0.0.0.0 nos containers, 127.0.0.1 por omissão) |
| Registo com `http://127.0.0.1:PORT` (o registry e os outros serviços não lhe chegam, e o health check removia-os) | `SERVICE_URL` configurável, via `service_url()` no `common.py` |
| Registo feito uma só vez: se o registry reiniciar, perde tudo | Heartbeat: re-registo a cada `HEARTBEAT` segundos |
| Réplicas no mesmo nó geravam o mesmo ID hierárquico | `INSTANCE` substitui a porta no último segmento (nome do pod) |
| BD ao lado do código, sem volume | `DB_PATH` configurável (volume persistente) |
| Registry sem `/health` | Adicionado (usado pelas probes do Kubernetes) |
| `handled_by` devolvia só a porta | Devolve o ID da instância (vê-se o round-robin) |

## 5.1 — Incus
```bash
./incus/deploy-incus.sh
IP=$(incus list analytics -c4 --format csv | cut -d' ' -f1)
curl http://$IP:5003/average
incus exec sensor -- journalctl -u ssle-app -f
```

## 5.2 — Docker + k3s
```bash
./scripts/build-and-import.sh
./scripts/deploy-k8s.sh
incus exec k3s-master -- k3s kubectl -n ssle get pods -o wide
curl http://<IP_k3s-master>:30003/average      # analytics
curl http://<IP_k3s-master>:30050/services     # registry (2 réplicas da ingestion)
incus exec k3s-master -- k3s kubectl -n ssle logs deploy/sensor -f
```

Depois de alterar o código: corre de novo o `build-and-import.sh` e depois
`incus exec k3s-master -- k3s kubectl -n ssle rollout restart deploy`.

## Limpar
```bash
incus exec k3s-master -- k3s kubectl delete ns ssle
incus delete --force registry storage ingestion analytics sensor
```
