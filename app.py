import streamlit as st
import pandas as pd
import os
import smtplib
import time
import io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 設定網頁標題 ---
st.set_page_config(page_title="衛生組評分系統", layout="wide", page_icon="🧹")

# ==========================================
# 0. 基礎設定與時區
# ==========================================
TW_TZ = pytz.timezone('Asia/Taipei')

# Google Sheet 網址
SHEET_URL = "https://docs.google.com/spreadsheets/d/1nrX4v-K0xr-lygiBXrBwp4eWiNi9LY0-LIr-K1vBHDw/edit#gid=0"

# 定義分頁名稱
SHEET_TABS = {
    "main": "main_data",        # 存成績
    "settings": "settings",     # 存開學日
    "roster": "roster",         # 全校名單
    "inspectors": "inspectors", # 糾察隊名單
    "duty": "duty",             # 晨掃輪值
    "teachers": "teachers",     # 導師名單
    "appeals": "appeals"        # 申訴紀錄
}

# 暫存圖片路徑
IMG_DIR = "evidence_photos"
if not os.path.exists(IMG_DIR):
    os.makedirs(IMG_DIR)

# 完整欄位定義
EXPECTED_COLUMNS = [
    "日期", "週次", "班級", "評分項目", "檢查人員",
    "內掃原始分", "外掃原始分", "垃圾原始分", "垃圾內掃原始分", "垃圾外掃原始分", "晨間打掃原始分", "手機人數",
    "備註", "違規細項", "照片路徑", "登錄時間", "修正", "晨掃未到者", "紀錄ID"
]

# 申訴欄位定義
APPEAL_COLUMNS = [
    "申訴日期", "班級", "違規日期", "違規項目", "原始扣分", "申訴理由", "佐證照片", "處理狀態", "登錄時間"
]

# ==========================================
# 1. Google Sheets 連線與工具函式
# ==========================================

@st.cache_resource
def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("❌ 找不到 secrets 設定，請在 Streamlit Cloud 後台設定 Secrets。")
            return None
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ Google連線失敗: {e}")
        return None

@st.cache_resource(ttl=21600)
def get_spreadsheet_object():
    client = get_gspread_client()
    if not client: return None
    try:
        return client.open_by_url(SHEET_URL)
    except Exception as e:
        st.error(f"❌ 無法開啟試算表連結: {e}")
        return None

def get_worksheet(tab_name):
    max_retries = 3
    wait_time = 2
    for attempt in range(max_retries):
        try:
            sheet = get_spreadsheet_object()
            if not sheet: return None
            try:
                return sheet.worksheet(tab_name)
            except gspread.WorksheetNotFound:
                cols = 20
                if tab_name == "appeals": cols = 10
                return sheet.add_worksheet(title=tab_name, rows=100, cols=cols)
        except Exception as e:
            if "429" in str(e):
                time.sleep(wait_time * (attempt + 1))
                continue
            else:
                st.error(f"❌ 無法讀取分頁 '{tab_name}': {e}")
                return None
    st.error(f"❌ 讀取分頁 '{tab_name}' 失敗。")
    return None

def clean_id(val):
    try:
        if pd.isna(val) or val == "": return ""
        val_float = float(val)
        val_int = int(val_float)
        return str(val_int).strip()
    except:
        return str(val).strip()

# ==========================================
# 2. 資料讀取
# ==========================================

