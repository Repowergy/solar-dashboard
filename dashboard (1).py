import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title='Solar Product Dashboard', page_icon='☀️', layout='wide')

# Initialize session state
if 'products_df' not in st.session_state:
    st.session_state.products_df = None

st.title('☀️ Solar Product Intelligence Dashboard')
st.markdown('*KI-gestützte Produktanalyse & Katalog-Management*')

# Sidebar
with st.sidebar:
    st.header('📁 Daten laden')
    
    # Load pre-downloaded files
    if st.button('📥 Sun Store laden (3.995 Produkte)', use_container_width=True):
        df = pd.read_csv('/home/user/dashboard_app/sun_store_products_complete.csv')
        df['source'] = 'Sun Store'
        st.session_state.products_df = df
        st.rerun()
    
    if st.button('📥 Solidtrading laden (166 Produkte)', use_container_width=True):
        df = pd.read_csv('/home/user/dashboard_app/solidtrading_products_complete.csv')
        df['source'] = 'Solidtrading'
        st.session_state.products_df = df
        st.rerun()
    
    if st.button('📥 Tritec Energy laden (446 Produkte)', use_container_width=True):
        df = pd.read_csv('/home/user/dashboard_app/tritec_energy_products_complete.csv')
        df['source'] = 'Tritec Energy'
        st.session_state.products_df = df
        st.rerun()
    
    if st.button('📥 ALLE laden (4.607 Produkte)', type='primary', use_container_width=True):
        dfs = []
        for name, path in [
            ('Sun Store', '/home/user/dashboard_app/sun_store_products_complete.csv'),
            ('Solidtrading', '/home/user/dashboard_app/solidtrading_products_complete.csv'),
            ('Tritec Energy', '/home/user/dashboard_app/tritec_energy_products_complete.csv')
        ]:
            df = pd.read_csv(path)
            df['source'] = name
            dfs.append(df)
        
        combined = pd.concat(dfs).drop_duplicates(subset=['product_url'], keep='first')
        st.session_state.products_df = combined
        st.rerun()
    
    st.divider()
    
    # AI Settings
    st.header('🤖 KI-Analyse')
    st.write('**Verfügbare Features:**')
    st.write('• Auto-Kategorisierung')
    st.write('• Dubletten-Erkennung')
    st.write('• Preisanalyse')
    st.write('• Datenqualitäts-Score')
    
    st.info('💡 Alle Features sind automatisch aktiviert!')

def detect_product_type(title, category):
    text = str((title or '') + ' ' + (category or '')).lower()
    
    if any(x in text for x in ['inverter', 'wechselrichter', 'inverter', 'mppt']):
        return '🔌 Wechselrichter'
    elif any(x in text for x in ['solar', 'pv', 'panel', 'modul', 'module', 'shingled']):
        return '☀️ Solarmodul'
    elif any(x in text for x in ['cable', 'kabel', 'leitung', 'wire', 'h1z2z2']):
        return '🔗 Kabel & Leitungen'
    elif any(x in text for x in ['battery', 'batterie', 'speicher', 'akku', 'ess']):
        return '🔋 Speicher'
    elif any(x in text for x in ['mount', 'halter', 'befestigung', 'rack', 'montage']):
        return '🏗️ Montage'
    elif any(x in text for x in ['connector', 'stecker', 'anschluss', 'mc4']):
        return '🔌 Stecker'
    else:
        return '📦 Sonstiges'

def extract_brand(row):
    if pd.notna(row.get('brand')) and str(row['brand']).strip():
        return str(row['brand']).strip()
    if pd.notna(row.get('manufacturer')) and str(row['manufacturer']).strip():
        return str(row['manufacturer']).strip()
    
    # Common brands from title
    title = str(row.get('product_title', '')).upper()
    brands = ['Deye', 'Huawei', 'Fronius', 'SMA', 'SolarEdge', 'KBE', 'LONGi', 
              'JA Solar', 'Trina', 'Jinko', 'Canadian Solar', 'Qcells', 'AIKO', 
              'REC', 'Maxeon', 'SE', 'ABB', 'Victron', 'FIMER']
    
    for brand in brands:
        if brand.upper() in title:
            return brand
    
    return 'Unbekannt'

def calculate_quality(row):
    score = 0
    if pd.notna(row.get('brand')) or pd.notna(row.get('manufacturer')): score += 1
    if pd.notna(row.get('image_urls')): score += 1
    if pd.notna(row.get('description')) and len(str(row['description'])) > 20: score += 1
    if pd.notna(row.get('price')): score += 1
    return score / 4 * 100

def find_duplicates(df):
    titles = df['product_title'].dropna().str.lower().str.strip()
    return titles[titles.duplicated(keep=False)].index.tolist()

