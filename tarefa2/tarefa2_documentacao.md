# Tarefa 2 — Documentação do Sistema de Alertas AML/FT
**CloudWalk AML/FT Technical Challenge**
Data: 2025-10-05 | Analista: lsl197

---

## Visão Geral

20 regras cobrindo 8 tipologias de lavagem de dinheiro e financiamento ao terrorismo.  
Cada regra é uma função Python independente que consulta o banco SQLite e retorna alertas padronizados.

**Severidades:**
- `HIGH` — ação requerida, investigação obrigatória
- `MEDIUM` — investigar dentro de prazo estendido, pode ser falso positivo

**Saída padrão de cada alerta:**
```
alert_id | rule_id | rule_name | customer_id | transaction_id
amount_brl | severity | evidence | timestamp
```

---

## Tipologia 1 — Structuring / Smurfing

> Fragmentação deliberada de valores abaixo do limiar de reporte (R$10.000) para evitar detecção. Tipologia mais clássica de LD — etapa de placement.

**Base regulatória:** Lei 9.613/98 Art. 1º; Carta-Circular BACEN 4.001/2020 item I; FATF Rec. 3

---

### R01 — PIX Structuring ≥3 txs R$9k–R$9.999

**Severidade:** HIGH  
**Critério:** cliente com ≥3 transações PIX na faixa R$9.000–R$9.999,99

**Por que esse threshold?**
- R$10.000 é o limiar histórico de reporte automático no mercado brasileiro
- Faixa R$9k–R$9.999 é a "zona de conforto" do smurfer — alto o suficiente pra mover valor, baixo o suficiente pra evitar flag
- ≥3 ocorrências elimina coincidência (1 tx pode ser normal, 3 é padrão)
- PIX separado do Card porque PIX é instantâneo e dificulta rastreio

**Falsos positivos esperados:** pagamentos recorrentes de aluguel/mensalidade próximos a R$9.500

---

### R02 — Card Structuring ≥3 txs R$9k–R$9.999

**Severidade:** HIGH  
**Critério:** mesmo que R01 mas em transações de cartão

**Por que separado do R01?**
Card e PIX têm rails distintos — um cliente pode fazer structuring em ambos simultaneamente para pulverizar ainda mais. Regra separada permite detectar structuring cross-rail.

---

### R03 — Rapid Structuring ≥2 txs R$9k+ em 24h

**Severidade:** HIGH  
**Critério:** ≥2 transações R$9k–R$9.999 no mesmo dia, com span ≤24h

**Por que esse critério?**
Structuring em rajada é mais grave que structuring espaçado — indica urgência de movimentar valor, típico de placement de dinheiro acabou de entrar em caixa (ex: tráfico, fraude). Threshold de 2 txs (não 3) porque a concentração temporal já é evidência suficiente.

---

## Tipologia 2 — Income Ratio Incompatível

> Transações incompatíveis com a capacidade financeira declarada do cliente. Indica renda não declarada de origem ilícita ou declaração falsa de ocupação/renda no KYC.

**Base regulatória:** Circular BACEN 3.978/2020 Art. 27; Carta-Circular 4.001/2020 item III; FATF Rec. 10

---

### R04 — Income Ratio >15x Renda Mensal

**Severidade:** HIGH  
**Critério:** transação individual > 15 × (renda_anual / 12)

**Por que 15x?**
- Abaixo de 10x: muitos falsos positivos (parcelamentos, venda de bem, empréstimo)
- Acima de 20x: miss rate alto — casos relevantes escapam
- 15x = tx equivale a 1,25× renda anual inteira em uma única operação
- Calibrado empiricamente: gera ~1.986 alertas no dataset de 52k txs (~3,8%)
- Em produção: threshold ajustado por segmento (Trader tolera mais que Teacher)

---

### R05 — PEP Income Ratio >5x Renda Mensal

**Severidade:** HIGH  
**Critério:** cliente PEP com transação > 5 × renda mensal

