import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.generativeai as genai
import matplotlib.pyplot as plt
import re
from datetime import datetime

# Configuration de la page Streamlit
st.set_page_config(page_title="Bot Trading IA - Mondial & ISIN", layout="wide")

st.title("🎯 Bot d'Analyse Trading Technique & Fondamental")
st.markdown("Analyse technique complète, graphique global ultra-lisible, journal de trading et gestion de l'historique.")

# ---------------------------------------------------------
# Liste des clés API Gemini (Système de rotation / Fallback)
# ---------------------------------------------------------
API_KEYS = [
    "AQ.Ab8RN6J07BTFUTUoWBM2cfsiUduTyV756t_c7L6i6SZxY7wgTg",
    "AQ.Ab8RN6KvFijAko4RVnTWf9Uf3qE4lVbXgrMsTXay1utBmqq5-w",
    "AQ.Ab8RN6JCQvTU9IjwjDzw6puDfrNtZllbOnggOM69BtXEKgshqg",
    "AQ.Ab8RN6I00i8wi5lYccvl0UHNBkTHAvQ6xZTQC6WQk3dIEOx1JQ"
]

def generate_ai_report(prompt_text):
    models_to_try = ['gemini-3.8-flash', 'gemini-1.5-flash', 'gemini-pro']
    error_details = []

    for api_key in API_KEYS:
        try:
            genai.configure(api_key=api_key)
            for m_name in models_to_try:
                try:
                    m = genai.GenerativeModel(m_name)
                    response = m.generate_content(prompt_text)
                    if response and response.text:
                        return response.text
                except Exception as e:
                    error_str = str(e)
                    error_details.append(f"Clé `{api_key[:8]}...` | Modèle `{m_name}` : {error_str}")
                    if "429" in error_str or "quota" in error_str.lower():
                        break
        except Exception as e:
            error_details.append(f"Erreur de configuration clé `{api_key[:8]}...` : {e}")

    return "### ⚠️ Erreur détaillée de l'API Gemini :\n\nToutes les clés API configurées ont dépassé leurs quotas ou ont rencontré une erreur.\n\n" + "\n\n".join(error_details)

