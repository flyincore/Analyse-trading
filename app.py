import json
import os
import re
from datetime import datetime, timedelta
import feedparser
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from supabase import Client, create_client

st.set_page_config(page_title="Analyse Trading Pro", layout="wide")

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
    .news-summary-box {
        background-color: #1a1d24;
        border-left: 4px solid #26a69a;
        padding: 20px;
        border-radius: 6px;
        margin-bottom: 20px;
        font-size: 0.96em;
        line-height: 1.8;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎯 Analyse Trading Pro")

def init_supabase():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception:
        return None

supabase_client = init_supabase()

def load_persistent_history():
    if supabase_client:
        try:
            response = supabase_client.table("trade_history").select("*").order("id", desc=False).execute()
            if response.data:
                history = []
                for r in response.data:
                    raw_news = r.get("news", [])
                    if isinstance(raw_news, str):
                        try:
                            parsed_news = json.loads(raw_news)
                            if not isinstance(parsed_news, list):
                                parsed_news = [str(parsed_news)]
                        except Exception:
                            parsed_news = [raw_news] if raw_news else []
                    elif isinstance(raw_news, list):
                        parsed_news = raw_news
                    else:
                        parsed_news = []

                    history.append({
                        "id": int(r["id"]),
                        "timestamp": str(r["timestamp"]),
                        "asset": str(r["asset"]),
                        "ticker": str(r["ticker"]),
                        "tf": str(r["tf"]),
                        "price": float(r["price"]),
                        "mtf_trend": str(r["mtf_trend"]),
                        "confluence": int(r["confluence"]),
                        "report": str(r["report"]),
                        "news": parsed_news,
                        "zoom_36h": bool(r.get("zoom_36h", True)),
                        "executed": bool(r.get("executed", False)),
                        "result": str(r.get("result", "En cours / Indéterminé")),
                        "pivot": float(r.get("pivot", 0)),
                        "r1": float(r.get("r1", 0)),
                        "r2": float(r.get("r2", 0)),
                        "s1": float(r.get("s1", 0)),
                        "s2": float(r.get("s2", 0))
                    })
                return history
        except Exception:
            pass
    
    HISTORY_FILE = "trade_history.json"
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_history_entry(entry):
    if supabase_client:
        try:
            data = {
                "id": entry["id"],
                "timestamp": entry["timestamp"],
                "asset": entry["asset"],
                "ticker": entry["ticker"],
                "tf": entry["tf"],
                "price": entry["price"],
                "mtf_trend": entry["mtf_trend"],
                "confluence": entry["confluence"],
                "report": entry["report"],
                "news": json.dumps(entry.get("news", []), ensure_ascii=False),
                "zoom_36h": entry.get("zoom_36h", True),
                "executed": entry.get("executed", False),
                "result": entry.get("result", "En cours / Indéterminé"),
                "pivot": entry.get("pivot", 0),
                "r1": entry.get("r1", 0),
                "r2": entry.get("r2", 0),
                "s1": entry.get("s1", 0),
                "s2": entry.get("s2", 0)
            }
            supabase_client.table("trade_history").upsert(data).execute()
            return True
        except Exception:
            pass
            
    try:
        with open("trade_history.json", "w", encoding="utf-8") as f:
            json.dump(st.session_state.trade_history, f, ensure_ascii=False, indent=4)
    except Exception:
        pass
    return True

def update_supabase_status(entry_id, executed, result):
    if supabase_client:
        try:
            supabase_client.table("trade_history").update({
                "executed": executed,
                "result": result
            }).eq("id", entry_id).execute()
        except Exception:
            pass

def delete_all_history_db():
    if supabase_client:
        try:
            res = supabase_client.table("trade_history").select("id").execute()
            if res.data:
                ids = [row["id"] for row in res.data]
                for i in ids:
                    supabase_client.table("trade_history").delete().eq("id", i).execute()
        except Exception:
            pass
    if os.path.exists("trade_history.json"):
        os.remove("trade_history.json")

if "trade_history" not in st.session_state:
    st.session_state.trade_history = load_persistent_history()

if "active_tab" not in st.session_state:
    st.session_state.active_tab = "new"
if "current_analysis" not in st.session_state:
    st.session_state.current_analysis = None
if "chat_session_id" not in st.session_state:
    st.session_state.chat_session_id = datetime.now().strftime("%Y%m%d%H%M%S%f")

KIE_API_KEY = "e1d8051846b1cdd140d743826770a614"
KIE_ENDPOINT = "https://api.kie.ai/v1/chat/completions"

def generate_ai_report(prompt_text, data_context=None):
    if KIE_API_KEY:
        for model_name in ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-2.5-flash"]:
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
                res = requests.post(KIE_ENDPOINT, headers=headers, json=payload, timeout=30)
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, dict):
                        if "choices" in data and len(data["choices"]) > 0:
                            content = data["choices"][0].get("message", {}).get("content", "")
                            if content:
                                return f"*(Rapport / Réponse généré via Kie.ai - {model_name})*\n\n" + content
                        for key in ["content", "response", "output", "text", "result"]:
                            if key in data and data[key]:
                                return f"*(Rapport / Réponse généré via Kie.ai - {model_name})*\n\n" + str(data[key])
            except Exception:
                pass

    if data_context:
        price = data_context.get("price", 0)
        pivot = data_context.get("pivot", 0)
        r1 = data_context.get("r1", 0)
        r2 = data_context.get("r2", 0)
        s1 = data_context.get("s1", 0)
        s2 = data_context.get("s2", 0)
        trend = data_context.get("mtf_trend", "Neutre")
        rsi = data_context.get("rsi", 50)
        macd = data_context.get("macd", 0)
        macd_signal = data_context.get("macd_signal", 0)
        mm50 = data_context.get("mm50", price)
        mm100 = data_context.get("mm100", price)
        mm200 = data_context.get("mm200", price)
        boll_up = data_context.get("boll_up", price * 1.02)
        boll_low = data_context.get("boll_low", price * 0.98)
        vol = data_context.get("volume", 0)
        vol_ma = data_context.get("vol_ma", 0)
        fund = data_context.get("fundamentals", {})

        bull_signals = 0
        bear_signals = 0
        if "Haussièr" in trend: bull_signals += 2
        elif "Baissièr" in trend: bear_signals += 2
        if price > mm50: bull_signals += 1
        elif price < mm50: bear_signals += 1
        if price > mm100: bull_signals += 1
        elif price < mm100: bear_signals += 1
        if price > mm200: bull_signals += 2
        elif price < mm200: bear_signals += 2
        if macd > macd_signal: bull_signals += 1
        elif macd < macd_signal: bear_signals += 1
        if rsi > 52: bull_signals += 1
        elif rsi < 48: bear_signals += 1

        if bull_signals > bear_signals:
            bias = "LONG 🟢"
            sl_val = s1 if (s1 > 0 and s1 < price) else price * 0.988
            be_val = price + abs(price - sl_val)
            tp1_val = r1 if (r1 > price) else price * 1.015
            tp2_val = r2 if (r2 > price) else price * 1.03
        elif bear_signals > bull_signals:
            bias = "SHORT 🔴"
            sl_val = r1 if (r1 > price) else price * 1.012
            be_val = price - abs(price - sl_val)
            tp1_val = s1 if (s1 > 0 and s1 < price) else price * 0.985
            tp2_val = s2 if (s2 > 0 and s2 < price) else price * 0.97
        else:
            bias = "NEUTRE / ATTENTE DE CASSURE ⚪"
            sl_val = s1 if (s1 > 0 and s1 < price) else price * 0.99
            be_val = price
            tp1_val = r1 if (r1 > price) else price * 1.01
            tp2_val = r2 if (r2 > price) else price * 1.02

        entry_opt = price

        return f"""*(Rapport d'Expertise Institutionnelle — Mode Algorithmique Détaillé)*

### 1. 📈 ANALYSE FONDAMENTALE DE L'ACTIF
- **Positionnement Sectoriel & Industriel :** L'actif évolue dans le secteur **{fund.get('sector', 'N/A')}** (Industrie : **{fund.get('industry', 'N/A')}**).
- **Structure de Valorisation :** Capitalisation de **{fund.get('marketCap', 'N/A')}** | P/E Ratio : **{fund.get('peRatio', 'N/A')}**.
- **Rentabilité :** Marges nettes à **{fund.get('profitMargins', 'N/A')}** | Dividende : **{fund.get('dividendYield', 'N/A')}**.
- **Description :** {fund.get('description', 'N/A')[:400]}

---

### 2. 🌍 BIAIS MACROÉCONOMIQUE (Taux, Inflation & Emploi)
- **Politique Monétaire :** Sensibilité aux taux directeurs et aux conditions de financement globales.
- **Inflation & Coûts :** Impact des prix des intrants sur les marges et le pricing power.
- **Emploi & Demande :** Résilience macroéconomique et orientation des flux sectoriels ({bull_signals} signaux haussiers vs {bear_signals} baissiers).

---

### 3. 📊 ANALYSE TECHNIQUE MULTI-INDICATEURS
- **MM (50/100/200) :** MM50 (`{mm50:.2f}`) | MM100 (`{mm100:.2f}`) | MM200 (`{mm200:.2f}`).
- **Momentum :** RSI (`{rsi:.2f}`) | MACD (`{macd:.4f}` vs Signal `{macd_signal:.4f}`).
- **Bollinger :** Sup (`{boll_up:.2f}`) | Inf (`{boll_low:.2f}`).
- **Volume :** `{vol:,.0f}` (Moyenne 20 : `{vol_ma:,.0f}`).
- **Pivots Fibonacci :** R2=`{r2:.2f}`, R1=`{r1:.2f}`, Pivot=`{pivot:.2f}`, S1=`{s1:.2f}`, S2=`{s2:.2f}`.

---

### 4. 🎯 SYNTHÈSE ET PLAN STRATÉGIQUE EXPERT
- **Biais Opérationnel :** **{bias}**
- **Point d'Entrée Optimal :** `{entry_opt:.2f}`
- **Stop Loss :** `{sl_val:.2f}` | **TP1 :** `{tp1_val:.2f}` | **TP2 :** `{tp2_val:.2f}`
- **Break-Even :** Déplacer le SL à `{be_val:.2f}` dès que le prix l'atteint."""

    if "question de l'utilisateur" in prompt_text.lower() or "xtb" in prompt_text.lower():
        price_match = re.findall(r'(?:sur|à|de)\s+(\d{1,6}(?:\.\d+)?)', prompt_text.lower())
        custom_price = float(price_match[-1]) if price_match else None

        if custom_price:
            upper_prompt = prompt_text.upper()
            is_short = "SHORT 🔴" in upper_prompt or "BAISSIÈR" in upper_prompt or "BAISSIER" in upper_prompt or "VENDRE" in upper_prompt
            step_est = custom_price * 0.01 
            
            if is_short:
                bias_text = "SHORT 🔴"
                sl_val = custom_price + (1.2 * step_est)
                be_val = custom_price - (1.0 * step_est)
                tp1_val = custom_price - (1.5 * step_est)
                tp2_val = custom_price - (3.0 * step_est)
            else:
                bias_text = "LONG 🟢"
                sl_val = custom_price - (1.2 * step_est)
                be_val = custom_price + (1.0 * step_est)
                tp1_val = custom_price + (1.5 * step_est)
                tp2_val = custom_price + (3.0 * step_est)

            return f"""*(Recalcul Automatique du Plan — Basé sur le prix : {custom_price:.2f})*

### 🎯 PLAN DE TRADE RECALCULÉ (EXPERT)
- **Nouveau Prix de Référence :** `{custom_price:.2f}`
- **Biais Opérationnel :** **{bias_text}**
- **Point d'Entrée Optimal :** `{custom_price:.2f}`
- **Stop Loss :** `{sl_val:.2f}`
- **Take Profit 1 (TP1) :** `{tp1_val:.2f}`
- **Take Profit 2 (TP2) :** `{tp2_val:.2f}`
- **Break-Even (BE) :** `{be_val:.2f}`"""

    return f"""*(Assistant Trading IA - Mode Expert)*
J'ai bien pris en compte votre message. Analysons les détails techniques et fondamentaux de cet actif."""

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

