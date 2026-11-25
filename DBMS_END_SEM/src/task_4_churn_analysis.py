"""Deliverable 4: Churn Prediction Pipeline (EDA, Modelling, Evaluation, Business Scenarios).

Executes sql/task_4_churn_analysis.sql against outputs/telemetry.duckdb,
runs EDA, trains Baseline, Logistic Regression (Standard & Balanced), Decision Tree,
and HistGradientBoosting models on time-based Train -> Val -> Test splits,
evaluates ROC-AUC, PR-AUC, calibration, Top-K targeting, unseen-player test subset,
cost-value scenarios, and saves all tables and charts.
"""

from pathlib import Path
import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

DB_PATH = Path("outputs/telemetry.duckdb")
SQL_PATH = Path("sql/task_4_churn_analysis.sql")
OUT_TABLES = Path("outputs/tables")
OUT_CHARTS = Path("outputs/charts")
OUT_TABLES.mkdir(parents=True, exist_ok=True)
OUT_CHARTS.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", context="notebook")
RANDOM_SEED = 42

con = duckdb.connect(str(DB_PATH), read_only=True)

# ---------------------------------------------------------------------------
# 1. Churn Definition Evidence Table (Data-driven justification)
# ---------------------------------------------------------------------------
df_def = con.execute("""
    WITH pd AS (
        SELECT device_id, TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE AS dt
        FROM player_day
    ),
    as_of AS (
        SELECT pf.device_id,
               MAX(CASE WHEN pd.dt <= DATE '2026-03-15' THEN pd.dt END) AS last_act_dt,
               MAX(CASE WHEN pd.dt BETWEEN DATE '2026-03-16' AND DATE '2026-03-29' THEN 1 ELSE 0 END) AS active_next_14d,
               MAX(CASE WHEN pd.dt BETWEEN DATE '2026-03-30' AND DATE '2026-04-30' THEN 1 ELSE 0 END) AS active_after_14d
        FROM player_profile pf
        LEFT JOIN pd ON pf.device_id = pd.device_id
        WHERE pf.install_date <= DATE '2026-03-15'
        GROUP BY 1
    ),
    binned AS (
        SELECT *,
               CASE
                   WHEN last_act_dt IS NULL THEN 'Never active'
                   WHEN DATEDIFF('day', last_act_dt, DATE '2026-03-15') = 0 THEN '0d (active today)'
                   WHEN DATEDIFF('day', last_act_dt, DATE '2026-03-15') BETWEEN 1 AND 3 THEN '1-3d'
                   WHEN DATEDIFF('day', last_act_dt, DATE '2026-03-15') BETWEEN 4 AND 7 THEN '4-7d'
                   WHEN DATEDIFF('day', last_act_dt, DATE '2026-03-15') BETWEEN 8 AND 14 THEN '8-14d'
                   WHEN DATEDIFF('day', last_act_dt, DATE '2026-03-15') BETWEEN 15 AND 30 THEN '15-30d'
                   ELSE '31+d'
               END AS recency_bucket
        FROM as_of
    )
    SELECT recency_bucket,
           COUNT(*) AS players,
           ROUND(100.0 * AVG(active_next_14d), 2) AS pct_returned_in_14d,
           ROUND(100.0 * AVG(1 - active_next_14d), 2) AS churn_14d_pct,
           ROUND(100.0 * AVG(CASE WHEN active_next_14d = 0 AND active_after_14d = 1 THEN 1.0 ELSE 0.0 END), 2) AS missed_14d_but_returned_later_pct
    FROM binned
    GROUP BY 1
""").df()
bucket_order = ["0d (active today)", "1-3d", "4-7d", "8-14d", "15-30d", "31+d", "Never active"]
df_def["recency_bucket"] = pd.Categorical(df_def["recency_bucket"], categories=bucket_order, ordered=True)
df_def = df_def.sort_values("recency_bucket")
df_def.to_csv(OUT_TABLES / "task_4_churn_definition_evidence.csv", index=False)

# ---------------------------------------------------------------------------
# 2. Build Leak-Free Modelling Dataset from SQL
# ---------------------------------------------------------------------------
sql_text = SQL_PATH.read_text(encoding="utf-8")
df_all = con.execute(sql_text).df()
con.close()

