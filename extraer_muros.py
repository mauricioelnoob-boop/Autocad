#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extraer_muros.py
================
Extrae los MUROS REALES del DWG (capas A-MUROS, A-MUROS BAJOS y A-CANCELERIA,
con cualquier prefijo de bloque) y los guarda como bandas (polígonos) en
muros_real_<modelo>.json. Estas son las líneas de cara de muro; se engrosan
0.09 m para formar la banda del muro.

Uso: python3 extraer_muros.py <Modelo>
"""
import json
import sys
from shapely.geometry import LineString
from shapely.ops import unary_union
from modelos import MODELOS

SUFIJOS = ("A-MUROS", "A-MUROS BAJOS", "A-CANCELERIA")


def _capa(o, capas):
    l = o.get("layer")
    return capas.get(l[-1], "?") if isinstance(l, list) else "?"


def _quiere(ln):
    return any(ln == s or ln.endswith("$" + s) or ln.endswith(" " + s) for s in SUFIJOS)


def extraer(modelo):
    cfg = MODELOS[modelo]
    raw = open(cfg["json"], "rb").read()
    doc = json.loads(raw.decode("utf-8", "replace"))
    objs = doc["OBJECTS"]
    capas = {}
    for o in objs:
        if o.get("object") == "LAYER":
            h = o.get("handle")
            if isinstance(h, list):
                capas[h[-1]] = o.get("name")
    segs = []
    for o in objs:
        if not _quiere(_capa(o, capas)):
            continue
        e = o.get("entity")
        if e == "LWPOLYLINE":
            pts = [(p[0], p[1]) for p in o.get("points", [])]
            segs += [(a, b) for a, b in zip(pts, pts[1:]) if a != b]
            if o.get("flag", 0) & 1 and len(pts) > 2:
                segs.append((pts[-1], pts[0]))
        elif e == "LINE":
            s = o.get("start"); en = o.get("end")
            if s and en and (s[0], s[1]) != (en[0], en[1]):
                segs.append(((s[0], s[1]), (en[0], en[1])))
    band = unary_union([LineString([a, b]).buffer(0.09, cap_style=2) for a, b in segs])
    polys = list(getattr(band, "geoms", [band]))
    salida = [list(p.exterior.coords) for p in polys if not p.is_empty]
    out = f"muros_real_{modelo.lower()}.json"
    json.dump(salida, open(out, "w"), separators=(",", ":"))
    print(f"{modelo}: {len(segs)} segmentos -> {len(salida)} bandas de muro -> {out}")


if __name__ == "__main__":
    ms = sys.argv[1:] or list(MODELOS)
    for m in ms:
        extraer(m)
