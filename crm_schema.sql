
CREATE TABLE IF NOT EXISTS contactos_crm (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    uid             TEXT UNIQUE,              -- mismo uid de estructurales
    nombre          TEXT NOT NULL,
    email           TEXT DEFAULT '',
    empresa         TEXT DEFAULT '',
    rol             TEXT DEFAULT '',
    region          TEXT DEFAULT '',
    score           REAL DEFAULT 0,
    fuente          TEXT DEFAULT 'linkedin',  -- linkedin, manual, mp
    estado          TEXT DEFAULT 'pendiente', -- pendiente, contactado, en_seguimiento, responded, cerrado
    fecha_contacto  TEXT,
    metodo          TEXT DEFAULT '',           -- email, linkedin, telefono
    notas           TEXT DEFAULT '',
    ultimo_seguimiento TEXT,
    num_seguimientos INTEGER DEFAULT 0,
    creado_en       TEXT DEFAULT (datetime('now','-4 hours')),
    actualizado_en  TEXT DEFAULT (datetime('now','-4 hours'))
);

CREATE TABLE IF NOT EXISTS interacciones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    contacto_uid    TEXT NOT NULL,
    tipo            TEXT NOT NULL,            -- email_enviado, email_recibido, linkedin_msg, llamada, nota
    contenido       TEXT DEFAULT '',
    fecha           TEXT DEFAULT (datetime('now','-4 hours')),
    estado          TEXT DEFAULT '',           -- pendiente_respuesta, responded, cerrado
    metadata        TEXT DEFAULT '{}',
    FOREIGN KEY (contacto_uid) REFERENCES contactos_crm(uid)
);

CREATE INDEX IF NOT EXISTS idx_crm_uid ON contactos_crm(uid);
CREATE INDEX IF NOT EXISTS idx_crm_estado ON contactos_crm(estado);
CREATE INDEX IF NOT EXISTS idx_crm_region ON contactos_crm(region);
CREATE INDEX IF NOT EXISTS idx_interacciones_contacto ON interacciones(contacto_uid);
