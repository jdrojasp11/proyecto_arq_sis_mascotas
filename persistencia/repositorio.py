# -*- coding: utf-8 -*-
"""Repositorio de persistencia del corte vertical (RF-05 y RF-34).

El repositorio encapsula todo el SQL. Los servicios de la semana 2 y la API
no deben construir consultas: solo llaman estos métodos y traducen sus
excepciones al catálogo de errores.

Uso:
    repo = RepositorioMascotas("evidencias/prueba.db")
    nuevo_id = repo.crear_ficha(1, ficha, ["foto1.jpg", "foto2.jpg"])
    ficha = repo.obtener_por_id(nuevo_id)
    pagina = repo.listar_catalogo(especie="perro", pagina=1)
"""

from __future__ import annotations

import datetime as _dt
import os
import sqlite3
from contextlib import closing
from typing import Any, Iterable, Mapping, Sequence

ESPECIES = {"perro", "gato"}
TAMANOS = {"pequeno", "mediano", "grande"}
ENERGIAS = {"baja", "media", "alta"}
EXPERIENCIAS = {"ninguna", "basica", "amplia"}
ESTADOS = {"incompleta", "disponible", "adoptada", "baja"}
EXTENSIONES_FOTO = {".jpg", ".jpeg", ".png"}
MAX_FOTOS = 5
CAMPOS_OBLIGATORIOS = (
    "nombre",
    "especie",
    "edad_meses",
    "tamano",
    "nivel_energia",
    "experiencia_requerida",
    "apta_con_menores",
    "apta_con_mascotas",
    "fecha_publicacion",
)


class ErrorPersistencia(Exception):
    """Error controlado de la capa de persistencia."""

    def __init__(self, codigo: str, mensaje: str):
        super().__init__(f"{codigo}: {mensaje}")
        self.codigo = codigo
        self.mensaje = mensaje


class DatosInvalidos(ErrorPersistencia):
    def __init__(self, mensaje: str):
        super().__init__("ERR-004", mensaje)


class RefugioNoEncontrado(ErrorPersistencia):
    def __init__(self, refugio_id: int):
        super().__init__("ERR-008", f"no existe el refugio {refugio_id}")


class RefugioNoVerificado(ErrorPersistencia):
    def __init__(self, refugio_id: int):
        super().__init__(
            "ERR-009",
            f"el refugio {refugio_id} no está verificado y no puede publicar fichas",
        )


class FichaNoEncontrada(ErrorPersistencia):
    def __init__(self, mascota_id: int):
        super().__init__("ERR-011", f"no existe la ficha {mascota_id}")


class SinPermiso(ErrorPersistencia):
    def __init__(self, mascota_id: int):
        super().__init__(
            "ERR-003", f"la ficha {mascota_id} no pertenece al refugio indicado"
        )


def _es_entero(valor: Any) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _validar_ficha(ficha: Mapping[str, Any]) -> dict[str, Any]:
    """Valida los campos de RN-22 y devuelve una copia normalizada."""
    if not isinstance(ficha, Mapping):
        raise DatosInvalidos("la ficha debe ser un objeto con campos")

    faltantes = [c for c in CAMPOS_OBLIGATORIOS if c not in ficha or ficha[c] is None]
    if faltantes:
        raise DatosInvalidos(f"faltan campos obligatorios: {', '.join(faltantes)}")

    datos = dict(ficha)

    nombre = datos["nombre"]
    if not isinstance(nombre, str) or not (1 <= len(nombre.strip()) <= 60):
        raise DatosInvalidos("nombre debe tener entre 1 y 60 caracteres")
    datos["nombre"] = nombre.strip()

    raza = datos.get("raza")
    if raza is not None and (not isinstance(raza, str) or len(raza) > 80):
        raise DatosInvalidos("raza debe ser texto de máximo 80 caracteres")
    if isinstance(raza, str):
        datos["raza"] = raza.strip() or None

    if datos["especie"] not in ESPECIES:
        raise DatosInvalidos("especie debe ser perro o gato")
    if datos["tamano"] not in TAMANOS:
        raise DatosInvalidos("tamano debe ser pequeno, mediano o grande")
    if datos["nivel_energia"] not in ENERGIAS:
        raise DatosInvalidos("nivel_energia debe ser baja, media o alta")
    if datos["experiencia_requerida"] not in EXPERIENCIAS:
        raise DatosInvalidos(
            "experiencia_requerida debe ser ninguna, basica o amplia"
        )

    if not _es_entero(datos["edad_meses"]) or not (0 <= datos["edad_meses"] <= 300):
        raise DatosInvalidos("edad_meses debe ser un entero entre 0 y 300")

    for campo in ("apta_con_menores", "apta_con_mascotas"):
        valor = datos[campo]
        if isinstance(valor, bool):
            datos[campo] = int(valor)
        elif not (_es_entero(valor) and valor in (0, 1)):
            raise DatosInvalidos(f"{campo} debe ser booleano o 0/1")

    try:
        fecha = _dt.date.fromisoformat(str(datos["fecha_publicacion"]))
    except ValueError as exc:
        raise DatosInvalidos(
            "fecha_publicacion debe tener formato ISO 8601 (AAAA-MM-DD)"
        ) from exc
    datos["fecha_publicacion"] = fecha.isoformat()

    for campo in ("historial_salud", "historial_comportamiento"):
        valor = datos.get(campo)
        if valor is not None and (not isinstance(valor, str) or len(valor) > 1000):
            raise DatosInvalidos(f"{campo} debe ser texto de máximo 1000 caracteres")

    return datos


