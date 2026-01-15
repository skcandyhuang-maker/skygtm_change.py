import streamlit as st
import pandas as pd
import re
import io

# --- 設定頁面資訊 ---
st.set_page_config(page_title="DNS 紀錄轉換工具 Pro", page_icon="🛠️", layout="wide")

# --- 初始化 Session State (用於管理輸入框內容) ---
if 'dns_input' not in st.session_state:
    st.session_state.dns_input = ""

# --- 核心解析函式 (維持不變) ---
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
            clean_line = raw_line[1:].strip()
            
        if not clean_line:
            continue

        # 2. 切割字串
        parts = re.split(r'\s+', clean_line)
        
        filtered_parts = [p for p in parts if p.upper() != 'IN']
        
        host = ""
        r_type = ""
        value = ""
        priority = "" 
        
        if len(filtered_parts) >= 2:
            host = filtered_parts[0]
            
            # 根網域轉換
            if ('.' in host and host.endswith('.')) or host == "": 
                host = '@'
            
            r_type = filtered_parts[1].upper()
            
            if r_type == 'MX' and len(filtered_parts) >= 4:
                priority = filtered_parts[2]
                value = filtered_parts[3]
            elif r_type == 'MX' and len(filtered_parts) == 3:
                priority = filtered_parts[2] 
                value = "" 
            elif len(filtered_parts) >= 3:
                value = " ".join(filtered_parts[2:])
            else:
                value = ""

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

# --- 輔助函式：載入範例 ---
def load_example():
    st.session_state.dns_input = """localhost           IN      A       127.0.0.1
taiwan-india.org.tw.    IN  A   203.75.177.1
#                       IN      MX 3    mailserver.taian-electric.com.tw.
;mailserver             IN      A       203.75.177.50
ns1         IN      A       203.75.177.1
ns2         IN  A   203.75.177.111
www                     IN      A       60.251.30.110
;old-www                IN      CNAME   google.com"""

# --- 輔助函式：讀取上傳檔案 ---
def load_file():
    uploaded_file = st.session_state.uploader
    if uploaded_file is not None:
        # 嘗試解碼檔案內容
        stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
        st.session_state.dns_input = stringio.read()

# --- 輔助函式：清空輸入 ---
def clear_input():
    st.session_state.dns_input = ""

# --- UI 介面設計 ---

st.title("🛠️ DNS Zone File 轉換神器 (可編輯版)")
st.markdown("貼上 DNS 設定，或上傳檔案，我們會幫您整理成表格並匯出 Excel。")

col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("1. 輸入來源")
    
    # 功能按鈕區
    btn_col1, btn_col2, btn_col3 = st.columns([0.4, 0.3, 0.3])
    with btn_col1:
        st.file_uploader("上傳 .txt 或 .zone 檔", type=['txt', 'zone'], key='uploader', on_change=load_file, label_visibility="collapsed")
    with btn_col2:
        st.button("載入範例", on_click=load_example, use_container_width=True)
    with btn_col3:
        st.button("🗑️ 清空", on_click=clear_input, use_container_width=True)

    # 輸入框 (綁定 session_state)
    input_text = st.text_area(
        "或是直接在此貼上內容：", 
        key="dns_input",
        height=500,
        placeholder="請貼上 BIND 格式的 DNS 設定..."
    )

with col2:
    st.subheader("2. 預覽與編輯結果")
    
    if input_text:
        active_list, paused_list = parse_dns_data(input_text)
        
        # 轉換成 DataFrame
        df_active = pd.DataFrame(active_list, columns=["主機紀錄", "紀錄類型", "紀錄值", "優先級"])
        df_paused = pd.DataFrame(paused_list, columns=["主機紀錄", "紀錄類型", "紀錄值", "優先級"])
        
        # 顯示統計
        st.caption(f"📊 統計：啟用 {len(df_active)} 筆 / 暫停 {len(df_paused)} 筆")

        st.markdown("### ✅ 啟用中 (可直接編輯下表)")
        # 使用 data_editor 讓使用者可以修正資料
        edited_df_active = st.data_editor(df_active, use_container_width=True, num_rows="dynamic", key="editor_active")
        
        st.markdown("### ⏸️ 已暫停 (可直接編輯下表)")
        edited_df_paused = st.data_editor(df_paused, use_container_width=True, num_rows="dynamic", key="editor_paused")

        # --- 產生 Excel 下載 ---
        # 注意：我們使用 edited_df (編輯後的資料) 來產生 Excel
        output = io.BytesIO()
        try:
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                edited_df_active.to_excel(writer, sheet_name='DNS設定', index=False, startrow=0)
                
                start_row = len(edited_df_active) + 3
                pd.DataFrame([["=== 以下為暫停紀錄 ===", "", "", ""]], columns=df_active.columns).to_excel(
                    writer, sheet_name='DNS設定', index=False, startrow=start_row-1, header=False
                )
                edited_df_paused.to_excel(writer, sheet_name='DNS設定', index=False, startrow=start_row)
            
            processed_data = output.getvalue()
            
            st.download_button(
                label="📥 下載 Excel (包含您的修改)",
                data=processed_data,
                file_name="dns_records_custom.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        except ModuleNotFoundError:
            st.error("⚠️ 系統缺少 'openpyxl' 套件。請確認您已安裝該套件 (pip install openpyxl)。")
    else:
        st.info("👈 請在左側輸入資料或上傳檔案以開始轉換。")