**Por que threshold menor para PEP?**
FATF Recomendação 12 exige enhanced due diligence para PEPs. Risco inerente é maior — mesmo uma tx de 5x renda de servidor público é red flag de corrupção. Threshold separado evita que PEPs passem pelo R04 com threshold mais permissivo.

---

## Tipologia 3 — Sanções e Geopolítica

> Transações com contrapartes ou jurisdições sob sanções internacionais (OFAC, UNSC) ou classificadas como alto risco pelo FATF/GAFI.

**Base regulatória:** Lei 13.810/2019; Circular BACEN 3.978/2020 Art. 37; OFAC SDN List; UNSC Consolidated List; FATF Recs. 6 e 7

---

### R06 — Sanctions Screening Hit

**Severidade:** HIGH  
**Critério:** `sanctions_screening_hit = Yes` em qualquer transação

**Por que HIGH imediato?**
Hit em lista de sanções (OFAC/UNSC/UE) não é um sinal — é uma certeza. Obrigação legal de comunicação ao COAF em até 24h (Circular 3.978 Art. 37 §1º). Não há threshold: qualquer hit, qualquer valor, dispara alerta.

---

### R07 — KYC Sanctions List Hit

**Severidade:** HIGH  
**Critério:** `sanctions_list_hit = Yes` no perfil KYC do cliente

**Diferença do R06:**
R06 detecta hit em tempo real na transação. R07 detecta cliente que foi identificado em lista de sanções durante processo de onboarding/revisão KYC. São eventos distintos — cliente pode estar na lista sem ter feito tx suspeita ainda (bloqueio preventivo).

---

### R08 — Cross-border País Alto Risco

**Severidade:** HIGH (ambos lados alto risco) / MEDIUM (um lado)  
**Critério:** `cross_border = Yes` + `country_risk_geo = High` ou `country_risk_receiver = High`

**Por que severidade variável?**
- Ambos os lados em país alto risco = maior probabilidade de rota deliberada de layering
- Apenas um lado = pode ser turismo, comércio legítimo com fornecedor internacional
- Países considerados alto risco: alinhado com lista FATF grey/black list + jurisdições não cooperantes

---

## Tipologia 4 — Geo-jump / Viagem Impossível

> Mesmo cliente realiza transações em países diferentes em intervalo fisicamente impossível para deslocamento humano. Indica uso de VPN/proxy não detectado, falsificação de geolocalização, ou múltiplos dispositivos/pessoas usando mesma conta.

**Base regulatória:** Carta-Circular BACEN 4.001/2020 item VIII (acesso atípico); FATF Rec. 16

---

### R09 — Geo-jump Países Diferentes em <12h

**Severidade:** HIGH  
**Critério:** mesmo `sender_id` com `geo_country` diferentes em duas txs com intervalo <12h

**Por que 12h?**
- Voo mais longo do Brasil: ~18h (Brasil→Austrália)
- Voos intercontinentais mais comuns: 10–14h
- 12h como limite garante que qualquer par de países detectado é fisicamente impossível sem teleporte
- Casos extremos encontrados no dataset: Síria→Brasil em 0,6 min, China→Brasil em 10 min

**Limitação conhecida:** gera muitos alertas (1.618) porque qualquer par de geo_country diferente dispara. Em produção: filtrar por distância geográfica mínima entre países.

---

## Tipologia 5 — Cash Fan-out / Mula de Dinheiro

> Cliente recebe agregado de múltiplas fontes e redistribui rapidamente para múltiplos destinos. Comportamento típico de conta laranja (money mule) na etapa de layering.

**Base regulatória:** Lei 9.613/98 Art. 1º §2º (ocultação); Carta-Circular 4.001/2020 item V; FATF Rec. 3

---

### R10 — PIX Fan-out Ratio >10x

**Severidade:** HIGH  
**Critério:** `vol_out_PIX / vol_in_PIX > 10` com ≥3 txs em cada direção