# ---------------------------------------------------------
# Dictionnaire ultra-enrichi (Top 20+ actifs par catégorie)
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
        "Netflix": "NFLX",
        "Intel": "INTC",
        "JPMorgan Chase": "JPM",
        "Visa": "V",
        "Mastercard": "MA",
        "Bank of America": "BAC",
        "Coca-Cola": "KO",
        "PepsiCo": "PEP",
        "Walt Disney": "DIS",
        "Nike": "NKE",
        "Pfizer": "PFE",
        "Johnson & Johnson": "JNJ",
        "ExxonMobil": "XOM",
        "Chevron": "CVX",
        "Walmart": "WMT",
        "Palantir": "PLTR",
        "Super Micro Computer": "SMCI"
    },
    "🇪🇺 Actions Europe (Euronext, DAX, LSE)": {
        "TotalEnergies (France)": "TTE.PA",
        "LVMH (France)": "MC.PA",
        "ASML (Pays-Bas)": "ASML.AS",
        "SAP (Allemagne)": "SAP.DE",
        "Siemens (Allemagne)": "SIE.DE",
        "Sanofi (France)": "SAN.PA",
        "Airbus (France/DE)": "AIR.PA",
        "L'Oréal (France)": "OR.PA",
        "Schneider Electric (France)": "SU.PA",
        "Air Liquide (France)": "AI.PA",
        "BNP Paribas (France)": "BNP.PA",
        "AXA (France)": "CS.PA",
        "Hermès (France)": "RMS.PA",
        "Kering (France)": "KER.PA",
        "Stellantis (France/IT)": "STLAM.MI",
        "Volkswagen (Allemagne)": "VOW3.DE",
        "Allianz (Allemagne)": "ALV.DE",
        "Mercedes-Benz (Allemagne)": "MBG.DE",
        "BASF (Allemagne)": "BAS.DE",
        "Bayer (Allemagne)": "BAYN.DE",
        "Unilever (Royaume-Uni)": "ULVR.L",
        "Shell (Royaume-Uni)": "SHEL.L",
        "BP (Royaume-Uni)": "BP.L",
        "HSBC (Royaume-Uni)": "HSBA.L",
        "Banco Santander (Espagne)": "SAN.MC"
    },
    "🌏 Actions Asie & Pacifique": {
        "TSMC (Taïwan - ADR US)": "TSM",
        "Toyota (Japon)": "7203.T",
        "Sony (Japon)": "6758.T",
        "Tencent (Hong Kong)": "0700.HK",
        "Alibaba (Hong Kong)": "9988.HK",
        "Samsung Electronics (Corée du Sud)": "005930.KS",
        "SoftBank Group (Japon)": "9984.T",
        "Nintendo (Japon)": "7974.T",
        "Mitsubishi UFJ (Japon)": "8306.T",
        "Keyence (Japon)": "6861.T",
        "Tokyo Electron (Japon)": "8035.T",
        "Fast Retailing / Uniqlo (Japon)": "9983.T",
        "Honda (Japon)": "7267.T",
        "KDDI (Japon)": "9433.T",
        "Meituan (Hong Kong)": "3690.HK",
        "JD.com (Hong Kong)": "9618.HK",
        "Baidu (Hong Kong)": "9888.HK",
        "Xiaomi (Hong Kong)": "1810.HK",
        "BYD Company (Hong Kong)": "1211.HK",
        "SK Hynix (Corée du Sud)": "000660.KS"
    },
    "📊 Indices Boursiers": {
        "S&P 500 (USA)": "^GSPC",
        "Nasdaq 100 (USA)": "^IXIC",
        "Dow Jones Industrial Average (USA)": "^DJI",
        "Russell 2000 (USA)": "^RUT",
        "CAC 40 (France)": "^FCHI",
        "DAX 40 (Allemagne)": "^GDAXI",
        "Euro Stoxx 50 (Europe)": "^STOXX50E",
        "FTSE 100 (Royaume-Uni)": "^FTSE",
        "IBEX 35 (Espagne)": "^IBEX",
        "FTSE MIB (Italie)": "FTSEMIB.MI",
        "AEX (Pays-Bas)": "^AEX",
        "SMI (Suisse)": "^SSMI",
        "Nikkei 225 (Japon)": "^N225",
        "TOPIX (Japon)": "^TOPX",
        "Hang Seng (Hong Kong)": "^HSI",
        "Shanghai Composite (Chine)": "000030.SS",
        "CSI 300 (Chine)": "000300.SS",
        "Nifty 50 (Inde)": "^NSEI",
        "BSE Sensex (Inde)": "^BSESN",
        "ASX 200 (Australie)": "^AXJO",
        "IBOVESPA (Brésil)": "^BVSP",
        "IPC Mexico (Mexique)": "^MXX",
        "FTSE JSE Top 40 (Afrique du Sud)": "^J200.JO",
        "JSX Composite (Indonésie)": "^JKSE",
        "STI (Singapour)": "^STI"
    },
    "🛢️ Matières Premières": {
        "Pétrole Brent": "BZ=F",
        "Pétrole WTI (Light Crude)": "CL=F",
        "Or (Gold)": "GC=F",
        "Argent (Silver)": "SI=F",
        "Cuivre (Copper)": "HG=F",
        "Platinium": "PL=F",
        "Palladium": "PA=F",
        "Gaz Naturel (Natural Gas)": "NG=F",
        "Blé (Wheat)": "ZW=F",
        "Maïs (Corn)": "ZC=F",
        "Soja (Soybean)": "ZS=F",
        "Café (Coffee)": "KC=F",
        "Sucre (Sugar)": "SB=F",
        "Cacao (Cocoa)": "CC=F",
        "Coton (Cotton)": "CT=F",
        "Aluminium": "ALI=F",
        "Zinc": "ZNC=F",
        "Nickel": "NIC=F",
        "Bétail Vivant (Live Cattle)": "LE=F",
        "Porc Maigre (Lean Hogs)": "HE=F",
        "Avoine (Oats)": "ZO=F",
        "Riz (Rough Rice)": "ZR=F",
        "Essence RBOB (Gasoline)": "RB=F",
        "Fioul Domestique (Heating Oil)": "HO=F",
        "Fer (Iron Ore)": "TIO=F"
    },
    "💱 Forex (Devises)": {
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
        "USD/JPY": "USDJPY=X",
        "USD/CHF": "USDCHF=X",
        "AUD/USD": "AUDUSD=X",
        "USD/CAD": "USDCAD=X",
        "NZD/USD": "NZDUSD=X",
        "EUR/GBP": "EURGBP=X",
        "EUR/JPY": "EURJPY=X",
        "GBP/JPY": "GBPJPY=X",
        "EUR/CHF": "EURCHF=X",
        "AUD/JPY": "AUDJPY=X",
        "EUR/AUD": "EURAUD=X",
        "EUR/CAD": "EURCAD=X",
        "GBP/CHF": "GBPCHF=X",
        "CHF/JPY": "CHFJPY=X",
        "NZD/JPY": "NZDJPY=X",
        "AUD/CAD": "AUDCAD=X",
        "AUD/NZD": "AUDNZD=X",
        "CAD/JPY": "CADJPY=X",
        "USD/ZAR": "USDZAR=X",
        "USD/MXN": "USDMXN=X",
        "USD/TRY": "USDTRY=X",
        "USD/BRL": "USDBRL=X",
        "USD/SEK": "USDSEK=X"
    },
    "🪙 Cryptomonnaies": {
        "Bitcoin (BTC/USD)": "BTC-USD",
        "Ethereum (ETH/USD)": "ETH-USD",
        "Solana (SOL-USD)": "SOL-USD",
        "Binance Coin (BNB/USD)": "BNB-USD",
        "Ripple (XRP/USD)": "XRP-USD",
        "Cardano (ADA/USD)": "ADA-USD",
        "Dogecoin (DOGE/USD)": "DOGE-USD",
        "Avalanche (AVAX/USD)": "AVAX-USD",
        "Chainlink (LINK/USD)": "LINK-USD",
        "Polkadot (DOT/USD)": "DOT-USD",
        "Polygon (POL/USD)": "POL-USD",
        "Tron (TRX/USD)": "TRX-USD",
        "Shiba Inu (SHIB/USD)": "SHIB-USD",
        "Litecoin (LTC/USD)": "LTC-USD",
        "Uniswap (UNI/USD)": "UNI-USD",
        "Cosmos (ATOM/USD)": "ATOM-USD",
        "Monero (XMR/USD)": "XMR-USD",
        "Stellar (XLM/USD)": "XLM-USD",
        "Near Protocol (NEAR/USD)": "NEAR-USD",
        "Render (RENDER/USD)": "RENDER-USD",
        "Sui (SUI/USD)": "SUI-USD",
        "Aptos (APT/USD)": "APT-USD",
        "Arbitrum (ARB/USD)": "ARB-USD",
        "Pepe (PEPE/USD)": "PEPE-USD",
        "Toncoin (TON/USD)": "TON-USD"
    }
}

