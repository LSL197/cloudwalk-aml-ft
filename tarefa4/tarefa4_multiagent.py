"""
CloudWalk AML/FT — Tarefa 4: Sistema Multi-agente LLM
======================================================
5 agentes especializados cobrindo o ciclo AML completo:

  1. AgenteDADOS        — coleta e estrutura perfil do cliente
  2. AgenteDETECCAO     — avalia flags e ML score, decide se investiga
  3. AgenteINVESTIGACAO — aprofunda evidências, mapeia rede
  4. AgenteSAR          — redige SAR completo em formato COAF
  5. AgenteCOMPLIANCE   — valida, dá score regulatório, aprova/rejeita

Orquestrador passa contexto estruturado (JSON) entre agentes.
Input: customer_id
Output: SAR redigido + decisão de compliance + log completo
"""

import sqlite3
import pandas as pd
import json
import os
import time
from datetime import datetime
from groq import Groq

# ── Config ────────────────────────────────────────────────────────
DB    = '/Users/limaslucas197/Documents/cw-risk-aml-test/aml.db'
OUT   = '/Users/limaslucas197/Documents/cw-risk-aml-test/'
MODEL = 'llama-3.3-70b-versatile'

client = Groq(api_key=os.environ.get('GROQ_API_KEY'))

def q(sql):
    with sqlite3.connect(DB) as c:
        return pd.read_sql(sql, c)

def llm(system: str, user: str, max_tokens: int = 2048) -> str:
    import re
    for attempt in range(8):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {'role': 'system', 'content': system},
                    {'role': 'user',   'content': user},
                ],
                max_tokens=max_tokens,
                temperature=0.2,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            msg = str(e)
            if '429' not in msg:
                raise
            if 'TPD' in msg or 'per day' in msg:
                raise  # daily limit — não adianta retry
            # TPM limit — extrai tempo de espera da mensagem
            m = re.search(r'try again in (\d+)m(\d+(?:\.\d+)?)s', msg)
            if m:
                sleep_s = int(m.group(1)) * 60 + float(m.group(2)) + 2
            else:
                m2 = re.search(r'try again in (\d+(?:\.\d+)?)s', msg)
                sleep_s = float(m2.group(1)) + 2 if m2 else 65
            print(f"  [TPM] aguardando {sleep_s:.0f}s (tentativa {attempt+1}/8)...")
            time.sleep(sleep_s)
    raise Exception("Max retries (8) exceeded")


# ══════════════════════════════════════════════════════════════════
# AGENTE 1 — DADOS
# Coleta todas as informações do cliente no banco
# ══════════════════════════════════════════════════════════════════

