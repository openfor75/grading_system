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
ROSTER_FILE = "全校名單.csv"  # 請確認您的檔案名稱是這個

if not os.path.exists(IMG_DIR): os.makedirs(IMG_DIR)

# ==========================================
# 1. 資料處理：名單載入與解析
# ==========================================

# --- A. 晨間打掃名單 (直接內建) ---
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
    # 逐行讀取，分割出 學號、代碼、姓名
    for line in raw_text.strip().split('\n'):
        parts = line.split()
        if len(parts) >= 3:
            # 儲存為字典方便後續取用
            team_list.append({
                "id": parts[0],
                "code": parts[1],
                "name": parts[2],
                "label": f"{parts[0]} - {parts[2]}" # 用於選單顯示
            })
    return team_list

MORNING_TEAM_LIST = parse_morning_team(MORNING_TEAM_RAW)
MORNING_OPTIONS = [person["label"] for person in MORNING_TEAM_LIST]

# --- B. 全校名單 (讀取 CSV) ---
@st.cache_data
def load_roster_dict():
    roster_dict = {}
    if os.path.exists(ROSTER_FILE):
        try:
            # 嘗試讀取 CSV，確保學號讀取為字串以免開頭0被吃掉
            df = pd.read_csv(ROSTER_FILE, dtype=str)
            
            # 清理欄位名稱 (移除可能的空白)
            df.columns = df.columns.str.strip()
            
            # 自動尋找「學號」和「班級」欄位
            id_col = next((c for c in df.columns if "學號" in c), None)
            class_col = next((c for c in df.columns if "班級" in c), None)
            
            if id_col and class_col:
                # 建立對照表：學號 -> 班級
                for _, row in df.iterrows():
                    # 確保學號是乾淨的字串
                    s_id = str(row[id_col]).strip()
                    s_class = str(row[class_col]).strip()
                    roster_dict[s_id] = s_class
            else:
                st.error(f"⚠️ 在 `{ROSTER_FILE}` 中找不到「學號」或「班級」欄位，請檢查檔案。")
        except Exception as e:
            st.error(f"⚠️ 讀取全校名單失敗：{e}")
    return roster_dict

ROSTER_DICT = load_roster_dict()

# --- C. 其他預設名單 ---
DEFAULT_HYGIENE = [
    "311019 衛糾01 胡林琇涵", "311005 衛糾02 康克勤", "311076 衛糾03 戴可婕", "311119 衛糾04 羅苡宸",
    "311118 衛糾05 鍾語芯", "312021 衛糾06 許舒婷", "312012 衛糾07 江芸茜", "313017 衛糾08 何詒恩",
    "314020 衛糾09 許依晴", "314004 衛糾10 李睿宸", "314068 衛糾11 黃婉庭", "314076 衛糾12 賴文娟",
    "315008 衛糾13 吳貽禎", "315068 衛糾14 鄭家臻", "411002 衛糾15 李福", "411004 衛糾16 俞含秀",
    "411057 衛糾17 翁于晴", "411063 衛糾18 游清滿", "411081 衛糾19 廖呈睿", "411085 衛糾20 蘇悠翔",
    "412018 衛糾21 范愛瑄", "412019 衛糾22 徐苡涵", "413004 衛糾23 吳柏澄", "413009 衛糾24 盧業鈞",
    "414037 衛糾25 謝薇琳", "414040 衛糾26 嚴羽璇", "414045 衛糾27 李云云", "414046 衛糾28 李詠芯",
    "415026 衛糾29 陳悅禾", "415038 衛糾30 羅翊萱", "415053 衛糾31 徐暄芳", "415039 衛糾32 楊鈞凱",
    "313035 衛糾37 葉夏恩", "311057 衛糾38 宋云馨", "311097 衛糾39 沈千涵", "414015 衛糾40 柯志恩",
    "413016 衛糾41 林子靖", "414079 衛糾42 饒恩瑜"
]

