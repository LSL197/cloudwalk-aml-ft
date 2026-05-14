import sqlite3
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

DB = '/Users/limaslucas197/Documents/cw-risk-aml-test/aml.db'

pd.set_option('display.max_columns', None)
pd.set_option('display.max_colwidth', 60)
pd.set_option('display.float_format', '{:.2f}'.format)

def q(sql):
    with sqlite3.connect(DB) as conn:
        return pd.read_sql(sql, conn)

def show(titulo, sql):
    print(f'\n{"="*60}')
    print(f'  {titulo}')
    print('='*60)
    df = q(sql)
    print(df.to_string(index=False))
    return df

# ── RODE APENAS O BLOCO QUE QUISER ──────────────────────────

if __name__ == '__main__':

    # 1. VISÃO GERAL
    show('Distribuição por Rail', """
        SELECT transaction_type, COUNT(*) n,
               ROUND(COUNT(*)*100.0/52000,1) pct,
               ROUND(SUM(CAST(amount_brl AS REAL)),2) volume_brl
        FROM transactions
        GROUP BY transaction_type ORDER BY n DESC
    """)

    show('Sinais de Risco', """
        SELECT
          SUM(CASE WHEN sanctions_screening_hit='Yes' THEN 1 ELSE 0 END) sanctions_hit,
          SUM(CASE WHEN ip_proxy_vpn_tor != 'None' THEN 1 ELSE 0 END)   vpn_proxy_tor,
          SUM(CASE WHEN cross_border='Yes' THEN 1 ELSE 0 END)           cross_border,
          SUM(CASE WHEN country_risk_geo='High' THEN 1 ELSE 0 END)      high_risk_geo,
          SUM(CASE WHEN device_rooted='Yes' THEN 1 ELSE 0 END)          device_rooted
        FROM transactions
    """)

    show('KYC - PEP / Sancionados / Alto Risco', """
        SELECT
          SUM(CASE WHEN pep='Yes' THEN 1 ELSE 0 END)               pep,
          SUM(CASE WHEN sanctions_list_hit='Yes' THEN 1 ELSE 0 END) sanctioned,
          SUM(CASE WHEN risk_rating='High' THEN 1 ELSE 0 END)       high_risk,
          SUM(CASE WHEN beneficial_owner='Yes' THEN 1 ELSE 0 END)   beneficial_owner,
          COUNT(*) total
        FROM kyc_profiles
    """)

    # 2. TIPOLOGIAS

    show('Structuring (3+ txs R$9k-R$9.9k)', """
        SELECT sender_id, COUNT(*) n_txs,
               ROUND(SUM(CAST(amount_brl AS REAL)),2) total_brl,
               MIN(timestamp) primeira, MAX(timestamp) ultima
        FROM transactions
        WHERE CAST(amount_brl AS REAL) BETWEEN 9000 AND 9999.99
        GROUP BY sender_id HAVING n_txs >= 3
        ORDER BY n_txs DESC, total_brl DESC
    """)

    show('Structuring por Velocidade — ≥4 txs sub-R$10k em 24h (top 20)', """
        SELECT sender_id,
               DATE(timestamp) dia,
               COUNT(*) n_txs,
               ROUND(SUM(CAST(amount_brl AS REAL)),2) total_brl,
               ROUND(MAX(CAST(amount_brl AS REAL)),2) maior_tx,
               ROUND(MIN(CAST(amount_brl AS REAL)),2) menor_tx,
               ROUND(AVG(CAST(amount_brl AS REAL)),2) media_tx,
               MIN(timestamp) primeira,
               MAX(timestamp) ultima,
               ROUND((JULIANDAY(MAX(timestamp))-JULIANDAY(MIN(timestamp)))*60,0) minutos_span
        FROM transactions
        WHERE CAST(amount_brl AS REAL) < 10000
        GROUP BY sender_id, DATE(timestamp)
        HAVING n_txs >= 4
        ORDER BY n_txs DESC, total_brl DESC
        LIMIT 20
    """)

    show('Structuring por Velocidade — ≥3 txs em 1h (top 20)', """
        SELECT sender_id,
               STRFTIME('%Y-%m-%d %H:00', timestamp) hora,
               COUNT(*) n_txs,
               ROUND(SUM(CAST(amount_brl AS REAL)),2) total_brl,
               ROUND(MAX(CAST(amount_brl AS REAL)),2) maior_tx,
               MIN(timestamp) primeira,
               MAX(timestamp) ultima,
               ROUND((JULIANDAY(MAX(timestamp))-JULIANDAY(MIN(timestamp)))*60,1) minutos_span
        FROM transactions
        WHERE CAST(amount_brl AS REAL) < 10000
        GROUP BY sender_id, STRFTIME('%Y-%m-%d %H', timestamp)
        HAVING n_txs >= 3
        ORDER BY n_txs DESC, total_brl DESC
        LIMIT 20
    """)

    show('Income Ratio > 15x renda mensal (top 20)', """
        SELECT t.sender_id, k.declared_occupation, k.annual_income_brl,
               ROUND(CAST(k.annual_income_brl AS REAL)/12,2) monthly_income,
               t.transaction_id, t.amount_brl, t.transaction_type, t.timestamp,
               ROUND(CAST(t.amount_brl AS REAL)/(CAST(k.annual_income_brl AS REAL)/12),1) ratio_x
        FROM transactions t
        JOIN kyc_profiles k ON t.sender_id = k.customer_id
        WHERE CAST(t.amount_brl AS REAL) > 15*(CAST(k.annual_income_brl AS REAL)/12)
        ORDER BY ratio_x DESC LIMIT 20
    """)

    show('Sanctions + País Alto Risco (top 20)', """
        SELECT t.sender_id, t.transaction_id, t.amount_brl, t.transaction_type,
               t.geo_country, t.sanctions_screening_hit,
               t.country_risk_geo, t.country_risk_receiver, t.timestamp
        FROM transactions t
        WHERE t.sanctions_screening_hit = 'Yes'
           OR (t.country_risk_geo = 'High' AND t.cross_border = 'Yes')
           OR t.country_risk_receiver = 'High'
        ORDER BY CAST(t.amount_brl AS REAL) DESC LIMIT 20
    """)

    show('Rede Iran - M200363', """
        SELECT sender_id, receiver_id, transaction_id, amount_brl,
               timestamp, transaction_type, pix_flow, geo_country, sanctions_screening_hit
        FROM transactions
        WHERE receiver_id='M200363' OR sender_id='M200363'
        ORDER BY timestamp
    """)

    show('Self-Merchant', """
        SELECT t.sender_id, t.receiver_id, t.transaction_id, t.amount_brl,
               t.transaction_type, t.timestamp, m.mcc, m.mcc_risk,
               m.merchant_high_risk_flag, m.merchant_chargeback_ratio_90d
        FROM transactions t
        JOIN merchants m ON t.receiver_id = m.merchant_id
        WHERE t.sender_id = m.owner_customer_id
        ORDER BY CAST(t.amount_brl AS REAL) DESC
    """)

    show('E-commerce sem 3DS + Alto Valor', """
        SELECT t.sender_id, t.transaction_id, t.amount_brl, t.auth_3ds, t.eci,
               t.capture_method, t.cross_border, t.mcc, t.timestamp
        FROM transactions t
        WHERE t.transaction_type='Card' AND t.capture_method='E-commerce'
          AND (t.auth_3ds='No' OR t.eci='07')
          AND CAST(t.amount_brl AS REAL) > 5000
        ORDER BY CAST(t.amount_brl AS REAL) DESC LIMIT 20
    """)

    show('PEP com Alto Volume', """
        SELECT t.sender_id, k.declared_occupation, k.annual_income_brl,
               COUNT(*) n_txs,
               ROUND(SUM(CAST(t.amount_brl AS REAL)),2) total_brl,
               ROUND(MAX(CAST(t.amount_brl AS REAL)),2) max_tx
        FROM transactions t
        JOIN kyc_profiles k ON t.sender_id=k.customer_id
        WHERE k.pep='Yes'
        GROUP BY t.sender_id ORDER BY total_brl DESC LIMIT 20
    """)

    show('Cash Fan-out PIX (vol_out/vol_in > 10x)', """
        WITH cash_in AS (
          SELECT receiver_id AS customer_id, COUNT(*) n, SUM(CAST(amount_brl AS REAL)) vol
          FROM transactions WHERE pix_flow='cash_in' AND transaction_type='PIX'
          GROUP BY receiver_id
        ),
        cash_out AS (
          SELECT sender_id AS customer_id, COUNT(*) n, SUM(CAST(amount_brl AS REAL)) vol
          FROM transactions WHERE pix_flow='cash_out' AND transaction_type='PIX'
          GROUP BY sender_id
        )
        SELECT ci.customer_id, ci.n n_in, co.n n_out,
               ROUND(ci.vol,2) vol_in_brl, ROUND(co.vol,2) vol_out_brl,
               ROUND(co.vol/ci.vol,2) passthrough_ratio
        FROM cash_in ci JOIN cash_out co ON ci.customer_id=co.customer_id
        WHERE ci.n >= 3 AND co.n >= 3
        ORDER BY passthrough_ratio DESC LIMIT 20
    """)

    show('MCC Alto Risco (6011/6051/7995/4829)', """
        SELECT t.sender_id, k.declared_occupation, k.annual_income_brl,
               COUNT(*) n_txs,
               GROUP_CONCAT(DISTINCT CAST(t.mcc AS TEXT)) mccs,
               ROUND(SUM(CAST(t.amount_brl AS REAL)),2) total_brl
        FROM transactions t
        JOIN kyc_profiles k ON t.sender_id=k.customer_id
        WHERE CAST(t.mcc AS INTEGER) IN (6011,6051,7995,4829,6538)
        GROUP BY t.sender_id HAVING n_txs >= 3
        ORDER BY total_brl DESC LIMIT 20
    """)

    show('VPN/Proxy/Tor + Alto Valor', """
        SELECT t.sender_id, t.transaction_id, t.amount_brl, t.ip_proxy_vpn_tor,
               t.transaction_type, t.cross_border, t.mcc, k.pep, k.risk_rating, t.timestamp
        FROM transactions t
        JOIN kyc_profiles k ON t.sender_id=k.customer_id
        WHERE t.ip_proxy_vpn_tor != 'None'
        ORDER BY CAST(t.amount_brl AS REAL) DESC LIMIT 20
    """)

    show('Score de Risco por Cliente (top 30)', """
        WITH
        structuring AS (SELECT sender_id, 1 flag FROM transactions WHERE CAST(amount_brl AS REAL) BETWEEN 9000 AND 9999.99 GROUP BY sender_id HAVING COUNT(*) >= 3),
        income_ratio AS (SELECT t.sender_id, 1 flag FROM transactions t JOIN kyc_profiles k ON t.sender_id=k.customer_id WHERE CAST(t.amount_brl AS REAL) > 15*(CAST(k.annual_income_brl AS REAL)/12) GROUP BY t.sender_id),
        geo_risk AS (SELECT sender_id, 1 flag FROM transactions WHERE country_risk_geo='High' OR country_risk_sender='High' OR country_risk_receiver='High' GROUP BY sender_id),
        vpn_tor AS (SELECT sender_id, 1 flag FROM transactions WHERE ip_proxy_vpn_tor != 'None' GROUP BY sender_id),
        self_merch AS (SELECT t.sender_id, 1 flag FROM transactions t JOIN merchants m ON t.receiver_id=m.merchant_id WHERE t.sender_id=m.owner_customer_id GROUP BY t.sender_id),
        pep AS (SELECT customer_id, 1 flag FROM kyc_profiles WHERE pep='Yes'),
        mcc_risk AS (SELECT sender_id, 1 flag FROM transactions WHERE CAST(mcc AS INTEGER) IN (6011,6051,7995,4829,6538) GROUP BY sender_id HAVING COUNT(*) >= 3),
        fanout AS (
          SELECT ci.customer_id, 1 flag
          FROM (SELECT receiver_id customer_id, COUNT(*) n, SUM(CAST(amount_brl AS REAL)) vol FROM transactions WHERE pix_flow='cash_in' AND transaction_type='PIX' GROUP BY receiver_id) ci
          JOIN (SELECT sender_id customer_id, SUM(CAST(amount_brl AS REAL)) vol FROM transactions WHERE pix_flow='cash_out' AND transaction_type='PIX' GROUP BY sender_id) co
          ON ci.customer_id=co.customer_id WHERE co.vol/ci.vol > 10 AND ci.n >= 3
        ),
        sanctions AS (SELECT sender_id, 1 flag FROM transactions WHERE sanctions_screening_hit='Yes' GROUP BY sender_id),
        kyc_hr AS (SELECT customer_id, 1 flag FROM kyc_profiles WHERE risk_rating='High' OR sanctions_list_hit='Yes')
        SELECT k.customer_id, k.declared_occupation, k.pep, k.risk_rating, k.annual_income_brl,
          COALESCE(st.flag,0) structuring, COALESCE(ir.flag,0) income_ratio,
          COALESCE(gr.flag,0) geo_risk, COALESCE(vp.flag,0) vpn_tor,
          COALESCE(sm.flag,0) self_merch, COALESCE(pp.flag,0) pep_flag,
          COALESCE(mr.flag,0) high_mcc, COALESCE(fo.flag,0) fanout,
          COALESCE(sc.flag,0) sanctions, COALESCE(kh.flag,0) kyc_high,
          (COALESCE(st.flag,0)+COALESCE(ir.flag,0)+COALESCE(gr.flag,0)+COALESCE(vp.flag,0)+
           COALESCE(sm.flag,0)+COALESCE(pp.flag,0)+COALESCE(mr.flag,0)+COALESCE(fo.flag,0)+
           COALESCE(sc.flag,0)+COALESCE(kh.flag,0)) risk_score
        FROM kyc_profiles k
        LEFT JOIN structuring st ON k.customer_id=st.sender_id
        LEFT JOIN income_ratio ir ON k.customer_id=ir.sender_id
        LEFT JOIN geo_risk gr ON k.customer_id=gr.sender_id
        LEFT JOIN vpn_tor vp ON k.customer_id=vp.sender_id
        LEFT JOIN self_merch sm ON k.customer_id=sm.sender_id
        LEFT JOIN pep pp ON k.customer_id=pp.customer_id
        LEFT JOIN mcc_risk mr ON k.customer_id=mr.sender_id
        LEFT JOIN fanout fo ON k.customer_id=fo.customer_id
        LEFT JOIN sanctions sc ON k.customer_id=sc.sender_id
        LEFT JOIN kyc_hr kh ON k.customer_id=kh.customer_id
        ORDER BY risk_score DESC, CAST(k.annual_income_brl AS REAL) ASC
        LIMIT 30
    """)

    print('\n✓ Concluído. Para query personalizada, use a função q() no terminal Python.')
