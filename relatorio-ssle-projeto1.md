# SSLE — Projeto 1
## Design and Run a Service-Based Architecture that Scales

**Autor:** Lucas Rebelo
**Entrega:** 22 de novembro de 2026

Estrutura conforme `Projeto.pdf`, slide 4 ("Classic article/thesis structure"):
Introduction · Relevant State of the Art · Service Architecture Used ·
Risk Management and Mitigation · Approach to three threats considered ·
Evaluation of the solution's approaches and scalability · Conclusions

---

## 1. Introduction

Sistemas distribuídos de larga escala assentam cada vez mais em
arquiteturas orientadas a serviços (SOA), onde múltiplos componentes
independentes comunicam através de um mecanismo de descoberta partilhado.
Esta descentralização traz benefícios de escalabilidade e manutenibilidade,
mas desloca também a superfície de ataque: comprometer o ponto de
descoberta compromete, por transitividade, todos os serviços que nele
confiam.

Este relatório documenta o desenho, implementação e análise de segurança
de uma arquitetura SOA de pequena escala — um pipeline de ingestão,
armazenamento e análise de dados de sensores — construída sobre os Guiões
1 e 2 da disciplina e empacotada num cluster Kubernetes (k3s) dentro de
contentores Incus. O objetivo do Projeto 1 é duplo: (i) desenhar e correr
uma arquitetura orientada a serviços capaz de escalar, com um esquema de
identificação e localização hierárquico adequado a ambientes de larga
escala; e (ii) analisar, explorar na prática e propor mitigação para três
ameaças do syllabus da cadeira — route/signals hijacking, denial-of-service
massivo, e botnets/fraude de dados — completando o ciclo exploração →
deteção → resposta → post-mortem para cada uma.

O relatório está organizado da seguinte forma: a Secção 2 enquadra os
conceitos teóricos relevantes (SOA, FCAPS, monitorização de larga escala,
SIEM e Attack-Defense Trees); a Secção 3 descreve a arquitetura de
serviços implementada; a Secção 4 apresenta a metodologia de gestão de
risco, incluindo a superfície de ataque e as três ADTrees construídas; a
Secção 5 detalha, para cada uma das três ameaças escolhidas, a sua
exploração prática (prova de conceito), deteção e resposta; a Secção 6
avalia a escalabilidade da solução; e a Secção 7 fecha com as principais
conclusões e limitações identificadas. Este é o Projeto 1 de um conjunto
de dois: o foco aqui está na deteção e prevenção de ameaças, enquanto o
Projeto 2, subsequente, reutilizará esta mesma arquitetura para abordar
tolerância a ataques.

---

## 2. Relevant State of the Art

Esta secção enquadra os conceitos teóricos sobre os quais o restante
relatório assenta: a arquitetura orientada a serviços como padrão de
design, o modelo de gestão de falhas FCAPS e a sua lacuna face a eventos
de segurança, as abordagens de monitorização de larga escala consideradas,
e a metodologia de modelação de ameaças (Attack-Defense Trees) usada na
Secção 4.

### 2.1 Service-Oriented Architecture / Microservices

Uma arquitetura orientada a serviços (SOA) decompõe um sistema num
conjunto de serviços independentes, fracamente acoplados (*loose
coupling*), que comunicam através de contratos bem definidos em vez de
partilharem estado ou memória. Os papéis clássicos de uma SOA — *provider*
(quem presta o serviço), *consumer* (quem o consome) e *broker/registry*
(o intermediário que permite a descoberta mútua, desacoplando consumidores
de endereços fixos de providers) — são todos representados na arquitetura
deste projeto: o Service Registry assume o papel de broker, enquanto os
restantes quatro serviços alternam entre provider e consumer consoante a
direção do fluxo de dados (por exemplo, o Storage é provider para o
Ingestion e para o Analytics, mas consumer do Registry).

A propriedade de *discoverability* — um serviço anunciar a sua presença e
localização sem exigir configuração estática nos seus consumidores — é o
que permite a uma SOA escalar horizontalmente (múltiplas réplicas de um
mesmo serviço, descobertas de forma transparente) e geograficamente
(serviços distribuídos por múltiplos nós ou regiões). Esta mesma
propriedade é, como se discute na Secção 4 e 5.1, o ponto de maior
concentração de risco do sistema: a descoberta depende inteiramente da
integridade do broker.

### 2.2 FCAPS e Fault Management

Modelo FCAPS (ISO/IEC 7498-4), com foco no workflow de Fault Management:
Detecting → Diagnosing and Isolating → Correlating → Resolution/Mitigation
→ Post-Mortem (Lesson03). Nota do syllabus: *"Fault Management within FCAPS
does not deal with security events (i.e., at least explicit security
events)"* — motiva a integração com um SIEM (secção 2.4).

### 2.3 Monitorização de larga escala: Prometheus / Zabbix