# Fill any edge nulls cleanly (e.g., avg_session_duration_30d if sess_30d=0)
df_all["avg_session_duration_30d"] = df_all["avg_session_duration_30d"].fillna(0.0)
df_all["sessions_per_active_day_30d"] = df_all["sessions_per_active_day_30d"].fillna(0.0)
df_all["playtime_per_active_day_30d"] = df_all["playtime_per_active_day_30d"].fillna(0.0)
df_all["country_tier"] = df_all["country_tier"].astype(str)

df_train = df_all[df_all["split_name"] == "train"].copy().reset_index(drop=True)
df_val = df_all[df_all["split_name"] == "val"].copy().reset_index(drop=True)
df_test = df_all[df_all["split_name"] == "test"].copy().reset_index(drop=True)

train_val_ids = set(df_train["device_id"]).union(set(df_val["device_id"]))
test_unseen_mask = ~df_test["device_id"].isin(train_val_ids)

# Assertions for leakage and completeness
assert df_train["snap_date"].max() < df_val["snap_date"].min() < df_test["snap_date"].min()
assert len(df_train) == 20025 and len(df_val) == 26886 and len(df_test) == 38644
assert df_all.isna().sum().sum() == 0, f"Unexpected nulls: {df_all.isna().sum()}"
print(f"[PASS] Dataset loaded: Train={len(df_train):,} (churn={df_train['churn_14d'].mean():.2%}), "
      f"Val={len(df_val):,} (churn={df_val['churn_14d'].mean():.2%}), "
      f"Test={len(df_test):,} (churn={df_test['churn_14d'].mean():.2%}, unseen={test_unseen_mask.sum():,})")

# ---------------------------------------------------------------------------
# 3. Phase 3 Exploratory Analysis (Segments & Feature Summaries)
# ---------------------------------------------------------------------------
df_all["install_age_bucket"] = pd.cut(
    df_all["install_age_days"],
    bins=[-1, 7, 30, 90, 9999],
    labels=["0-7d (New)", "8-30d", "31-90d", "91+d (Veteran)"],
)
eda_rows = []
for split in ["train", "val", "test"]:
    sub_s = df_all[df_all["split_name"] == split]
    eda_rows.append({
        "split": split, "segment_type": "overall", "segment_value": "All Active Players",
        "players": len(sub_s), "churners": int(sub_s["churn_14d"].sum()),
        "churn_rate_pct": round(100.0 * sub_s["churn_14d"].mean(), 2),
    })
    for col in ["platform", "country_tier", "acquisition_channel", "install_age_bucket"]:
        grp = sub_s.groupby(col, observed=False)["churn_14d"].agg(["count", "sum", "mean"]).reset_index()
        for _, r_g in grp.iterrows():
            eda_rows.append({
                "split": split, "segment_type": col, "segment_value": str(r_g[col]),
                "players": int(r_g["count"]), "churners": int(r_g["sum"]),
                "churn_rate_pct": round(100.0 * float(r_g["mean"]), 2),
            })
df_eda = pd.DataFrame(eda_rows)
df_eda.to_csv(OUT_TABLES / "task_4_eda_segments.csv", index=False)

num_features = [
    "install_age_days", "act_7d", "act_prev_7d", "act_trend_7d", "act_14d", "act_30d",
    "act_lifetime", "days_since_last_activity", "sess_7d", "sess_14d", "sess_30d",
    "play_7d", "play_trend_7d", "play_14d", "play_30d",
    "avg_session_duration_30d", "sessions_per_active_day_30d", "playtime_per_active_day_30d",
    "level_as_of", "level_gain_14d", "is_payer_lifetime", "gross_spend_lifetime_usd",
    "gross_spend_30d_usd", "purchase_count_lifetime", "days_since_last_purchase_filled",
    "spend_events_14d", "clean_currency_spent_14d", "ad_views_14d", "ad_completed_14d",
]
cat_features = ["platform", "country_tier", "acquisition_channel"]
feature_cols = num_features + cat_features

