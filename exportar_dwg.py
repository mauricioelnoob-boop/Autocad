#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exportar_dwg.py
===============

Exporta el despiece de un modelo a un DXF (+DWG) EDITABLE para AutoCAD.

Capas: ver LEYENDA_CAPAS abajo (la misma leyenda se escribe DENTRO del DXF, en
la capa RESUMEN, para que cualquiera sepa qué es cada layer sin abrir el código).

El "plan de corte" se dibuja DEBAJO del plano: cada pieza que hay que abrir,
con el/los recorte(s) que salen de ella ya puestos en su lugar, numerada en el
ORDEN DE CORTE PROPUESTO: M-01 es el primer corte (PLANTA ALTA junto a la
ESCALERA, por ahí sube el material) y se avanza alejándose; al terminar P.A.
se sigue con P.B.

SOBRANTE-JUNTO-AL-RECORTE: a cada recorte del plano se le dibuja pegado, en
amarillo, el sobrante que completa la pieza entera (puede salir de los muros);
se elige la posición que menos se encima con otros sobrantes amarillos.

MEDIDA REAL: los planos de origen dibujan la celda pieza+junta (p.ej. 0.600 /
1.200); aquí cada pieza del plano se dibuja a su MEDIDA REAL 0.596 x 1.194
(la junta de ~4 mm queda visible entre piezas), para que al medir en AutoCAD
salga la medida física del vitropiso.

Nota (obs. de supervisión): no hay capa morada de tablones imaginarios.

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
    "MORET-COMPLETAS": 30, "MORET-RECORTES": 40,
    "ROYAL-COMPLETAS": 4, "ROYAL-RECORTES": 140, "ETIQUETAS": 7,
    "MUROS": 8, "SOBRANTE-JUNTO-AL-RECORTE": 2,
    "PLAN-CORTE-PIEZAS-A-ABRIR": 7, "PLAN-CORTE-RECORTES": 3, "PLAN-CORTE-SOBRANTES": 2,
    "PLAN-CORTE-DESPERDICIO": 1, "PLAN-CORTE-TEXTOS": 5, "RESUMEN": 5,
    "ZOCLO": 3, "URBANIA-LAVANDERIA": 5, "REGADERA-MALLA-MURO": 1,
}

# Variante "fusionada" (segundo ZIP): una sola capa por material con TODAS las
# piezas completas que se COMPRAN (enteras + las que se abren para recorte),
# para contarlas con un solo QSELECT; los FALTANTES (recortes que salen de un
# sobrante, los morados del PDF) van aparte y no suman piezas.
LAYERS_FUSIONADO = {
    "MORET": 30, "MORET-FALTANTES": 6,
    "ROYAL": 4, "ROYAL-FALTANTES": 200, "ETIQUETAS": 7,
    "MUROS": 8, "SOBRANTE-JUNTO-AL-RECORTE": 2,
    "PLAN-CORTE-PIEZAS-A-ABRIR": 7, "PLAN-CORTE-RECORTES": 3, "PLAN-CORTE-SOBRANTES": 2,
    "PLAN-CORTE-DESPERDICIO": 1, "PLAN-CORTE-TEXTOS": 5, "RESUMEN": 5,
    "ZOCLO": 3, "URBANIA-LAVANDERIA": 5, "REGADERA-MALLA-MURO": 1,
}

# Qué es cada capa (esta leyenda también se escribe DENTRO del DXF, capa RESUMEN):
LEYENDA_CAPAS = [
    ("MORET-COMPLETAS", "piezas COMPLETAS de Moret en el plano; 1 polilinea = 1 pieza (contar con QSELECT)"),
    ("MORET-RECORTES", "piezas de Moret que llevan corte, en su posicion real del plano"),
    ("ROYAL-COMPLETAS", "piezas completas de Royal Walnut; 1 polilinea = 1 pieza"),
    ("ROYAL-RECORTES", "piezas de Royal Walnut que llevan corte"),
    ("ETIQUETAS", "ID de cada pieza del plano (PB/PA - M/R - numero)"),
    ("MUROS", "muros REALES del plano de origen (capa A-MUROS del DWG), con su grosor"),
    ("SOBRANTE-JUNTO-AL-RECORTE", "amarillo PEGADO a cada recorte del plano: lo que le falta al recorte"
                                  " para completar la pieza entera (puede salir de los muros)"),
]

