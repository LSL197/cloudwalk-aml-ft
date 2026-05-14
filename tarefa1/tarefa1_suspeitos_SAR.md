# Tarefa 1 — Suspeitos AML/FT e SAR
**CloudWalk AML/FT Technical Challenge**
Data de análise: 2025-10-05 | Analista: lsl197

---

## Metodologia

**Dataset:** 52.000 transações · 2.500 perfis KYC · 1.000 merchants · jul–out 2025

**Score de risco ponderado** (12 dimensões):

| Flag | Peso | Critério |
|---|---|---|
| Structuring valor | 2 | ≥2 txs entre R$9k–R$9.999 |
| Velocity structuring | 1 | ≥3 txs sub-R$10k no mesmo dia |
| Income ratio | 2 | tx > 15x renda mensal |
| Geo-jump | 3 | países diferentes em <12h (fisicamente impossível) |
| VPN/Tor/Proxy | 1 | acesso via anonimizador |
| Fan-out PIX | 2 | vol_out/vol_in > 3x com ≥3 txs cada lado |
| Self-merchant | 2 | sender = dono do merchant receptor |
| Sanctions hit | 3 | screening hit em qualquer tx |
| KYC alto risco | 1 | risk_rating=High ou sanctions_list_hit=Yes |
| PEP | 1 | pessoa politicamente exposta |
| Geo país alto risco | 1 | cross-border + country_risk=High |
| MCC alto risco | 1 | ≥3 txs em MCC 6011/6051/7995/4829/6538 |

**Nota:** Merchant M200363 (rede Iran) tratado exclusivamente no SAR ao final deste documento. Os 30 suspeitos abaixo são independentes dessa rede.

---

## Parte 1 — 30 Suspeitos Prioritários

### Tier Crítico — Score 11 (3 casos)

---

#### C100136 — Designer · Renda R$12.490/ano · Risk: Medium

**Score 11** | Structuring + Velocity + Geo-jump + VPN + Geo-risco + MCC

| Campo | Dado |
|---|---|
| Beneficial owner | Sim |
| KYC risk score | 47 |
| Total movimentado | R$109.861 (19 txs, jul–out 2025) |
| Maior tx | R$23.742 |
| Rails | PIX + Card + Wire |
| Cross-border | 4 txs |

**Evidências:**

- **Structuring valor:** 2 txs na faixa R$9k–R$9.999
- **Velocity burst:** ≥3 txs sub-R$10k em único dia
- **Geo-jump 1:** BR → MM (Myanmar) em **9,9 minutos** (2025-07-16) — R$2.342 → R$463
- **Geo-jump 2:** BR → PT em **29 minutos** (2025-08-12) — R$1.233 → R$7.476
- **VPN:** 3 txs via anonimizador, maior valor R$7.476
- **Geo risco:** transações cross-border com país alto risco
- **MCC alto risco:** ≥3 txs em MCC sensível
- **Beneficial owner declarado:** aumenta exposição a estruturas de ocultação

**Red flag principal:** Designer com renda de R$1.040/mês movimentando R$109k em 3 meses, com geo-jump BR→Myanmar em 10 minutos e beneficial owner declarado.

---

#### C101208 — Chef · Renda R$13.047/ano · Risk: Low

**Score 11** | Sanctions hit + Income ratio 31.6x + Geo-jump + VPN + Geo-risco + MCC

| Campo | Dado |
|---|---|
| KYC risk score | 51 |
| Total movimentado | R$150.178 (29 txs, jul–set 2025) |
| Maior tx | R$34.398 |
| Rails | PIX + Wire + Card |
| Cross-border | 9 txs |
| Sanctions hits | 1 |

**Evidências:**

