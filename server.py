"""
BOT Dashboard - Servidor con detección de procesos en tiempo real
Ejecutar: python server.py
URL: http://localhost:9191
"""
import json
import os
import subprocess
import sys
import re
import sqlite3
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime
from urllib.parse import urlparse

# ─── Base de Datos Unificada ───
sys.path.insert(0, str(Path(__file__).parent))
from unified_db import get_db
db = get_db()

DASHBOARD_DIR = Path(__file__).parent
LINKEDIN_DIR  = Path(r"C:\Users\Usuario\Desktop\Programación\Linkedin-AG")
MERCADO_DIR   = Path(r"C:\Users\Usuario\Desktop\Programación\MercadoPublico-AG (API)")
TRADING_DIR   = Path(r"C:\Users\Usuario\Desktop\Programación\spot2")

# ─── Utilidades ──────────────────────────────────────────────────────────────

def get_running_processes():
    """Devuelve lista de procesos activos relevantes"""
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, timeout=5, encoding='cp1252', errors='replace'
        )
        procs = []
        for line in result.stdout.splitlines():
            parts = line.strip().strip('"').split('","')
            if len(parts) >= 5:
                procs.append({
                    "name": parts[0],
                    "pid":  parts[1],
                    "mem":  parts[4]
                })
        return procs
    except Exception:
        return []

def is_process_running(name_fragment: str, procs=None) -> dict:
    """Detecta si un proceso está corriendo por fragmento de nombre"""
    if procs is None:
        procs = get_running_processes()
    matches = [p for p in procs if name_fragment.lower() in p["name"].lower()]
    return {
        "running": len(matches) > 0,
        "count":   len(matches),
        "pids":    [m["pid"] for m in matches]
    }

