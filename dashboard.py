import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title='Solar Price Comparison Engine', page_icon='💰', layout='wide')

# --- KI & MAPPING LOGIK ---
AI_MAPPING = {
    '🔌 Wechselrichter': ['inverter', 'wechselrichter', 'falownik', 'onduleur', 'inversore'],
    '☀️ Solarmodul': ['panel', 'module', 'modul', 'pv', 'shingled', 'bifacial'],
    '🔋 Speicher': ['battery', 'batterie', 'speicher', 'akku', 'storage', 'bateria'],
    '🔗 Kabel': ['cable', 'kabel', 'leitung', 'wire', 'przewód'],
}

def ai_detect_type(text):
    text = str(text).lower()
    for category, keywords in AI_MAPPING.items():
        if any(kw in text for kw in keywords): return category
    return '📦 Sonstiges'

def clean_price(price_val):
    """Extrahiert eine Zahl aus einem Preis-String (z.B. '1.200,50 €' -> 1200.50)"""
    if pd.isna(price_val): return 0.0
    res = re.sub(r'[^\d,.]', '', str(price_val)).replace(',', '.')
    try: return float(res)
    except: return 0.0

# --- UI ---
st.title('💰 Solar Price Comparison Engine')
st.markdown('### Vergleiche Preise über alle 150+ Lieferanten-Listen hinweg')

with st.sidebar:
    st.header("📥 Massen-Upload")
    uploaded_files = st.file_uploader(
        "Ziehe alle deine CSV-Dateien hierher", 
        type=['csv'], 
        accept_multiple_files=True
    )
    st.info(f"Aktuell geladene Dateien: {len(uploaded_files) if uploaded_files else 0}")

if uploaded_files:
    all_data = []
    
    # 1. Alle Dateien einlesen und normalisieren
    for file in uploaded_files:
        df_temp = pd.read_csv(file)
        # Finde Spalten (Titel & Preis)
        t_col = next((c for c in df_temp.columns if any(x in c.lower() for x in ['title', 'titel', 'name', 'nazwa', 'produk'])), df_temp.columns[0])
        p_col = next((c for c in df_temp.columns if any(x in c.lower() for x in ['price', 'preis', 'cena', 'prix'])), None)
        
        if p_col:
            df_final = pd.DataFrame({
                'Produkt': df_temp[t_col],
                'Preis': df_temp[p_col].apply(clean_price),
                'Quelle': file.name,
                'Kategorie': df_temp[t_col].apply(ai_detect_type)
            })
            all_data.append(df_final)

    if all_data:
        master_df = pd.concat(all_data, ignore_index=True)
        
        # --- DASHBOARD BEREICH ---
        t1, t2, t3 = st.tabs(["🏆 Preis-Sieger", "📈 Markt-Analyse", "📋 Alle Daten"])
        
        with t1:
            st.subheader("Welches Produkt ist wo am günstigsten?")
            search_query = st.text_input("Suche nach Modell (z.B. 'Deye 10k' oder 'Jinko 440'):")
            
            if search_query:
                results = master_df[master_df['Produkt'].str.contains(search_query, case=False, na=False)]
                results = results.sort_values('Preis', ascending=True)
                
                if not results.empty:
                    # Markiere den günstigsten
                    best_price = results.iloc[0]
                    st.success(f"🔥 **Bester Preis gefunden:** {best_price['Preis']:.2f} bei Lieferant: **{best_price['Quelle']}**")
                    st.dataframe(results, use_container_width=True)
                else:
                    st.info("Keine Ergebnisse für diese Suche.")

        with t2:
            st.subheader("Händler-Benchmark")
            # Durchschnittspreis pro Quelle
            avg_source = master_df.groupby('Quelle')['Preis'].mean().sort_values()
            st.write("Durchschnittliches Preisniveau pro Lieferant (Günstigste oben):")
            st.bar_chart(avg_source)
            
            st.subheader("Kategorien-Check")
            cat_stats = master_df.groupby('Kategorie').size()
            st.pie_chart(cat_stats)

        with t3:
            st.subheader("Gesamter Datenbestand")
            st.write(f"Insgesamt {len(master_df)} Preis-Einträge aus {len(uploaded_files)} Dateien.")
            st.dataframe(master_df)
else:
    st.warning("Bitte lade die CSV-Dateien in der Sidebar hoch, um den Vergleich zu starten.")