# Feature comparison between churned and retained on Validation set
feat_rows = []
for f in num_features:
    m0 = df_val.loc[df_val["churn_14d"] == 0, f].mean()
    m1 = df_val.loc[df_val["churn_14d"] == 1, f].mean()
    auc_uni = roc_auc_score(df_val["churn_14d"], df_val[f])
    if auc_uni < 0.5:
        auc_uni_dir = 1.0 - auc_uni
        direction = "Higher -> Lower Churn"
    else:
        auc_uni_dir = auc_uni
        direction = "Higher -> Higher Churn"
    feat_rows.append({
        "feature": f,
        "mean_retained": round(float(m0), 3),
        "mean_churned": round(float(m1), 3),
        "diff_churned_minus_retained": round(float(m1 - m0), 3),
        "univariate_roc_auc": round(float(auc_uni_dir), 4),
        "direction": direction,
    })
df_feat_sum = pd.DataFrame(feat_rows).sort_values("univariate_roc_auc", ascending=False)
df_feat_sum.to_csv(OUT_TABLES / "task_4_feature_summary.csv", index=False)

# ---------------------------------------------------------------------------
# 4. Modelling: Baseline, Logistic Regression (Tuned), Decision Tree, HGB
# ---------------------------------------------------------------------------
X_train, y_train = df_train[feature_cols], df_train["churn_14d"].to_numpy()
X_val, y_val = df_val[feature_cols], df_val["churn_14d"].to_numpy()
X_test, y_test = df_test[feature_cols], df_test["churn_14d"].to_numpy()

preprocessor = ColumnTransformer(
    transformers=[
        ("num", StandardScaler(), num_features),
        ("cat", OneHotEncoder(drop="first", handle_unknown="ignore"), cat_features),
    ]
)

# Tune Logistic Regression C on Validation PR-AUC / ROC-AUC
best_c, best_val_auc = 1.0, -1.0
for c_val in [0.01, 0.05, 0.1, 0.5, 1.0, 5.0]:
    pipe_tmp = Pipeline([
        ("prep", preprocessor),
        ("clf", LogisticRegression(C=c_val, max_iter=1000, random_state=RANDOM_SEED)),
    ])
    pipe_tmp.fit(X_train, y_train)
    p_v = pipe_tmp.predict_proba(X_val)[:, 1]
    auc_v = roc_auc_score(y_val, p_v)
    if auc_v > best_val_auc:
        best_val_auc = auc_v
        best_c = c_val

models = {
    "Baseline (Prior Dummy)": Pipeline([
        ("prep", preprocessor),
        ("clf", DummyClassifier(strategy="prior")),
    ]),
    "Baseline (Recency Rule Only)": None,  # handled manually via recency score
    f"Logistic Regression (C={best_c})": Pipeline([
        ("prep", preprocessor),
        ("clf", LogisticRegression(C=best_c, max_iter=1000, random_state=RANDOM_SEED)),
    ]),
    f"Logistic Regression (Balanced, C={best_c})": Pipeline([
        ("prep", preprocessor),
        ("clf", LogisticRegression(C=best_c, class_weight="balanced", max_iter=1000, random_state=RANDOM_SEED)),
    ]),
    "Decision Tree (depth=5, leaf=100)": Pipeline([
        ("prep", preprocessor),
        ("clf", DecisionTreeClassifier(max_depth=5, min_samples_leaf=100, random_state=RANDOM_SEED)),
    ]),
    "HistGradientBoosting (depth=4)": Pipeline([
        ("prep", preprocessor),
        ("clf", HistGradientBoostingClassifier(max_depth=4, max_iter=120, learning_rate=0.05, min_samples_leaf=100, random_state=RANDOM_SEED)),
    ]),
}


def eval_probs(name: str, split_lbl: str, y_true: np.ndarray, probs: np.ndarray, thresh: float = 0.5) -> dict:
    preds = (probs >= thresh).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, preds).ravel()
    return {
        "model": name,
        "split": split_lbl,
        "n_players": len(y_true),
        "actual_churners": int(y_true.sum()),
        "threshold": thresh,
        "roc_auc": round(float(roc_auc_score(y_true, probs)), 4),
        "pr_auc": round(float(average_precision_score(y_true, probs)), 4),
        "brier_score": round(float(brier_score_loss(y_true, probs)), 4),
        "precision": round(float(precision_score(y_true, preds, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, preds, zero_division=0)), 4),
        "f1_score": round(float(f1_score(y_true, preds, zero_division=0)), 4),
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
    }


