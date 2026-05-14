"""
CloudWalk AML/FT — Tarefa 2: Sistema de Alertas
================================================
20 regras cobrindo 8 tipologias. Cada regra retorna um DataFrame
de alertas com colunas padronizadas:

  alert_id | rule_id | rule_name | customer_id | transaction_id | amount_brl
  | severity | evidence | timestamp

Severidade: HIGH / MEDIUM / LOW
"""

import sqlite3
import pandas as pd
import hashlib
from datetime import datetime

warnings_disabled = True
import warnings; warnings.filterwarnings('ignore')

DB = '/Users/limaslucas197/Documents/cw-risk-aml-test/aml.db'

pd.set_option('display.max_columns', None)
pd.set_option('display.max_colwidth', 80)
pd.set_option('display.float_format', '{:.2f}'.format)

def q(sql: str) -> pd.DataFrame:
    with sqlite3.connect(DB) as conn:
        return pd.read_sql(sql, conn)


def make_alert_id(rule_id: str, key: str) -> str:
    h = hashlib.md5(f"{rule_id}:{key}".encode()).hexdigest()[:8].upper()
    return f"ALT-{rule_id}-{h}"


# ══════════════════════════════════════════════════════════════════
# TIPOLOGIA 1 — STRUCTURING / SMURFING
# ══════════════════════════════════════════════════════════════════

def rule_01_structuring_pix():
    """R01 — PIX Structuring: ≥3 txs R$9k–R$9.999 por cliente (HIGH)"""
    df = q("""
        SELECT sender_id, COUNT(*) n_txs,
               ROUND(SUM(CAST(amount_brl AS REAL)),2) total_brl,
               MIN(timestamp) primeira, MAX(timestamp) ultima
        FROM transactions
        WHERE CAST(amount_brl AS REAL) BETWEEN 9000 AND 9999.99
          AND transaction_type = 'PIX'
        GROUP BY sender_id HAVING n_txs >= 3
        ORDER BY n_txs DESC
    """)
    alerts = []
    for _, r in df.iterrows():
        alerts.append({
            'alert_id': make_alert_id('R01', r.sender_id),
            'rule_id': 'R01', 'rule_name': 'PIX Structuring ≥3 txs R$9k-9.999',
            'customer_id': r.sender_id, 'transaction_id': None,
            'amount_brl': r.total_brl, 'severity': 'HIGH',
            'evidence': f"{r.n_txs} txs PIX R$9k-9.999, total R${r.total_brl:,.0f}, {r.primeira}→{r.ultima}",
            'timestamp': r.ultima
        })
    return pd.DataFrame(alerts)


def rule_02_structuring_card():
    """R02 — Card Structuring: ≥3 txs R$9k–R$9.999 no cartão (HIGH)"""
    df = q("""
        SELECT sender_id, COUNT(*) n_txs,
               ROUND(SUM(CAST(amount_brl AS REAL)),2) total_brl,
               MIN(timestamp) primeira, MAX(timestamp) ultima
        FROM transactions
        WHERE CAST(amount_brl AS REAL) BETWEEN 9000 AND 9999.99
          AND transaction_type = 'Card'
        GROUP BY sender_id HAVING n_txs >= 3
        ORDER BY n_txs DESC
    """)
    alerts = []
    for _, r in df.iterrows():
        alerts.append({
            'alert_id': make_alert_id('R02', r.sender_id),
            'rule_id': 'R02', 'rule_name': 'Card Structuring ≥3 txs R$9k-9.999',
            'customer_id': r.sender_id, 'transaction_id': None,
            'amount_brl': r.total_brl, 'severity': 'HIGH',
            'evidence': f"{r.n_txs} card txs R$9k-9.999, total R${r.total_brl:,.0f}",
            'timestamp': r.ultima
        })
    return pd.DataFrame(alerts)


