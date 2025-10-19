# Hướng dẫn deploy lên Render (Streamlit)
## 1) Chuẩn bị repo
Đảm bảo repo có các file:
- `app.py`
- `requirements.txt`
- `config.toml`
- `README.md`
- `render.yaml` (file này)

## 2) Tạo dịch vụ trên Render từ YAML
1. Push toàn bộ lên GitHub.
2. Vào https://render.com → **New** → **Blueprint** (From YAML).
3. Chọn repo chứa `render.yaml` → **Apply**.

## 3) Thiết lập biến môi trường
Sau khi dịch vụ tạo xong, vào tab **Environment**:
- Thêm `FB_APP_ID` = App ID của bạn
- Thêm `FB_APP_SECRET` = App Secret của bạn

> Không cần đặt `PORT` — Render sẽ tự truyền vào `$PORT`. Start command đã dùng biến này.

## 4) Build & chạy
Render sẽ tự:
- `pip install -r requirements.txt`
- chạy `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`

Khi xong, mở URL Render cấp để truy cập ứng dụng.

## 5) Lỗi thường gặp
- *Bad Gateway/Không lên trang*: kiểm tra lại start command và `config.toml`.
- *ModuleNotFoundError*: bổ sung thư viện vào `requirements.txt` rồi redeploy.
- *Không gọi được Graph API*: kiểm tra `FB_APP_ID`, `FB_APP_SECRET` và token bạn nhập trong UI.

Chúc bạn triển khai thành công!
