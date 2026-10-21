import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import os
import re
import feedparser
import plotly.graph_objects as go
from datetime import datetime, timedelta
from supabase import create_client, Client

# Configuration de la page Streamlit avec un thème global sombre / carbone
st.set_page_config(page_title="Analyse Trading Pro", layout="wide")

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
    .news-summary-box {
        background-color: #1a1d24;
        border-left: 4px solid #26a69a;
        padding: 18px;
        border-radius: 6px;
        margin-bottom: 20px;
        font-size: 0.95em;
        line-height: 1.75;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎯 Analyse Trading Pro")

# ---------------------------------------------------------
# CONNEXION SUPABASE & PERSISTANCE CLOUD DE L'HISTORIQUE
# ---------------------------------------------------------
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
                        "news": json.loads(r["news"]) if r.get("news") else [],
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

# ---------------------------------------------------------
# CONFIGURATION KIE.AI & MOTEUR D'ANALYSE EXPERT & CHAT INTELLIGENT
# ---------------------------------------------------------
KIE_API_KEY = "e1d8051846b1cdd140d743826770a614"
KIE_ENDPOINT = "https://api.kie.ai/v1/chat/completions"

def generate_ai_report(prompt_text, data_context=None):
    if KIE_API_KEY:
        # Restriction exclusive sur Gemini 3.8 Flash et Gemini 3.7 Flash
        for model_name in ["gemini-3.8-flash", "gemini-3.7-flash"]:
            try:
                headers = {
                    "Authorization": f"Bearer {KIE_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt_text}],
                    "temperature": 0.2
                }
                res = requests.post(KIE_ENDPOINT, headers=headers, json=payload, timeout=20)
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

    price_match = re.findall(r'(?:sur|à|de)\s+(\d{1,6}(?:\.\d+)?)', prompt_text.lower())
    custom_price = float(price_match[-1]) if price_match else None

    if custom_price:
        is_short = "SHORT" in prompt_text.upper() or "BAISSIÈR" in prompt_text.upper() or "BAISSIER" in prompt_text.upper()
        atr_est = custom_price * 0.008 
        
        if is_short:
            bias_text = "SHORT 🔴"
            sl_val = custom_price + (1.5 * atr_est)
            be_val = custom_price - (1.0 * atr_est)
            tp1_val = custom_price - (1.5 * atr_est)
            tp2_val = custom_price - (3.0 * atr_est)
        else:
            bias_text = "LONG 🟢"
            sl_val = custom_price - (1.5 * atr_est)
            be_val = custom_price + (1.0 * atr_est)
            tp1_val = custom_price + (1.5 * atr_est)
            tp2_val = custom_price + (3.0 * atr_est)

        return f"""*(Recalcul Automatique du Plan — Basé sur le prix XTB : {custom_price:.2f})*

### 🎯 PLAN DE TRADE RECALCULÉ (EXPERT)
- **Nouveau Prix de Référence :** `{custom_price:.2f}`
- **Biais Opérationnel :** **{bias_text}** (Préservé et aligné sur l'analyse initiale)
- **Point d'Entrée Optimal :** `{custom_price:.2f}` (Sur test de la zone de déséquilibre)
- **Stop Loss (SL) Institutionnel :** `{sl_val:.2f}` (Calculé avec un risque de 1.5x ATR estimé à `{atr_est:.2f}`)
- **Take Profit 1 (TP1) :** `{tp1_val:.2f}` (Allègement de 50% de la position)
- **Take Profit 2 (TP2) :** `{tp2_val:.2f}` (Objectif d'extension de marché)
- **GESTION DU BREAK-EVEN (BE) :** Déplacer le Stop Loss au point d'entrée dès que le prix atteint `{be_val:.2f}`."""

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
        macd = data_context.get("macd", 0)
        macd_signal = data_context.get("macd_signal", 0)
        mm50 = data_context.get("mm50", price)
        mm100 = data_context.get("mm100", price)
        mm200 = data_context.get("mm200", price)
        boll_up = data_context.get("boll_up", price * 1.02)
        boll_low = data_context.get("boll_low", price * 0.98)
        fund = data_context.get("fundamentals", {})

        bias = "LONG 🟢" if "Haussièr" in trend else "SHORT 🔴"
        sl_val = price - (1.5 * atr) if "LONG" in bias else price + (1.5 * atr)
        be_val = price + (1.0 * atr) if "LONG" in bias else price - (1.0 * atr)
        tp1_val = r1 if "LONG" in bias else s1
        tp2_val = r2 if "LONG" in bias else s2
        entry_opt = price - (0.2 * atr) if "LONG" in bias else price + (0.2 * atr)

        return f"""*(Rapport d'Expertise Institutionnelle — Mode de Secours Algorithmique)*

### 1. 📈 ANALYSE FONDAMENTALE DE L'ACTIF
- **Secteur / Industrie :** {fund.get('sector', 'N/A')} ({fund.get('industry', 'N/A')})
- **Capitalisation & Valorisation :** Cap. Boursière : {fund.get('marketCap', 'N/A')} | P/E Ratio : {fund.get('peRatio', 'N/A')}

---

### 2. 🌍 BIAIS MACROÉCONOMIQUE (Taux, Inflation & Emploi)
- **Politique Monétaire :** Les anticipations de taux des banques centrales guident l'allocation des flux de capitaux sur cet actif.
- **Inflation & Emploi :** Le climat macroéconomique global soutient la structure de volatilité mesurée par l'ATR (`{atr:.2f}`).

---

### 3. 🏛️ ANALYSE STRUCTURELLE (Auction Market Theory - AMT)
- **Zone de Déséquilibre :** Le marché évalue l'acceptation des prix autour du pivot central (`{pivot:.2f}`).

---

### 4. 📊 ANALYSE TECHNIQUE MULTI-INDICATEURS
- **Moyennes Mobiles :** MM50 (`{mm50:.2f}`) | MM100 (`{mm100:.2f}`) | MM200 (`{mm200:.2f}`).
- **RSI (14) :** `{rsi:.2f}` | **MACD :** `{macd:.4f}` (Signal: `{macd_sig_val:.4f}`).
- **Bandes de Bollinger :** Sup=`{boll_up:.2f}` | Inf=`{boll_low:.2f}`.
- **Pivots Fibonacci :** R2=`{r2:.2f}`, R1=`{r1:.2f}`, Pivot=`{pivot:.2f}`, S1=`{s1:.2f}`, S2=`{s2:.2f}`.

---

### 5. 🎯 PLAN DE TRADE & EXÉCUTION PAR ORDER FLOW
- **Biais Opérationnel :** **{bias}**
- **Point d'Entrée Chirurgical :** `{entry_opt:.2f}` sur confirmation d'absorption des flux.
- **Stop Loss (SL) :** `{sl_val:.2f}` | **TP1 :** `{tp1_val:.2f}` | **TP2 :** `{tp2_val:.2f}`
- **BREAK-EVEN (BE) :** Déplacer le SL au point d'entrée dès que le prix atteint `{be_val:.2f}`."""

    return f"""*(Assistant Trading IA - Mode Expert)*
En tant qu'analyste institutionnel, j'ai bien pris en compte votre remarque sur le prix. Pour valider votre position par rapport au carnet d'ordres, surveillez l'absorption des flux et le respect des zones de valeur de l'ATR."""

# ---------------------------------------------------------
# Dictionnaire complet des actifs
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

# ---------------------------------------------------------
# RÉSUMÉ D'ACTUALITÉ & DIAGNOSTIC MICRO-ÉCONOMIQUE APPROFONDI (GEMINI 3.8 / 3.7 FLASH)
# ---------------------------------------------------------
def get_recent_news(ticker_str, clean_asset_name="", fundamental_info=None):
    raw_articles = []
    
    # 1. Google News RSS Multi-Sources (Investing, Boursorama, Bloomberg, Les Echos...)
    try:
        query = clean_asset_name.replace(" ", "+")
        rss_url = f"https://news.google.com/rss/search?q={query}+bourse+trading&hl=fr&gl=FR&ceid=FR:fr"
        feed = feedparser.parse(rss_url)
        if feed.entries:
            for entry in feed.entries[:4]:
                source = entry.get('source', {}).get('title', 'Presse Financière')
                title = entry.get('title', '')
                if title:
                    raw_articles.append(f"- Titre: {title} (Source: {source})")
    except Exception:
        pass

    # 2. Yahoo Finance Direct
    try:
        t = yf.Ticker(ticker_str)
        news = t.news
        if news and isinstance(news, list):
            for item in news[:3]:
                title = item.get('title') or item.get('content', {}).get('title', '')
                publisher = item.get('publisher') or item.get('content', {}).get('provider', {}).get('displayName', '')
                if title:
                    raw_articles.append(f"- Titre: {title} (Source: {publisher})")
    except Exception:
        pass

    raw_news_str = "\n".join(raw_articles) if raw_articles else "Aucune dépêche directe immédiate trouvée."
    fund = fundamental_info if fundamental_info else {}

    micro_prompt = f"""
    En tant qu'analyste senior spécialisé en stratégie d'entreprise et micro-économie financière institutionnelle, rédige un diagnostic micro-économique extrêmement approfondi et professionnel pour l'actif **{clean_asset_name}** ({ticker_symbol}).

    ### DÉPÊCHES RECENTES ET DÉTECTÉES EN DIRECT :
    {raw_news_str}

    ### ÉLÉMENTS FONDAMENTAUX DISPONIBLES :
    - Secteur : {fund.get('sector', 'N/A')}
    - Industrie : {fund.get('industry', 'N/A')}
    - Capitalisation Boursière : {fund.get('marketCap', 'N/A')}
    - P/E Ratio (Valorisation) : {fund.get('peRatio', 'N/A')}
    - Marge bénéficiaire : {fund.get('profitMargins', 'N/A')}
    - Rendement Dividende : {fund.get('dividendYield', 'N/A')}

    CONSIGNES STRICTES DE RÉDACTION :
    - Adopte un ton d'analyste sell-side / buy-side institutionnel (très qualitatif, concis mais dense et technique).
    - Rédige exactement 4 points stratégiques structurés sous forme de puces markdown avec titres en gras.
    - Évite la généralité : aborde la dynamique des marges, le pricing power, la structure des coûts (opératoires / d'extraction / financiers), les catalyseurs de court/moyen terme et la situation concurrentielle spécifique à **{clean_asset_name}**.
    - Ne fais JAMAIS référence à un code ISIN ou un ticker brut dans les descriptions, utilise uniquement le nom exact : **{clean_asset_name}**.
    """

    try:
        if KIE_API_KEY:
            headers = {
                "Authorization": f"Bearer {KIE_API_KEY}",
                "Content-Type": "application/json"
            }
            # Utilisation prioritaire de Gemini 3.8 Flash et Gemini 3.7 Flash
            for micro_model in ["gemini-3.8-flash", "gemini-3.7-flash"]:
                try:
                    payload = {
                        "model": micro_model,
                        "messages": [{"role": "user", "content": micro_prompt}],
                        "temperature": 0.2
                    }
                    res = requests.post(KIE_ENDPOINT, headers=headers, json=payload, timeout=15)
                    if res.status_code == 200:
                        data = res.json()
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        if content:
                            bullets = [line.strip() for line in content.split("\n") if line.strip().startswith("•") or line.strip().startswith("-") or line.strip().startswith("*")]
                            if len(bullets) >= 3:
                                return bullets[:4]
                            else:
                                return [content]
                except Exception:
                    continue
    except Exception:
        pass

    return [
        f"• **Dynamique des Marges & Pricing Power ({clean_asset_name}) :** Évaluation de la capacité de l'actif à répercuter l'inflation des coûts sur ses prix de vente sans dégrader son carnet de commandes ni sa part de marché relative.",
        f"• **Structure des Coûts Opérationnels & Levier Financier :** Analyse du besoin en fonds de roulement (BFR), du refinancement des dettes et de la maîtrise du Cash Cost opératoire face au contexte économique actuel.",
        f"• **Catalyseurs Micro-économiques & Visibilité du Cash-Flow :** Analyse des prochains rendez-vous financiers et des perspectives d'EBITDA/Free Cash Flow récurrent pour soutenir la valorisation globale.",
        f"• **Positionnement Concurrentiel & Risques Spécifiques ({clean_asset_name}) :** Veille sur la structure de l'offre, la pression réglementaire et la résilience du modèle d'affaires face aux acteurs majeurs du secteur."
    ]

def get_fundamental_data(ticker_str):
    try:
        t = yf.Ticker(ticker_str)
        info = t.info
        name = info.get("longName") or info.get("shortName") or ticker_str
        return {
            "name": name,
            "sector": info.get("sector", "Actif Global / Hors Secteur standard"),
            "industry": info.get("industry", "N/A"),
            "marketCap": info.get("marketCap", "N/A"),
            "peRatio": info.get("trailingPE", "N/A"),
            "dividendYield": info.get("dividendYield", "N/A"),
            "profitMargins": info.get("profitMargins", "N/A"),
            "description": info.get("longBusinessSummary", "Description non disponible.")
        }
    except Exception:
        return {"name": ticker_str, "sector": "N/A", "industry": "N/A", "marketCap": "N/A", "peRatio": "N/A", "dividendYield": "N/A", "profitMargins": "N/A", "description": "N/A"}

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

    if user_query := st.chat_input("Ex: Le prix actuel sur XTB est de 4134.83, refait l'analyse sur ce prix...", key=f"chat_input_widget_{unique_chat_id}"):
        st.session_state[chat_key].append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        with st.chat_message("assistant"):
            with st.spinner("Analyse experte et recalcul des niveaux en cours..."):
                history = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state[chat_key][:-1]])
                prompt_chat = f"Contexte actif : {asset_name} ({ticker_symbol}). Rapport initial : {report_text}\nHistorique des échanges : {history}\nQuestion de l'utilisateur : {user_query}"
                reply = generate_ai_report(prompt_chat)
                st.markdown(reply)
                st.session_state[chat_key].append({"role": "assistant", "content": reply})

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
    selected_asset_name = custom_isin_input.upper()
    st.sidebar.info(f"Code ISIN actif : `{ticker_symbol}`")