def _validar_fotos(fotos: Iterable[str]) -> list[tuple[str, int]]:
    """Valida 0 a 5 archivos JPG/PNG y devuelve (archivo, orden)."""
    if fotos is None:
        return []
    if isinstance(fotos, (str, bytes)):
        raise DatosInvalidos("fotografias debe ser una lista de archivos")
    lista = list(fotos)
    if len(lista) > MAX_FOTOS:
        raise DatosInvalidos(f"una ficha admite como máximo {MAX_FOTOS} fotografías")

    resultado: list[tuple[str, int]] = []
    for indice, archivo in enumerate(lista, start=1):
        if not isinstance(archivo, str) or not archivo.strip():
            raise DatosInvalidos("cada fotografía debe ser una ruta de archivo")
        archivo = archivo.strip()
        if os.path.splitext(archivo)[1].lower() not in EXTENSIONES_FOTO:
            raise DatosInvalidos("las fotografías deben ser JPG o PNG")
        resultado.append((archivo, indice))
    return resultado


class RepositorioMascotas:
    """Acceso a datos de refugios, fichas de mascota y fotografías."""

    def __init__(self, ruta_db: str):
        self.ruta_db = ruta_db

    # ------------------------------------------------------------------
    # Conexión
    # ------------------------------------------------------------------
    def _conectar(self) -> sqlite3.Connection:
        conexion = sqlite3.connect(self.ruta_db)
        conexion.row_factory = sqlite3.Row
        conexion.execute("PRAGMA foreign_keys = ON")
        return conexion

    # ------------------------------------------------------------------
    # RF-05: crear / consultar / actualizar / dar de baja una ficha
    # ------------------------------------------------------------------
    def crear_ficha(
        self,
        refugio_id: int,
        ficha: Mapping[str, Any],
        fotografias: Sequence[str] | None = None,
    ) -> int:
        """Registra una ficha y devuelve su identificador real.

        La ficha se inserta como ``incompleta`` y solo pasa a ``disponible``
        si tiene al menos una fotografía y el refugio está verificado. Las
        reglas también se refuerzan con triggers en la base de datos.
        """
        if not _es_entero(refugio_id):
            raise DatosInvalidos("refugio_id debe ser un entero")
        datos = _validar_ficha(ficha)
        fotos = _validar_fotos(fotografias or [])

        with closing(self._conectar()) as conexion:
            try:
                conexion.execute("BEGIN IMMEDIATE")
                refugio = conexion.execute(
                    "SELECT estado_verificacion FROM refugio WHERE id = ?",
                    (refugio_id,),
                ).fetchone()
                if refugio is None:
                    raise RefugioNoEncontrado(refugio_id)
                if refugio["estado_verificacion"] != "verificado":
                    raise RefugioNoVerificado(refugio_id)

                cursor = conexion.execute(
                    """
                    INSERT INTO mascota (
                        refugio_id, nombre, raza, especie, edad_meses, tamano,
                        nivel_energia, experiencia_requerida, apta_con_menores,
                        apta_con_mascotas, historial_salud,
                        historial_comportamiento, estado, fecha_publicacion
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'incompleta', ?)
                    """,
                    (
                        refugio_id,
                        datos["nombre"],
                        datos.get("raza"),
                        datos["especie"],
                        datos["edad_meses"],
                        datos["tamano"],
                        datos["nivel_energia"],
                        datos["experiencia_requerida"],
                        datos["apta_con_menores"],
                        datos["apta_con_mascotas"],
                        datos.get("historial_salud"),
                        datos.get("historial_comportamiento"),
                        datos["fecha_publicacion"],
                    ),
                )
                mascota_id = int(cursor.lastrowid)

                conexion.executemany(
                    "INSERT INTO fotografia (mascota_id, archivo, orden) VALUES (?, ?, ?)",
                    [(mascota_id, archivo, orden) for archivo, orden in fotos],
                )

                if fotos:
                    conexion.execute(
                        "UPDATE mascota SET estado = 'disponible' WHERE id = ?",
                        (mascota_id,),
                    )

                conexion.commit()
                return mascota_id
            except ErrorPersistencia:
                conexion.rollback()
                raise
            except sqlite3.IntegrityError as exc:
                conexion.rollback()
                raise ErrorPersistencia("ERR-006", str(exc)) from exc

    def obtener_por_id(self, mascota_id: int) -> dict[str, Any] | None:
        """Recupera una ficha completa o ``None`` si el id no existe (RF-05)."""
        if not _es_entero(mascota_id):
            raise DatosInvalidos("mascota_id debe ser un entero")

        with closing(self._conectar()) as conexion:
            fila = conexion.execute(
                """
                SELECT m.*, r.nombre AS refugio_nombre,
                       r.localidad AS refugio_localidad,
                       r.estado_verificacion AS refugio_estado
                FROM mascota m
                JOIN refugio r ON r.id = m.refugio_id
                WHERE m.id = ?
                """,
                (mascota_id,),
            ).fetchone()
            if fila is None:
                return None

            fotos = conexion.execute(
                "SELECT id, archivo, orden FROM fotografia WHERE mascota_id = ? ORDER BY orden",
                (mascota_id,),
            ).fetchall()

            resultado = dict(fila)
            resultado["apta_con_menores"] = bool(resultado["apta_con_menores"])
            resultado["apta_con_mascotas"] = bool(resultado["apta_con_mascotas"])
            resultado["fotografias"] = [dict(f) for f in fotos]
            return resultado

    def actualizar_ficha(
        self,
        mascota_id: int,
        refugio_id: int,
        cambios: Mapping[str, Any],
        fotografias: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Actualiza campos de una ficha del refugio y, si se envían, sus fotos.

        Si se reemplazan las fotografías, se vuelve a calcular el estado:
        ``disponible`` cuando hay al menos una y ``incompleta`` cuando no.
        """
        if not cambios and fotografias is None:
            raise DatosInvalidos("no hay cambios para aplicar")

        with closing(self._conectar()) as conexion:
            try:
                conexion.execute("BEGIN IMMEDIATE")
                actual = conexion.execute(
                    "SELECT * FROM mascota WHERE id = ?", (mascota_id,)
                ).fetchone()
                if actual is None:
                    raise FichaNoEncontrada(mascota_id)
                if actual["refugio_id"] != refugio_id:
                    raise SinPermiso(mascota_id)

                campos_permitidos = set(CAMPOS_OBLIGATORIOS) | {
                    "raza",
                    "historial_salud",
                    "historial_comportamiento",
                }
                desconocidos = set(cambios) - campos_permitidos
                if desconocidos:
                    raise DatosInvalidos(
                        f"campos no permitidos: {', '.join(sorted(desconocidos))}"
                    )

                combinada = {k: actual[k] for k in CAMPOS_OBLIGATORIOS}
                combinada.update(
                    {
                        k: actual[k]
                        for k in ("raza", "historial_salud", "historial_comportamiento")
                    }
                )
                combinada.update(cambios)
                datos = _validar_ficha(combinada)

                conexion.execute(
                    """
                    UPDATE mascota SET
                        nombre = ?, raza = ?, especie = ?, edad_meses = ?, tamano = ?,
                        nivel_energia = ?, experiencia_requerida = ?,
                        apta_con_menores = ?, apta_con_mascotas = ?,
                        historial_salud = ?, historial_comportamiento = ?,
                        fecha_publicacion = ?
                    WHERE id = ?
                    """,
                    (
                        datos["nombre"],
                        datos.get("raza"),
                        datos["especie"],
                        datos["edad_meses"],
                        datos["tamano"],
                        datos["nivel_energia"],
                        datos["experiencia_requerida"],
                        datos["apta_con_menores"],
                        datos["apta_con_mascotas"],
                        datos.get("historial_salud"),
                        datos.get("historial_comportamiento"),
                        datos["fecha_publicacion"],
                        mascota_id,
                    ),
                )

                if fotografias is not None:
                    fotos = _validar_fotos(fotografias)
                    conexion.execute(
                        "DELETE FROM fotografia WHERE mascota_id = ?", (mascota_id,)
                    )
                    conexion.executemany(
                        "INSERT INTO fotografia (mascota_id, archivo, orden) VALUES (?, ?, ?)",
                        [(mascota_id, archivo, orden) for archivo, orden in fotos],
                    )
                    nuevo_estado = "disponible" if fotos else "incompleta"
                    conexion.execute(
                        "UPDATE mascota SET estado = ? WHERE id = ?",
                        (nuevo_estado, mascota_id),
                    )

                conexion.commit()
            except ErrorPersistencia:
                conexion.rollback()
                raise
            except sqlite3.IntegrityError as exc:
                conexion.rollback()
                raise ErrorPersistencia("ERR-006", str(exc)) from exc

        ficha = self.obtener_por_id(mascota_id)
        assert ficha is not None
        return ficha

    def dar_de_baja(self, mascota_id: int, refugio_id: int) -> None:
        """Baja lógica: la ficha deja de aparecer en el catálogo (RN-15)."""
        with closing(self._conectar()) as conexion:
            actual = conexion.execute(
                "SELECT refugio_id FROM mascota WHERE id = ?", (mascota_id,)
            ).fetchone()
            if actual is None:
                raise FichaNoEncontrada(mascota_id)
            if actual["refugio_id"] != refugio_id:
                raise SinPermiso(mascota_id)
            conexion.execute(
                "UPDATE mascota SET estado = 'baja' WHERE id = ?", (mascota_id,)
            )
            conexion.commit()

    # ------------------------------------------------------------------
    # RF-34: catálogo de mascotas disponibles
    # ------------------------------------------------------------------
    def listar_catalogo(
        self,
        especie: str | None = None,
        tamano: str | None = None,
        edad_min: int | None = None,
        edad_max: int | None = None,
        pagina: int = 1,
        por_pagina: int = 20,
    ) -> dict[str, Any]:
        """Lista fichas disponibles de refugios verificados, con filtros.

        Orden: fecha de publicación ascendente y, a igual fecha, id ascendente.
        No muestra fichas incompletas, adoptadas ni dadas de baja.
        """
        if especie is not None and especie not in ESPECIES:
            raise DatosInvalidos("especie debe ser perro o gato")
        if tamano is not None and tamano not in TAMANOS:
            raise DatosInvalidos("tamano debe ser pequeno, mediano o grande")
        if edad_min is not None and (not _es_entero(edad_min) or edad_min < 0):
            raise DatosInvalidos("edad_min debe ser un entero mayor o igual a 0")
        if edad_max is not None and (not _es_entero(edad_max) or edad_max < 0):
            raise DatosInvalidos("edad_max debe ser un entero mayor o igual a 0")
        if edad_min is not None and edad_max is not None and edad_min > edad_max:
            raise DatosInvalidos("edad_min no puede ser mayor que edad_max")
        if not _es_entero(pagina) or pagina < 1:
            raise DatosInvalidos("pagina debe ser un entero mayor o igual a 1")
        if not _es_entero(por_pagina) or not (1 <= por_pagina <= 100):
            raise DatosInvalidos("por_pagina debe estar entre 1 y 100")

        condiciones = [
            "m.estado = 'disponible'",
            "r.estado_verificacion = 'verificado'",
        ]
        parametros: list[Any] = []
        if especie is not None:
            condiciones.append("m.especie = ?")
            parametros.append(especie)
        if tamano is not None:
            condiciones.append("m.tamano = ?")
            parametros.append(tamano)
        if edad_min is not None:
            condiciones.append("m.edad_meses >= ?")
            parametros.append(edad_min)
        if edad_max is not None:
            condiciones.append("m.edad_meses <= ?")
            parametros.append(edad_max)

        where = " AND ".join(condiciones)
        offset = (pagina - 1) * por_pagina

        with closing(self._conectar()) as conexion:
            total = conexion.execute(
                f"""
                SELECT COUNT(*)
                FROM mascota m
                JOIN refugio r ON r.id = m.refugio_id
                WHERE {where}
                """,
                parametros,
            ).fetchone()[0]

            filas = conexion.execute(
                f"""
                SELECT m.id, m.nombre, m.especie, m.edad_meses, m.tamano,
                       m.nivel_energia, m.fecha_publicacion,
                       r.id AS refugio_id, r.nombre AS refugio_nombre,
                       r.localidad AS refugio_localidad,
                       (SELECT f.archivo FROM fotografia f
                         WHERE f.mascota_id = m.id
                         ORDER BY f.orden LIMIT 1) AS foto_principal
                FROM mascota m
                JOIN refugio r ON r.id = m.refugio_id
                WHERE {where}
                ORDER BY m.fecha_publicacion ASC, m.id ASC
                LIMIT ? OFFSET ?
                """,
                parametros + [por_pagina, offset],
            ).fetchall()

            return {
                "total": int(total),
                "pagina": pagina,
                "porPagina": por_pagina,
                "mascotas": [dict(fila) for fila in filas],
            }

    # ------------------------------------------------------------------
    # Utilidad para pruebas y verificación manual
    # ------------------------------------------------------------------
    def contar_fichas(self) -> int:
        with closing(self._conectar()) as conexion:
            return int(conexion.execute("SELECT COUNT(*) FROM mascota").fetchone()[0])
