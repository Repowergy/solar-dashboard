import streamlit as st

import solar_db as db

st.set_page_config(page_title='Solar Mega-Engine AI', page_icon='⚡', layout='wide')


def _files_signature(files):
    return [(f.name, getattr(f, "size", None)) for f in files]


def _get_connection(files):
    """Baut die DuckDB-Datenbank nur neu, wenn sich die Dateiauswahl ändert.

    Verhindert, dass die Datei bei jedem Streamlit-Neustart erneut verarbeitet
    wird.
    """
    signature = _files_signature(files)
    if st.session_state.get("files_signature") != signature:
        with st.spinner("Verarbeite Dateien (speicherschonend über DuckDB)..."):
            con, infos = db.build_database(files)
        st.session_state["con"] = con
        st.session_state["infos"] = infos
        st.session_state["files_signature"] = signature
    return st.session_state["con"], st.session_state["infos"]


st.title('⚡ Solar Price Engine (Mega-Engine)')
st.markdown("Suche über alle Dateien hinweg. **Klicke auf 'Öffnen'**, um zum Shop zu gelangen.")

with st.sidebar:
    st.header("📥 Massen-Import")
    files = st.file_uploader(
        "Alle Lieferanten-Listen (CSV) hochladen",
        type=['csv'],
        accept_multiple_files=True,
    )

con = None
if files:
    con, infos = _get_connection(files)
    for info in infos:
        if "error" in info:
            st.sidebar.error(f"❌ {info['name']}: {info['error']}")
        else:
            st.sidebar.success(f"✅ {info['name']} geladen")
    total = db.total_rows(con)
    st.sidebar.caption(f"📊 Insgesamt {total:,} Produkte in der Datenbank")

