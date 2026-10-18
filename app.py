import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go
import re
from datetime import datetime, timedelta

# Configuration de la page Streamlit avec un thème global sombre / carbone
st.set_page_config(page_title="Bot Trading IA - Mondial & ISIN", layout="wide")

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
    </style>
""", unsafe_allow_html=True)

st.title("🎯 Bot d'Analyse Trading Technique & Fondamental")
st.markdown("Analyse technique complète, graphique interactif Plotly avec flèches de retournement, pivots Fibonacci et journal de trading.")

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
    "H1":     {"interval": "1h",  "period": "30d"},
    "H4":     {"interval": "1h",  "period": "60d"},
    "D1":     {"interval": "1d",  "period": "1y"},
    "1 mois": {"interval": "1mo", "period": "5y"},
    "1 an":   {"interval": "1mo", "period": "max"}
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
        return headlines if headlines else ["Aucune actualité récente directement disponible."]
    except Exception:
        return ["Impossible de récupérer les actualités récentes pour cet actif."]

# ---------------------------------------------------------
# Graphique interactif Plotly avec flèches de retournement
# ---------------------------------------------------------
def draw_interactive_chart(df, pivot, r1, r2, s1, s2, asset_name, timeframe, zoom_36h=False):
    df_plot = df.copy()
    if zoom_36h and timeframe in ["M15", "H1", "H4"]:
        if isinstance(df_plot.index, pd.DatetimeIndex) and len(df_plot) > 0:
            cutoff_time = df_plot.index[-1] - timedelta(hours=36)
            df_plot = df_plot[df_plot.index >= cutoff_time]

    df_reset = df_plot.reset_index()
    date_col = 'Datetime' if 'Datetime' in df_reset.columns else 'Date'

    # Détection algorithmique des zones de retournement (Reversal Signals)
    reversal_bull_x = []
    reversal_bull_y = []
    reversal_bear_x = []
    reversal_bear_y = []

    for i in range(2, len(df_reset) - 1):
        prev_close = df_reset.loc[i-1, 'Close']
        prev_open = df_reset.loc[i-1, 'Open']
        curr_close = df_reset.loc[i, 'Close']
        curr_open = df_reset.loc[i, 'Open']
        curr_low = df_reset.loc[i, 'Low']
        curr_high = df_reset.loc[i, 'High']

        # Signal de retournement haussier (ex: bougie précédente baissière suivie d'une forte bougie haussière)
        if (prev_close < prev_open) and (curr_close > curr_open) and (curr_close >= prev_open):
            reversal_bull_x.append(df_reset.loc[i, date_col])
            reversal_bull_y.append(curr_low * 0.995)

        # Signal de retournement baissier (ex: bougie précédente haussière suivie d'une forte bougie baissière)
        elif (prev_close > prev_open) and (curr_close < curr_open) and (curr_close <= prev_open):
            reversal_bear_x.append(df_reset.loc[i, date_col])
            reversal_bear_y.append(curr_high * 1.005)

    fig = go.Figure()

    # Bougies japonaises pleines
    fig.add_trace(go.Candlestick(
        x=df_reset[date_col],
        open=df_reset['Open'],
        high=df_reset['High'],
        low=df_reset['Low'],
        close=df_reset['Close'],
        name='Prix',
        increasing=dict(line=dict(color='#00c853', width=1), fillcolor='#00c853'),
        decreasing=dict(line=dict(color='#ff5252', width=1), fillcolor='#ff5252')
    ))

    # Flèches de retournement haussier (Vers le haut)
    if reversal_bull_x:
        fig.add_trace(go.Scatter(
            x=reversal_bull_x,
            y=reversal_bull_y,
            mode='markers',
            name='Retournement Haussier',
            marker=dict(symbol='triangle-up', size=12, color='#00e676')
        ))

    # Flèches de retournement baissier (Vers le bas)
    if reversal_bear_x:
        fig.add_trace(go.Scatter(
            x=reversal_bear_x,
            y=reversal_bear_y,
            mode='markers',
            name='Retournement Baissier',
            marker=dict(symbol='triangle-down', size=12, color='#ff1744')
        ))

    # Moyenne Mobile MM50
    if 'MM50' in df_reset.columns and df_reset['MM50'].notna().any():
        fig.add_trace(go.Scatter(
            x=df_reset[date_col],
            y=df_reset['MM50'],
            mode='lines',
            name='MM 50',
            line=dict(color='#ffab40', width=1.5)
