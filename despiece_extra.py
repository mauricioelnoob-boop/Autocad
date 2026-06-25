#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
despiece_extra.py
=================
Despiece de los acabados Moret que NO van en el piso plano:

  1) MURO DE REGADERA  (piso Moret ACOSTADO en las 3 caras: fondo 1.50 m + 2
     laterales 1.20 m; alto = NPT-losa; se descuenta la ventana del fondo).
  2) ESCALERA          (piso Moret en peraltes y huellas; peralte 0.175 m dato
     del cliente; huella 0.28 m; alto entre niveles 3.00 m = 2.75 + losa 0.25;
     ancho de escalera 1.20 m).  Superficie DESARROLLADA (peraltes + huellas).

Devuelve, por concepto, la lista de piezas (acostadas) marcando completas y
recortes, con su posición para dibujarlas, además de ancho/largo para empacarlas
con el optimizador y sacar sobrantes/desperdicio.
"""
import math
import generadores as G

TW, TH = G.MORET[0], G.MORET[1]      # acostado: 1.194 ancho x 0.596 alto
M_M2 = TW * TH

PERALTE = 0.175        # alto del escalón (dato del cliente)
HUELLA = 0.28          # fondo del escalón (típico residencial)
ENTRE_NIVELES = 3.00   # NPT a NPT (2.75 + losa 0.25)
ESC_ANCHO = 1.20       # ancho de la escalera (m)


def _tile_pared(w, h, etiqueta):
    """Despieza una pared w (ancho) x h (alto) con piezas acostadas TWxTH.
    Devuelve piezas con x,y,w,h (dibujo) y ancho/largo/completa (corte)."""
    pzs = []
    y = 0.0
    while y < h - 1e-6:
        hh = min(TH, h - y)
        x = 0.0
        while x < w - 1e-6:
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
    """Lista de (titulo, ancho, alto, piezas) por cada cara de cada regadera."""
    out = []
    for k, (planta, h) in enumerate(G.GEN[modelo]["regaderas"], 1):
        # fondo: se enchapa SÓLO bajo la ventana (la ventana va pegada al plafón)
        hf = max(0.0, h - G.VENTANA_ALTO)
        out.append((f"Regadera {k} ({planta}) — fondo {G.REG_FONDO:.2f}×{hf:.2f}",
                    G.REG_FONDO, hf, _tile_pared(G.REG_FONDO, hf, f"R{k}-fondo")))
        for lado in ("izq", "der"):
            out.append((f"Regadera {k} ({planta}) — lateral {lado} 1.20×{h:.2f}",
                        1.20, h, _tile_pared(1.20, h, f"R{k}-lat-{lado}")))
    return out


def escalera_tramos(modelo):
    """Superficie DESARROLLADA de la escalera (peraltes + huellas), como una sola
    'pared' de ancho ESC_ANCHO y alto = n_peraltes*peralte + n_huellas*huella."""
    n_peraltes = round(ENTRE_NIVELES / PERALTE)        # 3.00/0.175 ≈ 17
    n_huellas = n_peraltes - 1                          # 16
    desarrollo = n_peraltes * PERALTE + n_huellas * HUELLA
    titulo = (f"Escalera — desarrollo {ESC_ANCHO:.2f} × {desarrollo:.2f} m  "
              f"({n_peraltes} peraltes×{PERALTE:.3f} + {n_huellas} huellas×{HUELLA:.2f})")
    return [(titulo, ESC_ANCHO, desarrollo,
             _tile_pared(ESC_ANCHO, desarrollo, "escalera"))], n_peraltes, n_huellas


def _resumen(piezas):
    comp = sum(1 for p in piezas if p["completa"])
    rec = sum(1 for p in piezas if not p["completa"])
    area = sum(p["w"] * p["h"] for p in piezas)
    return comp, rec, area


def regadera_resumen(modelo):
    pzs = [p for _t, _w, _h, ps in regadera_paredes(modelo) for p in ps]
    comp, rec, area = _resumen(pzs)
    return {"piezas": pzs, "completas": comp, "recortes": rec, "m2": area,
            "cajas": math.ceil(area * 1.1 / G.MORET_CAJA)}


def escalera_resumen(modelo):
    tramos, npe, nhu = escalera_tramos(modelo)
    pzs = [p for _t, _w, _h, ps in tramos for p in ps]
    comp, rec, area = _resumen(pzs)
    return {"piezas": pzs, "completas": comp, "recortes": rec, "m2": area,
            "cajas": math.ceil(area * 1.1 / G.MORET_CAJA),
            "n_peraltes": npe, "n_huellas": nhu}


if __name__ == "__main__":
    import sys
    for m in (sys.argv[1:] or ["Cabernet", "Merlot", "Chardonnay"]):
        r = regadera_resumen(m); e = escalera_resumen(m)
        print(f"{m}: regadera {r['m2']:.2f} m2 ({r['completas']}c/{r['recortes']}r) "
              f"-> {r['cajas']} cajas  |  escalera {e['m2']:.2f} m2 "
              f"({e['completas']}c/{e['recortes']}r) -> {e['cajas']} cajas")