DEFAULT_ENV = [
    "312013 一般01 李明錚", "411018 一般02 周芸如", "412014 一般03 王家家", "315020 一般持板 許瑋玲",
    "414007 其他 江焄柔", "312015 其他持板 林妤姍", "311088 紙類01 劉承恩", "315015 紙類02 范可昕",
    "411064 紙類03 楊采翎", "415002 紙類04 張維恩", "313029 紙類持板 陳靜儀", "314046 換袋01 鄭國佑",
    "411045 換袋02 彭莛浥", "315043 網袋01 吳宜軒", "411095 網袋02 梁芷苓", "414073 網袋03 蔡沐慈",
    "314028 網袋持板 黃心柔", "411029 整潔01 許家綺", "415052 整潔02 徐曼綺", "314041 機動01 林柏融",
    "411089 機動02 江書文"
]

# --- 讀取/儲存 設定檔 ---
def load_config():
    default_config = {"semester_start": "2025-08-25"}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding='utf-8') as f:
            return json.load(f)
    return default_config

def save_config(date_str):
    current = load_config()
    current["semester_start"] = str(date_str)
    with open(CONFIG_FILE, "w", encoding='utf-8') as f:
        json.dump(current, f, ensure_ascii=False)

# --- 讀取/儲存 人員名單 ---
def load_inspectors():
    if os.path.exists(INSPECTORS_FILE):
        with open(INSPECTORS_FILE, "r", encoding='utf-8') as f:
            return json.load(f)
    else:
        default_data = {"hygiene": DEFAULT_HYGIENE, "env": DEFAULT_ENV}
        with open(INSPECTORS_FILE, "w", encoding='utf-8') as f:
            json.dump(default_data, f, ensure_ascii=False)
        return default_data

