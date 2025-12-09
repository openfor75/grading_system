import streamlit as st
import pandas as pd
import os
import json
import shutil
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta

# --- 設定網頁標題 ---
st.set_page_config(page_title="衛生糾察評分系統 (單機版)", layout="wide")

# ==========================================
# 0. 基礎設定與檔案管理
# ==========================================

SCORING_FILE = "scoring_data.csv"
BACKUP_DIR = "backups"
IMG_DIR = "evidence_photos"
CONFIG_FILE = "config.json"
HOLIDAY_FILE = "holidays.csv"
ROSTER_FILE = "全校名單.csv" 
DUTY_FILE = "晨掃輪值.csv" 
APPEALS_FILE = "appeals.csv"
INSPECTOR_DUTY_FILE = "糾察隊名單.csv" 
TEACHER_MAIL_FILE = "導師名單.csv"

if not os.path.exists(IMG_DIR): os.makedirs(IMG_DIR)
if not os.path.exists(BACKUP_DIR): os.makedirs(BACKUP_DIR)

# ==========================================
# 1. 資料庫與備份函式
# ==========================================

def perform_daily_backup():
    if not os.path.exists(SCORING_FILE): return
    today_str = datetime.now().strftime("%Y-%m-%d")
    backup_filename = f"scoring_data_{today_str}.csv"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    if not os.path.exists(backup_path):
        try: shutil.copy(SCORING_FILE, backup_path)
        except: pass

