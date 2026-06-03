import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title='Solar Mega-Engine AI', page_icon='⚡', layout='wide')

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

def find_column(df_columns, keywords):
    cols_list = [str(c).lower().strip() for c in df_columns]
    for kw in keywords:
        if kw in cols_list:
            idx = cols_list.index(kw)
            return df_columns[idx]
    for i, col_low in enumerate(cols_list):
        for kw in keywords:
            if kw in col_low:
                return df_columns[i]
    return None

def process_csv(uploaded_file):
    try:
        content = uploaded_file.read()
        uploaded_file.seek(0)
        
        try:
            df = pd.read_csv(io.BytesIO(content), sep=',', on_bad_lines='skip', low_memory=False, encoding='utf-8')
        except:
            df = pd.read_csv(io.BytesIO(content), sep=';', on_bad_lines='skip', low_memory=False, encoding='utf-8')
        
        if len(df.columns) < 3:
            df = pd.read_csv(io.BytesIO(content), sep=';', on_bad_lines='skip', low_memory=False)
        
        st.sidebar.success(f"✅ {uploaded_file.name}: {len(df):,} Zeilen geladen")
        st.sidebar.caption(f"Spalten: {list(df.columns)}")
        
        cols = {
            'shop': find_column(df.columns, ['shop', 'seller', 'anbieter']),
            'title': find_column(df.columns, ['produktname', 'product_title', 'title', 'titel', 'name']),
            'price': find_column(df.columns, ['preis', 'price', 'cena']),
            'stock': find_column(df.columns, ['verfügbarkeit', 'verfugbarkeit', 'stock', 'availability']),
            'url': find_column(df.columns, ['shop_url', 'product_url', 'url', 'link']),
            'image': find_column(df.columns, ['image_urls', 'image', 'bild']),
            'brand': find_column(df.columns, ['hersteller', 'brand', 'manufacturer'])
        }
        
        st.sidebar.caption(f"Mapping: {cols}")
        
        if cols['title'] is None:
            cols['title'] = df.columns[0]
        
        result = pd.DataFrame()
        result['Produktname'] = df[cols['title']].fillna("").astype(str).replace("", "Unbekannt")
        result['URL'] = df[cols['url']].fillna("").astype(str) if cols['url'] else ""
        result['Shop'] = df[cols['shop']].fillna(uploaded_file.name).astype(str) if cols['shop'] else uploaded_file.name
        result['Hersteller'] = df[cols['brand']].fillna("N/A").astype(str) if cols['brand'] else "N/A"
        
        if cols['price']:
            result['Preis'] = df[cols['price']].apply(clean_price)
        else:
            result['Preis'] = 0.0
        
        result['Status'] = df[cols['stock']].fillna("Auf Anfrage").astype(str) if cols['stock'] else "Auf Anfrage"
        result['Kategorie'] = result['Produktname'].apply(safe_detect_type)
        result['Bild'] = df[cols['image']].fillna("").astype(str) if cols['image'] else ""
        
        return result
    except Exception as e:
        st.error(f"Fehler bei {uploaded_file.name}: {e}")
        import traceback
        st.sidebar.code(traceback.format_exc())
        return None

st.title('⚡ Solar Price Engine (Mega-Engine)')
st.markdown("Suche über alle Dateien hinweg. **Klicke auf 'Öffnen'**, um zum Shop zu gelangen.")

with st.sidebar:
    st.header("📥 Massen-Import")
    files = st.file_uploader("Alle Lieferanten-Listen (CSV) hochladen", type=['csv'], accept_multiple_files=True)

if files:
    if 'last_files' not in st.session_state or st.session_state.get('last_files') != [f.name for f in files]:
        with st.spinner("Verarbeite Dateien..."):
            all_dfs = []
            for f in files:
                df = process_csv(f)
                if df is not None and len(df) > 0:
                    all_dfs.append(df)
            
            if all_dfs:
                st.session_state['master_df'] = pd.concat(all_dfs, ignore_index=True)
                st.session_state['last_files'] = [f.name for f in files]

master_df = st.session_state.get('master_df')

if master_df is not None and len(master_df) > 0:
    st.subheader("🔍 Globale Suche")
    search_query = st.text_input("Tippe Modell oder Marke ein (z.B. 'Tripower X 25'):", placeholder="Ergebnisse erscheinen sofort beim Tippen...")

    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
    with col_f1:
        sel_shops = st.multiselect("Anbieter filtern:", sorted(master_df['Shop'].unique().tolist()))
    with col_f2:
        sort_order = st.selectbox("Sortierung:", ["Preis: Günstigste zuerst", "Preis: Teuerster zuerst", "Alphabetisch", "Mit Preis zuerst"])
    with col_f3:
        show_all = st.checkbox("Auch Produkte ohne Preis", value=True)

    filtered_df = master_df.copy()
    
    if search_query:
        kws = search_query.lower().split()
        for kw in kws:
            filtered_df = filtered_df[filtered_df['Produktname'].str.lower().str.contains(kw, na=False)]
    
    if sel_shops:
        filtered_df = filtered_df[filtered_df['Shop'].isin(sel_shops)]

    if sort_order == "Preis: Günstigste zuerst":
        if show_all:
            filtered_df = filtered_df.sort_values('Preis', ascending=True)
        else:
            filtered_df = filtered_df[filtered_df['Preis'] > 0].sort_values('Preis', ascending=True)
    elif sort_order == "Preis: Teuerster zuerst":
        filtered_df = filtered_df.sort_values('Preis', ascending=False)
    elif sort_order == "Mit Preis zuerst":
        filtered_df = filtered_df.sort_values('Preis', ascending=False)
    else:
        filtered_df = filtered_df.sort_values('Produktname', ascending=True)

    st.divider()
    
    with_price = (filtered_df['Preis'] > 0).sum()
    without_price = (filtered_df['Preis'] == 0).sum()
    
    col_s1, col_s2, col_s3 = st.columns(3)
    col_s1.metric("📊 Gesamt-Treffer", f"{len(filtered_df):,}")
    col_s2.metric("💰 Mit Preis", f"{with_price:,}")
    col_s3.metric("📞 Auf Anfrage", f"{without_price:,}")

    display_df = filtered_df.head(1000).copy()
    
    st.dataframe(
        display_df[['URL', 'Produktname', 'Shop', 'Hersteller', 'Preis', 'Status', 'Kategorie', 'Bild']],
        column_config={
            "URL": st.column_config.LinkColumn("Zum Shop 🔗", display_text="Öffnen", width="small"),
            "Produktname": st.column_config.TextColumn("Produktname", width="large"),
            "Preis": st.column_config.NumberColumn("Preis", format="%.2f €"),
            "Bild": st.column_config.ImageColumn("Vorschau", width="small"),
            "Shop": st.column_config.TextColumn("Shop"),
            "Hersteller": st.column_config.TextColumn("Hersteller"),
            "Status": st.column_config.TextColumn("Status"),
            "Kategorie": st.column_config.TextColumn("Kategorie")
        },
        use_container_width=True,
        height=600,
        hide_index=True
    )
    
    if len(filtered_df) > 1000:
        st.warning(f"⚠️ Zeige die ersten 1000 von {len(filtered_df):,} Treffern an.")

    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button("📊 Liste als CSV exportieren", csv_data, "solar_export.csv", "text/csv")

else:
    st.info("👋 Bereit. Bitte lade deine CSV-Dateien hoch.")
