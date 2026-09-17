# Kịch bản thuyết trình phân tích mô tả dữ liệu Online Retail II

**Thời lượng đề xuất:** 10–12 phút  
**Mục tiêu:** Trình bày dữ liệu, cách làm sạch và kể câu chuyện về nhu cầu hàng hóa trước khi xây dựng mô hình dự báo.

---

## Slide 1 – Mục tiêu phân tích

### Nội dung trên slide

- Dữ liệu bán lẻ trực tuyến giai đoạn 2009–2011
- Đối tượng phân tích: sản phẩm và số lượng bán
- Câu hỏi chính: *Nhu cầu hàng hóa có đặc điểm gì và điều đó ảnh hưởng thế nào tới dự báo?*

### Lời trình bày

“Trong phần này, tôi chưa đi ngay vào mô hình dự báo. Trước hết, tôi muốn trả lời ba câu hỏi. Thứ nhất, dữ liệu hiện có bao gồm những gì và có đủ tin cậy hay không? Thứ hai, cần xử lý dữ liệu như thế nào để lượng bán phản ánh đúng nhu cầu? Cuối cùng, sau khi làm sạch, dữ liệu kể cho chúng ta câu chuyện gì về thị trường và từng sản phẩm? Những kết quả này sẽ là cơ sở để lựa chọn cách dự báo ở bước tiếp theo.”

### Câu chuyển

“Trước tiên, chúng ta bắt đầu từ quy mô và cấu trúc của dữ liệu gốc.”

---

## Slide 2 – Tổng quan bộ dữ liệu

### Nội dung trên slide

| Nội dung | Kết quả |
|---|---:|
| Số bản ghi | 1.067.371 |
| Số thuộc tính | 8 |
| Khoảng thời gian | 01/12/2009–09/12/2011 |
| Số quốc gia | 43 |
| Các biến chính | Invoice, StockCode, Quantity, InvoiceDate, Price |

### Lời trình bày

“Dữ liệu ban đầu có hơn 1,06 triệu dòng giao dịch và 8 thuộc tính. Mỗi dòng biểu diễn một mặt hàng nằm trong một hóa đơn, chứ không phải toàn bộ một hóa đơn. `StockCode` xác định sản phẩm, `Quantity` là số lượng của sản phẩm trong giao dịch, `Price` là đơn giá và `InvoiceDate` là thời điểm giao dịch. Dữ liệu trải dài khoảng hai năm và bao gồm 43 quốc gia. Vì mục tiêu là dự báo xu hướng hàng hóa, đơn vị quan sát cuối cùng sẽ được chuyển từ dòng giao dịch sang sản phẩm theo tuần.”

### Câu chuyển

“Tuy nhiên, trước khi tổng hợp dữ liệu, chúng ta cần kiểm tra những vấn đề chất lượng dữ liệu.”

---

## Slide 3 – Dữ liệu khuyết và quyết định giữ Customer ID

### Hình cần chèn

`product_descriptive_analysis_outputs/charts/01_missing_values.png`

### Nội dung trên slide

- `Customer ID`: thiếu 243.007 dòng, tương đương 22,767%
- `Description`: thiếu 4.382 dòng, tương đương 0,411%
- Các trường thiết yếu cho dự báo sản phẩm không bị thiếu
- Không điền và không loại dòng chỉ vì thiếu `Customer ID`

### Lời trình bày

“Biểu đồ cho thấy phần thiếu chủ yếu nằm ở `Customer ID`, với khoảng 22,77% số dòng. Nếu bài toán là dự báo từng khách hàng sẽ mua gì thì đây là vấn đề lớn. Nhưng bài toán của tôi là dự báo sản phẩm nào được mua nhiều. Các dòng thiếu Customer ID vẫn có hóa đơn, sản phẩm, số lượng, giá và thời gian nên vẫn phản ánh lượng hàng đã bán. Sau làm sạch, nhóm thiếu Customer ID còn chiếm 22,45% số dòng nhưng đóng góp 6,14% tổng Quantity và 15,08% tổng Revenue. Loại nhóm này sẽ làm mất nhu cầu có thật, vì vậy tôi giữ lại và không dùng Customer ID làm biến dự báo.”

“Description chỉ phục vụ hiển thị tên sản phẩm; StockCode mới là khóa định danh. Vì thế tôi cũng không điền một mô tả giả vào các ô thiếu.”

### Câu chuyển

“Dữ liệu khuyết không phải vấn đề duy nhất. Tập dữ liệu còn chứa dòng trùng, đơn hủy và các giao dịch không phản ánh mua hàng mới.”

