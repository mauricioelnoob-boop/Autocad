#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exportar_dwg.py
===============

Exporta el despiece de un modelo a un DXF (+DWG) EDITABLE para AutoCAD.

Capas (todas prendibles/apagables por separado, nombres limpios):
  MORET-COMPLETAS       -> UNA polilínea por pieza COMPLETA de Moret
                           (contarlas = contar entidades de esta capa, QSELECT)
  MORET-RECORTES        -> piezas de Moret que llevan corte
  ROYAL-COMPLETAS       -> UNA polilínea por pieza completa de Royal Walnut
  ROYAL-RECORTES        -> piezas de Royal Walnut que llevan corte
  ETIQUETAS             -> ID de cada pieza del plano (texto)

  PLAN-CORTE-TABLAS     -> contorno de cada pieza entera que se abre para cortar
  PLAN-CORTE-PIEZAS     -> el recorte ya ACOMODADO dentro de su pieza
  PLAN-CORTE-SOBRANTES  -> sobrante reutilizable (amarillo) con su medida y destino
  PLAN-CORTE-DESPERDICIO-> desperdicio (muy corto)
  PLAN-CORTE-TEXTOS     -> etiquetas del plan de corte (texto)
  RESUMEN               -> conteo de piezas completas / tablas / cajas y m2 de
                           sobrante-desperdicio, para revisión de compra

El "plan de corte" se dibuja DEBAJO del plano: cada pieza que hay que abrir,
con el/los recorte(s) que salen de ella ya puestos en su lugar. Así ves, pieza
por pieza, qué se corta y de dónde sale — todo en su propio layer.

MEDIDA REAL: los planos de origen dibujan la celda pieza+junta (p.ej. 0.600 /
1.200); aquí cada pieza del plano se dibuja a su MEDIDA REAL 0.596 x 1.194
(la junta de ~4 mm queda visible entre piezas), para que al medir en AutoCAD
salga la medida física del vitropiso.

Nota (obs. de supervisión): ya NO se dibujan tablones completos "imaginarios"
sobre el plano (antes capa morada SOBRANTES-MAPA): se encimaban con las piezas
completas. Los sobrantes viven únicamente en el plan de corte, cada uno con su
medida y a dónde va (GUARDAR EN RESERVA); los recortes que salen del sobrante
de otra pieza lo dicen en su etiqueta.

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

CAPA = {("Moret", True): "MORET-COMPLETAS", ("Moret", False): "MORET-RECORTES",
        ("Royal Walnut", True): "ROYAL-COMPLETAS", ("Royal Walnut", False): "ROYAL-RECORTES"}
LAYERS = {
    "MORET-COMPLETAS": 30, "MORET-RECORTES": 41,
    "ROYAL-COMPLETAS": 4, "ROYAL-RECORTES": 151, "ETIQUETAS": 7,
    "PLAN-CORTE-TABLAS": 7, "PLAN-CORTE-PIEZAS": 3, "PLAN-CORTE-SOBRANTES": 2,
    "PLAN-CORTE-DESPERDICIO": 1, "PLAN-CORTE-TEXTOS": 5, "RESUMEN": 5,
    "ZOCLO": 3, "URBANIA-LAVANDERIA": 5, "REGADERA-MALLA-MURO": 1,
}


def _dim_real(v, material):
    """Convierte una medida de CELDA del dibujo (pieza+junta) a la medida REAL
    de la pieza: 0.600->0.596, 1.200->1.194 (tolerancia 12 mm, igual que
    ajustar()/_retipo()). Las medidas parciales (recortes) no se tocan."""
    aw, al = PISOS[material]
    for t in (aw, al):
        if 0 < v - t <= 0.012:
            return t
    return v


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


def _txt(msp, s, x, y, h, layer, rot=0):
    t = msp.add_text(s, dxfattribs={"layer": layer, "height": h, "rotation": rot})
    t.set_placement((x, y), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)


def _fmt(v):
    """Medida con precisión real y sin ceros de sobra: 0.596 -> '0.596',
    0.41 -> '0.41', 1.194 -> '1.194' (nunca redondea 0.596 a 0.60)."""
    return f"{v:.3f}".rstrip("0").rstrip(".")


