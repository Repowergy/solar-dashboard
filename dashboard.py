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
            # Wir behalten den Namen als String für die Anzeige
            df_clean['Produktname'] = df_temp[cols['title']].fillna("Unbekannt").astype(str)
            # Wir speichern die URL separat
            df_clean['URL_Hidden'] = df_temp[cols['url']].fillna("").astype(str) if cols['url'] else ""
            df_clean['Shop'] = df_temp[cols['shop']].fillna(file.name).astype(str) if cols['shop'] else file.name
            df_clean['Hersteller'] = df_temp[cols['brand']].fillna("N/A").astype(str) if cols['brand'] else "N/A"
            
            if cols['price']:
                df_clean['Preis'] = df_temp[cols['price']].apply(clean_price)
            else:
                df_clean['Preis'] = 0.0

            df_clean['Status'] = df_temp[cols['stock']].fillna("Unbekannt").astype(str) if cols['stock'] else "Unbekannt"
            df_clean['Kategorie'] = df_clean['Produktname'].apply(safe_detect_type)
            df_clean['Bild'] = df_temp[cols['image']].fillna("").astype(str) if cols['image'] else None
            
            all_data.append(df_clean)
        except Exception as e:
            st.error(f"Fehler in {file.name}: {e}")
            
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return None

# --- UI START ---
st.title('⚡ Solar Price Engine (Mega-Engine)')
st.markdown("Suche über alle Dateien hinweg. **Klicke auf den Produktnamen**, um zum Shop zu gelangen.")

with st.sidebar:
    st.header("📥 Massen-Import")
    files = st.file_uploader("Alle Lieferanten-Listen (CSV) hochladen", type=['csv'], accept_multiple_files=True)
    if st.button("🔄 Cache leeren & neu laden"):
        st.cache_data.clear()
        st.rerun()

master_df = load_and_combine_data(files)

if master_df is not None:
    # --- GLOBALE SUCHE ---
    st.subheader("🔍 Globale Suche")
    search_query = st.text_input("Tippe Modell oder Marke ein (z.B. 'Tripower X 25'):", placeholder="Ergebnisse erscheinen sofort...")

    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        sel_shops = st.multiselect("Anbieter filtern:", sorted(master_df['Shop'].unique().tolist()))
    with col_f2:
        sort_order = st.selectbox("Sortierung:", ["Preis: Günstigste zuerst", "Preis: Teuerster zuerst", "Alphabetisch"])

    # --- FILTER LOGIK ---
    filtered_df = master_df
    if search_query:
        kws = search_query.lower().split()
        for kw in kws:
            filtered_df = filtered_df[filtered_df['Produktname'].str.lower().str.contains(kw, na=False)]
    
    if sel_shops:
        filtered_df = filtered_df[filtered_df['Shop'].isin(sel_shops)]

    if sort_order == "Preis: Günstigste zuerst":
        filtered_df = filtered_df.sort_values('Preis', ascending=True)
    elif sort_order == "Preis: Teuerster zuerst":
        filtered_df = filtered_df.sort_values('Preis', ascending=False)
    else:
        filtered_df = filtered_df.sort_values('Produktname', ascending=True)

    # --- ANZEIGE (DER TITEL-FIX) ---
    st.divider()
    st.write(f"📊 **Treffer:** {len(filtered_df):,} Produkte")

    # WICHTIG: Wir nutzen die Spalte 'URL_Hidden' als Datenquelle für den Link, 
    # lassen aber 'Produktname' als Text anzeigen.
    st.dataframe(
        filtered_df[['URL_Hidden', 'Produktname', 'Shop', 'Hersteller', 'Preis', 'Status', 'Kategorie', 'Bild']],
        column_config={
            "URL_Hidden": st.column_config.LinkColumn(
                "Produktname (Link zum Shop) 🔗", 
                display_text=filtered_df["Produktname"], # ZEIGT DEN NAMEN AN
                width="large"
            ),
            "Preis": st.column_config.NumberColumn("Preis", format="%.2f €"),
            "Bild": st.column_config.ImageColumn("Vorschau"),
            "Produktname": None # Blendet die redundante Namens-Spalte aus
        },
        use_container_width=True,
        height=600,
        hide_index=True
    )
    
    if len(filtered_df) > 1000:
        st.warning(f"⚠️ Zeige die ersten 1000 von {len(filtered_df):,} Treffern an.")

    # Export
    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button("📊 Liste als CSV exportieren", csv_data, "solar_export.csv", "text/csv")

else:
    st.info("👋 Bereit. Bitte lade deine CSV-Dateien hoch.")
