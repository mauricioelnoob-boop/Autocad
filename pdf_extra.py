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


def _zoclo_tablas(modelo, material):
    if material == "Moret":
        ml = G.GEN[modelo]["zoclo_m"]; largo = 1.194; per = 4
    else:
        ml = G.GEN[modelo]["zoclo_r"]; largo = 1.20; per = 1
    return math.ceil(math.ceil(ml / largo) / per)


def real_datos(modelo):
    """REQUERIDO REAL = baldosas que de verdad se ocupan (piso + regadera +
    escalera + zoclo) con el corte real y redondeo a caja entera. El DESPERDICIO
    real = comprado - neto."""
    from datos_piezas import cargar_anotado
    from optimizador_recortes import ajustar, empaquetar, PISOS
    todas = cargar_anotado(modelo)
    d = resumen_datos(modelo)
    out = {}
    for material, pzc, cm2, net in (("Moret", G.MORET_PZCAJA, G.MORET_CAJA, d["moret"]["total"]),
                                    ("Royal Walnut", G.ROYAL_PZCAJA, G.ROYAL_CAJA, d["royal"]["total"])):
        an, la = PISOS[material]
        # TODOS los recortes juntos (piso + regadera + escalera + zoclo) en un solo
        # empaquetado: el corte reutiliza el sobrante de cada baldosa (lo más real).
        comp = sum(1 for p in todas if p["material"] == material and p["completa"])
        ent = [(*ajustar(p["ancho"], p["largo"], an, la), p["id"])
               for p in todas if p["material"] == material and not p["completa"]]
        if material == "Moret":
            for r in (DE.regadera_resumen(modelo), DE.escalera_resumen(modelo)):
                comp += r["completas"]
                ent += [(*ajustar(p["ancho"], p["largo"], an, la), "X")
                        for p in r["piezas"] if not p["completa"]]
            zml, zw, zl = G.GEN[modelo]["zoclo_m"], 0.149, 1.194
        else:
            zml, zw, zl = G.GEN[modelo]["zoclo_r"], 0.15, 1.20
        ent += [(zw, zl, "Z")] * math.ceil(zml / zl)
        baldosas = empaquetar(ent, material, 0.0, True)
        cajas = math.ceil((comp + len(baldosas)) / pzc)
        comprado = cajas * cm2
        # separar el desperdicio: sobrante REUSABLE (>=10cm) vs MERMA real (<10cm)
        reut = merma = 0.0
        for b in baldosas:
            for (fx, fy, fw, fl, *_z) in b.libres:
                if fw > 0.005 and fl > 0.005:
                    if fw >= 0.10 and fl >= 0.10:
                        reut += fw * fl
                    else:
                        merma += fw * fl
        out[material] = {"neto": net, "cajas": cajas, "comprado": comprado,
                         "desp": max(0.0, comprado - net),
                         "reusable": reut, "merma": merma}
    # Urbania (despiece real) y Malla
    *_, upz, ucajas, uarea = urbania_despiece(modelo)[3:]
    out["Urbania"] = {"neto": uarea, "cajas": ucajas, "comprado": ucajas * G.URB_CAJA,
                      "desp": max(0.0, ucajas * G.URB_CAJA - uarea)}
    out["Malla_pz"] = d["malla"]["pzas"]
    return out


def pagina_comparativo(pdf, modelo):
    R = real_datos(modelo); P = PRESUP[modelo]
    fig = plt.figure(figsize=(11.7, 8.3))
    ax = fig.add_subplot(111); ax.axis("off")
    ax.set_title(f"GENERADORES (con DESPERDICIO REAL) vs PRESUPUESTO · {modelo.upper()}",
                 fontsize=14.5, fontweight="bold", y=0.97)

    cols = ["MATERIAL", "NETO\n(m²)", "SOBRANTE\nREUSABLE (m²)", "MERMA\nREAL (m²)",
            "REQUERIDO\n(cajas)", "SUMINISTRADO\n(cajas)", "DIFERENCIA\n(cajas)"]
    spec = [("PISO Moret Arena", "Moret", P["Moret"]),
            ("PISO Royal Walnut", "Royal Walnut", P["Royal"]),
            ("Urbania White", "Urbania", P["Urbania"])]
    cell, colors = [], []
    for (etq, key, sumin) in spec:
        r = R[key]
        dif_c = sumin - r["cajas"]
        cell.append([etq, f"{r['neto']:.2f}", f"{r.get('reusable',0):.2f}",
                     f"{r.get('merma',0):.2f}", f"{r['cajas']}", f"{sumin}", f"{dif_c:+d}"])
        cd = "#d5f5e3" if dif_c >= 0 else "#f5b7b1"
        colors.append(["#f4f6f7", "#fdfefe", "#eafaf1", "#fdf2e9", "#fdfefe", "#eaf2f8", cd])
    # Malla (en piezas)
    req_pz = R["Malla_pz"]; sum_pz = P["Malla_pz"]; difp = sum_pz - req_pz
    cdp = "#d5f5e3" if difp >= 0 else "#f5b7b1"
    cell.append(["Malla Lyndhurst (pz)", f"{req_pz} pz", "—", "—", f"{req_pz} pz",
                 f"{sum_pz} pz", f"{difp:+d}"])
    colors.append(["#f4f6f7", "#fdfefe", "#eafaf1", "#fdf2e9", "#fdfefe", "#eaf2f8", cdp])

    t = ax.table(cellText=cell, colLabels=cols, cellColours=colors,
                 cellLoc="center", loc="center", bbox=[0.0, 0.34, 1.0, 0.5])
    t.auto_set_font_size(False); t.set_fontsize(9); t.scale(1, 2.3)
    for (rr, cc), c in t.get_celld().items():
        if rr == 0:
            c.set_facecolor("#1b4f72"); c.set_text_props(color="white", weight="bold")
        if cc == 0 and rr > 0:
            c.set_text_props(weight="bold")

    falta = [s[0] for s in spec if (P[{"Moret":"Moret","Royal Walnut":"Royal","Urbania":"Urbania"}[s[1]]] - R[s[1]]["cajas"]) < 0]
    estado = ("⚠ Aún con el reuso óptimo, el presupuesto QUEDA CORTO en: " + ", ".join(falta)
              if falta else "✓ El presupuesto alcanza en todos los materiales.")
    ax.text(0.5, 0.27, estado, ha="center", fontsize=11, fontweight="bold",
            color="#922b21" if falta else "#1e8449", transform=ax.transAxes)

    nota = ("REQUERIDO = cajas que de verdad se ocupan, empacando TODOS los recortes juntos y REUSANDO el sobrante\n"
            "de cada baldosa (con rotación) antes de abrir tabla nueva.  El 'desperdicio' se separa en:\n"
            "  • SOBRANTE REUSABLE (≥10 cm) = pedazos que SÍ sirven para otra pieza (stock, no se pierde).\n"
            "  • MERMA REAL (<10 cm) = lo único que de verdad se tira (es chica).\n"
            "DIFERENCIA = SUMINISTRADO − REQUERIDO (verde = alcanza; rojo = faltan cajas aún con reuso óptimo).")
    ax.text(0.02, 0.20, nota, fontsize=8.5, color="#444", transform=ax.transAxes, va="top",
            bbox=dict(boxstyle="round", facecolor="#fef9e7", edgecolor="#b7950b"))
    fig.text(0.5, 0.03, f"{PIE}        Generadores (desperdicio real) vs Presupuesto — {modelo}        {FECHA}",
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
