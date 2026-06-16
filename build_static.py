#!/usr/bin/env python3
"""
build_static.py — Genera el dashboard estático para GitHub Pages.
Lee todos los datos desde las fuentes originales y genera JSONs + HTML
en la carpeta docs/ lista para servir en GitHub Pages.

Ejecutar: python build_static.py
Resultado: docs/index.html + docs/data/*.json
"""

import json
import sys
import shutil
from pathlib import Path
from datetime import datetime

HERE = Path(__file__).parent
DOCS = HERE / "docs"
DATA = DOCS / "data"
LINKEDIN_DIR = Path(r"C:\Users\Usuario\Desktop\Programación\Linkedin-AG")
TRADING_DIR = Path(r"C:\Users\Usuario\Desktop\Programación\spot2")

# ─── Helpers ────────────────────────────────────────────

def load_json(path, default=None):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except:
            pass
    return default if default is not None else {}

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# ─── LinkedIn Stats ─────────────────────────────────────

def build_li_stats():
    """Estadísticas de LinkedIn"""
    posts_path = LINKEDIN_DIR / "extracted_posts.json"
    ofertas_path = LINKEDIN_DIR / "Todas_Ofertas.csv"
    estructurales_path = LINKEDIN_DIR / "Ofertas_Estructurales.csv"
    contactos_path = LINKEDIN_DIR / "Contactos_Emails.csv"

    stats = {"total_posts": 0, "total_ofertas": 0, "total_estructurales": 0,
             "total_contactos_email": 0, "autores_unicos": 0,
             "ultimo_scraping": None, "ultima_oferta": None}

    if posts_path.exists():
        posts = load_json(posts_path, [])
        stats["total_posts"] = len(posts)
        autores = set(p.get("author", "") for p in posts if p.get("author"))
        stats["autores_unicos"] = len(autores)
        scraped_times = [p.get("scraped_at", "") for p in posts if p.get("scraped_at")]
        if scraped_times:
            stats["ultimo_scraping"] = max(scraped_times)[:19]

    if ofertas_path.exists():
        import csv
        with open(str(ofertas_path), "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        stats["total_ofertas"] = len(rows)
        fechas = [r.get("Fecha", "") for r in rows if r.get("Fecha")]
        if fechas:
            stats["ultima_oferta"] = max(fechas)[:19]

    if estructurales_path.exists():
        import csv
        with open(str(estructurales_path), "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        stats["total_estructurales"] = len(rows)

    if contactos_path.exists():
        import csv
        with open(str(contactos_path), "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        stats["total_contactos_email"] = len(rows)

    return stats

def build_li_posts(limit=20):
    posts = load_json(LINKEDIN_DIR / "extracted_posts.json", [])
    posts.sort(key=lambda p: p.get("scraped_at", ""), reverse=True)
    return posts[:limit]

def build_li_ofertas(limit=30, estructurales=False):
    import csv
    filename = "Ofertas_Estructurales.csv" if estructurales else "Todas_Ofertas.csv"
    path = LINKEDIN_DIR / filename
    if not path.exists():
        return []
    with open(str(path), "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))[:limit]

def build_estructurales(limit=50):
    import csv
    path = LINKEDIN_DIR / "Ofertas_Estructurales.csv"
    if not path.exists():
        return []
    with open(str(path), "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [{"autor": r.get("Autor", ""), "correos": r.get("Correos", ""),
             "region": r.get("Region", ""), "rol": r.get("Rol", ""),
             "empresa": r.get("Empresa", ""), "score": float(r.get("Score", 0) or 0),
             "fecha": r.get("Fecha", "")} for r in rows[:limit]]

# ─── Detection Stats ────────────────────────────────────

def build_detection():
    posts = load_json(LINKEDIN_DIR / "extracted_posts.json", [])
    keywords = load_json(LINKEDIN_DIR / "job_keywords.json", {})
    training = load_json(LINKEDIN_DIR / "training_data.json", [])
    network = load_json(LINKEDIN_DIR / "network_stats.json", {})
    import csv
    ofertas_csv = []
    path = LINKEDIN_DIR / "Todas_Ofertas.csv"
    if path.exists():
        with open(str(path), "r", encoding="utf-8") as f:
            ofertas_csv = list(csv.DictReader(f))

    pct = round(len(ofertas_csv) / max(len(posts), 1) * 100, 1)
    kw_count = len(keywords.get("positive", [])) if isinstance(keywords, dict) else 0
    return {
        "total_posts": len(posts),
        "total_ofertas": len(ofertas_csv),
        "porcentaje_deteccion": pct,
        "keywords_activas": kw_count,
        "training_entries": len(training),
        "training_votes": sum(1 for t in training if "votes" in t),
        "weekly_invites": network.get("weekly_invites", 0) if isinstance(network, dict) else 0,
        "followers": network.get("followers", 0) if isinstance(network, dict) else 0,
    }

# ─── CRM ────────────────────────────────────────────────

def build_crm():
    """CRM contacts summary"""
    import sqlite3
    crm_path = HERE / "crm.db"
    if not crm_path.exists():
        return {"total": 0, "pendientes": 0, "contactados": 0, "con_email": 0, "contactos": []}
    conn = sqlite3.connect(str(crm_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        total = cur.execute("SELECT COUNT(*) FROM contactos_crm").fetchone()[0]
    except:
        conn.close()
        return {"total": 0, "pendientes": 0, "contactados": 0, "con_email": 0, "contactos": []}
    pendientes = cur.execute("SELECT COUNT(*) FROM contactos_crm WHERE estado='pendiente'").fetchone()[0]
    contactados = cur.execute("SELECT COUNT(*) FROM contactos_crm WHERE estado IN ('contactado','en_seguimiento')").fetchone()[0]
    con_email = cur.execute("SELECT COUNT(*) FROM contactos_crm WHERE email != ''").fetchone()[0]
    rows = cur.execute("SELECT * FROM contactos_crm ORDER BY CASE estado WHEN 'pendiente' THEN 0 ELSE 1 END, score DESC LIMIT 50").fetchall()
    contactos = [{k: row[k] for k in row.keys()} for row in rows]
    conn.close()
    return {"total": total, "pendientes": pendientes, "contactados": contactados,
            "con_email": con_email, "contactos": contactos}

# ─── DB Unificada ───────────────────────────────────────

def build_db_stats():
    try:
        sys.path.insert(0, str(HERE))
        from unified_db import get_db
        db = get_db()
        return db.get_global_stats()
    except:
        return {"error": "DB no disponible"}

# ─── Trading ────────────────────────────────────────────

def build_trading():
    portfolio_path = TRADING_DIR / "portfolio.json"
    data = load_json(portfolio_path, {})
    positions = data.get("positions", {})
    profit = data.get("profit_history", {})
    return {
        "open_positions": len(positions),
        "positions": [{"symbol": s, "buy_price": p.get("buy_price"),
                       "invested": round(p.get("usdt_invested", 0), 2),
                       "buy_time": (p.get("buy_time", "") or "")[:16],
                       "trade_type": p.get("trade_type", "")}
                      for s, p in positions.items()],
        "total_profit": round(profit.get("total_profit_usdt", 0), 4),
        "total_trades": profit.get("total_trades", 0),
        "winning_trades": profit.get("winning_trades", 0),
        "win_rate": round(profit.get("winning_trades", 0) / max(profit.get("total_trades", 1), 1) * 100, 1),
    }

# ─── Ratings ────────────────────────────────────────────

def build_ratings():
    return load_json(HERE / "post_ratings.json", {})

# ─── Suggestions ────────────────────────────────────────
# (import from server module to avoid duplication)

def build_suggestions():
    try:
        sys.path.insert(0, str(HERE))
        from server import analyze_feedback
        return analyze_feedback()
    except Exception as e:
        return {"error": str(e)}


# ─── MAIN ───────────────────────────────────────────────

def main():
    print("🔨 Construyendo dashboard estático...")
    DOCS.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build all data
    data_files = {
        "stats.json": build_li_stats(),
        "posts.json": build_li_posts(20),
        "ofertas.json": build_li_ofertas(30),
        "estructurales.json": build_estructurales(50),
        "detection.json": build_detection(),
        "crm.json": build_crm(),
        "db_stats.json": build_db_stats(),
        "trading.json": build_trading(),
        "ratings.json": build_ratings(),
        "suggestions.json": build_suggestions(),
        "meta.json": {"built_at": timestamp, "version": "2.0-static"},
    }

    for filename, data in data_files.items():
        save_json(DATA / filename, data)
        preview = str(data)[:80].replace('\n', ' ')
        print(f"  ✅ data/{filename} — {preview}...")

    # Copy static index.html
    src_index = HERE / "index_static.html"
    if src_index.exists():
        shutil.copy(str(src_index), str(DOCS / "index.html"))
        print(f"  ✅ index.html")

    print(f"\n✅ Dashboard estático listo en: {DOCS}")
    print(f"   Abrir: {DOCS / 'index.html'}")
    print(f"   Timestamp: {timestamp}")


if __name__ == "__main__":
    main()
