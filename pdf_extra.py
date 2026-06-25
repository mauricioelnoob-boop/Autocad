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
    # La hilera de recorte (altura parcial) va ABAJO: se calcula el residuo y se
    # coloca como primera fila (y=0); encima van las hileras completas.
    n_full = int(H / th + 1e-9)
    rem = round(H - n_full * th, 4)
    row_h = ([rem] if rem > 0.01 else []) + [th] * n_full
    y = 0.0
    for hh in row_h:
        x = 0.0
        while x < W - 1e-6:
            ww = min(tw, W - x)
            completa = abs(ww - tw) < 0.01 and abs(hh - th) < 0.01
            piezas.append((x, y, ww, hh, completa))
            x += tw
        y += hh
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


# Desperdicio que el PRESUPUESTO aplica sobre la base (lo suministrado = base +
# este %). De aquí se deriva la base y se compara contra el % que de verdad se
# necesita. Ajustable si algún presupuesto usara otro %.
BUDGET_PCT = 0.03


def pagina_comparativo(pdf, modelo):
    R = real_datos(modelo); P = PRESUP[modelo]
    bp = int(round(BUDGET_PCT * 100))
    fig = plt.figure(figsize=(11.7, 8.3))
    ax = fig.add_subplot(111); ax.axis("off")
    ax.set_title(f"GENERADORES — % DE DESPERDICIO REAL vs PRESUPUESTO · {modelo.upper()}",
                 fontsize=14.5, fontweight="bold", y=0.97)

    cols = ["MATERIAL", "NETO\n(m²)", f"BASE\nPRESUP. (cajas)",
            f"SUMINISTRADO\nbase + {bp}% (cajas)", "REQUERIDO\nREAL (cajas)",
            "% REAL\nNECESARIO", "FALTAN\n(cajas)"]
    spec = [("PISO Moret Arena", "Moret", P["Moret"]),
            ("PISO Royal Walnut", "Royal Walnut", P["Royal"]),
            ("Urbania White", "Urbania", P["Urbania"])]
    cell, colors = [], []
    cortos = []
    for (etq, key, sumin) in spec:
        r = R[key]; req = r["cajas"]
        base = int(round(sumin / (1 + BUDGET_PCT))) or 1
        realpct = (req / base - 1) * 100
        faltan = max(0, req - sumin)
        cd = "#d5f5e3" if faltan == 0 else "#f5b7b1"
        cell.append([etq, f"{r['neto']:.2f}", f"{base}", f"{sumin}", f"{req}",
                     f"{realpct:.1f} %", f"{faltan}" if faltan else "—"])
        colors.append(["#f4f6f7", "#fdfefe", "#eafaf1", "#eaf2f8", "#fdfefe", cd, cd])
        if faltan:
            cortos.append(f"{etq.replace('PISO ', '')}: {realpct:.0f}% (faltan {faltan})")
    # Malla (piezas): mismo esquema en pz
    req_pz = R["Malla_pz"]; sum_pz = P["Malla_pz"]
    base_pz = int(round(sum_pz / (1 + BUDGET_PCT))) or 1
    realpct_pz = (req_pz / base_pz - 1) * 100
    faltan_pz = max(0, req_pz - sum_pz)
    cdp = "#d5f5e3" if faltan_pz == 0 else "#f5b7b1"
    cell.append(["Malla Lyndhurst (pz)", f"{req_pz} pz", f"{base_pz}", f"{sum_pz}",
                 f"{req_pz}", f"{realpct_pz:.1f} %", f"{faltan_pz}" if faltan_pz else "—"])
    colors.append(["#f4f6f7", "#fdfefe", "#eafaf1", "#eaf2f8", "#fdfefe", cdp, cdp])
    if faltan_pz:
        cortos.append(f"Malla: {realpct_pz:.0f}% (faltan {faltan_pz})")

    t = ax.table(cellText=cell, colLabels=cols, cellColours=colors,
                 cellLoc="center", loc="center", bbox=[0.0, 0.36, 1.0, 0.48],
                 colWidths=[0.21, 0.11, 0.14, 0.16, 0.13, 0.13, 0.12])
    t.auto_set_font_size(False); t.set_fontsize(9.5); t.scale(1, 2.4)
    for (rr, cc), c in t.get_celld().items():
        if rr == 0:
            c.set_facecolor("#1b4f72"); c.set_text_props(color="white", weight="bold")
        if rr > 0 and cc == 0:
            c.set_text_props(weight="bold", ha="left")
        if rr > 0 and cc == 5:
            c.set_text_props(weight="bold")

    estado = ("⚠ Para que ALCANCE hay que pedir más % de desperdicio en: " + " · ".join(cortos)
              if cortos else f"✓ El {bp}% del presupuesto alcanza en todos los materiales.")
    ax.text(0.5, 0.29, estado, ha="center", fontsize=10.5, fontweight="bold",
            color="#922b21" if cortos else "#1e8449", transform=ax.transAxes)

    nota = (f"CÓMO LEERLO:  el PRESUPUESTO surte la BASE + {bp}% de desperdicio = lo SUMINISTRADO\n"
            f"   (ej. Merlot Moret: base 95 + {bp}% ≈ 98 cajas).\n"
            "REQUERIDO REAL = cajas que de verdad se ocupan (despiece con reuso máximo de sobrantes).\n"
            f"% REAL NECESARIO = desperdicio que en realidad se necesita sobre la base (base → requerido).\n"
            f"   Si es mayor al {bp}% presupuestado, hay que pedir ese % (ej. Merlot Moret ≈ 5%, no {bp}%).\n"
            "FALTAN = cajas que hay que reponer (rojo) para que alcance.")
    ax.text(0.02, 0.225, nota, fontsize=8.5, color="#444", transform=ax.transAxes, va="top",
            bbox=dict(boxstyle="round", facecolor="#fef9e7", edgecolor="#b7950b"))
    fig.text(0.5, 0.03, f"{PIE}        Generadores — % de desperdicio real — {modelo}        {FECHA}",
             ha="center", fontsize=8, color="#555")
    pdf.savefig(fig); plt.close(fig)


