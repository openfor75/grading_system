# 寫入資料 (強壯版：確保格式正確且強制寫入)
def save_entry(new_entry):
    client = get_gsheet_client()
    if not client: 
        st.error("⚠️ 無法連線至 Google，請檢查網路或金鑰。")
        return

    try:
        sheet = client.open(GSHEET_NAME).sheet1
        
        # 為了保險起見，我們將所有要寫入的資料強制轉成字串 (String)
        # 這樣可以避免 Google Sheets API 因為看不懂 Python 的某些格式而拒絕寫入
        row_values = [
            str(new_entry.get("日期", "")),
            str(new_entry.get("週次", "")),
            str(new_entry.get("班級", "")),
            str(new_entry.get("評分項目", "")),
            str(new_entry.get("檢查人員", "")),
            str(new_entry.get("內掃原始分", 0)),
            str(new_entry.get("外掃原始分", 0)),
            str(new_entry.get("垃圾原始分", 0)),
            str(new_entry.get("垃圾內掃原始分", 0)),
            str(new_entry.get("垃圾外掃原始分", 0)),
            str(new_entry.get("晨間打掃原始分", 0)),
            str(new_entry.get("手機人數", 0)),
            str(new_entry.get("備註", "")),
            str(new_entry.get("違規細項", "")),
            str(new_entry.get("照片路徑", "")),
            str(new_entry.get("登錄時間", "")),
            str(new_entry.get("修正", False)),
            str(new_entry.get("晨掃未到者", ""))
        ]
        
        # 檢查是否為空表，如果是，先寫入標題
        # (這裡用 try-except 包起來，避免讀取失敗影響寫入)
        try:
            if not sheet.get_all_values():
                 headers = [
                    "日期", "週次", "班級", "評分項目", "檢查人員",
                    "內掃原始分", "外掃原始分", "垃圾原始分", "垃圾內掃原始分", "垃圾外掃原始分", "晨間打掃原始分", "手機人數", 
                    "備註", "違規細項", "照片路徑", "登錄時間", "修正", "晨掃未到者"
                ]
                 sheet.append_row(headers)
        except:
            pass # 如果讀取失敗，我們就直接嘗試寫入資料，不理會標題

        # 執行寫入
        sheet.append_row(row_values)
        
    except Exception as e:
        # 這裡會把錯誤印在螢幕上，讓我們知道為什麼寫不進去
        st.error(f"⚠️ 寫入資料失敗: {e}")
