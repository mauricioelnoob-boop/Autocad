#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf_colocacion.py
=================
GUÍA DE COLOCACIÓN PASO A PASO (el PDF de 100-200 páginas):

  * Una página por cada pieza que se ABRE (la numeración M-xx / R-xx del plan
    de corte ES el orden: se empieza en PLANTA ALTA junto a la ESCALERA).
  * En cada página: el despiece de la planta en GRIS, lo ya colocado en verde
    claro, y EN AZUL lo que se corta y coloca en este paso; a la derecha, el
    dibujo del corte de la pieza (recortes, sobrantes amarillos con destino y
    mermas rojas) y el REGISTRO acumulado de sobrantes guardados.
  * Los cortes de ESCALERA (P#/H#/D#) y MUROS DE BAÑO (R#) que salen en el
    paso se anotan (no están en el plano: van a su despiece).

Uso:  python3 pdf_colocacion.py [Modelo ...]
"""
import math
import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Patch
from matplotlib.backends.backend_pdf import PdfPages

from datos_piezas import cargar_anotado, PREF_CORTE
from optimizador_recortes import PISOS
from pdf_material import empacar, es_reutilizable, _fmt

FECHA = datetime.date.today().strftime("%d/%m/%Y")
PIE = "Elaboró: Ing. Mauricio Gastelum Mora"

AZUL = "#2E86C1"        # pieza que se coloca en ESTE paso
VERDE = "#d5f5e3"       # ya colocado en pasos anteriores
GRIS = "#f2f3f4"        # aún sin colocar
CTX = "#fafafa"         # el otro material (contexto)


def _portada(pdf, modelo, n_m, n_r):
    fig = plt.figure(figsize=(13.5, 8.0))
    fig.text(0.5, 0.66, "GUÍA DE COLOCACIÓN PASO A PASO", ha="center",
             fontsize=26, weight="bold", color="#1b4f72")
    fig.text(0.5, 0.58, f"{modelo.upper()} · Viñas Norte", ha="center",
             fontsize=16, color="#2874a6")
    pm, pr = PREF_CORTE["Moret"], PREF_CORTE["Royal Walnut"]
    txt = (f"Una página por cada pieza que se ABRE: {n_m} de Moret ({pm}-01…{pm}-{n_m:02d})"
           f" y {n_r} de Royal Walnut ({pr}-01…{pr}-{n_r:02d}).\n"
           "La numeración ES el orden de corte: se empieza en PLANTA ALTA junto a la"
           " ESCALERA (por ahí sube el material),\nse avanza alejándose y al terminar"
           " P.A. se sigue con P.B., también desde la escalera.\n\n"
           "En cada página: GRIS = por colocar · VERDE = ya colocado · AZUL = lo que"
           " se corta y coloca en este paso.\nA la derecha: el corte de la pieza"
           " (sobrantes amarillos con destino, mermas rojas)\ny el registro acumulado"
           " de sobrantes guardados.\n\n"
           "Las piezas ENTERAS se tienden de corrido en su cuarto (no llevan página):"
           " esta guía ordena los CORTES.")
    fig.text(0.5, 0.30, txt, ha="center", fontsize=10.5, color="#333", linespacing=1.7)
    fig.text(0.5, 0.06, f"{PIE}        {FECHA}", ha="center", fontsize=9, color="#777")
    pdf.savefig(fig)
    plt.close(fig)


def _pagina_paso(pdf, modelo, material, todas, b, idx, total, colocadas,
                 guardadas, merma_acum, mapa, destino_de):
    pc = PREF_CORTE[material]
    aB, lB = PISOS[material]
    cur = [(x, y, w, l, etq, rot, org) for (x, y, w, l, etq, rot), (org, _o)
           in zip(b.piezas, b.meta)]
    ids_cur = {c[4] for c in cur}
    en_plano = [mapa[c[4]] for c in cur if c[4] in mapa]
    extras = [c for c in cur if c[4] not in mapa]
    planta = en_plano[0]["planta"] if en_plano else None

    fig = plt.figure(figsize=(13.5, 8.0))
    # ---------- plano de la planta (izquierda) ----------
    ax = fig.add_axes([0.03, 0.06, 0.60, 0.84])
    if planta is not None:
        focos = [p for p in todas if p["planta"] == planta]
        for p in focos:
            es_mat = p["material"] == material
            pid = p.get("id")
            if es_mat and pid in ids_cur:
                fc, ec, lw, z = AZUL, "#1a5276", 1.2, 4
            elif es_mat and pid in colocadas:
                fc, ec, lw, z = VERDE, "#82b366", 0.4, 2
            elif es_mat:
                fc, ec, lw, z = GRIS, "#b3b6b7", 0.4, 2
            else:
                fc, ec, lw, z = CTX, "#dddddd", 0.3, 1
            ax.add_patch(Rectangle((p["x0"], p["y0"]), p["wx"], p["hy"],
                                   facecolor=fc, edgecolor=ec, lw=lw, zorder=z))
            if es_mat and pid in ids_cur:
                ax.text(p["x"], p["y"], pid, ha="center", va="center", fontsize=7,
                        weight="bold", color="white", zorder=5,
                        rotation=0 if p["wx"] >= p["hy"] else 90)
        xs0 = [p["x0"] for p in focos]; ys0 = [p["y0"] for p in focos]
        xs1 = [p["x0"] + p["wx"] for p in focos]; ys1 = [p["y0"] + p["hy"] for p in focos]
        ax.set_xlim(min(xs0) - 0.3, max(xs1) + 0.3)
        ax.set_ylim(min(ys0) - 0.3, max(ys1) + 0.3)
        ax.set_title(f"{'PLANTA ALTA' if planta == 'alta' else 'PLANTA BAJA'} — "
                     f"en AZUL lo que se coloca en este paso", fontsize=10)
    else:
        ax.text(0.5, 0.55, "Este paso corta piezas para\nESCALERA / MUROS DE BAÑO",
                ha="center", va="center", fontsize=14, color="#1b4f72",
                transform=ax.transAxes, weight="bold")
        ax.text(0.5, 0.35, "(no van en el plano: ver su despiece\nen el DXF y en las"
                " páginas de escalera/regadera)", ha="center", va="center",
                fontsize=10, color="#555", transform=ax.transAxes)
    ax.set_aspect("equal")
    ax.axis("off")

    # ---------- el corte de la pieza (derecha arriba) ----------
    axc = fig.add_axes([0.66, 0.42, 0.16, 0.50])
    axc.add_patch(Rectangle((0, 0), aB, lB, fill=False, edgecolor="black", lw=1.5))
    for (x, y, w, l, etq, rot, org) in cur:
        axc.add_patch(Rectangle((x, y), w, l, facecolor=AZUL, edgecolor="#1a5276",
                                lw=0.7, alpha=0.9))
        src = "nueva" if org == "TABLA" else f"de sobra\nde {org}"
        axc.text(x + w / 2, y + l / 2, f"{etq}\n{_fmt(w)}x{_fmt(l)}\n({src})",
                 ha="center", va="center", fontsize=5.2, color="white",
                 rotation=0 if w >= l else 90)
    sobras_paso = []
    for (fx, fy, fw, fl, *_z) in b.libres:
        if fw <= 0.005 or fl <= 0.005:
            continue
        reut = es_reutilizable(fw, fl)
        sobras_paso.append((fw, fl, reut))
        axc.add_patch(Rectangle((fx, fy), fw, fl,
                                facecolor="#f9e79f" if reut else "#f1948a",
                                edgecolor="#b7950b" if reut else "#922b21",
                                lw=0.7, hatch=".." if reut else "xx"))
        axc.text(fx + fw / 2, fy + fl / 2,
                 f"SOBRA\n{_fmt(fw)}x{_fmt(fl)}\n→ GUARDAR" if reut
                 else f"merma\n{_fmt(fw)}x{_fmt(fl)}",
                 ha="center", va="center", fontsize=4.6,
                 color="#7d6608" if reut else "#641e16",
                 rotation=0 if fw >= fl else 90)
    axc.set_xlim(-0.02, aB + 0.02)
    axc.set_ylim(-0.02, lB + 0.02)
    axc.set_aspect("equal")
    axc.axis("off")
    axc.set_title(f"CORTE de {pc}-{idx:02d}", fontsize=10, weight="bold")

    # ---------- texto del paso + registro de sobrantes (derecha abajo) ----------
    axt = fig.add_axes([0.83, 0.06, 0.16, 0.86])
    axt.axis("off")
    lineas = [f"PASO {idx} de {total}", ""]
    for (x, y, w, l, etq, rot, org) in cur:
        destino = ("ESCALERA" if etq[:1] in ("P", "H", "D") and etq not in mapa
                   else "MURO DE BAÑO" if etq.startswith("R") and etq not in mapa
                   else "plano")
        origen = "pieza nueva" if org == "TABLA" else f"sobra de {org}"
        lineas.append(f"{etq}")
        lineas.append(f"  {_fmt(w)}x{_fmt(l)} · {origen}")
        if destino != "plano":
            lineas.append(f"  → va a {destino}")
    lineas.append("")
    n_g = sum(1 for (_w, _l, r) in sobras_paso if r)
    n_m = len(sobras_paso) - n_g
    if n_g:
        lineas.append(f"guarda {n_g} sobrante(s)")
    if n_m:
        lineas.append(f"merma: {n_m} pedazo(s)")
    axt.text(0.0, 1.0, "\n".join(lineas), va="top", fontsize=7.6,
             family="monospace", transform=axt.transAxes, color="#1b2631")

    m2_g = sum(w * l for (w, l, _o, _s) in guardadas)
    reg = [f"RESERVA acumulada:", f"{len(guardadas)} sobras · {m2_g:.2f} m²", ""]
    for (w, l, org, paso) in guardadas[-12:]:
        reg.append(f"{_fmt(w)}x{_fmt(l)} (de {org}, paso {paso})")
    if len(guardadas) > 12:
        reg.append(f"… y {len(guardadas)-12} más")
    reg += ["", f"merma acumulada: {merma_acum:.2f} m²"]
    axt.text(0.0, 0.46, "\n".join(reg), va="top", fontsize=6.8,
             family="monospace", transform=axt.transAxes, color="#5d4037")

    fig.suptitle(f"COLOCACIÓN PASO A PASO · {modelo.upper()} · {material.upper()} — "
                 f"pieza {pc}-{idx:02d}", fontsize=13, weight="bold", y=0.985)
    fig.text(0.5, 0.015, f"{PIE}        Guía de colocación — {modelo}        {FECHA}",
             ha="center", fontsize=7.5, color="#777")
    pdf.savefig(fig)
    plt.close(fig)


def hacer(modelo):
    todas = cargar_anotado(modelo)
    salida = f"Viñas Norte - {modelo} Colocación paso a paso.pdf"
    datos = {}
    for material in ("Moret", "Royal Walnut"):
        datos[material] = empacar(todas, material, modelo)
    n_m = len(datos["Moret"][0])
    n_r = len(datos["Royal Walnut"][0])
    with PdfPages(salida) as pdf:
        _portada(pdf, modelo, n_m, n_r)
        for material in ("Moret", "Royal Walnut"):
            baldosas, mapa, _dims = datos[material]
            from collections import defaultdict
            origen_de = {}
            for b in baldosas:
                for (x, y, w, l, etq, rot), (org, _o) in zip(b.piezas, b.meta):
                    origen_de[etq] = org
            destino_de = defaultdict(list)
            for pid, org in origen_de.items():
                if org != "TABLA":
                    destino_de[org].append(pid)
            colocadas = set()
            guardadas = []
            merma_acum = 0.0
            for idx, b in enumerate(baldosas, 1):
                _pagina_paso(pdf, modelo, material, todas, b, idx, len(baldosas),
                             colocadas, guardadas, merma_acum, mapa, destino_de)
                # actualizar estado DESPUÉS de la página (la página muestra el antes)
                colocadas |= {etq for (x, y, w, l, etq, rot) in b.piezas}
                primero = b.piezas[0][4] if b.piezas else f"{PREF_CORTE[material]}-{idx:02d}"
                for (fx, fy, fw, fl, *_z) in b.libres:
                    if fw <= 0.005 or fl <= 0.005:
                        continue
                    if es_reutilizable(fw, fl):
                        guardadas.append((fw, fl, primero, idx))
                    else:
                        merma_acum += fw * fl
    n_pags = 1 + n_m + n_r
    print(f"-> {salida}  ({n_pags} páginas: portada + {n_m} Moret + {n_r} Royal)")
    return salida


if __name__ == "__main__":
    import sys
    for m in (sys.argv[1:] or ["Cabernet", "Merlot", "Chardonnay"]):
        hacer(m)
