#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cruce_area_generador.py
=======================

Cruza el ÁREA REAL del despiece (medida pieza por pieza en el plano, ya sin las
charolas de baño) contra el "Área a revestir" del generador (modelo Cabernet),
para afinar el dato de piso.

Salidas: cruce_area.csv  (+ impresión en consola)

Fuente del "área generador": por defecto generadores.area_piso(Cabernet) (la
medición canónica del piso, sin depender de un xlsx). Si se pasa un xlsx con el
formato antiguo (hoja "Cabernet <material>" con fila "Area piso"), se usa ése.

Uso:  python3 cruce_area_generador.py  [Numeros_Generadores_....xlsx]
"""

import sys
import csv
from collections import defaultdict

from optimizador_recortes import PISOS, ajustar
from datos_piezas import cargar_anotado
import generadores as G


def area_real_por_material(piezas):
    ag = defaultdict(float)
    agp = defaultdict(float)   # por planta+material
    for p in piezas:
        ancho, largo = PISOS[p["material"]]
        aw, al = ajustar(p["ancho"], p["largo"], ancho, largo)
        ag[p["material"]] += aw * al
        agp[(p["planta"], p["material"])] += aw * al
    return ag, agp


def area_generador(xlsx):
    import openpyxl, unicodedata
    def norm(s):
        s = "".join(c for c in unicodedata.normalize("NFD", str(s or ""))
                    if unicodedata.category(c) != "Mn")
        return s.strip().lower()
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    out = {}
    for ws in wb.worksheets:
        if "cabernet" not in norm(ws.title):
            continue
        mat = "Moret" if "moret" in norm(ws.title) else "Royal Walnut"
        for row in ws.iter_rows(values_only=True):
            if row and "area piso" in norm(row[0]):
                nums = [c for c in row[1:] if isinstance(c, (int, float))]
                if nums:
                    out[mat] = nums[0]      # m² a revestir
                break
    return out


def main():
    xlsx = sys.argv[1] if len(sys.argv) >= 2 else None

    piezas = cargar_anotado()
    real, real_pl = area_real_por_material(piezas)
    if xlsx:
        gen = area_generador(xlsx)
        if not gen:
            print(f"(no se pudo leer área del xlsx '{xlsx}'; uso generadores.area_piso)")
    else:
        gen = {}
    if not gen:
        am, ar = G.area_piso("Cabernet")          # medición canónica del piso
        gen = {"Moret": am, "Royal Walnut": ar}

    filas = []
    print("CRUCE DE ÁREA — despiece real (plano) vs generador (Cabernet)\n")
    print(f"{'Material':14}{'Real plano':>12}{'Generador':>12}{'Dif':>10}")
    for mat in PISOS:
        r = real.get(mat, 0.0)
        g = gen.get(mat, 0.0)
        dif = r - g
        print(f"{mat:14}{r:>11.2f}m{g:>11.2f}m{dif:>+9.2f}m")
        filas.append([mat, f"{r:.2f}", f"{g:.2f}", f"{dif:+.2f}"])

    print("\nDesglose por planta (área real del despiece):")
    for k in sorted(real_pl):
        print(f"  Planta {k[0]:5} {k[1]:13}: {real_pl[k]:6.2f} m²")

    with open("cruce_area.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["material", "area_real_plano_m2", "area_generador_m2", "diferencia_m2"])
        w.writerows(filas)
        w.writerow([])
        w.writerow(["planta", "material", "area_real_m2"])
        for k in sorted(real_pl):
            w.writerow([k[0], k[1], f"{real_pl[k]:.2f}"])

    print("\nNota: chequeo de auto-consistencia despiece vs generadores.area_piso "
          "(deben coincidir salvo el ajuste de orilla < 1 m²).\nGuardado: cruce_area.csv")


if __name__ == "__main__":
    main()
