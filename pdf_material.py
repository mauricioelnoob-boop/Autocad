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

VERSION = "v5.0"          # versión del despiece (cámbiala al hacer correcciones)
MIN_REUSABLE = 0.10
POR_PAGINA = 9


def _tapar_notch(ax, p, face="#ffffff", edge="#333", lw=0.4):
    """Dibuja el ENTRANTE (muro/jamba/escalera) como hueco dentro de la pieza: una
    pieza con notch es UNA sola pieza que RODEA el obstáculo (no lo encima). El
    notch es el contorno real (polígono), así sigue diagonales de escalera."""
    from matplotlib.patches import Polygon as MplPolygon
    for ring in p.get("notch", []):
        if len(ring) >= 3:
            ax.add_patch(MplPolygon(ring, closed=True, facecolor=face,
                                    edgecolor=edge, lw=lw, zorder=6))
PAL = ["#7fb3d5", "#82e0aa", "#f7dc6f", "#f0b27a", "#bb8fce", "#85c1e9",
       "#f1948a", "#73c6b6", "#f8c471", "#aab7b8", "#a3e4d7", "#d7bde2"]


def pagina_zoclo(pdf, guardar, modelo, material):
    """Catálogo de corte del ZOCLO: cómo sale el zoclo de cada baldosa/tabla.
    Moret 0.596 m de alto -> 4 tiras de 0.146 m. Council: 4 tiras necesitan 3
    cortes; con kerf de sierra 3 mm, 4×0.146 + 3×0.003 = 0.593 <= 0.596 (caben con
    holgura). A 0.149 el kerf NO deja caber la 4ª (sólo salen 3, como a 0.15).
    Royal 0.20 m de alto -> 1 tira de 0.146 m por tabla (sobra 0.05 m)."""
    import math
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Patch
    import generadores as G
    g = G.GEN[modelo]
    if material == "Moret":
        ml = g["zoclo_m"]; alto_t, largo_t = 0.596, 1.194
        alto_z, por_tabla = G.ZOCLO_ALTO, 4; pzcaja = G.MORET_PZCAJA
        comprob = "0.146 m × 4 + 3 cortes (kerf 3 mm) = 0.593 m ≤ 0.596 m  (4 tiras con holgura)"
        antes = ("Cortando a 0.15 m sólo salen 3 zoclos y se tira ~0.146 m (~25%). "
                 "A 0.149 el kerf de sierra impide la 4ª tira; por eso 0.146.")
    else:
        ml = g["zoclo_r"]; alto_t, largo_t = 0.20, 1.20
        alto_z, por_tabla = G.ZOCLO_ALTO, 1; pzcaja = G.ROYAL_PZCAJA
        comprob = "1 zoclo de 0.146 m por tabla (la tabla Royal mide 0.20 m de alto)"
        antes = "De cada tabla Royal (0.20 m) sale 1 zoclo de 0.146 m; sobran ~0.05 m."
    tiras = math.ceil(ml / largo_t)
    tablas = math.ceil(tiras / por_tabla)
    cajas = math.ceil(tablas / pzcaja)

    fig = plt.figure(figsize=(11.7, 8.3))
    fig.suptitle(f"ZOCLO {material.upper()} — CATÁLOGO DE CORTE · {modelo.upper()}",
                 fontsize=15, fontweight="bold", y=0.96)

    # --- dibujo de UNA baldosa con sus cortes de zoclo ---
    ax = fig.add_axes([0.06, 0.30, 0.52, 0.55]); ax.set_aspect("equal"); ax.axis("off")
    ax.add_patch(Rectangle((0, 0), largo_t, alto_t, facecolor="#fdf2e3" if material == "Moret"
                           else "#eef3f8", edgecolor="#333", lw=1.4))
    cols = ["#f5b66b", "#f8c471", "#f5b041", "#eb984e"]
    for i in range(por_tabla):
        y = i * alto_z
        ax.add_patch(Rectangle((0, y), largo_t, alto_z,
                     facecolor=cols[i % len(cols)], edgecolor="#7e5109", lw=0.8))
        ax.text(largo_t / 2, y + alto_z / 2, f"ZOCLO {i+1}  ({alto_z:.3f} × {largo_t:.3f} m)",
                ha="center", va="center", fontsize=8, color="#5b3a08")
    sobra = alto_t - por_tabla * alto_z
    if sobra > 0.003:
        ax.add_patch(Rectangle((0, por_tabla * alto_z), largo_t, sobra,
                     facecolor="#f1948a", edgecolor="#922b21", lw=0.6, hatch=".."))
        ax.text(largo_t / 2, por_tabla * alto_z + sobra / 2, f"sobra {sobra:.3f} m",
                ha="center", va="center", fontsize=7, color="#922b21")
    ax.set_xlim(-0.05, largo_t + 0.05); ax.set_ylim(-0.05, alto_t + 0.05)
    ax.set_title(f"De 1 baldosa {material} ({alto_t:.3f} × {largo_t:.3f} m)\n"
                 f"salen {por_tabla} zoclo(s) de {alto_z:.3f} m de alto", fontsize=10)

    # --- panel de cantidades ---
    axt = fig.add_axes([0.62, 0.28, 0.34, 0.58]); axt.axis("off")
    filas = [
        ("Metros lineales de zoclo (generador)", f"{ml:.2f} ml"),
        (f"Largo útil por tira", f"{largo_t:.3f} m"),
        ("Tiras de zoclo necesarias", f"{tiras} tiras"),
        (f"Zoclos por baldosa (corte a {alto_z:.3f} m)", f"{por_tabla}"),
        ("Baldosas a destinar a zoclo", f"{tablas} pzas"),
        (f"Cajas ({pzcaja} pz/caja)", f"{cajas} cajas"),
    ]
    y = 0.92
    for a, b in filas:
        axt.text(0.0, y, a, fontsize=10, transform=axt.transAxes)
        axt.text(1.0, y, b, fontsize=10, fontweight="bold", ha="right",
                 color="#1b4f72", transform=axt.transAxes)
        axt.axhline(y - 0.035, color="#e5e5e5", lw=0.5, xmin=0, xmax=1)
        y -= 0.12

    nota = (f"PROPUESTA DE CORTE:  {comprob}.\n{antes}\n"
            "El zoclo se obtiene de la misma baldosa del piso (mismo tono y lote).")
    fig.text(0.5, 0.13, nota, ha="center", va="top", fontsize=9.5, color="#444",
             bbox=dict(boxstyle="round", facecolor="#eafaf1", edgecolor="#27ae60"))
    guardar(fig)