def rule_03_rapid_structuring():
    """R03 — Rapid Structuring: ≥2 txs R$9k+ dentro de 24h (HIGH)"""
    df = q("""
        SELECT sender_id, COUNT(*) n_txs,
               ROUND(SUM(CAST(amount_brl AS REAL)),2) total_brl,
               MIN(timestamp) primeira, MAX(timestamp) ultima,
               ROUND((JULIANDAY(MAX(timestamp)) - JULIANDAY(MIN(timestamp)))*24,1) hours_span
        FROM transactions
        WHERE CAST(amount_brl AS REAL) BETWEEN 9000 AND 9999.99
        GROUP BY sender_id, DATE(timestamp)
        HAVING n_txs >= 2 AND hours_span <= 24
        ORDER BY n_txs DESC
    """)
    alerts = []
    for _, r in df.iterrows():
        alerts.append({
            'alert_id': make_alert_id('R03', f"{r.sender_id}{r.primeira}"),
            'rule_id': 'R03', 'rule_name': 'Rapid Structuring ≥2 txs R$9k+ em 24h',
            'customer_id': r.sender_id, 'transaction_id': None,
            'amount_brl': r.total_brl, 'severity': 'HIGH',
            'evidence': f"{r.n_txs} txs R$9k+ em {r.hours_span}h, total R${r.total_brl:,.0f}",
            'timestamp': r.ultima
        })
    return pd.DataFrame(alerts)


# ══════════════════════════════════════════════════════════════════
# TIPOLOGIA 2 — INCOME RATIO INCOMPATÍVEL
# ══════════════════════════════════════════════════════════════════

def rule_04_income_ratio_15x():
    """R04 — Tx > 15x renda mensal (HIGH)"""
    df = q("""
        SELECT t.transaction_id, t.sender_id, t.amount_brl,
               t.transaction_type, t.timestamp,
               k.declared_occupation, k.annual_income_brl,
               ROUND(CAST(k.annual_income_brl AS REAL)/12,2) monthly,
               ROUND(CAST(t.amount_brl AS REAL)/(CAST(k.annual_income_brl AS REAL)/12),1) ratio_x
        FROM transactions t
        JOIN kyc_profiles k ON t.sender_id = k.customer_id
        WHERE CAST(k.annual_income_brl AS REAL) > 0
          AND CAST(t.amount_brl AS REAL) > 15*(CAST(k.annual_income_brl AS REAL)/12)
        ORDER BY ratio_x DESC
    """)
    alerts = []
    for _, r in df.iterrows():
        alerts.append({
            'alert_id': make_alert_id('R04', r.transaction_id),
            'rule_id': 'R04', 'rule_name': 'Income Ratio >15x renda mensal',
            'customer_id': r.sender_id, 'transaction_id': r.transaction_id,
            'amount_brl': float(r.amount_brl), 'severity': 'HIGH',
            'evidence': f"Tx R${float(r.amount_brl):,.0f} = {r.ratio_x}x renda mensal R${r.monthly:,.0f} ({r.declared_occupation})",
            'timestamp': r.timestamp
        })
    return pd.DataFrame(alerts)


def rule_05_income_ratio_5x_pep():
    """R05 — PEP com tx > 5x renda mensal (HIGH)"""
    df = q("""
        SELECT t.transaction_id, t.sender_id, t.amount_brl, t.timestamp,
               k.declared_occupation, k.annual_income_brl,
               ROUND(CAST(k.annual_income_brl AS REAL)/12,2) monthly,
               ROUND(CAST(t.amount_brl AS REAL)/(CAST(k.annual_income_brl AS REAL)/12),1) ratio_x
        FROM transactions t
        JOIN kyc_profiles k ON t.sender_id = k.customer_id
        WHERE k.pep = 'Yes'
          AND CAST(k.annual_income_brl AS REAL) > 0
          AND CAST(t.amount_brl AS REAL) > 5*(CAST(k.annual_income_brl AS REAL)/12)
        ORDER BY ratio_x DESC
    """)
    alerts = []
    for _, r in df.iterrows():
        alerts.append({
            'alert_id': make_alert_id('R05', r.transaction_id),
            'rule_id': 'R05', 'rule_name': 'PEP Income Ratio >5x renda mensal',
            'customer_id': r.sender_id, 'transaction_id': r.transaction_id,
            'amount_brl': float(r.amount_brl), 'severity': 'HIGH',
            'evidence': f"PEP: Tx R${float(r.amount_brl):,.0f} = {r.ratio_x}x renda (R${r.monthly:,.0f}/mês)",
            'timestamp': r.timestamp
        })
    return pd.DataFrame(alerts)


