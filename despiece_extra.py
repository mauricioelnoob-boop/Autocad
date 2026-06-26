#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
despiece_extra.py
=================
Despiece de los acabados Moret que NO van en el piso plano:

  1) MURO DE REGADERA  (piso Moret ACOSTADO en las 3 caras: fondo 1.50 m + 2
     laterales 1.20 m; alto = NPT-losa; se descuenta la ventana del fondo).
  2) ESCALERA          (piso Moret en PERALTES y HUELLAS). Datos del cliente:
     ancho 1.15 m, peralte 0.175 m, huella 0.27 m.
        - Cabernet y Merlot: 7 escalones + descanso (2 piezas enteras + 2 recortes
          grandes) + 7 escalones (el 8º es la losa de entrepiso).
        - Chardonnay: 6 escalones + descanso (1 entera + 1 recorte grande) + 2
          escalones + descanso (1 entera + 1 recorte grande) + 6 escalones.
          Lleva zoclo de 0.15 m por la orilla, pegado al muro, desde el 1er descanso.
     Cada peralte (P1, P2, …) y cada huella (H1, H2, …) es un RECORTE que se saca
     de una baldosa completa; el despiece muestra de qué baldosa sale cada uno.
"""
import math
import generadores as G
from optimizador_recortes import empaquetar

TW, TH = G.MORET[0], G.MORET[1]      # baldosa: 1.194 (largo) x 0.596 (corto)
M_M2 = TW * TH


def _tablones(pzs):
    """Tablones Moret ENTEROS que se consumen al cortar estas piezas, por
    rendimiento real (bin-packing guillotina del proyecto, con kerf de sierra).
    Cuenta el desperdicio de corte que el método por ÁREA ignoraba: peraltes,
    huellas y recortes de orilla salen de un tablón entero y dejan sobrante."""
    rec = [(p["ancho"], p["largo"], p.get("id", "")) for p in pzs]
    return len(empaquetar(rec, "Moret", G.ZOCLO_KERF, False))

# ----- regadera -----
def _tile_pared(w, h, etiqueta):
    """Despieza una pared w (ancho) x h (alto) con piezas acostadas TWxTH.

    Un residuo final menor a 2 cm (p.ej. 1.20 m de pared con tabla de 1.194 m
    deja 6 mm) NO genera pieza: es tolerancia de boquilla, no un recorte real."""
    RES = 0.02
    pzs = []
    y = 0.0
    while y < h - RES:
        hh = min(TH, h - y)
        x = 0.0
        while x < w - RES:
            ww = min(TW, w - x)
            corto, largo = min(ww, hh), max(ww, hh)
            completa = abs(ww - TW) < 0.012 and abs(hh - TH) < 0.012
            pzs.append({"x": round(x, 4), "y": round(y, 4),
                        "w": round(ww, 4), "h": round(hh, 4),
                        "ancho": round(corto, 4), "largo": round(largo, 4),
                        "completa": completa, "pared": etiqueta})
            x += TW
        y += TH
    return pzs


def regadera_paredes(modelo):
    out = []
    for k, (planta, h) in enumerate(G.GEN[modelo]["regaderas"], 1):
        hf = max(0.0, h - G.VENTANA_ALTO)
        out.append((f"Regadera {k} ({planta}) — fondo {G.REG_FONDO:.2f}×{hf:.2f}",
                    G.REG_FONDO, hf, _tile_pared(G.REG_FONDO, hf, f"R{k}-fondo")))
        for lado in ("izq", "der"):
            out.append((f"Regadera {k} ({planta}) — lateral {lado} 1.20×{h:.2f}",
                        1.20, h, _tile_pared(1.20, h, f"R{k}-lat-{lado}")))
    return out


def regadera_resumen(modelo):
    pzs = [p for _t, _w, _h, ps in regadera_paredes(modelo) for p in ps]
    comp = sum(1 for p in pzs if p["completa"])
    rec = sum(1 for p in pzs if not p["completa"])
    area = sum(p["w"] * p["h"] for p in pzs)
    tablones = _tablones(pzs)
    return {"piezas": pzs, "completas": comp, "recortes": rec, "m2": area,
            "tablones": tablones,
            "cajas": math.ceil(tablones * 1.1 / G.MORET_PZCAJA)}


# ----- escalera -----
ESC_ANCHO = 1.15
PERALTE = 0.175
HUELLA = 0.27
DESC_REC_LARGO = 0.70     # largo del "recorte grande" del descanso (ancho = 0.596)

ESCALERA = {
    "Cabernet":   {"tramos": [7, 7],    "descansos": [(2, 2)]},
    "Merlot":     {"tramos": [7, 7],    "descansos": [(2, 2)]},
    "Chardonnay": {"tramos": [6, 2, 6], "descansos": [(1, 1), (1, 1)], "zoclo_orilla": True},
}


def escalera_piezas(modelo):
    """Lista de piezas de la escalera. Peraltes/huellas y recortes de descanso son
    RECORTES; las piezas enteras de descanso son completas. ancho<=largo."""
    cfg = ESCALERA[modelo]
    n = sum(cfg["tramos"])
    pzs = []
    for i in range(n):
        pzs.append({"id": f"P{i+1}", "ancho": PERALTE, "largo": ESC_ANCHO,
                    "completa": False, "tipo": "peralte"})
    for i in range(n):
        pzs.append({"id": f"H{i+1}", "ancho": HUELLA, "largo": ESC_ANCHO,
                    "completa": False, "tipo": "huella"})
    d = 0
    for (ent, rec) in cfg["descansos"]:
        d += 1
        for j in range(ent):
            pzs.append({"id": f"D{d}-E{j+1}", "ancho": round(TH, 3), "largo": round(TW, 3),
                        "completa": True, "tipo": "descanso-entera"})
        for j in range(rec):
            pzs.append({"id": f"D{d}-R{j+1}", "ancho": round(TH, 3), "largo": DESC_REC_LARGO,
                        "completa": False, "tipo": "descanso-recorte"})
    return pzs


def escalera_resumen(modelo):
    cfg = ESCALERA[modelo]
    pzs = escalera_piezas(modelo)
    n = sum(cfg["tramos"])
    comp = sum(1 for p in pzs if p["completa"])
    rec = sum(1 for p in pzs if not p["completa"])
    # m2 instalado: peraltes + huellas + descansos
    area = sum(p["ancho"] * p["largo"] for p in pzs)
    tablones = _tablones(pzs)
    return {"piezas": pzs, "completas": comp, "recortes": rec, "m2": area,
            "n_escalones": n, "tramos": cfg["tramos"], "descansos": cfg["descansos"],
            "zoclo_orilla": cfg.get("zoclo_orilla", False),
            "tablones": tablones,
            "cajas": math.ceil(tablones * 1.15 / G.MORET_PZCAJA)}


if __name__ == "__main__":
    import sys
    for m in (sys.argv[1:] or ["Cabernet", "Merlot", "Chardonnay"]):
        r = regadera_resumen(m); e = escalera_resumen(m)
        print(f"{m}: regadera {r['m2']:.2f} m2 ({r['completas']}c/{r['recortes']}r) -> {r['cajas']} cajas"
              f"  |  escalera {e['n_escalones']} escalones, {e['m2']:.2f} m2 "
              f"({e['completas']}c/{e['recortes']}r) -> {e['cajas']} cajas  zoclo_orilla={e['zoclo_orilla']}")
