import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import os
import json
import smtplib
import io
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta

# --- 設定網頁標題 ---
st.set_page_config(page_title="衛生糾察評分系統 (雲端復刻版)", layout="wide")

# ==========================================
# 0. 基礎設定
# ==========================================
GSHEET_NAME = "衛生糾察評分資料庫"
IMG_DIR = "evidence_photos"
if not os.path.exists(IMG_DIR): os.makedirs(IMG_DIR)

# 這些檔案建議您直接上傳到 GitHub，這樣雲端重啟才不會消失
CONFIG_FILE = "config.json"
ROSTER_FILE = "全校名單.csv" 
DUTY_FILE = "晨掃輪值.csv" 
INSPECTOR_DUTY_FILE = "糾察隊名單.csv" 
TEACHER_MAIL_FILE = "導師名單.csv"

# ==========================================
# 1. Google Sheets 連線與資料庫 (核心)
# ==========================================
def get_gsheet_client():
    if "gcp_service_account" not in st.secrets:
        st.error("⚠️ 請在 Streamlit Secrets 設定 Google 金鑰")
        return None
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"連線失敗: {e}")
        return None

def load_data():
    client = get_gsheet_client()
    if not client: return pd.DataFrame()

    expected_columns = [
        "日期", "週次", "班級", "評分項目", "檢查人員",
        "內掃原始分", "外掃原始分", "垃圾原始分", "垃圾內掃原始分", "垃圾外掃原始分", "晨間打掃原始分", "手機人數", 
        "備註", "違規細項", "照片路徑", "登錄時間", "修正", "晨掃未到者"
    ]

    try:
        sheet = client.open(GSHEET_NAME).sheet1
        data = sheet.get_all_values()
        
        if not data: return pd.DataFrame(columns=expected_columns)
        
        rows = data[1:]
        if not rows: return pd.DataFrame(columns=expected_columns)

        # 1. 統一資料寬度 (v40 防呆邏輯)
        n_cols = len(expected_columns)
        cleaned_rows = []
        for row in rows:
            if len(row) > n_cols: cleaned_rows.append(row[:n_cols])
            elif len(row) < n_cols: cleaned_rows.append(row + [""] * (n_cols - len(row)))
            else: cleaned_rows.append(row)
        
        df = pd.DataFrame(cleaned_rows, columns=expected_columns)

        # 2. 強制轉數字
        numeric_cols = ["內掃原始分", "外掃原始分", "垃圾原始分", "垃圾內掃原始分", "垃圾外掃原始分", "晨間打掃原始分", "手機人數"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

        # 3. 處理布林值
        if "修正" in df.columns:
            df["修正"] = df["修正"].astype(str).apply(lambda x: True if x.upper() == "TRUE" else False)
            
        return df

    except gspread.exceptions.SpreadsheetNotFound:
        # 自動建立試算表
        try:
            sh = client.create(GSHEET_NAME)
            try: sh.share(st.secrets["gcp_service_account"]["client_email"], perm_type='user', role='owner')
            except: pass
            sh.sheet1.append_row(expected_columns)
            st.success("✅ 已自動建立雲端資料庫")
            return pd.DataFrame(columns=expected_columns)
        except: return pd.DataFrame(columns=expected_columns)
    except Exception as e:
        st.error(f"讀取錯誤: {e}")
        return pd.DataFrame(columns=expected_columns)

def save_entry(new_entry):
    client = get_gsheet_client()
    if not client: return

    try:
        sheet = client.open(GSHEET_NAME).sheet1
        
        # 轉字串寫入 (最安全)
        row_values = [
            str(new_entry.get("日期", "")), str(new_entry.get("週次", "")), str(new_entry.get("班級", "")),
            str(new_entry.get("評分項目", "")), str(new_entry.get("檢查人員", "")),
            str(new_entry.get("內掃原始分", 0)), str(new_entry.get("外掃原始分", 0)),
            str(new_entry.get("垃圾原始分", 0)), str(new_entry.get("垃圾內掃原始分", 0)),
            str(new_entry.get("垃圾外掃原始分", 0)), str(new_entry.get("晨間打掃原始分", 0)),
            str(new_entry.get("手機人數", 0)), str(new_entry.get("備註", "")),
            str(new_entry.get("違規細項", "")), str(new_entry.get("照片路徑", "")),
            str(new_entry.get("登錄時間", "")), str(new_entry.get("修正", False)),
            str(new_entry.get("晨掃未到者", ""))
        ]
        
        if not sheet.get_all_values():
             sheet.append_row([
                "日期", "週次", "班級", "評分項目", "檢查人員",
                "內掃原始分", "外掃原始分", "垃圾原始分", "垃圾內掃原始分", "垃圾外掃原始分", "晨間打掃原始分", "手機人數", 
                "備註", "違規細項", "照片路徑", "登錄時間", "修正", "晨掃未到者"
            ])
        
        sheet.append_row(row_values)
        
    except Exception as e:
        st.error(f"寫入雲端失敗: {e}")

# 雲端版刪除 (覆蓋寫入)
def delete_entry(indices_to_delete):
    client = get_gsheet_client()
    if not client: return
    try:
        df = load_data()
        df = df.drop(indices_to_delete)
        
        sheet = client.open(GSHEET_NAME).sheet1
        sheet.clear()
        sheet.append_row(df.columns.tolist())
        sheet.append_rows(df.astype(str).values.tolist())
    except Exception as e:
        st.error(f"刪除失敗: {e}")

# 雲端版批次刪除
def delete_batch(start_date, end_date):
    client = get_gsheet_client()
    if not client: return 0
    try:
        df = load_data()
        if df.empty: return 0
        
        df["日期_dt"] = pd.to_datetime(df["日期"]).dt.date
        mask = (df["日期_dt"] >= start_date) & (df["日期_dt"] <= end_date)
        deleted_count = mask.sum()
        
        df_remaining = df[~mask].drop(columns=["日期_dt"])
        
        sheet = client.open(GSHEET_NAME).sheet1
        sheet.clear()
        sheet.append_row(df_remaining.columns.tolist())
        sheet.append_rows(df_remaining.astype(str).values.tolist())
        return deleted_count
    except Exception as e:
        st.error(f"批次刪除失敗: {e}")
        return 0

# 歷史資料匿名化 (寫回雲端)
def anonymize_history():
    client = get_gsheet_client()
    if not client: return "連線失敗"
    
    df = load_data()
    if df.empty: return "無資料"
    
    count = 0
    # 清洗檢查人員
    if "檢查人員" in df.columns:
        def clean_name(val):
            val = str(val)
            match = re.search(r'\((.*?)\)', val) # 抓括號內的學號
            if match: return match.group(1)
            if val.isdigit(): return val
            return val # 沒括號也沒數字就保留
        
        orig = df["檢查人員"].copy()
        df["檢查人員"] = df["檢查人員"].apply(clean_name)
        count += sum(orig != df["檢查人員"])

    # 清洗晨掃未到
    if "晨掃未到者" in df.columns:
        def clean_absent(val):
            return str(val).split()[0] if len(str(val).split()) > 0 else val
        df["晨掃未到者"] = df["晨掃未到者"].apply(clean_absent)

    if count > 0:
        try:
            sheet = client.open(GSHEET_NAME).sheet1
            sheet.clear()
            sheet.append_row(df.columns.tolist())
            sheet.append_rows(df.astype(str).values.tolist())
            return f"✅ 已清洗 {count} 筆資料"
        except: return "寫入失敗"
    else:
        return "無須清洗"

# ==========================================
# 2. 設定檔與密碼 (優先讀 Secrets)
# ==========================================
def load_config():
    default_config = { "semester_start": "2025-08-25", "admin_password": "1234", "team_password": "0000", "smtp_email": "", "smtp_password": "" }
    if "system_config" in st.secrets: default_config.update(st.secrets["system_config"])
    elif os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding='utf-8') as f: return json.load(f)
        except: pass
    return default_config