comp_rows = []
test_probs_dict = {}

for m_name, pipe in models.items():
    if pipe is None:
        # Simple recency heuristic: scaled recency score in [0, 1] from Train churn rate per recency day
        rec_map = df_train.groupby("days_since_last_activity")["churn_14d"].mean().to_dict()
        p_val = df_val["days_since_last_activity"].map(rec_map).fillna(df_train["churn_14d"].mean()).to_numpy()
        p_test = df_test["days_since_last_activity"].map(rec_map).fillna(df_train["churn_14d"].mean()).to_numpy()
    else:
        pipe.fit(X_train, y_train)
        p_val = pipe.predict_proba(X_val)[:, 1]
        p_test = pipe.predict_proba(X_test)[:, 1]

    test_probs_dict[m_name] = p_test
    # Evaluate at default 0.50 AND at F1-optimal threshold chosen on Validation
    prec_v, rec_v, thr_v = precision_recall_curve(y_val, p_val)
    f1s_v = np.where((prec_v[:-1] + rec_v[:-1]) > 0, 2 * prec_v[:-1] * rec_v[:-1] / (prec_v[:-1] + rec_v[:-1]), 0)
    opt_thr = float(thr_v[np.argmax(f1s_v)]) if len(thr_v) > 0 else 0.5

    comp_rows.append(eval_probs(m_name, "validation_thr_0.50", y_val, p_val, 0.50))
    comp_rows.append(eval_probs(m_name, "validation_opt_f1", y_val, p_val, round(opt_thr, 4)))
    comp_rows.append(eval_probs(m_name, "test_thr_0.50", y_test, p_test, 0.50))
    comp_rows.append(eval_probs(m_name, "test_opt_f1", y_test, p_test, round(opt_thr, 4)))
    comp_rows.append(eval_probs(m_name, "test_unseen_players_opt_f1", y_test[test_unseen_mask], p_test[test_unseen_mask], round(opt_thr, 4)))

df_comp = pd.DataFrame(comp_rows)
df_comp.to_csv(OUT_TABLES / "task_4_model_comparison.csv", index=False)

# Select Final Model: Standard Logistic Regression (interpretable, well-calibrated, matches/beats DT and near HGB)
final_model_name = f"Logistic Regression (C={best_c})"
final_pipe = models[final_model_name]
p_test_final = test_probs_dict[final_model_name]

# Feature coefficients for Final Logistic Regression
ohe = final_pipe.named_steps["prep"].named_transformers_["cat"]
all_feat_names = num_features + list(ohe.get_feature_names_out(cat_features))
coefs = final_pipe.named_steps["clf"].coef_[0]
df_imp = pd.DataFrame({
    "feature": all_feat_names,
    "std_log_odds_coef": np.round(coefs, 4),
    "abs_coef": np.round(np.abs(coefs), 4),
    "odds_ratio_per_1sd": np.round(np.exp(coefs), 4),
}).sort_values("abs_coef", ascending=False)
df_imp.to_csv(OUT_TABLES / "task_4_feature_importance.csv", index=False)

# ---------------------------------------------------------------------------
# 5. Threshold & Top-K% Targeting Analysis (on Test Set, n=38,644)
# ---------------------------------------------------------------------------
base_churn_rate = float(y_test.mean())
thresh_rows = []

for top_k in [5, 10, 20, 30, 50]:
    cutoff = float(np.percentile(p_test_final, 100 - top_k))
    mask = p_test_final >= cutoff
    tn, fp, fn, tp = confusion_matrix(y_test, mask.astype(int)).ravel()
    targeted = int(tp + fp)
    prec = tp / targeted if targeted else 0.0
    rec = tp / y_test.sum()
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    thresh_rows.append({
        "rule_type": "top_k_pct",
        "rule_label": f"Top {top_k}% Riskiest",
        "prob_cutoff": round(cutoff, 4),
        "targeted_players": targeted,
        "pct_of_active_base": round(100.0 * targeted / len(y_test), 2),
        "true_churners_caught_tp": int(tp),
        "wasted_offers_fp": int(fp),
        "wasted_offer_pct": round(100.0 * fp / targeted, 2),
        "precision_pct": round(100.0 * prec, 2),
        "recall_pct": round(100.0 * rec, 2),
        "f1_score": round(float(f1), 4),
        "lift_over_random": round(float(prec / base_churn_rate), 2),
    })

