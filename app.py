import streamlit as st
import yfinance as yf
import pandas as pd
import google.generativeai as genai
import matplotlib.pyplot as plt

# Configuration de la page Streamlit
st.set_page_config(page_title="Bot Trading IA - Mondial", layout="wide")

st.title("🎯 Bot d'Analyse Trading Technique & Fondamental (Mondial)")
st.markdown("Analyse technique (chandelles, indicateurs, pivots) et fondamentale (actualités en direct) sur toutes les actions US, Europe, Asie et cryptos.")

# ---------------------------------------------------------
# Configuration de la clé API & Modèle IA officiel
# ---------------------------------------------------------
API_KEY = "AQ.Ab8RN6KvFijAko4RVnTWf9Uf3qE4lVbXgrMsTXay1utBmqq5-w"
genai.configure(api_key=API_KEY)

def generate_ai_report(prompt_text):
    models_to_try = ['gemini-3.8-flash', 'gemini-1.5-flash', 'gemini-pro']
    error_details = []
    
    for m_name in models_to_try:
        try:
            m = genai.GenerativeModel(m_name)
            response = m.generate_content(prompt_text)
            if response and response.text:
                return response.text
        except Exception as e:
            error_details.append(f"Modèle `{m_name}` : {e}")
            
    return "### ⚠️ Erreur détaillée de l'API Gemini :\n\n" + "\n\n".join(error_details)

# ---------------------------------------------------------
# Dictionnaire enrichi (US, Europe, Asie, Cryptos, Forex...)
# ---------------------------------------------------------
ASSETS_DICTIONARY = {
    "🇺🇸 Actions USA (Wall Street)": {
        "Apple": "AAPL",
        "Nvidia": "NVDA",
        "Microsoft": "MSFT",
        "Amazon": "AMZN",
        "Alphabet (Google)": "GOOGL",
        "Meta (Facebook)": "META",
        "Tesla": "TSLA",
        "AMD": "AMD",
        "Berkshire Hathaway": "BRK-B",
        "Eli Lilly": "LLY",
        "Broadcom": "AVGO",
        "JPMorgan Chase": "JPM"
    },
    "🇪🇺 Actions Europe (Euronext, DAX, LSE)": {
        "TotalEnergies (France)": "TTE.PA",
        "LVMH (France)": "MC.PA",
        "ASML (Pays-Bas)": "ASML.AS",
        "SAP (Allemagne)": "SAP.DE",
        "Siemens (Allemagne)": "SIE.DE",
        "Sanofi (France)": "SAN.PA",
        "Schneider Electric (France)": "SU.PA",
        "Airbus (France/DE)": "AIR.PA",
        "Shell (UK/NL)": "SHEL.L",
        "Novo Nordisk (Danemark)": "NOVO-B.CO",
        "Ferrari (Italie)": "RACE.MI"
    },
    "🌏 Actions Asie & Pacifique": {
        "TSMC (Taïwan - ADR US)": "TSM",
        "Toyota (Japon)": "7203.T",
        "Sony (Japon)": "6758.T",
        "SoftBank (Japon)": "9984.T",
        "Tencent (Hong Kong)": "0700.HK",
        "Alibaba (Hong Kong)": "9988.HK",
        "Samsung Electronics (Corée)": "005930.KS",
        "Reliance Industries (Inde)": "RELIANCE.NS",
        "BHP Group (Australie)": "BHP.AX"
    },
    "📊 Indices Boursiers": {
        "S&P 500 (USA)": "^GSPC",
        "Nasdaq 100 (USA)": "^IXIC",
        "Dow Jones (USA)": "^DJI",
        "CAC 40 (France)": "^FCHI",
        "DAX 40 (Allemagne)": "^GDAXI",
        "FTSE 100 (Royaume-Uni)": "^FTSE",
        "Nikkei 225 (Japon)": "^N225",
        "Hang Seng (Hong Kong)": "^HSI"
    },
    "🛢️ Matières Premières": {
        "Pétrole Brent": "BZ=F",
        "Pétrole WTI": "CL=F",
        "Or (Gold)": "GC=F",
        "Argent (Silver)": "SI=F",
        "Gaz Naturel": "NG=F",
        "Cuivre": "HG=F"
    },
    "💱 Forex (Devises)": {
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
        "USD/JPY": "USDJPY=X",
        "AUD/USD": "AUDUSD=X",
        "USD/CAD": "USDCAD=X",
        "EUR/GBP": "EURGBP=X"
    },
    "🪙 Cryptomonnaies": {
        "Bitcoin (BTC/USD)": "BTC-USD",
        "Ethereum (ETH/USD)": "ETH-USD",
        "Solana (SOL-USD)": "SOL-USD",
        "Ripple (XRP-USD)": "XRP-USD",
        "Binance Coin (BNB-USD)": "BNB-USD"
    }
}

