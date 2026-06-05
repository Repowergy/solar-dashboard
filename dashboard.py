
Claude hat die Antwort abgeschlossen

import streamlit as st import pandas as pd import re import io st.set_page_config(page_title='Solar Mega-Engine AI', page_icon='⚡', layout='wide') def clean_price(price_val): if pd.isna(price_val): return 0.0 res = str(price_val).replace('EUR', '').replace('€', '').strip() re

pasted

ergänze zusätzlich das dashboard das wenn ich eiinen bestimmten hersteller suche seperat es einen reter gibt der mir sagt welcher shop diesen hersteller hat
07:28
Ich ergänze die app.py um einen Hersteller-Radar als separaten Reiter direkt im bestehenden Dashboard.


2 Befehle ausgeführt, datei lesen
2 Befehle ausgeführt, datei lesen
Das neue solar_price_engine.py hat jetzt zwei Tabs:

Tab 1 — 🔍 Produktsuche (unverändert wie bisher)

Tab 2 — 🏭 Hersteller-Radar (neu) — was du gebaut bekommst:

Freitextsuche nach Hersteller-Name (z.B. „SMA", „Fronius", „Huawei") — durchsucht sowohl die Hersteller-Spalte als auch den Produktnamen
Dropdown-Multiselect zur direkten Auswahl aus allen bekannten Herstellern
KPI-Zeile oben: wie viele Hersteller gefunden, in wie vielen Shops, wie viele Produkte gesamt
Shop-Übersicht (die eigentliche Radar-Tabelle): zeigt pro Shop + Hersteller die Anzahl Produkte, günstigsten Preis, teuersten Preis und welche Kategorien geführt werden
Detaillierte Produktliste darunter mit Link zum Shop
CSV-Export für die Treffer
Einfach die alte app.py durch diese Datei ersetzen — keine weiteren Abhängigkeiten nötig.


Solar price engine
PY 


Möchtest du benachrichtigt werden, wenn Claude antwortet?




Claude ist eine KI und kann Fehler machen. Bitte überprüfe die Antworten.
Solar price engine · PY
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
            'shop':  find_column(df.columns, ['shop', 'seller', 'anbieter']),
            'title': find_column(df.columns, ['produktname', 'product_title', 'title', 'titel', 'name']),
            'price': find_column(df.columns, ['preis', 'price', 'cena']),
            'stock': find_column(df.columns, ['verfügbarkeit', 'verfugbarkeit', 'stock', 'availability']),
            'url':   find_column(df.columns, ['shop_url', 'product_url', 'url', 'link']),
            'image': find_column(df.columns, ['image_urls', 'image', 'bild']),
            'brand': find_column(df.columns, ['hersteller', 'brand', 'manufacturer'])
        }
 
        st.sidebar.caption(f"Mapping: {cols}")
 
        if cols['title'] is None:
            cols['title'] = df.columns[0]
 
        result = pd.DataFrame()
        result['Produktname'] = df[cols['title']].fillna("").astype(str).replace("", "Unbekannt")
        result['URL']         = df[cols['url']].fillna("").astype(str)   if cols['url']   else ""
        result['Shop']        = df[cols['shop']].fillna(uploaded_file.name).astype(str) if cols['shop'] else uploaded_file.name
        result['Hersteller']  = df[cols['brand']].fillna("N/A").astype(str) if cols['brand'] else "N/A"
        result['Preis']       = df[cols['price']].apply(clean_price) if cols['price'] else 0.0
        result['Status']      = df[cols['stock']].fillna("Auf Anfrage").astype(str) if cols['stock'] else "Auf Anfrage"
        result['Kategorie']   = result['Produktname'].apply(safe_detect_type)
        result['Bild']        = df[cols['image']].fillna("").astype(str) if cols['image'] else ""
 
        return result
    except Exception as e:
        st.error(f"Fehler bei {uploaded_file.name}: {e}")
        import traceback
        st.sidebar.code(traceback.format_exc())
        return None
 
# ──────────────────────────────────────────────────────────────────────────────
# Layout
# ──────────────────────────────────────────────────────────────────────────────
 
st.title('⚡ Solar Price Engine (Mega-Engine)')
st.markdown("Suche über alle Dateien hinweg. **Klicke auf 'Öffnen'**, um zum Shop zu gelangen.")
 
