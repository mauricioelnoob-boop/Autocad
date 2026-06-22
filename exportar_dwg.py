#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exportar_dwg.py
===============

Exporta el despiece de un modelo a un DWG EDITABLE para AutoCAD, donde puedes:
  * agregar piezas que falten   (dibuja un rectángulo en la capa del material)
  * ajustar piezas              (mueve / estira los rectángulos)
  * borrar piezas fantasma      (borra el rectángulo)

Capas:
  PISO-MORET           -> piezas de Moret   (cada pieza = polilínea cerrada)
  PISO-ROYAL-WALNUT    -> piezas de Royal Walnut
  ETIQUETAS            -> el ID de cada pieza (texto)
  AGREGAR-AQUI         -> capa vacía, opcional, para tus notas

Después de editar, corre:  python3 importar_dwg.py  <archivo_editado.dwg>

Uso:  python3 exportar_dwg.py  [Cabernet]
"""

import os
import sys
import subprocess

import ezdxf
from datos_piezas import cargar_anotado

DXF2DWG = os.environ.get("DXF2DWG", "/tmp/libredwg-0.13.3/programs/dxf2dwg")

CAPA = {"Moret": "PISO-MORET", "Royal Walnut": "PISO-ROYAL-WALNUT"}
ACI = {"PISO-MORET": 30, "PISO-ROYAL-WALNUT": 4, "ETIQUETAS": 7, "AGREGAR-AQUI": 1}


def exportar(modelo):
    piezas = cargar_anotado(modelo)
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.M
    msp = doc.modelspace()
    for nombre, color in ACI.items():
        doc.layers.add(nombre).color = color

    for p in piezas:
        capa = CAPA[p["material"]]
        x0, y0, w, h = p["x0"], p["y0"], p["wx"], p["hy"]
        msp.add_lwpolyline([(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)],
                           close=True, dxfattribs={"layer": capa})
        th = min(max(0.03, min(w, h) * 0.30), 0.09)
        t = msp.add_text(p["id"], dxfattribs={"layer": "ETIQUETAS", "height": th})
        t.set_placement((p["x"], p["y"]), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

    dxf = f"{modelo}_editable.dxf"
    dwg = f"{modelo}_editable.dwg"
    doc.saveas(dxf)
    if os.path.exists(DXF2DWG):
        subprocess.run([DXF2DWG, "-y", "-o", dwg, dxf], check=True, stderr=subprocess.DEVNULL)
        print(f"DWG editable: {dwg}")
    else:
        print(f"(no se encontró dxf2dwg; queda el DXF: {dxf})")
    print(f"Piezas exportadas: {len(piezas)}  "
          f"(Moret {sum(1 for p in piezas if p['material']=='Moret')}, "
          f"Royal {sum(1 for p in piezas if p['material']=='Royal Walnut')})")
    print("Edita en AutoCAD y luego: python3 importar_dwg.py " + dwg)


if __name__ == "__main__":
    exportar(sys.argv[1] if len(sys.argv) > 1 else "Cabernet")