# ══════════════════════════════════════════════════════════════════
# TIPOLOGIA 3 — SANÇÕES E GEOPOLÍTICA
# ══════════════════════════════════════════════════════════════════

def rule_06_sanctions_hit():
    """R06 — sanctions_screening_hit=Yes em qualquer tx (HIGH)"""
    df = q("""
        SELECT transaction_id, sender_id, amount_brl, transaction_type,
               geo_country, country_risk_geo, timestamp
        FROM transactions
        WHERE sanctions_screening_hit = 'Yes'
        ORDER BY CAST(amount_brl AS REAL) DESC
    """)
    alerts = []
    for _, r in df.iterrows():
        alerts.append({
            'alert_id': make_alert_id('R06', r.transaction_id),
            'rule_id': 'R06', 'rule_name': 'Sanctions Screening Hit',
            'customer_id': r.sender_id, 'transaction_id': r.transaction_id,
            'amount_brl': float(r.amount_brl), 'severity': 'HIGH',
            'evidence': f"OFAC/UNSC hit: {r.geo_country}, R${float(r.amount_brl):,.0f}, tipo={r.transaction_type}",
            'timestamp': r.timestamp
        })
    return pd.DataFrame(alerts)


def rule_07_kyc_sanctions_list():
    """R07 — Cliente com sanctions_list_hit=Yes no KYC (HIGH)"""
    df = q("""
        SELECT k.customer_id, k.full_name, k.country, k.risk_rating,
               k.pep, k.sanctions_list_hit
        FROM kyc_profiles k
        WHERE k.sanctions_list_hit = 'Yes'
    """)
    alerts = []
    for _, r in df.iterrows():
        alerts.append({
            'alert_id': make_alert_id('R07', r.customer_id),
            'rule_id': 'R07', 'rule_name': 'KYC Sanctions List Hit',
            'customer_id': r.customer_id, 'transaction_id': None,
            'amount_brl': None, 'severity': 'HIGH',
            'evidence': f"KYC hit lista sanções: {r.full_name}, país={r.country}, PEP={r.pep}",
            'timestamp': None
        })
    return pd.DataFrame(alerts)


def rule_08_high_risk_country_crossborder():
    """R08 — Cross-border p/ país Alto Risco (MEDIUM)"""
    df = q("""
        SELECT transaction_id, sender_id, amount_brl, transaction_type,
               geo_country, country_risk_geo, country_risk_receiver, timestamp
        FROM transactions
        WHERE cross_border = 'Yes'
          AND (country_risk_geo = 'High' OR country_risk_receiver = 'High')
        ORDER BY CAST(amount_brl AS REAL) DESC
    """)
    alerts = []
    for _, r in df.iterrows():
        sev = 'HIGH' if r.country_risk_geo == 'High' and r.country_risk_receiver == 'High' else 'MEDIUM'
        alerts.append({
            'alert_id': make_alert_id('R08', r.transaction_id),
            'rule_id': 'R08', 'rule_name': 'Cross-border País Alto Risco',
            'customer_id': r.sender_id, 'transaction_id': r.transaction_id,
            'amount_brl': float(r.amount_brl), 'severity': sev,
            'evidence': f"XBorder: origem={r.geo_country} ({r.country_risk_geo}), destino risco={r.country_risk_receiver}",
            'timestamp': r.timestamp
        })
    return pd.DataFrame(alerts)


# ══════════════════════════════════════════════════════════════════
# TIPOLOGIA 4 — GEO-JUMP / VIAGEM IMPOSSÍVEL
# ══════════════════════════════════════════════════════════════════

