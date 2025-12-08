import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, date, timedelta
import shutil

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

if not os.path.exists(IMG_DIR): os.makedirs(IMG_DIR)

# --- 預設名單 ---
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

# --- 載入名單與班級 ---
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
        expected_cols = ["日期", "週次", "班級", "評分項目", "檢查人員", "內掃原始分", "外掃原始分", "垃圾原始分", "晨間打掃原始分", "手機人數", "備註", "照片路徑", "登錄時間"]
        for col in expected_cols:
            if col not in df.columns: df[col] = 0 if "分" in col or "人數" in col else ""
        return df
    else:
        return pd.DataFrame(columns=[
            "日期", "週次", "班級", "評分項目", "檢查人員",
            "內掃原始分", "外掃原始分", "垃圾原始分", "晨間打掃原始分", "手機人數", 
            "備註", "照片路徑", "登錄時間"
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
    
    if role == "垃圾/回收檢查":
        inspector_name = st.selectbox("檢查人員姓名", env_team)
    elif role == "晨間打掃":
        st.info("ℹ️ 晨間打掃檢查權限：衛生組長")
        inspector_name = "衛生組長"
    else:
        inspector_name = st.selectbox("檢查人員姓名", hygiene_team)
        
    col1, col2 = st.columns(2)
    input_date = col1.date_input("檢查日期", datetime.now())
    selected_class = col2.selectbox("被登記班級", all_classes)
    
    week_num, start_date = get_school_week(input_date)
    
    holidays_df = load_holidays()
    is_holiday = str(input_date) in holidays_df["日期"].values
    if is_holiday:
        reason = holidays_df[holidays_df["日期"] == str(input_date)]["原因"].values[0]
        st.warning(f"⚠️ 注意：{input_date} 是假日 ({reason})，但您仍可評分。")
    
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
            st.markdown("🌅 **晨間打掃檢查 (無扣分上限)**")
            morning_score = st.number_input("扣分分數", min_value=0, step=1)
            note = st.text_input("違規說明", placeholder="例如：未進行打掃")

        # --- v9.0 新增：修正資料勾選 ---
        st.write("")
        is_correction = st.checkbox("🚩 這是一筆修正資料 (勾選後，請通知老師刪除上一筆錯誤紀錄)")

        uploaded_files = st.file_uploader("📸 上傳違規照片 (可多選)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
        
        submitted = st.form_submit_button("送出評分", use_container_width=True)

        if submitted:
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

            # 如果是修正資料，自動在備註加標籤
            final_note = note
            if is_correction:
                final_note = f"【申請更正】 {note}"

            entry = {
                "日期": input_date, "週次": week_num, "班級": selected_class,
                "評分項目": role, "檢查人員": inspector_name,
                "內掃原始分": in_score, "外掃原始分": out_score,
                "垃圾原始分": trash_score, "晨間打掃原始分": morning_score,
                "手機人數": phone_count,
                "備註": final_note, "照片路徑": img_path_str,
                "登錄時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            save_entry(entry)
            st.success(f"✅ 登記完成！")

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
            class_df = class_df.sort_values(by="日期", ascending=False)
            st.subheader(f"📅 {search_class} 近期紀錄")
            for index, row in class_df.iterrows():
                total_raw = row["內掃原始分"] + row["外掃原始分"] + row["垃圾原始分"] + row["晨間打掃原始分"] + row["手機人數"]
                if total_raw > 0:
                    with st.expander(f"[第{row['週次']}週] {row['日期']} - {row['評分項目']} (扣分詳情)"):
                        c1, c2 = st.columns([3, 2])
                        with c1:
                            st.write(f"**違規：** {row['備註']}")
                            msg = []
                            if row["內掃原始分"] > 0: msg.append(f"內掃扣 {row['內掃原始分']}")
                            if row["外掃原始分"] > 0: msg.append(f"外掃扣 {row['外掃原始分']}")
                            if row["垃圾原始分"] > 0: msg.append(f"垃圾扣 {row['垃圾原始分']}")
                            if row["晨間打掃原始分"] > 0: msg.append(f"晨間打掃扣 {row['晨間打掃原始分']}")
                            if row["手機人數"] > 0: msg.append(f"手機 {row['手機人數']}人")
                            st.error(" | ".join(msg))
                            st.caption(f"檢查人員：{row['檢查人員']}")
                        with c2:
                            path_str = str(row["照片路徑"])
                            if path_str and path_str != "nan":
                                paths = path_str.split(";")
                                for p in paths:
                                    if os.path.exists(p):
                                        st.image(p, width=200)
                                    else:
                                        st.caption("無法預覽")
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
        
        tab1, tab2, tab3 = st.tabs(["📊 成績報表", "🛠️ 資料修正", "⚙️ 系統設定"])
        
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

                    daily_group = week_df.groupby(["日期", "班級"]).agg({
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
                    
                    final_deductions = daily_group.groupby("班級")["當日總扣分"].sum().reset_index()
                    class_score_df = pd.DataFrame(all_classes, columns=["班級"])
                    report = pd.merge(class_score_df, final_deductions, on="班級", how="left").fillna(0)
                    report["本週成績"] = 90 - report["當日總扣分"]
                    report = report.sort_values(by="本週成績", ascending=False)
                    
                    import io
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        report.to_excel(writer, index=False, sheet_name='總成績')
                        daily_group.to_excel(writer, index=False, sheet_name='每日統計')
                        if not week_holidays.empty:
                            week_holidays.to_excel(writer, index=False, sheet_name='本週假日紀錄')
                    
                    st.download_button(
                        label="📥 下載 Excel 結算報表",
                        data=output.getvalue(),
                        file_name=f"第{selected_week}週_衛生糾察總表.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                    
                    st.dataframe(report.style.format({"當日總扣分": "{:.0f}", "本週成績": "{:.0f}"})
                                .background_gradient(subset=["本週成績"], cmap="RdYlGn", vmin=60, vmax=90))

        # --- Tab 2: 修正區 (v9.0 優化) ---
        with tab2:
            st.write("勾選要刪除的項目，然後點擊下方的刪除按鈕。")
            
            if not df.empty:
                # --- v9.0 新增篩選器 ---
                filter_correction = st.checkbox("🔍 只顯示包含【申請更正】的資料")
                
                # 建立顯示用的 DataFrame
                display_df = df.copy()
                if filter_correction:
                    # 篩選備註含有 "【申請更正】" 的列
                    display_df = display_df[display_df["備註"].astype(str).str.contains("【申請更正】", na=False)]
                
                if not display_df.empty:
                    # 選單使用 display_df 來呈現，但 key (index) 還是要對應回原始 df
                    options = {i: f"{row['日期']} {row['班級']} - {row['評分項目']} (扣 {row['內掃原始分']+row['外掃原始分']+row['垃圾原始分']+row['晨間打掃原始分']} 分) | 備註: {row['備註']}" for i, row in display_df.iterrows()}
                    
                    selected_indices = st.multiselect(
                        "請選擇要刪除的紀錄：",
                        options=options.keys(),
                        format_func=lambda x: f"[{x}] {options[x]}"
                    )
                    
                    if st.button("🗑️ 確認刪除選取項目"):
                        if selected_indices:
                            delete_entry(selected_indices)
                            st.success("刪除成功！")
                            st.rerun()
                        else:
                            st.warning("請先選擇要刪除的項目")
                else:
                    if filter_correction:
                        st.info("目前沒有標記為【申請更正】的資料。")
                    else:
                        st.info("無資料")
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
                else:
                    st.error("請輸入原因")
            
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
            new_member = col_add1.text_input("輸入新人員 (建議格式：學號 職稱 姓名)", placeholder="例如：123456 衛糾99 王小明")
            if col_add2.button("➕ 加入名單"):
                if new_member and new_member not in current_list:
                    current_list.append(new_member)
                    save_inspectors(current_inspectors["hygiene"], current_inspectors["env"])
                    st.success(f"已加入：{new_member}")
                    st.rerun()
                elif new_member in current_list:
                    st.warning("該人員已在名單中")
                else:
                    st.warning("請輸入內容")
            
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