- **Sanctions screening hit:** 1 tx com hit OFAC/UNSC (Wire, R$11.672, 2025-08-07)
- **Income ratio:** tx de R$34.398 = **31,6x renda mensal** (renda mensal R$1.087)
- **Geo-jump 1:** RU → BR em **4,1 minutos** (2025-09-23) — Rússia→Brasil em 4 min fisicamente impossível
- **Geo-jump 2:** PT → BR em **6,7 minutos** (2025-09-17) — R$17.044 → R$2.091
- **Geo-jump 3:** GB → ES em 28 minutos (2025-08-18)
- **VPN:** 2 txs via anonimizador
- **Cross-border:** 9 transações internacionais

**Red flag principal:** Chef com renda R$1.087/mês, 1 sanctions hit confirmado, geo-jump Rússia→Brasil em 4 minutos, tx máxima R$34k. Candidato primário a SAR individual.

---

#### C100792 — Mechanic · Renda R$16.315/ano · Risk: High

**Score 11** | Structuring + Velocity + Geo-jump + KYC High + MCC

| Campo | Dado |
|---|---|
| KYC risk score | 52 |
| Total movimentado | R$158.213 (29 txs, jul–out 2025) |
| Maior tx | R$29.912 |
| Rails | PIX + Card + Wire |
| Cross-border | 2 txs |

**Evidências:**

- **KYC risk_rating = High** (classificado no onboarding)
- **Structuring valor:** 2 txs na faixa R$9k–R$9.999
- **Velocity burst:** ≥3 txs sub-R$10k em único dia
- **Geo-jump:** CN → BR em **10,4 minutos** (2025-08-10) — China→Brasil em 10 min impossível
- **Income ratio:** 22x renda mensal em tx isolada
- **MCC alto risco:** ≥3 txs em MCC sensível
- **Volume total:** R$158k = 9,7x renda anual declarada

**Red flag principal:** Mecânico com KYC já classificado High, geo-jump China→Brasil em 10 minutos, movimentação 9,7x renda anual.

---

### Tier Alto — Score 10 (7 casos)

---

#### C101432 — Teacher · Renda R$7.381/ano · Risk: Low

**Score 10** | Structuring + Velocity + Income 35.5x + Geo-jump + VPN + MCC

- Structuring: 2 txs R$9k–R$9.999 | Velocity: burst em dia único
- Income ratio: **35,5x** renda mensal (renda R$615/mês)
- Geo-jump: US → BR em **9,8 min** (2025-08-08)
- VPN: 2 txs via anonimizador
- Total: R$113.046 em 21 txs (jul–out 2025)

---

#### C101534 — Entrepreneur · Renda R$8.326/ano · Risk: Low

**Score 10** | Structuring 3x + Income 17.8x + Geo-jump + VPN + Geo-risco + MCC

- Structuring: **3 txs** R$9k–R$9.999
- Income ratio: 17,8x renda mensal
- Geo-jump 1: AE → BR em **12,2 min** (2025-09-22) — UAE→Brasil
- Geo-jump 2: BR → AR em 25 min (2025-10-01)
- Cross-border: **9 txs** (maior frequência do grupo)
- Total: R$98.528 em 22 txs

---

#### C101677 — Freelancer · Renda R$8.916/ano · Risk: High

**Score 10** | KYC High + Velocity + Income 21.4x + Geo-jump + VPN R$12k + Geo-risco + MCC

- KYC risk_rating = High
- Geo-jump 1: BR → YE (Iêmen) em **8,5 min** (2025-08-02) — destino FATF grey list
- Geo-jump 2: YE → BR em **10,3 min** — retorno imediato após tx no Iêmen
- VPN: 3 txs, maior valor **R$12.468**
- Income ratio: 21,4x renda mensal (R$743/mês)
- Total: R$101.764 em 22 txs

**Nota:** Sequência BR→Iêmen→BR em 18 minutos com VPN = padrão de tunelamento via jurisdição opaca.

---

#### C100351 — Trader · Renda R$11.872/ano · Risk: Low

**Score 10** | Structuring 3x + Velocity + Income 17.5x + Geo-jump + VPN + MCC

- Structuring: **3 txs** R$9k–R$9.999, total R$28.598
- Geo-jump: FR → BR em **6,7 min** (2025-08-24)
- Income ratio: 17,5x renda mensal
- VPN: 2 txs via anonimizador
- Total: R$95.439 em 20 txs

