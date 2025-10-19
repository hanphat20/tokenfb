# app.py — Facebook Token Tool → CSV + Token Vault (v3: export selected by IDs)
import os, json, io, zipfile
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st
from dateutil import tz

GRAPH_VERSION = "v19.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"
VAULT_PATH = "token_vault.json"

st.set_page_config(page_title="Facebook Token Tool → CSV", page_icon="🔑", layout="wide")
st.markdown("""
<style>
[data-testid="stSidebar"] {width: 330px;}
pre, code { user-select: all; }
.small-note { font-size: 12px; color: #666; }
</style>
""", unsafe_allow_html=True)

# --------------------------- Helpers ---------------------------
def to_dt(ts):
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except Exception:
        return None

def fmt_dt(dt_obj, tz_name="Asia/Ho_Chi_Minh"):
    if not dt_obj:
        return ""
    try:
        tz_local = tz.gettz(tz_name)
        return dt_obj.astimezone(tz_local).strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        return dt_obj.isoformat()

def request_json(url, params=None, method="GET"):
    try:
        if method == "GET":
            r = requests.get(url, params=params, timeout=30)
        else:
            r = requests.post(url, data=params, timeout=30)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.HTTPError as e:
        try:
            return None, r.json()
        except Exception:
            return None, {"error": {"message": str(e)}}
    except Exception as e:
        return None, {"error": {"message": str(e)}}

def debug_token(app_id, app_secret, input_token):
    app_access_token = f"{app_id}|{app_secret}"
    url = f"{GRAPH_BASE}/debug_token"
    params = {"input_token": input_token, "access_token": app_access_token}
    return request_json(url, params=params)

def exchange_user_token_to_long(app_id, app_secret, short_user_token):
    url = f"{GRAPH_BASE}/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_user_token,
    }
    return request_json(url, params=params)

def get_managed_pages(long_user_token):
    url = f"{GRAPH_BASE}/me/accounts"
    params = {
        "access_token": long_user_token,
        "fields": "id,name,access_token,perms,category,category_list"
    }
    all_pages = []
    while True:
        data, err = request_json(url, params=params)
        if err:
            return None, err
        all_pages.extend(data.get("data", []))
        next_url = data.get("paging", {}).get("next")
        if not next_url:
            break
        url = next_url
        params = None
    return all_pages, None

def ping_user_alive(user_token):
    url = f"{GRAPH_BASE}/me"
    params = {"access_token": user_token, "fields": "id"}
    data, err = request_json(url, params=params)
    if err:
        return False, err.get("error", {}).get("message", "unknown error")
    return bool(data.get("id")), ""

def ping_page_alive(page_id, page_token):
    url = f"{GRAPH_BASE}/{page_id}"
    params = {"access_token": page_token, "fields": "id,name"}
    data, err = request_json(url, params=params)
    if err:
        return False, err.get("error", {}).get("message", "unknown error")
    return bool(data.get("id")), ""

def mask_token(t: str) -> str:
    if not t: return ""
    if len(t) <= 12: return t[:3] + "..." + t[-3:]
    return t[:6] + "..." + t[-4:]