def rule_09_geo_jump():
    """R09 — Geo-jump: mesmo sender em países diferentes em <12h (HIGH)"""
    df = q("""
        SELECT a.sender_id,
               a.transaction_id tx1, a.geo_country country1, a.timestamp ts1,
               b.transaction_id tx2, b.geo_country country2, b.timestamp ts2,
               ROUND((JULIANDAY(b.timestamp)-JULIANDAY(a.timestamp))*24,2) hours_diff,
               a.amount_brl amount1, b.amount_brl amount2
        FROM transactions a
        JOIN transactions b
          ON a.sender_id = b.sender_id
         AND a.geo_country != b.geo_country
         AND b.timestamp > a.timestamp
         AND (JULIANDAY(b.timestamp)-JULIANDAY(a.timestamp))*24 < 12
        ORDER BY hours_diff ASC
    """)
    alerts = []
    for _, r in df.iterrows():
        alerts.append({
            'alert_id': make_alert_id('R09', f"{r.tx1}{r.tx2}"),
            'rule_id': 'R09', 'rule_name': 'Geo-jump Viagem Impossível <12h',
            'customer_id': r.sender_id, 'transaction_id': r.tx1,
            'amount_brl': float(r.amount1), 'severity': 'HIGH',
            'evidence': f"{r.country1}→{r.country2} em {r.hours_diff}h ({r.ts1}→{r.ts2})",
            'timestamp': r.ts1
        })
    return pd.DataFrame(alerts)


# ══════════════════════════════════════════════════════════════════
# TIPOLOGIA 5 — CASH FAN-OUT / MULA
# ══════════════════════════════════════════════════════════════════

def rule_10_cash_fanout():
    """R10 — PIX fan-out: vol_out/vol_in > 10x e ≥3 txs cada (HIGH)"""
    df = q("""
        WITH ci AS (
          SELECT receiver_id customer_id, COUNT(*) n_in, SUM(CAST(amount_brl AS REAL)) vol_in
          FROM transactions WHERE pix_flow='cash_in' AND transaction_type='PIX'
          GROUP BY receiver_id
        ),
        co AS (
          SELECT sender_id customer_id, COUNT(*) n_out, SUM(CAST(amount_brl AS REAL)) vol_out
          FROM transactions WHERE pix_flow='cash_out' AND transaction_type='PIX'
          GROUP BY sender_id
        )
        SELECT ci.customer_id, ci.n_in, co.n_out,
               ROUND(ci.vol_in,2) vol_in_brl, ROUND(co.vol_out,2) vol_out_brl,
               ROUND(co.vol_out/ci.vol_in,2) passthrough_ratio
        FROM ci JOIN co ON ci.customer_id=co.customer_id
        WHERE ci.n_in >= 3 AND co.n_out >= 3
          AND co.vol_out/ci.vol_in > 10
        ORDER BY passthrough_ratio DESC
    """)
    alerts = []
    for _, r in df.iterrows():
        alerts.append({
            'alert_id': make_alert_id('R10', r.customer_id),
            'rule_id': 'R10', 'rule_name': 'Cash Fan-out PIX Ratio >10x',
            'customer_id': r.customer_id, 'transaction_id': None,
            'amount_brl': r.vol_out_brl, 'severity': 'HIGH',
            'evidence': f"vol_out/vol_in={r.passthrough_ratio}x ({r.n_in} in, {r.n_out} out), R${r.vol_out_brl:,.0f} saída",
            'timestamp': None
        })
    return pd.DataFrame(alerts)


def rule_11_rapid_redistribution():
    """R11 — Recebe PIX e redistribui >80% em <48h (MEDIUM)"""
    df = q("""
        WITH inflow AS (
          SELECT receiver_id customer_id, DATE(timestamp) dt,
                 SUM(CAST(amount_brl AS REAL)) vol_in
          FROM transactions WHERE pix_flow='cash_in' AND transaction_type='PIX'
          GROUP BY receiver_id, DATE(timestamp)
        ),
        outflow AS (
          SELECT sender_id customer_id, DATE(timestamp) dt,
                 SUM(CAST(amount_brl AS REAL)) vol_out
          FROM transactions WHERE pix_flow='cash_out' AND transaction_type='PIX'
          GROUP BY sender_id, DATE(timestamp)
        )
        SELECT i.customer_id, i.dt,
               ROUND(i.vol_in,2) vol_in, ROUND(o.vol_out,2) vol_out,
               ROUND(o.vol_out/i.vol_in*100,1) pct_redistributed
        FROM inflow i
        JOIN outflow o ON i.customer_id=o.customer_id
          AND (o.dt=i.dt OR o.dt=DATE(i.dt,'+1 day') OR o.dt=DATE(i.dt,'+2 days'))
        WHERE o.vol_out/i.vol_in > 0.8 AND i.vol_in > 5000
        ORDER BY pct_redistributed DESC
    """)
    alerts = []
    for _, r in df.iterrows():
        dt_str = str(r['dt'])
        alerts.append({
            'alert_id': make_alert_id('R11', f"{r['customer_id']}{dt_str}"),
            'rule_id': 'R11', 'rule_name': 'Rapid Redistribution >80% em 48h',
            'customer_id': r['customer_id'], 'transaction_id': None,
            'amount_brl': r['vol_out'], 'severity': 'MEDIUM',
            'evidence': f"Recebeu R${r['vol_in']:,.0f} e redistribuiu {r['pct_redistributed']}% em até 48h ({dt_str})",
            'timestamp': dt_str
        })
    return pd.DataFrame(alerts)


