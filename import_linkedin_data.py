#!/usr/bin/env python3
"""
import_linkedin_data.py — Importa datos de LinkedIn a la base unificada
Procesa:
  1. Connections.csv (~16.800 contactos)
  2. extracted_posts.json (13.661 posts + emails extraídos)
  3. Deduplica y cruza con datos de Mercado Público
"""
import sys, json, csv, re, os
sys.path.insert(0, r"C:\Users\Usuario\Desktop\Programación\Dashboard-BOTS")
from unified_db import get_db

LINKEDIN_DIR = r"C:\Users\Usuario\Desktop\Programación\Linkedin-AG"
CSV_PATH = os.path.join(LINKEDIN_DIR, "SourceLINK", "Connections.csv")
POSTS_PATH = os.path.join(LINKEDIN_DIR, "extracted_posts.json")

EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

# Filtro: emails que probablemente NO son de contacto directo
EXCLUDE_DOMAINS = [
    "linkedin.com", "facebook.com", "twitter.com", "instagram.com",
    "youtube.com", "tiktok.com", "whatsapp.com",
    "example.com", "domain.com", "email.com",
    "gmail.com", "hotmail.com", "outlook.com", "yahoo.com",
    # Si el email es genérico sin nombre, lo filtramos
]
EXCLUDE_PATTERNS = [
    r'^info@', r'^contacto@', r'^contact@', r'^hello@',
    r'^hola@', r'^admin@', r'^support@', r'^noreply@',
    r'^no-?reply@', r'^jobs@', r'^rrhh@',
]

def extract_emails(text):
    """Extrae emails únicos de un texto, filtrando genéricos"""
    if not text:
        return set()
    found = re.findall(EMAIL_REGEX, text, re.IGNORECASE)
    emails = set()
    for e in found:
        e = e.lower().strip()
        domain = e.split("@")[-1] if "@" in e else ""
        # Excluir dominios conocidos
        if domain in EXCLUDE_DOMAINS:
            continue
        # Excluir patrones genéricos
        is_generic = any(re.match(pat, e) for pat in EXCLUDE_PATTERNS)
        if is_generic:
            continue
        # Debe tener al menos un punto en el dominio
        if "." not in domain:
            continue
        emails.add(e)
    return emails

def import_connections():
    """Importa Connections.csv a la DB"""
    db = get_db()
    if not os.path.exists(CSV_PATH):
        print("  ⚠️ Connections.csv no encontrado")
        return 0

    with open(CSV_PATH, encoding='utf-8') as f:
        lines = f.readlines()

    header_idx = next((i for i, l in enumerate(lines) if l.strip().startswith("First Name,")), None)
    if header_idx is None:
        print("  ⚠️ No se encontró header en Connections.csv")
        return 0

    imported = 0
    reader = csv.DictReader(lines[header_idx:])
    for row in reader:
        first = (row.get("First Name") or "").strip()
        last = (row.get("Last Name") or "").strip()
        full = f"{first} {last}".strip()
        if not full:
            continue
        email = (row.get("Email Address") or "").strip()
        company = (row.get("Company") or "").strip()
        position = (row.get("Position") or "").strip()
        url = (row.get("URL") or "").strip()
        codigo = url.split("linkedin.com/in/")[-1].rstrip("/") if "linkedin.com/in/" in url else email or full.lower().replace(" ", "-")

        db.upsert_contacto(
            codigo_externo=codigo,
            nombre=full[:200],
            email=email,
            cargo=position[:200],
            organismo_nombre=company[:200],
            fuente="linkedin_connections",
            metadata=json.dumps({"linkedin_url": url, "tipo": "conexion"}),
        )
        imported += 1
    print(f"  ✅ {imported} contactos desde Connections.csv")
    return imported

def import_posts_emails():
    """Extrae emails de los posts de LinkedIn y los guarda en DB"""
    db = get_db()
    if not os.path.exists(POSTS_PATH):
        print("  ⚠️ extracted_posts.json no encontrado")
        return 0

    with open(POSTS_PATH, encoding='utf-8') as f:
        posts = json.load(f)

    email_to_author = {}  # {email: set(authors)}
    post_with_emails = 0
    total_emails = 0

    for post in posts:
        text = post.get("text", "")
        author = post.get("author", "")
        emails = extract_emails(text)
        if emails:
            post_with_emails += 1
            total_emails += len(emails)
            for e in emails:
                if e not in email_to_author:
                    email_to_author[e] = set()
                email_to_author[e].add(author)

    imported = 0
    for email, authors in email_to_author.items():
        # Usar email como ID único
        nombre = f"[LI Post] {', '.join(list(authors)[:2])}"
        db.upsert_contacto(
            codigo_externo=email,
            nombre=nombre[:200],
            email=email,
            fuente="linkedin_posts",
            metadata=json.dumps({
                "autores": list(authors)[:5],
                "tipo": "email_extraido_post",
            }),
        )
        imported += 1

    print(f"  📬 {post_with_emails} posts con emails ({total_emails} emails únicos)")
    print(f"  ✅ {imported} contactos desde emails de posts")
    return imported

def show_summary():
    """Muestra resumen de la DB después de la importación"""
    db = get_db()
    stats = db.get_global_stats()
    print(f"\n📊 **Resumen final DB Unificada**")
    print(f"  👤 Contactos:          {stats['contactos']}")
    print(f"  🏛️ Organismos:          {stats['organismos']}")
    print(f"  📄 Licitaciones:        {stats['licitaciones']}")
    print(f"  ⚡ Compras Ágiles:      {stats['compras_agiles']}")
    print(f"  🔎 En Seguimiento:      {stats['en_seguimiento']}")
    print(f"  📊 Snapshots Bots:      {stats['bot_history']}")
    print(f"  💾 Tamaño DB:           {stats['db_size_kb']} KB")

    # Desglose de contactos por fuente
    fuentes = db.conn.execute(
        "SELECT fuente, COUNT(*) as c FROM contactos GROUP BY fuente ORDER BY c DESC"
    ).fetchall()
    print(f"  📋 Por fuente:")
    for row in fuentes:
        print(f"    • {row['fuente']}: {row['c']}")

    db.close()

if __name__ == "__main__":
    print("🌱 Importando datos de LinkedIn a DB Unificada...\n")
    con = import_connections()
    posts = import_posts_emails()
    print()
    show_summary()