**Por que ratio 10x?**
- Ratio 1x = pessoa que recebe e gasta normalmente (não suspeito)
- Ratio 2–5x = pode ser revendedor, intermediário comercial legítimo
- Ratio >10x = quase impossível explicar com comportamento legítimo
- ≥3 txs em cada direção elimina casos isolados (ex: recebeu 1 pix grande e fez 15 pequenos)

---

### R11 — Rapid Redistribution >80% em 48h

**Severidade:** MEDIUM  
**Critério:** cliente recebe PIX (cash_in) e redistribui >80% do volume no mesmo dia ou até 2 dias depois

**Por que MEDIUM (não HIGH)?**
Redistribuição rápida pode ser comportamento legítimo: empresas de pagamento, marketplaces, condomínios coletando e repassando. Por isso MEDIUM — requer contexto adicional para elevar. Combinado com outros sinais (VPN, geo-jump) eleva para HIGH na análise manual.

**Por que 80%?**
- 100% = conta que não retém nada (mais suspeito, mas raramente exato)
- 50% = metade sai, metade fica (pode ser poupança + gastos)
- 80% = quase tudo passa pela conta, retenção mínima = conta canal, não destino

---

## Tipologia 6 — Self-Merchant / Ciclo Fechado

> Cliente realiza transação para um merchant do qual é o próprio dono registrado. Permite criar receitas fictícias, simular vendas, e justificar entrada de dinheiro ilícito como receita empresarial (integration).

**Base regulatória:** Lei 9.613/98 Art. 1º (ocultação de origem); Carta-Circular 4.001/2020 item IX

---

### R12 — Self-Merchant

**Severidade:** HIGH (merchant de alto risco) / MEDIUM (merchant padrão)  
**Critério:** `sender_id = owner_customer_id` do merchant receptor

**Por que severidade varia?**
Self-merchant em MCC normal (ex: restaurante) pode ser empresário pagando própria empresa (baixo risco real). Self-merchant em MCC 7995 (gambling) ou com `merchant_high_risk_flag = Yes` é esquema claro de integration — daí HIGH.

---

## Tipologia 7 — Fraude / E-commerce sem Autenticação

> Transações de e-commerce sem autenticação 3DS (3D Secure) em valores altos, indicando possível uso de cartão furtado, compra com credenciais roubadas, ou tentativa de fraude no chargeaback.

**Base regulatória:** PCI-DSS v4.0; Carta-Circular BACEN 4.001/2020 item VII; FATF Rec. 15 (tecnologia)

---

### R13 — E-commerce sem 3DS Alto Valor >R$5k

**Severidade:** MEDIUM  
**Critério:** `transaction_type = Card` + `capture_method = E-commerce` + (`auth_3ds = No` OR `eci = 07`) + `amount_brl > 5.000`

**Por que ECI 07 é suspeito?**
ECI (Electronic Commerce Indicator) 07 = transação processada sem autenticação do portador. Lojistas legítimos preferem ECI 05/02 (autenticado) para reduzir chargeback. ECI 07 em valor alto = risco elevado de fraude.

**Por que threshold R$5k?**
Abaixo de R$5k o custo de investigar supera o risco. Acima de R$5k sem 3DS a exposição ao chargeback justifica alerta. Em produção: threshold por MCC (MCC 6051 crypto sem 3DS = HIGH qualquer valor).

---

### R14 — Merchant Alto Chargeback >2% (90d)

**Severidade:** MEDIUM  
**Critério:** merchant receptor com `merchant_chargeback_ratio_90d > 0.02`

**Por que 2%?**
- Visa/Mastercard: threshold de monitoramento = 1%, threshold de programa de risco = 2%
- >2% em 90 dias = merchant fora dos padrões das bandeiras
- Merchants com chargeback alto são usados em esquemas de friendly fraud e bust-out

**Limitação:** gera 33.240 alertas — maior volume do sistema. Em produção: combinar com valor mínimo (>R$1k) e outros sinais para reduzir noise.

---

## Tipologia 8 — Device e Acesso Suspeito