def _etq_sobrante(msp, ox, oy, fx, fy, fw, fl):
    """Etiqueta un sobrante reutilizable con su MEDIDA y su DESTINO (a reserva).
    El texto se adapta al tamaño del hueco para no encimarse con nada."""
    lado_c, lado_l = min(fw, fl), max(fw, fl)
    rot = 0 if fw >= fl else 90
    if lado_l > 0.55 and lado_c > 0.055:
        s = f"SOBRA {_fmt(fw)}x{_fmt(fl)} -> GUARDAR"
    elif lado_l > 0.28 and lado_c > 0.045:
        s = f"SOBRA {_fmt(fw)}x{_fmt(fl)}"
    elif lado_l > 0.14 and lado_c > 0.04:
        s = "SOBRA"
    else:
        return
    _txt(msp, s, ox + fx + fw / 2, oy + fy + fl / 2,
         min(0.045, lado_c * 0.45, lado_l / (len(s) * 0.75)), "PLAN-CORTE-TEXTOS", rot)


def dibujar_plan_corte(msp, piezas, x0_plan, y0_plan):
    """Dibuja, debajo del plano, cada pieza que se abre con sus recortes puestos."""
    y_top = y0_plan - 2.0
    for material in ("Moret", "Royal Walnut"):
        baldosas, mapa, (anchoB, largoB) = empacar(piezas, material)
        if not baldosas:
            continue
        pc = PREF_CORTE[material]
        cols = 22
        cellw = anchoB + 0.45          # más separación horizontal
        cellh = largoB + 0.70          # más separación vertical (texto no se encima)
        _txt(msp, f"PLAN DE CORTE - {material.upper()}  ({len(baldosas)} piezas a abrir; "
                  f"amarillo = SOBRANTE con su medida -> GUARDAR EN RESERVA; rojo = desperdicio)",
             x0_plan + 6, y_top + 0.5, 0.25, "PLAN-CORTE-TEXTOS")
        for i, b in enumerate(baldosas):
            col = i % cols
            row = i // cols
            ox = x0_plan + col * cellw
            oy = y_top - (row + 1) * cellh
            _rect(msp, ox, oy, anchoB, largoB, "PLAN-CORTE-TABLAS")
            _txt(msp, f"{pc}-{i+1:02d}", ox + anchoB / 2, oy + largoB + 0.14, 0.06, "PLAN-CORTE-TEXTOS")
            for (x, y, w, l, pid, rot), (origen, orden) in zip(b.piezas, b.meta):
                _rect(msp, ox + x, oy + y, w, l, "PLAN-CORTE-PIEZAS")
                etq = pid if origen == "TABLA" else f"{pid} (DE SOBRA DE {origen.split()[0]})"
                _txt(msp, etq, ox + x + w / 2, oy + y + l / 2,
                     min(0.035, w / 4.5, max(w, l) / (len(etq) * 0.72)), "PLAN-CORTE-TEXTOS",
                     rot=0 if w >= l else 90)
            for (fx, fy, fw, fl, *_z) in b.libres:
                if fw <= 0.005 or fl <= 0.005:
                    continue
                if es_reutilizable(fw, fl):
                    _rect(msp, ox + fx, oy + fy, fw, fl, "PLAN-CORTE-SOBRANTES")
                    _etq_sobrante(msp, ox, oy, fx, fy, fw, fl)
                else:
                    _rect(msp, ox + fx, oy + fy, fw, fl, "PLAN-CORTE-DESPERDICIO")
        filas = (len(baldosas) + cols - 1) // cols
        y_top = y_top - filas * cellh - 2.0
    return y_top


