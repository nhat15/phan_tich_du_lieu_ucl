"""Phân tích mô tả dữ liệu Online Retail II theo sản phẩm.

File này chỉ làm ba việc:
1. Audit và tiền xử lý giống product_demand_analysis_runner.py.
2. Phân tích mô tả theo thời gian, sản phẩm, quốc gia và kiểu nhu cầu.
3. Xuất log, JSON, Markdown và CSV. Không train hay đánh giá model.

Target được chuẩn bị cho bước sau là gross Quantity theo StockCode × tuần.
Giao dịch thiếu Customer ID vẫn được giữ vì ta dự báo hàng hóa, không dự báo từng khách.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PROJECT_DIR = Path(__file__).resolve().parent
DATA_PATH = PROJECT_DIR / "online_retail_II.csv"
OUTPUT_DIR = PROJECT_DIR / "product_descriptive_analysis_outputs"
LOG_PATH = OUTPUT_DIR / "descriptive_analysis.log"
JSON_REPORT_PATH = OUTPUT_DIR / "descriptive_report.json"
MARKDOWN_REPORT_PATH = OUTPUT_DIR / "descriptive_report.md"
CHART_DIR = OUTPUT_DIR / "charts"


def configure_logging() -> logging.Logger:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("product_descriptive_analysis")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S"
    )
    for handler in (
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8"),
    ):
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def start_step(logger: logging.Logger, number: int, title: str, reason: str) -> float:
    logger.info("")
    logger.info("=" * 78)
    logger.info("BƯỚC %02d - %s", number, title)
    logger.info("Mục đích: %s", reason)
    return time.perf_counter()


def finish_step(logger: logging.Logger, started_at: float) -> None:
    logger.info("Hoàn thành trong %.2f giây.", time.perf_counter() - started_at)


def pct(part: float, total: float) -> float:
    return float(100 * part / total) if total else 0.0


def numeric_summary(series: pd.Series) -> dict[str, float | int]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return {"count": 0}
    return {
        "count": int(values.size),
        "missing": int(series.isna().sum()),
        "min": float(values.min()),
        "p25": float(values.quantile(0.25)),
        "median": float(values.median()),
        "mean": float(values.mean()),
        "p75": float(values.quantile(0.75)),
        "p90": float(values.quantile(0.90)),
        "p95": float(values.quantile(0.95)),
        "p99": float(values.quantile(0.99)),
        "max": float(values.max()),
        "std": float(values.std()),
    }


def records(frame: pd.DataFrame) -> list[dict]:
    converted = frame.copy()
    for column in converted.columns:
        if isinstance(converted[column].dtype, pd.PeriodDtype):
            converted[column] = converted[column].astype(str)
        elif pd.api.types.is_datetime64_any_dtype(converted[column]):
            converted[column] = converted[column].astype(str)
    return converted.replace({np.nan: None}).to_dict(orient="records")


def most_common_description(values: pd.Series) -> str | None:
    modes = values.dropna().astype(str).str.strip().replace("", np.nan).dropna().mode()
    return None if modes.empty else str(modes.iloc[0])


def save_csv(frame: pd.DataFrame, filename: str) -> None:
    output = frame.copy()
    for column in output.columns:
        if isinstance(output[column].dtype, pd.PeriodDtype):
            output[column] = output[column].astype(str)
    output.to_csv(OUTPUT_DIR / filename, index=False, encoding="utf-8-sig")


def save_figure(filename: str) -> None:
    """Chuẩn hóa layout, lưu PNG và giải phóng bộ nhớ."""
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(CHART_DIR / filename, dpi=160, bbox_inches="tight")
    plt.close()


def product_labels(frame: pd.DataFrame) -> list[str]:
    """Nãn sản phẩm ngắn gọn cho trục biểu đồ."""
    return [
        f"{row.StockCode} | {str(row.description)[:28]}"
        for row in frame.itertuples(index=False)
    ]


def create_charts(
    missing_table: pd.DataFrame,
    weekly_market: pd.DataFrame,
    monthly_market: pd.DataFrame,
    weekday: pd.DataFrame,
    hourly: pd.DataFrame,
    product_summary: pd.DataFrame,
    observed: pd.DataFrame,
    demand_profile: pd.DataFrame,
    type_summary: pd.DataFrame,
    ranked: pd.DataFrame,
    country: pd.DataFrame,
    return_products: pd.DataFrame,
) -> list[str]:
    """Tạo các biểu đồ EDA; mỗi biểu đồ trả lời một câu hỏi."""
    plt.rcParams.update(
        {
            "figure.figsize": (12, 6),
            "axes.grid": True,
            "grid.alpha": 0.25,
            "axes.titlesize": 14,
            "axes.labelsize": 11,
            "font.family": "DejaVu Sans",
        }
    )
    chart_files: list[str] = []

    # 1. Cột nào thiếu nhiều nhất?
    plot_data = missing_table.sort_values("missing_pct")
    plt.figure(figsize=(10, 6))
    plt.barh(plot_data["column"], plot_data["missing_pct"], color="#4C78A8")
    plt.xlabel("Tỷ lệ thiếu (%)")
    plt.title("Tỷ lệ dữ liệu thiếu theo cột")
    for index, value in enumerate(plot_data["missing_pct"]):
        plt.text(value + 0.15, index, f"{value:.2f}%", va="center", fontsize=9)
    filename = "01_missing_values.png"
    save_figure(filename)
    chart_files.append(filename)

    # 2. Thị trường thay đổi thế nào qua từng tuần?
    weekly_dates = weekly_market["Week"].dt.start_time
    plt.figure(figsize=(14, 6))
    plt.plot(weekly_dates, weekly_market["quantity"], color="#9ECAE1", linewidth=1, label="Quantity từng tuần")
    plt.plot(weekly_dates, weekly_market["quantity_ma_4"], color="#D62728", linewidth=2.2, label="Trung bình trượt 4 tuần")
    plt.ylabel("Tổng Quantity")
    plt.xlabel("Tuần")
    plt.title("Xu hướng số lượng bán theo tuần")
    plt.legend()
    filename = "02_weekly_quantity_trend.png"
    save_figure(filename)
    chart_files.append(filename)

    # 3. So sánh Quantity và Revenue theo tháng (hai panel, không trộn thang đo).
    monthly_dates = monthly_market["Month"].dt.start_time
    figure, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    axes[0].plot(monthly_dates, monthly_market["quantity"], marker="o", color="#4C78A8")
    axes[0].set_ylabel("Quantity")
    axes[0].set_title("Số lượng bán theo tháng")
    axes[1].plot(monthly_dates, monthly_market["revenue"], marker="o", color="#F58518")
    axes[1].set_ylabel("Revenue")
    axes[1].set_xlabel("Tháng")
    axes[1].set_title("Doanh thu theo tháng")
    filename = "03_monthly_quantity_revenue.png"
    save_figure(filename)
    chart_files.append(filename)

    # 4. Nhu cầu phân bố theo thứ nào?
    plt.figure(figsize=(10, 6))
    plt.bar(weekday["weekday"], weekday["quantity"], color="#54A24B")
    plt.ylabel("Tổng Quantity")
    plt.xlabel("Thứ trong tuần")
    plt.title("Số lượng bán theo thứ")
    plt.xticks(rotation=25)
    filename = "04_quantity_by_weekday.png"
    save_figure(filename)
    chart_files.append(filename)

    # 5. Hóa đơn thường được ghi nhận vào giờ nào?
    plt.figure(figsize=(10, 6))
    plt.plot(hourly["hour"], hourly["invoices"], marker="o", color="#B279A2")
    plt.xticks(range(0, 24))
    plt.xlabel("Giờ trong ngày")
    plt.ylabel("Số Invoice duy nhất")
    plt.title("Số hóa đơn theo giờ")
    filename = "05_invoices_by_hour.png"
    save_figure(filename)
    chart_files.append(filename)

    # 6. Sản phẩm nào bán nhiều đơn vị nhất?
    top_products = product_summary.nlargest(20, "quantity").sort_values("quantity")
    plt.figure(figsize=(13, 9))
    plt.barh(product_labels(top_products), top_products["quantity"], color="#E45756")
    plt.xlabel("Tổng Quantity")
    plt.title("Top 20 sản phẩm theo số lượng bán")
    filename = "06_top_products_by_quantity.png"
    save_figure(filename)
    chart_files.append(filename)

    # 7. Quantity sản phẩm-tuần lệch phải đến mức nào?
    plt.figure(figsize=(11, 6))
    plt.hist(np.log1p(observed["quantity"]), bins=60, color="#4C78A8", edgecolor="white")
    plt.xlabel("log(1 + Quantity sản phẩm-tuần)")
    plt.ylabel("Số quan sát")
    plt.title("Phân phối nhu cầu dương sau biến đổi log1p")
    filename = "07_product_week_quantity_distribution.png"
    save_figure(filename)
    chart_files.append(filename)

    # 8. Bao nhiêu sản phẩm có nhu cầu gián đoạn?
    plt.figure(figsize=(11, 6))
    plt.hist(demand_profile["zero_rate_pct"], bins=np.arange(0, 105, 5), color="#72B7B2", edgecolor="white")
    plt.xlabel("Tỷ lệ tuần không bán trong vòng đời (%)")
    plt.ylabel("Số sản phẩm")
    plt.title("Phân phối zero-rate theo sản phẩm")
    filename = "08_product_zero_rate_distribution.png"
    save_figure(filename)
    chart_files.append(filename)

    # 9. Bản đồ ADI-CV² phân nhóm nhu cầu.
    colors = {"smooth": "#54A24B", "erratic": "#F58518", "intermittent": "#4C78A8", "lumpy": "#E45756"}
    x_limit = max(1.4, float(demand_profile["adi"].quantile(0.99)))
    y_limit = max(0.55, float(demand_profile["cv_squared"].quantile(0.99)))
    plt.figure(figsize=(11, 7))
    for demand_type, group in demand_profile.groupby("demand_type", observed=True):
        plt.scatter(group["adi"].clip(upper=x_limit), group["cv_squared"].clip(upper=y_limit), s=16, alpha=0.5, label=demand_type, color=colors[demand_type])
    plt.axvline(1.32, color="black", linestyle="--", linewidth=1)
    plt.axhline(0.49, color="black", linestyle="--", linewidth=1)
    plt.xlabel("ADI - khoảng cách trung bình giữa các tuần có bán")
    plt.ylabel("CV² - độ biến động của lượng bán dương")
    plt.title("Phân loại kiểu nhu cầu bằng ADI và CV² (giới hạn ở p99 để dễ nhìn)")
    plt.legend()
    filename = "09_adi_cv2_demand_map.png"
    save_figure(filename)
    chart_files.append(filename)

    # 10. Bao nhiêu phần trăm sản phẩm tạo ra phần lớn Quantity?
    product_percent = 100 * np.arange(1, len(ranked) + 1) / len(ranked)
    plt.figure(figsize=(11, 6))
    plt.plot(product_percent, ranked["quantity_cumulative_pct"], color="#4C78A8", linewidth=2)
    plt.axvline(20, color="#E45756", linestyle="--", label="Top 20% sản phẩm")
    plt.axhline(80, color="#54A24B", linestyle="--", label="80% Quantity")
    plt.xlabel("Tỷ lệ sản phẩm sau khi xếp hạng (%)")
    plt.ylabel("Quantity tích lũy (%)")
    plt.title("Đường cong Pareto của số lượng bán")
    plt.legend()
    filename = "10_quantity_pareto.png"
    save_figure(filename)
    chart_files.append(filename)

    # 11. Thị trường nào chi phối Quantity?
    top_countries = country.head(15).sort_values("quantity")
    plt.figure(figsize=(11, 7))
    plt.barh(top_countries["Country"], top_countries["quantity_share_pct"], color="#59A14F")
    plt.xlabel("Tỷ trọng Quantity toàn bộ dữ liệu (%)")
    plt.title("Top 15 quốc gia theo tỷ trọng số lượng bán")
    filename = "11_country_quantity_share.png"
    save_figure(filename)
    chart_files.append(filename)

    # 12. Sản phẩm nào có nhiều đơn vị trả/hủy nhất?
    top_returns = return_products.head(20).sort_values("returned_units")
    plt.figure(figsize=(12, 8))
    plt.barh(top_returns["StockCode"], top_returns["returned_units"], color="#E45756")
    plt.xlabel("Tổng đơn vị trả/hủy")
    plt.ylabel("StockCode")
    plt.title("Top 20 sản phẩm theo số lượng trả/hủy")
    filename = "12_top_product_returns.png"
    save_figure(filename)
    chart_files.append(filename)

    # 13. Cơ cấu bốn kiểu nhu cầu là gì?
    demand_order = ["smooth", "erratic", "intermittent", "lumpy"]
    demand_colors = [colors[name] for name in demand_order]
    demand_counts = (
        type_summary.set_index("demand_type")["products"]
        .reindex(demand_order, fill_value=0)
    )
    plt.figure(figsize=(10, 6))
    bars = plt.bar(demand_counts.index, demand_counts.values, color=demand_colors)
    plt.ylabel("Số sản phẩm")
    plt.xlabel("Kiểu nhu cầu")
    plt.title("Số sản phẩm theo kiểu nhu cầu")
    plt.bar_label(bars, fmt="%.0f", padding=3)
    filename = "13_demand_type_counts.png"
    save_figure(filename)
    chart_files.append(filename)

    return chart_files


def load_and_preprocess(logger: logging.Logger) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy dữ liệu: {DATA_PATH}")

    raw = pd.read_csv(DATA_PATH, encoding="latin1", low_memory=False)
    raw["InvoiceDate"] = pd.to_datetime(raw["InvoiceDate"], errors="coerce")
    for column in ["Quantity", "Price", "Customer ID"]:
        raw[column] = pd.to_numeric(raw[column], errors="coerce")

    duplicate_mask = raw.duplicated()
    cancelled_mask = raw["Invoice"].astype(str).str.startswith("C", na=False)
    invalid_date_mask = raw["InvoiceDate"].isna()
    missing_stock_mask = raw["StockCode"].isna()
    nonpositive_quantity_mask = raw["Quantity"] <= 0
    nonpositive_price_mask = raw["Price"] <= 0

    deduplicated = raw.loc[~duplicate_mask].copy()
    valid_mask = (
        deduplicated["InvoiceDate"].notna()
        & deduplicated["StockCode"].notna()
        & (deduplicated["Quantity"] > 0)
        & (deduplicated["Price"] > 0)
        & ~deduplicated["Invoice"].astype(str).str.startswith("C", na=False)
    )
    sales = deduplicated.loc[valid_mask].copy()
    sales["StockCode"] = sales["StockCode"].astype(str).str.strip()
    sales["Revenue"] = sales["Quantity"] * sales["Price"]
    sales["Week"] = sales["InvoiceDate"].dt.to_period("W-SUN")
    sales["Month"] = sales["InvoiceDate"].dt.to_period("M")

    first_timestamp = sales["InvoiceDate"].min()
    last_timestamp = sales["InvoiceDate"].max()
    first_week = first_timestamp.to_period("W-SUN")
    last_week = last_timestamp.to_period("W-SUN")
    incomplete_weeks: list[pd.Period] = []
    if first_timestamp.normalize() > first_week.start_time.normalize():
        incomplete_weeks.append(first_week)
    if last_timestamp.normalize() < last_week.end_time.normalize():
        incomplete_weeks.append(last_week)
    incomplete_weeks = list(dict.fromkeys(incomplete_weeks))
    rows_before_week_filter = len(sales)
    sales = sales.loc[~sales["Week"].isin(incomplete_weeks)].copy()

    anonymous_mask = sales["Customer ID"].isna()
    report = {
        "raw_rows": int(len(raw)),
        "raw_columns": int(raw.shape[1]),
        "date_min_raw": str(raw["InvoiceDate"].min()),
        "date_max_raw": str(raw["InvoiceDate"].max()),
        "missing_count": raw.isna().sum().astype(int).to_dict(),
        "missing_pct": (100 * raw.isna().mean()).round(3).to_dict(),
        "exact_duplicate_rows": int(duplicate_mask.sum()),
        "cancelled_rows": int(cancelled_mask.sum()),
        "invalid_date_rows": int(invalid_date_mask.sum()),
        "missing_stock_rows": int(missing_stock_mask.sum()),
        "nonpositive_quantity_rows": int(nonpositive_quantity_mask.sum()),
        "nonpositive_price_rows": int(nonpositive_price_mask.sum()),
        "clean_rows": int(len(sales)),
        "clean_rows_pct": pct(len(sales), len(raw)),
        "removed_incomplete_weeks": [str(week) for week in incomplete_weeks],
        "rows_removed_by_incomplete_week_filter": int(rows_before_week_filter - len(sales)),
        "complete_week_min": str(sales["Week"].min()),
        "complete_week_max": str(sales["Week"].max()),
        "anonymous_rows_clean": int(anonymous_mask.sum()),
        "anonymous_rows_pct_clean": pct(anonymous_mask.sum(), len(sales)),
        "anonymous_quantity_pct_clean": pct(
            sales.loc[anonymous_mask, "Quantity"].sum(), sales["Quantity"].sum()
        ),
        "anonymous_revenue_pct_clean": pct(
            sales.loc[anonymous_mask, "Revenue"].sum(), sales["Revenue"].sum()
        ),
    }
    logger.info("Dữ liệu gốc: %s dòng; dữ liệu sạch: %s dòng (%.2f%%).", f"{len(raw):,}", f"{len(sales):,}", report["clean_rows_pct"])
    logger.info("Không loại theo Customer ID. Dòng sạch thiếu ID chiếm %.2f%%.", report["anonymous_rows_pct_clean"])
    logger.info("Tuần biên không đủ bị loại: %s.", ", ".join(report["removed_incomplete_weeks"]) or "không có")
    return raw, sales, report


def build_complete_product_week_panel(
    observed: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Thêm các tuần không bán = 0 trong vòng đời quan sát của sản phẩm."""
    bounds = observed.groupby("StockCode")["Week"].agg(["min", "max"])
    index = pd.MultiIndex.from_tuples(
        [
            (stock_code, week)
            for stock_code, row in bounds.iterrows()
            for week in pd.period_range(row["min"], row["max"], freq="W-SUN")
        ],
        names=["StockCode", "Week"],
    )
    panel = observed.set_index(["StockCode", "Week"]).reindex(index).reset_index()
    for column in ["quantity", "revenue", "invoices"]:
        panel[column] = panel[column].fillna(0)

    demand_profile = (
        panel.groupby("StockCode", observed=True)
        .agg(
            lifetime_weeks=("Week", "size"),
            active_weeks=("quantity", lambda values: int((values > 0).sum())),
            zero_weeks=("quantity", lambda values: int((values == 0).sum())),
            mean_weekly_quantity=("quantity", "mean"),
            median_weekly_quantity=("quantity", "median"),
            std_weekly_quantity=("quantity", "std"),
            max_weekly_quantity=("quantity", "max"),
        )
        .reset_index()
    )
    demand_profile["zero_rate_pct"] = (
        100 * demand_profile["zero_weeks"] / demand_profile["lifetime_weeks"]
    )
    demand_profile["active_rate_pct"] = 100 - demand_profile["zero_rate_pct"]

    positive_stats = (
        panel.loc[panel["quantity"] > 0]
        .groupby("StockCode")["quantity"]
        .agg(positive_mean="mean", positive_std="std")
        .reset_index()
    )
    demand_profile = demand_profile.merge(positive_stats, on="StockCode", how="left")
    demand_profile["adi"] = (
        demand_profile["lifetime_weeks"] / demand_profile["active_weeks"]
    )
    demand_profile["cv_squared"] = (
        demand_profile["positive_std"].fillna(0)
        / demand_profile["positive_mean"].replace(0, np.nan)
    ) ** 2

    smooth = (demand_profile["adi"] < 1.32) & (demand_profile["cv_squared"] < 0.49)
    erratic = (demand_profile["adi"] < 1.32) & (demand_profile["cv_squared"] >= 0.49)
    intermittent = (demand_profile["adi"] >= 1.32) & (demand_profile["cv_squared"] < 0.49)
    demand_profile["demand_type"] = np.select(
        [smooth, erratic, intermittent],
        ["smooth", "erratic", "intermittent"],
        default="lumpy",
    )
    return panel, demand_profile