# ══════════════════════════════════════════════════════════════════
# TIPOLOGIA 6 — SELF-MERCHANT / CICLO FECHADO
# ══════════════════════════════════════════════════════════════════

def rule_12_self_merchant():
    """R12 — Sender = dono do merchant receptor (HIGH)"""
    df = q("""
        SELECT t.sender_id, t.receiver_id, t.transaction_id, t.amount_brl,
               t.transaction_type, t.timestamp, m.mcc, m.mcc_risk,
               m.merchant_high_risk_flag, m.merchant_chargeback_ratio_90d
        FROM transactions t
        JOIN merchants m ON t.receiver_id = m.merchant_id
        WHERE t.sender_id = m.owner_customer_id
        ORDER BY CAST(t.amount_brl AS REAL) DESC
    """)
    alerts = []
    for _, r in df.iterrows():
        sev = 'HIGH' if r.merchant_high_risk_flag == 'Yes' else 'MEDIUM'
        alerts.append({
            'alert_id': make_alert_id('R12', r.transaction_id),
            'rule_id': 'R12', 'rule_name': 'Self-Merchant Ciclo Fechado',
            'customer_id': r.sender_id, 'transaction_id': r.transaction_id,
            'amount_brl': float(r.amount_brl), 'severity': sev,
            'evidence': f"Sender={r.sender_id} é dono de {r.receiver_id}, MCC={r.mcc} (risco={r.mcc_risk}), alto_risco={r.merchant_high_risk_flag}",
            'timestamp': r.timestamp
        })
    return pd.DataFrame(alerts)


# ══════════════════════════════════════════════════════════════════
# TIPOLOGIA 7 — FRAUDE / E-COMMERCE SEM 3DS
# ══════════════════════════════════════════════════════════════════

def rule_13_ecommerce_no_3ds():
    """R13 — E-commerce sem 3DS + valor > R$5k (MEDIUM)"""
    df = q("""
        SELECT transaction_id, sender_id, amount_brl, auth_3ds, eci,
               capture_method, cross_border, mcc, timestamp
        FROM transactions
        WHERE transaction_type='Card' AND capture_method='E-commerce'
          AND (auth_3ds='No' OR eci='07')
          AND CAST(amount_brl AS REAL) > 5000
        ORDER BY CAST(amount_brl AS REAL) DESC
    """)
    alerts = []
    for _, r in df.iterrows():
        alerts.append({
            'alert_id': make_alert_id('R13', r.transaction_id),
            'rule_id': 'R13', 'rule_name': 'E-commerce sem 3DS alto valor >R$5k',
            'customer_id': r.sender_id, 'transaction_id': r.transaction_id,
            'amount_brl': float(r.amount_brl), 'severity': 'MEDIUM',
            'evidence': f"E-comm s/3DS: R${float(r.amount_brl):,.0f}, ECI={r.eci}, XBorder={r.cross_border}, MCC={r.mcc}",
            'timestamp': r.timestamp
        })
    return pd.DataFrame(alerts)