O syllabus da cadeira recomenda explicitamente o uso de Prometheus,
seguindo o modelo *pull-based* (o servidor central faz *scrape* periódico
de métricas expostas pelos próprios serviços), amplamente adotado em
ambientes Kubernetes nativos pela sua integração direta com a API do
cluster e pelo modelo de dados multidimensional (labels). Este projeto
adota Zabbix como alternativa, uma plataforma de monitorização mais
tradicionalmente orientada a infraestrutura, que suporta tanto o modelo
pull (checks ativos/passivos via agente) como um modelo *push* através de
proxies — este último particularmente relevante na topologia de rede do
projeto, onde o site do cluster Incus/k3s está atrás de NAT e não é
diretamente alcançável a partir das VMs que hospedam o Zabbix server
(Secção 3.3). A substituição de Prometheus por Zabbix foi autorizada
verbalmente pelo docente em aula, no contexto de liberdade de escolha
tecnológica ("podemos usar as tecnologias que quisermos"); esta autorização
deve ser confirmada por escrito antes da entrega final, dado o enunciado
nomear Prometheus explicitamente.

### 2.4 SIEM e Attack-Defense Trees

Um SIEM (Security Information and Event Management) combina as funções de
*log management*, *Security Information Management* (SIM — armazenamento e
análise histórica de logs) e *Security Event Management* (SEM —
correlação e deteção em tempo quase real), tipicamente completadas por
normalização de eventos de múltiplas fontes, motores de correlação,
capacidades de resposta a incidentes e relatórios de compliance. Neste
projeto, a função de SIEM é cumprida pelo Elastic Stack (Elasticsearch +
Kibana + Filebeat), em substituição de Wazuh — ferramenta recomendada no
syllabus pela sua capacidade nativa de *active response*. A escolha de
Elastic cobre bem as funções de SIM/SEM e normalização, mas exige um
mecanismo de resposta automática próprio (não nativo à licença base),
discutido na Secção 5 como limitação a endereçar.

Attack-Defense Trees (ADTrees), segundo a formulação de Kordy et al.
referenciada no syllabus, modelam um cenário de ameaça como uma hierarquia
onde o nó raiz representa o ativo ou objetivo visado, cada nível seguinte
refina esse objetivo em sub-objetivos ou técnicas mais específicas
(*disjunctive refinement*, OR — qualquer um basta; ou *conjunctive
refinement*, AND — todos são necessários), e nós de defesa
(*countermeasures*) se ligam ao nó de ataque específico que mitigam. As
três ADTrees construídas para este projeto (Secção 4.2) seguem esta
notação, com os serviços-alvo no topo da hierarquia, à semelhança do
exemplo dos autores originais apresentado no syllabus.

---

## 3. Service Architecture Used

### 3.1 Visão geral

Sistema SOA baseado nos Guiões 1 e 2 da disciplina: 5 microsserviços Flask
(Service Registry, Ingestion, Storage, Analytics, Sensor), empacotados como
imagens Docker e orquestrados em cluster k3s (k3s-master + k3s-node1) dentro
de contentores Incus.

```
sensor → [discover via registry] → ingestion → [discover via registry] → storage
                                                                              ↑
                                                                        analytics
                                                                     (discover via registry)
```

[TODO: inserir diagrama de arquitetura]

### 3.2 Identificação e naming hierárquico (slide 7)

Esquema implementado em `common.py`:

```
<país>.<região>.<datacenter>.<rack>.<node>.<serviço>.<instância>
ex: pt.centro.dc-incus.k3s.k3s-node1.storage-service.storage-f6f4dbd-lvwth
```

Propaga-se como campo `location` no Service Registry. Cobre os 4 aspetos
pedidos no slide 7:
- **Localização física/lógica:** país→região→datacenter→rack→node
- **Delegação geográfica:** campos independentes por nível
- **Monitorização por localização / bónus de largura de banda:**
  [TODO: Zabbix proxy por site — descrever a arquitetura de 2 sites
  discutida]
- **Localização rápida da origem de um incidente:** o `instance_id` é a
  chave de correlação partilhada entre o registry, os logs e o SIEM

### 3.3 Topologia de rede e infraestrutura

- VM Debian (`lucas@ssle`) hospeda o Incus
- Bridge `incus-default`, NAT, rede `10.255.255.0/24`
- Cluster k3s: `k3s-master` (10.255.255.42) + `k3s-node1`
- Serviços expostos via NodePort: registry (30050), ingestion (30001),
  analytics (30003); storage em ClusterIP
- Sem NetworkPolicies no namespace `ssle`

[TODO: inserir diagrama de topologia — VM → Incus → k3s → pods]

### 3.4 Integração com monitorização/SIEM

[TODO: Zabbix proxy no site Incus (modo ativo, devido ao NAT) +
Filebeat → Elasticsearch; correlação FCAPS↔segurança via webhook do
Alertmanager/Zabbix para o SIEM]

---

## 4. Risk Management and Mitigation

### 4.1 Attack surfaces

A superfície de ataque do sistema organiza-se em três camadas, cada uma
com um conjunto distinto de pontos de exposição.

**Camada de aplicação:** os cinco serviços expõem, no total, nove
endpoints HTTP, nenhum deles protegido por autenticação ou autorização.
O Service Registry é o ponto de maior concentração de risco: é o único
componente que todos os outros quatro serviços consultam cegamente
(`discover()`, `common.py`), e os seus endpoints de escrita (`/register`,
`/unregister`) aceitam qualquer `name`/`url`/`instance_id` declarado pelo
cliente, sem verificação de identidade. O Storage Service, apesar de
pensado como acessível apenas através do Ingestion, expõe `/store` sem
qualquer validação própria — uma segunda camada de confiança implícita
que, como demonstrado em 5.3, é trivialmente contornável.