def save_inspectors(hygiene_list, env_list):
    data = {"hygiene": hygiene_list, "env": env_list}
    with open(INSPECTORS_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

# --- 讀取/儲存 假日 ---
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
    return df

def delete_holiday(date_str):
    df = load_holidays()
    df = df[df["日期"] != date_str]
    df.to_csv(HOLIDAY_FILE, index=False)

# --- 計算週次 ---
def get_school_week(date_obj):
    config = load_config()
    start_date = datetime.strptime(config["semester_start"], "%Y-%m-%d").date()
    if isinstance(date_obj, datetime):
        date_obj = date_obj.date()
    delta = date_obj - start_date
    week_num = (delta.days // 7) + 1
    if week_num < 1: week_num = 0 
    return week_num, start_date

# --- 載入名單與班級 (一般糾察用) ---
inspectors_data = load_inspectors()
hygiene_team = inspectors_data["hygiene"]
env_team = inspectors_data["env"]

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

# --- 資料處理 ---
def load_data():
    if os.path.exists(FILE_PATH):
        df = pd.read_csv(FILE_PATH)
        # 增加「晨掃未到者」欄位
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

# ------------------------------------------
# 模式一：糾察隊評分
# ------------------------------------------
if app_mode == "我是糾察隊 (評分)":
    st.title("📝 衛生糾察評分系統")
    st.markdown("---")
    
    role = st.selectbox("檢查項目", ("內掃檢查", "外掃檢查", "垃圾/回收檢查", "晨間打掃"))
    
    # 初始化變數
    selected_class = None
    target_student_name = ""
    target_student_id = ""
    
    # 根據不同項目顯示不同介面
    if role == "晨間打掃":
        st.info("ℹ️ 晨間打掃檢查權限：衛生組長")
        inspector_name = "衛生組長"
        
        # --- 晨間打掃專用搜尋介面 ---
        st.markdown("### 🔍 搜尋未打掃人員")
        
        # 搜尋學號 (下拉選單，可搜尋)
        student_select = st.selectbox(
            "輸入學號或姓名搜尋 (未完成打掃者)", 
            options=MORNING_OPTIONS,
            index=None,
            placeholder="請輸入學號..."
        )
        
        if student_select:
            # 解析選擇的字串 "211035 - 黎宜臻"
            target_student_id = student_select.split(" - ")[0]
            target_student_name = student_select.split(" - ")[1]
            
            # 自動對應班級
            if target_student_id in ROSTER_DICT:
                selected_class = ROSTER_DICT[target_student_id]
                st.success(f"✅ 已自動鎖定：**{selected_class}** (學號: {target_student_id})")
            else:
                st.error(f"❌ 找不到學號 {target_student_id} 的班級資料，請確認全校名單 csv 是否正確。")
                selected_class = st.selectbox("請手動選擇班級", all_classes) # Fallback
                
        # 顯示日期選擇
        col1, _ = st.columns(2)
        input_date = col1.date_input("檢查日期", datetime.now())

    else:
        # 其他項目的正常介面
        if role == "垃圾/回收檢查":
            inspector_name = st.selectbox("檢查人員姓名", env_team)
        else:
            inspector_name = st.selectbox("檢查人員姓名", hygiene_team)
            
        col1, col2 = st.columns(2)
        input_date = col1.date_input("檢查日期", datetime.now())
        selected_class = col2.selectbox("被登記班級", all_classes)
    
    # 計算週次
    week_num, start_date = get_school_week(input_date)
    
    holidays_df = load_holidays()
    is_holiday = str(input_date) in holidays_df["日期"].values
    if is_holiday:
        reason = holidays_df[holidays_df["日期"] == str(input_date)]["原因"].values[0]
        st.warning(f"⚠️ 注意：{input_date} 是假日 ({reason})，但您仍可評分。")
    
    if selected_class:
        st.info(f"📅 日期：{input_date} (第 {week_num} 週) | 人員：{inspector_name}")

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
                st.markdown(f"🌅 **晨間打掃檢查：{target_student_name} ({target_student_id})**")
                # 強制設定
                morning_score = st.number_input("扣分分數", min_value=0, step=1, value=1) # 預設扣1分?
                note = "未進行打掃"
                st.text_input("違規說明", value=note, disabled=True) # 鎖定唯讀

            st.write("")
            is_correction = st.checkbox("🚩 這是一筆修正資料 (勾選後，系統將自動覆蓋今日同項目的舊紀錄)")

            uploaded_files = st.file_uploader("📸 上傳違規照片 (可多選)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
            
            submitted = st.form_submit_button("送出評分", use_container_width=True)

            if submitted:
                if role == "晨間打掃" and not target_student_id:
                    st.error("請先搜尋並選擇未打掃的學生！")
                    st.stop()

                saved_paths = []
                if uploaded_files:
                    timestamp = datetime.now().strftime("%H%M%S")
                    for i, u_file in enumerate(uploaded_files):
                        file_ext = u_file.name.split('.')[-1]
                        filename = f"{input_date}_{selected_class}_{timestamp}_{i+1}.{file_ext}"
                        full_path = os.path.join(IMG_DIR, filename)
                        with open(full_path, "wb") as f:
                            f.write(u_file.getbuffer())
                        saved_paths.append(full_path)
                
                img_path_str = ";".join(saved_paths)

                final_note = note
                if is_correction and "【修正】" not in note:
                    final_note = f"【修正】 {note}"
                
                # 晨掃特別備註：加入人名以便辨識
                if role == "晨間打掃":
                    final_note = f"{final_note} - {target_student_name}"

                entry = {
                    "日期": input_date, "週次": week_num, "班級": selected_class,
                    "評分項目": role, "檢查人員": inspector_name,
                    "內掃原始分": in_score, "外掃原始分": out_score,
                    "垃圾原始分": trash_score, "晨間打掃原始分": morning_score,
                    "手機人數": phone_count,
                    "備註": final_note, "照片路徑": img_path_str,
                    "登錄時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "修正": is_correction,
                    "晨掃未到者": f"{target_student_id} {target_student_name}" if role == "晨間打掃" else ""
                }
                save_entry(entry)
                st.success(f"✅ 登記完成！")

# ------------------------------------------
# 模式二：班上衛生股長 (略為修改以適應晨掃顯示)
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
                        c1, c2 = st.columns([3, 2])
                        with c1:
                            st.write(f"**違規：** {row['備註']}")
                            msg = []
                            if row["內掃原始分"] > 0: msg.append(f"內掃扣 {row['內掃原始分']}")
                            if row["外掃原始分"] > 0: msg.append(f"外掃扣 {row['外掃原始分']}")
                            if row["垃圾原始分"] > 0: msg.append(f"垃圾扣 {row['垃圾原始分']}")
                            if row["晨間打掃原始分"] > 0: msg.append(f"晨間打掃扣 {row['晨間打掃原始分']}")
                            if row["手機人數"] > 0: msg.append(f"手機 {row['手機人數']}人")
                            if msg: st.error(" | ".join(msg))
                            else: st.success("無扣分")
                            st.caption(f"檢查人員：{row['檢查人員']} | 時間：{row['登錄時間']}")
                        with c2:
                            path_str = str(row["照片路徑"])
                            if path_str and path_str != "nan":
                                paths = path_str.split(";")
                                for p in paths:
                                    if os.path.exists(p): st.image(p, width=200)
                                    else: st.caption("無法預覽")
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
    
    if password == "1234":
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
                    
                    holidays_df = load_holidays()
                    week_dates = week_df["日期"].unique()
                    week_holidays = holidays_df[holidays_df["日期"].isin(week_dates)]
                    if not week_holidays.empty:
                        st.info("ℹ️ 本週包含假日/停課日：")
                        st.dataframe(week_holidays, hide_index=True)

                    # 智慧清洗
                    week_df_sorted = week_df.sort_values(by="登錄時間", ascending=False)
                    cleaned_rows = []
                    groups = week_df_sorted.groupby(["日期", "班級", "評分項目"])
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
                        # 每日統計 (Daily Stats)
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
                        
                        # 報表生成
                        class_score_df = pd.DataFrame(all_classes, columns=["班級"])
                        final_deductions = daily_group.groupby("班級")["當日總扣分"].sum().reset_index()
                        
                        daily_pivot = daily_group.pivot(index="班級", columns="日期", values="當日總扣分").reset_index()
                        daily_pivot = daily_pivot.fillna(0)
                        
                        report = pd.merge(class_score_df, final_deductions, on="班級", how="left").fillna(0)
                        report = pd.merge(report, daily_pivot, on="班級", how="left").fillna(0)
                        
                        report["本週成績"] = 90 - report["當日總扣分"]
                        
                        date_cols = sorted([col for col in report.columns if col not in ["班級", "當日總扣分", "本週成績"]])
                        final_cols = ["班級"] + date_cols + ["當日總扣分", "本週成績"]
                        report = report[final_cols]
                        report = report.sort_values(by="本週成績", ascending=False)
                        
                        # --- 新增：晨間打掃未到專屬報表 ---
                        morning_absent_df = cleaned_df[cleaned_df["評分項目"] == "晨間打掃"][["日期", "班級", "晨掃未到者", "晨間打掃原始分", "備註"]]
                        morning_absent_df = morning_absent_df.sort_values(by="日期")

                        import io
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            report.to_excel(writer, index=False, sheet_name='總成績')
                            morning_absent_df.to_excel(writer, index=False, sheet_name='🌅晨掃未到明細') # 新增這頁
                            daily_group.to_excel(writer, index=False, sheet_name='詳細流水帳(清洗後)')
                            week_df.to_excel(writer, index=False, sheet_name='原始輸入紀錄')
                            if not week_holidays.empty:
                                week_holidays.to_excel(writer, index=False, sheet_name='本週假日紀錄')
                        
                        st.download_button(
                            label="📥 下載 Excel 結算報表 (含晨掃專屬頁面)",
                            data=output.getvalue(),
                            file_name=f"第{selected_week}週_衛生糾察總表.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                        
                        st.write("##### 🏆 班級成績總表")
                        numeric_cols = report.select_dtypes(include=['number']).columns
                        st.dataframe(
                            report.style
                            .format("{:.0f}", subset=numeric_cols)
                            .background_gradient(subset=["本週成績"], cmap="RdYlGn", vmin=60, vmax=90)
                        )
                        
                        if not morning_absent_df.empty:
                            st.write("##### 🌅 本週晨掃未到名單")
                            st.dataframe(morning_absent_df)

        # --- Tab 2: 資料管理 ---
        with tab2:
            st.write("原則上系統會自動處理修正單，若您仍需手動刪除資料，請在此操作。")
            if not df.empty:
                df_display = df.sort_values(by="登錄時間", ascending=False).reset_index()
                options = {row['index']: f"[{'修正單' if row['修正'] else '一般'}] {row['日期']} {row['班級']} - {row['評分項目']} (扣 {row['內掃原始分']+row['外掃原始分']+row['垃圾原始分']+row['晨間打掃原始分']} 分) | 備註: {row['備註']}" for i, row in df_display.iterrows()}
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
            st.header("⚙️ 系統參數設定")
            
            st.subheader("1. 學期開學日")
            config = load_config()
            current_start = datetime.strptime(config["semester_start"], "%Y-%m-%d").date()
            new_date = st.date_input("設定本學期第一週開始日", current_start)
            if st.button("💾 儲存開學日"):
                save_config(new_date)
                st.success("已更新開學日！")
                st.rerun()
            
            st.divider()
            
            st.subheader("2. 假日/停課登錄")
            c1, c2 = st.columns([2, 1])
            h_date = c1.date_input("選擇假日日期", datetime.now())
            h_reason = c2.text_input("假日原因", placeholder="例：校慶補假")
            if st.button("➕ 新增假日"):
                if h_reason:
                    save_holiday(h_date, h_reason)
                    st.success(f"已新增：{h_date}")
            
            holidays = load_holidays()
            if not holidays.empty:
                with st.expander("查看已登記假日"):
                    for i, row in holidays.iterrows():
                        col_text, col_btn = st.columns([4, 1])
                        col_text.text(f"{row['日期']} - {row['原因']}")
                        if col_btn.button("刪除", key=f"del_h_{i}"):
                            delete_holiday(row['日期'])
                            st.rerun()

            st.divider()

            st.subheader("3. 👥 人員名單管理")
            edit_team = st.radio("選擇要編輯的隊伍", ["衛生糾察隊 (內/外掃)", "環保糾察隊 (垃圾/回收)"], horizontal=True)
            current_inspectors = load_inspectors()
            target_list_key = "hygiene" if edit_team == "衛生糾察隊 (內/外掃)" else "env"
            current_list = current_inspectors[target_list_key]
            
            col_add1, col_add2 = st.columns([3, 1])
            new_member = col_add1.text_input("輸入新人員", placeholder="學號 職稱 姓名")
            if col_add2.button("➕ 加入名單"):
                if new_member and new_member not in current_list:
                    current_list.append(new_member)
                    save_inspectors(current_inspectors["hygiene"], current_inspectors["env"])
                    st.success(f"已加入：{new_member}")
                    st.rerun()
            
            st.write("移除人員：")
            members_to_remove = st.multiselect("選擇要移除的人員", current_list)
            if st.button("🗑️ 確認移除人員"):
                if members_to_remove:
                    new_list = [m for m in current_list if m not in members_to_remove]
                    if target_list_key == "hygiene":
                        save_inspectors(new_list, current_inspectors["env"])
                    else:
                        save_inspectors(current_inspectors["hygiene"], new_list)
                    st.success("已移除選取人員！")
                    st.rerun()

    elif password:
        st.error("密碼錯誤")