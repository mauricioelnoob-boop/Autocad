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
    "ZOCLO": 3, "URBANIA-LAVANDERIA": 5, "REGADERA-MALLA-MURO": 1,
}


def dibujar_acabados(msp, modelo):
    """Dibuja zoclo (perímetro) y marca las zonas de Urbania (lavandería) y las
    regaderas (Malla en charola + muro Moret), cada una en su propio layer."""
    try:
        import pdf_generadores as PG
        zoclo, muros, escal, claves = PG._datos_dwg(modelo)
    except Exception:
        return
    for a, b in zoclo:
        msp.add_line(a, b, dxfattribs={"layer": "ZOCLO"})
    for c in claves:
        if c[0] == "5":
            _txt(msp, "URBANIA", c[1], c[2], 0.12, "URBANIA-LAVANDERIA")
        elif c[0] == "2":
            _txt(msp, "REGADERA", c[1], c[2], 0.12, "REGADERA-MALLA-MURO")


def _rect(msp, x, y, w, h, layer):
    msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
                       close=True, dxfattribs={"layer": layer})


def _contorno_notch(msp, p, layer):
    """Dibuja el CONTORNO real de una pieza con entrante (bbox menos el muro):
    una sola polilínea que rodea la jamba. Si el resultado se parte, dibuja cada
    parte; así el piso queda RODEANDO el muro, no encima."""
    try:
        from shapely.geometry import box, Polygon
    except Exception:
        return _rect(msp, p["x0"], p["y0"], p["wx"], p["hy"], layer)
    g = box(p["x0"], p["y0"], p["x0"] + p["wx"], p["y0"] + p["hy"])
    for ring in p.get("notch", []):
        if len(ring) >= 3:
            g = g.difference(Polygon(ring).buffer(0))
    polys = [g] if g.geom_type == "Polygon" else list(getattr(g, "geoms", []))
    for gg in polys:
        if gg.is_empty:
            continue
        pts = [(round(x, 4), round(y, 4)) for x, y in gg.exterior.coords[:-1]]
        if len(pts) >= 3:
            msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer})


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
            for (fx, fy, fw, fl, *_z) in b.libres:
                if fw <= 0.005 or fl <= 0.005:
                    continue
                capa = "CORTE-SOBRANTE" if es_reutilizable(fw, fl) else "CORTE-DESPERDICIO"
                _rect(msp, ox + fx, oy + fy, fw, fl, capa)
        filas = (len(baldosas) + cols - 1) // cols
        y_top = y_top - filas * cellh - 2.0