with st.sidebar:
    st.header("📥 Massen-Import")
    files = st.file_uploader(
        "Alle Lieferanten-Listen (CSV) hochladen",
        type=['csv'],
        accept_multiple_files=True
    )
 
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
 
    tab_search, tab_radar = st.tabs(["🔍 Produktsuche", "🏭 Hersteller-Radar"])
 
    # ──────────────────────────────────────────────────────────────────────────
    # TAB 1 – Produktsuche (original)
    # ──────────────────────────────────────────────────────────────────────────
    with tab_search:
        search_query = st.text_input(
            "Tippe Modell oder Marke ein (z.B. 'Tripower X 25'):",
            placeholder="Ergebnisse erscheinen sofort beim Tippen..."
        )
 
        col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
        with col_f1:
            sel_shops = st.multiselect("Anbieter filtern:", sorted(master_df['Shop'].unique().tolist()))
        with col_f2:
            sort_order = st.selectbox(
                "Sortierung:",
                ["Preis: Günstigste zuerst", "Preis: Teuerster zuerst", "Alphabetisch", "Mit Preis zuerst"]
            )
        with col_f3:
            show_all = st.checkbox("Auch Produkte ohne Preis", value=True)
 
        filtered_df = master_df.copy()
        if search_query:
            for kw in search_query.lower().split():
                filtered_df = filtered_df[filtered_df['Produktname'].str.lower().str.contains(kw, na=False)]
        if sel_shops:
            filtered_df = filtered_df[filtered_df['Shop'].isin(sel_shops)]
 
        if sort_order == "Preis: Günstigste zuerst":
            if not show_all:
                filtered_df = filtered_df[filtered_df['Preis'] > 0]
            filtered_df = filtered_df.sort_values('Preis', ascending=True)
        elif sort_order == "Preis: Teuerster zuerst":
            filtered_df = filtered_df.sort_values('Preis', ascending=False)
        elif sort_order == "Mit Preis zuerst":
            filtered_df = filtered_df.sort_values('Preis', ascending=False)
        else:
            filtered_df = filtered_df.sort_values('Produktname', ascending=True)
 
        st.divider()
        with_price    = (filtered_df['Preis'] > 0).sum()
        without_price = (filtered_df['Preis'] == 0).sum()
 
        c1, c2, c3 = st.columns(3)
        c1.metric("📊 Gesamt-Treffer", f"{len(filtered_df):,}")
        c2.metric("💰 Mit Preis",       f"{with_price:,}")
        c3.metric("📞 Auf Anfrage",     f"{without_price:,}")
 
        display_df = filtered_df.head(1000).copy()
        st.dataframe(
            display_df[['URL', 'Produktname', 'Shop', 'Hersteller', 'Preis', 'Status', 'Kategorie', 'Bild']],
            column_config={
                "URL":         st.column_config.LinkColumn("Zum Shop 🔗", display_text="Öffnen", width="small"),
                "Produktname": st.column_config.TextColumn("Produktname", width="large"),
                "Preis":       st.column_config.NumberColumn("Preis", format="%.2f €"),
                "Bild":        st.column_config.ImageColumn("Vorschau", width="small"),
                "Shop":        st.column_config.TextColumn("Shop"),
                "Hersteller":  st.column_config.TextColumn("Hersteller"),
                "Status":      st.column_config.TextColumn("Status"),
                "Kategorie":   st.column_config.TextColumn("Kategorie"),
            },
            use_container_width=True,
            height=600,
            hide_index=True
        )
        if len(filtered_df) > 1000:
            st.warning(f"⚠️ Zeige die ersten 1.000 von {len(filtered_df):,} Treffern.")
 
        csv_data = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button("📊 Liste als CSV exportieren", csv_data, "solar_export.csv", "text/csv")
 
    # ──────────────────────────────────────────────────────────────────────────
    # TAB 2 – Hersteller-Radar (NEU)
    # ──────────────────────────────────────────────────────────────────────────
    with tab_radar:
        st.subheader("🏭 Hersteller-Radar – Wer führt welchen Hersteller?")
        st.markdown(
            "Suche nach einem **Hersteller** und sieh sofort, in welchen Shops er gelistet ist, "
            "wie viele Produkte er hat und wie der günstigste Preis ist."
        )
 
        # ── Suchfeld ──
        brand_query = st.text_input(
            "Hersteller suchen (z.B. 'SMA', 'Fronius', 'Huawei'):",
            placeholder="Hersteller-Name eingeben ...",
            key="brand_search"
        )
 
        # alle bekannten Hersteller (für Dropdown-Vorschau)
        all_brands = sorted(
            master_df['Hersteller']
            .dropna()
            .unique()
            .tolist()
        )
        # Filter: N/A heraushalten wenn sinnvoll
        all_brands = [b for b in all_brands if b not in ('N/A', '', 'nan')]
 
        col_b1, col_b2 = st.columns([3, 1])
        with col_b1:
            selected_brands = st.multiselect(
                "Oder direkt aus der Liste wählen:",
                all_brands,
                key="brand_multi"
            )
        with col_b2:
            show_no_price_brands = st.checkbox("Auch ohne Preis zeigen", value=True, key="brand_noprice")
 
        # ── Filtern ──
        radar_df = master_df.copy()
 
        # Text-Suche hat Vorrang; Multiselect ergänzt
        if brand_query:
            radar_df = radar_df[
                radar_df['Hersteller'].str.lower().str.contains(brand_query.lower(), na=False)
                | radar_df['Produktname'].str.lower().str.contains(brand_query.lower(), na=False)
            ]
        elif selected_brands:
            radar_df = radar_df[radar_df['Hersteller'].isin(selected_brands)]
 
        if not show_no_price_brands:
            radar_df = radar_df[radar_df['Preis'] > 0]
 
        if radar_df.empty:
            st.info("Keine Treffer. Bitte anderen Suchbegriff eingeben.")
        else:
            # ── KPI-Zeile ──
            found_brands  = radar_df['Hersteller'].nunique()
            found_shops   = radar_df['Shop'].nunique()
            found_products = len(radar_df)
 
            k1, k2, k3 = st.columns(3)
            k1.metric("🏭 Hersteller gefunden", found_brands)
            k2.metric("🏪 Shops mit diesem Hersteller", found_shops)
            k3.metric("📦 Produkte gesamt", f"{found_products:,}")
 
            st.divider()
 
            # ── Haupt-Radar-Tabelle: Shop × Hersteller ──
            st.markdown("#### Shop-Übersicht")
 
            # Aggregation pro Shop + Hersteller
            radar_agg = (
                radar_df
                .groupby(['Shop', 'Hersteller'])
                .agg(
                    Produkte   = ('Produktname', 'count'),
                    Min_Preis  = ('Preis', lambda x: x[x > 0].min() if (x > 0).any() else None),
                    Max_Preis  = ('Preis', lambda x: x[x > 0].max() if (x > 0).any() else None),
                    Kategorien = ('Kategorie', lambda x: ', '.join(sorted(x.unique())))
                )
                .reset_index()
                .sort_values(['Shop', 'Produkte'], ascending=[True, False])
            )
 
            # Preis-Spalten schön formatieren
            radar_agg['Min_Preis'] = radar_agg['Min_Preis'].apply(
                lambda v: f"{v:,.2f} €" if pd.notna(v) else "Auf Anfrage"
            )
            radar_agg['Max_Preis'] = radar_agg['Max_Preis'].apply(
                lambda v: f"{v:,.2f} €" if pd.notna(v) else "Auf Anfrage"
            )
 
            st.dataframe(
                radar_agg.rename(columns={
                    'Shop':       '🏪 Shop',
                    'Hersteller': '🏭 Hersteller',
                    'Produkte':   '# Produkte',
                    'Min_Preis':  'Günstigster Preis',
                    'Max_Preis':  'Teuerster Preis',
                    'Kategorien': 'Kategorien'
                }),
                use_container_width=True,
                hide_index=True
            )
 
            st.divider()
 
            # ── Detailtabelle ──
            st.markdown("#### Produktliste der Treffer")
            detail_display = radar_df.head(1000)[
                ['URL', 'Produktname', 'Hersteller', 'Shop', 'Preis', 'Status', 'Kategorie', 'Bild']
            ].copy()
 
            st.dataframe(
                detail_display,
                column_config={
                    "URL":         st.column_config.LinkColumn("Zum Shop 🔗", display_text="Öffnen", width="small"),
                    "Produktname": st.column_config.TextColumn("Produktname", width="large"),
                    "Preis":       st.column_config.NumberColumn("Preis", format="%.2f €"),
                    "Bild":        st.column_config.ImageColumn("Vorschau", width="small"),
                    "Hersteller":  st.column_config.TextColumn("Hersteller"),
                    "Shop":        st.column_config.TextColumn("Shop"),
                    "Status":      st.column_config.TextColumn("Status"),
                    "Kategorie":   st.column_config.TextColumn("Kategorie"),
                },
                use_container_width=True,
                height=500,
                hide_index=True
            )
 
            if len(radar_df) > 1000:
                st.warning(f"⚠️ Zeige die ersten 1.000 von {len(radar_df):,} Treffern.")
 
            # ── Export ──
            csv_radar = radar_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📊 Hersteller-Treffer als CSV",
                csv_radar,
                "hersteller_radar.csv",
                "text/csv",
                key="dl_radar"
            )
 
else:
    st.info("👋 Bereit. Bitte lade deine CSV-Dateien hoch.")
 