class AgenteDados:
    SYSTEM = """Você é um analista de dados de AML/FT especializado em estruturar perfis de clientes.
Sua função é receber dados brutos de transações e KYC e produzir um perfil estruturado e objetivo.
Seja preciso, conciso e foque em dados relevantes para risco AML.
Responda SEMPRE em JSON válido."""

    def run(self, customer_id: str) -> dict:
        # KYC
        kyc = q(f"SELECT * FROM kyc_profiles WHERE customer_id='{customer_id}'")
        # Transações
        txs = q(f"""
            SELECT transaction_id, sender_id, receiver_id, amount_brl,
                   transaction_type, pix_flow, geo_country, timestamp,
                   sanctions_screening_hit, ip_proxy_vpn_tor, device_rooted,
                   cross_border, country_risk_geo, country_risk_receiver,
                   mcc, auth_3ds, capture_method
            FROM transactions
            WHERE sender_id='{customer_id}' OR receiver_id='{customer_id}'
            ORDER BY timestamp
        """)
        # Merchants relacionados
        merchants = q(f"""
            SELECT DISTINCT m.merchant_id, m.mcc, m.mcc_risk,
                   m.merchant_high_risk_flag, m.merchant_chargeback_ratio_90d,
                   m.owner_customer_id
            FROM transactions t JOIN merchants m ON t.receiver_id=m.merchant_id
            WHERE t.sender_id='{customer_id}'
        """)
        # ML score (se existir)
        try:
            ml_df = pd.read_csv(OUT + 'ml_risk_scores.csv')
            ml_row = ml_df[ml_df.customer_id == customer_id]
            ml_data = ml_row.to_dict('records')[0] if len(ml_row) > 0 else {}
        except:
            ml_data = {}

        kyc_rec = kyc.to_dict('records')[0] if len(kyc) > 0 else {}
        # KYC compacto — só campos relevantes
        kyc_compact = {k: kyc_rec.get(k) for k in [
            'customer_id','full_name','annual_income_brl','declared_occupation',
            'risk_rating','pep','sanctions_list_hit','kyc_risk_score','beneficial_owner','country'
        ]}
        txs_float = txs.assign(amount_brl=txs['amount_brl'].astype(float))
        raw_data = {
            'customer_id': customer_id,
            'kyc': kyc_compact,
            'transactions_summary': {
                'total_txs': len(txs),
                'total_volume_brl': round(float(txs_float[txs_float.sender_id==customer_id]['amount_brl'].sum()), 2),
                'max_tx_brl': round(float(txs_float['amount_brl'].max()), 2) if len(txs) > 0 else 0,
                'rails_used': txs['transaction_type'].unique().tolist(),
                'n_sanctions_hits': int((txs['sanctions_screening_hit']=='Yes').sum()),
                'n_vpn_txs': int((txs['ip_proxy_vpn_tor']!='None').sum()),
                'n_crossborder': int((txs['cross_border']=='Yes').sum()),
                'n_struct_txs': int(((txs_float['amount_brl'] >= 9000) & (txs_float['amount_brl'] <= 9999.99)).sum()),
                'date_range': f"{txs['timestamp'].min()} → {txs['timestamp'].max()}" if len(txs) > 0 else 'N/A',
            },
            'top_transactions': txs_float.nlargest(5, 'amount_brl')[
                ['transaction_id','amount_brl','transaction_type','geo_country',
                 'sanctions_screening_hit','ip_proxy_vpn_tor','timestamp']
            ].to_dict('records') if len(txs) > 0 else [],
            'ml_score': {k: ml_data.get(k) for k in [
                'final_score','risk_tier','xgb_prob','iso_score',
                'max_income_ratio','min_geojump_min','n_geojumps'
            ]} if ml_data else {},
        }

        prompt = f"""Analise os dados brutos do cliente abaixo e produza um perfil estruturado em JSON.

DADOS BRUTOS:
{json.dumps(raw_data, indent=2, default=str)}

Produza um JSON com a estrutura:
{{
  "customer_id": "...",
  "perfil_resumido": "2-3 frases descrevendo quem é o cliente e o que chama atenção",
  "kyc_highlights": ["lista de pontos relevantes do KYC"],
  "transacoes_highlights": ["lista de padrões relevantes nas transações"],
  "dados_estruturados": {{dados completos organizados}},
  "nivel_dados": "completo|parcial|insuficiente"
}}"""

        response = llm(self.SYSTEM, prompt, max_tokens=1500)
        try:
            # Extrai JSON da resposta
            start = response.find('{')
            end = response.rfind('}') + 1
            return json.loads(response[start:end])
        except:
            return {'customer_id': customer_id, 'raw_response': response, 'dados_estruturados': raw_data}


# ══════════════════════════════════════════════════════════════════
# AGENTE 2 — DETECÇÃO
# Avalia flags e ML score, decide se o caso merece investigação
# ══════════════════════════════════════════════════════════════════

