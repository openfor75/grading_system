import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, date, timedelta
import shutil
import io

# --- 設定網頁標題 ---
st.set_page_config(page_title="衛生糾察評分系統", layout="wide")

# ==========================================
# 0. 基礎設定與檔案管理
# ==========================================

FILE_PATH = "score_data.csv"
IMG_DIR = "evidence_photos"
CONFIG_FILE = "config.json"
HOLIDAY_FILE = "holidays.csv"
ROSTER_FILE = "全校名單.csv" 
DUTY_FILE = "晨掃輪值.csv" 
APPEALS_FILE = "appeals.csv"
INSPECTOR_DUTY_FILE = "糾察隊名單.csv" 

if not os.path.exists(IMG_DIR): os.makedirs(IMG_DIR)

# ==========================================
# 1. 設定檔與密碼管理
# ==========================================

def load_config():
    default_config = {
        "semester_start": "2025-08-25",
        "admin_password": "1234",
        "team_password": "0000"
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding='utf-8') as f:
            saved = json.load(f)
            return {**default_config, **saved}
    return default_config

def save_config(new_config):
    with open(CONFIG_FILE, "w", encoding='utf-8') as f:
        json.dump(new_config, f, ensure_ascii=False)

SYSTEM_CONFIG = load_config()

# ==========================================
# 2. 名單與資料處理
# ==========================================

# --- A. 晨間打掃名單 (預設) ---
MORNING_TEAM_LIST = [] 
MORNING_OPTIONS = []

# --- B. 全校名單 ---
@st.cache_data
def load_roster_dict(csv_path=ROSTER_FILE):
    roster_dict = {}
    debug_info = {"status": "init", "cols": [], "error": ""}
    
    if os.path.exists(csv_path):
        encodings_to_try = ['utf-8', 'big5', 'cp950', 'utf-8-sig']
        df = None
        for enc in encodings_to_try:
            try:
                df = pd.read_csv(csv_path, encoding=enc, dtype=str)
                df.columns = df.columns.str.strip()
                if any("學號" in c for c in df.columns) and any("班級" in c for c in df.columns):
                    debug_info["status"] = "success"
                    debug_info["cols"] = list(df.columns)
                    break 
            except Exception as e:
                debug_info["error"] = str(e)
                continue
        
        if df is not None:
            id_col = next((c for c in df.columns if "學號" in c), None)
            class_col = next((c for c in df.columns if "班級" in c), None)
            if id_col and class_col:
                for _, row in df.iterrows():
                    s_id = str(row[id_col]).strip()
                    s_class = str(row[class_col]).strip()
                    if s_id and s_class and s_id.lower() != "nan":
                        roster_dict[s_id] = s_class
            else:
                debug_info["status"] = "missing_columns"
                debug_info["cols"] = list(df.columns)
        else:
            debug_info["status"] = "read_failed"
    return roster_dict, debug_info

ROSTER_DICT, ROSTER_DEBUG = load_roster_dict()

# --- C. 晨掃輪值表讀取 ---
def get_daily_duty(target_date, csv_path=DUTY_FILE):
    duty_list = []
    status = "init"
    diagnostic_info = {"all_dates_found": [], "total_rows": 0, "matched_rows": 0}
    
    if os.path.exists(csv_path):
        encodings = ['utf-8', 'big5', 'cp950', 'utf-8-sig']
        df = None
        for enc in encodings:
            try:
                df = pd.read_csv(csv_path, encoding=enc, dtype=str)
                df.columns = df.columns.str.strip()
                break
            except:
                continue
        
        if df is not None:
            diagnostic_info["total_rows"] = len(df)
            date_col = next((c for c in df.columns if "日期" in c or "時間" in c), None)
            id_col = next((c for c in df.columns if "學號" in c), None)
            name_col = next((c for c in df.columns if "姓名" in c), None)
            loc_col = next((c for c in df.columns if "地點" in c or "區域" in c), None)
            
            if date_col and id_col:
                try:
                    df[date_col] = pd.to_datetime(df[date_col], errors='coerce').dt.date
                    found_dates = df[date_col].dropna().unique()
                    diagnostic_info["all_dates_found"] = sorted(found_dates)
                except:
                    pass
                
                target_date_obj = target_date if isinstance(target_date, date) else target_date.date()
                today_df = df[df[date_col] == target_date_obj]
                diagnostic_info["matched_rows"] = len(today_df)
                
                if not today_df.empty:
                    for _, row in today_df.iterrows():
                        s_id = str(row[id_col]).strip()
                        s_name = str(row[name_col]).strip() if name_col else ""
                        s_loc = str(row[loc_col]).strip() if loc_col else "未指定"
                        duty_list.append({
                            "學號": s_id, "姓名": s_name, "掃地區域": s_loc, "已完成打掃": False 
                        })
                    status = "success"
                else:
                    status = "no_data_for_date"
            else:
                status = "missing_columns"
        else:
            status = "read_failed"
    else:
        status = "file_not_found"
        
    return duty_list, status, diagnostic_info