---

#### C101141 — Student · Renda R$12.007/ano · Risk: Medium

**Score 10** | Structuring 3x + Income 27.8x + Geo-jump + VPN R$27k + Geo-risco + MCC

- Structuring: 3 txs R$9k–R$9.999
- Income ratio: **27,8x** renda mensal (R$1.000/mês)
- Geo-jump: PT → BR em **17,7 min** (2025-08-27)
- VPN: 2 txs, maior valor **R$27.810** — tx de 27x renda mensal via anonimizador
- Total: R$154.713 em 26 txs — volume incompatível com perfil de estudante

---

#### C101411 — Chef · Renda R$13.776/ano · Risk: Low · Beneficial Owner

**Score 10** | Structuring + Income 19.1x + Geo-jump + VPN + Geo-risco + MCC

- Beneficial owner declarado
- Structuring: 2 txs R$9k–R$9.999
- Geo-jump: US → BR em **23,9 min** (2025-08-30)
- Income ratio: 19,1x renda mensal (R$1.148/mês)
- VPN: 2 txs via anonimizador
- Cross-border: 5 txs internacionais
- Total: R$118.583 em 23 txs

---

#### C101222 — Trader · Renda R$14.534/ano · Risk: Low

**Score 10** | Structuring + Income 32.7x + Geo-jump + VPN + Geo-risco + MCC

- Structuring: 2 txs R$9k–R$9.999
- Income ratio: **32,7x** renda mensal (R$1.211/mês) — tx de R$39.546
- Geo-jump: BR → AE (Emirados) em **29,7 min** (2025-09-07)
- VPN: 2 txs via anonimizador
- Maior tx: **R$39.546**
- Total: R$115.027 em 25 txs

---

### Tier Elevado — Score 9 (20 casos)

---

#### C102202 — Chef · Renda R$2.445/ano · Risk: High

**Income ratio 101x** — maior incompatibilidade renda/volume do dataset

- Income ratio: **101,3x** renda mensal (renda mensal R$203)
- KYC risk_rating = High
- Geo-jump: detectado em 6,1 minutos
- VPN: 1 tx via anonimizador
- Total: R$68.860 em 18 txs — 28x renda anual declarada

---

#### C102221 — Consultant · Renda R$7.313/ano · Risk: High

**Geo-jump Síria→Brasil em 36 segundos**

- Geo-jump: **SY → BR em 0,6 minutos** (2025-07-06) — R$5.266 → R$32.528
- Síria: alta concentração de grupos sancionados OFAC/UNSC
- Income ratio: 53,4x renda mensal (tx de R$32.528)
- KYC risk_rating = High | VPN: 3 txs
- Total: R$103.323 em 18 txs

**Nota:** 36 segundos entre tx na Síria e tx no Brasil é fisicamente impossível. Indica falsificação de geolocalização não capturada pela flag de VPN padrão.

---

#### C102179 — Driver · Renda R$8.267/ano · Risk: Low

**PEP com ocupação incompatível**

- **PEP = Yes** (motorista declarado como PEP — inconsistência de ocupação)
- Geo-jump: BR → ES em **8,2 min** (2025-07-29)
- Income ratio: 25x renda mensal (R$688/mês)
- VPN: 3 txs, maior valor **R$17.239**
- Total: R$122.941 em 28 txs

---

#### C101166 — Software Engineer · Renda R$10.815/ano · Risk: High

**PEP + KYC High**

- PEP = Yes + risk_rating = High (dupla flag KYC)
- Income ratio: 37,6x renda mensal (tx de R$33.909)
- Geo-jump: US → BR em **25,2 min** (2025-08-11) — R$10.468 → R$880
- VPN: 1 tx via anonimizador
- Total: R$103.852 em 23 txs

---

#### C100853 — Accountant · Renda R$8.326/ano · Risk: Medium

