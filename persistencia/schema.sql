-- Esquema mínimo del corte vertical: RF-05 (gestión de ficha de mascota)
-- y RF-34 (consulta del catálogo de mascotas disponibles).
-- Motor: SQLite 3. Base reproducible desde cero con schema.sql + seed.sql.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS fotografia;
DROP TABLE IF EXISTS mascota;
DROP TABLE IF EXISTS refugio;

CREATE TABLE refugio (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre              TEXT    NOT NULL CHECK (length(nombre) BETWEEN 3 AND 120),
    localidad           TEXT    NOT NULL,
    estado_verificacion TEXT    NOT NULL DEFAULT 'pendiente'
        CHECK (estado_verificacion IN ('pendiente', 'verificado', 'rechazado'))
);

CREATE TABLE mascota (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    refugio_id               INTEGER NOT NULL REFERENCES refugio(id) ON DELETE RESTRICT,
    nombre                   TEXT    NOT NULL CHECK (length(nombre) BETWEEN 1 AND 60),
    raza                     TEXT,
    especie                  TEXT    NOT NULL CHECK (especie IN ('perro', 'gato')),
    edad_meses               INTEGER NOT NULL CHECK (edad_meses BETWEEN 0 AND 300),
    tamano                   TEXT    NOT NULL CHECK (tamano IN ('pequeno', 'mediano', 'grande')),
    nivel_energia            TEXT    NOT NULL CHECK (nivel_energia IN ('baja', 'media', 'alta')),
    experiencia_requerida    TEXT    NOT NULL CHECK (experiencia_requerida IN ('ninguna', 'basica', 'amplia')),
    apta_con_menores         INTEGER NOT NULL CHECK (apta_con_menores IN (0, 1)),
    apta_con_mascotas        INTEGER NOT NULL CHECK (apta_con_mascotas IN (0, 1)),
    historial_salud          TEXT,
    historial_comportamiento TEXT,
    estado                   TEXT    NOT NULL DEFAULT 'incompleta'
        CHECK (estado IN ('incompleta', 'disponible', 'adoptada', 'baja')),
    fecha_publicacion        TEXT    NOT NULL,
    creado_en                TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Índice que soporta el orden y el filtro principal del catálogo (RF-34).
CREATE INDEX idx_mascota_catalogo
    ON mascota (estado, fecha_publicacion, id);

-- Índice de apoyo para los filtros opcionales del catálogo (RF-34).
CREATE INDEX idx_mascota_filtros
    ON mascota (especie, tamano, edad_meses);

CREATE TABLE fotografia (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    mascota_id INTEGER NOT NULL REFERENCES mascota(id) ON DELETE CASCADE,
    archivo    TEXT    NOT NULL,
    orden      INTEGER NOT NULL CHECK (orden BETWEEN 1 AND 5),
    UNIQUE (mascota_id, orden)
);

-- Regla de integridad: máximo 5 fotografías por ficha (RN-22).
CREATE TRIGGER trg_max_fotos
BEFORE INSERT ON fotografia
WHEN (SELECT COUNT(*) FROM fotografia WHERE mascota_id = NEW.mascota_id) >= 5
BEGIN
    SELECT RAISE(ABORT, 'MAX_FOTOS: una ficha admite maximo 5 fotografias');
END;

-- Regla de integridad: solo una ficha con al menos una fotografía puede
-- pasar a estado disponible (RN-22).
CREATE TRIGGER trg_disponible_con_foto
BEFORE UPDATE OF estado ON mascota
WHEN NEW.estado = 'disponible'
     AND (SELECT COUNT(*) FROM fotografia WHERE mascota_id = NEW.id) = 0
BEGIN
    SELECT RAISE(ABORT, 'FICHA_INCOMPLETA: se requiere al menos una fotografia');
END;

-- Regla de integridad: solo un refugio verificado puede publicar (RN-03).
CREATE TRIGGER trg_disponible_refugio_verificado
BEFORE UPDATE OF estado ON mascota
WHEN NEW.estado = 'disponible'
     AND (SELECT estado_verificacion FROM refugio WHERE id = NEW.refugio_id) <> 'verificado'
BEGIN
    SELECT RAISE(ABORT, 'REFUGIO_NO_VERIFICADO: el refugio debe estar verificado');
END;
