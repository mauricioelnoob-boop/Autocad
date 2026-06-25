#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py
========
UN SOLO COMANDO para reconstruir TODO el paquete "Viñas Norte" de forma
reproducible:

    1. (DWG → JSON) regenera el export de LibreDWG si falta /tmp/<modelo>.json.
    2. VALIDA la geometría (validar.py) y ABORTA si algo falla — no se genera
       nada sobre un despiece inválido.
    3. GENERA todos los entregables (6 despieces, 3 Urbania, comparativo PDF,
       generadores Excel, inventario Excel, 3 DXF).
    4. EMPAQUETA el ZIP final con su manifiesto.

Uso:  python3 build.py            (los 3 modelos, paquete completo)
      python3 build.py --no-zip   (genera pero no empaqueta)

Requisitos: pip install -r requirements.txt  +  LibreDWG en /tmp (ver README).
"""
import os
import sys
import subprocess
import zipfile

MODELOS_LISTA = ["Cabernet", "Merlot", "Chardonnay"]
DWGREAD = os.environ.get("DWGREAD", "/tmp/libredwg-0.13.3/programs/dwgread")
PKG = "Vinas Norte - Despiece de Pisos (Entrega Final).zip"

# Estructura del ZIP (mismas rutas que se entregan). PDFs/Excel con "Viñas";
# CAD con "Vinas" (sin ñ) para que AutoCAD los abra.
CONTENIDO = {
    "01 Despieces de Piso": [
        "Viñas Norte - Cabernet Moret.pdf", "Viñas Norte - Cabernet Royal.pdf",
        "Viñas Norte - Merlot Moret.pdf", "Viñas Norte - Merlot Royal.pdf",
        "Viñas Norte - Chardonnay Moret.pdf", "Viñas Norte - Chardonnay Royal.pdf",
        "Viñas Norte - Cabernet Urbania.pdf", "Viñas Norte - Merlot Urbania.pdf",
        "Viñas Norte - Chardonnay Urbania.pdf",
    ],
    "02 Generadores e Inventario": [
        "Viñas Norte - Generadores.pdf", "Viñas Norte - Generadores.xlsx",
        "Viñas Norte - Inventario.xlsx",
    ],
    "03 Editables CAD (DXF)": [
        "Vinas Norte - Cabernet.dxf", "Vinas Norte - Merlot.dxf",
        "Vinas Norte - Chardonnay.dxf",
    ],
}


def paso(msg):
    print(f"\n=== {msg} ===", flush=True)


def regen_json():
    paso("1) DWG → JSON (si falta)")
    from modelos import MODELOS
    for m in MODELOS_LISTA:
        cfg = MODELOS[m]; jp = cfg["json"]; dwg = cfg["dwg"]
        if os.path.exists(jp):
            print(f"[{m}] {jp} ya existe.")
            continue
        if os.path.exists(DWGREAD) and os.path.exists(dwg):
            print(f"[{m}] generando {jp} desde {dwg} ...")
            subprocess.run([DWGREAD, "-O", "JSON", "-o", jp, dwg],
                           check=True, stderr=subprocess.DEVNULL)
        else:
            print(f"[{m}] ⚠ falta {jp} y no hay dwgread/{dwg}; se usa "
                  f"piezas_{m.lower()}.json ya extraído (zoclo/generadores podrían fallar).")


def validar_o_abortar():
    paso("2) VALIDACIÓN (aborta si falla)")
    import validar
    fallo = False
    for m in MODELOS_LISTA:
        problemas, avisos, metr = validar.validar(m)
        if problemas:
            fallo = True
            print(f"✗ {m}: {len(problemas)} problema(s)  {metr}")
            for pr in problemas:
                print(f"    ✗ {pr}")
        else:
            print(f"✓ {m}: OK  {metr}")
        for av in avisos:
            print(f"    ⚠ {av}")
    if fallo:
        sys.exit("\nBUILD ABORTADO: la validación falló. Corrige antes de generar.")
    print("Validación OK.")


def generar():
    import pdf_material, pdf_extra, exportar_dwg, inventario_excel
    for m in MODELOS_LISTA:
        paso(f"3) {m}: despiece (Moret + Royal)")
        pdf_material.main(m)
        paso(f"3) {m}: Urbania")
        pdf_extra.main(m)
        paso(f"3) {m}: DXF editable")
        exportar_dwg.exportar(m)
    paso("3) Comparativo PDF + Generadores Excel")
    pdf_extra.comparativo()
    pdf_extra.generadores_excel()
    paso("3) Inventario de control")
    inventario_excel.main()


def zipear():
    paso("4) EMPAQUETADO + manifiesto")
    faltan = [f for files in CONTENIDO.values() for f in files if not os.path.exists(f)]
    if faltan:
        sys.exit("No se puede empaquetar, faltan archivos:\n  " + "\n  ".join(faltan))
    with zipfile.ZipFile(PKG, "w", zipfile.ZIP_DEFLATED) as z:
        for carpeta, files in CONTENIDO.items():
            for f in files:
                z.write(f, arcname=f"{carpeta}/{f}")
    print(f"-> {PKG}  ({round(os.path.getsize(PKG)/1e6, 2)} MB)")
    print("\nMANIFIESTO:")
    for carpeta, files in CONTENIDO.items():
        print(f"  {carpeta}/")
        for f in files:
            print(f"    - {f}")


def main():
    no_zip = "--no-zip" in sys.argv
    regen_json()
    validar_o_abortar()
    generar()
    if not no_zip:
        zipear()
    print("\nBUILD COMPLETO.")


if __name__ == "__main__":
    main()
