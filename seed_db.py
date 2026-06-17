#!/usr/bin/env python3
"""
seed_db.py — Puebla la base de datos unificada con datos existentes
Carga: Firebase (seguimiento, favoritos), Mercado Público API, Dashboard status
"""
import sys, os, json, urllib.request, datetime, re
sys.path.insert(0, r"C:\Users\Usuario\Desktop\Programación\Dashboard-BOTS")
from unified_db import get_db

TICKET_MP = "25D6C503-FA30-48BD-86FA-0A1D74D54254"
FIREBASE_BASE = "https://firestore.googleapis.com/v1/projects/mercado-api-292ad/databases/(default)/documents/rooms"
MP_BASE = "https://api.mercadopublico.cl/servicios/v1/publico"
CA_BASE = "https://api2.mercadopublico.cl"
DASHBOARD_URL = "http://localhost:9191"

def fetch(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except:
        return {}

def firebase_fields_to_dict(data):
    """Convierte Firestore fields a dict plano"""
    result = {}
    for key, val in data.get("fields", {}).items():
        fields = val.get("mapValue", {}).get("fields", {})
        entry = {}
        for fk, fv in fields.items():
            for vt in ("stringValue", "integerValue", "doubleValue", "booleanValue"):
                if vt in fv:
                    entry[fk] = fv[vt]
                    break
        result[key] = entry
    return result

def seed():
    db = get_db()
    print("🌱 Sembrando base de datos...")

    # ─── 1. Firebase: Seguimiento y Favoritos ───
    print("  📥 Firebase...")
    seguimiento = firebase_fields_to_dict(fetch(f"{FIREBASE_BASE}/seg_public"))
    favoritos = firebase_fields_to_dict(fetch(f"{FIREBASE_BASE}/public"))

    for codigo, data in seguimiento.items():
        estado = data.get("estado", "")
        fav = favoritos.get(codigo, {})
        rating = int(fav.get("rating", 0)) if fav.get("rating") else 0
        db.upsert_contacto(
            codigo_externo=codigo,
            nombre=f"[Seguimiento] {codigo}",
            nota=rating,
            estado_seguimiento=estado,
            fuente="mercadopublico",
            metadata=json.dumps({"savedAt": data.get("savedAt", "")})
        )
        print(f"    ✓ {codigo}: {estado}" + (f" ⭐{rating}" if rating else ""))

    # ─── 2. Mercado Público: Licitaciones activas (primeras 50) ───
    print("  📥 Mercado Público (activas)...")
    data = fetch(f"{MP_BASE}/licitaciones.json?ticket={TICKET_MP}&estado=activas")
    for l in (data.get("Listado", []) or [])[:200]:
        codigo = l.get("CodigoExterno", "")
        if not codigo:
            continue
        nombre = l.get("Nombre", "")[:200]
        cod_estado = l.get("CodigoEstado", "")
        cats = []
        # Save
        db.upsert_licitacion(
            codigo_externo=codigo,
            nombre=nombre,
            descripcion=(l.get("Descripcion", "") or "")[:500],
            tipo=l.get("Tipo", ""),
            codigo_estado=cod_estado,
            estado_nombre={5:"Publicada",6:"Cerrada",7:"Desierta",8:"Adjudicada",
                          18:"Revocada",19:"Suspendida",20:"Cancelada"}.get(cod_estado, ""),
            organismo_nombre=(l.get("NombreOrganismo", "") or "")[:100],
            fecha_cierre=l.get("FechaCierre", ""),
            moneda=l.get("Moneda", "CLP"),
            monto_estimado=l.get("MontoEstimado"),
            categorias=json.dumps(cats),
            rating=int(str(favoritos.get(codigo, {}).get("rating", 0))),
        )
    print(f"    ✓ {len(list(data.get('Listado',[]) or []))} licitaciones")

    # ─── 3. Compra Ágil ───
    print("  📥 Compra Ágil (publicadas)...")
    ca_data = fetch(f"{CA_BASE}/v2/compra-agil?estado=publicada&tamano_pagina=50&numero_pagina=1",
                    headers={"ticket": TICKET_MP})
    items = ca_data.get("payload", {}).get("items", [])
    for item in items:
        codigo = item.get("codigo", "")
        if not codigo:
            continue
        fechas = item.get("fechas", {}) or {}
        montos = item.get("montos", {}) or {}
        inst = item.get("institucion", {}) or {}
        db.upsert_compra_agil(
            codigo=codigo,
            nombre=(item.get("nombre", "") or "")[:200],
            estado=item.get("estado", {}).get("codigo", ""),
            organismo=(inst.get("organismo_comprador", "") or "")[:100],
            region=(inst.get("nombre_region", "") or "").strip(),
            fecha_cierre=fechas.get("fecha_cierre", ""),
            monto_disponible=montos.get("monto_disponible"),
            rating=int(str(favoritos.get(codigo, {}).get("rating", 0))),
        )
    print(f"    ✓ {len(items)} compras ágiles")

    # ─── 4. Bot History desde Dashboard ───
    print("  📥 Bot History (dashboard)...")
    try:
        status = fetch(f"{DASHBOARD_URL}/api/status")
        for bid, bdata in status.get("bots", {}).items():
            db.save_bot_snapshot(bid, bdata.get("status",""), bdata.get("status_text",""), {
                "positions": bdata.get("open_positions", 0),
                "profit": bdata.get("total_profit", 0),
                "items": bdata.get("last_items", 0),
            })
            print(f"    ✓ {bid}: {bdata.get('status_text','')[:50]}")
    except Exception as e:
        print(f"    ⚠️ Dashboard no disponible: {e}")

    # ─── 5. Stats final ───
    stats = db.get_global_stats()
    print(f"\n✅ Siembra completa!")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    db.close()

if __name__ == "__main__":
    seed()
