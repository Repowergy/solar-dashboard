"""
Speicherschonende Datenhaltung für das Solar-Dashboard.

Die komplette Suche, Filterung und der Export laufen über eine lokale
DuckDB-Datenbank. Dadurch muss die (potenziell mehrere hundert MB große)
CSV-Datei niemals vollständig als Pandas-DataFrame im Arbeitsspeicher
gehalten werden:

* Die hochgeladene Datei wird in kleinen Blöcken auf die Platte geschrieben
  (kein ``uploaded_file.read()`` das eine komplette Byte-Kopie erzeugt).
* DuckDB liest die CSV streamend ein und übernimmt dabei nur die wirklich
  benötigten Spalten – Bild-URLs und lange Beschreibungstexte werden
  gar nicht erst geladen.
* Suche, Aggregation und Export sind reine SQL-Abfragen mit ``LIMIT``.
  Es entstehen keine dauerhaften DataFrame-Kopien und keine ``master_df.copy()``.

Dieses Modul hat bewusst KEINE Streamlit-Abhängigkeit, damit es unabhängig
getestet werden kann.
"""

import os
import re
import shutil
import tempfile

import duckdb

# Blockgröße für das Schreiben der Upload-Datei auf die Platte (1 MiB).
_CHUNK = 1024 * 1024

# Spalten, die wir aus den Quelldateien übernehmen. Alles andere
# (Bild-URLs, Beschreibungen, technische Daten ...) wird ignoriert.
_COLUMN_KEYWORDS = {
    "title": ["produktname", "product_title", "title", "titel", "name"],
    "url": ["shop_url", "product_url", "url", "link"],
    "shop": ["shop", "seller", "anbieter"],
    "brand": ["hersteller", "brand", "manufacturer"],
    "price": ["preis", "price", "cena"],
    "stock": ["verfügbarkeit", "verfugbarkeit", "stock", "availability"],
}

# Spalten, die im UI angezeigt/exportiert werden (bewusst OHNE Bild).
DISPLAY_COLUMNS = [
    "URL",
    "Produktname",
    "Shop",
    "Hersteller",
    "Preis",
    "Status",
    "Kategorie",
]

# Kategorisierung anhand des Produktnamens – als reines SQL, damit die
# Zuordnung streamend beim Import passiert und nicht zeilenweise in Python.
_CATEGORY_SQL = """
CASE
  WHEN lower(Produktname) LIKE '%inverter%' OR lower(Produktname) LIKE '%wechselrichter%'
       OR lower(Produktname) LIKE '%falownik%' OR lower(Produktname) LIKE '%tripower%'
    THEN '🔌 Inverter'
  WHEN lower(Produktname) LIKE '%panel%' OR lower(Produktname) LIKE '%module%'
       OR lower(Produktname) LIKE '%modul%' OR lower(Produktname) LIKE '%pv%'
       OR lower(Produktname) LIKE '%shingled%'
    THEN '☀️ Modul'
  WHEN lower(Produktname) LIKE '%battery%' OR lower(Produktname) LIKE '%batterie%'
       OR lower(Produktname) LIKE '%speicher%' OR lower(Produktname) LIKE '%akku%'
       OR lower(Produktname) LIKE '%storage%'
    THEN '🔋 Speicher'
  WHEN lower(Produktname) LIKE '%cable%' OR lower(Produktname) LIKE '%kabel%'
       OR lower(Produktname) LIKE '%leitung%' OR lower(Produktname) LIKE '%wire%'
    THEN '🔗 Kabel'
  ELSE '📦 Sonstiges'
END
"""


def clean_price(price_val):
    """Wandelt einen Preis-Rohwert in eine Fließkommazahl um.

    Der zuletzt auftretende Trenner (``.`` oder ``,``) gilt als
    Dezimaltrenner, alles davor als Tausendertrenner. Nicht interpretierbare
    Werte (z. B. ``price_not_visible``) ergeben ``0.0``.
    """
    if price_val is None:
        return 0.0
    res = str(price_val).replace("EUR", "").replace("€", "").strip()
    res = re.sub(r"[^\d,.]", "", res).replace(",", ".")
    if res in ("", "."):
        return 0.0
    try:
        if res.count(".") > 1:
            parts = res.split(".")
            res = "".join(parts[:-1]) + "." + parts[-1]
        return float(res)
    except ValueError:
        return 0.0


def find_column(available, keywords):
    """Findet die passende Quellspalte anhand einer Keyword-Liste."""
    lookup = {str(c).lower().strip(): c for c in available}
    for kw in keywords:
        if kw in lookup:
            return lookup[kw]
    for col in available:
        col_low = str(col).lower().strip()
        for kw in keywords:
            if kw in col_low:
                return col
    return None