def _dibujar_pared(ax, titulo, w, h, piezas):
    from matplotlib.patches import Rectangle
    for p in piezas:
        col = "#f5b66b" if p["completa"] else "#aed6f1"
        ax.add_patch(Rectangle((p["x"], p["y"]), p["w"], p["h"], facecolor=col,
                     edgecolor="#5b3a08" if p["completa"] else "#1b4f72", lw=0.5))
    ax.set_xlim(-0.05, w + 0.05); ax.set_ylim(-0.05, h + 0.05)
    ax.set_aspect("equal"); ax.set_title(titulo, fontsize=7.5)
    ax.tick_params(labelsize=6)


def pagina_despiece_regadera(pdf, guardar, modelo):
    """DESPIECE del muro de regadera: las 3 caras (fondo + 2 laterales) de cada
    regadera, con piezas completas (naranja) y recortes (azul), y su resumen de
    sobrante/desperdicio (incluido también en la tabla global)."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    import despiece_extra as DE
    paredes = DE.regadera_paredes(modelo)
    res = DE.regadera_resumen(modelo)
    n = len(paredes)
    cols = 3
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(11.7, 2.6 * rows + 1.2))
    axes = axes.flatten() if hasattr(axes, "flatten") else [axes]
    for ax, (titulo, w, h, pzs) in zip(axes, paredes):
        _dibujar_pared(ax, titulo, w, h, pzs)
    for ax in axes[n:]:
        ax.axis("off")
    fig.suptitle(f"DESPIECE — MURO DE REGADERA (piso Moret acostado) · {modelo.upper()}\n"
                 f"{res['completas']} completas + {res['recortes']} recortes = {res['m2']:.2f} m²  ·  "
                 f"≈ {res['cajas']} cajas (incluido en la tabla de sobrante/desperdicio)",
                 fontsize=12, fontweight="bold")
    fig.legend(handles=[Patch(facecolor="#f5b66b", edgecolor="#5b3a08", label="pieza completa"),
                        Patch(facecolor="#aed6f1", edgecolor="#1b4f72", label="recorte")],
               loc="lower center", ncol=2, fontsize=9)
    fig.tight_layout(rect=[0, 0.05, 1, 0.92])
    guardar(fig)


def pagina_despiece_escalera(pdf, guardar, modelo):
    """DESPIECE de la escalera tipo CATÁLOGO DE CORTE: cada baldosa completa con
    los recortes que se le sacan, marcados P1, P2… (peraltes), H1, H2… (huellas) y
    D#-R# (recortes de descanso). Datos del cliente: ancho 1.15 m, peralte 0.175 m,
    huella 0.27 m. Cada peralte/huella es un recorte de una baldosa."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Patch
    import despiece_extra as DE
    from optimizador_recortes import ajustar, empaquetar, PISOS
    res = DE.escalera_resumen(modelo)
    aT, lT = PISOS["Moret"]                          # 0.596 x 1.194
    recortes = [p for p in res["piezas"] if not p["completa"]]
    enteras = [p for p in res["piezas"] if p["completa"]]
    entradas = [(*ajustar(p["ancho"], p["largo"], aT, lT), p["id"]) for p in recortes]
    baldosas = empaquetar(entradas, "Moret", 0.0, True)

    def color_for(pid):
        return "#aed6f1" if pid.startswith("P") else "#f5b66b" if pid.startswith("H") else "#c39bd3"

    nb = len(baldosas) + len(enteras)
    cols = 5
    rows = (nb + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(11.7, 2.5 * rows + 1.5))
    axes = axes.flatten() if hasattr(axes, "flatten") else [axes]
    ai = 0
    for idx, b in enumerate(baldosas, 1):
        ax = axes[ai]; ai += 1
        ax.add_patch(Rectangle((0, 0), aT, lT, facecolor="#fbfbfb", edgecolor="#333", lw=1.4))
        for (x, y, w, l, pid, rot) in b.piezas:
            ax.add_patch(Rectangle((x, y), w, l, facecolor=color_for(pid),
                         edgecolor="#333", lw=0.5))
            ax.text(x + w / 2, y + l / 2, pid, ha="center", va="center",
                    fontsize=5.5, rotation=90 if l > w else 0)
        for (fx, fy, fw, fl, *_z) in b.libres:
            if fw > 0.02 and fl > 0.02:
                ax.add_patch(Rectangle((fx, fy), fw, fl, facecolor="#efefef",
                             edgecolor="#cfcfcf", lw=0.3))
        ax.set_xlim(-0.03, aT + 0.03); ax.set_ylim(-0.03, lT + 0.03)
        ax.set_aspect("equal"); ax.set_title(f"Baldosa {idx}", fontsize=7)
        ax.set_xticks([]); ax.set_yticks([])
    for p in enteras:
        ax = axes[ai]; ai += 1
        ax.add_patch(Rectangle((0, 0), aT, lT, facecolor="#f5b66b", edgecolor="#333", lw=1.4))
        ax.text(aT / 2, lT / 2, p["id"] + "\n(entera)", ha="center", va="center", fontsize=6)
        ax.set_xlim(-0.03, aT + 0.03); ax.set_ylim(-0.03, lT + 0.03)
        ax.set_aspect("equal"); ax.set_title("Descanso", fontsize=7)
        ax.set_xticks([]); ax.set_yticks([])
    for ax in axes[ai:]:
        ax.axis("off")

    cfg = DE.ESCALERA[modelo]
    tramos = " + ".join(f"{t} escal." for t in cfg["tramos"])
    zoclo = ("  ·  + ZOCLO 0.15 m en la orilla (desde 1er descanso)"
             if res["zoclo_orilla"] else "")
    fig.suptitle(f"DESPIECE — ESCALERA (catálogo de corte) · {modelo.upper()}\n"
                 f"ancho 1.15 m · peralte 0.175 m · huella 0.27 m · {tramos} · "
                 f"{len(cfg['descansos'])} descanso(s){zoclo}\n"
                 f"{res['n_escalones']} peraltes (P) + {res['n_escalones']} huellas (H) + descansos · "
                 f"{nb} baldosas ≈ {res['cajas']} cajas (sumadas a la tabla)",
                 fontsize=10.5, fontweight="bold")
    fig.legend(handles=[Patch(facecolor="#aed6f1", label="Peralte (P#)"),
                        Patch(facecolor="#f5b66b", label="Huella (H#) / entera"),
                        Patch(facecolor="#c39bd3", label="Recorte de descanso (D#-R#)"),
                        Patch(facecolor="#efefef", label="sobrante")],
               loc="lower center", ncol=4, fontsize=8)
    fig.tight_layout(rect=[0, 0.05, 1, 0.90])
    guardar(fig)


