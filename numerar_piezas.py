#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
numerar_piezas.py
=================

Reconstruye el plano a partir del DWG y le pone un CODIGO a cada baldosa del
despiece, para poder hablar de "esta pieza" sin ambiguedad.

El DWG (binario de AutoCAD 2010+) se convierte primero a JSON con LibreDWG:

    dwgread -O JSON -o plano.json plano_pisos.dwg
    python3 numerar_piezas.py plano.json

Codigo de cada pieza:  <PLANTA>-<MATERIAL>-<NNN>
  PLANTA   : PB (planta baja, mitad izquierda del dibujo)
             PA (planta alta, mitad derecha)
  MATERIAL : M = Moret (lado corto ~0.6),  R = Royal Walnut (lado corto ~0.2)
  NNN      : consecutivo dentro de cada (planta, material), en orden de lectura
             (de arriba hacia abajo por filas, y de izquierda a derecha).

NOTA: esta numeracion es la que genera este script; sirve como mapa comun.
Si tu plano de AutoCAD ya trae otra numeracion, usa este plano para mapear.

Salidas:
    numeracion_piezas.csv  -> codigo, planta, material, medidas, tipo y (x,y) en el plano
    PA_numerado.png        -> planta alta con cada pieza rotulada
    PB_numerado.png        -> planta baja con cada pieza rotulada