def rule_14_high_chargeback_merchant():
    """R14 — Merchant com chargeback_ratio > 2% recebendo txs (MEDIUM)"""
    df = q("""
        SELECT t.transaction_id, t.sender_id, t.receiver_id, t.amount_brl,
               t.transaction_type, t.timestamp,
               m.merchant_chargeback_ratio_90d, m.mcc, m.mcc_risk
        FROM transactions t
        JOIN merchants m ON t.receiver_id = m.merchant_id
        WHERE CAST(m.merchant_chargeback_ratio_90d AS REAL) > 0.02
        ORDER BY CAST(m.merchant_chargeback_ratio_90d AS REAL) DESC
    """)
    alerts = []
    for _, r in df.iterrows():
        alerts.append({
            'alert_id': make_alert_id('R14', r.transaction_id),
            'rule_id': 'R14', 'rule_name': 'Merchant Alto Chargeback >2% (90d)',
            'customer_id': r.sender_id, 'transaction_id': r.transaction_id,
            'amount_brl': float(r.amount_brl), 'severity': 'MEDIUM',
            'evidence': f"Merchant {r.receiver_id}: chargeback={float(r.merchant_chargeback_ratio_90d)*100:.1f}%, MCC={r.mcc} ({r.mcc_risk})",
            'timestamp': r.timestamp
        })
    return pd.DataFrame(alerts)


# ══════════════════════════════════════════════════════════════════
# TIPOLOGIA 8 — DEVICE / ACESSO SUSPEITO
# ══════════════════════════════════════════════════════════════════

def rule_15_vpn_tor_high_value():
    """R15 — VPN/Proxy/Tor + valor > R$10k (HIGH)"""
    df = q("""
        SELECT t.transaction_id, t.sender_id, t.amount_brl, t.ip_proxy_vpn_tor,
               t.transaction_type, t.cross_border, k.pep, k.risk_rating, t.timestamp
        FROM transactions t
        JOIN kyc_profiles k ON t.sender_id=k.customer_id
        WHERE t.ip_proxy_vpn_tor != 'None'
          AND CAST(t.amount_brl AS REAL) > 10000
        ORDER BY CAST(t.amount_brl AS REAL) DESC
    """)
    alerts = []
    for _, r in df.iterrows():
        sev = 'HIGH' if r.pep == 'Yes' or r.cross_border == 'Yes' else 'MEDIUM'
        alerts.append({
            'alert_id': make_alert_id('R15', r.transaction_id),
            'rule_id': 'R15', 'rule_name': 'VPN/Tor Alto Valor >R$10k',
            'customer_id': r.sender_id, 'transaction_id': r.transaction_id,
            'amount_brl': float(r.amount_brl), 'severity': sev,
            'evidence': f"IP={r.ip_proxy_vpn_tor}, R${float(r.amount_brl):,.0f}, PEP={r.pep}, XBorder={r.cross_border}",
            'timestamp': r.timestamp
        })
    return pd.DataFrame(alerts)


def rule_16_rooted_device_high_value():
    """R16 — Dispositivo rooted/jailbroken + valor > R$5k (MEDIUM)"""
    df = q("""
        SELECT transaction_id, sender_id, amount_brl, device_rooted,
               transaction_type, timestamp
        FROM transactions
        WHERE device_rooted = 'Yes'
          AND CAST(amount_brl AS REAL) > 5000
        ORDER BY CAST(amount_brl AS REAL) DESC
    """)
    alerts = []
    for _, r in df.iterrows():
        alerts.append({
            'alert_id': make_alert_id('R16', r.transaction_id),
            'rule_id': 'R16', 'rule_name': 'Dispositivo Rooted Alto Valor >R$5k',
            'customer_id': r.sender_id, 'transaction_id': r.transaction_id,
            'amount_brl': float(r.amount_brl), 'severity': 'MEDIUM',
            'evidence': f"Device rooted/jailbroken: R${float(r.amount_brl):,.0f}, tipo={r.transaction_type}",
            'timestamp': r.timestamp
        })
    return pd.DataFrame(alerts)


