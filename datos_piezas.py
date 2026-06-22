#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
datos_piezas.py
===============

Carga el despiece de un modelo y lo ANOTA con planta, material correcto, ID y
de qué pieza de corte sale cada recorte. Toda la configuración específica del
modelo (corte de plantas, regiones de recámaras, etc.) está en modelos.py.

Reglas:
  * Planta baja (x < x_corte): sólo Moret. Los tablones de 0.20 m en planta baja
    son charolas de baño (otro piso) y se excluyen.
  * Planta alta: una pieza es Royal Walnut sólo si es un tablón de ~0.20 m dentro
    de una región de recámara; las piezas de ~0.60 m (baño/vestidor) siguen Moret.
  * Lo demás es Moret.

Función principal:  cargar_anotado(modelo) -> lista de piezas anotadas.
"""

import json
from collections import defaultdict

from optimizador_recortes import PISOS, ajustar, empaquetar
from modelos import MODELOS

PREF_PLANTA = {"baja": "PB", "alta": "PA"}
PREF_MAT = {"Moret": "M", "Royal Walnut": "R"}
PREF_CORTE = {"Moret": "M", "Royal Walnut": "RW"}

ANCHO_ROYAL = 0.20     # ancho del tablón Royal Walnut
LIMITE_MORET = 0.35    # un lado corto > esto = pieza Moret (no cabe en recámara)


def en_region(p, reg):
    return reg[0] <= p["x"] <= reg[1] and reg[2] <= p["y"] <= reg[3]


def en_bbox(p, bb):
    return bb is None or (bb[0] <= p["x"] <= bb[1] and bb[2] <= p["y"] <= bb[3])


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


def recortar(anotadas, muros_path):
    """Recorta las piezas según los MUROS y la frontera de material:
      * En la recámara manda Royal: las piezas Moret que pisan Royal se recortan
        a la parte que NO pisa Royal (corte de pared/transición que faltaba).
      * Todas las piezas se recortan por los muros estructurales.
    Devuelve (lista_filtrada, n_recortadas). Si no hay shapely, no hace nada."""
    try:
        from shapely.geometry import box, Polygon
        from shapely.ops import unary_union
    except Exception:
        return anotadas, 0

    def rect(p):
        return box(p["x0"], p["y0"], p["x0"] + p["wx"], p["y0"] + p["hy"])

    def es_muro_delgado(poly):
        # Muros reales = bandas delgadas. Descarta contornos de cuarto rellenados
        # (área grande Y ancho mínimo grande), que recortarían de más.
        xs = [a[0] for a in poly]; ys = [a[1] for a in poly]
        mindim = min(max(xs) - min(xs), max(ys) - min(ys))
        return not (Polygon(poly).buffer(0).area > 2.0 and mindim > 0.5)

    try:
        raw = json.load(open(muros_path, encoding="utf-8"))
        muros = unary_union([Polygon(m).buffer(0) for m in raw
                             if len(m) >= 3 and es_muro_delgado(m)])
    except Exception:
        from shapely.geometry import GeometryCollection
        muros = GeometryCollection()

    royal = unary_union([rect(p) for p in anotadas if p["material"] == "Royal Walnut"])

    def trim(p, obst):
        """Hace UN corte recto (guillotina) para quitar el traslape con obst,
        dejando el rectángulo más grande sin traslape. Devuelve True si cortó,
        False si no lo toca, None si no se puede limpiar con un corte (quitar)."""
        r = rect(p)
        inter = r.intersection(obst)
        if inter.area < 0.02 * r.area:
            return False
        ix0, iy0, ix1, iy1 = inter.bounds
        rx0, ry0, rx1, ry1 = p["x0"], p["y0"], p["x0"] + p["wx"], p["y0"] + p["hy"]
        cands = []
        if iy0 > ry0 + 0.02: cands.append((rx0, ry0, rx1, iy0))   # conservar abajo
        if iy1 < ry1 - 0.02: cands.append((rx0, iy1, rx1, ry1))   # conservar arriba
        if ix0 > rx0 + 0.02: cands.append((rx0, ry0, ix0, ry1))   # conservar izquierda
        if ix1 < rx1 - 0.02: cands.append((ix1, ry0, rx1, ry1))   # conservar derecha
        best = None
        for (a, b, c, d) in cands:
            cand = box(a, b, c, d)
            if cand.intersection(obst).area < 0.02 * cand.area:
                if best is None or cand.area > best[0]:
                    best = (cand.area, a, b, c, d)
        if best is None:
            return None
        _, a, b, c, d = best
        p["x0"], p["y0"] = round(a, 4), round(b, 4)
        p["wx"], p["hy"] = round(c - a, 4), round(d - b, 4)
        p["x"], p["y"] = round((a + c) / 2, 3), round((b + d) / 2, 3)
        _retipo(p)
        return True

    salida, recortadas = [], 0
    for p in anotadas:
        if rect(p).area <= 0:
            salida.append(p); continue
        # 1) En la recámara manda Royal: una pieza Moret mayoritariamente dentro
        #    de Royal es un error del despiece -> se quita; si sólo asoma, se recorta.
        if p["material"] == "Moret":
            r = rect(p)
            frac = r.intersection(royal).area / r.area
            if frac > 0.50:
                recortadas += 1
                continue
            if frac > 0.03:
                if trim(p, royal) is None:    # no se limpia con un corte -> quitar
                    recortadas += 1
                    continue
                recortadas += 1
        # 2) Corte por muros estructurales (delgados)
        if not muros.is_empty:
            res = trim(p, muros)
            if res is None:
                recortadas += 1
                continue
            if res:
                recortadas += 1
        salida.append(p)
    return salida, recortadas


def rellenar_huecos(anotadas):
    """Genera las piezas que el DWG olvidó dibujar: huecos ENTRE piezas dentro de
    una misma columna o fila (hay pieza a ambos lados del hueco), de hasta ~1
    tablón. No rellena orillas abiertas ni vacíos grandes entre cuartos."""
    nuevos = []
    for eje in ("col", "fila"):
        bandas = defaultdict(list)
        for p in anotadas:
            clave = round(p["x0"], 2) if eje == "col" else round(p["y0"], 2)
            bandas[(p["planta"], p["material"], clave)].append(p)
        for (pl, mat, _), lst in bandas.items():
            if len(lst) < 2:
                continue
            if eje == "col":
                lst.sort(key=lambda p: p["y0"])
                ext = sorted(p["wx"] for p in lst)[len(lst) // 2]   # ancho típico
                lim = PISOS[mat][1] + 0.05                          # 1 tablón de largo
            else:
                lst.sort(key=lambda p: p["x0"])
                ext = sorted(p["hy"] for p in lst)[len(lst) // 2]
                lim = PISOS[mat][0] + 0.05
            for a, b in zip(lst, lst[1:]):
                if eje == "col":
                    ini = a["y0"] + a["hy"]; gap = b["y0"] - ini
                else:
                    ini = a["x0"] + a["wx"]; gap = b["x0"] - ini
                if not (0.06 < gap <= lim):
                    continue
                if eje == "col":
                    p = _nueva(mat, pl, a["x0"], ini, ext, gap)
                else:
                    p = _nueva(mat, pl, ini, a["y0"], gap, ext)
                nuevos.append(p)

    # Seguridad anti-fantasmas: descarta rellenos que se encimen con una pieza
    # real o con otro relleno (=el "hueco" en realidad estaba ocupado).
    try:
        from shapely.geometry import box
        from shapely.ops import unary_union
        reales = unary_union([box(q["x0"], q["y0"], q["x0"] + q["wx"], q["y0"] + q["hy"])
                              for q in anotadas])
    except Exception:
        return nuevos
    buenos = []
    ocupado = reales
    for p in sorted(nuevos, key=lambda q: -q["wx"] * q["hy"]):
        r = box(p["x0"], p["y0"], p["x0"] + p["wx"], p["y0"] + p["hy"])
        if r.area <= 0 or r.intersection(ocupado).area > 0.10 * r.area:
            continue
        buenos.append(p)
        ocupado = unary_union([ocupado, r])
    return buenos


def _nueva(mat, pl, x0, y0, wx, hy):
    p = {"material": mat, "x0": round(x0, 4), "y0": round(y0, 4),
         "wx": round(wx, 4), "hy": round(hy, 4),
         "x": round(x0 + wx / 2, 3), "y": round(y0 + hy / 2, 3),
         "planta": pl, "relleno": True}
    _retipo(p)
    return p


def cargar_anotado(modelo="Cabernet"):
    cfg = MODELOS[modelo]
    piezas = json.load(open(cfg["piezas"], encoding="utf-8"))
    x_corte = cfg["x_corte"]
    bbox = cfg.get("bbox_valido")

    def planta_de(p):
        return "baja" if p["x"] < x_corte else "alta"

    # Claves de acabado del propio plano (capa A-ACABADOS PISOS):
    #   1 = Moret Arena   3 = Royal Walnut   2/4/5 = otro piso (concreto/baños)
    claves = json.load(open(cfg["claves"], encoding="utf-8"))

    def clusters_royal_y_otro(piezas):
        """Agrupa los tablones de 0.20 m en cuartos (componentes conexas) y
        etiqueta cada cuarto con la clave que cae dentro de su recuadro:
        '3' -> Royal Walnut, '4'/'5' -> otro piso (baño) a excluir."""
        planks = [p for p in piezas if abs(min(p["wx"], p["hy"]) - ANCHO_ROYAL) < 0.06]
        n = len(planks)
        par = list(range(n))

        def find(a):
            while par[a] != a:
                par[a] = par[par[a]]; a = par[a]
            return a

        def cerca(a, b):                    # rects casi tocándose
            return not (a["x0"] + a["wx"] + 0.10 < b["x0"] or b["x0"] + b["wx"] + 0.10 < a["x0"]
                        or a["y0"] + a["hy"] + 0.10 < b["y0"] or b["y0"] + b["hy"] + 0.10 < a["y0"])

        for i in range(n):
            for j in range(i + 1, n):
                if cerca(planks[i], planks[j]):
                    par[find(i)] = find(j)
        grupos = defaultdict(list)
        for i, p in enumerate(planks):
            grupos[find(i)].append(p)

        royal_ids, otro_ids = set(), set()
        for g in grupos.values():
            x0 = min(q["x0"] for q in g) - 0.3; x1 = max(q["x0"] + q["wx"] for q in g) + 0.3
            y0 = min(q["y0"] for q in g) - 0.3; y1 = max(q["y0"] + q["hy"] for q in g) + 0.3
            dentro = [k[0] for k in claves if x0 <= k[1] <= x1 and y0 <= k[2] <= y1]
            if "3" in dentro:
                royal_ids |= {id(q) for q in g}
            elif any(c in dentro for c in ("4", "5")):
                otro_ids |= {id(q) for q in g}
        return royal_ids, otro_ids

    royal_ids, otro_ids = clusters_royal_y_otro(piezas)

    def material_de(p):
        if id(p) in otro_ids:
            return None                      # baño / otro piso -> excluir
        if id(p) in royal_ids:
            return "Royal Walnut"
        return "Moret"

    anotadas = []
    excluidas = 0
    for p in piezas:
        if not en_bbox(p, bbox):                 # descarta bloques sueltos / detalles
            continue
        mat = material_de(p)
        if mat is None:                          # otro piso (concreto, baño) -> excluir
            excluidas += 1
            continue
        p["planta"] = planta_de(p)
        if mat != p["material"]:
            p["material"] = mat
            _retipo(p)
        anotadas.append(p)

    # Piezas faltantes agregadas a mano (p.ej. el arranque de Moret)
    for extra in cfg.get("piezas_extra", []):
        e = dict(extra)
        e["planta"] = planta_de(e)
        anotadas.append(e)

    # Correcciones puntuales en la frontera (por ubicación)
    for r in cfg.get("reclasificar", []):
        cerca = min(anotadas, key=lambda p: (p["x"] - r["x"])**2 + (p["y"] - r["y"])**2)
        if (cerca["x"] - r["x"])**2 + (cerca["y"] - r["y"])**2 > 0.25:
            continue
        cerca["material"] = r["material"]
        _retipo(cerca)
        if "completa" in r:
            cerca["completa"] = r["completa"]
            if not r["completa"] and cerca["tipo_corte"] == "completa":
                cerca["tipo_corte"] = "corte_largo"

    # Generar las piezas que el DWG olvidó dibujar (huecos internos de columna)
    rellenos = rellenar_huecos(anotadas)
    anotadas.extend(rellenos)
    cargar_anotado.rellenadas = len(rellenos)

    # Recorte por muros y frontera de material (Royal manda en la recámara)
    anotadas, cargar_anotado.recortadas = recortar(anotadas, cfg.get("muros", ""))

    # Zonas que NO se despiezan (escalera, boiler, hueco de cancelería): se
    # quitan al final para que tampoco sobrevivan piezas rellenadas en ese hueco.
    cajas = cfg.get("cajas_excluir", [])
    if cajas:
        def _excluida(p):
            return any(c[0] <= p["x"] <= c[1] and c[2] <= p["y"] <= c[3] for c in cajas)
        antes = len(anotadas)
        anotadas = [p for p in anotadas if not _excluida(p)]
        excluidas += antes - len(anotadas)

    # IDs y pieza de corte, por (planta, material)
    asignar_ids_corte(anotadas)

    cargar_anotado.excluidas = excluidas
    return anotadas


def asignar_ids_corte(anotadas):
    """Asigna ID por (planta, material) en orden de lectura y calcula de qué
    pieza de corte sale cada recorte (optimización por planta+material)."""
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



cargar_anotado.excluidas = 0
cargar_anotado.recortadas = 0


if __name__ == "__main__":
    import sys
    modelo = sys.argv[1] if len(sys.argv) > 1 else "Cabernet"
    ps = cargar_anotado(modelo)
    print(f"{modelo}: {len(ps)} piezas   (charolas excluidas: {cargar_anotado.excluidas}, "
          f"recortadas por muro/frontera: {cargar_anotado.recortadas})")
    agg = defaultdict(lambda: [0, 0])
    for p in ps:
        k = (p["planta"], p["material"])
        agg[k][0] += 1
        agg[k][1] += 0 if p["completa"] else 1
    for k in sorted(agg):
        print(f"  Planta {k[0]:5} {k[1]:13}: {agg[k][0]:3} piezas ({agg[k][1]} recortes)")