else:
    selected_category = st.sidebar.selectbox("Sélectionnez la Catégorie", list(ASSETS_DICTIONARY.keys()))
    selected_asset_name = st.sidebar.selectbox("Sélectionnez l'Actif", list(ASSETS_DICTIONARY[selected_category].keys()))
    ticker_symbol = ASSETS_DICTIONARY[selected_category][selected_asset_name]
    st.sidebar.markdown(f"**Ticker Yahoo Finance :** `{ticker_symbol}`")

# --- Menu Historique ---
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

# ---------------------------------------------------------
# Affichage Principal
# ---------------------------------------------------------
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
        
        with st.spinner(f"Récupération fondamentale et analyse multi-sources pour {selected_asset_name}..."):
            df = load_market_data(ticker_symbol, tf_info["period"], tf_info["interval"])
            df_daily = load_market_data(ticker_symbol, "6m", "1d")
            
            fundamental_info = get_fundamental_data(ticker_symbol)
            clean_display_name = fundamental_info.get("name") if fundamental_info.get("name") != ticker_symbol else selected_asset_name
            
            recent_news_list = get_recent_news(ticker_symbol, clean_display_name, fundamental_info)
            news_text = "\n".join(recent_news_list)

            if df.empty or 'Close' not in df.columns:
                st.error(f"Erreur : Impossible de récupérer les données pour `{ticker_symbol}`. Vérifiez que le code ISIN ou le ticker est valide.")
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
                mm100 = float(latest.get('MM100', 0)) if pd.notna(latest.get('MM100')) else current_price
                mm200 = float(latest.get('MM200', 0)) if pd.notna(latest.get('MM200')) else current_price
                macd_val = float(latest.get('MACD', 0)) if pd.notna(latest.get('MACD')) else 0
                macd_sig_val = float(latest.get('MACD_Signal', 0)) if pd.notna(latest.get('MACD_Signal')) else 0
                boll_up = float(latest.get('Boll_Upper', current_price * 1.02))
                boll_low = float(latest.get('Boll_Lower', current_price * 0.98))

                confluence_score = 50
                if mtf_trend.startswith("Haussièr"): confluence_score += 15
                if current_price > mm50: confluence_score += 10
                if current_price > mm200: confluence_score += 10
                if 40 <= rsi_val <= 60: confluence_score += 5
                if current_price <= s1 or current_price >= r1: confluence_score += 10
                confluence_score = min(98, max(15, confluence_score))

                prompt = f"""
                Agis en tant qu'expert senior en marchés financiers, analyse micro-économique et trading institutionnel.
                Réalise une analyse complète, rigoureuse et de niveau institutionnel pour l'actif **{clean_display_name} ({ticker_symbol})** en unité de temps **{selected_timeframe}**.

                ### ACTUALITÉS RÉCENTES & DIAGNOSTIC MICRO-ÉCONOMIQUE APPROFONDI :
                {news_text}

                ### DONNÉES FONDAMENTALES & SECTORIELLES :
                - Nom Officiel : {clean_display_name}
                - Secteur : {fundamental_info.get('sector')}
                - Industrie : {fundamental_info.get('industry')}
                - Capitalisation : {fundamental_info.get('marketCap')}
                - P/E Ratio : {fundamental_info.get('peRatio')}
                - Rendement du dividende : {fundamental_info.get('dividendYield')}
                - Marges bénéficiaires : {fundamental_info.get('profitMargins')}
                - Résumé d'entreprise : {fundamental_info.get('description')}

                ### DONNÉES QUANTITATIVES & TECHNIQUES :
                - Prix actuel : {current_price:.2f}
                - Tendance Daily (MTF) : {mtf_trend}
                - Score de Confluence Globale : {confluence_score}%
                - RSI (14) : {rsi_val:.2f}
                - MACD : {macd_val:.4f} (Signal : {macd_sig_val:.4f})
                - Moyennes Mobiles : MM50={mm50:.2f}, MM100={mm100:.2f}, MM200={mm200:.2f}
                - Bandes de Bollinger : Sup={boll_up:.2f} | Inf={boll_low:.2f}
                - Volatilité (ATR) : {atr_val:.2f}
                - PIVOTS FIBONACCI : R2={r2:.2f}, R1={r1:.2f}, Pivot={pivot:.2f}, S1={s1:.2f}, S2={s2:.2f}

                Structure ton rapport selon les exigences professionnelles suivantes :
                1. **Analyse Micro-économique & Conjoncturelle** : Intègre les éléments d'actualité récente, la santé financière, la structure des marges et des coûts de {clean_display_name}.
                2. **Biais Macroéconomique (Taux, Inflation, Emploi)** : Impact des politiques monétaires et des flux globaux sur l'actif.
                3. **Auction Market Theory (AMT)** : Définition de la Value Area, acceptation/rejet des prix, et zone de déséquilibre.
                4. **Analyse Technique Avancée** : Lecture croisée MM (50/100/200), MACD, RSI, Bollinger et Pivots Fibonacci.
                5. **Plan de Trade & Order Flow** : Point d'entrée chirurgical, SL dynamique, TP et gestion rigoureuse du Break-Even (BE).
                """

                data_ctx = {
                    "price": current_price,
                    "pivot": pivot, "r1": r1, "r2": r2, "s1": s1, "s2": s2,
                    "mtf_trend": mtf_trend,
                    "rsi": rsi_val,
                    "atr": atr_val,
                    "macd": macd_val,
                    "macd_signal": macd_sig_val,
                    "mm50": mm50,
                    "mm100": mm100,
                    "mm200": mm200,
                    "boll_up": boll_up,
                    "boll_low": boll_low,
                    "confluence": confluence_score,
                    "fundamentals": fundamental_info
                }

                with st.spinner("Génération du rapport d'expertise institutionnelle..."):
                    ai_text = generate_ai_report(prompt, data_context=data_ctx)

                timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                st.session_state.current_analysis = {
                    "timestamp": timestamp_str,
                    "asset": clean_display_name,
                    "ticker": ticker_symbol,
                    "tf": selected_timeframe,
                    "price": current_price,
                    "mtf_trend": mtf_trend,
                    "confluence": confluence_score,
                    "report": ai_text,
                    "df": df,
                    "pivot": pivot,
                    "r1": r1, "r2": r2, "s1": s1, "s2": s2,
                    "news": recent_news_list,
                    "zoom_36h": zoom_36h_option,
                    "executed": False,
                    "result": "En cours / Indéterminé"
                }

    if st.session_state.current_analysis is not None:
        ca = st.session_state.current_analysis
        
        if st.button("🔍 Nouvelle recherche", type="secondary", use_container_width=True):
            st.session_state.current_analysis = None
            st.session_state.chat_session_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
            st.rerun()

        st.markdown("---")
        st.markdown(f"## 📊 Rapport Institutionnel Expert : {ca['asset']} ({ca['tf']}) — {ca['timestamp']}")
        
        m1, m2, m3 = st.columns(3)
        with m1: st.metric("Tendance Daily (MTF)", ca['mtf_trend'])
        with m2: st.metric("Score de Confluence", ca['confluence'])
        with m3: st.metric("Prix de Référence", f"{ca['price']:.2f}")

        fig_interactive = draw_interactive_chart(ca['df'], ca['pivot'], ca['r1'], ca['r2'], ca['s1'], ca['s2'], ca['asset'], ca['tf'], zoom_36h=ca['zoom_36h'])
        st.plotly_chart(fig_interactive, use_container_width=True)

        st.markdown("---")
        st.markdown(f"### 📰 Synthèse d'Actualité Multi-Sources & Diagnostic Micro ({ca['asset']})")
        news_html = "<div class='news-summary-box'>" + "<br><br>".join(ca['news']) + "</div>"
        st.markdown(news_html, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 📋 Synthèse et Plan Stratégique Expert")
        st.markdown(ca['report'])

        render_chat_interface(f"live_{st.session_state.chat_session_id}", ca['asset'], ca['ticker'], ca['report'])

        st.markdown("---")
        col_save1, col_save2 = st.columns([1, 2])
        with col_save1:
            if st.button("💾 Enregistrer dans l'historique cloud", type="primary", use_container_width=True):
                new_id = (max([item['id'] for item in st.session_state.trade_history]) + 1) if st.session_state.trade_history else 1
                ca_to_save = ca.copy()
                ca_to_save['id'] = new_id
                
                df_temp = ca_to_save.pop('df', None)
                st.session_state.trade_history.append(ca_to_save)
                
                save_history_entry(ca_to_save)
                
                ca_to_save['df'] = df_temp
                
                st.session_state.active_tab = new_id
                st.session_state.current_analysis = None
                st.success("Analyse enregistrée définitivement dans le cloud !")
                st.rerun()
        with col_save2:
            st.info("💡 Cliquez pour archiver l'analyse, suivre votre position et retrouver vos données sur tous vos appareils.")

else:
    entry = next((item for item in st.session_state.trade_history if item['id'] == st.session_state.active_tab), None)
    
    if entry:
        if st.button("⬅️ Effectuer une nouvelle analyse"):
            st.session_state.active_tab = "new"
            st.session_state.current_analysis = None
            st.session_state.chat_session_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
            st.rerun()

        st.markdown(f"## 📜 Archive : {entry['asset']} ({entry['tf']}) — {entry['timestamp']}")
        
        if 'df' not in entry or entry['df'] is None or isinstance(entry['df'], list):
            tf_info = TIMEFRAME_MAPPING.get(entry['tf'], {"interval": "1d", "period": "1y"})
            entry['df'] = load_market_data(entry['ticker'], tf_info["period"], tf_info["interval"])

        m1, m2, m3 = st.columns(3)
        with m1: st.metric("Tendance Daily", entry['mtf_trend'])
        with m2: st.metric("Score Confluence", entry['confluence'])
        with m3: st.metric("Prix de référence", f"{entry['price']:.2f}")

        fig_interactive = draw_interactive_chart(entry['df'], entry['pivot'], entry['r1'], entry['r2'], entry['s1'], entry['s2'], entry['asset'], entry['tf'], zoom_36h=entry['zoom_36h'])
        st.plotly_chart(fig_interactive, use_container_width=True)

        st.markdown("---")
        st.markdown(f"### 📰 Synthèse d'Actualité Multi-Sources & Diagnostic Micro ({entry['asset']})")
        news_html = "<div class='news-summary-box'>" + "<br><br>".join(entry.get('news', ['Actualités non disponibles.'])) + "</div>"
        st.markdown(news_html, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 📊 Rapport d'Analyse")
        st.markdown(entry['report'])

        st.markdown("---")
        st.markdown("### 📋 Suivi de la Position")
        col_a, col_b = st.columns(2)
        with col_a:
            trade_executed = st.radio("Trade réalisé ?", ["Non", "Oui"], index=1 if entry['executed'] else 0, key=f"exec_{entry['id']}")
            entry['executed'] = (trade_executed == "Oui")
        with col_b:
            if entry['executed']:
                result_options = ["En cours / Indéterminé", "Gagnant 🟢", "Perdant 🔴"]
                current_res_idx = result_options.index(entry['result']) if entry['result'] in result_options else 0
                entry['result'] = st.radio("Résultat :", result_options, index=current_res_idx, key=f"res_{entry['id']}")
            else:
                entry['result'] = "N/A"
                st.info("Cochez 'Oui' pour consigner le résultat du trade.")

        update_supabase_status(entry['id'], entry['executed'], entry['result'])

        render_chat_interface(f"archive_{entry['id']}", entry['asset'], entry['ticker'], entry['report'])

    else:
        st.session_state.active_tab = "new"
        st.session_state.current_analysis = None
        st.session_state.chat_session_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        st.rerun()
