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
INSPECTORS_FILE = "inspectors.json" 
ROSTER_FILE = "全校名單.csv" 
DUTY_FILE = "晨掃輪值.csv" 
APPEALS_FILE = "appeals.csv"

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

# --- A. 全校名單讀取 ---
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

# --- B. 晨掃輪值表讀取 (含診斷功能) ---
def get_daily_duty(target_date, csv_path=DUTY_FILE):
    duty_list = []
    status = "init"
    # 用於診斷的額外資訊
    diagnostic_info = {
        "all_dates_found": [],
        "total_rows": 0,
        "matched_rows": 0
    }
    
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
                    # 嘗試標準化日期
                    df[date_col] = pd.to_datetime(df[date_col], errors='coerce').dt.date
                    # 收集所有出現過的日期 (去除空值)
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
                            "學號": s_id,
                            "姓名": s_name,
                            "掃地區域": s_loc,
                            "已完成打掃": False 
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

# --- C. 糾察名單 ---
DEFAULT_HYGIENE = ["311019 衛糾01 胡林琇涵"]
DEFAULT_ENV = ["312013 一般01 李明錚"]

def load_inspectors():
    if os.path.exists(INSPECTORS_FILE):
        with open(INSPECTORS_FILE, "r", encoding='utf-8') as f:
            return json.load(f)
    else:
        return {"hygiene": DEFAULT_HYGIENE, "env": DEFAULT_ENV}