**4 geo-jumps em 48h incluindo Afeganistão**

- Geo-jump 1: ES → GB em **0,8 min** (2025-07-23)
- Geo-jump 2: GB → BR em 22,6 min
- Geo-jump 3: BR → AF (Afeganistão) em **3,5 min** (2025-08-01) — FATF black list
- Geo-jump 4: AF → BR em 19,2 min
- VPN: **4 txs**, maior valor R$16.201
- Income ratio: 29,5x renda mensal
- Total: R$136.816 em 28 txs

**Nota:** Sequência passando pelo Afeganistão (FATF black list) = padrão de layering via jurisdição de alto risco TF.

---

#### C100424 — Student · Renda R$9.278/ano · Risk: Medium

**VPN R$20k + Velocity**

- VPN: 2 txs, maior valor **R$20.054** (estudante, renda R$773/mês)
- Velocity burst: ≥3 txs sub-R$10k em único dia
- Geo-jump: detectado em 4,9 minutos
- Income ratio: 25,9x renda mensal
- Cross-border: 6 txs internacionais
- Total: R$79.205 em 27 txs

---

#### C100014 — Designer · Renda R$6.703/ano · Risk: High

**KYC High + VPN R$13k**

- KYC risk_rating = High
- VPN: 3 txs, maior valor **R$13.723**
- Income ratio: 24,6x renda mensal (R$558/mês)
- Geo-jump: detectado em 10,6 minutos
- Total: R$85.543 em 19 txs

---

#### C101047 — Store Owner · Renda R$6.832/ano · Risk: High

**KYC High + VPN R$23k + Income 40.7x**

- KYC risk_rating = High
- VPN: 3 txs, maior valor **R$23.170**
- Income ratio: **40,7x** renda mensal (R$569/mês)
- Geo-jump: detectado em 14,3 minutos
- Cross-border: 5 txs
- Total: R$63.543 em 24 txs

---

#### C102003 — Trader · Renda R$4.810/ano · Risk: Low

**Income ratio 88.9x**

- Income ratio: **88,9x** renda mensal (R$400/mês) — 2º maior do dataset
- Structuring: 2 txs R$9k–R$9.999
- Geo-jump: detectado em 8,1 minutos
- VPN: 2 txs, maior valor R$5.021
- Maior tx: R$35.649
- Total: R$145.814 em 21 txs

---

#### C100940 — Lawyer · Renda R$5.364/ano · Risk: Low

**Income 74.4x + Velocity + 8 txs cross-border**

- Income ratio: **74,4x** renda mensal (R$447/mês)
- Velocity burst: ≥3 txs sub-R$10k em único dia
- VPN: 3 txs via anonimizador
- Cross-border: **8 txs** — maior frequência do tier
- Maior tx: R$33.273
- Total: R$127.123 em 28 txs

---

#### C101756 — Chef · Renda R$6.166/ano · Risk: Low

**Income 52.4x + Structuring**

- Income ratio: **52,4x** renda mensal (R$513/mês)
- Structuring: 2 txs R$9k–R$9.999
- Geo-jump: detectado em 12 minutos
- Maior tx: R$26.931
- Total: R$99.121 em 19 txs

---

#### C100435 — Dentist · Renda R$6.995/ano · Risk: Low

**Income 51.9x + Structuring**

- Income ratio: **51,9x** renda mensal (R$582/mês)
- Structuring: 2 txs R$9k–R$9.999
- Geo-jump: detectado em 22,2 minutos
- Cross-border: 5 txs
- Maior tx: R$30.241
- Total: R$126.678 em 22 txs

---

#### C100359 — Store Owner · Renda R$5.167/ano · Risk: Low

**KYC Score interno 100 + Income 41.6x**

- KYC risk score interno: **100** (máximo possível)
- Income ratio: 41,6x renda mensal (R$430/mês)
- Structuring: 2 txs R$9k–R$9.999
- VPN: 2 txs via anonimizador
- Geo-jump: detectado em 13,3 minutos
- Total: R$138.404 em 21 txs

