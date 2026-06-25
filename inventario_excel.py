#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inventario_excel.py
===================
Genera Inventario_Acabados.xlsx con una hoja por prototipo. Cada hoja tiene:
  1) EXISTENCIAS: material de presupuesto (en cajas/piezas) vs requerido del
     generador y la diferencia.
  2) BITÁCORA DE SALIDAS: registro de cuánto piso/material sale cada día.
  3) EXTRAS: renglones para boquillas, impermeabilizante, etc.
Todo en español.
"""
import math
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import generadores as G

PRESUP = {
 'Cabernet':  {'Moret':117, 'Royal':41, 'Urbania':8, 'Malla_pz':28},
 'Merlot':    {'Moret':98,  'Royal':37, 'Urbania':8, 'Malla_pz':17},
 'Chardonnay':{'Moret':127, 'Royal':32, 'Urbania':8, 'Malla_pz':28},
}
EXTRAS = ["Boquilla Cantera", "Boquilla Chocolate", "Boquilla Blanco",
          "Boquilla Plata", "Impermeabilizante para charola", "", ""]

# Lotes suministrados: (lote, manzana, modelo). Agregar aquí cada lote nuevo.
LOTES = [
    (34, 14, "Cabernet"),
    (9,   7, "Merlot"),
    (10,  7, "Merlot"),
]

HDR = PatternFill("solid", fgColor="1F4E78")
SUB = PatternFill("solid", fgColor="D6E4F0")
EXT = PatternFill("solid", fgColor="FCF3CF")
LOG = PatternFill("solid", fgColor="E8F5E9")
WH = Font(color="FFFFFF", bold=True)
B = Font(bold=True)
thin = Side(style="thin", color="BBBBBB")
BORD = Border(left=thin, right=thin, top=thin, bottom=thin)
CEN = Alignment(horizontal="center")


def req_cajas(modelo):
    g = G.GEN[modelo]; am, ar = G.area_piso(modelo)
    zpm, zm2m, zcm = G.zoclo(g['zoclo_m'], G.MORET_CAJA)
    bruto = sum(G.REG_PERIM * h for _, h in g['regaderas'])
    wm2 = max(0.0, bruto - len(g['regaderas']) * G.VENTANA_M2)
    moret_cajas = math.ceil((am*1.1 + zm2m + wm2*1.1) / G.MORET_CAJA)
    zpr, zm2r, zcr = G.zoclo(g['zoclo_r'], G.ROYAL_CAJA)
    royal_cajas = math.ceil((ar*1.07 + zm2r) / G.ROYAL_CAJA)
    urb_cajas = math.ceil(g['urbania_m2']*1.1 / G.URB_CAJA)
    malla_pz = math.ceil(len(g['regaderas'])*G.MALLA_M2_CHAROLA / G.MALLA_M2)
    return moret_cajas, royal_cajas, urb_cajas, malla_pz


def hoja(ws, modelo):
    p = PRESUP[modelo]; rm, rr, ru, rmalla = req_cajas(modelo)
    ws.merge_cells("A1:F1")
    ws["A1"] = f"INVENTARIO Y BITÁCORA DE ACABADOS — {modelo.upper()}"
    ws["A1"].font = Font(bold=True, size=14, color="FFFFFF"); ws["A1"].fill = HDR
    ws["A1"].alignment = CEN
    r = 3
    ws.cell(r, 1, "1) EXISTENCIAS (presupuesto)").font = B
    r += 1
    for c, h in enumerate(["Material", "Presentación", "En existencia", "Requerido (generador)", "Diferencia", "Observaciones"], 1):
        cell = ws.cell(r, c, h); cell.font = WH; cell.fill = HDR; cell.alignment = CEN; cell.border = BORD
    r += 1
    for nombre, pres, tiene, req in [
        ("Piso Moret Arena", "caja 1.42 m² (2 pz)", p['Moret'], rm),
        ("Piso Royal Walnut", "caja 1.20 m² (5 pz)", p['Royal'], rr),
        ("Urbania White", "caja 1.36 m² (10 pz)", p['Urbania'], ru),
        ("Malla Lyndhurst", "pieza 0.30×0.60 m", p['Malla_pz'], rmalla)]:
        ws.cell(r, 1, nombre).font = B
        ws.cell(r, 2, pres)
        ws.cell(r, 3, tiene).alignment = CEN
        ws.cell(r, 4, req).alignment = CEN
        dif = tiene - req
        dc = ws.cell(r, 5, dif); dc.alignment = CEN
        dc.font = Font(bold=True, color=("1E8449" if dif >= 0 else "C0392B"))
        ws.cell(r, 6, "Suficiente" if dif >= 0 else "Falta")
        for c in range(1, 7):
            ws.cell(r, c).border = BORD
        r += 1
    # 2) Bitácora
    r += 1
    ws.cell(r, 1, "2) BITÁCORA DE SALIDAS (registrar cada día cuánto piso sale)").font = B
    r += 1
    for c, h in enumerate(["Fecha", "Material", "Cantidad que salió", "Frente / área", "Recibió", "Saldo en obra"], 1):
        cell = ws.cell(r, c, h); cell.font = WH; cell.fill = HDR; cell.alignment = CEN; cell.border = BORD
    r += 1
    for _ in range(22):
        for c in range(1, 7):
            cell = ws.cell(r, c); cell.border = BORD
            if r % 2 == 0:
                cell.fill = LOG
        r += 1
    # 3) Extras
    r += 1
    ws.cell(r, 1, "3) EXTRAS / COMPLEMENTOS").font = B
    r += 1
    for c, h in enumerate(["Material", "Presentación / color", "Cantidad", "Observaciones"], 1):
        cell = ws.cell(r, c, h); cell.font = B; cell.fill = SUB; cell.border = BORD
    r += 1
    for ex in EXTRAS:
        ws.cell(r, 1, ex)
        for c in range(1, 7):
            ws.cell(r, c).border = BORD; ws.cell(r, c).fill = EXT
        r += 1
    for c, w in enumerate([24, 24, 18, 18, 16, 18], 1):
        ws.column_dimensions[chr(64 + c)].width = w


def hoja_lotes(ws):
    """Control por LOTE: cada lote (lote/manzana) se liga a su modelo y se compara
    lo requerido (generador del modelo) contra lo suministrado, por material."""
    ws.merge_cells("A1:I1")
    ws["A1"] = "CONTROL DE LOTES — SUMINISTRADO vs REQUERIDO"
    ws["A1"].font = Font(bold=True, size=14, color="FFFFFF"); ws["A1"].fill = HDR
    ws["A1"].alignment = CEN
    ws.merge_cells("A2:I2")
    ws["A2"] = ("Cada lote se liga a su modelo. 'Requerido' sale del generador del modelo; "
                "'Suministrado' arranca con el presupuesto y se puede editar conforme llega material.")
    ws["A2"].alignment = Alignment(horizontal="center"); ws["A2"].font = Font(italic=True, color="555555")

    r = 4
    hdrs = ["Lote", "Manzana", "Modelo", "Material", "Presentación",
            "Requerido (cajas)", "Suministrado (cajas)", "Diferencia", "Observaciones"]
    for c, h in enumerate(hdrs, 1):
        cell = ws.cell(r, c, h); cell.font = WH; cell.fill = HDR
        cell.alignment = CEN; cell.border = BORD
    r += 1

    MAT = [("Piso Moret Arena", "caja 1.42 m² (2 pz)", "Moret"),
           ("Piso Royal Walnut", "caja 1.20 m² (5 pz)", "Royal"),
           ("Urbania White", "caja 1.36 m² (10 pz)", "Urbania"),
           ("Malla Lyndhurst", "pieza 0.30×0.60 m", "Malla_pz")]

    for (lote, mza, modelo) in LOTES:
        rm, rr, ru, rmalla = req_cajas(modelo)
        req = {"Moret": rm, "Royal": rr, "Urbania": ru, "Malla_pz": rmalla}
        sup = PRESUP[modelo]
        fila0 = r
        for (nombre, pres, key) in MAT:
            ws.cell(r, 4, nombre).font = B
            ws.cell(r, 5, pres)
            rq = req[key]; sm = sup[key]; dif = sm - rq
            ws.cell(r, 6, rq).alignment = CEN
            ws.cell(r, 7, sm).alignment = CEN
            dc = ws.cell(r, 8, dif); dc.alignment = CEN
            dc.font = Font(bold=True, color=("1E8449" if dif >= 0 else "C0392B"))
            ws.cell(r, 9, "Suficiente" if dif >= 0 else "Falta")
            for c in range(1, 10):
                ws.cell(r, c).border = BORD
            r += 1
        # celdas agrupadas del lote (lote/manzana/modelo) sobre las 4 filas
        for col, val in ((1, f"L{lote}"), (2, f"M{mza}"), (3, modelo)):
            ws.merge_cells(start_row=fila0, start_column=col, end_row=r - 1, end_column=col)
            cell = ws.cell(fila0, col, val)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.font = B; cell.fill = SUB
        r += 1   # renglón en blanco entre lotes

    for c, w in enumerate([8, 9, 13, 20, 20, 16, 18, 12, 22], 1):
        ws.column_dimensions[chr(64 + c)].width = w


def main():
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    hoja_lotes(wb.create_sheet("Control de Lotes"))
    for m in ['Cabernet', 'Merlot', 'Chardonnay']:
        hoja(wb.create_sheet(m), m)
    out = "Inventario_Acabados_y_Lotes.xlsx"
    wb.save(out)
    print("->", out)


if __name__ == "__main__":
    main()
