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
    table = pd.read_html(StringIO(html))[0]
    filtered = table[~table['GICS Sector'].isin(['Financials', 'Utilities'])]
    return filtered[['Symbol', 'GICS Sector']].to_dict('records')

def calculate_magic_formula(ticker_symbol, sector, min_market_cap, max_peg):
    ticker = yf.Ticker(ticker_symbol)
    try:
        info = ticker.info
        bs = ticker.balance_sheet
        inc = ticker.income_stmt
        
        if bs.empty or inc.empty: return None
        market_cap = info.get('marketCap', 0)
        if market_cap < min_market_cap: return None

        # משיכת PEG עם גיבוי לשם המשתנה החדש של Yahoo
        peg = info.get('trailingPegRatio') or info.get('pegRatio')
        if max_peg is not None and peg is not None and peg > max_peg:
            return None

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
        
        # חישוב באחוזים כדי שיהיה נוח בעין
        earnings_yield = (ebit / ev) * 100
        roc = (ebit / (net_working_capital + net_fixed_assets)) * 100
        
        return {
            'Ticker': ticker_symbol,
            'Company Name': info.get('shortName', ticker_symbol),
            'Sector': sector,
            'Market Cap ($B)': round(market_cap / 1e9, 2),
            'PEG Ratio': peg,
            'Earnings Yield (%)': earnings_yield,
            'ROC (%)': roc
        }
    except: return None

# שליפת נתוני הבסיס לטובת המסננים
all_stock_data = get_sp500_tickers()
all_sectors = sorted(list(set([item['GICS Sector'] for item in all_stock_data])))

# תפריט צד (Sidebar)
st.sidebar.header("הגדרות סריקה")
num_stocks = st.sidebar.slider("כמה מניות לסרוק? (10-500)", 10, 500, 30)
min_cap = st.sidebar.number_input("שווי שוק מינימלי (במיליארדים)", min_value=1, value=1) * 1e9

st.sidebar.subheader("מסננים מתקדמים")
selected_sectors = st.sidebar.multiselect("סינון סקטורים (השאר ריק כדי לסרוק הכל)", all_sectors)
max_peg_input = st.sidebar.number_input("PEG מקסימלי (השאר 0 ללא סינון)", min_value=0.0, value=0.0, step=0.1)
max_peg = max_peg_input if max_peg_input > 0 else None

if st.sidebar.button("התחל סריקה 🚀"):
    if selected_sectors:
        tickers_to_run = [item for item in all_stock_data if item['GICS Sector'] in selected_sectors][:num_stocks]
    else:
        tickers_to_run = all_stock_data[:num_stocks]
    
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    if len(tickers_to_run) == 0:
        st.warning("לא נמצאו מניות התואמות לסינון הסקטורים שבחרת.")
    else:
        for i, item in enumerate(tickers_to_run):
            ticker = item['Symbol']
            sector = item['GICS Sector']
            status_text.text(f"סורק את: {ticker} ({i+1}/{len(tickers_to_run)})")
            
            data = calculate_magic_formula(ticker, sector, min_cap, max_peg)
            if data: results.append(data)
            
            progress_bar.progress((i + 1) / len(tickers_to_run))
            time.sleep(1)
            
        df = pd.DataFrame(results)
        
        if not df.empty:
            df['EY_Rank'] = df['Earnings Yield (%)'].rank(ascending=False)
            df['ROC_Rank'] = df['ROC (%)'].rank(ascending=False)
            df['Combined_Score'] = df['EY_Rank'] + df['ROC_Rank']
            df = df.sort_values('Combined_Score').reset_index(drop=True)
            
            status_text.empty()
            st.success("הסריקה הושלמה בהצלחה! 🎈")
            st.balloons() # אנימציה קטנה של הצלחה
            
            # גרף עמודות אינטראקטיבי - עכשיו צבוע לפי סקטורים!
            st.subheader("📊 התפלגות המניות המובילות")
            top_30 = df.head(30)
            fig = px.bar(
                top_30, x='Ticker', y='Earnings Yield (%)',
                hover_name='Company Name', hover_data=['Sector', 'ROC (%)', 'Market Cap ($B)', 'Combined_Score'],
                color='Sector', # הצבע הוא לפי הסקטור, נותן מראה הרבה יותר חי
                title='Top Magic Formula Stocks by Sector'
            )
            fig.update_layout(template='plotly_dark', xaxis={'categoryorder': 'array', 'categoryarray': top_30['Ticker']})
            st.plotly_chart(fig, use_container_width=True)
            
            # טבלת נתונים עם עיצוב אינטראקטיבי
            st.subheader("📑 נתונים מלאים")
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Ticker": st.column_config.TextColumn("סימול"),
                    "Company Name": st.column_config.TextColumn("שם חברה"),
                    "Sector": st.column_config.TextColumn("סקטור"),
                    "Market Cap ($B)": st.column_config.NumberColumn("שווי שוק ($B)", format="$%.2f"),
                    "PEG Ratio": st.column_config.NumberColumn("PEG", format="%.2f"),
                    "Earnings Yield (%)": st.column_config.NumberColumn("תשואת רווח", format="%.2f%%"),
                    "ROC (%)": st.column_config.NumberColumn("ROC", format="%.2f%%"),
                    "Combined_Score": st.column_config.ProgressColumn(
                        "ציון משולב (נמוך=טוב)",
                        min_value=0,
                        max_value=int(df['Combined_Score'].max())
                    )
                }
            )
            
            # כפתור הורדה
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 הורד נתונים כקובץ CSV",
                data=csv,
                file_name='magic_formula_results.csv',
                mime='text/csv',
            )
        else:
            st.error("לא נמשכו נתונים (או שכל המניות סוננו החוצה על ידי מסנן ה-PEG/שווי שוק).")