# Main content
if st.session_state.products_df is not None:
    df = st.session_state.products_df
    
    # Process data
    df['detected_type'] = df.apply(lambda r: detect_product_type(r.get('product_title'), r.get('category')), axis=1)
    df['brand_clean'] = df.apply(extract_brand, axis=1)
    df['quality_score'] = df.apply(calculate_quality, axis=1)
    
    # Clean prices
    df['price_clean'] = pd.to_numeric(
        df['price'].astype(str).str.replace(',', '.').str.extract(r'([\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*)')[0],
        errors='coerce'
    )
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        '📊 Übersicht', 
        '🔍 Produkte durchsuchen', 
        '🤖 KI-Analyse',
        '📈 Vergleiche Quellen',
        '💾 Export'
    ])
    
    with tab1:
        st.subheader('Dashboard Übersicht')
        
        # KPIs
        col1, col2, col3, col4 = st.columns(4)
        total = len(df)
        with_images = df['image_urls'].notna().sum()
        with_price = df['price_clean'].notna().sum()
        sources = df['source'].nunique()
        
        col1.metric('Gesamt Produkte', total)
        col2.metric('Mit Bildern', with_images, f'{with_images/total*100:.0f}%')
        col3.metric('Mit Preis', with_price, f'{with_price/total*100:.0f}%')
        col4.metric('Quellen', sources)
        
        st.divider()
        
        # Category distribution
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.subheader('Produktkategorien')
            cat_counts = df['detected_type'].value_counts()
            st.bar_chart(cat_counts)
        
        with col2:
            st.subheader('🏆 Top Marken')
            brand_counts = df['brand_clean'].value_counts().head(10)
            st.dataframe(brand_counts.reset_index().rename(columns={'index': 'Marke', 0: 'Anzahl'}), hide_index=True)
        
        # Data quality overview
        st.subheader('Datenqualität')
        quality_dist = pd.cut(df['quality_score'], bins=[0, 25, 50, 75, 100], labels=['Arm', 'Mittel', 'Gut', 'Sehr Gut']).value_counts()
        st.bar_chart(quality_dist)
    
    with tab2:
        st.subheader('🔍 Produkte durchsuchen')
        
        # Search
        search = st.text_input('Suche nach Produktname, Marke oder SKU...', placeholder='z.B. Deye, 10K, KBE Solar...')
        
        # Filters
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filter_type = st.selectbox('Kategorie', ['Alle'] + list(df['detected_type'].unique()))
        with col2:
            filter_source = st.selectbox('Quelle', ['Alle'] + list(df['source'].unique()))
        with col3:
            filter_quality = st.slider('Min. Qualität', 0, 100, 0)
        
        # Apply filters
        filtered = df.copy()
        
        if search:
            search_lower = search.lower()
            filtered = filtered[
                filtered['product_title'].str.lower().str.contains(search_lower, na=False) |
                filtered['brand_clean'].str.lower().str.contains(search_lower, na=False) |
                filtered['sku'].astype(str).str.contains(search_lower, na=False)
            ]
        
        if filter_type != 'Alle':
            filtered = filtered[filtered['detected_type'] == filter_type]
        
        if filter_source != 'Alle':
            filtered = filtered[filtered['source'] == filter_source]
        
        filtered = filtered[filtered['quality_score'] >= filter_quality]
        
        st.write(f'**{len(filtered)} von {len(df)} Produkten** angezeigt')
        
        # Show products
        if len(filtered) > 0:
            for i, (_, row) in enumerate(filtered.head(100).iterrows()):
                title_str = str(row.get('product_title', 'N/A'))[:70]
                with st.expander('📦 ' + title_str + '...', expanded=i < 5):
                    col_a, col_b = st.columns([3, 1])
                    
                    with col_a:
                        st.write('**Marke:** ' + str(row.get('brand_clean', '-')))
                        st.write('**Kategorie:** ' + str(row.get('detected_type', '-')))
                        st.write('**Preis:** ' + str(row.get('price', 'N/A')) + ' ' + str(row.get('currency', '')))
                        st.write('**Quelle:** ' + str(row.get('source', '-')))
                        st.write('**SKU:** ' + str(row.get('sku', '-')))
                        
                        if pd.notna(row.get('description')):
                            with st.expander('📝 Beschreibung'):
                                desc = str(row['description'])
                                if len(desc) > 500:
                                    st.write(desc[:500] + '...')
                                else:
                                    st.write(desc)
                    
                    with col_b:
                        st.metric('Qualität', f'{row.get(0, 0):.0f}%')
                        if pd.notna(row.get('image_urls')):
                            st.success('🖼️ Bild')
                        else:
                            st.warning('❌ Kein Bild')
        else:
            st.info('Keine Produkte gefunden.')
    
    with tab3:
        st.subheader('🤖 KI-Produktanalyse')
        
        # Auto-Categorization
        st.write('### 🔍 Auto-Kategorisierung')
        cat_summary = df.groupby('detected_type').agg({
            'product_title': 'count',
            'price_clean': 'mean'
        }).round(2)
        cat_summary.columns = ['Anzahl', 'Ø Preis (PLN)']
        st.dataframe(cat_summary, use_container_width=True)
        
        st.divider()
        
        # Duplicate Detection
        st.write('### 🔄 Dubletten-Erkennung')
        dup_indices = find_duplicates(df)
        
        if dup_indices:
            st.warning(f'⚠️ **{len(dup_indices)} mögliche Dubletten** gefunden!')
            
            dups = df.loc[dup_indices].sort_values('product_title')
            for title in dups['product_title'].dropna().unique()[:10]:
                same = dups[dups['product_title'].str.lower() == title.lower()]
                title_short = str(title)[:60]
                with st.expander(f'⚠️ {title_short}... ({len(same)}x)'):
                    st.dataframe(same[['source', 'price', 'sku']], hide_index=True)
        else:
            st.success('✅ Keine exakten Dubletten gefunden')
        
        st.divider()
        
        # Price Analysis
        st.write('### 💰 Preis-Analyse')
        price_df = df[df['price_clean'].notna() & (df['price_clean'] > 0)]
        
        if len(price_df) > 0:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric('Min Preis', f'{price_df['price_clean'].min():.2f} PLN')
            col2.metric('Ø Preis', f'{price_df['price_clean'].mean():.2f} PLN')
            col3.metric('Median', f'{price_df['price_clean'].median():.2f} PLN')
            col4.metric('Max Preis', f'{price_df['price_clean'].max():.2f} PLN')
            
            # Price distribution by category
            st.write('**Preisverteilung nach Kategorie:**')
            for cat in df['detected_type'].unique():
                cat_prices = price_df[price_df['detected_type'] == cat]['price_clean']
                if len(cat_prices) > 0:
                    avg_price = cat_prices.mean()
                    st.write(f'{cat}: Ø {avg_price:.0f} PLN (n={len(cat_prices)})')
        else:
            st.info('Nicht genügend Preis-Daten.')
        
        st.divider()
        
        # Missing Data Analysis
        st.write('### 📋 Datenqualitäts-Analyse')
        
        missing = {
            'Brand': df['brand_clean'] == 'Unbekannt',
            'Bild': df['image_urls'].isna(),
            'Preis': df['price'].isna(),
            'Beschreibung': df['description'].isna()
        }
        
        missing_counts = {k: v.sum() for k, v in missing.items()}
        st.bar_chart(missing_counts)
        
        # Products missing critical data
        critical_missing = df[df['brand_clean'] == 'Unbekannt']
        if len(critical_missing) > 0:
            st.warning(f'{len(critical_missing)} Produkte ohne erkannte Marke')
    
    with tab4:
        st.subheader('📈 Quellen-Vergleich')
        
        source_stats = df.groupby('source').agg({
            'product_title': 'count',
            'price_clean': ['mean', 'median'],
            'image_urls': lambda x: x.notna().mean() * 100,
            'description': lambda x: x.notna().mean() * 100,
            'quality_score': 'mean'
        }).round(2)
        
        source_stats.columns = ['Produkte', 'Ø Preis', 'Median Preis', '% Bilder', '% Beschreibung', 'Ø Qualität']
        st.dataframe(source_stats, use_container_width=True)
        
        # Category distribution by source
        st.write('**Kategorieverteilung pro Quelle:**')
        pivot = pd.crosstab(df['source'], df['detected_type'], normalize='index') * 100
        st.bar_chart(pivot)
    
    with tab5:
        st.subheader('💾 Daten exportieren')
        
        col1, col2 = st.columns(2)
        
        with col1:
            export_format = st.selectbox('Format', ['CSV', 'Excel', 'JSON'])
        
        with col2:
            default_cols = ['product_title', 'brand_clean', 'detected_type', 'price', 'source', 'quality_score']
            export_cols = st.multiselect(
                'Spalten auswählen',
                list(df.columns),
                default=default_cols
            )
        
        if st.button('📥 Exportieren', type='primary'):
            export_df = df[export_cols].copy()
            
            if export_format == 'CSV':
                csv = export_df.to_csv(index=False)
                st.download_button('Download CSV', csv, 'products_export.csv', 'text/csv')
            elif export_format == 'Excel':
                st.info('Excel Export in Arbeit...')
            else:
                json_str = export_df.to_json(orient='records', indent=2)
                st.download_button('Download JSON', json_str, 'products_export.json', 'application/json')
        
        # Export filtered data
        st.write('**Aktuelle Filter:**')
        st.write(f'- Gesamt: {len(df)} Produkte')
        st.write(f'- Kategorien: {df['detected_type'].nunique()}')
        st.write(f'- Marken: {df['brand_clean'].nunique()}')

else:
    st.info('👈 **Wähle eine Datenquelle aus der Seitenleiste** um zu beginnen!')
    
    st.subheader('📊 Beispiel-Dashboard Vorschau')
    col1, col2, col3 = st.columns(3)
    
    col1.metric('Verfügbare Quellen', '3')
    col2.metric('Produkte gesamt', '4.607')
    col3.metric('Produktkategorien', '7')
    
    st.markdown('''
    **Verfügbare Funktionen:**
    - ✅ Auto-Kategorisierung (Wechselrichter, Solarmodule, Kabel...)
    - ✅ Dubletten-Erkennung
    - ✅ Preis-Analyse
    - ✅ Datenqualitäts-Score
    - ✅ Quellen-Vergleich
    - ✅ Export (CSV/JSON)
    ''')

st.divider()
st.caption('☀️ Solar Product Intelligence Dashboard | Version 1.0')