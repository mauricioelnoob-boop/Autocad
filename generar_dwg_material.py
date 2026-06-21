#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generar_dwg_material.py
=======================

Genera, por material, un archivo DXF (luego convertido a DWG) con TODO el
trabajo en un solo dibujo para AutoCAD:

  * El plano de la casa con ese piso identificado por pieza (el otro piso va
    tenue, sólo de contexto).
  * Abajo, el despiece de los recortes: cada baldosa que se corta, con las
    piezas (a dónde van) y el sobrante coloreado (amarillo = reutilizable,
    rojo = desperdicio).
  * Un cuadro con el resumen y la firma del responsable.

Capas para que puedas prender/apagar lo que necesites.

Salidas:  piso_moret.dxf  y  piso_royal_walnut.dxf
(la conversión a .dwg se hace con dxf2dwg de LibreDWG).

Uso:  python3 generar_dwg_material.py
"""

import datetime
from collections import Counter

import ezdxf

from optimizador_recortes import PISOS, CAJAS
from datos_piezas import cargar_anotado, PREF_CORTE
from pdf_material import empacar, es_reutilizable, MIN_REUSABLE

FIRMA = "Ing. Mauricio Gastelum Mora"

# Colores ACI por capa
CAP = {
    "Moret":        {"completa": 8,  "recorte": 30},
    "Royal Walnut": {"completa": 9,  "recorte": 4},
}
ACI_CONTEXTO = 254
ACI_PIEZA = 3          # verde: pieza que se corta
ACI_SOBRANTE = 2       # amarillo
ACI_DESPERDICIO = 1    # rojo
ACI_TEXTO = 7
ACI_TITULO = 5


def rect(msp, x, y, w, h, layer):
    msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
                       close=True, dxfattribs={"layer": layer})


def relleno(msp, x, y, w, h, layer, aci, trans=0.0):
    hatch = msp.add_hatch(color=aci, dxfattribs={"layer": layer})
    hatch.set_solid_fill(aci)
    hatch.paths.add_polyline_path([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], is_closed=True)
    if trans:
        hatch.transparency = trans


def texto(msp, s, x, y, h, layer, aci=None, rot=0, align="MIDDLE_CENTER"):
    attr = {"layer": layer, "height": h, "rotation": rot}
    if aci is not None:
        attr["color"] = aci
    t = msp.add_text(s, dxfattribs=attr)
    t.set_placement((x, y), align=ezdxf.enums.TextEntityAlignment[align])


def construir_dxf(todas, material, path):
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.M
    msp = doc.modelspace()

    for nombre, aci in [
        (f"PISO-{material}-COMPLETA", CAP[material]["completa"]),
        (f"PISO-{material}-RECORTE", CAP[material]["recorte"]),
        ("CONTEXTO-OTRO-PISO", ACI_CONTEXTO),
        ("ID-PIEZA", ACI_TEXTO),
        ("RECORTE-PIEZA", ACI_PIEZA),
        ("RECORTE-SOBRANTE", ACI_SOBRANTE),
        ("RECORTE-DESPERDICIO", ACI_DESPERDICIO),
        ("RECORTE-TEXTO", ACI_TEXTO),
        ("TITULO", ACI_TITULO),
    ]:
        doc.layers.add(nombre).color = aci

    focal = [p for p in todas if p["material"] == material]
    otro = [p for p in todas if p["material"] != material]
    baldosas, mapa, (anchoB, largoB) = empacar(todas, material)

    # ---------- Plano de la casa ----------
    for p in otro:
        rect(msp, p["x0"], p["y0"], p["wx"], p["hy"], "CONTEXTO-OTRO-PISO")
    for p in focal:
        ly = f"PISO-{material}-{'COMPLETA' if p['completa'] else 'RECORTE'}"
        rect(msp, p["x0"], p["y0"], p["wx"], p["hy"], ly)
        if not p["completa"]:
            relleno(msp, p["x0"], p["y0"], p["wx"], p["hy"], ly, CAP[material]["recorte"], 0.55)
        th = min(max(0.03, min(p["wx"], p["hy"]) * 0.30), 0.09)
        texto(msp, p["id"], p["x"], p["y"], th, "ID-PIEZA",
              rot=0 if p["wx"] >= p["hy"] else 90)

    xs0 = [p["x0"] for p in todas]; ys0 = [p["y0"] for p in todas]
    xs1 = [p["x0"] + p["wx"] for p in todas]; ys1 = [p["y0"] + p["hy"] for p in todas]
    minx, maxx, miny, maxy = min(xs0), max(xs1), min(ys0), max(ys1)

    texto(msp, f"PLANO DE LA CASA - PISO {material.upper()}", (minx + maxx) / 2, maxy + 0.6,
          0.30, "TITULO", ACI_TITULO)

    # ---------- Despiece de recortes (abajo del plano) ----------
    pc = PREF_CORTE[material]
    cols = 22
    cellw = anchoB + 0.18
    cellh = largoB + 0.40
    bx0 = minx
    by0 = miny - 2.5                     # empieza debajo del plano
    texto(msp, f"DESPIECE DE RECORTES - {material.upper()}  "
               f"(verde=pieza, amarillo=sobrante reutilizable, rojo=desperdicio)",
          bx0 + 6, by0 + 0.5, 0.28, "TITULO", ACI_TITULO)

    area_reut = area_desp = 0.0
    reut = Counter(); desp = Counter()
    for i, b in enumerate(baldosas):
        col = i % cols
        row = i // cols
        ox = bx0 + col * cellw
        oy = by0 - (row + 1) * cellh
        rect(msp, ox, oy, anchoB, largoB, "RECORTE-TEXTO")
        texto(msp, f"{pc}-{i+1:02d}", ox + anchoB / 2, oy + largoB + 0.10, 0.07, "RECORTE-TEXTO")
        for (x, y, w, l, pid, rotp) in b.piezas:
            relleno(msp, ox + x, oy + y, w, l, "RECORTE-PIEZA", ACI_PIEZA, 0.35)
            rect(msp, ox + x, oy + y, w, l, "RECORTE-PIEZA")
            dest = mapa.get(pid)
            etq = pid + (f" -> ({dest['x']:.1f},{dest['y']:.1f})" if dest else "")
            texto(msp, etq, ox + x + w / 2, oy + y + l / 2, min(0.05, w / 3.5),
                  "RECORTE-TEXTO", rot=0 if w >= l else 90)
        for (fx, fy, fw, fl) in b.libres:
            if fw <= 0.005 or fl <= 0.005:
                continue
            if es_reutilizable(fw, fl):
                relleno(msp, ox + fx, oy + fy, fw, fl, "RECORTE-SOBRANTE", ACI_SOBRANTE, 0.3)
                rect(msp, ox + fx, oy + fy, fw, fl, "RECORTE-SOBRANTE")
                area_reut += fw * fl
                reut[(round(min(fw, fl), 2), round(max(fw, fl), 2))] += 1
            else:
                relleno(msp, ox + fx, oy + fy, fw, fl, "RECORTE-DESPERDICIO", ACI_DESPERDICIO, 0.3)
                rect(msp, ox + fx, oy + fy, fw, fl, "RECORTE-DESPERDICIO")
                area_desp += fw * fl
                desp[(round(min(fw, fl), 2), round(max(fw, fl), 2))] += 1

    filas_baldosas = (len(baldosas) + cols - 1) // cols
    base_y = by0 - filas_baldosas * cellh - 1.5

    # ---------- Cuadro resumen + firma ----------
    completas = sum(1 for p in focal if p["completa"])
    total = completas + len(baldosas)
    cfg = CAJAS[material]
    cajas = -(-total // cfg["pzas_caja"])
    fecha = datetime.date.today().strftime("%d/%m/%Y")
    lineas = [
        f"PISO {material.upper()}",
        f"Piezas completas: {completas}    Baldosas para recortes: {len(baldosas)}",
        f"Total de piezas: {total}    Cajas: {cajas}    ({cajas*cfg['m2_caja']:.2f} m2)",
        f"Sobrante reutilizable: {area_reut:.2f} m2    Desperdicio: {area_desp:.2f} m2",
        "",
        f"Elaboro: {FIRMA}        Fecha: {fecha}",
    ]
    for k, ln in enumerate(lineas):
        texto(msp, ln, minx, base_y - k * 0.45, 0.22 if k == 0 else 0.18,
              "TITULO", ACI_TITULO, align="MIDDLE_LEFT")
    doc.saveas(path)
    return total, cajas, area_reut, area_desp


def main():
    todas = cargar_anotado()
    for material, path in [("Moret", "piso_moret.dxf"),
                           ("Royal Walnut", "piso_royal_walnut.dxf")]:
        total, cajas, reut, desp = construir_dxf(todas, material, path)
        print(f"{material}: {total} piezas / {cajas} cajas  ·  reutilizable {reut:.2f} m²  ·  "
              f"desperdicio {desp:.2f} m²  ->  {path}")


if __name__ == "__main__":
    main()
