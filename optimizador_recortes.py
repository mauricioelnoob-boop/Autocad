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
import math
import argparse
from collections import defaultdict

# Medidas nominales de la baldosa completa (metros): (ancho, largo)
PISOS = {
    "Moret":        (0.596, 1.194),
    "Royal Walnut": (0.200, 1.200),
}

# Presentación comercial (cajas). m2_caja canónico = medida pieza × pzas/caja
# (Moret 0.7116×2 = 1.4232, Royal 0.24×5 = 1.20). suministrado_m2 es el dato
# histórico de Cabernet (legacy de este script standalone; el pipeline oficial
# usa datos_cliente.SUMINISTRADO por modelo).
CAJAS = {
    "Moret":        {"pzas_caja": 2, "m2_caja": 1.4232, "suministrado_m2": 166.52},
    "Royal Walnut": {"pzas_caja": 5, "m2_caja": 1.20, "suministrado_m2": 49.20},
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
    los rectángulos libres (sobrantes) disponibles para más recortes.

    SEGUIMIENTO DE REUSO: cada rectángulo libre recuerda de QUÉ pieza salió
    (`origen`); así cada pieza colocada sabe si se cortó de la tabla nueva o del
    SOBRANTE de otra pieza. `self.meta[i]` = (origen, orden_corte) para piezas[i].
    """

    _contador = 0

    def __init__(self, material, ancho, largo):
        Baldosa._contador += 1
        self.id = Baldosa._contador
        self.material = material
        self.ancho = ancho
        self.largo = largo
        self.piezas = []          # (x, y, w, l, etiqueta, rot)
        self.meta = []            # (origen, orden) paralelo a piezas
        # rectángulos libres: (x, y, w, l, origen)   origen = etiqueta o "TABLA"
        self.libres = [(0.0, 0.0, ancho, largo, "TABLA")]

    def _buscar(self, pw, pl, kerf, rotar):
        mejor = None
        for i, (fx, fy, fw, fl, org) in enumerate(self.libres):
            for (w, l, rot) in ((pw, pl, False), (pl, pw, True)) if rotar else ((pw, pl, False),):
                if w <= fw + EPS and l <= fl + EPS:
                    sobra = fw * fl - w * l
                    if mejor is None or sobra < mejor[0]:
                        mejor = (sobra, i, w, l, rot)
        return None if mejor is None else (mejor[1], mejor[2], mejor[3], mejor[4])

    def evaluar(self, pw, pl, kerf, rotar):
        mejor = None
        for (fx, fy, fw, fl, org) in self.libres:
            for (w, l, rot) in ((pw, pl, False), (pl, pw, True)) if rotar else ((pw, pl, False),):
                if w <= fw + EPS and l <= fl + EPS:
                    sobra = fw * fl - w * l
                    if mejor is None or sobra < mejor:
                        mejor = sobra
        return mejor

    def colocar(self, pw, pl, etiqueta, kerf, rotar, orden=0):
        r = self._buscar(pw, pl, kerf, rotar)
        if r is None:
            return False
        i, w, l, rot = r
        fx, fy, fw, fl, origen = self.libres.pop(i)
        self.piezas.append((fx, fy, w, l, etiqueta, rot))
        self.meta.append((origen, orden))

        cw = w + kerf if w + kerf <= fw + EPS else w
        cl = l + kerf if l + kerf <= fl + EPS else l
        a1 = (fw - cw) * fl; a2 = cw * (fl - cl); areaA = max(a1, a2)
        b1 = fw * (fl - cl); b2 = (fw - cw) * cl; areaB = max(b1, b2)
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
        for n in nuevos:
            if n[2] > 0.01 and n[3] > 0.01:
                self.libres.append((n[0], n[1], n[2], n[3], etiqueta))  # sobrante DE esta pieza
        return True

    def area_usada(self):
        return sum(w * l for (_, _, w, l, _, _) in self.piezas)

    def area_total(self):
        return self.ancho * self.largo

    def sobrantes_utiles(self):
        return [(w, l) for (_, _, w, l, _) in self.libres if w > 0.05 and l > 0.05]


def empaquetar(recortes, material, kerf, rotar):
    """recortes: lista de (ancho, largo, etiqueta). Devuelve lista de Baldosa.

    Best-Fit-Decreasing: las piezas grandes primero; cada una se coloca en la
    baldosa donde deja MENOS sobrante (reusando el SOBRANTE de cortes anteriores)
    antes de abrir tabla nueva. Cada pieza queda con su ORDEN de corte y de qué
    sobrante salió (Baldosa.meta), para imprimir la cadena de reuso.
    """
    ancho, largo = PISOS[material]
    piezas = sorted(recortes, key=lambda p: p[0] * p[1], reverse=True)
    baldosas = []
    orden = 0
    for (pw, pl, etiqueta) in piezas:
        orden += 1
        mejor_b, mejor_score = None, None
        for b in baldosas:
            s = b.evaluar(pw, pl, kerf, rotar)
            if s is not None and (mejor_score is None or s < mejor_score):
                mejor_score, mejor_b = s, b
        if mejor_b is not None:
            mejor_b.colocar(pw, pl, etiqueta, kerf, rotar, orden)
        else:
            b = Baldosa(material, ancho, largo)
            if not b.colocar(pw, pl, etiqueta, kerf, rotar, orden):
                b.piezas.append((0, 0, pw, pl, etiqueta + " (NO CABE)", False)); b.meta.append(("TABLA", orden))
            baldosas.append(b)
    return baldosas


def cadena_de_corte(baldosas):
    """Para cada baldosa, la secuencia ORDENADA de cortes y de qué sobrante sale
    cada pieza. Devuelve lista de dicts: {id, material, cortes:[{orden, etiqueta,
    w, l, rot, origen}], sobrante_reusable_m2, merma_m2}."""
    out = []
    for b in baldosas:
        cortes = []
        for (x, y, w, l, etq, rot), (origen, orden) in zip(b.piezas, b.meta):
            cortes.append({"orden": orden, "etiqueta": etq, "w": round(w, 4),
                           "l": round(l, 4), "rot": rot, "origen": origen})
        cortes.sort(key=lambda c: c["orden"])
        reut = sum(w * l for (_, _, w, l, _) in b.libres if w >= 0.10 and l >= 0.10)
        merma = sum(w * l for (_, _, w, l, _) in b.libres
                    if (w > 0.005 and l > 0.005) and (w < 0.10 or l < 0.10))
        out.append({"id": b.id, "material": b.material, "cortes": cortes,
                    "sobrante_reusable_m2": round(reut, 4), "merma_m2": round(merma, 4)})
    return out


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
    materiales = []      # datos estructurados por material (para el PDF)

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
        W(f"  TOTAL PIEZAS A COMPRAR ({material}): {total_baldosas} piezas")
        W(f"     = {len(completas)} completas + {n_recorte} para recortes")

        # --- Conversión a cajas y m² ---
        cfg = CAJAS.get(material, {})
        pzas_caja = cfg.get("pzas_caja")
        m2_caja = cfg.get("m2_caja")
        cajas = m2_compra = pzas_compradas = None
        if pzas_caja and m2_caja:
            cajas = math.ceil(total_baldosas / pzas_caja)
            pzas_compradas = cajas * pzas_caja        # se compran cajas enteras
            m2_compra = cajas * m2_caja
            W(f"     En cajas: {cajas} cajas de {pzas_caja} pzas = {pzas_compradas} piezas")
            W(f"     Equivale a: {f2(m2_compra)} m²  (caja = {m2_caja:g} m²)")
            sumin = cfg.get("suministrado_m2")
            if sumin is not None:
                W(f"     (Dato proveedor: te suministraron {sumin:g} m² de {material})")
        W(f"     Área neta instalada: {f2(area_piezas)} m²")
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

        materiales.append({
            "material": material, "ancho": ancho, "largo": largo,
            "completas": len(completas), "recortes": len(recortes),
            "baldosas_recorte": n_recorte, "ahorro": ahorro,
            "piezas_compra": total_baldosas,
            "cajas": cajas, "pzas_caja": pzas_caja, "m2_caja": m2_caja,
            "pzas_compradas": pzas_compradas, "m2_compra": m2_compra,
            "area_instalada": area_piezas,
            "suministrado_m2": cfg.get("suministrado_m2"),
        })

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
    W(f"   TOTAL PIEZAS A COMPRAR    : {total}")
    W(f"   Ahorro por reuso          : {sin_opt_total - total} baldosas")
    if rg["area_baldosas"]:
        merma = rg["area_baldosas"] - rg["area_piezas"]
        W(f"   Merma total               : {f2(merma)} m²  ({100*merma/rg['area_baldosas']:.1f}%)")
    W("")
    W("   CANTIDADES A COMPRAR (piezas / cajas / m²):")
    for m in materiales:
        if m["cajas"] is not None:
            W(f"     {m['material']:13}: {m['piezas_compra']:3} pzas -> "
              f"{m['cajas']} cajas ({m['pzas_compradas']} pzas) = {f2(m['m2_compra'])} m²")
        else:
            W(f"     {m['material']:13}: {m['piezas_compra']:3} pzas")
    W("=" * 70)

    return "\n".join(lineas), plan_filas, todas_baldosas, materiales


# --------------------------------------------------------------------------
#  Reporte PDF (opcional, requiere matplotlib): resumen + diagramas de corte
# --------------------------------------------------------------------------
def _pagina_resumen(pdf, materiales, plt):
    """Primera página: tabla de cantidades a comprar (piezas, cajas, m²)."""
    fig = plt.figure(figsize=(11.7, 8.3))
    fig.suptitle("Cantidades a comprar — Optimización de recortes de piso",
                 fontsize=15, y=0.96)

    encab = ["Material", "Baldosa (m)", "Completas", "Recortes",
             "Baldosas\nrecortes", "Ahorro\n(pzas)", "PIEZAS A\nCOMPRAR",
             "Cajas", "Piezas/\ncaja", "m² A\nCOMPRAR"]
    filas = []
    tot_pzas = tot_cajas = 0
    tot_m2 = 0.0
    for m in materiales:
        cajas = m["cajas"] if m["cajas"] is not None else "-"
        pzcaja = m["pzas_caja"] if m["pzas_caja"] else "-"
        m2 = f"{m['m2_compra']:.2f}" if m["m2_compra"] is not None else "-"
        filas.append([m["material"], f'{m["ancho"]:.3f} x {m["largo"]:.3f}',
                      m["completas"], m["recortes"], m["baldosas_recorte"],
                      m["ahorro"], m["piezas_compra"], cajas, pzcaja, m2])
        tot_pzas += m["piezas_compra"]
        if m["cajas"]:
            tot_cajas += m["cajas"]
        if m["m2_compra"]:
            tot_m2 += m["m2_compra"]
    filas.append(["TOTAL", "", "", "", "", "", tot_pzas, tot_cajas, "", f"{tot_m2:.2f}"])

    ax = fig.add_axes([0.04, 0.50, 0.92, 0.36])
    ax.axis("off")
    tabla = ax.table(cellText=filas, colLabels=encab, loc="center", cellLoc="center")
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(8.5)
    tabla.scale(1, 2.2)
    ncol = len(encab)
    for (r, c), cell in tabla.get_celld().items():
        if r == 0:
            cell.set_facecolor("#34495e"); cell.set_text_props(color="white", weight="bold")
        elif r == len(filas):
            cell.set_facecolor("#d5dbdb"); cell.set_text_props(weight="bold")
        if c in (6, 9) and r != 0:           # columnas clave resaltadas
            cell.set_facecolor("#fcf3cf" if r != len(filas) else "#f7dc6f")

    # Notas con el dato del proveedor (sin veredicto de si alcanza o no)
    notas = ["Material suministrado por el proveedor (dato informativo):"]
    for m in materiales:
        if m["suministrado_m2"] is not None:
            cj = ""
            if m["m2_caja"]:
                cj = f"  (≈ {m['suministrado_m2']/m['m2_caja']:.1f} cajas / {m['suministrado_m2']/m['m2_caja']*m['pzas_caja']:.0f} pzas)"
            notas.append(f"   • {m['material']}: {m['suministrado_m2']:g} m²{cj}")
    notas.append("")
    notas.append("Notas:")
    notas.append("   • 'Piezas a comprar' = baldosas completas + baldosas abiertas para sacar recortes (ya optimizado).")
    notas.append("   • Las cajas se redondean hacia arriba (se compran cajas enteras).")
    notas.append("   • Diagramas de corte de cada baldosa en las páginas siguientes.")
    fig.text(0.06, 0.42, "\n".join(notas), fontsize=10, va="top", family="monospace")

    pdf.savefig(fig)
    plt.close(fig)


def dibujar(baldosas, path, materiales=None):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
        from matplotlib.backends.backend_pdf import PdfPages
    except Exception as e:
        print(f"(PDF omitido: matplotlib no disponible: {e})")
        return False

    colores = ["#7fb3d5", "#82e0aa", "#f7dc6f", "#f0b27a", "#bb8fce",
               "#85c1e9", "#f1948a", "#73c6b6", "#f8c471", "#aab7b8"]
    por_pag = 12
    with PdfPages(path) as pdf:
        if materiales:
            _pagina_resumen(pdf, materiales, plt)
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
                for (fx, fy, fw, fl, *_z) in b.libres:
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
    ap.add_argument("--pdf", default="reporte_recortes.pdf")
    args = ap.parse_args()

    piezas = json.load(open(args.piezas, encoding="utf-8"))
    texto, plan_filas, baldosas, materiales = generar(piezas, args.kerf, args.rotar)

    print(texto)
    with open(args.reporte, "w", encoding="utf-8") as f:
        f.write(texto + "\n")
    with open(args.plan, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["material", "baldosa_n", "ancho_m", "largo_m", "orientacion", "pieza_y_ubicacion"])
        w.writerows(plan_filas)
    if dibujar(baldosas, args.pdf, materiales):
        print(f"\nPDF (resumen + diagramas): {args.pdf}")
    print(f"Reporte:  {args.reporte}")
    print(f"Plan CSV: {args.plan}")


if __name__ == "__main__":
    main()
