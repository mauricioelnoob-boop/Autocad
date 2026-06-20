#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plano_casa.py
=============

Genera el PLANO DE LA CASA con todo el despiece en su lugar real, donde CADA
pieza está identificada con un ID (ej. M-042 = Moret pieza 42, R-118 = Royal
Walnut pieza 118). Así sabes, pieza por pieza, cuál vas a recortar, cómo, y
dónde va instalada.

Cada recorte se enlaza con la baldosa del PLANO DE CORTE (plano_corte.pdf):
la columna "corte_de" dice de qué baldosa (M-01..M-79 / RW-01..RW-86) sale.

Salidas:
    plano_casa.dxf        -> el plano para AutoCAD (cada pieza con su ID)
    plano_casa.pdf        -> plano de la casa + tabla de recortes (ID -> cómo cortar)
    lista_piezas.csv      -> todas las piezas: ID, material, medida, tipo, ubicación, corte_de

Uso:
    python3 plano_casa.py  [piezas_piso.json]
"""

import json
import csv
import argparse
from collections import defaultdict

from optimizador_recortes import PISOS, CAJAS, ajustar, empaquetar, f2

PREFIJO = {"Moret": "M", "Royal Walnut": "R"}
PREFIJO_CORTE = {"Moret": "M", "Royal Walnut": "RW"}

# Colores (matplotlib / ACI para DXF)
ESTILO = {
    ("Moret", True):         {"face": "#dfe3e6", "aci": 8},   # completa: gris claro
    ("Moret", False):        {"face": "#f5b041", "aci": 30},  # recorte: naranja
    ("Royal Walnut", True):  {"face": "#e8eef0", "aci": 9},   # completa: gris azulado
    ("Royal Walnut", False): {"face": "#48c9b0", "aci": 4},   # recorte: turquesa
}


def asignar_ids_y_corte(piezas):
    """Numera las piezas por material (orden de lectura: arriba->abajo,
    izq->der) y calcula de qué baldosa de corte sale cada recorte."""
    por_material = defaultdict(list)
    for p in piezas:
        por_material[p["material"]].append(p)

    for material, ps in por_material.items():
        # Orden de lectura para numerar
        ps.sort(key=lambda p: (-p["y"], p["x"]))
        for i, p in enumerate(ps, 1):
            p["id"] = f'{PREFIJO[material]}-{i:03d}'

        # Empaquetar los recortes para saber de qué baldosa sale cada uno
        ancho, largo = PISOS[material]
        recortes = [p for p in ps if not p["completa"]]
        entradas = []
        for p in recortes:
            aw, al = ajustar(p["ancho"], p["largo"], ancho, largo)
            entradas.append((aw, al, p["id"]))
        baldosas = empaquetar(entradas, material, 0.0, False)
        pref = PREFIJO_CORTE[material]
        mapa = {}
        for idx, b in enumerate(baldosas, 1):
            etiqueta = f"{pref}-{idx:02d}"
            for (x, y, w, l, pid, rot) in b.piezas:
                mapa[pid] = etiqueta
        for p in ps:
            p["corte_de"] = mapa.get(p["id"], "")

    return piezas


# --------------------------------------------------------------------------
#  DXF
# --------------------------------------------------------------------------
def hacer_dxf(piezas, path):
    import ezdxf
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.M
    msp = doc.modelspace()

    layers = {
        "PISO-MORET-COMPLETA":  8,
        "PISO-MORET-RECORTE":   30,
        "PISO-ROYAL-COMPLETA":  9,
        "PISO-ROYAL-RECORTE":   4,
        "ID-TEXTO":             7,
        "ID-TEXTO-RECORTE":     1,
    }
    for n, c in layers.items():
        doc.layers.add(n).color = c

    def layer_de(p):
        mat = "MORET" if p["material"] == "Moret" else "ROYAL"
        tipo = "COMPLETA" if p["completa"] else "RECORTE"
        return f"PISO-{mat}-{tipo}"

    for p in piezas:
        x0, y0, w, h = p["x0"], p["y0"], p["wx"], p["hy"]
        ly = layer_de(p)
        msp.add_lwpolyline([(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)],
                           close=True, dxfattribs={"layer": ly})
        # Relleno tenue sólo a los recortes (para que resalten)
        if not p["completa"]:
            est = ESTILO[(p["material"], False)]
            hatch = msp.add_hatch(color=est["aci"], dxfattribs={"layer": ly})
            hatch.set_solid_fill(est["aci"])
            hatch.paths.add_polyline_path(
                [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)], is_closed=True)
            hatch.transparency = 0.6
        # ID en el centro
        th = max(0.03, min(w, h) * 0.30)
        th = min(th, 0.09)
        tl = "ID-TEXTO-RECORTE" if not p["completa"] else "ID-TEXTO"
        t = msp.add_text(p["id"], dxfattribs={"layer": tl, "height": th})
        t.set_placement((p["x"], p["y"]), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

    doc.saveas(path)


# --------------------------------------------------------------------------
#  PDF (plano + tabla)
# --------------------------------------------------------------------------
def hacer_pdf(piezas, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle, Patch
        from matplotlib.backends.backend_pdf import PdfPages
    except Exception as e:
        print(f"(PDF omitido: matplotlib no disponible: {e})")
        return

    xs0 = [p["x0"] for p in piezas]; ys0 = [p["y0"] for p in piezas]
    xs1 = [p["x0"] + p["wx"] for p in piezas]; ys1 = [p["y0"] + p["hy"] for p in piezas]
    minx, maxx = min(xs0), max(xs1)
    miny, maxy = min(ys0), max(ys1)
    ancho_plano = maxx - minx
    alto_plano = maxy - miny

    with PdfPages(path) as pdf:
        # ---- Página 1: PLANO DE LA CASA ----
        escala = 1.4
        fig, ax = plt.subplots(figsize=(ancho_plano * escala, alto_plano * escala + 1))
        for p in piezas:
            est = ESTILO[(p["material"], p["completa"])]
            ax.add_patch(Rectangle((p["x0"], p["y0"]), p["wx"], p["hy"],
                                   facecolor=est["face"], edgecolor="#333",
                                   lw=0.4 if p["completa"] else 0.7))
            fs = max(1.6, min(p["wx"], p["hy"]) * 14)
            fs = min(fs, 4.5)
            ax.text(p["x"], p["y"], p["id"], ha="center", va="center",
                    fontsize=fs, color="#111",
                    rotation=0 if p["wx"] >= p["hy"] else 90)
        ax.set_xlim(minx - 0.3, maxx + 0.3)
        ax.set_ylim(miny - 0.3, maxy + 0.3)
        ax.set_aspect("equal")
        ax.set_title("PLANO DE LA CASA — Despiece de piso identificado por pieza\n"
                     "(naranja = recorte Moret, turquesa = recorte Royal Walnut, "
                     "gris = baldosa completa)", fontsize=11)
        ax.legend(handles=[
            Patch(facecolor=ESTILO[("Moret", True)]["face"], edgecolor="#333", label="Moret completa"),
            Patch(facecolor=ESTILO[("Moret", False)]["face"], edgecolor="#333", label="Moret recorte"),
            Patch(facecolor=ESTILO[("Royal Walnut", True)]["face"], edgecolor="#333", label="Royal completa"),
            Patch(facecolor=ESTILO[("Royal Walnut", False)]["face"], edgecolor="#333", label="Royal recorte"),
        ], loc="upper center", ncol=4, fontsize=8, frameon=True, bbox_to_anchor=(0.5, -0.01))
        ax.tick_params(labelsize=6)
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # ---- Páginas siguientes: TABLA DE RECORTES ----
        recortes = [p for p in piezas if not p["completa"]]
        recortes.sort(key=lambda p: (p["material"], p["id"]))
        encab = ["ID pieza", "Material", "Medida a cortar (m)", "Tipo de corte",
                 "Cortar de baldosa", "Ubicación (x,y)"]
        por_pag = 34
        for ini in range(0, len(recortes), por_pag):
            grupo = recortes[ini:ini + por_pag]
            filas = []
            nombre_tipo = {"corte_largo": "a lo largo", "corte_ancho": "a lo ancho",
                           "corte_esquina": "en esquina"}
            for p in grupo:
                filas.append([
                    p["id"], p["material"],
                    f'{p["wx"]:.3f} x {p["hy"]:.3f}',
                    nombre_tipo.get(p["tipo_corte"], p["tipo_corte"]),
                    p.get("corte_de", ""),
                    f'({p["x"]:.2f}, {p["y"]:.2f})',
                ])
            fig, ax = plt.subplots(figsize=(11.7, 8.3))
            ax.axis("off")
            ax.set_title(f"Lista de recortes — cómo cortar cada pieza  "
                         f"(pág. {ini//por_pag + 1} de {(len(recortes)+por_pag-1)//por_pag})",
                         fontsize=12, pad=14)
            tabla = ax.table(cellText=filas, colLabels=encab, loc="upper center", cellLoc="center")
            tabla.auto_set_font_size(False)
            tabla.set_fontsize(7.5)
            tabla.scale(1, 1.35)
            for (r, c), cell in tabla.get_celld().items():
                if r == 0:
                    cell.set_facecolor("#34495e"); cell.set_text_props(color="white", weight="bold")
                elif c == 0:
                    cell.set_text_props(weight="bold")
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description="Plano de la casa con el despiece identificado")
    ap.add_argument("piezas", nargs="?", default="piezas_piso.json")
    ap.add_argument("--dxf", default="plano_casa.dxf")
    ap.add_argument("--pdf", default="plano_casa.pdf")
    ap.add_argument("--csv", default="lista_piezas.csv")
    args = ap.parse_args()

    piezas = json.load(open(args.piezas, encoding="utf-8"))
    asignar_ids_y_corte(piezas)

    hacer_dxf(piezas, args.dxf)
    hacer_pdf(piezas, args.pdf)

    with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "material", "completa", "tipo_corte",
                    "ancho_m", "largo_m", "x", "y", "cortar_de_baldosa"])
        for p in sorted(piezas, key=lambda p: p["id"]):
            w.writerow([p["id"], p["material"], "si" if p["completa"] else "no",
                        p["tipo_corte"], f'{p["wx"]:.3f}', f'{p["hy"]:.3f}',
                        p["x"], p["y"], p.get("corte_de", "")])

    nrec = sum(1 for p in piezas if not p["completa"])
    print(f"Piezas totales: {len(piezas)}  (recortes: {nrec})")
    print(f"Plano AutoCAD: {args.dxf}")
    print(f"Plano PDF:     {args.pdf}")
    print(f"Lista CSV:     {args.csv}")


if __name__ == "__main__":
    main()