def dibujar_despiece_extra(msp, modelo, x0, y0):
    """Agrega al DXF el DESPIECE de la ESCALERA (peraltes P#, huellas H#) y del
    ZOCLO (catálogo de corte), a la derecha del plano, como baldosas con sus
    recortes acomodados. Sólo aplica al Moret (acabados de escalera y zoclo)."""
    try:
        import despiece_extra as DE
        from optimizador_recortes import ajustar, empaquetar, PISOS
    except Exception:
        return
    aT, lT = PISOS["Moret"]                       # 0.596 x 1.194
    cols, gx, gy = 6, aT + 0.30, lT + 0.55

    def _baldosa(cx, cy, etq, piezas, libres):
        _rect(msp, cx, cy - lT, aT, lT, "CORTE-TILE")
        for (px, py, pw, pl, pid, rot) in piezas:
            _rect(msp, cx + px, cy - lT + py, pw, pl, "CORTE-RECORTE")
            _txt(msp, pid, cx + px + pw / 2, cy - lT + py + pl / 2, 0.045, "CORTE-TEXTO")
        for (fx, fy, fw, fl, *_z) in libres:
            if fw > 0.03 and fl > 0.03:
                _rect(msp, cx + fx, cy - lT + fy, fw, fl, "CORTE-SOBRANTE")
        _txt(msp, etq, cx + aT / 2, cy + 0.07, 0.06, "CORTE-TEXTO")

    # ---- ESCALERA ----
    res = DE.escalera_resumen(modelo)
    recortes = [p for p in res["piezas"] if not p["completa"]]
    enteras = [p for p in res["piezas"] if p["completa"]]
    entradas = [(*ajustar(p["ancho"], p["largo"], aT, lT), p["id"]) for p in recortes]
    baldosas = empaquetar(entradas, "Moret", 0.0, True)
    _txt(msp, f"DESPIECE ESCALERA (ancho 1.15, peralte 0.175, huella 0.27) - {res['n_escalones']} escalones",
         x0, y0 + 0.5, 0.16, "CORTE-TEXTO")
    n = 0
    for b in baldosas:
        cx = x0 + (n % cols) * gx; cy = y0 - (n // cols) * gy
        _baldosa(cx, cy, f"B{n+1}", b.piezas, b.libres); n += 1
    for p in enteras:
        cx = x0 + (n % cols) * gx; cy = y0 - (n // cols) * gy
        _rect(msp, cx, cy - lT, aT, lT, "CORTE-TILE")
        _txt(msp, p["id"], cx + aT / 2, cy - lT / 2, 0.06, "CORTE-TEXTO")
        _txt(msp, f"B{n+1}", cx + aT / 2, cy + 0.07, 0.06, "CORTE-TEXTO"); n += 1
    filas_esc = (n + cols - 1) // cols

    # ---- ZOCLO Moret (catálogo: 4 tiras de 0.149 por baldosa) ----
    yz = y0 - filas_esc * gy - 0.8
    _txt(msp, "DESPIECE ZOCLO MORET (4 tiras de 0.149 x 1.194 por baldosa)",
         x0, yz + 0.5, 0.16, "CORTE-TEXTO")
    _rect(msp, x0, yz - lT, aT, lT, "CORTE-TILE")
    for i in range(4):
        _rect(msp, x0 + i * 0.149, yz - lT, 0.149, lT, "CORTE-RECORTE")
        _txt(msp, f"Z{i+1}", x0 + i * 0.149 + 0.07, yz - lT / 2, 0.05, "CORTE-TEXTO")


def exportar(modelo):
    piezas = cargar_anotado(modelo)
    doc = ezdxf.new("R2000", setup=True)   # R2000 = máxima compatibilidad (AutoCAD 2000+)
    doc.units = ezdxf.units.M
    msp = doc.modelspace()
    for nombre, color in LAYERS.items():
        doc.layers.add(nombre).color = color

    # --- Plano: piezas + IDs ---
    for p in piezas:
        x0, y0, w, h = p["x0"], p["y0"], p["wx"], p["hy"]
        if p.get("notch"):
            _contorno_notch(msp, p, CAPA[p["material"]])
        else:
            _rect(msp, x0, y0, w, h, CAPA[p["material"]])
        th = min(max(0.022, min(w, h) * 0.22), 0.055)
        _txt(msp, p["id"], p["x"], p["y"], th, "ETIQUETAS")

    # --- Acabados: zoclo + zonas de Urbania / regaderas ---
    dibujar_acabados(msp, modelo)

    # --- Mapa de sobrantes (sobre el plano, saliendo hacia afuera) ---
    dibujar_mapa_sobrantes(msp, piezas)

    # --- Plan de corte (debajo del plano) ---
    minx = min(p["x0"] for p in piezas)
    miny = min(p["y0"] for p in piezas)
    maxx = max(p["x0"] + p["wx"] for p in piezas)
    maxy = max(p["y0"] + p["hy"] for p in piezas)
    dibujar_plan_corte(msp, piezas, minx, miny)

    # --- Despiece de ESCALERA y ZOCLO (a la derecha del plano) ---
    dibujar_despiece_extra(msp, modelo, maxx + 3.0, maxy)

    dxf = f"Viñas Norte - {modelo}.dxf"
    dwg = f"Viñas Norte - {modelo}.dwg"
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
