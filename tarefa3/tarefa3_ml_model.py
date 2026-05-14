"""
CloudWalk AML/FT — Tarefa 3: ML Risk Scoring (Híbrido)
=======================================================
Abordagem em 3 etapas:
  1. Feature engineering — features contínuas por cliente
  2. Isolation Forest — anomaly score sem label (unsupervised)
  3. XGBoost — aprende a refinar usando pseudo-labels derivados
     do risk_score ponderado das regras (Tarefa 2)
  4. SHAP — explicabilidade por cliente e global
  5. Métricas — AUC-ROC, Precision-Recall, threshold analysis
"""

import sqlite3
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import (roc_auc_score, average_precision_score,
                             precision_recall_curve, roc_curve,
                             classification_report)
import xgboost as xgb
import shap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

DB = '/Users/limaslucas197/Documents/cw-risk-aml-test/aml.db'
OUT = '/Users/limaslucas197/Documents/cw-risk-aml-test/'

pd.set_option('display.float_format', '{:.4f}'.format)

def q(sql):
    with sqlite3.connect(DB) as c:
        return pd.read_sql(sql, c)


# ══════════════════════════════════════════════════════════════════
# ETAPA 1 — FEATURE ENGINEERING
# Features contínuas (não binárias) por cliente
# ══════════════════════════════════════════════════════════════════

print("\n" + "="*65)
print("  ETAPA 1 — Feature Engineering")
print("="*65)