# --- D. 糾察隊名單 ---
@st.cache_data
def load_inspector_csv():
    inspectors = []
    debug_info = {"status": "init", "cols": [], "rows": 0, "name_col": None, "role_col": None}
    
    if not os.path.exists(INSPECTOR_DUTY_FILE):
        return [{"label": "衛生組長 (預設)", "allowed_roles": ["內掃檢查","外掃檢查","垃圾/回收檢查","晨間打掃"], "assigned_classes": []}], debug_info
    
    encodings = ['utf-8', 'big5', 'cp950', 'utf-8-sig', 'gbk']
    df = None
    for enc in encodings:
        try:
            df = pd.read_csv(INSPECTOR_DUTY_FILE, encoding=enc, dtype=str)
            df.columns = df.columns.str.strip()
            if any(k in "".join(df.columns) for k in ["姓名", "Name", "學號"]):
                break
        except:
            continue
            
    if df is not None:
        debug_info["cols"] = list(df.columns)
        debug_info["rows"] = len(df)
        name_col = next((c for c in df.columns if "姓名" in c), None)
        id_col = next((c for c in df.columns if "學號" in c or "編號" in c), None)
        role_col = next((c for c in df.columns if "負責" in c or "項目" in c or "職位" in c), None)
        class_scope_col = next((c for c in df.columns if "班級" in c or "範圍" in c), None)
        
        debug_info["name_col"] = name_col
        debug_info["role_col"] = role_col
        
        if name_col:
            debug_info["status"] = "success"
            for _, row in df.iterrows():
                s_name = str(row[name_col]).strip()
                s_id = str(row[id_col]).strip() if id_col else ""
                s_raw_role = str(row[role_col]).strip() if role_col else "未指定"
                
                s_classes = []
                if class_scope_col:
                    raw_scope = str(row[class_scope_col])
                    if raw_scope and raw_scope.lower() != "nan":
                        s_classes = [c.strip() for c in raw_scope.replace("、", ";").replace(",", ";").split(";") if c.strip()]

                allowed_roles = []
                if "組長" in s_raw_role:
                    allowed_roles = ["內掃檢查", "外掃檢查", "垃圾/回收檢查", "晨間打掃"]
                elif "機動" in s_raw_role:
                    allowed_roles = ["內掃檢查", "外掃檢查", "垃圾/回收檢查"] 
                else:
                    if "外掃" in s_raw_role: allowed_roles.append("外掃檢查")
                    if "垃圾" in s_raw_role or "回收" in s_raw_role: allowed_roles.append("垃圾/回收檢查")
                    if "晨" in s_raw_role: allowed_roles.append("晨間打掃")
                    if "內掃" in s_raw_role: allowed_roles.append("內掃檢查")
                
                if not allowed_roles: 
                    allowed_roles = ["內掃檢查"]
                    s_raw_role += " (未識別)"

                label = f"{s_name}"
                if s_id: label = f"{s_name} ({s_id})"
                
                inspectors.append({
                    "label": label,
                    "allowed_roles": allowed_roles,
                    "assigned_classes": s_classes,
                    "raw_role": s_raw_role
                })
        else:
            debug_info["status"] = "missing_name_col"
    else:
        debug_info["status"] = "read_failed"
    
    if not inspectors:
        inspectors.append({"label": "測試人員", "allowed_roles": ["內掃檢查"], "assigned_classes": []})
        
    return inspectors, debug_info

INSPECTOR_LIST, INSPECTOR_DEBUG = load_inspector_csv()

# --- E. 假日與週次 ---
def load_holidays():
    if os.path.exists(HOLIDAY_FILE):
        return pd.read_csv(HOLIDAY_FILE)
    return pd.DataFrame(columns=["日期", "原因"])

def save_holiday(date_obj, reason):
    df = load_holidays()
    df = df[df["日期"] != str(date_obj)] 
    new_entry = pd.DataFrame([{"日期": str(date_obj), "原因": reason}])
    df = pd.concat([df, new_entry], ignore_index=True)
    df.to_csv(HOLIDAY_FILE, index=False)

def delete_holiday(date_str):
    df = load_holidays()
    df = df[df["日期"] != date_str]
    df.to_csv(HOLIDAY_FILE, index=False)

