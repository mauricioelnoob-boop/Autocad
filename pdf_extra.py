#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf_extra.py
============
PDFs ligeros adicionales (NO tocan los despieces pesados ni los DXF):

  1) <Modelo>_Urbania-White_Despiece.pdf
     Despiece sencillo del piso Urbania White de la lavandería (0.45 x 0.30,
     10 pz/caja, 1.36 m2/caja). Muestra el acomodo y las cantidades.

  2) <Modelo>_Generadores-Resumen.pdf
     Resumen que SUMA todo por material (Moret = piso + zoclo + regadera +
     escalera; Royal = piso + zoclo; Urbania; Malla). m2 NETOS, SIN % de
     desperdicio.
"""
import math
import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.backends.backend_pdf import PdfPages

import generadores as G
import despiece_extra as DE

FECHA = datetime.date.today().strftime("%d/%m/%Y")
PIE = "Elaboró: Ing. Mauricio Gastelum Mora"


# ---------------------------------------------------------------- Urbania
def urbania_despiece(modelo):
    """Acomodo del Urbania White en un rectángulo ~ área de lavandería del modelo."""
    area = G.GEN[modelo]["urbania_m2"]
    tw, th = G.URB                       # 0.45 x 0.30
    # rectángulo representativo de la lavandería (ancho fijo, alto por área)
    W = 3.60
    H = round(area / W, 2)
    piezas = []
    y = 0.0
    while y < H - 1e-6:
        hh = min(th, H - y); x = 0.0
        while x < W - 1e-6:
            ww = min(tw, W - x)
            completa = abs(ww - tw) < 0.01 and abs(hh - th) < 0.01
            piezas.append((x, y, ww, hh, completa))
            x += tw
        y += th
    comp = sum(1 for *_, c in piezas if c)
    rec = len(piezas) - comp
    pzas = comp + rec
    cajas = math.ceil(pzas / G.URB_PZCAJA)
    return W, H, piezas, comp, rec, pzas, cajas, area


def pagina_urbania(pdf, modelo):
    W, H, piezas, comp, rec, pzas, cajas, area = urbania_despiece(modelo)
    fig, ax = plt.subplots(figsize=(11.0, 7.0))
    for (x, y, w, h, c) in piezas:
        ax.add_patch(Rectangle((x, y), w, h, facecolor="#d6eaf8" if c else "#aed6f1",
                     edgecolor="#1b4f72", lw=0.6))
    ax.set_xlim(-0.1, W + 0.1); ax.set_ylim(-0.1, H + 0.1); ax.set_aspect("equal")
    ax.set_title(f"DESPIECE — URBANIA WHITE (lavandería) · {modelo.upper()}\n"
                 f"pieza 0.45 × 0.30 m · área ≈ {area:.2f} m² · {comp} completas + {rec} recortes "
                 f"= {pzas} pzas · {cajas} cajas (10 pz/caja, 1.36 m²/caja)",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("acomodo representativo de la lavandería (m)")
    ax.text(0.5, -0.13, "El Urbania White va en el cuarto de lavado; el acomodo real se ajusta a la "
            "forma del cuarto (este es el conteo y el corte tipo).", transform=ax.transAxes,
            ha="center", fontsize=8.5, color="#555")
    fig.text(0.5, 0.02, f"{PIE}        Urbania White — {modelo}        {FECHA}",
             ha="center", fontsize=8, color="#555")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    pdf.savefig(fig); plt.close(fig)


# ---------------------------------------------------------------- Resumen
def resumen_datos(modelo):
    am, ar = G.area_piso(modelo)                         # piso Moret / Royal
    zmp, zmm2, _ = G.zoclo(G.GEN[modelo]["zoclo_m"], G.MORET_CAJA)   # zoclo Moret
    zrp, zrm2, _ = G.zoclo(G.GEN[modelo]["zoclo_r"], G.ROYAL_CAJA)   # zoclo Royal
    reg = DE.regadera_resumen(modelo)["m2"]
    esc = DE.escalera_resumen(modelo)
    esc_m2 = esc["m2"]
    esc_zoclo_m2 = 0.0
    if esc.get("zoclo_orilla"):
        _, esc_zoclo_m2, _ = G.zoclo(5.0, G.MORET_CAJA)   # zoclo de orilla de escalera (Chardonnay)
    urb = G.GEN[modelo]["urbania_m2"]
    nch = len(G.GEN[modelo]["regaderas"])
    malla_pz = math.ceil(nch * G.MALLA_M2_CHAROLA / G.MALLA_M2)

    moret_tot = am + zmm2 + reg + esc_m2 + esc_zoclo_m2
    royal_tot = ar + zrm2
    return {
        "moret": {"piso": am, "zoclo": zmm2, "regadera": reg,
                  "escalera": esc_m2 + esc_zoclo_m2, "total": moret_tot,
                  "cajas": math.ceil(moret_tot / G.MORET_CAJA)},
        "royal": {"piso": ar, "zoclo": zrm2, "total": royal_tot,
                  "cajas": math.ceil(royal_tot / G.ROYAL_CAJA)},
        "urbania": {"total": urb, "cajas": math.ceil(urb / G.URB_CAJA)},
        "malla": {"pzas": malla_pz},
    }


def pagina_resumen(pdf, modelo):
    d = resumen_datos(modelo)
    fig = plt.figure(figsize=(11.7, 8.3))
    ax = fig.add_subplot(111); ax.axis("off")
    ax.set_title(f"RESUMEN DE GENERADORES — m² NETOS (sin % de desperdicio) · {modelo.upper()}",
                 fontsize=14, fontweight="bold")
    ax.text(0.03, 0.88, "MATERIAL", fontsize=10, fontweight="bold", transform=ax.transAxes)
    ax.text(0.27, 0.88, "DESGLOSE (m²)", fontsize=10, fontweight="bold", transform=ax.transAxes)
    ax.text(0.79, 0.88, "TOTAL", fontsize=10, fontweight="bold", transform=ax.transAxes)
    ax.text(0.91, 0.88, "CAJAS", fontsize=10, fontweight="bold", transform=ax.transAxes)
    ax.axhline(0.865, xmin=0.03, xmax=0.99, color="#333", lw=1.0)

    m = d["moret"]; r = d["royal"]
    filas = [
        ("PISO MORET ARENA",
         f"piso {m['piso']:.2f} + zoclo {m['zoclo']:.2f} + regadera {m['regadera']:.2f} + escalera {m['escalera']:.2f}",
         f"{m['total']:.2f} m²", f"{m['cajas']} cajas"),
        ("PISO ROYAL WALNUT",
         f"piso {r['piso']:.2f} + zoclo {r['zoclo']:.2f}",
         f"{r['total']:.2f} m²", f"{r['cajas']} cajas"),
        ("URBANIA WHITE", "lavandería", f"{d['urbania']['total']:.2f} m²", f"{d['urbania']['cajas']} cajas"),
        ("MALLA LYNDHURST", "charolas de regadera", f"{d['malla']['pzas']} pzas", "—"),
    ]
    y = 0.80
    for mat, des, tot, caj in filas:
        ax.text(0.03, y, mat, fontsize=10, fontweight="bold", transform=ax.transAxes)
        ax.text(0.27, y, des, fontsize=8.5, transform=ax.transAxes)
        ax.text(0.79, y, tot, fontsize=10, fontweight="bold", color="#1b4f72", transform=ax.transAxes)
        ax.text(0.91, y, caj, fontsize=10, color="#1b4f72", transform=ax.transAxes)
        ax.axhline(y - 0.04, xmin=0.03, xmax=0.99, color="#e5e5e5", lw=0.5)
        y -= 0.11

    nota = ("m² NETOS (sin sumar desperdicio). Cajas: Moret 1.4232 m²/caja (2 pz), "
            "Royal 1.20 m²/caja (5 pz), Urbania 1.36 m²/caja (10 pz). Malla por piezas (0.30×0.60).\n"
            "Moret suma piso + zoclo + muro de regadera (3 caras) + escalera (peraltes y huellas)"
            + (" + zoclo de escalera." if modelo == "Chardonnay" else "."))
    ax.text(0.03, 0.18, nota, fontsize=9, color="#444", transform=ax.transAxes, va="top",
            bbox=dict(boxstyle="round", facecolor="#eaf2f8", edgecolor="#5499c7"))
    fig.text(0.5, 0.02, f"{PIE}        Resumen de generadores — {modelo}        {FECHA}",
             ha="center", fontsize=8, color="#555")
    pdf.savefig(fig); plt.close(fig)


# ---------------------------------------------------------------- Comparativo
# Suministrado (presupuesto) — datos del cliente. Cabernet/Merlot en cajas;
# Chardonnay venía en m² (Moret 180.75, Royal 38.27, Urbania 10.12, Malla 5 m²).
PRESUP = {
    "Cabernet":   {"Moret": 117, "Royal": 41, "Urbania": 8, "Malla_pz": 28},
    "Merlot":     {"Moret": 98,  "Royal": 37, "Urbania": 8, "Malla_pz": 17},
    "Chardonnay": {"Moret": 127, "Royal": 32, "Urbania": 8, "Malla_pz": 28},
}


def _fila_comp(req_m2, caja_m2, sumin_cajas):
    req_cajas = math.ceil(req_m2 / caja_m2)
    sumin_m2 = sumin_cajas * caja_m2
    holg = (sumin_m2 - req_m2) / req_m2 * 100 if req_m2 > 0 else 0.0
    return req_m2, req_cajas, sumin_cajas, sumin_m2, holg


def pagina_comparativo(pdf, modelo):
    d = resumen_datos(modelo); P = PRESUP[modelo]
    rows = []  # material, req m2, req cajas, sumin cajas, sumin m2, holgura %
    rows.append(("PISO Moret Arena", *_fila_comp(d["moret"]["total"], G.MORET_CAJA, P["Moret"])))
    rows.append(("PISO Royal Walnut", *_fila_comp(d["royal"]["total"], G.ROYAL_CAJA, P["Royal"])))
    rows.append(("Urbania White", *_fila_comp(d["urbania"]["total"], G.URB_CAJA, P["Urbania"])))

    fig = plt.figure(figsize=(11.7, 8.3))
    ax = fig.add_subplot(111); ax.axis("off")
    ax.set_title(f"GENERADORES vs PRESUPUESTO (suministrado) · {modelo.upper()}",
                 fontsize=15, fontweight="bold", y=0.97)

    cols = ["MATERIAL", "REQUERIDO\n(m² neto)", "REQUERIDO\n(cajas)",
            "SUMINISTRADO\n(presup., cajas)", "SUMINISTRADO\n(m²)", "HOLGURA\n(% presup.)"]
    cell = []
    colors = []
    for (mat, rm2, rc, sc, sm2, h) in rows:
        cell.append([mat, f"{rm2:.2f}", f"{rc}", f"{sc}", f"{sm2:.2f}", f"{h:+.1f} %"])
        cg = "#d5f5e3" if h >= 0 else "#fadbd8"
        colors.append(["#f4f6f7", "#fdfefe", "#fdfefe", "#eaf2f8", "#eaf2f8", cg])
    # Malla por piezas
    req_pz = d["malla"]["pzas"]; sum_pz = P["Malla_pz"]
    hp = (sum_pz - req_pz) / req_pz * 100 if req_pz else 0
    cell.append(["Malla Lyndhurst", f"{req_pz} pz", "—", f"{sum_pz} pz", "—", f"{hp:+.1f} %"])
    colors.append(["#f4f6f7", "#fdfefe", "#fdfefe", "#eaf2f8", "#eaf2f8",
                   "#d5f5e3" if hp >= 0 else "#fadbd8"])

    t = ax.table(cellText=cell, colLabels=cols, cellColours=colors,
                 cellLoc="center", loc="center", bbox=[0.02, 0.35, 0.96, 0.5])
    t.auto_set_font_size(False); t.set_fontsize(9.5); t.scale(1, 2.2)
    for (rr, cc), c in t.get_celld().items():
        if rr == 0:
            c.set_facecolor("#1b4f72"); c.set_text_props(color="white", weight="bold")
        if cc == 0 and rr > 0:
            c.set_text_props(weight="bold")

    nota = ("REQUERIDO = m² netos del despiece (sin desperdicio): Moret = piso + zoclo +\n"
            "regadera + escalera;  Royal = piso + zoclo.\n"
            "SUMINISTRADO = lo que trae el presupuesto del cliente.\n"
            "HOLGURA % = cuánto cubre el presupuesto por encima de lo neto\n"
            "(verde = alcanza con holgura;  rojo = queda corto).\n"
            "Cajas: Moret 1.4232 m² (2 pz) · Royal 1.20 m² (5 pz) · Urbania 1.36 m² (10 pz).")
    ax.text(0.02, 0.24, nota, fontsize=9, color="#444", transform=ax.transAxes, va="top",
            bbox=dict(boxstyle="round", facecolor="#fef9e7", edgecolor="#b7950b"))
    fig.text(0.5, 0.03, f"{PIE}        Generadores vs Presupuesto — {modelo}        {FECHA}",
             ha="center", fontsize=8, color="#555")
    pdf.savefig(fig); plt.close(fig)


def comparativo(salida="Generadores-Resumen_Comparativo.pdf"):
    with PdfPages(salida) as pdf:
        for m in ("Cabernet", "Merlot", "Chardonnay"):
            pagina_comparativo(pdf, m)
    print("->", salida)


def main(modelo):
    out_u = f"{modelo}_Urbania-White_Despiece.pdf"
    with PdfPages(out_u) as pdf:
        pagina_urbania(pdf, modelo)
    print("->", out_u)
    out_r = f"{modelo}_Generadores-Resumen.pdf"
    with PdfPages(out_r) as pdf:
        pagina_resumen(pdf, modelo)
    print("->", out_r)


if __name__ == "__main__":
    import sys
    for mm in (sys.argv[1:] or ["Cabernet", "Merlot", "Chardonnay"]):
        main(mm)
