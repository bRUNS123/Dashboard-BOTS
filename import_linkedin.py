#!/usr/bin/env python3
"""Importa Connections.csv de LinkedIn a la base de datos unificada"""
import sys, csv, json
sys.path.insert(0, r"C:\Users\Usuario\Desktop\Programación\Dashboard-BOTS")
from unified_db import get_db

CSV_PATH = r"C:\Users\Usuario\Desktop\Programación\Linkedin-AG\SourceLINK\Connections.csv"

def import_linkedin_contacts():
    db = get_db()
    imported = 0
    skipped = 0
    errors = 0

    with open(CSV_PATH, encoding='utf-8') as f:
        lines = f.readlines()

    # Find header
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("First Name,"):
            header_idx = i
            break

    if header_idx is None:
        print("❌ No se encontró header en Connections.csv")
        return

    reader = csv.DictReader(lines[header_idx:])

    for row in reader:
        first = (row.get("First Name") or "").strip()
        last = (row.get("Last Name") or "").strip()
        full = f"{first} {last}".strip()
        if not full:
            skipped += 1
            continue

        email = (row.get("Email Address") or "").strip()
        company = (row.get("Company") or "").strip()
        position = (row.get("Position") or "").strip()
        url = (row.get("URL") or "").strip()
        connected_on = (row.get("Connected On") or "").strip()

        # Use LinkedIn URL as unique ID
        codigo = url.split("linkedin.com/in/")[-1].rstrip("/") if "linkedin.com/in/" in url else url
        if not codigo:
            codigo = email if email else full.lower().replace(" ", "-")

        try:
            db.upsert_contacto(
                codigo_externo=codigo,
                nombre=full[:200],
                email=email,
                cargo=position[:200] if position else "",
                organismo_nombre=company[:200] if company else "",
                fuente="linkedin",
                metadata=json.dumps({
                    "linkedin_url": url,
                    "connected_on": connected_on,
                })
            )
            imported += 1
        except Exception as e:
            errors += 1

        if imported % 2000 == 0:
            print(f"  ... {imported} importados")

    print(f"\n✅ Importación completa!")
    print(f"  Importados: {imported}")
    print(f"  Omitidos:   {skipped}")
    print(f"  Errores:    {errors}")
    print(f"  Total DB:   {db.count_contactos()} contactos")

    db.close()

if __name__ == "__main__":
    import_linkedin_contacts()