**Camada de orquestração:** três dos cinco serviços (`registry`,
`ingestion`, `analytics`) estão expostos como `type=NodePort`, tornando-os
alcançáveis em qualquer nó do cluster a partir de qualquer ponto com
reachability de rede, sem qualquer `NetworkPolicy` a restringir o tráfego
interno entre pods no namespace `ssle`. O `storage`, embora configurado
como `ClusterIP` — pensado para só ser alcançável de dentro do cluster —
tem o seu IP de pod divulgado publicamente via `GET /services` do
registry, anulando na prática essa barreira (I2).

**Camada de rede/infraestrutura:** duas fronteiras de NAT separam o
atacante do sistema consoante o ponto de partida: a bridge Incus
(`incus-default`, NAT) isola a rede `10.255.255.0/24` da rede das VMs do
mini SOC, e o `externalTrafficPolicy: Cluster` por omissão dos NodePorts
introduz SNAT, mascarando o IP de origem real de um atacante externo nos
logs da aplicação. A rede overlay do flannel (`10.42.0.0/16`), por sua
vez, não é routável a partir de um contentor Incus genérico fora do
cluster — uma barreira adicional confirmada empiricamente durante a PoC
da Ameaça 3 (Secção 5.3), que reduz o conjunto de atacantes realistas
àqueles com execução de código dentro da rede overlay do cluster.

### 4.2 Attack and Defense Trees

Metodologia: notação de Kordy et al. (Lesson04, slides 21-25) — nós de
ataque (círculo vermelho), nós de defesa (retângulo verde), disjunctive/
conjunctive refinement, countermeasures. Três ADTrees construídas para as
ameaças da secção 5, disponíveis em `adtrees-ssle-projeto1.md` e como
export do attacktree.online (Anexo C/D).

### 4.3 Large-scale system monitoring

[TODO: como o esquema de naming (3.2) e a correlação Zabbix/Elastic
suportam deteção e root-cause analysis à escala — referir Alertmanager
inhibit rules / trigger dependencies]

### 4.4 Priorização de mitigação

Das três ameaças selecionadas (secção 5), duas (Hijacking, DDoS)
apresentam risco estrutural elevado por serem exploráveis num único passo
(disjunctive refinement). A terceira (Botnet/Fraude) depende de uma cadeia
de dois passos obrigatórios (conjunctive refinement): divulgação do IP do
pod seguida de escrita direta. Uma única mitigação de baixo custo —
impedir a divulgação de URLs internos no registry — neutraliza o ataque
completo, sem necessidade das mitigações mais caras (ex. credencial por
dispositivo). Esta observação informa a ordem de prioridade de
implementação: as mitigações de baixo esforço e alto impacto devem ser
priorizadas primeiro, independentemente da ameaça a que pertencem — por
exemplo, `Do not expose internal pod URLs` (Effort: Low) e `Require
instance_id and restrict deletion` (Effort: Low) eliminam, por si só, o
Attack Path mais barato de duas das três ameaças, antes de se avançar
para mitigações de maior esforço como mTLS ou credenciais por dispositivo.

---

## 5. Approach to Three Threats Considered in the Course Syllabus

Ameaças escolhidas: **Route and signals hijacking**, **Massive
denial-of-service disruptions**, **Botnets** (combinado com fraude de
dados/Reputation Systems). Para cada uma, a estrutura segue exatamente os
6 pontos pedidos no slide 12 ("Discussion of results").

### 5.1 Ameaça 1 — Route/Signals Hijacking

- **Description of the threat:**
  Exploits the absence of authentication on the custom Service Registry
  (Flask REST API, port 5050/NodePort 30050). An attacker registers a
  malicious endpoint as "storage-service" (`registry.py` `/register`),
  causing round-robin discovery to route a portion of traffic to the
  attacker (data interception/tampering). Alternatively, `DELETE
  /unregister` without an `instance_id` wipes all registered instances of
  a service, causing a denial of service that self-recovers only via the
  15s heartbeat.

- **Why is it relevant to the system?**
  The Service Registry is the single point of trust every other component
  depends on blindly: Sensor, Ingestion, Storage and Analytics all resolve
  each other exclusively through it (`discover()` in `common.py`).
  Compromising this one component compromises the entire data flow, making
  it the highest-value target in the architecture.

