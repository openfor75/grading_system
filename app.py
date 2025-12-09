import streamlit as st
import pandas as pd
import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re

# --- 設定網頁標題 ---
st.set_page_config(page_title="衛生糾察評分系統 (雲端下載版)", layout="wide")

# ==========================================
# 0. 基礎設定
# ==========================================
GSHEET_NAME = "衛生糾察評分資料庫"
# 注意：雲端上的 IMG_DIR 只是暫存，重啟後照片會消失，但資料庫會在
IMG_DIR = "evidence_photos"
if not os.path.exists(IMG_DIR): os.makedirs(IMG_DIR)

# 名單設定 (請將您的 csv 檔一同上傳到 GitHub)
ROSTER_FILE = "全校名單.csv" 
DUTY_FILE = "晨掃輪值.csv" 
INSPECTOR_DUTY_FILE = "糾察隊名單.csv" 
TEACHER_MAIL_FILE = "導師名單.csv"

# ==========================================
# 1. Google Sheets 連線 (超強防呆版)
# ==========================================
def get_gsheet_client():
    if "gcp_service_account" not in st.secrets:
        st.error("⚠️ 請在 Streamlit Secrets 設定 Google 金鑰")
        return None
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"⚠️ 連線失敗: {e}")
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
        
        # 這裡使用 v40.0 的邏輯：不管標題爛不爛，我們自己定義
        rows = data[1:]
        if not rows: return pd.DataFrame(columns=expected_columns)

        # 統一寬度
        n_cols = len(expected_columns)
        cleaned_rows = []
        for row in rows:
            if len(row) > n_cols: cleaned_rows.append(row[:n_cols])
            elif len(row) < n_cols: cleaned_rows.append(row + [""] * (n_cols - len(row)))
            else: cleaned_rows.append(row)
        
        df = pd.DataFrame(cleaned_rows, columns=expected_columns)

        # 強制轉數字 (這就是之前修復報錯的關鍵)
        numeric_cols = ["內掃原始分", "外掃原始分", "垃圾原始分", "垃圾內掃原始分", "垃圾外掃原始分", "晨間打掃原始分", "手機人數"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

        if "修正" in df.columns:
            df["修正"] = df["修正"].astype(str).apply(lambda x: True if x.upper() == "TRUE" else False)
            
        return df

    except gspread.exceptions.SpreadsheetNotFound:
        # 自動建立試算表
        try:
            sh = client.create(GSHEET_NAME)
            sh.share(st.secrets["gcp_service_account"]["client_email"], perm_type='user', role='owner')
            sh.sheet1.append_row(expected_columns)
            st.success(f"✅ 已自動建立雲端資料庫：{GSHEET_NAME}")
            return pd.DataFrame(columns=expected_columns)
        except Exception as e:
            st.error(f"❌ 無法建立試算表，請手動建立: {e}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"⚠️ 讀取錯誤: {e}")
        return pd.DataFrame()

def save_entry(new_entry):
    client = get_gsheet_client()
    if not client: return

    try:
        sheet = client.open(GSHEET_NAME).sheet1
        # 全部轉字串寫入，最安全
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
        
        # 如果是空表，先補標題
        if not sheet.get_all_values():
             sheet.append_row([
                "日期", "週次", "班級", "評分項目", "檢查人員",
                "內掃原始分", "外掃原始分", "垃圾原始分", "垃圾內掃原始分", "垃圾外掃原始分", "晨間打掃原始分", "手機人數", 
                "備註", "違規細項", "照片路徑", "登錄時間", "修正", "晨掃未到者"
            ])
        
        sheet.append_row(row_values)
        
    except Exception as e:
        st.error(f"⚠️ 寫入雲端失敗: {e}")

# ==========================================
# 2. 其他輔助函式
# ==========================================
# (這裡保留您之前的名單讀取邏輯，不變)
@st.cache_data
def load_roster_dict():
    roster_dict = {}
    if os.path.exists(ROSTER_FILE):
        try:
            df = pd.read_csv(ROSTER_FILE, dtype=str) # 簡化讀取，假設 utf-8
            # 若亂碼可嘗試 encoding='big5'
            if len(df.columns) >= 2:
                for _, row in df.iterrows():
                    roster_dict[str(row[0]).strip()] = str(row[1]).strip()
        except: pass
    return roster_dict

ROSTER_DICT = load_roster_dict()

# 簡化的名單載入，避免編碼問題
@st.cache_data
def get_simple_list(filename):
    items = []
    if os.path.exists(filename):
        try:
            df = pd.read_csv(filename, dtype=str)
            if not df.empty:
                # 假設第一欄是我們要的 (例如班級或學號)
                items = df.iloc[:, 0].dropna().astype(str).tolist()
        except: pass
    return items

all_classes = get_simple_list(ROSTER_FILE) # 這裡假設名單第一欄是班級，若不是請自行調整
if not all_classes: # 預設班級
    all_classes = ["商一甲", "商一乙", "商一丙"]

def get_school_week(date_obj):
    # 這裡請填入您的開學日
    start_date = date(2025, 8, 25)
    if isinstance(date_obj, datetime): date_obj = date_obj.date()
    delta = date_obj - start_date
    week_num = (delta.days // 7) + 1
    return max(0, week_num)

# ==========================================
# 介面開始
# ==========================================
st.title("☁️ 衛生糾察評分系統 (雲端版)")

# --- 側邊欄：下載備份 (這就是您要的功能！) ---
st.sidebar.header("📦 資料保全")
st.sidebar.info("資料儲存於 Google 試算表。您隨時可以按下方按鈕將資料備份回自己的電腦。")

# 讀取目前最新的資料
df = load_data()

if not df.empty:
    # 轉換成 CSV 字串
    csv = df.to_csv(index=False).encode('utf-8-sig')
    
    st.sidebar.download_button(
        label="📥 立即下載備份 (CSV)",
        data=csv,
        file_name=f"衛生評分備份_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        key='download-csv'
    )
else:
    st.sidebar.warning("目前雲端無資料可下載")

# --- 主畫面：評分區 ---
st.header("📝 新增評分")

col1, col2 = st.columns(2)
input_date = col1.date_input("日期", datetime.now())
week_num = get_school_week(input_date)
col2.info(f"📅 第 {week_num} 週")

# 選擇班級
selected_class = st.selectbox("選擇班級", all_classes)

# 評分項目
role = st.radio("評分項目", ["內掃檢查", "外掃檢查", "垃圾檢查", "晨間打掃"], horizontal=True)

with st.form("score_form", clear_on_submit=True):
    score = 0
    note = ""
    
    if role == "晨間打掃":
        st.write("請輸入未到學號 (用空白分隔)")
        absent_str = st.text_input("學號", placeholder="例如: 91001 91002")
        score = st.number_input("未到扣分 (總分)", min_value=0, step=1)
        note = "晨掃未到"
    else:
        score = st.number_input("扣分", min_value=0, step=1)
        note = st.text_input("違規說明")
    
    inspector = st.text_input("檢查人員 (學號)", placeholder="請輸入學號")
    
    submitted = st.form_submit_button("送出評分")
    
    if submitted:
        entry = {
            "日期": input_date,
            "週次": week_num,
            "班級": selected_class,
            "評分項目": role,
            "檢查人員": inspector,
            "內掃原始分": score if role=="內掃檢查" else 0,
            "外掃原始分": score if role=="外掃檢查" else 0,
            "垃圾原始分": score if role=="垃圾檢查" else 0,
            "晨間打掃原始分": score if role=="晨間打掃" else 0,
            "備註": note,
            "晨掃未到者": absent_str if role=="晨間打掃" else "",
            "登錄時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        save_entry(entry)
        st.success(f"✅ 已上傳雲端：{selected_class} 扣 {score} 分")
        st.rerun()

# --- 下方顯示今日紀錄 ---
st.divider()
st.subheader("📋 今日已評分紀錄 (雲端同步)")
if not df.empty:
    # 篩選今日
    today_df = df[df["日期"] == str(input_date)]
    if not today_df.empty:
        st.dataframe(today_df)
    else:

        st.info("今日尚無紀錄")