def comparativo(salida="Viñas Norte - Generadores.pdf"):
    with PdfPages(salida) as pdf:
        for m in ("Cabernet", "Merlot", "Chardonnay"):
            pagina_comparativo(pdf, m)
    print("->", salida)


def generadores_excel(salida="Viñas Norte - Generadores.xlsx"):
    """Mismo comparativo, pero en Excel MODIFICABLE: el Suministrado (cajas) es
    editable y el m², la diferencia en cajas y en m² se recalculan con fórmulas."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.formatting.rule import CellIsRule
    HDR = PatternFill("solid", fgColor="1F4E78"); SUB = PatternFill("solid", fgColor="D6E4F0")
    VERDE = PatternFill("solid", fgColor="D5F5E3"); ROJO = PatternFill("solid", fgColor="F5B7B1")
    WH = Font(color="FFFFFF", bold=True); B = Font(bold=True)
    thin = Side(style="thin", color="BBBBBB"); BORD = Border(thin, thin, thin, thin)
    CEN = Alignment(horizontal="center")
    CAJA = {"Moret": G.MORET_CAJA, "Royal Walnut": G.ROYAL_CAJA, "Urbania": G.URB_CAJA}
    PKEY = {"Moret": "Moret", "Royal Walnut": "Royal", "Urbania": "Urbania"}
    ETQ = [("PISO Moret Arena", "Moret"), ("PISO Royal Walnut", "Royal Walnut"),
           ("Urbania White", "Urbania")]
    cols = ["Material", "Neto (m²)", "Sobrante reusable (m²)", "Merma real (m²)",
            "Requerido (cajas)", "Requerido (m²)", "Suministrado (cajas)",
            "Suministrado (m²)", "Diferencia (cajas)", "Diferencia (m²)"]

    wb = openpyxl.Workbook(); wb.remove(wb.active)
    for modelo in ("Cabernet", "Merlot", "Chardonnay"):
        R = real_datos(modelo); P = PRESUP[modelo]
        ws = wb.create_sheet(modelo)
        ws.merge_cells("A1:J1")
        ws["A1"] = f"GENERADORES (con desperdicio real) vs PRESUPUESTO — {modelo.upper()}"
        ws["A1"].font = Font(bold=True, size=13, color="FFFFFF"); ws["A1"].fill = HDR
        ws["A1"].alignment = CEN
        for c, h in enumerate(cols, 1):
            cell = ws.cell(3, c, h); cell.font = WH; cell.fill = HDR
            cell.alignment = Alignment(horizontal="center", wrap_text=True); cell.border = BORD
        r = 4
        for (etq, key) in ETQ:
            d = R[key]; cm = CAJA[key]; sumin = P[PKEY[key]]
            ws.cell(r, 1, etq).font = B
            ws.cell(r, 2, round(d["neto"], 2))
            ws.cell(r, 3, round(d.get("reusable", 0), 2))
            ws.cell(r, 4, round(d.get("merma", 0), 2))
            ws.cell(r, 5, d["cajas"])
            ws.cell(r, 6, round(d["cajas"] * cm, 2))            # requerido m²
            ws.cell(r, 7, sumin)                                # suministrado cajas (editable)
            ws.cell(r, 8, f"=G{r}*{cm}")                        # suministrado m²
            ws.cell(r, 9, f"=G{r}-E{r}")                        # diferencia cajas
            ws.cell(r, 10, f"=H{r}-F{r}")                       # diferencia m²
            for c in range(1, 11):
                ws.cell(r, c).border = BORD; ws.cell(r, c).alignment = CEN
            ws.cell(r, 1).alignment = Alignment(horizontal="left")
            r += 1
        # Malla (en piezas)
        ws.cell(r, 1, "Malla Lyndhurst (pz)").font = B
        ws.cell(r, 5, R["Malla_pz"]); ws.cell(r, 7, P["Malla_pz"])
        ws.cell(r, 9, f"=G{r}-E{r}")
        for c in range(1, 11):
            ws.cell(r, c).border = BORD; ws.cell(r, c).alignment = CEN
        ws.cell(r, 1).alignment = Alignment(horizontal="left")
        last = r
        # colorear diferencias (cajas y m²): verde >=0, rojo <0
        for col in ("I", "J"):
            rng = f"{col}4:{col}{last}"
            ws.conditional_formatting.add(rng, CellIsRule(operator="greaterThanOrEqual",
                                          formula=["0"], fill=VERDE))
            ws.conditional_formatting.add(rng, CellIsRule(operator="lessThan",
                                          formula=["0"], fill=ROJO))
        ws.cell(last + 2, 1, "Suministrado (cajas) es editable; m², diferencia en cajas y en m² se recalculan solas.").font = Font(italic=True, color="555555")
        ws.cell(last + 3, 1, f"{PIE}    ·    {FECHA}").font = Font(italic=True, color="888888")
        widths = [22, 10, 14, 12, 12, 12, 14, 13, 12, 12]
        for c, w in enumerate(widths, 1):
            ws.column_dimensions[chr(64 + c)].width = w
        ws.row_dimensions[3].height = 30
    wb.save(salida)
    print("->", salida)


def main(modelo):
    out_u = f"Viñas Norte - {modelo} Urbania.pdf"
    with PdfPages(out_u) as pdf:
        pagina_urbania(pdf, modelo)
    print("->", out_u)


if __name__ == "__main__":
    import sys
    for mm in (sys.argv[1:] or ["Cabernet", "Merlot", "Chardonnay"]):
        main(mm)
