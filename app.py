import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import time
import requests
from io import StringIO

# הגדרות עמוד
st.set_page_config(page_title="Magic Formula Screener", layout="wide", page_icon="📈")
st.title("📈 Magic Formula Screener")

@st.cache_data
def get_sp500_tickers():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    headers = {'User-Agent': 'Mozilla/5.0'}
    html = requests.get(url, headers=headers).text
    # הנה התיקון: עטפנו את ה-html ב-StringIO
    table = pd.read_html(StringIO(html))[0]
    filtered = table[~table['GICS Sector'].isin(['Financials', 'Utilities'])]
    return filtered['Symbol'].tolist()

def calculate_magic_formula(ticker_symbol, min_market_cap):
    ticker = yf.Ticker(ticker_symbol)
    try:
        info = ticker.info
        bs = ticker.balance_sheet
        inc = ticker.income_stmt
        
        if bs.empty or inc.empty: return None
        market_cap = info.get('marketCap', 0)
        if market_cap < min_market_cap: return None

        ebit = inc.loc['EBIT'].iloc[0] if 'EBIT' in inc.index else None
        total_debt = bs.loc['Total Debt'].iloc[0] if 'Total Debt' in bs.index else 0
        cash = bs.loc['Cash And Cash Equivalents'].iloc[0] if 'Cash And Cash Equivalents' in bs.index else 0
        current_assets = bs.loc['Total Current Assets'].iloc[0] if 'Total Current Assets' in bs.index else 0
        current_liabilities = bs.loc['Total Current Liabilities'].iloc[0] if 'Total Current Liabilities' in bs.index else 0
        net_fixed_assets = bs.loc['Net PPE'].iloc[0] if 'Net PPE' in bs.index else 0
        
        if ebit is None: return None
        ev = market_cap + total_debt - cash
        net_working_capital = current_assets - current_liabilities
        
        if ev <= 0 or (net_working_capital + net_fixed_assets) <= 0: return None
        
        return {
            'Ticker': ticker_symbol,
            'Company Name': info.get('shortName', ticker_symbol),
            'Market Cap ($B)': round(market_cap / 1e9, 2),
            'Earnings Yield': ebit / ev,
            'ROC': ebit / (net_working_capital + net_fixed_assets)
        }
    except: return None

# תפריט צד (Sidebar)
st.sidebar.header("הגדרות סריקה")
num_stocks = st.sidebar.slider("כמה מניות לסרוק? (10-500)", 10, 500, 30)
min_cap = st.sidebar.number_input("שווי שוק מינימלי (במיליארדים)", min_value=1, value=1) * 1e9

if st.sidebar.button("התחל סריקה 🚀"):
    tickers = get_sp500_tickers()
    tickers_to_run = tickers[:num_stocks]
    
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, ticker in enumerate(tickers_to_run):
        status_text.text(f"סורק את: {ticker} ({i+1}/{len(tickers_to_run)})")
        data = calculate_magic_formula(ticker, min_cap)
        if data: results.append(data)
        progress_bar.progress((i + 1) / len(tickers_to_run))
        time.sleep(1)
        
    df = pd.DataFrame(results)
    
    if not df.empty:
        df['EY_Rank'] = df['Earnings Yield'].rank(ascending=False)
        df['ROC_Rank'] = df['ROC'].rank(ascending=False)
        df['Combined_Score'] = df['EY_Rank'] + df['ROC_Rank']
        df = df.sort_values('Combined_Score').reset_index(drop=True)
        
        st.success("הסריקה הושלמה בהצלחה!")
        
        # גרף עמודות אינטראקטיבי
        top_30 = df.head(30)
        fig = px.bar(
            top_30, x='Ticker', y='Earnings Yield',
            hover_name='Company Name', hover_data=['ROC', 'Market Cap ($B)', 'Combined_Score'],
            color='Combined_Score', color_continuous_scale='Viridis_r',
            title='Top Magic Formula Stocks'
        )
        fig.update_layout(template='plotly_dark', xaxis={'categoryorder': 'array', 'categoryarray': top_30['Ticker']})
        st.plotly_chart(fig, use_container_width=True)
        
        # טבלת נתונים
        st.dataframe(df, use_container_width=True)
        
        # כפתור הורדה
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 הורד נתונים כקובץ CSV",
            data=csv,
            file_name='magic_formula_results.csv',
            mime='text/csv',
        )
    else:
        st.error("לא נמשכו נתונים. נסה שוב מאוחר יותר.")
