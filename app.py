import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Configuration de la page Streamlit
st.set_page_config(page_title="Bot Trading IA - Version Institutionnelle", layout="wide")

# Style CSS sombre / carbone
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

st.title("🎯 Bot d'Analyse Trading Pro — Suite Institutionnelle")
st.markdown("Analyse technique & fondamentale, calculs financiers exacts en Euros (€) et journal de trading.")

# API Keys Gemini
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

    return "### ⚠️ Erreur API Gemini :\n" + "\n\n".join(error_details)

# Actifs
ASSETS_DICTIONARY = {
    "🇺🇸 Actions USA (Wall Street)": {
        "Apple": "AAPL", "Nvidia": "NVDA", "Microsoft": "MSFT", "Amazon": "AMZN",
        "Alphabet (Google)": "GOOGL", "Meta (Facebook)": "META", "Tesla": "TSLA", "AMD": "AMD"
    },
    "🇪🇺 Actions Europe": {
        "TotalEnergies": "TTE.PA", "LVMH": "MC.PA", "ASML": "ASML.AS", "SAP": "SAP.DE"
    },
    "🛢️ Matières Premières": {
        "Pétrole Brent": "BZ=F", "Pétrole WTI": "CL=F", "Or (Gold)": "GC=F", "Argent": "SI=F"
    },
    "💱 Forex": {
        "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X"
    },
    "🪙 Cryptomonnaies": {
        "Bitcoin": "BTC-USD", "Ethereum": "ETH-USD", "Solana": "SOL-USD"
    }
}