def save_config(new_config):
    # 雲端版無法永久修改 secrets，只能存本地 json (重啟後消失)
    # 但為了讓當次操作有效，我們還是存一下
    with open(CONFIG_FILE, "w", encoding='utf-8') as f: json.dump(new_config, f, ensure_ascii=False)

SYSTEM_CONFIG = load_config()

# ==========================================
# 3. CSV 讀取 (支援 v40 的匿名邏輯)
# ==========================================
@st.cache_data
def load_teacher_emails():
    email_dict = {}
    if os.path.exists(TEACHER_MAIL_FILE):
        try:
            df = pd.read_csv(TEACHER_MAIL_FILE, dtype=str)
            if len(df.columns) >= 2:
                for _, row in df.iterrows():
                    # 假設前三欄是: 班級, Email, 姓名(選填)
                    cls = str(row[0]).strip()
                    mail = str(row[1]).strip()
                    name = str(row[2]).strip() if len(row) > 2 else "老師"
                    if "@" in mail: email_dict[cls] = {"email": mail, "name": name}
        except: pass
    return email_dict

@st.cache_data
def load_roster_dict():
    roster_dict = {}
    if os.path.exists(ROSTER_FILE):
        try:
            df = pd.read_csv(ROSTER_FILE, dtype=str)
            if len(df.columns) >= 2:
                for _, row in df.iterrows():
                    roster_dict[str(row[0]).strip()] = str(row[1]).strip()
        except: pass
    return roster_dict
