#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
demostracion_faltante.py
========================

Toma el Excel de "Números Generadores" (Moret Arena y Royal Walnut para los
modelos Chardonnay, Cabernet y Merlot) y consolida la verificación de material
para DEMOSTRAR que el material suministrado NO alcanza.

Usa la columna realista "CON desperdicio" (factor 10% Moret / 7% Royal, tal
como está en el propio generador) y, para Royal, el zoclo REAL como se instaló.
Suma piso + escalera + zoclo y compara contra lo suministrado.

Salidas:
    demostracion_faltante.pdf   -> documento para presentar (tablas + conclusión)
    demostracion_faltante.csv   -> el mismo comparativo para Excel

Uso:
    python3 demostracion_faltante.py  Numeros_Generadores....xlsx
"""

import sys
import csv
import argparse
import unicodedata

import openpyxl

# m² y piezas por caja (del propio generador)
CAJA = {
    "Moret":        {"m2": 1.423, "pzas": 2},
    "Royal Walnut": {"m2": 1.200, "pzas": 5},
}
MODELOS = ["Chardonnay", "Cabernet", "Merlot"]


def norm(s):
    if s is None:
        return ""
    s = str(s)
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return s.strip().lower()


def material_de(hoja):
    n = norm(hoja)
    return "Moret" if "moret" in n else ("Royal Walnut" if "royal" in n else None)


def modelo_de(hoja):
    n = norm(hoja)
    for m in MODELOS:
        if norm(m) in n:
            return m
    return "?"


def numeros(row):
    """Valores numéricos de una fila (omite la etiqueta y los None)."""
    return [c for c in row[1:] if isinstance(c, (int, float))]


def parse_hoja(ws):
    """Extrae suministrado y requerido (columna realista 'con desperdicio')."""
    d = {"sum_cajas": None, "sum_m2": None, "sum_pzas": None,
         "req_piso": 0, "req_escalera": 0, "req_zoclo": 0,
         "req_total": None, "diferencia": None, "resultado": None}

    # índice de la columna "con desperdicio realista" entre los valores numéricos:
    # en hojas de 2 columnas es la 2a (index 1); en Royal Cabernet (4 cols:
    # REAL/SIMUL) usamos REAL con desperdicio, que también es index 1.
    COL = 1

    for row in ws.iter_rows(values_only=True):
        if not any(c is not None for c in row):
            continue
        lab = norm(row[0])
        nums = numeros(row)

        if "suministrad" in lab and d["sum_cajas"] is None and nums:
            # fila tipo: [.., cajas, m2/caja, m2, pzas]
            d["sum_cajas"] = row[1]
            d["sum_m2"] = next((c for c in row[2:] if isinstance(c, (int, float)) and c > 5), None)
            d["sum_pzas"] = next((c for c in reversed(row) if isinstance(c, int) and c > 20), None)
        elif "cajas suministradas" in lab and nums:
            d["sum_cajas"] = nums[min(COL, len(nums)-1)]
        elif "m2 suministrados" in lab or "m² suministrados" in lab:
            if nums:
                d["sum_m2"] = nums[0]
        elif ("req" in lab and "piso" in lab) or ("area piso" in lab):
            if nums:
                d["req_piso"] = nums[min(COL, len(nums)-1)]
        elif "escalera" in lab and "req" in lab:
            if nums:
                d["req_escalera"] = nums[min(COL, len(nums)-1)]
        elif "zoclo" in lab and ("req" in lab or "cajas" in lab):
            if nums:
                d["req_zoclo"] = nums[min(COL, len(nums)-1)]
        elif lab.startswith("total") and ("requerid" in lab):
            if nums:
                d["req_total"] = nums[min(COL, len(nums)-1)]
        elif "diferencia" in lab:
            if nums:
                d["diferencia"] = nums[min(COL, len(nums)-1)]
        elif lab.startswith("resultado"):
            vals = [c for c in row[1:] if isinstance(c, str)]
            if vals:
                d["resultado"] = vals[min(COL, len(vals)-1)]

    # Si no vino el total explícito, lo armamos
    if d["req_total"] is None:
        d["req_total"] = (d["req_piso"] or 0) + (d["req_escalera"] or 0) + (d["req_zoclo"] or 0)
    if d["diferencia"] is None and d["sum_cajas"] is not None:
        d["diferencia"] = d["sum_cajas"] - d["req_total"]
    return d


def parse_libro(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    datos = {"Moret": {}, "Royal Walnut": {}}
    for ws in wb.worksheets:
        mat = material_de(ws.title)
        mod = modelo_de(ws.title)
        if mat and mod != "?":
            datos[mat][mod] = parse_hoja(ws)
    return datos


# --------------------------------------------------------------------------
#  Reporte
# --------------------------------------------------------------------------
def construir_tablas(datos):
    """Devuelve, por material, las filas y los totales de faltante."""
    out = {}
    for mat in ("Moret", "Royal Walnut"):
        filas = []
        tot_sum = tot_req = 0
        for mod in MODELOS:
            d = datos[mat].get(mod)
            if not d:
                continue
            sumc = d["sum_cajas"] or 0
            req = d["req_total"] or 0
            dif = (d["diferencia"] if d["diferencia"] is not None else sumc - req)
            filas.append({
                "modelo": mod, "sum": sumc, "piso": d["req_piso"] or 0,
                "escalera": d["req_escalera"] or 0, "zoclo": d["req_zoclo"] or 0,
                "req": req, "dif": dif,
                "resultado": "FALTA" if dif < 0 else "SUFICIENTE",
            })
            tot_sum += sumc
            tot_req += req
        out[mat] = {"filas": filas, "tot_sum": tot_sum, "tot_req": tot_req,
                    "faltante_cajas": max(0, tot_req - tot_sum),
                    "neto": tot_sum - tot_req}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--pdf", default="demostracion_faltante.pdf")
    ap.add_argument("--csv", default="demostracion_faltante.csv")
    args = ap.parse_args()

    datos = parse_libro(args.xlsx)
    tablas = construir_tablas(datos)

    # ---- CSV ----
    with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["material", "modelo", "cajas_suministradas", "req_piso",
                    "req_escalera", "req_zoclo", "req_total", "diferencia", "resultado"])
        for mat, t in tablas.items():
            for r in t["filas"]:
                w.writerow([mat, r["modelo"], r["sum"], r["piso"], r["escalera"],
                            r["zoclo"], r["req"], r["dif"], r["resultado"]])
            w.writerow([mat, "TOTAL", t["tot_sum"], "", "", "", t["tot_req"],
                        t["neto"], "FALTA" if t["neto"] < 0 else "SUFICIENTE"])

    # ---- Consola ----
    print("DEMOSTRACIÓN DE FALTANTE DE MATERIAL (con desperdicio real)\n")
    for mat, t in tablas.items():
        print(f"== {mat} ==")
        for r in t["filas"]:
            print(f"  {r['modelo']:11} sumin {r['sum']:>4}  req {r['req']:>4} "
                  f"(piso {r['piso']}, esc {r['escalera']}, zoclo {r['zoclo']})  "
                  f"dif {r['dif']:+}  {r['resultado']}")
        falt = t["faltante_cajas"]
        cj = CAJA[mat]
        print(f"  TOTAL: suministrado {t['tot_sum']}  requerido {t['tot_req']}  "
              f"NETO {t['neto']:+} cajas")
        if falt:
            print(f"  >> FALTAN {falt} cajas de {mat} = "
                  f"{falt*cj['m2']:.1f} m² = {falt*cj['pzas']} piezas\n")
        else:
            print()

    hacer_pdf(tablas, args.pdf)
    print(f"PDF: {args.pdf}")
    print(f"CSV: {args.csv}")


def hacer_pdf(tablas, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
    except Exception as e:
        print(f"(PDF omitido: {e})")
        return

    with PdfPages(path) as pdf:
        fig = plt.figure(figsize=(11.7, 8.3))
        fig.suptitle("DEMOSTRACIÓN DE FALTANTE DE MATERIAL — Pisos",
                     fontsize=16, y=0.965, weight="bold")
        fig.text(0.5, 0.925,
                 "Verificación con el factor de desperdicio del propio generador "
                 "(10% Moret · 7% Royal Walnut) y zoclo real como se instaló.",
                 ha="center", fontsize=9, style="italic")

        y_pos = 0.86
        for mat in ("Moret", "Royal Walnut"):
            t = tablas[mat]
            cj = CAJA[mat]
            encab = ["Modelo", "Suministrado\n(cajas)", "Piso", "Escalera",
                     "Zoclo", "Requerido\n(cajas)", "Diferencia", "Resultado"]
            filas = []
            for r in t["filas"]:
                filas.append([r["modelo"], r["sum"], r["piso"], r["escalera"],
                              r["zoclo"], r["req"], f'{r["dif"]:+}',
                              "FALTA" if r["dif"] < 0 else "OK"])
            filas.append(["TOTAL", t["tot_sum"], "", "", "", t["tot_req"],
                          f'{t["neto"]:+}', "FALTA" if t["neto"] < 0 else "OK"])

            ax = fig.add_axes([0.06, y_pos - 0.205, 0.88, 0.18])
            ax.axis("off")
            ax.set_title(f"{mat}   (1 caja = {cj['m2']:g} m² = {cj['pzas']} pzas)",
                         fontsize=12, loc="left", weight="bold")
            tabla = ax.table(cellText=filas, colLabels=encab, loc="center", cellLoc="center")
            tabla.auto_set_font_size(False)
            tabla.set_fontsize(9)
            tabla.scale(1, 1.9)
            ncol = len(encab)
            for (rr, cc), cell in tabla.get_celld().items():
                if rr == 0:
                    cell.set_facecolor("#34495e"); cell.set_text_props(color="white", weight="bold")
                elif rr == len(filas):
                    cell.set_facecolor("#d5dbdb"); cell.set_text_props(weight="bold")
                # resaltar diferencia/resultado en rojo si falta
                if cc in (6, 7) and rr > 0:
                    val = filas[rr-1][6]
                    if str(val).startswith("-"):
                        cell.set_facecolor("#f5b7b1"); cell.set_text_props(weight="bold")
            y_pos -= 0.30

        # Conclusión
        lineas = ["CONCLUSIÓN:"]
        for mat in ("Moret", "Royal Walnut"):
            t = tablas[mat]; cj = CAJA[mat]
            if t["neto"] < 0:
                falt = -t["neto"]
                lineas.append(f"  • {mat}: el material NO alcanza. Faltan {falt} cajas "
                              f"= {falt*cj['m2']:.1f} m² = {falt*cj['pzas']} piezas.")
            else:
                lineas.append(f"  • {mat}: suministro ajustado, sobran {t['neto']} cajas "
                              f"(sin margen para roturas adicionales).")
        falt_m = max(0, -tablas["Moret"]["neto"])
        falt_r = max(0, -tablas["Royal Walnut"]["neto"])
        lineas.append("")
        lineas.append(f"  TOTAL FALTANTE:  Moret {falt_m} cajas  +  Royal Walnut {falt_r} cajas.")
        lineas.append("  Los números del suministro no cubren piso + escalera + zoclo con el")
        lineas.append("  desperdicio real por cortes (el plano ejecutado tiene >50% de piezas recortadas).")
        fig.text(0.06, 0.20, "\n".join(lineas), fontsize=10.5, va="top", family="monospace",
                 bbox=dict(boxstyle="round", facecolor="#fdebd0", edgecolor="#e67e22"))

        pdf.savefig(fig)
        plt.close(fig)


if __name__ == "__main__":
    main()
