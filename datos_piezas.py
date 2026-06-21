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


def cargar_anotado(modelo="Cabernet"):
    cfg = MODELOS[modelo]
    piezas = json.load(open(cfg["piezas"], encoding="utf-8"))
    x_corte = cfg["x_corte"]
    regiones = cfg["regiones_royal"]
    bbox = cfg.get("bbox_valido")

    def planta_de(p):
        return "baja" if p["x"] < x_corte else "alta"

    anotadas = []
    excluidas = 0
    for p in piezas:
        if not en_bbox(p, bbox):                 # descarta bloques sueltos / detalles
            continue
        pl = planta_de(p)
        # Charolas de baño en planta baja (tablón 0.20 m) = otro piso -> excluir
        if cfg.get("excluir_royal_baja") and pl == "baja" \
                and abs(min(p["wx"], p["hy"]) - ANCHO_ROYAL) < 0.06:
            excluidas += 1
            continue
        p["planta"] = pl
        anotadas.append(p)

    # Piezas faltantes agregadas a mano (p.ej. el arranque de Moret)
    for extra in cfg.get("piezas_extra", []):
        e = dict(extra)
        e["planta"] = planta_de(e)
        anotadas.append(e)

    # Material por REGIÓN: Royal sólo si es tablón de 0.20 dentro de una recámara.
    for p in anotadas:
        corto = min(p["wx"], p["hy"])
        if p["planta"] == "alta" and corto <= LIMITE_MORET \
                and any(en_region(p, r) for r in regiones):
            debe = "Royal Walnut"
        else:
            debe = "Moret"
        if debe != p["material"]:
            p["material"] = debe
            _retipo(p)

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

    # IDs y pieza de corte, por (planta, material)
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
    import sys
    modelo = sys.argv[1] if len(sys.argv) > 1 else "Cabernet"
    ps = cargar_anotado(modelo)
    print(f"{modelo}: {len(ps)} piezas   (charolas excluidas: {cargar_anotado.excluidas})")
    agg = defaultdict(lambda: [0, 0])
    for p in ps:
        k = (p["planta"], p["material"])
        agg[k][0] += 1
        agg[k][1] += 0 if p["completa"] else 1
    for k in sorted(agg):
        print(f"  Planta {k[0]:5} {k[1]:13}: {agg[k][0]:3} piezas ({agg[k][1]} recortes)")