def pagina_muro_regadera(pdf, guardar, modelo):
    """Despiece del PISO EN MURO DE REGADERA (Moret acostado). Muro de fondo
    1.50 m de ancho × alto (NPT − losa: P.B. 2.75 / P.A. 2.90 m). La VENTANA va
    pegada al plafón, del mismo ancho del fondo (1.50 m) × 0.90 m de alto, y se
    descuenta. El NICHO (0.09 m de profundidad) se marca sobre el muro. Piezas
    acostadas 1.194 × 0.596 m."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    import generadores as G
    g = G.GEN[modelo]
    tw, th = G.MORET[0], G.MORET[1]      # acostada: 1.194 ancho × 0.596 alto
    FONDO = G.REG_FONDO                   # 1.50 m
    VH = G.VENTANA_ALTO                   # ventana 0.90 m de alto, del ancho del fondo
    NA, NH, NP = G.NICHO_ANCHO, G.NICHO_ALTO, G.NICHO_PROF
    regs = g["regaderas"]
    fig, axes = plt.subplots(1, len(regs), figsize=(min(11.7, 3.7 * len(regs) + 0.5), 7.8))
    if len(regs) == 1:
        axes = [axes]
    for k, (ax, (planta, h)) in enumerate(zip(axes, regs), 1):
        vy = h - VH                       # la ventana arranca a (alto − 0.90) y llega al plafón
        # enchape Moret SÓLO bajo la ventana (la ventana no se enchapa)
        y = 0.0
        while y < vy - 1e-6:
            hh = min(th, vy - y); x = 0.0
            while x < FONDO - 1e-6:
                w = min(tw, FONDO - x)
                ax.add_patch(Rectangle((x, y), w, hh, facecolor="#f5b66b",
                             edgecolor="#7e5109", lw=0.5))
                x += tw
            y += th
        # ventana (hueco: no se enchapa) — pegada al plafón, del ancho del fondo
        ax.add_patch(Rectangle((0, vy), FONDO, VH, facecolor="#d6eaf8",
                     edgecolor="#2e86c1", lw=1.6, zorder=5))
        ax.text(FONDO / 2, vy + VH / 2, f"VENTANA\n{FONDO:.2f} × {VH:.2f} m\n(al plafón)",
                ha="center", va="center", fontsize=7, color="#1b4f72", zorder=6)
        # nicho (recesado 0.09 m): RECARGADO a la izquierda (lado del monomando,
        # donde va la pieza completa). Se marca con doble contorno.
        nx, ny = 0.0, vy - 0.45 - NH
        ax.add_patch(Rectangle((nx, ny), NA, NH, fill=False, edgecolor="#c0392b",
                     lw=1.8, zorder=6))
        ax.add_patch(Rectangle((nx + 0.03, ny + 0.03), NA - 0.06, NH - 0.06, fill=False,
                     edgecolor="#c0392b", lw=0.8, ls="--", zorder=6))
        ax.text(nx + NA / 2, ny + NH / 2, f"NICHO\n{NA:.2f}×{NH:.2f} m\nprof. {NP:.2f} m",
                ha="center", va="center", fontsize=6.5, color="#c0392b", zorder=7)
        ax.set_xlim(-0.1, FONDO + 0.1); ax.set_ylim(-0.1, h + 0.2); ax.set_aspect("equal")
        ax.set_xticks([0, FONDO]); ax.set_yticks([0, 1, 2, round(h, 2)])
        ax.tick_params(labelsize=7)
        m2 = max(0.0, G.REG_PERIM * h - G.VENTANA_M2)
        ax.set_title(f"Regadera {k} ({planta})\nmuro de fondo {FONDO:.2f} × {h:.2f} m\n"
                     f"3 caras − ventana = {m2:.2f} m²", fontsize=9)
        ax.set_xlabel("fondo (m) — piezas acostadas", fontsize=8)
    fig.suptitle(f"PISO EN MURO DE REGADERA (Moret acostado) · {modelo.upper()}\n"
                 "piezas 1.194 × 0.596 m · ventana al plafón (1.50 × 0.90 m) descontada · "
                 "nicho 0.09 m de profundidad · alto = NPT − losa",
                 fontsize=11.5, fontweight="bold")
    fig.tight_layout(rect=[0, 0.02, 1, 0.90])
    guardar(fig)



def es_reutilizable(w, l):
    return min(w, l) >= MIN_REUSABLE


def empacar(piezas, material):
    mapa = {p["id"]: p for p in piezas if p["material"] == material}
    ancho, largo = PISOS[material]
    recortes = [p for p in piezas if p["material"] == material and not p["completa"]]
    entradas = [(*ajustar(p["ancho"], p["largo"], ancho, largo), p["id"]) for p in recortes]
    return empaquetar(entradas, material, 0.0, True), mapa, (ancho, largo)


def pagina_plan_corte(pdf, guardar, modelo, material, baldosas):
    """PLAN DE CORTE — ORDEN Y REUSO: marca el ORDEN en que se corta cada baldosa
    y de qué SOBRANTE sale cada pieza (la cadena de reuso). Dibuja las tablas que
    aprovechan sobrante (2+ piezas) con el orden 1°, 2°, 3° y su origen."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Patch
    from optimizador_recortes import cadena_de_corte, PISOS
    aB, lB = PISOS[material]
    ch = cadena_de_corte(baldosas)
    multi = [c for c in ch if len(c["cortes"]) >= 2]
    solo = len(ch) - len(multi)
    if not ch:
        return
    PALo = ["#aed6f1", "#f5b66b", "#a9dfbf", "#f9e79f", "#d7bde2", "#f5b7b1"]
    por_pag = 18
    primero = True
    for ini in range(0, max(1, len(multi)), por_pag):
        grupo = multi[ini:ini + por_pag]
        fig, axes = plt.subplots(3, 6, figsize=(13.5, 8.0))
        axes = axes.ravel()
        for ax, c in zip(axes, grupo):
            b = next(b for b in baldosas if b.id == c["id"])
            ax.add_patch(Rectangle((0, 0), aB, lB, fill=False, edgecolor="#333", lw=1.4))
            cortes = sorted(c["cortes"], key=lambda k: k["orden"])
            ordmap = {ct["orden"]: i + 1 for i, ct in enumerate(cortes)}
            for (x, y, w, l, etq, rot), (origen, orden) in zip(b.piezas, b.meta):
                o = ordmap.get(orden, 1)
                ax.add_patch(Rectangle((x, y), w, l, facecolor=PALo[(o - 1) % len(PALo)],
                             edgecolor="#333", lw=0.5))
                src = "tabla" if origen == "TABLA" else "sobra"
                # La etiqueta se adapta al tamaño de la pieza para NO encimarse:
                # piezas muy angostas llevan solo el orden; las medianas, orden+clave;
                # las amplias, las 3 líneas. La fuente escala con el lado corto.
                smin = min(w, l)
                fs = max(2.6, min(5.0, smin * 26))
                dim = f"{round(w*100):.0f}×{round(l*100):.0f}"   # ancho×largo en cm
                if smin < 0.09:
                    txt = f"{o}°"
                elif smin < 0.20:
                    txt = f"{o}°\n{dim}"
                else:
                    txt = f"{o}°  {etq.split()[0]}\n{dim} cm\n({src})"
                ax.text(x + w / 2, y + l / 2, txt, ha="center", va="center",
                        fontsize=fs, rotation=0 if w >= l else 90)
            for (fx, fy, fw, fl, *_z) in b.libres:
                if fw > 0.05 and fl > 0.05:
                    ax.add_patch(Rectangle((fx, fy), fw, fl, facecolor="#eeeeee",
                                 edgecolor="#cfcfcf", hatch="//", lw=0.3))
                    if fw > 0.13 and fl > 0.13:      # sobrante con su medida
                        ax.text(fx + fw / 2, fy + fl / 2,
                                f"sobra\n{round(fw*100):.0f}×{round(fl*100):.0f}",
                                ha="center", va="center", fontsize=3.0, color="#999",
                                rotation=0 if fw >= fl else 90)
            ax.set_xlim(-0.02, aB + 0.02); ax.set_ylim(-0.02, lB + 0.02)
            ax.set_aspect("equal"); ax.set_title(f"Tabla #{c['id']}", fontsize=6.5)
            ax.set_xticks([]); ax.set_yticks([])
        for ax in axes[len(grupo):]:
            ax.axis("off")
        ttl = (f"PLAN DE CORTE — ORDEN Y REUSO DE SOBRANTES · {modelo.upper()} · {material.upper()}"
               if primero else
               f"PLAN DE CORTE — ORDEN Y REUSO (cont.) · {modelo.upper()} · {material.upper()}")
        fig.suptitle(ttl, fontsize=12, fontweight="bold", y=0.985)
        if primero:
            fig.text(0.5, 0.945,
                     f"{len(ch)} tablas se abren para recortes; {len(multi)} aprovechan el sobrante "
                     f"para 2+ piezas (ahorro de {len(multi)} tablas).",
                     ha="center", fontsize=8.5, color="#444")
            fig.text(0.5, 0.928,
                     "El número = orden de corte · '(tabla)' = corte de tabla nueva · "
                     "'(sobra)' = sale del sobrante de la pieza anterior.",
                     ha="center", fontsize=8.5, color="#444")
            fig.text(0.5, 0.911,
                     "El código de cada recorte (p.ej. PB-M-122) es su POSICIÓN en el PLANO de la pág. 1; "
                     "las medidas son ancho×largo en cm. "
                     "H#/P# = escalera, R# = regadera (ver sus páginas).",
                     ha="center", fontsize=8.0, color="#666")
            primero = False
        fig.tight_layout(rect=[0, 0.0, 1, 0.90])
        guardar(fig)