features_sql = """
WITH

-- Features de volume e comportamento de transações
tx_stats AS (
    SELECT
        sender_id AS customer_id,
        COUNT(*)                                            AS n_txs,
        ROUND(SUM(CAST(amount_brl AS REAL)), 2)            AS total_vol,
        ROUND(AVG(CAST(amount_brl AS REAL)), 2)            AS avg_tx,
        ROUND(MAX(CAST(amount_brl AS REAL)), 2)            AS max_tx,
        ROUND(MIN(CAST(amount_brl AS REAL)), 2)            AS min_tx,
        -- Range normalizado como proxy de dispersão (max-min)/avg
        ROUND(
            CASE WHEN AVG(CAST(amount_brl AS REAL)) > 0
            THEN (MAX(CAST(amount_brl AS REAL)) - MIN(CAST(amount_brl AS REAL)))
                 / AVG(CAST(amount_brl AS REAL))
            ELSE 0 END, 4)                                AS cv_amount,
        COUNT(DISTINCT transaction_type)                   AS n_rails,
        COUNT(DISTINCT DATE(timestamp))                    AS n_active_days,
        SUM(CASE WHEN cross_border='Yes' THEN 1 ELSE 0 END) AS n_crossborder,
        SUM(CASE WHEN sanctions_screening_hit='Yes' THEN 1 ELSE 0 END) AS n_sanctions_hits,
        SUM(CASE WHEN ip_proxy_vpn_tor!='None' THEN 1 ELSE 0 END) AS n_vpn_txs,
        ROUND(MAX(CASE WHEN ip_proxy_vpn_tor!='None'
              THEN CAST(amount_brl AS REAL) ELSE 0 END), 2) AS max_vpn_amount,
        SUM(CASE WHEN device_rooted='Yes' THEN 1 ELSE 0 END) AS n_rooted_txs,
        SUM(CASE WHEN CAST(amount_brl AS REAL) BETWEEN 9000 AND 9999.99
              THEN 1 ELSE 0 END)                          AS n_struct_txs,
        SUM(CASE WHEN CAST(mcc AS INTEGER) IN (6011,6051,7995,4829,6538)
              THEN 1 ELSE 0 END)                          AS n_highrisk_mcc_txs,
        SUM(CASE WHEN transaction_type='PIX' AND pix_flow='cash_out'
              THEN CAST(amount_brl AS REAL) ELSE 0 END)   AS vol_pix_out,
        SUM(CASE WHEN transaction_type='PIX' AND pix_flow='cash_in'
              THEN CAST(amount_brl AS REAL) ELSE 0 END)   AS vol_pix_in,
        COUNT(DISTINCT receiver_id)                        AS n_unique_receivers,
        -- Txs num único dia (burst máximo)
        (SELECT MAX(cnt) FROM (
            SELECT COUNT(*) cnt FROM transactions t2
            WHERE t2.sender_id = t.sender_id
            GROUP BY DATE(t2.timestamp)
        ))                                                AS max_txs_in_day
    FROM transactions t
    GROUP BY sender_id
),

-- Income ratio máximo por cliente
income_feat AS (
    SELECT t.sender_id AS customer_id,
           ROUND(MAX(CAST(t.amount_brl AS REAL) /
                 NULLIF(CAST(k.annual_income_brl AS REAL)/12, 0)), 2) AS max_income_ratio,
           ROUND(SUM(CAST(t.amount_brl AS REAL)) /
                 NULLIF(CAST(k.annual_income_brl AS REAL), 0), 2)      AS total_vol_to_income
    FROM transactions t
    JOIN kyc_profiles k ON t.sender_id = k.customer_id
    WHERE CAST(k.annual_income_brl AS REAL) > 0
    GROUP BY t.sender_id
),

-- Geo-jump: menor intervalo entre países distintos
geo_feat AS (
    SELECT a.sender_id AS customer_id,
           ROUND(MIN((JULIANDAY(b.timestamp)-JULIANDAY(a.timestamp))*60), 2) AS min_geojump_min,
           COUNT(*)                                                            AS n_geojumps
    FROM transactions a
    JOIN transactions b
      ON a.sender_id = b.sender_id
     AND a.geo_country != b.geo_country
     AND b.timestamp > a.timestamp
     AND (JULIANDAY(b.timestamp)-JULIANDAY(a.timestamp))*24 < 12
    GROUP BY a.sender_id
),

-- Fan-out ratio
fanout_feat AS (
    SELECT ci.customer_id,
           ROUND(COALESCE(co.vol, 0) / NULLIF(ci.vol, 0), 4) AS fanout_ratio,
           ci.n AS n_pix_in,
           COALESCE(co.n, 0)                                   AS n_pix_out
    FROM (SELECT receiver_id customer_id, COUNT(*) n,
                 SUM(CAST(amount_brl AS REAL)) vol
          FROM transactions WHERE pix_flow='cash_in' AND transaction_type='PIX'
          GROUP BY receiver_id) ci
    LEFT JOIN (SELECT sender_id customer_id, COUNT(*) n,
                      SUM(CAST(amount_brl AS REAL)) vol
               FROM transactions WHERE pix_flow='cash_out' AND transaction_type='PIX'
               GROUP BY sender_id) co
      ON ci.customer_id = co.customer_id
)

SELECT
    k.customer_id,
    -- KYC features
    CAST(k.annual_income_brl AS REAL)                    AS annual_income,
    CASE WHEN k.pep='Yes' THEN 1 ELSE 0 END             AS pep,
    CASE WHEN k.risk_rating='High' THEN 2
         WHEN k.risk_rating='Medium' THEN 1 ELSE 0 END  AS kyc_risk_level,
    CAST(k.kyc_risk_score AS REAL)                       AS kyc_risk_score,
    CASE WHEN k.beneficial_owner='Yes' THEN 1 ELSE 0 END AS beneficial_owner,
    CASE WHEN k.sanctions_list_hit='Yes' THEN 1 ELSE 0 END AS kyc_sanctions,
    -- TX features
    COALESCE(tx.n_txs, 0)                               AS n_txs,
    COALESCE(tx.total_vol, 0)                            AS total_vol,
    COALESCE(tx.avg_tx, 0)                               AS avg_tx,
    COALESCE(tx.max_tx, 0)                               AS max_tx,
    COALESCE(tx.cv_amount, 0)                            AS cv_amount,
    COALESCE(tx.n_rails, 0)                              AS n_rails,
    COALESCE(tx.n_active_days, 0)                        AS n_active_days,
    COALESCE(tx.n_crossborder, 0)                        AS n_crossborder,
    COALESCE(tx.n_sanctions_hits, 0)                     AS n_sanctions_hits,
    COALESCE(tx.n_vpn_txs, 0)                            AS n_vpn_txs,
    COALESCE(tx.max_vpn_amount, 0)                       AS max_vpn_amount,
    COALESCE(tx.n_rooted_txs, 0)                         AS n_rooted_txs,
    COALESCE(tx.n_struct_txs, 0)                         AS n_struct_txs,
    COALESCE(tx.n_highrisk_mcc_txs, 0)                  AS n_highrisk_mcc_txs,
    COALESCE(tx.vol_pix_out, 0)                          AS vol_pix_out,
    COALESCE(tx.vol_pix_in, 0)                           AS vol_pix_in,
    COALESCE(tx.n_unique_receivers, 0)                   AS n_unique_receivers,
    COALESCE(tx.max_txs_in_day, 0)                       AS max_txs_in_day,
    -- Income ratio
    COALESCE(ir.max_income_ratio, 0)                     AS max_income_ratio,
    COALESCE(ir.total_vol_to_income, 0)                  AS total_vol_to_income,
    -- Geo features
    COALESCE(gf.min_geojump_min, 9999)                   AS min_geojump_min,
    COALESCE(gf.n_geojumps, 0)                           AS n_geojumps,
    -- Fan-out
    COALESCE(ff.fanout_ratio, 0)                         AS fanout_ratio,
    COALESCE(ff.n_pix_in, 0)                             AS n_pix_in,
    COALESCE(ff.n_pix_out, 0)                            AS n_pix_out

FROM kyc_profiles k
LEFT JOIN tx_stats      tx ON k.customer_id = tx.customer_id
LEFT JOIN income_feat   ir ON k.customer_id = ir.customer_id
LEFT JOIN geo_feat      gf ON k.customer_id = gf.customer_id
LEFT JOIN fanout_feat   ff ON k.customer_id = ff.customer_id
"""

