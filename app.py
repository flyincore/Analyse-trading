import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import google.generativeai as genai
import plotly.graph_objects as go
import re

# Configuration de la page Streamlit
st.set_page_config(page_title="Bot Trading Technique & Fondamental", layout="wide")

st.title("🎯 Bot d'Analyse Technique & Fondamentale Multi-Actifs")
st.markdown("Combinez l'analyse technique (indicateurs, pivots, graphique) et l'analyse fondamentale (actualités récentes) pour une prise de décision optimale.")

# ---------------------------------------------------------
# Configuration automatique de la clé API
# ---------------------------------------------------------
API_KEY = "AQ.Ab8RN6KvFijAko4RVnTWf9Uf3qE4lVbXgrMsTXay1utBmqq5-w"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-3.8-flash')

# ---------------------------------------------------------
# Dictionnaire des actifs par classe
# ---------------------------------------------------------
ASSETS_DICTIONARY = {
    "Matières Premières (Commodities)": {
        "Pétrole Brent": "BZ=F",
        "Pétrole WTI": "CL=F",
        "Or (Gold)": "GC=F",
        "Argent (Silver)": "SI=F",
        "Gaz Naturel": "NG=F"
    },
    "Forex (Devises)": {
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
        "USD/JPY": "USDJPY=X",
        "AUD/USD": "AUDUSD=X",
        "USD/CAD": "USDCAD=X"
    },
    "Indices Boursiers": {
        "CAC 40": "^FCHI",
        "S&P 500": "^GSPC",
        "Nasdaq 100": "^IXIC",
        "DAX 40": "^GDAXI",
        "Dow Jones": "^DJI"
    },
    "Cryptomonnaies": {
        "Bitcoin (BTC/USD)": "BTC-USD",
        "Ethereum (ETH/USD)": "ETH-USD",
        "Solana (SOL-USD)": "SOL-USD",
        "Ripple (XRP-USD)": "XRP-USD"
    },
    "Actions (US / FR)": {
        "Apple": "AAPL",
        "Nvidia": "NVDA",
        "Tesla": "TSLA",
        "TotalEnergies": "TTE.PA",
        "LVMH": "MC.PA"
    }
}

TIMEFRAME_MAPPING = {
    "M15": {"interval": "15m", "period": "14d"},
    "M30": {"interval": "30m", "period": "30d"},
    "H1":  {"interval": "1h",  "period": "60d"},
    "H4":  {"interval": "1h",  "period": "60d"},
    "D1":  {"interval": "1d",  "period": "1y"}
}

# Fonction de récupération des actualités Yahoo Finance
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
# Barre latérale : Sélection de l'actif
# ---------------------------------------------------------
st.sidebar.header("1. Sélection de l'Actif")

selected_category = st.sidebar.selectbox("Sélectionnez la Classe d'actif", list(ASSETS_DICTIONARY.keys()))
selected_asset_name = st.sidebar.selectbox("Sélectionnez l'Actif", list(ASSETS_DICTIONARY[selected_category].keys()))
ticker_symbol = ASSETS_DICTIONARY[selected_category][selected_asset_name]

