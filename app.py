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

# --- A. 晨間打掃名單 ---
MORNING_TEAM_RAW = """
211035 晨掃01 黎宜臻
211015 晨掃02 石依玄
211022 晨掃03 林亞璇
211037 晨掃04 簡巧玲
211042 晨掃05 林均則
211043 晨掃06 高捷鈞
211065 晨掃07 陳敏宜
211072 晨掃08 劉宥君
211078 晨掃09 吳振誠
211080 晨掃10 邱炘唐
211082 晨掃11 連健仰
211087 晨掃12 蘇晉翰
212012 晨掃13 李卉芯
212015 晨掃14 周亞昕
212030 晨掃15 黃以馨
212032 晨掃16 楊尹歆
213006 晨掃17 沈明德
213007 晨掃18 卓品宏
213018 晨掃19 王筠雁
213025 晨掃20 許馨鈺
214003 晨掃21 黃俊斌
214022 晨掃22 黃心彤
214027 晨掃23 廖于榛
214030 晨掃24 蔡育甄
214039 晨掃25 陳聖勳
214056 晨掃26 陳湘穎
214061 晨掃27 黃珮綺
214066 晨掃28 謝沅容
215008 晨掃29 李家綺
215009 晨掃30 林雨彤
215029 晨掃31 劉品君
215030 晨掃32 蔡育慈
215046 晨掃33 李子芸
215055 晨掃34 陳玉真
215038 晨掃35 陳瑋泓
215068 晨掃36 盧姿穎
311006 晨掃37 莊家宇
311009 晨掃38 馮煥庭
311023 晨掃39 張逸恩
311037 晨掃40 蕭竹恩
311045 晨掃41 許晉愷
311048 晨掃42 黃柏維
311070 晨掃43 黃卉安
311077 晨掃44 戴培育
311082 晨掃45 林立權
311083 晨掃46 柯竣譯
311086 晨掃47 陳品諺
311120 晨掃48 王墿傑
312002 晨掃49 吳富凱
312006 晨掃50 高旻
312023 晨掃51 陳芷萱
312024 晨掃52 陳姸安
313012 晨掃53 楊子衡
313016 晨掃54 王綵婕
313023 晨掃55 邱妍妍
313024 晨掃56 邱筠娟
314012 晨掃57 李沛澄
314017 晨掃58 姚希璇
314027 晨掃59 黃之妘
314032 晨掃60 廖依淇
314050 晨掃61 周家誼
314061 晨掃62 陳家羽
314067 晨掃63 黃美玉
314077 晨掃64 簡恩語
315002 晨掃65 許丞皓
315003 晨掃66 詹庭碩
315011 晨掃67 林芊邑
315014 晨掃68 邱羽君
315040 晨掃69 吉芸誼
315041 晨掃70 曲苡廷
315042 晨掃71 江玠蓉
315048 晨掃72 洪玟汝
411021 晨掃73 林依潔
411023 晨掃74 林雅萱
411029 晨掃75 許家綺
411035 晨掃76 楊雲茜
411064 晨掃77 楊采翎
411045 晨掃78 彭莛浥
411055 晨掃79 施慕榕
411068 晨掃80 鄭宇婷
411073 晨掃81 吳宥翔
411079 晨掃82 黃聖鈞
411086 晨掃83 王宥云
411099 晨掃84 彭俐璇
412009 晨掃85 陳靖寧
412011 晨掃86 戴登秝
412032 晨掃87 黃若椏
412035 晨掃88 龍以軒
413008 晨掃89 潘柏元
413022 晨掃90 莊捷伊
413026 晨掃91 曾子瑄
413028 晨掃92 温華茜
414005 晨掃93 王可煖
414006 晨掃94 王苡芹
414032 晨掃95 廖翊婷
414039 晨掃96 魏彩芊
414042 晨掃97 金冠政
414050 晨掃98 林晏愉
414065 晨掃99 曾雁婷
414075 晨掃100 盧姵璇
415031 晨掃101 黃恩希
415025 晨掃102 陳峟妘
415032 晨掃103 楊睿青
415033 晨掃104 鄭羽軒
415050 晨掃105 林采駽
415052 晨掃106 徐曼綺
415061 晨掃107 陳乙萱
415066 晨掃108 曾逸馨
"""