def save_inspectors(hygiene_list, env_list):
    data = {"hygiene": hygiene_list, "env": env_list}
    with open(INSPECTORS_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

# --- D. 假日與週次 ---
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

# --- E. 班級產生 ---
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

# --- F. 主資料庫 ---
def load_data():
    if os.path.exists(FILE_PATH):
        df = pd.read_csv(FILE_PATH)
        expected_cols = ["日期", "週次", "班級", "評分項目", "檢查人員", "內掃原始分", "外掃原始分", "垃圾原始分", "晨間打掃原始分", "手機人數", "備註", "照片路徑", "登錄時間", "修正", "晨掃未到者"]
        for col in expected_cols:
            if col == "修正":
                if col not in df.columns: df[col] = False
            elif col == "晨掃未到者":
                if col not in df.columns: df[col] = ""
            elif col not in df.columns: 
                df[col] = 0 if "分" in col or "人數" in col else ""
        return df
    else:
        return pd.DataFrame(columns=[
            "日期", "週次", "班級", "評分項目", "檢查人員",
            "內掃原始分", "外掃原始分", "垃圾原始分", "晨間打掃原始分", "手機人數", 
            "備註", "照片路徑", "登錄時間", "修正", "晨掃未到者"
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

# --- G. 申訴資料庫 ---
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

inspectors_data = load_inspectors()
hygiene_team = inspectors_data["hygiene"]
env_team = inspectors_data["env"]

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
        role = st.selectbox("檢查項目", ("內掃檢查", "外掃檢查", "垃圾/回收檢查", "晨間打掃"))
        
        selected_class = None
        edited_morning_df = None
        
        col_date, _ = st.columns(2)
        input_date = col_date.date_input("檢查日期", datetime.now())
        week_num, start_date = get_school_week(input_date)
        
        holidays_df = load_holidays()
        is_holiday = str(input_date) in holidays_df["日期"].values
        if is_holiday:
            st.warning(f"⚠️ 注意：{input_date} 是假日。")

        # --- 模式分流 ---
        if role == "晨間打掃":
            st.info(f"ℹ️ 晨間打掃檢查 (日期: {input_date}) | 權限：衛生組長")
            inspector_name = "衛生組長"
            
            # v19.0: 接收診斷資訊
            daily_duty_list, duty_status, diag_info = get_daily_duty(input_date)
            
            if duty_status == "success":
                st.markdown(f"### 📋 今日 ({input_date}) 晨掃點名表")
                st.info("👇 請在 **「已完成打掃」** 欄位打勾。**未打勾者** 將被視為缺席並扣分。")
                
                duty_df = pd.DataFrame(daily_duty_list)
                
                edited_morning_df = st.data_editor(
                    duty_df,
                    column_config={
                        "已完成打掃": st.column_config.CheckboxColumn(
                            "✅ 已完成打掃",
                            help="有掃地請打勾，沒打勾會被扣分",
                            default=False,
                        )
                    },
                    disabled=["學號", "姓名", "掃地區域"],
                    hide_index=True,
                    use_container_width=True
                )
                
                checked_count = edited_morning_df["已完成打掃"].sum()
                total_count = len(edited_morning_df)
                absent_count = total_count - checked_count
                
                st.caption(f"📊 應到: {total_count} 人 | 實到: {checked_count} 人 | ⚠️ 缺席(將扣分): {absent_count} 人")
                
                if absent_count == total_count:
                    st.warning("⚠️ 注意：目前沒有任何人被打勾，送出後將視為「全員缺席」！")

            elif duty_status == "no_data_for_date":
                st.warning(f"⚠️ 找不到 {input_date} 的輪值資料。")
                # --- v19.0: 智慧提示 ---
                st.markdown("#### 🕵️ 系統診斷建議")
                if diag_info["all_dates_found"]:
                    st.write("系統在檔案中只找到了這些日期：")
                    # 顯示前5個日期
                    st.write(diag_info["all_dates_found"][:10]) 
                    st.info("💡 提示：請檢查 Excel 檔中的高三學生日期，是否被自動變成了明天或後天？")
                else:
                    st.write("檔案中似乎沒有任何有效的日期欄位。")
                    
            else:
                st.error("⚠️ 讀取輪值表失敗，請檢查後台設定。")

        else:
            if role == "垃圾/回收檢查":
                inspector_name = st.selectbox("檢查人員姓名", env_team)
            else:
                inspector_name = st.selectbox("檢查人員姓名", hygiene_team)
                
            selected_class = st.selectbox("被登記班級", all_classes)
            st.info(f"📅 第 {week_num} 週 | 人員：{inspector_name}")

        with st.form("scoring_form"):
            st.subheader("違規事項登錄")
            in_score = 0; out_score = 0; trash_score = 0; morning_score = 0; phone_count = 0; note = ""
            
            if role == "內掃檢查":
                in_score = st.number_input("🧹 內掃扣分", min_value=0, step=1)
                note = st.text_input("違規說明", placeholder="例：黑板未擦")
                phone_count = st.number_input("📱 玩手機人數", min_value=0, step=1)
            elif role == "外掃檢查":
                out_score = st.number_input("🍂 外掃扣分", min_value=0, step=1)
                note = st.text_input("違規說明", placeholder="例：走廊有垃圾")
                phone_count = st.number_input("📱 玩手機人數", min_value=0, step=1)
            elif role == "垃圾/回收檢查":
                st.markdown("每項錯誤扣 1 分")
                c1, c2, c3, c4 = st.columns(4)
                t1 = c1.number_input("一般", min_value=0)
                t2 = c2.number_input("紙類", min_value=0)
                t3 = c3.number_input("紙容器", min_value=0)
                t4 = c4.number_input("其他", min_value=0)
                trash_score = t1 + t2 + t3 + t4
                if trash_score > 0: note = f"一般:{t1}, 紙類:{t2}, 容器:{t3}, 其他:{t4}"
                
            elif role == "晨間打掃":
                st.markdown("**扣分設定：**")
                morning_score = st.number_input("未到扣分 (每人)", min_value=0, step=1, value=1)
                note = "晨掃未到/未打掃"

            st.write("")
            is_correction = st.checkbox("🚩 這是一筆修正資料 (勾選後，系統將覆蓋舊紀錄)")

            uploaded_files = None
            if role != "晨間打掃":
                uploaded_files = st.file_uploader("📸 上傳違規照片 (可多選)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
            
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
                        with open(full_path, "wb") as f:
                            f.write(u_file.getbuffer())
                        saved_paths.append(full_path)
                    img_path_str = ";".join(saved_paths)

                if role == "晨間打掃":
                    if edited_morning_df is None:
                        st.error("無資料可送出")
                    else:
                        absent_students = edited_morning_df[edited_morning_df["已完成打掃"] == False]
                        if absent_students.empty:
                            st.success("🎉 全員到齊！無需扣分。")
                        else:
                            success_count = 0
                            for _, row_data in absent_students.iterrows():
                                target_id = row_data["學號"]
                                target_name = row_data["姓名"]
                                target_loc = row_data["掃地區域"]
                                target_class = ROSTER_DICT.get(target_id, "待確認班級")

                                final_note = f"{note} ({target_loc}) - {target_name}"
                                if is_correction: final_note = f"【修正】 {final_note}"

                                entry = {
                                    "日期": input_date, "週次": week_num, "班級": target_class,
                                    "評分項目": role, "檢查人員": inspector_name,
                                    "內掃原始分": 0, "外掃原始分": 0, "垃圾原始分": 0, "晨間打掃原始分": morning_score,
                                    "手機人數": 0,
                                    "備註": final_note, "照片路徑": "",
                                    "登錄時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "修正": is_correction,
                                    "晨掃未到者": f"{target_id} {target_name}"
                                }
                                save_entry(entry)
                                success_count += 1
                            st.success(f"✅ 已對 {success_count} 位未掃地學生進行扣分登記！")

                else:
                    final_note = note
                    if is_correction and "【修正】" not in note:
                        final_note = f"【修正】 {note}"

                    entry = {
                        "日期": input_date, "週次": week_num, "班級": selected_class,
                        "評分項目": role, "檢查人員": inspector_name,
                        "內掃原始分": in_score, "外掃原始分": out_score,
                        "垃圾原始分": trash_score, "晨間打掃原始分": morning_score,
                        "手機人數": phone_count,
                        "備註": final_note, "照片路徑": img_path_str,
                        "登錄時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "修正": is_correction,
                        "晨掃未到者": ""
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
                total_raw = row["內掃原始分"] + row["外掃原始分"] + row["垃圾原始分"] + row["晨間打掃原始分"] + row["手機人數"]
                title_prefix = "🔴 [修正單] " if row["修正"] else ""
                
                if total_raw >= 0:
                    with st.expander(f"{title_prefix}[第{row['週次']}週] {row['日期']} - {row['評分項目']} (扣分詳情)"):
                        c1, c2 = st.columns([3, 2])
                        with c1:
                            st.write(f"**違規：** {row['備註']}")
                            msg = []
                            if row["內掃原始分"] > 0: msg.append(f"內掃扣 {row['內掃原始分']}")
                            if row["外掃原始分"] > 0: msg.append(f"外掃扣 {row['外掃原始分']}")
                            if row["垃圾原始分"] > 0: msg.append(f"垃圾扣 {row['垃圾原始分']}")
                            if row["晨間打掃原始分"] > 0: msg.append(f"晨掃扣 {row['晨間打掃原始分']}")
                            if row["手機人數"] > 0: msg.append(f"手機 {row['手機人數']}人")
                            if msg: st.error(" | ".join(msg))
                            else: st.success("無扣分")
                            st.caption(f"檢查人員：{row['檢查人員']} | 時間：{row['登錄時間']}")
                            
                            if st.button("📣 我要申訴", key=f"appeal_btn_{record_id}"):
                                st.session_state[f"show_appeal_{record_id}"] = True
                            
                            if st.session_state.get(f"show_appeal_{record_id}", False):
                                with st.form(key=f"appeal_form_{record_id}"):
                                    appeal_reason = st.text_area("請輸入申訴理由：")
                                    appeal_imgs = st.file_uploader("📸 上傳佐證照片 (選填)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
                                    
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
                                        
                        with c2:
                            path_str = str(row["照片路徑"])
                            if path_str and path_str != "nan":
                                paths = path_str.split(";")
                                st.write("違規照片：")
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
                        week_df = df[df["週次"].isin(selected_weeks)]
                        week_df_sorted = week_df.sort_values(by="登錄時間", ascending=False)
                        cleaned_rows = []
                        groups = week_df_sorted.groupby(["日期", "班級", "評分項目", "晨掃未到者"])
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
                                "內掃原始分": "sum", "外掃原始分": "sum", "垃圾原始分": "sum", "晨間打掃原始分": "sum",
                                "手機人數": "sum", 
                                "備註": lambda x: " | ".join([str(s) for s in x if str(s) not in ["", "nan", "None"]]),
                                "檢查人員": lambda x: ", ".join(set([str(s) for s in x if str(s) not in ["", "nan"]]))
                            }).reset_index()
                            
                            daily_group["內掃結算"] = daily_group["內掃原始分"].apply(lambda x: min(x, 2))
                            daily_group["外掃結算"] = daily_group["外掃原始分"].apply(lambda x: min(x, 2))
                            daily_group["垃圾結算"] = daily_group["垃圾原始分"].apply(lambda x: min(x, 2))
                            daily_group["晨間打掃結算"] = daily_group["晨間打掃原始分"]
                            daily_group["手機扣分"] = daily_group["手機人數"] * 1
                            daily_group["當日總扣分"] = (daily_group["內掃結算"] + daily_group["外掃結算"] + daily_group["垃圾結算"] + daily_group["晨間打掃結算"] + daily_group["手機扣分"])
                            
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
                                if row["垃圾原始分"] > 0: reasons.append(f"垃圾({row['垃圾原始分']})")
                                if row["晨間打掃原始分"] > 0: reasons.append(f"晨掃({row['晨間打掃原始分']})")
                                if row["手機人數"] > 0: reasons.append(f"手機({row['手機人數']})")
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

                        if not df.empty and row['原始紀錄ID'] in df.index:
                            original_record = df.loc[row['原始紀錄ID']]
                            st.info(f"原始紀錄：{original_record['評分項目']} | 備註：{original_record['備註']} | 扣分總計：{original_record['內掃原始分']+original_record['外掃原始分']+original_record['垃圾原始分']+original_record['晨間打掃原始分']}")
                        else:
                            st.warning("原始紀錄已無法讀取")
                        
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
            else:
                st.info("無待處理案件。")
            with st.expander("查看歷史紀錄"): st.dataframe(appeals_df)

        # --- Tab 3: 資料管理 ---
        with tab3:
            if not df.empty:
                df_display = df.sort_values(by="登錄時間", ascending=False).reset_index()
                options = {row['index']: f"[{'修正單' if row['修正'] else '一般'}] {row['日期']} {row['班級']} - {row['評分項目']} | 備註: {row['備註']}" for i, row in df_display.iterrows()}
                selected_indices = st.multiselect("選擇要刪除的紀錄：", options=options.keys(), format_func=lambda x: options[x])
                if st.button("🗑️ 確認刪除"):
                    delete_entry(selected_indices)
                    st.success("刪除成功！")
                    st.rerun()
            else:
                st.info("無資料")

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
            st.write("**B. 晨掃輪值表 (csv)**")
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

        # --- Tab 5: 資料診斷 (v19.0 新增) ---
        with tab5:
            st.header("🩺 資料診斷室")
            st.info("這裡可以幫您檢查為什麼某些學生在晨掃名單中找不到。")
            
            st.write("#### 1. 晨掃輪值表診斷")
            if os.path.exists(DUTY_FILE):
                # 再次讀取並顯示詳細資訊
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
                    
                    if diag_info.get('matched_rows', 0) == 0:
                        st.error("❌ 找不到符合此日期的資料！請檢查上方列表，看看日期是否被 Excel 自動加一天了？")
                else:
                    st.warning("無法解析出任何日期，請檢查 CSV 欄位名稱是否包含「日期」。")
            else:
                st.error("找不到晨掃輪值表檔案。")

    else:
        st.error("密碼錯誤")