class AgenteDeteccao:
    SYSTEM = """Você é um sistema especializado em detecção de lavagem de dinheiro e financiamento ao terrorismo (LD/FT).
Sua função é avaliar flags de risco e scores de ML para decidir se um caso merece investigação aprofundada.
Use critérios técnicos baseados em tipologias FATF, regulamentação BACEN e padrões de mercado.
Seja objetivo e fundamente cada decisão em evidências concretas.
Responda SEMPRE em JSON válido."""

    def run(self, perfil: dict) -> dict:
        prompt = f"""Avalie o perfil do cliente abaixo e determine se o caso merece investigação AML aprofundada.

PERFIL DO CLIENTE:
{json.dumps(perfil, indent=2, default=str)}

TIPOLOGIAS A VERIFICAR:
- Structuring/Smurfing: txs repetidas abaixo de R$10k
- Income Ratio: txs incompatíveis com renda declarada
- Geo-jump: transações em países impossíveis no mesmo horário
- Fan-out PIX: recebe de muitos, distribui para muitos
- Sanctions: hits em listas OFAC/UNSC
- VPN/Tor: ocultação de identidade em txs de alto valor
- Self-merchant: ciclo fechado de pagamento
- MCC Alto Risco: gambling, crypto, wire transfer

Produza JSON com:
{{
  "decisao": "INVESTIGAR|MONITORAR|ARQUIVAR",
  "score_deteccao": 0-100,
  "flags_acionadas": [
    {{"flag": "nome", "evidencia": "dado concreto", "peso": "ALTO|MEDIO|BAIXO"}}
  ],
  "tipologias_identificadas": ["lista de tipologias"],
  "justificativa": "parágrafo explicando a decisão",
  "urgencia": "IMEDIATA|ALTA|NORMAL",
  "proximo_passo": "instrução para o agente de investigação"
}}"""

        response = llm(self.SYSTEM, prompt, max_tokens=1500)
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            return json.loads(response[start:end])
        except:
            return {'decisao': 'INVESTIGAR', 'raw_response': response}


# ══════════════════════════════════════════════════════════════════
# AGENTE 3 — INVESTIGAÇÃO
# Aprofunda o caso, mapeia rede, identifica padrão de tipologia
# ══════════════════════════════════════════════════════════════════

class AgenteInvestigacao:
    SYSTEM = """Você é um investigador especializado em crimes financeiros e AML/FT.
Sua função é aprofundar casos suspeitos, mapear redes de relacionamento, identificar a tipologia exata
e construir a narrativa investigativa que suportará um SAR (Suspicious Activity Report).
Siga metodologias FATF e padrões do COAF brasileiro.
Responda SEMPRE em JSON válido."""

    def run(self, perfil: dict, deteccao: dict) -> dict:
        # Busca txs completas do cliente para investigação detalhada
        cid = perfil.get('customer_id', '')
        txs_full = q(f"""
            SELECT t.transaction_id, t.sender_id, t.receiver_id, t.amount_brl,
                   t.transaction_type, t.geo_country, t.timestamp,
                   t.sanctions_screening_hit, t.ip_proxy_vpn_tor,
                   t.cross_border, t.country_risk_geo, t.mcc,
                   k2.declared_occupation AS receiver_occupation,
                   k2.risk_rating AS receiver_risk
            FROM transactions t
            LEFT JOIN kyc_profiles k2 ON t.receiver_id = k2.customer_id
            WHERE t.sender_id='{cid}'
            ORDER BY t.timestamp
        """)

        # Geo-jumps detectados
        geo_jumps = q(f"""
            SELECT a.geo_country c1, b.geo_country c2,
                   a.timestamp ts1, b.timestamp ts2,
                   ROUND((JULIANDAY(b.timestamp)-JULIANDAY(a.timestamp))*60,1) min_diff,
                   a.amount_brl amt1, b.amount_brl amt2
            FROM transactions a JOIN transactions b
              ON a.sender_id=b.sender_id
             AND a.geo_country!=b.geo_country
             AND b.timestamp>a.timestamp
             AND (JULIANDAY(b.timestamp)-JULIANDAY(a.timestamp))*24 < 12
            WHERE a.sender_id='{cid}'
            ORDER BY min_diff ASC
        """)

        investigacao_data = {
            'perfil': perfil,
            'deteccao': deteccao,
            'transacoes_completas': txs_full.head(10).to_dict('records'),  # top 10 evita token overflow
            'geo_jumps_detectados': geo_jumps.to_dict('records'),
        }

        prompt = f"""Conduza uma investigação aprofundada do caso abaixo.

DADOS DA INVESTIGAÇÃO:
{json.dumps(investigacao_data, indent=2, default=str)}

Analise:
1. Linha do tempo completa das transações suspeitas
2. Padrão de comportamento (recorrente? oportunista? sistemático?)
3. Rede de relacionamentos (quem envia/recebe desse cliente?)
4. Tipologia exata segundo FATF/COAF
5. Evidências que sustentam ou refutam a suspeita
6. Lacunas de informação que precisariam ser investigadas

Produza JSON com:
{{
  "tipologia_principal": "nome exato da tipologia FATF",
  "tipologias_secundarias": ["lista"],
  "narrativa_investigativa": "texto completo da investigação (mínimo 300 palavras)",
  "linha_do_tempo": [
    {{"data": "...", "evento": "...", "relevancia": "ALTA|MEDIA|BAIXA"}}
  ],
  "evidencias_fortes": ["lista de evidências concretas"],
  "evidencias_fracas": ["pontos que enfraquecem o caso"],
  "rede_suspeita": {{"nos": [...], "conexoes": [...]}},
  "lacunas_investigativas": ["o que falta apurar"],
  "recomendacao_sar": "EMITIR|NAO_EMITIR|AGUARDAR_MAIS_INFO",
  "fundamentacao_legal": ["artigos de lei aplicáveis"]
}}"""

        response = llm(self.SYSTEM, prompt, max_tokens=3000)
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            return json.loads(response[start:end])
        except:
            return {'tipologia_principal': 'Indeterminada', 'raw_response': response}


