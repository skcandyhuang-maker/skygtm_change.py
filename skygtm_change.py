import streamlit as st
import pandas as pd
import re
import io
import dns.resolver

# --- 設定頁面資訊 ---
st.set_page_config(page_title="DNS 紀錄轉換工具 Pro", page_icon="🛠️", layout="wide")

# --- 初始化 Session State ---
if 'dns_input' not in st.session_state:
    st.session_state.dns_input = ""
if 'verify_input' not in st.session_state:
    st.session_state.verify_input = ""

# ==========================================
#  核心函式 1: Zone File 解析
# ==========================================
def parse_dns_data(text):
    active_records = []
    paused_records = []
    lines = text.strip().split('\n')
    
    for line in lines:
        raw_line = line.strip()
        if not raw_line: continue
            
        is_paused = False
        clean_line = raw_line
        if raw_line.startswith('#') or raw_line.startswith(';'):
            is_paused = True
            clean_line = raw_line[1:].strip()
        if not clean_line: continue

        parts = re.split(r'\s+', clean_line)
        filtered_parts = [p for p in parts if p.upper() != 'IN']
        
        host = ""
        r_type = ""
        value = ""
        priority = "" 
        
        if len(filtered_parts) >= 2:
            host = filtered_parts[0]
            
            # 處理長前綴與 @ 的邏輯
            if host == "" or host == "@":
                host = '@'
            elif host.endswith('.'):
                host = host[:-1]
                if host == "":
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

# ==========================================
#  核心函式 2: DNS 比對
# ==========================================
def query_dns_record(server_ip, host, record_type):
    try:
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [server_ip]
        resolver.lifetime = 3 
        q_type = record_type if record_type else 'A'
        answers = resolver.resolve(host, q_type)
        result_list = sorted([r.to_text() for r in answers])
        return ", ".join(result_list)
    except dns.resolver.NXDOMAIN:
        return "NoAnswer (無回應/無此紀錄)"
    except dns.resolver.NoAnswer:
        return "NoAnswer (無回應)"
    except dns.resolver.LifetimeTimeout:
        return "Timeout (逾時)"
    except Exception as e:
        return f"Error: {str(e)}"

# --- 輔助函式 ---
def load_example_zone():
    st.session_state.dns_input = """localhost           IN      A       127.0.0.1
# 修正後的長前綴測試
default._domainkey.elite.  IN      TXT     "v=DKIM1; k=rsa;"
taiwan-india.org.tw.    IN  A   203.75.177.1
#                       IN      MX 3    mailserver.taian-electric.com.tw.
;mailserver             IN      A       203.75.177.50
ns1         IN      A       203.75.177.1
www                     IN      A       60.251.30.110"""

def load_example_verify():
    # 這裡放入您截圖中的情境
    st.session_state.verify_input = """www, A
@, MX
default._domainkey.elite, TXT
develite, A"""

def clear_input_zone():
    st.session_state.dns_input = ""

def clear_input_verify():
    st.session_state.verify_input = ""

# ==========================================
#  UI 介面設計
# ==========================================

st.title("🛠️ DNS 綜合工具箱")

tab1, tab2 = st.tabs(["📄 Zone File 轉換", "🔍 DNS 比對驗證"])