st.sidebar.markdown(f"**Ticker Yahoo Finance :** `{ticker_symbol}`")
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

        if df.empty:
            st.error("Erreur : Impossible de récupérer les données de marché.")
        else:
            df['MM50'] = ta.sma(df['Close'], length=50)
            df['MM100'] = ta.sma(df['Close'], length=100)
            df['MM200'] = ta.sma(df['Close'], length=200)
            df['RSI'] = ta.rsi(df['Close'], length=14)
            
            macd_df = ta.macd(df['Close'])
            if macd_df is not None and not macd_df.empty:
                df = pd.concat([df, macd_df], axis=1)

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
            
            macd_cols = [col for col in df.columns if 'MACD_' in col]
            signal_cols = [col for col in df.columns if 'MACDs_' in col]
            macd_line = float(latest[macd_cols[0]]) if macd_cols and pd.notna(latest[macd_cols[0]]) else 0.0
            macd_signal = float(latest[signal_cols[0]]) if signal_cols and pd.notna(latest[signal_cols[0]]) else 0.0

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
            - **Take Profit 2 (TP2) :** [Prix exact ex: 104.00]
            - **Ratio Risque / Récompense (R/R) :** [ex: 1:2.5]
            - **Justification :** [Raison technique + alignment fondamental]
            """

            with st.spinner("Génération de l'analyse globale (Technique + Fondamentale)..."):
                response = model.generate_content(prompt)
                ai_text = response.text

            # --- CONSTRUCTION DU GRAPHIQUE INTERACTIF PLOTLY ---
            fig = go.Figure()

            fig.add_trace(go.Candlestick(
                x=df.index,
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name='Prix'
            ))

            if 'MM50' in df.columns:
                fig.add_trace(go.Scatter(x=df.index, y=df['MM50'], mode='lines', name='MM 50', line=dict(color='orange', width=1.5)))
            if 'MM100' in df.columns:
                fig.add_trace(go.Scatter(x=df.index, y=df['MM100'], mode='lines', name='MM 100', line=dict(color='blue', width=1.5)))
            if 'MM200' in df.columns:
                fig.add_trace(go.Scatter(x=df.index, y=df['MM200'], mode='lines', name='MM 200', line=dict(color='purple', width=1.5)))

            if pivot > 0: fig.add_hline(y=pivot, line_dash="dash", line_color="gray", annotation_text=f"Pivot: {pivot:.2f}")
            if s1 > 0: fig.add_hline(y=s1, line_dash="dot", line_color="indianred", annotation_text=f"S1: {s1:.2f}")
            if r1 > 0: fig.add_hline(y=r1, line_dash="dot", line_color="mediumseagreen", annotation_text=f"R1: {r1:.2f}")

            try:
                buy_entry_match = re.search(r"SCÉNARIO D'ACHAT.*?Point d'entrée recommandé.*?:.*?([0-9]+\.[0-9]+)", ai_text, re.DOTALL)
                buy_sl_match = re.search(r"SCÉNARIO D'ACHAT.*?Stop Loss.*?([0-9]+\.[0-9]+)", ai_text, re.DOTALL)
                buy_tp1_match = re.search(r"SCÉNARIO D'ACHAT.*?Take Profit 1.*?([0-9]+\.[0-9]+)", ai_text, re.DOTALL)
                
                sell_entry_match = re.search(r"SCÉNARIO DE VENTE.*?Point d'entrée recommandé.*?:.*?([0-9]+\.[0-9]+)", ai_text, re.DOTALL)
                sell_sl_match = re.search(r"SCÉNARIO DE VENTE.*?Stop Loss.*?([0-9]+\.[0-9]+)", ai_text, re.DOTALL)
                sell_tp1_match = re.search(r"SCÉNARIO DE VENTE.*?Take Profit 1.*?([0-9]+\.[0-9]+)", ai_text, re.DOTALL)

                if buy_entry_match: fig.add_hline(y=float(buy_entry_match.group(1)), line_dash="solid", line_color="green", annotation_text=f"Entrée Achat: {buy_entry_match.group(1)}")
                if buy_sl_match: fig.add_hline(y=float(buy_sl_match.group(1)), line_dash="dash", line_color="red", annotation_text=f"SL Achat: {buy_sl_match.group(1)}")
                if buy_tp1_match: fig.add_hline(y=float(buy_tp1_match.group(1)), line_dash="dash", line_color="green", annotation_text=f"TP1 Achat: {buy_tp1_match.group(1)}")

                if sell_entry_match: fig.add_hline(y=float(sell_entry_match.group(1)), line_dash="solid", line_color="darkred", annotation_text=f"Entrée Vente: {sell_entry_match.group(1)}")
                if sell_sl_match: fig.add_hline(y=float(sell_sl_match.group(1)), line_dash="dash", line_color="orange", annotation_text=f"SL Vente: {sell_sl_match.group(1)}")
                if sell_tp1_match: fig.add_hline(y=float(sell_tp1_match.group(1)), line_dash="dash", line_color="darkgreen", annotation_text=f"TP1 Vente: {sell_tp1_match.group(1)}")
            except Exception:
                pass

            fig.update_layout(
                title=f"Graphique Technique & Niveaux Clés — {selected_asset_name} ({selected_timeframe})",
                xaxis_title="Date / Heure",
                yaxis_title="Prix ($)",
                template="plotly_dark",
                height=650,
                xaxis_rangeslider_visible=False
            )

            # --- AFFICHAGE STREAMLIT ---
            st.markdown("---")
            
            with st.expander("📰 Voir les flux d'actualités récents capturés", expanded=False):
                for headline in recent_news_list:
                    st.write(headline)

            st.plotly_chart(fig, use_container_width=True, key=f"chart_{ticker_symbol}_{selected_timeframe}")

            st.markdown("---")
            st.markdown("### 📊 Rapport d'Analyse Global")
            st.markdown(ai_text)
