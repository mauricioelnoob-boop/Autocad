#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
datos_piezas.py
===============

Carga el despiece (piezas_piso.json) y lo ANOTA con la planta a la que
pertenece cada pieza, aplicando las reglas reales de la obra:

  * El plano tiene las dos plantas dibujadas lado a lado. Se separan por la
    coordenada X (hay un hueco claro entre ambas):
        - Planta BAJA  (X < X_CORTE): SOLO piso Moret.
        - Planta ALTA  (X >= X_CORTE): Moret + Royal Walnut.
  * El Royal Walnut SOLO va en las recámaras (planta alta). Las piezas de
    0.20 m que aparecen en planta baja son las CHAROLAS de baño (otro piso)
    y se EXCLUYEN del conteo.

A cada pieza se le asigna un ID por planta+material (ej. PB-M-001 = planta baja
Moret pieza 1, PA-R-014 = planta alta Royal pieza 14) y, si es recorte, de qué
baldosa de corte sale (corte_de), optimizando por planta+material.

Función principal:  cargar_anotado(path) -> lista de piezas anotadas.
"""

import json
from collections import defaultdict

from optimizador_recortes import PISOS, ajustar, empaquetar

X_CORTE = 498.7        # frontera entre planta baja (izq) y planta alta (der)

PREF_PLANTA = {"baja": "PB", "alta": "PA"}
PREF_MAT = {"Moret": "M", "Royal Walnut": "R"}
PREF_CORTE = {"Moret": "M", "Royal Walnut": "RW"}

# Piezas que faltan en el despiece del DWG y se agregan a mano.
# El arranque del piso Moret en planta baja (baldosa completa) no quedó dibujado.
PIEZAS_EXTRA = [
    {"material": "Moret", "ancho": 0.596, "largo": 1.194, "completa": True,
     "tipo_corte": "completa", "x": 489.84, "y": -86.14,
     "x0": 489.539, "y0": -86.738, "wx": 0.600, "hy": 1.194, "extra": True},
]

# Correcciones de material en la frontera entre pisos (la detección por ancho
# se equivoca en algunas piezas pegadas al límite recámara/pasillo).
# Cada entrada reasigna la pieza más cercana a (x,y): material correcto y, si se
# indica, si es completa o recorte. Editar aquí para cada modelo de casa.
RECLASIFICAR = [
    # Pieza de transición dibujada completa que en realidad es recorte de Moret
    {"x": 503.04, "y": -84.90, "material": "Moret", "completa": False},
]

# Regiones de las recámaras (única zona con Royal Walnut). Todo lo demás de
# planta alta (baño, vestidor, pasillo, escalera) es Moret. (X0,X1,Y0,Y1)
REGIONES_ROYAL = [
    (499.5, 502.75, -86.7, -81.8),   # Recámara 1
    (503.6, 508.1, -85.3, -81.8),    # Recámara principal
    (503.8, 508.1, -93.5, -89.6),    # Recámara 2
]

# Zona de escalera: se ignora (no se marca despiece ahí; va Moret pero no se cuenta).
REGION_ESCALERA = None   # (X0,X1,Y0,Y1) si se necesita excluir


def en_region(p, reg):
    return reg[0] <= p["x"] <= reg[1] and reg[2] <= p["y"] <= reg[3]


def planta_de(p):
    return "baja" if p["x"] < X_CORTE else "alta"


def _retipo(p):
    """Recalcula completa/tipo_corte de una pieza según su material y medida."""
    aw, al = PISOS[p["material"]]
    corto, largo = min(p["wx"], p["hy"]), max(p["wx"], p["hy"])
    p["ancho"], p["largo"] = round(corto, 4), round(largo, 4)
    ancho_ok = abs(corto - aw) <= 0.012
    largo_ok = abs(largo - al) <= 0.012
    p["completa"] = ancho_ok and largo_ok
    p["tipo_corte"] = ("completa" if p["completa"] else
                       "corte_largo" if ancho_ok else
                       "corte_ancho" if largo_ok else "corte_esquina")


def recortar_por_obstaculos(piezas, path):
    """Recorta al tamaño real las piezas que el despiece dibujó metidas en
    muros, closets o muebles fijos. Devuelve cuántas se corrigieron.
    Si no hay shapely o el archivo de obstáculos, no hace nada."""
    try:
        import json as _json
        from shapely.geometry import box, Polygon
        from shapely.ops import unary_union
        raw = _json.load(open(path, encoding="utf-8"))
    except Exception:
        return 0
    polys = [Polygon(m).buffer(0) for m in raw if len(m) >= 3]
    U = unary_union([p for p in polys if not p.is_empty and p.area > 0])
    n = 0
    for p in piezas:
        if p.get("planta") != "alta":      # sólo planta alta (baños/closets)
            continue
        r = box(p["x0"], p["y0"], p["x0"] + p["wx"], p["y0"] + p["hy"])
        if r.area <= 0:
            continue
        inter = r.intersection(U).area
        if inter <= 0.06 * r.area:
            continue
        rem = r.difference(U)
        if rem.is_empty or rem.area < 0.02 * r.area:
            p["completa"] = False
            if p["tipo_corte"] == "completa":
                p["tipo_corte"] = "corte_esquina"
            n += 1
            continue
        geoms = list(rem.geoms) if rem.geom_type == "MultiPolygon" else [rem]
        g = max(geoms, key=lambda q: q.area)
        x0, y0, x1, y1 = g.bounds
        p["x0"], p["y0"] = round(x0, 4), round(y0, 4)
        p["wx"], p["hy"] = round(x1 - x0, 4), round(y1 - y0, 4)
        p["x"], p["y"] = round((x0 + x1) / 2, 3), round((y0 + y1) / 2, 3)
        _retipo(p)
        n += 1
    return n


def cargar_anotado(path="piezas_piso.json", obstaculos="obstaculos_cabernet.json"):
    piezas = json.load(open(path, encoding="utf-8"))

    anotadas = []
    excluidas = 0
    for p in piezas:
        pl = planta_de(p)
        # Planta baja: sólo Moret. El Royal de planta baja son charolas de baño.
        if pl == "baja" and p["material"] == "Royal Walnut":
            excluidas += 1
            continue
        p["planta"] = pl
        anotadas.append(p)

    # Piezas faltantes agregadas a mano (p.ej. el arranque de Moret)
    for extra in PIEZAS_EXTRA:
        e = dict(extra)
        e["planta"] = planta_de(e)
        anotadas.append(e)

    # Material por REGIÓN en planta alta: Royal sólo en las recámaras, el resto
    # (baño, vestidor, pasillo) es Moret. Más confiable que el ancho en la frontera.
    if REGION_ESCALERA:
        anotadas = [p for p in anotadas if not (p["planta"] == "alta" and en_region(p, REGION_ESCALERA))]
    for p in anotadas:
        if p["planta"] != "alta":
            continue
        debe = "Royal Walnut" if any(en_region(p, r) for r in REGIONES_ROYAL) else "Moret"
        if debe != p["material"]:
            p["material"] = debe
            _retipo(p)

    # Correcciones de material en la frontera
    TOL = 0.012
    for r in RECLASIFICAR:
        cerca = min(anotadas, key=lambda p: (p["x"] - r["x"])**2 + (p["y"] - r["y"])**2)
        if (cerca["x"] - r["x"])**2 + (cerca["y"] - r["y"])**2 > 0.25:   # > 0.5 m, no match
            continue
        cerca["material"] = r["material"]
        aw, al = PISOS[r["material"]]
        corto, largo = min(cerca["wx"], cerca["hy"]), max(cerca["wx"], cerca["hy"])
        ancho_ok = abs(corto - aw) <= TOL
        largo_ok = abs(largo - al) <= TOL
        if "completa" in r:
            cerca["completa"] = r["completa"]
        else:
            cerca["completa"] = ancho_ok and largo_ok
        if cerca["completa"]:
            cerca["tipo_corte"] = "completa"
        elif ancho_ok:
            cerca["tipo_corte"] = "corte_largo"
        elif largo_ok:
            cerca["tipo_corte"] = "corte_ancho"
        else:
            cerca["tipo_corte"] = "corte_esquina"

    # IDs y baldosa de corte, por (planta, material)
    grupos = defaultdict(list)
    for p in anotadas:
        grupos[(p["planta"], p["material"])].append(p)

    for (pl, material), ps in grupos.items():
        ps.sort(key=lambda q: (-q["y"], q["x"]))           # orden de lectura
        pref = f'{PREF_PLANTA[pl]}-{PREF_MAT[material]}'
        for i, p in enumerate(ps, 1):
            p["id"] = f"{pref}-{i:03d}"

        ancho, largo = PISOS[material]
        recortes = [p for p in ps if not p["completa"]]
        entradas = [(*ajustar(p["ancho"], p["largo"], ancho, largo), p["id"]) for p in recortes]
        baldosas = empaquetar(entradas, material, 0.0, False)
        pc = PREF_CORTE[material]
        mapa = {}
        for idx, b in enumerate(baldosas, 1):
            for (x, y, w, l, pid, rot) in b.piezas:
                mapa[pid] = f"{pc}-{idx:02d}"
        for p in ps:
            p["corte_de"] = mapa.get(p["id"], "")

    cargar_anotado.excluidas = excluidas
    return anotadas


cargar_anotado.excluidas = 0


if __name__ == "__main__":
    ps = cargar_anotado()
    print(f"Piezas anotadas: {len(ps)}   (charolas excluidas: {cargar_anotado.excluidas})")
    agg = defaultdict(lambda: [0, 0])
    for p in ps:
        k = (p["planta"], p["material"])
        agg[k][0] += 1
        agg[k][1] += 0 if p["completa"] else 1
    for k in sorted(agg):
        print(f"  Planta {k[0]:5} {k[1]:13}: {agg[k][0]:3} piezas ({agg[k][1]} recortes)")