> Uso de ferramentas de anonimização (VPN, Tor, Proxy), dispositivos comprometidos (rooted/jailbreak), ou padrões de acesso atípicos que indicam tentativa de ocultar identidade ou localização real do operador.

**Base regulatória:** Carta-Circular BACEN 4.001/2020 item VIII; FATF Rec. 15; Resolução CMN 4.893/2021 (segurança cibernética)

---

### R15 — VPN/Tor/Proxy + Alto Valor >R$10k

**Severidade:** HIGH (com PEP ou cross-border) / MEDIUM (demais)  
**Critério:** `ip_proxy_vpn_tor != None` + `amount_brl > 10.000`

**Por que R$10k (não R$5k)?**
VPN sozinho não é crime — muitas pessoas usam por privacidade. O sinal torna-se suspeito combinado com alto valor. R$10k como threshold porque abaixo disso VPN+valor tem alta taxa de falso positivo (funcionário home-office fazendo pagamento normal).

**Por que severidade sobe com PEP/cross-border?**
VPN + PEP = tentativa de ocultar identidade de pessoa com obrigação de transparência.
VPN + cross-border = dupla camada de ocultação (localização + jurisdição).

---

### R16 — Dispositivo Rooted/Jailbroken + Alto Valor >R$5k

**Severidade:** MEDIUM  
**Critério:** `device_rooted = Yes` + `amount_brl > 5.000`

**Por que é suspeito?**
Dispositivo rooted/jailbroken remove proteções de segurança do SO. Indica: (a) usuário técnico contornando controles, (b) malware que obteve root para interceptar autenticação, (c) dispositivo comprometido usado para fraude. Threshold R$5k porque device rooted em compra pequena pode ser casual.

---

### R17 — MCC Alto Risco Acumulado ≥3 txs

**Severidade:** MEDIUM  
**Critério:** ≥3 transações em MCCs 6011, 6051, 7995, 4829 ou 6538

**MCCs e por que são alto risco:**

| MCC | Categoria | Risco |
|---|---|---|
| 6011 | Saque em ATM / casa lotérica | Conversão para cash, placement |
| 6051 | Troca de moeda / crypto | Layering via cripto |
| 7995 | Apostas / gambling | Mixer de dinheiro, difícil rastrear |
| 4829 | Wire transfer / remessa | Cross-border sem identificação clara |
| 6538 | Recargas / top-up | Valor fracionado, difícil rastrear destino |

**Por que ≥3 txs?**
1–2 transações em MCC de risco pode ser comportamento pontual (saque ocasional, aposta esportiva). 3+ txs indica padrão habitual de uso desses canais para movimentar valor.

---

### R18 — PEP Volume Total >R$100k

**Severidade:** HIGH  
**Critério:** cliente PEP com soma de transações > R$100.000 no período

**Por que PEP merece regra de volume separada?**
PEPs têm enhanced due diligence obrigatório (FATF Rec. 12). Volume alto de PEP não é automaticamente suspeito (político rico existe), mas acima de R$100k no período analisado (3 meses) justifica revisão formal do relacionamento e atualização do perfil de risco.

---

### R19 — Velocity Spike >10 txs/dia

**Severidade:** MEDIUM  
**Critério:** cliente com >10 transações no mesmo dia

**Por que 10 txs/dia?**
Comportamento normal de pessoa física: 2–5 txs/dia (alimentação, transporte, compras). >10 txs/dia é atípico para PF — pode indicar conta sendo usada como terminal de pagamento não declarado, bot realizando operações automatizadas, ou teste de cartão (carding).

**Resultado no dataset:** 0 alertas — threshold provavelmente alto demais para este dataset. Em produção: ajustar para >5 txs/dia ou analisar por tipo de cliente (PF vs PJ).

---

### R20 — Rede Iran M200363 (OFAC)

**Severidade:** HIGH  
**Critério:** transação com `sender_id = M200363` ou `receiver_id = M200363`