def dibujar_resumen(msp, piezas, modelo, x0, y0):
    """Cuadro RESUMEN (capa RESUMEN): piezas COMPLETAS, tablas abiertas para
    recorte, TOTAL de piezas y cajas por material, y el desglose de sobrante
    reutilizable vs desperdicio. Mismos números que el PDF y los generadores,
    para revisar la compra y justificar el porcentaje de desperdicio."""
    import math
    import datetime
    from optimizador_recortes import CAJAS
    lineas = [f"RESUMEN DE PIEZAS - {modelo.upper()}", ""]
    for material in ("Moret", "Royal Walnut"):
        focal = [p for p in piezas if p["material"] == material]
        if not focal:
            continue
        completas = sum(1 for p in focal if p["completa"])
        baldosas, _, (aB, lB) = empacar(piezas, material)
        extra_comp = 0
        extra_bald = []
        if material == "Moret":
            try:
                import despiece_extra as DE
                from optimizador_recortes import ajustar as _aj, empaquetar as _emp
                for res in (DE.regadera_resumen(modelo), DE.escalera_resumen(modelo)):
                    extra_comp += res["completas"]
                    ent = [(*_aj(p["ancho"], p["largo"], aB, lB),
                            p.get("id") or p.get("pared") or "extra")
                           for p in res["piezas"] if not p["completa"]]
                    extra_bald += _emp(ent, material, 0.0, True)
            except Exception:
                extra_comp = 0
                extra_bald = []
        bald_all = baldosas + extra_bald
        area_reut = area_desp = 0.0
        n_sob = n_desp = 0
        for b in bald_all:
            for (fx, fy, fw, fl, *_z) in b.libres:
                if fw <= 0.005 or fl <= 0.005:
                    continue
                if es_reutilizable(fw, fl):
                    area_reut += fw * fl
                    n_sob += 1
                else:
                    area_desp += fw * fl
                    n_desp += 1
        total = completas + extra_comp + len(bald_all)
        cfg = CAJAS[material]
        cajas = math.ceil(total / cfg["pzas_caja"])
        m2_comprados = cajas * cfg["m2_caja"]
        pct = 100.0 * (area_reut + area_desp) / m2_comprados if m2_comprados else 0.0
        nota_extra = ("  (incluye muro de regadera y escalera)"
                      if material == "Moret" and (extra_comp or extra_bald) else "")
        capa_comp = CAPA[(material, True)]
        lineas += [
            f"{material.upper()}{nota_extra}:",
            f"  PIEZAS COMPLETAS: {completas + extra_comp}   [en plano: {completas} = entidades de la capa {capa_comp}"
            + (f"; extras regadera/escalera: {extra_comp}]" if extra_comp else "]"),
            f"  PIEZAS ABIERTAS P/RECORTES: {len(bald_all)}   |   TOTAL DE PIEZAS: {total}"
            f"   |   CAJAS: {cajas} ({m2_comprados:.2f} m2)",
            f"  SOBRANTE REUTILIZABLE: {area_reut:.2f} m2 en {n_sob} pzas -> GUARDAR EN RESERVA"
            f"   |   DESPERDICIO: {area_desp:.2f} m2 ({n_desp} pedazos <10 cm)"
            f"   |   SOBRA TOTAL: {pct:.1f}% de lo comprado",
            "",
        ]
    lineas += [
        "CONTEO RAPIDO EN AUTOCAD: QSELECT (polilinea) por capa MORET-COMPLETAS o ROYAL-COMPLETAS:",
        "1 polilinea = 1 pieza completa. Las piezas estan a MEDIDA REAL 0.596 x 1.194 (junta visible).",
        "",
        f"Elaboro: Ing. Mauricio Gastelum Mora   -   {datetime.date.today().strftime('%d/%m/%Y')}",
    ]
    for k, ln in enumerate(lineas):
        h = 0.24 if k == 0 else 0.15
        t = msp.add_text(ln, dxfattribs={"layer": "RESUMEN", "height": h})
        t.set_placement((x0, y0 - k * 0.42), align=ezdxf.enums.TextEntityAlignment.MIDDLE_LEFT)


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
        _rect(msp, cx, cy - lT, aT, lT, "PLAN-CORTE-TABLAS")
        for (px, py, pw, pl, pid, rot) in piezas:
            _rect(msp, cx + px, cy - lT + py, pw, pl, "PLAN-CORTE-PIEZAS")
            _txt(msp, pid, cx + px + pw / 2, cy - lT + py + pl / 2, 0.045, "PLAN-CORTE-TEXTOS")
        for (fx, fy, fw, fl, *_z) in libres:
            if fw > 0.03 and fl > 0.03:
                _rect(msp, cx + fx, cy - lT + fy, fw, fl, "PLAN-CORTE-SOBRANTES")
                _etq_sobrante(msp, cx, cy - lT, fx, fy, fw, fl)
        _txt(msp, etq, cx + aT / 2, cy + 0.07, 0.06, "PLAN-CORTE-TEXTOS")

    # ---- ESCALERA ----
    res = DE.escalera_resumen(modelo)
    recortes = [p for p in res["piezas"] if not p["completa"]]
    enteras = [p for p in res["piezas"] if p["completa"]]
    entradas = [(*ajustar(p["ancho"], p["largo"], aT, lT), p["id"]) for p in recortes]
    baldosas = empaquetar(entradas, "Moret", 0.0, True)
    _txt(msp, f"DESPIECE ESCALERA (ancho 1.15, peralte 0.175, huella 0.27) - {res['n_escalones']} escalones",
         x0, y0 + 0.5, 0.16, "PLAN-CORTE-TEXTOS")
    n = 0
    for b in baldosas:
        cx = x0 + (n % cols) * gx; cy = y0 - (n // cols) * gy
        _baldosa(cx, cy, f"B{n+1}", b.piezas, b.libres); n += 1
    for p in enteras:
        cx = x0 + (n % cols) * gx; cy = y0 - (n // cols) * gy
        _rect(msp, cx, cy - lT, aT, lT, "PLAN-CORTE-TABLAS")
        _txt(msp, p["id"], cx + aT / 2, cy - lT / 2, 0.06, "PLAN-CORTE-TEXTOS")
        _txt(msp, f"B{n+1}", cx + aT / 2, cy + 0.07, 0.06, "PLAN-CORTE-TEXTOS"); n += 1
    filas_esc = (n + cols - 1) // cols

    # ---- ZOCLO Moret (catálogo: 4 tiras de 0.148 por baldosa, cortadora diamante) ----
    import generadores as _G
    H = _G.ZOCLO_ALTO          # 0.148
    KERF = _G.ZOCLO_KERF       # 0.0 (cortadora de diamante: rayar y tronchar)
    yz = y0 - filas_esc * gy - 0.8
    _txt(msp, "DESPIECE ZOCLO MORET (4 tiras de 0.148 x 1.194 por pieza; cortadora de diamante kerf~0, holgura para calibre 0.594-0.596)",
         x0, yz + 0.5, 0.16, "PLAN-CORTE-TEXTOS")
    _rect(msp, x0, yz - lT, aT, lT, "PLAN-CORTE-TABLAS")
    for i in range(4):
        _rect(msp, x0 + i * (H + KERF), yz - lT, H, lT, "PLAN-CORTE-PIEZAS")
        _txt(msp, f"Z{i+1}", x0 + i * (H + KERF) + H / 2, yz - lT / 2, 0.05, "PLAN-CORTE-TEXTOS")


def exportar(modelo):
    piezas = cargar_anotado(modelo)
    doc = ezdxf.new("R2000", setup=True)   # R2000 = máxima compatibilidad (AutoCAD 2000+)
    doc.units = ezdxf.units.M
    msp = doc.modelspace()
    for nombre, color in LAYERS.items():
        doc.layers.add(nombre).color = color

    # --- Plano: piezas + IDs (a MEDIDA REAL: la junta queda entre piezas) ---
    for p in piezas:
        capa = CAPA[(p["material"], bool(p["completa"]))]
        x0, y0 = p["x0"], p["y0"]
        if p.get("notch"):
            _contorno_notch(msp, p, capa)     # contorno real con entrante, sin encoger
            w, h = p["wx"], p["hy"]
        else:
            w = _dim_real(p["wx"], p["material"])
            h = _dim_real(p["hy"], p["material"])
            _rect(msp, x0, y0, w, h, capa)
        th = min(max(0.022, min(w, h) * 0.22), 0.055)
        _txt(msp, p["id"], p["x"], p["y"], th, "ETIQUETAS")

    # --- Acabados: zoclo + zonas de Urbania / regaderas ---
    dibujar_acabados(msp, modelo)

    # --- Plan de corte (debajo del plano) ---
    minx = min(p["x0"] for p in piezas)
    miny = min(p["y0"] for p in piezas)
    maxx = max(p["x0"] + p["wx"] for p in piezas)
    maxy = max(p["y0"] + p["hy"] for p in piezas)
    y_fin = dibujar_plan_corte(msp, piezas, minx, miny)

    # --- Cuadro RESUMEN (conteo de completas / tablas / cajas / sobra) ---
    dibujar_resumen(msp, piezas, modelo, minx, (y_fin if y_fin is not None else miny - 4.0) - 0.6)

    # --- Despiece de ESCALERA y ZOCLO (a la derecha del plano) ---
    dibujar_despiece_extra(msp, modelo, maxx + 3.0, maxy)

    # Nombre ASCII (sin ñ) para los CAD: evita que AutoCAD falle al resolver la
    # ruta por el carácter especial. Los PDF/Excel sí conservan "Viñas".
    dxf = f"Vinas Norte - {modelo}.dxf"
    dwg = f"Vinas Norte - {modelo}.dwg"
    doc.saveas(dxf)
    if os.path.exists(DXF2DWG):
        subprocess.run([DXF2DWG, "-y", "-o", dwg, dxf], check=True, stderr=subprocess.DEVNULL)
        print(f"DWG editable: {dwg}")
    else:
        print(f"(no se encontró dxf2dwg; queda el DXF: {dxf})")
    nrec = sum(1 for p in piezas if not p["completa"])
    print(f"DXF editable: {dxf}")
    print(f"Piezas en el plano: {len(piezas)}  (completas: {len(piezas)-nrec}, recortes: {nrec})")
    print("Capas: MORET-COMPLETAS/RECORTES, ROYAL-COMPLETAS/RECORTES, ETIQUETAS, "
          "PLAN-CORTE-TABLAS/PIEZAS/SOBRANTES/DESPERDICIO/TEXTOS, RESUMEN "
          "(piezas a medida real 0.596x1.194; sin capa morada)")


if __name__ == "__main__":
    exportar(sys.argv[1] if len(sys.argv) > 1 else "Cabernet")
