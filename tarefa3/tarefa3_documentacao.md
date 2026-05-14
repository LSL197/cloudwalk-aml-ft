# Tarefa 3 — ML Risk Scoring (Explicação Simples)
**CloudWalk AML/FT Technical Challenge** | Analista: lsl197 | 2025-10-05

---

## O problema central

Queremos um modelo de ML que detecte clientes suspeitos de lavagem de dinheiro.

**Problema:** não existe uma coluna `é_lavador = sim/não` no dataset. Sem isso, não dá para treinar um modelo supervisionado direto — ele não sabe o que é "certo" ou "errado".

**Solução adotada:** usamos as **regras da Tarefa 2** como substituto. Se um cliente disparou regras suficientes, tratamos ele como "provavelmente suspeito" para fins de treinamento.

---

## Como funciona em 5 etapas simples

### Etapa 1 — Calcular números por cliente

Transformamos 52.000 transações individuais em **31 números por cliente**. Exemplos:

- Quantos geo-jumps esse cliente teve?
- Qual foi a maior transação dele em múltiplos da renda mensal?
- Quantas vezes usou VPN?
- Em quanto tempo viajou entre dois países?

**Por que números e não sim/não?** Porque "fez 1 geo-jump" é muito diferente de "fez 7 geo-jumps". Números capturam a **intensidade** do comportamento, não só se aconteceu.

---

### Etapa 2 — Isolation Forest (encontrar os esquisitos sem saber o que é suspeito)

**O que é:** algoritmo que encontra anomalias sem precisar de labels.

**Intuição:** imagine que você embaralha aleatoriamente 2.500 pessoas numa sala e tenta isolar cada uma colocando paredes. Pessoas "esquisitas" (fora do padrão) ficam isoladas muito mais rápido — precisam de menos paredes. Isso é o Isolation Forest.

**Resultado:** cada cliente recebe um score de 0 a 1. Score 1 = muito diferente do padrão (anômalo). Score 0 = comportamento normal.

**Limitação:** ele não sabe *por que* o cliente é esquisito — só que é diferente.

---

### Etapa 3 — XGBoost (aprender com as regras da Tarefa 2)

**O problema:** o Isolation Forest acha anomalias, mas não necessariamente lavagem de dinheiro. Um cliente que compra muitas vezes no mesmo dia pode ser esquisito, mas não suspeito.

**Solução:** usamos os scores das regras (Tarefa 2) para criar pseudo-labels:
- Cliente disparou muitas regras pesadas? → marcamos como `suspeito (1)`
- Cliente disparou poucas regras? → marcamos como `normal (0)`

Aí treinamos o XGBoost com esses labels. Ele aprende quais combinações de números (os 31 da etapa 1) aparecem em clientes que as regras identificam como suspeitos.

**Por que não usar só as regras então?** O XGBoost aprende padrões não-óbvios. Exemplo: "renda baixa + muitos PIX recebidos + geo-jump rápido" pode ser suspeito mesmo sem disparar nenhuma regra individual com score alto o suficiente.

**Resultado:** probabilidade de 0 a 1 por cliente. Quanto mais próximo de 1, mais parecido com os clientes que as regras identificaram como suspeitos.

---

### Etapa 4 — SHAP (explicar por que o modelo deu aquele score)

**Por que é necessário:** reguladores (BACEN, COAF) não aceitam "o modelo disse que é suspeito". Precisam saber *por que*.

**O que é SHAP:** para cada cliente, decompõe o score em contribuições de cada variável. Exemplo:

> Cliente C101048 — score 0,999
> - n_geojumps contribuiu +0,42
> - max_income_ratio contribuiu +0,31
> - n_vpn_txs contribuiu +0,18
> - annual_income contribuiu -0,05 (fator que puxou pra baixo)

O analista vê exatamente o que pesou mais para aquele cliente específico.

**Top features globais (mais importantes no geral):**

| Feature | Peso global | O que significa |
|---|---|---|
| n_geojumps | 2,48 | Qtd de "viagens impossíveis" → maior discriminador |
| max_income_ratio | 1,31 | Maior tx em múltiplos da renda mensal |
| min_geojump_min | 0,71 | Tempo mínimo entre países (menor = pior) |
| n_vpn_txs | 0,59 | Quantas txs via VPN/Tor |
| n_pix_in | 0,50 | Volume de PIX recebidos |

---

### Etapa 5 — Score final e classificação

Combinamos os dois modelos num score final:

```
final_score = 70% × (score do XGBoost) + 30% × (score do Isolation Forest)
```

Por que 70/30? O XGBoost é mais preciso (aprendeu das regras). O Isolation Forest cobre casos esquisitos que *nenhuma regra* capturou. Os 30% garantem que esses casos não somem.

**Classificação final:**

| Tier | Score | O que fazer |
|---|---|---|
| CRITICAL | 0,70 – 1,00 | Investigar agora |
| HIGH | 0,50 – 0,70 | Investigar em 72h |
| MEDIUM | 0,30 – 0,50 | Monitorar |
| LOW | 0,00 – 0,30 | Rotina normal |

**Resultado:** 1.075 CRITICAL · 83 HIGH · 52 MEDIUM · 1.290 LOW (dos 2.500 clientes)

---

## Limitações honestas

1. **Circularidade:** o XGBoost aprende a imitar as regras. Se um cliente lavar dinheiro de um jeito que nenhuma regra pega, o ML também pode errar. O Isolation Forest (30%) é a salvaguarda.

2. **Sem dados reais:** o dataset é sintético. Em produção precisaria retraining com casos reais confirmados.

3. **AUC de 0,986 não é milagre:** é alto porque o modelo aprende a replicar as próprias regras. Não significa que acerta 98,6% de lavadores reais.

---

## Arquivos gerados

| Arquivo | Conteúdo |
|---|---|
| `ml_risk_scores.csv` | Score e tier por cliente (2.500 linhas) |
| `shap_summary.png` | Gráfico mostrando quais variáveis mais pesaram |
| `roc_pr_curves.png` | Curvas de performance do modelo |

---

*Tarefa 3 — CloudWalk AML/FT Technical Challenge*
