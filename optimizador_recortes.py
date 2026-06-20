#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
optimizador_recortes.py
=======================

A partir del despiece de piso (piezas_piso.json producido por extraer_despiece.py)
hace dos cosas:

  1) Te dice QUÉ PIEZAS hay que recortar (no son baldosa completa).
  2) Optimiza DÓNDE reusar esos recortes: agrupa las piezas recortadas para que
     el sobrante de cortar una baldosa sirva para otra pieza, en vez de cortar
     una baldosa entera nueva. Así se minimiza el desperdicio.

Método: empaquetado tipo "guillotina" (cortes rectos de lado a lado, como los
hace una cortadora de piso) con heurística First-Fit-Decreasing por área.
Cada baldosa completa es un "contenedor"; las piezas recortadas se acomodan
dentro y el sobrante (offcut) se reutiliza para piezas posteriores.

Salidas:
    reporte_recortes.txt  -> resumen legible (cuántas baldosas, cuánto se ahorra)
    plan_corte.csv        -> de qué baldosa sale cada pieza recortada
    diagramas_corte.pdf   -> dibujo de cada baldosa con sus piezas (si hay matplotlib)

Uso:
    python3 optimizador_recortes.py  [piezas_piso.json]  [--kerf 0.003] [--rotar]
"""

import json
import csv
import sys
import argparse
from collections import defaultdict

# Medidas nominales de la baldosa completa (metros): (ancho, largo)
PISOS = {
    "Moret":        (0.596, 1.194),
    "Royal Walnut": (0.200, 1.200),
}

EPS = 1e-6

# Tolerancia para ajustar medidas dibujadas al tamaño real de la baldosa.
# El plano dibuja la baldosa Moret como 0.6 x 1.194 cuando en realidad es
# 0.596 x 1.194 (redondeo). Una pieza nunca puede ser más grande que la
# baldosa de la que se cortó, así que ajustamos esas diferencias de dibujo.
TOL_CLAMP = 0.012


def ajustar(pw, pl, ancho, largo):
    """Recorta las medidas de la pieza al tamaño de la baldosa (absorbe el
    redondeo del dibujo: 0.600->0.596, 1.200->1.194, etc.)."""
    if pw > ancho and pw - ancho <= TOL_CLAMP:
        pw = ancho
    if pl > largo and pl - largo <= TOL_CLAMP:
        pl = largo
    return min(pw, ancho), min(pl, largo)


# --------------------------------------------------------------------------
#  Empaquetado guillotina de una baldosa (free-rectangle, best area fit)
# --------------------------------------------------------------------------
class Baldosa:
    """Una baldosa completa que se va recortando. Guarda piezas colocadas y
    los rectángulos libres (sobrantes) disponibles para más recortes."""

    _contador = 0

    def __init__(self, material, ancho, largo):
        Baldosa._contador += 1
        self.id = Baldosa._contador
        self.material = material
        self.ancho = ancho
        self.largo = largo
        # piezas: lista de (x, y, w, l, etiqueta)
        self.piezas = []
        # rectángulos libres: lista de (x, y, w, l)
        self.libres = [(0.0, 0.0, ancho, largo)]

    def _buscar(self, pw, pl, kerf, rotar):
        """Devuelve (indice_libre, w_usado, l_usado, rotada) del mejor hueco, o None."""
        mejor = None
        for i, (fx, fy, fw, fl) in enumerate(self.libres):
            for (w, l, rot) in ((pw, pl, False), (pl, pw, True)) if rotar else ((pw, pl, False),):
                need_w = w + (kerf if w + kerf <= fw + EPS else 0)
                need_l = l + (kerf if l + kerf <= fl + EPS else 0)
                if w <= fw + EPS and l <= fl + EPS:
                    sobra = fw * fl - w * l       # área desperdiciada -> minimizar
                    if mejor is None or sobra < mejor[0]:
                        mejor = (sobra, i, w, l, rot)
        if mejor is None:
            return None
        return mejor[1], mejor[2], mejor[3], mejor[4]

    def colocar(self, pw, pl, etiqueta, kerf, rotar):
        r = self._buscar(pw, pl, kerf, rotar)
        if r is None:
            return False
        i, w, l, rot = r
        fx, fy, fw, fl = self.libres.pop(i)
        self.piezas.append((fx, fy, w, l, etiqueta, rot))

        # Corte guillotina: elegimos la división que deja el rectángulo libre
        # más grande posible (mejor para seguir reusando).
        cw = w + kerf if w + kerf <= fw + EPS else w   # ancho consumido con sierra
        cl = l + kerf if l + kerf <= fl + EPS else l
        # Opción A (corte vertical): derecha de ancho completo + arriba angosto
        a1 = (fw - cw) * fl
        a2 = cw * (fl - cl)
        areaA = max(a1, a2)
        # Opción B (corte horizontal): arriba de ancho completo + derecha bajo
        b1 = fw * (fl - cl)
        b2 = (fw - cw) * cl
        areaB = max(b1, b2)

        nuevos = []
        if areaA >= areaB:
            if fw - cw > EPS:
                nuevos.append((fx + cw, fy, fw - cw, fl))
            if fl - cl > EPS:
                nuevos.append((fx, fy + cl, cw, fl - cl))
        else:
            if fl - cl > EPS:
                nuevos.append((fx, fy + cl, fw, fl - cl))
            if fw - cw > EPS:
                nuevos.append((fx + cw, fy, fw - cw, cl))
        # Sólo guardamos sobrantes con tamaño útil (> 1 cm en ambos lados)
        for n in nuevos:
            if n[2] > 0.01 and n[3] > 0.01:
                self.libres.append(n)
        return True

    def area_usada(self):
        return sum(w * l for (_, _, w, l, _, _) in self.piezas)

    def area_total(self):
        return self.ancho * self.largo

    def sobrantes_utiles(self):
        return [(w, l) for (_, _, w, l) in self.libres if w > 0.05 and l > 0.05]


def empaquetar(recortes, material, kerf, rotar):
    """recortes: lista de (ancho, largo, etiqueta). Devuelve lista de Baldosa."""
    ancho, largo = PISOS[material]
    # First-Fit-Decreasing: piezas grandes primero
    piezas = sorted(recortes, key=lambda p: p[0] * p[1], reverse=True)
    baldosas = []
    for (pw, pl, etiqueta) in piezas:
        colocada = False
        for b in baldosas:
            if b.colocar(pw, pl, etiqueta, kerf, rotar):
                colocada = True
                break
        if not colocada:
            b = Baldosa(material, ancho, largo)
            if not b.colocar(pw, pl, etiqueta, kerf, rotar):
                # La pieza no cabe ni en una baldosa nueva (no debería pasar)
                b.piezas.append((0, 0, pw, pl, etiqueta + " (NO CABE)", False))
            baldosas.append(b)
    return baldosas


# --------------------------------------------------------------------------
#  Reporte
# --------------------------------------------------------------------------
def f2(x):
    return f"{x:.3f}"


def generar(piezas, kerf, rotar):
    por_material = defaultdict(list)
    for p in piezas:
        por_material[p["material"]].append(p)

    lineas = []
    W = lineas.append
    W("=" * 70)
    W("   OPTIMIZACIÓN DE RECORTES DE PISO")
    W("=" * 70)
    if kerf:
        W(f"   (considerando {kerf*1000:.0f} mm de sierra entre cortes)")
    W("")

    resumen_global = {"completas": 0, "recortes": 0, "baldosas_recorte": 0,
                      "area_piezas": 0.0, "area_baldosas": 0.0}
    plan_filas = []
    todas_baldosas = []

    for material in PISOS:
        ps = por_material.get(material, [])
        if not ps:
            continue
        ancho, largo = PISOS[material]
        completas = [p for p in ps if p["completa"]]
        recortes = [p for p in ps if not p["completa"]]

        W("-" * 70)
        W(f"  {material}   (baldosa completa {f2(ancho)} x {f2(largo)} m)")
        W("-" * 70)
        W(f"  Piezas totales en el plano : {len(ps)}")
        W(f"  Baldosas COMPLETAS         : {len(completas)}  (1 baldosa cada una)")
        W(f"  Piezas a RECORTAR          : {len(recortes)}")

        # Desglose de recortes por tipo
        tipos = defaultdict(int)
        for p in recortes:
            tipos[p["tipo_corte"]] += 1
        if recortes:
            detalle = ", ".join(f"{k.replace('corte_','')}: {v}" for k, v in sorted(tipos.items()))
            W(f"      desglose                : {detalle}")

        # --- Optimización de los recortes ---
        entradas = []
        for p in recortes:
            aw, al = ajustar(p["ancho"], p["largo"], ancho, largo)
            loc = ""
            if "x" in p and "y" in p:
                loc = f' @({p["x"]:.2f},{p["y"]:.2f})'
            entradas.append((aw, al, f'{f2(aw)}x{f2(al)}{loc}'))
        baldosas = empaquetar(entradas, material, kerf, rotar)
        todas_baldosas.extend(baldosas)

        n_recorte = len(baldosas)
        sin_optim = len(recortes)        # si cada recorte saliera de una baldosa entera
        ahorro = sin_optim - n_recorte

        W("")
        W(f"  >> Reuso de recortes:")
        W(f"     Sin optimizar : {sin_optim} baldosas (una por cada recorte)")
        W(f"     Optimizado    : {n_recorte} baldosas (reusando sobrantes)")
        W(f"     AHORRO        : {ahorro} baldosas  ({'%.0f' % (100*ahorro/sin_optim) if sin_optim else 0}%)")

        total_baldosas = len(completas) + n_recorte
        area_piezas = 0.0
        for p in ps:
            aw, al = ajustar(p["ancho"], p["largo"], ancho, largo)
            area_piezas += aw * al
        area_baldosas = total_baldosas * ancho * largo
        merma = area_baldosas - area_piezas
        W("")
        W(f"  TOTAL BALDOSAS A COMPRAR ({material}): {total_baldosas}")
        W(f"     = {len(completas)} completas + {n_recorte} para recortes")
        W(f"     Área instalada: {f2(area_piezas)} m²   Área comprada: {f2(area_baldosas)} m²")
        W(f"     Merma (desperdicio): {f2(merma)} m²  ({100*merma/area_baldosas:.1f}%)")
        W("")

        # Detalle: de qué baldosa sale cada recorte
        W(f"  Plan de corte de las {n_recorte} baldosas de recorte:")
        for b in baldosas:
            etiquetas = [pz[4] for pz in b.piezas]
            sob = b.sobrantes_utiles()
            sob_txt = ""
            if sob:
                sob_txt = "  | sobra: " + ", ".join(f"{f2(w)}x{f2(l)}" for w, l in sob)
            W(f"     Baldosa #{b.id:<3} -> {len(etiquetas)} pza(s): {', '.join(etiquetas)}{sob_txt}")
            for (x, y, w, l, etq, rot) in b.piezas:
                plan_filas.append([material, b.id, f2(w), f2(l),
                                   "rotada" if rot else "normal", etq])
        W("")

        resumen_global["completas"] += len(completas)
        resumen_global["recortes"] += len(recortes)
        resumen_global["baldosas_recorte"] += n_recorte
        resumen_global["area_piezas"] += area_piezas
        resumen_global["area_baldosas"] += area_baldosas

    # --- Resumen global ---
    rg = resumen_global
    total = rg["completas"] + rg["baldosas_recorte"]
    sin_opt_total = rg["completas"] + rg["recortes"]
    W("=" * 70)
    W("   RESUMEN GLOBAL")
    W("=" * 70)
    W(f"   Baldosas completas        : {rg['completas']}")
    W(f"   Baldosas para recortes    : {rg['baldosas_recorte']}  (en vez de {rg['recortes']} sin optimizar)")
    W(f"   TOTAL BALDOSAS A COMPRAR  : {total}")
    W(f"   Ahorro por reuso          : {sin_opt_total - total} baldosas")
    if rg["area_baldosas"]:
        merma = rg["area_baldosas"] - rg["area_piezas"]
        W(f"   Merma total               : {f2(merma)} m²  ({100*merma/rg['area_baldosas']:.1f}%)")
    W("=" * 70)

    return "\n".join(lineas), plan_filas, todas_baldosas


# --------------------------------------------------------------------------
#  Diagramas (opcional, requiere matplotlib)
# --------------------------------------------------------------------------
def dibujar(baldosas, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
        from matplotlib.backends.backend_pdf import PdfPages
    except Exception as e:
        print(f"(diagramas omitidos: matplotlib no disponible: {e})")
        return False

    colores = ["#7fb3d5", "#82e0aa", "#f7dc6f", "#f0b27a", "#bb8fce",
               "#85c1e9", "#f1948a", "#73c6b6", "#f8c471", "#aab7b8"]
    por_pag = 12
    with PdfPages(path) as pdf:
        for inicio in range(0, len(baldosas), por_pag):
            grupo = baldosas[inicio:inicio + por_pag]
            fig, axes = plt.subplots(3, 4, figsize=(11.7, 8.3))
            axes = axes.ravel()
            for ax, b in zip(axes, grupo):
                ax.add_patch(Rectangle((0, 0), b.ancho, b.largo,
                                       fill=False, edgecolor="black", lw=1.5))
                for k, (x, y, w, l, etq, rot) in enumerate(b.piezas):
                    ax.add_patch(Rectangle((x, y), w, l, facecolor=colores[k % len(colores)],
                                           edgecolor="black", lw=0.6, alpha=0.9))
                    ax.text(x + w / 2, y + l / 2, f"{w:.2f}x{l:.2f}",
                            ha="center", va="center", fontsize=5.5)
                for (fx, fy, fw, fl) in b.libres:
                    if fw > 0.05 and fl > 0.05:
                        ax.add_patch(Rectangle((fx, fy), fw, fl, facecolor="#fdfefe",
                                               edgecolor="#cccccc", hatch="////", lw=0.4))
                ax.set_xlim(-0.02, b.ancho + 0.02)
                ax.set_ylim(-0.02, b.largo + 0.02)
                ax.set_aspect("equal")
                ax.set_title(f"{b.material} #{b.id}", fontsize=7)
                ax.tick_params(labelsize=4)
            for ax in axes[len(grupo):]:
                ax.axis("off")
            fig.suptitle("Plan de corte de baldosas (área rayada = sobrante reutilizable)", fontsize=10)
            fig.tight_layout(rect=[0, 0, 1, 0.96])
            pdf.savefig(fig)
            plt.close(fig)
    return True


def main():
    ap = argparse.ArgumentParser(description="Optimiza el reuso de recortes de piso")
    ap.add_argument("piezas", nargs="?", default="piezas_piso.json",
                    help="JSON de piezas (default: piezas_piso.json)")
    ap.add_argument("--kerf", type=float, default=0.0,
                    help="grosor de sierra en metros (default 0). Ej: 0.003 = 3 mm")
    ap.add_argument("--rotar", action="store_true",
                    help="permitir rotar piezas 90° (cuidado con el sentido de la veta)")
    ap.add_argument("--reporte", default="reporte_recortes.txt")
    ap.add_argument("--plan", default="plan_corte.csv")
    ap.add_argument("--pdf", default="diagramas_corte.pdf")
    args = ap.parse_args()

    piezas = json.load(open(args.piezas, encoding="utf-8"))
    texto, plan_filas, baldosas = generar(piezas, args.kerf, args.rotar)

    print(texto)
    with open(args.reporte, "w", encoding="utf-8") as f:
        f.write(texto + "\n")
    with open(args.plan, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["material", "baldosa_n", "ancho_m", "largo_m", "orientacion", "pieza_y_ubicacion"])
        w.writerows(plan_filas)
    if dibujar(baldosas, args.pdf):
        print(f"\nDiagramas: {args.pdf}")
    print(f"Reporte:  {args.reporte}")
    print(f"Plan CSV: {args.plan}")


if __name__ == "__main__":
    main()
