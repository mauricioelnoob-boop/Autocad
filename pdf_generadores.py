#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf_generadores.py
==================
Genera, por prototipo, un PDF de "Generadores de acabados" con:
  Pág 1: tabla de números generadores (piso, zoclo, Urbania, Malla, muro regadera).
  Pág 2: diagrama del plano con el ZOCLO (verde), la zona de URBANIA (lavandería),
         las REGADERAS (Malla + muro) marcadas, y el despiece de piso de fondo.
  Pág 3: alzados (elevaciones) tipo de muro de regadera con el despiece Moret.

Uso:  python3 pdf_generadores.py [Modelo ...]
"""
import json, math, datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Patch, Polygon as Patch_Polygon
from matplotlib.backends.backend_pdf import PdfPages

from modelos import MODELOS
from datos_piezas import cargar_anotado
import generadores as G

FECHA = datetime.date.today().strftime("%d/%m/%Y")
PIE = "Elaboró: Ing. Mauricio Gastelum Mora"


def _capas(objs):
    capas = {}
    for o in objs:
        if o.get("object") == "LAYER":
            h = o.get("handle")
            if isinstance(h, list):
                capas[h[-1]] = o.get("name")
    return capas


def _segmentos(objs, capas, frag):
    def capa(o):
        l = o.get("layer")
        return capas.get(l[-1], "?") if isinstance(l, list) else "?"
    S = []
    for o in objs:
        if frag not in capa(o):
            continue
        e = o.get("entity"); pts = []
        if e == "LWPOLYLINE":
            pts = [(p[0], p[1]) for p in o.get("points", [])]
            if o.get("flag", 0) & 1 and len(pts) > 2:
                pts = pts + [pts[0]]
        elif e == "LINE":
            s = o.get("start"); en = o.get("end")
            if s and en:
                pts = [(s[0], s[1]), (en[0], en[1])]
        S += [(a, b) for a, b in zip(pts, pts[1:]) if a != b]
    return S


def _datos_dwg(modelo):
    cfg = MODELOS[modelo]
    doc = json.loads(open(cfg["json"], "rb").read().decode("utf-8", "replace"))
    objs = doc["OBJECTS"]; capas = _capas(objs)
    zoclo = _segmentos(objs, capas, "A-ZOCLO")
    # muros = los estructurales (A-MUROS, incluye A-MUROS BAJOS por fragmento)
    # + los MUROS FALSOS de tablaroca (más delgados), que también delimitan piso
    muros = (_segmentos(objs, capas, "A-MUROS")
             + _segmentos(objs, capas, "A-TABLAROCA"))
    escal = _segmentos(objs, capas, "A-ESCALON")
    claves = json.load(open(cfg["claves"]))
    return zoclo, muros, escal, claves


def guardar(pdf, fig, modelo):
    fig.text(0.5, 0.015, f"{PIE}        Generadores de acabados — {modelo}        {FECHA}",
             ha="center", fontsize=8, color="#555")
    pdf.savefig(fig); plt.close(fig)


def pagina_tabla(pdf, modelo):
    fig = plt.figure(figsize=(11.7, 8.3))
    ax = fig.add_subplot(111); ax.axis("off")
    ax.set_title(f"NÚMEROS GENERADORES — ACABADOS · {modelo.upper()}",
                 fontsize=15, fontweight="bold")
    ax.text(0.02, 0.90, "CONCEPTO", fontsize=8.5, fontweight="bold", transform=ax.transAxes)
    ax.text(0.40, 0.90, "CANTIDAD", fontsize=8.5, fontweight="bold", transform=ax.transAxes)
    ax.text(0.82, 0.90, "SUMINISTRO", fontsize=8.5, fontweight="bold", transform=ax.transAxes)
    ax.axhline(0.885, xmin=0.02, xmax=0.98, color="#333", lw=1.0)
    y = 0.84
    for concepto, detalle, cajas in G.reporte(modelo):
        ax.text(0.02, y, concepto, fontsize=8, fontweight="bold", transform=ax.transAxes)
        ax.text(0.40, y, detalle, fontsize=8, transform=ax.transAxes)
        ax.text(0.82, y, cajas, fontsize=8, color="#1b4f72", transform=ax.transAxes)
        ax.axhline(y - 0.025, xmin=0.02, xmax=0.98, color="#e5e5e5", lw=0.5)
        y -= 0.085
    nota = ("Zoclo: Moret se corta a 0.149 m = 4 tiras EXACTAS por pieza (4 x 0.149 = 0.596) con cortadora de diamante (rayar y tronchar, corte sin merma). Royal 1 tira/tabla. Largo 1.194 m; ml del generador del cliente.\n"
            "Urbania White 0.30×0.45 m horizontal (lavandería) — 10 pzas/caja, 1.36 m²/caja.\n"
            "Malla Lyndhurst 0.30×0.60 m en charola de regadera (~1.5 m²/charola).\n"
            "Piso en muro de regadera = piso Moret acostado; fondo 1.50 m, alto = NPT − losa (P.B. 2.75 m, P.A. 2.90 m), 3 caras, menos la ventana (1.50×0.90 al plafón).")
    ax.text(0.02, 0.10, nota, fontsize=8.5, color="#444", transform=ax.transAxes, va="top")
    guardar(pdf, fig, modelo)


def pagina_plano(pdf, modelo):
    zoclo, muros, escal, claves = _datos_dwg(modelo)
    ps = cargar_anotado(modelo)
    fig, ax = plt.subplots(figsize=(13.5, 9.0))
    for p in ps:
        col = "#fbe6c8" if p["material"] == "Moret" else "#e8e8e8"
        ax.add_patch(Rectangle((p["x0"], p["y0"]), p["wx"], p["hy"],
                     facecolor=col, edgecolor="#d9d9d9", lw=0.2))
        for ring in p.get("notch", []):
            if len(ring) >= 3:
                ax.add_patch(Patch_Polygon(ring, closed=True, facecolor="#ffffff",
                             edgecolor="#d9d9d9", lw=0.2, zorder=2))
    for a, b in muros:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#cc2222", lw=1.0, zorder=3)
    for a, b in escal:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#8e44ad", lw=0.8, zorder=3)
    # zoclo (verde grueso)
    first = True
    for a, b in zoclo:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#1e8449", lw=2.6, zorder=4,
                label="Zoclo" if first else None); first = False
    # claves: 5=Urbania (azul), 2=regadera (rojo)
    for c in claves:
        if c[0] == "5":
            ax.scatter([c[1]], [c[2]], s=120, marker="s", c="#2e86c1", zorder=5,
                       edgecolors="black")
        elif c[0] == "2":
            ax.scatter([c[1]], [c[2]], s=160, marker="*", c="#e74c3c", zorder=5,
                       edgecolors="black")
    xs = [p["x0"] for p in ps] + [p["x0"] + p["wx"] for p in ps]
    ys = [p["y0"] for p in ps] + [p["y0"] + p["hy"] for p in ps]
    ax.set_xlim(min(xs) - 0.5, max(xs) + 0.5); ax.set_ylim(min(ys) - 0.5, max(ys) + 0.5)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(f"DIAGRAMA DE ACABADOS — {modelo.upper()}\n"
                 "verde = zoclo · ▣ azul = Urbania (lavandería) · ★ rojo = regadera (Malla + muro)",
                 fontsize=12)
    ax.legend(handles=[
        Patch(facecolor="#1e8449", label="Zoclo (perímetro Moret)"),
        Patch(facecolor="#2e86c1", label="Urbania White (lavandería)"),
        Patch(facecolor="#e74c3c", label="Regadera (Malla + muro Moret)"),
        Patch(facecolor="#fbe6c8", label="Piso Moret"),
        Patch(facecolor="#e8e8e8", label="Piso Royal"),
    ], loc="upper center", ncol=5, fontsize=8, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout()
    guardar(pdf, fig, modelo)


def pagina_regaderas(pdf, modelo):
    """Alzado tipo del muro de fondo de la regadera: piso Moret ACOSTADO
    (1.194 ancho × 0.596 alto). Muro de fondo 1.50 m de ancho; ventana pegada al
    plafón del ancho del fondo (1.50 m) × 0.90 m de alto (descontada); nicho de
    0.09 m de profundidad. Alto = NPT − losa; varía por baño."""
    g = G.GEN[modelo]
    tw, th = G.MORET[0], G.MORET[1]   # acostada: 1.194 ancho x 0.596 alto
    FONDO = G.REG_FONDO                # 1.50 m
    VH = G.VENTANA_ALTO                # ventana 0.90 m, del ancho del fondo, al plafón
    NA, NH, NP = G.NICHO_ANCHO, G.NICHO_ALTO, G.NICHO_PROF
    fig, axes = plt.subplots(1, len(g["regaderas"]), figsize=(3.7 * len(g["regaderas"]), 7.2))
    if len(g["regaderas"]) == 1:
        axes = [axes]
    for k, (ax, (planta, h)) in enumerate(zip(axes, g["regaderas"]), 1):
        vy = h - VH                   # la ventana llega al plafón
        # despiece acostado SÓLO bajo la ventana
        y = 0.0
        while y < vy - 1e-6:
            hh = min(th, vy - y)
            x = 0.0
            while x < FONDO - 1e-6:
                w = min(tw, FONDO - x)
                ax.add_patch(Rectangle((x, y), w, hh, facecolor="#f5b66b",
                             edgecolor="#7e5109", lw=0.6))
                x += tw
            y += th
        # ventana (no se enchapa), pegada al plafón y del ancho del fondo
        ax.add_patch(Rectangle((0, vy), FONDO, VH, facecolor="#d6eaf8",
                     edgecolor="#2e86c1", lw=1.6, zorder=5))
        ax.text(FONDO / 2, vy + VH / 2, f"VENTANA\n{FONDO:.2f}×{VH:.2f} m",
                ha="center", va="center", fontsize=7, color="#1b4f72", zorder=6)
        # nicho recesado (0.09 m de profundidad), RECARGADO a la izquierda
        # (lado del monomando, donde va la pieza completa)
        nx, ny = 0.0, vy - 0.45 - NH
        ax.add_patch(Rectangle((nx, ny), NA, NH, fill=False, edgecolor="#c0392b", lw=1.8))
        ax.text(nx + NA / 2, ny + NH / 2, f"NICHO\nprof. {NP:.2f} m", ha="center",
                va="center", fontsize=6.5, color="#c0392b")
        ax.set_xlim(-0.1, FONDO + 0.1); ax.set_ylim(-0.1, h + 0.2)
        ax.set_aspect("equal")
        wm2 = max(0.0, G.REG_PERIM * h - G.VENTANA_M2)
        ax.set_title(f"Regadera {k} ({planta})\nmuro de fondo {FONDO:.2f}×{h:.2f} m  ·  "
                     f"3 caras − ventana = {wm2:.2f} m²", fontsize=9)
        ax.set_xlabel("fondo (m) — piezas acostadas")
    fig.suptitle(f"ALZADO TIPO — MURO DE REGADERA (piso Moret ACOSTADO) · {modelo.upper()}",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    guardar(pdf, fig, modelo)


def main(modelo):
    out = f"{modelo}_Generadores-Acabados.pdf"
    with PdfPages(out) as pdf:
        pagina_tabla(pdf, modelo)
        pagina_plano(pdf, modelo)
        pagina_regaderas(pdf, modelo)
    print("->", out)


if __name__ == "__main__":
    import sys
    for m in (sys.argv[1:] or list(MODELOS)):
        main(m)
