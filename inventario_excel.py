#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inventario_excel.py
===================
Genera Inventario_Acabados.xlsx con una hoja por prototipo (Cabernet, Merlot,
Chardonnay). Lista el material de PRESUPUESTO (lo que ya se tiene) en cajas/piezas,
contra el REQUERIDO del take-off, y deja renglones para EXTRAS (boquillas,
impermeabilizante, pegas) para llenar a mano.
"""
import math
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import generadores as G

# --- Presupuesto (lo que el cliente YA tiene). m2/caja: Moret 1.42, Royal 1.20,
#     Urbania 1.36, Malla pieza 0.30x0.60=0.18 m2. ---
PRESUP = {
 'Cabernet':  {'Moret':117, 'Royal':41, 'Urbania':8, 'Malla_pz':28},
 'Merlot':    {'Moret':98,  'Royal':37, 'Urbania':8, 'Malla_pz':17},
 'Chardonnay':{'Moret':127, 'Royal':32, 'Urbania':8, 'Malla_pz':28},  # de m2: 180.75/1.42, 38.27/1.2, 10.12/1.36, 5/0.18
}
EXTRAS = ["Boquilla Cantera", "Boquilla Chocolate", "Boquilla Blanco",
          "Boquilla Plata", "Impermeabilizante para charola",
          "Pegavitro 20 kg", "Pegaporcelánico 20 kg", "", ""]

HDR = PatternFill("solid", fgColor="1F4E78")
SUB = PatternFill("solid", fgColor="D6E4F0")
EXT = PatternFill("solid", fgColor="FCF3CF")
WH = Font(color="FFFFFF", bold=True)
B = Font(bold=True)
thin = Side(style="thin", color="BBBBBB")
BORD = Border(left=thin, right=thin, top=thin, bottom=thin)
CEN = Alignment(horizontal="center")


def req_cajas(modelo):
    """Cajas requeridas por el take-off, sumando piso+zoclo+muro regadera por material."""
    g = G.GEN[modelo]; am, ar = G.area_piso(modelo)
    # Moret = piso + zoclo Moret + muro regadera
    zpm, zm2m, zcm = G.zoclo(g['zoclo_m'], G.MORET_CAJA)
    wm2 = sum(G.REG_PERIM * h for _, h in g['regaderas'])
    moret_m2 = am*1.1 + zm2m + wm2*1.1
    moret_cajas = math.ceil(moret_m2 / G.MORET_CAJA)
    # Royal = piso + zoclo Royal
    zpr, zm2r, zcr = G.zoclo(g['zoclo_r'], G.ROYAL_CAJA)
    royal_cajas = math.ceil((ar*1.07 + zm2r) / G.ROYAL_CAJA)
    urb_cajas = math.ceil(g['urbania_m2']*1.1 / G.URB_CAJA)
    malla_pz = math.ceil(len(g['regaderas'])*G.MALLA_M2_CHAROLA / G.MALLA_M2)
    return moret_cajas, royal_cajas, urb_cajas, malla_pz


def hoja(ws, modelo):
    p = PRESUP[modelo]; rm, rr, ru, rmalla = req_cajas(modelo)
    ws.title = modelo
    ws.merge_cells("A1:F1")
    ws["A1"] = f"INVENTARIO DE ACABADOS — {modelo.upper()}"
    ws["A1"].font = Font(bold=True, size=14, color="FFFFFF"); ws["A1"].fill = HDR
    ws["A1"].alignment = CEN
    hdr = ["Material", "Presentación", "Presupuesto (se tiene)", "Requerido (take-off)", "Diferencia", "Observaciones"]
    for c, h in enumerate(hdr, 1):
        cell = ws.cell(2, c, h); cell.font = WH; cell.fill = HDR; cell.alignment = CEN; cell.border = BORD
    filas = [
        ("Moret Arena", "caja 1.42 m² (2 pz)", p['Moret'], rm),
        ("Royal Walnut", "caja 1.20 m² (5 pz)", p['Royal'], rr),
        ("Urbania White", "caja 1.36 m² (10 pz)", p['Urbania'], ru),
        ("Malla Lyndhurst", "pieza 0.30×0.60 m", p['Malla_pz'], rmalla),
    ]
    r = 3
    for nombre, pres, tiene, req in filas:
        ws.cell(r, 1, nombre).font = B
        ws.cell(r, 2, pres)
        ws.cell(r, 3, tiene).alignment = CEN
        ws.cell(r, 4, req).alignment = CEN
        dif = tiene - req
        dc = ws.cell(r, 5, dif); dc.alignment = CEN
        dc.font = Font(bold=True, color=("1E8449" if dif >= 0 else "C0392B"))
        ws.cell(r, 6, "✔ suficiente" if dif >= 0 else "⚠ falta")
        for c in range(1, 7):
            ws.cell(r, c).border = BORD
            if r % 2 == 0:
                ws.cell(r, c).fill = SUB
        r += 1
    # extras
    r += 1
    ws.cell(r, 1, "EXTRAS / COMPLEMENTOS").font = B
    ws.cell(r, 1).fill = EXT
    for c in range(2, 7):
        ws.cell(r, c).fill = EXT
    r += 1
    for c, h in enumerate(["Material", "Presentación", "Cantidad", "", "", "Observaciones"], 1):
        cell = ws.cell(r, c, h); cell.font = B; cell.fill = SUB; cell.border = BORD
    r += 1
    for ex in EXTRAS:
        ws.cell(r, 1, ex)
        for c in range(1, 7):
            ws.cell(r, c).border = BORD
            if ex == "":
                pass
        r += 1
    widths = [26, 22, 20, 20, 12, 24]
    for c, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + c)].width = w


def main():
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for m in ['Cabernet', 'Merlot', 'Chardonnay']:
        hoja(wb.create_sheet(m), m)
    out = "Inventario_Acabados.xlsx"
    wb.save(out)
    print("->", out)


if __name__ == "__main__":
    main()