# ══════════════════════════════════════════════════════════════════
# AGENTE 4 — SAR
# Redige o Suspicious Activity Report em formato COAF
# ══════════════════════════════════════════════════════════════════

class AgenteSAR:
    SYSTEM = """Você é um especialista em compliance AML/FT e redação de Relatórios de Atividade Suspeita (SAR/RAS).
Sua função é redigir SARs completos no formato exigido pelo COAF (Conselho de Controle de Atividades Financeiras),
baseado em evidências investigativas concretas.
O SAR deve ser preciso, juridicamente fundamentado e seguir o padrão da Resolução COAF 36/2021.
Não invente fatos — baseie-se apenas nas evidências fornecidas.
Responda com o SAR completo em JSON."""

    def run(self, perfil: dict, deteccao: dict, investigacao: dict) -> dict:
        prompt = f"""Redija um SAR (Suspicious Activity Report / Relatório de Atividade Suspeita) completo
para submissão ao COAF, com base nas evidências investigativas abaixo.

PERFIL DO CLIENTE:
{json.dumps(perfil, indent=2, default=str)}

DETECÇÃO:
{json.dumps(deteccao, indent=2, default=str)}

INVESTIGAÇÃO:
{json.dumps(investigacao, indent=2, default=str)}

Produza JSON com a estrutura do SAR:
{{
  "sar_numero": "SAR-{datetime.now().strftime('%Y-%m')}-AUTO",
  "data_emissao": "{datetime.now().strftime('%Y-%m-%d')}",
  "classificacao": "CONFIDENCIAL",
  "secao_1_identificacao": {{
    "sujeito_obrigado": "CloudWalk Payments",
    "cnpj_sujeito": "09.173.490/0001-50",
    "responsavel_compliance": "Departamento AML/FT",
    "cliente_id": "...",
    "nome_cliente": "...",
    "cpf_cnpj": "...",
    "ocupacao": "...",
    "renda_declarada": "..."
  }},
  "secao_2_resumo_executivo": "parágrafo conciso de 100-150 palavras",
  "secao_3_descricao_operacoes": {{
    "periodo": "...",
    "volume_total": "...",
    "numero_operacoes": "...",
    "operacoes_criticas": [
      {{"id": "...", "data": "...", "valor": "...", "descricao": "...", "red_flag": "..."}}
    ]
  }},
  "secao_4_tipologia": {{
    "tipologia_principal": "...",
    "descricao_tipologia": "...",
    "fase_ld": "Placement|Layering|Integration",
    "base_fatf": "FATF Recomendação X"
  }},
  "secao_5_fundamentacao_legal": [
    {{"norma": "...", "artigo": "...", "aplicacao": "..."}}
  ],
  "secao_6_evidencias": {{
    "evidencias_objetivas": ["lista"],
    "documentos_anexos": ["lista do que deveria ser anexado"],
    "lacunas": ["o que falta apurar"]
  }},
  "secao_7_medidas_tomadas": ["lista de ações já tomadas ou recomendadas"],
  "secao_8_conclusao": "parágrafo final com recomendação clara",
  "grau_certeza": "ALTO|MEDIO|BAIXO",
  "prazo_comunicacao_coaf": "24h|72h|30 dias"
}}"""

        response = llm(self.SYSTEM, prompt, max_tokens=3000)
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            return json.loads(response[start:end])
        except:
            return {'sar_numero': 'ERRO-PARSE', 'raw_response': response}


