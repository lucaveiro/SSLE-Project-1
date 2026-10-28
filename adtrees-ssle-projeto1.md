# Attack-Defense Trees — SSLE Projeto 1

Notação seguida de Lesson04-Monitoring (slide 25, Kordy et al.):
- ◯ círculo vermelho = attack/target node (o(s) serviço(s) atacado(s) é
  o topo da hierarquia, tal como "Bank Account" no exemplo dos autores
  originais)
- ▭ retângulo verde = defense node (countermeasure)
- linha sólida = disjunctive refinement (OR)
- linha sólida rotulada "AND" = conjunctive refinement
- linha pontilhada = countermeasure, ligada ao nó específico que mitiga

---

## ADTree 1 — Service Registry (alvo único no topo)

```mermaid
graph TD
    A0((Service Registry<br/>registry.py : 5050))

    A1((Abuse /register<br/>endpoint))
    A2((Abuse /unregister<br/>endpoint))
    A3((Reach registry<br/>via NodePort))

    A0 --- A1
    A0 --- A2
    A0 --- A3

    A1b((Register fake<br/>storage-service))
    A2b((Mass unregister<br/>wipe))

    A1 --- A1b
    A2 --- A2b

    D1[Require mTLS +<br/>identity-bound<br/>registration]
    D2[Require instance_id<br/>+ scoped auth]
    D3[Restrict to ClusterIP<br/>+ NetworkPolicy]
    D4[Alert on registration<br/>anomalies]

    A1b -.-> D1
    A2b -.-> D2
    A3 -.-> D3
    A0 -.-> D4

    style A0 fill:#fff,stroke:#d32f2f,stroke-width:3px,color:#d32f2f
    style A1 fill:#fff,stroke:#d32f2f,stroke-width:3px,color:#d32f2f
    style A2 fill:#fff,stroke:#d32f2f,stroke-width:3px,color:#d32f2f
    style A3 fill:#fff,stroke:#d32f2f,stroke-width:3px,color:#d32f2f
    style A1b fill:#fff,stroke:#d32f2f,stroke-width:3px,color:#d32f2f
    style A2b fill:#fff,stroke:#d32f2f,stroke-width:3px,color:#d32f2f
    style D1 fill:#fff,stroke:#388e3c,stroke-width:3px,color:#388e3c
    style D2 fill:#fff,stroke:#388e3c,stroke-width:3px,color:#388e3c
    style D3 fill:#fff,stroke:#388e3c,stroke-width:3px,color:#388e3c
    style D4 fill:#fff,stroke:#388e3c,stroke-width:3px,color:#388e3c
```

---

## ADTree 2 — DDoS (2 serviços-alvo no topo, OR)

```mermaid
graph TD
    B1((Analytics + Storage<br/>analytics.py:5003<br/>storage.py:5002))
    B2((Ingestion + Registry<br/>ingestion.py:5001<br/>registry.py:5050))

    B1 ---|OR| B2

    B1b((Unbounded query<br/>limit=-1))
    B2b((Flood /ingest<br/>amplified by registry))

    B1 --- B1b
    B2 --- B2b

    E1[Enforce 1 ≤ limit<br/>≤ 1000]
    E2[Rate limiting<br/>on /ingest]
    E3[Decouple discovery<br/>cache + TTL]
    E4[Production WSGI<br/>server]
    E5[Tune resource<br/>requests/limits]
    E6[Zabbix/Elastic<br/>DDoS alerts]

    B1b -.-> E1
    B2b -.-> E2
    B2b -.-> E3
    B2b -.-> E4
    B1 -.-> E5
    B2 -.-> E6

    style B1 fill:#fff,stroke:#d32f2f,stroke-width:3px,color:#d32f2f
    style B2 fill:#fff,stroke:#d32f2f,stroke-width:3px,color:#d32f2f
    style B1b fill:#fff,stroke:#d32f2f,stroke-width:3px,color:#d32f2f
    style B2b fill:#fff,stroke:#d32f2f,stroke-width:3px,color:#d32f2f
    style E1 fill:#fff,stroke:#388e3c,stroke-width:3px,color:#388e3c
    style E2 fill:#fff,stroke:#388e3c,stroke-width:3px,color:#388e3c
    style E3 fill:#fff,stroke:#388e3c,stroke-width:3px,color:#388e3c
    style E4 fill:#fff,stroke:#388e3c,stroke-width:3px,color:#388e3c
    style E5 fill:#fff,stroke:#388e3c,stroke-width:3px,color:#388e3c
    style E6 fill:#fff,stroke:#388e3c,stroke-width:3px,color:#388e3c
```

---

## ADTree 3 — Botnet/Fraude (2 serviços-alvo no topo, AND)

```mermaid
graph TD
    C1((Service Registry<br/>registry.py : 5050))
    C2((Storage Service<br/>storage.py : 5002))

    C1 ---|AND| C2

    C1b((Disclose pod IP<br/>via GET /services))
    C2b((Write directly to<br/>/store, bypass<br/>ingestion))

    C1 --- C1b
    C2 --- C2b

    F1[Do not expose<br/>internal pod URLs]
    F2[NetworkPolicy:<br/>restrict Storage<br/>ingress]
    F3[Validate in<br/>storage.py too]
    F4[Per-device<br/>credential]
    F5[Anomaly scoring<br/>on device_id<br/>cardinality]

    C1b -.-> F1
    C2b -.-> F2
    C2b -.-> F3
    C2b -.-> F4
    C1 -.-> F5

    style C1 fill:#fff,stroke:#d32f2f,stroke-width:3px,color:#d32f2f
    style C2 fill:#fff,stroke:#d32f2f,stroke-width:3px,color:#d32f2f
    style C1b fill:#fff,stroke:#d32f2f,stroke-width:3px,color:#d32f2f
    style C2b fill:#fff,stroke:#d32f2f,stroke-width:3px,color:#d32f2f
    style F1 fill:#fff,stroke:#388e3c,stroke-width:3px,color:#388e3c
    style F2 fill:#fff,stroke:#388e3c,stroke-width:3px,color:#388e3c
    style F3 fill:#fff,stroke:#388e3c,stroke-width:3px,color:#388e3c
    style F4 fill:#fff,stroke:#388e3c,stroke-width:3px,color:#388e3c
    style F5 fill:#fff,stroke:#388e3c,stroke-width:3px,color:#388e3c
```
