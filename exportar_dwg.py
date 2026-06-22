#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exportar_dwg.py
===============

Exporta el despiece de un modelo a un DXF (+DWG) EDITABLE para AutoCAD.

Capas (todas prendibles/apagables por separado):
  PISO-MORET            -> piezas de Moret en el plano (polilínea cerrada)
  PISO-ROYAL-WALNUT     -> piezas de Royal Walnut en el plano
  ETIQUETAS             -> ID de cada pieza del plano (texto)

  CORTE-TILE            -> contorno de cada baldosa entera que se abre para cortar
  CORTE-RECORTE         -> el recorte ya ACOMODADO dentro de su baldosa
  CORTE-SOBRANTE        -> sobrante reutilizable de esa baldosa
  CORTE-DESPERDICIO     -> desperdicio (muy corto)
  CORTE-TEXTO           -> etiquetas del plan de corte (texto)

El "plan de corte" se dibuja DEBAJO del plano: cada baldosa que hay que abrir,
con el/los recorte(s) que salen de ella ya puestos en su lugar. Así ves, pieza
por pieza, qué se corta y de dónde sale — todo en su propio layer.

Edita en AutoCAD (agrega/mueve/borra en la capa correcta), guarda como DXF y:
    python3 importar_dwg.py  Cabernet_editable.dxf