for thr in [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]:
    mask = p_test_final >= thr
    tn, fp, fn, tp = confusion_matrix(y_test, mask.astype(int)).ravel()
    targeted = int(tp + fp)
    prec = tp / targeted if targeted else 0.0
    rec = tp / y_test.sum()
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    thresh_rows.append({
        "rule_type": "prob_threshold",
        "rule_label": f"Prob >= {thr:.2f}",
        "prob_cutoff": thr,
        "targeted_players": targeted,
        "pct_of_active_base": round(100.0 * targeted / len(y_test), 2),
        "true_churners_caught_tp": int(tp),
        "wasted_offers_fp": int(fp),
        "wasted_offer_pct": round(100.0 * fp / targeted, 2) if targeted else 0.0,
        "precision_pct": round(100.0 * prec, 2),
        "recall_pct": round(100.0 * rec, 2),
        "f1_score": round(float(f1), 4),
        "lift_over_random": round(float(prec / base_churn_rate), 2) if targeted else 0.0,
    })

df_thresh = pd.DataFrame(thresh_rows)
df_thresh.to_csv(OUT_TABLES / "task_4_threshold_analysis.csv", index=False)

# Subgroup error analysis on Test Set
df_test_eval = df_test.copy()
df_test_eval["pred_prob"] = p_test_final
df_test_eval["install_age_bucket"] = pd.cut(
    df_test_eval["install_age_days"], bins=[-1, 7, 30, 90, 9999], labels=["0-7d (New)", "8-30d", "31-90d", "91+d (Veteran)"]
)
sub_rows = []
for col in ["platform", "country_tier", "acquisition_channel", "install_age_bucket", "is_payer_lifetime"]:
    for val, grp in df_test_eval.groupby(col, observed=False):
        auc_s = roc_auc_score(grp["churn_14d"], grp["pred_prob"]) if grp["churn_14d"].nunique() > 1 else np.nan
        brier_s = brier_score_loss(grp["churn_14d"], grp["pred_prob"])
        sub_rows.append({
            "subgroup_type": col,
            "subgroup_value": str(val),
            "n_players": len(grp),
            "actual_churn_pct": round(100.0 * grp["churn_14d"].mean(), 2),
            "mean_pred_prob_pct": round(100.0 * grp["pred_prob"].mean(), 2),
            "roc_auc": round(float(auc_s), 4),
            "brier_score": round(float(brier_s), 4),
        })
df_sub = pd.DataFrame(sub_rows)
df_sub.to_csv(OUT_TABLES / "task_4_subgroup_errors.csv", index=False)

# ---------------------------------------------------------------------------
# 6. Business Cost-Value Scenario Analysis (on Test Set n=38,644)
# ---------------------------------------------------------------------------
# Expected Net Value = (TP * save_rate * retained_value) - (Targeted * offer_cost)
# Theoretical Bayes-optimal threshold: p* = offer_cost / (save_rate * retained_value)
scen_rows = []
for offer_cost in [0.25, 0.50, 1.00]:
    for ret_val in [5.0, 10.0, 20.0]:
        for save_rate in [0.15, 0.25]:
            p_star = offer_cost / (save_rate * ret_val)
            # Evaluate at Bayes-optimal threshold (clamped to <=1) AND at Top 20% and Top 30%
            for label, mask in [
                (f"Optimal p*>={min(p_star, 1.0):.2f}", p_test_final >= p_star),
                ("Top 20% Targeted", p_test_final >= np.percentile(p_test_final, 80)),
                ("Top 30% Targeted", p_test_final >= np.percentile(p_test_final, 70)),
                ("Target Everyone (No Model)", np.ones(len(y_test), dtype=bool)),
            ]:
                targeted = int(mask.sum())
                tp = int((y_test[mask] == 1).sum())
                fp = targeted - tp
                gross_saved = tp * save_rate * ret_val
                tot_cost = targeted * offer_cost
                net_val = gross_saved - tot_cost
                scen_rows.append({
                    "offer_cost_usd": offer_cost,
                    "retained_value_usd": ret_val,
                    "assumed_save_rate": save_rate,
                    "breakeven_prob_p_star": round(p_star, 4),
                    "strategy": label,
                    "targeted_players": targeted,
                    "true_churners_tp": tp,
                    "wasted_offers_fp": fp,
                    "total_offer_cost_usd": round(tot_cost, 2),
                    "expected_saved_value_usd": round(gross_saved, 2),
                    "expected_net_value_usd": round(net_val, 2),
                })
