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
st.set_page_config(page_title="衛生糾察評分系統 (完整雲端版)", layout="wide", page_icon="🧹")

# ==========================================
# 0. 基礎設定與時區
# ==========================================
TW_TZ = pytz.timezone('Asia/Taipei')

# Google Sheet 網址 (請確認您的 Sheet 網址)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1nrX4v-K0xr-lygiBXrBwp4eWiNi9LY0-LIr-K1vBHDw/edit#gid=0"

# 定義分頁名稱 (請在 Google Sheet 下方建立這 5 個分頁)
SHEET_TABS = {
    "main": "main_data",        # 存成績
    "settings": "settings",     # 存開學日
    "roster": "roster",         # 全校名單
    "inspectors": "inspectors", # 糾察隊名單
    "duty": "duty"              # 晨掃輪值
}

# 暫存圖片路徑
IMG_DIR = "evidence_photos"
if not os.path.exists(IMG_DIR): os.makedirs(IMG_DIR)

# 完整欄位定義 (對應你原本的程式碼)
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
            # 自動建立缺少的表
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
        
        if "修正" in df.columns:
            df["修正"] = df["修正"].astype(str).apply(lambda x: True if x.upper() == "TRUE" else False)
            
        return df[EXPECTED_COLUMNS]
    except: return pd.DataFrame(columns=EXPECTED_COLUMNS)

def save_entry(new_entry):
    """寫入一筆資料"""
    ws = get_worksheet(SHEET_TABS["main"])
    if not ws: st.error("寫入失敗"); return
    
    if not ws.get_all_values():
        ws.append_row(EXPECTED_COLUMNS) # 如果是空的先寫標題

    row = []
    for col in EXPECTED_COLUMNS:
        val = new_entry.get(col, "")
        if isinstance(val, bool): val = str(val).upper()
        if col == "日期": val = str(val)
        row.append(val)
        
    ws.append_row(row)
    st.cache_data.clear() # 清除快取

@st.cache_data(ttl=300)
def load_roster_dict():
    """讀取全校名單回傳字典 {學號: 班級}"""
    ws = get_worksheet(SHEET_TABS["roster"])
    roster_dict = {}
    if ws:
        try:
            df = pd.DataFrame(ws.get_all_records())
            # 自動找欄位名稱
            id_col = next((c for c in df.columns if "學號" in c), None)
            class_col = next((c for c in df.columns if "班級" in c), None)
            if id_col and class_col:
                for _, row in df.iterrows():
                    sid = str(row[id_col]).strip()
                    if sid: roster_dict[sid] = str(row[class_col]).strip()
        except: pass
    return roster_dict

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
                
                # 權限判斷 (還原原本邏輯)
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

                inspectors.append({
                    "label": f"學號: {s_id}",
                    "allowed_roles": allowed,
                    "assigned_classes": s_classes,
                    "id_prefix": s_id[0] if s_id else "X"
                })
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
                res.append({
                    "學號": str(row[id_col]).strip(),
                    "掃地區域": str(row[loc_col]).strip() if loc_col else "",
                    "已完成打掃": False
                })
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

# ==========================================
# 3. 變數準備
# ==========================================
SYSTEM_CONFIG = load_settings()
ROSTER_DICT = load_roster_dict()
INSPECTOR_LIST = load_inspector_list()