def hacer_pdf(todas, material, path, modelo=""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Patch, FancyBboxPatch
    from matplotlib.backends.backend_pdf import PdfPages

    focal = [p for p in todas if p["material"] == material]
    otro = [p for p in todas if p["material"] != material]

    baldosas, mapa, (ancho, largo) = empacar(todas, material)

    # EXTRAS Moret (muro de regadera + escalera): se empacan también y entran al
    # conteo de cajas y a las tablas de sobrante/desperdicio (además de su propia
    # página de despiece). Sólo aplican al PDF de Moret.
    extra_reg = extra_esc = None
    extra_baldosas = []
    extra_completas = 0
    if material == "Moret" and modelo:
        try:
            import despiece_extra as DE
            from optimizador_recortes import ajustar as _aj, empaquetar as _emp
            extra_reg = DE.regadera_resumen(modelo)
            extra_esc = DE.escalera_resumen(modelo)
            for res in (extra_reg, extra_esc):
                extra_completas += res["completas"]
                ent = [(*_aj(p["ancho"], p["largo"], ancho, largo),
                        p.get("id") or p.get("pared") or "extra")
                       for p in res["piezas"] if not p["completa"]]
                extra_baldosas += _emp(ent, material, 0.0, True)
        except Exception:
            extra_reg = extra_esc = None

    baldosas_all = baldosas + extra_baldosas
    area_reut = area_desp = 0.0
    for b in baldosas_all:
        for (fx, fy, fw, fl, *_z) in b.libres:
            if fw <= 0.005 or fl <= 0.005:
                continue
            if es_reutilizable(fw, fl):
                area_reut += fw * fl
            else:
                area_desp += fw * fl

    completas = sum(1 for p in focal if p["completa"])
    total_pzas = completas + extra_completas + len(baldosas_all)
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
        # ZOCLO: se dibuja por DENTRO, sobre el perímetro del piso de cada material
        # (pegado al muro, no flotando afuera). El zoclo de las recámaras es Royal
        # (morado); el del resto de la casa es Moret (verde). En Moret no se dibuja
        # el zoclo sobre la escalera (la escalera no lleva zoclo de piso).
        from shapely.geometry import Polygon as _Poly, box as _box
        from shapely.ops import unary_union as _uni2
        _esc_zona = None
        if material == "Moret":
            try:
                import json as _json, os as _os
                _ep = f"escalon_{modelo.lower()}.json"
                if _os.path.exists(_ep):
                    _esc_zona = _uni2([_Poly(q).buffer(0.05)
                                       for q in _json.load(open(_ep))])
            except Exception:
                _esc_zona = None
        zcol = "#1e8449" if material == "Moret" else "#7d3c98"

        def _plot_linea(geom):
            if geom.is_empty:
                return
            gt = geom.geom_type
            if gt == "LineString":
                xs, ys = geom.xy
                ax.plot(xs, ys, color=zcol, lw=2.0, zorder=5,
                        solid_capstyle="round")
            elif gt in ("MultiLineString", "GeometryCollection"):
                for g in geom.geoms:
                    _plot_linea(g)

        try:
            # superficie de piso del material, unida por cuarto
            _floor = _uni2([_box(p["x0"], p["y0"], p["x0"] + p["wx"],
                                 p["y0"] + p["hy"]) for p in focal])
            if not _floor.is_empty:
                # closing pequeño (1.2 cm): fusiona la junta entre tablas SIN cruzar
                # los muros (~10 cm). Luego se reconstruye cada cuarto descartando
                # islas chicas y huecos diminutos, pero conservando los huecos reales
                # (p.ej. una recámara dentro de la zona Moret sí lleva zoclo alrededor).
                _closed = _floor.buffer(0.012).buffer(-0.012)
                _geoms = list(_closed.geoms) if _closed.geom_type.startswith("Multi") else [_closed]
                _rooms = []
                for g in _geoms:
                    if g.area < 0.30:
                        continue
                    _holes = [r.coords for r in g.interiors if _Poly(r).area > 0.50]
                    _rooms.append(_Poly(g.exterior.coords, _holes))
                _solid = _uni2(_rooms) if _rooms else None
                if _solid is not None and not _solid.is_empty:
                    # zoclo recorrido ~3 cm hacia adentro para que quede sobre el piso
                    linea = _solid.buffer(-0.03).boundary
                    if _esc_zona is not None:              # quitar el de la escalera
                        linea = linea.difference(_esc_zona.buffer(0.03))
                    _plot_linea(linea)
        except Exception:
            pass
        ax.set_xlim(minx - 0.3, maxx + 0.3); ax.set_ylim(miny - 0.3, maxy + 0.3)
        ax.set_aspect("equal"); ax.axis("off")
        col_rec = ESTILO[(material, False)]["face"]
        col_com = ESTILO[(material, True)]["face"]
        _zlab = "verde = zoclo" if material == "Moret" else "morado = zoclo recámaras"
        ax.set_title(f"PLANO {modelo.upper()} — PISO {material.upper()}\n"
                     f"(coloreado = {material}; gris claro = el otro piso; {_zlab})",
                     fontsize=12)
        ax.legend(handles=[
            Patch(facecolor=col_com, edgecolor="#333", label=f"{material} completa"),
            Patch(facecolor=col_rec, edgecolor="#333", label=f"{material} recorte"),
            Patch(facecolor="#f4f6f6", edgecolor="#d5d8dc", label="otro piso (contexto)"),
            Patch(facecolor=zcol, label=f"zoclo {material}"),
        ], loc="upper center", ncol=4, fontsize=9, bbox_to_anchor=(0.5, -0.02))
        fig.tight_layout()
        guardar(fig)

        # ---------- Página 1b: RECORTES CON SU PIEZA COMPLETA ----------
        pc = PREF_CORTE[material]
        recortes_plan = [p for p in focal if not p["completa"]]
        cxh = sum(p["x"] for p in focal) / len(focal) if focal else 0
        cyh = sum(p["y"] for p in focal) / len(focal) if focal else 0
        # Según el empaque: de dónde sale cada recorte. "TABLA" = se corta de una
        # baldosa nueva; cualquier otra etiqueta = sale del SOBRANTE de esa pieza
        # (no se abre tabla nueva).
        origen_de = {}
        for b in baldosas:
            for (x, y, w, l, etq, rot), (origen, orden) in zip(b.piezas, b.meta):
                origen_de[etq] = origen
        n_sobra = sum(1 for p in recortes_plan
                      if origen_de.get(p["id"], "TABLA") != "TABLA")
        if recortes_plan:
            fig, ax = plt.subplots(figsize=(min(24, W * 1.4), min(16, H * 1.4) + 1))
            for p in focal:
                ax.add_patch(Rectangle((p["x0"], p["y0"]), p["wx"], p["hy"],
                                       facecolor="#eef3f8" if p["completa"] else "#ffffff",
                                       edgecolor="#d5d8dc", lw=0.3))
            for p in recortes_plan:
                org = origen_de.get(p["id"], "TABLA")
                if org != "TABLA":
                    # Sale del sobrante de otra pieza: NO se corta tabla nueva.
                    # Se marca en morado para indicar que ya está "de sobra".
                    ax.add_patch(Rectangle((p["x0"], p["y0"]), p["wx"], p["hy"],
                                           facecolor="#d2b4de", edgecolor="#6c3483", lw=0.7))
                    _tapar_notch(ax, p, edge="#6c3483")
                    ax.text(p["x"], p["y"], f"{p['id']}\n(de {org.split()[0]})",
                            ha="center", va="center", fontsize=3.2,
                            rotation=0 if p["wx"] >= p["hy"] else 90, color="#4a235a")
                    continue
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
            ax.legend(handles=[
                Patch(facecolor="#aed6f1", edgecolor="#1b4f72",
                      label="recorte cortado de tabla nueva"),
                Patch(facecolor="#fcf3cf", edgecolor="#b7950b",
                      label="sobrante de ese corte"),
                Patch(facecolor="#d2b4de", edgecolor="#6c3483",
                      label="sale de un sobrante previo (sin corte nuevo)"),
            ], loc="upper center", ncol=3, fontsize=9, bbox_to_anchor=(0.5, -0.02))
            ax.set_title(f"RECORTES Y SU PIEZA COMPLETA — {modelo.upper()} · {material.upper()}\n"
                         "azul = recorte que se corta de tabla nueva (línea punteada = baldosa entera, "
                         "amarillo = su sobrante)\n"
                         f"morado = recorte que SALE de un sobrante previo, no se corta tabla nueva "
                         f"({n_sobra} piezas)",
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
        axr = fig.add_axes([0, 0, 1, 1]); axr.axis("off")
        axr.set_xlim(0, 1); axr.set_ylim(0, 1)
        # banda de título
        axr.add_patch(Rectangle((0, 0.88), 1, 0.12, facecolor="#1b4f72", edgecolor="none"))
        axr.text(0.5, 0.94, f"PISO {material.upper()} — RESUMEN", ha="center", va="center",
                 fontsize=20, fontweight="bold", color="white")
        axr.text(0.5, 0.905, f"{modelo}", ha="center", va="center",
                 fontsize=11, color="#d6eaf8")
        # tarjetas KPI (3 arriba: piezas / cajas / m² instalados)
        kpis = [
            ("PIEZAS TOTALES", f"{total_pzas}", f"{completas} enteras · {len(baldosas)} con recorte", "#eaf2f8", "#2471a3"),
            ("CAJAS", f"{cajas}", f"{cfg['pzas_caja']} pzas/caja = {cajas*cfg['pzas_caja']} pzas", "#eafaf1", "#1e8449"),
            ("SUPERFICIE", f"{cajas*cfg['m2_caja']:.1f} m²", f"caja = {cfg['m2_caja']:g} m²", "#fef9e7", "#b7950b"),
        ]
        xs = [0.06, 0.385, 0.71]; cw = 0.23
        for (titulo, valor, sub, fc, ec), x in zip(kpis, xs):
            axr.add_patch(FancyBboxPatch((x, 0.62), cw, 0.18,
                          boxstyle="round,pad=0.012,rounding_size=0.02",
                          facecolor=fc, edgecolor=ec, lw=1.4))
            axr.text(x + cw/2, 0.762, titulo, ha="center", va="center",
                     fontsize=9.5, fontweight="bold", color=ec)
            axr.text(x + cw/2, 0.705, valor, ha="center", va="center",
                     fontsize=22, fontweight="bold", color="#1b2631")
            axr.text(x + cw/2, 0.648, sub, ha="center", va="center",
                     fontsize=8, color="#566573")
        # franja de aprovechamiento (sobrante reutilizable vs merma)
        axr.add_patch(FancyBboxPatch((0.06, 0.40), 0.88, 0.15,
                      boxstyle="round,pad=0.012,rounding_size=0.02",
                      facecolor="#fbfcfc", edgecolor="#aeb6bf", lw=1.2))
        axr.text(0.10, 0.51, "APROVECHAMIENTO DEL MATERIAL", ha="left", va="center",
                 fontsize=10.5, fontweight="bold", color="#1b4f72")
        axr.text(0.10, 0.455, "Sobrante reutilizable (≥10 cm, sirve para otra pieza)",
                 ha="left", va="center", fontsize=10, color="#566573")
        axr.text(0.90, 0.455, f"{area_reut:.2f} m²", ha="right", va="center",
                 fontsize=12, fontweight="bold", color="#1e8449")
        axr.text(0.10, 0.420, "Desperdicio real / merma (<10 cm, ya no sirve)",
                 ha="left", va="center", fontsize=10, color="#566573")
        axr.text(0.90, 0.420, f"{area_desp:.2f} m²", ha="right", va="center",
                 fontsize=12, fontweight="bold", color="#c0392b")
        # nota guía
        axr.text(0.06, 0.30,
                 "En las páginas siguientes se detalla cada pieza que se corta y a dónde va. El PLAN DE CORTE\n"
                 "usa un color por orden (1°/2°/3°…) y gris rayado para el sobrante de cada tabla; las TABLAS\n"
                 "DE SOBRANTE finales separan amarillo = reutilizable (≥10 cm) de rojo = desperdicio (<10 cm).\n"
                 "Royal Walnut sólo en recámaras (planta alta).",
                 fontsize=10.5, va="top", color="#2c3e50")
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
                ax.set_title(f"Pieza {pc}-{idx:02d} · {len(b.piezas)} recorte(s)", fontsize=9, weight="bold")
            for ax in axes[len(grupo):]:
                ax.axis("off")
            fig.suptitle(f"{material} — recortes: qué cortar, a dónde va y qué sobra\n"
                         f"(cada color = un recorte a cortar de esta pieza · amarillo = sobrante "
                         f"reutilizable · rojo = desperdicio)   pág. {ini//POR_PAGINA + 1} de {npag}",
                         fontsize=11)
            fig.tight_layout(rect=[0, 0.04, 1, 0.95])
            guardar(fig)

        # ---------- Página: ZOCLO (catálogo de corte) — antes de las tablas ----------
        try:
            pagina_zoclo(pdf, guardar, modelo, material)
        except Exception:
            pass

        # ---------- Páginas: MURO DE REGADERA y ESCALERA (sólo Moret) — antes de las tablas ----------
        if material == "Moret":
            try:
                pagina_muro_regadera(pdf, guardar, modelo)        # alzado tipo (ventana + nicho)
            except Exception:
                pass
            try:
                pagina_despiece_regadera(pdf, guardar, modelo)    # despiece 3 caras + recortes
            except Exception:
                pass
            try:
                pagina_despiece_escalera(pdf, guardar, modelo)    # despiece escalera (peralte 0.175)
            except Exception:
                pass

        # ---------- Página: PLAN DE CORTE (orden + reuso de sobrantes) ----------
        try:
            pagina_plan_corte(pdf, guardar, modelo, material, baldosas_all)
        except Exception:
            pass

        # ---------- Página FINAL: todos los sobrantes sumados ----------
        from collections import Counter
        reut = Counter()      # (w,l) -> cantidad
        desp = Counter()
        for b in baldosas_all:
            for (fx, fy, fw, fl, *_z) in b.libres:
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
        if material == "Moret":
            area_inst += (extra_reg["m2"] if extra_reg else 0) + (extra_esc["m2"] if extra_esc else 0)
        area_comprada = cajas * cfg["m2_caja"]
        total_sobra = area_reut + area_desp
        cab = (f"Total de piezas: {total_pzas}  ·  {cajas} cajas  ·  {area_comprada:.2f} m²    |    "
               f"Área neta instalada: {area_inst:.2f} m²\n"
               f"Recortes acomodados en {len(baldosas_all)} piezas (piso + muro de regadera + escalera), "
               f"reusando al máximo cada sobrante.")
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
            axg.text(0.02, 0.90, "CONCEPTO", fontsize=8, fontweight="bold", transform=axg.transAxes)
            axg.text(0.40, 0.90, "CANTIDAD", fontsize=8, fontweight="bold", transform=axg.transAxes)
            axg.text(0.82, 0.90, "SUMINISTRO", fontsize=8, fontweight="bold", transform=axg.transAxes)
            axg.axhline(0.885, xmin=0.02, xmax=0.98, color="#333", lw=1.0)
            yy = 0.84
            for _cc, _dd, _ss in _G.reporte(modelo):
                axg.text(0.02, yy, _cc, fontsize=7.5, fontweight="bold", transform=axg.transAxes)
                axg.text(0.40, yy, _dd, fontsize=7.5, transform=axg.transAxes)
                axg.text(0.82, yy, _ss, fontsize=7.5, color="#1b4f72", transform=axg.transAxes)
                axg.axhline(yy - 0.025, xmin=0.02, xmax=0.98, color="#e5e5e5", lw=0.5)
                yy -= 0.085
            axg.text(0.02, 0.10, "Zoclo: Moret se corta a 0.149 m (4 por baldosa, sale exacto); Royal 0.15 m por tabla. "
                     "Urbania White 0.30×0.45 (lavandería). Malla Lyndhurst 0.30×0.60 (charola). "
                     "Muro de regadera = Moret acostado, fondo 1.50 m, ventana al plafón descontada, alto P.B. 2.75 / P.A. 2.90 m.",
                     fontsize=8, color="#444", transform=axg.transAxes, va="top")
            guardar(fig)
        except Exception:
            pass

    return total_pzas, cajas, area_reut, area_desp


def main(modelo="Cabernet"):
    todas = cargar_anotado(modelo)
    salidas = {"Moret": f"Viñas Norte - {modelo} Moret.pdf",
               "Royal Walnut": f"Viñas Norte - {modelo} Royal.pdf"}
    for material, path in salidas.items():
        pzas, cajas, reut, desp = hacer_pdf(todas, material, path, modelo)
        print(f"{modelo} · {material}: {pzas} piezas / {cajas} cajas  ·  reutilizable "
              f"{reut:.2f} m²  ·  desperdicio {desp:.2f} m²  ->  {path}")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "Cabernet")