**Por que regra dedicada?**
M200363 é merchant iraniano com `merchant_high_risk_flag = Yes` e sem owner registrado, operando em jurisdição sob sanções OFAC/UNSC. Qualquer transação com essa contraparte, de qualquer valor, é HIGH por definição regulatória — independente dos demais sinais.

Esta regra é um exemplo de **blocklist dinâmica**: em produção, a lista de merchants/clientes bloqueados seria mantida separada do código e atualizada em tempo real conforme novas sanções são publicadas (OFAC SDN List é atualizada diariamente).

---

## Sumário das Regras

| ID | Nome | Tipologia | Severidade | Alertas no Dataset |
|---|---|---|---|---|
| R01 | PIX Structuring ≥3 txs R$9k-9.999 | Structuring | HIGH | 6 |
| R02 | Card Structuring ≥3 txs R$9k-9.999 | Structuring | HIGH | 0 |
| R03 | Rapid Structuring ≥2 txs em 24h | Structuring | HIGH | 1 |
| R04 | Income Ratio >15x renda mensal | Income | HIGH | 1.986 |
| R05 | PEP Income Ratio >5x renda mensal | Income | HIGH | 372 |
| R06 | Sanctions Screening Hit | Sanções | HIGH | 2 |
| R07 | KYC Sanctions List Hit | Sanções | HIGH | 9 |
| R08 | Cross-border País Alto Risco | Geopolítica | HIGH/MED | 590 |
| R09 | Geo-jump Países Diferentes <12h | Geo-jump | HIGH | 1.618 |
| R10 | PIX Fan-out Ratio >10x | Fan-out | HIGH | 36 |
| R11 | Rapid Redistribution >80% em 48h | Fan-out | MEDIUM | 50 |
| R12 | Self-Merchant Ciclo Fechado | Self-merchant | HIGH/MED | 2 |
| R13 | E-commerce sem 3DS >R$5k | Fraude | MEDIUM | 461 |
| R14 | Merchant Chargeback >2% (90d) | Fraude | MEDIUM | 33.240 |
| R15 | VPN/Tor Alto Valor >R$10k | Device | HIGH/MED | 332 |
| R16 | Dispositivo Rooted >R$5k | Device | MEDIUM | 425 |
| R17 | MCC Alto Risco ≥3 txs | Device | MEDIUM | 2.271 |
| R18 | PEP Volume Total >R$100k | PEP | HIGH | 24 |
| R19 | Velocity Spike >10 txs/dia | Device | MEDIUM | 0 |
| R20 | Rede Iran M200363 (OFAC) | Sanções | HIGH | 51 |

**Total:** 41.476 alertas brutos · 2.587 clientes únicos · 34.622 txs únicas

---

## Limitações Conhecidas

**1. Deduplicação ausente**
Mesmo cliente pode acionar 8 regras diferentes = 8 alertas separados. Em produção: agrupar por `customer_id`, consolidar evidências, apresentar 1 caso unificado ao analista.

**2. R14 gera ruído excessivo**
33.240 alertas de chargeback dominam o output. Threshold precisa de filtro adicional (valor mínimo + outro sinal corroborativo).

**3. R19 zerado**
Threshold >10 txs/dia muito alto para este dataset. Ajustar para >5 em produção.

**4. Thresholds estáticos**
15x income, R$5k, R$10k são fixos. Em produção: thresholds dinâmicos por segmento de cliente (Trader vs Teacher vs Student) calibrados com backtest em casos históricos confirmados.

**5. Sem estado temporal**
Sistema não sabe se alerta já foi investigado. Em produção: integrar com case management system (status: open/investigating/closed/SAR_filed).

---

---

## Referências Normativas

### Legislação Brasileira

| Instrumento | Ementa | Relevância |
|---|---|---|
| **Lei 9.613/1998** | Lei de Lavagem de Dinheiro — define o crime, obrigações de reporte e entidades sujeitas | Base de toda tipologia de LD — Art. 1º (crime), Art. 1º §2º (ocultação/dissimulação), Art. 11 (obrigação de comunicação) |
| **Lei 13.810/2019** | Adequação às Resoluções do Conselho de Segurança da ONU sobre terrorismo, proliferação e sanções | R06, R07, R20 — bloqueio preventivo e comunicação imediata em caso de sanção CSNU |