# ══════════════════════════════════════════════════════════════════
# AGENTE 5 — COMPLIANCE
# Valida o SAR, dá score regulatório, aprova ou rejeita
# ══════════════════════════════════════════════════════════════════

class AgenteCompliance:
    SYSTEM = """Você é o Chief Compliance Officer de uma fintech, especialista em regulamentação AML/FT brasileira.
Sua função é revisar SARs produzidos pela equipe de investigação, validar a fundamentação legal,
identificar falhas ou lacunas, e dar a decisão final de aprovação para submissão ao COAF.
Seja rigoroso — um SAR mal fundamentado pode gerar problemas regulatórios.
Responda SEMPRE em JSON válido."""

    def run(self, sar: dict, investigacao: dict) -> dict:
        prompt = f"""Revise o SAR abaixo e dê sua avaliação de compliance.

SAR PARA REVISÃO:
{json.dumps(sar, indent=2, default=str)}

INVESTIGAÇÃO BASE:
{json.dumps(investigacao, indent=2, default=str)}

Avalie:
1. Suficiência das evidências
2. Correção da fundamentação legal
3. Completude do SAR (seções obrigatórias COAF)
4. Proporcionalidade (o caso justifica o SAR?)
5. Riscos regulatórios de submeter ou não submeter

Produza JSON com:
{{
  "decisao_final": "APROVADO|APROVADO_COM_RESSALVAS|REPROVADO|AGUARDAR",
  "score_compliance": 0-100,
  "avaliacao_evidencias": "SUFICIENTE|INSUFICIENTE|PARCIAL",
  "pontos_fortes": ["lista"],
  "pontos_fracos": ["lista"],
  "ressalvas": ["lista de ajustes necessários antes de submeter"],
  "risco_nao_reportar": "ALTO|MEDIO|BAIXO",
  "risco_reportar_sem_base": "ALTO|MEDIO|BAIXO",
  "prazo_acao": "24h|72h|7 dias|30 dias",
  "instrucoes_finais": "parágrafo com orientações claras para a equipe",
  "checklist_coaf": {{
    "identificacao_completa": true/false,
    "descricao_operacoes": true/false,
    "tipologia_identificada": true/false,
    "fundamentacao_legal": true/false,
    "medidas_tomadas": true/false,
    "prazo_comunicacao": true/false
  }}
}}"""

        response = llm(self.SYSTEM, prompt, max_tokens=2000)
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            return json.loads(response[start:end])
        except:
            return {'decisao_final': 'AGUARDAR', 'raw_response': response}


# ══════════════════════════════════════════════════════════════════
# ORQUESTRADOR
# ══════════════════════════════════════════════════════════════════

