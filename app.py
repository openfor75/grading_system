import streamlit as st
import pandas as pd
import os
import smtplib
import io
import re
import zipfile
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 設定網頁標題 ---
st.set_page_config(page_title="衛生糾察評分系統 (終極完整版)", layout="wide", page_icon="🧹")

# ==========================================
# 0. 基礎設定與時區
# ==========================================
TW_TZ = pytz.timezone('Asia/Taipei')

# Google Sheet 網址 (請確認您的 Sheet 網址)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1nrX4v-K0xr-lygiBXrBwp4eWiNi9LY0-LIr-K1vBHDw/edit#gid=0"

# 定義分頁名稱 (請在 Google Sheet 下方建立這 6 個分頁)
SHEET_TABS = {
    "main": "main_data",        # 存成績
    "settings": "settings",     # 存開學日
    "roster": "roster",         # 全校名單
    "inspectors": "inspectors", # 糾察隊名單
    "duty": "duty",             # 晨掃輪值
    "teachers": "teachers"      # 導師名單 (NEW!)
}

# 暫存圖片路徑
IMG_DIR = "evidence_photos"
if not os.path.exists(IMG_DIR): os.makedirs(IMG_DIR)

# 完整欄位定義
EXPECTED_COLUMNS = [
    "日期", "週次", "班級", "評分項目", "檢查人員",
    "內掃原始分", "外掃原始分", "垃圾原始分", "垃圾內掃原始分", "垃圾外掃原始分", "晨間打掃原始分", "手機人數",
    "備註", "違規細項", "照片路徑", "登錄時間", "修正", "晨掃未到者"
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

def get_worksheet(tab_name):
    client = get_gspread_client()
    if not client: return None
    try:
        sheet = client.open_by_url(SHEET_URL)
        try:
            return sheet.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            return sheet.add_worksheet(title=tab_name, rows=100, cols=20)
    except Exception as e:
        st.error(f"❌ 無法開啟試算表: {e}")
        return None

# ==========================================
# 2. 資料讀取 (改為讀取分頁)
# ==========================================

@st.cache_data(ttl=60)
def load_main_data():
    """讀取成績"""
    ws = get_worksheet(SHEET_TABS["main"])
    if not ws: return pd.DataFrame(columns=EXPECTED_COLUMNS)
    
    try:
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        if df.empty: return pd.DataFrame(columns=EXPECTED_COLUMNS)
        
        # 補齊欄位
        for col in EXPECTED_COLUMNS:
            if col not in df.columns: df[col] = ""
        
        # 數值轉換
        numeric_cols = ["內掃原始分", "外掃原始分", "垃圾原始分", "垃圾內掃原始分", "垃圾外掃原始分", "晨間打掃原始分", "手機人數"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        
        # 週次轉換為數字
        if "週次" in df.columns:
            df["週次"] = pd.to_numeric(df["週次"], errors='coerce').fillna(0).astype(int)

        if "修正" in df.columns:
            df["修正"] = df["修正"].astype(str).apply(lambda x: True if x.upper() == "TRUE" else False)
            
        return df[EXPECTED_COLUMNS]
    except: return pd.DataFrame(columns=EXPECTED_COLUMNS)

def save_entry(new_entry):
    """寫入一筆資料"""
    ws = get_worksheet(SHEET_TABS["main"])
    if not ws: st.error("寫入失敗"); return
    
    if not ws.get_all_values():
        ws.append_row(EXPECTED_COLUMNS)

    row = []
    for col in EXPECTED_COLUMNS:
        val = new_entry.get(col, "")
        if isinstance(val, bool): val = str(val).upper()
        if col == "日期": val = str(val)
        row.append(val)
        
    ws.append_row(row)
    st.cache_data.clear()

def overwrite_all_data(df):
    """覆寫整張表 (用於刪除功能)"""
    ws = get_worksheet(SHEET_TABS["main"])
    if ws:
        ws.clear()
        # 處理布林值
        if "修正" in df.columns:
            df["修正"] = df["修正"].apply(lambda x: "TRUE" if x else "FALSE")
        df = df.fillna("")
        ws.update([df.columns.values.tolist()] + df.values.tolist())
        st.cache_data.clear()
        return True
    return False

@st.cache_data(ttl=300)
def load_roster_dict():
    """讀取全校名單"""
    ws = get_worksheet(SHEET_TABS["roster"])
    roster_dict = {}
    if ws:
        try:
            df = pd.DataFrame(ws.get_all_records())
            id_col = next((c for c in df.columns if "學號" in c), None)
            class_col = next((c for c in df.columns if "班級" in c), None)
            if id_col and class_col:
                for _, row in df.iterrows():
                    sid = str(row[id_col]).strip()
                    if sid: roster_dict[sid] = str(row[class_col]).strip()
        except: pass
    return roster_dict

@st.cache_data(ttl=300)
def load_teacher_emails():
    """讀取導師 Email (NEW!)"""
    ws = get_worksheet(SHEET_TABS["teachers"])
    email_dict = {}
    if ws:
        try:
            df = pd.DataFrame(ws.get_all_records())
            # 寬容的欄位名稱搜尋
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

@st.cache_data(ttl=300)
def load_inspector_list():
    """讀取糾察名單"""
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
                s_id = str(row[id_col]).strip()
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
                inspectors.append({"label": f"學號: {s_id}", "allowed_roles": allowed, "assigned_classes": s_classes, "id_prefix": s_id[0] if s_id else "X"})
        return inspectors if inspectors else default
    except: return default

@st.cache_data(ttl=60)
def get_daily_duty(target_date):
    """讀取晨掃輪值"""
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
                res.append({"學號": str(row[id_col]).strip(), "掃地區域": str(row[loc_col]).strip() if loc_col else "", "已完成打掃": False})
            return res, "success"
        return [], "missing_cols"
    except: return [], "error"

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
        cell = ws.find(key)
        if cell: ws.update_cell(cell.row, cell.col+1, val)
        else: ws.append_row([key, val])
        st.cache_data.clear()
        return True
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

# ==========================================
# 3. 變數與輔助
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

# ==========================================
# 4. 主程式介面
# ==========================================
now_tw = datetime.now(TW_TZ)
today_tw = now_tw.date()

st.sidebar.title("🏫 功能選單")
app_mode = st.sidebar.radio("請選擇模式", ["我是糾察隊 (評分)", "我是班上衛生股長", "衛生組後台"])

# --- 模式1: 糾察評分 ---
if app_mode == "我是糾察隊 (評分)":
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
            st.warning("找不到糾察名單，請通知老師在後台建立名單。")
        else:
            selected_prefix_label = st.radio("步驟 1：選擇開頭", prefix_labels, horizontal=True)
            selected_prefix = selected_prefix_label[0]
            filtered_inspectors = [p for p in INSPECTOR_LIST if p["id_prefix"] == selected_prefix]
            inspector_name = st.radio("步驟 2：點選身份", [p["label"] for p in filtered_inspectors])
            current_inspector_data = next((p for p in INSPECTOR_LIST if p["label"] == inspector_name), None)
            allowed_roles = current_inspector_data.get("allowed_roles", ["內掃檢查"])
            assigned_classes = current_inspector_data.get("assigned_classes", [])
            
            st.markdown("---")
            col_date, col_role = st.columns(2)
            input_date = col_date.date_input("檢查日期", today_tw)
            if len(allowed_roles) > 1: role = col_role.radio("請選擇檢查項目", allowed_roles, horizontal=True)
            else: role = allowed_roles[0]; col_role.info(f"📋 您的負責項目：**{role}**")
            
            week_num = get_week_num(input_date)
            st.caption(f"📅 第 {week_num} 週")

            if role == "晨間打掃":
                duty_list, status = get_daily_duty(input_date)
                if status == "success":
                    st.markdown(f"### 📋 {input_date} 晨掃點名")
                    with st.form("morning_form", clear_on_submit=True):
                        edited_df = st.data_editor(pd.DataFrame(duty_list), column_config={"已完成打掃": st.column_config.CheckboxColumn(default=False), "學號": st.column_config.TextColumn(disabled=True), "掃地區域": st.column_config.TextColumn(disabled=True)}, hide_index=True, use_container_width=True)
                        morning_score = st.number_input("未到扣分", min_value=0, step=1, value=1)
                        if st.form_submit_button("送出"):
                            base = {"日期": input_date, "週次": week_num, "檢查人員": inspector_name, "登錄時間": now_tw.strftime("%Y-%m-%d %H:%M:%S"), "修正": False}
                            absent = edited_df[edited_df["已完成打掃"] == False]
                            if absent.empty: st.success("🎉 全員到齊！")
                            else:
                                for _, r in absent.iterrows():
                                    tid = r["學號"]; tloc = r["掃地區域"]
                                    save_entry({**base, "班級": ROSTER_DICT.get(tid, "待確認"), "評分項目": role, "晨間打掃原始分": morning_score, "備註": f"晨掃未到 ({tloc})", "晨掃未到者": tid})
                                st.success(f"已登記 {len(absent)} 人")
                            st.rerun()
                elif status == "no_data": st.warning("無輪值資料")
                else: st.error("讀取失敗")

            elif role == "垃圾/回收檢查":
                st.info("🗑️ 全校垃圾檢查")
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
                st.markdown("### 🏫 選擇班級")
                if assigned_classes: selected_class = st.radio("請點選班級", assigned_classes)
                else:
                    g = st.radio("年級", grades, horizontal=True)
                    selected_class = st.radio("班級", [c["name"] for c in structured_classes if c["grade"] == g], horizontal=True)
                
                if selected_class:
                    st.info(f"📍 正在評分：**{selected_class}**")
                    with st.form("scoring_form", clear_on_submit=True):
                        in_s = 0; out_s = 0; ph_c = 0; note = ""
                        if role == "內掃檢查":
                            if st.radio("結果", ["❌ 違規", "✨ 乾淨"], horizontal=True) == "❌ 違規":
                                in_s = st.number_input("內掃扣分", 0); note = st.text_input("說明", placeholder="黑板未擦"); ph_c = st.number_input("手機人數", 0)
                            else: note = "【優良】"
                        elif role == "外掃檢查":
                            if st.radio("結果", ["❌ 違規", "✨ 乾淨"], horizontal=True) == "❌ 違規":
                                out_s = st.number_input("外掃扣分", 0); note = st.text_input("說明", placeholder="走廊垃圾"); ph_c = st.number_input("手機人數", 0)
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

# --- 模式2: 衛生股長 (略) ---
elif app_mode == "我是班上衛生股長":
    st.title("🔎 班級查詢")
    df = load_main_data()
    if not df.empty:
        g = st.radio("年級", grades, horizontal=True)
        cls = st.selectbox("班級", [c["name"] for c in structured_classes if c["grade"] == g])
        c_df = df[df["班級"] == cls].sort_values("登錄時間", ascending=False)
        if not c_df.empty:
            for _, r in c_df.iterrows():
                with st.expander(f"{r['日期']} - {r['評分項目']} (扣: {r['內掃原始分']+r['外掃原始分']+r['垃圾原始分']})"):
                    st.write(f"說明: {r['備註']}"); 
                    if r['手機人數']: st.error(f"手機: {r['手機人數']}")
        else: st.info("無紀錄")

# --- 模式3: 後台 (功能全開) ---
elif app_mode == "衛生組後台":
    st.title("⚙️ 管理後台")
    pwd = st.text_input("管理密碼", type="password")
    
    if pwd == st.secrets["system_config"]["admin_password"]:
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 成績報表", "📧 寄送通知", "🛠️ 資料刪除", "📅 設定", "📄 名單管理"])
        
        # 1. 成績報表 (含週次篩選)
        with tab1:
            st.subheader("成績報表")
            df = load_main_data()
            if not df.empty:
                valid_weeks = sorted(df[df["週次"]>0]["週次"].unique())
                selected_weeks = st.multiselect("選擇週次", valid_weeks, default=valid_weeks[-1:] if valid_weeks else [])
                
                if selected_weeks:
                    wdf = df[df["週次"].isin(selected_weeks)].copy()
                    
                    dg = wdf.groupby(["班級"]).agg({
                        "內掃原始分": "sum", "外掃原始分": "sum", "垃圾原始分": "sum",
                        "晨間打掃原始分": "sum", "手機人數": "sum"
                    }).reset_index()
                    dg["總扣分"] = dg["內掃原始分"] + dg["外掃原始分"] + dg["垃圾原始分"] + dg["晨間打掃原始分"] + dg["手機人數"]
                    dg["總成績"] = 90 - dg["總扣分"]
                    dg = dg.sort_values("總成績", ascending=False)
                    
                    try:
                        st.dataframe(
                            dg.style.format("{:.0f}")
                            .background_gradient(cmap="RdYlGn", subset=["總成績"], vmin=60, vmax=90)
                        )
                    except Exception as e:
                        st.warning("⚠️ 顏色渲染失敗，顯示原始表格")
                        st.dataframe(dg)
                    
                    csv = dg.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 下載統計報表 (CSV)", csv, f"report_weeks_{selected_weeks}.csv")
                else: st.info("請選擇週次")
            else: st.warning("無資料")
            
        # 2. 寄送通知 (恢復功能)
        with tab2:
            st.subheader("📧 每日違規通知")
            st.info("系統會從 Google Sheet 的 `teachers` 分頁讀取 Email。")
            target_date = st.date_input("選擇日期", today_tw)
            
            if st.button("🔍 搜尋當日違規並準備寄信"):
                df = load_main_data()
                # 篩選當日資料
                try:
                    df["日期Obj"] = pd.to_datetime(df["日期"], errors='coerce').dt.date
                    day_df = df[df["日期Obj"] == target_date]
                except: day_df = pd.DataFrame()
                
                if not day_df.empty:
                    # 找出有扣分的班級
                    stats = day_df.groupby("班級")[["內掃原始分", "外掃原始分", "垃圾原始分", "晨間打掃原始分", "手機人數"]].sum().reset_index()
                    stats["當日總扣分"] = stats.iloc[:, 1:].sum(axis=1)
                    violation_classes = stats[stats["當日總扣分"] > 0]
                    
                    if not violation_classes.empty:
                        st.write("準備寄信給以下班級：")
                        st.dataframe(violation_classes)
                        
                        if st.button("🚀 確認寄出"):
                            bar = st.progress(0)
                            count = 0
                            for idx, row in violation_classes.iterrows():
                                cls_name = row["班級"]
                                score = row["當日總扣分"]
                                
                                if cls_name in TEACHER_MAILS:
                                    t_info = TEACHER_MAILS[cls_name]
                                    subject = f"衛生評分通知 ({target_date}) - {cls_name}"
                                    content = f"{t_info['name']} 老師您好：\n\n貴班今日({target_date}) 衛生評分總扣分為：{score} 分。\n請協助督導，謝謝。\n\n衛生組 敬上"
                                    
                                    success, msg = send_email(t_info['email'], subject, content)
                                    if success: count += 1
                                else:
                                    st.warning(f"找不到 {cls_name} 的 Email")
                                bar.progress((idx + 1) / len(violation_classes))
                                
                            st.success(f"✅ 寄信完成！共成功寄出 {count} 封。")
                    else: st.success("🎉 今日全校無違規！")
                else: st.info("今日無評分紀錄")

        # 3. 資料刪除 (NEW!)
        with tab3:
            st.subheader("🛠️ 資料刪除")
            df = load_main_data()
            if not df.empty:
                del_mode = st.radio("刪除模式", ["單筆刪除", "日期區間刪除 (批次)"])
                
                if del_mode == "單筆刪除":
                    # 顯示最近 50 筆供選擇
                    df_display = df.sort_values("登錄時間", ascending=False).head(50).reset_index()
                    # 製作選項標籤
                    options = {row['index']: f"{row['日期']} | {row['班級']} | {row['評分項目']} (ID:{row['index']})" for i, row in df_display.iterrows()}
                    selected_indices = st.multiselect("選擇要刪除的紀錄", options=options.keys(), format_func=lambda x: options[x])
                    
                    if st.button("🗑️ 確認刪除選取項目"):
                        new_df = df.drop(selected_indices)
                        if overwrite_all_data(new_df): st.success("刪除成功！"); st.rerun()
                        else: st.error("刪除失敗")
                        
                elif del_mode == "日期區間刪除 (批次)":
                    c1, c2 = st.columns(2)
                    d_start = c1.date_input("開始日期")
                    d_end = c2.date_input("結束日期")
                    
                    if st.button("⚠️ 刪除此區間所有資料"):
                        # 轉換日期格式進行比較
                        df["d_tmp"] = pd.to_datetime(df["日期"], errors='coerce').dt.date
                        # 保留不在區間內的資料
                        mask = (df["d_tmp"] >= d_start) & (df["d_tmp"] <= d_end)
                        del_count = mask.sum()
                        
                        if del_count > 0:
                            new_df = df[~mask].drop(columns=["d_tmp"])
                            if overwrite_all_data(new_df): st.success(f"已刪除 {del_count} 筆資料"); st.rerun()
                        else: st.warning("此區間無資料")
            else: st.info("目前無資料")

        # 4. 設定
        with tab4:
            st.subheader("系統設定")
            curr = SYSTEM_CONFIG.get("semester_start", "2025-08-25")
            nd = st.date_input("開學日 (第一週週一)", datetime.strptime(curr, "%Y-%m-%d").date())
            if st.button("更新開學日"):
                save_setting("semester_start", str(nd))
                st.success("已更新")
                
        # 5. 名單說明
        with tab5:
            st.info("請直接至 Google Sheets 修改以下分頁，修改後點選重新讀取：")
            st.markdown("- **roster**: 全校學生名單\n- **inspectors**: 糾察隊名單\n- **duty**: 晨掃輪值\n- **teachers**: 導師 Email 名單")
            if st.button("🔄 重新讀取所有名單"):
                st.cache_data.clear()
                st.success("快取已清除，下次操作將讀取最新名單")
    else:
        st.error("密碼錯誤")

