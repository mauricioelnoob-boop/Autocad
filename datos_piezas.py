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


def planta_de(p):
    return "baja" if p["x"] < X_CORTE else "alta"


def cargar_anotado(path="piezas_piso.json"):
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