LEYENDA_CAPAS_FUSIONADO = [
    ("MORET", "TODAS las piezas de Moret que se COMPRAN: enteras + las que se abren para recorte;"
              " 1 polilinea = 1 pieza completa a colocar o recortar (contar con QSELECT)"),
    ("MORET-FALTANTES", "recortes que salen del SOBRANTE de otra pieza: NO abren pieza nueva"
                        " (los morados del PDF); no suman al conteo de piezas"),
    ("ROYAL", "TODAS las piezas de Royal Walnut que se compran (enteras + abiertas p/recorte)"),
    ("ROYAL-FALTANTES", "recortes de Royal que salen de un sobrante: no abren pieza nueva"),
    ("ETIQUETAS", "ID de cada pieza del plano (PB/PA - M/R - numero)"),
    ("MUROS", "muros REALES del plano de origen (capa A-MUROS del DWG), con su grosor"),
    ("SOBRANTE-JUNTO-AL-RECORTE", "amarillo PEGADO a cada recorte del plano: lo que le falta al recorte"
                                  " para completar la pieza entera (puede salir de los muros)"),
]

LEYENDA_COMUN = [
    ("PLAN-CORTE-PIEZAS-A-ABRIR", "plan de corte: contorno de cada pieza ENTERA que se abre (M-01, M-02...)"),
    ("PLAN-CORTE-RECORTES", "plan de corte: los recortes ya acomodados dentro de su pieza"),
    ("PLAN-CORTE-SOBRANTES", "plan de corte: sobrante reutilizable de cada pieza, con medida y destino"),
    ("PLAN-CORTE-DESPERDICIO", "plan de corte: pedazos <10 cm que ya no sirven"),
    ("PLAN-CORTE-TEXTOS", "textos del plan de corte (numeracion y etiquetas)"),
    ("RESUMEN", "conteos (completas / piezas a abrir / cajas), % de sobra y esta leyenda"),
    ("ZOCLO", "linea de zoclo sobre el perimetro de piso"),
    ("URBANIA-LAVANDERIA", "marca de la zona con piso Urbania (lavanderia)"),
    ("REGADERA-MALLA-MURO", "marca de regaderas (malla en charola + muro Moret)"),
]


def _dim_real(v, material):
    """Convierte una medida de CELDA del dibujo (pieza+junta) a la medida REAL
    de la pieza: 0.600->0.596, 1.200->1.194 (tolerancia 12 mm, igual que
    ajustar()/_retipo()). Las medidas parciales (recortes) no se tocan."""
    aw, al = PISOS[material]
    for t in (aw, al):
        if 0 < v - t <= 0.012:
            return t
    return v


# Boquilla REAL entre piezas (medida en obra): Moret 2 mm, Royal Walnut 1 mm.
BOQUILLA = {"Moret": 0.002, "Royal Walnut": 0.001}


def _relayar_juntas(piezas):
    """Devuelve una COPIA de las piezas re-tendida con la BOQUILLA REAL para el
    DXF: 2 mm entre piezas de Moret y 1 mm en Royal Walnut (los planos de
    origen de Cabernet/Chardonnay traen retícula nominal 0.602/1.202 que deja
    6-8 mm; Merlot ya viene a paso real y no se mueve).

    Cada corrida contigua (fila o columna) se re-tiende desde su PRIMERA pieza
    (el lado del muro): pieza a medida real + boquilla. Si la corrida termina
    en RECORTE, ese recorte conserva su borde lejano (en obra el corte real
    absorbe la diferencia); si termina en pieza completa, la holgura queda en
    el perímetro (la tapa el zoclo). Las piezas con entrante de muro no se
    mueven (anclan contra su muro)."""
    ps = [dict(p) for p in piezas]
    for eje in ("x", "y"):
        a0, w = ("x0", "wx") if eje == "x" else ("y0", "hy")
        o0 = "y0" if eje == "x" else "x0"
        for mat in ("Moret", "Royal Walnut"):
            J = BOQUILLA[mat]
            grupo = sorted([p for p in ps if p["material"] == mat],
                           key=lambda p: p[o0])
            if not grupo:
                continue
            filas = [[grupo[0]]]
            for p in grupo[1:]:
                if p[o0] - filas[-1][-1][o0] <= 0.03:
                    filas[-1].append(p)
                else:
                    filas.append([p])
            for fila in filas:
                fila.sort(key=lambda p: p[a0])
                runs = [[fila[0]]]
                for p in fila[1:]:
                    prev = runs[-1][-1]
                    contigua = p[a0] - (prev[a0] + prev[w]) <= 0.02
                    if contigua and not p.get("notch") and not prev.get("notch"):
                        runs[-1].append(p)
                    else:
                        runs.append([p])
                for run in runs:
                    if run[0].get("notch"):
                        continue                      # ancla: no se mueve
                    cursor = run[0][a0]
                    for k, p in enumerate(run):
                        borde_lejano = p[a0] + p[w]
                        p[a0] = round(cursor, 4)
                        if k == len(run) - 1 and not p["completa"] and k > 0:
                            # el recorte del final absorbe la diferencia
                            p[w] = round(max(borde_lejano - p[a0], 0.02), 4)
                        else:
                            p[w] = round(_dim_real(p[w], mat), 4)
                        cursor = p[a0] + p[w] + J
    for p in ps:
        p["x"] = round(p["x0"] + p["wx"] / 2, 4)
        p["y"] = round(p["y0"] + p["hy"] / 2, 4)
    return ps


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
    # MUROS reales, sacados del plano de origen (capa A-MUROS del DWG): así se
    # revisan las piezas contra el grosor del muro directamente en AutoCAD.
    for a, b in muros:
        msp.add_line(a, b, dxfattribs={"layer": "MUROS"})
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