# ----------------------------------------------------
#  頁籤 1: Zone File 轉換
# ----------------------------------------------------
with tab1:
    col1, col2 = st.columns([1, 1.2])
    with col1:
        st.subheader("1. 輸入來源")
        btn_col1, btn_col2, btn_col3 = st.columns([0.4, 0.3, 0.3])
        with btn_col1:
            uploaded_file = st.file_uploader("上傳 .txt/.zone", type=['txt', 'zone'], key='uploader_zone', label_visibility="collapsed")
            if uploaded_file:
                stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
                st.session_state.dns_input = stringio.read()
        with btn_col2:
            st.button("載入範例", on_click=load_example_zone, key="btn_ex_zone", use_container_width=True)
        with btn_col3:
            st.button("🗑️ 清空", on_click=clear_input_zone, key="btn_clr_zone", use_container_width=True)

        input_text = st.text_area("貼上內容：", key="dns_input", height=500)

    with col2:
        st.subheader("2. 預覽與編輯結果")
        if input_text:
            active_list, paused_list = parse_dns_data(input_text)
            df_active = pd.DataFrame(active_list, columns=["主機紀錄", "紀錄類型", "紀錄值", "優先級"])
            df_paused = pd.DataFrame(paused_list, columns=["主機紀錄", "紀錄類型", "紀錄值", "優先級"])
            
            st.caption(f"📊 統計：啟用 {len(df_active)} 筆 / 暫停 {len(df_paused)} 筆")
            st.markdown("### ✅ 啟用中")
            edited_df_active = st.data_editor(df_active, use_container_width=True, num_rows="dynamic", key="editor_active")
            st.markdown("### ⏸️ 已暫停")
            edited_df_paused = st.data_editor(df_paused, use_container_width=True, num_rows="dynamic", key="editor_paused")

            output = io.BytesIO()
            try:
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    edited_df_active.to_excel(writer, sheet_name='DNS設定', index=False)
                    start_row = len(edited_df_active) + 3
                    pd.DataFrame([["=== 以下為暫停紀錄 ===", "", "", ""]], columns=df_active.columns).to_excel(
                        writer, sheet_name='DNS設定', index=False, startrow=start_row-1, header=False
                    )
                    edited_df_paused.to_excel(writer, sheet_name='DNS設定', index=False, startrow=start_row)
                
                st.download_button("📥 下載 Excel", output.getvalue(), "dns_records_custom.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
            except ModuleNotFoundError:
                st.error("⚠️ 系統缺少 'openpyxl' 套件。")
        else:
            st.info("👈 請輸入資料開始轉換。")

# ----------------------------------------------------
#  頁籤 2: DNS 比對驗證 (修正版)
# ----------------------------------------------------
with tab2:
    st.markdown("比較兩個 DNS Server 對同一組域名的解析結果是否一致。")
    
    with st.expander("⚙️ 測試環境設定", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            ns1_input = st.text_input("DNS Server 1 (基準)", value="8.8.8.8")
        with c2:
            ns2_input = st.text_input("DNS Server 2 (對照)", value="1.1.1.1")
        with c3:
            default_domain = st.text_input("預設網域 (Default Domain)", value="example.com")
            
    col_input, col_result = st.columns([1, 1.5])
    
    with col_input:
        st.subheader("1. 輸入查詢清單")
        st.caption("格式：`主機(Host), 類型(Type)`")
        
        b1, b2 = st.columns([1, 1])
        with b1:
            st.button("載入測試清單", on_click=load_example_verify, key="btn_ex_verify", use_container_width=True)
        with b2:
            st.button("🗑️ 清空清單", on_click=clear_input_verify, key="btn_clr_verify", use_container_width=True)
            
        verify_text = st.text_area("查詢內容", key="verify_input", height=300)
        start_btn = st.button("🚀 開始比對", type="primary", use_container_width=True)

    with col_result:
        st.subheader("2. 比對結果")
        
        if start_btn and verify_text and ns1_input and ns2_input and default_domain:
            results = []
            
            # 解析 NS IP
            with st.spinner("正在解析 DNS Server IP..."):
                try:
                    resolver_ip_1 = ns1_input 
                    try:
                        dns.inet.inet_pton(dns.inet.AF_INET, ns1_input)
                    except:
                        try:
                            res = dns.resolver.resolve(ns1_input, 'A')
                            resolver_ip_1 = res[0].to_text()
                        except:
                            st.error(f"❌ 無法解析 DNS Server 1 IP: {ns1_input}")
                            st.stop()

                    resolver_ip_2 = ns2_input
                    try:
                        dns.inet.inet_pton(dns.inet.AF_INET, ns2_input)
                    except:
                        try:
                            res = dns.resolver.resolve(ns2_input, 'A')
                            resolver_ip_2 = res[0].to_text()
                        except:
                            st.error(f"❌ 無法解析 DNS Server 2 IP: {ns2_input}")
                            st.stop()
                except Exception as e:
                    st.error(f"DNS Server 設定錯誤: {e}")
                    st.stop()

            lines = verify_text.strip().split('\n')
            progress_bar = st.progress(0)
            
            for idx, line in enumerate(lines):
                line = line.strip()
                if not line or line.startswith('#'): continue
                
                parts = line.split(',')
                host_raw = parts[0].strip()
                q_type = parts[1].strip().upper() if len(parts) > 1 else "A"
                
                # --- 🔥 修正後的網域補全邏輯 ---
                # 1. 如果是 @ -> 預設網域
                if host_raw == '@':
                    query_host = default_domain
                # 2. 如果結尾有點 . (例如 google.com.) -> 絕對路徑，移除點
                elif host_raw.endswith('.'):
                    query_host = host_raw[:-1]
                # 3. 如果原本就包含了預設網域 (例如 www.teco.com 在 teco.com 下) -> 視為完整
                elif host_raw.endswith(default_domain):
                    query_host = host_raw
                # 4. 其他所有情況 (包含 default._domainkey.elite) -> 補上預設網域
                else:
                    query_host = f"{host_raw}.{default_domain}"
                # -------------------------------
                
                res1 = query_dns_record(resolver_ip_1, query_host, q_type)
                res2 = query_dns_record(resolver_ip_2, query_host, q_type)
                
                is_match = (res1 == res2)
                status = "✅ 一致" if is_match else "❌ 不一致"
                
                results.append({
                    "主機": query_host,
                    "類型": q_type,
                    f"Server 1 ({ns1_input})": res1,
                    f"Server 2 ({ns2_input})": res2,
                    "狀態": status
                })
                
                progress_bar.progress((idx + 1) / len(lines))
            
            if results:
                df_res = pd.DataFrame(results)
                def highlight_status(val):
                    color = 'red' if '不一致' in val else 'green'
                    return f'color: {color}; font-weight: bold'

                st.dataframe(df_res.style.map(highlight_status, subset=['狀態']), use_container_width=True, hide_index=True)
                csv = df_res.to_csv(index=False).encode('utf-8')
                st.download_button("📥 下載比對報告 (CSV)", csv, "dns_verify_report.csv", "text/csv", key='download-csv')
            else:
                st.warning("沒有有效的查詢資料")