df = q(features_sql)
print(f"  Clientes: {len(df)} | Features: {df.shape[1]-1}")
print(f"  Missings: {df.isnull().sum().sum()}")

# Fill remaining nulls
df = df.fillna(0)

FEATURE_COLS = [c for c in df.columns if c != 'customer_id']
X = df[FEATURE_COLS].copy()
print(f"  Features finais: {len(FEATURE_COLS)}")
print(f"  {FEATURE_COLS}")


# ══════════════════════════════════════════════════════════════════
# ETAPA 2 — ISOLATION FOREST (unsupervised)
# ══════════════════════════════════════════════════════════════════

print("\n" + "="*65)
print("  ETAPA 2 — Isolation Forest (Anomaly Detection)")
print("="*65)

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

iso = IsolationForest(
    n_estimators=300,
    contamination=0.05,   # 5% dos clientes esperados como anômalos
    max_samples='auto',
    random_state=42,
    n_jobs=-1
)
iso.fit(X_scaled)

# score_samples: mais negativo = mais anômalo
iso_raw = iso.score_samples(X_scaled)
# Normaliza para 0–1 onde 1 = mais anômalo
iso_score = 1 - (iso_raw - iso_raw.min()) / (iso_raw.max() - iso_raw.min())

df['iso_score'] = iso_score
df['iso_label'] = (iso.predict(X_scaled) == -1).astype(int)

n_anomalies = df['iso_label'].sum()
print(f"  Anomalias detectadas: {n_anomalies} ({n_anomalies/len(df)*100:.1f}%)")
print(f"  ISO score — média: {iso_score.mean():.4f} | max: {iso_score.max():.4f}")

top_iso = df.nlargest(10, 'iso_score')[['customer_id','iso_score','iso_label',
                                         'max_income_ratio','min_geojump_min',
                                         'n_struct_txs','n_vpn_txs','total_vol']]
print(f"\n  Top 10 anomalias (Isolation Forest):")
print(top_iso.to_string(index=False))


# ══════════════════════════════════════════════════════════════════
# ETAPA 3 — PSEUDO-LABELS + XGBOOST
# ══════════════════════════════════════════════════════════════════

print("\n" + "="*65)
print("  ETAPA 3 — XGBoost com Pseudo-labels")
print("="*65)