- **How can it be exploited?**
  - **Attack Path 1 — Unauthenticated registration of malicious
    storage-service instance:** `POST /register` accepts arbitrary
    `name`/`url`/`instance_id`/`location` fields with no authentication.
    An attacker registers an instance named `storage-service` pointing to
    an attacker-controlled endpoint. The registry's round-robin load
    balancer (`get_service()`) then routes a fraction of all
    `storage-service` lookups to the attacker, enabling data interception
    and falsified location/geography metadata.
  - **Attack Path 2 — Unauthenticated service wipe via mass unregister:**
    `DELETE /unregister` accepts `{"name": "<service>"}` without requiring
    `instance_id`. When `instance_id` is omitted, the registry clears ALL
    registered instances of that service in a single unauthenticated
    request (`registry.py`: `registry[name].clear()`). Repeated every few
    seconds, this sustains a persistent denial of service despite the 15s
    self-healing heartbeat.
  - **Attack Path 3 — Registry reachable externally via Kubernetes
    NodePort:** `10-registry.yaml` exposes the registry as `type=NodePort`
    (30050) with no NetworkPolicy restricting ingress. This makes Paths 1
    and 2 exploitable from any host with network reachability to the k3s
    nodes, not only from within the cluster.
  - ADTree: `adtrees-ssle-projeto1.md`, árvore 1 (disjunctive refinement —
    qualquer um dos 3 paths é suficiente)

![ADTree 1 — Service Registry](images/adtree1-hijacking.png)

- **Relevant monitoring/mitigation actions/metrics:**
  - Require mutual TLS and identity-bound registration (Development, High
    effort, Preventive): client certificate CN must match the registered
    `name`, closing Attack Path 1.
  - Require `instance_id` and restrict deletion to caller's own identity
    (Development, Low effort, Preventive): removes the
    `registry[name].clear()` code path, closing Attack Path 2.
  - Restrict registry Service to ClusterIP, remove NodePort exposure
    (Configuration, Low effort, Preventive): closes Attack Path 3.
  - Alert on registration anomalies (Configuration, Medium effort,
    Detective): monitor for registration overwrites or location fields
    inconsistent with known deployment regions.
  - [TODO: métricas concretas do Zabbix/Elastic após ligação — taxa de
    `POST /register`/`DELETE /unregister`, cardinalidade de
    `instance_id` por serviço]

- **Action-response adopted:**
  PoC executada com um contentor Incus dedicado (`attacker`,
  `10.255.255.184`) na mesma rede `incus-default` dos nós k3s, simulando
  um atacante já presente no site (cenário "lab": atacante adjacente,
  distinto do cenário "produção" descrito em 3.3, onde o NodePort
  tornaria o registry acessível também de fora do site). O atacante correu
  um endpoint HTTP próprio (porta 9999) que responde `200 OK` em
  `GET /health` — sobrevivendo deliberadamente ao health-checker do
  registry (`MAX_FAILURES=3`, `HEALTH_INTERVAL=10s`) — e regista em log
  todo o conteúdo recebido em `POST /store`.

  **Fase A — Registo da instância falsa:**
  ```
  POST /register
  {"name":"storage-service","url":"http://10.255.255.184:9999",
   "instance_id":"xx.evil.dc-evil.rack0.nodeX.storage-service.pwned",
   "location":{"country":"xx","region":"evil","datacenter":"dc-evil",
               "rack":"rack0","node":"nodeX"}}
  → 200 OK
  ```
  Nenhuma validação de identidade foi exigida pelo registry, confirmando
  V1. O round-robin de `get_service()` passou de imediato a alternar entre
  a instância real e a falsa (confirmado em 6 pedidos consecutivos, ver
  evidência `poc1-roundrobin-alternancia.txt`).

  **Fase B — DoS via unregister em massa:**
  ```
  DELETE /unregister {"name":"storage-service"}
  → 200 OK {"message":"unregistered"}
  ```
  Um único pedido não autenticado removeu simultaneamente a instância
  real **e** a falsa, confirmando V2. O sistema demonstrou o
  comportamento de autorrecuperação previsto: a instância real
  reapareceu via heartbeat (`registered_at` passou para o instante do
  próximo re-registo, ~15s depois do `unregister`), mas a instância
  falsa não — por não implementar o padrão de heartbeat do
  `register_service()` de `common.py`, ficando permanentemente fora do
  registry até um novo `POST /register` manual.

- **Post-mortem of PoC:**
  - **Impacto observado:** a Fase A resultou em interceção **contínua e
    sustentada** de dados reais do sensor (`pt.centro.dc-incus.sensor-
    dc9b95965-mlt4f`) ao longo de aproximadamente 2 horas ininterruptas
    (18:54:02–20:51:13, UTC — contentores Incus em `Etc/UTC`, VM
    hospedeira em `Europe/Lisbon`/WEST; ver nota metodológica abaixo),
    sem qualquer indicação de erro do lado do `ingestion-service` — o
    atacante recebeu exatamente as mesmas temperaturas reais que seriam
    entregues ao Storage legítimo, em cada ciclo de 5s do sensor.
  - **Nenhum controlo de deteção estava ativo durante a PoC**, pelo que o
    ataque não gerou qualquer alerta — confirma o risco "Alto" atribuído
    na ADTree (árvore 1) e a prioridade de implementação de `Alert on
    registration anomalies` descrito em "Relevant monitoring/mitigation
    actions/metrics" acima.
  - **A Fase B confirmou a assimetria de recuperação:** o `/unregister`
    não distingue entre instâncias legítimas e maliciosas, mas o
    mecanismo de recuperação (heartbeat) só beneficia serviços
    corretamente implementados — um atacante teria de reemitir o
    `/register` periodicamente para manter persistência, o que por si só
    é um padrão observável (repetição de registos com o mesmo
    `instance_id` suspeito) para a regra de deteção proposta.
  - **Limitação identificada:** a ausência de autenticação ou autorização
    nos dois endpoints (`/register`, `/unregister`) torna esta PoC
    trivialmente reprodutível por qualquer entidade com acesso de rede ao
    registry, sem qualquer conhecimento prévio do sistema — reforça a
    classificação de Complexity "Ordinary" atribuída na ADTree.
  - **Nota metodológica:** os contentores Incus operam em `Etc/UTC`
    enquanto a VM hospedeira opera em `Europe/Lisbon` (WEST, UTC+1);
    confirmado via `timedatectl` que o desvio é uniforme entre todos os
    contentores, pelo que a ordem relativa dos eventos documentados
    permanece válida.
  - Evidência: `evidencia/poc1-registry-poisoned.json`,
    `evidencia/poc1-roundrobin-alternancia.txt`,
    `evidencia/poc1-intercepted-data.log`,
    `evidencia/poc1-unregister-dos.json`