---

## Slide 4 – Quy trình tiền xử lý

### Nội dung trên slide

```text
1.067.371 dòng gốc
        ↓ chuyển kiểu dữ liệu
        ↓ loại 34.335 dòng trùng hoàn toàn
        ↓ loại hóa đơn C, Quantity ≤ 0, Price ≤ 0
        ↓ chuẩn hóa StockCode và tạo Revenue
        ↓ loại hai tuần biên không đầy đủ
976.674 dòng gross sales sạch (91,50%)
```

### Lời trình bày

“Quy trình làm sạch được thực hiện theo từng bước. Đầu tiên, InvoiceDate được chuyển sang kiểu thời gian; Quantity và Price được chuyển sang kiểu số. Tiếp theo, 34.335 dòng trùng hoàn toàn được loại để tránh tính doanh số nhiều lần.”

“Tôi loại các hóa đơn bắt đầu bằng chữ C vì đây là hóa đơn bị hủy. Dữ liệu có 19.494 dòng như vậy. Tôi cũng loại các dòng Quantity không dương và Price không dương, vì chúng không phải giao dịch bán mới tạo ra gross demand. Các nhóm lỗi có thể giao nhau nên không cộng trực tiếp số lượng từng nhóm để tính tổng dòng bị loại.”

“Sau đó, StockCode được loại khoảng trắng thừa và Revenue được tính bằng Quantity nhân Price. Cuối cùng, tôi loại tuần đầu và tuần cuối vì hai tuần này không đủ bảy ngày. Kết quả còn 976.674 dòng, tương đương 91,50% dữ liệu ban đầu.”

### Câu chuyển

“Trong số các bước trên, việc tách đơn hủy đặc biệt quan trọng vì hủy hàng và nhu cầu mua mới mang hai ý nghĩa khác nhau.”

---

## Slide 5 – Hóa đơn hủy, hoàn trả và mã hàng không chuẩn

### Hình cần chèn

- Ảnh chụp một số dòng trong `18_cancelled_invoice_records.csv`
- `product_descriptive_analysis_outputs/charts/12_top_product_returns.png`
- Có thể chèn thêm ảnh chụp `11_nonstandard_stock_codes.csv`

### Nội dung trên slide

- 19.494 dòng thuộc 8.292 hóa đơn bắt đầu bằng C
- 22.950 dòng có Quantity không dương
- 211 StockCode không theo cấu trúc sản phẩm thông thường
- Hủy/hoàn trả được phân tích riêng, không tính vào gross demand

### Lời trình bày

“Các hóa đơn bắt đầu bằng C và những dòng Quantity âm thường phản ánh hủy hoặc trả hàng. Nếu cộng chung với bán hàng, chúng ta đang trộn hai hiện tượng: nhu cầu mua mới và rủi ro hoàn trả. Vì mục tiêu mô hình là dự báo gross demand, tôi loại chúng khỏi tập huấn luyện nhưng vẫn lưu thành bảng riêng để không làm mất thông tin nghiệp vụ.”

“Ngoài ra, có 211 StockCode không giống mã sản phẩm thông thường. Chúng có thể là phí vận chuyển, chiết khấu hoặc thao tác nội bộ. Trong phân tích mô tả, chúng được giữ lại để kiểm tra. Khi xây dựng mô hình hàng hóa, chỉ các mã có năm chữ số và có thể kèm một chữ cái cuối được giữ, qua đó loại 9.060 dòng không thuộc nhóm mã chuẩn.”

### Câu chuyển

“Sau khi xác định được giao dịch bán hợp lệ, bước tiếp theo là kiểm tra hình dạng phân phối của các biến số.”

---

## Slide 6 – Phân phối lệch phải và các giao dịch cực lớn

### Hình cần chèn

`product_descriptive_analysis_outputs/charts/14_numeric_boxplots.png`

### Nội dung trên slide

| Biến | Trung vị | P99 | Lớn nhất |
|---|---:|---:|---:|
| Quantity | 4 | 108 | 74.215 |
| Price | 2,10 | 18 | 25.111,09 |
| Revenue/dòng | 10,08 | 185 | 77.183,60 |

### Lời trình bày

“Box plot sử dụng trục log cho thấy cả Quantity, Price và Revenue đều lệch phải mạnh. Ví dụ, Quantity trung vị chỉ bằng 4 và 99% số dòng không vượt quá 108 đơn vị, nhưng giá trị lớn nhất lên tới 74.215. Như vậy, phần lớn giao dịch nhỏ nhưng tồn tại một số rất ít đơn hàng cực lớn.”