TIMEFRAME_MAPPING = {
    "M15": {"interval": "15m", "period": "14d"},
    "M30": {"interval": "30m", "period": "30d"},
    "H1":  {"interval": "1h",  "period": "60d"},
    "H4":  {"interval": "1h",  "period": "60d"},
    "D1":  {"interval": "1d",  "period": "1y"}
}

def get_recent_news(ticker_str):
    try:
        t = yf.Ticker(ticker_str)
        news = t.news
        headlines = []
        if news:
            for item in news[:5]:
                title = item.get('title') or item.get('content', {}).get('title', '')
                publisher = item.get('publisher') or item.get('content', {}).get('provider', {}).get('displayName', '')
                if title:
                    headlines.append(f"- {title} (Source: {publisher})")
        return headlines if headlines else ["Aucune actualité récente directement disponible."]
    except Exception:
        return ["Impossible de récupérer les actualités récentes pour cet actif."]

# ---------------------------------------------------------
# Barre latérale : Sélection globale
# ---------------------------------------------------------
st.sidebar.header("1. Sélection de l'Actif")

# Recherche libre universelle
custom_ticker_input = st.sidebar.text_input("🔍 Ticker libre (ex: BABA, 7203.T, TTE.PA...)", "").strip()

if custom_ticker_input:
    ticker_symbol = custom_ticker_input.upper()
    selected_asset_name = custom_ticker_input.upper()
    st.sidebar.info(f"Ticker personnalisé actif : `{ticker_symbol}`")
else:
    selected_category = st.sidebar.selectbox("Sélectionnez la Catégorie", list(ASSETS_DICTIONARY.keys()))
    selected_asset_name = st.sidebar.selectbox("Sélectionnez l'Actif", list(ASSETS_DICTIONARY[selected_category].keys()))
    ticker_symbol = ASSETS_DICTIONARY[selected_category][selected_asset_name]
    st.sidebar.markdown(f"**Ticker Yahoo Finance :** `{ticker_symbol}`")

with st.sidebar.expander("ℹ️ Suffixes boursiers mondiaux"):
    st.markdown("""
    Pour chercher n'importe quelle action mondiale, ajoutez son extension :
    * **France :** `.PA` (ex: `AIR.PA`)
    * **Allemagne :** `.DE` (ex: `BMW.DE`)
    * **Londres :** `.L` (ex: `BP.L`)
    * **Japon :** `.T` (ex: `7203.T`)
    * **Hong Kong :** `.HK` (ex: `0700.HK`)
    * **USA :** Pas de suffixe (ex: `NVDA`)
    """)

st.sidebar.success("🔑 Clé API pré-configurée avec succès !")

# ---------------------------------------------------------
# Application Principale
# ---------------------------------------------------------
st.subheader("2. Choisissez l'unité de temps pour l'analyse")

col1, col2, col3, col4, col5 = st.columns(5)
selected_timeframe = None
if col1.button("⚡ M15", use_container_width=True): selected_timeframe = "M15"
if col2.button("⏱️ M30", use_container_width=True): selected_timeframe = "M30"
if col3.button("📊 H1", use_container_width=True): selected_timeframe = "H1"
if col4.button("📈 H4", use_container_width=True): selected_timeframe = "H4"
if col5.button("📅 D1", use_container_width=True): selected_timeframe = "D1"

