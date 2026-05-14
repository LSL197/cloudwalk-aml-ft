# CloudWalk AML/FT Technical Challenge

**Analista:** lsl197 | **Data:** 2025-10-05

Análise completa de AML/FT sobre dataset sintético CloudWalk — 52.000 transações, 2.500 clientes, 1.000 merchants (PIX, Card, Wire | Jul–Out 2025).

---

## Estrutura do Repositório

```
├── tarefa1/          → Identificação de suspeitos + SAR completo
├── tarefa2/          → Sistema de 20 regras AML/FT + outputs
├── tarefa3/          → Modelo ML híbrido (Isolation Forest + XGBoost) + outputs
├── tarefa4/          → Pipeline multi-agente LLM (5 agentes) + outputs JSON
├── notebook/         → Análise exploratória interativa
└── relatorio/        → Relatório técnico PDF
```

---

## Tarefa 1 — Identificação de Suspeitos + SAR

**Arquivo:** [`tarefa1/tarefa1_suspeitos_SAR.md`](tarefa1/tarefa1_suspeitos_SAR.md)

Score de risco ponderado com 12 dimensões via SQL CTEs. Resultado: **29 suspeitos prioritários** divididos em tiers Crítico / Alto / Elevado, com scores de 9 a 11.

SAR completo do merchant iraniano **M200363**: R$ 171k agregado de 43 clientes, 1 sanctions hit confirmado (OFAC), obrigação de comunicação ao COAF em 24h.

| Tier | Score | Clientes |
|---|---|---|
| Crítico | 11 | 3 |
| Alto | 10 | 7 |
| Elevado | 9 | 19 |

---

## Tarefa 2 — Sistema de Alertas (20 Regras)

**Script:** [`tarefa2/tarefa2_alert_system.py`](tarefa2/tarefa2_alert_system.py)  
**Documentação:** [`tarefa2/tarefa2_documentacao.md`](tarefa2/tarefa2_documentacao.md)  
**Output:** [`tarefa2/outputs/alerts_output.csv`](tarefa2/outputs/alerts_output.csv)

20 regras independentes cobrindo 8 tipologias. Cada regra é uma função Python que consulta SQLite e retorna alertas padronizados.

| Métrica | Valor |
|---|---|
| Total de alertas | 41.476 |
| Clientes únicos | 2.587 |
| Transações únicas | 34.622 |
| Alertas HIGH | 4.698 |
| Alertas MEDIUM | 36.778 |

**Tipologias cobertas:** Structuring · Income Ratio · Sanções · Geo-jump · Fan-out PIX · Self-Merchant · Fraude E-commerce · Dispositivo/Acesso suspeito

**Para executar:**
```bash
pip install pandas
python tarefa2/tarefa2_alert_system.py
# → gera alerts_output.csv
```

> Requer `aml.db` na raiz (não versionado — arquivo pesado de 15MB).

---

## Tarefa 3 — Modelo de Machine Learning Híbrido

**Script:** [`tarefa3/tarefa3_ml_model.py`](tarefa3/tarefa3_ml_model.py)  
**Documentação:** [`tarefa3/tarefa3_documentacao.md`](tarefa3/tarefa3_documentacao.md)  
**Outputs:** [`tarefa3/outputs/`](tarefa3/outputs/)

Abordagem híbrida em 5 etapas para contornar ausência de ground truth:

```
Feature Engineering (31 features) → Isolation Forest → Pseudo-labels → XGBoost → SHAP
final_score = 0.7 × xgb_prob + 0.3 × iso_score
```

| Métrica | Valor |
|---|---|
| AUC-ROC (CV 5-fold) | 0,9860 ± 0,003 |
| Clientes CRITICAL | 1.075 (43%) |
| Clientes HIGH | 83 (3,3%) |
| Feature #1 (SHAP) | n_geojumps (2,48) |
| Feature #2 (SHAP) | max_income_ratio (1,31) |

**Gráficos gerados:**