### 5.2 Ameaça 2 — Massive Denial-of-Service

- **Description of the threat:**
  Two distinct vectors converge on the same impact. (1) Low-volume: `GET
  /anomalies?limit=-1` is forwarded unvalidated from `analytics.py` to
  `storage.py`, where SQLite interprets `LIMIT -1` as unbounded, forcing a
  full-table dump per request (CWE-770). (2) Volume-based: `POST /ingest`
  has no rate limiting; each request triggers a synchronous `discover()`
  call against the Service Registry, amplifying load onto the
  single-instance registry (SPOF, in-memory state). Werkzeug's development
  server (single-threaded by default) and low Kubernetes CPU limits (250m)
  lower the threshold further.

- **Why is it relevant to the system?**
  "Massive denial-of-service disruptions" is an explicit threat in the
  course syllabus. In this architecture the impact is compounded by
  architectural choices specific to the system: a single point of
  amplification (the registry, queried on every ingest) and a single
  point of persistence (SQLite behind one Storage replica), meaning even
  a low-volume attack can degrade the entire pipeline, not just the
  endpoint it targets directly.

- **How can it be exploited?**
  - **Attack Path 1 — Unbounded query via negative limit parameter:**
    `GET /anomalies?limit=-1` (analytics-service, port 5003) forwards the
    `limit` parameter unvalidated to `GET /temperatures` on
    storage-service. SQLite interprets "LIMIT -1" as no limit, forcing a
    full table scan and serialization of every stored reading in a single
    request.
  - **Attack Path 2 — Unthrottled flood against /ingest amplified by
    registry lookups:** `POST /ingest` (ingestion-service, port
    5001/NodePort 30001) has no authentication, no rate limiting, and no
    request size cap. Each request triggers a synchronous `discover()`
    call to the Service Registry, so request volume is amplified onto the
    single-replica, in-memory registry (SPOF). Low Kubernetes CPU limits
    (250m per pod) and Werkzeug's default single-threaded dev server
    lower the volume needed to cause saturation.
  - ADTree: `adtrees-ssle-projeto1.md`, árvore 2 (disjunctive refinement —
    qualquer um dos 2 paths é suficiente)

![ADTree 2 — DDoS](images/adtree2-ddos.png)

- **Relevant monitoring/mitigation actions/metrics:**
  - Enforce `1 <= limit <= 1000` in `storage.py` and `analytics.py`
    (Development, Low effort, Preventive): closes Attack Path 1.
  - Rate limiting on `/ingest` (Development, Medium effort, Preventive):
    per-IP or per-`device_id`, e.g. Flask-Limiter.
  - Decouple service registry discovery (Development, Medium effort,
    Preventive): client-side discovery cache with TTL, circuit breakers.
  - Replace Werkzeug with production WSGI server (Configuration, Low
    effort, Preventive): gunicorn/uWSGI with multiple workers.
  - Tune Kubernetes resource requests/limits (Configuration, Low effort,
    Preventive).
  - Configure Zabbix/Elastic alerts for DDoS indicators (Configuration,
    Medium effort, Detective): request-rate spikes on `/ingest` e
    `/anomalies`, latência do registry, taxa de 5xx, duração de queries
    SQLite.
  - [TODO: métricas concretas após ligação do Zabbix/Elastic]

- **Action-response adopted:**
  PoC executada a partir do contentor `attacker` (10.255.255.184), com
  dois vetores testados isoladamente e em sequência contra os NodePorts
  do `analytics-service` (30003) e `ingestion-service` (30001).

  **Vetor 1 — Unbounded query:**
  ```
  GET /anomalies?limit=100   → 0.102s (baseline normal)
  GET /anomalies?limit=-1    → 2.783s, 290 277 bytes devolvidos
  ```
  Um único parâmetro alterado resultou em **~27× mais tempo de resposta**
  e num payload que, por omissão, estaria limitado a uma fração do
  tamanho. Confirma CWE-770 de forma quantitativa.

  **Vetor 2 — Flood sobre /ingest, execuções sucessivas:**

  | Execução | Pedidos | Paralelismo | Falhas (502) | Taxa |
  |---|---|---|---|---|
  | 1 (imediatamente após o vetor 1) | 200 | 20 | 11 | 5.5% |
  | 2 (isolada) | 500 | 50 | 0 | 0% |
  | 3 (repetição do teste 1) | 200 | 20 | **153** | **76.5%** |

  A taxa de erro não foi constante nem previsível a partir do volume de
  pedidos isoladamente — foi a **repetição e proximidade temporal** dos
  testes que produziu a degradação mais severa (execução 3), sugerindo
  um efeito cumulativo sobre os limites de CPU (250m) partilhados pelos
  pods do namespace `ssle`, consistente com I5. Após ~30s sem carga, o
  sistema recuperou (`GET /health` voltou a responder 200), confirmando
  que a degradação foi temporária e não um colapso permanente.

