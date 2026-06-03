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
            df_temp = pd.read_csv(file, sep=None, engine='python', on_bad_lines='skip', low_memory=True)
            
            # Präzise Spaltenerkennung
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
            # WICHTIG: Wir speichern den echten Namen und die URL separat
            df_clean['Echter_Name'] = df_temp[cols['title']].astype(str)
            df_clean['Shop-Link 🔗'] = df_temp[cols['url']] if cols['url'] else None
            df_clean['Shop'] = df_temp[cols['shop']] if cols['shop'] else file.name
            df_clean['Hersteller'] = df_temp[cols['brand']].astype(str) if cols['brand'] else "N/A"
            
            if cols['price']:
                p_series = df_temp[cols['price']].astype(str).str.replace('EUR', '', case=False).str.replace('€', '')
                p_series = p_series.str.replace('[^\d,.]', '', regex=True).str.replace(',', '.')
                df_clean['Preis (€)'] = pd.to_numeric(p_series, errors='coerce').fillna(0.0)
            else:
                df_clean['Preis (€)'] = 0.0

            df_clean['Status'] = df_temp[cols['stock']].astype(str) if cols['stock'] else "Unbekannt"
            df_clean['Kategorie'] = df_clean['Echter_Name'].apply(lambda x: '🔌 Inverter' if 'tripower' in x.lower() or 'inverter' in x.lower() else ('☀️ Modul' if 'panel' in x.lower() or 'module' in x.lower() else '📦 Sonstiges'))
            df_clean['Vorschau'] = df_temp[cols['image']] if cols['image'] else None
            
            all_data.append(df_clean)
        except Exception as e:
            st.error(f"Fehler in {file.name}: {e}")
            
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return None

# --- UI START ---
st.title('⚡ Solar Mega-Engine')
st.markdown("Suche über 1 Mio. Datensätze. **Klicke auf den Namen**, um zum Shop zu gelangen.")

with st.sidebar:
    st.header("📥 Massen-Import")
    files = st.file_uploader("Lieferanten-CSVs hochladen", type=['csv'], accept_multiple_files=True)
    if st.button("Cache leeren / Daten neu laden"):
        st.cache_data.clear()
        st.rerun()

master_df = load_and_combine_data(files)

if master_df is not None:
    # Autocomplete Index
    @st.cache_data
    def get_search_index(df):
        return sorted(df['Echter_Name'].unique().tolist())

    search_index = get_search_index(master_df)

    st.subheader("🔍 Sofort-Suche")
    selected_product = st.selectbox(
        "Tippe ein Modell ein (z.B. Tripower X 25):",
        options=[""] + search_index,
        format_func=lambda x: "🔎 Schnellsuche..." if x == "" else x,
        index=0
    )

    c1, c2 = st.columns(2)
    with c1:
        sel_shops = st.multiselect("Anbieter:", sorted(master_df['Shop'].unique().tolist()))
    with c2:
        sort_order = st.selectbox("Sortierung:", ["Günstigste zuerst", "Teuerste zuerst", "Alphabetisch"])

    # Filter Logik
    filtered_df = master_df
    if selected_product:
        filtered_df = filtered_df[filtered_df['Echter_Name'] == selected_product]
    if sel_shops:
        filtered_df = filtered_df[filtered_df['Shop'].isin(sel_shops)]

    if sort_order == "Günstigste zuerst":
        filtered_df = filtered_df.sort_values('Preis (€)', ascending=True)
    elif sort_order == "Teuerste zuerst":
        filtered_df = filtered_df.sort_values('Preis (€)', ascending=False)

    st.divider()
    st.write(f"🔍 **Treffer:** {len(filtered_df):,} Produkte")

    # --- KORRIGIERTE ANZEIGE ---
    # Wir nutzen die LinkColumn für den echten Namen
    st.dataframe(
        filtered_df.head(1000),
        column_config={
            "Shop-Link 🔗": st.column_config.LinkColumn(
                "Produktname (Direktlink) 🔗", 
                display_text=filtered_df["Echter_Name"] # Hier wird der Name statt der URL angezeigt
            ),
            "Preis (€)": st.column_config.NumberColumn("Preis (€)", format="%.2f €"),
            "Vorschau": st.column_config.ImageColumn("Bild"),
            "Echter_Name": None # Blende die Hilfsspalte aus
        },
        use_container_width=True,
        height=600,
        hide_index=True
    )
    
    if len(filtered_df) > 1000:
        st.warning("⚠️ Zeige die ersten 1000 Treffer an.")

    # Export
    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button("📊 Auswahl exportieren", csv_data, "solar_export.csv", "text/csv")
else:
    st.info("👋 Bitte lade deine CSV-Dateien hoch.")
