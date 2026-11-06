# Corte vertical Semana 13 — Persistencia de RF-05 y RF-34

Repositorio: <https://github.com/jdrojasp11/proyecto_arq_sis_mascotas>

Proyecto: **Sistema de Apoyo a la Decisión para la Adopción Responsable de Mascotas mediante Inteligencia Artificial**.

## Contexto

Este repositorio documenta el **corte vertical de la semana 13** de la asignatura
**Arquitectura de Sistemas I**. El caso de estudio es un sistema de apoyo a la
**adopción responsable de mascotas**, desarrollado en la asignatura **Práctica de
Ingeniería**: los refugios registran las fichas de los animales que tienen en
adopción y los adoptantes consultan ese catálogo. En esta entrega no se
implementa la inteligencia artificial: se prepara la base de datos y la capa de
persistencia de dos funciones básicas.

- **RF-05** (requisito funcional 05): el refugio crea, edita y da de baja la ficha de una mascota.
- **RF-34** (requisito funcional 34): el adoptante consulta el catálogo de mascotas disponibles y lo filtra por especie, tamaño y edad.
- **Corte vertical**: porción pequeña del sistema que se construye de punta a punta; en esta semana llega hasta la base de datos, y la API y la interfaz se completan en las semanas 2 y 3.

Este entregable prepara la base de datos y la capa de persistencia de dos
requerimientos funcionales que comparten datos:

| Orden | RF | Resultado observable |
|---|---|---|
| 1 | **RF-05 — Gestión de la ficha de mascota** | El refugio crea, actualiza o da de baja una ficha; obtiene su id y su estado (`incompleta` o `disponible`). |
| 2 | **RF-34 — Consulta del catálogo de mascotas disponibles** | Cualquier usuario autorizado lista fichas disponibles, con filtros y paginación, de la más antigua a la más reciente. |

El detalle de priorización, RNF, ISO/IEC 25010:2023, modelo de datos y
resultados está en `plantilla/plantilla_13_1.pdf` (entrega formal compilada).
La fuente editable está en `plantilla/plantilla_13_1.tex` para compilar en Overleaf.

## 1. Requisitos

- **Python 3.12.10** (probado con esta versión; funciona con 3.10 o superior).
- **SQLite 3.49.1** (incluido en la biblioteca estándar de Python; no requiere servidor).
- Sin dependencias externas: solo `sqlite3`, `pathlib`, `json`, `statistics`, `time`.

> **Nota de stack.** El proyecto de segundo corte define PostgreSQL como base
> objetivo (ADR-03/ADR-10). Para esta verificación local se usa SQLite porque
> permite reproducir el corte sin instalar un servidor. El esquema mantiene
> claves foráneas, `CHECK`, `UNIQUE`, índices y triggers equivalentes; la
> migración a PostgreSQL se hará al conectar la API en la semana 2.

## 2. Estructura

```text
proyecto_arq_sis_mascotas/
├── persistencia/
│   ├── schema.sql                 # tablas, índices, CHECK, FK y triggers
│   ├── seed.sql                   # estado inicial conocido
│   ├── repositorio.py             # RepositorioMascotas (todo el SQL)
│   ├── prueba_persistencia.py     # 12 pruebas + medición de tiempos
│   └── demo_consulta.py           # consulta manual del catálogo y una ficha
├── evidencias/
│   ├── prueba.db                  # base recreada por la prueba
│   ├── salida_pruebas.txt         # resultado de las 12 pruebas
│   └── salida_consulta.txt        # salida de demo_consulta.py
└── plantilla/
    ├── plantilla_13_1.tex         # fuente LaTeX formal para Overleaf (pdfLaTeX)
    ├── plantilla_13_1.pdf         # entrega formal compilada (portada + 8 páginas)
    ├── plantilla_13_1_latex.pdf   # misma vista previa de la compilación
    └── plantilla_13_1.html        # versión HTML anterior (referencia)
```

## 3. Cómo reproducir la verificación

Desde PowerShell, en la raíz del repositorio:

```powershell
cd persistencia
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
python prueba_persistencia.py
```

La prueba **borra y recrea** `../evidencias/prueba.db` con `schema.sql` y
`seed.sql`, ejecuta los 12 casos y escribe `../evidencias/salida_pruebas.txt`.

Resultado esperado:

```text
RESUMEN: 12/12 pruebas pasaron
```

Consulta manual adicional:

```powershell
python demo_consulta.py
```

También se puede cambiar la ruta de la base sin tocar el código:

```powershell
$env:DB_PATH = "C:\ruta\alterna\prueba.db"
python prueba_persistencia.py
```

No hay credenciales ni secretos: la base local no usa usuario ni contraseña.
En PostgreSQL la cadena se tomará de una variable de entorno y no se versionará.

## 4. Estado inicial de los datos

La carga `seed.sql` deja un estado conocido (fecha de referencia 2026-11-04):

| Refugio | Estado | Localidad |
|---|---|---|
| 1 — Refugio Patitas | verificado | ENGATIVA |
| 2 — Fundación Colitas | pendiente | SUBA |

| Mascota | Refugio | Especie / tamaño | Estado | ¿Aparece en el catálogo? |
|---|---|---|---|---|
| 1 — Luna | 1 | perro / grande | disponible | Sí |
| 2 — Milo | 1 | gato / pequeño | disponible | Sí |
| 3 — Rocky | 1 | perro / mediano | disponible | Sí |
| 4 — Nube | 2 | gato / pequeño | disponible | **No**: refugio pendiente |
| 5 — Toby | 1 | perro / pequeño | incompleta | **No**: sin fotografía |
| 6 — Canela | 1 | perro / mediano | adoptada | **No**: ya adoptada |

Catálogo esperado, ordenado por `fecha_publicacion` ascendente:
**Luna (2026-10-01), Rocky (2026-10-03), Milo (2026-10-05)**.

## 5. Operaciones del repositorio

| Operación | Entrada | Salida | RF |
|---|---|---|---|
| `crear_ficha(refugio_id, ficha, fotografias)` | id del refugio, campos de RN-22 y 0–5 fotos JPG/PNG | id real de la ficha; estado `incompleta` o `disponible` | RF-05 |
| `obtener_por_id(mascota_id)` | id | ficha completa con refugio y fotos, o `None` | RF-05 |
| `actualizar_ficha(mascota_id, refugio_id, cambios, fotografias)` | id, refugio propietario, campos y fotos opcionales | ficha actualizada | RF-05 |
| `dar_de_baja(mascota_id, refugio_id)` | id y refugio propietario | baja lógica; deja de aparecer en el catálogo | RF-05 |
| `listar_catalogo(especie, tamano, edad_min, edad_max, pagina, por_pagina)` | filtros opcionales y paginación | `total`, `pagina`, `porPagina`, `mascotas` | RF-34 |

El repositorio concentra el SQL. La API y los servicios de la semana 2 no
deben construir consultas; solo llaman estos métodos y traducen las
excepciones (`ERR-003`, `ERR-004`, `ERR-006`, `ERR-008`, `ERR-009`, `ERR-011`).

## 6. Reglas de integridad implementadas

1. **FK** `mascota.refugio_id → refugio.id` y `fotografia.mascota_id → mascota.id`
   (con `ON DELETE CASCADE` en fotos).
2. **Dominios cerrados** con `CHECK`: especie, tamaño, energía, experiencia,
   estado, edad entre 0 y 300 meses, booleanos 0/1.
3. **Máximo 5 fotos** por ficha: validación en el repositorio y trigger
   `trg_max_fotos`.
4. **Ficha disponible exige al menos una foto**: trigger
   `trg_disponible_con_foto` (RN-22).
5. **Solo un refugio verificado publica**: trigger
   `trg_disponible_refugio_verificado` (RN-03).
6. **Orden de fotos único** por ficha: `UNIQUE (mascota_id, orden)`.
7. **Transacción**: crear/actualizar usan `BEGIN IMMEDIATE`; si falla una
   inserción, se hace `ROLLBACK` y no queda una ficha a medias.
8. **Catálogo sin datos personales**: la consulta solo devuelve datos de la
   ficha y del refugio (nombre y localidad), no del adoptante (RN-24/RNF-04).

## 7. Pruebas ejecutadas (evidencia real)

Salida completa en `../evidencias/salida_pruebas.txt`:

| # | Prueba | Resultado |
|---|---|---|
| 1 | Crear ficha en refugio verificado y leerla desde una conexión nueva | PASA — id 7, estado `disponible`, 2 fotos |
| 2 | Rechazar ficha de refugio no verificado | PASA — `ERR-009`, 0 filas nuevas |
| 3 | Rechazar datos inválidos | PASA — `ERR-004`, 0 filas nuevas |
| 4 | Consultar id inexistente | PASA — `None` |
| 5 | Violar la FK de refugio | PASA — `FOREIGN KEY constraint failed` |
| 6 | Ficha sin fotos queda `incompleta` y fuera del catálogo | PASA — id 8 |
| 7 | Catálogo: solo disponibles/verificados, orden, filtros y paginación | PASA — total 4, orden `[1,3,2,7]` |
| 8 | Actualizar ficha incompleta, publicarla y darla de baja | PASA — `incompleta → disponible → baja` |
| 9 | Más de 5 fotos | PASA — rechazo del repositorio y del trigger |
| 10 | Triggers de publicación (refugio pendiente / sin foto) | PASA — ambos rechazos |
| 11 | El catálogo y la ficha no exponen datos personales | PASA — 0 campos personales |
| 12 | 20 consultas consecutivas al catálogo | PASA — promedio 0,53 ms; máx. 0,66 ms |

**Línea base de tiempos:** 8 fichas en la base de prueba. El umbral RNF-05
(p95 ≤ 1 s con 500 fichas y 50 usuarios concurrentes) se verificará con la API
en la semana 2 y con la integración en la semana 3; esta medición es solo la
línea base local, no la prueba de carga.

## 8. Qué está probado y qué queda pendiente

**Probado en semana 1**

- Esquema reproducible y carga inicial conocida.
- Crear, leer, actualizar y dar de baja una ficha.
- Catálogo con filtros, paginación y orden.
- Integridad referencial, dominios, máximo de fotos, publicación solo de
  refugios verificados y fichas completas.
- Identificador inexistente y rechazo de datos inválidos.
- Lectura desde una conexión nueva (persistencia real, no memoria).

**Pendiente para semanas 2 y 3**

- API REST (`POST/PUT/DELETE /mascotas`, `GET /mascotas`) y autenticación por rol.
- Almacenamiento binario de fotos en objeto/archivo (ahora se guarda la ruta).
- Pruebas de servicios con un doble del repositorio (RNF-08).
- Prueba de carga con 500 fichas y 50 usuarios concurrentes (RNF-05).
- Migración y verificación en PostgreSQL (ADR-03/ADR-10).
- Interfaz de ficha y catálogo (semana 3).
- Rechazo automático de solicitudes pendientes al dar de baja (RN-15), que
  depende del módulo de solicitudes, fuera de este corte.

## 9. Trazabilidad rápida

| Elemento | Dónde se evidencia |
|---|---|
| RF-05 | `repositorio.py` (crear/leer/actualizar/baja), pruebas 1, 2, 3, 6, 8, 9, 10 |
| RF-34 | `repositorio.py` (`listar_catalogo`), pruebas 4, 7, 11, 12 |
| RNF-05 | prueba 12 (línea base) y pendiente de carga |
| RNF-07 | pendiente de prueba de escalabilidad |
| RNF-08 | contrato del repositorio y pruebas directas; doble pendiente |
| RNF-10 | pruebas 2, 3, 5, 6, 9, 10 |
| ISO/IEC 25010:2023 | matriz de la plantilla, con característica y subcaracterística |
| Plantilla 13.1 | `plantilla/plantilla_13_1.pdf` y `plantilla/plantilla_13_1.tex` |

## 10. Versión LaTeX

`plantilla/plantilla_13_1.tex` reproduce el contenido con un estilo formal:
portada independiente, tipografía serif NewTX de 11 pt, texto en blanco y negro,
tablas con reglas de **booktabs** (sin líneas verticales ni colores) y encabezado
en versalitas. Incluye una sección inicial de contexto que explica el proyecto,
el corte vertical y el significado de RF, RNF y RN para un lector que no conoce
el sistema. El documento tiene una portada sin numerar y ocho páginas numeradas.
Se compila en Overleaf con **pdfLaTeX** y no requiere archivos adicionales ni
bibliografía.

1. Crear un proyecto vacío en Overleaf y subir `plantilla_13_1.tex`.
2. Verificar que el compilador sea **pdfLaTeX** (el archivo ya incluye
   `% !TEX program = pdflatex`).
3. Compilar dos veces para que `lastpage` resuelva el total de páginas.
4. Reemplazar «Equipo de trabajo (completar nombres)» por los nombres reales
   antes de la entrega.

La vista previa compilada está en `plantilla/plantilla_13_1.pdf` y
`plantilla/plantilla_13_1_latex.pdf`. Verificación: pdfLaTeX de TeX Live, 0
errores, 0 líneas desbordadas y 9 páginas físicas (portada + 8 numeradas).