- **Post-mortem of PoC:**
  - **Impacto observado:** DoS parcial e reprodutível, não um colapso
    total — a taxa de falha variou entre 0% e 76.5% consoante o estado
    de saturação prévio do sistema, mostrando que o impacto de um
    atacante de baixo esforço é **cumulativo** e não isolado por pedido.
  - **Mecanismo de recuperação:** confirmado via `kubectl get pods`
    (namespace `ssle`), que o pod `storage` acumulou **11 restarts**, com
    o mais recente a ocorrer **52 minutos antes da verificação** — uma
    janela temporal consistente com a execução das PoCs 1 e 2 no mesmo
    dia. Os restantes pods (`analytics`, `ingestion`, `registry`,
    `sensor`) apresentavam entre 8 e 9 restarts cada, todos com idade de
    19 dias mas restarts recentes concentrados nas últimas ~2h de
    execução das PoCs. Isto confirma que **a recuperação não resultou de
    resiliência aplicacional, mas do mecanismo de restart do Kubernetes**
    (`livenessProbe`/`readinessProbe`, `periodSeconds: 10`, Secção 3.3):
    o Kubernetes reinicia um pod que deixa de responder a `/health`,
    substituindo-o por uma nova instância — uma forma indireta e não
    controlada de mitigação, sem qualquer envolvimento do código da
    aplicação. A confirmação final (`GET /health` → `{"status":"ok"}`,
    `200`) foi obtida depois da reinicialização, validando que o sistema
    estava operacional outra vez no momento da verificação.
  - **Nenhum controlo de deteção estava ativo durante a PoC**: a
    degradação e a recuperação ocorreram sem qualquer alerta gerado,
    confirmando a prioridade de `Configure Zabbix/Elastic alerts for DDoS
    indicators` definida em "Relevant monitoring/mitigation actions/metrics".
  - **Limitação identificada:** a ausência de rate limiting significa que
    o comportamento observado (degradação progressiva com repetição) é
    inteiramente dependente do timing das execuções do atacante, não de
    um limiar fixo do sistema — o que torna o impacto real **imprevisível
    para um operador sem monitorização ativa**, agravando a severidade
    relativa a um DoS com comportamento constante e previsível.
  - Evidência: `evidencia/poc2-dump-limit-negativo.json`,
    `evidencia/poc2-dump-limit-normal.json`, `evidencia/poc2-flood-500.txt`,
    `evidencia/poc2-pods-apos-recuperacao.txt`,
    `evidencia/poc2-health-recuperado.txt`

### 5.3 Ameaça 3 — Botnets / Data Fraud

- **Description of the threat:**
  `GET /services` on the registry discloses internal pod IPs (bypassing
  the ClusterIP abstraction). With the Storage pod's real address, an
  attacker writes directly to `POST /store`, which performs no type or
  range validation independently of `ingestion.py` — the validation
  implemented there (temperature range, `device_id` truncation) is
  entirely bypassed. No credential or identity is tied to `device_id`,
  enabling impersonation of an arbitrary number of fabricated sensors
  (botnet simulation) and poisoning of analytics-service outputs
  (`/average`, `/anomalies`).

- **Why is it relevant to the system?**
  Covers both "Botnets" and "Reputation Systems" from the syllabus: the
  lack of per-device identity means `device_id` functions as an
  unauthenticated reputation claim, and the architecture has no mechanism
  to distinguish a real sensor fleet from an arbitrarily large forged one.
  This directly undermines the trustworthiness of Analytics outputs,
  which downstream monitoring and root-cause analysis would otherwise
  rely on.

- **How can it be exploited?**
  - **Attack Path 1 — Internal pod IP disclosure via unauthenticated GET
    /services:** `GET /services` on the registry returns full internal
    state including pod IPs (e.g. `10.42.1.46:5002` for
    `storage-service`), bypassing the Kubernetes ClusterIP abstraction
    (storage Service is `type=ClusterIP`, intended to be the only path to
    the Storage pod).
  - **Attack Path 2 — Direct unauthenticated write to Storage, bypassing
    Ingestion validation:** `POST /store` (storage-service) performs no
    type or range validation independent of `ingestion.py`. An attacker
    with the pod IP from Path 1 writes directly to `/store`, bypassing
    all validation implemented in `ingestion.py` (temperature range
    check, `device_id` truncation). No credential is bound to
    `device_id`, allowing impersonation of an arbitrary number of
    fabricated sensors and poisoning of analytics-service's `/average`
    and `/anomalies` outputs.
  - ADTree: `adtrees-ssle-projeto1.md`, árvore 3 — **conjunctive
    refinement**: ao contrário das ameaças 1 e 2, os dois passos são
    ambos necessários (AND), o que reduz estruturalmente a probabilidade
    face aos vetores de um único passo. Ver 4.4 para a implicação na
    priorização de mitigação.

