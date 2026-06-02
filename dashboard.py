import streamlit as st
import pandas as pd
import re

# Seite konfigurieren
st.set_page_config(page_title='Solar Price Engine', page_icon='💰', layout='wide')

# --- HILFSFUNKTIONEN ---
def clean_price(price_val):
    if pd.isna(price_val): return 0.0
    # Entfernt alles außer Zahlen, Kommas und Punkten
    res = re.sub(r'[^\d,.]', '', str(price_val)).replace(',', '.')
    try:
        # Falls mehrere Punkte durch Tausender-Trennzeichen entstehen
        if res.count('.') > 1:
            parts = res.split('.')
            res = "".join(parts[:-1]) + "." + parts[-1]
        return float(res)
    except: return 0.0

def detect_type(text):
    text = str(text).lower()
    if any(x in text for x in ['inverter', 'wechselrichter', 'falownik']): return '🔌 Inverter'
    if any(x in text for x in ['panel', 'module', 'modul', 'pv']): return '☀️ Modul'
    if any(x in text for x in ['battery', 'batterie', 'speicher', 'akku']): return '🔋 Speicher'
    return '📦 Sonstiges'

# --- UI START ---
st.title('💰 Solar Price Comparison Engine')
st.info("Lade deine 150+ CSV-Dateien hoch, um hunderte Preise gleichzeitig zu vergleichen.")

with st.sidebar:
    st.header("📥 Daten-Upload")
    uploaded_files = st.file_uploader(
        "Alle CSV-Dateien hier reinziehen", 
        type=['csv'], 
        accept_multiple_files=True
    )

# --- DATEN-VERARBEITUNG ---
if uploaded_files:
    all_data = []
    
    for file in uploaded_files:
        try:
            # Versuche CSV zu lesen (mit Fallback für verschiedene Trennzeichen)
            df_temp = pd.read_csv(file, sep=None, engine='python')
            
            # Spalten-Mapping (Suche nach Titeln und Preisen)
            t_col = next((c for c in df_temp.columns if any(x in c.lower() for x in ['title', 'titel', 'name', 'nazwa', 'produk'])), df_temp.columns[0])
            p_col = next((c for c in df_temp.columns if any(x in c.lower() for x in ['price', 'preis', 'cena', 'prix'])), None)
            
            if p_col:
                df_clean = pd.DataFrame({
                    'Produkt': df_temp[t_col],
                    'Preis': df_temp[p_col].apply(clean_price),
                    'Lieferant': file.name,
                    'Kategorie': df_temp[t_col].apply(detect_type)
                })
                all_data.append(df_clean)
        except Exception as e:
            st.error(f"Fehler in Datei {file.name}: {e}")

    if all_data:
        master_df = pd.concat(all_data, ignore_index=True)
        
        # Tabs für die Übersicht
        tab1, tab2, tab3 = st.tabs(["🏆 Bester Preis Suche", "📈 Marktanalyse", "📋 Rohdaten"])
        
        with tab1:
            st.subheader("🔍 Globale Produktsuche")
            query = st.text_input("Suche nach Modellname (z.B. 'Deye 10k', 'Jinko 440', etc.):")
            
            if query:
                # Suche über alle Produkte
                results = master_df[master_df['Produkt'].str.contains(query, case=False, na=False)]
                results = results.sort_values('Preis', ascending=True)
                
                if not results.empty:
                    # Der günstigste ganz oben
                    best = results.iloc[0]
                    st.success(f"Günstigstes Angebot: **{best['Preis']:.2f}** bei **{best['Lieferant']}**")
                    
                    # Schöne Tabelle
                    st.dataframe(results.style.format({"Preis": "{:.2f}"}), use_container_width=True)
                else:
                    st.warning("Keine Treffer für diese Suche.")
            else:
                st.write("Gib oben einen Namen ein, um Preise zu vergleichen.")

        with tab2:
            st.subheader("📊 Auswertungen")
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Top 10 Günstigste Lieferanten (Ø-Preis):**")
                avg_prices = master_df.groupby('Lieferant')['Preis'].mean().sort_values().head(10)
                st.bar_chart(avg_prices)
            
            with col2:
                st.write("**Verteilung der Produktgruppen:**")
                cat_counts = master_df['Kategorie'].value_counts()
                st.bar_chart(cat_counts) # Bar chart ist sicherer als Pie in alten Versionen

        with tab3:
            st.subheader("Vollständige Liste")
            st.write(f"Daten aus {len(uploaded_files)} Dateien mit insgesamt {len(master_df)} Produkten.")
            st.dataframe(master_df)

else:
    st.warning("Bitte ziehe deine CSV-Dateien in die linke Seitenleiste.")