ROSTER_DICT = load_roster_dict()

@st.cache_data
def get_simple_list(filename):
    items = []
    if os.path.exists(filename):
        try:
            df = pd.read_csv(filename, dtype=str)
            if not df.empty: items = df.iloc[:, 0].dropna().astype(str).tolist()
        except: pass
    return items

all_classes = get_simple_list(ROSTER_FILE) 
if not all_classes: all_classes = ["商一甲", "商一乙", "商一丙"]

def get_school_week(date_obj):
    start_date = datetime.strptime(SYSTEM_CONFIG["semester_start"], "%Y-%m-%d").date()
    if isinstance(date_obj, datetime): date_obj = date_obj.date()
    delta = date_obj - start_date
    week_num = (delta.days // 7) + 1
    return max(0, week_num)

# 晨掃名單 (只抓學號+地點)
def get_daily_duty(target_date):
    duty_list = []
    status = "init"
    if os.path.exists(DUTY_FILE):
        try:
            df = pd.read_csv(DUTY_FILE, dtype=str)
            # 自動判斷欄位
            date_col = df.columns[0]
            id_col = df.columns[1]
            # 嘗試找地點欄位 (假設第4欄，或含有"地點"字樣)
            loc_col_name = next((c for c in df.columns if "地點" in c or "區域" in c), None)
            
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce').dt.date
            target = target_date if isinstance(target_date, date) else target_date.date()
            today_df = df[df[date_col] == target]
            
            for _, row in today_df.iterrows():
                loc_val = str(row[loc_col_name]).strip() if loc_col_name else "未指定"
                duty_list.append({
                    "學號": str(row[id_col]).strip(),
                    "掃地區域": loc_val,
                    "已完成打掃": False
                })
            status = "success"
        except: status = "error"
    else: status = "no_file"
    return duty_list, status

# 糾察隊名單 (只抓學號)
@st.cache_data
def load_inspector_csv():
    inspectors = []
    if not os.path.exists(INSPECTOR_DUTY_FILE):
        return [{"label": "衛生組長", "allowed_roles": ["內掃檢查","外掃檢查","垃圾/回收檢查","晨間打掃"], "assigned_classes": [], "id_prefix": "9"}], {}
    
    try:
        df = pd.read_csv(INSPECTOR_DUTY_FILE, dtype=str)
        # 找學號欄位
        id_col = next((c for c in df.columns if "學號" in c or "編號" in c), None)
        role_col = next((c for c in df.columns if "負責" in c or "項目" in c), None)
        
        if id_col:
            for _, row in df.iterrows():
                s_id = str(row[id_col]).strip()
                s_role = str(row[role_col]).strip() if role_col else ""
                
                # 簡單權限判斷
                roles = ["內掃檢查"]
                if "組長" in s_role: roles = ["內掃檢查", "外掃檢查", "垃圾/回收檢查", "晨間打掃"]
                elif "外掃" in s_role: roles.append("外掃檢查")
                elif "垃圾" in s_role: roles.append("垃圾/回收檢查")
                elif "晨" in s_role: roles.append("晨間打掃")
                
                inspectors.append({
                    "label": f"學號: {s_id}", # 匿名化顯示
                    "allowed_roles": roles,
                    "assigned_classes": [],
                    "id_prefix": s_id[0] if s_id else "X"
                })
    except: pass
    
    if not inspectors: inspectors.append({"label": "測試人員", "allowed_roles": ["內掃檢查"], "id_prefix": "測"})
    return inspectors, {}

INSPECTOR_LIST, _ = load_inspector_csv()

def load_holidays():
    if os.path.exists(HOLIDAY_FILE): return pd.read_csv(HOLIDAY_FILE)
    return pd.DataFrame(columns=["日期", "原因"])

def load_appeals():
    # 申訴也存在 Google Sheets 會比較好，但這裡先維持 CSV 讓您能跑起來
    if os.path.exists(APPEALS_FILE):
        df = pd.read_csv(APPEALS_FILE)
        if "佐證照片" not in df.columns: df["佐證照片"] = ""
        return df
    return pd.DataFrame(columns=["日期", "班級", "原始紀錄ID", "申訴理由", "申請時間", "狀態", "佐證照片"])

def save_appeal(entry):
    # 這裡維持存 CSV (雲端會消失)，建議未來也改成 Google Sheet
    df = load_appeals()
    df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
    df.to_csv(APPEALS_FILE, index=False, encoding="utf-8-sig")

def update_appeal_status(index, status):
    df = load_appeals()
    df.at[index, "狀態"] = status
    df.to_csv(APPEALS_FILE, index=False, encoding="utf-8-sig")

def is_appeal_expired(record_date_str):
    try:
        record_date = pd.to_datetime(record_date_str).date()
        return len(pd.bdate_range(start=record_date, end=date.today())) > 4
    except: return True

def send_email(to_email, subject, body):
    sender = SYSTEM_CONFIG.get("smtp_email")
    pwd = SYSTEM_CONFIG.get("smtp_password")
    if not sender or not pwd: return False, "未設定郵件帳號"
    try:
        msg = MIMEMultipart()
        msg['From'] = sender; msg['To'] = to_email; msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls(); server.login(sender, pwd)
        server.sendmail(sender, to_email, msg.as_string()); server.quit()
        return True, "發送成功"
    except Exception as e: return False, str(e)

# ==========================================
# 介面開始
# ==========================================
st.sidebar.title("🏫 功能選單")
app_mode = st.sidebar.radio("請選擇模式", ["我是糾察隊 (評分)", "我是班上衛生股長", "衛生組後台"])

if app_mode == "我是糾察隊 (評分)":
    st.title("📝 衛生糾察評分系統 (雲端版)")
    if "team_logged_in" not in st.session_state: st.session_state["team_logged_in"] = False
    
    if not st.session_state["team_logged_in"]:
        with st.expander("🔐 身份驗證", expanded=True):
            input_code = st.text_input("請輸入隊伍通行碼", type="password")
            if st.button("登入"):
                if input_code == SYSTEM_CONFIG["team_password"]:
                    st.session_state["team_logged_in"] = True
                    st.rerun()
                else: st.error("通行碼錯誤")
    
    if st.session_state["team_logged_in"]:
        # 1. 選擇人員 (v40 邏輯)
        st.markdown("### 👤 請選擇您的學號/身份")
        prefixes = sorted(list(set([p["id_prefix"] for p in INSPECTOR_LIST])))
        prefix_labels = [f"{p}開頭" for p in prefixes]
        if prefixes:
            selected_prefix_label = st.radio("步驟 1：選擇開頭", prefix_labels, horizontal=True)
            selected_prefix = selected_prefix_label[0]
            filtered = [p for p in INSPECTOR_LIST if p["id_prefix"] == selected_prefix]
            inspector_name = st.radio("步驟 2：點選身份", [p["label"] for p in filtered])
            curr_inspector = next((p for p in filtered if p["label"] == inspector_name), None)
            allowed_roles = curr_inspector.get("allowed_roles", ["內掃檢查"])
        else:
            allowed_roles = ["內掃檢查"]; inspector_name = "測試人員"

        st.markdown("---")
        
        # 2. 選擇項目
        col1, col2 = st.columns(2)
        input_date = col1.date_input("檢查日期", datetime.now())
        if len(allowed_roles) > 1: role = col2.radio("檢查項目", allowed_roles, horizontal=True)
        else: col2.info(f"負責項目: {allowed_roles[0]}"); role = allowed_roles[0]
        
        col2.caption(f"第 {get_school_week(input_date)} 週")
        if str(input_date) in load_holidays()["日期"].values: st.warning("⚠️ 假日")

        # 讀取雲端資料 (狀態顯示用)
        df = load_data()
        today_recs = df[df["日期"] == str(input_date)] if not df.empty else pd.DataFrame()

        # --- 介面分流 ---
        if role == "晨間打掃":
            duty_list, status = get_daily_duty(input_date)
            if status == "success":
                st.info("請勾選 **已完成** 的同學")
                if not today_recs[today_recs["評分項目"]=="晨間打掃"].empty: st.warning("⚠️ 今日已評過")
                
                with st.form("morning_form", clear_on_submit=True):
                    edited = st.data_editor(pd.DataFrame(duty_list), column_config={"已完成打掃": st.column_config.CheckboxColumn(default=False)}, hide_index=True, use_container_width=True)
                    score = st.number_input("未到扣分", value=1)
                    if st.form_submit_button("送出"):
                        absent = edited[edited["已完成打掃"]==False]
                        base = {"日期": input_date, "週次": get_school_week(input_date), "檢查人員": inspector_name, "登錄時間": str(datetime.now())}
                        for _, r in absent.iterrows():
                            save_entry({**base, "班級": ROSTER_DICT.get(r["學號"], "未知"), "評分項目": role, "晨間打掃原始分": score, "備註": f"未掃:{r['掃地區域']}", "晨掃未到者": r["學號"]})
                        st.success("已登記"); st.rerun()
            else: st.warning("無今日輪值資料")

        elif role == "垃圾/回收檢查":
            st.info("勾選違規")
            with st.form("trash_form", clear_on_submit=True):
                trash_data = [{"班級": c, "無簽名": False, "無分類": False} for c in all_classes]
                edited = st.data_editor(pd.DataFrame(trash_data), hide_index=True, height=400)
                if st.form_submit_button("送出"):
                    count = 0
                    base = {"日期": input_date, "週次": get_school_week(input_date), "檢查人員": inspector_name, "登錄時間": str(datetime.now())}
                    for _, r in edited.iterrows():
                        v = []
                        if r["無簽名"]: v.append("無簽名")
                        if r["無分類"]: v.append("無分類")
                        if v:
                            save_entry({**base, "班級": r["班級"], "評分項目": role, "垃圾原始分": len(v), "備註": ",".join(v), "違規細項": "垃圾"})
                            count += 1
                    if count: st.success(f"已登記 {count} 班"); st.rerun()
                    else: st.info("無違規")

        else: # 內掃/外掃
            s_class = st.selectbox("選擇班級", all_classes)
            if not today_recs.empty:
                if not today_recs[(today_recs["班級"]==s_class) & (today_recs["評分項目"]==role)].empty:
                    st.success("✅ 今日已評分")
            
            with st.form("main_form", clear_on_submit=True):
                status = st.radio("結果", ["❌ 有違規", "✨ 很乾淨"], horizontal=True)
                score = st.number_input("扣分", min_value=0) if status == "❌ 有違規" else 0
                note = st.text_input("說明") if status == "❌ 有違規" else "【優良】"
                phones = st.number_input("手機違規", min_value=0)
                # 雲端版照片暫時只能存檔名，無法永久保存
                img = st.file_uploader("照片", accept_multiple_files=True)
                
                if st.form_submit_button("送出"):
                    entry = {
                        "日期": input_date, "週次": get_school_week(input_date), "班級": s_class,
                        "評分項目": role, "檢查人員": inspector_name,
                        "內掃原始分": score if role=="內掃檢查" else 0,
                        "外掃原始分": score if role=="外掃檢查" else 0,
                        "手機人數": phones, "備註": note,
                        "登錄時間": str(datetime.now())
                    }
                    save_entry(entry)
                    st.toast(f"已儲存 {s_class}")
                    st.rerun()

elif app_mode == "我是班上衛生股長":
    st.title("🔎 查詢與申訴")
    df = load_data()
    if not df.empty:
        my_class = st.selectbox("我的班級", all_classes)
        my_df = df[df["班級"] == my_class].sort_values("登錄時間", ascending=False)
        if not my_df.empty:
            for i, row in my_df.iterrows():
                total = row["內掃原始分"] + row["外掃原始分"] + row["垃圾原始分"] + row["晨間打掃原始分"] + row["手機人數"]
                with st.expander(f"{row['日期']} {row['評分項目']} (扣 {total} 分)"):
                    st.write(f"說明: {row['備註']}")
                    if str(row["照片路徑"]) and str(row["照片路徑"]) != "nan": st.write("(有照片)")
                    # 申訴功能 (簡化)
                    if st.button("我要申訴", key=f"btn_{i}"):
                        st.info("請截圖向衛生組說明 (雲端版暫不支援線上申訴單)")
        else: st.info("無紀錄")
    else: st.warning("雲端無資料")

elif app_mode == "衛生組後台":
    st.title("📊 管理後台")
    if st.text_input("管理密碼", type="password") == SYSTEM_CONFIG["admin_password"]:
        df = load_data()
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 成績", "📢 申訴", "📧 通知", "🛠️ 資料", "⚙️ 設定"])
        
        with tab1:
            if not df.empty:
                st.dataframe(df)
                # Excel 下載
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                st.download_button("📥 下載 Excel", buffer.getvalue(), "report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else: st.info("無資料")

        with tab2:
            st.info("申訴資料庫 (雲端版需連接 Sheets，目前僅顯示 CSV 暫存)")
            adf = load_appeals()
            st.dataframe(adf)

        with tab3:
            st.write("寄信測試")
            ed = load_teacher_emails()
            if st.button("掃描今日並寄信"):
                st.info("需設定 Secrets 才能寄出")

        with tab4:
            st.write("### 資料管理")
            # 這是您要的「下載雲端備份」按鈕
            if not df.empty:
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 下載雲端備份 (CSV)", csv, f"backup_{date.today()}.csv", "text/csv")
            
            if st.button("🧹 一鍵清洗歷史姓名"):
                msg = anonymize_history()
                st.success(msg); st.rerun()

            st.write("---")
            st.write("刪除資料")
            if not df.empty:
                del_idx = st.multiselect("選擇刪除", df.index)
                if st.button("確認刪除"):
                    delete_entry(del_idx)
                    st.success("已刪除"); st.rerun()

        with tab5:
            st.write("系統設定 (雲端重啟後會還原，建議改 secrets)")
            c1, c2 = st.columns(2)
            n_admin = c1.text_input("新管理密碼", type="password")
            n_team = c2.text_input("新糾察密碼", type="password")
            if st.button("暫時更新密碼"):
                SYSTEM_CONFIG.update({"admin_password": n_admin, "team_password": n_team})
                st.success("已更新 (重啟後失效)")
                
            st.write("更新名單 (請上傳到 GitHub 永久生效)")
            st.file_uploader("全校名單.csv")
            st.file_uploader("晨掃輪值.csv")
    else: st.error("密碼錯誤")