def get_recent_news(ticker_str, clean_asset_name="", fundamental_info=None):
    raw_articles = []
    try:
        query = f"{clean_asset_name} {ticker_str}".replace(" ", "+")
        rss_url = f"https://news.google.com/rss/search?q={query}+bourse+trading+actualite+resultats&hl=fr&gl=FR&ceid=FR:fr"
        feed = feedparser.parse(rss_url)
        if feed.entries:
            for entry in feed.entries[:8]:
                source = entry.get('source', {}).get('title', 'Presse Financière')
                title = entry.get('title', '')
                pub_date = entry.get('published', '')
                if title:
                    raw_articles.append(f"- [{pub_date}] {title} (Source: {source})")
    except Exception:
        pass

    try:
        t = yf.Ticker(ticker_str)
        news = t.news
        if news and isinstance(news, list):
            for item in news[:6]:
                title = item.get('title') or item.get('content', {}).get('title', '')
                publisher = item.get('publisher') or item.get('content', {}).get('provider', {}).get('displayName', '')
                if title:
                    raw_articles.append(f"- {title} (Source: {publisher})")
    except Exception:
        pass

    raw_news_str = "\n".join(raw_articles) if raw_articles else "Recherche élargie sur le secteur, les résultats trimestriels et la dynamique concurrentielle récente."
    fund = fundamental_info if fundamental_info else {}

    expert_prompt = f"""
    Agis en tant qu'analyste financier senior et gestionnaire de portefeuille institutionnel. 
    Rédige une **Synthèse d'Actualité Multi-Sources & Diagnostic Micro-Économique** pour l'actif **{clean_asset_name}** (Ticker: {ticker_str}).
    {raw_news_str}
    """
    return [
        f"• **1. Revue de Presse :** Analyse des publications récentes pour {clean_asset_name}.",
        f"• **2. Diagnostic :** Positionnement sur le secteur {fund.get('sector', 'N/A')}.",
        f"• **3. Marges :** Marge nette observée à {fund.get('profitMargins', 'N/A')}."
    ]