def load_data():
    expected_columns = [
        "日期", "週次", "班級", "評分項目", "檢查人員",
        "內掃原始分", "外掃原始分", "垃圾原始分", "垃圾內掃原始分", "垃圾外掃原始分", "晨間打掃原始分", "手機人數", 
        "備註", "違規細項", "照片路徑", "登錄時間", "修正", "晨掃未到者"
    ]
    if os.path.exists(SCORING_FILE):
        try:
            df = pd.read_csv(SCORING_FILE)
            for col in expected_columns:
                if col not in df.columns: df[col] = ""
            numeric_cols = ["內掃原始分", "外掃原始分", "垃圾原始分", "垃圾內掃原始分", "垃圾外掃原始分", "晨間打掃原始分", "手機人數"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            if "修正" in df.columns:
                df["修正"] = df["修正"].astype(str).apply(lambda x: True if x.upper() == "TRUE" else False)
            return df[expected_columns]
        except Exception as e:
            st.error(f"讀取 CSV 失敗: {e}")
            return pd.DataFrame(columns=expected_columns)
    else:
        return pd.DataFrame(columns=expected_columns)

def save_entry(new_entry):
    try:
        perform_daily_backup()
        df = load_data()
        new_row = pd.DataFrame([new_entry])
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv(SCORING_FILE, index=False, encoding='utf-8-sig')
    except Exception as e:
        st.error(f"寫入資料失敗: {e}")

def delete_entry(indices_to_delete):
    try:
        perform_daily_backup()
        df = load_data()
        df = df.drop(indices_to_delete)
        df.to_csv(SCORING_FILE, index=False, encoding='utf-8-sig')
    except Exception as e:
        st.error(f"刪除資料失敗: {e}")

def delete_batch(start_date, end_date):
    try:
        perform_daily_backup()
        df = load_data()
        if df.empty: return 0
        df["日期_dt"] = pd.to_datetime(df["日期"]).dt.date
        mask = (df["日期_dt"] >= start_date) & (df["日期_dt"] <= end_date)
        deleted_count = mask.sum()
        df_remaining = df[~mask].drop(columns=["日期_dt"])
        df_remaining.to_csv(SCORING_FILE, index=False, encoding='utf-8-sig')
        return deleted_count
    except Exception as e:
        st.error(f"批次刪除失敗: {e}")
        return 0

# ==========================================
# 2. 設定檔
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
    with open(CONFIG_FILE, "w", encoding='utf-8') as f: json.dump(new_config, f, ensure_ascii=False)

SYSTEM_CONFIG = load_config()

# ==========================================
# 3. CSV 讀取 (輔助函式)
# ==========================================
@st.cache_data
def load_teacher_emails():
    email_dict = {}
    if os.path.exists(TEACHER_MAIL_FILE):
        try:
            encodings = ['utf-8', 'big5', 'cp950']
            df = None
            for enc in encodings:
                try: df = pd.read_csv(TEACHER_MAIL_FILE, encoding=enc, dtype=str); break
                except: continue
            if df is not None:
                df.columns = df.columns.str.strip()
                class_col = next((c for c in df.columns if "班級" in c), None)
                mail_col = next((c for c in df.columns if "Email" in c or "信箱" in c), None)
                name_col = next((c for c in df.columns if "導師" in c or "姓名" in c), None)
                if class_col and mail_col:
                    for _, row in df.iterrows():
                        cls, mail = str(row[class_col]).strip(), str(row[mail_col]).strip()
                        name = str(row[name_col]).strip() if name_col else "老師"
                        if cls and mail and "@" in mail: email_dict[cls] = {"email": mail, "name": name}
        except: pass
    return email_dict

@st.cache_data
def load_roster_dict(csv_path=ROSTER_FILE):
    roster_dict = {}
    if os.path.exists(csv_path):
        encodings = ['utf-8', 'big5', 'cp950', 'utf-8-sig']
        df = None
        for enc in encodings:
            try: df = pd.read_csv(csv_path, encoding=enc, dtype=str); df.columns = df.columns.str.strip(); break
            except: continue
        if df is not None:
            id_col = next((c for c in df.columns if "學號" in c), None)
            class_col = next((c for c in df.columns if "班級" in c), None)
            if id_col and class_col:
                for _, row in df.iterrows():
                    s_id, s_class = str(row[id_col]).strip(), str(row[class_col]).strip()
                    if s_id and s_class and s_id.lower() != "nan": roster_dict[s_id] = s_class
    return roster_dict, {}
ROSTER_DICT, _ = load_roster_dict()

# 修正：確保讀取地點
def get_daily_duty(target_date, csv_path=DUTY_FILE):
    duty_list = []
    status = "init"
    if os.path.exists(csv_path):
        encodings = ['utf-8', 'big5', 'cp950', 'utf-8-sig']
        df = None
        for enc in encodings:
            try: df = pd.read_csv(csv_path, encoding=enc, dtype=str); df.columns = df.columns.str.strip(); break
            except: continue
        if df is not None:
            date_col = next((c for c in df.columns if "日期" in c or "時間" in c), None)
            id_col = next((c for c in df.columns if "學號" in c), None)
            loc_col = next((c for c in df.columns if "地點" in c or "區域" in c), None)
            
            if date_col and id_col:
                try: df[date_col] = pd.to_datetime(df[date_col], errors='coerce').dt.date
                except: pass
                target_date_obj = target_date if isinstance(target_date, date) else target_date.date()
                today_df = df[df[date_col] == target_date_obj]
                if not today_df.empty:
                    for _, row in today_df.iterrows():
                        duty_list.append({
                            "學號": str(row[id_col]).strip(), 
                            "掃地區域": str(row[loc_col]).strip() if loc_col else "未指定", 
                            "已完成打掃": False
                        })
                    status = "success"
                else: status = "no_data_for_date"
            else: status = "missing_columns"
        else: status = "read_failed"
    else: status = "file_not_found"
    return duty_list, status, {}

@st.cache_data
def load_inspector_csv():
    inspectors = []
    if not os.path.exists(INSPECTOR_DUTY_FILE):
        return [{"label": "衛生組長 (預設)", "allowed_roles": ["內掃檢查","外掃檢查","垃圾/回收檢查","晨間打掃"], "assigned_classes": [], "id_prefix": "9"}], {}
    encodings = ['utf-8', 'big5', 'cp950', 'utf-8-sig', 'gbk']
    df = None
    for enc in encodings:
        try: df = pd.read_csv(INSPECTOR_DUTY_FILE, encoding=enc, dtype=str); df.columns = df.columns.str.strip(); break
        except: continue
    if df is not None:
        id_col = next((c for c in df.columns if "學號" in c or "編號" in c), None)
        role_col = next((c for c in df.columns if "負責" in c or "項目" in c), None)
        class_scope_col = next((c for c in df.columns if "班級" in c or "範圍" in c), None)
        
        if id_col:
            for _, row in df.iterrows():
                s_id = str(row[id_col]).strip()
                s_raw_role = str(row[role_col]).strip() if role_col else "未指定"
                s_classes = []
                if class_scope_col:
                    raw_scope = str(row[class_scope_col])
                    if raw_scope and raw_scope.lower() != "nan":
                        s_classes = [c.strip() for c in raw_scope.replace("、", ";").replace(",", ";").split(";") if c.strip()]
                
                allowed_roles = []
                if "組長" in s_raw_role: allowed_roles = ["內掃檢查", "外掃檢查", "垃圾/回收檢查", "晨間打掃"]
                elif "機動" in s_raw_role: allowed_roles = ["內掃檢查", "外掃檢查", "垃圾/回收檢查"]
                else:
                    if "外掃" in s_raw_role: allowed_roles.append("外掃檢查")
                    if "垃圾" in s_raw_role or "回收" in s_raw_role: allowed_roles.append("垃圾/回收檢查")
                    if "晨" in s_raw_role: allowed_roles.append("晨間打掃")
                    if "內掃" in s_raw_role: allowed_roles.append("內掃檢查")
                if not allowed_roles: allowed_roles = ["內掃檢查"]
                
                label = f"學號: {s_id}"
                prefix = s_id[0] if s_id else "其"
                inspectors.append({"label": label, "allowed_roles": allowed_roles, "assigned_classes": s_classes, "raw_role": s_raw_role, "id_prefix": prefix})
    if not inspectors: inspectors.append({"label": "測試人員", "allowed_roles": ["內掃檢查"], "assigned_classes": [], "id_prefix": "測"})
    return inspectors, {}
INSPECTOR_LIST, _ = load_inspector_csv()

def load_holidays():
    if os.path.exists(HOLIDAY_FILE): return pd.read_csv(HOLIDAY_FILE)
    return pd.DataFrame(columns=["日期", "原因"])
def get_school_week(date_obj):
    start_date = datetime.strptime(SYSTEM_CONFIG["semester_start"], "%Y-%m-%d").date()
    if isinstance(date_obj, datetime): date_obj = date_obj.date()
    delta = date_obj - start_date
    week_num = (delta.days // 7) + 1
    return max(0, week_num), start_date

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

def load_appeals():
    if os.path.exists(APPEALS_FILE):
        df = pd.read_csv(APPEALS_FILE)
        if "佐證照片" not in df.columns: df["佐證照片"] = ""
        return df
    return pd.DataFrame(columns=["日期", "班級", "原始紀錄ID", "申訴理由", "申請時間", "狀態", "佐證照片"])
def save_appeal(entry):
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
        today = datetime.now().date()
        date_range = pd.bdate_range(start=record_date, end=today)
        return len(date_range) > 4
    except: return True

def send_email(to_email, subject, body):
    sender_email = SYSTEM_CONFIG["smtp_email"]
    sender_password = SYSTEM_CONFIG["smtp_password"]
    if not sender_email or not sender_password: return False, "尚未設定寄件者"
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
# 介面開始
# ==========================================
st.sidebar.title("🏫 功能選單")
app_mode = st.sidebar.radio("請選擇模式", ["我是糾察隊 (評分)", "我是班上衛生股長", "衛生組後台"])

if app_mode == "我是糾察隊 (評分)":
    st.title("📝 衛生糾察評分系統 (單機版)")
    
    if "team_logged_in" not in st.session_state: st.session_state["team_logged_in"] = False
    
    # 登入區塊
    if not st.session_state["team_logged_in"]:
        with st.expander("🔐 身份驗證", expanded=True):
            input_code = st.text_input("請輸入隊伍通行碼", type="password")
            if st.button("登入"):
                if input_code == SYSTEM_CONFIG["team_password"]:
                    st.session_state["team_logged_in"] = True
                    st.rerun()
                else: st.error("通行碼錯誤")
    
    # 已登入區塊
    if st.session_state["team_logged_in"]:
        # 1. 選擇人員
        st.markdown("### 👤 請選擇您的學號/身份")
        prefixes = sorted(list(set([p["id_prefix"] for p in INSPECTOR_LIST])))
        prefix_labels = [f"{p}開頭" for p in prefixes]
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
        input_date = col_date.date_input("檢查日期", datetime.now())
        
        if len(allowed_roles) > 1: role = col_role.radio("請選擇檢查項目", allowed_roles, horizontal=True)
        else:
            col_role.info(f"📋 您的負責項目：**{allowed_roles[0]}**")
            role = allowed_roles[0]
        
        week_num, start_date = get_school_week(input_date)
        if str(input_date) in load_holidays()["日期"].values: st.warning(f"⚠️ 注意：{input_date} 是假日。")

        # 讀取目前已有的資料 (用來顯示狀態)
        df = load_data()
        today_records = df[df["日期"] == str(input_date)] if not df.empty else pd.DataFrame()

        # --- 介面分流 ---
        if role == "晨間打掃":
            daily_duty_list, duty_status, _ = get_daily_duty(input_date)
            if duty_status == "success":
                st.markdown(f"### 📋 今日 ({input_date}) 晨掃點名")
                st.info("👇 請在 **「已完成打掃」** 欄位打勾。")
                
                # 檢查是否已評分過
                already_graded = not today_records[today_records["評分項目"]=="晨間打掃"].empty
                if already_graded: st.warning("⚠️ 注意：今日已有晨掃評分紀錄。")

                with st.form("morning_form", clear_on_submit=True):
                    # 這裡確認有讀取並顯示「掃地區域」
                    edited_morning_df = st.data_editor(
                        pd.DataFrame(daily_duty_list), 
                        column_config={
                            "已完成打掃": st.column_config.CheckboxColumn("✅ 已完成打掃", default=False),
                            "掃地區域": st.column_config.TextColumn("掃地區域", disabled=True),
                            "學號": st.column_config.TextColumn("學號", disabled=True),
                        }, 
                        disabled=["學號", "姓名", "掃地區域"], 
                        hide_index=True, 
                        use_container_width=True
                    )
                    morning_score = st.number_input("未到扣分 (每人)", min_value=0, step=1, value=1)
                    note = "晨掃未到/未打掃"
                    if st.form_submit_button("送出晨掃評分", use_container_width=True):
                        base_entry = {"日期": input_date, "週次": week_num, "檢查人員": inspector_name, "登錄時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "修正": False}
                        absent_students = edited_morning_df[edited_morning_df["已完成打掃"] == False]
                        if absent_students.empty: st.success("🎉 全員到齊！")
                        else:
                            for _, r in absent_students.iterrows():
                                tid = r["學號"]
                                tloc = r["掃地區域"]
                                entry = {**base_entry, "班級": ROSTER_DICT.get(tid, "待確認"), "評分項目": role, "晨間打掃原始分": morning_score, "備註": f"{note} ({tloc})", "晨掃未到者": f"{tid}".strip()}
                                save_entry(entry)
                            st.success(f"✅ 已登記 {len(absent_students)} 位未到學生！")
                        st.rerun()

            elif duty_status == "no_data_for_date": st.warning(f"⚠️ 找不到 {input_date} 的輪值資料。")
            else: st.error(f"⚠️ 讀取輪值表失敗 ({duty_status})。")

        elif role == "垃圾/回收檢查":
            st.info(f"📅 第 {week_num} 週 (垃圾評分)")
            trash_category = st.radio("請選擇違規項目：", ["一般垃圾", "紙類", "網袋", "其他回收"], horizontal=True)
            st.markdown(f"### 📋 全校違規登記表 ({trash_category})")
            
            # 檢查是否已評分過
            graded_classes = today_records[today_records["評分項目"]=="垃圾/回收檢查"]["班級"].unique()
            if len(graded_classes) > 0: st.caption(f"今日已登記違規班級數：{len(graded_classes)}")

            with st.form("trash_form", clear_on_submit=True):
                trash_data = [{"班級": cls, "無簽名": False, "無分類": False} for cls in all_classes]
                edited_trash_df = st.data_editor(pd.DataFrame(trash_data), column_config={"班級": st.column_config.TextColumn("班級", disabled=True), "無簽名": st.column_config.CheckboxColumn("❌ 無簽名 (扣1分)", default=False), "無分類": st.column_config.CheckboxColumn("❌ 無分類 (扣1分)", default=False)}, hide_index=True, height=400, use_container_width=True)
                if st.form_submit_button("送出垃圾評分", use_container_width=True):
                    base_entry = {"日期": input_date, "週次": week_num, "檢查人員": inspector_name, "登錄時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "修正": False}
                    saved_count = 0
                    for _, row in edited_trash_df.iterrows():
                        violations = []
                        if row["無簽名"]: violations.append("無簽名")
                        if row["無分類"]: violations.append("無分類")
                        if violations:
                            entry = {**base_entry, "班級": row["班級"], "評分項目": role, "垃圾原始分": len(violations), "備註": f"{trash_category}-{'、'.join(violations)}", "違規細項": trash_category}
                            save_entry(entry); saved_count += 1
                    if saved_count > 0: st.success(f"✅ 已登記 {saved_count} 班違規！")
                    else: st.info("👍 無違規。")
                    st.rerun()

        else:
            st.markdown("### 🏫 選擇班級")
            selected_class = None
            if assigned_classes: 
                selected_class = st.radio("請點選班級", assigned_classes, key="sel_class_assigned")
            else:
                s_grade = st.radio("步驟 1：選擇年級", grades, horizontal=True, key="sel_grade")
                selected_class = st.radio("步驟 2：選擇班級", [c["name"] for c in structured_classes if c["grade"] == s_grade], horizontal=True, key="sel_class_all")
            
            # 狀態顯示
            if selected_class:
                is_done = False
                if not today_records.empty:
                    check_df = today_records[(today_records["班級"]==selected_class) & (today_records["評分項目"]==role)]
                    if not check_df.empty: is_done = True
                
                if is_done: st.success(f"✅ {selected_class} 今日已完成 {role} 評分！")
                else: st.info(f"📍 準備評分：**{selected_class}** (尚未評分)")

            # 表單區
            with st.form("scoring_form", clear_on_submit=True):
                in_score = 0; out_score = 0; trash_score = 0; morning_score = 0; phone_count = 0; note = ""
                is_perfect = False
                
                if role == "內掃檢查":
                    check_status = st.radio("檢查結果", ["❌ 發現違規", "✨ 很乾淨 (不扣分)"], horizontal=True)
                    if check_status == "❌ 發現違規":
                        st.subheader("違規事項")
                        in_score = st.number_input("🧹 內掃扣分", min_value=0, step=1)
                        note = st.text_input("違規說明", placeholder="例：黑板未擦")
                        phone_count = st.number_input("📱 玩手機人數", min_value=0, step=1)
                    else: is_perfect = True; note = "【優良】環境整潔"
                elif role == "外掃檢查":
                    check_status = st.radio("檢查結果", ["❌ 發現違規", "✨ 很乾淨 (不扣分)"], horizontal=True)
                    if check_status == "❌ 發現違規":
                        st.subheader("違規事項")
                        out_score = st.number_input("🍂 外掃扣分", min_value=0, step=1)
                        note = st.text_input("違規說明", placeholder="例：走廊有垃圾")
                        phone_count = st.number_input("📱 玩手機人數", min_value=0, step=1)
                    else: is_perfect = True; note = "【優良】環境整潔"

                st.write("")
                is_correction = st.checkbox("🚩 這是一筆修正資料 (覆蓋舊紀錄)")
                uploaded_files = st.file_uploader("📸 上傳照片", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
                
                submitted = st.form_submit_button("送出評分", use_container_width=True)

                if submitted:
                    img_path_str = ""
                    if uploaded_files:
                        saved_paths = []
                        timestamp = datetime.now().strftime("%H%M%S")
                        for i, u_file in enumerate(uploaded_files):
                            filename = f"{input_date}_batch_{timestamp}_{i+1}.{u_file.name.split('.')[-1]}"
                            full_path = os.path.join(IMG_DIR, filename)
                            with open(full_path, "wb") as f: f.write(u_file.getbuffer())
                            saved_paths.append(full_path)
                        img_path_str = ";".join(saved_paths)

                    base_entry = {
                        "日期": input_date, "週次": week_num, "檢查人員": inspector_name,
                        "登錄時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "修正": is_correction
                    }

                    final_note = f"【修正】 {note}" if is_correction and "【修正】" not in note else note
                    entry = {**base_entry, "班級": selected_class, "評分項目": role, "內掃原始分": in_score, "外掃原始分": out_score,
                             "垃圾原始分": trash_score, "晨間打掃原始分": morning_score, "手機人數": phone_count,
                             "備註": final_note, "照片路徑": img_path_str}
                    save_entry(entry)
                    st.toast(f"✅ 已儲存：{selected_class} - {role}", icon="🎉")
                    st.rerun()

    else: st.info("👈 請在左側輸入通行碼以開始評分")

elif app_mode == "我是班上衛生股長":
    st.title("🔎 班級成績查詢與申訴")
    df = load_data()
    if not df.empty:
        s_grade = st.radio("步驟 1：選擇年級", grades, horizontal=True)
        search_class = st.radio("步驟 2：選擇班級", [c["name"] for c in structured_classes if c["grade"] == s_grade], horizontal=True)
        class_df = df[df["班級"] == search_class].copy()
        if not class_df.empty:
            class_df = class_df.sort_values(by="登錄時間", ascending=False).reset_index()
            st.subheader(f"📅 {search_class} 近期紀錄")
            for i, row in class_df.iterrows():
                total_raw = sum([row[c] for c in ["內掃原始分", "外掃原始分", "垃圾原始分", "晨間打掃原始分", "手機人數", "垃圾內掃原始分", "垃圾外掃原始分"] if c in row])
                title_prefix = "🔴 [修正單] " if row["修正"] else ""
                is_praise = "【優良】" in str(row["備註"])
                if total_raw > 0 or is_praise:
                    with st.expander(f"{title_prefix}[第{row['週次']}週] {row['日期']} - {row['評分項目']}"):
                        st.write(f"**說明：** {row['備註']}")
                        if is_praise: st.success("✨ 表現優良！")
                        else:
                            msg = []
                            if row["內掃原始分"] > 0: msg.append(f"內掃扣 {row['內掃原始分']}")
                            if row["外掃原始分"] > 0: msg.append(f"外掃扣 {row['外掃原始分']}")
                            if row["晨間打掃原始分"] > 0: msg.append(f"晨掃扣 {row['晨間打掃原始分']}")
                            if row["手機人數"] > 0: msg.append(f"手機 {row['手機人數']}人")
                            if row["垃圾原始分"] > 0: msg.append(f"垃圾扣 {row['垃圾原始分']}")
                            if msg: st.error(" | ".join(msg))
                        st.caption(f"檢查人員：{row['檢查人員']} | 時間：{row['登錄時間']}")
                        if not is_praise:
                            if is_appeal_expired(row["日期"]): st.button("🚫 已超過申訴期限 (3工作天)", key=f"xp_{row['index']}", disabled=True)
                            else:
                                if st.button("📣 我要申訴", key=f"ap_{row['index']}"): st.session_state[f"sa_{row['index']}"] = True
                                if st.session_state.get(f"sa_{row['index']}", False):
                                    with st.form(key=f"af_{row['index']}"):
                                        reason = st.text_area("理由"); imgs = st.file_uploader("佐證", type=['jpg','png'], accept_multiple_files=True)
                                        if st.form_submit_button("送出"):
                                            paths = []
                                            if imgs:
                                                ts = datetime.now().strftime("%H%M%S")
                                                for k, f in enumerate(imgs):
                                                    p = os.path.join(IMG_DIR, f"Ap_{row['index']}_{ts}_{k}.jpg")
                                                    with open(p, "wb") as w: w.write(f.getbuffer())
                                                    paths.append(p)
                                            save_appeal({"日期": str(datetime.now().date()), "班級": search_class, "原始紀錄ID": row['index'], "申訴理由": reason, "申請時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "狀態": "待處理", "佐證照片": ";".join(paths)})
                                            st.success("已送出"); st.session_state[f"sa_{row['index']}"] = False; st.rerun()
                        if str(row["照片路徑"]) not in ["nan", ""]:
                            cols = st.columns(3)
                            for k, p in enumerate(str(row["照片路徑"]).split(";")):
                                if os.path.exists(p): cols[k%3].image(p, width=150)
        else: st.success("🎉 目前沒有違規紀錄")
    else: st.info("尚無資料")

elif app_mode == "衛生組後台":
    st.title("📊 衛生組長管理後台")
    if st.text_input("管理密碼", type="password") == SYSTEM_CONFIG["admin_password"]:
        df = load_data()
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 成績", "📢 申訴", "📧 通知", "🛠️ 資料", "⚙️ 設定"])
        with tab1:
            if not df.empty:
                wks = sorted(df["週次"].unique())
                sw = st.multiselect("週次", wks, default=[wks[-1]])
                if sw:
                    wdf = df[df["週次"].isin(sw)].copy()
                    num_cols = ["內掃原始分", "外掃原始分", "垃圾原始分", "垃圾內掃原始分", "垃圾外掃原始分", "晨間打掃原始分", "手機人數"]
                    for c in num_cols: 
                        if c in wdf.columns:
                            wdf[c] = pd.to_numeric(wdf[c], errors='coerce').fillna(0).astype(int)

                    dg = wdf.groupby(["日期", "班級"]).agg({
                        "內掃原始分": "sum", "外掃原始分": "sum", "垃圾原始分": "sum", "垃圾內掃原始分": "sum", "垃圾外掃原始分": "sum",
                        "晨間打掃原始分": "sum", "手機人數": "sum",
                        "備註": lambda x: " | ".join([str(s) for s in x if str(s) not in ["", "nan"]]),
                        "檢查人員": lambda x: ", ".join(set([str(s) for s in x if str(s) not in ["", "nan"]]))
                    }).reset_index()
                    
                    dg["內掃結算"] = dg["內掃原始分"].apply(lambda x: min(x, 2))
                    dg["外掃結算"] = dg["外掃原始分"].apply(lambda x: min(x, 2))
                    dg["垃圾結算"] = (dg["垃圾原始分"] + dg["垃圾內掃原始分"] + dg["垃圾外掃原始分"]).apply(lambda x: min(x, 2))
                    dg["總扣分"] = dg["內掃結算"] + dg["外掃結算"] + dg["垃圾結算"] + dg["晨間打掃原始分"] + dg["手機人數"]
                    
                    rep = pd.merge(pd.DataFrame(all_classes, columns=["班級"]), dg.groupby("班級")["總扣分"].sum().reset_index(), on="班級", how="left").fillna(0)
                    rep["總成績"] = 90 - rep["總扣分"]
                    rep = rep.sort_values(by="總成績", ascending=False)
                    
                    st.dataframe(rep.style.format("{:.0f}", subset=["總扣分", "總成績"]).background_gradient(subset=["總成績"], cmap="RdYlGn", vmin=60, vmax=90))
            else: st.warning("無資料")
            
        with tab2:
            adf = load_appeals()
            pdf = adf[adf["狀態"] == "待處理"].copy()
            if not pdf.empty:
                for i, r in pdf.iterrows():
                    with st.expander(f"{r['班級']} - {r['申訴理由']}"):
                        c1, c2 = st.columns(2)
                        if c1.button("✅ 核准", key=f"ok_{i}"): delete_entry([r['原始紀錄ID']]); update_appeal_status(adf[adf['申請時間']==r['申請時間']].index[0], "已核准"); st.rerun()
                        if c2.button("❌ 駁回", key=f"no_{i}"): update_appeal_status(adf[adf['申請時間']==r['申請時間']].index[0], "已駁回"); st.rerun()
            else: st.info("無待處理案件")
            
        with tab3:
            st.write("### 📧 寄送通知")
            ed = load_teacher_emails()
            md = st.date_input("日期", datetime.now())
            tdf = df[pd.to_datetime(df["日期"]).dt.date == md]
            if not tdf.empty and ed:
                pl = []
                for c in tdf["班級"].unique():
                    if c in ed:
                        sc = tdf[tdf["班級"]==c][["內掃原始分","外掃原始分","垃圾原始分","晨間打掃原始分","手機人數"]].sum().sum()
                        if sc > 0: pl.append({"班級": c, "導師": ed[c]["name"], "Email": ed[c]["email"], "總扣分": sc})
                st.dataframe(pd.DataFrame(pl))
                if st.button("🚀 寄出"):
                    for p in pl: send_email(p["Email"], f"違規通知 {md} {p['班級']}", f"導師您好，貴班今日扣分: {p['總扣分']}，請協助督導。")
                    st.success("完成")
            else: st.info("無資料或無名單")

        with tab4:
            st.write("### 🛠️ 資料管理")
            
            st.write("#### 🗑️ 單筆刪除")
            if not df.empty:
                df_display = df.sort_values(by="登錄時間", ascending=False).reset_index()
                options = {row['index']: f"[{'修正單' if row['修正'] else '一般'}] {row['日期']} {row['班級']} - {row['評分項目']} | 備註: {row['備註']}" for i, row in df_display.iterrows()}
                selected_indices = st.multiselect("選擇要刪除的紀錄：", options=options.keys(), format_func=lambda x: options[x])
                if st.button("🗑️ 確認永久刪除"):
                    delete_entry(selected_indices)
                    st.success("刪除成功！")
                    st.rerun()
            else: st.info("無資料")
            
            st.write("---")
            st.write("#### 🗑️ 區間刪除")
            c1, c2 = st.columns(2)
            d1, d2 = c1.date_input("起", datetime.now()-timedelta(7)), c2.date_input("迄", datetime.now())
            if st.button("🗑️ 刪除區間資料"):
                count = delete_batch(d1, d2)
                st.success(f"刪除 {count} 筆")
                st.rerun()
            
        with tab5:
            st.write("### ⚙️ 系統設定")
            
            st.write("#### 🔐 密碼管理")
            c1, c2 = st.columns(2)
            n_admin = c1.text_input("新管理密碼", value=SYSTEM_CONFIG.get("admin_password", ""), type="password")
            n_team = c2.text_input("新糾察密碼", value=SYSTEM_CONFIG.get("team_password", ""), type="password")
            
            st.write("#### 📧 郵件設定 (Gmail)")
            c3, c4 = st.columns(2)
            n_mail = c3.text_input("Gmail 信箱", value=SYSTEM_CONFIG.get("smtp_email", ""))
            n_pwd = c4.text_input("應用程式密碼", value=SYSTEM_CONFIG.get("smtp_password", ""), type="password")
            
            if st.button("💾 儲存設定"):
                SYSTEM_CONFIG.update({
                    "admin_password": n_admin, 
                    "team_password": n_team,
                    "smtp_email": n_mail,
                    "smtp_password": n_pwd
                })
                save_config(SYSTEM_CONFIG)
                st.success("設定已更新！")
            
            st.divider()
            st.write("#### 📂 檔案上傳")
            
            u1 = st.file_uploader("上傳全校名單", key="u1")
            if u1: 
                with open(ROSTER_FILE, "wb") as f: f.write(u1.getbuffer())
                st.success("全校名單更新成功！"); st.rerun()
                
            u2 = st.file_uploader("上傳導師名單", key="u2")
            if u2:
                with open(TEACHER_MAIL_FILE, "wb") as f: f.write(u2.getbuffer())
                st.success("導師名單更新成功！"); st.rerun()
                
            u3 = st.file_uploader("上傳糾察名單", key="u3")
            if u3:
                with open(INSPECTOR_DUTY_FILE, "wb") as f: f.write(u3.getbuffer())
                st.success("糾察名單更新成功！"); st.rerun()
                
            u4 = st.file_uploader("上傳輪值表", key="u4")
            if u4:
                with open(DUTY_FILE, "wb") as f: f.write(u4.getbuffer())
                st.success("輪值表更新成功！"); st.rerun()
                
    else: st.error("密碼錯誤")