def _save_to_temp(file_obj):
    """Schreibt ein datei-ähnliches Objekt blockweise auf die Platte.

    ``shutil.copyfileobj`` liest in ``_CHUNK``-Blöcken – es entsteht keine
    zusätzliche vollständige Byte-Kopie im RAM.
    """
    file_obj.seek(0)
    fd, path = tempfile.mkstemp(suffix=".csv", prefix="solar_upload_")
    try:
        with os.fdopen(fd, "wb") as out:
            shutil.copyfileobj(file_obj, out, _CHUNK)
    except Exception:
        if os.path.exists(path):
            os.remove(path)
        raise
    return path


def _quote_ident(name):
    return '"' + str(name).replace('"', '""') + '"'


def _quote_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def _detect_columns(con, path):
    result = con.execute(
        "SELECT * FROM read_csv_auto(?, all_varchar=true, ignore_errors=true, "
        "sample_size=-1) LIMIT 0",
        [path],
    )
    return [d[0] for d in result.description]


def _build_select_sql(available, filename):
    """Baut das ``SELECT`` für den streamenden CSV-Import.

    Nur die benötigten Spalten werden übernommen; fehlende Spalten werden
    durch sinnvolle Standardwerte ersetzt.
    """
    mapping = {key: find_column(available, kws) for key, kws in _COLUMN_KEYWORDS.items()}
    if not mapping["title"]:
        mapping["title"] = available[0]

    def src(name):
        return f"CAST({_quote_ident(name)} AS VARCHAR)"

    title = f"COALESCE(NULLIF({src(mapping['title'])}, ''), 'Unbekannt')"
    url = f"COALESCE({src(mapping['url'])}, '')" if mapping["url"] else "''"
    if mapping["shop"]:
        shop = f"COALESCE(NULLIF({src(mapping['shop'])}, ''), {_quote_literal(filename)})"
    else:
        shop = _quote_literal(filename)
    brand = (
        f"COALESCE(NULLIF({src(mapping['brand'])}, ''), 'N/A')"
        if mapping["brand"]
        else "'N/A'"
    )
    price = f"clean_price({_quote_ident(mapping['price'])})" if mapping["price"] else "0.0"
    status = (
        f"COALESCE(NULLIF({src(mapping['stock'])}, ''), 'Auf Anfrage')"
        if mapping["stock"]
        else "'Auf Anfrage'"
    )

    inner = f"""
        SELECT
            {title} AS Produktname,
            {url} AS URL,
            {shop} AS Shop,
            {brand} AS Hersteller,
            {price} AS Preis,
            {status} AS Status
        FROM read_csv_auto(?, all_varchar=true, ignore_errors=true, sample_size=-1)
    """
    return f"SELECT *, {_CATEGORY_SQL} AS Kategorie FROM ({inner})"


def build_database(files):
    """Liest alle hochgeladenen Dateien in eine DuckDB-Tabelle ``products`` ein.

    ``files`` ist eine Liste datei-ähnlicher Objekte mit ``.name`` und
    ``.seek``/``.read`` (z. B. Streamlit ``UploadedFile``). Gibt
    ``(connection, infos)`` zurück; ``infos`` enthält pro Datei die Zeilenzahl
    bzw. eine Fehlermeldung.
    """
    con = duckdb.connect(database=":memory:")
    con.create_function("clean_price", clean_price, ["VARCHAR"], "DOUBLE")

    infos = []
    table_created = False
    for f in files:
        name = getattr(f, "name", "upload.csv")
        tmp_path = None
        try:
            tmp_path = _save_to_temp(f)
            columns = _detect_columns(con, tmp_path)
            select_sql = _build_select_sql(columns, name)
            if not table_created:
                con.execute(f"CREATE TABLE products AS {select_sql}", [tmp_path])
                table_created = True
            else:
                con.execute(f"INSERT INTO products {select_sql}", [tmp_path])
            rows = con.execute(
                "SELECT count(*) FROM products"
            ).fetchone()[0]
            infos.append({"name": name, "columns": columns, "total_rows": rows})
        except Exception as exc:  # pragma: no cover - defensive
            infos.append({"name": name, "error": str(exc)})
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    if not table_created:
        # Leere Tabelle anlegen, damit das UI nicht abstürzt.
        con.execute(
            "CREATE TABLE products (Produktname VARCHAR, URL VARCHAR, Shop VARCHAR, "
            "Hersteller VARCHAR, Preis DOUBLE, Status VARCHAR, Kategorie VARCHAR)"
        )
    return con, infos


# ---------------------------------------------------------------------------
# Abfragen für das UI – alles als SQL mit LIMIT, keine DataFrame-Kopien.
# ---------------------------------------------------------------------------