def dibujar_sobrantes_en_plano(msp, piezas, modelo):
    """Capa SOBRANTE-JUNTO-AL-RECORTE: a cada recorte del plano que se corta de
    pieza NUEVA se le dibuja PEGADO, en amarillo, el sobrante que le falta para
    completar la pieza entera (0.596 x 1.194). Se acomoda hacia AFUERA de la
    casa (puede salir de los muros) y se elige, de las 4 posiciones posibles,
    la que MENOS se encima: primero con otros amarillos, luego con las PIEZAS
    del plano (para no taparlas). Cada tira lleva su etiqueta 'SOBRA DE <id>'
    para que nunca se confunda con una pieza."""
    try:
        from shapely.geometry import box as _box
        from shapely.ops import unary_union as _uni
    except Exception:
        return
    # qué recortes abren pieza nueva (los que salen de un sobrante no la abren)
    origen_de = {}
    for material in ("Moret", "Royal Walnut"):
        baldosas, _, _dims = empacar(piezas, material, modelo)
        for b in baldosas:
            for (x, y, w, l, etq, rot), (origen, orden) in zip(b.piezas, b.meta):
                origen_de[etq] = origen
    cx = sum(p["x"] for p in piezas) / len(piezas)
    cy = sum(p["y"] for p in piezas) / len(piezas)
    todas = _uni([_box(p["x0"], p["y0"], p["x0"] + p["wx"], p["y0"] + p["hy"])
                  for p in piezas])
    puestos = None                       # unión de amarillos ya colocados
    pend = [p for p in piezas
            if not p["completa"] and origen_de.get(p["id"], "TABLA") == "TABLA"]
    # primero los recortes de la orilla (lejos del centro): toman su lado de
    # afuera y dejan el interior más libre para los que no tienen opción
    pend.sort(key=lambda p: -((p["x"] - cx) ** 2 + (p["y"] - cy) ** 2))
    for p in pend:
        aw, al = PISOS[p["material"]]
        if p["wx"] <= aw + 0.012:
            Wt, Lt = aw, al              # pieza parada (como se tiende el piso)
        else:
            Wt, Lt = al, aw              # pieza acostada
        Wt, Lt = max(Wt, p["wx"]), max(Lt, p["hy"])
        rec = _box(p["x0"], p["y0"], p["x0"] + p["wx"], p["y0"] + p["hy"])
        cands = []
        for tx in {p["x0"], p["x0"] + p["wx"] - Wt}:
            for ty in {p["y0"], p["y0"] + p["hy"] - Lt}:
                sob = _box(tx, ty, tx + Wt, ty + Lt).difference(rec)
                if sob.is_empty:
                    continue
                enc = sob.intersection(puestos).area if puestos is not None else 0.0
                tapa = sob.intersection(todas).area      # cuánto tapa a las piezas
                sc = sob.centroid
                afuera = (sc.x - cx) ** 2 + (sc.y - cy) ** 2
                cands.append((round(enc, 5), round(tapa, 4), -afuera, tx, ty, sob))
        if not cands:
            continue
        enc, _tp, _na, tx, ty, sob = min(cands)
        # dos tiras que completan la pieza: vertical (ancho faltante, alto total)
        # y horizontal (ancho del recorte, largo faltante)
        tiras = []
        if Wt - p["wx"] > 0.02:
            ox = (p["x0"] + p["wx"]) if tx == p["x0"] else tx
            tiras.append((ox, ty, Wt - p["wx"], Lt))
        if Lt - p["hy"] > 0.02:
            oy = (p["y0"] + p["hy"]) if ty == p["y0"] else ty
            tiras.append((p["x0"], oy, p["wx"], Lt - p["hy"]))
        for (sx, sy, sw, sl) in tiras:
            _rect(msp, sx, sy, sw, sl, "SOBRANTE-JUNTO-AL-RECORTE")
        # etiqueta 'SOBRA DE <id>' en la tira más grande donde quepa
        if tiras:
            sx, sy, sw, sl = max(tiras, key=lambda t: t[2] * t[3])
            corto, largo_l = min(sw, sl), max(sw, sl)
            if corto >= 0.045 and largo_l >= 0.30:
                s = f"SOBRA DE {p['id']}"
                _txt(msp, s, sx + sw / 2, sy + sl / 2,
                     min(0.045, corto * 0.5, largo_l / (len(s) * 0.75)),
                     "SOBRANTE-JUNTO-AL-RECORTE", rot=0 if sw >= sl else 90)
        puestos = sob if puestos is None else _uni([puestos, sob])