df_scen = pd.DataFrame(scen_rows)
df_scen.to_csv(OUT_TABLES / "task_4_cost_value_scenarios.csv", index=False)

print("\n=== MODEL COMPARISON SUMMARY (TEST SET, N=38,644) ===")
print(df_comp[df_comp["split"].isin(["test_thr_0.50", "test_opt_f1", "test_unseen_players_opt_f1"])][
    ["model", "split", "threshold", "roc_auc", "pr_auc", "brier_score", "precision", "recall", "f1_score"]
].to_string(index=False))

print("\n=== TARGETING THRESHOLDS (FINAL LOGISTIC REGRESSION, TEST) ===")
print(df_thresh[["rule_label", "prob_cutoff", "targeted_players", "true_churners_caught_tp", "wasted_offer_pct", "precision_pct", "recall_pct", "lift_over_random"]].to_string(index=False))

# ---------------------------------------------------------------------------
# 7. Generate 4 Charts
# ---------------------------------------------------------------------------

# CHART 1: task_4_eda_churn_drivers.png
fig, axes = plt.subplots(2, 2, figsize=(13, 9))

# Panel A: Recency evidence
axes[0, 0].bar(df_def["recency_bucket"].astype(str), df_def["churn_14d_pct"], color="#4e79a7")
axes[0, 0].set_title("14-Day Churn Rate by Days Since Last Activity\n(As of Mar 15: Justifies 7d-Active Population)", fontweight="bold")
axes[0, 0].set_ylabel("Did Not Play in Next 14d (%)")
axes[0, 0].tick_params(axis="x", rotation=22)
for i, v in enumerate(df_def["churn_14d_pct"]):
    axes[0, 0].text(i, v + 1, f"{v:.1f}%", ha="center", fontsize=8.5)
axes[0, 0].set_ylim(0, 62)

# Panel B: Churn by Country Tier & Platform (Test cohort)
eda_t = df_eda[(df_eda["split"] == "test") & (df_eda["segment_type"] == "country_tier")]
axes[0, 1].bar(eda_t["segment_value"].map(lambda s: f"Tier {s}"), eda_t["churn_rate_pct"], color="#f28e2b", width=0.5)
axes[0, 1].set_title("Test Churn Rate by Country Tier (Apr 16)", fontweight="bold")
axes[0, 1].set_ylabel("14-Day Churn Rate (%)")
axes[0, 1].set_ylim(0, 26)
for i, v in enumerate(eda_t["churn_rate_pct"]):
    axes[0, 1].text(i, v + 0.5, f"{v:.1f}%", ha="center", fontsize=9)

# Panel C: Churn by Install Age Bucket (Test cohort)
eda_a = df_eda[(df_eda["split"] == "test") & (df_eda["segment_type"] == "install_age_bucket")]
axes[1, 0].bar(eda_a["segment_value"], eda_a["churn_rate_pct"], color="#e15759", width=0.55)
axes[1, 0].set_title("Test Churn Rate by Install Age\n(Veteran Active Players Show Highest 14d Lapses)", fontweight="bold")
axes[1, 0].set_ylabel("14-Day Churn Rate (%)")
axes[1, 0].set_ylim(0, 42)
for i, v in enumerate(eda_a["churn_rate_pct"]):
    axes[1, 0].text(i, v + 0.8, f"{v:.1f}%", ha="center", fontsize=9)

