# SSLE — Projeto 1

Segurança em Sistemas de Larga Escala · Design and Run a Service-Based
Architecture that Scales

## Estrutura

```
relatorio-ssle-projeto1.md     relatório completo (entrega)
adtrees-ssle-projeto1.md       as 3 Attack-Defense Trees (fonte mermaid)
howto-pocs-projeto1.md         guia reexecutável das 3 PoCs + deteção/resposta
images/                        diagramas e ADTrees renderizadas (PNG)

ssle-guide2/                   aplicação (5 microsserviços Flask + k3s/Incus)
deteccao-resposta/             Fase 4 — deteção e resposta (Wazuh + Zabbix)
  wazuh/local_rules.xml          regras 100100-100300
  wazuh/active-response/         scripts de resposta automática
  zabbix/items-triggers.md       items/triggers (config vive no servidor)
  responder/responder.py         microsserviço de rate-limit (Ameaça 2)
poc/                           ferramentas do lado atacante
  fake-storage/fake_storage.py   endpoint falso (Ameaça 1)
systemd/                       units dos serviços custom (ver howto-pocs)

evidencias/                    evidência recolhida (antes/, poc1/, poc2/,
                                poc3/, evidencias-detecao/)
```

## Correr a demo

Segue `howto-pocs-projeto1.md` — tem o checklist de pré-requisitos e os
3 PoCs completos, cada um com a fase de exploração e a fase de
deteção+resposta automática (Wazuh + Zabbix).

## Infraestrutura

5 microsserviços Flask (registry, ingestion ×2, storage, analytics,
sensor) em k3s (`k3s-master`+`k3s-node1`) dentro de contentores Incus,
monitorizados por Wazuh (SIEM) e Zabbix (operacional), com
active-response automático para as 3 ameaças do syllabus exploradas
(Route/Signals Hijacking, Massive DDoS, Botnets/Data Fraud). Detalhe
completo no relatório.
