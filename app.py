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
st.markdown("Analyse technique (chandelles, indicateurs, pivots Fibonacci) et fondamentale (actualités en direct) avec visuels de trades, journal et gestion de l'historique.")

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
        "AMD": "AMD"
    },
    "🇪🇺 Actions Europe (Euronext, DAX, LSE)": {
        "TotalEnergies (France)": "TTE.PA",
        "LVMH (France)": "MC.PA",
        "ASML (Pays-Bas)": "ASML.AS",
        "SAP (Allemagne)": "SAP.DE",
        "Siemens (Allemagne)": "SIE.DE",
        "Sanofi (France)": "SAN.PA",
        "Airbus (France/DE)": "AIR.PA"
    },
    "🌏 Actions Asie & Pacifique": {
        "TSMC (Taïwan - ADR US)": "TSM",
        "Toyota (Japon)": "7203.T",
        "Sony (Japon)": "6758.T",
        "Tencent (Hong Kong)": "0700.HK",
        "Alibaba (Hong Kong)": "9988.HK"
    },
    "📊 Indices Boursiers": {
        "S&P 500 (USA)": "^GSPC",
        "Nasdaq 100 (USA)": "^IXIC",
        "CAC 40 (France)": "^FCHI",
        "DAX 40 (Allemagne)": "^GDAXI"
    },
    "🛢️ Matières Premières": {
        "Pétrole Brent": "BZ=F",
        "Or (Gold)": "GC=F",
        "Argent (Silver)": "SI=F"
    },
    "💱 Forex (Devises)": {
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
        "USD/JPY": "USDJPY=X"
    },
    "🪙 Cryptomonnaies": {
        "Bitcoin (BTC/USD)": "BTC-USD",
        "Ethereum (ETH/USD)": "ETH-USD",
        "Solana (SOL-USD)": "SOL-USD"
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
# Extraction ultra-robuste des niveaux de prix
# ---------------------------------------------------------
def extract_number(text_line):
    if not text_line:
        return None
    clean_line = text_line.replace(',', '.')
    match = re.search(r'([0-9]+\.?[0-9]*)', clean_line)
    if match:
        try:
            val = float(match.group(1))
            return val if val > 0 else None
        except ValueError:
            return None
    return None

def extract_trade_levels(ai_text, scenario_type):
    try:
        text_upper = ai_text.upper()
        if "ACHAT" in scenario_type:
            if "SCÉNARIO D'ACHAT" in text_upper or "SCENARIO D'ACHAT" in text_upper:
                pos = text_upper.find("ACHAT")
                section = ai_text[pos:pos+1200]
            else:
                section = ai_text
        else:
            if "SCÉNARIO DE VENTE" in text_upper or "SCENARIO DE VENTE" in text_upper:
                pos = text_upper.find("VENTE")
                section = ai_text[pos:pos+1200]
            else:
                section = ai_text

        entry, sl, tp1, tp2 = None, None, None, None

        for line in section.split('\n'):
            line_up = line.upper()
            if "ENTRÉE" in line_up or "ENTREE" in line_up or "POINT D'ENTRÉE" in line_up:
                if not entry: entry = extract_number(line)
            elif "STOP LOSS" in line_up or "SL" in line_up:
                if not sl: sl = extract_number(line)
            elif "TAKE PROFIT 1" in line_up or "TP1" in line_up or "TAKE PROFIT 1 (TP1)" in line_up:
                if not tp1: tp1 = extract_number(line)
            elif "TAKE PROFIT 2" in line_up or "TP2" in line_up or "TAKE PROFIT 2 (TP2)" in line_up:
                if not tp2: tp2 = extract_number(line)

        return entry, sl, tp1, tp2
    except Exception:
        return None, None, None, None

def draw_trade_setup_chart(entry, sl, tp1, tp2, is_buy=True):
    if not entry or not sl or not tp1:
        return None
    
    fig, ax = plt.subplots(figsize=(7, 3.5))
    fig.patch.set_facecolor('#0e1117')
    ax.set_facecolor('#0e1117')
    
    all_vals = [entry, sl, tp1]
    if tp2: all_vals.append(tp2)
    min_p, max_p = min(all_vals), max(all_vals)
    margin = (max_p - min_p) * 0.30 if max_p != min_p else entry * 0.02
    
    ax.set_ylim(min_p - margin, max_p + margin)
    ax.set_xlim(0, 1)
    ax.axis('off')
    
    if is_buy:
        target_tp = tp2 if tp2 else tp1
        ax.axhspan(entry, target_tp, color='#26a69a', alpha=0.25, label='Zone de Gain (TP)')
        ax.axhspan(sl, entry, color='#ef5350', alpha=0.25, label='Zone de Risque (SL)')
    else:
        target_tp = tp2 if tp2 else tp1
        ax.axhspan(target_tp, entry, color='#26a69a', alpha=0.25, label='Zone de Gain (TP)')
        ax.axhspan(entry, sl, color='#ef5350', alpha=0.25, label='Zone de Risque (SL)')
        
    ax.axhline(entry, color='white', linestyle='-', linewidth=2)
    ax.text(0.5, entry, f'  📍 Point d\'Entrée: {entry:.2f}  ', color='white', fontweight='bold', ha='center', va='center', fontsize=10, bbox=dict(facecolor='#1e222d', edgecolor='white', alpha=0.9, boxstyle='round,pad=0.4'))
    
    ax.axhline(sl, color='#ef5350', linestyle='--', linewidth=1.5)
    ax.text(0.5, sl, f'  🛡️ Stop Loss (SL): {sl:.2f}  ', color='#ff8a80', fontweight='bold', ha='center', va='center', fontsize=9, bbox=dict(facecolor='#1e222d', edgecolor='#ef5350', alpha=0.9, boxstyle='round,pad=0.3'))
    
    ax.axhline(tp1, color='#26a69a', linestyle='--', linewidth=1.5)
    ax.text(0.5, tp1, f'  🎯 Take Profit 1 (TP1): {tp1:.2f}  ', color='#80cbc4', fontweight='bold', ha='center', va='center', fontsize=9, bbox=dict(facecolor='#1e222d', edgecolor='#26a69a', alpha=0.9, boxstyle='round,pad=0.3'))
    
    if tp2:
        ax.axhline(tp2, color='#004d40', linestyle=':', linewidth=1.5)
        ax.text(0.5, tp2, f'  🎯 Take Profit 2 (TP2): {tp2:.2f}  ', color='#a7ffeb', fontweight='bold', ha='center', va='center', fontsize=9, bbox=dict(facecolor='#1e222d', edgecolor='#004d40', alpha=0.9, boxstyle='round,pad=0.3'))

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
        
        # --- Graphique de l'archive ---
        df = entry['df']
        pivot, r1, r2, s1, s2 = entry['pivot'], entry['r1'], entry['r2'], entry['s1'], entry['s2']
        
        fig, ax = plt.subplots(figsize=(10, 5))
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

        ax.vlines(x[up], lows[up], highs[up], color=up_color, linewidth=1)
        ax.vlines(x[down], lows[down], highs[down], color=down_color, linewidth=1)

        body_bottom = np.minimum(opens, closes)
        body_height = np.abs(closes - opens)
        body_height[body_height == 0] = 0.01

        ax.bar(x[up], body_height[up], bottom=body_bottom[up], color=up_color, width=0.6)
        ax.bar(x[down], body_height[down], bottom=body_bottom[down], color=down_color, width=0.6)

        if 'MM50' in df_reset.columns and df_reset['MM50'].notna().any():
            ax.plot(x, df_reset['MM50'], label='MM 50', color='orange', linewidth=1)
        if 'MM200' in df_reset.columns and df_reset['MM200'].notna().any():
            ax.plot(x, df_reset['MM200'], label='MM 200', color='purple', linewidth=1)

        if pivot > 0:
            ax.axhline(y=pivot, color='yellow', linestyle='--', alpha=0.8, label=f'Pivot: {pivot:.2f}')
            ax.axhline(y=r1, color='red', linestyle=':', alpha=0.6, label=f'R1 Fib: {r1:.2f}')
            ax.axhline(y=r2, color='darkred', linestyle=':', alpha=0.6, label=f'R2 Fib: {r2:.2f}')
            ax.axhline(y=s1, color='limegreen', linestyle=':', alpha=0.6, label=f'S1 Fib: {s1:.2f}')
            ax.axhline(y=s2, color='green', linestyle=':', alpha=0.6, label=f'S2 Fib: {s2:.2f}')

        n_ticks = min(6, len(df_reset))
        step = max(1, len(df_reset) // n_ticks)
        tick_indices = list(range(0, len(df_reset), step))
        date_col = 'Datetime' if 'Datetime' in df_reset.columns else 'Date'
        tick_labels = [str(df_reset.iloc[i][date_col]).split()[0] for i in tick_indices]
        
        ax.set_xticks(tick_indices)
        ax.set_xticklabels(tick_labels, rotation=30, fontsize=9)

        ax.set_facecolor('#0e1117')
        fig.patch.set_facecolor('#0e1117')
        ax.tick_params(colors='white')
        ax.xaxis.label.set_color('white')
        ax.yaxis.label.set_color('white')
        ax.title.set_color('white')
        for spine in ax.spines.values():
            spine.set_edgecolor('gray')

        ax.set_title(f"Graphique en Chandelles & Pivots Fibonacci — {entry['asset']} ({entry['tf']})", fontsize=12)
        ax.legend(loc='upper left', facecolor='#262730', edgecolor='none', labelcolor='white')
        ax.grid(True, linestyle=':', alpha=0.3, color='gray')

        st.markdown("---")
        with st.expander("📰 Voir les flux d'actualités capturés lors de l'analyse", expanded=False):
            for headline in entry['news']:
                st.write(headline)

        st.pyplot(fig)

        st.markdown("---")
        st.markdown("### 📊 Rapport d'Analyse Global")
        st.markdown(entry['report'])

        # --- Affichage des graphiques visuels de trade (Achat & Vente) ---
        st.markdown("---")
        st.markdown("### 📈 Visualisation Graphique des Scénarios de Trade")
        
        buy_entry, buy_sl, buy_tp1, buy_tp2 = extract_trade_levels(entry['report'], "ACHAT")
        sell_entry, sell_sl, sell_tp1, sell_tp2 = extract_trade_levels(entry['report'], "VENTE")
        
        col_vis1, col_vis2 = st.columns(2)
        with col_vis1:
            st.markdown("#### 🟢 Visuel du Scénario d'Achat")
            fig_buy_setup = draw_trade_setup_chart(buy_entry, buy_sl, buy_tp1, buy_tp2, is_buy=True)
            if fig_buy_setup:
                st.pyplot(fig_buy_setup)
                plt.close(fig_buy_setup)
            else:
                st.info("Niveaux d'achat non détectés pour ce visuel.")
                
        with col_vis2:
            st.markdown("#### 🔴 Visuel du Scénario de Vente")
            fig_sell_setup = draw_trade_setup_chart(sell_entry, sell_sl, sell_tp1, sell_tp2, is_buy=False)
            if fig_sell_setup:
                st.pyplot(fig_sell_setup)
                plt.close(fig_sell_setup)
            else:
                st.info("Niveaux de vente non détectés pour ce visuel.")

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

        # --- Chat interactif spécifique à l'archive ---
        st.markdown("---")
        st.markdown("### 💬 Affiner l'analyse avec Gemini")
        st.markdown("Posez vos questions complémentaires sur ce trade :")

        chat_key = f"chat_history_id_{entry['id']}"
        if chat_key not in st.session_state:
            st.session_state[chat_key] = []

        for message in st.session_state[chat_key]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if user_query := st.chat_input("Ex: Comment ajuster mon SL sur ce niveau ?", key=f"chat_input_{entry['id']}"):
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
