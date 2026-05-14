# Tarefa 4 — Sistema Multi-agente LLM (Explicação Simples)
**CloudWalk AML/FT Technical Challenge** | Analista: lsl197 | 2025-10-05

---

## O que é e por que existe

As Tarefas 1, 2 e 3 geram listas de suspeitos e scores. Mas transformar isso num **relatório formal para o COAF** (SAR — Suspicious Activity Report) é trabalho que normalmente leva horas de analista: cruzar dados, construir narrativa, citar legislação, aprovar o documento.

A Tarefa 4 automatiza esse processo com 5 "agentes" (instâncias de um LLM) que trabalham em sequência, cada um fazendo uma parte do trabalho.

**Input:** um `customer_id`  
**Output:** SAR completo + decisão de compliance + arquivo JSON auditável

---

## Os 5 agentes — o que cada um faz

Pense como uma linha de produção. Cada agente recebe o trabalho anterior já feito, adiciona o que é de sua responsabilidade, e passa adiante.

---

### Agente 1 — DADOS
**Tarefa:** buscar tudo que existe sobre o cliente no banco e organizar.

Consulta 4 fontes:
- KYC (quem é o cliente, renda, PEP, rating de risco)
- Transações (valores, países, VPN, sanctions hit)
- Merchants (para quem ele pagou)
- Score ML da Tarefa 3 (final_score, tier, geo-jumps, income ratio)

**Output:** um JSON estruturado com o perfil completo do cliente.

---

### Agente 2 — DETECÇÃO
**Tarefa:** olhar o perfil e decidir se o caso merece investigação.

Verifica as 8 tipologias de lavagem de dinheiro (structuring, geo-jump, income incompatível, fan-out PIX, sanções, VPN, self-merchant, MCC alto risco) e dá uma decisão:

- `INVESTIGAR` → segue para os próximos agentes
- `MONITORAR` → não urgente, mas fica no radar
- `ARQUIVAR` → nada de suspeito, encerra aqui

Também dá um `score_deteccao` de 0–100 e lista as flags que acionou.

---

### Agente 3 — INVESTIGAÇÃO
**Tarefa:** aprofundar. Busca mais dados no banco, monta linha do tempo, identifica rede suspeita.

Executa duas queries adicionais:
1. Todas as transações do cliente com detalhes dos receptores
2. Self-join de geo-jumps: cruza transações para encontrar pares onde o cliente "apareceu" em dois países em menos de 12h

**Output:** narrativa investigativa completa + linha do tempo + evidências fortes/fracas + mapeamento da rede.

---

### Agente 4 — SAR
**Tarefa:** redigir o relatório formal.

Usa tudo que os agentes 1, 2 e 3 produziram para escrever um SAR nas 8 seções obrigatórias da **Resolução COAF 36/2021**:

1. Identificação (quem é o suspeito, qual empresa está reportando)
2. Resumo executivo
3. Descrição das operações (volume, período, operações críticas)
4. Tipologia (qual esquema de lavagem, qual fase — placement/layering/integration)
5. Fundamentação legal (quais leis se aplicam)
6. Evidências
7. Medidas tomadas
8. Conclusão com prazo para comunicar ao COAF

**Regra do prazo:**
- 24h → sanção confirmada (OFAC/UNSC) — obrigação legal
- 72h → geo-jump ou income ratio grave
- 30 dias → suspeita sem evidência direta de crime

---

### Agente 5 — COMPLIANCE
**Tarefa:** revisar o SAR do Agente 4 antes de submeter.

Funciona como um segundo par de olhos independente. Verifica:
- As evidências são suficientes para justificar o SAR?
- Os artigos de lei citados estão corretos?
- O SAR está completo nas 8 seções?
- Vale submeter ou é melhor coletar mais dados?

**Decisão final:**
- `APROVADO` → manda para o COAF
- `APROVADO_COM_RESSALVAS` → pode mandar, mas corrigir esses pontos antes
- `REPROVADO` → reinvestigar, evidências insuficientes
- `AGUARDAR` → caso promissor, mas faltam dados

---

## Como o contexto passa entre agentes

Cada agente recebe o JSON acumulado dos anteriores. Nenhum repete trabalho:

```
Agente 1 → perfil_json
Agente 2 → perfil_json + detecção
Agente 3 → perfil_json + detecção + investigação (+ queries próprias no banco)
Agente 4 → tudo acima
Agente 5 → SAR + investigação (só o que precisa para revisar)
```

---

## Resultados dos casos testados

| Cliente | Situação | Decisão final | Score compliance | Prazo COAF |
|---|---|---|---|---|
| C101048 | Mechanic, PEP, 5 geo-jumps, income 22× | APROV. COM RESSALVAS | 85/100 | 24h |
| C100932 | Nurse, 31 alertas HIGH, income 28× | APROV. COM RESSALVAS | 85/100 | 24h |
| C101208 | Chef, sanctions hit, geo-jump RU→BR 4min | APROV. COM RESSALVAS | 80/100 | 24h |
| C100091 | Analyst, rede M200363, sanctions Wire | APROV. COM RESSALVAS | 85/100 | 24h |
| C102221 | Consultant, geo-jump SY→BR 36 segundos | APROV. COM RESSALVAS | 85/100 | 24h |

Tempo por caso: ~50–90 segundos. Output salvo em `aml_case_{customer_id}.json`.

---

## Problema técnico: limite de tokens da API

O Groq (tier gratuito) aceita no máximo **12.000 tokens por minuto**. Um pipeline de 5 agentes pode consumir 10.000–15.000 tokens por caso.

**Solução:** quando a API retorna erro de rate limit, extraímos o tempo exato de espera da mensagem de erro e esperamos só esse tempo (geralmente menos de 2 segundos). Isso evita esperas fixas desnecessárias de 60 segundos.

---

## Limitações

| Limitação | Impacto | Solução em produção |
|---|---|---|
| Dados de clientes reais não podem ir para API pública | LGPD + sigilo bancário | Modelo hospedado internamente |
| Cada caso é independente — agentes não aprendem dos anteriores | SARs não melhoram com o tempo | RAG com histórico de casos aprovados |
| ~8–10 casos por dia (limite gratuito Groq) | Não escala para volume real | Tier pago ou modelo próprio |
| LLM pode gerar outputs levemente diferentes em runs distintos | Não é 100% determinístico | Temperatura 0.0 + revisão humana obrigatória |

---

*Tarefa 4 — CloudWalk AML/FT Technical Challenge*
