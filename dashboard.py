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
    if any(x in text for x in ['inverter', 'wechselrichter', 'falownik', 'onduleur']): return '🔌 Inverter'
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
    st.divider()
    if uploaded_files:
        st.success(f"{len(uploaded_files)} Dateien aktiv")

# --- DATEN-VERARBEITUNG ---
if uploaded_files:
    all_data = []
    
    for file in uploaded_files:
        try:
            # CSV flexibel einlesen
            df_temp = pd.read_csv(file, sep=None, engine='python', on_bad_lines='skip')
            
            # Automatische Spaltenerkennung (Sucht nach Schlüsselwörtern in jeder Sprache)
            cols = {
                'title': next((c for c in df_temp.columns if any(x in c.lower() for x in ['title', 'titel', 'name', 'nazwa', 'produk', 'label'])), df_temp.columns[0]),
                'price': next((c for c in df_temp.columns if any(x in c.lower() for x in ['price', 'preis', 'cena', 'prix', 'prezzo'])), None),
                'ean': next((c for c in df_temp.columns if any(x in c.lower() for x in ['ean', 'gtin', 'art-nr', 'article', 'sku'])), None),
                'brand': next((c for c in df_temp.columns if any(x in c.lower() for x in ['brand', 'hersteller', 'manufacturer', 'marka'])), None)
            }
            
            # Normalisierung der Daten
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
        
        # --- GLOBALE FILTER SEKTION ---
        st.subheader("🔍 Globale Suche & Filter")
        
        # Obere Filter-Leiste
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            search_query = st.text_input("Suche nach Produktname oder Modell:", placeholder="z.B. Deye, Jinko, 10kW...")
        with c2:
            ean_query = st.text_input("Suche nach EAN / Artikelnummer:")
        with c3:
            sort_order = st.selectbox("Sortierung", ["Preis: Günstigster zuerst", "Preis: Teuerster zuerst", "Name A-Z"])

        # Erweiterte Filter (Expander)
        with st.expander("➕ Erweiterte Filter (Kategorie, Hersteller, Anbieter)"):
            f1, f2, f3 = st.columns(3)
            with f1:
                selected_cats = st.multiselect("Kategorien wählen:", options=list(master_df['Kategorie'].unique()), default=list(master_df['Kategorie'].unique()))
            with f2:
                selected_brands = st.multiselect("Hersteller wählen:", options=list(master_df['Hersteller'].unique()))
            with f3:
                selected_sources = st.multiselect("Anbieter wählen:", options=list(master_df['Anbieter'].unique()))

        # --- FILTER LOGIK ANWENDEN ---
        filtered_df = master_df.copy()

        if search_query:
            filtered_df = filtered_df[filtered_df['Produktname'].str.contains(search_query, case=False, na=False)]
        
        if ean_query:
            filtered_df = filtered_df[filtered_df['EAN/SKU'].astype(str).str.contains(ean_query, case=False, na=False)]

        if selected_cats:
            filtered_df = filtered_df[filtered_df['Kategorie'].isin(selected_cats)]

        if selected_brands:
            filtered_df = filtered_df[filtered_df['Hersteller'].isin(selected_brands)]

        if selected_sources:
            filtered_df = filtered_df[filtered_df['Anbieter'].isin(selected_sources)]

        # Sortierung anwenden
        if sort_order == "Preis: Günstigster zuerst":
            filtered_df = filtered_df.sort_values('Preis', ascending=True)
        elif sort_order == "Preis: Teuerster zuerst":
            filtered_df = filtered_df.sort_values('Preis', ascending=False)
        else:
            filtered_df = filtered_df.sort_values('Produktname', ascending=True)

        # --- ANZEIGE ---
        st.divider()
        st.write(f"**Ergebnis:** {len(filtered_df)} Treffer gefunden.")

        if not filtered_df.empty:
            # Hervorhebung des günstigsten Preises
            if sort_order == "Preis: Günstigster zuerst" and not search_query == "":
                best_deal = filtered_df.iloc[0]
                st.success(f"💡 **Top Deal:** {best_deal['Preis']:.2f} € bei **{best_deal['Anbieter']}** ({best_deal['Produktname']})")

            # Tabelle mit Formatierung
            st.dataframe(
                filtered_df.style.format({
                    "Preis": "{:.2f} €"
                }), 
                use_container_width=True,
                height=600
            )
        else:
            st.warning("Keine Produkte mit diesen Filtereinstellungen gefunden.")

        # Export Funktion
        csv = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📊 Diese Auswahl als CSV exportieren",
            data=csv,
            file_name="solar_preisvergleich_export.csv",
            mime="text/csv",
        )
else:
    # Begrüßung wenn keine Daten da sind
    st.info("👋 Willkommen! Bitte lade deine Lieferanten-CSV-Dateien in der Sidebar hoch.")
    st.image("https://img.icons8.com/clouds/200/solar-panel.png")