Uso:  python3 exportar_dwg.py  [Cabernet]
"""

import os
import sys
import subprocess

import ezdxf
from datos_piezas import cargar_anotado, PREF_CORTE
from optimizador_recortes import PISOS
from pdf_material import empacar, es_reutilizable

DXF2DWG = os.environ.get("DXF2DWG", "/tmp/libredwg-0.13.3/programs/dxf2dwg")

CAPA = {"Moret": "PISO-MORET", "Royal Walnut": "PISO-ROYAL-WALNUT"}
LAYERS = {
    "PISO-MORET": 30, "PISO-ROYAL-WALNUT": 4, "ETIQUETAS": 7,
    "CORTE-TILE": 7, "CORTE-RECORTE": 3, "CORTE-SOBRANTE": 2,
    "CORTE-DESPERDICIO": 1, "CORTE-TEXTO": 5,
    "SOBRANTES-MAPA": 6, "SOBRANTES-RECORTE": 2, "SOBRANTES-TEXTO": 6,
}


def _rect(msp, x, y, w, h, layer):
    msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
                       close=True, dxfattribs={"layer": layer})


def _txt(msp, s, x, y, h, layer):
    t = msp.add_text(s, dxfattribs={"layer": layer, "height": h})
    t.set_placement((x, y), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)


def dibujar_mapa_sobrantes(msp, piezas):
    """En CADA recorte del plano, dibuja el tablón COMPLETO del que sale, extendido
    hacia AFUERA de la casa: así, apagando lo demás, queda un mapa de todos los
    sobrantes y de dónde salen. (Si es orilla, sale por fuera; si no, se encima.)"""
    cx = sum(p["x"] for p in piezas) / len(piezas)
    cy = sum(p["y"] for p in piezas) / len(piezas)
    for p in piezas:
        if p["completa"]:
            continue
        W, L = PISOS[p["material"]]          # W = ancho (x), L = largo (y) del tablón
        W = max(W, p["wx"]); L = max(L, p["hy"])
        dx = 1 if p["x"] >= cx else -1
        dy = 1 if p["y"] >= cy else -1
        tx = p["x0"] if dx > 0 else p["x0"] + p["wx"] - W
        ty = p["y0"] if dy > 0 else p["y0"] + p["hy"] - L
        # tablón completo (contorno) y el sobrante (lo que NO es el recorte)
        _rect(msp, tx, ty, W, L, "SOBRANTES-MAPA")
        sob_w = round(W - p["wx"], 3); sob_l = round(L - p["hy"], 3)
        if sob_w > 0.02:                      # sobrante de ancho
            ox = (p["x0"] + p["wx"]) if dx > 0 else tx
            _rect(msp, ox, p["y0"], W - p["wx"], p["hy"], "SOBRANTES-RECORTE")
        if sob_l > 0.02:                      # sobrante de largo
            oy = (p["y0"] + p["hy"]) if dy > 0 else ty
            _rect(msp, p["x0"], oy, p["wx"], L - p["hy"], "SOBRANTES-RECORTE")
        _txt(msp, p["id"], tx + W / 2, ty + L / 2, min(0.05, W / 4), "SOBRANTES-TEXTO")


def dibujar_plan_corte(msp, piezas, x0_plan, y0_plan):
    """Dibuja, debajo del plano, cada baldosa que se abre con sus recortes puestos."""
    y_top = y0_plan - 2.0
    for material in ("Moret", "Royal Walnut"):
        baldosas, mapa, (anchoB, largoB) = empacar(piezas, material)
        if not baldosas:
            continue
        pc = PREF_CORTE[material]
        cols = 22
        cellw = anchoB + 0.45          # más separación horizontal
        cellh = largoB + 0.70          # más separación vertical (texto no se encima)
        _txt(msp, f"PLAN DE CORTE - {material.upper()}  ({len(baldosas)} baldosas a abrir)",
             x0_plan + 3, y_top + 0.5, 0.25, "CORTE-TEXTO")
        for i, b in enumerate(baldosas):
            col = i % cols
            row = i // cols
            ox = x0_plan + col * cellw
            oy = y_top - (row + 1) * cellh
            _rect(msp, ox, oy, anchoB, largoB, "CORTE-TILE")
            _txt(msp, f"{pc}-{i+1:02d}", ox + anchoB / 2, oy + largoB + 0.14, 0.06, "CORTE-TEXTO")
            for (x, y, w, l, pid, rot) in b.piezas:
                _rect(msp, ox + x, oy + y, w, l, "CORTE-RECORTE")
                _txt(msp, pid, ox + x + w / 2, oy + y + l / 2, min(0.035, w / 4.5), "CORTE-TEXTO")
            for (fx, fy, fw, fl) in b.libres:
                if fw <= 0.005 or fl <= 0.005:
                    continue
                capa = "CORTE-SOBRANTE" if es_reutilizable(fw, fl) else "CORTE-DESPERDICIO"
                _rect(msp, ox + fx, oy + fy, fw, fl, capa)
        filas = (len(baldosas) + cols - 1) // cols
        y_top = y_top - filas * cellh - 2.0


def exportar(modelo):
    piezas = cargar_anotado(modelo)
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.M
    msp = doc.modelspace()
    for nombre, color in LAYERS.items():
        doc.layers.add(nombre).color = color

    # --- Plano: piezas + IDs ---
    for p in piezas:
        x0, y0, w, h = p["x0"], p["y0"], p["wx"], p["hy"]
        _rect(msp, x0, y0, w, h, CAPA[p["material"]])
        th = min(max(0.03, min(w, h) * 0.30), 0.09)
        _txt(msp, p["id"], p["x"], p["y"], th, "ETIQUETAS")

    # --- Mapa de sobrantes (sobre el plano, saliendo hacia afuera) ---
    dibujar_mapa_sobrantes(msp, piezas)

    # --- Plan de corte (debajo del plano) ---
    minx = min(p["x0"] for p in piezas)
    miny = min(p["y0"] for p in piezas)
    dibujar_plan_corte(msp, piezas, minx, miny)

    dxf = f"{modelo}_editable.dxf"
    dwg = f"{modelo}_editable.dwg"
    doc.saveas(dxf)
    if os.path.exists(DXF2DWG):
        subprocess.run([DXF2DWG, "-y", "-o", dwg, dxf], check=True, stderr=subprocess.DEVNULL)
        print(f"DWG editable: {dwg}")
    else:
        print(f"(no se encontró dxf2dwg; queda el DXF: {dxf})")
    nrec = sum(1 for p in piezas if not p["completa"])
    print(f"DXF editable: {dxf}")
    print(f"Piezas en el plano: {len(piezas)}  (recortes: {nrec})")
    print("Capas: PISO-MORET, PISO-ROYAL-WALNUT, ETIQUETAS, "
          "CORTE-TILE/RECORTE/SOBRANTE/DESPERDICIO/TEXTO")


if __name__ == "__main__":
    exportar(sys.argv[1] if len(sys.argv) > 1 else "Cabernet")