def rule_17_mcc_risk_cumulative():
    """R17 — ≥3 txs em MCCs alto risco (6011/6051/7995/4829/6538) (MEDIUM)"""
    df = q("""
        SELECT t.sender_id, k.declared_occupation, k.annual_income_brl,
               COUNT(*) n_txs,
               GROUP_CONCAT(DISTINCT CAST(t.mcc AS TEXT)) mccs,
               ROUND(SUM(CAST(t.amount_brl AS REAL)),2) total_brl
        FROM transactions t
        JOIN kyc_profiles k ON t.sender_id=k.customer_id
        WHERE CAST(t.mcc AS INTEGER) IN (6011,6051,7995,4829,6538)
        GROUP BY t.sender_id HAVING n_txs >= 3
        ORDER BY total_brl DESC
    """)
    alerts = []
    for _, r in df.iterrows():
        alerts.append({
            'alert_id': make_alert_id('R17', r.sender_id),
            'rule_id': 'R17', 'rule_name': 'MCC Alto Risco Acumulado ≥3 txs',
            'customer_id': r.sender_id, 'transaction_id': None,
            'amount_brl': r.total_brl, 'severity': 'MEDIUM',
            'evidence': f"{r.n_txs} txs MCC alto risco ({r.mccs}), total R${r.total_brl:,.0f}, ocup={r.declared_occupation}",
            'timestamp': None
        })
    return pd.DataFrame(alerts)


def rule_18_pep_high_volume():
    """R18 — PEP com volume total > R$100k (HIGH)"""
    df = q("""
        SELECT t.sender_id, k.declared_occupation, k.annual_income_brl,
               COUNT(*) n_txs,
               ROUND(SUM(CAST(t.amount_brl AS REAL)),2) total_brl,
               ROUND(MAX(CAST(t.amount_brl AS REAL)),2) max_tx
        FROM transactions t
        JOIN kyc_profiles k ON t.sender_id=k.customer_id
        WHERE k.pep='Yes'
        GROUP BY t.sender_id
        HAVING total_brl > 100000
        ORDER BY total_brl DESC
    """)
    alerts = []
    for _, r in df.iterrows():
        alerts.append({
            'alert_id': make_alert_id('R18', r.sender_id),
            'rule_id': 'R18', 'rule_name': 'PEP Volume Total >R$100k',
            'customer_id': r.sender_id, 'transaction_id': None,
            'amount_brl': r.total_brl, 'severity': 'HIGH',
            'evidence': f"PEP: {r.n_txs} txs, total R${r.total_brl:,.0f}, maior tx R${r.max_tx:,.0f}, ocup={r.declared_occupation}",
            'timestamp': None
        })
    return pd.DataFrame(alerts)


def rule_19_velocity_spike():
    """R19 — Velocidade: >10 txs no mesmo dia (MEDIUM)"""
    df = q("""
        SELECT sender_id, DATE(timestamp) dt, COUNT(*) n_txs,
               ROUND(SUM(CAST(amount_brl AS REAL)),2) total_brl,
               MIN(timestamp) primeira, MAX(timestamp) ultima
        FROM transactions
        GROUP BY sender_id, DATE(timestamp)
        HAVING n_txs > 10
        ORDER BY n_txs DESC
    """)
    alerts = []
    for _, r in df.iterrows():
        alerts.append({
            'alert_id': make_alert_id('R19', f"{r.sender_id}{r.dt}"),
            'rule_id': 'R19', 'rule_name': 'Velocity Spike >10 txs/dia',
            'customer_id': r.sender_id, 'transaction_id': None,
            'amount_brl': r.total_brl, 'severity': 'MEDIUM',
            'evidence': f"{r.n_txs} txs em {r.dt}, total R${r.total_brl:,.0f}, período {r.primeira}→{r.ultima}",
            'timestamp': r.ultima
        })
    return pd.DataFrame(alerts)


def rule_20_iran_network():
    """R20 — Transação com counterpart M200363 (Iran merchant sancionado) (HIGH)"""
    df = q("""
        SELECT transaction_id, sender_id, receiver_id, amount_brl,
               transaction_type, pix_flow, geo_country,
               sanctions_screening_hit, timestamp
        FROM transactions
        WHERE receiver_id='M200363' OR sender_id='M200363'
        ORDER BY timestamp
    """)
    alerts = []
    for _, r in df.iterrows():
        customer = r.sender_id if r.sender_id != 'M200363' else r.receiver_id
        alerts.append({
            'alert_id': make_alert_id('R20', r.transaction_id),
            'rule_id': 'R20', 'rule_name': 'Rede Iran M200363 (OFAC)',
            'customer_id': customer, 'transaction_id': r.transaction_id,
            'amount_brl': float(r.amount_brl), 'severity': 'HIGH',
            'evidence': f"Counterpart M200363 (Iran), R${float(r.amount_brl):,.0f}, sanção={r.sanctions_screening_hit}, país={r.geo_country}",
            'timestamp': r.timestamp
        })
    return pd.DataFrame(alerts)


