#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generar_modelo.py
=================

Pipeline completo de un prototipo: DWG -> JSON (LibreDWG) -> extrae despiece ->
genera los 2 PDFs (Moret y Royal Walnut) de ese modelo.

Uso:
    python3 generar_modelo.py Cabernet|Merlot|Chardonnay [--todos]

Requiere el binario `dwgread` de LibreDWG (por defecto en
/tmp/libredwg-0.13.3/programs/dwgread; ajustar DWGREAD si está en otra ruta).
"""

import os
import sys
import subprocess

from modelos import MODELOS
import extraer_despiece
import pdf_material

DWGREAD = os.environ.get("DWGREAD", "/tmp/libredwg-0.13.3/programs/dwgread")


def generar(modelo):
    cfg = MODELOS[modelo]
    # 1) DWG -> JSON (sólo si no existe ya)
    if not os.path.exists(cfg["json"]):
        if not os.path.exists(DWGREAD):
            sys.exit(f"No se encontró dwgread en {DWGREAD}. Instala/compila LibreDWG "
                     f"o exporta DWGREAD con la ruta correcta.")
        print(f"[{modelo}] DWG -> JSON ...")
        subprocess.run([DWGREAD, "-O", "JSON", "-o", cfg["json"], cfg["dwg"]],
                       check=True, stderr=subprocess.DEVNULL)
    # 2) Extraer despiece
    print(f"[{modelo}] extrayendo despiece de la capa {cfg['capa']} ...")
    piezas, descartadas = extraer_despiece.extraer(cfg["json"], cfg["capa"])
    salida = [{k: v for k, v in p.items() if k != "handle"} for p in piezas]
    import json
    base = cfg["piezas"].rsplit(".", 1)[0]
    with open(cfg["piezas"], "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)
    print(f"[{modelo}] {len(piezas)} piezas  (descartadas {descartadas}) -> {cfg['piezas']}")
    # 3) PDFs
    pdf_material.main(modelo)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--todos" in sys.argv or not args:
        modelos = list(MODELOS.keys())
    else:
        modelos = args
    for m in modelos:
        if m not in MODELOS:
            sys.exit(f"Modelo desconocido: {m}. Opciones: {list(MODELOS)}")
        generar(m)


if __name__ == "__main__":
    main()
