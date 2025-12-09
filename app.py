import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta
import re

# --- 設定網頁標題 ---
st.set_page_config(page_title="衛生糾察評分系統 (雲端全功能版)", layout="wide")

# ==========================================
# 0. 基礎設定
# ==========================================
GSHEET_NAME = "衛生糾察評分資料庫"
IMG_DIR = "evidence_photos"
if not os.path.exists(IMG_DIR): os.makedirs(IMG_DIR)

# 設定檔與名單
CONFIG_FILE = "config.json"
ROSTER_FILE = "全校名單.csv" 
DUTY_FILE = "晨掃輪值.csv" 
INSPECTOR_DUTY_FILE = "糾察隊名單.csv" 
TEACHER_MAIL_FILE = "導師名單.csv"

# ==========================================
# 1. Google Sheets 連線與資料庫
# ==========================================
def get_gsheet_client():
    if "gcp_service_account" not in st.secrets:
        st.error("⚠️ 未設定 Google 金鑰 (Secrets)")
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

        # 統一資料寬度 (防呆)
        n_cols = len(expected_columns)
        cleaned_rows = []
        for row in rows:
            if len(row) > n_cols: cleaned_rows.append(row[:n_cols])
            elif len(row) < n_cols: cleaned_rows.append(row + [""] * (n_cols - len(row)))
            else: cleaned_rows.append(row)
        
        df = pd.DataFrame(cleaned_rows, columns=expected_columns)

        # 強制轉數字
        numeric_cols = ["內掃原始分", "外掃原始分", "垃圾原始分", "垃圾內掃原始分", "垃圾外掃原始分", "晨間打掃原始分", "手機人數"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

        if "修正" in df.columns:
            df["修正"] = df["修正"].astype(str).apply(lambda x: True if x.upper() == "TRUE" else False)
            
        return df

    except gspread.exceptions.SpreadsheetNotFound:
        # 自動建立
        try:
            sh = client.create(GSHEET_NAME)
            try: sh.share(st.secrets["gcp_service_account"]["client_email"], perm_type='user', role='owner')
            except: pass
            sh.sheet1.append_row(expected_columns)
            return pd.DataFrame(columns=expected_columns)
        except: return pd.DataFrame(columns=expected_columns)
    except: return pd.DataFrame(columns=expected_columns)

def save_entry(new_entry):
    client = get_gsheet_client()
    if not client: return
    try:
        sheet = client.open(GSHEET_NAME).sheet1
        # 轉字串寫入
        row_values = [str(new_entry.get(c, "")) for c in [
            "日期", "週次", "班級", "評分項目", "檢查人員",
            "內掃原始分", "外掃原始分", "垃圾原始分", "垃圾內掃原始分", "垃圾外掃原始分", "晨間打掃原始分", "手機人數", 
            "備註", "違規細項", "照片路徑", "登錄時間", "修正", "晨掃未到者"
        ]]
        
        if not sheet.get_all_values():
             sheet.append_row([
                "日期", "週次", "班級", "評分項目", "檢查人員",
                "內掃原始分", "外掃原始分", "垃圾原始分", "垃圾內掃原始分", "垃圾外掃原始分", "晨間打掃原始分", "手機人數", 
                "備註", "違規細項", "照片路徑", "登錄時間", "修正", "晨掃未到者"
            ])
        sheet.append_row(row_values)
    except Exception as e: st.error(f"寫入失敗: {e}")

# 雲端版刪除功能 (重新寫入整張表)
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
    except Exception as e: st.error(f"刪除失敗: {e}")

# ==========================================
# 2. 輔助函式
# ==========================================
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
    start_date = date(2025, 8, 25) # 請自行修改開學日
    if isinstance(date_obj, datetime): date_obj = date_obj.date()
    delta = date_obj - start_date
    week_num = (delta.days // 7) + 1
    return max(0, week_num)

@st.cache_data
def load_teacher_emails():
    email_dict = {}
    if os.path.exists(TEACHER_MAIL_FILE):
        try:
            df = pd.read_csv(TEACHER_MAIL_FILE, dtype=str)
            if len(df.columns) >= 2:
                # 簡單假設：第一欄班級，第二欄Email，第三欄姓名
                for _, row in df.iterrows():
                    cls = str(row[0]).strip()
                    mail = str(row[1]).strip()
                    name = str(row[2]).strip() if len(row) > 2 else "老師"
                    if "@" in mail: email_dict[cls] = {"email": mail, "name": name}
        except: pass
    return email_dict

# 晨掃名單 (只抓學號)
def get_daily_duty(target_date):
    duty_list = []
    status = "init"
    if os.path.exists(DUTY_FILE):
        try:
            df = pd.read_csv(DUTY_FILE, dtype=str)
            # 假設欄位順序：日期, 學號, 姓名, 地點
            # 這裡做一個簡單的欄位對應
            date_col = df.columns[0]
            id_col = df.columns[1]
            loc_col = df.columns[3] if len(df.columns) > 3 else None
            
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce').dt.date
            target = target_date if isinstance(target_date, date) else target_date.date()
            today_df = df[df[date_col] == target]
            
            for _, row in today_df.iterrows():
                duty_list.append({
                    "學號": str(row[id_col]).strip(),
                    "掃地區域": str(row[loc_col]).strip() if loc_col else "未指定",
                    "已完成打掃": False
                })
            status = "success"
        except: status = "error"
    else: status = "no_file"
    return duty_list, status

def send_email(to_email, subject, body):
    # 這裡需要您在 Secrets 裡設定 smtp_email 和 smtp_password
    # 或者透過 Admin 介面暫時設定 (但雲端重啟會消失)
    # 建議直接寫在 Secrets 裡
    if "system_config" in st.secrets:
        sender = st.secrets["system_config"].get("smtp_email")
        pwd = st.secrets["system_config"].get("smtp_password")
    else:
        return False, "未設定 Secrets 郵件帳號"
        
    if not sender or not pwd: return False, "未設定郵件帳號"
    
    try:
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender, pwd)
        server.sendmail(sender, to_email, msg.as_string())
        server.quit()
        return True, "發送成功"
    except Exception as e: return False, str(e)

# ==========================================
# 介面開始
# ==========================================
st.sidebar.title("🏫 功能選單")

# --- 側邊欄：備份按鈕 (隨時可按) ---
st.sidebar.markdown("---")
if st.sidebar.button("📥 下載雲端備份 (CSV)"):
    df = load_data()
    if not df.empty:
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.sidebar.download_button(
            label="點此儲存檔案",
            data=csv,
            file_name=f"衛生評分備份_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.sidebar.warning("雲端目前無資料")
st.sidebar.markdown("---")

app_mode = st.sidebar.radio("請選擇模式", ["我是糾察隊 (評分)", "我是班上衛生股長", "衛生組後台"])

# ------------------------------------------
# 模式一：糾察隊 (雲端版)
# ------------------------------------------
if app_mode == "我是糾察隊 (評分)":
    st.title("📝 衛生糾察評分 (雲端版)")
    
    if "team_logged_in" not in st.session_state: st.session_state["team_logged_in"] = False
    
    if not st.session_state["team_logged_in"]:
        pwd = st.text_input("請輸入通行碼", type="password")
        if st.button("登入"):
            # 簡單密碼驗證，雲端建議用 secrets
            target_pwd = st.secrets["system_config"]["team_password"] if "system_config" in st.secrets else "0000"
            if pwd == target_pwd:
                st.session_state["team_logged_in"] = True
                st.rerun()
            else:
                st.error("密碼錯誤 (預設 0000)")
    
    if st.session_state["team_logged_in"]:
        col1, col2 = st.columns(2)
        input_date = col1.date_input("日期", datetime.now())
        week_num = get_school_week(input_date)
        col2.info(f"📅 第 {week_num} 週")
        
        role = st.radio("評分項目", ["內掃檢查", "外掃檢查", "垃圾/回收檢查", "晨間打掃"], horizontal=True)
        
        # 讀取今日狀態
        df = load_data()
        today_df = df[df["日期"] == str(input_date)] if not df.empty else pd.DataFrame()
        
        if role == "晨間打掃":
            duty_list, status = get_daily_duty(input_date)
            if status == "success":
                st.info("請勾選 **已完成** 的同學")
                with st.form("morning_form", clear_on_submit=True):
                    edited = st.data_editor(pd.DataFrame(duty_list), hide_index=True, use_container_width=True)
                    score = st.number_input("未到扣分", min_value=0, value=1)
                    inspector = st.text_input("檢查員學號")
                    
                    if st.form_submit_button("送出"):
                        absent = edited[edited["已完成打掃"]==False]
                        if absent.empty: st.success("全勤！")
                        else:
                            for _, r in absent.iterrows():
                                entry = {
                                    "日期": input_date, "週次": week_num, "評分項目": role,
                                    "班級": ROSTER_DICT.get(str(r["學號"]), "未知"),
                                    "檢查人員": inspector, "晨間打掃原始分": score,
                                    "備註": f"未掃:{r['掃地區域']}", "晨掃未到者": r["學號"],
                                    "登錄時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                }
                                save_entry(entry)
                            st.success("已登記未到同學")
            else: st.warning("找不到今日輪值表 (請確認 CSV 是否已上傳)")

        elif role == "垃圾/回收檢查":
            st.info("勾選違規項目")
            with st.form("trash_form", clear_on_submit=True):
                # 產生全校列表
                trash_data = [{"班級": c, "無簽名": False, "無分類": False} for c in all_classes]
                edited = st.data_editor(pd.DataFrame(trash_data), hide_index=True)
                inspector = st.text_input("檢查員學號")
                
                if st.form_submit_button("送出"):
                    count = 0
                    for _, r in edited.iterrows():
                        violations = []
                        if r["無簽名"]: violations.append("無簽名")
                        if r["無分類"]: violations.append("無分類")
                        if violations:
                            entry = {
                                "日期": input_date, "週次": week_num, "班級": r["班級"],
                                "評分項目": role, "檢查人員": inspector,
                                "垃圾原始分": len(violations), 
                                "備註": ",".join(violations), "違規細項": "一般垃圾",
                                "登錄時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                            save_entry(entry)
                            count += 1
                    if count: st.success(f"已登記 {count} 班違規")
                    else: st.info("無違規")

        else: # 內掃/外掃
            selected_class = st.selectbox("選擇班級", all_classes)
            
            # 顯示是否已評
            if not today_df.empty:
                check = today_df[(today_df["班級"]==selected_class) & (today_df["評分項目"]==role)]
                if not check.empty: st.success("✅ 今日已評分")
                else: st.info("尚未評分")

            with st.form("main_form", clear_on_submit=True):
                st.write(f"正在評分：{selected_class}")
                status = st.radio("結果", ["❌ 有違規", "✨ 很乾淨"], horizontal=True)
                
                score = 0
                note = ""
                phones = 0
                
                if status == "❌ 有違規":
                    score = st.number_input("扣分", min_value=0)
                    note = st.text_input("說明")
                    phones = st.number_input("手機違規人數", min_value=0)
                else:
                    note = "【優良】"
                
                inspector = st.text_input("檢查員學號")
                img = st.file_uploader("照片 (雲端暫存)", accept_multiple_files=True)
                
                if st.form_submit_button("送出"):
                    entry = {
                        "日期": input_date, "週次": week_num, "班級": selected_class,
                        "評分項目": role, "檢查人員": inspector,
                        "內掃原始分": score if role=="內掃檢查" else 0,
                        "外掃原始分": score if role=="外掃檢查" else 0,
                        "手機人數": phones, "備註": note,
                        "登錄時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    save_entry(entry)
                    st.toast(f"已儲存 {selected_class}")
                    st.rerun()

# ------------------------------------------
# 模式二：衛生股長 (查詢)
# ------------------------------------------
elif app_mode == "我是班上衛生股長":
    st.title("🔎 查詢與申訴")
    df = load_data()
    if not df.empty:
        my_class = st.selectbox("選擇班級", all_classes)
        my_df = df[df["班級"] == my_class].sort_values("登錄時間", ascending=False)
        
        if not my_df.empty:
            for _, row in my_df.iterrows():
                # 計算總扣分
                total = row["內掃原始分"] + row["外掃原始分"] + row["垃圾原始分"] + row["晨間打掃原始分"] + row["手機人數"]
                with st.expander(f"{row['日期']} - {row['評分項目']} (扣 {total} 分)"):
                    st.write(f"說明: {row['備註']}")
                    if total > 0:
                        st.button("我要申訴", key=f"btn_{row.name}", help="請截圖向衛生組說明")
        else:
            st.info("目前無紀錄")
    else:
        st.warning("雲端無資料")

# ------------------------------------------
# 模式三：衛生組後台
# ------------------------------------------
elif app_mode == "衛生組後台":
    st.title("📊 管理後台")
    pwd = st.text_input("管理密碼", type="password")
    target_admin = st.secrets["system_config"]["admin_password"] if "system_config" in st.secrets else "1234"
    
    if pwd == target_admin:
        tab1, tab2, tab3 = st.tabs(["📊 報表與刪除", "📧 寄信通知", "⚙️ 設定"])
        
        df = load_data()
        
        with tab1:
            if not df.empty:
                st.dataframe(df)
                
                st.subheader("🗑️ 刪除資料")
                # 製作選單
                options = {i: f"{r['日期']} {r['班級']} {r['評分項目']} ({r['備註']})" for i, r in df.iterrows()}
                to_del = st.multiselect("選擇要刪除的項目", options.keys(), format_func=lambda x: options[x])
                
                if st.button("確認刪除"):
                    delete_entry(to_del)
                    st.success("刪除成功")
                    st.rerun()
            else:
                st.info("無資料")

        with tab2:
            st.write("寄送違規通知 (需設定 Secrets)")
            ed = load_teacher_emails()
            if st.button("掃描今日違規並寄信"):
                today_str = str(date.today())
                today_bad = df[(df["日期"] == today_str)]
                # (這裡簡化寄信邏輯，需搭配 Secrets)
                st.info(f"今日共有 {len(today_bad)} 筆紀錄")

        with tab3:
            st.write("⚠️ 注意：雲端版請將名單 CSV 直接上傳至 GitHub，此處上傳僅為暫時性 (重啟消失)。")
            st.file_uploader("更新全校名單.csv")
            st.file_uploader("更新晨掃輪值.csv")
            st.file_uploader("更新糾察隊名單.csv")
            
    else:
        if pwd: st.error("密碼錯誤 (預設 1234)")
