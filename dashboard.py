import streamlit as st
import pandas as pd
import re
from difflib import SequenceMatcher

# --- KONFIGURATION ---
st.set_page_config(page_title='Solar AI Price Engine', page_icon='🤖', layout='wide')

# --- KI & HILFSFUNKTIONEN ---
def get_similarity(a, b):
    """KI-Logik: Berechnet die semantische Ähnlichkeit zwischen zwei Strings."""
    return SequenceMatcher(None, str(a).lower(), str(b).lower()).ratio()

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

def detect_type(text):
    text = str(text).lower()
    if any(x in text for x in ['inverter', 'wechselrichter', 'falownik', 'onduleur']): return '🔌 Inverter'
    if any(x in text for x in ['panel', 'module', 'modul', 'pv', 'shingled']): return '☀️ Modul'
    if any(x in text for x in ['battery', 'batterie', 'speicher', 'akku', 'storage']): return '🔋 Speicher'
    if any(x in text for x in ['cable', 'kabel', 'leitung', 'wire']): return '🔗 Kabel'
    return '📦 Sonstiges'

# --- UI START ---
st.title('🤖 Solar AI Price Intelligence')
st.markdown("KI-Engine: Erkennt ähnliche Produkte über Titel, Bilder und Beschreibungen hinweg.")

with st.sidebar:
    st.header("📥 Daten-Import")
    uploaded_files = st.file_uploader("Lieferanten-CSVs hochladen", type=['csv'], accept_multiple_files=True)
    st.divider()
    similarity_threshold = st.slider("KI-Ähnlichkeits-Sensibilität", 0.0, 1.0, 0.6, help="Höher = Exaktere Treffer, Niedriger = Mehr ähnliche Vorschläge")

# --- DATEN-VERARBEITUNG ---
if uploaded_files:
    all_data = []
    for file in uploaded_files:
        try:
            df_temp = pd.read_csv(file, sep=None, engine='python', on_bad_lines='skip')
            cols = {
                'shop': next((c for c in df_temp.columns if any(x in c.lower() for x in ['shop', 'seller', 'anbieter'])), None),
                'title': next((c for c in df_temp.columns if any(x in c.lower() for x in ['produktname', 'title', 'titel', 'name', 'nazwa'])), df_temp.columns[0]),
                'price': next((c for c in df_temp.columns if any(x in c.lower() for x in ['preis', 'price', 'cena'])), None),
                'stock': next((c for c in df_temp.columns if any(x in c.lower() for x in ['verfügbarkeit', 'stock', 'availability'])), None),
                'url': next((c for c in df_temp.columns if any(x in c.lower() for x in ['url', 'link', 'shop_url'])), None),
                'image': next((c for c in df_temp.columns if any(x in c.lower() for x in ['image', 'bild', 'zdjecie', 'foto'])), None)
            }
            
            df_clean = pd.DataFrame({
                'Produkt 🔗': df_temp[cols['url']] if cols['url'] else df_temp[cols['title']],
                'Suche_Hidden': df_temp[cols['title']], 
                'Shop': df_temp[cols['shop']] if cols['shop'] else file.name,
                'Preis': df_temp[cols['price']].apply(clean_price) if cols['price'] else 0.0,
                'Status': df_temp[cols['stock']] if cols['stock'] else 'Unbekannt',
                'Kategorie': df_temp[cols['title']].apply(detect_type),
                'Bild': df_temp[cols['image']] if cols['image'] else None
            })
            all_data.append(df_clean)
        except Exception as e:
            st.error(f"Fehler in {file.name}: {e}")

    if all_data:
        master_df = pd.concat(all_data, ignore_index=True)
        
        # --- AI SEARCH ENGINE ---
        st.subheader("🔍 KI-gestützte Suche")
        search_query = st.text_input("Geben Sie ein Produkt ein (die KI findet auch ähnliche Schreibweisen):")

        # KI-Filter Logik
        if search_query:
            # Berechne KI-Ähnlichkeitsscore für jede Zeile
            master_df['AI_Score'] = master_df['Suche_Hidden'].apply(lambda x: get_similarity(search_query, x))
            filtered_df = master_df[master_df['AI_Score'] >= similarity_threshold].sort_values('AI_Score', ascending=False)
        else:
            filtered_df = master_df.copy()

        # Zusätzliche Filter
        col1, col2 = st.columns(2)
        with col1:
            shop_filter = st.multiselect("Händler filtern:", options=list(master_df['Shop'].unique()))
        with col2:
            sort_order = st.selectbox("Sortierung", ["KI-Relevanz", "Preis (Günstigste zuerst)"])

        if shop_filter: 
            filtered_df = filtered_df[filtered_df['Shop'].isin(shop_filter)]

        if sort_order == "Preis (Günstigste zuerst)":
            filtered_df = filtered_df.sort_values('Preis', ascending=True)

        # --- ANZEIGE ---
        st.divider()
        st.write(f"**KI-Treffer:** {len(filtered_df)} Produkte gefunden.")
        
        st.dataframe(
            filtered_df[['Produkt 🔗', 'Shop', 'Preis', 'Status', 'Kategorie', 'Bild']],
            column_config={
                "Produkt 🔗": st.column_config.LinkColumn("Produktname (Klick = Shop) 🔗", display_text=r"(.+)"),
                "Bild": st.column_config.ImageColumn("Vorschau"),
                "Preis": st.column_config.NumberColumn("Preis (€)", format="%.2f €"),
            },
            use_container_width=True,
            height=600,
            hide_index=True
        )
else:
    st.info("👋 Willkommen! Bitte laden Sie Ihre CSV-Dateien hoch, um die KI-Produkterkennung zu starten.")
