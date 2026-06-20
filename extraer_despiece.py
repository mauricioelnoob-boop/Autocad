#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extraer_despiece.py
===================

Lee el despiece de piso YA DIBUJADO en el plano de AutoCAD y lo convierte en
una lista limpia de piezas (material, ancho, largo, si es completa o recorte).

El plano viene en formato DWG (binario de AutoCAD). Como DWG no se puede leer
directamente con Python, primero se convierte a JSON con LibreDWG:

    dwgread -O JSON -o pisos.json  plano.dwg

(LibreDWG: https://github.com/LibreDWG/libredwg ; el ejecutable `dwgread`).

Este script toma ese JSON, busca las polilíneas de la capa del despiece
(por defecto "A-PISO"), mide el rectángulo de cada pieza y la clasifica como
piso "Moret" (0.596 x 1.194 m) o "Royal Walnut" (0.2 x 1.2 m).

Salida:
    piezas_piso.json  -> lista de piezas para el optimizador
    piezas_piso.csv   -> la misma lista, para abrir en Excel

Uso:
    python3 extraer_despiece.py  pisos.json  [--capa A-PISO]
"""

import json
import csv
import sys
import argparse

# --------------------------------------------------------------------------
# Definición de los pisos (medidas nominales en metros)
# --------------------------------------------------------------------------
PISOS = {
    "Moret":        {"ancho": 0.596, "largo": 1.194},
    "Royal Walnut": {"ancho": 0.200, "largo": 1.200},
}

# Tolerancia para considerar dos medidas "iguales" (8 mm).
# Absorbe el redondeo del dibujo (p.ej. 0.6 dibujado vs 0.596 real, 1.192 vs 1.194).
TOL = 0.012


def cargar_json(path):
    """Carga el JSON de LibreDWG tolerando bytes no-UTF8 (acentos latin-1)."""
    raw = open(path, "rb").read()
    return json.loads(raw.decode("utf-8", errors="replace"))


def mapa_capas(objetos):
    """handle absoluto de la capa -> nombre de la capa."""
    capas = {}
    for o in objetos:
        if o.get("object") == "LAYER":
            h = o.get("handle")
            if isinstance(h, list):
                capas[h[-1]] = o.get("name")
    return capas


def nombre_capa(o, capas):
    l = o.get("layer")
    if isinstance(l, list):
        return capas.get(l[-1], "?")
    return "?"


def bbox(puntos):
    """Ancho, alto y centroide del rectángulo que envuelve a la polilínea."""
    xs = [p[0] for p in puntos]
    ys = [p[1] for p in puntos]
    cx = (max(xs) + min(xs)) / 2.0
    cy = (max(ys) + min(ys)) / 2.0
    return max(xs) - min(xs), max(ys) - min(ys), cx, cy


def clasificar(corto, largo):
    """
    Decide a qué piso pertenece la pieza y si es completa o recorte.

    Devuelve dict con material, ancho, largo, completa(bool), tipo_corte,
    o None si el rectángulo no es una pieza de piso (contornos de cuarto, etc.).
    """
    # Descartar lo que no cabe en ninguna baldosa (contornos, marcos, muros...)
    max_ancho = max(p["ancho"] for p in PISOS.values())
    max_largo = max(p["largo"] for p in PISOS.values())
    if corto > max_ancho + 0.02 or largo > max_largo + 0.02:
        return None

    # --- Elegir material por el ANCHO (lado corto), que es lo más confiable ---
    moret = PISOS["Moret"]
    royal = PISOS["Royal Walnut"]

    if abs(corto - royal["ancho"]) <= 0.03:
        material = "Royal Walnut"
    elif corto > royal["ancho"] + 0.03:
        # Más ancho que un Royal (0.2) -> sólo puede ser Moret
        material = "Moret"
    else:
        # Tira muy angosta (< 0.2): ambiguo, se asigna por el largo
        material = "Royal Walnut" if abs(largo - royal["largo"]) < abs(largo - moret["largo"]) else "Moret"

    p = PISOS[material]
    ancho_completo = abs(corto - p["ancho"]) <= TOL
    largo_completo = abs(largo - p["largo"]) <= TOL
    completa = ancho_completo and largo_completo

    if completa:
        tipo = "completa"
    elif ancho_completo and not largo_completo:
        tipo = "corte_largo"      # se cortó a lo largo (lo más común)
    elif largo_completo and not ancho_completo:
        tipo = "corte_ancho"      # se cortó a lo ancho
    else:
        tipo = "corte_esquina"    # se cortó en las dos direcciones

    return {
        "material": material,
        "ancho": round(corto, 4),
        "largo": round(largo, 4),
        "completa": completa,
        "tipo_corte": tipo,
    }


def extraer(json_path, capa_objetivo):
    doc = cargar_json(json_path)
    objetos = doc["OBJECTS"]
    capas = mapa_capas(objetos)

    piezas = []
    descartadas = 0
    for o in objetos:
        if o.get("entity") != "LWPOLYLINE":
            continue
        if nombre_capa(o, capas) != capa_objetivo:
            continue
        pts = o.get("points", [])
        if len(pts) < 3:
            continue
        w, h, cx, cy = bbox(pts)
        if w <= 0.001 or h <= 0.001:
            continue
        corto, largo = (w, h) if w <= h else (h, w)
        info = clasificar(round(corto, 4), round(largo, 4))
        if info is None:
            descartadas += 1
            continue
        info["x"] = round(cx, 3)   # ubicación en el plano (centro de la pieza)
        info["y"] = round(cy, 3)
        info["handle"] = o.get("handle")
        piezas.append(info)

    return piezas, descartadas


def main():
    ap = argparse.ArgumentParser(description="Extrae el despiece de piso de un JSON de LibreDWG")
    ap.add_argument("json", help="archivo JSON generado con: dwgread -O JSON -o pisos.json plano.dwg")
    ap.add_argument("--capa", default="A-PISO", help="capa del despiece (default: A-PISO)")
    ap.add_argument("--out", default="piezas_piso", help="prefijo de los archivos de salida")
    args = ap.parse_args()

    piezas, descartadas = extraer(args.json, args.capa)

    # Quitar el handle de la salida JSON principal (lo dejamos sólo en CSV por trazabilidad)
    salida = [{k: v for k, v in p.items() if k != "handle"} for p in piezas]
    with open(args.out + ".json", "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)

    with open(args.out + ".csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["material", "ancho_m", "largo_m", "completa", "tipo_corte", "x_plano", "y_plano"])
        for p in piezas:
            w.writerow([p["material"], p["ancho"], p["largo"],
                        "si" if p["completa"] else "no", p["tipo_corte"],
                        p["x"], p["y"]])

    # Resumen en pantalla
    from collections import Counter
    print(f"Capa: {args.capa}")
    print(f"Piezas de piso encontradas: {len(piezas)}   (rectángulos descartados: {descartadas})")
    for mat in PISOS:
        ps = [p for p in piezas if p["material"] == mat]
        comp = sum(1 for p in ps if p["completa"])
        print(f"  - {mat:13}: {len(ps):3} piezas  ({comp} completas, {len(ps)-comp} recortes)")
    print(f"\nGuardado: {args.out}.json  y  {args.out}.csv")


if __name__ == "__main__":
    main()
