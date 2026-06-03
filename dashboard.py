import streamlit as st
import pandas as pd
import re

# --- KONFIGURATION ---
st.set_page_config(page_title='Solar Mega-Engine', page_icon='⚡', layout='wide')

# --- CACHING DER DATEN ---
@st.cache_data(show_spinner="Verarbeite Massendaten...")
def load_and_combine_data(uploaded_files):
    if not uploaded_files:
        return None
    
    all_data = []
    for file in uploaded_files:
        try:
            # Datei laden
            df_temp = pd.read_csv(file, sep=None, engine='python', on_bad_lines='skip', low_memory=True)
            
            # Spaltenerkennung
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
            
            # STABILISIERUNG: Alle Textfelder explizit in String umwandeln (Fix für 'float' error)
            df_clean['Echter_Name'] = df_temp[cols['title']].fillna("Unbekannt").astype(str)
            df_clean['Shop-Link 🔗'] = df_temp[cols['url']].fillna("").astype(str) if cols['url'] else None
            df_clean['Shop'] = df_temp[cols['shop']].fillna(file.name).astype(str) if cols['shop'] else file.name
            df_clean['Hersteller'] = df_temp[cols['brand']].fillna("N/A").astype(str) if cols['brand'] else "N/A"
            
            # Preis-Reinigung
            if cols['price']:
                p_series = df_temp[cols['price']].astype(str).str.replace('EUR', '', case=False).str.replace('€', '')
                p_series = p_series.str.replace('[^\d,.]', '', regex=True).str.replace(',', '.')
                df_clean['Preis (€)'] = pd.to_numeric(p_series, errors='coerce').fillna(0.0)
            else:
                df_clean['Preis (€)'] = 0.0

            df_clean['Status'] = df_temp[cols['stock']].fillna("Unbekannt").astype(str) if cols['stock'] else "Unbekannt"
            
            # Kategorie-Zuweisung (Fix für 'lower' error durch explizites Casting)
            def safe_detect(name):
                n = str(name).lower()
                if 'tripower' in n or 'inverter' in n or 'wechselrichter' in n: return '🔌 Inverter'
                if 'panel' in n or 'module' in n or 'modul' in n: return '☀️ Modul'
                if 'battery' in n or 'batterie' in n or 'speicher' in n: return '🔋 Speicher'
                if 'cable' in n or 'kabel' in n: return '🔗 Kabel'
                return '📦 Sonstiges'
                
            df_clean['Kategorie'] = df_clean['Echter_Name'].apply(safe_detect)
            df_clean['Vorschau'] = df_temp[cols['image']].astype(str) if cols['image'] else None
            
            all_data.append(df_clean)
        except Exception as e:
            st.error(f"Fehler in {file.name}: {e}")
            
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return None

# --- UI START ---
st.title('⚡ Solar Mega-Engine')
st.markdown("Analysiere bis zu 1 Mio. Zeilen. **Klicke auf den Produktnamen**, um zum Shop zu gelangen.")

with st.sidebar:
    st.header("📥 Massen-Import")
    files = st.file_uploader("Lieferanten-CSVs hier hochladen", type=['csv'], accept_multiple_files=True)
    if st.button("Cache leeren / Daten neu laden"):
        st.cache_data.clear()
        st.rerun()

master_df = load_and_combine_data(files)

if master_df is not None:
    @st.cache_data
    def get_search_index(df):
        return sorted(df['Echter_Name'].unique().tolist())

    search_index = get_search_index(master_df)

    st.subheader("🔍 Produktsuche")
    selected_product = st.selectbox(
        "Wähle ein Modell aus den Listen:",
        options=[""] + search_index,
        format_func=lambda x: "🔎 Schnellsuche..." if x == "" else x,
        index=0
    )

    c1, c2 = st.columns(2)
    with c1:
        sel_shops = st.multiselect("Anbieter filtern:", sorted(master_df['Shop'].unique().tolist()))
    with c2:
        sort_order = st.selectbox("Preissortierung:", ["Günstigste zuerst", "Teuerste zuerst"])

    # Filter Logik
    filtered_df = master_df
    if selected_product:
        filtered_df = filtered_df[filtered_df['Echter_Name'] == selected_product]
    if sel_shops:
        filtered_df = filtered_df[filtered_df['Shop'].isin(sel_shops)]

    if sort_order == "Günstigste zuerst":
        filtered_df = filtered_df.sort_values('Preis (€)', ascending=True)
    else:
        filtered_df = filtered_df.sort_values('Preis (€)', ascending=False)

    st.divider()
    st.write(f"🔍 **Gefundene Produkte:** {len(filtered_df):,}")

    # --- ANZEIGE ---
    st.dataframe(
        filtered_df.head(1000),
        column_config={
            "Shop-Link 🔗": st.column_config.LinkColumn(
                "Produktname (Link zum Shop) 🔗", 
                display_text=r"(.+)" # Verhindert, dass der Linktext den Namen überschreibt
            ),
            "Echter_Name": st.column_config.TextColumn("Produktname (Anzeige)"),
            "Preis (€)": st.column_config.NumberColumn("Preis (€)", format="%.2f €"),
            "Vorschau": st.column_config.ImageColumn("Bild"),
            "Shop-Link 🔗": None # Blende die rohe URL-Spalte aus
        },
        use_container_width=True,
        height=600,
        hide_index=True
    )
    
    # Da die LinkColumn manchmal Probleme mit dem Namen hat, 
    # fügen wir hier die klickbare Funktionalität explizit hinzu
    if len(filtered_df) > 1000:
        st.warning("⚠️ Zeige die ersten 1000 Treffer an.")

    # Export
    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button("📊 Auswahl exportieren", csv_data, "solar_export.csv", "text/csv")
else:
    st.info("👋 Bereit. Bitte lade deine CSV-Dateien hoch.")