def check_linkedin_dashboard_running() -> dict:
    """Detecta si dashboard_app.py o scrap.py de LinkedIn están corriendo (PowerShell rápido)"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-WmiObject Win32_Process -Filter \"name='python.exe'\" | Select-Object ProcessId,CommandLine | ConvertTo-Csv -NoTypeInformation"],
            capture_output=True, encoding='utf-8', errors='replace', timeout=6
        )
        for line in result.stdout.splitlines():
            line_lower = line.lower()
            if 'dashboard_app' in line_lower:
                parts = line.strip().strip('"').split('","')
                pid = parts[0].strip('"') if parts else ''
                return {"running": True, "pid": pid, "script": "dashboard_app.py"}
            if 'scrap.py' in line_lower:
                parts = line.strip().strip('"').split('","')
                pid = parts[0].strip('"') if parts else ''
                return {"running": True, "pid": pid, "script": "scrap.py"}
        return {"running": False, "pid": None, "script": None}
    except Exception:
        return {"running": False, "pid": None, "script": None}

# ─── LinkedIn Data ────────────────────────────────────────────────────────────

def load_linkedin_posts(limit: int = 20) -> list:
    """Carga posts recientes desde extracted_posts.json"""
    try:
        path = LINKEDIN_DIR / "extracted_posts.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        # Ordenar por fecha descendente
        data.sort(key=lambda p: p.get("scraped_at", ""), reverse=True)
        return data[:limit]
    except Exception:
        return []

def load_linkedin_ofertas(limit: int = 50, solo_estructurales: bool = False) -> list:
    """Carga ofertas desde Todas_Ofertas.csv o Ofertas_Estructurales.csv"""
    try:
        filename = "Ofertas_Estructurales.csv" if solo_estructurales else "Todas_Ofertas.csv"
        path = LINKEDIN_DIR / filename
        if not path.exists():
            return []
        import csv
        with open(str(path), "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        return rows[:limit]
    except Exception:
        return []

def load_linkedin_contactos_emails(limit: int = 50) -> list:
    """Carga contactos con emails desde Contactos_Emails.csv"""
    try:
        path = LINKEDIN_DIR / "Contactos_Emails.csv"
        if not path.exists():
            return []
        import csv
        with open(str(path), "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        return rows[:limit]
    except Exception:
        return []

def get_linkedin_stats() -> dict:
    """Estadísticas completas de LinkedIn"""
    try:
        posts_path = LINKEDIN_DIR / "extracted_posts.json"
        ofertas_path = LINKEDIN_DIR / "Todas_Ofertas.csv"
        estructurales_path = LINKEDIN_DIR / "Ofertas_Estructurales.csv"
        contactos_path = LINKEDIN_DIR / "Contactos_Emails.csv"

        stats = {"total_posts": 0, "total_ofertas": 0, "total_estructurales": 0,
                 "total_contactos_email": 0, "autores_unicos": 0,
                 "ultimo_scraping": None, "ultima_oferta": None,
                 "estructurales_contacto": 0, "contactados": 0}

        # Posts
        if posts_path.exists():
            posts = json.loads(posts_path.read_text(encoding="utf-8", errors="replace"))
            stats["total_posts"] = len(posts)
            autores = set()
            for p in posts:
                a = p.get("author", "")
                if a: autores.add(a)
            stats["autores_unicos"] = len(autores)
            scraped_times = [p.get("scraped_at", "") for p in posts if p.get("scraped_at")]
            if scraped_times:
                stats["ultimo_scraping"] = max(scraped_times)[:19]

        # Ofertas
        if ofertas_path.exists():
            import csv
            with open(str(ofertas_path), "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            stats["total_ofertas"] = len(rows)
            fechas = [r.get("Fecha", "") for r in rows if r.get("Fecha")]
            if fechas:
                stats["ultima_oferta"] = max(fechas)[:19]

        # Estructurales
        if estructurales_path.exists():
            import csv
            with open(str(estructurales_path), "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            stats["total_estructurales"] = len(rows)

        # Contactos con emails
        if contactos_path.exists():
            import csv
            with open(str(contactos_path), "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            stats["total_contactos_email"] = len(rows)
            stats["estructurales_contacto"] = sum(1 for r in rows if r.get("Es Estructural", "").lower() == "sí")
            stats["contactados"] = sum(1 for r in rows if r.get("Contactado", "").lower() == "true")

        return stats
    except Exception as e:
        return {"error": str(e)}

# ─── Estructurales (sección dedicada) ────────────────────

LI_CONTACTADOS_FILE = DASHBOARD_DIR / "li_contactados.json"

def _load_contactados() -> set:
    """Carga set de ofertas marcadas como contactadas"""
    if LI_CONTACTADOS_FILE.exists():
        try:
            return set(json.loads(LI_CONTACTADOS_FILE.read_text(encoding="utf-8")))
        except:
            return set()
    return set()

def _save_contactados(codes: set):
    LI_CONTACTADOS_FILE.write_text(json.dumps(list(codes)), encoding="utf-8")

def load_estructurales(limit: int = 50, region: str = "", solo_email: bool = False) -> dict:
    """Carga ofertas estructurales con filtros y estado contactado"""
    try:
        path = LINKEDIN_DIR / "Ofertas_Estructurales.csv"
        if not path.exists():
            return {"ofertas": [], "regiones": [], "total": 0, "contactados": 0}
        import csv
        with open(str(path), "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        contactados = _load_contactados()
        regiones_set = set()

        result = []
        for r in rows:
            reg = r.get("Region", "").strip()
            email = r.get("Correos", "").strip()
            score = float(r.get("Score", 0) or 0)

            # Extraer regiones individuales
            if reg:
                for rpart in reg.split(","):
                    rclean = rpart.strip()
                    if rclean:
                        regiones_set.add(rclean)

            # Filtro por región
            if region and region not in reg:
                continue

            # Filtro solo con email
            if solo_email and not email:
                continue

            # Autor como ID único
            uid = f"{r.get('Autor','')}|{r.get('Fecha','')}"
            marcado = uid in contactados

            result.append({
                "autor": r.get("Autor", ""),
                "correos": email,
                "region": reg,
                "comuna": r.get("Comuna", ""),
                "fecha": r.get("Fecha", ""),
                "score": score,
                "rol": r.get("Rol", ""),
                "empresa": r.get("Empresa", ""),
                "texto": (r.get("Texto", "") or "")[:300],
                "es_contacto": r.get("Es Contacto", ""),
                "url_perfil": r.get("URL Perfil", ""),
                "uid": uid,
                "contactado": marcado,
            })

        # Ordenar: no contactados primero, luego por score descendente
        result.sort(key=lambda x: (x["contactado"], -x["score"]))

        regiones = sorted(regiones_set)
        total_contactados = sum(1 for r in result if r["contactado"])

        return {
            "ofertas": result[:limit],
            "regiones": regiones,
            "total": len(rows),
            "filtrados": len(result),
            "contactados": total_contactados,
        }
    except Exception as e:
        return {"error": str(e)}

# ─── CRM - Seguimiento de Contactos ──────────────────────

CRM_DB_PATH = DASHBOARD_DIR / "crm.db"

def _init_crm_db():
    """Inicializa la base de datos CRM si no existe"""
    schema_path = DASHBOARD_DIR / "crm_schema.sql"
    conn = sqlite3.connect(str(CRM_DB_PATH))
    conn.row_factory = sqlite3.Row
    if schema_path.exists():
        schema = schema_path.read_text(encoding="utf-8")
        for statement in schema.split(";"):
            s = statement.strip()
            if s:
                try:
                    conn.execute(s)
                except Exception:
                    pass
        conn.commit()
    return conn

def _crm_conn():
    conn = sqlite3.connect(str(CRM_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def crm_stats() -> dict:
    """Estadísticas del CRM"""
    try:
        conn = _crm_conn()
        cur = conn.cursor()
        total = cur.execute("SELECT COUNT(*) FROM contactos_crm").fetchone()[0]
        pendientes = cur.execute("SELECT COUNT(*) FROM contactos_crm WHERE estado='pendiente'").fetchone()[0]
        contactados = cur.execute("SELECT COUNT(*) FROM contactos_crm WHERE estado IN ('contactado','en_seguimiento')").fetchone()[0]
        responded = cur.execute("SELECT COUNT(*) FROM contactos_crm WHERE estado='responded'").fetchone()[0]
        con_email = cur.execute("SELECT COUNT(*) FROM contactos_crm WHERE email != ''").fetchone()[0]
        conn.close()
        return {"total": total, "pendientes": pendientes, "contactados": contactados,
                "responded": responded, "con_email": con_email}
    except Exception as e:
        return {"error": str(e), "total": 0, "pendientes": 0, "contactados": 0}

def crm_list(estado: str = "", search: str = "", limit: int = 50) -> list:
    """Lista contactos CRM con filtros"""
    try:
        conn = _crm_conn()
        where = []
        params = []
        if estado:
            if estado == "activos":
                where.append("estado NOT IN ('cerrado')")
            else:
                where.append("estado = ?")
                params.append(estado)
        if search:
            where.append("(nombre LIKE ? OR email LIKE ? OR empresa LIKE ? OR rol LIKE ?)")
            params += [f"%{search}%"] * 4
        sql = "SELECT * FROM contactos_crm"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY CASE estado WHEN 'pendiente' THEN 0 WHEN 'contactado' THEN 1 WHEN 'en_seguimiento' THEN 2 WHEN 'responded' THEN 3 ELSE 4 END, score DESC LIMIT ?"
        params.append(limit)
        cur = conn.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        return []

def crm_import_from_estructurales():
    """Importa ofertas estructurales no contactadas al CRM"""
    try:
        # Cargar estructurales
        data = load_estructurales(limit=400)
        conn = _crm_conn()
        cur = conn.cursor()
        imported = 0
        for o in data.get("ofertas", []):
            if not o.get("correos") and not o.get("autor"):
                continue
            uid = o["uid"]
            # Verificar si ya existe
            existing = cur.execute("SELECT id FROM contactos_crm WHERE uid=?", (uid,)).fetchone()
            if existing:
                continue
            cur.execute(
                "INSERT OR IGNORE INTO contactos_crm (uid, nombre, email, empresa, rol, region, score, fuente, estado) VALUES (?,?,?,?,?,?,?,?,?)",
                (uid, o["autor"][:100], o["correos"][:200], o["empresa"][:100],
                 o["rol"][:100], o["region"][:100], o["score"],
                 "linkedin", "pendiente" if o.get("correos") else "pendiente")
            )
            imported += cur.rowcount
        conn.commit()
        conn.close()
        return {"imported": imported}
    except Exception as e:
        return {"error": str(e)}

def crm_add(nombre: str, email: str = "", empresa: str = "", rol: str = "",
            region: str = "", fuente: str = "manual", notas: str = "") -> dict:
    """Agrega un contacto manual al CRM"""
    try:
        conn = _crm_conn()
        uid = f"manual_{nombre.replace(' ','_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        conn.execute(
            "INSERT INTO contactos_crm (uid, nombre, email, empresa, rol, region, fuente, notas) VALUES (?,?,?,?,?,?,?,?)",
            (uid, nombre, email, empresa, rol, region, fuente, notas))
        conn.commit()
        conn.close()
        return {"success": True, "uid": uid}
    except Exception as e:
        return {"error": str(e)}

def crm_update(uid: str, **kwargs) -> dict:
    """Actualiza un contacto CRM"""
    try:
        conn = _crm_conn()
        allowed = {"estado", "notas", "metodo", "fecha_contacto"}
        sets = []
        vals = []
        for k, v in kwargs.items():
            if k in allowed:
                sets.append(f"{k}=?")
                vals.append(v)
        if sets:
            sets.append("actualizado_en = datetime('now','-4 hours')")
            if kwargs.get("estado") == "contactado" and "fecha_contacto" not in kwargs:
                sets.append("fecha_contacto = datetime('now','-4 hours')")
            sql = f"UPDATE contactos_crm SET {', '.join(sets)} WHERE uid=?"
            vals.append(uid)
            conn.execute(sql, vals)
            conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}

def crm_log_interaccion(contacto_uid: str, tipo: str, contenido: str = "",
                        estado: str = "") -> dict:
    """Registra una interacción (email enviado, nota, etc.)"""
    try:
        conn = _crm_conn()
        conn.execute(
            "INSERT INTO interacciones (contacto_uid, tipo, contenido, estado) VALUES (?,?,?,?)",
            (contacto_uid, tipo, contenido, estado))
        # Actualizar contador en contacto
        conn.execute(
            "UPDATE contactos_crm SET num_seguimientos = num_seguimientos + 1, ultimo_seguimiento = datetime('now','-4 hours'), actualizado_en = datetime('now','-4 hours') WHERE uid=?",
            (contacto_uid,))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}

def crm_get_interacciones(contacto_uid: str, limit: int = 20) -> list:
    """Obtiene historial de interacciones de un contacto"""
    try:
        conn = _crm_conn()
        cur = conn.execute(
            "SELECT * FROM interacciones WHERE contacto_uid=? ORDER BY fecha DESC LIMIT ?",
            (contacto_uid, limit))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        return []

# ─── Detección, Seguimiento y Feedback ─────────────────────
# Integra funcionalidad del Streamlit dashboard (8501) en Dashboard-BOTS

SEGUIMIENTO_FILE = LINKEDIN_DIR / "seguimiento.json"
TRAINING_FILE = LINKEDIN_DIR / "training_data.json"
KEYWORDS_FILE = LINKEDIN_DIR / "job_keywords.json"
NETWORK_FILE = LINKEDIN_DIR / "network_stats.json"

def load_json_file(path: Path, default=list):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except:
            return default()
    return default()

def save_json_file(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def get_detection_stats() -> dict:
    """Estadísticas de detección: cuántos posts => ofertas"""
    try:
        posts = load_json_file(LINKEDIN_DIR / "extracted_posts.json", default=list)
        training = load_json_file(TRAINING_FILE, default=list)
        keywords = load_json_file(KEYWORDS_FILE, default=dict)
        network = load_json_file(NETWORK_FILE, default=dict)
        ofertas_csv = load_linkedin_ofertas(limit=5000)

        total_ofertas = len(ofertas_csv)
        total_posts = len(posts)
        pct = round(total_ofertas / max(total_posts, 1) * 100, 1)
        
        keywords_count = len(keywords.get("job_keywords", []) if isinstance(keywords, dict) else keywords)
        training_entries = len(training)
        training_votes = sum(1 for t in training if "votes" in t)
        
        # Network stats
        weekly_invites = network.get("weekly_invites", 0) if isinstance(network, dict) else 0
        followers = network.get("followers", 0) if isinstance(network, dict) else 0

        return {
            "total_posts": total_posts,
            "total_ofertas": total_ofertas,
            "porcentaje_deteccion": pct,
            "keywords_activas": keywords_count,
            "training_entries": training_entries,
            "training_votes": training_votes,
            "weekly_invites": weekly_invites,
            "followers": followers,
        }
    except Exception as e:
        return {"error": str(e)}

def get_seguimiento() -> list:
    return load_json_file(SEGUIMIENTO_FILE, default=list)

def seguimiento_add(data: dict) -> dict:
    """Agrega un post/oficina al seguimiento"""
    try:
        items = load_json_file(SEGUIMIENTO_FILE, default=list)
        text = data.get("text", "")
        # Evitar duplicados
        if any(item.get("text") == text for item in items):
            return {"success": False, "error": "Ya existe en seguimiento"}
        item = {
            "text": text,
            "autor": data.get("autor", ""),
            "empresa": data.get("empresa", ""),
            "correos": data.get("correos", ""),
            "url_perfil": data.get("url_perfil", ""),
            "region": data.get("region", ""),
            "score": data.get("score", 0),
            "estado": "pendiente",
            "notas": "",
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        items.append(item)
        save_json_file(SEGUIMIENTO_FILE, items)
        return {"success": True, "added": 1}
    except Exception as e:
        return {"error": str(e)}

def seguimiento_update(text: str, estado: str = "", notas: str = "") -> dict:
    """Actualiza estado/notas de un ítem en seguimiento"""
    try:
        items = load_json_file(SEGUIMIENTO_FILE, default=list)
        for item in items:
            if item.get("text") == text:
                if estado:
                    item["estado"] = estado
                if notas:
                    item["notas"] = notas
                item["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_json_file(SEGUIMIENTO_FILE, items)
                return {"success": True}
        return {"success": False, "error": "No encontrado"}
    except Exception as e:
        return {"error": str(e)}

def seguimiento_remove(text: str) -> dict:
    """Elimina un ítem del seguimiento"""
    try:
        items = load_json_file(SEGUIMIENTO_FILE, default=list)
        new_items = [item for item in items if item.get("text") != text]
        if len(new_items) == len(items):
            return {"success": False, "error": "No encontrado"}
        save_json_file(SEGUIMIENTO_FILE, new_items)
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}

# ─── Rating (Estrellas 1-5) ────────────────────────────────────

RATINGS_FILE = DASHBOARD_DIR / "post_ratings.json"

def get_ratings() -> dict:
    """Devuelve todas las puntuaciones { "autor|text_preview": {"rating": 4.2, "count": 5} }"""
    return load_json_file(RATINGS_FILE, default=dict)

def rate_post(author: str, text: str, stars: int) -> dict:
    """Puntúa un post de 1 a 5 estrellas. Acumula promedio."""
    try:
        stars = max(1, min(5, int(stars)))
        ratings = load_json_file(RATINGS_FILE, default=dict)
        key = f"{author[:30]}|{text[:80]}"
        if key in ratings:
            entry = ratings[key]
            total = entry.get("total", 0) + stars
            count = entry.get("count", 0) + 1
            entry["total"] = total
            entry["count"] = count
            entry["rating"] = round(total / count, 1)
            entry["last"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            ratings[key] = {"total": stars, "count": 1, "rating": float(stars),
                          "last": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                          "autor": author[:80], "text_preview": text[:120]}
        save_json_file(RATINGS_FILE, ratings)
        return {"success": True, "rating": ratings[key]["rating"], "count": ratings[key]["count"]}
    except Exception as e:
        return {"error": str(e)}

# ─── Análisis inteligente de feedback ─────────────────────

def analyze_feedback() -> dict:
    """Analiza training_data.json para sugerir mejoras al bot de detección"""
    try:
        training = load_json_file(TRAINING_FILE, default=list)
        keywords = load_json_file(KEYWORDS_FILE, default=dict)
        positive_kw = set(k.lower() for k in keywords.get("positive", []))
        negative_kw = set(k.lower() for k in keywords.get("negative", []))

        # Separar feedback confirmado
        confirmed_offers = [t for t in training if t.get("is_offer") and t.get("votes", {}).get("yes", 0) > t.get("votes", {}).get("no", 0)]
        confirmed_noise = [t for t in training if not t.get("is_offer") and t.get("votes", {}).get("no", 0) > t.get("votes", {}).get("yes", 0)]
        disputed = [t for t in training if t.get("votes", {}).get("yes", 0) == t.get("votes", {}).get("no", 0) and sum(t.get("votes", {}).values()) > 0]

        # Extraer palabras/frases de ofertas confirmadas
        import re
        stopwords = {"de", "la", "el", "en", "y", "a", "los", "las", "del", "se", "por", "un", "una",
                     "con", "no", "su", "para", "es", "al", "lo", "como", "más", "pero", "sus", "le",
                     "ya", "o", "este", "fue", "entre", "también", "muy", "hay", "era", "ser", "que",
                     "the", "and", "for", "are", "our", "you", "this", "that", "with", "from"}
        
        def extract_phrases(text: str, n=3) -> list:
            """Extrae bigramas y trigramas significativos"""
            words = re.findall(r'[a-záéíóúñüA-ZÁÉÍÓÚÑÜ#]{3,}', text.lower())
            phrases = []
            for i in range(len(words)-n+1):
                phrase = " ".join(words[i:i+n])
                if not all(w in stopwords for w in phrase.split()):
                    phrases.append(phrase)
            return phrases

        # Palabras frecuentes en ofertas vs ruido
        from collections import Counter
        offer_words = Counter()
        noise_words = Counter()
        offer_phrases = Counter()

        for o in confirmed_offers:
            text = o.get("text", "").lower()
            words = re.findall(r'[a-záéíóúñü]{3,}', text)
            offer_words.update(w for w in words if w not in stopwords)
            for p in extract_phrases(text, 2):
                offer_phrases[p.split()[-1] if len(p.split()) == 2 else p] += 0
            for p in extract_phrases(text, 3):
                offer_phrases[p] += 1

        for n in confirmed_noise:
            text = n.get("text", "").lower()
            words = re.findall(r'[a-záéíóúñü]{3,}', text)
            noise_words.update(w for w in words if w not in stopwords)

        # Keywords con mejor precisión (cuántas ofertas confirman vs ruido)
        kw_precision = {}
        for kw in positive_kw:
            offers_with_kw = sum(1 for o in confirmed_offers if kw in o.get("text","").lower())
            noise_with_kw = sum(1 for n in confirmed_noise if kw in n.get("text","").lower())
            total_matches = offers_with_kw + noise_with_kw
            if total_matches > 0:
                kw_precision[kw] = {
                    "precision": round(offers_with_kw / total_matches * 100, 1),
                    "ofertas": offers_with_kw,
                    "ruido": noise_with_kw,
                }

        # Top keywords efectivas y problemáticas
        effective = sorted(
            [(k, v) for k, v in kw_precision.items() if v["precision"] >= 70],
            key=lambda x: -x[1]["ofertas"]
        )[:15]

        problematic = sorted(
            [(k, v) for k, v in kw_precision.items() if v["precision"] < 30 and v["ruido"] > 0],
            key=lambda x: -x[1]["ruido"]
        )[:10]

        # Sugerir nuevas keywords (frases frecuentes en ofertas confirmadas no en keywords)
        suggested_new = []
        for phrase, count in offer_phrases.most_common(30):
            if count >= 1 and phrase.lower() not in positive_kw and phrase.lower() not in negative_kw:
                if len(phrase) > 4:
                    suggested_new.append({"keyword": phrase, "frecuencia": count})

        # Keywords más activadas en ofertas (aunque no estén en el set actual)
        top_offer_words = [(w, c) for w, c in offer_words.most_common(30) 
                          if w not in positive_kw and w not in stopwords and len(w) > 5]
        word_suggestions = [{"keyword": w, "frecuencia": c} for w, c in top_offer_words[:15]]

        # Métricas de mejora
        total_votes = sum(t.get("votes",{}).get("yes",0) + t.get("votes",{}).get("no",0) for t in training)
        agreement = sum(1 for t in training 
                      if (t.get("is_offer") and t.get("votes",{}).get("yes",0) > t.get("votes",{}).get("no",0))
                      or (not t.get("is_offer") and t.get("votes",{}).get("no",0) > t.get("votes",{}).get("yes",0)))
        bot_accuracy = round(agreement / max(len(training), 1) * 100, 1)

        return {
            "feedback_total": len(training),
            "ofertas_confirmadas": len(confirmed_offers),
            "ruido_confirmado": len(confirmed_noise),
            "disputados": len(disputed),
            "total_votos": total_votes,
            "bot_accuracy": bot_accuracy,
            "keywords_efectivas": [{"kw": k, **v} for k, v in effective],
            "keywords_problematicas": [{"kw": k, **v} for k, v in problematic],
            "sugerencias_frases": suggested_new[:12],
            "sugerencias_palabras": word_suggestions[:10],
            "total_keywords_positivas": len(positive_kw),
            "total_keywords_negativas": len(negative_kw),
        }
    except Exception as e:
        return {"error": str(e)}


def feedback_vote(author: str, text: str, is_offer: bool, is_structural: bool = False) -> dict:
    """Vota un post como oferta o no oferta"""
    try:
        items = load_json_file(TRAINING_FILE, default=list)
        # Buscar existente
        found = None
        for item in items:
            if item.get("text") == text and item.get("author") == author:
                found = item
                break
        if found:
            if "votes" not in found:
                found["votes"] = {"yes": 0, "no": 0}
            if is_offer:
                found["votes"]["yes"] = found["votes"].get("yes", 0) + 1
            else:
                found["votes"]["no"] = found["votes"].get("no", 0) + 1
            found["is_offer"] = found["votes"]["yes"] > found["votes"]["no"]
            found["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if is_structural:
                found["is_structural"] = True
        else:
            new_item = {
                "author": author,
                "text": text,
                "is_offer": is_offer,
                "is_structural": is_structural,
                "votes": {"yes": 1 if is_offer else 0, "no": 1 if not is_offer else 0},
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            items.append(new_item)
        save_json_file(TRAINING_FILE, items)
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


def read_log_tail(log_path: Path, lines: int = 15) -> list:
    """Lee las últimas N líneas de un log"""
    try:
        if not log_path.exists():
            return []
        text = log_path.read_text(encoding="utf-8", errors="replace")
        all_lines = [l for l in text.splitlines() if l.strip()]
        return all_lines[-lines:]
    except Exception:
        return []

def parse_mercado_log(log_path: Path) -> dict:
    """Parsea el log de MercadoPublico para extraer métricas"""
    tail = read_log_tail(log_path, 80)
    last_run = None
    last_status = None
    last_items = None
    errors_429 = 0
    last_exit_code = None

    for line in reversed(tail):
        if "Iniciando" in line and last_run is None:
            m = re.search(r'\[(.+?)\]', line)
            if m: last_run = m.group(1).strip()
        if "Finalizado (codigo" in line and last_exit_code is None:
            m = re.search(r'codigo (\d+)', line)
            if m: last_exit_code = int(m.group(1))
            last_status = "ok" if last_exit_code == 0 else "error"
        if "oportunidades guardadas" in line and last_items is None:
            m = re.search(r'(\d+) oportunidades', line)
            if m: last_items = int(m.group(1))

    for line in tail:
        if "429" in line:
            errors_429 += 1

    return {
        "last_run":    last_run,
        "last_status": last_status or "unknown",
        "last_items":  last_items,
        "errors_429":  errors_429,
        "log_tail":    tail[-10:],
    }

def get_git_status(repo_path: Path) -> dict:
    """Estado git del repositorio"""
    try:
        def git(args):
            r = subprocess.run(
                ["git"] + args,
                cwd=str(repo_path), capture_output=True,
                encoding='utf-8', errors='replace', timeout=8
            )
            return r.stdout.strip(), r.returncode

        # Branch actual
        branch, _ = git(["rev-parse", "--abbrev-ref", "HEAD"])

        # Cuánto detrás/delante del origin
        git(["fetch", "--quiet"])
        ahead_behind, _ = git(["rev-list", "--left-right", "--count", "HEAD...@{u}"])
        ahead, behind = (0, 0)
        if ahead_behind:
            parts = ahead_behind.split()
            if len(parts) == 2:
                ahead, behind = int(parts[0]), int(parts[1])

        # Archivos modificados sin commit
        status_out, _ = git(["status", "--porcelain"])
        dirty_files = [l[3:].strip() for l in status_out.splitlines() if l.strip()]

        # Últimos 5 commits
        log_out, _ = git(["log", "-5", "--pretty=format:%h|%cd|%s", "--date=short"])
        commits = []
        if log_out:
            for line in log_out.splitlines():
                parts = line.split("|", 2)
                if len(parts) == 3:
                    commits.append({"hash": parts[0], "date": parts[1], "msg": parts[2]})

        return {
            "ok": True,
            "branch": branch.strip(),
            "ahead": ahead,
            "behind": behind,
            "dirty": len(dirty_files) > 0,
            "dirty_files": dirty_files,
            "commits": commits
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}




# ─── Endpoint principal ───────────────────────────────────────────────────────

def build_status() -> dict:
    procs = get_running_processes()
    now   = datetime.now().isoformat(timespec="seconds")

    # ── LinkedIn ──
    li_app_info        = check_linkedin_dashboard_running()
    linkedin_log_lines = read_log_tail(LINKEDIN_DIR / "scrap_log.txt", 12)
    linkedin_session   = (LINKEDIN_DIR / "linkedin_state.json").exists()
    linkedin_git       = get_git_status(LINKEDIN_DIR)

    # Determinar estado LinkedIn
    if li_app_info["running"]:
        li_status = "running"
        li_status_text = f"🔄 {li_app_info['script']} activo"
    elif linkedin_session:
        li_status = "ok"
        li_status_text = "✅ Listo (sesión activa)"
    else:
        li_status = "warn"
        li_status_text = "⚠️ Sin sesión"

    # ── MercadoPublico ──
    mp_log_path  = MERCADO_DIR / "scripts" / "update-compra-agil.log"
    mp_log_data  = parse_mercado_log(mp_log_path)
    mp_git       = get_git_status(MERCADO_DIR)
    mp_node_running = is_process_running("node", procs)

    mp_sync_status = {}
    try:
        sync_file = MERCADO_DIR / "scripts" / "sync-status.json"
        if sync_file.exists():
            mp_sync_status = json.loads(sync_file.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        pass

    sync_val = mp_sync_status.get("status")
    if sync_val == "error":
        mp_status = "error"
        mp_status_text = "❌ Error Tareas/Sync"
    elif sync_val == "warn":
        mp_status = "warn"
        mp_status_text = "⚠️ Atención Git/Sync"
    elif mp_node_running["running"] and mp_log_data["last_status"] != "error":
        mp_status = "running"
        mp_status_text = "🔄 Snapshot en curso"
    elif mp_log_data["last_status"] == "ok" and mp_log_data["errors_429"] == 0:
        mp_status = "ok"
        mp_status_text = "✅ Operativo"
    elif mp_log_data["errors_429"] > 0:
        mp_status = "warn"
        mp_status_text = f"⚠️ {mp_log_data['errors_429']} errores 429"
    else:
        mp_status = "unknown"
        mp_status_text = "❓ Sin datos"

    # ── Trading Bot (spot2 / Binance) ──
    trading_log_path = TRADING_DIR / "logs" / "bot.log"
    trading_log_tail = read_log_tail(trading_log_path, 15)
    trading_git      = get_git_status(TRADING_DIR)

    # Leer portfolio.json para posiciones actuales
    portfolio_data = {}
    try:
        pf_path = TRADING_DIR / "portfolio.json"
        if pf_path.exists():
            portfolio_data = json.loads(pf_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        pass

    positions     = portfolio_data.get("positions", {})
    profit_hist   = portfolio_data.get("profit_history", {})
    total_profit  = profit_hist.get("total_profit_usdt", 0)
    total_trades  = profit_hist.get("total_trades", 0)
    winning       = profit_hist.get("winning_trades", 0)
    losing        = profit_hist.get("losing_trades", 0)
    win_rate      = round(winning / total_trades * 100, 1) if total_trades > 0 else 0
    last_buy_time = portfolio_data.get("last_buy_time", None)

    # Detectar si bot.py está corriendo: buscar en log la línea más reciente
    bot_recently_active = False
    last_cycle = None
    last_check = None
    for line in reversed(trading_log_tail):
        if "CICLO COMPLETO" in line and last_cycle is None:
            m = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if m: last_cycle = m.group(1)
        if "CHECK #" in line and last_check is None:
            m = re.search(r'(\d{2}:\d{2}:\d{2})', line)
            if m: last_check = m.group(1)

    # Si el último ciclo fue en los últimos 10 minutos => activo
    if last_cycle:
        try:
            from datetime import timedelta
            cycle_dt = datetime.strptime(last_cycle, "%Y-%m-%d %H:%M:%S")
            bot_recently_active = (datetime.now() - cycle_dt).total_seconds() < 600
        except Exception:
            pass

    # Detectar proceso python corriendo con bot.py
    bot_process = is_process_running("python", procs)

    if bot_recently_active:
        tr_status      = "ok"
        tr_status_text = "🟢 Activo — ciclo reciente"
    elif len(positions) > 0:
        tr_status      = "warn"
        tr_status_text = f"⏸ Pausado — {len(positions)} pos. abiertas"
    else:
        tr_status      = "unknown"
        tr_status_text = "⬜ Sin actividad reciente"

    # Posiciones abiertas como lista resumida
    positions_list = []
    for sym, pos in positions.items():
        positions_list.append({
            "symbol":     sym,
            "buy_price":  pos.get("buy_price"),
            "invested":   round(pos.get("usdt_invested", 0), 2),
            "buy_time":   pos.get("buy_time", "")[:16].replace("T", " "),
            "trade_type": pos.get("trade_type", ""),
        })

    return {
        "timestamp": now,
        "bots": {
            "linkedin": {
                "id":           "linkedin-ag",
                "name":         "LinkedIn-AG",
                "status":       li_status,
                "status_text":  li_status_text,
                "scraper_open": li_app_info["running"],
                "script":       li_app_info["script"],
                "pid":          li_app_info["pid"],
                "session_ok":   linkedin_session,
                "log_tail":     linkedin_log_lines,
                "git":          linkedin_git,
            },
            "mercadopublico": {
                "id":           "mercadopublico-ag",
                "name":         "MercadoPublico-AG",
                "status":       mp_status,
                "status_text":  mp_status_text,
                "node_running": mp_node_running["running"],
                "node_pids":    mp_node_running["pids"],
                "last_run":     mp_log_data["last_run"],
                "last_items":   mp_log_data["last_items"],
                "errors_429":   mp_log_data["errors_429"],
                "log_tail":     mp_log_data["log_tail"],
                "sync_status":  mp_sync_status,
                "git":          mp_git,
            },
            "trading": {
                "id":              "spot2",
                "name":            "Binance Trading Bot",
                "status":          tr_status,
                "status_text":     tr_status_text,
                "bot_active":      bot_recently_active,
                "last_cycle":      last_cycle,
                "last_check":      last_check,
                "open_positions":  len(positions),
                "positions_list":  positions_list,
                "total_profit":    round(total_profit, 4),
                "total_trades":    total_trades,
                "winning_trades":  winning,
                "losing_trades":   losing,
                "win_rate":        win_rate,
                "last_buy_time":   last_buy_time,
                "log_tail":        trading_log_tail,
                "git":             trading_git,
            },
        }
    }


# ─── HTTP Handler ─────────────────────────────────────────────────────────────

class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/status":
            try:
                data = build_status()
                body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())
        elif parsed.path == "/api/start_linkedin":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            app_info = check_linkedin_dashboard_running()
            if app_info["running"]:
                self.wfile.write(json.dumps({"success": True, "msg": "Ya estaba corriendo"}).encode())
                return
                
            try:
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-WindowStyle", "Normal", "-Command", "Start-Process python -ArgumentList 'dashboard_app.py','--autostart' -WorkingDirectory 'C:\\Users\\Usuario\\Desktop\\Programación\\Linkedin-AG' -WindowStyle Normal"],
                    cwd=str(LINKEDIN_DIR),
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
                self.wfile.write(json.dumps({"success": True, "msg": "Bot lanzado exitosamente"}).encode())
            except Exception as e:
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())
            return
        elif parsed.path == "/api/capture":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            from urllib.parse import parse_qs
            query = parse_qs(parsed.query)
            target_id = query.get("id", [""])[0]
            
            if target_id in ["mp-api", "linkedin-feed"]:
                subprocess.Popen(
                    ["python", "screenshot_worker.py", target_id],
                    cwd=str(DASHBOARD_DIR),
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
                self.wfile.write(json.dumps({"success": True, "msg": "Captura iniciada en background"}).encode())
            else:
                self.wfile.write(json.dumps({"success": False, "error": "ID inválido"}).encode())
            return
        # ─── API: Database ───────────────────────────────────────────
        elif parsed.path == "/api/db/stats":
            try:
                stats = db.get_global_stats()
                bot_status = build_status()
                for bid, bdata in bot_status.get("bots", {}).items():
                    db.save_bot_snapshot(bid, bdata.get("status","unknown"), bdata.get("status_text",""), {
                        "positions": bdata.get("open_positions",0),
                        "profit": bdata.get("total_profit",0),
                        "items": bdata.get("last_items",0),
                    })
                stats["bots"] = {k: {"status":v.get("status"),"status_text":v.get("status_text")}
                                for k,v in bot_status.get("bots",{}).items()}
                body = json.dumps(stats, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/db/search":
            try:
                from urllib.parse import parse_qs
                q = parse_qs(parsed.query).get("q",[""])[0]
                results = db.search(q) if q else []
                body = json.dumps({"results":results,"query":q}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/db/contactos":
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query)
                contactos = db.get_contactos(search=qs.get("q",[None])[0], estado=qs.get("estado",[None])[0],
                                            limit=int(qs.get("limit",[50])[0]))
                body = json.dumps({"contactos":contactos,"total":db.count_contactos()}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/db/organismos":
            try:
                orgs = db.get_organismos_mas_activos()
                body = json.dumps({"organismos":orgs}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/db/licitaciones":
            try:
                licits = db.get_licitaciones_interesantes()
                body = json.dumps({"licitaciones":licits,"total":db.count_licitaciones()}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/db/history":
            try:
                from urllib.parse import parse_qs
                bot_id = parse_qs(parsed.query).get("bot_id",["trading"])[0]
                history = db.get_bot_history(bot_id)
                body = json.dumps({"history":history,"bot_id":bot_id}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        # ─── API: LinkedIn ────────────────────────────────────────────
        elif parsed.path == "/api/linkedin/stats":
            try:
                stats = get_linkedin_stats()
                body = json.dumps(stats, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/linkedin/posts":
            try:
                from urllib.parse import parse_qs
                limit = int(parse_qs(parsed.query).get("limit",[20])[0])
                data = load_linkedin_posts(limit)
                body = json.dumps({"posts":data,"total":len(data)}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/linkedin/ofertas":
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query)
                limit = int(qs.get("limit",[50])[0])
                estructurales = qs.get("estructurales",["false"])[0].lower() == "true"
                data = load_linkedin_ofertas(limit, solo_estructurales=estructurales)
                body = json.dumps({"ofertas":data,"total":len(data),"tipo":"estructurales" if estructurales else "todas"}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/linkedin/contactos":
            try:
                from urllib.parse import parse_qs
                limit = int(parse_qs(parsed.query).get("limit",[50])[0])
                data = load_linkedin_contactos_emails(limit)
                body = json.dumps({"contactos":data,"total":len(data)}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/linkedin/estructurales":
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query)
                limit = int(qs.get("limit",[50])[0])
                region = qs.get("region",[""])[0]
                solo_email = qs.get("email_only",["false"])[0].lower() == "true"
                data = load_estructurales(limit=limit, region=region, solo_email=solo_email)
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/linkedin/marcar_contactado":
            # GET para mantener simplicidad
            try:
                from urllib.parse import parse_qs
                uid = parse_qs(parsed.query).get("uid",[""])[0]
                action = parse_qs(parsed.query).get("action",["toggle"])[0]
                if not uid:
                    self.send_response(400); self.end_headers()
                    self.wfile.write(b'{"error":"uid requerido"}')
                    return
                contactados = _load_contactados()
                if action == "add":
                    contactados.add(uid)
                elif action == "remove":
                    contactados.discard(uid)
                else:  # toggle
                    if uid in contactados:
                        contactados.discard(uid)
                    else:
                        contactados.add(uid)
                _save_contactados(contactados)
                body = json.dumps({"success":True,"uid":uid,"contactado":uid in contactados,"total":len(contactados)}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        # ─── API: CRM ────────────────────────────────────────────────
        elif parsed.path == "/api/crm/init":
            """Inicializa CRM: importa datos desde estructurales"""
            try:
                # Primero asegurar que DB exista
                _init_crm_db()
                result = crm_import_from_estructurales()
                stats = crm_stats()
                body = json.dumps({**result, **stats}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/crm/stats":
            try:
                stats = crm_stats()
                body = json.dumps(stats, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/crm/list":
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query)
                estado = qs.get("estado",[""])[0]
                search = qs.get("search",[""])[0]
                limit = int(qs.get("limit",[50])[0])
                rows = crm_list(estado=estado, search=search, limit=limit)
                body = json.dumps({"contactos":rows, "total":len(rows)}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/crm/add":
            try:
                from urllib.parse import parse_qs, urlencode
                qs = parse_qs(parsed.query)
                nombre = qs.get("nombre",[""])[0]
                if not nombre:
                    self.send_response(400); self.end_headers()
                    self.wfile.write(b'{"error":"nombre requerido"}'); return
                result = crm_add(
                    nombre=nombre,
                    email=qs.get("email",[""])[0],
                    empresa=qs.get("empresa",[""])[0],
                    rol=qs.get("rol",[""])[0],
                    region=qs.get("region",[""])[0],
                    notas=qs.get("notas",[""])[0],
                )
                body = json.dumps(result, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/crm/update":
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query)
                uid = qs.get("uid",[""])[0]
                if not uid:
                    self.send_response(400); self.end_headers()
                    self.wfile.write(b'{"error":"uid requerido"}'); return
                kwargs = {}
                for k in ("estado", "notas", "metodo", "fecha_contacto"):
                    if k in qs and qs[k][0]:
                        kwargs[k] = qs[k][0]
                result = crm_update(uid, **kwargs)
                body = json.dumps(result, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/crm/log":
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query)
                uid = qs.get("uid",[""])[0]
                tipo = qs.get("tipo",["nota"])[0]
                contenido = qs.get("contenido",[""])[0]
                estado = qs.get("estado",[""])[0]
                if not uid or not tipo:
                    self.send_response(400); self.end_headers()
                    self.wfile.write(b'{"error":"uid y tipo requeridos"}'); return
                result = crm_log_interaccion(uid, tipo, contenido, estado)
                body = json.dumps(result, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/crm/interacciones":
            try:
                from urllib.parse import parse_qs
                uid = parse_qs(parsed.query).get("uid",[""])[0]
                if not uid:
                    self.send_response(400); self.end_headers()
                    self.wfile.write(b'{"error":"uid requerido"}'); return
                rows = crm_get_interacciones(uid)
                body = json.dumps({"interacciones":rows}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        # ─── API: Detección / Seguimiento / Feedback ──────────────
        elif parsed.path == "/api/linkedin/detection":
            try:
                stats = get_detection_stats()
                body = json.dumps(stats, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/linkedin/post-detail":
            try:
                from urllib.parse import parse_qs
                q = parse_qs(parsed.query).get("q",[""])[0]
                posts = load_json_file(LINKEDIN_DIR / "extracted_posts.json", default=list)
                match = None
                for p in posts:
                    if q and q in (p.get("text","") + p.get("author","")):
                        match = p
                        break
                if not match and posts:
                    match = posts[0]
                body = json.dumps({"post": match}, ensure_ascii=False).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/seguimiento/list":
            try:
                items = get_seguimiento()
                body = json.dumps({"items":items,"total":len(items)}, ensure_ascii=False).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*"); self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/seguimiento/add":
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query)
                data = {k: qs.get(k,[""])[0] for k in ("autor","text","empresa","correos","url_perfil","region")}
                data["score"] = float(qs.get("score",["0"])[0])
                result = seguimiento_add(data)
                body = json.dumps(result, ensure_ascii=False).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*"); self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/seguimiento/update":
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query)
                text = qs.get("text",[""])[0]
                result = seguimiento_update(text, estado=qs.get("estado",[""])[0], notas=qs.get("notas",[""])[0])
                body = json.dumps(result, ensure_ascii=False).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*"); self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/seguimiento/remove":
            try:
                from urllib.parse import parse_qs
                text = parse_qs(parsed.query).get("text",[""])[0]
                result = seguimiento_remove(text)
                body = json.dumps(result, ensure_ascii=False).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*"); self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/feedback/vote":
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query)
                author = qs.get("author",[""])[0]
                text = qs.get("text",[""])[0]
                is_offer = qs.get("is_offer",["false"])[0].lower() == "true"
                is_structural = qs.get("is_structural",["false"])[0].lower() == "true"
                result = feedback_vote(author, text, is_offer, is_structural)
                body = json.dumps(result, ensure_ascii=False).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*"); self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        # ─── API: Rating ⭐ 1-5 estrellas ──────────────────────
        elif parsed.path == "/api/linkedin/ratings":
            try:
                ratings = get_ratings()
                body = json.dumps(ratings, ensure_ascii=False).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*"); self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        elif parsed.path == "/api/linkedin/rate":
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query)
                author = qs.get("author",[""])[0]
                text = qs.get("text",[""])[0]
                stars = int(qs.get("stars",["3"])[0])
                result = rate_post(author, text, stars)
                body = json.dumps(result, ensure_ascii=False).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*"); self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        # ─── API: Sugerencias inteligentes ───────────────────
        elif parsed.path == "/api/linkedin/suggestions":
            try:
                data = analyze_feedback()
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin","*"); self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
        else:
            super().do_GET()

    def log_message(self, fmt, *args):
        # Silenciar logs de archivos estáticos, solo mostrar /api
        try:
            if args and isinstance(args[0], str) and "/api/" in args[0]:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {fmt % args}")
        except Exception:
            pass


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    port = 9191
    os.chdir(DASHBOARD_DIR)
    httpd = HTTPServer(("", port), DashboardHandler)
    print(f"BOT Dashboard - Servidor activo")
    print(f"URL: http://localhost:{port}")
    print(f"API: http://localhost:{port}/api/status")
    print(f"Ctrl+C para detener")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
