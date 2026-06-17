#!/usr/bin/env python3
"""
unified_db.py — Base de Datos Unificada para Dashboard-BOTS
============================================================
Concentra: contactos, organismos, licitaciones, bots, emails, tracking.

Todas las tablas tienen UNIQUE constraints para evitar duplicados.
Usa sólo la biblioteca estándar (sqlite3, datetime, json).
"""
import sqlite3, json, os, datetime, hashlib, re
from pathlib import Path

DB_DIR = Path(r"C:\Users\Usuario\Desktop\Programación\Dashboard-BOTS")
DB_PATH = DB_DIR / "dashboard.db"

# ─── Esquema ──────────────────────────────────────────────────────────────────

SCHEMA = """
-- ============================================================
-- 1. CONTACTOS (Prospectos, leads, clientes)
-- ============================================================
CREATE TABLE IF NOT EXISTS contactos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_externo  TEXT UNIQUE,       -- CodigoExterno de Mercado Público si aplica
    nombre          TEXT NOT NULL,
    email           TEXT,
    telefono        TEXT,
    cargo           TEXT,              -- Jefe de Adquisiciones, Inspector Técnico, etc.
    organismo_id    INTEGER REFERENCES organismos(id),
    organismo_nombre TEXT,             -- Denormalizado para búsqueda rápida
    fuente          TEXT DEFAULT 'manual',  -- 'mercadopublico', 'compra_agil', 'linkedin', 'manual'
    nota            INTEGER DEFAULT 0, -- Rating de interés 1-10
    estado_seguimiento TEXT DEFAULT '', -- 'interesante', 'en_estudio', 'postulada'
    tags            TEXT DEFAULT '',   -- JSON array: ["construccion","ingenieria"]
    creado_en       TIMESTAMP DEFAULT (datetime('now', '-4 hours')),
    actualizado_en  TIMESTAMP DEFAULT (datetime('now', '-4 hours')),
    metadata        TEXT DEFAULT '{}'  -- JSON extra
);

-- ============================================================
-- 2. ORGANISMOS (Entidades públicas de ChileCompra)
-- ============================================================
CREATE TABLE IF NOT EXISTS organismos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo          TEXT UNIQUE,       -- Código del organismo en Mercado Público
    nombre          TEXT NOT NULL,
    rut             TEXT,
    region          TEXT,
    comuna          TEXT,
    tipo            TEXT,              -- Municipalidad, Servicio Público, etc.
    total_licitaciones INTEGER DEFAULT 0,
    ultima_compra   TIMESTAMP,
    monto_total     REAL DEFAULT 0,
    creado_en       TIMESTAMP DEFAULT (datetime('now', '-4 hours')),
    metadata        TEXT DEFAULT '{}'
);

-- ============================================================
-- 3. LICITACIONES (Histórico de Mercado Público)
-- ============================================================
CREATE TABLE IF NOT EXISTS licitaciones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_externo  TEXT UNIQUE NOT NULL,  -- ej: "1234-56-LP24"
    nombre          TEXT NOT NULL,
    descripcion     TEXT DEFAULT '',
    tipo            TEXT,                  -- LP, LE, L1, CO, etc.
    codigo_estado   INTEGER,
    estado_nombre   TEXT,
    organismo_id    INTEGER REFERENCES organismos(id),
    organismo_nombre TEXT,
    fecha_publicacion TIMESTAMP,
    fecha_cierre    TIMESTAMP,
    moneda          TEXT DEFAULT 'CLP',
    monto_estimado  REAL,
    monto_estimado_clp REAL,           -- Normalizado a CLP
    region          TEXT,
    comuna          TEXT,
    categorias      TEXT DEFAULT '[]', -- JSON: ["construccion","ingenieria"]
    interes         INTEGER DEFAULT 0, -- 0=neutro, 1=interesante, -1=descartado
    rating          INTEGER DEFAULT 0, -- 1-10 desde favoritos
    url             TEXT,
    creado_en       TIMESTAMP DEFAULT (datetime('now', '-4 hours'))
);

-- ============================================================
-- 4. COMPRAS ÁGILES
-- ============================================================
CREATE TABLE IF NOT EXISTS compras_agiles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo          TEXT UNIQUE NOT NULL,  -- ej: "1621-142-COT26"
    nombre          TEXT NOT NULL,
    estado          TEXT,
    organismo       TEXT,
    organismo_rut   TEXT,
    region          TEXT,
    fecha_publicacion TIMESTAMP,
    fecha_cierre    TIMESTAMP,
    moneda          TEXT DEFAULT 'CLP',
    monto_disponible REAL,
    categorias      TEXT DEFAULT '[]',
    interes         INTEGER DEFAULT 0,
    rating          INTEGER DEFAULT 0,
    creado_en       TIMESTAMP DEFAULT (datetime('now', '-4 hours'))
);

-- ============================================================
-- 5. BOT_HISTORY (Snapshot periódico del estado de los bots)
-- ============================================================
CREATE TABLE IF NOT EXISTS bot_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id          TEXT NOT NULL,      -- 'linkedin', 'mercadopublico', 'trading'
    timestamp       TIMESTAMP DEFAULT (datetime('now', '-4 hours')),
    status          TEXT,               -- 'ok', 'warn', 'error', 'unknown'
    status_text     TEXT,
    extra_data      TEXT DEFAULT '{}',  -- JSON con datos específicos
    UNIQUE(bot_id, timestamp)
);

-- ============================================================
-- 6. EMAIL_CAMPAIGNS (Campañas de correo enviadas)
-- ============================================================
CREATE TABLE IF NOT EXISTS email_campaigns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL,
    asunto          TEXT,
    cuerpo          TEXT,
    destinatarios   INTEGER DEFAULT 0,
    enviados        INTEGER DEFAULT 0,
    abiertos        INTEGER DEFAULT 0,
    clics           INTEGER DEFAULT 0,
    rebotados       INTEGER DEFAULT 0,
    creado_en       TIMESTAMP DEFAULT (datetime('now', '-4 hours')),
    metadata        TEXT DEFAULT '{}'
);

-- ============================================================
-- 7. EMAIL_EVENTS (Tracking individual: opens, clicks, bounces)
-- ============================================================
CREATE TABLE IF NOT EXISTS email_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id     INTEGER REFERENCES email_campaigns(id),
    contacto_id     INTEGER REFERENCES contactos(id),
    email           TEXT,
    tipo            TEXT NOT NULL,      -- 'sent', 'open', 'click', 'bounce', 'reply'
    timestamp       TIMESTAMP DEFAULT (datetime('now', '-4 hours')),
    metadata        TEXT DEFAULT '{}',  -- URL clickeada, error de bounce, etc.
    UNIQUE(campaign_id, contacto_id, tipo)
);

-- ============================================================
-- 8. SEGUIMIENTO_LOGS (Registro de cambios en estados)
-- ============================================================
CREATE TABLE IF NOT EXISTS seguimiento_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_externo  TEXT NOT NULL,
    tipo            TEXT NOT NULL,      -- 'licitacion', 'compra_agil', 'contacto'
    estado_anterior TEXT,
    estado_nuevo    TEXT,
    changed_by      TEXT DEFAULT 'hermes', -- 'web', 'telegram', 'hermes'
    timestamp       TIMESTAMP DEFAULT (datetime('now', '-4 hours'))
);

-- ============================================================
-- 9. CONFIG (Configuración clave-valor)
-- ============================================================
CREATE TABLE IF NOT EXISTS config (
    key             TEXT PRIMARY KEY,
    value           TEXT,
    updated_at      TIMESTAMP DEFAULT (datetime('now', '-4 hours'))
);

-- Índices para búsqueda rápida
CREATE INDEX IF NOT EXISTS idx_contactos_email ON contactos(email);
CREATE INDEX IF NOT EXISTS idx_contactos_organismo ON contactos(organismo_id);
CREATE INDEX IF NOT EXISTS idx_licitaciones_organismo ON licitaciones(organismo_id);
CREATE INDEX IF NOT EXISTS idx_licitaciones_estado ON licitaciones(codigo_estado);
CREATE INDEX IF NOT EXISTS idx_licitaciones_fecha ON licitaciones(fecha_cierre);
CREATE INDEX IF NOT EXISTS idx_compras_agiles_fecha ON compras_agiles(fecha_cierre);
CREATE INDEX IF NOT EXISTS idx_bot_history_bot ON bot_history(bot_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_email_events_campaign ON email_events(campaign_id);
CREATE INDEX IF NOT EXISTS idx_seguimiento_logs_codigo ON seguimiento_logs(codigo_externo);
"""