![ADTree 3 — Botnet/Fraude de Dados](images/adtree3-botnet-fraude.png)

- **Relevant monitoring/mitigation actions/metrics:**
  - Do not expose internal pod URLs in unauthenticated registry reads
    (Development, Low effort, Preventive): closes Attack Path 1 — e, por
    ser o primeiro elo da cadeia AND, é suficiente para neutralizar o
    ataque completo (ver 4.4).
  - NetworkPolicy restricting Storage pod ingress (Configuration, Low
    effort, Preventive): apenas `ingestion-service` e `analytics-service`
    podem alcançar o Storage.
  - Replicate type/range validation inside `storage.py` (Development, Low
    effort, Preventive): defesa em profundidade, independente do Path 1.
  - Per-device credential bound to `device_id` (Development, High effort,
    Preventive): token ou certificado por sensor.
  - Anomaly scoring on `device_id` cardinality (Configuration, Medium
    effort, Detective): deteção de picos de `device_id` distintos por
    janela temporal, sinal de frota de sensores forjada.
  - [TODO: métricas concretas após ligação do Zabbix/Elastic]

- **Action-response adopted:**
  PoC executada em duas fases, com um refinamento de rede descoberto a
  meio da execução (ver nota metodológica abaixo).

  **Fase A — Disclosure (Attack Path 1):**
  ```
  GET /services/storage-service  (via NodePort, do contentor attacker)
  → url: "http://10.42.1.65:5002"
  ```
  Confirmado: o registry devolve o IP real do pod do Storage a qualquer
  cliente não autenticado, incluindo um cliente externo ao cluster.

  **Nota metodológica — refinamento do ponto de execução:** o IP do pod
  pertence à rede overlay do flannel (`10.42.0.0/16`), que não é
  routável a partir de um contentor Incus genérico (`attacker`, na rede
  `10.255.255.0/24`) — confirmado por timeout (`curl` exit code 28) a
  partir da VM Debian e `000` a partir do `attacker`. O `POST /store`
  só foi bem-sucedido quando executado **a partir de dentro de um nó do
  cluster** (`k3s-master`). Isto refina o modelo de ameaça original:
  explorar I2 exige que o atacante tenha execução de código dentro da
  rede overlay do cluster (ex: um pod comprometido, ou acesso a um nó),
  não apenas presença genérica no mesmo site Incus — uma barreira
  adicional não capturada na ADTree inicial, mas que não invalida a
  vulnerabilidade: um único pod comprometido (por qualquer outro vetor)
  dá acesso irrestrito a todos os outros serviços pela mesma via.

  **Fase B — Escrita direta, bypass da validação (Attack Path 2):**
  ```
  POST http://10.42.1.65:5002/store (a partir de k3s-master)
  {"device_id":"botnet-spoof-001","temperature":999.0}
  → 200 {"status":"stored"}
  ```
  Um valor fisicamente impossível (999°C) — muito fora da gama `-50..150`
  validada em `ingestion.py` — foi aceite sem qualquer rejeição.

  **Simulação de escala (botnet):** 15 dispositivos forjados adicionais
  (`bot-1`...`bot-15`), com temperaturas aleatórias entre 100°C e 500°C,
  foram injetados da mesma forma, todos com `200 {"status":"stored"}`.

- **Post-mortem of PoC:**
  - **Impacto observado, quantificado:**

    | Métrica | Antes da injeção | Depois (16 dispositivos forjados) |
    |---|---|---|
    | `average_temperature` | 24.6 °C | **64.93 °C** (+164%) |
    | `max` | 29.41 °C | **456.0 °C** |
    | `count` | 100 | 100 |

    O `/average` do `analytics-service` — um endpoint consumido para
    decisões a jusante — ficou completamente não confiável com apenas
    16 escritas forjadas, sem qualquer credencial ou autenticação.
  - **Limitação do próprio mecanismo de deteção interno:** o endpoint
    `/anomalies` (`ANOMALY_THRESHOLD = 28.0`) devolveu `[]` mesmo com
    valores muito acima do limiar. Causa identificada: `/anomalies`
    opera sobre uma janela deslizante dos 100 registos mais recentes
    (`GET /temperatures?limit=100` ao Storage); com o sensor legítimo a
    gerar uma leitura a cada 5s, os valores forjados podem sair dessa
    janela antes de serem consultados. **Achado relevante:** mesmo um
    mecanismo de deteção de anomalias nativo da aplicação não é robusto
    a um atacante que opere em rajadas curtas e espace a reconsulta —
    reforça a necessidade de deteção centrada em logs/SIEM (janela
    alargada, correlação temporal) em vez de depender só de filtros
    aplicacionais de janela curta. **Confirmado duas vezes:** `[]`
    imediatamente após a injeção, e novamente ~2h20m depois
    (`?limit=100`, janela alargada) — nesse momento a janela continha
    apenas as ~1400 leituras legítimas geradas pelo sensor real no
    intervalo (uma leitura a cada 5s), todas entre 28.1 °C e 30.0 °C,
    confirmando que os registos forjados tinham sido completamente
    expulsos da janela de consulta sem deixar qualquer rasto acessível
    pela própria API da aplicação.
  - **Nenhum controlo de deteção estava ativo durante a PoC.**
  - Evidência: `evidencia/poc3-average-poisoned.json`,
    `evidencia/poc3-anomalies-poisoned.json`,
    `evidencia/poc3-average-after-botnet.json`,
    `evidencia/poc3-anomalies-wide-window.json`

