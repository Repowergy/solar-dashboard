import streamlit as st
import pandas as pd
import re

# --- KONFIGURATION ---
st.set_page_config(page_title='Solar Mega-Engine AI', page_icon='⚡', layout='wide')

# --- HILFSFUNKTIONEN ---
def clean_price(price_val):
    """Bereinigt Preis-Strings sicher und vektorisiert."""
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
    """KI-Kategorisierung mit Fehlerabsicherung gegen Nicht-String-Objekte."""
    n = str(name).lower()
    if any(x in n for x in ['inverter', 'wechselrichter', 'falownik', 'tripower']): return '🔌 Inverter'
    if any(x in n for x in ['panel', 'module', 'modul', 'pv', 'shingled']): return '☀️ Modul'
    if any(x in n for x in ['battery', 'batterie', 'speicher', 'akku', 'storage']): return '🔋 Speicher'
    if any(x in n for x in ['cable', 'kabel', 'leitung', 'wire']): return '🔗 Kabel'
    return '📦 Sonstiges'

# --- CACHING DER DATEN ---
@st.cache_data(show_spinner="Analysiere Massendaten (bis zu 1 Mio. Zeilen)...")
def load_and_combine_data(uploaded_files):
    if not uploaded_files:
        return None
    
    all_data = []
    for file in uploaded_files:
        try:
            # Schnelles Laden
            df_temp = pd.read_csv(file, sep=None, engine='python', on_bad_lines='skip', low_memory=True)
            
            # Intelligente Spaltenerkennung
            cols = {
                'shop': next((c for c in df_temp.columns if any(x in c.lower() for x in ['shop', 'seller', 'anbieter'])), None),
                'title': next((c for c in df_temp.columns if any(x in c.lower() for x in ['produktname', 'title', 'titel', 'name', 'nazwa'])), df_temp.columns[0]),
                'price': next((c for c in df_temp.columns if any(x in c.lower() for x in ['preis', 'price', 'cena'])), None),
                'stock': next((c for c in df_temp.columns if any(x in c.lower() for x in ['verfügbarkeit', 'stock', 'availability'])), None),
                'url': next((c for c in df_temp.columns if any(x in c.lower() for x in ['url', 'link', 'shop_url'])), None),
                'image': next((c for c in df_temp.columns if any(x in c.lower() for x in ['image', 'bild', 'zdjecie'])), None),
                'brand': next((c for c in df_temp.columns if any(x in c.lower() for x in ['hersteller', 'brand', 'manufacturer'])), None)
            }
            
            # Normalisierung & Fehlervermeidung (float-lower fix)
            df_clean = pd.DataFrame()
            df_clean['Produktname'] = df_temp[cols['title']].fillna("Unbekannt").astype(str)
            df_clean['Link'] = df_temp[cols['url']].fillna("").astype(str) if cols['url'] else None
            df_clean['Shop'] = df_temp[cols['shop']].fillna(file.name).astype(str) if cols['shop'] else file.name
            df_clean['Hersteller'] = df_temp[cols['brand']].fillna("N/A").astype(str) if cols['brand'] else "N/A"
            
            # Preisvektorisierung
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
st.title('⚡ Solar Mega-Engine AI')
st.markdown("Analysiere Preise und Bestände in Echtzeit. **Klicke auf den Link**, um zum Shop zu gelangen.")

with st.sidebar:
    st.header("📥 Massen-Import")
    files = st.file_uploader("Alle Lieferanten-Listen (CSV) hochladen", type=['csv'], accept_multiple_files=True)
    if st.button("🔄 Cache leeren & neu laden"):
        st.cache_data.clear()
        st.rerun()

# Daten laden
master_df = load_and_combine_data(files)

if master_df is not None:
    # Such-Index für Autocomplete
    @st.cache_data
    def get_search_index(df):
        return sorted(df['Produktname'].unique().tolist())

    search_index = get_search_index(master_df)

    # --- FILTER BEREICH ---
    st.subheader("🔍 Sofort-Suche & Autocomplete")
    
    selected_product = st.selectbox(
        "Tippe ein Modell oder einen Namen ein:",
        options=[""] + search_index,
        format_func=lambda x: "🔎 Schnellsuche starten..." if x == "" else x,
        index=0
    )

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        sel_shops = st.multiselect("Anbieter filtern:", sorted(master_df['Shop'].unique().tolist()))
    with c2:
        sort_order = st.selectbox("Preissortierung:", ["Günstigste zuerst", "Teuerste zuerst"])
    with c3:
        st.write(f"📊 **Datenbestand:** {len(master_df):,} Produkte")

    # --- FILTER LOGIK ---
    filtered_df = master_df
    if selected_product:
        filtered_df = filtered_df[filtered_df['Produktname'] == selected_product]
    if sel_shops:
        filtered_df = filtered_df[filtered_df['Shop'].isin(sel_shops)]

    if sort_order == "Günstigste zuerst":
        filtered_df = filtered_df.sort_values('Preis', ascending=True)
    else:
        filtered_df = filtered_df.sort_values('Preis', ascending=False)

    # --- ANZEIGE ---
    st.divider()
    
    # Anzeige-Formatierung
    # Wir nutzen 'Link' als klickbare Spalte, zeigen aber den 'Produktname' an
    st.dataframe(
        filtered_df.head(1000),
        column_config={
            "Link": st.column_config.LinkColumn(
                "Produktname (Link zum Shop) 🔗", 
                display_text=r"(.+)" # Verhindert URL-Anzeige, nutzt Inhalt der Link-Zelle
            ),
            "Preis": st.column_config.NumberColumn("Preis", format="%.2f €"),
            "Vorschau": st.column_config.ImageColumn("Bild"),
            "Produktname": st.column_config.TextColumn("Name für Suche")
        },
        use_container_width=True,
        height=600,
        hide_index=True
    )
    
    if len(filtered_df) > 1000:
        st.warning("⚠️ Zeige die ersten 1000 Treffer von {len(filtered_df):,} an.")

    # Export
    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button("📊 Auswahl als CSV exportieren", csv_data, "solar_preisvergleich_export.csv", "text/csv")

else:
    st.info("👋 Willkommen! Bitte laden Sie Ihre CSV-Listen in der Sidebar hoch.")