# ─── Clase principal ──────────────────────────────────────────────────────────

class UnifiedDB:
    def __init__(self, db_path=None):
        self.db_path = Path(db_path or DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self):
        for statement in SCHEMA.split(";"):
            s = statement.strip()
            if s:
                try:
                    self.conn.execute(s)
                except sqlite3.OperationalError as e:
                    print(f"⚠️ Schema warning: {e}")
        self.conn.commit()

    def _row_to_dict(self, row):
        if row is None:
            return None
        return dict(row)

    def _rows_to_list(self, rows):
        return [dict(r) for r in rows]

    # ─── Contactos ────────────────────────────────────────────────────────

    def upsert_contacto(self, codigo_externo, nombre, **kwargs):
        """Inserta o actualiza un contacto (no duplica por codigo_externo)"""
        data = {"codigo_externo": codigo_externo, "nombre": nombre, **kwargs}
        data["actualizado_en"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        existing = self.conn.execute(
            "SELECT id FROM contactos WHERE codigo_externo = ?", (codigo_externo,)
        ).fetchone()

        if existing:
            # Build UPDATE: exclude codigo_externo from SET, add actualizado_en
            update_fields = {k: v for k, v in kwargs.items() if k != "codigo_externo"}
            update_fields["actualizado_en"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sets = ", ".join(f"{k} = ?" for k in update_fields)
            vals = list(update_fields.values()) + [codigo_externo]
            self.conn.execute(
                f"UPDATE contactos SET {sets} WHERE codigo_externo = ?", vals
            )
        else:
            cols = ", ".join(data.keys())
            placeholders = ", ".join("?" for _ in data)
            self.conn.execute(
                f"INSERT INTO contactos ({cols}) VALUES ({placeholders})",
                list(data.values())
            )
        self.conn.commit()

    def get_contactos(self, limit=50, offset=0, search=None, estado=None):
        query = "SELECT * FROM contactos"
        params = []
        conditions = []
        if search:
            conditions.append("(nombre LIKE ? OR email LIKE ? OR organismo_nombre LIKE ?)")
            params.extend([f"%{search}%"] * 3)
        if estado:
            conditions.append("estado_seguimiento = ?")
            params.append(estado)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY nota DESC, actualizado_en DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        return self._rows_to_list(self.conn.execute(query, params).fetchall())

    def count_contactos(self):
        return self.conn.execute("SELECT COUNT(*) as c FROM contactos").fetchone()["c"]

    # ─── Organismos ───────────────────────────────────────────────────────

    def upsert_organismo(self, codigo, nombre, **kwargs):
        existing = self.conn.execute(
            "SELECT id FROM organismos WHERE codigo = ?", (codigo,)
        ).fetchone()
        if existing:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            vals = [kwargs[k] for k in kwargs] + [codigo]
            self.conn.execute(f"UPDATE organismos SET {sets} WHERE codigo = ?", vals)
            return existing["id"]
        else:
            data = {"codigo": codigo, "nombre": nombre, **kwargs}
            cols = ", ".join(data.keys())
            ph = ", ".join("?" for _ in data)
            self.conn.execute(f"INSERT INTO organismos ({cols}) VALUES ({ph})", list(data.values()))
            self.conn.commit()
            return self.conn.execute("SELECT id FROM organismos WHERE codigo = ?", (codigo,)).fetchone()["id"]

    def get_organismos_mas_activos(self, limit=20):
        return self._rows_to_list(self.conn.execute(
            "SELECT * FROM organismos ORDER BY total_licitaciones DESC LIMIT ?", (limit,)
        ).fetchall())

    # ─── Licitaciones ─────────────────────────────────────────────────────

    def upsert_licitacion(self, codigo_externo, nombre, **kwargs):
        existing = self.conn.execute(
            "SELECT id FROM licitaciones WHERE codigo_externo = ?", (codigo_externo,)
        ).fetchone()
        if existing:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            vals = [kwargs[k] for k in kwargs] + [codigo_externo]
            self.conn.execute(f"UPDATE licitaciones SET {sets} WHERE codigo_externo = ?", vals)
        else:
            data = {"codigo_externo": codigo_externo, "nombre": nombre, **kwargs}
            cols = ", ".join(data.keys())
            ph = ", ".join("?" for _ in data)
            self.conn.execute(f"INSERT INTO licitaciones ({cols}) VALUES ({ph})", list(data.values()))
        self.conn.commit()

    def get_licitaciones_interesantes(self, limit=30):
        return self._rows_to_list(self.conn.execute(
            "SELECT * FROM licitaciones WHERE interes = 1 OR rating >= 5 ORDER BY fecha_cierre ASC LIMIT ?",
            (limit,)
        ).fetchall())

    def count_licitaciones(self):
        return self.conn.execute("SELECT COUNT(*) as c FROM licitaciones").fetchone()["c"]

    # ─── Compras Ágiles ───────────────────────────────────────────────────

    def upsert_compra_agil(self, codigo, nombre, **kwargs):
        existing = self.conn.execute(
            "SELECT id FROM compras_agiles WHERE codigo = ?", (codigo,)
        ).fetchone()
        if existing:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            vals = [kwargs[k] for k in kwargs] + [codigo]
            self.conn.execute(f"UPDATE compras_agiles SET {sets} WHERE codigo = ?", vals)
        else:
            data = {"codigo": codigo, "nombre": nombre, **kwargs}
            cols = ", ".join(data.keys())
            ph = ", ".join("?" for _ in data)
            self.conn.execute(f"INSERT INTO compras_agiles ({cols}) VALUES ({ph})", list(data.values()))
        self.conn.commit()

    # ─── Bot History ──────────────────────────────────────────────────────

    def save_bot_snapshot(self, bot_id, status, status_text, extra_data=None):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self.conn.execute(
                "INSERT OR REPLACE INTO bot_history (bot_id, timestamp, status, status_text, extra_data) VALUES (?, ?, ?, ?, ?)",
                (bot_id, ts, status, status_text, json.dumps(extra_data or {}))
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            # Misma marca de tiempo (milisegundos diferentes) - update
            self.conn.execute(
                "UPDATE bot_history SET status=?, status_text=?, extra_data=? WHERE bot_id=? AND timestamp=?",
                (status, status_text, json.dumps(extra_data or {}), bot_id, ts)
            )
            self.conn.commit()

    def get_bot_history(self, bot_id, limit=50):
        return self._rows_to_list(self.conn.execute(
            "SELECT * FROM bot_history WHERE bot_id = ? ORDER BY timestamp DESC LIMIT ?",
            (bot_id, limit)
        ).fetchall())

    # ─── Email Campaigns ──────────────────────────────────────────────────

    def create_campaign(self, nombre, asunto, cuerpo=""):
        self.conn.execute(
            "INSERT INTO email_campaigns (nombre, asunto, cuerpo) VALUES (?, ?, ?)",
            (nombre, asunto, cuerpo)
        )
        self.conn.commit()
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def log_email_event(self, campaign_id, contacto_id, email, tipo, metadata=None):
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO email_events (campaign_id, contacto_id, email, tipo, metadata) VALUES (?, ?, ?, ?, ?)",
                (campaign_id, contacto_id, email, tipo, json.dumps(metadata or {}))
            )
            self.conn.commit()
        except Exception:
            pass

    # ─── Estadísticas Globales ────────────────────────────────────────────

    def get_global_stats(self):
        stats = {}
        for table in ["contactos", "organismos", "licitaciones", "compras_agiles", "email_campaigns", "bot_history"]:
            r = self.conn.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()
            stats[table] = r["c"] if r else 0
        # Contactos con seguimiento
        stats["en_seguimiento"] = self.conn.execute(
            "SELECT COUNT(*) as c FROM contactos WHERE estado_seguimiento != ''"
        ).fetchone()["c"]
        # Licitaciones activas (con rating)
        stats["licitaciones_activas"] = self.conn.execute(
            "SELECT COUNT(*) as c FROM licitaciones WHERE codigo_estado = 5"
        ).fetchone()["c"]
        # Última actualización
        stats["ultima_actualizacion"] = datetime.datetime.now().strftime("%H:%M:%S")
        # Tamaño de la base
        try:
            stats["db_size_kb"] = round(os.path.getsize(self.db_path) / 1024, 1)
        except:
            stats["db_size_kb"] = 0
        return stats

    # ─── Búsqueda Unificada ────────────────────────────────────────────────

    def search(self, query, limit=20):
        q = f"%{query}%"
        results = []

        # En contactos
        for r in self.conn.execute(
            "SELECT id, nombre, 'contacto' as tipo, email as subtitulo, "
            "estado_seguimiento as estado, nota FROM contactos "
            "WHERE nombre LIKE ? OR email LIKE ? OR organismo_nombre LIKE ? LIMIT ?",
            (q, q, q, limit)
        ).fetchall():
            results.append(dict(r))

        # En licitaciones
        for r in self.conn.execute(
            "SELECT id, nombre, 'licitacion' as tipo, codigo_externo as subtitulo, "
            "COALESCE(estado_nombre, '') as estado, rating as nota FROM licitaciones "
            "WHERE nombre LIKE ? OR codigo_externo LIKE ? OR organismo_nombre LIKE ? LIMIT ?",
            (q, q, q, limit)
        ).fetchall():
            results.append(dict(r))

        # En organismos
        for r in self.conn.execute(
            "SELECT id, nombre, 'organismo' as tipo, "
            "COALESCE(region, '') as subtitulo, '' as estado, 0 as nota FROM organismos "
            "WHERE nombre LIKE ? OR codigo LIKE ? LIMIT ?",
            (q, q, limit)
        ).fetchall():
            results.append(dict(r))

        results.sort(key=lambda x: -x.get("nota", 0))
        return results[:limit]

    # ─── Limpieza ─────────────────────────────────────────────────────────

    def close(self):
        self.conn.close()


# ─── Función singleton ────────────────────────────────────────────────────────

_db_instance = None

def get_db():
    global _db_instance
    if _db_instance is None:
        _db_instance = UnifiedDB()
    return _db_instance


# ─── Test rápido ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    db = get_db()
    stats = db.get_global_stats()
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print(f"DB en: {db.db_path}")
    print("✅ Base de datos lista")
