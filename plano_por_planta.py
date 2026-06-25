#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plano_por_planta.py
===================

Genera UN PDF POR PLANTA (planta baja y planta alta):

  * Planta BAJA: sólo piso Moret.
  * Planta ALTA: Moret + Royal Walnut (las 3 recámaras).

Cada PDF contiene:
  1) El plano de esa planta con cada pieza identificada por su ID.
  2) El detalle de recortes: cada baldosa que se corta, con las piezas y
     A DÓNDE VAN, y el sobrante coloreado (amarillo=reutilizable, rojo=desperdicio).
  3) Un resumen de compra de esa planta (piezas, cajas, m², desperdicio).

Las charolas de baño de planta baja (otro piso) ya quedan excluidas.

Salidas:  planta_baja.pdf  y  planta_alta.pdf

Uso:  python3 plano_por_planta.py
"""

import math
from collections import defaultdict

from optimizador_recortes import PISOS, CAJAS, ajustar, empaquetar
from datos_piezas import cargar_anotado, PREF_CORTE
from plano_casa import ESTILO

MIN_REUSABLE = 0.10
POR_PAGINA = 9
PAL = ["#7fb3d5", "#82e0aa", "#f7dc6f", "#f0b27a", "#bb8fce", "#85c1e9",
       "#f1948a", "#73c6b6", "#f8c471", "#aab7b8", "#a3e4d7", "#d7bde2"]


def es_reutilizable(w, l):
    return min(w, l) >= MIN_REUSABLE


def empacar_material(piezas, material):
    mapa = {p["id"]: p for p in piezas if p["material"] == material}
    ancho, largo = PISOS[material]
    recortes = [p for p in piezas if p["material"] == material and not p["completa"]]
    entradas = [(*ajustar(p["ancho"], p["largo"], ancho, largo), p["id"]) for p in recortes]
    return empaquetar(entradas, material, 0.0, False), mapa, (ancho, largo)


def resumen(piezas, material, n_baldosas_recorte):
    completas = sum(1 for p in piezas if p["material"] == material and p["completa"])
    total_pzas = completas + n_baldosas_recorte
    cfg = CAJAS[material]
    cajas = math.ceil(total_pzas / cfg["pzas_caja"])
    return {"completas": completas, "recortes_tiles": n_baldosas_recorte,
            "piezas": total_pzas, "cajas": cajas,
            "m2": cajas * cfg["m2_caja"]}


def hacer_pdf(piezas, planta_nombre, materiales, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Patch
    from matplotlib.backends.backend_pdf import PdfPages

    with PdfPages(path) as pdf:
        # ---------- Página 1: PLANO DE LA PLANTA ----------
        xs0 = [p["x0"] for p in piezas]; ys0 = [p["y0"] for p in piezas]
        xs1 = [p["x0"] + p["wx"] for p in piezas]; ys1 = [p["y0"] + p["hy"] for p in piezas]
        minx, maxx, miny, maxy = min(xs0), max(xs1), min(ys0), max(ys1)
        W, H = maxx - minx, maxy - miny
        fig, ax = plt.subplots(figsize=(min(22, W * 1.5), min(16, H * 1.5) + 1.2))
        for p in piezas:
            est = ESTILO[(p["material"], p["completa"])]
            ax.add_patch(Rectangle((p["x0"], p["y0"]), p["wx"], p["hy"],
                                   facecolor=est["face"], edgecolor="#333",
                                   lw=0.4 if p["completa"] else 0.7))
            fs = min(max(1.8, min(p["wx"], p["hy"]) * 14), 4.5)
            ax.text(p["x"], p["y"], p["id"], ha="center", va="center",
                    fontsize=fs, rotation=0 if p["wx"] >= p["hy"] else 90)
        ax.set_xlim(minx - 0.3, maxx + 0.3); ax.set_ylim(miny - 0.3, maxy + 0.3)
        ax.set_aspect("equal"); ax.axis("off")
        ax.set_title(f"PLANO {planta_nombre.upper()} — despiece identificado por pieza\n"
                     "(gris = baldosa completa · naranja = recorte Moret · turquesa = recorte Royal)",
                     fontsize=12)
        ax.legend(handles=[
            Patch(facecolor=ESTILO[("Moret", True)]["face"], edgecolor="#333", label="Moret completa"),
            Patch(facecolor=ESTILO[("Moret", False)]["face"], edgecolor="#333", label="Moret recorte"),
            Patch(facecolor=ESTILO[("Royal Walnut", True)]["face"], edgecolor="#333", label="Royal completa"),
            Patch(facecolor=ESTILO[("Royal Walnut", False)]["face"], edgecolor="#333", label="Royal recorte"),
        ], loc="upper center", ncol=4, fontsize=8, bbox_to_anchor=(0.5, -0.02))
        fig.tight_layout()
        pdf.savefig(fig); plt.close(fig)

        # ---------- Página 2: RESUMEN DE COMPRA ----------
        fig = plt.figure(figsize=(11.7, 8.3))
        fig.suptitle(f"{planta_nombre} — Resumen de compra", fontsize=15, weight="bold", y=0.92)
        filas = []
        for material, info in materiales.items():
            r = info["resumen"]; cfg = CAJAS[material]
            filas.append([material, r["completas"], r["recortes_tiles"], r["piezas"],
                          r["cajas"], f'{r["m2"]:.2f}',
                          f'{info["area_reut"]:.2f}', f'{info["area_desp"]:.2f}'])
        ax = fig.add_axes([0.05, 0.5, 0.9, 0.28]); ax.axis("off")
        tabla = ax.table(cellText=filas,
                         colLabels=["Material", "Completas", "Tiles p/recorte",
                                    "PIEZAS", "Cajas", "m²",
                                    "Sobrante\nreutil. m²", "Desperdicio\nm²"],
                         loc="center", cellLoc="center")
        tabla.auto_set_font_size(False); tabla.set_fontsize(9.5); tabla.scale(1, 2.2)
        for (rr, cc), cell in tabla.get_celld().items():
            if rr == 0:
                cell.set_facecolor("#34495e"); cell.set_text_props(color="white", weight="bold")
            elif cc in (3, 4, 5):
                cell.set_facecolor("#fcf3cf")
        nota = (f"Planta: {planta_nombre}.  'PIEZAS' = baldosas completas + baldosas "
                "abiertas para recortes (optimizado).\nLas cajas se redondean hacia arriba. "
                "Charolas de baño de planta baja excluidas (otro piso).")
        fig.text(0.06, 0.42, nota, fontsize=10, va="top", family="monospace")
        pdf.savefig(fig); plt.close(fig)

        # ---------- Páginas: RECORTES por material ----------
        for material, info in materiales.items():
            baldosas, mapa, (ancho, largo) = info["pack"]
            pc = PREF_CORTE[material]
            for ini in range(0, len(baldosas), POR_PAGINA):
                grupo = baldosas[ini:ini + POR_PAGINA]
                fig, axes = plt.subplots(3, 3, figsize=(16, 11)); axes = axes.ravel()
                for ax, b in zip(axes, grupo):
                    idx = baldosas.index(b) + 1
                    ax.add_patch(Rectangle((0, 0), ancho, largo, fill=False, edgecolor="black", lw=1.6))
                    for k, (x, y, w, l, pid, rot) in enumerate(b.piezas):
                        ax.add_patch(Rectangle((x, y), w, l, facecolor=PAL[k % len(PAL)],
                                               edgecolor="black", lw=0.8))
                        dest = mapa.get(pid)
                        loc = f"\n→ ({dest['x']:.1f}, {dest['y']:.1f})" if dest else ""
                        ax.text(x + w / 2, y + l / 2, f"{pid}\n{w:.2f}x{l:.2f}{loc}",
                                ha="center", va="center",
                                fontsize=6 if w >= 0.25 else 4.6, rotation=0 if w >= l else 90)
                    for (fx, fy, fw, fl, *_z) in b.libres:
                        if fw <= 0.005 or fl <= 0.005:
                            continue
                        if es_reutilizable(fw, fl):
                            ax.add_patch(Rectangle((fx, fy), fw, fl, facecolor="#f9e79f",
                                                   edgecolor="#b7950b", lw=0.8, hatch=".."))
                            ax.text(fx + fw / 2, fy + fl / 2, f"SOBRA\n{fw:.2f}x{fl:.2f}",
                                    ha="center", va="center", fontsize=5.2, color="#7d6608")
                        else:
                            ax.add_patch(Rectangle((fx, fy), fw, fl, facecolor="#f1948a",
                                                   edgecolor="#922b21", lw=0.8, hatch="xx"))
                            ax.text(fx + fw / 2, fy + fl / 2, f"desperd.\n{fw:.2f}x{fl:.2f}",
                                    ha="center", va="center", fontsize=4.8, color="#641e16")
                    ax.set_xlim(-0.03, ancho + 0.03); ax.set_ylim(-0.03, largo + 0.03)
                    ax.set_aspect("equal"); ax.axis("off")
                    ax.set_title(f"Baldosa {pc}-{idx:02d} · {len(b.piezas)} pza(s)", fontsize=9, weight="bold")
                for ax in axes[len(grupo):]:
                    ax.axis("off")
                npag = (len(baldosas) + POR_PAGINA - 1) // POR_PAGINA
                fig.suptitle(f"{planta_nombre} · {material} — recortes: qué cortar, a dónde va y qué sobra\n"
                             f"(amarillo = sobrante reutilizable · rojo = desperdicio)   "
                             f"pág. {ini//POR_PAGINA + 1} de {npag}", fontsize=12)
                fig.legend(handles=[
                    Patch(facecolor="#82e0aa", edgecolor="k", label="pieza que se corta (con destino)"),
                    Patch(facecolor="#f9e79f", edgecolor="#b7950b", label="sobrante reutilizable"),
                    Patch(facecolor="#f1948a", edgecolor="#922b21", label="desperdicio"),
                ], loc="lower center", ncol=3, fontsize=9, frameon=False)
                fig.tight_layout(rect=[0, 0.03, 1, 0.95])
                pdf.savefig(fig); plt.close(fig)


def main():
    piezas = cargar_anotado()
    salidas = {"baja": "planta_baja.pdf", "alta": "planta_alta.pdf"}
    nombre = {"baja": "Planta Baja", "alta": "Planta Alta"}

    for pl, path in salidas.items():
        pzs = [p for p in piezas if p["planta"] == pl]
        if not pzs:
            continue
        mats_presentes = [m for m in PISOS if any(p["material"] == m for p in pzs)]
        materiales = {}
        for material in mats_presentes:
            baldosas, mapa, dims = empacar_material(pzs, material)
            area_reut = area_desp = 0.0
            for b in baldosas:
                for (fx, fy, fw, fl, *_z) in b.libres:
                    if fw <= 0.005 or fl <= 0.005:
                        continue
                    if es_reutilizable(fw, fl):
                        area_reut += fw * fl
                    else:
                        area_desp += fw * fl
            materiales[material] = {
                "pack": (baldosas, mapa, dims),
                "resumen": resumen(pzs, material, len(baldosas)),
                "area_reut": area_reut, "area_desp": area_desp,
            }
        hacer_pdf(pzs, nombre[pl], materiales, path)
        resumenes = "  ".join(f"{m}: {materiales[m]['resumen']['piezas']} pzas/"
                              f"{materiales[m]['resumen']['cajas']} cajas"
                              for m in materiales)
        print(f"{nombre[pl]} ({len(pzs)} piezas) -> {path}   [{resumenes}]")


if __name__ == "__main__":
    main()