---

## 6. Evaluation of the Solution's Approaches and Scalability

[TODO: testes de carga, cardinalidade de séries no Zabbix/Elastic, EPS do
SIEM, latência de scrape/ingestão vs. número de nós/réplicas; comparação
do comportamento do sistema com e sem as mitigações implementadas]

---

## 7. Conclusions

As três provas de conceito executadas confirmaram, com evidência
quantificada e reprodutível, que as três ameaças do syllabus escolhidas
são exploráveis na arquitetura construída, cada uma a partir de uma falha
de design concreta e não de uma exploração sofisticada: ausência de
autenticação no Service Registry (hijacking), ausência de limites e de
controlo de taxa (DDoS), e ausência de validação independente no Storage
combinada com divulgação de endereços internos (fraude de dados). O
achado transversal mais relevante é que **o Service Registry concentra a
maior parte do risco do sistema** — está presente em todas as três
ADTrees como alvo direto ou como passo intermédio — o que o torna o
candidato natural para a primeira prioridade de mitigação em qualquer
iteração futura da arquitetura.

Um segundo achado relevante, descoberto durante a execução das PoCs e não
antecipado na modelação de ameaças inicial, é que **nem todas as
superfícies de ataque teoricamente expostas são igualmente acessíveis na
prática**: a rede overlay do flannel não é routável a partir de um
contentor genérico fora do cluster, o que introduz uma barreira adicional
de facto para a Ameaça 3. Isto não invalida a vulnerabilidade — qualquer
ponto de execução dentro do cluster (incluindo um único pod comprometido
por outro vetor) continua a ter acesso irrestrito — mas é um lembrete de
que a topologia de rede real deve ser sempre validada empiricamente, e não
apenas inferida a partir dos manifestos.

### Porque esta solução não é perfeita

A arquitetura apresenta limitações estruturais, documentadas e assumidas
conscientemente, que condicionam tanto a severidade de alguns dos
cenários testados como a fiabilidade da própria monitorização:

- **Pontos únicos de falha (SPOF):** o Service Registry corre com uma
  única réplica e estado inteiramente em memória (perdido num restart); o
  Storage corre também com uma única réplica, ligada a um volume
  `local-path` preso a um nó específico do cluster. Ambos foram
  observados a reiniciar múltiplas vezes durante a execução das PoCs
  (Secção 5.2).
- **Perfil de contentor privilegiado:** os nós Incus do cluster k3s correm
  com `security.privileged=true` e `security.nesting=true`, um requisito
  do laboratório (não uma escolha de design) que, em caso de fuga de um
  contentor, concederia root sobre a VM anfitriã.
- **Atribuição de origem degradada:** o SNAT por omissão nos NodePorts, e
  a camada adicional de NAT da bridge Incus, significam que o IP de
  origem de um atacante externo real não chegaria limpo aos logs da
  aplicação — a identificação da origem depende inteiramente do que o
  próprio atacante decide declarar (ex: `location` no `/register`), o
  que é ele próprio forjável, como demonstrado na Ameaça 1.
- **Servidor de desenvolvimento em produção:** todos os cinco serviços
  correm sobre o servidor de desenvolvimento do Werkzeug, explicitamente
  desaconselhado para produção pela sua própria documentação, o que baixa
  o limiar de esforço necessário para o DDoS demonstrado em 5.2.
- **Mecanismo de deteção de anomalias de janela curta:** como demonstrado
  em 5.3, o endpoint `/anomalies` da aplicação opera sobre uma janela
  deslizante de apenas 100 registos, insuficiente para capturar um
  ataque em rajada seguido de tráfego legítimo normal — reforçando que a
  deteção de segurança não deve depender de mecanismos aplicacionais
  pontuais, mas de um SIEM com janela de correlação alargada.

### Trabalho futuro

As limitações acima — em particular os SPOFs do Registry e do Storage —
são o ponto de partida natural para o Projeto 2, que reutilizará esta
mesma arquitetura sob o tema de tolerância a ataques: réplicas com estado
partilhado, mecanismos de consenso ou quorum para o registry, e
redundância do volume de dados são passos diretos a partir do que aqui
foi identificado como limitação, não como trabalho em separado.

---

## Anexos

- A. Evidência "antes" (`evidencia/antes/`)
- B. Evidência das PoCs (`evidencia/poc{1,2,3}-*`)
- C. ADTrees completas (`adtrees-ssle-projeto1.md`)
- D. Export do attacktree.online