def get_school_week(date_obj):
    start_date = datetime.strptime(SYSTEM_CONFIG["semester_start"], "%Y-%m-%d").date()
    if isinstance(date_obj, datetime):
        date_obj = date_obj.date()
    delta = date_obj - start_date
    week_num = (delta.days // 7) + 1
    if week_num < 1: week_num = 0 
    return week_num, start_date

# --- F. 班級產生 ---
dept_config = {"商經科": 3, "應英科": 1, "資處科": 1, "家政科": 2, "服裝科": 2}
grades = ["一年級", "二年級", "三年級"]
class_labels = ["甲", "乙", "丙"] 
all_classes = []
for dept, count in dept_config.items():
    for grade in grades:
        g_num = grade[0]
        dept_short = dept[:1]
        if dept == "商經科": dept_short = "商"
        for i in range(count):
            all_classes.append(f"{dept_short}{g_num}{class_labels[i]}")

# --- G. 主資料庫 ---
def load_data():
    if os.path.exists(FILE_PATH):
        df = pd.read_csv(FILE_PATH)
        expected_cols = ["日期", "週次", "班級", "評分項目", "檢查人員", "內掃原始分", "外掃原始分", "垃圾原始分", "垃圾內掃原始分", "垃圾外掃原始分", "晨間打掃原始分", "手機人數", "備註", "違規細項", "照片路徑", "登錄時間", "修正", "晨掃未到者"]
        for col in expected_cols:
            if col == "修正":
                if col not in df.columns: df[col] = False
            elif col == "晨掃未到者" or col == "違規細項":
                if col not in df.columns: df[col] = ""
            elif col not in df.columns: 
                df[col] = 0 if "分" in col or "人數" in col else ""
        return df
    else:
        return pd.DataFrame(columns=[
            "日期", "週次", "班級", "評分項目", "檢查人員",
            "內掃原始分", "外掃原始分", "垃圾原始分", "垃圾內掃原始分", "垃圾外掃原始分", "晨間打掃原始分", "手機人數", 
            "備註", "違規細項", "照片路徑", "登錄時間", "修正", "晨掃未到者"
        ])

def save_entry(new_entry):
    df = load_data()
    new_df = pd.DataFrame([new_entry])
    df = pd.concat([df, new_df], ignore_index=True)
    df.to_csv(FILE_PATH, index=False, encoding="utf-8-sig")

def delete_entry(idx_list):
    df = load_data()
    df = df.drop(idx_list).reset_index(drop=True)
    df.to_csv(FILE_PATH, index=False, encoding="utf-8-sig")

def delete_batch(start_date, end_date):
    df = load_data()
    df["日期"] = pd.to_datetime(df["日期"]).dt.date
    mask = (df["日期"] >= start_date) & (df["日期"] <= end_date)
    df_remaining = df[~mask]
    df_remaining.to_csv(FILE_PATH, index=False, encoding="utf-8-sig")
    return mask.sum()

# --- H. 申訴資料庫 ---
def load_appeals():
    if os.path.exists(APPEALS_FILE):
        df = pd.read_csv(APPEALS_FILE)
        if "佐證照片" not in df.columns: df["佐證照片"] = "" 
        return df
    return pd.DataFrame(columns=["日期", "班級", "原始紀錄ID", "申訴理由", "申請時間", "狀態", "佐證照片"]) 

def save_appeal(entry):
    df = load_appeals()
    new_df = pd.DataFrame([entry])
    df = pd.concat([df, new_df], ignore_index=True)
    df.to_csv(APPEALS_FILE, index=False, encoding="utf-8-sig")

def update_appeal_status(index, status):
    df = load_appeals()
    df.at[index, "狀態"] = status
    df.to_csv(APPEALS_FILE, index=False, encoding="utf-8-sig")

# ==========================================
# 介面開始
# ==========================================
st.sidebar.title("🏫 功能選單")
app_mode = st.sidebar.radio("請選擇模式", ["我是糾察隊 (評分)", "我是班上衛生股長", "衛生組後台"])

# ------------------------------------------
# 模式一：糾察隊評分
# ------------------------------------------
if app_mode == "我是糾察隊 (評分)":
    st.title("📝 衛生糾察評分系統")
    
    with st.sidebar.expander("🔐 身份驗證", expanded=True):
        input_code = st.text_input("請輸入隊伍通行碼", type="password")
        if input_code == SYSTEM_CONFIG["team_password"]:
            st.success("驗證通過")
            access_granted = True
        elif input_code == "":
            st.warning("請輸入通行碼")
            access_granted = False
        else:
            st.error("通行碼錯誤")
            access_granted = False
    
    if access_granted:
        st.markdown("---")
        
        inspector_options = [p["label"] for p in INSPECTOR_LIST]
        inspector_name = st.selectbox("👤 請選擇您的姓名", inspector_options)
        
        current_inspector_data = next((p for p in INSPECTOR_LIST if p["label"] == inspector_name), None)
        allowed_roles = current_inspector_data.get("allowed_roles", ["內掃檢查"])
        assigned_classes = current_inspector_data.get("assigned_classes", [])
        
        if len(allowed_roles) > 1:
            st.success(f"👋 您好 {inspector_name}，您的權限：{', '.join(allowed_roles)}")
            role = st.selectbox("請選擇現在要執行的檢查", allowed_roles)
        else:
            st.info(f"📋 您的負責項目：**{allowed_roles[0]}**")
            role = allowed_roles[0]
        
        selected_class = None
        edited_morning_df = None
        edited_trash_df = None
        trash_category = ""
        
        col_date, col_btn = st.columns([3, 1])
        with col_date:
            input_date = st.date_input("檢查日期", datetime.now())
        with col_btn:
            st.write("") 
            st.write("")
            if st.button("🔄 刷新"): st.rerun()

        week_num, start_date = get_school_week(input_date)
        holidays_df = load_holidays()
        is_holiday = str(input_date) in holidays_df["日期"].values
        if is_holiday: st.warning(f"⚠️ 注意：{input_date} 是假日。")

        # --- 介面分流 ---
        if role == "晨間打掃":
            daily_duty_list, duty_status, diag_info = get_daily_duty(input_date)
            
            if duty_status == "success":
                st.markdown(f"### 📋 今日 ({input_date}) 晨掃點名表")
                st.info("👇 請在 **「已完成打掃」** 欄位打勾。**未打勾者** 將被視為缺席並扣分。")
                duty_df = pd.DataFrame(daily_duty_list)
                edited_morning_df = st.data_editor(
                    duty_df,
                    column_config={"已完成打掃": st.column_config.CheckboxColumn("✅ 已完成打掃", default=False)},
                    disabled=["學號", "姓名", "掃地區域"],
                    hide_index=True, use_container_width=True
                )
                checked_count = edited_morning_df["已完成打掃"].sum()
                total_count = len(edited_morning_df)
                absent_count = total_count - checked_count
                
                st.write(f"**統計：** 應到 {total_count} 人｜實到 {checked_count} 人｜🔴 缺席 {absent_count} 人")
                
                if absent_count == total_count: st.warning("⚠️ 注意：目前全員缺席！")
            elif duty_status == "no_data_for_date": 
                st.warning(f"⚠️ 找不到 {input_date} 的輪值資料。")
            else: st.error("⚠️ 讀取輪值表失敗。")

        elif role == "垃圾/回收檢查":
            # v30.0: 垃圾評分重製版 (不分區，直接填表)
            st.info(f"📅 第 {week_num} 週 (垃圾/回收評分)")
            
            trash_category = st.selectbox("1. 請選擇違規項目", ["一般垃圾", "紙類", "網袋", "其他回收"])
            
            st.markdown(f"### 📋 全校違規登記表 ({trash_category})")
            st.info("請點選下方欄位選擇違規事項 (若無違規請留空)。")
            
            # 選項
            vio_options = [None, "無簽名", "分類錯"]
            
            # 建立空的資料表結構
            trash_data = [{"班級": cls, "扣分1": None, "扣分2": None} for cls in all_classes]
            trash_df_init = pd.DataFrame(trash_data)
            
            edited_trash_df = st.data_editor(
                trash_df_init,
                column_config={
                    "班級": st.column_config.TextColumn("班級", disabled=True),
                    "扣分1": st.column_config.SelectboxColumn(
                        "扣分1 (1分)",
                        help="選擇違規原因",
                        width="medium",
                        options=vio_options
                    ),
                    "扣分2": st.column_config.SelectboxColumn(
                        "扣分2 (1分)",
                        help="選擇第二個違規原因",
                        width="medium",
                        options=vio_options
                    )
                },
                hide_index=True,
                height=600,
                use_container_width=True
            )

        else:
            if assigned_classes:
                class_options = assigned_classes
                st.caption("✅ 已依據您的職掌，自動篩選出負責班級。")
            else:
                class_options = all_classes
                st.caption("ℹ️ 您未被指定特定班級，顯示全校列表。")
            selected_class = st.selectbox("被登記班級", class_options)
            st.info(f"📅 第 {week_num} 週")

        with st.form("scoring_form"):
            in_score = 0; out_score = 0; trash_score = 0; morning_score = 0; phone_count = 0; note = ""
            is_perfect = False
            
            if role == "內掃檢查":
                check_status = st.radio("檢查結果", ["❌ 發現違規", "✨ 很乾淨 (不扣分)"], horizontal=True)
                if check_status == "❌ 發現違規":
                    st.subheader("違規事項登錄")
                    in_score = st.number_input("🧹 內掃扣分", min_value=0, step=1)
                    note = st.text_input("違規說明", placeholder="例：黑板未擦")
                    phone_count = st.number_input("📱 玩手機人數", min_value=0, step=1)
                else:
                    is_perfect = True
                    st.success("🎉 太棒了！請上傳照片作為嘉獎佐證。")
                    note = "【優良】環境整潔"

            elif role == "外掃檢查":
                check_status = st.radio("檢查結果", ["❌ 發現違規", "✨ 很乾淨 (不扣分)"], horizontal=True)
                if check_status == "❌ 發現違規":
                    st.subheader("違規事項登錄")
                    out_score = st.number_input("🍂 外掃扣分", min_value=0, step=1)
                    note = st.text_input("違規說明", placeholder="例：走廊有垃圾")
                    phone_count = st.number_input("📱 玩手機人數", min_value=0, step=1)
                else:
                    is_perfect = True
                    st.success("🎉 太棒了！請上傳照片作為嘉獎佐證。")
                    note = "【優良】環境整潔"

            elif role == "晨間打掃":
                st.markdown("**扣分設定：**")
                morning_score = st.number_input("未到扣分 (每人)", min_value=0, step=1, value=1)
                note = "晨掃未到/未打掃"

            st.write("")
            if role != "垃圾/回收檢查" and role != "晨間打掃":
                is_correction = st.checkbox("🚩 這是一筆修正資料 (勾選後，系統將覆蓋舊紀錄)")
            else:
                is_correction = False

            uploaded_files = None
            if role in ["內掃檢查", "外掃檢查"]:
                uploaded_files = st.file_uploader("📸 上傳照片 (違規或優良佐證)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
            
            submitted = st.form_submit_button("送出評分", use_container_width=True)

            if submitted:
                img_path_str = ""
                if uploaded_files:
                    saved_paths = []
                    timestamp = datetime.now().strftime("%H%M%S")
                    for i, u_file in enumerate(uploaded_files):
                        file_ext = u_file.name.split('.')[-1]
                        filename = f"{input_date}_batch_{timestamp}_{i+1}.{file_ext}"
                        full_path = os.path.join(IMG_DIR, filename)
                        with open(full_path, "wb") as f: f.write(u_file.getbuffer())
                        saved_paths.append(full_path)
                    img_path_str = ";".join(saved_paths)

                # --- 邏輯分流 ---
                if role == "晨間打掃":
                    if edited_morning_df is None:
                        st.error("無資料可送出")
                    else:
                        absent_students = edited_morning_df[edited_morning_df["已完成打掃"] == False]
                        if absent_students.empty:
                            st.success("🎉 全員到齊！")
                        else:
                            count = 0
                            for _, r in absent_students.iterrows():
                                tid, tname, tloc = r["學號"], r["姓名"], r["掃地區域"]
                                tclass = ROSTER_DICT.get(tid, "待確認")
                                entry = {
                                    "日期": input_date, "週次": week_num, "班級": tclass,
                                    "評分項目": role, "檢查人員": inspector_name,
                                    "內掃原始分":0, "外掃原始分":0, "垃圾原始分":0, "晨間打掃原始分": morning_score,
                                    "手机人數":0, "垃圾內掃原始分":0, "垃圾外掃原始分":0,
                                    "備註": f"{note} ({tloc}) - {tname}", "照片路徑":"", "違規細項":"",
                                    "登錄時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "修正": False, "晨掃未到者": f"{tid} {tname}"
                                }
                                save_entry(entry)
                                count += 1
                            st.success(f"✅ 已登記 {count} 位未到學生！")

                elif role == "垃圾/回收檢查":
                    # v30.0 垃圾下拉選單處理
                    if edited_trash_df is None:
                        st.error("無資料")
                    else:
                        saved_count = 0
                        for _, row in edited_trash_df.iterrows():
                            # 檢查扣分欄位
                            v1 = row["扣分1"]
                            v2 = row["扣分2"]
                            
                            score = 0
                            reasons = []
                            if v1: 
                                score += 1
                                reasons.append(v1)
                            if v2: 
                                score += 1
                                reasons.append(v2)
                            
                            if score > 0:
                                detail_str = "、".join(reasons)
                                note_str = f"{trash_category}: {detail_str}"
                                
                                # 存入「垃圾原始分」，後台會自動加總並計算上限
                                entry = {
                                    "日期": input_date, "週次": week_num, "班級": row["班級"],
                                    "評分項目": role, "檢查人員": inspector_name,
                                    "內掃原始分":0, "外掃原始分":0, 
                                    "垃圾原始分": score, # 存入總分
                                    "晨間打掃原始分":0, "手機人數":0,
                                    "垃圾內掃原始分": 0, "垃圾外掃原始分": 0, # 不分區，填0
                                    "備註": note_str, "照片路徑": "", "違規細項": trash_category,
                                    "登錄時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "修正": False, "晨掃未到者": ""
                                }
                                save_entry(entry)
                                saved_count += 1
                        
                        if saved_count > 0: st.success(f"✅ 已成功登記 {saved_count} 筆違規紀錄！")
                        else: st.info("👍 沒有任何班級違規。")

                else:
                    final_note = note
                    if is_correction and "【修正】" not in note: final_note = f"【修正】 {note}"

                    entry = {
                        "日期": input_date, "週次": week_num, "班級": selected_class,
                        "評分項目": role, "檢查人員": inspector_name,
                        "內掃原始分": in_score, "外掃原始分": out_score,
                        "垃圾原始分": trash_score, "晨間打掃原始分": morning_score,
                        "手機人數": phone_count, "垃圾內掃原始分":0, "垃圾外掃原始分":0,
                        "備註": final_note, "照片路徑": img_path_str, "違規細項": "",
                        "登錄時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "修正": is_correction, "晨掃未到者": ""
                    }
                    save_entry(entry)
                    st.success(f"✅ 登記完成！")
    else:
        st.info("👈 請在左側輸入通行碼以開始評分")

# ------------------------------------------
# 模式二：班上衛生股長
# ------------------------------------------
elif app_mode == "我是班上衛生股長":
    st.title("🔎 班級成績查詢與申訴")
    df = load_data()
    if not df.empty:
        search_class = st.selectbox("請選擇您的班級", all_classes)
        class_df = df[df["班級"] == search_class].copy()
        
        if not class_df.empty:
            class_df = class_df.sort_values(by="登錄時間", ascending=False).reset_index()
            st.subheader(f"📅 {search_class} 近期紀錄")
            
            for i, row in class_df.iterrows():
                record_id = row['index'] 
                total_raw = (row["內掃原始分"] + row["外掃原始分"] + row["垃圾原始分"] + 
                             row["晨間打掃原始分"] + row["手機人數"] + 
                             row["垃圾內掃原始分"] + row["垃圾外掃原始分"])
                title_prefix = "🔴 [修正單] " if row["修正"] else ""
                is_praise = "【優良】" in str(row["備註"])
                
                if total_raw >= 0 or is_praise:
                    with st.expander(f"{title_prefix}[第{row['週次']}週] {row['日期']} - {row['評分項目']}"):
                        st.write(f"**說明：** {row['備註']}")
                        if is_praise:
                            st.success("✨ 表現優良！")
                        else:
                            msg = []
                            if row["內掃原始分"] > 0: msg.append(f"內掃扣 {row['內掃原始分']}")
                            if row["外掃原始分"] > 0: msg.append(f"外掃扣 {row['外掃原始分']}")
                            # 合併垃圾顯示
                            trash_total = row["垃圾原始分"] + row["垃圾內掃原始分"] + row["垃圾外掃原始分"]
                            if trash_total > 0: msg.append(f"垃圾/回收扣 {trash_total}")
                            
                            if row["晨間打掃原始分"] > 0: msg.append(f"晨掃扣 {row['晨間打掃原始分']}")
                            if row["手機人數"] > 0: msg.append(f"手機 {row['手機人數']}人")
                            if msg: st.error(" | ".join(msg))
                            else: st.info("無扣分")
                        st.caption(f"檢查人員：{row['檢查人員']} | 時間：{row['登錄時間']}")
                        
                        if not is_praise:
                            if st.button("📣 我要申訴", key=f"appeal_btn_{record_id}"):
                                st.session_state[f"show_appeal_{record_id}"] = True
                            if st.session_state.get(f"show_appeal_{record_id}", False):
                                with st.form(key=f"appeal_form_{record_id}"):
                                    appeal_reason = st.text_area("請輸入申訴理由：")
                                    appeal_imgs = st.file_uploader("📸 上傳佐證照片", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
                                    if st.form_submit_button("送出申訴"):
                                        appeal_img_str = ""
                                        if appeal_imgs:
                                            paths = []
                                            ts = datetime.now().strftime("%H%M%S")
                                            for idx, f in enumerate(appeal_imgs):
                                                fname = f"Appeal_{record_id}_{ts}_{idx}.jpg"
                                                fpath = os.path.join(IMG_DIR, fname)
                                                with open(fpath, "wb") as w: w.write(f.getbuffer())
                                                paths.append(fpath)
                                            appeal_img_str = ";".join(paths)
                                        appeal_entry = {
                                            "日期": str(datetime.now().date()),
                                            "班級": search_class,
                                            "原始紀錄ID": record_id,
                                            "申訴理由": appeal_reason,
                                            "申請時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                            "狀態": "待處理",
                                            "佐證照片": appeal_img_str
                                        }
                                        save_appeal(appeal_entry)
                                        st.success("申訴已送出！")
                                        st.session_state[f"show_appeal_{record_id}"] = False
                                        st.rerun()
                        path_str = str(row["照片路徑"])
                        if path_str and path_str != "nan":
                            paths = path_str.split(";")
                            st.write("現場照片：")
                            cols = st.columns(3)
                            for k, p in enumerate(paths):
                                if os.path.exists(p): cols[k%3].image(p, width=150)
        else:
            st.success("🎉 目前沒有違規紀錄")
    else:
        st.info("尚無資料")

# ------------------------------------------
# 模式三：衛生組後台
# ------------------------------------------
elif app_mode == "衛生組後台":
    st.title("📊 衛生組長管理後台")
    password = st.text_input("請輸入管理密碼", type="password")
    
    if password == SYSTEM_CONFIG["admin_password"]:
        df = load_data()
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 成績報表", "📢 申訴管理", "🛠️ 資料管理", "⚙️ 系統設定", "🩺 資料診斷"])
        
        # --- Tab 1: 報表區 ---
        with tab1:
            if not df.empty:
                available_weeks = sorted(df["週次"].unique())
                if not available_weeks:
                    st.warning("無資料")
                else:
                    st.write("### 📅 報表範圍選擇")
                    selected_weeks = st.multiselect("選擇要結算的週次", available_weeks, default=[available_weeks[-1]])
                    
                    if selected_weeks:
                        week_df = df[df["週次"].isin(selected_weeks)].copy()
                        week_df["晨掃未到者"] = week_df["晨掃未到者"].fillna("")
                        week_df["違規細項"] = week_df["違規細項"].fillna("")
                        week_df["修正"] = week_df["修正"].fillna(False)
                        
                        week_df_sorted = week_df.sort_values(by="登錄時間", ascending=False)
                        cleaned_rows = []
                        groups = week_df_sorted.groupby(["日期", "班級", "評分項目", "晨掃未到者", "違規細項"])
                        for name, group in groups:
                            if group["修正"].any():
                                best_entry = group[group["修正"] == True].iloc[0]
                                cleaned_rows.append(best_entry)
                            else:
                                for _, row in group.iterrows():
                                    cleaned_rows.append(row)
                        cleaned_df = pd.DataFrame(cleaned_rows)
                        
                        if cleaned_df.empty:
                            st.warning("無有效數據")
                        else:
                            daily_group = cleaned_df.groupby(["日期", "班級"]).agg({
                                "內掃原始分": "sum", "外掃原始分": "sum", "垃圾原始分": "sum", 
                                "垃圾內掃原始分": "sum", "垃圾外掃原始分": "sum",
                                "晨間打掃原始分": "sum",
                                "手機人數": "sum", 
                                "備註": lambda x: " | ".join([str(s) for s in x if str(s) not in ["", "nan", "None"]]),
                                "檢查人員": lambda x: ", ".join(set([str(s) for s in x if str(s) not in ["", "nan"]]))
                            }).reset_index()
                            
                            daily_group["內掃結算"] = daily_group["內掃原始分"].apply(lambda x: min(x, 2))
                            daily_group["外掃結算"] = daily_group["外掃原始分"].apply(lambda x: min(x, 2))
                            # v30.0: 垃圾總分 (舊制+新制) 上限2分
                            daily_group["垃圾結算"] = (daily_group["垃圾原始分"] + daily_group["垃圾內掃原始分"] + daily_group["垃圾外掃原始分"]).apply(lambda x: min(x, 2))
                            
                            daily_group["晨間打掃結算"] = daily_group["晨間打掃原始分"]
                            daily_group["手機扣分"] = daily_group["手機人數"] * 1
                            
                            daily_group["當日總扣分"] = (daily_group["內掃結算"] + daily_group["外掃結算"] + daily_group["垃圾結算"] + 
                                                       daily_group["晨間打掃結算"] + daily_group["手機扣分"])
                            
                            class_score_df = pd.DataFrame(all_classes, columns=["班級"])
                            final_deductions = daily_group.groupby("班級")["當日總扣分"].sum().reset_index()
                            daily_pivot = daily_group.pivot(index="班級", columns="日期", values="當日總扣分").reset_index().fillna(0)
                            
                            report = pd.merge(class_score_df, final_deductions, on="班級", how="left").fillna(0)
                            report = pd.merge(report, daily_pivot, on="班級", how="left").fillna(0)
                            report["總成績"] = 90 - report["當日總扣分"]
                            
                            date_cols = sorted([col for col in report.columns if col not in ["班級", "當日總扣分", "總成績"]])
                            final_cols = ["班級"] + date_cols + ["當日總扣分", "總成績"]
                            report = report[final_cols].sort_values(by="總成績", ascending=False)
                            
                            def make_desc(row):
                                reasons = []
                                if row["內掃原始分"] > 0: reasons.append(f"內掃({row['內掃原始分']})")
                                if row["外掃原始分"] > 0: reasons.append(f"外掃({row['外掃原始分']})")
                                
                                # 合併顯示垃圾
                                trash_sum = row["垃圾原始分"] + row["垃圾內掃原始分"] + row["垃圾外掃原始分"]
                                if trash_sum > 0: reasons.append(f"垃圾({trash_sum})")
                                
                                if row["晨間打掃原始分"] > 0: reasons.append(f"晨掃({row['晨間打掃原始分']})")
                                if row["手機人數"] > 0: reasons.append(f"手機({row['手機人數']})")
                                if "【優良】" in str(row["備註"]): reasons.append("✨優良")
                                return "\n".join(reasons)
                            
                            cleaned_df['違規簡述'] = cleaned_df.apply(make_desc, axis=1)
                            detail_df = cleaned_df[cleaned_df['違規簡述'] != ""]
                            reason_pivot = pd.DataFrame()
                            if not detail_df.empty:
                                reason_pivot = detail_df.pivot_table(index="班級", columns="日期", values="違規簡述", aggfunc=lambda x: "\n".join(x)).reset_index().fillna("")

                            morning_absent_df = cleaned_df[cleaned_df["評分項目"] == "晨間打掃"][["日期", "班級", "晨掃未到者", "晨間打掃原始分", "備註"]].sort_values(by="日期")

                            import io
                            output = io.BytesIO()
                            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                                report.to_excel(writer, index=False, sheet_name='總成績')
                                if not reason_pivot.empty: reason_pivot.to_excel(writer, index=False, sheet_name='違規原因一覽表')
                                morning_absent_df.to_excel(writer, index=False, sheet_name='🌅晨掃未到明細')
                                daily_group.to_excel(writer, index=False, sheet_name='每日統計')
                                week_df.to_excel(writer, index=False, sheet_name='原始輸入紀錄')
                            
                            st.download_button(label="📥 下載 Excel 報表", data=output.getvalue(), file_name="衛生糾察總表.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                            
                            st.write("##### 🏆 成績總覽")
                            numeric_cols = report.select_dtypes(include=['number']).columns
                            st.dataframe(report.style.format("{:.0f}", subset=numeric_cols).background_gradient(subset=["總成績"], cmap="RdYlGn", vmin=60, vmax=90))

        # --- Tab 2: 申訴管理 ---
        with tab2:
            st.write("### 📢 學生申訴案件")
            appeals_df = load_appeals()
            pending_appeals = appeals_df[appeals_df["狀態"] == "待處理"].copy()
            if not pending_appeals.empty:
                for i, row in pending_appeals.iterrows():
                    with st.expander(f"【申訴】{row['日期']} {row['班級']} - 理由：{row['申訴理由']}"):
                        st.write(f"申請時間：{row['申請時間']}")
                        if "佐證照片" in row and str(row["佐證照片"]) != "nan" and row["佐證照片"]:
                            st.write("**📸 申訴佐證照片：**")
                            appeal_paths = str(row["佐證照片"]).split(";")
                            acols = st.columns(3)
                            for k, ap in enumerate(appeal_paths):
                                if os.path.exists(ap): acols[k%3].image(ap, width=150)
                        c1, c2 = st.columns(2)
                        if c1.button("✅ 核准 (撤銷扣分)", key=f"approve_{i}"):
                            delete_entry([row['原始紀錄ID']])
                            real_idx = appeals_df[appeals_df['申請時間'] == row['申請時間']].index[0]
                            update_appeal_status(real_idx, "已核准(撤銷)")
                            st.success("已撤銷！")
                            st.rerun()
                        if c2.button("❌ 駁回", key=f"reject_{i}"):
                            real_idx = appeals_df[appeals_df['申請時間'] == row['申請時間']].index[0]
                            update_appeal_status(real_idx, "已駁回")
                            st.warning("已駁回。")
                            st.rerun()
            else: st.info("無待處理案件。")
            with st.expander("查看歷史紀錄"): st.dataframe(appeals_df)

        # --- Tab 3: 資料管理 ---
        with tab3:
            st.write("### 🗑️ 批次刪除")
            c1, c2 = st.columns(2)
            d1 = c1.date_input("起始日期", datetime.now() - timedelta(days=7))
            d2 = c2.date_input("結束日期", datetime.now())
            if st.button("🗑️ 確認刪除區間資料"):
                if d1 > d2: st.error("起始日期不能晚於結束日期")
                else:
                    deleted_count = delete_batch(d1, d2)
                    st.success(f"已刪除 {deleted_count} 筆紀錄！")
                    st.rerun()
            st.write("---")
            st.write("### 🛠️ 單筆刪除")
            if not df.empty:
                df_display = df.sort_values(by="登錄時間", ascending=False).reset_index()
                options = {row['index']: f"[{'修正單' if row['修正'] else '一般'}] {row['日期']} {row['班級']} - {row['評分項目']} | 備註: {row['備註']}" for i, row in df_display.iterrows()}
                selected_indices = st.multiselect("選擇要刪除的紀錄：", options=options.keys(), format_func=lambda x: options[x])
                if st.button("🗑️ 確認刪除"):
                    delete_entry(selected_indices)
                    st.success("刪除成功！")
                    st.rerun()
            else: st.info("無資料")

        # --- Tab 4: 系統設定區 ---
        with tab4:
            st.header("⚙️ 系統設定")
            st.subheader("1. 🔐 密碼管理")
            c1, c2 = st.columns(2)
            new_admin_pwd = c1.text_input("管理員密碼", value=SYSTEM_CONFIG["admin_password"], type="password")
            new_team_pwd = c2.text_input("糾察隊通行碼", value=SYSTEM_CONFIG["team_password"])
            if st.button("💾 更新密碼"):
                SYSTEM_CONFIG["admin_password"] = new_admin_pwd
                SYSTEM_CONFIG["team_password"] = new_team_pwd
                save_config(SYSTEM_CONFIG)
                st.success("密碼已更新")

            st.divider()
            st.subheader("2. 📂 檔案上傳設定")
            st.write("**A. 全校名單 (csv)**")
            if ROSTER_DEBUG['status'] == 'success': st.success(f"✅ 已讀取 {len(ROSTER_DICT)} 筆資料")
            else: st.error(f"❌ 讀取失敗: {ROSTER_DEBUG['status']}")
            uploaded_roster = st.file_uploader("更新全校名單", type=["csv"], key="roster_up")
            if uploaded_roster:
                with open(ROSTER_FILE, "wb") as f: f.write(uploaded_roster.getbuffer())
                st.success("上傳成功！")
                st.rerun()
            st.write("---")
            st.write("**B. 糾察隊名單 (csv)**")
            if INSPECTOR_DEBUG['status'] == 'success':
                st.success(f"✅ 名單格式正確，共 {INSPECTOR_DEBUG['rows']} 人。")
                with st.expander("🔍 點擊查看名單預覽"):
                    preview_df = pd.DataFrame(INSPECTOR_LIST).drop(columns=["raw_role", "assigned_classes"], errors='ignore')
                    st.dataframe(preview_df.head(10))
            elif INSPECTOR_DEBUG['status'] == 'missing_name_col':
                st.error("❌ 找不到「姓名」欄位！")
                st.write("目前讀取到的欄位：", INSPECTOR_DEBUG['cols'])
            else: st.warning("⚠️ 尚未上傳或讀取失敗")
            uploaded_insp = st.file_uploader("更新糾察隊名單", type=["csv"], key="insp_up")
            if uploaded_insp:
                with open(INSPECTOR_DUTY_FILE, "wb") as f: f.write(uploaded_insp.getbuffer())
                st.success("名單更新成功！")
                st.rerun()
            st.write("---")
            st.write("**C. 晨掃輪值表 (csv)**")
            if os.path.exists(DUTY_FILE): st.success("✅ 目前已有輪值表檔案")
            else: st.warning("⚠️ 尚未上傳輪值表")
            uploaded_duty = st.file_uploader("上傳晨掃輪值表", type=["csv"], key="duty_up")
            if uploaded_duty:
                with open(DUTY_FILE, "wb") as f: f.write(uploaded_duty.getbuffer())
                st.success("輪值表上傳成功！")
                st.rerun()
            st.divider()
            st.subheader("3. 學期與假日")
            current_start = datetime.strptime(SYSTEM_CONFIG["semester_start"], "%Y-%m-%d").date()
            new_date = st.date_input("開學日", current_start)
            if st.button("更新開學日"):
                SYSTEM_CONFIG["semester_start"] = str(new_date)
                save_config(SYSTEM_CONFIG)
                st.success("已更新")

        # --- Tab 5: 資料診斷 ---
        with tab5:
            st.header("🩺 資料診斷室")
            st.info("這裡可以幫您檢查為什麼某些學生在晨掃名單中找不到。")
            
            st.write("#### 1. 晨掃輪值表診斷")
            if os.path.exists(DUTY_FILE):
                test_date = st.date_input("測試日期", datetime.now(), key="diag_date")
                _, status, diag_info = get_daily_duty(test_date)
                st.write(f"**檔案狀態**: {status}")
                st.write(f"**總資料筆數**: {diag_info.get('total_rows', 0)}")
                if diag_info.get("all_dates_found"):
                    st.write("**檔案中包含的所有日期 (前20筆):**")
                    st.write(diag_info["all_dates_found"][:20])
                    st.write("---")
                    st.write(f"**您選擇的日期**: {test_date}")
                    st.write(f"**符合該日期的筆數**: {diag_info.get('matched_rows', 0)}")
                    if diag_info.get('matched_rows', 0) == 0: st.error("❌ 找不到符合此日期的資料！")
                else: st.warning("無法解析出任何日期")
            else: st.error("找不到晨掃輪值表檔案")

    else:
        st.error("密碼錯誤")