“Điều này dẫn đến ba quyết định. Một là không chỉ sử dụng trung bình mà cần báo cáo thêm trung vị và các phân vị. Hai là không tự động xóa outlier, vì đó có thể là đơn bán buôn thật. Ba là khi đánh giá mô hình, không chỉ sử dụng RMSE vì chỉ vài sai số lớn có thể chi phối chỉ số; cần kết hợp MAE, WMAPE, RMSLE và các chỉ số xếp hạng.”

### Câu chuyển

“Sau khi hiểu phân phối ở cấp giao dịch, tôi chuyển sang nhìn nhu cầu của toàn thị trường theo thời gian.”

---

## Slide 7 – Câu chuyện theo thời gian: nhu cầu tăng mạnh vào cuối năm

### Hình cần chèn

- `product_descriptive_analysis_outputs/charts/02_weekly_quantity_trend.png`
- `product_descriptive_analysis_outputs/charts/03_monthly_quantity_revenue.png`

### Nội dung trên slide

- 102 tuần đầy đủ
- Quantity trung vị mỗi tuần: 98.114
- Tuần cao nhất: 237.249 sản phẩm
- Tháng 11/2010 và 11/2011 đều nằm trong nhóm cao nhất

### Lời trình bày

“Dữ liệu sau làm sạch bao gồm 102 tuần đầy đủ. Đường mảnh thể hiện Quantity từng tuần, còn đường trung bình trượt bốn tuần giúp nhìn xu hướng chung. Nhu cầu không cố định mà biến động mạnh, với trung vị khoảng 98 nghìn sản phẩm mỗi tuần và tuần cao nhất đạt hơn 237 nghìn.”

“Khi nhìn theo tháng, một mẫu hình đáng chú ý xuất hiện: tháng 10 và đặc biệt tháng 11 của cả hai năm đều có lượng bán cao. Tháng 11/2010 đạt khoảng 725 nghìn sản phẩm, còn tháng 11/2011 đạt khoảng 751 nghìn. Điều này gợi ý yếu tố mùa vụ cuối năm. Tuy nhiên, dữ liệu chỉ có khoảng hai chu kỳ năm nên đây là dấu hiệu, chưa đủ để khẳng định quy luật lâu dài.”

### Câu chuyển

“Xu hướng thị trường tăng không có nghĩa mọi sản phẩm đều đóng góp giống nhau.”

---

## Slide 8 – Nhu cầu tập trung vào một nhóm sản phẩm

### Hình cần chèn

- `product_descriptive_analysis_outputs/charts/06_top_products_by_quantity.png`
- `product_descriptive_analysis_outputs/charts/10_quantity_pareto.png`

### Nội dung trên slide

- 4.881 StockCode trong dữ liệu mô tả
- Top 10 sản phẩm đóng góp 7,41% Quantity
- Top 50 đóng góp 19,29%
- Top 20% sản phẩm đóng góp 78,29%

### Lời trình bày

“Biểu đồ Top 20 cho biết những sản phẩm bán nhiều nhất, trong đó các mã như 84077, 85099B và 21212 đứng đầu về tổng số lượng. Tuy nhiên, tổng Quantity cao có thể do sản phẩm bán đều qua nhiều tuần hoặc do một vài đơn hàng rất lớn. Vì vậy, tôi không chỉ nhìn tổng lượng mà còn xem số hóa đơn và số tuần hoạt động.”

“Đường Pareto cho thấy nhu cầu có tính tập trung cao: 20% sản phẩm đóng góp khoảng 78,29% tổng Quantity. Điều này gần với nguyên lý 80/20. Về nghiệp vụ, nhóm sản phẩm này cần được ưu tiên khi lập kế hoạch tồn kho. Về mô hình, các chỉ số Top-K như Precision@20 và NDCG@20 trở nên cần thiết vì doanh nghiệp thường quan tâm trước hết tới việc tìm đúng nhóm hàng bán chạy.”

### Câu chuyển

“Không chỉ tập trung theo sản phẩm, dữ liệu còn tập trung rất mạnh theo thị trường địa lý.”

---

## Slide 9 – Thị trường chủ đạo là United Kingdom

### Hình cần chèn

`product_descriptive_analysis_outputs/charts/11_country_quantity_share.png`

### Nội dung trên slide

- 43 quốc gia
- United Kingdom chiếm 81,64% Quantity
- United Kingdom chiếm 84,72% Revenue