def _search_filter(search_query, shops):
    """Baut die WHERE-Bedingung (ohne Preisfilter) plus Parameterliste."""
    clauses = []
    params = []
    if search_query:
        for kw in search_query.lower().split():
            clauses.append("contains(lower(Produktname), ?)")
            params.append(kw)
    if shops:
        placeholders = ", ".join("?" for _ in shops)
        clauses.append(f"Shop IN ({placeholders})")
        params.extend(shops)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


_ORDER_BY = {
    "Preis: Günstigste zuerst": "ORDER BY Preis ASC",
    "Preis: Teuerster zuerst": "ORDER BY Preis DESC",
    "Mit Preis zuerst": "ORDER BY Preis DESC",
    "Alphabetisch": "ORDER BY Produktname ASC",
}


def total_rows(con):
    return con.execute("SELECT count(*) FROM products").fetchone()[0]


def distinct_shops(con):
    rows = con.execute(
        "SELECT DISTINCT Shop FROM products ORDER BY Shop"
    ).fetchall()
    return [r[0] for r in rows]


def search_counts(con, search_query, shops, only_with_price=False):
    where, params = _search_filter(search_query, shops)
    if only_with_price:
        where = (where + " AND Preis > 0") if where else " WHERE Preis > 0"
    row = con.execute(
        f"SELECT count(*), "
        f"count(*) FILTER (WHERE Preis > 0), "
        f"count(*) FILTER (WHERE Preis = 0) "
        f"FROM products{where}",
        params,
    ).fetchone()
    return {"total": row[0], "with_price": row[1], "without_price": row[2]}


def search_page(con, search_query, shops, sort_order, only_with_price, limit=1000):
    where, params = _search_filter(search_query, shops)
    if only_with_price:
        where = (where + " AND Preis > 0") if where else " WHERE Preis > 0"
    order = _ORDER_BY.get(sort_order, "ORDER BY Produktname ASC")
    cols = ", ".join(DISPLAY_COLUMNS)
    return con.execute(
        f"SELECT {cols} FROM products{where} {order} LIMIT {int(limit)}",
        params,
    ).fetchdf()


def export_dataframe(con, search_query, shops, sort_order, only_with_price):
    """Vollständiger Export – wird nur auf ausdrücklichen Wunsch erzeugt."""
    where, params = _search_filter(search_query, shops)
    if only_with_price:
        where = (where + " AND Preis > 0") if where else " WHERE Preis > 0"
    order = _ORDER_BY.get(sort_order, "ORDER BY Produktname ASC")
    cols = ", ".join(DISPLAY_COLUMNS)
    return con.execute(
        f"SELECT {cols} FROM products{where} {order}", params
    ).fetchdf()


def distinct_brands(con):
    rows = con.execute(
        "SELECT DISTINCT Hersteller FROM products "
        "WHERE Hersteller NOT IN ('N/A', '', 'Unbekannt') "
        "ORDER BY Hersteller"
    ).fetchall()
    return [r[0] for r in rows]


def brand_summary(con, brand):
    row = con.execute(
        "SELECT count(*), count(DISTINCT Shop), "
        "avg(Preis) FILTER (WHERE Preis > 0) "
        "FROM products WHERE Hersteller = ?",
        [brand],
    ).fetchone()
    return {"products": row[0], "shops": row[1], "avg_price": row[2]}


def brand_shop_analysis(con, brand, min_products=1):
    return con.execute(
        "SELECT Shop, "
        "count(*) AS Produkte, "
        "coalesce(min(Preis) FILTER (WHERE Preis > 0), 0) AS Min_Preis, "
        "coalesce(max(Preis) FILTER (WHERE Preis > 0), 0) AS Max_Preis, "
        "coalesce(avg(Preis) FILTER (WHERE Preis > 0), 0) AS \"Ø_Preis\", "
        "any_value(URL) AS Beispiel_URL "
        "FROM products WHERE Hersteller = ? "
        "GROUP BY Shop HAVING count(*) >= ? "
        "ORDER BY Produkte DESC",
        [brand, int(min_products)],
    ).fetchdf()


def brand_products(con, brand, sort_brand, limit=500):
    order = {
        "Günstigste zuerst": "ORDER BY Preis ASC",
        "Teuerste zuerst": "ORDER BY Preis DESC",
        "Nach Shop": "ORDER BY Shop ASC",
    }.get(sort_brand, "ORDER BY Preis ASC")
    where = "WHERE Hersteller = ?"
    params = [brand]
    if sort_brand == "Günstigste zuerst":
        where += " AND Preis > 0"
    cols = "URL, Produktname, Shop, Preis, Status"
    return con.execute(
        f"SELECT {cols} FROM products {where} {order} LIMIT {int(limit)}",
        params,
    ).fetchdf()


def brand_export(con, brand):
    cols = ", ".join(DISPLAY_COLUMNS)
    return con.execute(
        f"SELECT {cols} FROM products WHERE Hersteller = ? ORDER BY Preis ASC",
        [brand],
    ).fetchdf()