def parse_morning_team(raw_text):
    team_list = []
    for line in raw_text.strip().split('\n'):
        parts = line.split()
        if len(parts) >= 3:
            team_list.append({
                "id": parts[0],
                "code": parts[1],
                "name": parts[2],
                "label": f"{parts[0]} - {parts[2]}" 
            })
    return team_list

MORNING_TEAM_LIST = parse_morning_team(MORNING_TEAM_RAW)
MORNING_OPTIONS = [person["label"] for person in MORNING_TEAM_LIST]

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

# --- C. 糾察名單 ---
DEFAULT_HYGIENE = ["311019 衛糾01 胡林琇涵"]
DEFAULT_ENV = ["312013 一般01 李明錚"]

def load_inspectors():
    if os.path.exists(INSPECTORS_FILE):
        with open(INSPECTORS_FILE, "r", encoding='utf-8') as f:
            return json.load(f)
    else:
        default_data = {"hygiene": DEFAULT_HYGIENE, "env": DEFAULT_ENV}
        return default_data

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

# ==========================================
# 介面開始
# ==========================================
st.sidebar.title("🏫 功能選單")
app_mode = st.sidebar.radio("請選擇模式", ["我是糾察隊 (評分)", "我是班上衛生股長", "衛生組後台"])

inspectors_data = load_inspectors()
hygiene_team = inspectors_data["hygiene"]
env_team = inspectors_data["env"]

