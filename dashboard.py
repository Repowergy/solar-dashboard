import streamlit as st
import pandas as pd
import re

# Seite konfigurieren
st.set_page_config(page_title='Solar Price Intelligence', page_icon='💰', layout='wide')

# --- FUNKTIONEN ---
def clean_price(price_val):
    if pd.isna(price_val): return 0.0
    # Entfernt Währungen wie 'EUR' und Sonderzeichen
    res = str(price_val).replace('EUR', '').replace('€', '').strip()
    res = re.sub(r'[^\d,.]', '', res).replace(',', '.')
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
st.markdown("Analysiere Preise, Bestände und Shops über alle Listen hinweg.")

with st.sidebar:
    st.header("📥 Daten-Zentrale")
    uploaded_files = st.file_uploader(
        "CSV-Dateien hier hochladen", 
        type=['csv'], 
        accept_multiple_files=True
    )

# --- DATEN-VERARBEITUNG ---
if uploaded_files:
    all_data = []
    
    for file in uploaded_files:
        try:
            df_temp = pd.read_csv(file, sep=None, engine='python', on_bad_lines='skip')
            
            # Spaltenerkennung (Shop, Titel, Preis, EAN, Verfügbarkeit)
            cols = {
                'shop': next((c for c in df_temp.columns if any(x in c.lower() for x in ['shop', 'verkäufer', 'seller', 'anbieter'])), None),
                'title': next((c for c in df_temp.columns if any(x in c.lower() for x in ['produktname', 'title', 'titel', 'name', 'nazwa'])), df_temp.columns[0]),
                'price': next((c for c in df_temp.columns if any(x in c.lower() for x in ['preis', 'price', 'cena'])), None),
                'ean': next((c for c in df_temp.columns if any(x in c.lower() for x in ['artikelnummer', 'ean', 'sku', 'art-nr'])), None),
                'brand': next((c for c in df_temp.columns if any(x in c.lower() for x in ['hersteller', 'brand', 'manufacturer'])), None),
                'stock': next((c for c in df_temp.columns if any(x in c.lower() for x in ['verfügbarkeit', 'stock', 'availability'])), None)
            }
            
            df_clean = pd.DataFrame({
                'Shop/Quelle': df_temp[cols['shop']] if cols['shop'] else file.name,
                'Produktname': df_temp[cols['title']],
                'EAN/ArtNr': df_temp[cols['ean']] if cols['ean'] else 'N/A',
                'Hersteller': df_temp[cols['brand']] if cols['brand'] else 'N/A',
                'Preis': df_temp[cols['price']].apply(clean_price) if cols['price'] else 0.0,
                'Status': df_temp[cols['stock']] if cols['stock'] else 'Unbekannt',
                'Kategorie': df_temp[cols['title']].apply(detect_type)
            })
            all_data.append(df_clean)
        except Exception as e:
            st.error(f"Fehler in Datei {file.name}: {e}")

    if all_data:
        master_df = pd.concat(all_data, ignore_index=True)
        
        # --- FILTER ---
        st.subheader("🔍 Produktsuche")
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            search_query = st.text_input("Nach Modell suchen:")
        with c2:
            shop_filter = st.multiselect("Shop auswählen:", options=list(master_df['Shop/Quelle'].unique()))
        with c3:
            sort_order = st.selectbox("Sortierung", ["Preis: Günstigster zuerst", "Preis: Teuerster zuerst"])

        # Filter anwenden
        filtered_df = master_df.copy()
        if search_query: filtered_df = filtered_df[filtered_df['Produktname'].str.contains(search_query, case=False, na=False)]
        if shop_filter: filtered_df = filtered_df[filtered_df['Shop/Quelle'].isin(shop_filter)]

        if sort_order == "Preis: Günstigster zuerst": filtered_df = filtered_df.sort_values('Preis', ascending=True)
        else: filtered_df = filtered_df.sort_values('Preis', ascending=False)

        st.divider()
        st.write(f"**Treffer:** {len(filtered_df)}")

        if not filtered_df.empty:
            # Tabelle anzeigen (Shop/Quelle steht jetzt ganz links!)
            st.dataframe(filtered_df, use_container_width=True, height=600)
            
            # Export
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button("📊 Auswahl exportieren", csv, "solar_preisvergleich.csv", "text/csv")
else:
    st.info("👋 Bitte lade die CSV-Dateien in der Sidebar hoch.")
