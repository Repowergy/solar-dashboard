import streamlit as st
import pandas as pd
import re
import io

# Konfiguration der Seite
st.set_page_config(page_title='Universal Solar AI Intelligence', page_icon='☀️', layout='wide')

# --- KI LOGIK: SPRACHUNABHÄNGIGE ERKENNUNG ---
# Erkennt Begriffe in DE, EN, PL, IT, FR
AI_MAPPING = {
    '🔌 Wechselrichter': ['inverter', 'wechselrichter', 'falownik', 'onduleur', 'inversore', 'mppt', 'micro'],
    '☀️ Solarmodul': ['panel', 'module', 'modul', 'pv', 'shingled', 'bifacial', 'mono', 'poly', 'ogniwo'],
    '🔋 Speicher': ['battery', 'batterie', 'speicher', 'akku', 'storage', 'accumulo', 'bateria', 'ess'],
    '🔗 Kabel': ['cable', 'kabel', 'leitung', 'wire', 'h1z2z2', 'cavo', 'przewód'],
    '🏗️ Montage': ['mount', 'halter', 'befestigung', 'rack', 'montage', 'mounting', 'struttura', 'uchwyt'],
    '🔌 Stecker': ['connector', 'stecker', 'anschluss', 'mc4', 'plug', 'adapter', 'złącze']
}

def ai_detect_type(text):
    """KI-Erkennung basierend auf multilingualen Schlüsselwörtern"""
    text = str(text).lower()
    for category, keywords in AI_MAPPING.items():
        if any(kw in text for kw in keywords):
            return category
    return '📦 Sonstiges'

def ai_find_columns(df):
    """KI-Logik um Spaltennamen automatisch zu finden (egal welche Sprache)"""
    cols = [c.lower() for c in df.columns]
    mapping = {}
    
    # Suche Titel-Spalte
    for c in df.columns:
        if any(x in c.lower() for x in ['title', 'titel', 'name', 'nazwa', 'produk', 'label', 'titolo']):
            mapping['title'] = c
            break
            
    # Suche Preis-Spalte
    for c in df.columns:
        if any(x in c.lower() for x in ['price', 'preis', 'cena', 'prix', 'prezzo', 'cost']):
            mapping['price'] = c
            break

    # Suche Bild-Spalte
    for c in df.columns:
        if any(x in c.lower() for x in ['image', 'bild', 'img', 'url', 'zdjecie', 'foto']):
            mapping['image'] = c
            break
            
    return mapping

# --- UI DESIGN ---
st.title('☀️ Universal Solar AI Intelligence')
st.markdown('### Lade eine beliebige CSV hoch – die KI erkennt Produkte in jeder Sprache')

# Sidebar für Upload
with st.sidebar:
    st.header("📥 CSV Upload")
    uploaded_file = st.file_uploader("Wähle eine oder mehrere CSV Dateien", type=['csv'], accept_multiple_files=False)
    
    st.divider()
    st.info("💡 Die KI analysiert automatisch Spaltennamen und Inhalte (DE, EN, PL, IT, FR).")

if uploaded_file:
    # Daten laden
    try:
        df = pd.read_csv(uploaded_file)
        st.success(f"Erfolgreich geladen: {uploaded_file.name} ({len(df)} Zeilen)")
        
        # Spalten automatisch finden
        col_map = ai_find_columns(df)
        
        # KI Analyse durchführen
        with st.spinner('KI analysiert Produkte...'):
            title_col = col_map.get('title', df.columns[0])
            df['KI_Kategorie'] = df[title_col].apply(ai_detect_type)
            
            # Datenqualität berechnen
            df['Qualität'] = df.apply(lambda x: sum([pd.notna(x.get(c)) for c in col_map.values()]) / len(col_map) * 100 if col_map else 50, axis=1)

        # Tabs für Übersicht
        tab1, tab2, tab3 = st.tabs(["📊 Analyse", "🔍 Produktdetails", "💾 Export"])

        with tab1:
            col1, col2, col3 = st.columns(3)
            col1.metric("Produkte erkannt", len(df))
            col2.metric("Kategorien", df['KI_Kategorie'].nunique())
            col3.metric("Durchschn. Qualität", f"{df['Qualität'].mean():.1f}%")

            st.subheader("Verteilung nach KI-Kategorie")
            st.bar_chart(df['KI_Kategorie'].value_counts())

        with tab2:
            st.subheader("Gefundene Produkte")
            search = st.text_input("Suche (Marke, Modell, Typ)...")
            
            filtered_df = df
            if search:
                filtered_df = df[df[title_col].str.contains(search, case=False, na=False)]

            # Produkt-Karten
            for i, row in filtered_df.head(50).iterrows():
                with st.expander(f"{row['KI_Kategorie']} | {str(row[title_col])[:80]}"):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.write(f"**Original Spalte '{title_col}':** {row[title_col]}")
                        if 'price' in col_map:
                            st.write(f"**Preis:** {row[col_map['price']]}")
                        if 'image' in col_map:
                            st.write(f"**Bild-URL:** {row[col_map['image']]}")
                    with c2:
                        st.progress(row['Qualität']/100, text=f"Daten-Qualität")

        with tab3:
            st.subheader("Bereinigte Daten herunterladen")
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("CSV mit KI-Kategorien exportieren", csv, "ai_solar_export.csv", "text/csv")

    except Exception as e:
        st.error(f"Fehler beim Verarbeiten der Datei: {e}")
else:
    # Startseite wenn nichts hochgeladen ist
    st.info("Bitte lade eine CSV-Datei in der Seitenleiste hoch, um die Analyse zu starten.")
    
    st.subheader("So funktioniert die KI:")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("🌐 **Multilingual**\nErkennt Begriffe wie 'Wechselrichter', 'Inverter' oder 'Falownik'.")
    with c2:
        st.markdown("🤖 **Smart Mapping**\nFindet automatisch die richtigen Spalten für Titel, Preis und Bild.")
    with c3:
        st.markdown("📈 **Qualitäts-Check**\nBewertet automatisch, wie vollständig deine Produktdaten sind.")

st.divider()
st.caption('Universal Solar AI Dashboard | Powered by Streamlit & AI Integration')
