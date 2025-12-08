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
ROSTER_FILE = "全校名單.csv" # 系統預設儲存路徑

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

# --- B. 全校名單 (智慧讀取功能) ---
@st.cache_data
def load_roster_dict(csv_path=ROSTER_FILE):
    roster_dict = {}
    if os.path.exists(csv_path):
        # 嘗試多種編碼，解決 Excel 存檔造成的亂碼問題
        encodings_to_try = ['utf-8', 'big5', 'cp950']
        df = None
        
        for enc in encodings_to_try:
            try:
                df = pd.read_csv(csv_path, encoding=enc, dtype=str)
                # 檢查關鍵欄位是否存在
                if any("學號" in c for c in df.columns) and any("班級" in c for c in df.columns):
                    break # 成功讀取，跳出迴圈
            except:
                continue
        
        if df is not None:
            # 清理欄位名稱
            df.columns = df.columns.str.strip()
            
            # 模糊搜尋欄位名稱 (避免 " 學號" 或 "學號 " 這種空白問題)
            id_col = next((c for c in df.columns if "學號" in c), None)
            class_col = next((c for c in df.columns if "班級" in c), None)
            
            if id_col and class_col:
                for _, row in df.iterrows():
                    s_id = str(row[id_col]).strip()
                    s_class = str(row[class_col]).strip()
                    if s_id and s_class and s_id.lower() != "nan":
                        roster_dict[s_id] = s_class
            else:
                return None