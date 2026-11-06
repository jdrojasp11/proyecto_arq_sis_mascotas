# -*- coding: utf-8 -*-
"""Prueba real de persistencia del corte vertical (semana 13).

Ejecuta:  python prueba_persistencia.py
Genera:   ../evidencias/prueba.db  y  ../evidencias/salida_pruebas.txt
"""

from __future__ import annotations

import os
import sqlite3
import statistics
import sys
import time
from contextlib import closing
from pathlib import Path

from repositorio import (
    DatosInvalidos,
    ErrorPersistencia,
    RefugioNoVerificado,
    RepositorioMascotas,
)

BASE = Path(__file__).resolve().parent
EVIDENCIAS = BASE.parent / "evidencias"
RUTA_DB = Path(os.environ.get("DB_PATH", EVIDENCIAS / "prueba.db"))
SCHEMA = BASE / "schema.sql"
SEED = BASE / "seed.sql"

resultados: list[tuple[str, bool, str]] = []


def ejecutar_sql(ruta_db: Path, ruta_sql: Path) -> None:
    with closing(sqlite3.connect(ruta_db)) as conexion:
        conexion.executescript(ruta_sql.read_text(encoding="utf-8"))
        conexion.commit()


def recrear_base() -> None:
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    if RUTA_DB.exists():
        RUTA_DB.unlink()
    ejecutar_sql(RUTA_DB, SCHEMA)
    ejecutar_sql(RUTA_DB, SEED)


def prueba(nombre: str):
    def decorador(funcion):
        def envoltura(*args, **kwargs):
            try:
                detalle = funcion(*args, **kwargs)
                resultados.append((nombre, True, detalle or ""))
                print(f"[PASA] {nombre}")
                if detalle:
                    print(f"       {detalle}")
            except Exception as exc:  # noqa: BLE001 - reporte de prueba
                resultados.append((nombre, False, f"{type(exc).__name__}: {exc}"))
                print(f"[FALLA] {nombre}")
                print(f"        {type(exc).__name__}: {exc}")

        return envoltura

    return decorador


def ficha_base(nombre: str = "Nala", **cambios) -> dict:
    ficha = {
        "nombre": nombre,
        "especie": "perro",
        "edad_meses": 24,
        "tamano": "mediano",
        "nivel_energia": "media",
        "experiencia_requerida": "basica",
        "apta_con_menores": True,
        "apta_con_mascotas": True,
        "historial_salud": "Vacunas al día",
        "historial_comportamiento": "Sociable",
        "fecha_publicacion": "2026-10-10",
    }
    ficha.update(cambios)
    return ficha


@prueba("1. Crear una ficha en un refugio verificado y recuperarla desde una conexión nueva")
def test_crear_y_leer() -> str:
    repo = RepositorioMascotas(str(RUTA_DB))
    nuevo_id = repo.crear_ficha(1, ficha_base("Nala"), ["nala_01.jpg", "nala_02.jpg"])
    assert nuevo_id == 7, f"id esperado 7, obtenido {nuevo_id}"

    # Conexión nueva: simula otro proceso o una petición posterior de la API.
    repo_nuevo = RepositorioMascotas(str(RUTA_DB))
    ficha = repo_nuevo.obtener_por_id(nuevo_id)
    assert ficha is not None
    assert ficha["nombre"] == "Nala"
    assert ficha["estado"] == "disponible"
    assert len(ficha["fotografias"]) == 2
    assert ficha["refugio_nombre"] == "Refugio Patitas"
    return (
        f"id={nuevo_id}, estado={ficha['estado']}, "
        f"fotos={len(ficha['fotografias'])}, refugio={ficha['refugio_nombre']}"
    )


@prueba("2. Rechazar la creación de una ficha si el refugio no está verificado")
def test_refugio_pendiente() -> str:
    repo = RepositorioMascotas(str(RUTA_DB))
    antes = repo.contar_fichas()
    try:
        repo.crear_ficha(2, ficha_base("No permitida"), ["x.jpg"])
    except RefugioNoVerificado as exc:
        assert repo.contar_fichas() == antes, "no debe persistirse ninguna fila"
        return f"{exc.codigo}: {exc.mensaje}; filas antes={antes}, después={repo.contar_fichas()}"
    raise AssertionError("se esperaba RefugioNoVerificado")


@prueba("3. Rechazar datos inválidos y no persistirlos")
def test_datos_invalidos() -> str:
    repo = RepositorioMascotas(str(RUTA_DB))
    antes = repo.contar_fichas()
    try:
        repo.crear_ficha(1, ficha_base("Conejo", especie="conejo"), ["x.jpg"])
    except DatosInvalidos as exc:
        assert repo.contar_fichas() == antes
        return f"{exc.codigo}: {exc.mensaje}; filas antes={antes}, después={repo.contar_fichas()}"
    raise AssertionError("se esperaba DatosInvalidos")


@prueba("4. Consultar un identificador inexistente y obtener None")
def test_inexistente() -> str:
    repo = RepositorioMascotas(str(RUTA_DB))
    assert repo.obtener_por_id(99999) is None
    return "obtener_por_id(99999) -> None"