"""

import json
import csv
import re
import sys
import argparse

# Linea divisoria entre planta baja (x menor) y planta alta (x mayor).
X_SPLIT = 498.5

# Limites de una baldosa real (para descartar contornos de cuarto y la losa).
MORET = (0.596, 1.194)
ROYAL = (0.200, 1.200)


def cargar_json(path):
    return json.loads(open(path, "rb").read().decode("utf-8", errors="replace"))


def mapa_capas(objs):
    capas = {}
    for o in objs_iter(objs):
        if o.get("object") == "LAYER":
            h = o.get("handle")
            capas[h[-1] if isinstance(h, list) else h] = o.get("name")
    return capas


def objs_iter(objs):
    return objs


def nombre_capa(o, capas):
    l = o.get("layer")
    return capas.get(l[-1], "?") if isinstance(l, list) else "?"


def declean(t):
    t = re.sub(r"\\[A-Za-z][^;]*;", "", t)
    return re.sub(r"[{}]", "", t).strip()


def extraer_tiles(objs, capas):
    tiles = []
    for o in objs:
        if o.get("entity") != "LWPOLYLINE" or nombre_capa(o, capas) != "A-PISO":
            continue
        pts = o.get("points", [])
        if len(pts) < 3:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        short, lng = min(w, h), max(w, h)
        # Descartar contornos de cuarto / losa de regadera (no son baldosas)
        if short > 0.62 or lng > 1.25 or short < 0.02:
            continue
        if short > 0.32:
            mat = "M"
        elif abs(short - 0.2) < 0.07:
            mat = "R"
        else:
            mat = "R" if abs(lng - 1.2) < abs(lng - 1.194) else "M"
        tiles.append(dict(
            cx=(max(xs) + min(xs)) / 2, cy=(max(ys) + min(ys)) / 2,
            short=round(short, 3), lng=round(lng, 3), mat=mat,
            pts=list(zip(xs, ys)),
        ))
    return tiles


def numerar(tiles):
    """Asigna codigo PLANTA-MAT-NNN en orden de lectura."""
    grupos = {}
    for t in tiles:
        zona = "PB" if t["cx"] < X_SPLIT else "PA"
        grupos.setdefault((zona, t["mat"]), []).append(t)
    for (zona, mat), g in grupos.items():
        g.sort(key=lambda t: (-round(t["cy"], 1), t["cx"]))  # filas arriba->abajo, izq->der
        for i, t in enumerate(g, 1):
            t["code"] = f"{zona}-{mat}-{i:03d}"
            t["zona"] = zona
    return tiles


def es_recorte(t):
    return not (t["short"] > (0.55 if t["mat"] == "M" else 0.18) and t["lng"] > 1.17)


def render(tiles, objs, capas, zona, fname):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Polygon
    except Exception as e:
        print(f"(plano {zona} omitido: matplotlib no disponible: {e})")
        return
    grp = [t for t in tiles if t["zona"] == zona]
    xs = [t["cx"] for t in grp]
    ys = [t["cy"] for t in grp]
    X0, X1 = min(xs) - 0.8, max(xs) + 0.8
    Y0, Y1 = min(ys) - 0.8, max(ys) + 0.8
    fig, ax = plt.subplots(figsize=(15, 18))
    for t in grp:
        col = "#e0b074" if t["mat"] == "M" else "#7fa6cf"
        ax.add_patch(Polygon(t["pts"], closed=True, facecolor=col, edgecolor="#222",
                             lw=0.5, alpha=0.9 if es_recorte(t) else 0.5))
        sliver = t["short"] < 0.08
        ax.text(t["cx"], t["cy"], t["code"].split("-", 1)[1], fontsize=4.2,
                ha="center", va="center", color="red" if sliver else "black",
                weight="bold" if sliver else "normal",
                rotation=90 if t["lng"] > 0.8 and t["short"] < 0.3 else 0)
    # zoclos (rojo) y nombres de cuarto (verde) como contexto
    for o in objs:
        if o.get("entity") == "LWPOLYLINE" and nombre_capa(o, capas) == "A-ZOCLO":
            pts = o.get("points", [])
            if pts and X0 <= pts[0][0] <= X1 and Y0 <= pts[0][1] <= Y1:
                ax.add_patch(Polygon([(p[0], p[1]) for p in pts], closed=False,
                                     fill=False, edgecolor="red", lw=0.8))
        if o.get("entity") in ("TEXT", "MTEXT"):
            t = (o.get("text_value") or o.get("text") or "")
            pt = o.get("ins_pt") or [0, 0]
            x, y = (pt[0], pt[1]) if isinstance(pt, list) else (0, 0)
            tt = declean(t)
            if (X0 <= x <= X1 and Y0 <= y <= Y1 and re.search(
                    r"(?i)rec.mara|vestidor|regadera|principal|ba.o|cocina|comedor|"
                    r"sala|lava|escal|sube|baja|alacena", tt)):
                ax.text(x, y, tt[:14], fontsize=7, color="darkgreen", ha="center", weight="bold")
    ax.set_xlim(X0, X1)
    ax.set_ylim(Y0, Y1)
    ax.set_aspect("equal")
    ax.set_title(f"CABERNET (Prototipo 169) - {zona} - numeracion propuesta "
                 f"(rojo=sliver, verde=cuarto)", fontsize=11)
    ax.grid(True, alpha=0.15)
    fig.savefig(fname, dpi=110, bbox_inches="tight")
    print(f"  {fname}")


def main():
    ap = argparse.ArgumentParser(description="Numera las piezas del despiece desde el JSON de LibreDWG")
    ap.add_argument("json", help="JSON generado con: dwgread -O JSON -o plano.json plano_pisos.dwg")
    ap.add_argument("--csv", default="numeracion_piezas.csv")
    args = ap.parse_args()

    doc = cargar_json(args.json)
    objs = doc["OBJECTS"]
    capas = mapa_capas(objs)
    tiles = numerar(extraer_tiles(objs, capas))

    rows = []
    for t in sorted(tiles, key=lambda t: t["code"]):
        rows.append([t["code"], t["zona"], "Moret" if t["mat"] == "M" else "Royal Walnut",
                     t["short"], t["lng"], "recorte" if es_recorte(t) else "completa",
                     round(t["cx"], 3), round(t["cy"], 3)])
    with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["codigo", "planta", "material", "lado_corto_m", "lado_largo_m",
                    "tipo", "x_plano", "y_plano"])
        w.writerows(rows)

    print(f"Piezas numeradas: {len(rows)}")
    for z in ("PB", "PA"):
        for m in ("M", "R"):
            n = sum(1 for t in tiles if t["zona"] == z and t["mat"] == m)
            print(f"  {z}-{m}: {n}")
    print("Planos:")
    render(tiles, objs, capas, "PA", "PA_numerado.png")
    render(tiles, objs, capas, "PB", "PB_numerado.png")
    print(f"CSV: {args.csv}")


if __name__ == "__main__":
    main()
