#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
importar_dwg.py
===============

Lee el DWG que editaste en AutoCAD (exportado con exportar_dwg.py) y regenera
los PDF de despiece con tus cambios: piezas agregadas, ajustadas o borradas.

El material lo toma de la CAPA de cada pieza:
    PISO-MORET          -> Moret
    PISO-ROYAL-WALNUT   -> Royal Walnut
El tamaño/posición lo toma del rectángulo (no importa si lo moviste o estiraste).
Si dibujas una pieza nueva en la capa correcta, se incluye. Si la borras, se va.

Uso:  python3 importar_dwg.py  Cabernet_editable.dwg  [--modelo Cabernet]

Requiere dwgread de LibreDWG (DWG -> JSON).
"""

import os
import sys
import argparse
import subprocess

import ezdxf
from ezdxf import recover

from datos_piezas import asignar_ids_corte, _retipo, MODELOS
import pdf_material

DWG2DXF = os.environ.get("DWG2DXF", "/tmp/libredwg-0.13.3/programs/dwg2dxf")
CAPA_MAT = {"PISO-MORET": "Moret", "PISO-ROYAL-WALNUT": "Royal Walnut"}


def leer_piezas(archivo, modelo):
    # AutoCAD: edita y GUARDA COMO DXF (recomendado). Si mandas DWG, se convierte.
    dxf = archivo
    if archivo.lower().endswith(".dwg"):
        dxf = f"/tmp/{os.path.splitext(os.path.basename(archivo))[0]}_imp.dxf"
        if not os.path.exists(DWG2DXF):
            sys.exit(f"No se encontró dwg2dxf en {DWG2DXF}. Guarda mejor el DWG como DXF.")
        subprocess.run([DWG2DXF, "-y", "-o", dxf, archivo], check=True, stderr=subprocess.DEVNULL)

    try:
        doc = ezdxf.readfile(dxf)
    except Exception:
        doc, _ = recover.readfile(dxf)
    msp = doc.modelspace()

    x_corte = MODELOS[modelo]["x_corte"]
    piezas = []
    for e in msp:
        if e.dxftype() != "LWPOLYLINE":
            continue
        mat = CAPA_MAT.get(e.dxf.layer)
        if mat is None:
            continue
        pts = [(p[0], p[1]) for p in e.get_points()]
        if len(pts) < 3:
            continue
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        x0, y0 = min(xs), min(ys)
        wx, hy = max(xs) - x0, max(ys) - y0
        if wx <= 0.005 or hy <= 0.005:
            continue
        p = {"material": mat, "x0": round(x0, 4), "y0": round(y0, 4),
             "wx": round(wx, 4), "hy": round(hy, 4),
             "x": round(x0 + wx / 2, 3), "y": round(y0 + hy / 2, 3),
             "planta": "baja" if (x0 + wx / 2) < x_corte else "alta"}
        _retipo(p)
        piezas.append(p)
    return piezas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dwg")
    ap.add_argument("--modelo", default="Cabernet")
    args = ap.parse_args()

    piezas = leer_piezas(args.dwg, args.modelo)
    asignar_ids_corte(piezas)
    print(f"Leídas {len(piezas)} piezas del DWG editado "
          f"(Moret {sum(1 for p in piezas if p['material']=='Moret')}, "
          f"Royal {sum(1 for p in piezas if p['material']=='Royal Walnut')}).")

    for material, suf in [("Moret", "Moret-Arena"), ("Royal Walnut", "Royal-Walnut")]:
        path = f"{args.modelo}_Despiece-Piso_{suf}_EDITADO.pdf"
        r = pdf_material.hacer_pdf(piezas, material, path, args.modelo + " (editado)")
        print(f"  {material}: {r[0]} piezas / {r[1]} cajas -> {path}")


if __name__ == "__main__":
    main()