# Pseudo-label: risk_score ponderado das flags (Tarefa 2 CTE)
pseudo_sql = """
WITH
structuring AS (SELECT sender_id, 1 flag FROM transactions WHERE CAST(amount_brl AS REAL) BETWEEN 9000 AND 9999.99 GROUP BY sender_id HAVING COUNT(*)>=2),
vel_struct  AS (SELECT sender_id, 1 flag FROM (SELECT sender_id, DATE(timestamp) d, COUNT(*) n FROM transactions WHERE CAST(amount_brl AS REAL)<10000 GROUP BY sender_id, DATE(timestamp) HAVING n>=3) GROUP BY sender_id),
income_r    AS (SELECT t.sender_id, 1 flag FROM transactions t JOIN kyc_profiles k ON t.sender_id=k.customer_id WHERE CAST(k.annual_income_brl AS REAL)>0 AND CAST(t.amount_brl AS REAL)>15*(CAST(k.annual_income_brl AS REAL)/12) GROUP BY t.sender_id),
geo_j       AS (SELECT DISTINCT a.sender_id, 1 flag FROM transactions a JOIN transactions b ON a.sender_id=b.sender_id AND a.geo_country!=b.geo_country AND b.timestamp>a.timestamp AND (JULIANDAY(b.timestamp)-JULIANDAY(a.timestamp))*24<12),
vpn_t       AS (SELECT sender_id, 1 flag FROM transactions WHERE ip_proxy_vpn_tor!='None' GROUP BY sender_id),
fanout      AS (SELECT ci.customer_id, 1 flag FROM (SELECT receiver_id customer_id, COUNT(*) n, SUM(CAST(amount_brl AS REAL)) vol FROM transactions WHERE pix_flow='cash_in' AND transaction_type='PIX' GROUP BY receiver_id HAVING n>=3) ci JOIN (SELECT sender_id customer_id, SUM(CAST(amount_brl AS REAL)) vol FROM transactions WHERE pix_flow='cash_out' AND transaction_type='PIX' GROUP BY sender_id) co ON ci.customer_id=co.customer_id WHERE co.vol/ci.vol>3),
self_m      AS (SELECT t.sender_id, 1 flag FROM transactions t JOIN merchants m ON t.receiver_id=m.merchant_id WHERE t.sender_id=m.owner_customer_id GROUP BY t.sender_id),
sanctions   AS (SELECT sender_id, 1 flag FROM transactions WHERE sanctions_screening_hit='Yes' GROUP BY sender_id),
kyc_hr      AS (SELECT customer_id, 1 flag FROM kyc_profiles WHERE risk_rating='High' OR sanctions_list_hit='Yes'),
pep_f       AS (SELECT customer_id, 1 flag FROM kyc_profiles WHERE pep='Yes'),
geo_risk    AS (SELECT sender_id, 1 flag FROM transactions WHERE country_risk_geo='High' OR country_risk_receiver='High' GROUP BY sender_id),
mcc_r       AS (SELECT sender_id, 1 flag FROM transactions WHERE CAST(mcc AS INTEGER) IN (6011,6051,7995,4829,6538) GROUP BY sender_id HAVING COUNT(*)>=3)

SELECT k.customer_id,
  (COALESCE(st.flag,0)*2 + COALESCE(vs.flag,0) + COALESCE(ir.flag,0)*2 +
   COALESCE(gj.flag,0)*3 + COALESCE(vp.flag,0) + COALESCE(fo.flag,0)*2 +
   COALESCE(sm.flag,0)*2 + COALESCE(sc.flag,0)*3 + COALESCE(kh.flag,0) +
   COALESCE(pp.flag,0) + COALESCE(gr.flag,0) + COALESCE(mr.flag,0)) risk_score
FROM kyc_profiles k
LEFT JOIN structuring st ON k.customer_id=st.sender_id
LEFT JOIN vel_struct  vs ON k.customer_id=vs.sender_id
LEFT JOIN income_r    ir ON k.customer_id=ir.sender_id
LEFT JOIN geo_j       gj ON k.customer_id=gj.sender_id
LEFT JOIN vpn_t       vp ON k.customer_id=vp.sender_id
LEFT JOIN fanout      fo ON k.customer_id=fo.customer_id
LEFT JOIN self_m      sm ON k.customer_id=sm.sender_id
LEFT JOIN sanctions   sc ON k.customer_id=sc.sender_id
LEFT JOIN kyc_hr      kh ON k.customer_id=kh.customer_id
LEFT JOIN pep_f       pp ON k.customer_id=pp.customer_id
LEFT JOIN geo_risk    gr ON k.customer_id=gr.sender_id
LEFT JOIN mcc_r       mr ON k.customer_id=mr.sender_id
"""