| Arquivo | Descrição |
|---|---|
| [`shap_summary.png`](tarefa3/outputs/graficos/shap_summary.png) | SHAP beeswarm — top 15 features |
| [`roc_pr_curves.png`](tarefa3/outputs/graficos/roc_pr_curves.png) | Curvas ROC e Precision-Recall |
| [`tier_distribution.png`](tarefa3/outputs/graficos/tier_distribution.png) | Distribuição de tiers de risco |

**Para executar:**
```bash
pip install pandas scikit-learn xgboost shap matplotlib
python tarefa3/tarefa3_ml_model.py
# → gera ml_risk_scores.csv + gráficos
```

> Requer `aml.db` na raiz.

---

## Tarefa 4 — Pipeline Multi-agente LLM

**Script:** [`tarefa4/tarefa4_multiagent.py`](tarefa4/tarefa4_multiagent.py)  
**Documentação:** [`tarefa4/tarefa4_documentacao.md`](tarefa4/tarefa4_documentacao.md)  
**Outputs JSON:** [`tarefa4/outputs/`](tarefa4/outputs/)

5 agentes LLM especializados em sequência (Groq — LLaMA 3.3 70B):

```
[DADOS] → [DETECÇÃO] → [INVESTIGAÇÃO] → [SAR] → [COMPLIANCE]
```

Cada agente recebe o JSON acumulado dos anteriores. Output final: SAR completo em formato COAF + decisão de compliance.

**Casos processados:**

| Cliente | Perfil | Score | Decisão | Prazo COAF |
|---|---|---|---|---|
| C101048 | Mechanic, PEP, 5 geo-jumps, income 22× | 95 | APROV. COM RESSALVAS | 24h |
| C100932 | Nurse, 31 alertas HIGH, income 28× | 95 | APROV. COM RESSALVAS | 24h |
| C101208 | Chef, sanctions hit, geo-jump RU→BR 4min | 85 | APROV. COM RESSALVAS | 24h |
| C100091 | Analyst, rede M200363, sanctions Wire | 85 | APROV. COM RESSALVAS | 24h |
| C102221 | Consultant, geo-jump SY→BR 36s, income 53× | 85 | APROV. COM RESSALVAS | 24h |

**Para executar:**
```bash
pip install groq pandas
# Configurar GROQ_API_KEY no script ou como variável de ambiente
python tarefa4/tarefa4_multiagent.py
# → gera aml_case_{customer_id}.json
```

> Requer `aml.db` + `ml_risk_scores.csv` na raiz.

---

## Notebook Exploratório

**Arquivo:** [`notebook/aml_explore.ipynb`](notebook/aml_explore.ipynb)

Análise interativa com 51 células executadas cobrindo:
- Visão geral do dataset
- Queries por tipologia (structuring, geo-jump, fan-out, sanções)
- Score ponderado dos 29 suspeitos
- Distribuição de tiers ML com gráficos
- Inspeção dos outputs do pipeline multi-agente

```bash
pip install jupyter pandas matplotlib
jupyter notebook notebook/aml_explore.ipynb
```

---

## Banco de Dados

O arquivo `aml.db` (SQLite, ~15MB) não está versionado. Estrutura:

| Tabela | Registros | Descrição |
|---|---|---|
| `transactions` | 52.000 | Todas as transações PIX/Card/Wire |
| `kyc_profiles` | 2.500 | Perfis KYC dos clientes |
| `merchants` | 1.000 | Cadastro de merchants |

---

## Stack Técnica

| Componente | Tecnologia |
|---|---|
| Banco de dados | SQLite (`aml.db`) |
| Processamento | Python 3.12 + pandas |
| ML | scikit-learn 1.3 · XGBoost 2.0 · SHAP 0.44 |
| LLM | Groq API — LLaMA 3.3 70B Versatile |
| Relatório | reportlab 4.4 · python-docx |

---

## Referências Regulatórias Principais

- Lei 9.613/1998 — Lei de Lavagem de Dinheiro
- Circular BACEN 3.978/2020 — Política PLD/FT
- Carta-Circular BACEN 4.001/2020 — Tipologias suspeitas
- Resolução COAF 36/2021 — Estrutura do SAR
- FATF Recomendações 3, 6, 7, 10, 12, 15, 16
- OFAC SDN List · UNSC Consolidated List