def dibujar_plan_corte(msp, piezas, x0_plan, y0_plan, modelo):
    """Dibuja, debajo del plano, cada pieza que se abre con sus recortes puestos,
    en el ORDEN DE CORTE PROPUESTO (M-01 = P.A. junto a la escalera)."""
    y_top = y0_plan - 2.0
    for material in ("Moret", "Royal Walnut"):
        baldosas, mapa, (anchoB, largoB) = empacar(piezas, material, modelo)
        if not baldosas:
            continue
        pc = PREF_CORTE[material]
        cols = 22
        cellw = anchoB + 0.45          # más separación horizontal
        cellh = largoB + 0.70          # más separación vertical (texto no se encima)
        _txt(msp, f"PLAN DE CORTE - {material.upper()}  ({len(baldosas)} piezas a abrir "
                  f"EN ORDEN: {pc}-01 = primer corte, PLANTA ALTA junto a la ESCALERA, y se avanza "
                  f"alejandose; al terminar P.A. sigue P.B.; "
                  f"amarillo = SOBRANTE con su medida -> GUARDAR EN RESERVA; rojo = desperdicio)",
             x0_plan + 9, y_top + 0.5, 0.25, "PLAN-CORTE-TEXTOS")
        for i, b in enumerate(baldosas):
            col = i % cols
            row = i // cols
            ox = x0_plan + col * cellw
            oy = y_top - (row + 1) * cellh
            _rect(msp, ox, oy, anchoB, largoB, "PLAN-CORTE-PIEZAS-A-ABRIR")
            _txt(msp, f"{pc}-{i+1:02d}", ox + anchoB / 2, oy + largoB + 0.14, 0.06, "PLAN-CORTE-TEXTOS")
            for (x, y, w, l, pid, rot), (origen, orden) in zip(b.piezas, b.meta):
                _rect(msp, ox + x, oy + y, w, l, "PLAN-CORTE-RECORTES")
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


