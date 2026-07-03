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
    "ESCALERA-REGADERA-ZOCLO": 6, "ESCALERA-REGADERA-ZOCLO-TEXTO": 7,
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
    "ESCALERA-REGADERA-ZOCLO": 6, "ESCALERA-REGADERA-ZOCLO-TEXTO": 7,
}

# Qué es cada capa (esta leyenda también se escribe DENTRO del DXF, capa RESUMEN):
LEYENDA_CAPAS = [
    ("MORET-COMPLETAS", "piezas COMPLETAS de Moret en el plano; 1 polilinea = 1 pieza (contar con QSELECT)"),
    ("MORET-RECORTES", "piezas de Moret que llevan corte, en su posicion real del plano"),
    ("ROYAL-COMPLETAS", "piezas completas de Royal Walnut; 1 polilinea = 1 pieza"),
    ("ROYAL-RECORTES", "piezas de Royal Walnut que llevan corte"),
    ("ETIQUETAS", "ID de cada pieza del plano (PB/PA - M/R - numero)"),
    ("MUROS", "muros del plano de origen: estructurales (A-MUROS) + muros falsos de"
              " tablaroca (A-TABLAROCA, mas delgados), con su grosor"),
    ("SOBRANTE-JUNTO-AL-RECORTE", "amarillo PEGADO a cada recorte del plano: lo que le falta al recorte"
                                  " para completar la pieza entera (puede salir de los muros);"
                                  " si la tira es MERMA (<10 cm) va en ROJO (PLAN-CORTE-DESPERDICIO)"),
]

