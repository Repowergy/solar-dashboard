import streamlit as st
import pandas as pd
import re

# --- KONFIGURATION ---
st.set_page_config(page_title='Solar Mega-Engine AI', page_icon='⚡', layout='wide')

# --- HILFSFUNKTIONEN ---
def clean_price(price_val):
    if pd.isna(price_val): return 0.0
    res = str(price_val).replace('EUR', '').replace('€', '').strip()
    res = re.sub(r'[^\d,.]', '', res).replace(',', '.')
    try:
        if res.count('.') > 1:
            parts = res.split('.')
            res = "".join(parts[:-1]) + "." + parts[-1]
        return float(res)
    except: return 0.0

def safe_detect_type(name):
    n = str(name).lower()
    if any(x in n for x in ['inverter', 'wechselrichter', 'falownik', 'tripower']): return '🔌 Inverter'
    if any(x in n for x in ['panel', 'module', 'modul', 'pv', 'shingled']): return '☀️ Modul'
    if any(x in n for x in ['battery', 'batterie', 'speicher', 'akku', 'storage']): return '🔋 Speicher'
    if any(x in n for x in ['cable', 'kabel', 'leitung', 'wire']): return '🔗 Kabel'
    return '📦 Sonstiges'

# --- CACHING DER DATEN ---
@st.cache_data(show_spinner="Analysiere Massendaten...")
def load_and_combine_data(uploaded_files):
    if not uploaded_files:
        return None
    
    all_data = []
    for file in uploaded_files:
        try:
            df_temp = pd.read_csv(file, sep=None, engine='python', on_bad_lines='skip', low_memory=True)
            
            cols = {
                'shop': next((c for c in df_temp.columns if any(x in c.lower() for x in ['shop', 'seller', 'anbieter'])), None),
                'title': next((c for c in df_temp.columns if any(x in c.lower() for x in ['produktname', 'title', 'titel', 'name', 'nazwa'])), df_temp.columns[0]),
                'price': next((c for c in df_temp.columns if any(x in c.lower() for x in ['preis', 'price', 'cena'])), None),
                'stock': next((c for c in df_temp.columns if any(x in c.lower() for x in ['verfügbarkeit', 'stock', 'availability'])), None),
                'url': next((c for c in df_temp.columns if any(x in c.lower() for x in ['url', 'link', 'shop_url'])), None),
                'image': next((c for c in df_temp.columns if any(x in c.lower() for x in ['image', 'bild', 'zdjecie'])), None),
                'brand': next((c for c in df_temp.columns if any(x in c.lower() for x in ['hersteller', 'brand', 'manufacturer'])), None)
            }
            
            df_clean = pd.DataFrame()
            df_clean['Produktname'] = df_temp[cols['title']].fillna("Unbekannt").astype(str)
            df_clean['Link'] = df_temp[cols['url']].fillna("").astype(str) if cols['url'] else df_clean['Produktname']
            df_clean['Shop'] = df_temp[cols['shop']].fillna(file.name).astype(str) if cols['shop'] else file.name
            df_clean['Hersteller'] = df_temp[cols['brand']].fillna("N/A").astype(str) if cols['brand'] else "N/A"
            
            if cols['price']:
                df_clean['Preis'] = df_temp[cols['price']].apply(clean_price)
            else:
                df_clean['Preis'] = 0.0

            df_clean['Status'] = df_temp[cols['stock']].fillna("Unbekannt").astype(str) if cols['stock'] else "Unbekannt"
            df_clean['Kategorie'] = df_clean['Produktname'].apply(safe_detect_type)
            df_clean['Vorschau'] = df_temp[cols['image']].fillna("").astype(str) if cols['image'] else None
            
            all_data.append(df_clean)
        except Exception as e:
            st.error(f"Fehler in {file.name}: {e}")
            
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return None

# --- UI START ---
st.title('⚡ Solar Price Intelligence (Mega-Engine)')
st.markdown("Suche über alle Dateien hinweg. Ergebnisse werden **sofort** beim Tippen gefiltert.")

with st.sidebar:
    st.header("📥 Massen-Import")
    files = st.file_uploader("Alle Lieferanten-Listen (CSV) hochladen", type=['csv'], accept_multiple_files=True)
    if st.button("🔄 Cache leeren & neu laden"):
        st.cache_data.clear()
        st.rerun()

# Daten laden
master_df = load_and_combine_data(files)

if master_df is not None:
    # --- FLEXIBLE SUCHE ---
    st.subheader("🔍 Globale Suche")
    
    # Text-Eingabe für flexible Suche (Tripower X etc.)
    search_query = st.text_input("Tippe Modell, Marke oder EAN ein (z.B. 'Tripower X' oder 'Jinko 440'):", placeholder="Suche startet automatisch beim Tippen...")

    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        sel_shops = st.multiselect("Anbieter filtern:", sorted(master_df['Shop'].unique().tolist()))
    with col_f2:
        sort_order = st.selectbox("Sortierung:", ["Preis: Günstigste zuerst", "Preis: Teuerster zuerst", "Alphabetisch"])

    # --- FILTER LOGIK (Fuzzy & Flexibel) ---
    filtered_df = master_df
    
    if search_query:
        # Splittet Suche in Begriffe auf (AND-Logik für höhere Präzision)
        keywords = search_query.lower().split()
        for kw in keywords:
            filtered_df = filtered_df[filtered_df['Produktname'].str.lower().str.contains(kw, na=False)]
    
    if sel_shops:
        filtered_df = filtered_df[filtered_df['Shop'].isin(sel_shops)]

    # Sortierung
    if sort_order == "Preis: Günstigste zuerst":
        filtered_df = filtered_df.sort_values('Preis', ascending=True)
    elif sort_order == "Preis: Teuerster zuerst":
        filtered_df = filtered_df.sort_values('Preis', ascending=False)
    else:
        filtered_df = filtered_df.sort_values('Produktname', ascending=True)

    # --- ANZEIGE ---
    st.divider()
    st.write(f"📊 **Treffer:** {len(filtered_df):,} von {len(master_df):,} Produkten")

    # Wir nutzen eine performante Tabellenansicht
    st.dataframe(
        filtered_df.head(1000),
        column_config={
            "Link": st.column_config.LinkColumn(
                "Produktname (Link zum Shop) 🔗", 
                display_text=r"(.+)",
                width="large"
            ),
            "Preis": st.column_config.NumberColumn("Preis", format="%.2f €"),
            "Vorschau": st.column_config.ImageColumn("Bild"),
            "Produktname": None # Blende die Rohspalte aus, da der Link den Namen anzeigt
        },
        use_container_width=True,
        height=600,
        hide_index=True
    )
    
    if len(filtered_df) > 1000:
        st.warning(f"⚠️ Zeige nur die ersten 1000 von {len(filtered_df):,} Treffern an. Bitte grenze die Suche weiter ein.")

    # Export
    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button("📊 Gefilterte Liste als CSV exportieren", csv_data, "solar_preisvergleich_suche.csv", "text/csv")

else:
    st.info("👋 Bereit. Bitte lade deine CSV-Dateien in der Sidebar hoch.")
