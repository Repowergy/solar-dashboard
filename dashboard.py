import streamlit as st
import pandas as pd
import re

# Seite konfigurieren
st.set_page_config(page_title='Solar Price Intelligence', page_icon='💰', layout='wide')

# --- FUNKTIONEN ---
def clean_price(price_val):
    if pd.isna(price_val): return 0.0
    res = re.sub(r'[^\d,.]', '', str(price_val)).replace(',', '.')
    try:
        if res.count('.') > 1:
            parts = res.split('.')
            res = "".join(parts[:-1]) + "." + parts[-1]
        return float(res)
    except: return 0.0

def detect_type(text):
    text = str(text).lower()
    if any(x in text for x in ['inverter', 'wechselrichter', 'falownik']): return '🔌 Inverter'
    if any(x in text for x in ['panel', 'module', 'modul', 'pv', 'shingled']): return '☀️ Modul'
    if any(x in text for x in ['battery', 'batterie', 'speicher', 'akku', 'storage']): return '🔋 Speicher'
    if any(x in text for x in ['cable', 'kabel', 'leitung', 'wire']): return '🔗 Kabel'
    return '📦 Sonstiges'

# --- UI START ---
st.title('💰 Solar Price Comparison & Filter Engine')
st.markdown("Analysiere und filtere über 150+ Lieferantenlisten gleichzeitig.")

with st.sidebar:
    st.header("📥 Daten-Zentrale")
    uploaded_files = st.file_uploader(
        "Alle CSV-Dateien hier hochladen", 
        type=['csv'], 
        accept_multiple_files=True
    )
    if uploaded_files:
        st.success(f"{len(uploaded_files)} Dateien aktiv")

# --- DATEN-VERARBEITUNG ---
if uploaded_files:
    all_data = []
    
    for file in uploaded_files:
        try:
            # Schnelles Einlesen für große Dateien
            df_temp = pd.read_csv(file, sep=None, engine='python', on_bad_lines='skip')
            
            # Spaltenerkennung
            cols = {
                'title': next((c for c in df_temp.columns if any(x in c.lower() for x in ['title', 'titel', 'name', 'nazwa', 'produk'])), df_temp.columns[0]),
                'price': next((c for c in df_temp.columns if any(x in c.lower() for x in ['price', 'preis', 'cena', 'prix'])), None),
                'ean': next((c for c in df_temp.columns if any(x in c.lower() for x in ['ean', 'gtin', 'art-nr', 'sku'])), None),
                'brand': next((c for c in df_temp.columns if any(x in c.lower() for x in ['brand', 'hersteller', 'manufacturer', 'marka'])), None)
            }
            
            df_clean = pd.DataFrame({
                'Produktname': df_temp[cols['title']],
                'EAN/SKU': df_temp[cols['ean']] if cols['ean'] else 'N/A',
                'Hersteller': df_temp[cols['brand']] if cols['brand'] else 'N/A',
                'Preis': df_temp[cols['price']].apply(clean_price) if cols['price'] else 0.0,
                'Anbieter': file.name,
                'Kategorie': df_temp[cols['title']].apply(detect_type)
            })
            all_data.append(df_clean)
        except Exception as e:
            st.error(f"Fehler in Datei {file.name}: {e}")

    if all_data:
        master_df = pd.concat(all_data, ignore_index=True)
        
        # --- GLOBALE FILTER ---
        st.subheader("🔍 Globale Suche & Filter")
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            search_query = st.text_input("Suche nach Produktname oder Modell:")
        with c2:
            ean_query = st.text_input("Suche nach EAN / Artikelnummer:")
        with c3:
            sort_order = st.selectbox("Sortierung", ["Preis: Günstigster zuerst", "Preis: Teuerster zuerst", "Name A-Z"])

        with st.expander("➕ Erweiterte Filter"):
            f1, f2, f3 = st.columns(3)
            with f1:
                selected_cats = st.multiselect("Kategorien:", options=list(master_df['Kategorie'].unique()), default=list(master_df['Kategorie'].unique()))
            with f2:
                selected_brands = st.multiselect("Hersteller:", options=list(master_df['Hersteller'].unique()))
            with f3:
                selected_sources = st.multiselect("Anbieter:", options=list(master_df['Anbieter'].unique()))

        # Filter anwenden
        filtered_df = master_df.copy()
        if search_query: filtered_df = filtered_df[filtered_df['Produktname'].str.contains(search_query, case=False, na=False)]
        if ean_query: filtered_df = filtered_df[filtered_df['EAN/SKU'].astype(str).str.contains(ean_query, case=False, na=False)]
        if selected_cats: filtered_df = filtered_df[filtered_df['Kategorie'].isin(selected_cats)]
        if selected_brands: filtered_df = filtered_df[filtered_df['Hersteller'].isin(selected_brands)]
        if selected_sources: filtered_df = filtered_df[filtered_df['Anbieter'].isin(selected_sources)]

        # Sortierung
        if sort_order == "Preis: Günstigster zuerst": filtered_df = filtered_df.sort_values('Preis', ascending=True)
        elif sort_order == "Preis: Teuerster zuerst": filtered_df = filtered_df.sort_values('Preis', ascending=False)
        else: filtered_df = filtered_df.sort_values('Produktname', ascending=True)

        st.divider()
        st.write(f"**Ergebnis:** {len(filtered_df)} Treffer gefunden.")

        # --- FIX: STABILE ANZEIGE FÜR GROSSE DATENMENGEN ---
        if not filtered_df.empty:
            # Top-Deal Anzeige nur bei Suche
            if (search_query or ean_query) and sort_order == "Preis: Günstigster zuerst":
                best = filtered_df.iloc[0]
                st.success(f"🔥 **Bester Preis:** {best['Preis']:.2f} € bei **{best['Anbieter']}**")

            # Wir zeigen die Daten ohne .style (vermeidet Absturz) in einem performanten Dataframe
            st.dataframe(filtered_df, use_container_width=True, height=500)
            
            # Export
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button("📊 Auswahl als CSV exportieren", csv, "solar_export.csv", "text/csv")
        else:
            st.warning("Keine Treffer.")
else:
    st.info("👋 Bitte lade deine CSV-Dateien in der Sidebar hoch.")