if con is not None and db.total_rows(con) > 0:

    # --- TABS: Produktsuche + Hersteller-Shop-Analyse ---
    tab1, tab2 = st.tabs(["🔍 Globale Produktsuche", "🏭 Hersteller → Shops"])

    # ===========================
    # TAB 1: PRODUKTSUCHE
    # ===========================
    with tab1:
        st.subheader("🔍 Globale Suche")
        search_query = st.text_input(
            "Tippe Modell oder Marke ein (z.B. 'Tripower X 25'):",
            placeholder="Ergebnisse erscheinen sofort beim Tippen...",
        )

        col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
        with col_f1:
            sel_shops = st.multiselect("Anbieter filtern:", db.distinct_shops(con))
        with col_f2:
            sort_order = st.selectbox(
                "Sortierung:",
                ["Preis: Günstigste zuerst", "Preis: Teuerster zuerst", "Alphabetisch", "Mit Preis zuerst"],
            )
        with col_f3:
            show_all = st.checkbox("Auch Produkte ohne Preis", value=True)

        only_with_price = not show_all

        counts = db.search_counts(con, search_query, sel_shops, only_with_price)

        st.divider()

        col_s1, col_s2, col_s3 = st.columns(3)
        col_s1.metric("📊 Gesamt-Treffer", f"{counts['total']:,}")
        col_s2.metric("💰 Mit Preis", f"{counts['with_price']:,}")
        col_s3.metric("📞 Auf Anfrage", f"{counts['without_price']:,}")

        display_df = db.search_page(con, search_query, sel_shops, sort_order, only_with_price, limit=1000)

        st.dataframe(
            display_df,
            column_config={
                "URL": st.column_config.LinkColumn("Zum Shop 🔗", display_text="Öffnen", width="small"),
                "Produktname": st.column_config.TextColumn("Produktname", width="large"),
                "Preis": st.column_config.NumberColumn("Preis", format="%.2f €"),
                "Shop": st.column_config.TextColumn("Shop"),
                "Hersteller": st.column_config.TextColumn("Hersteller"),
                "Status": st.column_config.TextColumn("Status"),
                "Kategorie": st.column_config.TextColumn("Kategorie"),
            },
            use_container_width=True,
            height=600,
            hide_index=True,
        )

        if counts["total"] > len(display_df):
            st.warning(f"⚠️ Zeige die ersten {len(display_df):,} von {counts['total']:,} Treffern an.")

        # Export nur auf Klick erzeugen – nicht bei jedem Seitenlauf.
        if st.button("📊 CSV-Export vorbereiten"):
            st.session_state["export_ready"] = True
        if st.session_state.get("export_ready"):
            export_df = db.export_dataframe(con, search_query, sel_shops, sort_order, only_with_price)
            st.download_button(
                "⬇️ Liste als CSV herunterladen",
                export_df.to_csv(index=False).encode("utf-8"),
                "solar_export.csv",
                "text/csv",
            )

    # ===========================
    # TAB 2: HERSTELLER → SHOPS
    # ===========================
    with tab2:
        st.subheader("🏭 Welcher Shop führt welchen Hersteller?")
        st.markdown("Wähle einen Hersteller und sieh alle Shops, die diesen führen – inklusive Preisspanne und Anzahl der Produkte.")

        all_brands = db.distinct_brands(con)

        col_h1, col_h2 = st.columns([2, 1])
        with col_h1:
            brand_search = st.text_input(
                "🔍 Hersteller suchen (z.B. 'Victron', 'Huawei', 'SMA'):",
                placeholder="Tippe einen Hersteller...",
            )
        with col_h2:
            min_products = st.number_input("Min. Produkte pro Shop:", min_value=1, value=1)

        if brand_search:
            matching_brands = [b for b in all_brands if brand_search.lower() in b.lower()]
        else:
            matching_brands = all_brands[:50]

        if not all_brands:
            st.info("ℹ️ In den geladenen Dateien sind keine Hersteller-Angaben vorhanden.")
        elif not matching_brands:
            st.warning(f"❌ Kein Hersteller gefunden für '{brand_search}'")
        else:
            selected_brand = st.selectbox(
                f"📋 Hersteller wählen ({len(matching_brands)} gefunden):",
                matching_brands,
            )

            if selected_brand:
                summary = db.brand_summary(con, selected_brand)

                st.divider()
                col_b1, col_b2, col_b3, col_b4 = st.columns(4)
                col_b1.metric("🏭 Hersteller", selected_brand)
                col_b2.metric("📦 Produkte gesamt", f"{summary['products']:,}")
                col_b3.metric("🏬 Shops", f"{summary['shops']}")
                if summary["avg_price"]:
                    col_b4.metric("💰 Ø Preis", f"{summary['avg_price']:.2f} €")
                else:
                    col_b4.metric("💰 Ø Preis", "N/A")

                shop_analysis = db.brand_shop_analysis(con, selected_brand, min_products)

                st.subheader(f"🏬 Shops, die {selected_brand} führen ({len(shop_analysis)} Shops)")
                st.dataframe(
                    shop_analysis,
                    column_config={
                        "Shop": st.column_config.TextColumn("🏬 Shop", width="medium"),
                        "Produkte": st.column_config.NumberColumn("📦 Anzahl Produkte"),
                        "Min_Preis": st.column_config.NumberColumn("💰 Min. Preis", format="%.2f €"),
                        "Max_Preis": st.column_config.NumberColumn("💰 Max. Preis", format="%.2f €"),
                        "Ø_Preis": st.column_config.NumberColumn("💰 Ø Preis", format="%.2f €"),
                        "Beispiel_URL": st.column_config.LinkColumn("🔗 Zum Shop", display_text="Öffnen", width="small"),
                    },
                    use_container_width=True,
                    height=400,
                    hide_index=True,
                )

                if not shop_analysis.empty:
                    st.subheader(f"📊 Top 15 Shops für {selected_brand}")
                    top_shops_chart = shop_analysis.head(15).set_index('Shop')['Produkte']
                    st.bar_chart(top_shops_chart)

                st.subheader(f"📋 Produkte von {selected_brand}")
                sort_brand = st.selectbox(
                    "Sortierung:",
                    ["Günstigste zuerst", "Teuerste zuerst", "Nach Shop"],
                    key="brand_sort",
                )
                brand_df_sorted = db.brand_products(con, selected_brand, sort_brand, limit=500)

                st.dataframe(
                    brand_df_sorted,
                    column_config={
                        "URL": st.column_config.LinkColumn("🔗", display_text="Öffnen", width="small"),
                        "Produktname": st.column_config.TextColumn("Produktname", width="large"),
                        "Preis": st.column_config.NumberColumn("Preis", format="%.2f €"),
                        "Shop": st.column_config.TextColumn("Shop"),
                        "Status": st.column_config.TextColumn("Status"),
                    },
                    use_container_width=True,
                    height=500,
                    hide_index=True,
                )

                if st.button(f"📊 {selected_brand}-Export vorbereiten", key="brand_export_btn"):
                    st.session_state["brand_export_ready"] = selected_brand
                if st.session_state.get("brand_export_ready") == selected_brand:
                    brand_csv = db.brand_export(con, selected_brand).to_csv(index=False).encode("utf-8")
                    st.download_button(
                        f"⬇️ Alle {selected_brand}-Produkte als CSV herunterladen",
                        brand_csv,
                        f"{selected_brand.replace(' ', '_')}_export.csv",
                        "text/csv",
                        key="brand_download",
                    )

else:
    st.info("👋 Bereit. Bitte lade deine CSV-Dateien hoch.")
