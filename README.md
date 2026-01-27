# Masothue.com Scraper

Công cụ tự động thu thập thông tin doanh nghiệp từ trang web `masothue.com` dựa trên danh sách tên công ty đầu vào.

## Tính năng

- **Giao diện trực quan**: Sử dụng Streamlit dễ dàng thao tác.
- **Tự động hóa trình duyệt**: Sử dụng Selenium (với `undetected-chromedriver`) để giả lập hành vi người dùng, giảm thiểu khả năng bị chặn.
- **Chế độ Fast Mode**: Sử dụng `cloudscraper` để tăng tốc độ thu thập dữ liệu.
- **Hỗ trợ Proxy**:
    - Danh sách Proxy thủ công (tải lên file .txt).
    - Tự động xoay vòng Proxy.
- **Hỗ trợ Extension**: Cho phép tải lên Chrome Extension (ví dụ: giải Captcha, quản lý Proxy).
- **Cơ chế Resume**: Tự động lưu tiến độ (Checkpoint) và cho phép tiếp tục cào dữ liệu nếu bị gián đoạn.
- **Vượt Cloudflare**: Tích hợp logic tự động phát hiện và xử lý Cloudflare Turnstile.
- **Xuất dữ liệu**: Kết quả được lưu dưới dạng file CSV.

## Yêu cầu hệ thống

- Python 3.8 trở lên
- Google Chrome (phiên bản mới nhất)

## Cài đặt

1.  **Clone hoặc tải dự án về máy.**

2.  **Cài đặt các thư viện cần thiết:**

    Mở terminal tại thư mục dự án và chạy lệnh:

    ```bash
    pip install -r requirements.txt
    ```

## Hướng dẫn sử dụng

1.  **Khởi chạy ứng dụng:**

    ```bash
    streamlit run app.py
    ```

    Trình duyệt sẽ tự động mở giao diện ứng dụng tại địa chỉ `http://localhost:8501`.

2.  **Tải lên dữ liệu đầu vào:**
    - Chuẩn bị file Excel (`.xlsx`) hoặc CSV (`.csv`) chứa danh sách công ty cần tra cứu.
    - **Quan trọng**: File phải có cột tên là **"Người mua bảo hiểm"** chứa tên các công ty.
    - Nhấn nút "Browse files" để tải file lên.

3.  **Cấu hình (Tùy chọn):**
    - **Extension**: Nếu cần dùng extension (ví dụ để giải captcha), tải lên file `.zip` của extension đó.
    - **Proxy (Tính năng này em đang update lại) **:
        - Chọn "Manual List (File)" để tải lên file `.txt` chứa danh sách proxy (mỗi dòng một proxy `ip:port`).
        - Chọn "No Proxy" nếu chạy trực tiếp bằng IP của máy.
    - **Fast Mode**: Tích chọn "⚡ Fast Mode (Cloudscraper)" để tăng tốc độ (khuyên dùng).
    - **Only scrape Companies**: Lọc chỉ giữ lại các dòng có từ khóa công ty (TNHH, CP, v.v.).
    - **Crawl Detailed Info**: Tích chọn để vào từng trang chi tiết lấy đầy đủ thông tin (Mã số thuế, Địa chỉ, Người đại diện...). Nếu bỏ chọn, chỉ lấy Tên và Link.

4.  **Bắt đầu cào dữ liệu:**
    - Nhấn nút **"1. Launch Browser"** để mở trình duyệt Chrome điều khiển tự động.
        - *Lưu ý*: Lúc này bạn có thể cần xử lý thủ công các quảng cáo hoặc captcha nếu xuất hiện lần đầu.
    - Sau khi trình duyệt đã mở và sẵn sàng, nhấn nút **"2. Start Scraping"** để bắt đầu quá trình.

5.  **Theo dõi và Kết quả:**
    - Thanh tiến trình sẽ hiển thị trạng thái hiện tại.
    - Kết quả được lưu tự động vào file `scraped_results_<tên_file_gốc>.csv` trong thư mục dự án.
    - Khi hoàn tất, bạn có thể tải file kết quả về trực tiếp từ giao diện.

## Cơ chế Resume (Tiếp tục khi bị lỗi)

Nếu quá trình cào bị gián đoạn (mất mạng, lỗi trình duyệt, tắt máy...), bạn chỉ cần:
1. Chạy lại ứng dụng.
2. Tải lên **cùng một file đầu vào**.
3. Ứng dụng sẽ tự động phát hiện file Checkpoint (`checkpoint_<tên_file>.json`) và file kết quả cũ.
4. Nhấn "Start Scraping", ứng dụng sẽ hỏi hoặc tự động tiếp tục từ dòng dữ liệu tiếp theo, không cào lại từ đầu.

## Cấu trúc thư mục

- `app.py`: Mã nguồn chính của ứng dụng.
- `requirements.txt`: Danh sách các thư viện phụ thuộc.
- `chrome_profile/`: Thư mục lưu profile của trình duyệt (cookies, cache) để duy trì đăng nhập/phiên làm việc.
- `extracted_extensions/`: Thư mục chứa các extension đã giải nén.
- `scraper.log`: File log ghi lại chi tiết quá trình chạy và lỗi (nếu có).

## Lưu ý

- Không tắt cửa sổ Chrome được mở tự động trong quá trình chạy.
- Nếu gặp lỗi liên tục với Cloudflare, hãy thử thay đổi Proxy hoặc tắt Fast Mode để chạy chậm hơn nhưng ổn định hơn.
- Để sử dụng proxy thuận lợi thì nên sử dụng extension lúc mở browswer, đồng thời ưu tiên sử dụng proxy xoay để tránh bị chặn.