pseudo = q(pseudo_sql)
df = df.merge(pseudo, on='customer_id', how='left')
df['risk_score'] = df['risk_score'].fillna(0)

# Pseudo-label: score >= 5 = suspeito (1), < 5 = normal (0)
THRESHOLD_LABEL = 5
df['y_pseudo'] = (df['risk_score'] >= THRESHOLD_LABEL).astype(int)

n_pos = df['y_pseudo'].sum()
n_neg = len(df) - n_pos
print(f"  Pseudo-labels: {n_pos} suspeitos ({n_pos/len(df)*100:.1f}%) | {n_neg} normais")
print(f"  Risk score — média: {df['risk_score'].mean():.2f} | max: {df['risk_score'].max():.0f}")

# Features para XGBoost: contínuas + iso_score (não inclui risk_score nem flags binárias puras)
XGB_FEATURES = FEATURE_COLS + ['iso_score']
X_xgb = df[XGB_FEATURES].values
y = df['y_pseudo'].values

# Scale ratio (peso inverso de frequência de classe)
scale_pos = n_neg / max(n_pos, 1)

model = xgb.XGBClassifier(
    n_estimators=300,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    scale_pos_weight=scale_pos,
    eval_metric='aucpr',
    use_label_encoder=False,
    random_state=42,
    n_jobs=-1
)

# Cross-validation
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
auc_scores = cross_val_score(model, X_xgb, y, cv=cv, scoring='roc_auc', n_jobs=-1)
apr_scores  = cross_val_score(model, X_xgb, y, cv=cv, scoring='average_precision', n_jobs=-1)

print(f"\n  Cross-validation (5-fold):")
print(f"    AUC-ROC:  {auc_scores.mean():.4f} ± {auc_scores.std():.4f}")
print(f"    Avg Prec: {apr_scores.mean():.4f} ± {apr_scores.std():.4f}")

# Treina modelo final em todos os dados
model.fit(X_xgb, y)
df['xgb_prob'] = model.predict_proba(X_xgb)[:, 1]

# Score final híbrido: combina XGBoost + Isolation Forest
df['final_score'] = 0.7 * df['xgb_prob'] + 0.3 * df['iso_score']

print(f"\n  XGBoost prob — média: {df['xgb_prob'].mean():.4f} | top 1%: {df['xgb_prob'].quantile(0.99):.4f}")
print(f"  Final score  — média: {df['final_score'].mean():.4f} | top 1%: {df['final_score'].quantile(0.99):.4f}")

# Métricas no conjunto completo
auc_full = roc_auc_score(y, df['xgb_prob'])
apr_full = average_precision_score(y, df['xgb_prob'])
print(f"\n  Métricas (treino completo — referência):")
print(f"    AUC-ROC:        {auc_full:.4f}")
print(f"    Avg Precision:  {apr_full:.4f}")


# ══════════════════════════════════════════════════════════════════
# ETAPA 4 — SHAP
# ══════════════════════════════════════════════════════════════════

print("\n" + "="*65)
print("  ETAPA 4 — SHAP Explainability")
print("="*65)

explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_xgb)

# Importância global (mean |SHAP|)
shap_importance = pd.DataFrame({
    'feature': XGB_FEATURES,
    'mean_abs_shap': np.abs(shap_values).mean(axis=0)
}).sort_values('mean_abs_shap', ascending=False)

print("\n  Importância Global das Features (mean |SHAP|):")
print(shap_importance.head(15).to_string(index=False))

# Salva gráfico SHAP summary
plt.figure(figsize=(10, 8))
shap.summary_plot(shap_values, X_xgb, feature_names=XGB_FEATURES,
                  max_display=15, show=False)