if selected_timeframe:
    tf_info = TIMEFRAME_MAPPING[selected_timeframe]
    
    with st.spinner(f"Chargement des données & actualités pour {selected_asset_name} ({selected_timeframe})..."):
        df = yf.download(ticker_symbol, period=tf_info["period"], interval=tf_info["interval"], progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        recent_news_list = get_recent_news(ticker_symbol)
        news_text = "\n".join(recent_news_list)

        if df.empty or 'Close' not in df.columns:
            st.error(f"Erreur : Impossible de récupérer les données pour `{ticker_symbol}`. Vérifiez la valeur ou le suffixe boursier (ex: `.PA`, `.DE`, `.T`).")
        else:
            df['MM50'] = df['Close'].rolling(window=50).mean()
            df['MM100'] = df['Close'].rolling(window=100).mean()
            df['MM200'] = df['Close'].rolling(window=200).mean()
            
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))

            exp1 = df['Close'].ewm(span=12, adjust=False).mean()
            exp2 = df['Close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = exp1 - exp2
            df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

            df_d = yf.download(ticker_symbol, period="5d", interval="1d", progress=False)
            if isinstance(df_d.columns, pd.MultiIndex):
                df_d.columns = df_d.columns.get_level_values(0)
            
            if len(df_d) >= 2:
                prev_day = df_d.iloc[-2]
                h, l, c = prev_day['High'], prev_day['Low'], prev_day['Close']
                pivot = (h + l + c) / 3
                r1 = (2 * pivot) - l
                r2 = pivot + (h - l)
                s1 = (2 * pivot) - h
                s2 = pivot - (h - l)
            else:
                pivot, r1, r2, s1, s2 = 0, 0, 0, 0, 0

            latest = df.iloc[-1]
            current_price = float(latest['Close'])
            mm50 = float(latest.get('MM50', 0)) if pd.notna(latest.get('MM50')) else 0.0
            mm100 = float(latest.get('MM100', 0)) if pd.notna(latest.get('MM100')) else 0.0
            mm200 = float(latest.get('MM200', 0)) if pd.notna(latest.get('MM200')) else 0.0
            rsi = float(latest.get('RSI', 0)) if pd.notna(latest.get('RSI')) else 0.0
            macd_line = float(latest.get('MACD', 0)) if pd.notna(latest.get('MACD')) else 0.0
            macd_signal = float(latest.get('MACD_Signal', 0)) if pd.notna(latest.get('MACD_Signal')) else 0.0

            prompt = f"""
            Tu es un système expert en trading quantitatif et analyse macroéconomique / fondamentale.
            Analyse l'actif **{selected_asset_name} ({ticker_symbol})** en unité de temps **{selected_timeframe}**.

            ### DONNÉES TECHNIQUES :
            - Prix actuel : {current_price:.2f}
            - MM50 = {mm50:.2f} | MM100 = {mm100:.2f} | MM200 = {mm200:.2f}
            - RSI (14) = {rsi:.2f}
            - MACD Line = {macd_line:.3f} | Signal = {macd_signal:.3f}
            - Pivots Fibonacci : S2 = {s2:.2f}, S1 = {s1:.2f}, Pivot = {pivot:.2f}, R1 = {r1:.2f}, R2 = {r2:.2f}

            ### ACTUALITÉS ET FLUX D'INFORMATIONS RÉCENTS :
            {news_text}

            Fournis un rapport complet structuré STRICTEMENT ainsi :

            ### 1. 📰 ANALYSE FONDAMENTALE ET ACTUALITÉS
            - Synthèse des dernières actualités majeures affectant l'actif.
            - Impact fondamental sur le prix à court/moyen terme (Haussier, Baisse, Neutre).
            - Facteurs macroéconomiques ou catalyseurs majeurs à surveiller.

            ---

            ### 2. 📊 SYNTHÈSE TENDANCE TECHNIQUE ({selected_timeframe})
            Résumé en 2-3 phrases de la configuration technique.

            ---

            ### 🟢 SCÉNARIO D'ACHAT (BUY / LONG) - {selected_timeframe}
            - **Point d'entrée recommandé :** [Prix exact ex: 107.50]
            - **Stop Loss (SL) :** [Prix exact ex: 105.20]
            - **Take Profit 1 (TP1) :** [Prix exact ex: 109.00]
            - **Take Profit 2 (TP2) :** [Prix exact ex: 111.50]
            - **Ratio Risque / Récompense (R/R) :** [ex: 1:2]
            - **Justification :** [Raison technique + alignment fondamental]

            ---

            ### 🔴 SCÉNARIO DE VENTE (SELL / SHORT) - {selected_timeframe}
            - **Point d'entrée recommandé :** [Prix exact ex: 108.50]
            - **Stop Loss (SL) :** [Prix exact ex: 110.10]
            - **Take Profit 1 (TP1) :** [Prix exact ex: 106.00]
            -