# Panel D: Active Days in Last 14d vs Churn Rate (Test cohort)
act_bin = df_test.groupby(df_test["act_14d"].clip(upper=8))["churn_14d"].agg(["count", "mean"]).reset_index()
axes[1, 1].plot(act_bin["act_14d"], 100.0 * act_bin["mean"], marker="o", linewidth=2.2, color="#2ca02c")
axes[1, 1].set_xticks(act_bin["act_14d"])
axes[1, 1].set_xticklabels([str(x) if x < 8 else "8+" for x in act_bin["act_14d"]])
axes[1, 1].set_title("14-Day Churn Rate by Recent Active Days (Last 14d)", fontweight="bold")
axes[1, 1].set_xlabel("Active Days in Past 14 Days")
axes[1, 1].set_ylabel("14-Day Churn Rate (%)")
for _, r_a in act_bin.iterrows():
    axes[1, 1].text(r_a["act_14d"], 100.0 * r_a["mean"] + 0.8, f"{100*r_a['mean']:.1f}%", ha="center", fontsize=8)
axes[1, 1].set_ylim(0, 32)

fig.suptitle("Deliverable 4: Exploratory Churn Patterns & Definition Evidence", fontsize=14, fontweight="bold", y=1.01)
fig.tight_layout()
fig.savefig(OUT_CHARTS / "task_4_eda_churn_drivers.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# CHART 2: task_4_model_evaluation.png (ROC, PR, Calibration on Test)
fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))
plot_models = [
    ("Baseline (Recency Rule Only)", "#bab0ac", "--"),
    (f"Logistic Regression (C={best_c})", "#1f77b4", "-"),
    ("Decision Tree (depth=5, leaf=100)", "#ff7f0e", "-."),
    ("HistGradientBoosting (depth=4)", "#2ca02c", ":"),
]
for m_lbl, col, ls in plot_models:
    probs = test_probs_dict[m_lbl]
    fpr, tpr, _ = roc_curve(y_test, probs)
    auc_v = roc_auc_score(y_test, probs)
    axes[0].plot(fpr, tpr, label=f"{m_lbl.split(' (')[0]} (AUC={auc_v:.3f})", color=col, linestyle=ls, linewidth=2)

    prec, rec, _ = precision_recall_curve(y_test, probs)
    ap_v = average_precision_score(y_test, probs)
    axes[1].plot(rec, prec, label=f"{m_lbl.split(' (')[0]} (PR={ap_v:.3f})", color=col, linestyle=ls, linewidth=2)

    if m_lbl != "Baseline (Recency Rule Only)":
        frac_pos, mean_pred = calibration_curve(y_test, probs, n_bins=10, strategy="quantile")
        axes[2].plot(mean_pred, frac_pos, marker="o", label=m_lbl.split(" (")[0], color=col, linewidth=1.8)

axes[0].plot([0, 1], [0, 1], "k:", alpha=0.5)
axes[0].set_title("ROC Curve (Test Set, n=38,644)", fontweight="bold")
axes[0].set_xlabel("False Positive Rate")
axes[0].set_ylabel("True Positive Rate (Recall)")
axes[0].legend(fontsize=8, loc="lower right")

axes[1].axhline(base_churn_rate, color="k", linestyle=":", alpha=0.6, label=f"Random ({base_churn_rate:.1%})")
axes[1].set_title("Precision-Recall Curve (Test Set)", fontweight="bold")
axes[1].set_xlabel("Recall (Churners Caught)")
axes[1].set_ylabel("Precision (1 - Wasted %)")
axes[1].legend(fontsize=8, loc="upper right")

axes[2].plot([0, 0.5], [0, 0.5], "k--", alpha=0.6, label="Perfect Calibration")
axes[2].set_title("Probability Calibration (10 Quantile Bins)", fontweight="bold")
axes[2].set_xlabel("Predicted Churn Probability")
axes[2].set_ylabel("Observed Churn Fraction")
axes[2].legend(fontsize=8, loc="upper left")

