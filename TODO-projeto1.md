# TODO List — SSLE Projeto 1

Estado a 28/10/2026. Entrega: 22/11/2026.
Legenda: ✅ feito · 🟡 parcial · ⬜ por fazer · 🔴 crítico/bloqueante

---

## FASE 1 — Construir (arquitetura)
- ✅ App SOA (5 serviços Flask) a correr em k3s + Incus
- ✅ Naming hierárquico implementado (`common.py`)
- ✅ Registry com discovery/health-check/round-robin funcional
- ✅ 2 réplicas de ingestion (tolerância básica)

## FASE 2 — Analisar (modelação de risco)
- ✅ 3 ameaças escolhidas e confirmadas com o docente
- ✅ Attack surfaces mapeados (I1–I8, V1–V7)
- ✅ 3 ADTrees (attacktree.online + imagens Graphviz no estilo do slide 25)
- ✅ Lógica AND/OR correta (AND na ameaça 3)

## FASE 3 — Provar (PoCs de exploração)
- ✅ Evidência "antes" capturada (`evidencia/antes/`)
- ✅ PoC 1 (Hijacking): interceção sustentada + DoS via unregister
- ✅ PoC 2 (DDoS): limit=-1 (27x) + flood (até 76.5% falhas) + recuperação
- ✅ PoC 3 (Botnet/Fraude): disclosure + escrita direta + média 24.6→64.93°C
- ✅ Achado de rede (flannel não routável) documentado
- ✅ Comandos consolidos num script (ver how-to)

## FASE 4 — Defender (deteção + resposta) 🔴 MAIOR BLOCO EM FALTA
- ⬜ 🔴 Ligar deteção mínima (Zabbix e/ou Elastic) — pelo menos 1 sinal por ameaça
- ⬜ 🔴 Implementar pelo menos 1 action-response real (slide 10 exige, não é opcional)
- ⬜ Capturar print/log de um alerta a disparar durante cada PoC
- ⬜ Demonstrar ponte FCAPS↔segurança (correlação sinal operacional + segurança)

---

## RELATÓRIO — secções de texto
- ✅ 1. Introduction
- ✅ 2.1 SOA · 2.2 FCAPS · 2.3 Prometheus/Zabbix · 2.4 SIEM/ADTrees
- ✅ 3.2 Naming · 3.3 Topologia
- ✅ 4.1 Attack surfaces · 4.2 ADTrees · 4.4 Priorização
- ✅ 5.1 / 5.2 / 5.3 — exploração, action-response, post-mortem das 3 PoCs
- ✅ 7. Conclusions (+ "porque não é perfeita" + trabalho futuro)
- 🟡 3.1 Visão geral (texto ok, falta diagrama de arquitetura)
- ⬜ 3.2 bónus — arquitetura Zabbix proxy 2 sites (depende da Fase 4)
- ⬜ 3.4 Integração SIEM (depende da Fase 4)
- ⬜ 4.3 Large-scale monitoring (depende da Fase 4)
- ⬜ 5.x — métricas concretas de deteção (depende da Fase 4)
- ⬜ 6. Evaluation of Scalability (depende de testes de carga)

## RELATÓRIO — figuras
- ✅ 3 ADTrees (PNG)
- ⬜ Diagrama de arquitetura (5 serviços + fluxo)
- ⬜ Diagrama de topologia de rede (VM → Incus → k3s → pods, 2 NAT)
- ⬜ Gráfico de degradação DDoS (opcional, reforça a secção 6)

---

## ADMINISTRATIVO / DEFESA
- ⬜ 🔴 Confirmar POR ESCRITO a autorização Prometheus→Zabbix (email ao docente)
- ⬜ Frase a justificar a combinação Botnet+Reputation+Fraude numa só ameaça
- ⬜ Organizar repositórios/código para a Demo (50% da nota, separado do relatório)
- ⬜ Consolidar evidência em `evidencia/poc{1,2,3}-*` (verificar que todos os ficheiros existem)
- ⬜ Preparar respostas para a defesa:
    - "Porque a PoC 2 às vezes falha e às vezes não?" (recursos partilhados, sem rate limiting)
    - "O atacante precisa de estar onde, exatamente?" (dentro da rede overlay do cluster)
    - "Como é que o sistema recuperou sozinho?" (restart do Kubernetes via livenessProbe)

---

## ORDEM SUGERIDA (para maximizar nota com o tempo que resta)
1. 🔴 Confirmar autorização Prometheus→Zabbix (1 email, desbloqueia risco de avaliação)
2. 🔴 Fase 4 mínima — 1 deteção + 1 resposta por ameaça (requisito explícito)
3. Diagramas de arquitetura e topologia (rápido, fecha vários TODOs de texto)
4. Secção 6 (testes de carga) — reutiliza os comandos de flood da PoC 2
5. Script consolidado das PoCs (para a demo ser reexecutável)
6. Revisão final + organização dos repositórios