def main() -> None:
    logger = configure_logging()
    total_started_at = time.perf_counter()
    report: dict[str, object] = {
        "objective": "Descriptive analysis before product demand forecasting",
        "model_trained": False,
    }

    started_at = start_step(
        logger, 1, "Audit và tiền xử lý", "Tạo tập gross sales nhất quán trước mọi phân tích."
    )
    raw, sales, preprocessing = load_and_preprocess(logger)
    report["preprocessing"] = preprocessing
    missing_table = pd.DataFrame(
        {
            "column": raw.columns,
            "missing_count": [preprocessing["missing_count"][c] for c in raw.columns],
            "missing_pct": [preprocessing["missing_pct"][c] for c in raw.columns],
        }
    ).sort_values("missing_pct", ascending=False)
    save_csv(missing_table, "01_missing_values.csv")
    finish_step(logger, started_at)

    started_at = start_step(
        logger, 2, "Mô tả biến số", "Hiểu phân phối Quantity, Price và Revenue và nhận biết giá trị cực lớn."
    )
    numeric = {
        "clean_quantity": numeric_summary(sales["Quantity"]),
        "clean_price": numeric_summary(sales["Price"]),
        "clean_revenue_per_row": numeric_summary(sales["Revenue"]),
    }
    report["numeric_summary"] = numeric
    numeric_table = pd.DataFrame(numeric).T.reset_index(names="variable")
    save_csv(numeric_table, "02_numeric_summary.csv")
    logger.info("Quantity: median=%.2f, p99=%.2f, max=%.2f.", numeric["clean_quantity"]["median"], numeric["clean_quantity"]["p99"], numeric["clean_quantity"]["max"])
    logger.info("Revenue/dòng: median=%.2f, p99=%.2f, max=%.2f.", numeric["clean_revenue_per_row"]["median"], numeric["clean_revenue_per_row"]["p99"], numeric["clean_revenue_per_row"]["max"])
    logger.info("Max cách xa p99 là dấu hiệu phân phối lệch phải; chưa tự động xóa outlier.")
    finish_step(logger, started_at)

    started_at = start_step(
        logger, 3, "Xu hướng theo tuần và tháng", "Quan sát trend, mùa vụ, tuần cao điểm và biến động thị trường."
    )
    weekly_market = (
        sales.groupby("Week", observed=True)
        .agg(quantity=("Quantity", "sum"), revenue=("Revenue", "sum"), invoices=("Invoice", "nunique"), active_products=("StockCode", "nunique"))
        .reset_index()
        .sort_values("Week")
    )
    weekly_market["quantity_change_pct"] = weekly_market["quantity"].pct_change() * 100
    weekly_market["quantity_ma_4"] = weekly_market["quantity"].rolling(4, min_periods=1).mean()
    weekly_market["revenue_ma_4"] = weekly_market["revenue"].rolling(4, min_periods=1).mean()
    # Tạo lại gross sales trước bộ lọc tuần biên, sau đó chỉ giữ tháng đầy đủ.
    # Nếu dùng `sales` ở đây, tháng đầu/cuối có thể mất vài ngày do bộ lọc tuần.
    monthly_sales = raw.drop_duplicates().copy()
    monthly_valid_mask = (
        monthly_sales["InvoiceDate"].notna()
        & monthly_sales["StockCode"].notna()
        & (monthly_sales["Quantity"] > 0)
        & (monthly_sales["Price"] > 0)
        & ~monthly_sales["Invoice"].astype(str).str.startswith("C", na=False)
    )
    monthly_sales = monthly_sales.loc[monthly_valid_mask].copy()
    monthly_sales["Revenue"] = monthly_sales["Quantity"] * monthly_sales["Price"]
    monthly_sales["Month"] = monthly_sales["InvoiceDate"].dt.to_period("M")
    first_month = monthly_sales["InvoiceDate"].min().to_period("M")
    last_month = monthly_sales["InvoiceDate"].max().to_period("M")
    incomplete_months: list[pd.Period] = []
    if monthly_sales["InvoiceDate"].min().normalize() > first_month.start_time.normalize():
        incomplete_months.append(first_month)
    if monthly_sales["InvoiceDate"].max().normalize() < last_month.end_time.normalize():
        incomplete_months.append(last_month)
    monthly_sales = monthly_sales.loc[~monthly_sales["Month"].isin(incomplete_months)]
    monthly_market = (
        monthly_sales.groupby("Month", observed=True)
        .agg(quantity=("Quantity", "sum"), revenue=("Revenue", "sum"), invoices=("Invoice", "nunique"), active_products=("StockCode", "nunique"))
        .reset_index()
        .sort_values("Month")
    )
    save_csv(weekly_market, "03_weekly_market_trend.csv")
    save_csv(monthly_market, "04_monthly_market_trend.csv")
    report["time_analysis"] = {
        "number_of_complete_weeks": int(len(weekly_market)),
        "weekly_quantity": numeric_summary(weekly_market["quantity"]),
        "top_10_weeks_by_quantity": records(weekly_market.nlargest(10, "quantity")),
        "top_10_months_by_quantity": records(monthly_market.nlargest(10, "quantity")),
    }
    logger.info("Có %s tuần hoàn chỉnh; Quantity tuần median=%.0f, max=%.0f.", len(weekly_market), weekly_market["quantity"].median(), weekly_market["quantity"].max())
    logger.info("Biểu đồ tháng chỉ dùng tháng đầy đủ; tháng biên bị loại: %s.", ", ".join(map(str, incomplete_months)) or "không có")
    finish_step(logger, started_at)

    started_at = start_step(
        logger, 4, "Phân tích theo thứ và giờ", "Tìm nhịp mua hàng trong tuần/ngày; đây là mô tả, không chứng minh nhân quả."
    )
    sales["weekday_number"] = sales["InvoiceDate"].dt.dayofweek
    sales["weekday"] = sales["InvoiceDate"].dt.day_name()
    sales["hour"] = sales["InvoiceDate"].dt.hour
    weekday = (
        sales.groupby(["weekday_number", "weekday"], observed=True)
        .agg(quantity=("Quantity", "sum"), revenue=("Revenue", "sum"), invoices=("Invoice", "nunique"))
        .reset_index()
        .sort_values("weekday_number")
    )
    hourly = (
        sales.groupby("hour", observed=True)
        .agg(quantity=("Quantity", "sum"), revenue=("Revenue", "sum"), invoices=("Invoice", "nunique"))
        .reset_index()
    )
    save_csv(weekday, "05_sales_by_weekday.csv")
    save_csv(hourly, "06_sales_by_hour.csv")
    report["calendar_patterns"] = {"weekday": records(weekday), "hour": records(hourly)}
    finish_step(logger, started_at)

    started_at = start_step(
        logger, 5, "Phân tích sản phẩm", "Phân biệt bán nhiều đơn vị, phổ biến trong nhiều hóa đơn và tạo doanh thu cao."
    )
    product_summary = (
        sales.groupby("StockCode", observed=True)
        .agg(
            description=("Description", most_common_description),
            quantity=("Quantity", "sum"),
            revenue=("Revenue", "sum"),
            invoices=("Invoice", "nunique"),
            active_weeks=("Week", "nunique"),
            countries=("Country", "nunique"),
            median_price=("Price", "median"),
            first_sale=("InvoiceDate", "min"),
            last_sale=("InvoiceDate", "max"),
        )
        .reset_index()
    )
    product_summary["quantity_per_invoice"] = product_summary["quantity"] / product_summary["invoices"]
    save_csv(product_summary.sort_values("quantity", ascending=False), "07_all_product_summary.csv")
    save_csv(product_summary.nlargest(30, "quantity"), "08_top_products_by_quantity.csv")
    save_csv(product_summary.nlargest(30, "invoices"), "09_top_products_by_invoices.csv")
    save_csv(product_summary.nlargest(30, "revenue"), "10_top_products_by_revenue.csv")
    report["product_analysis"] = {
        "unique_products": int(product_summary["StockCode"].nunique()),
        "top_10_quantity": records(product_summary.nlargest(10, "quantity")),
        "top_10_invoices": records(product_summary.nlargest(10, "invoices")),
        "top_10_revenue": records(product_summary.nlargest(10, "revenue")),
    }
    logger.info("Số StockCode: %s. Đã tách ba bảng xếp hạng vì Quantity, Invoice và Revenue không cùng nghĩa.", f"{len(product_summary):,}")
    finish_step(logger, started_at)

    started_at = start_step(
        logger, 6, "Mã hàng không chuẩn", "Tìm phí ship, chiết khấu hay mã nội bộ trước khi coi mọi StockCode là hàng tồn kho."
    )
    nonstandard = product_summary.loc[
        ~product_summary["StockCode"].str.match(r"^\d{5}[A-Z]?$", na=False)
    ].sort_values("invoices", ascending=False)
    save_csv(nonstandard, "11_nonstandard_stock_codes.csv")
    report["nonstandard_stock_codes"] = {
        "count": int(len(nonstandard)),
        "top_30": records(nonstandard.head(30)),
    }
    logger.info("Có %s mã không theo pattern sản phẩm thông thường; chưa xóa vì cần duyệt nghiệp vụ.", len(nonstandard))
    finish_step(logger, started_at)

    started_at = start_step(
        logger, 7, "Panel sản phẩm-tuần và zero demand", "Tuần không bán là thông tin thật; cần bổ sung 0 trong vòng đời sản phẩm."
    )
    observed = (
        sales.groupby(["StockCode", "Week"], observed=True)
        .agg(quantity=("Quantity", "sum"), revenue=("Revenue", "sum"), invoices=("Invoice", "nunique"))
        .reset_index()
    )
    panel, demand_profile = build_complete_product_week_panel(observed)
    save_csv(observed, "12_product_week_observed.csv")
    save_csv(demand_profile.sort_values("zero_rate_pct", ascending=False), "13_product_demand_profile.csv")
    zero_rate = pct((panel["quantity"] == 0).sum(), len(panel))
    report["product_week_panel"] = {
        "observed_rows": int(len(observed)),
        "complete_lifetime_rows": int(len(panel)),
        "zero_rows": int((panel["quantity"] == 0).sum()),
        "zero_rate_pct": zero_rate,
        "active_weeks_distribution": numeric_summary(demand_profile["active_weeks"]),
    }
    logger.info("Panel trong vòng đời có %s dòng; %.2f%% là tuần không bán.", f"{len(panel):,}", zero_rate)
    finish_step(logger, started_at)

    started_at = start_step(
        logger, 8, "Phân loại kiểu nhu cầu", "ADI đo mức gián đoạn; CV² đo độ biến động khi có bán."
    )
    type_summary = (
        demand_profile.groupby("demand_type", observed=True)
        .agg(products=("StockCode", "size"), median_zero_rate_pct=("zero_rate_pct", "median"), median_active_weeks=("active_weeks", "median"))
        .reset_index()
    )
    type_summary["product_pct"] = 100 * type_summary["products"] / type_summary["products"].sum()
    save_csv(type_summary, "14_demand_type_summary.csv")
    report["demand_types"] = records(type_summary)
    logger.info("Smooth=thường xuyên/ổn định; erratic=thường xuyên/biến động; intermittent=gián đoạn; lumpy=gián đoạn và biến động.")
    for row in type_summary.itertuples(index=False):
        logger.info("%-12s: %s sản phẩm (%.2f%%).", row.demand_type, f"{row.products:,}", row.product_pct)
    finish_step(logger, started_at)

    started_at = start_step(
        logger, 9, "Mức độ tập trung Pareto", "Xác định Top sản phẩm đóng góp bao nhiêu nhu cầu và doanh thu."
    )
    ranked = product_summary.sort_values("quantity", ascending=False).copy()
    ranked["quantity_share_pct"] = 100 * ranked["quantity"] / ranked["quantity"].sum()
    ranked["quantity_cumulative_pct"] = ranked["quantity_share_pct"].cumsum()
    ranked_revenue = product_summary.sort_values("revenue", ascending=False).copy()
    ranked_revenue["revenue_share_pct"] = 100 * ranked_revenue["revenue"] / ranked_revenue["revenue"].sum()
    ranked_revenue["revenue_cumulative_pct"] = ranked_revenue["revenue_share_pct"].cumsum()
    top_20_percent_n = max(1, int(np.ceil(0.2 * len(product_summary))))
    concentration = {
        "top_10_quantity_share_pct": float(ranked.head(10)["quantity_share_pct"].sum()),
        "top_50_quantity_share_pct": float(ranked.head(50)["quantity_share_pct"].sum()),
        "top_20_percent_quantity_share_pct": float(ranked.head(top_20_percent_n)["quantity_share_pct"].sum()),
        "top_10_revenue_share_pct": float(ranked_revenue.head(10)["revenue_share_pct"].sum()),
        "top_50_revenue_share_pct": float(ranked_revenue.head(50)["revenue_share_pct"].sum()),
        "top_20_percent_revenue_share_pct": float(ranked_revenue.head(top_20_percent_n)["revenue_share_pct"].sum()),
    }
    save_csv(ranked, "15_quantity_pareto.csv")
    save_csv(ranked_revenue, "16_revenue_pareto.csv")
    report["concentration"] = concentration
    logger.info("Top 10/50 sản phẩm đóng góp %.2f%% / %.2f%% Quantity.", concentration["top_10_quantity_share_pct"], concentration["top_50_quantity_share_pct"])
    finish_step(logger, started_at)

    started_at = start_step(
        logger, 10, "Phân tích quốc gia", "Kiểm tra thị trường nào chi phối dữ liệu và xu hướng tổng."
    )
    country = (
        sales.groupby("Country", observed=True)
        .agg(quantity=("Quantity", "sum"), revenue=("Revenue", "sum"), invoices=("Invoice", "nunique"), products=("StockCode", "nunique"))
        .reset_index()
        .sort_values("quantity", ascending=False)
    )
    country["quantity_share_pct"] = 100 * country["quantity"] / country["quantity"].sum()
    country["revenue_share_pct"] = 100 * country["revenue"] / country["revenue"].sum()
    save_csv(country, "17_country_summary.csv")
    report["countries"] = {"count": int(len(country)), "top_20": records(country.head(20))}
    logger.info("Thị trường lớn nhất theo Quantity: %s (%.2f%%).", country.iloc[0]["Country"], country.iloc[0]["quantity_share_pct"])
    finish_step(logger, started_at)

    started_at = start_step(
        logger, 11, "Trả hàng/hủy đơn", "Gross demand loại các dòng này, nhưng EDA vẫn phải báo cáo rủi ro hoàn trả."
    )
    # Trích nguyên bản tất cả dòng có Invoice bắt đầu bằng C.
    # SourceRowNumber tính cả dòng header CSV, nên index 0 của DataFrame là dòng 2.
    cancelled_raw_mask = raw["Invoice"].astype(str).str.startswith("C", na=False)
    # True chỉ cho bản sao xuất hiện sau bản ghi đầu tiên.
    all_duplicate_mask = raw.duplicated(keep="first")
    cancelled_records = raw.loc[cancelled_raw_mask].copy()
    cancelled_records.insert(0, "SourceRowNumber", cancelled_records.index + 2)
    cancelled_records["IsExactDuplicate"] = all_duplicate_mask.loc[cancelled_records.index]
    cancelled_records["SignedRevenue"] = (
        cancelled_records["Quantity"] * cancelled_records["Price"]
    )
    save_csv(cancelled_records, "18_cancelled_invoice_records.csv")

    deduplicated_raw = raw.drop_duplicates().copy()
    return_mask = (
        deduplicated_raw["Invoice"].astype(str).str.startswith("C", na=False)
        | (deduplicated_raw["Quantity"] < 0)
    )
    returns = deduplicated_raw.loc[return_mask & deduplicated_raw["StockCode"].notna()].copy()
    returns["StockCode"] = returns["StockCode"].astype(str).str.strip()
    return_products = (
        returns.groupby("StockCode", observed=True)
        .agg(returned_units=("Quantity", lambda values: float(-values.loc[values < 0].sum())), return_rows=("Invoice", "size"), return_invoices=("Invoice", "nunique"))
        .reset_index()
        .sort_values("returned_units", ascending=False)
    )
    save_csv(return_products, "19_returns_by_product.csv")
    report["returns"] = {
        "raw_cancelled_rows": int(len(cancelled_records)),
        "raw_cancelled_unique_invoices": int(cancelled_records["Invoice"].nunique()),
        "raw_cancelled_exact_duplicate_rows": int(cancelled_records["IsExactDuplicate"].sum()),
        "rows": int(len(returns)),
        "invoices": int(returns["Invoice"].nunique()),
        "top_20_products": records(return_products.head(20)),
    }
    logger.info("Đã trích %s dòng Invoice bắt đầu C (%s Invoice duy nhất) từ dữ liệu gốc.", f"{len(cancelled_records):,}", f"{cancelled_records['Invoice'].nunique():,}")
    logger.info("File chi tiết: %s", OUTPUT_DIR / "18_cancelled_invoice_records.csv")
    logger.info("Trả/hủy sau xóa trùng: %s dòng, %s hóa đơn.", f"{len(returns):,}", f"{returns['Invoice'].nunique():,}")
    finish_step(logger, started_at)

    started_at = start_step(
        logger, 12, "Vẽ và lưu biểu đồ", "Chuyển các bảng thống kê thành hình ảnh dễ quan sát trend, outlier, Pareto và nhu cầu gián đoạn."
    )
    chart_files = create_charts(
        missing_table=missing_table,
        weekly_market=weekly_market,
        monthly_market=monthly_market,
        weekday=weekday,
        hourly=hourly,
        product_summary=product_summary,
        observed=observed,
        demand_profile=demand_profile,
        type_summary=type_summary,
        ranked=ranked,
        country=country,
        return_products=return_products,
    )
    report["charts"] = [str(Path("charts") / filename) for filename in chart_files]
    for filename in chart_files:
        logger.info("Đã lưu: %s", CHART_DIR / filename)
    finish_step(logger, started_at)

    markdown = f"""# Báo cáo phân tích mô tả nhu cầu sản phẩm

File này không train model. Mục tiêu là hiểu dữ liệu trước khi dự báo.

## Tiền xử lý

- Dòng gốc: {preprocessing['raw_rows']:,}
- Dòng gross sales sạch: {preprocessing['clean_rows']:,} ({preprocessing['clean_rows_pct']:.2f}%)
- Dòng trùng: {preprocessing['exact_duplicate_rows']:,}
- Dòng hủy: {preprocessing['cancelled_rows']:,}
- Tuần biên bị loại: {', '.join(preprocessing['removed_incomplete_weeks']) or 'không có'}
- Giao dịch sạch thiếu Customer ID: {preprocessing['anonymous_rows_pct_clean']:.2f}% (vẫn được giữ)

## Phạm vi

- Số StockCode: {len(product_summary):,}
- Số tuần hoàn chỉnh: {len(weekly_market):,}
- Tỷ lệ tuần zero trong vòng đời sản phẩm: {zero_rate:.2f}%
- Mã StockCode không chuẩn cần duyệt: {len(nonstandard):,}

## Mức tập trung

- Top 10 sản phẩm: {concentration['top_10_quantity_share_pct']:.2f}% Quantity
- Top 50 sản phẩm: {concentration['top_50_quantity_share_pct']:.2f}% Quantity
- Top 20% sản phẩm: {concentration['top_20_percent_quantity_share_pct']:.2f}% Quantity

## Cách đọc các file

1. `01_missing_values.csv`: dữ liệu thiếu.
2. `03_weekly_market_trend.csv`: xu hướng theo tuần và moving average 4 tuần.
3. `07_all_product_summary.csv`: toàn bộ chỉ số theo sản phẩm.
4. `11_nonstandard_stock_codes.csv`: mã cần xác minh có phải hàng hóa thật hay không.
5. `13_product_demand_profile.csv`: zero rate, ADI, CV² và loại nhu cầu.
6. `15_quantity_pareto.csv`: mức đóng góp Quantity tích lũy.
7. `17_country_summary.csv`: mức đóng góp theo quốc gia.
8. `18_cancelled_invoice_records.csv`: toàn bộ bản ghi gốc có Invoice bắt đầu bằng C.
9. `19_returns_by_product.csv`: sản phẩm có nhiều lượng trả/hủy.

## Biểu đồ

1. ![Dữ liệu thiếu](charts/01_missing_values.png)
2. ![Xu hướng Quantity theo tuần](charts/02_weekly_quantity_trend.png)
3. ![Quantity và Revenue theo tháng](charts/03_monthly_quantity_revenue.png)
4. ![Quantity theo thứ](charts/04_quantity_by_weekday.png)
5. ![Invoice theo giờ](charts/05_invoices_by_hour.png)
6. ![Top sản phẩm](charts/06_top_products_by_quantity.png)
7. ![Phân phối Quantity sản phẩm-tuần](charts/07_product_week_quantity_distribution.png)
8. ![Phân phối zero-rate](charts/08_product_zero_rate_distribution.png)
9. ![Bản đồ ADI-CV2](charts/09_adi_cv2_demand_map.png)
10. ![Pareto Quantity](charts/10_quantity_pareto.png)
11. ![Tỷ trọng quốc gia](charts/11_country_quantity_share.png)
12. ![Sản phẩm trả hàng](charts/12_top_product_returns.png)
13. ![Cơ cấu kiểu nhu cầu](charts/13_demand_type_counts.png)

## Chưa được phép kết luận

- Tương quan giá và Quantity không tự động chứng minh giá gây ra nhu cầu.
- Outlier chưa được xóa vì có thể là đơn bán buôn thật.
- Mã không chuẩn chưa bị xóa khi chưa có quyết định nghiệp vụ.
- Dữ liệu chỉ khoảng hai năm, nên bằng chứng mùa vụ còn hạn chế.
"""
    MARKDOWN_REPORT_PATH.write_text(markdown, encoding="utf-8")
    with JSON_REPORT_PATH.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)

    logger.info("")
    logger.info("=" * 78)
    logger.info("HOÀN THÀNH TOÀN BỘ PHÂN TÍCH trong %.2f giây.", time.perf_counter() - total_started_at)
    logger.info("Báo cáo dễ đọc: %s", MARKDOWN_REPORT_PATH)
    logger.info("Báo cáo máy đọc: %s", JSON_REPORT_PATH)
    logger.info("Log từng bước: %s", LOG_PATH)
    logger.info("Thư mục biểu đồ: %s (%s file PNG)", CHART_DIR, len(chart_files))
    logger.info("Không có model nào được train trong file này.")


if __name__ == "__main__":
    main()
