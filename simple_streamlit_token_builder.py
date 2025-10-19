
import json, io, csv
from datetime import datetime, timezone
import streamlit as st

st.set_page_config(page_title="Token JSON Builder (Simple)", page_icon="⚡", layout="centered")
st.title("⚡ Token JSON Builder — đơn giản")
st.caption("Upload 2 file: access_token.json (long-lived user) và accounts.js (/me/accounts). Bấm nút để xuất tokens.json + vault files.")

st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    up_access = st.file_uploader("Tải access_token.json", type=["json"], key="access")
with col2:
    up_accounts = st.file_uploader("Tải accounts.js", type=["json","js"], key="accounts")

with st.expander("Hoặc dán nội dung thủ công (tuỳ chọn)"):
    ta1, ta2 = st.columns(2)
    with ta1:
        paste_access = st.text_area("Nội dung access_token.json", height=160, placeholder='{"access_token":"EA..","token_type":"bearer","expires_in":5180000}')
    with ta2:
        paste_accounts = st.text_area("Nội dung accounts.js (/me/accounts)", height=160, placeholder='{"data":[{"id":"123","name":"Page A","access_token":"EA.."}]}' )

st.markdown("---")
run = st.button("🚀 Tạo tokens.json + vault_import.*", type="primary")

if run:
    try:
        # ---- Load access_token.json ----
        if up_access is not None:
            access_obj = json.load(up_access)
        elif paste_access.strip():
            access_obj = json.loads(paste_access)
        else:
            st.error("Thiếu access_token.json (upload hoặc dán nội dung)")
            st.stop()

        # ---- Load accounts.js ----
        if up_accounts is not None:
            accounts_obj = json.load(up_accounts)
        elif paste_accounts.strip():
            accounts_obj = json.loads(paste_accounts)
        else:
            st.error("Thiếu accounts.js (upload hoặc dán nội dung)")
            st.stop()

        # ---- Extract pages ----
        pages = []
        if isinstance(accounts_obj, dict) and "data" in accounts_obj:
            pages = accounts_obj.get("data", [])
        elif isinstance(accounts_obj, list):
            pages = accounts_obj
        else:
            raise ValueError("accounts.js không đúng định dạng (mong đợi có khóa 'data' hoặc là list)")

        # ---- Build tokens.json ----
        pages_map = {}
        for p in pages:
            pid = str(p.get("id", "")).strip()
            tok = p.get("access_token", "").strip()
            if pid and tok:
                pages_map[pid] = tok

        tokens_payload = {
            "user_long": {
                "access_token": access_obj.get("access_token", ""),
                "token_type": access_obj.get("token_type", ""),
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            },
            "pages": pages_map,
        }

        tokens_bytes = json.dumps(tokens_payload, ensure_ascii=False, indent=2).encode("utf-8")

        # ---- Build vault_import.json ----
        now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        vault_records = []
        for p in pages:
            pid = str(p.get("id", "")).strip()
            tok = p.get("access_token", "").strip()
            if not (pid and tok):
                continue
            vault_records.append({
                "label": p.get("name") or pid,
                "type": "page",
                "page_id": pid,
                "token": tok,
                "added_at": now_ts,
            })

        vault_json = json.dumps(vault_records, ensure_ascii=False, indent=2).encode("utf-8")

        # ---- CSV (no pandas) ----
        csv_buf = io.StringIO()
        writer = csv.DictWriter(csv_buf, fieldnames=["label","type","page_id","token","added_at"])
        writer.writeheader()
        writer.writerows(vault_records)
        csv_bytes = csv_buf.getvalue().encode("utf-8")

        st.success(f"Đã tạo xong: {len(vault_records)} page token.")
        st.download_button("💾 Tải tokens.json", data=tokens_bytes, file_name="tokens.json", mime="application/json", use_container_width=True)
        st.download_button("📄 Tải vault_import.json", data=vault_json, file_name="vault_import.json", mime="application/json", use_container_width=True)
        st.download_button("🗂️ Tải vault_import.csv", data=csv_bytes, file_name="vault_import.csv", mime="text/csv", use_container_width=True)

    except Exception as e:
        st.error(f"Lỗi: {e}")