@prueba("5. Verificar la restricción de integridad referencial (FK refugio_id)")
def test_fk() -> str:
    with closing(sqlite3.connect(RUTA_DB)) as conexion:
        conexion.execute("PRAGMA foreign_keys = ON")
        try:
            conexion.execute(
                """
                INSERT INTO mascota (
                    refugio_id, nombre, especie, edad_meses, tamano, nivel_energia,
                    experiencia_requerida, apta_con_menores, apta_con_mascotas,
                    estado, fecha_publicacion
                ) VALUES (999, 'Huérfana', 'perro', 12, 'pequeno', 'baja',
                          'ninguna', 1, 1, 'incompleta', '2026-10-11')
                """
            )
        except sqlite3.IntegrityError as exc:
            return f"sqlite3.IntegrityError: {exc}"
        raise AssertionError("se esperaba una violación de FK")


@prueba("6. Guardar una ficha sin fotos como incompleta y excluirla del catálogo")
def test_incompleta() -> str:
    repo = RepositorioMascotas(str(RUTA_DB))
    nuevo_id = repo.crear_ficha(1, ficha_base("Toby", fecha_publicacion="2026-10-12"), [])
    ficha = repo.obtener_por_id(nuevo_id)
    assert ficha is not None and ficha["estado"] == "incompleta"
    catalogo = repo.listar_catalogo()
    ids = [m["id"] for m in catalogo["mascotas"]]
    assert nuevo_id not in ids, f"la ficha incompleta {nuevo_id} no debe aparecer"
    return f"id={nuevo_id}, estado=incompleta, catálogo={ids}"


@prueba("7. Catálogo: solo disponibles de refugios verificados, orden y filtros")
def test_catalogo() -> str:
    repo = RepositorioMascotas(str(RUTA_DB))
    catalogo = repo.listar_catalogo()
    assert catalogo["total"] == 4, f"total esperado 4, obtenido {catalogo['total']}"
    ids = [m["id"] for m in catalogo["mascotas"]]
    assert ids == [1, 3, 2, 7], f"orden esperado [1, 3, 2, 7], obtenido {ids}"
    assert all(m["foto_principal"] for m in catalogo["mascotas"])

    perros = repo.listar_catalogo(especie="perro")
    assert perros["total"] == 3, f"perros esperados 3, obtenido {perros['total']}"

    pequenos = repo.listar_catalogo(tamano="pequeno")
    assert pequenos["total"] == 1 and pequenos["mascotas"][0]["nombre"] == "Milo"

    jovenes = repo.listar_catalogo(edad_min=0, edad_max=20)
    assert jovenes["total"] == 1 and jovenes["mascotas"][0]["nombre"] == "Milo"

    pagina_1 = repo.listar_catalogo(pagina=1, por_pagina=3)
    pagina_2 = repo.listar_catalogo(pagina=2, por_pagina=3)
    assert pagina_1["total"] == 4 and len(pagina_1["mascotas"]) == 3
    assert pagina_2["total"] == 4 and len(pagina_2["mascotas"]) == 1
    return (
        f"total={catalogo['total']}, orden={ids}, perros={perros['total']}, "
        f"pequenos={pequenos['total']}, pagina2={len(pagina_2['mascotas'])}"
    )


@prueba("8. Actualizar una ficha incompleta, publicarla y luego darla de baja")
def test_actualizar_y_baja() -> str:
    repo = RepositorioMascotas(str(RUTA_DB))
    ficha = repo.obtener_por_id(8)  # Toby, creado sin fotos en la prueba 6
    assert ficha is not None and ficha["estado"] == "incompleta"
    actualizada = repo.actualizar_ficha(
        8, 1, {"nombre": "Toby actualizado"}, ["toby_01.jpg"]
    )
    assert actualizada["estado"] == "disponible"
    assert actualizada["nombre"] == "Toby actualizado"
    assert any(m["id"] == 8 for m in repo.listar_catalogo()["mascotas"])

    repo.dar_de_baja(8, 1)
    assert not any(m["id"] == 8 for m in repo.listar_catalogo()["mascotas"])
    return "incompleta -> disponible -> baja; excluida del catálogo"


@prueba("9. Rechazar más de 5 fotografías (validación y trigger de base)")
def test_max_fotos() -> str:
    repo = RepositorioMascotas(str(RUTA_DB))
    try:
        repo.crear_ficha(1, ficha_base("Muchas fotos"), [f"f{i}.jpg" for i in range(1, 7)])
    except DatosInvalidos as exc:
        mensaje_repo = f"{exc.codigo}: {exc.mensaje}"
    else:
        raise AssertionError("se esperaba DatosInvalidos por más de 5 fotos")

    with closing(sqlite3.connect(RUTA_DB)) as conexion:
        conexion.execute("PRAGMA foreign_keys = ON")
        mascota_id = conexion.execute(
            """
            INSERT INTO mascota (
                refugio_id, nombre, especie, edad_meses, tamano, nivel_energia,
                experiencia_requerida, apta_con_menores, apta_con_mascotas,
                estado, fecha_publicacion
            ) VALUES (1, 'Trigger', 'perro', 12, 'pequeno', 'baja',
                      'ninguna', 1, 1, 'incompleta', '2026-10-13')
            """
        ).lastrowid
        try:
            for orden in range(1, 7):
                conexion.execute(
                    "INSERT INTO fotografia (mascota_id, archivo, orden) VALUES (?, ?, ?)",
                    (mascota_id, f"t{orden}.jpg", orden),
                )
        except sqlite3.IntegrityError as exc:
            conexion.rollback()
            return f"repositorio: {mensaje_repo}; trigger: {exc}"
        raise AssertionError("se esperaba que el trigger rechazara la sexta foto")