def dibujar_resumen(msp, piezas, modelo, x0, y0, fusionado=False):
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
        # los recortes de regadera/escalera ya vienen empacados DENTRO (empacar)
        baldosas, _, (aB, lB) = empacar(piezas, material, modelo)
        extra_comp = 0
        if material == "Moret":
            try:
                import despiece_extra as DE
                extra_comp = (DE.regadera_resumen(modelo)["completas"]
                              + DE.escalera_resumen(modelo)["completas"])
            except Exception:
                extra_comp = 0
        bald_all = baldosas
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
                      if material == "Moret" and extra_comp else "")
        capa_comp = (("MORET" if material == "Moret" else "ROYAL") if fusionado
                     else CAPA[(material, True)])
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
    if fusionado:
        lineas += [
            "CONTEO RAPIDO EN AUTOCAD (ARCHIVO FUSIONADO): QSELECT (polilinea) por capa MORET o ROYAL:",
            "1 polilinea = 1 pieza completa QUE SE COMPRA (entera o que se abre para recorte).",
            "Los FALTANTES (salen de un sobrante, no abren pieza) van en MORET-FALTANTES / ROYAL-FALTANTES.",
        ]
    else:
        lineas += [
            "CONTEO RAPIDO EN AUTOCAD: QSELECT (polilinea) por capa MORET-COMPLETAS o ROYAL-COMPLETAS:",
            "1 polilinea = 1 pieza completa.",
        ]
    lineas += [
        "Las piezas estan a MEDIDA REAL 0.596 x 1.194, con BOQUILLA REAL entre piezas:",
        "0.002 (2 mm) en Moret y 0.001 (1 mm) en Royal Walnut.",
        "",
        "ORDEN DE CORTE PROPUESTO: la numeracion del plan de corte (M-01, M-02...) ES el orden:",
        "se empieza en PLANTA ALTA junto a la ESCALERA (por ahi sube el material) y se va uno",
        "alejando; al terminar P.A. se sigue con P.B., tambien desde la escalera.",
        "",
        "LEYENDA DE CAPAS (que es cada layer):",
    ]
    for nombre, desc in (LEYENDA_CAPAS_FUSIONADO if fusionado else LEYENDA_CAPAS) + LEYENDA_COMUN:
        lineas.append(f"  {nombre}: {desc}")
    lineas += [
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
        _rect(msp, cx, cy - lT, aT, lT, "PLAN-CORTE-PIEZAS-A-ABRIR")
        for (px, py, pw, pl, pid, rot) in piezas:
            _rect(msp, cx + px, cy - lT + py, pw, pl, "PLAN-CORTE-RECORTES")
            _txt(msp, pid, cx + px + pw / 2, cy - lT + py + pl / 2, 0.045, "PLAN-CORTE-TEXTOS")
        for (fx, fy, fw, fl, *_z) in libres:
            if fw > 0.03 and fl > 0.03:
                _rect(msp, cx + fx, cy - lT + fy, fw, fl, "PLAN-CORTE-SOBRANTES")
                _etq_sobrante(msp, cx, cy - lT, fx, fy, fw, fl)
        _txt(msp, etq, cx + aT / 2, cy + 0.07, 0.06, "PLAN-CORTE-TEXTOS")

    # ---- ESCALERA ----
    # Los CORTES de la escalera (H#/P#/D#) van DENTRO del plan de corte general
    # (reusan sobrantes del piso y ahí dicen a dónde brinca cada sobrante).
    # Aquí sólo quedan las piezas ENTERAS de los descansos, para contarlas.
    res = DE.escalera_resumen(modelo)
    enteras = [p for p in res["piezas"] if p["completa"]]
    _txt(msp, f"ESCALERA (ancho 1.15, peralte 0.175, huella 0.27) - {res['n_escalones']} escalones; "
              f"sus cortes estan en el PLAN DE CORTE general; aqui solo las enteras de descansos",
         x0, y0 + 0.5, 0.16, "PLAN-CORTE-TEXTOS")
    n = 0
    for p in enteras:
        cx = x0 + (n % cols) * gx; cy = y0 - (n // cols) * gy
        _rect(msp, cx, cy - lT, aT, lT, "PLAN-CORTE-PIEZAS-A-ABRIR")
        _txt(msp, p["id"], cx + aT / 2, cy - lT / 2, 0.06, "PLAN-CORTE-TEXTOS")
        _txt(msp, f"B{n+1}", cx + aT / 2, cy + 0.07, 0.06, "PLAN-CORTE-TEXTOS"); n += 1
    filas_esc = (n + cols - 1) // cols

    # ---- ZOCLO Moret (catálogo: 4 tiras de 0.148 por baldosa, cortadora diamante) ----
    import generadores as _G
    H = _G.ZOCLO_ALTO          # 0.148
    KERF = _G.ZOCLO_KERF       # 0.0 (cortadora de diamante: rayar y tronchar)
    yz = y0 - filas_esc * gy - 0.8
    _txt(msp, "DESPIECE ZOCLO MORET (4 tiras de 0.148 x 1.194 por pieza; cortadora de diamante: rayar y tronchar, corte sin merma; holgura para calibre 0.594-0.596)",
         x0, yz + 0.5, 0.16, "PLAN-CORTE-TEXTOS")
    _rect(msp, x0, yz - lT, aT, lT, "PLAN-CORTE-PIEZAS-A-ABRIR")
    for i in range(4):
        _rect(msp, x0 + i * (H + KERF), yz - lT, H, lT, "PLAN-CORTE-RECORTES")
        _txt(msp, f"Z{i+1}", x0 + i * (H + KERF) + H / 2, yz - lT / 2, 0.05, "PLAN-CORTE-TEXTOS")


def exportar(modelo, fusionado=False):
    """Exporta el DXF del modelo. Con fusionado=True genera la variante de
    CONTEO: una sola capa por material (MORET / ROYAL) con TODAS las piezas
    que se compran, y los FALTANTES (salen de un sobrante) aparte."""
    piezas = cargar_anotado(modelo)
    # geometría del plano con BOQUILLA REAL (2 mm Moret / 1 mm Royal)
    piezas_dxf = _relayar_juntas(piezas)
    origen_de = {}
    if fusionado:
        for material in ("Moret", "Royal Walnut"):
            baldosas, _, _d = empacar(piezas, material, modelo)
            for b in baldosas:
                for (x, y, w, l, etq, rot), (origen, orden) in zip(b.piezas, b.meta):
                    origen_de[etq] = origen

    doc = ezdxf.new("R2000", setup=True)   # R2000 = máxima compatibilidad (AutoCAD 2000+)
    doc.units = ezdxf.units.M
    msp = doc.modelspace()
    for nombre, color in (LAYERS_FUSIONADO if fusionado else LAYERS).items():
        doc.layers.add(nombre).color = color

    # --- Plano: piezas + IDs (medida real y boquilla real entre piezas) ---
    for p in piezas_dxf:
        if fusionado:
            base = "MORET" if p["material"] == "Moret" else "ROYAL"
            abre = p["completa"] or origen_de.get(p["id"], "TABLA") == "TABLA"
            capa = base if abre else f"{base}-FALTANTES"
        else:
            capa = CAPA[(p["material"], bool(p["completa"]))]
        if p.get("notch"):
            _contorno_notch(msp, p, capa)     # contorno real con entrante, sin mover
            w, h = p["wx"], p["hy"]
        else:
            w, h = p["wx"], p["hy"]           # ya vienen a medida real (re-tendido)
            _rect(msp, p["x0"], p["y0"], w, h, capa)
        th = min(max(0.022, min(w, h) * 0.22), 0.055)
        _txt(msp, p["id"], p["x"], p["y"], th, "ETIQUETAS")

    # --- Acabados: zoclo + muros + zonas de Urbania / regaderas ---
    dibujar_acabados(msp, modelo)

    # --- Sobrante amarillo PEGADO a cada recorte (completa la pieza entera) ---
    dibujar_sobrantes_en_plano(msp, piezas_dxf, modelo)

    # --- Plan de corte (debajo del plano) ---
    minx = min(p["x0"] for p in piezas_dxf)
    miny = min(p["y0"] for p in piezas_dxf)
    maxx = max(p["x0"] + p["wx"] for p in piezas_dxf)
    maxy = max(p["y0"] + p["hy"] for p in piezas_dxf)
    y_fin = dibujar_plan_corte(msp, piezas, minx, miny, modelo)

    # --- Cuadro RESUMEN (conteo de completas / piezas a abrir / cajas / sobra) ---
    dibujar_resumen(msp, piezas, modelo, minx,
                    (y_fin if y_fin is not None else miny - 4.0) - 0.6, fusionado)

    # --- Despiece de ESCALERA y ZOCLO (a la derecha del plano) ---
    dibujar_despiece_extra(msp, modelo, maxx + 3.0, maxy)

    # Nombre ASCII (sin ñ) para los CAD: evita que AutoCAD falle al resolver la
    # ruta por el carácter especial. Los PDF/Excel sí conservan "Viñas".
    suf = " (conteo por capa)" if fusionado else ""
    dxf = f"Vinas Norte - {modelo}{suf}.dxf"
    dwg = f"Vinas Norte - {modelo}.dwg"
    doc.saveas(dxf)
    if not fusionado and os.path.exists(DXF2DWG):
        subprocess.run([DXF2DWG, "-y", "-o", dwg, dxf], check=True, stderr=subprocess.DEVNULL)
        print(f"DWG editable: {dwg}")
    nrec = sum(1 for p in piezas if not p["completa"])
    print(f"DXF{' fusionado' if fusionado else ' editable'}: {dxf}")
    print(f"Piezas en el plano: {len(piezas)}  (completas: {len(piezas)-nrec}, recortes: {nrec})")


if __name__ == "__main__":
    import sys as _sys
    exportar(_sys.argv[1] if len(_sys.argv) > 1 else "Cabernet")