---

#### C102368 — Lawyer · Renda R$3.254/ano · Risk: Low

**KYC Score 93 + Income 34.1x**

- KYC risk score interno: **93**
- Income ratio: 34,1x renda mensal (R$271/mês)
- Structuring: 2 txs R$9k–R$9.999 (tx máxima R$9.254)
- Geo-jump: detectado em 17,4 minutos
- VPN: 1 tx
- Total: R$56.710 em 16 txs

---

#### C101225 — Designer · Renda R$7.629/ano · Risk: Low

**Structuring + Velocity + 7 txs cross-border**

- Structuring: 2 txs R$9k–R$9.999 + velocity burst
- Income ratio: 39,5x renda mensal (R$635/mês)
- Geo-jump: detectado em 2,9 minutos
- Cross-border: 7 txs internacionais
- Total: R$144.728 em 23 txs

---

#### C100504 — Consultant · Renda R$10.071/ano · Risk: Medium

**VPN 4 txs + Structuring**

- VPN: **4 txs** via anonimizador (mais frequente do tier)
- Structuring: 2 txs R$9k–R$9.999
- Income ratio: 28,2x renda mensal (R$839/mês)
- Geo-jump: detectado em 13,5 minutos
- Total: R$105.214 em 21 txs

---

#### C102398 — Entrepreneur · Renda R$8.760/ano · Risk: Low

**KYC Score 100 + VPN 4 txs + Structuring**

- KYC risk score interno: **100** (máximo)
- VPN: **4 txs** via anonimizador
- Structuring: 2 txs R$9k–R$9.999
- Income ratio: 35,9x renda mensal (R$730/mês)
- Geo-jump: detectado em 26,1 minutos
- Total: R$127.793 em 26 txs

---

#### C100366 — Software Engineer · Renda R$9.386/ano · Risk: High

**KYC High + Income 20.4x + 5 txs cross-border**

- KYC risk_rating = High
- Income ratio: 20,4x renda mensal (R$782/mês)
- Geo-jump: detectado em 3,1 minutos
- VPN: 1 tx
- Cross-border: 5 txs
- Total: R$103.057 em 29 txs

---

#### C101006 — Software Engineer · Renda R$11.572/ano · Risk: Low

**Velocity + VPN + 6 txs cross-border**

- Velocity burst: ≥3 txs sub-R$10k em único dia
- VPN: 2 txs via anonimizador
- Income ratio: 20,3x renda mensal (R$964/mês)
- Geo-jump: detectado em 12,1 minutos
- Cross-border: 6 txs
- Total: R$92.882 em 23 txs

---

#### C100507 — Accountant · Renda R$13.339/ano · Risk: Low

**Structuring + Velocity (padrão duplo)**

- Structuring: 2 txs R$9k–R$9.999 + velocity burst no mesmo período
- Income ratio: 18,6x renda mensal (R$1.111/mês)
- Geo-jump: detectado em 6,5 minutos
- Cross-border: 5 txs
- Total: R$81.682 em 21 txs

---

#### C100931 — Mechanic · Renda R$6.300/ano · Risk: High

**KYC High + Income 16.3x + VPN + Geo-risco + MCC**

- KYC risk_rating = High
- Income ratio: 16,3x renda mensal (R$525/mês)
- Geo-jump: detectado em 10,9 minutos
- VPN: 2 txs via anonimizador
- Cross-border: país alto risco detectado
- MCC alto risco: ≥3 txs em MCC sensível

---

## Parte 2 — SAR: Rede M200363 (Irã)

### Relatório de Atividade Suspeita
**Protocolo:** SAR-2025-001
**Data:** 2025-10-05
**Período:** 2025-07-02 a 2025-10-04
**Base legal primária:** Circular BACEN 3.978/2020, Art. 37

---

### 1. Identificação do Sujeito Principal

| Campo | Dado |
|---|---|
| **ID** | M200363 |
| **Tipo** | Merchant (pessoa jurídica) |
| **País de operação** | IR (Irã) |
| **Owner customer_id** | **Não registrado** |
| **merchant_high_risk_flag** | Yes |