TIMEFRAME_MAPPING = {
    "M15":    {"interval": "15m", "period": "7d"},
    "M30":    {"interval": "30m", "period": "14d"},
    "H1":     {"interval": "1h",  "period": "30d"},
    "H4":     {"interval": "1h",  "period": "60d"},
    "D1":     {"interval": "1d",  "period": "1y"},
    "Mois":   {"interval": "1mo", "period": "5y"},
    "Années": {"interval": "1mo", "period": "max"}
}

def get_recent_news(ticker_str):
    try:
        t = yf.Ticker(ticker_str)
        news = t.news
        headlines = []
        if news and isinstance(news, list):
            for item in news[:5]:
                title = item.get('title') or item.get('content', {}).get('title', '')
                publisher = item.get('publisher') or item.get('content', {}).get('provider', {}).get('displayName', '')
                if title:
                    headlines.append(f"- {title} (Source: {publisher})")
        return headlines if headlines else ["Aucune actualité récente directement disponible."]
    except Exception:
        return ["Impossible de récupérer les actualités récentes pour cet actif."]

# ---------------------------------------------------------
# Graphique technique global ultra-grand et très lisible
# ---------------------------------------------------------
def draw_global_chart(df, pivot, r1, r2, s1, s2, asset_name, timeframe):
    fig, ax = plt.subplots(figsize=(13, 7))  # Graphique plus large et plus haut pour une lisibilité maximale
    
    df_reset = df.reset_index()
    x = df_reset.index.values
    opens = df_reset['Open'].values
    highs = df_reset['High'].values
    lows = df_reset['Low'].values
    closes = df_reset['Close'].values
    
    up = closes >= opens
    down = closes < opens

    up_color = '#26a69a'
    down_color = '#ef5350'

    ax.vlines(x[up], lows[up], highs[up], color=up_color, linewidth=1.3)
    ax.vlines(x[down], lows[down], highs[down], color=down_color, linewidth=1.3)

    body_bottom = np.minimum(opens, closes)
    body_height = np.abs(closes - opens)
    body_height[body_height == 0] = 0.01

    ax.bar(x[up], body_height[up], bottom=body_bottom[up], color=up_color, width=0.65)
    ax.bar(x[down], body_height[down], bottom=body_bottom[down], color=down_color, width=0.65)

    if 'MM50' in df_reset.columns and df_reset['MM50'].notna().any():
        ax.plot(x, df_reset['MM50'], label='MM 50', color='orange', linewidth=1.8)
    if 'MM200' in df_reset.columns and df_reset['MM200'].notna().any():
        ax.plot(x, df_reset['MM200'], label='MM 200', color='purple', linewidth=1.8)

    if pivot > 0:
        ax.axhline(y=pivot, color='yellow', linestyle='--', alpha=0.85, label=f'Pivot: {pivot:.2f}')
        ax.axhline(y=r1, color='red', linestyle=':', alpha=0.65, label=f'R1 Fib: {r1:.2f}')
        ax.axhline(y=r2, color='darkred', linestyle=':', alpha=0.65, label=f'R2 Fib: {r2:.2f}')
        ax.axhline(y=s1, color='limegreen', linestyle=':', alpha=0.65, label=f'S1 Fib: {s1:.2f}')
        ax.axhline(y=s2, color='green', linestyle=':', alpha=0.65, label=f'S2 Fib: {s2:.2f}')

    n_ticks = min(7, len(df_reset))
    step = max(1, len(df_reset) // n_ticks)
    tick_indices = list(range(0, len(df_reset), step))
    date_col = 'Datetime' if 'Datetime' in df_reset.columns else 'Date'
    tick_labels = [str(df_reset.iloc[i][date_col]).split()[0] for i in tick_indices]
    
    ax.set_xticks(tick_indices)
    ax.set_xticklabels(tick_labels, rotation=25, fontsize=11)

    ax.set_facecolor('#0e1117')
    fig.patch.set_facecolor('#0e1117')
    ax.tick_params(colors='white', labelsize=11)
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    ax.title.set_color('white')
    for spine in ax.spines.values():
        spine.set_edgecolor('gray')

    ax.set_title(f"📈 Vue d'ensemble technique — {asset_name} ({timeframe})", fontsize=15, fontweight='bold', pad=15)
    ax.legend(loc='upper left', facecolor='#262730', edgecolor='none', labelcolor='white', fontsize=10)
    ax.grid(True, linestyle=':', alpha=0.45, color='gray')

    plt.tight_layout()
    return fig

# Initialisation des états de session
if "trade_history" not in st.session_state:
    st.session_state.trade_history = []
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "new"

# ---------------------------------------------------------
# Barre latérale : Sélection globale & Historique
# ---------------------------------------------------------
st.sidebar.header("1. Sélection de l'Actif")

custom_ticker_input = st.sidebar.text_input("🔍 Ticker libre (ex: AAPL, TSLA...)", "").strip()
custom_isin_input = st.sidebar.text_input("🔍 Ou code ISIN (ex: FR0000120271)", "").strip()

if custom_ticker_input:
    ticker_symbol = custom_ticker_input.upper()
    selected_asset_name = custom_ticker_input.upper()
    st.sidebar.info(f"Ticker actif : `{ticker_symbol}`")
elif custom_isin_input:
    ticker_symbol = custom_isin_input.upper()
    selected_asset_name = f"ISIN: {ticker_symbol}"
    st.sidebar.info(f"Code ISIN actif : `{ticker_symbol}`")
else:
    selected_category = st.sidebar.selectbox("Sélectionnez la Catégorie", list(ASSETS_DICTIONARY.keys()))
    selected_asset_name = st.sidebar.selectbox("Sélectionnez l'Actif", list(ASSETS_DICTIONARY[selected_category].keys()))
    ticker_symbol = ASSETS_DICTIONARY[selected_category][selected_asset_name]
    st.sidebar.markdown(f"**Ticker Yahoo Finance :** `{ticker_symbol}`")

# --- Menu Historique & Gestion des suppressions ---
st.sidebar.markdown("---")
st.sidebar.header("📜 Historique des Requêtes")

if st.session_state.trade_history:
    history_options = ["-- Nouvelle Analyse --"] + [f"{item['id']} | {item['timestamp']} - {item['asset']} ({item['tf']})" for item in st.session_state.trade_history]
    
    current_index = 0
    if st.session_state.active_tab != "new":
        for idx, opt in enumerate(history_options[1:], start=1):
            if opt.startswith(f"{st.session_state.active_tab} |"):
                current_index = idx
                break

    selected_history = st.sidebar.selectbox("Consulter une analyse passée :", history_options, index=current_index)
    
    if selected_history == "-- Nouvelle Analyse --":
        if st.session_state.active_tab != "new":
            st.session_state.active_tab = "new"
            st.rerun()
    else:
        selected_id = int(selected_history.split(" | ")[0])
        if st.session_state.active_tab != selected_id:
            st.session_state.active_tab = selected_id
            st.rerun()

    with st.sidebar.expander("🗑️ Gérer / Supprimer l'historique"):
        all_labels = [f"{item['id']} | {item['timestamp']} - {item['asset']} ({item['tf']})" for item in st.session_state.trade_history]
        to_delete_labels = st.multiselect("Sélectionner à supprimer :", all_labels)
        
        col_del1, col_del2 = st.columns(2)
        with col_del1:
            if st.button("Supprimer la sélection", use_container_width=True) and to_delete_labels:
                ids_to_del = [int(lbl.split(" | ")[0]) for lbl in to_delete_labels]
                st.session_state.trade_history = [item for item in st.session_state.trade_history if item['id'] not in ids_to_del]
                if st.session_state.active_tab in ids_to_del:
                    st.session_state.active_tab = "new"
                st.rerun()
        with col_del2:
            if st.button("Tout supprimer", use_container_width=True):
                st.session_state.trade_history = []
                st.session_state.active_tab = "new"
                st.rerun()

else:
    st.sidebar.info("Aucune analyse enregistrée.")
    if st.session_state.active_tab != "new":
        st.session_state.active_tab = "new"

# ---------------------------------------------------------
# Affichage Principal (Nouvelle Analyse ou Archive)
# ---------------------------------------------------------
if st.session_state.active_tab == "new":
    st.subheader("2. Paramétrage & Lancement de l'Analyse")
    
    col_tf, col_btn = st.columns([2, 1])
    with col_tf:
        selected_timeframe = st.selectbox("Choisissez l'unité de temps", list(TIMEFRAME_MAPPING.keys()))
    
    st.markdown("")
    run_analysis = st.button("🚀 Lancer l'analyse", type="primary", use_container_width=True)

    if run_analysis:
        tf_info = TIMEFRAME_MAPPING[selected_timeframe]
        
        with st.spinner(f"Chargement des données & actualités pour {selected_asset_name} ({selected_timeframe})..."):
            df = yf.download(ticker_symbol, period=tf_info["period"], interval=tf_info["interval"], progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            recent_news_list = get_recent_news(ticker_symbol)
            news_text = "\n".join(recent_news_list)

            if df.empty or 'Close' not in df.columns:
                st.error(f"Erreur : Impossible de récupérer les données pour `{ticker_symbol}`. Vérifiez que le code ISIN ou le ticker est valide.")
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
                    h, l, c = float(prev_day['High']), float(prev_day['Low']), float(prev_day['Close'])
                    pivot = (h + l + c) / 3
                    r1 = pivot + 0.382 * (h - l)
                    r2 = pivot + 0.618 * (h - l)
                    s1 = pivot - 0.382 * (h - l)
                    s2 = pivot - 0.618 * (h - l)
                else:
                    pivot, r1, r2, s1, s2 = 0.0, 0.0, 0.0, 0.0, 0.0

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
                - **POINTS DE PIVOT FIBONACCI :**
                  * Résistance 2 (R2) : {r2:.2f}
                  * Résistance 1 (R1) : {r1:.2f}
                  * Point Pivot Central (P) : {pivot:.2f}
                  * Support 1 (S1) : {s1:.2f}
                  * Support 2 (S2) : {s2:.2f}

                ### ACTUALITÉS ET FLUX D'INFORMATIONS RÉCENTS :
                {news_text}

                Fournis un rapport complet structuré STRICTEMENT ainsi (utilise EXACTEMENT des valeurs numériques pures pour les prix) :

                ### 1. 📰 ANALYSE FONDAMENTALE ET ACTUALITÉS
                - Synthèse des dernières actualités majeures affectant l'actif.
                - Impact fondamental sur le prix à court/moyen terme (Haussier, Baisse, Neutre).
                - Facteurs macroéconomiques ou catalyseurs majeurs à surveiller.

                ---

                ### 2. 📊 SYNTHÈSE TENDANCE TECHNIQUE ET PIVOTS FIBONACCI ({selected_timeframe})
                - Position actuelle du prix par rapport au Pivot Central, S1/S2 et R1/R2.
                - Analyse croisée avec les moyennes mobiles (MM50/100/200), RSI et MACD.

                ---

                ### 3. ⭐ SCÉNARIO À PRIVILÉGIER ET RAISONNEMENT
                - Indique clairement le scénario à privilégier entre l'Achat (LONG) et la Vente (SHORT).
                - Explique l'analyse croisée (fondamentale + technique + pivots) qui a poussé à ce raisonnement stratégique.

                ---

                ### 🟢 SCÉNARIO D'ACHAT (BUY / LONG) - {selected_timeframe}
                - Point d'entrée recommandé : {current_price:.2f}
                - Stop Loss : {s1:.2f}
                - Take Profit 1 : {r1:.2f}
                - Take Profit 2 : {r2:.2f}
                - Ratio Risque / Récompense (R/R) : 1:2
                - Justification : [Explication]

                ---

                ### 🔴 SCÉNARIO DE VENTE (SELL / SHORT) - {selected_timeframe}
                - Point d'entrée recommandé : {current_price:.2f}
                - Stop Loss : {r1:.2f}
                - Take Profit 1 : {s1:.2f}
                - Take Profit 2 : {s2:.2f}
                - Ratio Risque / Récompense (R/R) : 1:2
                - Justification : [Explication]
                """

                with st.spinner("Génération de l'analyse globale (Technique + Fondamentale)..."):
                    ai_text = generate_ai_report(prompt)

                timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                new_id = (max([item['id'] for item in st.session_state.trade_history]) + 1) if st.session_state.trade_history else 1
                
                new_entry = {
                    "id": new_id,
                    "timestamp": timestamp_str,
                    "asset": selected_asset_name,
                    "ticker": ticker_symbol,
                    "tf": selected_timeframe,
                    "price": current_price,
                    "report": ai_text,
                    "df": df,
                    "pivot": pivot,
                    "r1": r1, "r2": r2, "s1": s1, "s2": s2,
                    "news": recent_news_list,
                    "executed": False,
                    "result": "En cours / Indéterminé"
                }
                
                st.session_state.trade_history.append(new_entry)
                st.session_state.active_tab = new_id
                st.rerun()

else:
    # Mode consultation d'une analyse de l'historique
    entry = next((item for item in st.session_state.trade_history if item['id'] == st.session_state.active_tab), None)
    
    if entry:
        if st.button("⬅️ Effectuer une nouvelle analyse"):
            st.session_state.active_tab = "new"
            st.rerun()

        st.markdown(f"## 📜 Analyse Archivée : {entry['asset']} ({entry['tf']}) — {entry['timestamp']}")
        st.markdown(f"**Ticker :** `{entry['ticker']}` | **Prix au moment de l'analyse :** {entry['price']:.2f}")
        
        df = entry['df']
        pivot, r1, r2, s1, s2 = entry['pivot'], entry['r1'], entry['r2'], entry['s1'], entry['s2']

        # GRAPHIQUE UNIQUE : Vue d'ensemble technique globale ultra-lisible
        st.markdown("---")
        fig_global = draw_global_chart(df, pivot, r1, r2, s1, s2, entry['asset'], entry['tf'])
        st.pyplot(fig_global)
        plt.close(fig_global)

        st.markdown("---")
        with st.expander("📰 Voir les flux d'actualités capturés lors de l'analyse", expanded=False):
            for headline in entry['news']:
                st.write(headline)

        st.markdown("---")
        st.markdown("### 📊 Rapport d'Analyse Global")
        st.markdown(entry['report'])

        # --- Suivi du trade ---
        st.markdown("---")
        st.markdown("### 📋 Suivi de la Position")
        col_a, col_b = st.columns(2)
        
        with col_a:
            trade_executed = st.radio(
                "Trade réalisé ?", 
                ["Non", "Oui"], 
                index=1 if entry['executed'] else 0, 
                key=f"exec_{entry['id']}"
            )
            entry['executed'] = (trade_executed == "Oui")
            
        with col_b:
            if entry['executed']:
                result_options = ["En cours / Indéterminé", "Gagnant 🟢", "Perdant 🔴"]
                current_res_idx = result_options.index(entry['result']) if entry['result'] in result_options else 0
                trade_result = st.radio(
                    "Résultat du trade :", 
                    result_options, 
                    index=current_res_idx,
                    key=f"res_{entry['id']}"
                )
                entry['result'] = trade_result
            else:
                entry['result'] = "N/A"
                st.info("Cochez 'Oui' à 'Trade réalisé' pour renseigner le résultat.")

        # --- Chat interactif spécifique à l'archive (Isolé par ID unique de l'analyse) ---
        st.markdown("---")
        st.markdown("### 💬 Affiner l'analyse avec Gemini")
        st.markdown("Posez vos questions complémentaires sur ce trade :")

        chat_key = f"chat_history_unique_{entry['id']}_{entry['ticker']}"
        if chat_key not in st.session_state:
            st.session_state[chat_key] = []

        for message in st.session_state[chat_key]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if user_query := st.chat_input("Ex: Quel serait un meilleur niveau de SL si la volatilité augmente ?", key=f"chat_input_unique_{entry['id']}"):
            st.session_state[chat_key].append({"role": "user", "content": user_query})
            with st.chat_message("user"):
                st.markdown(user_query)

            with st.chat_message("assistant"):
                with st.spinner("Gemini analyse votre question..."):
                    conversation_history = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state[chat_key][:-1]])
                    
                    chat_prompt = f"""
                    Tu es un assistant expert en trading et analyse financière.
                    Contexte de l'actif analysé :
                    - Actif : {entry['asset']} ({entry['ticker']})
                    - Unité de temps : {entry['tf']}
                    - Prix actuel lors de l'analyse : {entry['price']:.2f}
                    - Rapport d'analyse initial :
                    {entry['report']}

                    Historique de la conversation :
                    {conversation_history}

                    Nouvelle question de l'utilisateur : {user_query}

                    Réponds de manière précise et professionnelle.
                    """
                    
                    reply = generate_ai_report(chat_prompt)
                    st.markdown(reply)
                    st.session_state[chat_key].append({"role": "assistant", "content": reply})
    else:
        st.session_state.active_tab = "new"
        st.rerun()
