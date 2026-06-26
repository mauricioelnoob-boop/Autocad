#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extraer_escalon.py
==================
Extrae las zonas de ESCALERA / ESCALÓN (capa A-ESCALON) como polígonos (envolvente
convexa de cada grupo de líneas). Estas zonas en PLANTA ALTA son VACÍO (la escalera
sube) y el piso NO debe pisarlas; el bbox de algunas piezas del despiece sí las pisa
porque el corte original era diagonal. Se guardan en escalon_<modelo>.json para que
el pipeline recorte las piezas que las invaden.

Sólo se guardan los grupos cuyo centro cae en PLANTA ALTA (x >= x_corte). En planta
baja el piso va POR DEBAJO de la escalera, así que NO se recorta.

Uso: python3 extraer_escalon.py [Modelo ...]
"""
import json, sys, math
from shapely.geometry import MultiPoint, LineString
from shapely.ops import unary_union
from modelos import MODELOS


def _capa(o, capas):
    l = o.get("layer")
    return capas.get(l[-1], "?") if isinstance(l, list) else "?"


def extraer(modelo):
    cfg = MODELOS[modelo]
    doc = json.loads(open(cfg["json"], "rb").read().decode("utf-8", "replace"))
    objs = doc["OBJECTS"]; capas = {}
    for o in objs:
        if o.get("object") == "LAYER":
            h = o.get("handle")
            if isinstance(h, list):
                capas[h[-1]] = o.get("name")
    pts = []
    for o in objs:
        if "A-ESCALON" not in _capa(o, capas):
            continue
        e = o.get("entity")
        if e == "LWPOLYLINE":
            pts.append([(p[0], p[1]) for p in o.get("points", [])])
        elif e == "LINE":
            s = o.get("start"); en = o.get("end")
            if s and en:
                pts.append([(s[0], s[1]), (en[0], en[1])])
    # agrupar por cercanía (union-find sobre cajas de cada polilínea)
    boxes = []
    for poly in pts:
        xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
        boxes.append([min(xs), min(ys), max(xs), max(ys), poly])
    n = len(boxes); par = list(range(n))
    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]; a = par[a]
        return a
    def cerca(A, B):
        return not (A[0] - 0.5 > B[2] or B[0] - 0.5 > A[2] or A[1] - 0.5 > B[3] or B[1] - 0.5 > A[3])
    for i in range(n):
        for j in range(i + 1, n):
            if cerca(boxes[i], boxes[j]):
                par[find(i)] = find(j)
    grupos = {}
    for i in range(n):
        grupos.setdefault(find(i), []).extend(boxes[i][4])
    xc = cfg.get("x_corte")
    salida = []
    for g, allpts in grupos.items():
        if len(allpts) < 3:
            continue
        hull = MultiPoint(allpts).convex_hull
        if hull.geom_type != "Polygon" or hull.area < 0.3:
            continue
        cx = hull.centroid.x
        planta = "baja" if (xc and cx < xc) else "alta"
        if planta != "alta":            # sólo PA es vacío
            continue
        salida.append(list(hull.exterior.coords))
    out = f"escalon_{modelo.lower()}.json"
    json.dump(salida, open(out, "w"), separators=(",", ":"))
    print(f"{modelo}: {len(salida)} zona(s) de escalera PA -> {out}")


if __name__ == "__main__":
    for m in (sys.argv[1:] or list(MODELOS)):
        extraer(m)
