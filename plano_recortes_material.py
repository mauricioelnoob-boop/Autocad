#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plano_recortes_material.py
==========================

Genera UN PDF POR MATERIAL (Moret y Royal Walnut) con el detalle de cada
baldosa que se va a recortar, mostrando:

  * cada pieza que sale de la baldosa, con su ID y A DÓNDE VA  (ubicación x,y),
  * el pedazo SOBRANTE coloreado:
        - amarillo = sobrante reutilizable (se puede usar en otra pieza/obra),
        - rojo     = desperdicio (tira muy chica para reusar).

La idea: ves qué cortas, a dónde va cada recorte y qué te sobra de cada baldosa.

Salidas:
    plano_recortes_moret.pdf
    plano_recortes_royal_walnut.pdf

Uso:
    python3 plano_recortes_material.py  [piezas_piso.json]
"""

import json
import argparse

from optimizador_recortes import PISOS, ajustar, empaquetar
from plano_casa import asignar_ids_y_corte, PREFIJO_CORTE

MIN_REUSABLE = 0.10     # lado mínimo (m) para considerar un sobrante reutilizable
POR_PAGINA = 9          # baldosas por hoja (3x3)

PAL = ["#7fb3d5", "#82e0aa", "#f7dc6f", "#f0b27a", "#bb8fce", "#85c1e9",
       "#f1948a", "#73c6b6", "#f8c471", "#aab7b8", "#a3e4d7", "#d7bde2"]


def es_reutilizable(w, l):
    return min(w, l) >= MIN_REUSABLE


def construir(piezas, material):
    """Empaqueta los recortes del material y devuelve las baldosas con
    info de destino de cada pieza."""
    mapa = {p["id"]: p for p in piezas if p["material"] == material}
    ancho, largo = PISOS[material]
    recortes = [p for p in piezas if p["material"] == material and not p["completa"]]
    entradas = []
    for p in recortes:
        aw, al = ajustar(p["ancho"], p["largo"], ancho, largo)
        entradas.append((aw, al, p["id"]))
    baldosas = empaquetar(entradas, material, 0.0, False)
    return baldosas, mapa, (ancho, largo)


def hacer_pdf(piezas, material, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Patch

    baldosas, mapa, (ancho, largo) = construir(piezas, material)
    pref = PREFIJO_CORTE[material]

    # Totales de sobrante/desperdicio
    area_reut = area_desp = 0.0
    for b in baldosas:
        for (fx, fy, fw, fl) in b.libres:
            if fw <= 0.005 or fl <= 0.005:
                continue
            if es_reutilizable(fw, fl):
                area_reut += fw * fl
            else:
                area_desp += fw * fl

    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(path) as pdf:
        for ini in range(0, len(baldosas), POR_PAGINA):
            grupo = baldosas[ini:ini + POR_PAGINA]
            fig, axes = plt.subplots(3, 3, figsize=(16, 11))
            axes = axes.ravel()
            for ax, b in zip(axes, grupo):
                idx = baldosas.index(b) + 1
                ax.add_patch(Rectangle((0, 0), ancho, largo, fill=False,
                                       edgecolor="black", lw=1.6))
                # Piezas (recortes) con su destino
                for k, (x, y, w, l, pid, rot) in enumerate(b.piezas):
                    ax.add_patch(Rectangle((x, y), w, l, facecolor=PAL[k % len(PAL)],
                                           edgecolor="black", lw=0.8))
                    dest = mapa.get(pid)
                    loc = f"\n→ va a ({dest['x']:.1f}, {dest['y']:.1f})" if dest else ""
                    txt = f"{pid}\n{w:.2f}x{l:.2f}{loc}"
                    ang = 0 if w >= l else 90
                    ax.text(x + w / 2, y + l / 2, txt, ha="center", va="center",
                            fontsize=6.5 if w >= 0.25 else 5, rotation=ang)
                # Sobrantes / desperdicio
                for (fx, fy, fw, fl) in b.libres:
                    if fw <= 0.005 or fl <= 0.005:
                        continue
                    if es_reutilizable(fw, fl):
                        ax.add_patch(Rectangle((fx, fy), fw, fl, facecolor="#f9e79f",
                                               edgecolor="#b7950b", lw=0.8, hatch=".."))
                        ax.text(fx + fw / 2, fy + fl / 2,
                                f"SOBRA\n{fw:.2f}x{fl:.2f}\n(reutilizable)",
                                ha="center", va="center", fontsize=5.5, color="#7d6608")
                    else:
                        ax.add_patch(Rectangle((fx, fy), fw, fl, facecolor="#f1948a",
                                               edgecolor="#922b21", lw=0.8, hatch="xx"))
                        ax.text(fx + fw / 2, fy + fl / 2,
                                f"desperdicio\n{fw:.2f}x{fl:.2f}",
                                ha="center", va="center", fontsize=5, color="#641e16")
                ax.set_xlim(-0.03, ancho + 0.03)
                ax.set_ylim(-0.03, largo + 0.03)
                ax.set_aspect("equal")
                npz = len(b.piezas)
                ax.set_title(f"Baldosa {pref}-{idx:02d}  ·  {npz} pieza(s)", fontsize=9, weight="bold")
                ax.axis("off")
            for ax in axes[len(grupo):]:
                ax.axis("off")
            fig.suptitle(
                f"{material} — Plano de recortes: qué cortar, a dónde va y qué sobra\n"
                f"(amarillo = sobrante reutilizable · rojo = desperdicio)   "
                f"pág. {ini//POR_PAGINA + 1} de {(len(baldosas)+POR_PAGINA-1)//POR_PAGINA}",
                fontsize=12)
            fig.legend(handles=[
                Patch(facecolor="#82e0aa", edgecolor="k", label="pieza que se corta (con su destino)"),
                Patch(facecolor="#f9e79f", edgecolor="#b7950b", label="sobrante reutilizable"),
                Patch(facecolor="#f1948a", edgecolor="#922b21", label="desperdicio"),
            ], loc="lower center", ncol=3, fontsize=9, frameon=False)
            fig.tight_layout(rect=[0, 0.03, 1, 0.95])
            pdf.savefig(fig)
            plt.close(fig)

    return len(baldosas), area_reut, area_desp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("piezas", nargs="?", default="piezas_piso.json")
    args = ap.parse_args()

    piezas = json.load(open(args.piezas, encoding="utf-8"))
    asignar_ids_y_corte(piezas)

    salidas = {
        "Moret": "plano_recortes_moret.pdf",
        "Royal Walnut": "plano_recortes_royal_walnut.pdf",
    }
    for material, path in salidas.items():
        n, reut, desp = hacer_pdf(piezas, material, path)
        print(f"{material}: {n} baldosas de recorte  ·  sobrante reutilizable "
              f"{reut:.2f} m²  ·  desperdicio {desp:.2f} m²  ->  {path}")


if __name__ == "__main__":
    main()
