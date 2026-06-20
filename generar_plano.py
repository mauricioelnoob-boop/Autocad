#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generar_plano.py
================

Genera un PLANO GENERAL de corte con TODAS las baldosas que se van a recortar,
mostrando dentro de cada una:

  * las piezas que se cortan (con su medida y su ubicación @x,y en el plano),
  * lo que SOBRA reutilizable (verde-amarillo),
  * el DESPERDICIO / merma (rojo, tira demasiado chica para reusar),

más un cuadro de totales (piezas, cajas, m², desperdicio).

Salidas:
    plano_corte.dxf   -> se abre directo en AutoCAD (cada baldosa a escala real)
    plano_corte.pdf   -> el mismo plano como póster para imprimir/ver rápido

Uso:
    python3 generar_plano.py  [piezas_piso.json]  [--kerf 0.003] [--rotar]
"""

import json
import argparse

from optimizador_recortes import generar, CAJAS, PISOS

# Una pieza sobrante es "reutilizable" si su lado menor llega a este tamaño;
# por debajo se considera desperdicio (merma).
MIN_REUSABLE = 0.10      # 10 cm

# Disposición de las baldosas en el plano
COLUMNAS = 12
SEP_X = 0.20             # separación horizontal entre baldosas (m)
SEP_Y = 0.30             # separación vertical entre baldosas (m)
SEP_MATERIAL = 2.0       # espacio entre el bloque de un material y el siguiente


def es_reutilizable(w, l):
    return min(w, l) >= MIN_REUSABLE


# --------------------------------------------------------------------------
#  Recolectar datos
# --------------------------------------------------------------------------
def resumen_material(baldosas, material):
    """Totales de desperdicio/sobrante para un material."""
    ancho, largo = PISOS[material]
    area_reut = area_desp = 0.0
    n_reut = n_desp = 0
    for b in baldosas:
        if b.material != material:
            continue
        for (fx, fy, fw, fl) in b.libres:
            if fw <= 0.005 or fl <= 0.005:
                continue
            a = fw * fl
            if es_reutilizable(fw, fl):
                area_reut += a; n_reut += 1
            else:
                area_desp += a; n_desp += 1
    return {"area_reutilizable": area_reut, "n_reutilizable": n_reut,
            "area_desperdicio": area_desp, "n_desperdicio": n_desp}


# --------------------------------------------------------------------------
#  DXF para AutoCAD
# --------------------------------------------------------------------------
def hacer_dxf(baldosas, materiales, path):
    import ezdxf
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.M           # metros
    msp = doc.modelspace()

    # Capas (color ACI)
    capas = {
        "BALDOSA":       (7,  "borde de la baldosa completa"),
        "PIEZA":         (3,  "pieza que se corta y se usa"),     # verde
        "PIEZA_TXT":     (7,  "etiqueta de la pieza"),
        "SOBRANTE":      (2,  "sobrante reutilizable"),           # amarillo
        "DESPERDICIO":   (1,  "merma, tira muy chica"),           # rojo
        "TITULO":        (5,  "titulos"),
    }
    for nombre, (color, desc) in capas.items():
        ly = doc.layers.add(nombre)
        ly.color = color
        ly.description = desc

    def rect(x, y, w, l, layer):
        msp.add_lwpolyline(
            [(x, y), (x + w, y), (x + w, y + l), (x, y + l)],
            close=True, dxfattribs={"layer": layer})

    def relleno(x, y, w, l, layer, color):
        h = msp.add_hatch(color=color, dxfattribs={"layer": layer})
        h.set_pattern_fill("ANSI31", scale=0.02) if layer == "DESPERDICIO" else h.set_solid_fill(color)
        h.paths.add_polyline_path(
            [(x, y), (x + w, y), (x + w, y + l), (x, y + l)], is_closed=True)

    def texto(s, x, y, h, layer, align="MIDDLE_CENTER"):
        t = msp.add_text(s, dxfattribs={"layer": layer, "height": h})
        t.set_placement((x, y), align=ezdxf.enums.TextEntityAlignment[align])

    y_cursor = 0.0
    for m in materiales:
        material = m["material"]
        ancho, largo = PISOS[material]
        bs = [b for b in baldosas if b.material == material]
        if not bs:
            continue

        cols = COLUMNAS
        cell_w = ancho + SEP_X
        cell_h = largo + SEP_Y
        filas = (len(bs) + cols - 1) // cols
        bloque_alto = filas * cell_h

        # Título del material (arriba del bloque)
        y_top = y_cursor
        rsm = resumen_material(baldosas, material)
        titulo = (f"{material}  |  baldosa {ancho:.3f}x{largo:.3f} m  |  "
                  f"{m['piezas_compra']} pzas = {m['cajas']} cajas = {m['m2_compra']:.2f} m2  |  "
                  f"recortes en {m['baldosas_recorte']} baldosas  |  "
                  f"desperdicio {rsm['area_desperdicio']:.2f} m2")
        texto(titulo, 0, y_top + 0.25, 0.15, "TITULO", "LEFT")

        # Dibujar cada baldosa
        for i, b in enumerate(bs):
            col = i % cols
            row = i // cols
            ox = col * cell_w
            oy = y_top - 0.4 - (row + 1) * cell_h + SEP_Y     # crece hacia abajo

            rect(ox, oy, ancho, largo, "BALDOSA")
            etiqueta_tile = f"{'M' if material=='Moret' else 'RW'}-{i+1:02d}"
            texto(etiqueta_tile, ox + ancho / 2, oy + largo + 0.06, 0.06, "TITULO")

            # Piezas usadas
            for (x, y, w, l, etq, rot) in b.piezas:
                relleno(ox + x, oy + y, w, l, "PIEZA", 3)
                rect(ox + x, oy + y, w, l, "PIEZA")
                # etiqueta: medida + ubicación origen si viene en la etiqueta
                loc = etq.split("@")[-1] if "@" in etq else ""
                lab = f"{w:.2f}x{l:.2f}"
                if loc:
                    lab += f"\n@{loc}"
                texto(f"{w:.2f}x{l:.2f}", ox + x + w / 2, oy + y + l / 2,
                      min(0.05, w / 4), "PIEZA_TXT")

            # Sobrantes / desperdicio
            for (fx, fy, fw, fl) in b.libres:
                if fw <= 0.005 or fl <= 0.005:
                    continue
                if es_reutilizable(fw, fl):
                    relleno(ox + fx, oy + fy, fw, fl, "SOBRANTE", 2)
                    rect(ox + fx, oy + fy, fw, fl, "SOBRANTE")
                    texto(f"sobra\n{fw:.2f}x{fl:.2f}", ox + fx + fw / 2,
                          oy + fy + fl / 2, min(0.04, fw / 5), "PIEZA_TXT")
                else:
                    relleno(ox + fx, oy + fy, fw, fl, "DESPERDICIO", 1)
                    rect(ox + fx, oy + fy, fw, fl, "DESPERDICIO")

        y_cursor = y_top - 0.4 - bloque_alto - SEP_MATERIAL

    # Cuadro de totales + leyenda
    tot_pzas = sum(m["piezas_compra"] for m in materiales)
    tot_cajas = sum(m["cajas"] or 0 for m in materiales)
    tot_m2 = sum(m["m2_compra"] or 0 for m in materiales)
    tot_desp = sum(resumen_material(baldosas, m["material"])["area_desperdicio"] for m in materiales)
    tot_reut = sum(resumen_material(baldosas, m["material"])["area_reutilizable"] for m in materiales)
    lineas = [
        "PLANO GENERAL DE CORTE - RECORTES DE PISO",
        f"TOTAL: {tot_pzas} piezas = {tot_cajas} cajas = {tot_m2:.2f} m2",
        f"Sobrante reutilizable: {tot_reut:.2f} m2    Desperdicio (merma): {tot_desp:.2f} m2",
        "LEYENDA:  verde = pieza que se corta y se usa   |   "
        "amarillo = sobrante reutilizable   |   rojo = desperdicio",
    ]
    yy = y_cursor - 0.2
    for ln in lineas:
        texto(ln, 0, yy, 0.16, "TITULO", "LEFT")
        yy -= 0.30

    doc.saveas(path)
    return tot_desp, tot_reut


# --------------------------------------------------------------------------
#  PDF póster (una vista equivalente)
# --------------------------------------------------------------------------
def hacer_pdf(baldosas, materiales, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
        from matplotlib.backends.backend_pdf import PdfPages
    except Exception as e:
        print(f"(PDF omitido: matplotlib no disponible: {e})")
        return

    cols = COLUMNAS
    with PdfPages(path) as pdf:
        for m in materiales:
            material = m["material"]
            ancho, largo = PISOS[material]
            bs = [b for b in baldosas if b.material == material]
            if not bs:
                continue
            filas = (len(bs) + cols - 1) // cols
            fig, ax = plt.subplots(figsize=(16, max(6, filas * 1.7)))
            cell_w = ancho + SEP_X
            cell_h = largo + SEP_Y
            for i, b in enumerate(bs):
                col = i % cols
                row = i // cols
                ox = col * cell_w
                oy = -(row + 1) * cell_h
                ax.add_patch(Rectangle((ox, oy), ancho, largo, fill=False,
                                       edgecolor="black", lw=1.0))
                ax.text(ox + ancho / 2, oy + largo + 0.05,
                        f"{'M' if material=='Moret' else 'RW'}-{i+1:02d}",
                        ha="center", va="bottom", fontsize=5)
                for (x, y, w, l, etq, rot) in b.piezas:
                    ax.add_patch(Rectangle((ox + x, oy + y), w, l, facecolor="#82e0aa",
                                           edgecolor="black", lw=0.4))
                    ax.text(ox + x + w / 2, oy + y + l / 2, f"{w:.2f}x{l:.2f}",
                            ha="center", va="center", fontsize=3.5)
                for (fx, fy, fw, fl) in b.libres:
                    if fw <= 0.005 or fl <= 0.005:
                        continue
                    if es_reutilizable(fw, fl):
                        c = "#f7dc6f"
                    else:
                        c = "#f1948a"
                    ax.add_patch(Rectangle((ox + fx, oy + fy), fw, fl, facecolor=c,
                                           edgecolor="#888", lw=0.3))
            rsm = resumen_material(baldosas, material)
            ax.set_title(
                f"{material} — {len(bs)} baldosas para recortes — "
                f"{m['piezas_compra']} pzas / {m['cajas']} cajas / {m['m2_compra']:.2f} m²   "
                f"|   desperdicio {rsm['area_desperdicio']:.2f} m²  ·  "
                f"sobrante reutilizable {rsm['area_reutilizable']:.2f} m²",
                fontsize=10)
            ax.set_aspect("equal")
            ax.autoscale_view()
            ax.axis("off")
            # Leyenda
            from matplotlib.patches import Patch
            ax.legend(handles=[
                Patch(facecolor="#82e0aa", edgecolor="k", label="pieza que se usa"),
                Patch(facecolor="#f7dc6f", edgecolor="k", label="sobrante reutilizable"),
                Patch(facecolor="#f1948a", edgecolor="k", label="desperdicio (merma)"),
            ], loc="lower center", ncol=3, fontsize=8, frameon=False,
               bbox_to_anchor=(0.5, -0.04))
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description="Genera el plano general de corte (DXF + PDF)")
    ap.add_argument("piezas", nargs="?", default="piezas_piso.json")
    ap.add_argument("--kerf", type=float, default=0.0)
    ap.add_argument("--rotar", action="store_true")
    ap.add_argument("--dxf", default="plano_corte.dxf")
    ap.add_argument("--pdf", default="plano_corte.pdf")
    args = ap.parse_args()

    piezas = json.load(open(args.piezas, encoding="utf-8"))
    _, _, baldosas, materiales = generar(piezas, args.kerf, args.rotar)

    desp, reut = hacer_dxf(baldosas, materiales, args.dxf)
    hacer_pdf(baldosas, materiales, args.pdf)

    print(f"Baldosas dibujadas: {len(baldosas)}")
    print(f"Desperdicio total (merma): {desp:.2f} m²")
    print(f"Sobrante reutilizable total: {reut:.2f} m²")
    print(f"Plano AutoCAD: {args.dxf}")
    print(f"Plano PDF:     {args.pdf}")


if __name__ == "__main__":
    main()
