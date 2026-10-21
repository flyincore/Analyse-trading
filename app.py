import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import os
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Configuration de la page Streamlit avec un thème global sombre / carbone
st.set_page_config(page_title="Bot Trading IA - Version Institutionnelle", layout="wide")

# Injection de style CSS personnalisé (effet carbone / sombre professionnel)
st.markdown("""
    <style>
    .stApp {
        background-color: #12141a;
        color: #e0e0e0;
    }
    sidebar .stSidebar {
        background-color: #1a1d24;
    }
    .stButton>button {
        background: linear-gradient(135deg, #2b313b 0%, #1f232a 100%);
        color: #ffffff;
        border: 1px solid #3a3f4b;
        border-radius: 6px;
        font-weight: 600;
    }
    .stButton>button:hover {
        border-color: #26a69a;
        color: #26a69a;
    }
    .metric-card {
        background-color: #1a1d24;
        border: 1px solid #2a2e39;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎯 Bot d'Analyse Trading Pro — Suite Institutionnelle")
st.markdown("Analyse technique & fondamentale, multi-timeframe incluant le **Scalping**, score de confluence, gestion du SL en Break-Even et journal de trading.")

# ---------------------------------------------------------
# GESTION DE LA PERSISTANCE DE L'HISTORIQUE (FICHIER LOCAL)
# ---------------------------------------------------------
HISTORY_FILE = "trade_history.json"

def load_persistent_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

if "trade_history" not in st.session_state:
    st.session_state.trade_history = load_persistent_history()

if "active_tab" not in st.session_state:
    st.session_state.active_tab = "new"
if "current_analysis" not in st.session_state:
    st.session_state.current_analysis = None

# ---------------------------------------------------------
# CONFIGURATION KIE.AI & MOTEUR D'ANALYSE HYBRIDE
# ---------------------------------------------------------
KIE_API_KEY = "e1d8051846b1cdd140d743826770a614"
KIE_ENDPOINT = "https://api.kie.ai/v1/chat/completions"

def generate_ai_report(prompt_text, data_context=None):
    # 1. Tentative d'appel via Kie.ai
    if KIE_API_KEY:
        for model_name in ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-1.5-flash"]:
            try:
                headers = {
                    "Authorization": f"Bearer {KIE_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt_text}],
                    "temperature": 0.3
                }
                res = requests.post(KIE_ENDPOINT, headers=headers, json=payload, timeout=12)
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, dict):
                        if "choices" in data and len(data["choices"]) > 0:
                            content = data["choices"][0].get("message", {}).get("content", "")
                            if content:
                                return f"*(Rapport généré via Kie.ai - {model_name})*\n\n" + content
                        for key in ["content", "response", "output", "text", "result"]:
                            if key in data and data[key]:
                                return f"*(Rapport généré via Kie.ai - {model_name})*\n\n" + str(data[key])
            except Exception:
                pass

    # 2. Secours Algorithmique Déterministe (Empêche tout blocage d'analyse)
    if data_context:
        price = data_context.get("price", 0)
        pivot = data_context.get("pivot", 0)
        r1 = data_context.get("r1", 0)
        r2 = data_context.get("r2", 0)
        s1 = data_context.get("s1", 0)
        s2 = data_context.get("s2", 0)
        trend = data_context.get("mtf_trend", "Neutre")
        rsi = data_context.get("rsi", 50)
        atr = data_context.get("atr", price * 0.01)

        bias = "LONG 🟢" if "Haussièr" in trend else "SHORT 🔴"
        sl_val = price - (1.5 * atr) if "LONG" in bias else price + (1.5 * atr)
        be_val = price + (1.0 * atr) if "LONG" in bias else price - (1.0 * atr)
        tp1_val = r1 if "LONG" in bias else s1
        tp2_val = r2 if "LONG" in bias else s2

        report = f"""
*(Rapport généré par le Moteur Quantitatif Algorithmique)*

### 1. 📰 ANALYSE FONDAMENTALE DE L'ACTIF
- **Santé Globale :** Traitement de l'actif en temps réel. La structure micro/macro-économique globale est analysée via le flux de volatilité ATR et la tendance de fond Daily.
- **Actualités récentes :** L'actif évolue dans un cadre technique dépendant des volumes de marché sur les principales bourses mondiales.

---

### 2. 🌐 FILTRE MACRO & TENDANCE MULTI-TIMEFRAME
- **Tendance Daily :** {trend}
- **RSI (14) :** {rsi:.2f} (Zones d'essoufflement ou d'impulsion surveillées)

---

### 3. 📊 ANALYSE TECHNIQUE & SCORE DE CONFLUENCE ({data_context.get('confluence', 50)}%)
- **Point Pivot Fibonacci :** {pivot:.2f}
- **Résistances clés :** R1 = {r1:.2f} | R2 = {r2:.2f}
- **Supports clés :** S1 = {s1:.2f} | S2 = {s2:.2f}

---

### 4. 🎯 PLAN DE TRADE INSTITUTIONNEL
- **Recommandation :** **{bias}**
- **Point d'entrée suggéré :** Procédure au cours actuel ({price:.2f}) après confirmation de bougie.
- **Stop Loss (SL) :** {sl_val:.2f} (Invalidation technique basée sur 1.5x ATR).
- **Take Profit 1 (TP1) :** {tp1_val:.2f}
- **Take Profit 2 (TP2) :** {tp2_val:.2f}
- **GESTION DU BREAK-EVEN (BE) :** Déplacez le Stop Loss au point d'entrée dès que le prix atteint **{be_val:.2f}** pour annuler le risque de la position.
"""
        return report

    return "### ⚠️ Rapport indisponible."

# ---------------------------------------------------------
# Dictionnaire complet des actifs (100+ actifs)
# ---------------------------------------------------------
ASSETS_DICTIONARY = {
    "🇺🇸 Actions USA (Wall Street)": {
        "Apple": "AAPL", "Nvidia": "NVDA", "Microsoft": "MSFT", "Amazon": "AMZN",
        "Alphabet (Google)": "GOOGL", "Meta (Facebook)": "META", "Tesla": "TSLA", "AMD": "AMD",
        "Netflix": "NFLX", "Intel": "INTC", "JPMorgan Chase": "JPM", "Visa": "V",
        "Mastercard": "MA", "Bank of America": "BAC", "Coca-Cola": "KO", "PepsiCo": "PEP",
        "Walt Disney": "DIS", "Nike": "NKE", "Pfizer": "PFE", "Johnson & Johnson": "JNJ",
        "ExxonMobil": "XOM", "Chevron": "CVX", "Walmart": "WMT", "Palantir": "PLTR", "Super Micro Computer": "SMCI"
    },
    "🇪🇺 Actions Europe (Euronext, DAX, LSE)": {
        "TotalEnergies (France)": "TTE.PA", "LVMH (France)": "MC.PA", "ASML (Pays-Bas)": "ASML.AS",
        "SAP (Allemagne)": "SAP.DE", "Siemens (Allemagne)": "SIE.DE", "Sanofi (France)": "SAN.PA",
        "Airbus (France/DE)": "AIR.PA", "L'Oréal (France)": "OR.PA", "Schneider Electric (France)": "SU.PA",
        "Air Liquide (France)": "AI.PA", "BNP Paribas (France)": "BNP.PA", "AXA (France)": "CS.PA",
        "Hermès (France)": "RMS.PA", "Kering (France)": "KER.PA", "Stellantis (France/IT)": "STLAM.MI",
        "Volkswagen (Allemagne)": "VOW3.DE", "Allianz (Allemagne)": "ALV.DE", "Mercedes-Benz (Allemagne)": "MBG.DE",
        "BASF (Allemagne)": "BAS.DE", "Bayer (Allemagne)": "BAYN.DE", "Unilever (Royaume-Uni)": "ULVR.L",
        "Shell (Royaume-Uni)": "SHEL.L", "BP (Royaume-Uni)": "BP.L", "HSBC (Royaume-Uni)": "HSBA.L", "Banco Santander (Espagne)": "SAN.MC"
    },
    "🌏 Actions Asie & Pacifique": {
        "TSMC (Taïwan - ADR US)": "TSM", "Toyota (Japon)": "7203.T", "Sony (Japon)": "6758.T",
        "Tencent (Hong Kong)": "0700.HK", "Alibaba (Hong Kong)": "9988.HK", "Samsung Electronics (Corée du Sud)": "005930.KS",
        "SoftBank Group (Japon)": "9984.T", "Nintendo (Japon)": "7974.T", "Mitsubishi UFJ (Japon)": "8306.T",
        "Keyence (Japon)": "6861.T", "Tokyo Electron (Japon)": "8035.T", "Fast Retailing / Uniqlo (Japon)": "9983.T",
        "Honda (Japon)": "7267.T", "KDDI (Japon)": "9433.T", "Meituan (Hong Kong)": "3690.HK",
        "JD.com (Hong Kong)": "9618.HK", "Baidu (Hong Kong)": "9888.HK", "Xiaomi (Hong Kong)": "1810.HK",
        "BYD Company (Hong Kong)": "1211.HK", "SK Hynix (Corée du Sud)": "000660.KS"
    },
    "📊 Indices Boursiers": {
        "S&P 500 (USA)": "^GSPC", "Nasdaq 100 (USA)": "^IXIC", "Dow Jones Industrial Average (USA)": "^DJI",
        "Russell 2000 (USA)": "^RUT", "CAC 40 (France)": "^FCHI", "DAX 40 (Allemagne)": "^GDAXI",
        "Euro Stoxx 50 (Europe)": "^STOXX50E", "FTSE 100 (Royaume-Uni)": "^FTSE", "IBEX 35 (Espagne)": "^IBEX",
        "FTSE MIB (Italie)": "FTSEMIB.MI", "AEX (Pays-Bas)": "^AEX", "SMI (Suisse)": "^SSMI",
        "Nikkei 225 (Japon)": "^N225", "TOPIX (Japon)": "^TOPX", "Hang Seng (Hong Kong)": "^HSI",
        "Shanghai Composite (Chine)": "000030.SS", "CSI 300 (Chine)": "000300.SS", "Nifty 50 (Inde)": "^NSEI",
        "BSE Sensex (Inde)": "^BSESN", "ASX 200 (Australie)": "^AXJO", "IBOVESPA (Brésil)": "^BVSP",
        "IPC Mexico (Mexique)": "^MXX", "FTSE JSE Top 40 (Afrique du Sud)": "^J200.JO", "JSX Composite (Indonésie)": "^JKSE", "STI (Singapour)": "^STI"
    },
    "🛢️ Matières Premières": {
        "Pétrole Brent": "BZ=F", "Pétrole WTI (Light Crude)": "CL=F", "Or (Gold)": "GC=F",
        "Argent (Silver)": "SI=F", "Cuivre (Copper)": "HG=F", "Platinium": "PL=F", "Palladium": "PA=F",
        "Gaz Naturel (Natural Gas)": "NG=F", "Blé (Wheat)": "ZW=F", "Maïs (Corn)": "ZC=F", "Soja (Soybean)": "ZS=F",
        "Café (Coffee)": "KC=F", "Sucre (Sugar)": "SB=F", "Cacao (Cocoa)": "CC=F", "Coton (Cotton)": "CT=F",
        "Aluminium": "ALI=F", "Zinc": "ZNC=F", "Nickel": "NIC=F", "Bétail Vivant (Live Cattle)": "LE=F",
        "Porc Maigre (Lean Hogs)": "HE=F", "Avoine (Oats)": "ZO=F", "Riz (Rough Rice)": "ZR=F",
        "Essence RBOB (Gasoline)": "RB=F", "Fioul Domestique (Heating Oil)": "HO=F", "Fer (Iron Ore)": "TIO=F"
    },
    "💱 Forex (Devises)": {
        "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X", "USD/CHF": "USDCHF=X",
        "AUD/USD": "AUDUSD=X", "USD/CAD": "USDCAD=X", "NZD/USD": "NZDUSD=X", "EUR/GBP": "EURGBP=X",
        "EUR/JPY": "EURJPY=X", "GBP/JPY": "GBPJPY=X", "EUR/CHF": "EURCHF=X", "AUD/JPY": "AUDJPY=X",
        "EUR/AUD": "EURAUD=X", "EUR/CAD": "EURCAD=X", "GBP/CHF": "GBPCHF=X", "CHF/JPY": "CHFJPY=X",
        "NZD/JPY": "NZDJPY=X", "AUD/CAD": "AUDCAD=X", "AUD/NZD": "AUDNZD=X", "CAD/JPY": "CADJPY=X",
        "USD/ZAR": "USDZAR=X", "USD/MXN": "USDMXN=X", "USD/TRY": "USDTRY=X", "USD/BRL": "USDBRL=X", "USD/SEK": "USDSEK=X"
    },
    "🪙 Cryptomonnaies": {
        "Bitcoin (BTC/USD)": "BTC-USD", "Ethereum (ETH/USD)": "ETH-USD", "Solana (SOL-USD)": "SOL-USD",
        "Binance Coin (BNB/USD)": "BNB-USD", "Ripple (XRP/USD)": "XRP-USD", "Cardano (ADA/USD)": "ADA-USD",
        "Dogecoin (DOGE/USD)": "DOGE-USD", "Avalanche (AVAX/USD)": "AVAX-USD", "Chainlink (LINK/USD)": "LINK-USD",
        "Polkadot (DOT/USD)": "DOT-USD", "Polygon (POL/USD)": "POL-USD", "Tron (TRX/USD)": "TRX-USD",
        "Shiba Inu (SHIB/USD)": "SHIB-USD", "Litecoin (LTC/USD)": "LTC-USD", "Uniswap (UNI/USD)": "UNI-USD",
        "Cosmos (ATOM/USD)": "ATOM-USD", "Monero (XMR/USD)": "XMR-USD", "Stellar (XLM/USD)": "XLM-USD",
        "Near Protocol (NEAR/USD)": "NEAR-USD", "Render (RENDER/USD)": "RENDER-USD", "Sui (SUI/USD)": "SUI-USD",
        "Aptos (APT/USD)": "APT-USD", "Arbitrum (ARB/USD)": "ARB-USD", "Pepe (PEPE/USD)": "PEPE-USD", "Toncoin (TON/USD)": "TON-USD"
    }
}

TIMEFRAME_MAPPING = {
    "Scalping": {"interval": "1m",  "period": "1d"},
    "M15":      {"interval": "15m", "period": "7d"},
    "H1":       {"interval": "1h",  "period": "30d"},
    "H4":       {"interval": "1h",  "period": "60d"},
    "D1":       {"interval": "1d",  "period": "1y"},
    "1 mois":   {"interval": "1mo", "period": "5y"},
    "1 an":     {"interval": "1mo", "period": "max"}
}

@st.cache_data(ttl=300)
def load_market_data(ticker_str, period, interval):
    df = yf.download(ticker_str, period=period, interval=interval, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

@st.cache_data(ttl=300)
def load_daily_pivots_data(ticker_str):
    df_d = yf.download(ticker_str, period="5d", interval="1d", progress=False)
    if isinstance(df_d.columns, pd.MultiIndex):
        df_d.columns = df_d.columns.get_level_values(0)
    return df_d

def get_recent_news(ticker_str):
    try:
        t = yf.Ticker(ticker_str)
        news = t.news
        headlines = []
        if news and isinstance(news, list):
            for item in news[:3]:
                title = item.get('title') or item.get('content', {}).get('title', '')
                publisher = item.get('publisher') or item.get('content', {}).get('provider', {}).get('displayName', '')
                if title:
                    headlines.append(f"- {title} (Source: {publisher})")
        return headlines if headlines else ["Aucune actualité récente majeure."]
    except Exception:
        return ["Actualités non disponibles."]

# ---------------------------------------------------------
# Graphique interactif Plotly
# ---------------------------------------------------------
def draw_interactive_chart(df, pivot, r1, r2, s1, s2, asset_name, timeframe, zoom_36h=False):
    df_plot = df.copy()
    if zoom_36h and timeframe in ["Scalping", "M15", "H1", "H4"]:
        if isinstance(df_plot.index, pd.DatetimeIndex) and len(df_plot) > 0:
            if timeframe != "Scalping":
                cutoff_time = df_plot.index[-1] - timedelta(hours=36)
                df_plot = df_plot[df_plot.index >= cutoff_time]

    df_reset = df_plot.reset_index()
    date_col = 'Datetime' if 'Datetime' in df_reset.columns else 'Date'

    reversal_bull_x, reversal_bull_y = [], []
    reversal_bear_x, reversal_bear_y = [], []

    for i in range(2, len(df_reset) - 1):
        prev_close = df_reset.loc[i-1, 'Close']
        prev_open = df_reset.loc[i-1, 'Open']
        curr_close = df_reset.loc[i, 'Close']
        curr_open = df_reset.loc[i, 'Open']
        curr_low = df_reset.loc[i, 'Low']
        curr_high = df_reset.loc[i, 'High']

        if (prev_close < prev_open) and (curr_close > curr_open) and (curr_close >= prev_open):
            reversal_bull_x.append(df_reset.loc[i, date_col])
            reversal_bull_y.append(curr_low * 0.995)
        elif (prev_close > prev_open) and (curr_close < curr_open) and (curr_close <= prev_open):
            reversal_bear_x.append(df_reset.loc[i, date_col])
            reversal_bear_y.append(curr_high * 1.005)

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df_reset[date_col],
        open=df_reset['Open'], high=df_reset['High'], low=df_reset['Low'], close=df_reset['Close'],
        name='Prix',
        increasing=dict(line=dict(color='#00c853', width=1), fillcolor='#00c853'),
        decreasing=dict(line=dict(color='#ff5252', width=1), fillcolor='#ff5252')
    ))

    if 'Boll_Upper' in df_reset.columns:
        fig.add_trace(go.Scatter(x=df_reset[date_col], y=df_reset['Boll_Upper'], mode='lines', name='Bollinger Sup', line=dict(color='rgba(100,100,255,0.4)', width=1)))
        fig.add_trace(go.Scatter(x=df_reset[date_col], y=df_reset['Boll_Lower'], mode='lines', name='Bollinger Inf', line=dict(color='rgba(100,100,255,0.4)', width=1), fill='tonexty', fillcolor='rgba(100,100,255,0.03)'))

    if reversal_bull_x:
        fig.add_trace(go.Scatter(x=reversal_bull_x, y=reversal_bull_y, mode='markers', name='Retournement Haussier', marker=dict(symbol='triangle-up', size=12, color='#00e676')))
    if reversal_bear_x:
        fig.add_trace(go.Scatter(x=reversal_bear_x, y=reversal_bear_y, mode='markers', name='Retournement Baissier', marker=dict(symbol='triangle-down', size=12, color='#ff1744')))

    if 'MM50' in df_reset.columns and df_reset['MM50'].notna().any():
        fig.add_trace(go.Scatter(x=df_reset[date_col], y=df_reset['MM50'], mode='lines', name='MM 50', line=dict(color='#ffab40', width=1.5)))

    if pivot > 0:
        fig.add_hline(y=pivot, line_dash="dash", line_color="#ffd700", annotation_text=f"Pivot: {pivot:.2f}", annotation_position="top left")
        fig.add_hline(y=r1, line_dash="dot", line_color="#ff8a80", annotation_text=f"R1: {r1:.2f}", annotation_position="top left")
        fig.add_hline(y=r2, line_dash="dashdot", line_color="#ff5252", annotation_text=f"R2: {r2:.2f}", annotation_position="top left")
        fig.add_hline(y=s1, line_dash="dot", line_color="#b9f6ca", annotation_text=f"S1: {s1:.2f}", annotation_position="bottom left")
        fig.add_hline(y=s2, line_dash="dashdot", line_color="#00c853", annotation_text=f"S2: {s2:.2f}", annotation_position="bottom left")

    zoom_label = " (Zoom Dernières 36h)" if zoom_36h and timeframe in ["M15", "H1", "H4"] else ""
    fig.update_layout(
        title=f"📈 Graphique Pro — {asset_name} ({timeframe}){zoom_label}",
        xaxis_title="Date / Heure", yaxis_title="Prix",
        template="plotly_dark", paper_bgcolor="#12141a", plot_bgcolor="#181b22", height=600,
        xaxis_rangeslider_visible=False, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

# ---------------------------------------------------------
# Barre latérale : Sélection globale
# ---------------------------------------------------------
st.sidebar.header("1. Sélection de l'Actif")

custom_ticker_input = st.sidebar.text_input("🔍 Ticker libre (ex: AAPL, BTC-USD)", "").strip()
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

# --- Menu Historique ---
st.sidebar.markdown("---")
st.sidebar.header("📜 Historique")
if st.session_state.trade_history:
    history_options = ["-- Nouvelle Analyse --"] + [f"{item['id']} | {item['timestamp']} - {item['asset']} ({item['tf']})" for item in st.session_state.trade_history]
    current_index = 0
    if st.session_state.active_tab != "new":
        for idx, opt in enumerate(history_options[1:], start=1):
            if opt.startswith(f"{st.session_state.active_tab} |"):
                current_index = idx
                break

    selected_history = st.sidebar.selectbox("Consulter l'archive :", history_options, index=current_index)
    if selected_history == "-- Nouvelle Analyse --":
        if st.session_state.active_tab != "new":
            st.session_state.active_tab = "new"
            st.session_state.current_analysis = None
            st.rerun()
    else:
        selected_id = int(selected_history.split(" | ")[0])
        if st.session_state.active_tab != selected_id:
            st.session_state.active_tab = selected_id
            st.rerun()

    with st.sidebar.expander("🗑️ Vider l'historique"):
        if st.button("Tout supprimer", use_container_width=True):
            st.session_state.trade_history = []
            if os.path.exists(HISTORY_FILE):
                os.remove(HISTORY_FILE)
            st.session_state.active_tab = "new"
            st.session_state.current_analysis = None
            st.rerun()
else:
    st.sidebar.info("Aucune archive.")

# ---------------------------------------------------------
# Affichage Principal
# ---------------------------------------------------------
if st.session_state.active_tab == "new":
    st.subheader("2. Paramétrage & Lancement de l'Analyse")
    
    col_tf, col_zoom = st.columns([2, 1])
    with col_tf:
        selected_timeframe = st.selectbox("Unité de temps principale", list(TIMEFRAME_MAPPING.keys()))
    with col_zoom:
        zoom_36h_option = st.checkbox("🔍 Zoom graphique 36h", value=True)
    
    st.markdown("")
    run_analysis = st.button("🚀 Lancer l'Analyse Institutionnelle", type="primary", use_container_width=True)

    if run_analysis:
        tf_info = TIMEFRAME_MAPPING[selected_timeframe]
        
        with st.spinner(f"Analyse multi-timeframe et calcul des indicateurs pour {selected_asset_name}..."):
            df = load_market_data(ticker_symbol, tf_info["period"], tf_info["interval"])
            df_daily = load_market_data(ticker_symbol, "6m", "1d")
            
            recent_news_list = get_recent_news(ticker_symbol)
            news_text = "\n".join(recent_news_list)

            if df.empty or 'Close' not in df.columns:
                st.error(f"Erreur : Impossible de récupérer les données pour `{ticker_symbol}`. Vérifiez que le code ISIN ou le ticker est valide.")
            else:
                df['MM50'] = df['Close'].rolling(window=50 if len(df) >= 50 else 10).mean()
                df['MM200'] = df['Close'].rolling(window=200 if len(df) >= 200 else 20).mean()
                
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                df['RSI'] = 100 - (100 / (1 + rs))

                exp1 = df['Close'].ewm(span=12, adjust=False).mean()
                exp2 = df['Close'].ewm(span=26, adjust=False).mean()
                df['MACD'] = exp1 - exp2
                df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

                high_low = df['High'] - df['Low']
                high_close = np.abs(df['High'] - df['Close'].shift())
                low_close = np.abs(df['Low'] - df['Close'].shift())
                true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                df['ATR'] = true_range.rolling(14).mean()

                boll_mid = df['Close'].rolling(20).mean()
                boll_std = df['Close'].rolling(20).std()
                df['Boll_Upper'] = boll_mid + (boll_std * 2)
                df['Boll_Lower'] = boll_mid - (boll_std * 2)

                mtf_trend = "Haussière 🟢" if not df_daily.empty and df_daily['Close'].iloc[-1] > df_daily['Close'].rolling(50).mean().iloc[-1] else "Baissière 🔴"

                df_d = load_daily_pivots_data(ticker_symbol)
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
                atr_val = float(latest.get('ATR', current_price * 0.01))
                rsi_val = float(latest.get('RSI', 50))
                mm50 = float(latest.get('MM50', 0)) if pd.notna(latest.get('MM50')) else current_price

                confluence_score = 50
                if mtf_trend.startswith("Haussièr"): confluence_score += 15
                if current_price > mm50: confluence_score += 15
                if 40 <= rsi_val <= 60: confluence_score += 10
                if current_price <= s1 or current_price >= r1: confluence_score += 20
                confluence_score = min(98, max(15, confluence_score))

                prompt = f"""
                Tu es un algorithme de trading institutionnel.
                Analyse l'actif **{selected_asset_name} ({ticker_symbol})** en unité de temps **{selected_timeframe}**.

                ### DONNÉES TECHNIQUES :
                - Prix actuel : {current_price:.2f}
                - Tendance Daily : {mtf_trend}
                - Score Confluence : {confluence_score}%
                - RSI (14) : {rsi_val:.2f} | ATR : {atr_val:.2f} | MM 50 : {mm50:.2f}
                - PIVOTS FIBONACCI : R2={r2:.2f}, R1={r1:.2f}, Pivot={pivot:.2f}, S1={s1:.2f}, S2={s2:.