# ══════════════════════════════════════════════════════════════════
# ENGINE — RODA TODAS AS REGRAS E CONSOLIDA
# ══════════════════════════════════════════════════════════════════

RULES = [
    rule_01_structuring_pix,
    rule_02_structuring_card,
    rule_03_rapid_structuring,
    rule_04_income_ratio_15x,
    rule_05_income_ratio_5x_pep,
    rule_06_sanctions_hit,
    rule_07_kyc_sanctions_list,
    rule_08_high_risk_country_crossborder,
    rule_09_geo_jump,
    rule_10_cash_fanout,
    rule_11_rapid_redistribution,
    rule_12_self_merchant,
    rule_13_ecommerce_no_3ds,
    rule_14_high_chargeback_merchant,
    rule_15_vpn_tor_high_value,
    rule_16_rooted_device_high_value,
    rule_17_mcc_risk_cumulative,
    rule_18_pep_high_volume,
    rule_19_velocity_spike,
    rule_20_iran_network,
]

COLS = ['alert_id','rule_id','rule_name','customer_id','transaction_id',
        'amount_brl','severity','evidence','timestamp']


def run_all_rules(verbose=True) -> pd.DataFrame:
    all_alerts = []
    print(f"\n{'='*70}")
    print("  CloudWalk AML — Sistema de Alertas v1.0  (20 regras)")
    print(f"{'='*70}")
    for fn in RULES:
        try:
            df = fn()
            n = len(df)
            if verbose:
                sev_counts = df['severity'].value_counts().to_dict() if n > 0 else {}
                tag = '  '.join(f"{s}:{c}" for s,c in sev_counts.items())
                print(f"  {fn.__name__[:35]:<35} → {n:>4} alertas  {tag}")
            all_alerts.append(df)
        except Exception as e:
            print(f"  ERRO {fn.__name__}: {e}")

    combined = pd.concat([df for df in all_alerts if len(df) > 0], ignore_index=True)
    combined = combined[COLS]
    return combined


def summary_report(alerts: pd.DataFrame):
    print(f"\n{'='*70}")
    print("  RESUMO EXECUTIVO")
    print(f"{'='*70}")
    print(f"  Total alertas brutos:   {len(alerts)}")
    print(f"  Clientes únicos:        {alerts['customer_id'].nunique()}")
    print(f"  Txs únicas alertadas:   {alerts['transaction_id'].dropna().nunique()}")

    print(f"\n  Por severidade:")
    for sev, cnt in alerts['severity'].value_counts().items():
        print(f"    {sev:<8} {cnt:>5}")

    print(f"\n  Por regra (top 10 por volume):")
    top = (alerts.groupby(['rule_id','rule_name','severity'])
           .size().reset_index(name='n')
           .sort_values('n', ascending=False).head(10))
    for _, r in top.iterrows():
        print(f"    {r.rule_id} [{r.severity}] {r.rule_name:<45} {r.n:>4}")

    print(f"\n  Clientes com mais alertas (HIGH) — top 15:")
    high = (alerts[alerts['severity']=='HIGH']
            .groupby('customer_id').size().reset_index(name='n_high_alerts')
            .sort_values('n_high_alerts', ascending=False).head(15))
    for _, r in high.iterrows():
        print(f"    {r.customer_id:<12} {r.n_high_alerts} alertas HIGH")


if __name__ == '__main__':
    alerts = run_all_rules(verbose=True)
    summary_report(alerts)

    # Salva CSV para análise posterior
    out = '/Users/limaslucas197/Documents/cw-risk-aml-test/alerts_output.csv'
    alerts.to_csv(out, index=False)
    print(f"\n  CSV salvo: {out}")
    print(f"\n✓ Engine concluído. {len(alerts)} alertas gerados.")