### Banco Central do Brasil (BACEN)

| Instrumento | Ementa | Relevância |
|---|---|---|
| **Circular BACEN 3.978/2020** | Política, procedimentos e controles internos de PLD/FT para instituições financeiras autorizadas | Art. 27 (monitoramento por incompatibilidade de renda), Art. 37 (comunicação ao COAF em até 24h), Art. 37 §1º (prazo em caso de sanção) |
| **Carta-Circular BACEN 4.001/2020** | Lista exemplificativa de operações e situações suspeitas que devem ser comunicadas ao COAF | Item I (structuring), Item III (incompatibilidade renda/patrimônio), Item V (mula/fan-out), Item VII (fraude eletrônica), Item VIII (acesso atípico/VPN), Item IX (ciclo fechado/self-merchant) |
| **Resolução CMN 4.893/2021** | Política de segurança cibernética e requisitos para contratação de serviços de TI por IFs | R15, R16 — dispositivos comprometidos e uso de anonimizadores como risco de segurança cibernética |

### FATF / GAFI (Financial Action Task Force)

| Recomendação | Assunto | Relevância |
|---|---|---|
| **Rec. 3** | Infração de lavagem de dinheiro — abrangência do crime e placement/layering/integration | R01–R03 (structuring), R10–R11 (fan-out) |
| **Rec. 6** | Sanções financeiras direcionadas — terrorismo e financiamento do terrorismo | R06, R07, R20 |
| **Rec. 7** | Sanções financeiras direcionadas — proliferação de armas de destruição em massa | R06, R20 |
| **Rec. 10** | Due diligence de clientes (KYC) — identificação, verificação e monitoramento | R04, R07, R08 |
| **Rec. 12** | Pessoas Politicamente Expostas — enhanced due diligence obrigatória | R05, R18 |
| **Rec. 15** | Novas tecnologias — gestão de risco em ativos virtuais e meios de pagamento digitais | R13, R15, R17 (crypto MCC) |
| **Rec. 16** | Transferências eletrônicas — rastreabilidade e informações de beneficiário/remetente | R08, MCC 4829 (wire transfer) |

### Padrões Internacionais

| Instrumento | Emissor | Relevância |
|---|---|---|
| **OFAC SDN List** (Specially Designated Nationals) | Escritório de Controle de Ativos Estrangeiros — Tesouro dos EUA | R06, R20 — atualizada diariamente; qualquer hit é bloqueio imediato |
| **UNSC Consolidated List** | Conselho de Segurança das Nações Unidas | R06, R07 — Resoluções 1267, 1373, 1718 e subsequentes |
| **PCI-DSS v4.0** | PCI Security Standards Council (Visa/Mastercard/Amex/Discover) | R13, R14 — autenticação 3DS, thresholds de chargeback e responsabilidade do adquirente |

### Notas de Verificação

> As referências acima foram selecionadas com base em conhecimento de treinamento (corte: ago/2025).  
> Antes de uso em produção ou contexto legal, recomenda-se verificar os instrumentos nas fontes primárias:
> - BACEN: [bcb.gov.br/estabilidadefinanceira/normativosconsolidados](https://www.bcb.gov.br/estabilidadefinanceira/normativosconsolidados)
> - COAF: [gov.br/coaf](https://www.gov.br/coaf/pt-br)
> - FATF: [fatf-gafi.org/recommendations](https://www.fatf-gafi.org/en/topics/fatf-recommendations.html)
> - OFAC SDN: [ofac.treas.gov/SDN-list](https://ofac.treas.gov/faqs/topics/specially-designated-nationals-sdn-list)

---

*Documento de referência para CloudWalk AML/FT Technical Challenge.*
