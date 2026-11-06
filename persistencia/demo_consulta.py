# -*- coding: utf-8 -*-
"""Consulta manual del catálogo y de una ficha (evidencia de lectura).

Ejecutar después de prueba_persistencia.py:
    python demo_consulta.py
"""

from __future__ import annotations

import json
from pathlib import Path

from repositorio import RepositorioMascotas

RUTA_DB = Path(__file__).resolve().parent.parent / "evidencias" / "prueba.db"


def main() -> None:
    repo = RepositorioMascotas(str(RUTA_DB))
    catalogo = repo.listar_catalogo(especie="perro")
    print("CATÁLOGO FILTRADO POR especie=perro")
    print(json.dumps(catalogo, ensure_ascii=False, indent=2))

    print("\nFICHA 1 RECUPERADA POR ID (con conexión nueva)")
    print(json.dumps(repo.obtener_por_id(1), ensure_ascii=False, indent=2))

    print("\nFICHA INEXISTENTE 99999")
    print(repo.obtener_por_id(99999))


if __name__ == "__main__":
    main()
