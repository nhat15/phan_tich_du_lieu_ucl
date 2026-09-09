# Báo cáo phân tích mô tả nhu cầu sản phẩm

File này không train model. Mục tiêu là hiểu dữ liệu trước khi dự báo.

## Tiền xử lý

- Dòng gốc: 1,067,371
- Dòng gross sales sạch: 976,674 (91.50%)
- Dòng trùng: 34,335
- Dòng hủy: 19,494
- Tuần biên bị loại: 2009-11-30/2009-12-06, 2011-12-05/2011-12-11
- Giao dịch sạch thiếu Customer ID: 22.45% (vẫn được giữ)

## Phạm vi

- Số StockCode: 4,881
- Số tuần hoàn chỉnh: 102
- Tỷ lệ tuần zero trong vòng đời sản phẩm: 40.10%
- Mã StockCode không chuẩn cần duyệt: 211

## Mức tập trung

- Top 10 sản phẩm: 7.41% Quantity
- Top 50 sản phẩm: 19.29% Quantity
- Top 20% sản phẩm: 78.29% Quantity

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
14. ![Box plot Quantity, Price và Revenue](charts/14_numeric_boxplots.png)

## Chưa được phép kết luận

- Tương quan giá và Quantity không tự động chứng minh giá gây ra nhu cầu.
- Outlier chưa được xóa vì có thể là đơn bán buôn thật.
- Mã không chuẩn chưa bị xóa khi chưa có quyết định nghiệp vụ.
- Dữ liệu chỉ khoảng hai năm, nên bằng chứng mùa vụ còn hạn chế.