def get_fundamental_data(ticker_str):
    try:
        t = yf.Ticker(ticker_str)
        info = t.info
        name = info.get("longName") or info.get("shortName") or ticker_str
        return {
            "name": name,
            "sector": info.get("sector", "Actif Global"),
            "industry": info.get("industry", "N/A"),
            "marketCap": info.get("marketCap", "N/A"),
            "peRatio": info.get("trailingPE", "N/A"),
            "forwardPE": info.get("forwardPE", "N/A"),
            "priceToBook": info.get("priceToBook", "N/A"),
            "debtToEquity": info.get("debtToEquity", "N/A"),
            "returnOnEquity": info.get("returnOnEquity", "N/A"),
            "revenueGrowth": info.get("revenueGrowth", "N/A"),
            "dividendYield": info.get("dividendYield", "N/A"),
            "profitMargins": info.get("profitMargins", "N/A"),
            "freeCashflow": info.get("freeCashflow", "N/A"),
            "description": info.get("longBusinessSummary", "Description non disponible.")
        }
    except Exception:
        return {
            "name": ticker_str, "sector": "N/A", "industry": "N/A", "marketCap": "N/A",
            "peRatio": "N/A", "forwardPE": "N/A", "priceToBook": "N/A", "debtToEquity": "N/A",
            "returnOnEquity": "N/A", "revenueGrowth": "N/A", "dividendYield": "N/A",
            "profitMargins": "N/A", "freeCashflow": "N/A", "description": "N/A"
        }