@st.cache_data(ttl=60)
def load_main_data():
    ws = get_worksheet(SHEET_TABS["main"])
    if not ws: return pd.DataFrame(columns=EXPECTED_COLUMNS)
    try:
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        if df.empty: return pd.DataFrame(columns=EXPECTED_COLUMNS)
        
        for col in EXPECTED_COLUMNS:
            if col not in df.columns: df[col] = ""
            
        if "紀錄ID" not in df.columns or df["紀錄ID"].all() == "":
            df["紀錄ID"] = df.index.astype(str)

        numeric_cols = ["內掃原始分", "外掃原始分", "垃圾原始分", "晨間打掃原始分", "手機人數"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        
        if "週次" in df.columns:
            df["週次"] = pd.to_numeric(df["週次"], errors='coerce').fillna(0).astype(int)

        if "修正" in df.columns:
            df["修正"] = df["修正"].astype(str).apply(lambda x: True if x.upper() == "TRUE" else False)
            
        return df[EXPECTED_COLUMNS]
    except: return pd.DataFrame(columns=EXPECTED_COLUMNS)

def save_entry(new_entry):
    ws = get_worksheet(SHEET_TABS["main"])
    if not ws: st.error("寫入失敗"); return
    if not ws.get_all_values(): ws.append_row(EXPECTED_COLUMNS)

    if "紀錄ID" not in new_entry:
        new_entry["紀錄ID"] = datetime.now(TW_TZ).strftime("%Y%m%d%H%M%S")

    row = []
    for col in EXPECTED_COLUMNS:
        val = new_entry.get(col, "")
        if isinstance(val, bool): val = str(val).upper()
        if col == "日期": val = str(val)
        row.append(val)
    
    try:
        ws.append_row(row)
        st.cache_data.clear()
    except Exception as e:
        if "429" in str(e):
            time.sleep(2)
            ws.append_row(row)
            st.cache_data.clear()
        else:
            st.error(f"寫入錯誤: {e}")

def save_appeal(entry):
    ws = get_worksheet(SHEET_TABS["appeals"])
    if not ws: st.error("申訴系統連線失敗"); return
    if not ws.get_all_values(): ws.append_row(APPEAL_COLUMNS)
    
    row = []
    for col in APPEAL_COLUMNS:
        val = entry.get(col, "")
        row.append(str(val))
    
    try:
        ws.append_row(row)
        st.cache_data.clear()
        return True
    except: return False

@st.cache_data(ttl=60)
def load_appeals():
    ws = get_worksheet(SHEET_TABS["appeals"])
    if not ws: return pd.DataFrame(columns=APPEAL_COLUMNS)
    try:
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except: return pd.DataFrame(columns=APPEAL_COLUMNS)

def overwrite_all_data(df):
    ws = get_worksheet(SHEET_TABS["main"])
    if ws:
        try:
            ws.clear()
            if "修正" in df.columns: df["修正"] = df["修正"].apply(lambda x: "TRUE" if x else "FALSE")
            df = df.fillna("")
            ws.update([df.columns.values.tolist()] + df.values.tolist())
            st.cache_data.clear()
            return True
        except: return False
    return False

@st.cache_data(ttl=21600)
def load_roster_dict():
    ws = get_worksheet(SHEET_TABS["roster"])
    roster_dict = {}
    if ws:
        try:
            df = pd.DataFrame(ws.get_all_records())
            id_col = next((c for c in df.columns if "學號" in c), None)
            class_col = next((c for c in df.columns if "班級" in c), None)
            if id_col and class_col:
                for _, row in df.iterrows():
                    sid = clean_id(row[id_col])
                    if sid: roster_dict[sid] = str(row[class_col]).strip()
        except Exception as e: pass
    return roster_dict

@st.cache_data(ttl=21600)
def load_teacher_emails():
    ws = get_worksheet(SHEET_TABS["teachers"])
    email_dict = {}
    if ws:
        try:
            df = pd.DataFrame(ws.get_all_records())
            class_col = next((c for c in df.columns if "班級" in c), None)
            mail_col = next((c for c in df.columns if "Email" in c or "信箱" in c or "郵件" in c), None)
            name_col = next((c for c in df.columns if "導師" in c or "姓名" in c), None)
            if class_col and mail_col:
                for _, row in df.iterrows():
                    cls = str(row[class_col]).strip()
                    mail = str(row[mail_col]).strip()
                    name = str(row[name_col]).strip() if name_col else "老師"
                    if cls and mail and "@" in mail:
                        email_dict[cls] = {"email": mail, "name": name}
        except: pass
    return email_dict

@st.cache_data(ttl=21600)
def load_inspector_list():
    ws = get_worksheet(SHEET_TABS["inspectors"])
    default = [{"label": "測試人員", "allowed_roles": ["內掃檢查"], "assigned_classes": [], "id_prefix": "測"}]
    if not ws: return default
    try:
        df = pd.DataFrame(ws.get_all_records())
        if df.empty: return default
        inspectors = []
        id_col = next((c for c in df.columns if "學號" in c or "編號" in c), None)
        role_col = next((c for c in df.columns if "負責" in c or "項目" in c), None)
        scope_col = next((c for c in df.columns if "班級" in c or "範圍" in c), None)
        if id_col:
            for _, row in df.iterrows():
                s_id = clean_id(row[id_col])
                s_role = str(row[role_col]).strip() if role_col else ""
                allowed = []
                if "組長" in s_role: allowed = ["內掃檢查", "外掃檢查", "垃圾/回收檢查", "晨間打掃"]
                elif "機動" in s_role: allowed = ["內掃檢查", "外掃檢查", "垃圾/回收檢查"]
                else:
                    if "外掃" in s_role: allowed.append("外掃檢查")
                    if "垃圾" in s_role: allowed.append("垃圾/回收檢查")
                    if "晨" in s_role: allowed.append("晨間打掃")
                    if "內掃" in s_role: allowed.append("內掃檢查")
                if not allowed: allowed = ["內掃檢查"]
                s_classes = []
                if scope_col and str(row[scope_col]):
                    raw = str(row[scope_col])
                    s_classes = [c.strip() for c in raw.replace("、", ";").replace(",", ";").split(";") if c.strip()]
                prefix = s_id[0] if len(s_id) > 0 else "X"
                inspectors.append({"label": f"學號: {s_id}", "allowed_roles": allowed, "assigned_classes": s_classes, "id_prefix": prefix})
        return inspectors if inspectors else default
    except: return default

@st.cache_data(ttl=60)
def get_daily_duty(target_date):
    ws = get_worksheet(SHEET_TABS["duty"])
    if not ws: return [], "error"
    try:
        df = pd.DataFrame(ws.get_all_records())
        if df.empty: return [], "no_data"
        date_col = next((c for c in df.columns if "日期" in c), None)
        id_col = next((c for c in df.columns if "學號" in c), None)
        loc_col = next((c for c in df.columns if "地點" in c), None)
        if date_col and id_col:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce').dt.date
            t_date = target_date if isinstance(target_date, date) else target_date.date()
            today_df = df[df[date_col] == t_date]
            res = []
            for _, row in today_df.iterrows():
                res.append({"學號": clean_id(row[id_col]), "掃地區域": str(row[loc_col]).strip() if loc_col else "", "已完成打掃": False})
            return res, "success"
        return [], "missing_cols"
    except: return [], "error"

@st.cache_data(ttl=21600)
def load_settings():
    ws = get_worksheet(SHEET_TABS["settings"])
    config = {"semester_start": "2025-08-25"}
    if ws:
        try:
            data = ws.get_all_values()
            for row in data:
                if len(row)>=2 and row[0] == "semester_start": config["semester_start"] = row[1]
        except: pass
    return config

def save_setting(key, val):
    ws = get_worksheet(SHEET_TABS["settings"])
    if ws:
        try:
            cell = ws.find(key)
            if cell: ws.update_cell(cell.row, cell.col+1, val)
            else: ws.append_row([key, val])
            st.cache_data.clear()
            return True
        except: return False
    return False

def send_email(to_email, subject, body):
    sender_email = st.secrets["system_config"]["smtp_email"]
    sender_password = st.secrets["system_config"]["smtp_password"]
    if not sender_email or not sender_password: return False, "Secrets 未設定 Email"
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        return True, "發送成功"
    except Exception as e: return False, str(e)

def check_duplicate_record(df, check_date, inspector, role, target_class=None):
    if df.empty: return False
    try:
        df["日期Str"] = df["日期"].astype(str)
        check_date_str = str(check_date)
        mask = (df["日期Str"] == check_date_str) & (df["檢查人員"] == inspector) & (df["評分項目"] == role)
        if target_class:
            mask = mask & (df["班級"] == target_class)
        return not df[mask].empty
    except:
        return False

# ==========================================
# 3. 主程式介面
# ==========================================
SYSTEM_CONFIG = load_settings()
ROSTER_DICT = load_roster_dict()
INSPECTOR_LIST = load_inspector_list()
TEACHER_MAILS = load_teacher_emails()

def get_week_num(d):
    try:
        start = datetime.strptime(SYSTEM_CONFIG["semester_start"], "%Y-%m-%d").date()
        if isinstance(d, datetime): d = d.date()
        return max(0, ((d - start).days // 7) + 1)
    except: return 0

grades = ["一年級", "二年級", "三年級"]
dept_config = {"商經科": 3, "應英科": 1, "資處科": 1, "家政科": 2, "服裝科": 2}
class_labels = ["甲", "乙", "丙"]
all_classes = []
structured_classes = []
for dept, count in dept_config.items():
    for grade in grades:
        g_num = grade[0]
        dept_short = {"商經科": "商", "應英科": "英"}.get(dept, dept[:1])
        for i in range(count):
            c_name = f"{dept_short}{g_num}{class_labels[i]}"
            all_classes.append(c_name)
            structured_classes.append({"grade": grade, "name": c_name})

now_tw = datetime.now(TW_TZ)
today_tw = now_tw.date()

st.sidebar.title("🏫 功能選單")
app_mode = st.sidebar.radio("請選擇模式", ["我是糾察隊(評分)", "我是班上衛生股長", "衛生組後台"])

if st.sidebar.checkbox("顯示系統連線狀態", value=True):
    if get_gspread_client(): st.sidebar.success("✅ Google Sheets 連線正常")
    else: st.sidebar.error("❌ 連線失敗")

# --- 模式1: 糾察評分 ---
if app_mode == "我是糾察隊(評分)":
    st.title("📝 衛生糾察評分系統")
    if "team_logged_in" not in st.session_state: st.session_state["team_logged_in"] = False
    
    if not st.session_state["team_logged_in"]:
        with st.expander("🔐 身份驗證", expanded=True):
            input_code = st.text_input("請輸入隊伍通行碼", type="password")
            if st.button("登入"):
                if input_code == st.secrets["system_config"]["team_password"]:
                   st.session_state["team_logged_in"] = True
                   st.rerun()
                else: st.error("通行碼錯誤")
    
    if st.session_state["team_logged_in"]:
        prefixes = sorted(list(set([p["id_prefix"] for p in INSPECTOR_LIST])))
        prefix_labels = [f"{p}開頭" for p in prefixes]
        if not prefix_labels:
            st.warning("找不到糾察名單，請通知老師在後台建立名單 (Sheet: inspectors)。")
        else:
            selected_prefix_label = st.radio("步驟 1：選擇開頭", prefix_labels, horizontal=True)
            selected_prefix = selected_prefix_label[0]
            filtered_inspectors = [p for p in INSPECTOR_LIST if p["id_prefix"] == selected_prefix]
            inspector_name = st.radio("步驟 2：點選身份", [p["label"] for p in filtered_inspectors])
            current_inspector_data = next((p for p in INSPECTOR_LIST if p["label"] == inspector_name), None)
            allowed_roles = current_inspector_data.get("allowed_roles", ["內掃檢查"])
            # 刪除「晨間打掃」選項，改由衛生組後台處理
            allowed_roles = [r for r in allowed_roles if r != "晨間打掃"]
            
            st.markdown("---")
            col_date, col_role = st.columns(2)
            input_date = col_date.date_input("檢查日期", today_tw)
            if len(allowed_roles) > 1: role = col_role.radio("請選擇檢查項目", allowed_roles, horizontal=True)
            else: role = allowed_roles[0]; col_role.info(f"📋 您的負責項目：**{role}**")
            
            week_num = get_week_num(input_date)
            st.caption(f"📅 第 {week_num} 週")
            
            main_df = load_main_data()

        elif role == "垃圾/回收檢查":
                st.info("🗑️ 全校垃圾檢查 (每日每班上限扣2分)")
                trash_cat = st.radio("違規項目", ["一般垃圾", "紙類", "網袋", "其他回收"], horizontal=True)
                with st.form("trash_form"):
                    t_data = [{"班級": c, "無簽名": False, "無分類": False} for c in all_classes]
                    edited_t_df = st.data_editor(pd.DataFrame(t_data), hide_index=True, height=400, use_container_width=True)
                    if st.form_submit_button("送出"):
                        base = {"日期": input_date, "週次": week_num, "檢查人員": inspector_name, "登錄時間": now_tw.strftime("%Y-%m-%d %H:%M:%S"), "修正": False}
                        cnt = 0
                        for _, row in edited_t_df.iterrows():
                            vios = []
                            if row["無簽名"]: vios.append("無簽名")
                            if row["無分類"]: vios.append("無分類")
                            if vios:
                                save_entry({**base, "班級": row["班級"], "評分項目": role, "垃圾原始分": len(vios), "備註": f"{trash_cat}-{'、'.join(vios)}", "違規細項": trash_cat})
                                cnt += 1
                        st.success(f"已登記 {cnt} 班" if cnt else "無違規")
                        st.rerun()

            else:
                st.markdown("### 🏫選擇班級")
                if assigned_classes: selected_class = st.radio("請點選班級", assigned_classes)
                else:
                    g = st.radio("年級", grades, horizontal=True)
                    selected_class = st.radio("班級", [c["name"] for c in structured_classes if c["grade"] == g], horizontal=True)
                
                if selected_class:
                    if check_duplicate_record(main_df, input_date, inspector_name, role, selected_class):
                         st.warning(f"⚠️ 注意：您今天已經評過「{selected_class}」了！")

                    st.info(f"📍 正在評分：**{selected_class}**")
                    with st.form("scoring_form", clear_on_submit=True):
                        in_s = 0; out_s = 0; ph_c = 0; note = ""
                        if role == "內掃檢查":
                            if st.radio("結果", ["❌ 違規", "✨ 乾淨"], horizontal=True) == "❌ 違規":
                                in_s = st.number_input("內掃扣分 (上限2分)", 0); note = st.text_input("說明", placeholder="黑板未擦"); ph_c = st.number_input("手機人數 (無上限)", 0)
                            else: note = "【優良】"
                        elif role == "外掃檢查":
                            if st.radio("結果", ["❌ 違規", "✨ 乾淨"], horizontal=True) == "❌ 違規":
                                out_s = st.number_input("外掃扣分 (上限2分)", 0); note = st.text_input("說明", placeholder="走廊垃圾"); ph_c = st.number_input("手機人數 (無上限)", 0)
                            else: note = "【優良】"

                        is_fix = st.checkbox("🚩 修正單"); files = st.file_uploader("照片", accept_multiple_files=True)
                        if st.form_submit_button("送出"):
                            path_str = ""
                            if files:
                                paths = [os.path.join(IMG_DIR, f"{input_date}_{now_tw.strftime('%H%M%S')}_{i}.jpg") for i in range(len(files))]
                                for f, p in zip(files, paths): 
                                    with open(p, "wb") as w: w.write(f.getbuffer())
                                path_str = ";".join(paths)
                            save_entry({"日期": input_date, "週次": week_num, "檢查人員": inspector_name, "登錄時間": now_tw.strftime("%Y-%m-%d %H:%M:%S"), "修正": is_fix, "班級": selected_class, "評分項目": role, "內掃原始分": in_s, "外掃原始分": out_s, "手機人數": ph_c, "備註": note, "照片路徑": path_str})
                            st.toast(f"✅ 已儲存：{selected_class}"); st.rerun()

# --- 模式2: 衛生股長 (整合申訴功能) ---
elif app_mode == "我是班上衛生股長":
    st.title("🔎 班級查詢 & 違規申訴")
    df = load_main_data()
    if not df.empty:
        st.write("請依照步驟選擇：")
        g = st.radio("步驟 1：選擇年級", grades, horizontal=True)
        class_options = [c["name"] for c in structured_classes if c["grade"] == g]

        # 確保在選擇班級前，先設定預設或上次的選擇
        if 'cls_selected' not in st.session_state or st.session_state.cls_selected not in class_options:
            cls = class_options[0] if class_options else None
            if cls: st.session_state.cls_selected = cls
        else:
            cls = st.session_state.cls_selected

        cls = st.radio("步驟 2：選擇班級", class_options, horizontal=True, index=class_options.index(cls) if cls in class_options else 0)
        st.session_state.cls_selected = cls # 儲存選擇

        st.divider()

        # 使用 if cls 確保有選擇的班級，並進行篩選
        if cls:
            # 篩選資料：只顯示選定班級的紀錄
            c_df = df[df["班級"] == cls].sort_values("登錄時間", ascending=False).copy()
        else:
            c_df = pd.DataFrame()
        
        # 計算3天前的日期
        three_days_ago = date.today() - timedelta(days=3)
        
        if not c_df.empty:
            st.subheader(f"📊 {cls}近期紀錄")
            for idx, r in c_df.iterrows():
                total_raw = r['內掃原始分']+r['外掃原始分']+r['垃圾原始分']+r['晨間打掃原始分']
                phone_msg = f" | 📱手機: {r['手機人數']}" if r['手機人數'] > 0 else ""
                
                # 外框顯示
                with st.expander(f"{r['日期']} - {r['評分項目']} (扣分: {total_raw}){phone_msg}"):
                    st.write(f"📝 說明: {r['備註']}")
                    st.caption(f"檢查人員: {r['檢查人員']}")
                    if total_raw > 2 and r['晨間打掃原始分'] == 0:
                         st.info("💡系統提示：單項每日扣分上限為 2 分 (手機、晨掃除外)，最終成績將由後台自動計算上限。")

                    # 修改點2：申訴功能整合在紀錄下方
                    # 判斷是否為3天內 + 有扣分
                    record_date_obj = pd.to_datetime(r['日期']).date() if isinstance(r['日期'], str) else r['日期']
                    
                    if record_date_obj >= three_days_ago and (total_raw > 0 or r['手機人數'] > 0):
                        st.markdown("---")
                        st.markdown("#### 🚨 我要申訴")
                        # 為每個紀錄建立唯一的表單 key
                        form_key = f"appeal_form_{r['紀錄ID']}_{idx}"
                        with st.form(form_key):
                            reason = st.text_area("申訴理由 (請詳細說明)", height=80, placeholder="例如：已經改善完成，附上照片證明...")
                            proof_file = st.file_uploader("上傳佐證照片 (必填)", type=["jpg", "png", "jpeg"], key=f"file_{idx}")
                            
                            if st.form_submit_button("提交申訴"):
                                if not reason:
                                    st.error("❌ 請填寫申訴理由")
                                elif not proof_file:
                                    st.error("❌ 請上傳佐證照片")
                                else:
                                    # 儲存照片
                                    timestamp = datetime.now(TW_TZ).strftime('%Y%m%d%H%M%S')
                                    ext = proof_file.name.split('.')[-1]
                                    fname = f"appeal_{cls}_{timestamp}.{ext}"
                                    fpath = os.path.join(IMG_DIR, fname)
                                    with open(fpath, "wb") as f:
                                        f.write(proof_file.getbuffer())
                                        
                                    # 儲存申訴資料
                                    appeal_entry = {
                                        "申訴日期": str(date.today()),
                                        "班級": cls,
                                        "違規日期": str(r["日期"]),
                                        "違規項目": f"{r['評分項目']} ({r['備註']})",
                                        "原始扣分": str(total_raw),
                                        "申訴理由": reason,
                                        "佐證照片": fpath,
                                        "處理狀態": "待處理",
                                        "登錄時間": datetime.now(TW_TZ).strftime("%Y-%m-%d %H:%M:%S")
                                    }
                                    if save_appeal(appeal_entry):
                                        st.success("✅ 申訴已提交！請等待衛生組審核。")
                                    else:
                                        st.error("提交失敗，請稍後再試。")
                    elif total_raw > 0:
                        st.caption("⏳ 已超過 3 天申訴期限，無法申訴。")
                        
        else: st.info("無紀錄")

# --- 模式3: 後台 ---
elif app_mode == "衛生組後台":
    st.title("⚙️ 管理後台")
    pwd = st.text_input("管理密碼", type="password")
    
    if pwd == st.secrets["system_config"]["admin_password"]:
        tab1, tab2, tab3_new, tab4, tab5 = st.tabs(["📊 成績報表", "📧 寄送通知", "🧹 晨間打掃", "📄 名單管理", "📣 申訴管理"])
        
        # 1. 成績報表
        with tab1:
            st.subheader("成績報表")
            st.caption("計算規則：內掃/外掃/垃圾 每日上限扣2分 | 手機與晨掃無上限")
            df = load_main_data()
            all_classes_df = pd.DataFrame(all_classes, columns=["班級"])
            
            if not df.empty:
                valid_weeks = sorted(df[df["週次"]>0]["週次"].unique())
                selected_weeks = st.multiselect("選擇週次", valid_weeks, default=valid_weeks[-1:] if valid_weeks else [])
                
                if selected_weeks:
                    wdf = df[df["週次"].isin(selected_weeks)].copy()
                    
                    daily_agg = wdf.groupby(["日期", "班級"]).agg({
                        "內掃原始分": "sum", "外掃原始分": "sum", "垃圾原始分": "sum",
                        "晨間打掃原始分": "sum", "手機人數": "sum"
                    }).reset_index()

                    daily_agg["內掃結算"] = daily_agg["內掃原始分"].apply(lambda x: min(x, 2))
                    daily_agg["外掃結算"] = daily_agg["外掃原始分"].apply(lambda x: min(x, 2))
                    daily_agg["垃圾結算"] = daily_agg["垃圾原始分"].apply(lambda x: min(x, 2))
                    
                    daily_agg["每日總扣分"] = (daily_agg["內掃結算"] + daily_agg["外掃結算"] + 
                                               daily_agg["垃圾結算"] + daily_agg["晨間打掃原始分"] + daily_agg["手機人數"])

                    violation_report = daily_agg.groupby("班級")["每日總扣分"].sum().reset_index()
                    violation_report.columns = ["班級", "總扣分"]
                    
                    final_report = pd.merge(all_classes_df, violation_report, on="班級", how="left")
                    final_report["總扣分"] = final_report["總扣分"].fillna(0)
                    final_report["總成績"] = 90 - final_report["總扣分"]
                    final_report = final_report.sort_values("總成績", ascending=False)
                    
                    try:
                       st.dataframe(final_report.style.format("{:.0f}").background_gradient(cmap="RdYlGn", subset=["總成績"], vmin=60, vmax=90))
                    except:
                       st.dataframe(final_report)
                    
                    csv = final_report.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥下載統計報表(CSV)", csv, f"report_weeks_{selected_weeks}.csv")
                else: st.info("請選擇週次")
            else: st.warning("無資料")
            
        # 2. 寄送通知
        with tab2:
            st.subheader("📧 每日違規通知")
            target_date = st.date_input("選擇日期", today_tw)
            if "mail_preview" not in st.session_state: st.session_state.mail_preview = None

            if st.button("🔍 搜尋當日違規 (並預覽收件人)"):
                df = load_main_data()
                try:
                    df["日期Obj"] = pd.to_datetime(df["日期"], errors='coerce').dt.date
                    day_df = df[df["日期Obj"] == target_date]
                except: day_df = pd.DataFrame()
                
                if not day_df.empty:
                    stats = day_df.groupby("班級")[["內掃原始分", "外掃原始分", "垃圾原始分", "晨間打掃原始分", "手機人數"]].sum().reset_index()
                    stats["內掃"] = stats["內掃原始分"].clip(upper=2)
                    stats["外掃"] = stats["外掃原始分"].clip(upper=2)
                    stats["垃圾"] = stats["垃圾原始分"].clip(upper=2)
                    stats["當日總扣分"] = stats["內掃"] + stats["外掃"] + stats["垃圾"] + stats["晨間打掃原始分"] + stats["手機人數"]
                    violation_classes = stats[stats["當日總扣分"] > 0]
                    
                    if not violation_classes.empty:
                        preview_data = []
                        for _, row in violation_classes.iterrows():
                            cls_name = row["班級"]
                            score = row["當日總扣分"]
                            t_name = "❌ 缺導師名單"; t_email = "❌ 無法寄送"; status = "異常"
                            if cls_name in TEACHER_MAILS:
                                t_info = TEACHER_MAILS[cls_name]
                                t_name = t_info['name']; t_email = t_info['email']; status = "準備寄送"
                            preview_data.append({"班級": cls_name, "當日總扣分": score, "導師姓名": t_name, "收件信箱": t_email, "狀態": status})
                        st.session_state.mail_preview = pd.DataFrame(preview_data)
                        st.success(f"找到 {len(violation_classes)} 筆違規班級")
                    else: st.session_state.mail_preview = None; st.info("今日無違規")
                else: st.session_state.mail_preview = None; st.info("今日無資料")

            if st.session_state.mail_preview is not None:
                st.write("### 📨 寄送預覽清單"); st.dataframe(st.session_state.mail_preview)
                if st.button("🚀 確認寄出信件"):
                    bar = st.progress(0); success_count = 0; total = len(st.session_state.mail_preview)
                    for idx, row in st.session_state.mail_preview.iterrows():
                        if row["狀態"] == "準備寄送":
                            subject = f"衛生評分通知 ({target_date}) - {row['班級']}"
                            content = f"{row['導師姓名']} 老師您好：\n\n貴班今日({target_date}) 衛生評分總扣分為：{row['當日總扣分']} 分。\n(內掃/外掃/垃圾每日上限扣2分)\n請協助督導，謝謝。\n\n衛生組敬上"
                            is_sent, _ = send_email(row["收件信箱"], subject, content)
                            if is_sent: success_count += 1
                        bar.progress((idx + 1) / total)
                    st.success(f"✅ 寄送完成！成功寄出 {success_count} 封。"); st.session_state.mail_preview = None


          # 這是新的 tab3_new: 晨間打掃評分
        with tab3_new:
            st.subheader("🧹 晨間打掃評分 (限組長使用)")
            main_df = load_main_data()

            # 使用組長身份資訊作為評分者
            inspector_name = "衛生組長 (系統登錄)" 

            col_date, col_score = st.columns(2)
            input_date = col_date.date_input("點名日期", today_tw)
            morning_score = col_score.number_input("每人扣分 (預設1分/無上限)", min_value=1, step=1, value=1)

            week_num = get_week_num(input_date)
        
            if check_duplicate_record(main_df, input_date, inspector_name, "晨間打掃"):
                st.warning(f"⚠️ 系統偵測：您今天 ({input_date}) 已經送出過「晨間打掃」的紀錄囉！")

            duty_list, status = get_daily_duty(input_date)

            if status == "success":
                st.markdown(f"### 📋 {input_date} 晨掃點名")
                total_duty = len(duty_list)
                st.metric("今日應到人數", f"{total_duty} 人")

                with st.form("admin_morning_form", clear_on_submit=True):
                    # 晨掃表格
                    edited_df = st.data_editor(pd.DataFrame(duty_list), 
                                               column_config={"已完成打掃": st.column_config.CheckboxColumn(default=False), 
                                                              "學號": st.column_config.TextColumn(disabled=True), 
                                                              "掃地區域": st.column_config.TextColumn(disabled=True)}, 
                                               hide_index=True, use_container_width=True)

                    if st.form_submit_button("送出晨掃紀錄"):
                        base = {"日期": input_date, "週次": week_num, "檢查人員": inspector_name, 
                                "登錄時間": now_tw.strftime("%Y-%m-%d %H:%M:%S"), "修正": False}
                        absent = edited_df[edited_df["已完成打掃"] == False]

                        if absent.empty:
                            st.success("🎉 全員到齊！")
                        else:
                            count = 0
                            for _, r in absent.iterrows():
                                tid = clean_id(r["學號"])
                                tloc = r["掃地區域"]
                                stu_class = ROSTER_DICT.get(tid, f"查無({tid})")
                                # 儲存紀錄 (使用組長身份、設定好的扣分)
                                save_entry({**base, "班級": stu_class, "評分項目": "晨間打掃", 
                                            "晨間打掃原始分": morning_score, "備註": f"晨掃未到 ({tloc}) - 學號:{tid}", 
                                            "晨掃未到者": tid})
                                count += 1
                            st.error(f"⚠️ 已登記 {count} 人未到，共扣 {count * morning_score} 分")
                        st.rerun()

            elif status == "no_data": st.warning("無輪值資料")
            else: st.error("讀取失敗")
        
        # 5. 名單說明
        with tab5:
            st.info("請至 Google Sheets 修改：roster, inspectors, duty, teachers, appeals")
            if st.button("🔄 重新讀取名單"): st.cache_data.clear(); st.success("快取已清除")
            
        # 6. 申訴管理
        with tab6:
            st.subheader("📣 申訴案件管理")
            appeals_df = load_appeals()
            if not appeals_df.empty:
                st.dataframe(appeals_df)
                st.caption("提示：目前僅提供檢視功能，狀態更改請至 Google Sheets (分頁 appeals) 操作")
            else:
                st.info("目前無申訴案件")
    else:
        st.error("密碼錯誤")