### Lời trình bày

“Mặc dù dữ liệu gồm 43 quốc gia, United Kingdom chiếm tới 81,64% tổng Quantity và 84,72% doanh thu. Do đó, xu hướng tổng thể của dữ liệu chủ yếu phản ánh thị trường UK. Đây là một giới hạn quan trọng: mô hình toàn cục có thể hoạt động tốt cho UK nhưng chưa chắc phản ánh chính xác các quốc gia nhỏ. Nếu mục tiêu kinh doanh mở rộng theo từng quốc gia, cần xây dựng thêm biến thị trường hoặc mô hình riêng khi có đủ dữ liệu.”

### Câu chuyển

“Tiếp theo, khi chuyển từ giao dịch sang sản phẩm–tuần, một đặc điểm khó hơn xuất hiện: rất nhiều tuần sản phẩm không bán được đơn vị nào.”

---

## Slide 10 – Nhu cầu bằng 0 là thông tin, không phải dữ liệu khuyết

### Hình cần chèn

- `product_descriptive_analysis_outputs/charts/08_product_zero_rate_distribution.png`
- `product_descriptive_analysis_outputs/charts/07_product_week_quantity_distribution.png`

### Nội dung trên slide

- Panel liên tục: 323.433 dòng sản phẩm–tuần
- 40,10% số tuần trong vòng đời sản phẩm có Quantity bằng 0
- Không có giao dịch trong tuần được biểu diễn là nhu cầu 0

### Lời trình bày

“Trong dữ liệu hóa đơn, một sản phẩm chỉ xuất hiện khi có bán. Nhưng nếu sản phẩm không xuất hiện trong một tuần, điều đó không có nghĩa dữ liệu bị thiếu; nó có nghĩa nhu cầu quan sát được bằng 0. Vì vậy, tôi tạo một panel liên tục cho từng sản phẩm từ tuần bán đầu tiên đến tuần bán cuối cùng và bổ sung Quantity bằng 0 cho các tuần không có giao dịch.”

“Panel thu được có 323.433 dòng sản phẩm–tuần và 40,10% trong số đó là tuần không bán. Nếu bỏ các số 0 này, mô hình chỉ được học từ những tuần bán được hàng và sẽ dự báo nhu cầu quá cao.”

### Câu chuyển

“Tỷ lệ tuần bằng 0 lớn cũng cho thấy không thể xem mọi sản phẩm là một chuỗi nhu cầu giống nhau.”

---

## Slide 11 – Bốn kiểu nhu cầu sản phẩm

### Hình cần chèn

- `product_descriptive_analysis_outputs/charts/09_adi_cv2_demand_map.png`
- `product_descriptive_analysis_outputs/charts/13_demand_type_counts.png`

### Nội dung trên slide

| Kiểu nhu cầu | Số sản phẩm | Tỷ lệ |
|---|---:|---:|
| Smooth | 483 | 9,90% |
| Erratic | 1.598 | 32,74% |
| Intermittent | 506 | 10,37% |
| Lumpy | 2.294 | 47,00% |

### Lời trình bày

“Tôi sử dụng ADI để đo khoảng cách giữa các tuần có bán và CV bình phương để đo độ biến động của lượng bán dương. Từ đó, sản phẩm được chia thành bốn nhóm. Smooth là bán thường xuyên và ổn định; erratic là thường xuyên nhưng biến động; intermittent là bán gián đoạn; còn lumpy vừa gián đoạn vừa biến động.”

“Kết quả quan trọng nhất là nhóm lumpy chiếm 47%, nhóm erratic chiếm 32,74%, trong khi nhóm smooth chỉ chiếm 9,90%. Như vậy, phần lớn sản phẩm không có nhu cầu đều và dễ dự báo. Đây là lý do một mô hình trung bình đơn giản có thể phù hợp với một số sản phẩm, nhưng khó xử lý toàn bộ danh mục.”

### Câu chuyển

“Từ tất cả các biểu đồ trên, chúng ta có thể ghép lại thành một câu chuyện thống nhất về dữ liệu.”

---

## Slide 12 – Câu chuyện của dữ liệu và định hướng bước tiếp theo

### Nội dung trên slide

```text
Thị trường lớn và có mùa vụ cuối năm
                    ↓
Nhu cầu tập trung vào một nhóm nhỏ sản phẩm
                    ↓
Nhưng phần lớn sản phẩm có nhu cầu gián đoạn hoặc biến động
                    ↓
Cần dự báo theo sản phẩm–tuần và đánh giá cả số lượng lẫn Top-K
```