def draw_interactive_chart(df, pivot, r1, r2, s1, s2, asset_name, timeframe, zoom_36h=False):
    df_plot = df.copy()
    if zoom_36h and timeframe in ["Scalping", "M15", "H1", "H4"]:
        if isinstance(df_plot.index, pd.DatetimeIndex) and len(df_plot) > 0:
            if timeframe != "Scalping":
                cutoff_time = df_plot.index[-1] - timedelta(hours=36)
                df_plot = df_plot[df_plot.index >= cutoff_time]

    df_reset = df_plot.reset_index()
    date_col = 'Datetime' if 'Datetime' in df_reset.columns else 'Date'

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df_reset[date_col],
        open=df_reset['Open'], high=df_reset['High'], low=df_reset['Low'], close=df_reset['Close'],
        name='Prix',
        increasing=dict(line=dict(color='#00c853', width=1), fillcolor='#00c853'),
        decreasing=dict(line=dict(color='#ff5252', width=1), fillcolor='#ff5252')
    ))

    if 'MM50' in df_reset.columns and df_reset['MM50'].notna().any():
        fig.add_trace(go.Scatter(x=df_reset[date_col], y=df_reset['MM50'], mode='lines', name='MM 50', line=dict(color='#ffab40', width=1.5)))
    if 'MM100' in df_reset.columns and df_reset['MM100'].notna().any():
        fig.add_trace(go.Scatter(x=df_reset[date_col], y=df_reset['MM100'], mode='lines', name='MM 100', line=dict(color='#29b6f6', width=1.5)))
    if 'MM200' in df_reset.columns and df_reset['MM200'].notna().any():
        fig.add_trace(go.Scatter(x=df_reset[date_col], y=df_reset['MM200'], mode='lines', name='MM 200', line=dict(color='#e040fb', width=2)))

    if pivot > 0:
        fig.add_hline(y=pivot, line_dash="dash", line_color="#ffd700", annotation_text=f"Pivot: {pivot:.2f}", annotation_position="top left")
        fig.add_hline(y=r1, line_dash="dot", line_color="#ff8a80", annotation_text=f"R1: {r1:.2f}", annotation_position="top left")
        fig.add_hline(y=s1, line_dash="dot", line_color="#b9f6ca", annotation_text=f"S1: {s1:.2f}", annotation_position="bottom left")

    zoom_label = " (Zoom Dernières 36h)" if zoom_36h and timeframe in ["M15", "H1", "H4"] else ""
    fig.update_layout(
        title=f"📈 Graphique Pro — {asset_name} ({timeframe}){zoom_label}",
        xaxis_title="Date / Heure", yaxis_title="Prix",
        template="plotly_dark", paper_bgcolor="#12141a", plot_bgcolor="#181b22", height=600,
        xaxis_rangeslider_visible=False, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

def render_chat_interface(unique_chat_id, asset_name, ticker_symbol, report_text):
    st.markdown("---")
    st.markdown("### 💬 Assistant Trading IA (Chat Permanent)")
    
    chat_key = f"chat_messages_{unique_chat_id}_{ticker_symbol}"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []

    for message in st.session_state[chat_key]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if user_query := st.chat_input("Posez votre question...", key=f"chat_input_widget_{unique_chat_id}"):
        st.session_state[chat_key].append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        with st.chat_message("assistant"):
            with st.spinner("Analyse..."):
                reply = generate_ai_report(user_query)
                st.markdown(reply)
                st.session_state[chat_key].append({"role": "assistant", "content": reply})

st.sidebar.header("1. Sélection de l'Actif")
custom_ticker_input = st.sidebar.text_input("🔍 Ticker libre (ex: AAPL, BTC-USD)", "").strip()
custom_isin_input = st.sidebar.text_input("🔍 Ou code ISIN (ex: FR0000120271)", "").strip()

if custom_ticker_input:
    ticker_symbol = custom_ticker_input.upper()
    selected_asset_name = custom_ticker_input.upper()
    st.sidebar.info(f"Ticker actif : `{ticker_symbol}`")
elif custom_isin_input:
    ticker_symbol = custom_isin_input.upper()
    selected_asset_name = custom_isin_input.upper()
    st.sidebar.info(f"Code ISIN actif : `{ticker_symbol}`")
else:
    selected_category = st.sidebar.selectbox("Sélectionnez la Catégorie", list(ASSETS_DICTIONARY.keys()))
    selected_asset_name = st.sidebar.selectbox("Sélectionnez l'Actif", list(ASSETS_DICTIONARY[selected_category].keys()))
    ticker_symbol = ASSETS_DICTIONARY[selected_category][selected_asset_name]
    st.sidebar.markdown(f"**Ticker Yahoo Finance :** `{ticker_symbol}`")

st.sidebar.markdown("---")
st.sidebar.header("📜 Historique Cloud")
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
            st.session_state.chat_session_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
            st.rerun()
    else:
        selected_id = int(selected_history.split(" | ")[0])
        if st.session_state.active_tab != selected_id:
            st.session_state.active_tab = selected_id
            st.rerun()

    with st.sidebar.expander("🗑️ Vider l'historique"):
        if st.button("Tout supprimer", use_container_width=True):
            delete_all_history_db()
            st.session_state.trade_history = []
            st.session_state.active_tab = "new"
            st.session_state.current_analysis = None
            st.session_state.chat_session_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
            st.rerun()
else:
    st.sidebar.info("Aucune archive.")

if st.session_state.active_tab == "new":
    st.subheader("2. Paramétrage & Lancement de l'Analyse Expert")
    col_tf, col_zoom = st.columns([2, 1])
    with col_tf:
        selected_timeframe = st.selectbox("Unité de temps principale", list(TIMEFRAME_MAPPING.keys()))
    with col_zoom:
        zoom_36h_option = st.checkbox("🔍 Zoom graphique 36h", value=True)
    
    st.markdown("")
    run_analysis = st.button("🚀 Lancer l'Analyse Institutionnelle Experte", type="primary", use_container_width=True)

    if run_analysis:
        st.session_state.chat_session_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        tf_info = TIMEFRAME_MAPPING[selected_timeframe]
        
        with st.spinner(f"Récupération fondamentale et analyse pour {selected_asset_name}..."):
            df = load_market_data(ticker_symbol, tf_info["period"], tf_info["interval"])
            df_daily = load_market_data(ticker_symbol, "6mo", "1d")
            
            fundamental_info = get_fundamental_data(ticker_symbol)
            clean_display_name = fundamental_info.get("name") if fundamental_info.get("name") != ticker_symbol else selected_asset_name
            
            recent_news_list = get_recent_news(ticker_symbol, clean_display_name, fundamental_info)
            news_text = "\n".join(recent_news_list)

            if df.empty or 'Close' not in df.columns:
                st.error(f"Erreur : Impossible de récupérer les données pour `{ticker_symbol}`.")
            else:
                df['MM50'] = df['Close'].rolling(window=50 if len(df) >= 50 else 10).mean()
                df['MM100'] = df['Close'].rolling(window=100 if len(df) >= 100 else 15).mean()
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

                boll_mid = df['Close'].rolling(20).mean()
                boll_std = df['Close'].rolling(20).std()
                df['Boll_Upper'] = boll_mid + (boll_std * 2)
                df['Boll_Lower'] = boll_mid - (boll_std * 2)

                if 'Volume' in df.columns:
                    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
                else:
                    df['Volume'] = 0
                    df['Vol_MA20'] = 0

                if not df_daily.empty and len(df_daily) >= 50:
                    daily_mm50 = float(df_daily['Close'].rolling(50).mean().iloc[-1])
                    daily_close = float(df_daily['Close'].iloc[-1])
                    mtf_trend = "Haussière 🟢" if daily_close > daily_mm50 else "Baissière 🔴"
                else:
                    mtf_trend = "Indéterminée ⚪"

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
                rsi_val = float(latest.get('RSI', 50)) if pd.notna(latest.get('RSI')) else 50.0
                mm50 = float(latest.get('MM50', 0)) if pd.notna(latest.get('MM50')) else current_price
                mm100 = float(latest.get('MM100', 0)) if pd.notna(latest.get('MM100')) else current_price
                mm200 = float(latest.get('MM200', 0)) if pd.notna(latest.get('MM200')) else current_price
                macd_val = float(latest.get('MACD', 0)) if pd.notna(latest.get('MACD')) else 0.0
                macd_sig_val = float(latest.get('MACD_Signal', 0)) if pd.notna(latest.get('MACD_Signal')) else 0.0
                boll_up = float(latest.get('Boll_Upper', current_price * 1.02)) if pd.notna(latest.get('Boll_Upper')) else current_price * 1.02
                boll_low = float(latest.get('Boll_Lower', current_price * 0.98)) if pd.notna(latest.get('Boll_Lower')) else current_price * 0.98
                vol_val = float(latest.get('Volume', 0)) if pd.notna(latest.get('Volume')) else 0.0
                vol_ma_val = float(latest.get('Vol_MA20', 0)) if pd.notna(latest.get('Vol_MA20')) else 0.0
                vol_ratio = (vol_val / vol_ma_val) if vol_ma_val > 0 else 1.0

                confluence_score = 50
                if mtf_trend.startswith("Haussièr"): confluence_score += 10
                if current_price > mm50: confluence_score += 8
                if current_price > mm100: confluence_score += 6
                if current_price > mm200: confluence_score += 8
                if macd_val > macd_sig_val: confluence_score += 6
                confluence_score = min(98, max(15, confluence_score))

                prompt = f"Analyse pour {clean_display_name}"
                data_ctx = {
                    "price": current_price, "pivot": pivot, "r1": r1, "r2": r2, "s1": s1, "s2": s2,
                    "mtf_trend": mtf_trend, "rsi": rsi_val, "macd": macd_val, "macd_signal": macd_sig_val,
                    "mm50": mm50, "mm100": mm100, "mm200": mm200, "boll_up": boll_up, "boll_low": boll_low,
                    "volume": vol_val, "vol_ma": vol_ma_val, "confluence": confluence_score, "fundamentals": fundamental_info
                }
                ai_text = generate_ai_report(prompt, data_context=data_ctx)

                st.session_state.current_analysis = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "asset": clean_display_name, "ticker": ticker_symbol, "tf": selected_timeframe,
                    "price": current_price, "mtf_trend": mtf_trend, "confluence": confluence_score,
                    "report": ai_text, "df": df, "pivot": pivot, "r1": r1, "r2": r2, "s1": s1, "s2": s2,
                    "news": recent_news_list, "zoom_36h": zoom_36h_option, "executed": False, "result": "En cours"
                }

    if st.session_state.current_analysis is not None:
        ca = st.session_state.current_analysis
        if st.button("🔍 Nouvelle recherche", type="secondary", use_container_width=True):
            st.session_state.current_analysis = None
            st.session_state.chat_session_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
            st.rerun()

        st.markdown(f"## 📊 Rapport : {ca['asset']} ({ca['tf']})")
        fig = draw_interactive_chart(ca['df'], ca['pivot'], ca['r1'], ca['r2'], ca['s1'], ca['s2'], ca['asset'], ca['tf'], zoom_36h=ca['zoom_36h'])
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(ca['report'])
        render_chat_interface(f"live_{st.session_state.chat_session_id}", ca['asset'], ca['ticker'], ca['report'])

        if st.button("💾 Enregistrer dans l'historique cloud", type="primary", use_container_width=True):
            new_id = (max([item['id'] for item in st.session_state.trade_history]) + 1) if st.session_state.trade_history else 1
            ca_to_save = ca.copy()
            ca_to_save['id'] = new_id
            df_temp = ca_to_save.pop('df', None)
            st.session_state.trade_history.append(ca_to_save)
            save_history_entry(ca_to_save)
            st.session_state.active_tab = new_id
            st.session_state.current_analysis = None
            st.rerun()

else:
    entry = next((item for item in st.session_state.trade_history if item['id'] == st.session_state.active_tab), None)
    if entry:
        if st.button("⬅️ Effectuer une nouvelle analyse"):
            st.session_state.active_tab = "new"
            st.session_state.current_analysis = None
            st.rerun()

        st.markdown(f"## 📜 Archive : {entry['asset']} ({entry['tf']})")
        if 'df' not in entry or entry['df'] is None or isinstance(entry['df'], list):
            tf_info = TIMEFRAME_MAPPING.get(entry['tf'], {"interval": "1d", "period": "1y"})
            entry['df'] = load_market_data(entry['ticker'], tf_info["period"], tf_info["interval"])

        fig = draw_interactive_chart(entry['df'], entry['pivot'], entry['r1'], entry['r2'], entry['s1'], entry['s2'], entry['asset'], entry['tf'], zoom_36h=entry['zoom_36h'])
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(entry['report'])
        render_chat_interface(f"archive_{entry['id']}", entry['asset'], entry['ticker'], entry['report'])
    else:
        st.session_state.active_tab = "new"
        st.session_state.current_analysis = None
        st.rerun()
