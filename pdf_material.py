#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf_material.py
===============

Genera DOS PDF (uno por material): piso_moret.pdf y piso_royal_walnut.pdf.

Cada PDF:
  Página 1  -> el PLANO DE LA CASA (mismo estilo del plano general) pero
               enfocado en ese material: sus piezas van coloreadas e
               identificadas por ID; el otro material se dibuja tenue, sólo
               como contexto. (Royal Walnut ya NO aparece en planta baja.)
  Página 2  -> resumen de compra y desperdicio del material.
  Págs. 3+  -> los DESPERDICIOS / recortes: cada baldosa que se corta, con las
               piezas y a dónde van, y el sobrante coloreado
               (amarillo = reutilizable, rojo = desperdicio).

Usa los datos corregidos (sin las charolas de baño de planta baja).

Uso:  python3 pdf_material.py
"""

import math
from collections import defaultdict

from optimizador_recortes import PISOS, CAJAS, ajustar, empaquetar
from datos_piezas import cargar_anotado, PREF_CORTE
from plano_casa import ESTILO

VERSION = "v4.4"          # versión del despiece (cámbiala al hacer correcciones)
MIN_REUSABLE = 0.10
POR_PAGINA = 9


def _tapar_notch(ax, p, face="#ffffff", edge="#333", lw=0.4):
    """Dibuja el ENTRANTE del muro (jamba) como hueco dentro de la pieza: una
    pieza con notch es UNA sola pieza que RODEA el muro (no lo encima)."""
    from matplotlib.patches import Rectangle
    for (a, b, c, d) in p.get("notch", []):
        ax.add_patch(Rectangle((a, b), c - a, d - b, facecolor=face,
                               edgecolor=edge, lw=lw, zorder=6))
PAL = ["#7fb3d5", "#82e0aa", "#f7dc6f", "#f0b27a", "#bb8fce", "#85c1e9",
       "#f1948a", "#73c6b6", "#f8c471", "#aab7b8", "#a3e4d7", "#d7bde2"]


def es_reutilizable(w, l):
    return min(w, l) >= MIN_REUSABLE


def empacar(piezas, material):
    mapa = {p["id"]: p for p in piezas if p["material"] == material}
    ancho, largo = PISOS[material]
    recortes = [p for p in piezas if p["material"] == material and not p["completa"]]
    entradas = [(*ajustar(p["ancho"], p["largo"], ancho, largo), p["id"]) for p in recortes]
    return empaquetar(entradas, material, 0.0, False), mapa, (ancho, largo)


def hacer_pdf(todas, material, path, modelo=""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Patch
    from matplotlib.backends.backend_pdf import PdfPages

    focal = [p for p in todas if p["material"] == material]
    otro = [p for p in todas if p["material"] != material]

    baldosas, mapa, (ancho, largo) = empacar(todas, material)
    area_reut = area_desp = 0.0
    for b in baldosas:
        for (fx, fy, fw, fl) in b.libres:
            if fw <= 0.005 or fl <= 0.005:
                continue
            if es_reutilizable(fw, fl):
                area_reut += fw * fl
            else:
                area_desp += fw * fl

    completas = sum(1 for p in focal if p["completa"])
    total_pzas = completas + len(baldosas)
    cfg = CAJAS[material]
    cajas = math.ceil(total_pzas / cfg["pzas_caja"])

    import datetime
    fecha = datetime.date.today().strftime("%d/%m/%Y")

    def guardar(fig):
        fig.text(0.5, 0.012,
                 f"Elaboró: Ing. Mauricio Gastelum Mora        Piso {material} — {modelo}        {fecha}",
                 ha="center", fontsize=8, color="#555")
        pdf.savefig(fig)
        plt.close(fig)

    with PdfPages(path) as pdf:
        # ---------- Página 1: PLANO ----------
        xs0 = [p["x0"] for p in todas]; ys0 = [p["y0"] for p in todas]
        xs1 = [p["x0"] + p["wx"] for p in todas]; ys1 = [p["y0"] + p["hy"] for p in todas]
        minx, maxx, miny, maxy = min(xs0), max(xs1), min(ys0), max(ys1)
        W, H = maxx - minx, maxy - miny
        fig, ax = plt.subplots(figsize=(min(24, W * 1.4), min(16, H * 1.4) + 1))
        # contexto (otro material) tenue
        for p in otro:
            ax.add_patch(Rectangle((p["x0"], p["y0"]), p["wx"], p["hy"],
                                   facecolor="#f4f6f6", edgecolor="#d5d8dc", lw=0.3))
        # material enfocado
        for p in focal:
            est = ESTILO[(p["material"], p["completa"])]
            ax.add_patch(Rectangle((p["x0"], p["y0"]), p["wx"], p["hy"],
                                   facecolor=est["face"], edgecolor="#333",
                                   lw=0.4 if p["completa"] else 0.7))
            _tapar_notch(ax, p)
            fs = min(max(1.8, min(p["wx"], p["hy"]) * 14), 4.5)
            ax.text(p["x"], p["y"], p["id"], ha="center", va="center",
                    fontsize=fs, rotation=0 if p["wx"] >= p["hy"] else 90)
        # zoclo (verde) del DWG, sólo como referencia del perímetro
        try:
            import pdf_generadores as _PG
            _z, _m, _e, _claves = _PG._datos_dwg(modelo)
            for a, b in _z:
                ax.plot([a[0], b[0]], [a[1], b[1]], color="#1e8449", lw=1.8, zorder=5)
        except Exception:
            _z = []
        ax.set_xlim(minx - 0.3, maxx + 0.3); ax.set_ylim(miny - 0.3, maxy + 0.3)
        ax.set_aspect("equal"); ax.axis("off")
        col_rec = ESTILO[(material, False)]["face"]
        col_com = ESTILO[(material, True)]["face"]
        ax.set_title(f"PLANO {modelo.upper()} — PISO {material.upper()}\n"
                     f"(coloreado = {material}; gris claro = el otro piso; verde = zoclo)",
                     fontsize=12)
        ax.legend(handles=[
            Patch(facecolor=col_com, edgecolor="#333", label=f"{material} completa"),
            Patch(facecolor=col_rec, edgecolor="#333", label=f"{material} recorte"),
            Patch(facecolor="#f4f6f6", edgecolor="#d5d8dc", label="otro piso (contexto)"),
            Patch(facecolor="#1e8449", label="zoclo"),
        ], loc="upper center", ncol=4, fontsize=9, bbox_to_anchor=(0.5, -0.02))
        fig.tight_layout()
        guardar(fig)

        # ---------- Página 1b: RECORTES CON SU PIEZA COMPLETA ----------
        pc = PREF_CORTE[material]
        recortes_plan = [p for p in focal if not p["completa"]]
        cxh = sum(p["x"] for p in focal) / len(focal) if focal else 0
        cyh = sum(p["y"] for p in focal) / len(focal) if focal else 0
        if recortes_plan:
            fig, ax = plt.subplots(figsize=(min(24, W * 1.4), min(16, H * 1.4) + 1))
            for p in focal:
                ax.add_patch(Rectangle((p["x0"], p["y0"]), p["wx"], p["hy"],
                                       facecolor="#eef3f8" if p["completa"] else "#ffffff",
                                       edgecolor="#d5d8dc", lw=0.3))
            for p in recortes_plan:
                aw, al = PISOS[material]
                Wt = max(aw, p["wx"]); Lt = max(al, p["hy"])
                tx = p["x0"] if p["x"] >= cxh else p["x0"] + p["wx"] - Wt
                ty = p["y0"] if p["y"] >= cyh else p["y0"] + p["hy"] - Lt
                # baldosa completa de la que sale (contorno punteado, pegada al recorte)
                ax.add_patch(Rectangle((tx, ty), Wt, Lt, fill=False,
                                       edgecolor="#7f8c8d", lw=0.5, ls="--"))
                # el sobrante (lo que NO es el recorte)
                if Wt - p["wx"] > 0.02:
                    ox = (p["x0"] + p["wx"]) if p["x"] >= cxh else tx
                    ax.add_patch(Rectangle((ox, p["y0"]), Wt - p["wx"], p["hy"],
                                           facecolor="#fcf3cf", edgecolor="#b7950b",
                                           lw=0.3, alpha=0.7, hatch=".."))
                if Lt - p["hy"] > 0.02:
                    oy = (p["y0"] + p["hy"]) if p["y"] >= cyh else ty
                    ax.add_patch(Rectangle((p["x0"], oy), p["wx"], Lt - p["hy"],
                                           facecolor="#fcf3cf", edgecolor="#b7950b",
                                           lw=0.3, alpha=0.7, hatch=".."))
                # el recorte en su lugar real (un solo color neutro)
                ax.add_patch(Rectangle((p["x0"], p["y0"]), p["wx"], p["hy"],
                                       facecolor="#aed6f1", edgecolor="#1b4f72", lw=0.6))
                _tapar_notch(ax, p, edge="#1b4f72")
                ax.text(p["x"], p["y"], p["id"], ha="center", va="center",
                        fontsize=3.6, rotation=0 if p["wx"] >= p["hy"] else 90)
            ax.set_xlim(minx - 0.6, maxx + 0.6); ax.set_ylim(miny - 0.6, maxy + 0.6)
            ax.set_aspect("equal"); ax.axis("off")
            ax.set_title(f"RECORTES Y SU PIEZA COMPLETA — {modelo.upper()} · {material.upper()}\n"
                         "cada recorte (azul) con la baldosa entera de la que sale (línea punteada) "
                         "y el sobrante (amarillo), pegado en su lugar",
                         fontsize=11)
            guardar(fig)

        # ---------- Página 1c: MAPA DE SOBRANTES (dónde encaja cada uno) ----------
        reusados = [(idx, b.piezas[k], mapa.get(b.piezas[k][4]))
                    for idx, b in enumerate(baldosas, 1)
                    for k in range(1, len(b.piezas))]
        reusados = [(idx, t, p) for (idx, t, p) in reusados if p]
        if reusados:
            fig, ax = plt.subplots(figsize=(min(24, W * 1.4), min(16, H * 1.4) + 1))
            for p in focal:
                ax.add_patch(Rectangle((p["x0"], p["y0"]), p["wx"], p["hy"],
                                       facecolor="#ffffff", edgecolor="#e5e8e8", lw=0.3))
            for idx, t, p in reusados:
                ax.add_patch(Rectangle((p["x0"], p["y0"]), p["wx"], p["hy"],
                                       facecolor="#f9e79f", edgecolor="#b7950b", lw=0.7))
                _tapar_notch(ax, p, edge="#b7950b")
                ax.text(p["x"], p["y"], f"{p['id']}\n(sobra {pc}-{idx:02d})",
                        ha="center", va="center", fontsize=3.4,
                        rotation=0 if p["wx"] >= p["hy"] else 90)
            ax.set_xlim(minx - 0.6, maxx + 0.6); ax.set_ylim(miny - 0.6, maxy + 0.6)
            ax.set_aspect("equal"); ax.axis("off")
            ax.set_title(f"MAPA DE SOBRANTES — {modelo.upper()} · {material.upper()}\n"
                         f"los recortes que ENCAJAN aprovechando un sobrante (amarillo); "
                         f"entre paréntesis, la baldosa de la que sobra ({len(reusados)} aprovechados)",
                         fontsize=11)
            guardar(fig)

        # ---------- Página 2: RESUMEN ----------
        fig = plt.figure(figsize=(11.7, 8.3))
        fig.suptitle(f"PISO {material} — Resumen", fontsize=16, weight="bold", y=0.9)
        lineas = [
            f"Piezas completas        : {completas}",
            f"Piezas con recorte      : {len(baldosas)}  (reusando sobrantes)",
            f"Total de piezas         : {total_pzas}",
            f"En cajas                : {cajas} cajas de {cfg['pzas_caja']} pzas "
            f"= {cajas*cfg['pzas_caja']} piezas",
            f"Equivale a              : {cajas*cfg['m2_caja']:.2f} m²  "
            f"(caja = {cfg['m2_caja']:g} m²)",
            "",
            f"Sobrante reutilizable   : {area_reut:.2f} m²",
            f"Desperdicio (merma)     : {area_desp:.2f} m²",
        ]
        fig.text(0.1, 0.66, "\n".join(lineas), fontsize=13, va="top", family="monospace",
                 bbox=dict(boxstyle="round", facecolor="#fcf3cf", edgecolor="#b7950b"))
        fig.text(0.1, 0.30,
                 "En las páginas siguientes: cada pieza que se corta, qué recortes\n"
                 "salen, a dónde van y qué sobra (amarillo = reutilizable, rojo =\n"
                 "desperdicio). Royal Walnut sólo en planta alta (recámaras).",
                 fontsize=11, va="top")
        guardar(fig)

        # ---------- Págs 3+: DESPERDICIOS / RECORTES ----------
        pc = PREF_CORTE[material]
        npag = (len(baldosas) + POR_PAGINA - 1) // POR_PAGINA
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
                for (fx, fy, fw, fl) in b.libres:
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
                ax.set_title(f"Pieza {pc}-{idx:02d} · {len(b.piezas)} recorte(s)", fontsize=9, weight="bold")
            for ax in axes[len(grupo):]:
                ax.axis("off")
            fig.suptitle(f"{material} — recortes: qué cortar, a dónde va y qué sobra\n"
                         f"(verde = recorte que se usa · amarillo = sobrante reutilizable · "
                         f"rojo = desperdicio)   pág. {ini//POR_PAGINA + 1} de {npag}", fontsize=11)
            fig.tight_layout(rect=[0, 0.04, 1, 0.95])
            guardar(fig)

        # ---------- Página FINAL: todos los sobrantes sumados ----------
        from collections import Counter
        reut = Counter()      # (w,l) -> cantidad
        desp = Counter()
        for b in baldosas:
            for (fx, fy, fw, fl) in b.libres:
                if fw <= 0.005 or fl <= 0.005:
                    continue
                clave = (round(min(fw, fl), 2), round(max(fw, fl), 2))
                if es_reutilizable(fw, fl):
                    reut[clave] += 1
                else:
                    desp[clave] += 1

        def filas_de(cont, limite=15):
            items = sorted(cont.items(), key=lambda kv: -kv[0][0] * kv[0][1] * kv[1])
            filas = []
            for (a, b_), n in items[:limite]:
                filas.append([f"{a:.2f} x {b_:.2f}", n, f"{a*b_*n:.3f}"])
            if len(items) > limite:
                resto = items[limite:]
                nn = sum(n for _, n in resto)
                mm = sum(a * b_ * n for (a, b_), n in resto)
                filas.append([f"otros ({len(resto)} tamaños)", nn, f"{mm:.3f}"])
            return filas

        fig = plt.figure(figsize=(11.7, 8.3))
        fig.suptitle(f"PISO {material} — Sobrantes y desperdicio (TODO sumado)",
                     fontsize=15, weight="bold", y=0.965)

        area_inst = sum(min(p["wx"], PISOS[material][0]) * min(p["hy"], PISOS[material][1])
                        for p in focal)
        area_comprada = cajas * cfg["m2_caja"]
        total_sobra = area_reut + area_desp
        cab = (f"Total de piezas: {total_pzas}  ·  {cajas} cajas  ·  {area_comprada:.2f} m²    |    "
               f"Área neta instalada: {area_inst:.2f} m²\n"
               f"Recortes acomodados en {len(baldosas)} piezas, reusando al máximo cada sobrante "
               f"para otro recorte.")
        fig.text(0.06, 0.91, cab, fontsize=10.5, va="top", family="monospace")

        resumen = (
            f"SOBRANTE TOTAL: {total_sobra:.2f} m² de {area_comprada:.2f} m² ({100*total_sobra/area_comprada:.1f}%)   ·   "
            f"reutilizable {area_reut:.2f} m² ({sum(reut.values())} pzs)   ·   "
            f"desperdicio {area_desp:.2f} m² ({sum(desp.values())} pedacitos muy cortos)")
        fig.text(0.5, 0.845, resumen, fontsize=8.6, va="top", ha="center", family="monospace",
                 bbox=dict(boxstyle="round", facecolor="#eaf2f8", edgecolor="#5499c7"))

        # Tabla de sobrantes reutilizables
        ax1 = fig.add_axes([0.05, 0.05, 0.43, 0.70]); ax1.axis("off")
        ax1.set_title(f"SOBRANTE REUTILIZABLE  (lado ≥ {MIN_REUSABLE*100:.0f} cm)\n"
                      f"total: {area_reut:.2f} m²", fontsize=11, color="#7d6608", weight="bold")
        f1 = filas_de(reut) or [["—", 0, "0.000"]]
        t1 = ax1.table(cellText=f1, colLabels=["Tamaño (m)", "Cant.", "m²"],
                       loc="upper center", cellLoc="center")
        t1.auto_set_font_size(False); t1.set_fontsize(8.5); t1.scale(1, 1.25)
        for (r, c), cell in t1.get_celld().items():
            if r == 0:
                cell.set_facecolor("#f9e79f"); cell.set_text_props(weight="bold")

        # Tabla de desperdicio
        ax2 = fig.add_axes([0.54, 0.05, 0.41, 0.70]); ax2.axis("off")
        ax2.set_title(f"DESPERDICIO  (lado < {MIN_REUSABLE*100:.0f} cm, ya no sirve)\n"
                      f"total: {area_desp:.2f} m²", fontsize=11, color="#922b21", weight="bold")
        f2 = filas_de(desp) or [["—", 0, "0.000"]]
        t2 = ax2.table(cellText=f2, colLabels=["Tamaño (m)", "Cant.", "m²"],
                       loc="upper center", cellLoc="center")
        t2.auto_set_font_size(False); t2.set_fontsize(8.5); t2.scale(1, 1.25)
        for (r, c), cell in t2.get_celld().items():
            if r == 0:
                cell.set_facecolor("#f1948a"); cell.set_text_props(weight="bold")

        guardar(fig)

        # ---------- Página: GENERADORES DE ACABADOS (todos los materiales) ----------
        try:
            import generadores as _G
            fig = plt.figure(figsize=(11.7, 8.3))
            axg = fig.add_subplot(111); axg.axis("off")
            axg.set_title(f"NÚMEROS GENERADORES — ACABADOS · {modelo.upper()}",
                          fontsize=14, fontweight="bold")
            axg.text(0.02, 0.90, "CONCEPTO", fontsize=9.5, fontweight="bold", transform=axg.transAxes)
            axg.text(0.42, 0.90, "CANTIDAD", fontsize=9.5, fontweight="bold", transform=axg.transAxes)
            axg.text(0.80, 0.90, "SUMINISTRO", fontsize=9.5, fontweight="bold", transform=axg.transAxes)
            axg.axhline(0.885, xmin=0.02, xmax=0.98, color="#333", lw=1.0)
            yy = 0.84
            for _cc, _dd, _ss in _G.reporte(modelo):
                axg.text(0.02, yy, _cc, fontsize=9.5, fontweight="bold", transform=axg.transAxes)
                axg.text(0.42, yy, _dd, fontsize=9.5, transform=axg.transAxes)
                axg.text(0.80, yy, _ss, fontsize=9.5, color="#1b4f72", transform=axg.transAxes)
                axg.axhline(yy - 0.025, xmin=0.02, xmax=0.98, color="#e5e5e5", lw=0.5)
                yy -= 0.085
            axg.text(0.02, 0.10, "Zoclo alto 0.15 m, largo 1.20 m (ml del generador). Urbania White 0.30×0.45 (lavandería). "
                     "Malla Lyndhurst 0.30×0.60 (charola). Muro de regadera = Moret vertical, alto P.B. 2.75 / P.A. 2.90 m.",
                     fontsize=8, color="#444", transform=axg.transAxes, va="top")
            guardar(fig)
        except Exception:
            pass

    return total_pzas, cajas, area_reut, area_desp


def main(modelo="Cabernet"):
    todas = cargar_anotado(modelo)
    salidas = {"Moret": f"{modelo}_Despiece-Piso_Moret-Arena_{VERSION}.pdf",
               "Royal Walnut": f"{modelo}_Despiece-Piso_Royal-Walnut_{VERSION}.pdf"}
    for material, path in salidas.items():
        pzas, cajas, reut, desp = hacer_pdf(todas, material, path, modelo)
        print(f"{modelo} · {material}: {pzas} piezas / {cajas} cajas  ·  reutilizable "
              f"{reut:.2f} m²  ·  desperdicio {desp:.2f} m²  ->  {path}")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "Cabernet")