LEYENDA_CAPAS_FUSIONADO = [
    ("MORET", "TODAS las piezas de Moret que se COMPRAN: enteras y abiertas del plano"
              " + piezas de escalera/regadera (abiertas y enteras) + piezas de zoclo;"
              " 1 polilinea = 1 pieza completa que se compra: apaga las demas capas,"
              " selecciona todo y el conteo es tu compra (QSELECT)"),
    ("MORET-FALTANTES", "recortes que salen del SOBRANTE de otra pieza: NO abren pieza nueva"
                        " (los morados del PDF); no suman al conteo de piezas"),
    ("ROYAL", "TODAS las piezas de Royal Walnut que se compran (enteras + abiertas del plano"
              " + tablas de zoclo Royal); 1 polilinea = 1 pieza (QSELECT)"),
    ("ROYAL-FALTANTES", "recortes de Royal que salen de un sobrante: no abren pieza nueva"),
    ("ETIQUETAS", "ID de cada pieza del plano (PB/PA - M/R - numero)"),
    ("MUROS", "muros del plano de origen: estructurales (A-MUROS) + muros falsos de"
              " tablaroca (A-TABLAROCA, mas delgados), con su grosor"),
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
    ("ESCALERA-REGADERA-ZOCLO", "geometria del despiece y plan de corte de ESCALERA, MUROS DE BANO"
                                " (regadera) y ZOCLO; en el archivo de conteo, lo que ahi es pieza"
                                " completa que se compra va en la capa del material (MORET/ROYAL)"),
    ("ESCALERA-REGADERA-ZOCLO-TEXTO", "SOLO los textos del bloque de escalera/regadera/zoclo"
                                      " (apagala si quieres ver la geometria limpia)"),
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


def _relayar_juntas(piezas, modelo=None):
    """Devuelve una COPIA de las piezas re-tendida con la BOQUILLA REAL para el
    DXF: piezas completas EXACTAS de 0.596 x 1.194 con boquilla de 2 mm en
    Moret (Royal Walnut ya viene a paso real con 1 mm y no se re-tiende;
    solo sus juntas a hueso del dibujo se abren a 1 mm cediendo el corte).

    Cómo: por cada CUARTO (piezas Moret conectadas) se detectan las COLUMNAS y
    FILAS de la retícula y se re-calcula su paso: todo paso nominal (0.600 a
    0.602 de columna, 1.194 a 1.202 de fila) pasa al paso real 0.598 / 1.196
    (pieza + boquilla); los pasos parciales (recortes) se conservan. Una sola
    malla por cuarto = las esquinas de todas las filas y columnas COINCIDEN.
    Las boquillas chuecas del dibujo original (hasta 4 cm, como la de
    PB-M-080/081 en Cabernet) se normalizan a 2 mm porque en ese espacio no
    cabe un muro: son vicios del dibujo. El recorte que remata contra un muro
    conserva su borde original (en obra el corte absorbe la diferencia). Las
    piezas con entrante se mueven con la retícula pero su muesca queda
    pegada al muro real (el muro no se mueve)."""
    def _snap_real(v):
        # medida dibujada ~pieza completa (calibre +-6 mm) -> medida real exacta
        if 0.590 <= v <= 0.6085:
            return 0.596
        if 1.188 <= v <= 1.2065:
            return 1.194
        return v

    try:
        from shapely.geometry import box as _box
        from shapely.ops import unary_union as _uni
    except Exception:
        return [dict(p) for p in piezas]

    ps = [dict(p) for p in piezas]
    orig_dim = {p["id"]: (p["wx"], p["hy"]) for p in piezas if "id" in p}
    orig_pos = {p["id"]: (p["x0"], p["y0"]) for p in piezas if "id" in p}
    # máscara de muros: las piezas que CRUZAN muro (umbrales de puerta, muescas)
    # no generan aristas ni se mueven: cada cuarto ancla contra SU muro y el
    # corrimiento no se propaga de un cuarto a otro (ni empuja piezas al muro)
    mask = None
    if modelo is not None:
        try:
            from datos_piezas import _mascara_muros, MODELOS
            mask = _mascara_muros(MODELOS[modelo])
        except Exception:
            mask = None

    def _cap(p, eje, propuesto):
        # tope FISICO: el corte tiene que caber en la pieza madre 0.596x1.194.
        # Aplica aun si el dibujo original traia el corte MAS GRANDE que la
        # madre (PB-M-022/023 de Chardonnay venian dibujados de 1.210: de una
        # pieza de 1.194 ese corte no sale; era vicio del dibujo)
        otro = p["hy"] if eje == "wx" else p["wx"]
        madre = 1.194 if otro <= 0.608 else 0.596
        return max(0.02, min(propuesto, madre))

    moret = [p for p in ps if p["material"] == "Moret"]
    if not moret:
        return ps
    cajas = [_box(p["x0"] - 0.021, p["y0"] - 0.021,
                  p["x0"] + p["wx"] + 0.021, p["y0"] + p["hy"] + 0.021) for p in moret]
    union = _uni(cajas)
    zonas = list(union.geoms) if union.geom_type == "MultiPolygon" else [union]
    for zona in zonas:
        grupo = [p for p, c in zip(moret, cajas) if c.intersects(zona)
                 and c.intersection(zona).area > 0.5 * c.area]
        moviles = list(grupo)      # las piezas con muesca también se mueven:
        if len(moviles) < 2:       # su anillo de muesca queda absoluto (pegado
            continue               # al muro real, que no se mueve)
        for eje in ("x", "y"):
            a0, w = ("x0", "wx") if eje == "x" else ("y0", "hy")
            o0, ow = ("y0", "hy") if eje == "x" else ("x0", "wx")
            # columnas (o filas) de la retícula del cuarto
            vals = sorted(p[a0] for p in moviles)
            cols = [[vals[0]]]
            for v in vals[1:]:
                if v - cols[-1][-1] <= 0.004:
                    cols[-1].append(v)
                else:
                    cols.append([v])
            orig = [sum(c) / len(c) for c in cols]

            def _idx(v):
                k = min(range(len(orig)), key=lambda i: abs(orig[i] - v))
                return k if abs(orig[k] - v) <= 0.004 else None

            # aristas: SOLO entre columnas de piezas vecinas en la misma fila
            # (así las retículas corridas de cuartos distintos no se mezclan)
            filas_o = sorted(moviles, key=lambda p: p[o0])
            filas = [[filas_o[0]]]
            for p in filas_o[1:]:
                if p[o0] - filas[-1][-1][o0] <= 0.03:
                    filas[-1].append(p)
                else:
                    filas.append([p])
            from collections import defaultdict as _dd
            ady = _dd(list)
            for fila in filas:
                fila.sort(key=lambda p: p[a0])
                for p, q in zip(fila, fila[1:]):
                    if q[a0] - (p[a0] + p[w]) <= 0.045:
                        # tras un RECORTE la retícula se corta: el corte es el
                        # que absorbe la diferencia (su largo lo ajusta a 2 mm
                        # exactos la cascada D). Si aquí se forzara "medida del
                        # corte + 2 mm" como paso, el corrimiento del paso real
                        # se propagaría de cuarto en cuarto a través de los
                        # cortes (así se cayó 8 cm la zona alta de Chardonnay).
                        paso = _snap_real(p[w])
                        if paso not in (0.596, 1.194):
                            continue
                        i, j = _idx(p[a0]), _idx(q[a0])
                        if i is None or j is None or i == j:
                            continue
                        # objetivo: pieza a su medida real + boquilla de 2 mm.
                        # Normaliza TODAS las juntas, incluidas las chuecas de
                        # hasta 4.5 cm (ahí no cabe un muro: vicio del dibujo,
                        # p.ej. la de PB-M-080/081) y las de piezas tocándose.
                        t = paso + 0.002
                        ady[i].append((j, t))
                        ady[j].append((i, -t))
            # columnas ANCLADAS A MURO: si una pieza tiene muro pegado a su
            # borde inicial (el maestro traza línea nueva después del muro),
            # su columna se fija en su posición original y no la arrastra el
            # corrimiento del resto del cuarto
            fijas = set()
            if False and mask is not None:   # (anclas a muro desactivadas: creaban
                                             # conflictos insolubles con el paso real)
                for p in moviles:
                    i = _idx(p[a0])
                    if i is None or i in fijas:
                        continue
                    if eje == "x":
                        franja = _box(p["x0"] - 0.012, p["y0"] + 0.02,
                                      p["x0"] - 0.001, p["y0"] + p["hy"] - 0.02)
                    else:
                        franja = _box(p["x0"] + 0.02, p["y0"] - 0.012,
                                      p["x0"] + p["wx"] - 0.02, p["y0"] - 0.001)
                    if not franja.is_empty and franja.intersection(mask).area > 0.55 * franja.area:
                        fijas.add(i)

            # posiciones: BFS inicial + relajación por mínimos cuadrados, para
            # que los vicios del dibujo (ciclos inconsistentes) se repartan en
            # fracciones de mm entre todas las juntas y no se concentren
            pos = {}
            for start in range(len(orig)):
                if start in pos or start not in ady:
                    continue
                comp = [start]
                pos[start] = None
                pila = [start]
                while pila:
                    u = pila.pop()
                    for v, t in ady[u]:
                        if v not in pos:
                            pos[v] = None
                            comp.append(v)
                            pila.append(v)
                ancla = min(comp, key=lambda i: orig[i])
                for i in comp:
                    if i in fijas:
                        pos[i] = orig[i]          # ancla extra: columna a muro
                pos[ancla] = orig[ancla]
                pila = [ancla]
                vistos = {ancla}
                while pila:
                    u = pila.pop()
                    for v, t in ady[u]:
                        if v not in vistos:
                            vistos.add(v)
                            if pos.get(v) is None:
                                pos[v] = pos[u] + t
                            pila.append(v)
                # relajación (mínimos cuadrados): los vicios del dibujo se
                # reparten en fracciones de mm; lo que quede concentrado lo
                # absorbe la cascada D en los cortes
                for _ in range(400):
                    peor = 0.0
                    for u in comp:
                        if u == ancla or u in fijas:
                            continue
                        est = [pos[v] - t for (v, t) in ady[u]]
                        nuevo = sum(est) / len(est)
                        peor = max(peor, abs(nuevo - pos[u]))
                        pos[u] = nuevo
                    if peor < 1e-7:
                        break
                # RE-CENTRADO: el bloque completo se coloca donde estaba en el
                # dibujo (promedio de sus columnas). El corrimiento del paso
                # real queda repartido mitad y mitad en los dos muros del
                # bloque (lo tapa el zoclo) en vez de acumularse todo en el
                # extremo lejano e invadir el muro. Las boquillas internas no
                # cambian: el corrimiento es uniforme.
                delta = sum(orig[i] - pos[i] for i in comp
                            if pos.get(i) is not None) / max(
                    1, sum(1 for i in comp if pos.get(i) is not None))
                # ... pero SIN meter al muro las piezas que en el dibujo van A
                # HUESO contra muro: esas acotan el corrimiento del bloque y la
                # holgura se va al extremo libre (en obra: al zoclo o al vano)
                if mask is not None:
                    lo, hi = -1e9, 1e9
                    for p in moviles:
                        i = _idx(p[a0])
                        if i is None or pos.get(i) is None:
                            continue
                        x0, y0 = p["x0"], p["y0"]
                        x1, y1 = x0 + p["wx"], y0 + p["hy"]
                        if eje == "x":
                            f_ini = _box(x0 - 0.012, y0 + 0.02, x0 - 0.001, y1 - 0.02)
                            f_fin = _box(x1 + 0.001, y0 + 0.02, x1 + 0.012, y1 - 0.02)
                        else:
                            f_ini = _box(x0 + 0.02, y0 - 0.012, x1 - 0.02, y0 - 0.001)
                            f_fin = _box(x0 + 0.02, y1 + 0.001, x1 - 0.02, y1 + 0.012)
                        if (not f_ini.is_empty
                                and f_ini.intersection(mask).area > 0.55 * f_ini.area):
                            lo = max(lo, p[a0] - pos[i] - 0.0015)
                        if (not f_fin.is_empty
                                and f_fin.intersection(mask).area > 0.55 * f_fin.area):
                            hi = min(hi, p[a0] + p[w] - _snap_real(p[w])
                                     - pos[i] + 0.0015)
                    if lo > hi:            # bloque sobre-determinado: al medio
                        delta = (lo + hi) / 2
                    else:
                        delta = min(max(delta, lo), hi)
                for i in comp:
                    if pos.get(i) is not None:
                        pos[i] += delta


            # precomputar (con coordenadas ORIGINALES): borde lejano y si la
            # pieza remata contra un muro (nadie enfrente en su franja)
            datos = []
            for p in moviles:
                lejos = p[a0] + p[w]
                # remata SOLO si su medida dibujada en este eje es PARCIAL: un
                # 0.600/1.200 dibujado es paso de pieza completa y va a medida
                # real exacta (si rematara, estiraría p.ej. PB-M-108 a 0.640 y
                # su esquina ya no coincidiría con la junta de la fila de abajo)
                remata = (not p["completa"]) and _snap_real(p[w]) not in (0.596, 1.194) and not any(
                    q is not p
                    and -0.001 <= q[a0] - lejos <= 0.045
                    and min(p[o0] + p[ow], q[o0] + q[ow]) - max(p[o0], q[o0]) > 0.02
                    for q in grupo)
                datos.append((p, lejos, remata))
            for p, lejos, remata in datos:
                i = _idx(p[a0])
                if i is None or i not in pos:     # fuera de retícula: no se mueve
                    continue
                p[a0] = pos[i]
                if remata:
                    p[w] = _cap(p, w, max(lejos - p[a0], 0.02))   # el corte absorbe (con tope)
                else:
                    # medida real exacta: completas 0.596 x 1.194; y cualquier
                    # lado dibujado a "casi pieza" (calibre +-6 mm) tambien
                    p[w] = _snap_real(p[w])
    for _pasada in range(8):
        # pase D: cerrar boquillas chuecas residuales (3 mm a 4.5 cm) extendiendo
        # el lado de CORTE hacia la junta (en obra el corte se llena a la boquilla);
        # nunca se toca una pieza completa.
        for _ronda in range(2):
            for a in moret:
                for b in moret:
                    if a is b:
                        continue
                    fy = min(a["y0"] + a["hy"], b["y0"] + b["hy"]) - max(a["y0"], b["y0"])
                    fx = min(a["x0"] + a["wx"], b["x0"] + b["wx"]) - max(a["x0"], b["x0"])
                    if fy > 0.05:
                        g = b["x0"] - (a["x0"] + a["wx"])
                        # incluye g = 0: piezas A HUESO también reciben boquilla
                        if -1e-9 <= g <= 0.045 and abs(g - 0.002) > 0.0005:
                            # el corte crece (o encoge) hacia la junta; si el
                            # tope de madre recortó la propuesta y saldría un
                            # encogimiento espurio, mejor se deja la holgura
                            if not a["completa"]:
                                prop = a["wx"] + g - 0.002
                                na = _cap(a, "wx", prop)
                                if na > a["wx"] or abs(na - prop) < 1e-9:
                                    a["wx"] = na
                            elif not b["completa"]:
                                prop = b["wx"] + g - 0.002
                                nb = _cap(b, "wx", prop)
                                if nb > b["wx"] or abs(nb - prop) < 1e-9:
                                    b["x0"] -= nb - b["wx"]
                                    b["wx"] = nb
                            # entre completas NO se corre nada: la holgura del
                            # dibujo queda donde está (los cortes son los únicos
                            # que absorben); así ninguna fila abandona su muro
                            # ni se rompe la colinealidad de las columnas
                    if fx > 0.05:
                        g = b["y0"] - (a["y0"] + a["hy"])
                        if -1e-9 <= g <= 0.045 and abs(g - 0.002) > 0.0005:
                            if not a["completa"]:
                                prop = a["hy"] + g - 0.002
                                na = _cap(a, "hy", prop)
                                if na > a["hy"] or abs(na - prop) < 1e-9:
                                    a["hy"] = na
                            elif not b["completa"]:
                                prop = b["hy"] + g - 0.002
                                nb = _cap(b, "hy", prop)
                                if nb > b["hy"] or abs(nb - prop) < 1e-9:
                                    b["y0"] -= nb - b["hy"]
                                    b["hy"] = nb
                            # (ídem en y: entre completas no se corre nada)

        # pase final: si al llevar una completa a su medida real (celda dibujada
        # corta) quedó encimada con la vecina, retrocede el borde invasor (nunca
        # por debajo de lo dibujado); los slivers residuales se los come el corte.
        # incluye pares Moret x Royal: si el re-tendido de Moret roza una pieza
        # Royal (que no se mueve), retrocede SIEMPRE el lado Moret
        royal = [p for p in ps if p["material"] == "Royal Walnut"]
        for i, a in enumerate(moret):
            for b in moret[i + 1:] + royal:
                ox = min(a["x0"] + a["wx"], b["x0"] + b["wx"]) - max(a["x0"], b["x0"])
                oy = min(a["y0"] + a["hy"], b["y0"] + b["hy"]) - max(a["y0"], b["y0"])
                if ox <= 1e-6 or oy <= 1e-6:
                    continue
                eje = "wx" if ox <= oy else "hy"
                a0 = "x0" if eje == "wx" else "y0"
                pen = min(ox, oy)
                # invade quien mete su borde lejano dentro del otro
                par = sorted(((p, q) for p, q in ((a, b), (b, a))
                              if q[a0] - 1e-9 <= p[a0] + p[eje] <= q[a0] + q[eje] + 1e-9),
                             key=lambda pq: (pq[0]["material"] != "Moret", pq[0]["completa"]))
                if not par:
                    par = [(a, b)]
                p = par[0][0]                      # de preferencia retrocede el corte Moret
                if p["material"] != "Moret":
                    p = par[0][1] if par[0][1]["material"] == "Moret" else a
                otro_p = b if p is a else a
                k = 0 if eje == "wx" else 1
                # retrocede la penetración Y ADEMAS deja la boquilla: si se
                # quedara a hueso (0 mm), el borde del corte quedaría corrido
                # exactamente 2 mm respecto a la completa de al lado y en el
                # zoom de una esquina en T ese jog es lo primero que se ve
                holg = 0.002 if otro_p["material"] == "Moret" else 0.001
                # una completa solo retrocede lo que había CRECIDO sobre el dibujo;
                # un corte puede retroceder hasta 2 cm
                piso_min = (orig_dim.get(p.get("id"), (0.02, 0.02))[k]
                            if p["completa"] else 0.02)
                p[eje] = max(p[eje] - pen - holg, min(piso_min, p[eje]))

    # Royal Walnut ya viene a paso real (boquilla de 1 mm): NO se re-tiende;
    # solo las juntas que el dibujo dejó A HUESO (o casi) se abren a 1 mm
    # cediendo el lado de CORTE (la completa de 0.200 x 1.200 no se toca)
    royal_ps = [p for p in ps if p["material"] == "Royal Walnut"]
    for a in royal_ps:
        for b in royal_ps:
            if a is b:
                continue
            fy = min(a["y0"] + a["hy"], b["y0"] + b["hy"]) - max(a["y0"], b["y0"])
            fx = min(a["x0"] + a["wx"], b["x0"] + b["wx"]) - max(a["x0"], b["x0"])
            if fy > 0.05:
                g = b["x0"] - (a["x0"] + a["wx"])
                if -1e-9 <= g < 0.0005:
                    if not a["completa"]:
                        a["wx"] = max(0.02, a["wx"] - (0.001 - g))
                    elif not b["completa"]:
                        b["x0"] += 0.001 - g
                        b["wx"] = max(0.02, b["wx"] - (0.001 - g))
            if fx > 0.05:
                g = b["y0"] - (a["y0"] + a["hy"])
                if -1e-9 <= g < 0.0005:
                    if not a["completa"]:
                        a["hy"] = max(0.02, a["hy"] - (0.001 - g))
                    elif not b["completa"]:
                        b["y0"] += 0.001 - g
                        b["hy"] = max(0.02, b["hy"] - (0.001 - g))

    # ninguna pieza Moret sale más grande que la madre 0.596 x 1.194: los
    # vicios del dibujo (cortes de 1.210 como PB-M-022/023) se recortan por
    # el lado lejano; el origen se queda en su nodo para no romper esquinas
    for p in moret:
        for eje in ("wx", "hy"):
            tope = _cap(p, eje, p[eje])
            if p[eje] > tope:
                p[eje] = tope

    # pase de COLINEALIDAD en T: un corte cuyo borde lejano caía en la MISMA
    # línea de junta que el de su pieza vecina (esquina en T del dibujo, como
    # PA-M-050 sobre PA-M-054) se re-alinea a esa línea si el re-tendido los
    # separó unos mm y su frente quedó libre: el jog de 2 mm en una esquina
    # en T es lo primero que se ve al hacer zoom.
    for eje, a0k, o0k, owk in (("wx", "x0", "y0", "hy"), ("hy", "y0", "x0", "wx")):
        for a in moret:
            if a["completa"] or a.get("id") not in orig_pos:
                continue
            ka = 0 if eje == "wx" else 1
            ofa = orig_pos[a["id"]][ka] + orig_dim[a["id"]][ka]
            fa = a[a0k] + a[eje]
            for b in moret:
                if b is a or b.get("id") not in orig_pos:
                    continue
                # vecinos en T: bandas pegadas en el otro eje, traslape en éste
                sep = max(b[o0k] - (a[o0k] + a[owk]), a[o0k] - (b[o0k] + b[owk]))
                tras = (min(a[a0k] + a[eje], b[a0k] + b[eje])
                        - max(a[a0k], b[a0k]))
                if not (-0.001 <= sep <= 0.045 and tras > 0.05):
                    continue
                kb = 0 if eje == "wx" else 1
                ofb = orig_pos[b["id"]][kb] + orig_dim[b["id"]][kb]
                if abs(ofa - ofb) > 0.0025:
                    continue                      # en el dibujo no eran colineales
                fb = b[a0k] + b[eje]
                d = fb - fa
                if not (0.0005 < abs(d) <= 0.014):
                    continue
                if d > 0 and mask is not None:
                    # crecer hacia la línea vecina, nunca hacia dentro de un muro
                    if eje == "wx":
                        franja = _box(fa, a["y0"] + 0.02, fb, a["y0"] + a["hy"] - 0.02)
                    else:
                        franja = _box(a["x0"] + 0.02, fa, a["x0"] + a["wx"] - 0.02, fb)
                    if not franja.is_empty and franja.intersection(mask).area > 0.2 * franja.area:
                        continue
                # el frente del corte tiene que estar libre (si tiene junta
                # armada a 2 mm, re-alinearlo la rompería)
                libre = not any(
                    q is not a
                    and min(a[o0k] + a[owk], q[o0k] + q[owk]) - max(a[o0k], q[o0k]) > 0.02
                    and -0.001 <= q[a0k] - fa <= 0.045
                    for q in moret + [p for p in ps if p["material"] == "Royal Walnut"])
                if not libre:
                    continue
                nuevo = _cap(a, eje, a[eje] + d)
                if abs((a[a0k] + nuevo) - fb) <= 0.0006:
                    a[eje] = nuevo
                    break

    for p in ps:
        for k in ("x0", "y0", "wx", "hy"):
            p[k] = round(p[k], 4)
        p["x"] = round(p["x0"] + p["wx"] / 2, 4)
        p["y"] = round(p["y0"] + p["hy"] / 2, 4)

    # las MUESCAS (notch) son absolutas: abrazan el muro real, que no se mueve.
    # Si la pieza se corrió, el lado de la muesca que iba al ras de un borde de
    # la pieza se EXTIENDE hasta el borde nuevo, para que el contorno dibujado
    # no muerda el muro (PB-M-103, PA-M-009). Se hace DESPUES del redondeo y
    # con el anillo redondeado a 4 decimales: si quedara 0.0001 de diferencia
    # con el borde, la muesca se convertiria en agujero interior y el contorno
    # saldria entero o con picos (PA-M-035 / PA-M-025 en Cabernet).
    for p in ps:
        if not p.get("notch") or p.get("id") not in orig_pos:
            continue
        ox0, oy0 = orig_pos[p["id"]]
        ow, oh = orig_dim[p["id"]]
        nuevo_notch = []
        for ring in p["notch"]:
            ring = [[round(pt[0], 4), round(pt[1], 4)] for pt in ring]
            for pt in ring:
                if abs(pt[0] - ox0) < 2e-4:
                    pt[0] = p["x0"]
                elif abs(pt[0] - (ox0 + ow)) < 2e-4:
                    pt[0] = p["x0"] + p["wx"]
                if abs(pt[1] - oy0) < 2e-4:
                    pt[1] = p["y0"]
                elif abs(pt[1] - (oy0 + oh)) < 2e-4:
                    pt[1] = p["y0"] + p["hy"]
            nuevo_notch.append(ring)
        p["notch"] = nuevo_notch
    return ps


def dibujar_acabados(msp, modelo, limites=None):
    """Dibuja zoclo (perímetro) y marca las zonas de Urbania (lavandería) y las
    regaderas (Malla en charola + muro Moret), cada una en su propio layer.
    Con `limites` (minx, miny, maxx, maxy del plano de piezas) se descartan los
    segmentos sueltos de OTRAS partes de la hoja del DWG de origen, que caían
    encima del plan de corte."""
    try:
        import pdf_generadores as PG
        zoclo, muros, escal, claves = PG._datos_dwg(modelo)
    except Exception:
        return

    def _recorta(a, b):
        """Devuelve el tramo del segmento DENTRO del recuadro del plano (+1.5 m),
        o None si queda todo afuera: las bardas largas del DWG de origen se
        recortan en vez de invadir el plan de corte de abajo."""
        if limites is None:
            return a, b
        x0, y0, x1, y1 = limites
        m = 1.5
        X0, Y0, X1, Y1 = x0 - m, y0 - m, x1 + m, y1 + m
        dx, dy = b[0] - a[0], b[1] - a[1]
        t0, t1 = 0.0, 1.0
        for p, q in ((-dx, a[0] - X0), (dx, X1 - a[0]),
                     (-dy, a[1] - Y0), (dy, Y1 - a[1])):
            if abs(p) < 1e-12:
                if q < 0:
                    return None
            else:
                t = q / p
                if p < 0:
                    t0 = max(t0, t)
                else:
                    t1 = min(t1, t)
        if t0 > t1:
            return None
        return ((a[0] + t0 * dx, a[1] + t0 * dy),
                (a[0] + t1 * dx, a[1] + t1 * dy))

    for a, b in zoclo:
        seg = _recorta(a, b)
        if seg:
            msp.add_line(seg[0], seg[1], dxfattribs={"layer": "ZOCLO"})
    # MUROS reales del plano de origen (A-MUROS + tablaroca): así se revisan
    # las piezas contra el grosor del muro directamente en AutoCAD.
    for a, b in muros:
        seg = _recorta(a, b)
        if seg:
            msp.add_line(seg[0], seg[1], dxfattribs={"layer": "MUROS"})
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
    g = box(round(p["x0"], 4), round(p["y0"], 4),
            round(p["x0"] + p["wx"], 4), round(p["y0"] + p["hy"], 4))
    for ring in p.get("notch", []):
        if len(ring) >= 3:
            anillo = Polygon([(round(x, 4), round(y, 4)) for x, y in ring]).buffer(0)
            g = g.difference(anillo)
    g = g.buffer(0)
    polys = [g] if g.geom_type == "Polygon" else list(getattr(g, "geoms", []))
    for gg in polys:
        if gg.is_empty or gg.area < 1e-5:
            continue
        pts = []
        for x, y in gg.exterior.coords[:-1]:
            q = (round(x, 4), round(y, 4))
            if not pts or q != pts[-1]:
                pts.append(q)
        # sin picos: un vértice que regresa por el mismo camino sobra
        limpio = []
        for q in pts:
            while len(limpio) >= 2:
                a, b = limpio[-2], limpio[-1]
                if ((b[0] - a[0]) * (q[1] - b[1]) == (b[1] - a[1]) * (q[0] - b[0])
                        and (q[0] - b[0]) * (b[0] - a[0]) + (q[1] - b[1]) * (b[1] - a[1]) < 0):
                    limpio.pop()
                else:
                    break
            limpio.append(q)
        if len(limpio) >= 3:
            msp.add_lwpolyline(limpio, close=True, dxfattribs={"layer": layer})
        # si aun asi quedo una muesca INTERIOR (isla de tablaroca en medio de
        # la pieza), se dibuja tambien su contorno para que el corte se vea
        for interior in gg.interiors:
            ptsi = [(round(x, 4), round(y, 4)) for x, y in interior.coords[:-1]]
            if len(ptsi) >= 3:
                msp.add_lwpolyline(ptsi, close=True, dxfattribs={"layer": layer})


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
            # tira MERMA (<10 cm): en ROJO (desperdicio), no se manda a guardar
            _rect(msp, sx, sy, sw, sl,
                  "SOBRANTE-JUNTO-AL-RECORTE" if es_reutilizable(sw, sl)
                  else "PLAN-CORTE-DESPERDICIO")
        # etiqueta 'SOBRA DE <id>' / 'MERMA DE <id>' en la tira más grande
        if tiras:
            sx, sy, sw, sl = max(tiras, key=lambda t: t[2] * t[3])
            corto, largo_l = min(sw, sl), max(sw, sl)
            if corto >= 0.045 and largo_l >= 0.30:
                reut = es_reutilizable(sw, sl)
                s = f"{'SOBRA' if reut else 'MERMA'} DE {p['id']}"
                _txt(msp, s, sx + sw / 2, sy + sl / 2,
                     min(0.045, corto * 0.5, largo_l / (len(s) * 0.75)),
                     "SOBRANTE-JUNTO-AL-RECORTE" if reut else "PLAN-CORTE-DESPERDICIO",
                     rot=0 if sw >= sl else 90)
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
    tablas_por_mat = {}
    for material in ("Moret", "Royal Walnut"):
        focal = [p for p in piezas if p["material"] == material]
        if not focal:
            continue
        completas = sum(1 for p in focal if p["completa"])
        recortes_plano = [p for p in focal if not p["completa"]]
        # los recortes de regadera/escalera ya vienen empacados DENTRO (empacar)
        baldosas, mapa_mat, (aB, lB) = empacar(piezas, material, modelo)
        # de que sale cada recorte del plano: "TABLA" abre pieza nueva; otra
        # etiqueta = sale del sobrante de esa pieza (FALTANTE, no abre pieza)
        origen_de = {}
        for b in baldosas:
            for (x, y, w, l, etq, rot), (origen, orden) in zip(b.piezas, b.meta):
                origen_de[etq] = origen
        abren = sum(1 for p in recortes_plano
                    if origen_de.get(p["id"], "TABLA") == "TABLA")
        faltan = len(recortes_plano) - abren
        # piezas abiertas por cortes de ESCALERA/REGADERA (no estan en el plano)
        # y faltantes de escalera/regadera (salen de un sobrante)
        abren_extra = sum(1 for b in baldosas
                          if b.piezas and b.piezas[0][4] not in mapa_mat)
        faltan_extra = sum(1 for b in baldosas
                           for (x, y, w, l, etq, rot), (origen, orden)
                           in zip(b.piezas, b.meta)
                           if etq not in mapa_mat and origen != "TABLA")
        # piezas destinadas a ZOCLO (plan de corte de zoclo, a la derecha)
        try:
            import generadores as _G
            if material == "Moret":
                zoclo_pzs = math.ceil(math.ceil(_G.GEN[modelo]["zoclo_m"] / 1.194) / 4)
            else:
                zoclo_pzs = math.ceil(_G.GEN[modelo]["zoclo_r"] / 1.20)
        except Exception:
            zoclo_pzs = 0
        extra_comp = 0
        if material == "Moret":
            try:
                import despiece_extra as DE
                extra_comp = (DE.regadera_resumen(modelo)["completas"]
                              + DE.escalera_resumen(modelo)["completas"])
            except Exception:
                extra_comp = 0
        bald_all = baldosas
        tablas_por_mat[material] = len(bald_all)
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
        base = "MORET" if material == "Moret" else "ROYAL"
        lineas.append(f"{material.upper()}{nota_extra}:")
        if fusionado:
            # cada cifra de capa CUADRA con QSELECT sobre esa capa. La capa del
            # material tiene TODAS las piezas completas que se COMPRAN: apaga
            # las demas capas, selecciona todo y el conteo es tu compra.
            tot_capa = completas + abren + abren_extra + extra_comp + zoclo_pzs
            desglose = (f"{completas} enteras del plano + {abren} recortes del plano"
                        f" que abren pieza")
            if extra_comp or abren_extra:
                desglose += (f" + {abren_extra} abiertas por escalera/regadera"
                             f" + {extra_comp} enteras de descansos/muros de bano")
            if zoclo_pzs:
                desglose += f" + {zoclo_pzs} piezas de zoclo"
            lineas += [
                f"  CAPA {base} (QSELECT): {tot_capa} polilineas = {desglose}",
                f"  CAPA {base}-FALTANTES (QSELECT): {faltan + faltan_extra} recortes que salen"
                f" de un sobrante (no abren pieza)"
                + (f"   [{faltan} del plano + {faltan_extra} de escalera/regadera]"
                   if faltan_extra else ""),
            ]
        else:
            lineas += [
                f"  CAPA {base}-COMPLETAS (QSELECT): {completas} piezas completas en el plano",
                f"  CAPA {base}-RECORTES (QSELECT): {len(recortes_plano)} piezas con corte en el plano"
                f"   [{abren} abren pieza nueva + {faltan} salen de un sobrante]",
            ]
        extra_txt = (f" + {extra_comp} enteras extra (descansos de escalera y muro de regadera,"
                     f" fuera del plano)" if extra_comp else "")
        lineas += [
            f"  PIEZAS QUE SE COMPRAN: {completas} enteras del plano{extra_txt}"
            f" + {len(bald_all)} que se abren p/recorte = {total}   |   CAJAS: {cajas} ({m2_comprados:.2f} m2)",
            f"  SOBRANTE REUTILIZABLE: {area_reut:.2f} m2 en {n_sob} pzas -> GUARDAR EN RESERVA"
            f"   |   DESPERDICIO: {area_desp:.2f} m2 ({n_desp} pedazos <10 cm)"
            f"   |   SOBRA TOTAL: {pct:.1f}% de lo comprado",
            "",
        ]
    if tablas_por_mat:
        tot_tablas = sum(tablas_por_mat.values())
        det = " + ".join(f"{n} {m}" for m, n in tablas_por_mat.items())
        lineas += [
            f"PLAN DE CORTE (abajo): la capa PLAN-CORTE-PIEZAS-A-ABRIR tiene {tot_tablas}"
            f" contornos ({det}), uno por pieza que se abre; incluye las tablas de"
            " escalera/regadera.",
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


def dibujar_despiece_extra(msp, modelo, x0, y0, piezas, fusionado=False):
    """Bloque ESCALERA-REGADERA-ZOCLO, a la derecha del plano. Geometría en la
    capa ESCALERA-REGADERA-ZOCLO y TODOS los textos en ...-ZOCLO-TEXTO.
      1. ESQUEMA de la escalera (perfil con P#/H#/descansos).
      2. PLAN DE CORTE - ESCALERA: piezas dibujadas con sus cortes, sobrantes
         (amarillo=guardar / rojo=merma) y destino; enteras de descanso.
      3. PLAN DE CORTE - MUROS DE BANO (regadera): alzados + piezas.
      4. PLAN DE CORTE - ZOCLO completo (todas las piezas, 4 tiras de 0.149).
    En el archivo de CONTEO (fusionado): cada pieza completa que se COMPRA de
    este bloque va en la capa del material (MORET / ROYAL): piezas que abren
    los cortes de escalera/regadera (si no estan ya contadas en el plano),
    enteras de descansos y muros, y piezas de zoclo. Los cortes que salen de
    un SOBRANTE van en MORET-FALTANTES. Asi QSELECT sobre MORET da TODAS las
    piezas que se compran."""
    try:
        import despiece_extra as DE
        from optimizador_recortes import PISOS
        import generadores as _G
    except Exception:
        return
    from collections import defaultdict
    CAPA_X = "ESCALERA-REGADERA-ZOCLO"
    CAPA_T = "ESCALERA-REGADERA-ZOCLO-TEXTO"
    # capa de PIEZA COMPLETA COMPRADA en el archivo de conteo:
    CAPA_M = "MORET" if fusionado else CAPA_X
    CAPA_R = "ROYAL" if fusionado else CAPA_X
    CAPA_F = "MORET-FALTANTES" if fusionado else CAPA_X
    aT, lT = PISOS["Moret"]                       # 0.596 x 1.194

    # --- la MISMA cadena de corte del plan general (no una aparte) ---
    baldosas, mapa, _dims = empacar(piezas, "Moret", modelo)
    pc = PREF_CORTE["Moret"]
    origen_de, tabla_de = {}, {}
    for idx, b in enumerate(baldosas, 1):
        for (px, py, pw, pl, etq, rot), (origen, orden) in zip(b.piezas, b.meta):
            origen_de[etq] = origen
            tabla_de[etq] = idx
    destino_de = defaultdict(list)
    for pid, org in origen_de.items():
        if org != "TABLA":
            destino_de[org].append(pid)

    def _abre_extra(idx):
        """True si la pieza M-idx la ABRE un corte de escalera/regadera (no
        esta dibujada en el plano): en el conteo debe sumar aqui."""
        b = baldosas[idx - 1]
        return bool(b.piezas) and b.piezas[0][4] not in mapa

    def _titulo(y, texto, alto=0.18):
        y -= 0.6                      # aire ANTES de cada sección
        _txt(msp, texto, x0, y, alto, CAPA_T)
        return y - 0.6

    def _lineas(y, filas, alto=0.13):
        for ln in filas:
            _txt(msp, ln, x0, y, alto, CAPA_T)
            y -= 0.38
        return y

    def _origen_txt(pid):
        org = origen_de.get(pid)
        if org is None:
            return "?"
        if org == "TABLA":
            return f"abre la pieza {pc}-{tabla_de.get(pid, 0):02d}"
        return f"sale de la SOBRA DE {org} (pieza {pc}-{tabla_de.get(pid, 0):02d}, no abre pieza)"

    def _tabla(cx, cy, idx, marcados):
        """Dibuja la pieza M-idx (la misma del plan general) con sus cortes,
        sobrantes (amarillo=guardar, rojo=merma) y faltantes (de sobrante)."""
        b = baldosas[idx - 1]
        capa_madre = CAPA_M if _abre_extra(idx) else CAPA_X
        _rect(msp, cx, cy - lT, aT, lT, capa_madre)
        for (px, py, pw, pl, pid, rot), (origen, orden) in zip(b.piezas, b.meta):
            es_faltante_extra = (pid not in mapa) and origen != "TABLA"
            _rect(msp, cx + px, cy - lT + py, pw, pl,
                  CAPA_F if es_faltante_extra else CAPA_X)
            marca = "*" if pid in marcados else ""
            _txt(msp, f"{marca}{pid}", cx + px + pw / 2, cy - lT + py + pl / 2,
                 min(0.038, max(0.02, min(pw, pl) * 0.2)), CAPA_T,
                 rot=0 if pw >= pl else 90)
        for (fx, fy, fw, fl, *_z) in b.libres:
            if fw > 0.03 and fl > 0.03:
                reut = es_reutilizable(fw, fl)
                _rect(msp, cx + fx, cy - lT + fy, fw, fl,
                      "PLAN-CORTE-SOBRANTES" if reut else "PLAN-CORTE-DESPERDICIO")
                if min(fw, fl) >= 0.05 and fw * fl >= 0.02:
                    _txt(msp, (f"SOBRA {_fmt(fw)}x{_fmt(fl)} -> GUARDAR" if reut
                               else f"MERMA {_fmt(fw)}x{_fmt(fl)} (<10 cm, ya no sirve)"),
                         cx + fx + fw / 2, cy - lT + fy + fl / 2, 0.028, CAPA_T,
                         rot=0 if fw >= fl else 90)
        nota = "" if _abre_extra(idx) else " (contada en el plano)"
        _txt(msp, f"{pc}-{idx:02d}{nota}", cx + aT / 2, cy + 0.08, 0.055, CAPA_T)

    y = y0

    # ================= 1) ESQUEMA DE LA ESCALERA =================
    res = DE.escalera_resumen(modelo)
    cfg = DE.ESCALERA[modelo]
    y = _titulo(y, f"1) ESCALERA - ESQUEMA ({res['n_escalones']} escalones: ancho 1.15,"
                   f" peralte 0.175, huella 0.27; tramos {'+'.join(str(t) for t in cfg['tramos'])})")
    px_, py_ = x0, y - 3.2          # arranque del perfil (sube hacia la derecha)
    ex, ey = px_, py_
    n_esc = 0
    DESC_LARGO = 1.0
    for t_i, tramo in enumerate(cfg["tramos"]):
        for _ in range(tramo):
            n_esc += 1
            msp.add_line((ex, ey), (ex, ey + 0.175), dxfattribs={"layer": CAPA_X})
            _txt(msp, f"P{n_esc}", ex - 0.10, ey + 0.0875, 0.045, CAPA_T)
            ey += 0.175
            msp.add_line((ex, ey), (ex + 0.27, ey), dxfattribs={"layer": CAPA_X})
            _txt(msp, f"H{n_esc}", ex + 0.135, ey + 0.055, 0.045, CAPA_T)
            ex += 0.27
        if t_i < len(cfg["descansos"]):
            ent, rec = cfg["descansos"][t_i]
            msp.add_line((ex, ey), (ex + DESC_LARGO, ey), dxfattribs={"layer": CAPA_X})
            _txt(msp, f"DESCANSO {t_i+1} ({ent} ent + {rec} rec)",
                 ex + DESC_LARGO / 2, ey + 0.09, 0.045, CAPA_T)
            ex += DESC_LARGO
    if res.get("zoclo_orilla"):
        _txt(msp, "+ zoclo de 0.149 en la orilla (pegado al muro) desde el 1er descanso",
             x0, py_ - 0.35, 0.11, CAPA_T)
    y = py_ - 0.9

    # ================= 2) PLAN DE CORTE - ESCALERA =================
    esc_rec = [p for p in res["piezas"] if not p["completa"]]
    esc_ent = [p for p in res["piezas"] if p["completa"]]
    y = _titulo(y, "2) PLAN DE CORTE - ESCALERA (piezas dibujadas con sus cortes y sobrantes;"
                   " son las MISMAS piezas del plan de corte general)")
    filas = [f"{p['id']} ({_fmt(p['ancho'])}x{_fmt(p['largo'])}): {_origen_txt(p['id'])}"
             for p in esc_rec]
    y = _lineas(y, filas)
    y -= 0.8
    idxs = sorted({tabla_de[p["id"]] for p in esc_rec if p["id"] in tabla_de})
    marcados = {p["id"] for p in esc_rec}
    ya_dibujadas = set(idxs)      # cada pieza M-xx se dibuja UNA sola vez
    cols, gx, gy = 6, aT + 0.55, lT + 0.85
    for k, idx in enumerate(idxs):
        cx = x0 + (k % cols) * gx
        cy = y - (k // cols) * gy
        _tabla(cx, cy - 0.2, idx, marcados)
    y -= ((len(idxs) + cols - 1) // cols) * gy + 1.4 if idxs else 0.6
    # piezas ENTERAS de los descansos: se colocan completas (cuentan como compra)
    if esc_ent:
        y = _titulo(y, f"ENTERAS DE DESCANSO ({len(esc_ent)}): se colocan completas, sin corte",
                    alto=0.15)
        for k, p in enumerate(esc_ent):
            cx = x0 + (k % cols) * gx
            cy = y - 0.2 - (k // cols) * gy
            _rect(msp, cx, cy - lT, aT, lT, CAPA_M)
            _txt(msp, f"{p['id']} (entera)", cx + aT / 2, cy - lT / 2, 0.05, CAPA_T, rot=90)
        y -= ((len(esc_ent) + cols - 1) // cols) * gy + 1.0

    # ================= 3) PLAN DE CORTE - MUROS DE BANO =================
    paredes = DE.regadera_paredes(modelo)
    rres = DE.regadera_resumen(modelo)
    y = _titulo(y, f"3) MUROS DE BANO (REGADERA) - piso Moret ACOSTADO en 3 caras;"
                   f" {rres['completas']} enteras + {rres['recortes']} recortes")
    # alzados de cada cara: las piezas ENTERAS del muro cuentan como compra
    cx = x0
    fila_h = 0.0
    for (titulo, w, h, pzs) in paredes:
        if cx + w > x0 + 14.0:          # nueva fila de alzados
            cx = x0
            y -= fila_h + 1.0
            fila_h = 0.0
        _rect(msp, cx, y - h, w, h, CAPA_X)
        for p in pzs:
            _rect(msp, cx + p["x"], y - h + p["y"], p["w"], p["h"],
                  CAPA_M if p["completa"] else CAPA_X)
            _txt(msp, p["id"], cx + p["x"] + p["w"] / 2, y - h + p["y"] + p["h"] / 2,
                 0.05, CAPA_T, rot=0 if p["w"] >= p["h"] else 90)
        etq_corta = (pzs[0]["pared"] if pzs else titulo.split("—")[0].strip())
        _txt(msp, f"{etq_corta} ({w:.2f}x{h:.2f})", cx + w / 2, y + 0.12, 0.06, CAPA_T)
        cx += w + 0.6
        fila_h = max(fila_h, h)
    y -= fila_h + 1.0
    reg_rec = [p for _t, _w, _h, ps in paredes for p in ps if not p["completa"]]
    filas = [f"{p['id']} ({_fmt(p['ancho'])}x{_fmt(p['largo'])}): {_origen_txt(p['id'])}"
             for p in reg_rec]
    filas.append("(las piezas enteras de los muros se colocan completas, sin corte)")
    compartidas = sorted({tabla_de[p["id"]] for p in reg_rec
                          if p["id"] in tabla_de} & ya_dibujadas)
    if compartidas:
        filas.append("(las piezas " + ", ".join(f"{pc}-{i:02d}" for i in compartidas)
                     + " ya estan dibujadas en la seccion de ESCALERA: es la misma pieza)")
    y = _lineas(y, filas)
    y -= 0.8
    idxs = sorted({tabla_de[p["id"]] for p in reg_rec if p["id"] in tabla_de}
                  - ya_dibujadas)
    marcados = {p["id"] for p in reg_rec}
    for k, idx in enumerate(idxs):
        cx = x0 + (k % cols) * gx
        cy = y - (k // cols) * gy
        _tabla(cx, cy - 0.2, idx, marcados)
    y -= ((len(idxs) + cols - 1) // cols) * gy + 1.4 if idxs else 0.6

    # ================= 4) PLAN DE CORTE - ZOCLO (COMPLETO) =================
    H = _G.ZOCLO_ALTO          # 0.149: 4 x 0.149 = 0.596, tiras exactas
    import math as _math
    ml = _G.GEN[modelo]["zoclo_m"]
    tiras = _math.ceil(ml / 1.194)
    tablas_z = _math.ceil(tiras / 4)
    y = _titulo(y, f"4) PLAN DE CORTE - ZOCLO MORET COMPLETO: {ml:.2f} ml -> {tiras} tiras"
                   f" de {H:.3f} x 1.194 -> {tablas_z} piezas (4 tiras EXACTAS por pieza;"
                   " cortadora de diamante, corte sin merma)")
    zn = 0
    for k in range(tablas_z):
        cx = x0 + (k % cols) * gx
        cy = y - 0.2 - (k // cols) * gy
        _rect(msp, cx, cy - lT, aT, lT, CAPA_M)
        for i in range(4):
            zn += 1
            if zn <= tiras:
                _rect(msp, cx + i * H, cy - lT, H, lT, CAPA_X)
                _txt(msp, f"Z{zn}", cx + i * H + H / 2, cy - lT / 2, 0.04, CAPA_T, rot=90)
            else:
                _rect(msp, cx + i * H, cy - lT, H, lT, "PLAN-CORTE-SOBRANTES")
                _txt(msp, "SOBRA (tira libre)", cx + i * H + H / 2, cy - lT / 2,
                     0.032, CAPA_T, rot=90)
        _txt(msp, f"ZOCLO {pc}-Z{k+1:02d}", cx + aT / 2, cy + 0.08, 0.05, CAPA_T)
    y -= ((tablas_z + cols - 1) // cols) * gy + 1.0

    # ---- zoclo ROYAL (1 tira de 0.149 por tabla de 0.20 x 1.20) ----
    ml_r = _G.GEN[modelo]["zoclo_r"]
    tiras_r = _math.ceil(ml_r / 1.20)
    y = _titulo(y, f"4b) PLAN DE CORTE - ZOCLO ROYAL COMPLETO: {ml_r:.2f} ml -> {tiras_r} tablas"
                   f" (de cada tabla Royal de 0.20 x 1.20 sale 1 tira de {H:.3f})")
    aR, lR = 0.20, 1.20
    gxr, gyr = lR + 0.4, aR + 0.55        # tablas Royal acostadas (1.20 x 0.20)
    colsr = 4
    for k in range(tiras_r):
        cx = x0 + (k % colsr) * gxr
        cy = y - 0.2 - (k // colsr) * gyr
        _rect(msp, cx, cy - aR, lR, aR, CAPA_R)
        _rect(msp, cx, cy - aR, lR, H, CAPA_X)
        _txt(msp, f"ZR{k+1}", cx + lR / 2, cy - aR + H / 2, 0.045, CAPA_T)
        _rect(msp, cx, cy - aR + H, lR, aR - H, "PLAN-CORTE-DESPERDICIO")
    y -= ((tiras_r + colsr - 1) // colsr) * gyr + 1.0


def exportar(modelo, fusionado=False):
    """Exporta el DXF del modelo. Con fusionado=True genera la variante de
    CONTEO: una sola capa por material (MORET / ROYAL) con TODAS las piezas
    que se compran, y los FALTANTES (salen de un sobrante) aparte."""
    piezas = cargar_anotado(modelo)
    # geometría del plano con BOQUILLA REAL (2 mm Moret / 1 mm Royal)
    piezas_dxf = _relayar_juntas(piezas, modelo)
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
        # etiqueta chica, centrada y a lo LARGO de la pieza (rotada si la pieza
        # es vertical): siempre queda contenida dentro de su pieza
        th = min(max(0.018, min(w, h) * 0.16), 0.042)
        _txt(msp, p["id"], p["x"], p["y"], th, "ETIQUETAS",
             rot=0 if w >= h else 90)

    # --- Acabados: zoclo + muros + zonas de Urbania / regaderas ---
    dibujar_acabados(msp, modelo,
                     (min(p["x0"] for p in piezas_dxf),
                      min(p["y0"] for p in piezas_dxf),
                      max(p["x0"] + p["wx"] for p in piezas_dxf),
                      max(p["y0"] + p["hy"] for p in piezas_dxf)))

    # --- Sobrante amarillo PEGADO a cada recorte (completa la pieza entera) ---
    dibujar_sobrantes_en_plano(msp, piezas_dxf, modelo)

    # --- Plan de corte (debajo del plano) ---
    minx = min(p["x0"] for p in piezas_dxf)
    miny = min(p["y0"] for p in piezas_dxf)
    maxx = max(p["x0"] + p["wx"] for p in piezas_dxf)
    maxy = max(p["y0"] + p["hy"] for p in piezas_dxf)
    y_fin = dibujar_plan_corte(msp, piezas, minx, miny, modelo)

    # --- Cuadro RESUMEN (conteo de completas / piezas a abrir / cajas / sobra),
    # bien SEPARADO del plan de corte para que no se encimen los textos ---
    dibujar_resumen(msp, piezas, modelo, minx,
                    (y_fin if y_fin is not None else miny - 4.0) - 1.8, fusionado)

    # --- Escalera, muros de baño y zoclo: A LA DERECHA DE TODO lo dibujado
    # (plano + plan de corte + resumen), para que NO se encime con nada ---
    max_x_global = maxx
    for e in msp:
        try:
            if e.dxftype() == "LWPOLYLINE":
                max_x_global = max(max_x_global, max(p[0] for p in e.get_points()))
            elif e.dxftype() == "LINE":
                max_x_global = max(max_x_global, e.dxf.start[0], e.dxf.end[0])
            elif e.dxftype() == "TEXT":
                ancho_txt = (0 if (e.dxf.rotation or 0) > 45
                             else len(e.dxf.text) * e.dxf.height * 0.85)
                max_x_global = max(max_x_global, e.dxf.insert[0] + ancho_txt)
        except Exception:
            pass
    dibujar_despiece_extra(msp, modelo, max_x_global + 3.0, maxy, piezas, fusionado)

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
