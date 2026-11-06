-- Carga de prueba con estado inicial conocido (semana 13).
-- Fecha de referencia del corte: 2026-11-04.
-- El catálogo debe devolver 3 fichas: Luna (1), Rocky (3) y Milo (2),
-- en ese orden por fecha_publicacion ascendente.

PRAGMA foreign_keys = ON;

INSERT INTO refugio (id, nombre, localidad, estado_verificacion) VALUES
    (1, 'Refugio Patitas',      'ENGATIVA', 'verificado'),
    (2, 'Fundación Colitas',    'SUBA',     'pendiente');

INSERT INTO mascota
    (id, refugio_id, nombre, raza, especie, edad_meses, tamano, nivel_energia,
     experiencia_requerida, apta_con_menores, apta_con_mascotas,
     historial_salud, historial_comportamiento, estado, fecha_publicacion)
VALUES
    (1, 1, 'Luna',  'Mestiza', 'perro', 30, 'grande',  'alta',  'basica',  1, 1,
     'Vacunas al día', 'Sociable', 'disponible', '2026-10-01'),
    (2, 1, 'Milo',  'Criollo', 'gato',  18, 'pequeno', 'media', 'ninguna', 1, 1,
     'Sin novedades', 'Tranquilo', 'disponible', '2026-10-05'),
    (3, 1, 'Rocky', 'Mestizo', 'perro', 60, 'mediano', 'alta',  'amplia',  0, 0,
     'Control cardíaco', 'Requiere manejo experimentado', 'disponible', '2026-10-03'),
    -- No debe aparecer: su refugio está pendiente de verificación.
    (4, 2, 'Nube',  'Criollo', 'gato',   8, 'pequeno', 'baja',  'ninguna', 1, 1,
     NULL, NULL, 'disponible', '2026-10-02'),
    -- No debe aparecer: ficha incompleta (sin fotografía).
    (5, 1, 'Toby',  'Mestizo', 'perro', 12, 'pequeno', 'media', 'ninguna', 1, 1,
     NULL, NULL, 'incompleta', '2026-10-04'),
    -- No debe aparecer: ya fue adoptada.
    (6, 1, 'Canela', 'Mestiza', 'perro', 48, 'mediano', 'media', 'basica', 1, 1,
     NULL, NULL, 'adoptada', '2026-09-20');

INSERT INTO fotografia (mascota_id, archivo, orden) VALUES
    (1, 'luna_01.jpg', 1),
    (1, 'luna_02.jpg', 2),
    (2, 'milo_01.jpg', 1),
    (3, 'rocky_01.jpg', 1),
    (4, 'nube_01.jpg', 1),
    (6, 'canela_01.jpg', 1);
