import streamlit as st
import pandas as pd
import re
import io

# --- 設定頁面資訊 ---
st.set_page_config(page_title="DNS 紀錄轉換工具", page_icon="🌐", layout="wide")

# --- 核心解析函式 ---
def parse_dns_data(text):
    active_records = []
    paused_records = []

    lines = text.strip().split('\n')
    
    for line in lines:
        raw_line = line.strip()
        if not raw_line:
            continue
            
        # 1. 判斷是否為暫停 (支援 # 和 ;)
        is_paused = False
        clean_line = raw_line
        
        if raw_line.startswith('#') or raw_line.startswith(';'):
            is_paused = True
            # 移除開頭的標記符號，並去除前後空白
            clean_line = raw_line[1:].strip()
            
        # 再次檢查移除符號後是否為空行
        if not clean_line:
            continue

        # 2. 使用正規表達式依照空白切割
        parts = re.split(r'\s+', clean_line)
        
        # 預設變數
        host = ""
        r_type = ""
        value = ""
        priority = "" # 給 MX 用
        
        # 3. 解析邏輯
        # 移除 'IN' (標準 BIND 格式通常有 IN，但有時會省略)
        # 我們建立一個過濾後的列表，排除 'IN'
        filtered_parts = [p for p in parts if p.upper() != 'IN']
        
        # 確保至少有 Host 和 Type
        if len(filtered_parts) >= 2:
            host = filtered_parts[0]
            
            # 處理根網域轉換：如果有 . 結尾或是 @
            if ('.' in host and host.endswith('.')) or host == "": 
                host = '@'
            
            r_type = filtered_parts[1].upper()
            
            # 針對 MX 紀錄處理優先級
            if r_type == 'MX' and len(filtered_parts) >= 4:
                priority = filtered_parts[2]
                value = filtered_parts[3]
            elif r_type == 'MX' and len(filtered_parts) == 3:
                # 預防某些格式沒有優先級 (雖然少見) 或位置偏移
                priority = filtered_parts[2] 
                value = "" 
            elif len(filtered_parts) >= 3:
                # 一般紀錄 (A, CNAME, TXT, NS...)
                priority = ""
                value = " ".join(filtered_parts[2:]) # 剩下的都當作值 (例如 TXT 可能有空白)
            else:
                value = ""

            # 建立資料物件
            record = {
                "主機紀錄": host,
                "紀錄類型": r_type,
                "紀錄值": value,
                "優先級": priority
            }
            
            if is_paused:
                paused_records.append(record)
            else:
                active_records.append(record)
            
    return active_records, paused_records

# --- UI 介面設計 ---

st.title("🌐 DNS Zone File 格式轉換器")
st.markdown("""
此工具可將 BIND 格式的 DNS 設定檔轉換為表格格式。
- 自動識別 **`#`** 和 **`;`** 為暫停（註解）紀錄。
- 自動將完整網域（結尾有 `.`）轉換為 **`@`**。
- 自動分離 **MX** 紀錄的優先級。
""")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. 輸入原始資料")
    default_input = """localhost           IN      A       127.0.0.1
taiwan-india.org.tw.    IN  A   203.75.177.1
#                       IN      MX 3    mailserver.taian-electric.com.tw.
;mailserver             IN      A       203.75.177.50
ns1         IN      A       203.75.177.1
ns2         IN  A   203.75.177.111
www                     IN      A       60.251.30.110
;old-www                IN      CNAME   google.com"""
    
    input_text = st.text_area("請貼上 DNS 設定內容：", value=default_input, height=400)

with col2:
    st.subheader("2. 轉換結果")
    
    if input_text:
        active_list, paused_list = parse_dns_data(input_text)
        
        # 轉換成 DataFrame
        df_active = pd.DataFrame(active_list, columns=["主機紀錄", "紀錄類型", "紀錄值", "優先級"])
        df_paused = pd.DataFrame(paused_list, columns=["主機紀錄", "紀錄類型", "紀錄值", "優先級"])
        
        st.info(f"偵測到：啟用紀錄 {len(df_active)} 筆 / 暫停紀錄 {len(df_paused)} 筆")

        st.markdown("### ✅ 啟用中 (Active)")
        st.dataframe(df_active, use_container_width=True, hide_index=True)
        
        st.markdown("### ⏸️ 已暫停 (Paused - # 或 ; 開頭)")
        st.dataframe(df_paused, use_container_width=True, hide_index=True)

        # --- 產生 Excel 下載 ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # 寫入啟用資料
            df_active.to_excel(writer, sheet_name='DNS設定', index=False, startrow=0)
            
            # 計算暫停資料要寫入的起始行 (空兩行)
            start_row = len(df_active) + 3
            
            # 寫入一個標題分隔
            pd.DataFrame([["=== 以下為暫停紀錄 ===", "", "", ""]], columns=df_active.columns).to_excel(
                writer, sheet_name='DNS設定', index=False, startrow=start_row-1, header=False
            )
            
            # 寫入暫停資料
            df_paused.to_excel(writer, sheet_name='DNS設定', index=False, startrow=start_row)

        processed_data = output.getvalue()
        
        st.download_button(
            label="📥 下載 Excel 檔案",
            data=processed_data,
            file_name="dns_records_converted.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