plt.tight_layout()
plt.savefig(OUT + 'shap_summary.png', dpi=150, bbox_inches='tight')
plt.close()
print(f"\n  Gráfico salvo: shap_summary.png")

# Salva gráfico ROC
fpr, tpr, _ = roc_curve(y, df['xgb_prob'])
precision, recall, _ = precision_recall_curve(y, df['xgb_prob'])

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

ax1.plot(fpr, tpr, 'b-', lw=2, label=f'AUC-ROC = {auc_full:.3f}')
ax1.plot([0,1],[0,1],'k--', lw=1)
ax1.set_xlabel('False Positive Rate'); ax1.set_ylabel('True Positive Rate')
ax1.set_title('ROC Curve'); ax1.legend()

ax2.plot(recall, precision, 'r-', lw=2, label=f'Avg Precision = {apr_full:.3f}')
ax2.set_xlabel('Recall'); ax2.set_ylabel('Precision')
ax2.set_title('Precision-Recall Curve'); ax2.legend()

plt.tight_layout()
plt.savefig(OUT + 'roc_pr_curves.png', dpi=150, bbox_inches='tight')
plt.close()
print(f"  Gráfico salvo: roc_pr_curves.png")


# ══════════════════════════════════════════════════════════════════
# ETAPA 5 — RANKING FINAL + OUTPUT
# ══════════════════════════════════════════════════════════════════

print("\n" + "="*65)
print("  ETAPA 5 — Ranking Final de Risco")
print("="*65)

# Adiciona info KYC para output
kyc_info = q("SELECT customer_id, declared_occupation, annual_income_brl, pep, risk_rating FROM kyc_profiles")
result = df.merge(kyc_info, on='customer_id', how='left')
result = result.sort_values('final_score', ascending=False)

# Tier de risco baseado no final_score
result['risk_tier'] = pd.cut(
    result['final_score'],
    bins=[0, 0.3, 0.5, 0.7, 1.0],
    labels=['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'],
    include_lowest=True
)

print("\n  Distribuição por tier:")
print(result['risk_tier'].value_counts().sort_index())

print("\n  Top 30 — Score Final Híbrido:")
top30 = result.head(30)[['customer_id','declared_occupation','annual_income_brl',
                           'risk_rating','risk_score','iso_score',
                           'xgb_prob','final_score','risk_tier',
                           'max_income_ratio','min_geojump_min','n_struct_txs',
                           'n_vpn_txs','total_vol']]
print(top30.to_string(index=False))

# Salva CSV completo
result_cols = ['customer_id','declared_occupation','annual_income_brl','risk_rating',
               'risk_score','iso_score','xgb_prob','final_score','risk_tier',
               'max_income_ratio','min_geojump_min','n_struct_txs','n_vpn_txs',
               'total_vol','n_txs','n_crossborder','fanout_ratio',
               'n_geojumps','n_sanctions_hits','kyc_risk_score']
result[result_cols].to_csv(OUT + 'ml_risk_scores.csv', index=False)
print(f"\n  CSV salvo: ml_risk_scores.csv")

# SHAP individual — top 5 suspeitos
print("\n  SHAP individual — Top 5 suspeitos:")
for i, row in result.head(5).iterrows():
    idx = df.index.get_loc(i)
    top_feats = pd.Series(shap_values[idx], index=XGB_FEATURES).abs().nlargest(3)
    print(f"\n  [{row.customer_id}] final={row.final_score:.4f} tier={row.risk_tier}")
    for feat, val in top_feats.items():
        raw_val = df.loc[i, feat] if feat in df.columns else '?'
        direction = '↑' if shap_values[idx][XGB_FEATURES.index(feat)] > 0 else '↓'
        print(f"    {direction} {feat}: SHAP={val:.4f} (valor={raw_val:.2f})")

print(f"\n{'='*65}")
print(f"  Modelo concluído.")
print(f"  AUC-ROC CV:  {auc_scores.mean():.4f}")
print(f"  Avg Prec CV: {apr_scores.mean():.4f}")
print(f"  Outputs: ml_risk_scores.csv | shap_summary.png | roc_pr_curves.png")
print(f"{'='*65}")
