#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf_colocacion.py
=================
GUÍA DE COLOCACIÓN PASO A PASO — una página por RECORTE COLOCADO, en orden
de colocación REAL (pegado, siguiendo boquillas):

  * ORDEN: se empieza en PLANTA ALTA junto a la ESCALERA; se avanza CUARTO
    POR CUARTO (zonas conexas de piso, de la más cercana a la escalera a la
    más lejana) y dentro del cuarto FILA POR FILA siguiendo las boquillas,
    serpenteando (una fila de ida, la siguiente de vuelta). Al terminar P.A.
    se sigue con P.B., también desde la escalera. Nunca se brinca de un
    cuarto a otro al azar.
  * La pieza madre se CORTA cuando se necesita su primer recorte; los demás
    recortes de esa misma pieza quedan CORTADOS EN RESERVA y la página de
    cada uno dice en qué paso se cortó. Así los FALTANTES (que salen de la
    sobra de otra pieza) siempre tienen su sobra ya cortada.
  * En cada página: plano en gris, colocado en verde, EN AZUL el recorte del
    paso; el corte de la pieza madre a la derecha (recortes con su paso de
    colocación, sobrantes amarillos, merma roja) y el registro acumulado.

Uso:  python3 pdf_colocacion.py [Modelo ...]
"""
import math
import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.backends.backend_pdf import PdfPages

from datos_piezas import cargar_anotado, PREF_CORTE
from optimizador_recortes import PISOS
from pdf_material import empacar, es_reutilizable, _fmt, _punto_escalera

FECHA = datetime.date.today().strftime("%d/%m/%Y")
PIE = "Elaboró: Ing. Mauricio Gastelum Mora"

AZUL = "#2E86C1"        # recorte que se coloca en ESTE paso
VERDE = "#d5f5e3"       # ya colocado en pasos anteriores
GRIS = "#f2f3f4"        # aún sin colocar
CTX = "#fafafa"         # el otro material (contexto)


def _orden_colocacion(piezas_mat, pe):
    """Orden de colocación con la REGLA DE OBRA: cada pieza que se pone queda
    JUNTO a una ya puesta (comparten boquilla). Caminata por adyacencia:
    arranca en P.A. junto a la escalera; en cada paso se coloca una pieza
    vecina de las ya puestas, prefiriendo seguir la MISMA FILA pegado a la
    última (serpenteo natural). Solo se 'brinca' al agotar una región conexa
    (cambio de planta o isla separada), reiniciando por la más cercana a la
    escalera. `pe` = centroide de la escalera."""
    n = len(piezas_mat)
    ady = [[] for _ in range(n)]
    for i in range(n):
        a = piezas_mat[i]
        ax1, ay1 = a["x0"] + a["wx"], a["y0"] + a["hy"]
        for j in range(i + 1, n):
            b = piezas_mat[j]
            bx1, by1 = b["x0"] + b["wx"], b["y0"] + b["hy"]
            fx = min(ax1, bx1) - max(a["x0"], b["x0"])
            fy = min(ay1, by1) - max(a["y0"], b["y0"])
            gx = max(b["x0"] - ax1, a["x0"] - bx1)
            gy = max(b["y0"] - ay1, a["y0"] - by1)
            # comparten boquilla: pegadas (hueco <= 2.5 cm) con traslape > 5 cm
            if (fy > 0.05 and -0.001 <= gx <= 0.025) or (fx > 0.05 and -0.001 <= gy <= 0.025):
                ady[i].append(j)
                ady[j].append(i)

    def d2(i, pt):
        return (piezas_mat[i]["x"] - pt[0]) ** 2 + (piezas_mat[i]["y"] - pt[1]) ** 2

    resto = set(range(n))
    orden = []
    while resto:
        # arranque de región: P.A. primero, lo más cerca de la escalera
        start = min(resto, key=lambda i: (piezas_mat[i]["planta"] != "alta", d2(i, pe)))
        resto.discard(start)
        orden.append(start)
        frontera = set(j for j in ady[start] if j in resto)
        last = start
        while frontera:
            pl = piezas_mat[last]
            ady_last = set(ady[last])

            def _score(j):
                q = piezas_mat[j]
                misma_fila = abs(q["y0"] - pl["y0"]) <= 0.12
                return (j not in ady_last,          # 1o: pegada a la ÚLTIMA
                        not misma_fila,             # 2o: sigue la misma fila
                        d2(j, (pl["x"], pl["y"])))  # 3o: la más cercana
            sig = min(frontera, key=_score)
            frontera.discard(sig)
            resto.discard(sig)
            orden.append(sig)
            frontera |= {j for j in ady[sig] if j in resto}
            frontera &= resto
            last = sig
    return [piezas_mat[i] for i in orden]


def _portada(pdf, modelo, pasos_m, pasos_r):
    pm, pr = PREF_CORTE["Moret"], PREF_CORTE["Royal Walnut"]
    fig = plt.figure(figsize=(13.5, 8.0))
    fig.text(0.5, 0.68, "GUÍA DE COLOCACIÓN PASO A PASO", ha="center",
             fontsize=26, weight="bold", color="#1b4f72")
    fig.text(0.5, 0.60, f"{modelo.upper()} · Viñas Norte", ha="center",
             fontsize=16, color="#2874a6")
    txt = (f"Una página por CADA PIEZA COLOCADA (enteras y recortes): {pasos_m} de Moret"
           f" y {pasos_r} de Royal Walnut.\n\n"
           "REGLA DE OBRA: cada pieza que se pone queda JUNTO a una ya puesta"
           " (comparten boquilla).\nSe empieza en PLANTA ALTA junto a la ESCALERA y se"
           " avanza pegado, fila por fila por las boquillas;\nsolo se cambia de frente"
           " al agotar una región (cambio de planta o isla separada).\n\n"
           "La pieza madre se CORTA cuando se necesita su primer recorte (dice"
           f" '{pm}-xx SE CORTA AHORA');\nlos demás recortes de esa pieza quedan en"
           " RESERVA con el paso en que se colocan,\ny los que salen de una SOBRA"
           " siempre tienen su sobra ya cortada.\n\n"
           "GRIS = por colocar · VERDE = ya colocado · AZUL = la pieza de este paso.")
    fig.text(0.5, 0.28, txt, ha="center", fontsize=10, color="#333", linespacing=1.7)
    fig.text(0.5, 0.05, f"{PIE}        {FECHA}", ha="center", fontsize=9, color="#777")
    pdf.savefig(fig)
    plt.close(fig)


def _dibujo_corte(axc, material, b, actual, paso_de, corta_ahora):
    aB, lB = PISOS[material]
    axc.add_patch(Rectangle((0, 0), aB, lB, fill=False, edgecolor="black", lw=1.5))
    for (x, y, w, l, etq, rot), (org, _o) in zip(b.piezas, b.meta):
        es_act = etq == actual
        axc.add_patch(Rectangle((x, y), w, l,
                                facecolor=AZUL if es_act else "#d6dbdf",
                                edgecolor="#1a5276" if es_act else "#7f8c8d",
                                lw=1.0 if es_act else 0.5))
        if es_act:
            det = "AHORA"
        elif etq in paso_de:
            det = f"paso {paso_de[etq]}"
        elif etq[:1] in ("P", "H", "D"):
            det = "escalera"
        else:
            det = "muro baño"
        src = "nueva" if org == "TABLA" else f"de sobra de {org}"
        axc.text(x + w / 2, y + l / 2, f"{etq}\n{_fmt(w)}x{_fmt(l)}\n({src})\n→ {det}",
                 ha="center", va="center", fontsize=4.6,
                 color="white" if es_act else "#333",
                 rotation=0 if w >= l else 90)
    for (fx, fy, fw, fl, *_z) in b.libres:
        if fw <= 0.005 or fl <= 0.005:
            continue
        reut = es_reutilizable(fw, fl)
        axc.add_patch(Rectangle((fx, fy), fw, fl,
                                facecolor="#f9e79f" if reut else "#f1948a",
                                edgecolor="#b7950b" if reut else "#922b21",
                                lw=0.7, hatch=".." if reut else "xx"))
        axc.text(fx + fw / 2, fy + fl / 2,
                 f"SOBRA\n{_fmt(fw)}x{_fmt(fl)}\n→ GUARDAR" if reut
                 else f"merma\n{_fmt(fw)}x{_fmt(fl)}",
                 ha="center", va="center", fontsize=4.4,
                 color="#7d6608" if reut else "#641e16",
                 rotation=0 if fw >= fl else 90)
    axc.set_xlim(-0.02, aB + 0.02)
    axc.set_ylim(-0.02, lB + 0.02)
    axc.set_aspect("equal")
    axc.axis("off")


def hacer(modelo):
    todas = cargar_anotado(modelo)
    pe = _punto_escalera(modelo) or (sum(p["x"] for p in todas) / len(todas),
                                     sum(p["y"] for p in todas) / len(todas))
    salida = f"Viñas Norte - {modelo} Colocación paso a paso.pdf"

    plan = {}
    for material in ("Moret", "Royal Walnut"):
        baldosas, mapa, _d = empacar(todas, material, modelo)
        tabla_de, origen_de = {}, {}
        for idx, b in enumerate(baldosas, 1):
            for (x, y, w, l, etq, rot), (org, _o) in zip(b.piezas, b.meta):
                tabla_de[etq] = idx
                origen_de[etq] = org
        # TODAS las piezas del material (enteras + recortes): la regla de obra
        # es que cada pieza colocada quede JUNTO a una ya puesta
        piezas_mat = [p for p in todas if p["material"] == material and p.get("id")]
        orden = _orden_colocacion(piezas_mat, pe)
        paso_de = {p["id"]: i + 1 for i, p in enumerate(orden)}
        plan[material] = (baldosas, mapa, tabla_de, origen_de, orden, paso_de)

    with PdfPages(salida) as pdf:
        _portada(pdf, modelo,
                 len(plan["Moret"][4]), len(plan["Royal Walnut"][4]))
        total_pags = 1
        for material in ("Moret", "Royal Walnut"):
            baldosas, mapa, tabla_de, origen_de, orden, paso_de = plan[material]
            pc = PREF_CORTE[material]
            colocadas = set()
            cortadas = set()          # índices de tabla ya cortados
            reserva = []              # (id, paso_destino) recortes cortados sin colocar
            guardadas = []            # (w, l, tabla, paso) sobras a guardar
            merma_acum = 0.0
            total = len(orden)
            for i, p in enumerate(orden, 1):
                pid = p["id"]
                es_recorte = (not p["completa"]) and pid in tabla_de
                idx = tabla_de.get(pid)
                b = baldosas[idx - 1] if idx else None
                corta_ahora = es_recorte and idx not in cortadas

                fig = plt.figure(figsize=(13.5, 8.0))
                ax = fig.add_axes([0.03, 0.06, 0.60, 0.84])
                focos = [q for q in todas if q["planta"] == p["planta"]]
                for q in focos:
                    es_mat = q["material"] == material
                    qid = q.get("id")
                    if es_mat and qid == pid:
                        fc, ec, lw, z = AZUL, "#1a5276", 1.2, 4
                    elif es_mat and qid in colocadas:
                        fc, ec, lw, z = VERDE, "#82b366", 0.4, 2
                    elif es_mat:
                        fc, ec, lw, z = GRIS, "#b3b6b7", 0.4, 2
                    else:
                        fc, ec, lw, z = CTX, "#dddddd", 0.3, 1
                    ax.add_patch(Rectangle((q["x0"], q["y0"]), q["wx"], q["hy"],
                                           facecolor=fc, edgecolor=ec, lw=lw, zorder=z))
                ax.text(p["x"], p["y"], pid, ha="center", va="center", fontsize=7,
                        weight="bold", color="white", zorder=5,
                        rotation=0 if p["wx"] >= p["hy"] else 90)
                xs0 = [q["x0"] for q in focos]; ys0 = [q["y0"] for q in focos]
                xs1 = [q["x0"] + q["wx"] for q in focos]
                ys1 = [q["y0"] + q["hy"] for q in focos]
                ax.set_xlim(min(xs0) - 0.3, max(xs1) + 0.3)
                ax.set_ylim(min(ys0) - 0.3, max(ys1) + 0.3)
                ax.set_aspect("equal")
                ax.axis("off")
                ax.set_title(f"{'PLANTA ALTA' if p['planta'] == 'alta' else 'PLANTA BAJA'}"
                             " — en AZUL la pieza de este paso", fontsize=10)

                axc = fig.add_axes([0.66, 0.42, 0.16, 0.50])
                if es_recorte:
                    _dibujo_corte(axc, material, b, pid, paso_de, corta_ahora)
                    axc.set_title((f"pieza {pc}-{idx:02d}: SE CORTA AHORA" if corta_ahora
                                   else f"pieza {pc}-{idx:02d} (cortada antes; estaba en reserva)"),
                                  fontsize=9, weight="bold",
                                  color="#c0392b" if corta_ahora else "#1e8449")
                else:
                    aB_, lB_ = PISOS[material]
                    axc.add_patch(Rectangle((0, 0), aB_, lB_, facecolor=AZUL,
                                            edgecolor="#1a5276", lw=1.5))
                    axc.text(aB_ / 2, lB_ / 2, f"{pid}\n{_fmt(p['wx'])}x{_fmt(p['hy'])}\nENTERA",
                             ha="center", va="center", fontsize=8, color="white",
                             weight="bold", rotation=90)
                    axc.set_xlim(-0.02, aB_ + 0.02)
                    axc.set_ylim(-0.02, lB_ + 0.02)
                    axc.set_aspect("equal")
                    axc.axis("off")
                    axc.set_title("PIEZA ENTERA (sin corte)", fontsize=9,
                                  weight="bold", color="#1e8449")

                axt = fig.add_axes([0.83, 0.06, 0.16, 0.86])
                axt.axis("off")
                org = origen_de.get(pid, "TABLA")
                lineas = [f"PASO {i} de {total}", "",
                          f"COLOCAR {pid}",
                          f"  {_fmt(p['wx'])}x{_fmt(p['hy'])}"]
                if es_recorte:
                    lineas.append(f"  {'corte de pieza nueva' if org == 'TABLA' else 'sale de la SOBRA de ' + org}")
                else:
                    lineas.append("  pieza entera, directo de caja")
                if corta_ahora:
                    otros = [etq for (x, y, w, l, etq, rot) in b.piezas if etq != pid]
                    if otros:
                        lineas += ["", f"al cortar {pc}-{idx:02d} salen", "también (a RESERVA):"]
                        for etq in otros:
                            dest = (f"paso {paso_de[etq]}" if etq in paso_de
                                    else "escalera" if etq[:1] in ("P", "H", "D")
                                    else "muro de baño")
                            lineas.append(f"  {etq} → {dest}")
                lineas.append("")
                if reserva:
                    lineas.append(f"EN RESERVA ({len(reserva)}):")
                    for (rid, rp) in reserva[:10]:
                        lineas.append(f"  {rid} → paso {rp}")
                    if len(reserva) > 10:
                        lineas.append(f"  … y {len(reserva)-10} más")
                axt.text(0.0, 1.0, "\n".join(lineas), va="top", fontsize=6.8,
                         family="monospace", transform=axt.transAxes, color="#1b2631")

                m2_g = sum(w * l for (w, l, _t, _p) in guardadas)
                reg = ["SOBRAS GUARDADAS:", f"{len(guardadas)} · {m2_g:.2f} m²", ""]
                for (w, l, t_, pas) in guardadas[-8:]:
                    reg.append(f"{_fmt(w)}x{_fmt(l)} (de {pc}-{t_:02d}, paso {pas})")
                if len(guardadas) > 8:
                    reg.append(f"… y {len(guardadas)-8} más")
                reg += ["", f"merma acum.: {merma_acum:.2f} m²"]
                axt.text(0.0, 0.30, "\n".join(reg), va="top", fontsize=6.4,
                         family="monospace", transform=axt.transAxes, color="#5d4037")

                fig.suptitle(f"COLOCACIÓN · {modelo.upper()} · {material.upper()} — "
                             f"PASO {i} de {total}: {pid}",
                             fontsize=13, weight="bold", y=0.985)
                fig.text(0.5, 0.015,
                         f"{PIE}        Guía de colocación — {modelo}        {FECHA}",
                         ha="center", fontsize=7.5, color="#777")
                pdf.savefig(fig)
                plt.close(fig)
                total_pags += 1

                # actualizar estado
                colocadas.add(pid)
                if corta_ahora:
                    cortadas.add(idx)
                    for (x, y, w, l, etq, rot) in b.piezas:
                        if etq != pid and etq in paso_de:
                            reserva.append((etq, paso_de[etq]))
                    for (fx, fy, fw, fl, *_z) in b.libres:
                        if fw <= 0.005 or fl <= 0.005:
                            continue
                        if es_reutilizable(fw, fl):
                            guardadas.append((fw, fl, idx, i))
                        else:
                            merma_acum += fw * fl
                reserva = [(rid, rp) for (rid, rp) in reserva if rid != pid]
                reserva.sort(key=lambda t: t[1])

            # piezas que quedaron sin cortar: solo cortes de escalera/regadera
            pendientes = [idx for idx in range(1, len(baldosas) + 1)
                          if idx not in cortadas]
            if pendientes and material == "Moret":
                fig = plt.figure(figsize=(13.5, 8.0))
                fig.suptitle(f"CORTES FINALES · {modelo.upper()} · MORET — piezas solo de"
                             " ESCALERA / MUROS DE BAÑO", fontsize=13, weight="bold")
                n = len(pendientes)
                cols = min(6, n)
                rows = (n + cols - 1) // cols
                for k, idx in enumerate(pendientes):
                    axc = fig.add_axes([0.04 + (k % cols) * 0.16,
                                        0.72 - (k // cols) * 0.42, 0.12, 0.34])
                    _dibujo_corte(axc, material, baldosas[idx - 1], None, paso_de, True)
                    axc.set_title(f"{pc}-{idx:02d}", fontsize=8, weight="bold")
                fig.text(0.5, 0.04, "Estas piezas se abren SOLO para la escalera y los"
                         " muros de baño (ver su despiece); se pueden cortar al final"
                         " o cuando toque ese frente.", ha="center", fontsize=9,
                         color="#555")
                pdf.savefig(fig)
                plt.close(fig)
                total_pags += 1
    print(f"-> {salida}  ({total_pags} páginas)")
    return salida


if __name__ == "__main__":
    import sys
    for m in (sys.argv[1:] or ["Cabernet", "Merlot", "Chardonnay"]):
        hacer(m)
