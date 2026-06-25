#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verificar_huecos.py
===================
Auditoría 'como tercero': detecta zonas DENTRO de la casa que quedaron sin piso
(huecos del A-PISO mal cerrado) y las dibuja en ROJO sobre el plano con los muros
reales. Excluye regaderas/concreto y zonas no despiezadas. Sirve para comprobar
que todo el interior tenga piso.

Uso:  python3 verificar_huecos.py [Modelo]
"""
import json, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon as MplPoly
from datos_piezas import cargar_anotado
from modelos import MODELOS
from shapely.geometry import box, Polygon
from shapely.ops import unary_union

COL = {"Moret": "#f4c542", "Royal Walnut": "#cf3a3a"}


def huecos(m):
    ps = cargar_anotado(m)
    cfg = MODELOS[m]
    cl = json.load(open(f"claves_{m.lower()}.json", encoding="latin-1"))
    cajas = cfg.get("cajas_excluir", [])
    walls = unary_union([Polygon(p).buffer(0) for p in json.load(open(f"muros_real_{m.lower()}.json"))])
    floor = unary_union([box(p["x0"], p["y0"], p["x0"]+p["wx"], p["y0"]+p["hy"]) for p in ps])
    solid = unary_union([floor, walls])
    closed = solid.buffer(0.30, join_style=2).buffer(-0.30, join_style=2)

    def otro(gx, gy):
        c = min(cl, key=lambda k: (k[1]-gx)**2 + (k[2]-gy)**2)
        return c[0] in ("2", "4", "5") and (c[1]-gx)**2 + (c[2]-gy)**2 < 0.9

    gaps = []
    for g in getattr(closed.difference(solid), "geoms", [closed.difference(solid)]):
        if not (0.03 < g.area < 1.2):
            continue
        if g.buffer(0.04).intersection(floor).area < 0.02:
            continue
        # Descarta la RED DELGADA junto a muros (artefacto del cierre buffer): un
        # hueco real es COMPACTO; el artefacto se extiende por todo el plano con un
        # área mínima respecto a su bbox.
        bx0, by0, bx1, by1 = g.bounds
        bbox_area = (bx1 - bx0) * (by1 - by0)
        if bbox_area > 3.0 and g.area < 0.15 * bbox_area:
            continue
        gx, gy = g.centroid.x, g.centroid.y
        if any(c[0] <= gx <= c[1] and c[2] <= gy <= c[3] for c in cajas):
            continue
        if otro(gx, gy):
            continue
        gaps.append(g)
    return ps, gaps


def render(m, out):
    ps, gaps = huecos(m)
    fig, ax = plt.subplots(figsize=(20, 14))
    for poly in json.load(open(f"muros_real_{m.lower()}.json")):
        ax.add_patch(MplPoly(poly, closed=True, facecolor="#ccc", alpha=0.5))
    for p in ps:
        ax.add_patch(Rectangle((p["x0"], p["y0"]), p["wx"], p["hy"],
                     facecolor=COL[p["material"]], edgecolor="gray", lw=0.2, alpha=0.6))
    for g in gaps:
        xs, ys = g.exterior.xy
        ax.fill(xs, ys, facecolor="red", edgecolor="darkred", lw=1.4, alpha=0.9)
        print("   hueco area=%.3f en (%.2f,%.2f)" % (g.area, g.centroid.x, g.centroid.y))
    xs = [p["x0"] for p in ps]+[p["x0"]+p["wx"] for p in ps]
    ys = [p["y0"] for p in ps]+[p["y0"]+p["hy"] for p in ps]
    ax.set_xlim(min(xs)-1, max(xs)+1); ax.set_ylim(min(ys)-1, max(ys)+1); ax.set_aspect("equal")
    ax.set_title(f"{m}: ROJO = hueco interior sin piso ({len(gaps)})")
    plt.savefig(out, dpi=80, bbox_inches="tight"); plt.close()
    print(f"{m}: {len(gaps)} huecos interiores -> {out}")


if __name__ == "__main__":
    for m in ([sys.argv[1]] if len(sys.argv) > 1 else ["Cabernet", "Merlot", "Chardonnay"]):
        render(m, f"/tmp/huecos_{m}.png")