@prueba("10. Verificar triggers de publicación (refugio no verificado y ficha sin foto)")
def test_triggers_publicacion() -> str:
    with closing(sqlite3.connect(RUTA_DB)) as conexion:
        conexion.execute("PRAGMA foreign_keys = ON")
        errores = []
        for mascota_id, etiqueta in ((4, "refugio pendiente"), (5, "ficha sin foto")):
            try:
                conexion.execute(
                    "UPDATE mascota SET estado = 'disponible' WHERE id = ?",
                    (mascota_id,),
                )
            except sqlite3.IntegrityError as exc:
                errores.append(f"{etiqueta}: {exc}")
        if len(errores) != 2:
            raise AssertionError(f"se esperaban 2 rechazos, obtenidos: {errores}")
        return " | ".join(errores)


@prueba("11. Verificar que el catálogo no expone datos personales (RNF-04)")
def test_sin_datos_personales() -> str:
    repo = RepositorioMascotas(str(RUTA_DB))
    catalogo = repo.listar_catalogo()
    claves = set().union(*(m.keys() for m in catalogo["mascotas"]))
    ficha = repo.obtener_por_id(1)
    assert ficha is not None
    claves_ficha = set(ficha.keys())
    prohibidas = {"correo", "telefono", "nombreCompleto", "documento", "direccion"}
    expuestas = (claves | claves_ficha) & prohibidas
    assert not expuestas, f"las respuestas exponen datos personales: {expuestas}"
    return (
        f"catálogo: {len(claves)} claves; ficha: {len(claves_ficha)} claves; "
        f"0 campos personales"
    )


@prueba("12. Medir 20 consultas consecutivas al catálogo")
def test_tiempos() -> str:
    repo = RepositorioMascotas(str(RUTA_DB))
    tiempos = []
    for _ in range(20):
        inicio = time.perf_counter()
        repo.listar_catalogo(pagina=1, por_pagina=20)
        tiempos.append((time.perf_counter() - inicio) * 1000)
    return (
        f"n=20, mínimo={min(tiempos):.2f} ms, "
        f"promedio={statistics.mean(tiempos):.2f} ms, "
        f"máximo={max(tiempos):.2f} ms"
    )


def main() -> int:
    recrear_base()
    print("=" * 78)
    print("PRUEBA DE PERSISTENCIA - CORTE VERTICAL SEMANA 13")
    print(f"Base de datos: {RUTA_DB}")
    print(f"Python: {sys.version.split()[0]} | SQLite: {sqlite3.sqlite_version}")
    print("=" * 78)

    test_crear_y_leer()
    test_refugio_pendiente()
    test_datos_invalidos()
    test_inexistente()
    test_fk()
    test_incompleta()
    test_catalogo()
    test_actualizar_y_baja()
    test_max_fotos()
    test_triggers_publicacion()
    test_sin_datos_personales()
    test_tiempos()

    fallas = [r for r in resultados if not r[1]]
    print("-" * 78)
    print(f"RESUMEN: {len(resultados) - len(fallas)}/{len(resultados)} pruebas pasaron")
    if fallas:
        print("FALLAS:")
        for nombre, _, detalle in fallas:
            print(f"  - {nombre}: {detalle}")
    print("=" * 78)

    salida = EVIDENCIAS / "salida_pruebas.txt"
    with salida.open("w", encoding="utf-8") as archivo:
        archivo.write("PRUEBA DE PERSISTENCIA - CORTE VERTICAL SEMANA 13\n")
        archivo.write(f"Base de datos: {RUTA_DB}\n")
        archivo.write(f"Python: {sys.version.split()[0]} | SQLite: {sqlite3.sqlite_version}\n")
        archivo.write("=" * 78 + "\n")
        for nombre, ok, detalle in resultados:
            archivo.write(f"[{'PASA' if ok else 'FALLA'}] {nombre}\n")
            if detalle:
                archivo.write(f"       {detalle}\n")
        archivo.write("-" * 78 + "\n")
        archivo.write(
            f"RESUMEN: {len(resultados) - len(fallas)}/{len(resultados)} pruebas pasaron\n"
        )
    print(f"Evidencia escrita en: {salida}")
    return 0 if not fallas else 1


if __name__ == "__main__":
    raise SystemExit(main())
