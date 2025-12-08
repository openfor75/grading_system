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

# --- C. 晨掃輪值表讀取 ---
def get_daily_duty(target_date, csv_path=DUTY_FILE):
    duty_list = []
    status = "init"
    
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
            date_col = next((c for c in df.columns if "日期" in c or "時間" in c), None)
            id_col = next((c for c in df.columns if "學號" in c), None)
            name_col = next((c for c in df.columns if "姓名" in c), None)
            loc_col = next((c for c in df.columns if "地點" in c or "區域" in c), None)
            
            if date_col and id_col:
                try:
                    df[date_col] = pd.to_datetime(df[date_col], errors='coerce').dt.date
                except:
                    pass
                
                target_date_obj = target_date if isinstance(target_date, date) else target_date.date()
                today_df = df[df[date_col] == target_date_obj]
                
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
        
    return duty_list, status

# --- D. 糾察隊名單 (v23.0 含診斷資訊) ---
@st.cache_data
def load_inspector_csv():
    inspectors = []
    debug_info = {"status": "init", "cols": [], "rows": 0, "name_col": None, "role_col": None}
    
    if not os.path.exists(INSPECTOR_DUTY_FILE):
        return [{"label": "衛生組長 (預設)", "role": "晨間打掃", "raw_role": "晨掃", "assigned_classes": []}], debug_info
    
    encodings = ['utf-8', 'big5', 'cp950', 'utf-8-sig']
    df = None
    for enc in encodings:
        try:
            df = pd.read_csv(INSPECTOR_DUTY_FILE, encoding=enc, dtype=str)
            df.columns = df.columns.str.strip()
            # 檢查是否有基本欄位，若有則視為成功開啟
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

                mapped_role = "內掃檢查" 
                if "外掃" in s_raw_role: mapped_role = "外掃檢查"
                elif "垃圾" in s_raw_role or "回收" in s_raw_role or "環保" in s_raw_role: mapped_role = "垃圾/回收檢查"
                elif "晨" in s_raw_role: mapped_role = "晨間打掃"
                elif "內掃" in s_raw_role: mapped_role = "內掃檢查"
                
                label = f"{s_name}"
                if s_id: label = f"{s_name} ({s_id})"
                
                inspectors.append({
                    "label": label,
                    "role": mapped_role,
                    "raw_role": s_raw_role,
                    "assigned_classes": s_classes 
                })
        else:
            debug_info["status"] = "missing_name_col"
    else:
        debug_info["status"] = "read_failed"
    
    if not inspectors:
        inspectors.append({"label": "測試人員", "role": "內掃檢查", "raw_role": "測試", "assigned_classes": []})
        
    return inspectors, debug_info

INSPECTOR_LIST