### Lời trình bày

“Câu chuyện tổng thể của dữ liệu có thể tóm tắt như sau. Đây là một thị trường bán lẻ có quy mô giao dịch lớn và có dấu hiệu tăng nhu cầu vào cuối năm. Tuy nhiên, nhu cầu phân bổ không đồng đều: một nhóm nhỏ sản phẩm tạo ra phần lớn số lượng bán, và thị trường UK chi phối toàn bộ dữ liệu.”

“Ở cấp từng sản phẩm, bài toán trở nên khó hơn vì 40,10% số tuần có nhu cầu bằng 0 và gần một nửa sản phẩm thuộc nhóm lumpy. Đồng thời, phân phối Quantity lệch phải mạnh do một số đơn hàng rất lớn.”

“Vì vậy, dữ liệu được tổ chức theo sản phẩm–tuần, giữ lại các tuần bằng 0 và tạo đặc trưng từ lịch sử như lượng bán trễ, trung bình trượt, tỷ lệ tuần có bán và yếu tố mùa vụ. Mô hình không chỉ cần dự báo số lượng chính xác mà còn phải xếp đúng nhóm sản phẩm bán chạy. Đây là cơ sở để so sánh baseline, Moving Average, XGBoost Poisson và mô hình hai tầng ở phần dự báo.”

### Câu kết

“Như vậy, phân tích mô tả không chỉ cho biết dữ liệu trông như thế nào; nó trực tiếp quyết định cách làm sạch, đơn vị dự báo, đặc trưng, mô hình và thước đo đánh giá trong bước tiếp theo.”

---

# Bản nói ngắn gọn nếu thời gian chỉ có 5 phút

“Dữ liệu Online Retail II có hơn 1,06 triệu dòng giao dịch trong khoảng hai năm. Sau khi loại dòng trùng, hóa đơn hủy, Quantity và Price không hợp lệ cùng hai tuần biên thiếu ngày, dữ liệu còn 976.674 dòng gross sales, tương đương 91,50% dữ liệu gốc.

Mặc dù 22,77% dữ liệu thiếu Customer ID, tôi không loại các dòng này vì bài toán dự báo hàng hóa, không dự báo từng khách hàng. Các giao dịch đó vẫn chứa sản phẩm, số lượng và thời gian nên vẫn phản ánh nhu cầu thực.

Phân tích phân phối cho thấy Quantity, Price và Revenue lệch phải mạnh. Quantity trung vị chỉ là 4, P99 là 108 nhưng lớn nhất tới 74.215. Vì vậy, không thể chỉ dùng giá trị trung bình và cũng không nên tự động xóa outlier khi chưa xác minh đó là lỗi.

Theo thời gian, lượng bán tăng rõ vào tháng 10 và tháng 11 của cả hai năm, gợi ý mùa vụ cuối năm. Nhu cầu cũng tập trung cao: 20% sản phẩm tạo ra 78,29% tổng Quantity; riêng UK chiếm 81,64% lượng bán.

Khi chuyển dữ liệu sang cấp sản phẩm–tuần, 40,10% số tuần có Quantity bằng 0. Gần 47% sản phẩm có nhu cầu lumpy, nghĩa là vừa gián đoạn vừa biến động. Do đó, dự báo nhu cầu là bài toán khó và cần giữ các tuần bằng 0, tạo đặc trưng lịch sử, đồng thời đánh giá cả sai số số lượng lẫn khả năng xếp hạng sản phẩm Top-K. Đây là cơ sở để lựa chọn XGBoost Poisson và so sánh nó với các mô hình baseline trong phần tiếp theo.”

---

# Lưu ý khi thiết kế slide

- Mỗi slide chỉ nên dùng một thông điệp chính; không chèn toàn bộ bảng CSV.
- Phóng to con số quan trọng và dùng biểu đồ làm bằng chứng.
- Với Slide 4, dùng sơ đồ mũi tên thay vì đọc từng dòng mã nguồn.
- Với Slide 6, giải thích rằng trục của box plot là thang log và outlier không bị xóa.
- Không nói “mùa vụ đã được chứng minh”; chỉ nói “có dấu hiệu mùa vụ” vì dữ liệu mới có khoảng hai năm.
- Không nói “giá cao làm giảm nhu cầu” nếu chỉ dựa trên tương quan.
- Không gọi tuần không bán là dữ liệu thiếu; đó là Quantity bằng 0 sau khi tạo panel.
