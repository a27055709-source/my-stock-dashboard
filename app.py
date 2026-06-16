import streamlit as st
import yfinance as yf
import pandas as pd
import datetime

# --- 網頁基本設定 ---
st.set_page_config(
    page_title="台股天價回檔佈局儀表板",
    page_icon="📈",
    layout="wide"  # 使用寬版排版，讓手機與電腦檢視都很舒適
)

# --- 標題與即時時間 ---
current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
st.title("📈 台股歷史最高價回檔計算儀表板")
st.markdown(f"**現在時間：** `{current_time}` *(每次重新整理網頁時會同步更新)*")

# --- 核心數據抓取與修正函式 ---
@st.cache_data(ttl=300)  # 快取機制：5分鐘內重複讀取會直接使用暫存
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
                # 1. 抓取盤中即時價格 (強制抓今日 1 分鐘 K 線以防延遲)
                today_data = ticker_obj.history(period="1d", interval="1m")
                if not today_data.empty:
                    realtime_price = today_data['Close'].iloc[-1]
                else:
                    realtime_price = hist['Close'].iloc[-1]

                # =========================================================
                #  通用型動態分割與除權息修正演算法 (處理歷史天價)
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

                # 2. 找出修正過後實質的歷史最高價
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

# 利用 Streamlit 的 columns 做出橫向並排的輸入框
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

# 準備轉換成表格的資料結構與橫列標題
row_headers = [
    "歷史最高價 (基準)", 
    "盤中即時價", 
    "目前回檔 %", # [新加入欄位]
    "回檔 10%", 
    "回檔 15%", 
    "回檔 20%", 
    "回檔 25%", 
    "回檔 30%"
]

# 計算各標的各個欄位的數值
matrix_data = {name: [] for name in targets}
for name in targets:
    ath = user_ath_prices[name]
    realtime = data_source[name]["realtime"]
    
    # 計算目前即時價距離天價的回檔百分比
    if ath > 0:
        if realtime >= ath:
            drawdown_pct = 0.0  # 持續創新高顯示 0%
        else:
            drawdown_pct = ((realtime - ath) / ath) * 100
    else:
        drawdown_pct = 0.0
        
    matrix_data[name].append(ath)
    matrix_data[name].append(realtime)
    matrix_data[name].append(drawdown_pct) # 存入回檔百分比
    matrix_data[name].append(ath * 0.90)   # 10%
    matrix_data[name].append(ath * 0.85)   # 15%
    matrix_data[name].append(ath * 0.80)   # 20%
    matrix_data[name].append(ath * 0.75)   # 25%
    matrix_data[name].append(ath * 0.70)   # 30%

# 將資料組合為 Pandas DataFrame (行列互換架構)
df = pd.DataFrame(matrix_data, index=row_headers)

# =========================================================
#  表格動態著色與格式化邏輯
# =========================================================
def highlight_breakthrough(row):
    """
    自訂表格著色：
    1. 當即時價跌破回檔目標價時，該回檔級距格子亮黃色。
    """
    styles = [''] * len(row)
    
    if row.name in ["回檔 10%", "回檔 15%", "回檔 20%", "回檔 25%", "回檔 30%"]:
        for col_idx, name in enumerate(row.index):
            realtime_p = matrix_data[name][1]  # 即時價
            target_p = row[name]               # 回檔價
            
            if realtime_p <= target_p:
                styles[col_idx] = 'background-color: #FFFFCC; color: black; font-weight: bold;'
    return styles

def format_value(val, row_name):
    """
    自訂格式化：
    讓『目前回檔 %』這列顯示百分比符號，其餘顯示一般兩位小數價格。
    """
    if row_name == "目前回檔 %":
        return f"{val:.2f}%" if val == 0 else f"{val:.2f}%"
    return f"{val:.2f}"

# 由於 Streamlit 的 format 接受函數，我們利用一個客製化的 DataFrame 渲染
styled_df = df.style.apply(highlight_breakthrough, axis=1)

# 套用逐行/逐格的文字格式化
for row_name in row_headers:
    row_idx = df.index.get_loc(row_name)
    if row_name == "目前回檔 %":
        styled_df = styled_df.format(lambda x: f"{x:.2f}%", subset=pd.IndexSlice[[row_name], :])
    else:
        styled_df = styled_df.format(lambda x: f"{x:.2f}", subset=pd.IndexSlice[[row_name], :])

# 渲染至網頁上
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