# ------------------------------------------
# 模式一：糾察隊評分 (v15.0 晨掃批次功能)
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
        
        # 變數初始化
        selected_class = None
        students_selected = [] # v15.0 改用 list
        
        if role == "晨間打掃":
            st.info("ℹ️ 晨間打掃檢查權限：衛生組長")
            inspector_name = "衛生組長"
            
            # --- 晨掃搜尋 (改為多選) ---
            st.markdown("### 🔍 批次登記未打掃人員")
            if ROSTER_DICT:
                students_selected = st.multiselect(
                    "輸入學號或姓名搜尋 (可一次選擇多位)", 
                    options=MORNING_OPTIONS,
                    placeholder="請輸入學號或姓名搜尋..."
                )
                
                # 即時預覽選擇結果
                if students_selected:
                    st.caption("即將新增以下紀錄：")
                    preview_data = []
                    for s in students_selected:
                        sid = s.split(" - ")[0]
                        sclass = ROSTER_DICT.get(sid, "⚠️ 查無班級")
                        preview_data.append({"學生": s, "班級": sclass})
                    st.dataframe(pd.DataFrame(preview_data), hide_index=True)
            else:
                st.error("⚠️ 無法讀取全校名單，請先至後台設定。")
                
            col1, _ = st.columns(2)
            input_date = col1.date_input("檢查日期", datetime.now())

        else:
            if role == "垃圾/回收檢查":
                inspector_name = st.selectbox("檢查人員姓名", env_team)
            else:
                inspector_name = st.selectbox("檢查人員姓名", hygiene_team)
                
            col1, col2 = st.columns(2)
            input_date = col1.date_input("檢查日期", datetime.now())
            selected_class = col2.selectbox("被登記班級", all_classes)
        
        week_num, start_date = get_school_week(input_date)
        
        holidays_df = load_holidays()
        is_holiday = str(input_date) in holidays_df["日期"].values
        if is_holiday:
            st.warning(f"⚠️ 注意：{input_date} 是假日，但您仍可評分。")
        
        # 顯示資訊 (晨掃模式不顯示單一班級)
        if role != "晨間打掃" and selected_class:
            st.info(f"📅 日期：{input_date} (第 {week_num} 週) | 人員：{inspector_name}")
        elif role == "晨間打掃":
            st.info(f"📅 日期：{input_date} (第 {week_num} 週) | 模式：批次登記")

        with st.form("scoring_form"):
            st.subheader("違規事項登錄")
            in_score = 0; out_score = 0; trash_score = 0; morning_score = 0; phone_count = 0; note = ""
            
            if role == "內掃檢查":
                in_score = st.number_input("🧹 內掃扣分 (原始)", min_value=0, step=1)
                note = st.text_input("違規說明", placeholder="例如：黑板未擦")
                phone_count = st.number_input("📱 玩手機人數", min_value=0, step=1)
            elif role == "外掃檢查":
                out_score = st.number_input("🍂 外掃扣分 (原始)", min_value=0, step=1)
                note = st.text_input("違規說明", placeholder="例如：走廊有垃圾")
                phone_count = st.number_input("📱 玩手機人數", min_value=0, step=1)
            elif role == "垃圾/回收檢查":
                st.markdown("每項錯誤扣 1 分")
                c1, c2, c3, c4 = st.columns(4)
                t1 = c1.number_input("一般垃圾", min_value=0)
                t2 = c2.number_input("紙類", min_value=0)
                t3 = c3.number_input("紙容器", min_value=0)
                t4 = c4.number_input("其他", min_value=0)
                trash_score = t1 + t2 + t3 + t4
                if trash_score > 0:
                    note = f"一般:{t1}, 紙類:{t2}, 容器:{t3}, 其他:{t4}"
            elif role == "晨間打掃":
                st.markdown(f"🌅 **晨間打掃檢查 (統一扣分)**")
                morning_score = st.number_input("每位學生扣分分數", min_value=0, step=1, value=1)
                note = "未進行打掃"
                st.text_input("違規說明", value=note, disabled=True)

            st.write("")
            is_correction = st.checkbox("🚩 這是一筆修正資料 (勾選後，系統將自動覆蓋今日同項目的舊紀錄)")

            uploaded_files = st.file_uploader("📸 上傳違規照片 (可多選，將套用於本次所有紀錄)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
            
            submitted = st.form_submit_button("送出評分", use_container_width=True)

            if submitted:
                # 圖片處理 (共用)
                saved_paths = []
                if uploaded_files:
                    timestamp = datetime.now().strftime("%H%M%S")
                    for i, u_file in enumerate(uploaded_files):
                        file_ext = u_file.name.split('.')[-1]
                        # 檔名使用 timestamp 避免重複
                        filename = f"{input_date}_batch_{timestamp}_{i+1}.{file_ext}"
                        full_path = os.path.join(IMG_DIR, filename)
                        with open(full_path, "wb") as f:
                            f.write(u_file.getbuffer())
                        saved_paths.append(full_path)
                img_path_str = ";".join(saved_paths)

                # --- 分流處理 ---
                if role == "晨間打掃":
                    if not students_selected:
                        st.error("請至少選擇一位學生！")
                    else:
                        success_count = 0
                        for s_str in students_selected:
                            # 解析資料
                            target_id = s_str.split(" - ")[0]
                            target_name = s_str.split(" - ")[1]
                            target_class = ROSTER_DICT.get(target_id, "待確認班級") # 自動抓班級

                            # 備註處理
                            final_note = f"{note} - {target_name}"
                            if is_correction: final_note = f"【修正】 {final_note}"

                            entry = {
                                "日期": input_date, "週次": week_num, "班級": target_class,
                                "評分項目": role, "檢查人員": inspector_name,
                                "內掃原始分": 0, "外掃原始分": 0, "垃圾原始分": 0, "晨間打掃原始分": morning_score,
                                "手機人數": 0,
                                "備註": final_note, "照片路徑": img_path_str,
                                "登錄時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "修正": is_correction,
                                "晨掃未到者": f"{target_id} {target_name}"
                            }
                            save_entry(entry)
                            success_count += 1
                        st.success(f"✅ 成功批次新增 {success_count} 筆紀錄！")

                else:
                    # 一般評分邏輯 (單筆)
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
    st.title("🔎 班級成績查詢")
    df = load_data()
    if not df.empty:
        search_class = st.selectbox("請選擇您的班級", all_classes)
        class_df = df[df["班級"] == search_class].copy()
        
        if not class_df.empty:
            class_df = class_df.sort_values(by="登錄時間", ascending=False)
            st.subheader(f"📅 {search_class} 近期紀錄")
            
            for index, row in class_df.iterrows():
                total_raw = row["內掃原始分"] + row["外掃原始分"] + row["垃圾原始分"] + row["晨間打掃原始分"] + row["手機人數"]
                title_prefix = "🔴 [修正單] " if row["修正"] else ""
                
                if total_raw >= 0:
                    with st.expander(f"{title_prefix}[第{row['週次']}週] {row['日期']} - {row['評分項目']} (扣分詳情)"):
                        st.write(f"**違規：** {row['備註']}")
                        msg = []
                        if row["內掃原始分"] > 0: msg.append(f"內掃扣 {row['內掃原始分']}")
                        if row["外掃原始分"] > 0: msg.append(f"外掃扣 {row['外掃原始分']}")
                        if row["垃圾原始分"] > 0: msg.append(f"垃圾扣 {row['垃圾原始分']}")
                        if row["晨間打掃原始分"] > 0: msg.append(f"晨掃扣 {row['晨間打掃原始分']}")
                        if row["手機人數"] > 0: msg.append(f"手機 {row['手機人數']}人")
                        if msg: st.error(" | ".join(msg))
                        else: st.success("無扣分")
                        
                        path_str = str(row["照片路徑"])
                        if path_str and path_str != "nan":
                            paths = path_str.split(";")
                            st.write("違規佐證：")
                            cols = st.columns(3)
                            for i, p in enumerate(paths):
                                if os.path.exists(p): cols[i%3].image(p, width=150)
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
        
        tab1, tab2, tab3 = st.tabs(["📊 成績報表", "🛠️ 資料管理", "⚙️ 系統設定"])
        
        # --- Tab 1: 報表區 ---
        with tab1:
            if not df.empty:
                available_weeks = sorted(df["週次"].unique())
                if not available_weeks:
                    st.warning("無資料")
                else:
                    selected_week = st.selectbox("選擇結算週次", available_weeks, index=len(available_weeks)-1)
                    week_df = df[df["週次"] == selected_week]
                    
                    # 智慧清洗
                    week_df_sorted = week_df.sort_values(by="登錄時間", ascending=False)
                    cleaned_rows = []
                    # 晨掃必須包含 "晨掃未到者" 區分，否則同班同天會被視為重複而被清洗掉
                    # 技巧：將 "晨掃未到者" 加入分組鍵值，這樣不同學生的紀錄就會被視為不同筆
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
                        st.warning("本週無有效數據")
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
                        
                        daily_group["當日總扣分"] = (daily_group["內掃結算"] + daily_group["外掃結算"] + 
                                                   daily_group["垃圾結算"] + daily_group["晨間打掃結算"] + 
                                                   daily_group["手機扣分"])
                        
                        class_score_df = pd.DataFrame(all_classes, columns=["班級"])
                        final_deductions = daily_group.groupby("班級")["當日總扣分"].sum().reset_index()
                        
                        daily_pivot = daily_group.pivot(index="班級", columns="日期", values="當日總扣分").reset_index()
                        daily_pivot = daily_pivot.fillna(0)
                        
                        report = pd.merge(class_score_df, final_deductions, on="班級", how="left").fillna(0)
                        report = pd.merge(report, daily_pivot, on="班級", how="left").fillna(0)
                        report["本週成績"] = 90 - report["當日總扣分"]
                        report = report.sort_values(by="本週成績", ascending=False)
                        
                        date_cols = sorted([col for col in report.columns if col not in ["班級", "當日總扣分", "本週成績"]])
                        final_cols = ["班級"] + date_cols + ["當日總扣分", "本週成績"]
                        report = report[final_cols]
                        
                        # 文字矩陣
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

                        # 晨掃報表
                        morning_absent_df = cleaned_df[cleaned_df["評分項目"] == "晨間打掃"][["日期", "班級", "晨掃未到者", "晨間打掃原始分", "備註"]]
                        morning_absent_df = morning_absent_df.sort_values(by="日期")

                        import io
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            report.to_excel(writer, index=False, sheet_name='總成績')
                            if not reason_pivot.empty:
                                reason_pivot.to_excel(writer, index=False, sheet_name='違規原因一覽表')
                            morning_absent_df.to_excel(writer, index=False, sheet_name='🌅晨掃未到明細')
                            daily_group.to_excel(writer, index=False, sheet_name='詳細流水帳(清洗後)')
                            week_df.to_excel(writer, index=False, sheet_name='原始輸入紀錄')
                        
                        st.download_button(
                            label="📥 下載 Excel 結算報表 (含原因矩陣)",
                            data=output.getvalue(),
                            file_name=f"第{selected_week}週_衛生糾察總表.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                        
                        st.write("##### 🏆 班級成績總表")
                        numeric_cols = report.select_dtypes(include=['number']).columns
                        st.dataframe(
                            report.style.format("{:.0f}", subset=numeric_cols)
                            .background_gradient(subset=["本週成績"], cmap="RdYlGn", vmin=60, vmax=90)
                        )
                        
                        if not reason_pivot.empty:
                            with st.expander("查看違規原因矩陣 (預覽)"):
                                st.dataframe(reason_pivot)

        # --- Tab 2: 資料管理 ---
        with tab2:
            st.write("若需手動刪除資料，請在此操作。")
            if not df.empty:
                df_display = df.sort_values(by="登錄時間", ascending=False).reset_index()
                options = {row['index']: f"[{'修正單' if row['修正'] else '一般'}] {row['日期']} {row['班級']} - {row['評分項目']} | 備註: {row['備註']}" for i, row in df_display.iterrows()}
                selected_indices = st.multiselect("選擇要永久刪除的紀錄：", options=options.keys(), format_func=lambda x: options[x])
                if st.button("🗑️ 確認永久刪除"):
                    if selected_indices:
                        delete_entry(selected_indices)
                        st.success("刪除成功！")
                        st.rerun()
            else:
                st.info("無資料")

        # --- Tab 3: 系統設定區 ---
        with tab3:
            st.header("⚙️ 系統設定")
            
            # 1. 密碼管理
            st.subheader("1. 🔐 密碼管理")
            c1, c2 = st.columns(2)
            new_admin_pwd = c1.text_input("管理員後台密碼", value=SYSTEM_CONFIG["admin_password"], type="password")
            new_team_pwd = c2.text_input("糾察隊通行碼", value=SYSTEM_CONFIG["team_password"])
            if st.button("💾 更新密碼設定"):
                SYSTEM_CONFIG["admin_password"] = new_admin_pwd
                SYSTEM_CONFIG["team_password"] = new_team_pwd
                save_config(SYSTEM_CONFIG)
                st.success("密碼已更新！請牢記。")

            st.divider()

            # 2. 名單上傳與檢測
            st.subheader("2. 📂 全校名單設定")
            if ROSTER_DEBUG['status'] == 'success':
                st.success(f"✅ 名單讀取成功！共讀取到 {len(ROSTER_DICT)} 筆學生資料。")
            else:
                st.error(f"❌ 名單讀取失敗。狀態：{ROSTER_DEBUG['status']}")
            
            uploaded_roster = st.file_uploader("上傳新的全校名單 (csv)", type=["csv"])
            if uploaded_roster:
                with open(ROSTER_FILE, "wb") as f:
                    f.write(uploaded_roster.getbuffer())
                st.success("上傳成功！請按下方按鈕重整。")
                if st.button("🔄 重新載入系統"):
                    st.rerun()
            
            st.divider()
            
            # 3. 其他設定
            st.subheader("3. 學期與假日")
            current_start = datetime.strptime(SYSTEM_CONFIG["semester_start"], "%Y-%m-%d").date()
            new_date = st.date_input("開學日", current_start)
            if st.button("更新開學日"):
                SYSTEM_CONFIG["semester_start"] = str(new_date)
                save_config(SYSTEM_CONFIG)
                st.success("已更新")

    else:
        st.error("密碼錯誤")