class OrchestratorAML:

    def __init__(self):
        self.dados       = AgenteDados()
        self.deteccao    = AgenteDeteccao()
        self.investigacao = AgenteInvestigacao()
        self.sar         = AgenteSAR()
        self.compliance  = AgenteCompliance()

    def run(self, customer_id: str, verbose: bool = True) -> dict:
        log = []
        inicio = datetime.now()

        def step(nome, fn, *args):
            if verbose:
                print(f"\n  [{nome}] iniciando...")
            t0 = time.time()
            result = fn(*args)
            elapsed = time.time() - t0
            if verbose:
                decisao = result.get('decisao') or result.get('decisao_final') or result.get('nivel_dados', '...')
                print(f"  [{nome}] concluído em {elapsed:.1f}s → {decisao}")
            log.append({'agente': nome, 'elapsed_s': round(elapsed, 1), 'keys': list(result.keys())})
            return result

        print(f"\n{'='*65}")
        print(f"  PIPELINE AML — Cliente: {customer_id}")
        print(f"  Início: {inicio.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*65}")

        # Executa pipeline
        perfil       = step('DADOS',        self.dados.run,       customer_id)
        detec        = step('DETECCAO',     self.deteccao.run,    perfil)
        invest       = step('INVESTIGACAO', self.investigacao.run, perfil, detec)
        sar_doc      = step('SAR',          self.sar.run,         perfil, detec, invest)
        compliance   = step('COMPLIANCE',   self.compliance.run,  sar_doc, invest)

        fim = datetime.now()
        total = (fim - inicio).total_seconds()

        resultado = {
            'customer_id':    customer_id,
            'timestamp':      inicio.isoformat(),
            'total_segundos': round(total, 1),
            'pipeline_log':   log,
            'perfil':         perfil,
            'deteccao':       detec,
            'investigacao':   invest,
            'sar':            sar_doc,
            'compliance':     compliance,
        }

        # Salva JSON completo
        out_path = f"{OUT}aml_case_{customer_id}.json"
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2, default=str)

        # Resumo final
        print(f"\n{'='*65}")
        print(f"  RESULTADO FINAL")
        print(f"{'='*65}")
        print(f"  Cliente:          {customer_id}")
        print(f"  Detecção:         {detec.get('decisao','?')} (score {detec.get('score_deteccao','?')})")
        print(f"  SAR nº:           {sar_doc.get('sar_numero','?')}")
        print(f"  Compliance:       {compliance.get('decisao_final','?')} (score {compliance.get('score_compliance','?')})")
        print(f"  Grau de certeza:  {sar_doc.get('grau_certeza','?')}")
        print(f"  Prazo COAF:       {compliance.get('prazo_acao','?')}")
        print(f"  Tempo total:      {total:.1f}s")
        print(f"  Output salvo:     aml_case_{customer_id}.json")
        print(f"{'='*65}")

        return resultado


# ══════════════════════════════════════════════════════════════════
# MAIN — roda para os casos mais críticos do dataset
# ══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    orchestrator = OrchestratorAML()

    # Casos prioritários: sanctions hit + geo-jump crítico + PEP+KYC high
    casos = [
        'C101048',   # Mechanic: PEP + 5 geo-jumps + income_ratio 22x
        'C100932',   # Nurse: risk_score 10 (max) + 31 alertas HIGH
    ]

    resultados = []
    for cid in casos:
        try:
            r = orchestrator.run(cid, verbose=True)
            resultados.append({
                'customer_id':   cid,
                'decisao':       r['deteccao'].get('decisao'),
                'sar':           r['sar'].get('sar_numero'),
                'compliance':    r['compliance'].get('decisao_final'),
                'score':         r['compliance'].get('score_compliance'),
            })
            time.sleep(2)  # rate limit
        except Exception as e:
            print(f"\n  ERRO em {cid}: {e}")
            resultados.append({'customer_id': cid, 'erro': str(e)})

    print("\n\n" + "="*65)
    print("  SUMÁRIO — TODOS OS CASOS")
    print("="*65)
    for r in resultados:
        print(f"  {r.get('customer_id')}: detecção={r.get('decisao')} | "
              f"compliance={r.get('compliance')} | score={r.get('score')}")
    print("="*65)
