"""Dự báo gross Quantity theo StockCode cho tuần kế tiếp.

So sánh 4 cách: Lag-1, trung bình 4 tuần, XGBoost Poisson trực tiếp
và XGBoost hai tầng (có bán? -> nếu bán thì bao nhiêu?).
Mọi feature chỉ dùng quá khứ; train/validation/test được chia theo thời gian.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    average_precision_score, brier_score_loss, f1_score, mean_absolute_error,
    mean_squared_error, r2_score, roc_auc_score,
)
from xgboost import XGBClassifier, XGBRegressor


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "online_retail_II.csv"
OUTPUT = ROOT / "product_demand_forecast_outputs"
RANDOM_STATE = 42
MIN_HISTORY_WEEKS = 13
ACTIVE_WITHIN_WEEKS = 13
VALIDATION_WEEKS = 8
TEST_WEEKS = 8
BACKTEST_WINDOWS = 4


def make_logger() -> logging.Logger:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("product_forecast")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(message)s", datefmt="%H:%M:%S")
    for handler in (logging.StreamHandler(sys.stdout), logging.FileHandler(OUTPUT / "forecast.log", mode="w", encoding="utf-8")):
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def step(logger: logging.Logger, number: int, title: str, reason: str) -> float:
    logger.info("")
    logger.info("=" * 76)
    logger.info("BƯỚC %s - %s", number, title)
    logger.info("Vì sao: %s", reason)
    return time.perf_counter()


def done(logger: logging.Logger, started: float) -> None:
    logger.info("Hoàn thành trong %.2f giây.", time.perf_counter() - started)


def regression_metrics(actual, predicted) -> dict[str, float]:
    actual = np.asarray(actual, dtype=float)
    predicted = np.clip(np.asarray(predicted, dtype=float), 0, None)
    return {
        "MAE": float(mean_absolute_error(actual, predicted)),
        "RMSE": float(mean_squared_error(actual, predicted) ** 0.5),
        "R2": float(r2_score(actual, predicted)),
        "WMAPE": float(np.abs(actual - predicted).sum() / max(np.abs(actual).sum(), 1e-12)),
        "RMSLE": float(np.mean((np.log1p(actual) - np.log1p(predicted)) ** 2) ** 0.5),
    }


def classification_metrics(actual, probability, threshold) -> dict[str, float]:
    actual = np.asarray(actual)
    probability = np.clip(np.asarray(probability), 1e-6, 1 - 1e-6)
    predicted = probability >= threshold
    return {
        "threshold": float(threshold),
        "F1": float(f1_score(actual, predicted, zero_division=0)),
        "ROC_AUC": float(roc_auc_score(actual, probability)),
        "PR_AUC": float(average_precision_score(actual, probability)),
        "Brier": float(brier_score_loss(actual, probability)),
    }


def best_f1_threshold(actual, probability) -> float:
    candidates = np.linspace(0.05, 0.95, 181)
    scores = [f1_score(actual, np.asarray(probability) >= value, zero_division=0) for value in candidates]
    return float(candidates[int(np.argmax(scores))])


def ranking_metrics(frame: pd.DataFrame, prediction_column: str, k: int) -> dict[str, float]:
    """Precision@K và NDCG@K trung bình qua các tuần test."""
    precisions, ndcgs = [], []
    for _, week_data in frame.groupby("Week", observed=True):
        k_used = min(k, len(week_data))
        predicted_top = week_data.nlargest(k_used, prediction_column)
        actual_top_codes = set(week_data.nlargest(k_used, "quantity")["StockCode"])
        precisions.append(predicted_top["StockCode"].isin(actual_top_codes).mean())
        gains = predicted_top["quantity"].to_numpy(dtype=float)
        discounts = 1 / np.log2(np.arange(2, k_used + 2))
        dcg = float(np.sum(gains * discounts))
        ideal = week_data.nlargest(k_used, "quantity")["quantity"].to_numpy(dtype=float)
        idcg = float(np.sum(ideal * discounts))
        ndcgs.append(dcg / idcg if idcg else 0.0)
    return {f"Precision@{k}": float(np.mean(precisions)), f"NDCG@{k}": float(np.mean(ndcgs))}


def load_sales(logger: logging.Logger) -> tuple[pd.DataFrame, dict[str, int]]:
    raw = pd.read_csv(DATA, encoding="latin1", low_memory=False)
    raw["InvoiceDate"] = pd.to_datetime(raw["InvoiceDate"], errors="coerce")
    for column in ["Quantity", "Price"]:
        raw[column] = pd.to_numeric(raw[column], errors="coerce")
    dedup = raw.drop_duplicates()
    valid = (
        dedup["InvoiceDate"].notna() & dedup["StockCode"].notna()
        & (dedup["Quantity"] > 0) & (dedup["Price"] > 0)
        & ~dedup["Invoice"].astype(str).str.startswith("C", na=False)
    )
    sales = dedup.loc[valid].copy()
    sales["StockCode"] = sales["StockCode"].astype(str).str.strip()
    standard = sales["StockCode"].str.match(r"^\d{5}[A-Z]?$", na=False)
    removed_nonstandard = int((~standard).sum())
    sales = sales.loc[standard].copy()
    sales["Week"] = sales["InvoiceDate"].dt.to_period("W-SUN")
    first_timestamp, last_timestamp = sales["InvoiceDate"].min(), sales["InvoiceDate"].max()
    first_week, last_week = first_timestamp.to_period("W-SUN"), last_timestamp.to_period("W-SUN")
    boundary = []
    if first_timestamp.normalize() > first_week.start_time.normalize(): boundary.append(first_week)
    if last_timestamp.normalize() < last_week.end_time.normalize(): boundary.append(last_week)
    sales = sales.loc[~sales["Week"].isin(boundary)].copy()
    description = sales.groupby("StockCode")["Description"].agg(lambda x: x.dropna().mode().iloc[0] if not x.dropna().mode().empty else "")
    logger.info("Giữ %s dòng gross sales và %s mã hàng chuẩn.", f"{len(sales):,}", f"{sales['StockCode'].nunique():,}")
    return sales, {"removed_nonstandard_rows": removed_nonstandard, "descriptions": description.to_dict()}


def make_panel(sales: pd.DataFrame) -> tuple[pd.DataFrame, pd.Period, pd.Period]:
    observed = sales.groupby(["StockCode", "Week"], observed=True).agg(quantity=("Quantity", "sum"), invoices=("Invoice", "nunique"), price=("Price", "median")).reset_index()
    last_week = observed["Week"].max()
    forecast_week = last_week + 1
    starts = observed.groupby("StockCode")["Week"].min()
    index = pd.MultiIndex.from_tuples(
        [(code, week) for code, first in starts.items() for week in pd.period_range(first, forecast_week, freq="W-SUN")],
        names=["StockCode", "Week"],
    )
    panel = observed.set_index(["StockCode", "Week"]).reindex(index).reset_index().sort_values(["StockCode", "Week"])
    historical = panel["Week"] <= last_week
    panel.loc[historical, ["quantity", "invoices"]] = panel.loc[historical, ["quantity", "invoices"]].fillna(0)
    return panel, last_week, forecast_week


def add_features(panel: pd.DataFrame, last_week: pd.Period) -> tuple[pd.DataFrame, list[str]]:
    grouped = panel.groupby("StockCode", sort=False)
    features = []
    for lag in [1, 2, 3, 4, 8, 13, 26, 52]:
        name = f"quantity_lag{lag}"
        panel[name] = grouped["quantity"].shift(lag)
        features.append(name)
    for window in [4, 8, 13, 26]:
        mean_name, active_name = f"quantity_mean_{window}", f"active_rate_{window}"
        panel[mean_name] = grouped["quantity"].transform(lambda x: x.shift(1).rolling(window, min_periods=1).mean())
        panel[active_name] = grouped["quantity"].transform(lambda x: x.shift(1).gt(0).rolling(window, min_periods=1).mean())
        features += [mean_name, active_name]
    for window in [4, 13]:
        name = f"quantity_std_{window}"
        panel[name] = grouped["quantity"].transform(lambda x: x.shift(1).rolling(window, min_periods=2).std())
        features.append(name)
    panel["tenure_weeks"] = grouped.cumcount()
    position = panel["tenure_weeks"].astype(float)
    was_active = grouped["quantity"].shift(1).gt(0)
    last_active_position = position.where(was_active).groupby(panel["StockCode"]).ffill()
    panel["weeks_since_last_sale"] = (position - last_active_position).fillna(position + 1)
    week_number = panel["Week"].dt.week.astype(float)
    panel["week_sin"] = np.sin(2 * np.pi * week_number / 52)
    panel["week_cos"] = np.cos(2 * np.pi * week_number / 52)
    features += ["tenure_weeks", "weeks_since_last_sale", "week_sin", "week_cos"]

    market = panel.loc[panel["Week"] <= last_week].groupby("Week")["quantity"].sum().reindex(pd.period_range(panel["Week"].min(), last_week, freq="W-SUN"), fill_value=0)
    market = pd.DataFrame({"Week": market.index, "market_quantity": market.values})
    market["market_lag1"] = market["market_quantity"].shift(1)
    market["market_mean_4"] = market["market_quantity"].shift(1).rolling(4, min_periods=1).mean()
    future_market = pd.DataFrame({"Week": [last_week + 1], "market_lag1": [market.iloc[-1]["market_quantity"]], "market_mean_4": [market.tail(4)["market_quantity"].mean()]})
    market_features = pd.concat([market[["Week", "market_lag1", "market_mean_4"]], future_market], ignore_index=True)
    panel = panel.merge(market_features, on="Week", how="left")
    features += ["market_lag1", "market_mean_4"]
    panel[features] = panel[features].fillna(0)
    return panel, features


def xgb_regressor(objective: str) -> XGBRegressor:
    return XGBRegressor(objective=objective, n_estimators=450, max_depth=7, learning_rate=0.04, subsample=0.8, colsample_bytree=0.8, min_child_weight=5, reg_lambda=2, random_state=RANDOM_STATE, n_jobs=-1, tree_method="hist")


def evaluate_backtest_window(
    history: pd.DataFrame,
    features: list[str],
    test_start: pd.Period,
    test_end: pd.Period,
) -> dict[str, dict[str, float]]:
    """Train lại và đánh giá một cửa sổ 8 tuần, chỉ dùng dữ liệu trước nó."""
    validation_start = test_start - VALIDATION_WEEKS
    train = history.loc[history["Week"] < validation_start]
    validation = history.loc[(history["Week"] >= validation_start) & (history["Week"] < test_start)]
    test = history.loc[(history["Week"] >= test_start) & (history["Week"] <= test_end)].copy()
    if train.empty or validation.empty or test.empty:
        raise ValueError(f"Không đủ dữ liệu cho backtest {test_start} -> {test_end}")

    X_train, X_validation, X_test = train[features], validation[features], test[features]
    test["NaiveLag1"] = X_test["quantity_lag1"]
    test["MovingAverage4"] = X_test["quantity_mean_4"]
    direct = xgb_regressor("count:poisson").fit(X_train, train["quantity"])
    test["XGBoostPoisson"] = direct.predict(X_test)

    classifier = XGBClassifier(
        objective="binary:logistic", eval_metric="logloss", n_estimators=400,
        max_depth=6, learning_rate=0.04, subsample=0.8, colsample_bytree=0.8,
        min_child_weight=5, reg_lambda=2, random_state=RANDOM_STATE,
        n_jobs=-1, tree_method="hist",
    ).fit(X_train, train["will_sell"])
    raw_validation_probability = classifier.predict_proba(X_validation)[:, 1]
    calibrator = IsotonicRegression(out_of_bounds="clip").fit(
        raw_validation_probability, validation["will_sell"]
    )
    validation_probability = calibrator.predict(raw_validation_probability)
    threshold = best_f1_threshold(validation["will_sell"], validation_probability)
    test_probability = calibrator.predict(classifier.predict_proba(X_test)[:, 1])

    positive_train = train["will_sell"] == 1
    conditional = xgb_regressor("reg:squarederror").fit(
        X_train.loc[positive_train], np.log1p(train.loc[positive_train, "quantity"])
    )
    positive_validation = validation["will_sell"] == 1
    validation_log_prediction = conditional.predict(X_validation.loc[positive_validation])
    smearing = float(np.mean(np.exp(
        np.log1p(validation.loc[positive_validation, "quantity"])
        - validation_log_prediction
    )))
    quantity_if_sold = np.clip(
        np.exp(conditional.predict(X_test)) * smearing - 1, 0, None
    )
    test["TwoStageExpected"] = test_probability * quantity_if_sold
    test["TwoStageHardGate"] = np.where(
        test_probability >= threshold, quantity_if_sold, 0
    )

    results = {}
    for name in ["NaiveLag1", "MovingAverage4", "XGBoostPoisson", "TwoStageExpected", "TwoStageHardGate"]:
        results[name] = regression_metrics(test["quantity"], test[name])
        for k in [10, 20, 50]:
            results[name].update(ranking_metrics(test, name, k))
    return results


def main() -> None:
    logger = make_logger()
    report: dict[str, object] = {}
    started = step(logger, 1, "Tiền xử lý", "Dùng gross sales, giữ giao dịch thiếu Customer ID và loại mã không giống hàng hóa.")
    sales, audit = load_sales(logger)
    panel, last_week, forecast_week = make_panel(sales)
    panel, features = add_features(panel, last_week)
    descriptions = audit.pop("descriptions")
    report["audit"] = audit
    done(logger, started)

    started = step(logger, 2, "Chia theo thời gian", "Validation chọn threshold/calibration; test chỉ đánh giá tương lai.")
    history = panel.loc[(panel["Week"] <= last_week) & (panel["tenure_weeks"] >= MIN_HISTORY_WEEKS)].copy()
    history["will_sell"] = (history["quantity"] > 0).astype("int8")
    test_start, validation_start = last_week - (TEST_WEEKS - 1), last_week - (TEST_WEEKS + VALIDATION_WEEKS - 1)
    train = history.loc[history["Week"] < validation_start]
    validation = history.loc[(history["Week"] >= validation_start) & (history["Week"] < test_start)]
    test = history.loc[history["Week"] >= test_start].copy()
    logger.info("Train %s -> %s; validation %s -> %s; test %s -> %s.", train["Week"].min(), train["Week"].max(), validation["Week"].min(), validation["Week"].max(), test["Week"].min(), test["Week"].max())
    report["split"] = {"train_rows": len(train), "validation_rows": len(validation), "test_rows": len(test), "test_start": str(test_start), "test_end": str(last_week)}
    done(logger, started)

    started = step(logger, 3, "Train các model", "Không giả định model phức tạp sẽ thắng; luôn so với baseline.")
    X_train, X_val, X_test = train[features], validation[features], test[features]
    direct = xgb_regressor("count:poisson").fit(X_train, train["quantity"])
    test["NaiveLag1"] = X_test["quantity_lag1"]
    test["MovingAverage4"] = X_test["quantity_mean_4"]
    test["XGBoostPoisson"] = direct.predict(X_test)

    classifier = XGBClassifier(objective="binary:logistic", eval_metric="logloss", n_estimators=400, max_depth=6, learning_rate=0.04, subsample=0.8, colsample_bytree=0.8, min_child_weight=5, reg_lambda=2, random_state=RANDOM_STATE, n_jobs=-1, tree_method="hist")
    classifier.fit(X_train, train["will_sell"])
    raw_val_probability = classifier.predict_proba(X_val)[:, 1]
    calibrator = IsotonicRegression(out_of_bounds="clip").fit(raw_val_probability, validation["will_sell"])
    calibrated_val_probability = calibrator.predict(raw_val_probability)
    threshold = best_f1_threshold(validation["will_sell"], calibrated_val_probability)
    test_probability = calibrator.predict(classifier.predict_proba(X_test)[:, 1])

    positive_train = train["will_sell"] == 1
    conditional = xgb_regressor("reg:squarederror").fit(X_train.loc[positive_train], np.log1p(train.loc[positive_train, "quantity"]))
    positive_val = validation["will_sell"] == 1
    val_log_prediction = conditional.predict(X_val.loc[positive_val])
    smearing = float(np.mean(np.exp(np.log1p(validation.loc[positive_val, "quantity"]) - val_log_prediction)))
    quantity_if_sold = np.clip(np.exp(conditional.predict(X_test)) * smearing - 1, 0, None)
    test["TwoStageExpected"] = test_probability * quantity_if_sold
    test["TwoStageHardGate"] = np.where(test_probability >= threshold, quantity_if_sold, 0)
    report["classification"] = classification_metrics(test["will_sell"], test_probability, threshold)
    done(logger, started)

    started = step(logger, 4, "Đánh giá", "MAE/WMAPE đo sai số lượng; Precision@K/NDCG@K đo khả năng tìm đúng hàng bán chạy.")
    model_names = ["NaiveLag1", "MovingAverage4", "XGBoostPoisson", "TwoStageExpected", "TwoStageHardGate"]
    metrics = {}
    for name in model_names:
        metrics[name] = regression_metrics(test["quantity"], test[name])
        for k in [10, 20, 50]: metrics[name].update(ranking_metrics(test, name, k))
        logger.info("%-20s MAE=%8.2f WMAPE=%6.3f Precision@20=%.3f NDCG@20=%.3f", name, metrics[name]["MAE"], metrics[name]["WMAPE"], metrics[name]["Precision@20"], metrics[name]["NDCG@20"])
    report["test_metrics"] = metrics
    test_export = test[["StockCode", "Week", "quantity"] + model_names].copy()
    test_export["Week"] = test_export["Week"].astype(str)
    test_export.to_csv(OUTPUT / "test_predictions.csv", index=False, encoding="utf-8-sig")
    done(logger, started)

    started = step(logger, 4.5, "Rolling backtest", "Danh gia model qua nhieu giai doan 8 tuan, thay vi ket luan tu mot test duy nhat.")
    backtest_rows = []
    for window_index in range(BACKTEST_WINDOWS):
        window_end = last_week - window_index * TEST_WEEKS
        window_start = window_end - (TEST_WEEKS - 1)
        window_metrics = metrics if window_index == 0 else evaluate_backtest_window(
            history, features, window_start, window_end
        )
        for model_name, model_metrics in window_metrics.items():
            backtest_rows.append({
                "window": window_index + 1,
                "test_start": str(window_start),
                "test_end": str(window_end),
                "model": model_name,
                **model_metrics,
            })
        logger.info("Backtest %s/%s: %s -> %s.", window_index + 1, BACKTEST_WINDOWS, window_start, window_end)

    backtest_details = pd.DataFrame(backtest_rows)
    metric_columns = [
        "MAE", "RMSE", "R2", "WMAPE", "RMSLE",
        "Precision@10", "NDCG@10", "Precision@20", "NDCG@20",
        "Precision@50", "NDCG@50",
    ]
    backtest_summary = backtest_details.groupby("model")[metric_columns].agg(["mean", "std"])
    backtest_summary.columns = [f"{metric}_{stat}" for metric, stat in backtest_summary.columns]
    backtest_summary = backtest_summary.reset_index().sort_values(
        ["NDCG@20_mean", "MAE_mean"], ascending=[False, True]
    ).reset_index(drop=True)
    recommended_model = str(backtest_summary.iloc[0]["model"])
    backtest_details.to_csv(OUTPUT / "rolling_backtest_details.csv", index=False, encoding="utf-8-sig")
    backtest_summary.to_csv(OUTPUT / "rolling_backtest_summary.csv", index=False, encoding="utf-8-sig")
    report["rolling_backtest"] = {
        "number_of_windows": BACKTEST_WINDOWS,
        "weeks_per_window": TEST_WEEKS,
        "selection_metric": "Highest mean NDCG@20; lowest mean MAE breaks ties",
        "recommended_model": recommended_model,
        "summary": json.loads(backtest_summary.to_json(orient="records")),
    }
    logger.info("Model duoc chon sau rolling backtest: %s.", recommended_model)
    done(logger, started)

    started = step(logger, 5, "Dự báo tuần kế tiếp", "Refit bằng toàn bộ lịch sử và chỉ xếp hạng sản phẩm còn hoạt động.")
    future = panel.loc[(panel["Week"] == forecast_week) & (panel["tenure_weeks"] >= MIN_HISTORY_WEEKS) & (panel["weeks_since_last_sale"] <= ACTIVE_WITHIN_WEEKS)].copy()
    X_all, X_future = history[features], future[features]
    direct_final = xgb_regressor("count:poisson").fit(X_all, history["quantity"])
    final_calibration_start = last_week - (VALIDATION_WEEKS - 1)
    base = history["Week"] < final_calibration_start
    calibration_rows = history["Week"] >= final_calibration_start
    classifier_final = XGBClassifier(objective="binary:logistic", eval_metric="logloss", n_estimators=400, max_depth=6, learning_rate=0.04, subsample=0.8, colsample_bytree=0.8, min_child_weight=5, reg_lambda=2, random_state=RANDOM_STATE, n_jobs=-1, tree_method="hist").fit(X_all.loc[base], history.loc[base, "will_sell"])
    raw_final_calibration_probability = classifier_final.predict_proba(X_all.loc[calibration_rows])[:, 1]
    final_calibrator = IsotonicRegression(out_of_bounds="clip").fit(raw_final_calibration_probability, history.loc[calibration_rows, "will_sell"])
    final_calibration_probability = final_calibrator.predict(raw_final_calibration_probability)
    final_threshold = best_f1_threshold(
        history.loc[calibration_rows, "will_sell"], final_calibration_probability
    )
    future_probability = final_calibrator.predict(classifier_final.predict_proba(X_future)[:, 1])
    positive_base = base & (history["will_sell"] == 1)
    conditional_final = xgb_regressor("reg:squarederror").fit(X_all.loc[positive_base], np.log1p(history.loc[positive_base, "quantity"]))
    positive_calibration = calibration_rows & (history["will_sell"] == 1)
    final_log_calibration = conditional_final.predict(X_all.loc[positive_calibration])
    final_smearing = float(np.mean(np.exp(np.log1p(history.loc[positive_calibration, "quantity"]) - final_log_calibration)))
    future_if_sold = np.clip(np.exp(conditional_final.predict(X_future)) * final_smearing - 1, 0, None)
    forecast = pd.DataFrame({
        "StockCode": future["StockCode"].to_numpy(),
        "Description": future["StockCode"].map(descriptions).fillna("").to_numpy(),
        "ForecastWeek": str(forecast_week),
        "ProbabilityOfSale": future_probability,
        "QuantityIfSold": future_if_sold,
        "TwoStageExpected": future_probability * future_if_sold,
        "TwoStageHardGate": np.where(future_probability >= final_threshold, future_if_sold, 0),
        "XGBoostPoisson": np.clip(direct_final.predict(X_future), 0, None),
        "NaiveLag1": X_future["quantity_lag1"].to_numpy(),
        "MovingAverage4": X_future["quantity_mean_4"].to_numpy(),
        "WeeksSinceLastSale": future["weeks_since_last_sale"].to_numpy(),
    }).sort_values([recommended_model, "StockCode"], ascending=[False, True])
    forecast.insert(0, "RecommendedRank", np.arange(1, len(forecast) + 1))
    forecast.insert(1, "RecommendedModel", recommended_model)
    forecast.to_csv(OUTPUT / "next_week_product_forecast.csv", index=False, encoding="utf-8-sig")
    forecast.head(50).to_csv(OUTPUT / "top_50_products_next_week.csv", index=False, encoding="utf-8-sig")
    report["forecast"] = {
        "week": str(forecast_week),
        "candidate_products": len(forecast),
        "ranking_column": recommended_model,
        "recommended_model": recommended_model,
        "note": "Top 50 is ranked by the rolling-backtest winner; predictions from every candidate model remain available.",
    }
    report["features"] = features
    with (OUTPUT / "metrics.json").open("w", encoding="utf-8") as file: json.dump(report, file, ensure_ascii=False, indent=2)
    logger.info("Dự báo %s sản phẩm cho %s.", len(forecast), forecast_week)
    logger.info("Top 50: %s", OUTPUT / "top_50_products_next_week.csv")
    done(logger, started)


if __name__ == "__main__":
    main()