TIMEFRAME_MAPPING = {
    "M15": {"interval": "15m", "period": "7d"},
    "H1":  {"interval": "1h",  "period": "30d"},
    "H4":  {"interval": "1h",  "period": "60d"},
    "D1":  {"interval": "1d",  "period": "1y"}
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
                if title:
                    headlines.append(f"- {title}")
        return headlines if headlines else ["Aucune actualité majeure."]
    except Exception:
        return ["Actualités indisponibles."]

def draw_interactive_chart(df, pivot, r1, r2, s1, s2, asset_name, timeframe, zoom_36h=False):
    df_plot = df.copy()
    if zoom_36h and timeframe in ["M15", "H1", "H4"]:
        if isinstance(df_plot.index, pd.DatetimeIndex) and len(df_plot) > 0:
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

    if pivot > 0:
        fig.add_hline(y=pivot, line_dash="dash", line_color="#ffd700", annotation_text=f"Pivot: {pivot:.2f}")
        fig.add_hline(y=r1, line_dash="dot", line_color="#ff8a80", annotation_text=f"R1: {r1:.2f}")
        fig.add_hline(y=s1, line_dash="dot", line_color="#b9f6ca", annotation_text=f"S1: {s1:.2f}")

    fig.update_layout(
        title=f"📈 {asset_name} ({timeframe})",
        template="plotly_dark", paper_bgcolor="#12141a", plot_bgcolor="#181b22", height=500,
        xaxis_rangeslider_visible=False
    )
    return fig

# Initialisation de la session
if "trade_history" not in st.session_state:
    st.session_state.trade_history = []
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "new"
if "current_analysis" not in st.session_state:
    st.session_state.current_analysis = None

# Sidebar
st.sidebar.header("1. Sélection de l'Actif")
selected_category = st.sidebar.selectbox("Catégorie", list(ASSETS_DICTIONARY.keys()))
selected_asset_name = st.sidebar.selectbox("Actif", list(ASSETS_DICTIONARY[selected_category].keys()))
ticker_symbol = ASSETS_DICTIONARY[selected_category][selected_asset_name]

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Paramètres de Position & Risque")
trade_volume = st.sidebar.number_input("Volume engagé (Lots/Unités)", min_value=0.01, value=0.03, step=0.01, format="%.2f")
leverage_value = st.sidebar.number_input("Effet de Levier (1:X)", min_value=1, max_value=500, value=30, step=1)
spread_value = st.sidebar.number_input("Spread (pips / pts)", min_value=0.0, value=0.06, step=0.01, format="%.2f")
pip_value = st.sidebar.number_input("Valeur du Pip/Point (€)", min_value=0.01, value=26.73, step=0.01, format="%.2f")

st.sidebar.markdown("---")
st.sidebar.header("🎯 Prix Cibles Réels (Optionnel)")
custom_entry = st.sidebar.number_input("Prix d'ouverture / Entrée (€)", min_value=0.0, value=108.30, step=0.01, format="%.2f")
custom_tp = st.sidebar.number_input("Take Profit (TP) (€)", min_value=0.0, value=105.15, step=0.01, format="%.2f")
custom_sl = st.sidebar.number_input("Stop Loss (SL) (€)", min_value=0.0, value=108.10, step=0.01, format="%.2f")

# Affichage principal
if st.session_state.active_tab == "new":
    selected_timeframe = st.selectbox("Unité de temps", list(TIMEFRAME_MAPPING.keys()), index=2)
    run_analysis = st.button("🚀 Lancer l'Analyse Institutionnelle", type="primary", use_container_width=True)

    if run_analysis:
        tf_info = TIMEFRAME_MAPPING[selected_timeframe]
        df = load_market_data(ticker_symbol, tf_info["period"], tf_info["interval"])
        df_daily = load_market_data(ticker_symbol, "6m", "1d")

        if not df.empty and 'Close' in df.columns:
            latest = df.iloc[-1]
            current_price = float(latest['Close']) if custom_entry == 0.0 else custom_entry
            
            # --- CALCULS EXONÉRÉS DES ERREURS D'ÉCHELLE ---
            # Distance en points
            tp_points = abs(current_price - custom_tp) if custom_tp > 0 else (3.0 * float(latest.get('High', current_price) - latest.get('Low', current_price)))
            sl_points = abs(current_price - custom_sl) if custom_sl > 0 else (1.5 * float(latest.get('High', current_price) - latest.get('Low', current_price)))
            
            spread_cost = spread_value * pip_value

            # Si SL/TP personnalisés sont fournis, calcul exact sur la valeur du point
            if custom_entry > 0 and custom_tp > 0:
                calc_tp_eur = (tp_points * pip_value) - spread_cost
            else:
                calc_tp_eur = (tp_points * trade_volume * pip_value) - spread_cost

            if custom_entry > 0 and custom_sl > 0:
                # Si SL est au-dessus de l'entrée en SHORT (Gain sécurisé) ou en dessous (Perte)
                if custom_sl < custom_entry: # SL vendeur en gain sécurisé
                    calc_sl_eur = (sl_points * pip_value) - spread_cost
                else: # SL classique en perte
                    calc_sl_eur = -(sl_points * pip_value) - spread_cost
            else:
                calc_sl_eur = -(sl_points * trade_volume * pip_value) - spread_cost

            # Marge requise (Contrat standard Brent approx 1000 barils * volume / levier)
            contract_size = 1000 if "BZ=F" in ticker_symbol or "CL=F" in ticker_symbol else 1
            margin_required_eur = (current_price * trade_volume * contract_size) / leverage_value

            mtf_trend = "Baissière 🔴" if not df_daily.empty and df_daily['Close'].iloc[-1] < df_daily['Close'].rolling(50).mean().iloc[-1] else "Haussière 🟢"

            prompt = f"""
            Analyse {selected_asset_name} ({ticker_symbol}) en {selected_timeframe}.
            Prix d'entrée: {current_price}, TP: {custom_tp}, SL: {custom_sl}.
            Valeur du Point: {pip_value}€, Volume: {trade_volume}, Levier: 1:{leverage_value}.
            """

            ai_report = generate_ai_report(prompt)

            st.session_state.current_analysis = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "asset": selected_asset_name,
                "ticker": ticker_symbol,
                "tf": selected_timeframe,
                "price": current_price,
                "mtf_trend": mtf_trend,
                "confluence": 75,
                "trade_volume": trade_volume,
                "leverage": leverage_value,
                "margin_eur": margin_required_eur,
                "spread_value": spread_value,
                "pip_value": pip_value,
                "risk_eur": calc_sl_eur,
                "tp1_eur": calc_tp_eur,
                "report": ai_report,
                "df": df, "pivot": 0, "r1": 0, "r2": 0, "s1": 0, "s2": 0,
                "executed": False, "result": "En cours"
            }

    if st.session_state.current_analysis:
        ca = st.session_state.current_analysis
        st.markdown(f"## 📊 Rapport : {ca['asset']} ({ca['tf']}) — {ca['timestamp']}")

        m1, m2, m3, m4 = st.columns(4)
        with m1: st.metric("Tendance Daily", ca['mtf_trend'])
        with m2: st.metric("Confluence", f"{ca['confluence']}%")
        with m3: st.metric("Marge Immobilisée", f"{ca['margin_eur']:.2f} €")
        with m4: st.metric("SL / Gain Sécurisé", f"{ca['risk_eur']:.2f} €")

        st.markdown("### 💰 Calculs Financiers Exacts en Euros (€)")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"""
            * **Volume engagé :** `{ca['trade_volume']:.2f} lots`
            * **Effet de Levier :** `1:{ca['leverage']}`
            * **Marge requise :** `{ca['margin_eur']:.2f} €`
            * **Valeur du Pip/Point :** `{ca['pip_value']:.2f} €`
            """)
        with c2:
            st.markdown(f"""
            * **Résultat du Stop Loss (SL) :** `{ca['risk_eur']:.2f} €`
            * **Gain potentiel Take Profit (TP) :** `🟢 +{ca['tp1_eur']:.2f} €`
            """)

        fig = draw_interactive_chart(ca['df'], 0, 0, 0, 0, 0, ca['asset'], ca['tf'])
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(ca['report'])