fig.suptitle("Deliverable 4: Model Comparison on Out-of-Time Test Set (2026-04-16)", fontsize=13.5, fontweight="bold", y=1.02)
fig.tight_layout()
fig.savefig(OUT_CHARTS / "task_4_model_evaluation.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# CHART 3: task_4_targeting_tradeoffs.png (Top-K Targeting Tradeoffs & Top LR Coefficients)
fig, axes = plt.subplots(1, 2, figsize=(14, 5.2))

sub_topk = df_thresh[df_thresh["rule_type"] == "top_k_pct"].copy()
x_k = np.arange(len(sub_topk))
w_k = 0.27
axes[0].bar(x_k - w_k, sub_topk["precision_pct"], width=w_k, label="Precision % (True Churners)", color="#2ca02c")
axes[0].bar(x_k, sub_topk["recall_pct"], width=w_k, label="Recall % (% of All Churners Caught)", color="#1f77b4")
axes[0].bar(x_k + w_k, sub_topk["wasted_offer_pct"], width=w_k, label="Wasted Offers % (False Positives)", color="#d62728")
axes[0].set_xticks(x_k)
axes[0].set_xticklabels(sub_topk["rule_label"], rotation=15)
axes[0].set_ylabel("Percentage (%)")
axes[0].set_ylim(0, 95)
axes[0].set_title("Targeting Trade-Offs by Risk Percentile (Test Set)\nHigher Precision Means Fewer Wasted Offers, Lower Recall", fontweight="bold")
axes[0].legend(fontsize=8)
for idx, r_k in sub_topk.reset_index(drop=True).iterrows():
    axes[0].text(idx - w_k, r_k["precision_pct"] + 1.5, f"{r_k['precision_pct']:.0f}%", ha="center", fontsize=7.5)
    axes[0].text(idx, r_k["recall_pct"] + 1.5, f"{r_k['recall_pct']:.0f}%", ha="center", fontsize=7.5)
    axes[0].text(idx + w_k, r_k["wasted_offer_pct"] + 1.5, f"{r_k['wasted_offer_pct']:.0f}%", ha="center", fontsize=7.5)

top_imp = df_imp.head(12).iloc[::-1]
cols_imp = ["#d62728" if v > 0 else "#2ca02c" for v in top_imp["std_log_odds_coef"]]
axes[1].barh(top_imp["feature"], top_imp["std_log_odds_coef"], color=cols_imp)
axes[1].axvline(0, color="black", linewidth=0.8)
axes[1].set_xlabel("Standardized Log-Odds Coefficient (+ = Higher Churn Risk)")
axes[1].set_title("Top 12 Logistic Regression Predictors\n(Red = Increases Risk; Green = Protects Against Churn)", fontweight="bold")

fig.tight_layout()
fig.savefig(OUT_CHARTS / "task_4_targeting_tradeoffs.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# CHART 4: task_4_cost_value_heatmap.png (Net Expected Value across Cost & Value Scenarios)
fig, axes = plt.subplots(1, 2, figsize=(13.5, 5))
for ax, sr, title in [
    (axes[0], 0.15, "Assumed Save Rate = 15% (Conservative)"),
    (axes[1], 0.25, "Assumed Save Rate = 25% (Optimistic)"),
]:
    sub_sc = df_scen[(df_scen["assumed_save_rate"] == sr) & (df_scen["strategy"].str.startswith("Optimal"))].copy()
    piv_sc = sub_sc.pivot(index="offer_cost_usd", columns="retained_value_usd", values="expected_net_value_usd")
    sns.heatmap(piv_sc, annot=True, fmt=",.0f", cmap="RdYlGn", center=0, ax=ax, cbar_kws={"label": "Expected Net Value ($)"})
    ax.set_title(f"{title}\nOptimal Model Threshold Net Value ($)", fontweight="bold")
    ax.set_xlabel("Assumed Retained Player Value ($)")
    ax.set_ylabel("Offer Cost per Targeted Player ($)")

fig.suptitle("Deliverable 4: Live-Ops Targeting Value Under Cost & Retention Assumptions (Test n=38,644)", fontsize=13, fontweight="bold", y=1.02)
fig.tight_layout()
fig.savefig(OUT_CHARTS / "task_4_cost_value_heatmap.png", dpi=150, bbox_inches="tight")
plt.close(fig)

print("\nAll Deliverable 4 CSVs and charts generated successfully.")