A ausência de owner_customer_id viola KYB (Know Your Business). Impossibilidade de identificar o Beneficial Owner Final (BOF) é red flag regulatório autônomo, independente das demais evidências.

---

### 2. Resumo Executivo

Entre jul e out 2025, M200363 recebeu **R$171.099,18** de **43 clientes brasileiros** via PIX, Card e Wire, distribuindo **R$53.373,16** para **8 destinatários** na mesma jurisdição iraniana.

Padrão: **placement → layering → integration**
- **Placement:** 43 clientes depositam valores de R$302 a R$14.625
- **Layering:** merchant agrega e redistribui para 8 contas distintas
- **Integration:** valores saem em nome de diferentes entidades iranianas

1 transação com **sanctions_screening_hit = Yes** (Wire R$11.672, cliente C100091, 2025-08-07) — obrigação de comunicação imediata ao COAF.

---

### 3. Entradas — 43 clientes → M200363 (R$171.099,18)

| Data | Sender | Valor (R$) | Rail | Sanctions |
|---|---|---|---|---|
| 2025-07-02 | C100953 | 1.647,81 | PIX | No |
| 2025-07-03 | C100842 | 773,94 | Wire | No |
| 2025-07-04 | C100611 | 2.653,33 | Card | No |
| 2025-07-15 | C102137 | 472,10 | PIX | No |
| 2025-07-17 | C101713 | 1.530,35 | Card | No |
| 2025-07-17 | C100049 | 355,69 | PIX | No |
| 2025-07-17 | C100291 | 4.299,72 | PIX | No |
| 2025-07-18 | C101065 | 14.625,65 | PIX | No |
| 2025-07-21 | C101114 | 7.330,75 | PIX | No |
| 2025-07-23 | C100947 | 10.782,30 | Card | No |
| 2025-07-25 | C100261 | 2.132,72 | PIX | No |
| 2025-07-28 | C100201 | 1.530,57 | PIX | No |
| 2025-07-28 | C101204 | 2.798,64 | Card | No |
| 2025-07-30 | C102411 | 7.191,90 | PIX | No |
| 2025-08-01 | C101126 | 872,04 | PIX | No |
| 2025-08-04 | C102022 | 1.766,77 | PIX | No |
| 2025-08-05 | C100711 | 3.404,97 | PIX | No |
| 2025-08-06 | C100680 | 905,67 | Card | No |
| **2025-08-07** | **C100091** | **11.672,88** | **Wire** | **YES ⚠️** |
| 2025-08-08 | C100133 | 13.886,93 | PIX | No |
| 2025-08-13 | C101637 | 1.522,15 | Card | No |
| 2025-08-14 | C100217 | 302,29 | PIX | No |
| 2025-08-23 | C100893 | 3.062,03 | PIX | No |
| 2025-08-23 | C102155 | 1.028,89 | PIX | No |
| 2025-08-25 | C100125 | 719,76 | PIX | No |
| 2025-08-26 | C101551 | 6.264,49 | Card | No |
| 2025-08-26 | C101033 | 2.572,56 | Card | No |
| 2025-08-31 | C101976 | 1.280,09 | PIX | No |
| 2025-09-02 | C100224 | 9.161,49 | PIX | No |
| 2025-09-03 | C102001 | 6.904,38 | Card | No |
| 2025-09-07 | C101933 | 7.705,05 | PIX | No |
| 2025-09-08 | C102348 | 2.687,39 | PIX | No |
| 2025-09-09 | C102339 | 1.507,28 | PIX | No |
| 2025-09-10 | C101772 | 7.807,64 | PIX | No |
| 2025-09-21 | C102304 | 1.963,13 | PIX | No |
| 2025-09-21 | C100982 | 1.598,90 | PIX | No |
| 2025-09-24 | C102163 | 3.346,59 | PIX | No |
| 2025-09-26 | C101659 | 4.284,74 | PIX | No |
| 2025-09-28 | C102286 | 4.152,82 | PIX | No |
| 2025-09-30 | C100024 | 4.827,04 | PIX | No |
| 2025-10-02 | C102185 | 2.854,47 | PIX | No |
| 2025-10-03 | C101826 | 441,03 | PIX | No |
| 2025-10-04 | C102289 | 4.470,24 | PIX | No |