def get_week_num(d):
    try:
        start = datetime.strptime(SYSTEM_CONFIG["semester_start"], "%Y-%m-%d").date()
        if isinstance(d, datetime): d = d.date()
        return max(0, ((d - start).days // 7) + 1)
    except: return 0

# 建構班級結構 (還原你原本的邏輯)
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

# --- 模式1: 糾察評分 (完全還原) ---
if app_mode == "我是糾察隊 (評分)":
    st.title("📝 衛生糾察評分系統 (雲端版)")

    if "team_logged_in" not in st.session_state: st.session_state["team_logged_in"] = False
    
    # 登入區塊
    if not st.session_state["team_logged_in"]:
        with st.expander("🔐 身份驗證", expanded=True):
            input_code = st.text_input("請輸入隊伍通行碼", type="password")
            if st.button("登入"):
                # 從 Secrets 讀取密碼
                if input_code == st.secrets["system_config"]["team_password"]:
                    st.session_state["team_logged_in"] = True
                    st.rerun()
                else: st.error("通行碼錯誤")
    
    # 已登入區塊
    if st.session_state["team_logged_in"]:
        # 1. 選擇人員
        st.markdown("### 👤 請選擇您的學號/身份")
        prefixes = sorted(list(set([p["id_prefix"] for p in INSPECTOR_LIST])))
        prefix_labels = [f"{p}開頭" for p in prefixes]
        
        if not prefix_labels:
            st.warning("找不到糾察名單，請通知老師在後台建立名單。")
        else:
            selected_prefix_label = st.radio("步驟 1：選擇開頭", prefix_labels, horizontal=True)
            selected_prefix = selected_prefix_label[0]
            filtered_inspectors = [p for p in INSPECTOR_LIST if p["id_prefix"] == selected_prefix]
            inspector_options = [p["label"] for p in filtered_inspectors]
            inspector_name = st.radio("步驟 2：點選身份", inspector_options)
            
            current_inspector_data = next((p for p in INSPECTOR_LIST if p["label"] == inspector_name), None)
            allowed_roles = current_inspector_data.get("allowed_roles", ["內掃檢查"])
            assigned_classes = current_inspector_data.get("assigned_classes", [])
            
            st.markdown("---")
            
            # 2. 選擇日期與項目
            col_date, col_role = st.columns(2)
            input_date = col_date.date_input("檢查日期", today_tw)
            
            if len(allowed_roles) > 1: role = col_role.radio("請選擇檢查項目", allowed_roles, horizontal=True)
            else:
                col_role.info(f"📋 您的負責項目：**{allowed_roles[0]}**")
                role = allowed_roles[0]
            
            week_num = get_week_num(input_date)
            st.caption(f"📅 第 {week_num} 週")

            # 3. 根據角色進入不同評分介面 (還原邏輯)
            if role == "晨間打掃":
                # --- 晨掃邏輯 ---
                duty_list, status = get_daily_duty(input_date)
                if status == "success":
                    st.markdown(f"### 📋 {input_date} 晨掃點名")
                    st.info("👇 請在 **「已完成打掃」** 欄位打勾。")
                    
                    with st.form("morning_form", clear_on_submit=True):
                        edited_df = st.data_editor(
                            pd.DataFrame(duty_list), 
                            column_config={
                                "已完成打掃": st.column_config.CheckboxColumn("✅ 已完成打掃", default=False),
                                "掃地區域": st.column_config.TextColumn("掃地區域", disabled=True),
                                "學號": st.column_config.TextColumn("學號", disabled=True),
                            }, 
                            disabled=["學號", "掃地區域"], 
                            hide_index=True, 
                            use_container_width=True
                        )
                        morning_score = st.number_input("未到扣分 (每人)", min_value=0, step=1, value=1)
                        
                        if st.form_submit_button("送出晨掃評分", use_container_width=True):
                            base = {"日期": input_date, "週次": week_num, "檢查人員": inspector_name, "登錄時間": now_tw.strftime("%Y-%m-%d %H:%M:%S"), "修正": False}
                            absent = edited_df[edited_df["已完成打掃"] == False]
                            
                            if absent.empty: st.success("🎉 全員到齊！")
                            else:
                                for _, r in absent.iterrows():
                                    tid = r["學號"]
                                    tloc = r["掃地區域"]
                                    # 寫入 Google Sheet
                                    entry = {**base, "班級": ROSTER_DICT.get(tid, "待確認"), "評分項目": role, "晨間打掃原始分": morning_score, "備註": f"晨掃未到 ({tloc})", "晨掃未到者": tid}
                                    save_entry(entry)
                                st.success(f"✅ 已登記 {len(absent)} 位未到學生！")
                            st.rerun()
                elif status == "no_data": st.warning(f"⚠️ {input_date} 沒有輪值資料，請確認 Google Sheet 'duty' 分頁。")
                else: st.error("無法讀取輪值表")

            elif role == "垃圾/回收檢查":
                # --- 垃圾檢查邏輯 ---
                st.info("🗑️ 全校垃圾檢查")
                trash_cat = st.radio("違規項目", ["一般垃圾", "紙類", "網袋", "其他回收"], horizontal=True)
                
                with st.form("trash_form"):
                    # 建立全校表格
                    t_data = [{"班級": c, "無簽名": False, "無分類": False} for c in all_classes]
                    edited_t_df = st.data_editor(pd.DataFrame(t_data), hide_index=True, height=400, use_container_width=True)
                    
                    if st.form_submit_button("送出垃圾評分"):
                        base = {"日期": input_date, "週次": week_num, "檢查人員": inspector_name, "登錄時間": now_tw.strftime("%Y-%m-%d %H:%M:%S"), "修正": False}
                        cnt = 0
                        for _, row in edited_t_df.iterrows():
                            vios = []
                            if row["無簽名"]: vios.append("無簽名")
                            if row["無分類"]: vios.append("無分類")
                            if vios:
                                entry = {**base, "班級": row["班級"], "評分項目": role, "垃圾原始分": len(vios), "備註": f"{trash_cat}-{'、'.join(vios)}", "違規細項": trash_cat}
                                save_entry(entry); cnt += 1
                        if cnt: st.success(f"已登記 {cnt} 班")
                        else: st.success("無違規")
                        st.rerun()

            else:
                # --- 一般內掃/外掃評分 (還原你的階層選單) ---
                st.markdown("### 🏫 選擇班級")
                selected_class = None
                
                # 如果有指定班級 (來自 Inspectors Sheet)
                if assigned_classes: 
                    selected_class = st.radio("請點選班級", assigned_classes)
                else:
                    # 原本的完整選單
                    s_grade = st.radio("步驟 1：選擇年級", grades, horizontal=True)
                    # 這裡用原本的 structured_classes 邏輯
                    class_opts = [c["name"] for c in structured_classes if c["grade"] == s_grade]
                    selected_class = st.radio("步驟 2：選擇班級", class_opts, horizontal=True)
                
                if selected_class:
                    st.info(f"📍 正在評分：**{selected_class}**")
                    
                    with st.form("scoring_form", clear_on_submit=True):
                        in_s = 0; out_s = 0; ph_c = 0; note = ""
                        
                        # 依照不同項目顯示不同輸入框
                        if role == "內掃檢查":
                            check = st.radio("檢查結果", ["❌ 發現違規", "✨ 很乾淨"], horizontal=True)
                            if check == "❌ 發現違規":
                                st.subheader("違規事項")
                                in_s = st.number_input("🧹 內掃扣分", min_value=0, step=1)
                                note = st.text_input("違規說明", placeholder="例：黑板未擦")
                                ph_c = st.number_input("📱 玩手機人數", min_value=0, step=1)
                            else: note = "【優良】環境整潔"
                        
                        elif role == "外掃檢查":
                            check = st.radio("檢查結果", ["❌ 發現違規", "✨ 很乾淨"], horizontal=True)
                            if check == "❌ 發現違規":
                                st.subheader("違規事項")
                                out_s = st.number_input("🍂 外掃扣分", min_value=0, step=1)
                                note = st.text_input("違規說明", placeholder="例：走廊有垃圾")
                                ph_c = st.number_input("📱 玩手機人數", min_value=0, step=1)
                            else: note = "【優良】環境整潔"

                        st.write("")
                        is_fix = st.checkbox("🚩 這是一筆修正資料")
                        files = st.file_uploader("📸 上傳照片 (雲端重啟後會清除)", accept_multiple_files=True)
                        
                        if st.form_submit_button("送出評分", use_container_width=True):
                            # 處理照片路徑 (暫存)
                            path_str = ""
                            if files:
                                paths = []
                                ts = now_tw.strftime("%H%M%S")
                                for i, f in enumerate(files):
                                    fname = f"{input_date}_{ts}_{i}.jpg"
                                    fp = os.path.join(IMG_DIR, fname)
                                    with open(fp, "wb") as w: w.write(f.getbuffer())
                                    paths.append(fp)
                                path_str = ";".join(paths)
                            
                            final_note = f"【修正】 {note}" if is_fix and "【修正】" not in note else note
                            
                            # 存入 Google Sheet
                            entry = {
                                "日期": input_date, "週次": week_num, "檢查人員": inspector_name,
                                "登錄時間": now_tw.strftime("%Y-%m-%d %H:%M:%S"), "修正": is_fix,
                                "班級": selected_class, "評分項目": role,
                                "內掃原始分": in_s, "外掃原始分": out_s, "手機人數": ph_c,
                                "備註": final_note, "照片路徑": path_str
                            }
                            save_entry(entry)
                            st.toast(f"✅ 已儲存：{selected_class}", icon="🎉")
                            st.rerun()

# --- 模式2: 衛生股長 (保持簡單讀取) ---
elif app_mode == "我是班上衛生股長":
    st.title("🔎 班級查詢")
    df = load_main_data()
    if not df.empty:
        g = st.radio("年級", grades, horizontal=True)
        cls = st.selectbox("班級", [c["name"] for c in structured_classes if c["grade"] == g])
        
        c_df = df[df["班級"] == cls].sort_values("登錄時間", ascending=False)
        if not c_df.empty:
            for _, r in c_df.iterrows():
                # 顯示邏輯
                with st.expander(f"{r['日期']} - {r['評分項目']} (扣分: {r['內掃原始分']+r['外掃原始分']+r['垃圾原始分']})"):
                    st.write(f"說明: {r['備註']}")
                    if r['手機人數']: st.error(f"手機人數: {r['手機人數']}")
        else: st.info("無紀錄")

# --- 模式3: 後台 (功能強化) ---
elif app_mode == "衛生組後台":
    st.title("⚙️ 管理後台")
    pwd = st.text_input("密碼", type="password")
    if pwd == st.secrets["system_config"]["admin_password"]:
        
        tab1, tab2 = st.tabs(["📅 開學日設定", "📥 資料管理"])
        
        with tab1:
            curr = SYSTEM_CONFIG["semester_start"]
            nd = st.date_input("開學日", datetime.strptime(curr, "%Y-%m-%d").date())
            if st.button("更新日期"):
                if save_setting("semester_start", str(nd)): st.success("已更新，請重新整理")
                else: st.error("更新失敗")
                
        with tab2:
            st.info("💡 名單管理請直接至 Google Sheets 修改對應分頁：roster, inspectors, duty")
            if st.button("🔄 重新讀取名單"):
                st.cache_data.clear()
                st.success("已更新快取")
            
            # 下載 CSV
            if st.button("下載成績 CSV"):
                df = load_main_data()
                st.download_button("下載", df.to_csv(index=False).encode('utf-8-sig'), "data.csv")
    else:
        st.error("密碼錯誤")
