import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz  # [新增] 匯入時區套件

# --- 網頁基本設定 ---
st.set_page_config(
    page_title="台股天價回檔佈局儀表板",
    page_icon="📈",
    layout="wide"
)

# --- 標題與即時時間 (強制設定為台灣時間) ---
# [修改] 使用 pytz 指定為 'Asia/Taipei' 時區
tw_timezone = pytz.timezone('Asia/Taipei')
current_time = datetime.datetime.now(tw_timezone).strftime('%Y-%m-%d %H:%M:%S')

st.title("📈 台股歷史最高價回檔計算儀表板")
st.markdown(f"**台灣時間：** `{current_time}` *(每次重新整理網頁時會同步更新)*")

# --- 核心數據抓取與修正函式 ---
@st.cache_data(ttl=300) 
def fetch_stock_data():
    tickers = {
        "台積電": "2330.TW",
        "0050": "0050.TW",
        "00631L": "00631L.TW",
        "0052": "0052.TW",
        "009816": "009816.TW"
    }
    
    results = {}
    
    for name, symbol in tickers.items():
        try:
            ticker_obj = yf.Ticker(symbol)
            hist = ticker_obj.history(period="max")
            
            if not hist.empty:
                # 抓取盤中即時價格
                today_data = ticker_obj.history(period="1d", interval="1m")
                if not today_data.empty:
                    realtime_price = today_data['Close'].iloc[-1]
                else:
                    realtime_price = hist['Close'].iloc[-1]

                # =========================================================
                #  通用型動態分割與除權息修正演算法
                # =========================================================
                for i in range(1, len(hist)):
                    prev_close = float(hist['Close'].iloc[i-1])
                    curr_open = float(hist['Open'].iloc[i])
                    
                    if pd.isna(curr_open) or curr_open <= 0:
                        curr_open = float(hist['Close'].iloc[i])
                        
                    if prev_close > 0 and curr_open > 0:
                        drop_ratio = (prev_close - curr_open) / prev_close
                        
                        if drop_ratio > 0.20: 
                            ratio = prev_close / curr_open
                            if abs(ratio - round(ratio)) < 0.1:
                                ratio = float(round(ratio))
                                
                            high_col_idx = hist.columns.get_loc('High')
                            hist.iloc[:i, high_col_idx] = hist.iloc[:i, high_col_idx] / ratio
                # =========================================================

                ath_price = hist['High'].max()
                
                results[name] = {
                    "ath": round(ath_price, 2),
                    "realtime": round(realtime_price, 2)
                }
            else:
                results[name] = {"ath": 0.0, "realtime": 0.0}
        except Exception as e:
            results[name] = {"ath": 0.0, "realtime": 0.0}
            
    return results

# --- 執行資料抓取 ---
with st.spinner("正在連線 Yahoo Finance 獲取最新行情與分割修正數據..."):
    data_source = fetch_stock_data()

# --- 互動式：手動修改歷史天價區塊 ---
st.subheader("🛠️ 數據調整與試算（您可以直接修改下方的天價）")

targets = ["台積電", "0050", "00631L", "0052", "009816"]

input_cols = st.columns(len(targets))
user_ath_prices = {}

for idx, name in enumerate(targets):
    with input_cols[idx]:
        user_ath_prices[name] = st.number_input(
            f"{name} 歷史天價", 
            value=data_source[name]["ath"],
            step=0.1,
            format="%.2f"
        )

# --- 建立核心回檔數據表格 ---
st.subheader("📊 回檔策略佈局矩陣（黃色區塊代表已跌破該關卡）")

row_headers = [
    "歷史最高價 (基準)", 
    "盤中即時價", 
    "目前回檔 %", 
    "回檔 10%", 
    "回檔 15%", 
    "回檔 20%", 
    "回檔 25%", 
    "回檔 30%"
]

matrix_data = {name: [] for name in targets}
for name in targets:
    ath = user_ath_prices[name]
    realtime = data_source[name]["realtime"]
    
    if ath > 0:
        if realtime >= ath:
            drawdown_pct = 0.0  
        else:
            drawdown_pct = ((realtime - ath) / ath) * 100
    else:
        drawdown_pct = 0.0
        
    matrix_data[name].append(ath)
    matrix_data[name].append(realtime)
    matrix_data[name].append(drawdown_pct)
    matrix_data[name].append(ath * 0.90)   
    matrix_data[name].append(ath * 0.85)   
    matrix_data[name].append(ath * 0.80)   
    matrix_data[name].append(ath * 0.75)   
    matrix_data[name].append(ath * 0.70)   

df = pd.DataFrame(matrix_data, index=row_headers)

# =========================================================
#  表格動態著色與格式化邏輯
# =========================================================
def highlight_breakthrough(row):
    styles = [''] * len(row)
    if row.name in ["回檔 10%", "回檔 15%", "回檔 20%", "回檔 25%", "回檔 30%"]:
        for col_idx, name in enumerate(row.index):
            realtime_p = matrix_data[name][1]  
            target_p = row[name]               
            
            if realtime_p <= target_p:
                styles[col_idx] = 'background-color: #FFFFCC; color: black; font-weight: bold;'
    return styles

styled_df = df.style.apply(highlight_breakthrough, axis=1)

for row_name in row_headers:
    row_idx = df.index.get_loc(row_name)
    if row_name == "目前回檔 %":
        styled_df = styled_df.format(lambda x: f"{x:.2f}%", subset=pd.IndexSlice[[row_name], :])
    else:
        styled_df = styled_df.format(lambda x: f"{x:.2f}", subset=pd.IndexSlice[[row_name], :])

st.dataframe(
    styled_df,
    use_container_width=True,
    height=360
)

# --- 功能控制按鈕 ---
if st.button("🔄 手動重新整理行情"):
    st.cache_data.clear() 
    st.rerun()

st.info("💡 提示：『目前回檔 %』欄位若數值為 0.00%，代表該標的目前正處於或超越歷史最高價位階（持續創新高）。")