---

### 4. Saídas — M200363 → 8 destinatários (R$53.373,16)

| Data | Receiver | Valor (R$) | Rail |
|---|---|---|---|
| 2025-07-20 | C101950 | 1.223,76 | Card |
| 2025-07-20 | C102419 | 19.218,89 | PIX |
| 2025-07-26 | C100954 | 5.604,45 | PIX |
| 2025-09-02 | C101839 | 7.797,62 | PIX |
| 2025-09-06 | C102375 | 986,88 | Card |
| 2025-09-09 | C101377 | 6.442,15 | Card |
| 2025-09-10 | C101615 | 9.169,40 | PIX |
| 2025-10-02 | C101862 | 2.930,01 | Card |

**Saldo retido no merchant: ~R$117.726**

---

### 5. Análise Tipológica

**T1 — Financiamento ao Terrorismo via intermediário iraniano**
Irã sob sanções OFAC (Iran Sanctions Program) e UNSC desde 2006. Transferência de valor a entidade iraniana sem licença OFAC específica constitui violação federal (EUA) e obrigação de reporte no Brasil. M200363 sem owner identificável é estrutura opaca típica de front company.

**T2 — Layering via fan-out reverso**
43 fontes → 1 agregador → 8 destinos. O merchant funciona como mixer: recebe de muitos, redistribui fragmentado, quebrando rastro origem→destino.

**T3 — Structuring temporal (slow drip)**
Entradas espaçadas ao longo de 94 dias (jul–out) em valores irregulares, evitando concentração temporal que dispararia alertas automáticos.

**T4 — KYB incompleto**
Merchant sem owner_customer_id registrado. Impossibilidade de identificar BOF viola Art. 8º da Lei 9.613/98 e Circular 3.978/2020.

---

### 6. Sujeito Prioritário — C100091

Único com sanctions_screening_hit = Yes na rede M200363:
- Tx: Wire R$11.672,88 → M200363, 2025-08-07T17:28:29, geo_country=IR
- **Obrigação:** comunicação ao COAF em até 24h (Circular 3.978 Art. 37 §1º)
- **Ação imediata:** bloqueio cautelar + solicitação de documentação comprobatória da relação comercial

---

### 7. Base Legal

| Norma | Aplicação |
|---|---|
| Lei 9.613/1998 Art. 1º | Crime de lavagem via ocultação de origem |
| Circular BACEN 3.978/2020 Art. 37 | Comunicação obrigatória ao COAF |
| Carta-Circular BACEN 4.001/2020 | Indícios de LD/FT |
| FATF Rec. 6 | Targeted Financial Sanctions |
| FATF Rec. 7 | Sanções — proliferação de armas |
| OFAC Iran Sanctions Program | Proibição de transações com entidades iranianas |
| UNSC Res. 1737/2006 e 2231/2015 | Sanções ao Irã — setor financeiro |

---

### 8. Ações Recomendadas

1. **Imediato (24h):** Comunicar C100091 ao COAF — sanctions hit confirmado
2. **72h:** Congelar preventivamente transações de/para M200363
3. **Investigação:** Mapear KYC dos 43 clientes — verificar coordenação (mesmo IP, device, endereço)
4. **KYB:** Solicitar documentação M200363 — contrato social, BOF, licença operacional no Irã
5. **Ampliação:** Verificar se os 8 destinatários das saídas possuem contas ativas na plataforma
6. **Regulatório:** Reportar à UIF/COAF conforme Resolução COAF 36/2021

---

*Documento gerado para CloudWalk AML/FT Technical Challenge. Dados sintéticos.*