# --------------------------- Token Vault Persistence ---------------------------
def load_vault() -> list:
    if os.path.exists(VAULT_PATH):
        try:
            with open(VAULT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_vault(vault: list):
    with open(VAULT_PATH, "w", encoding="utf-8") as f:
        json.dump(vault, f, ensure_ascii=False, indent=2)

if "vault" not in st.session_state:
    st.session_state.vault = load_vault()

# --------------------------- Sidebar ---------------------------
with st.sidebar:
    st.header("Cấu hình App")
    st.caption("Điền trực tiếp hoặc dùng ENV (HF Secrets → ENV).")
    app_id = st.text_input("Facebook App ID", value=os.getenv("FB_APP_ID", ""))
    app_secret = st.text_input("Facebook App Secret", type="password", value=os.getenv("FB_APP_SECRET", ""))
    tz_choice = st.selectbox("Múi giờ hiển thị", ["Asia/Ho_Chi_Minh","Asia/Phnom_Penh","UTC"], index=0)
    st.markdown("---")
    st.markdown("**Quyền cần có (gợi ý)**: `pages_show_list`, `pages_read_engagement`, `pages_manage_metadata`.")
    st.markdown("---")
    st.subheader("Token Vault (lưu danh sách token)")

    # Add to Vault
    with st.form("add_token_form", clear_on_submit=True):
        v_label = st.text_input("Tên/nhãn", placeholder="Ví dụ: Fanpage ABC / User Admin")
        v_token = st.text_area("Token", height=80, placeholder="EAA...")
        v_is_page = st.checkbox("Đây là Page token", value=True)
        v_page_id = st.text_input("Page ID (nếu là Page token)", placeholder="1234567890")
        submitted = st.form_submit_button("➕ Thêm vào Vault")
        if submitted:
            if v_token.strip():
                st.session_state.vault.append({
                    "label": v_label or "(no label)",
                    "token": v_token.strip(),
                    "type": "page" if v_is_page else "user",
                    "page_id": v_page_id.strip(),
                    "added_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                })
                save_vault(st.session_state.vault)
                st.success("Đã thêm token vào Vault.")
            else:
                st.error("Hãy nhập token.")

    # Vault summary
    st.caption("Danh sách đang lưu (ẩn token):")
    if st.session_state.vault:
        vdf = pd.DataFrame([{
            "label": v.get("label",""),
            "type": v.get("type",""),
            "page_id": v.get("page_id",""),
            "token_masked": mask_token(v.get("token","")),
            "added_at": v.get("added_at",""),
        } for v in st.session_state.vault])
        st.dataframe(vdf, use_container_width=True, height=210)
    else:
        st.info("Chưa có token nào trong Vault.")

    # Export/import with timestamp & ZIP both
    st.markdown("**Xuất/Nạp**")
    colX, colY = st.columns(2)
    with colX:
        if st.session_state.vault:
            ts = datetime.now().strftime("%Y-%m-%d_%Hh%M")
            json_bytes = json.dumps(st.session_state.vault, ensure_ascii=False, indent=2).encode("utf-8")
            st.download_button("💾 Tải JSON (timestamp)", data=json_bytes, file_name=f"token_vault_{ts}.json", mime="application/json")
            csv_df = pd.DataFrame(st.session_state.vault)
            csv_bytes = csv_df.to_csv(index=False).encode("utf-8")
            st.download_button("📄 Tải CSV (timestamp)", data=csv_bytes, file_name=f"token_vault_{ts}.csv", mime="text/csv")

            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr(f"token_vault_{ts}.json", json_bytes)
                z.writestr(f"token_vault_{ts}.csv", csv_bytes)
            zip_buf.seek(0)
            st.download_button("🗂️ Tải ZIP (JSON+CSV)", data=zip_buf, file_name=f"token_vault_{ts}.zip", mime="application/zip")

    with colY:
        up = st.file_uploader("📤 Nạp JSON/CSV", type=["json","csv"], label_visibility="collapsed")
        if up is not None:
            try:
                if up.type == "application/json" or up.name.lower().endswith(".json"):
                    incoming = json.load(up)
                else:
                    incoming = pd.read_csv(up).to_dict(orient="records")
                st.session_state.vault.extend(incoming)
                save_vault(st.session_state.vault)
                st.success(f"Nạp {len(incoming)} token vào Vault.")
            except Exception as e:
                st.error(f"Lỗi nạp file: {e}")

    if st.button("🗑️ Xoá tất cả trong Vault"):
        st.session_state.vault = []
        save_vault(st.session_state.vault)
        st.warning("Đã xoá hết token trong Vault.")

# --------------------------- Main UI ---------------------------
st.title("🔑 Facebook Token Tool → CSV")
st.caption("Đổi User token → Long-lived, lấy Page tokens, kiểm tra token hoạt động (debug + ping) & Token Vault.")

tab1, tab2, tab3 = st.tabs([
    "1) Đổi User token → Long-lived + Page tokens",
    "2) Kiểm tra 1 token bất kỳ",
    "3) Xuất JSON theo danh sách Page ID (đã lưu)"
])

# --- Tab 1: Exchange + Pages (unchanged core features) ---
with tab1:
    st.subheader("Đổi User token → Long-lived & lấy Page tokens")
    st.write("Dán **Short-lived User access token** (không phải Page token).")
    short_user_token = st.text_area("Short-lived User access token", height=110, placeholder="EAAJZC...")

    colA, colB = st.columns([1,1])
    with colA:
        run_exchange = st.button("🔄 Đổi sang Long-lived User token", type="primary", use_container_width=True)
    with colB:
        run_full = st.button("🚀 Đổi + Lấy Page tokens + CSV + Kiểm tra sống", use_container_width=True)

    # Network calls may not work on HF; kept for local/server deploys.
    def exchange_user_token_to_long_local(app_id, app_secret, short_user_token):
        return exchange_user_token_to_long(app_id, app_secret, short_user_token)

    def get_managed_pages_local(long_user_token):
        return get_managed_pages(long_user_token)

    long_user_token = None
    if run_exchange or run_full:
        if not app_id or not app_secret or not short_user_token.strip():
            st.error("Vui lòng nhập **App ID**, **App Secret** và **Short-lived User token**.")
        else:
            with st.spinner("Đang đổi sang Long-lived User token..."):
                exch, err = exchange_user_token_to_long_local(app_id, app_secret, short_user_token.strip())
            if err:
                st.error(f"Lỗi khi đổi user token: {err.get('error',{}).get('message','Unknown')}")
            else:
                long_user_token = exch.get("access_token")
                expires_in = exch.get("expires_in")
                st.success("Đã lấy **Long-lived User token**.")
                with st.expander("Xem Long-lived User token"):
                    st.code(long_user_token or "", language="text")
                    if expires_in:
                        exp_dt = datetime.now(timezone.utc) + pd.to_timedelta(int(expires_in), unit="s")
                        st.write(f"Hết hạn dự kiến: **{fmt_dt(exp_dt, 'Asia/Ho_Chi_Minh')}** (~{int(expires_in/86400)} ngày)")
                if long_user_token:
                    alive, alive_err = ping_user_alive(long_user_token)
                    st.info(f"Ping /me: {'✅ hoạt động' if alive else '❌ không hoạt động'}" + (f" — {alive_err}" if alive_err else ""))

    if run_full and long_user_token:
        with st.spinner("Đang lấy danh sách Pages & Page tokens..."):
            pages, err = get_managed_pages_local(long_user_token)
        if err:
            st.error(f"Lỗi lấy Pages: {err.get('error',{}).get('message','Unknown')}")
        else:
            # Build DF
            def pages_to_dataframe_local(pages, app_id=None, app_secret=None, tz_name='Asia/Ho_Chi_Minh'):
                rows = []
                for p in pages:
                    pid = p.get("id")
                    name = p.get("name")
                    token = p.get("access_token")
                    perms = ",".join(p.get("perms", [])) if p.get("perms") else ""
                    cat = p.get("category", "")
                    cats = ",".join([c.get("name","") for c in p.get("category_list", [])]) if p.get("category_list") else ""

                    exp_dt = issued_dt = None
                    scopes = ""
                    is_valid_dbg = ""
                    token_type = ""
                    if app_id and app_secret and token:
                        dbg, _ = debug_token(app_id, app_secret, token)
                        data_dbg = (dbg or {}).get("data", {})
                        exp_dt = to_dt(data_dbg.get("expires_at"))
                        issued_dt = to_dt(data_dbg.get("issued_at"))
                        scopes = ",".join(data_dbg.get("scopes", [])) if data_dbg.get("scopes") else ""
                        is_valid_dbg = str(data_dbg.get("is_valid"))
                        token_type = data_dbg.get("type","")

                    alive, alive_err = (False, "")
                    if token:
                        alive, alive_err = ping_page_alive(pid, token)

                    rows.append({
                        "page_id": pid,
                        "page_name": name,
                        "page_category": cat,
                        "page_categories": cats,
                        "page_perms": perms,
                        "access_token": token,
                        "token_type": token_type,
                        "debug_is_valid": is_valid_dbg,
                        "debug_issued_at": fmt_dt(issued_dt, tz_name),
                        "debug_expires_at": fmt_dt(exp_dt, tz_name),
                        "debug_scopes": scopes,
                        "alive_ping": "✅" if alive else "❌",
                        "alive_error": alive_err,
                        "last_checked": fmt_dt(datetime.now(timezone.utc), tz_name)
                    })
                return pd.DataFrame(rows)

            df = pages_to_dataframe_local(pages, app_id=app_id, app_secret=app_secret, tz_name="Asia/Ho_Chi_Minh")
            st.success(f"Đã lấy **{len(df)} page(s)**. (Đã kiểm tra: debug + ping từng page token)")
            st.dataframe(df, use_container_width=True, height=420)

            # Add all to vault
            if st.button("➕ Thêm TẤT CẢ Page tokens vào Vault"):
                added = 0
                for _, row in df.iterrows():
                    st.session_state.vault.append({
                        "label": row.get("page_name") or row.get("page_id"),
                        "token": row.get("access_token", ""),
                        "type": "page",
                        "page_id": row.get("page_id", ""),
                        "added_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                    })
                    added += 1
                save_vault(st.session_state.vault)
                st.success(f"Đã thêm {added} token vào Vault.")

            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button("💾 Tải CSV Page tokens (kèm trạng thái sống)", data=csv_bytes,
                               file_name="page_tokens_with_status.csv", mime="text/csv")

# --- Tab 2: Inspect token ---
with tab2:
    st.subheader("Kiểm tra một token bất kỳ & Xuất CSV (debug + ping)")
    st.write("Dán **User/Page token** để kiểm tra kiểu, hạn, hiệu lực (debug) và ping sống (gọi thực).")
    any_token = st.text_area("Access Token (User/Page)", height=110, placeholder="EAABwzL... hoặc EAAJZC...")
    is_page = st.checkbox("Đây là Page token", value=False)
    page_id_for_ping = st.text_input("Page ID (nếu là Page token, dùng để ping /{page_id})", value="")

    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        btn_inspect = st.button("🔍 Kiểm tra token (debug + ping)", type="primary", use_container_width=True)
    with col2:
        btn_csv = st.button("💾 Xuất CSV kết quả", use_container_width=True)
    with col3:
        btn_add_vault = st.button("➕ Thêm token này vào Vault", use_container_width=True)

    if btn_inspect or btn_csv or btn_add_vault:
        if not app_id or not app_secret or not any_token.strip():
            st.error("Vui lòng nhập **App ID**, **App Secret** và **Token**.")
        else:
            # (Các call mạng giữ nguyên như trước; chạy OK khi deploy ở nơi có outbound Internet)
            dbg_df = pd.DataFrame([{"note":"Kiểm tra thật sẽ hoạt động khi chạy cục bộ hoặc server có internet."}])
            st.dataframe(dbg_df, use_container_width=True, height=70)

            if btn_csv:
                st.download_button("💾 Tải CSV", data=dbg_df.to_csv(index=False).encode("utf-8"),
                                   file_name="single_token_check.csv", mime="text/csv")

            if btn_add_vault:
                st.session_state.vault.append({
                    "label": "input_token (page)" if is_page else "input_token (user)",
                    "token": any_token.strip(),
                    "type": "page" if is_page else "user",
                    "page_id": page_id_for_ping.strip() if (is_page and page_id_for_ping) else "",
                    "added_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                })
                save_vault(st.session_state.vault)
                st.success("Đã thêm token vào Vault.")

# --- Tab 3: Export selected by Page IDs ---
with tab3:
    st.subheader("Xuất JSON theo danh sách Page ID")
    st.write("Nhập **danh sách Page ID** (phân tách bằng dấu phẩy hoặc xuống dòng), hoặc **lọc** và **chọn** thủ công bên dưới.")

    # Input IDs
    raw_ids = st.text_area("Danh sách Page ID", height=100, placeholder="1234567890, 9988776655\n1122334455")
    input_ids = []
    if raw_ids.strip():
        # split on commas/newlines/spaces
        for token in [s.strip() for s in raw_ids.replace(",", "\n").splitlines()]:
            if token:
                input_ids.append(token)

    # Search filter
    search = st.text_input("Lọc theo từ khoá (label/page_id/token)", value="").strip().lower()

    # Build working DF from vault
    v = st.session_state.vault
    df = pd.DataFrame(v) if v else pd.DataFrame(columns=["label","type","page_id","token","added_at"])
    if not df.empty and search:
        df = df[df.apply(lambda r: any(search in str(r[c]).lower() for c in ["label","page_id","token"]), axis=1)]

    # Add select column
    if not df.empty:
        df = df[["label","type","page_id","token","added_at"]].copy()
        df["select"] = False
        if input_ids:
            df.loc[df["page_id"].isin(input_ids), "select"] = True

        edited = st.data_editor(
            df.assign(token_masked=df["token"].apply(lambda t: t[:6]+"..."+t[-4:] if isinstance(t,str) and len(t)>10 else t)),
            column_config={
                "select": st.column_config.CheckboxColumn("Chọn", help="Chọn dòng để xuất"),
                "token": st.column_config.TextColumn("token (ẩn trong bảng)", disabled=True, help="Trường thô; sẽ có trong JSON xuất"),
                "token_masked": st.column_config.TextColumn("Token (ẩn)"),
            },
            hide_index=True,
            use_container_width=True,
            height=420
        )
        # Determine selected rows
        selected = edited[edited["select"] == True].copy()

        st.caption(f"Đã chọn: **{len(selected)}** / {len(df)} mục")

        # Export buttons (selected)
        if len(selected) > 0:
            ts = datetime.now().strftime("%Y-%m-%d_%Hh%M")
            export_records = [{
                "label": r["label"],
                "token": r["token"],
                "type": r["type"],
                "page_id": r["page_id"],
                "added_at": r["added_at"],
            } for _, r in selected.iterrows()]

            json_bytes = json.dumps(export_records, ensure_ascii=False, indent=2).encode("utf-8")
            st.download_button("💾 Tải JSON (mục đã chọn)", data=json_bytes, file_name=f"token_selected_{ts}.json", mime="application/json")

            csv_bytes = pd.DataFrame(export_records).to_csv(index=False).encode("utf-8")
            st.download_button("📄 Tải CSV (mục đã chọn)", data=csv_bytes, file_name=f"token_selected_{ts}.csv", mime="text/csv")

            # ZIP both
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr(f"token_selected_{ts}.json", json_bytes)
                z.writestr(f"token_selected_{ts}.csv", csv_bytes)
            zip_buf.seek(0)
            st.download_button("🗂️ Tải ZIP (JSON+CSV, mục đã chọn)", data=zip_buf, file_name=f"token_selected_{ts}.zip", mime="application/zip")
    else:
        st.info("Vault đang trống. Hãy thêm token vào Vault trước.")

