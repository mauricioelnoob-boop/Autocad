#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validar.py
==========
Pase de validación que FALLA FUERTE (exit != 0). Antes el pipeline podía emitir
un despiece con piezas sobre muros, solapadas o con huecos y nadie se enteraba
(los fallbacks de geometría devolvían la pieza sin tocar en silencio). Esto
convierte "se ve bien en estos 3 planos" en "es demostrablemente correcto o se
niega a entregar".

Chequeos por modelo (sobre las piezas ya anotadas, con notch):
  1. HUECOS    : ninguna zona interior de la casa sin piso.
  2. SOLAPES   : ninguna pieza se encima con otra (> tolerancia).
  3. EN MURO   : ninguna pieza de piso cae dentro de un muro/escalera.
  4. ÁREA      : suma de áreas de piezas ≈ área de la unión (auto-consistencia;
                 si hubiera doble conteo o solape, no cuadra).
  5. CORRECCIONES: cada corrección manual de modelos.py (redimensionar/eliminar/
                 reclasificar) encontró exactamente UNA pieza; si 0 o varias,
                 se reporta (lo expone cargar_anotado.correcciones_ambiguas).

Uso:  python3 validar.py [Modelo ...]      (sin args = los 3)
Salida: imprime un reporte y termina con código != 0 si algún modelo falla.
"""
import sys
from shapely.geometry import box, Polygon
from shapely.ops import unary_union

from datos_piezas import cargar_anotado, _mascara_muros
from modelos import MODELOS
from verificar_huecos import huecos as _huecos

SOLAPE_TOL = 0.002      # m² — por debajo es ruido de redondeo
MURO_TOL = 0.010        # m² de pieza dentro de muro que se tolera (boquilla)
AREA_TOL = 0.02         # 2 % de descuadre suma vs unión


def _poly(p):
    g = box(p["x0"], p["y0"], p["x0"] + p["wx"], p["y0"] + p["hy"])
    for ring in (p.get("notch") or []):
        try:
            g = g.difference(Polygon(ring))
        except Exception:
            pass
    return g


def validar(modelo):
    """Devuelve (problemas, métricas). problemas = lista de strings (vacía = OK)."""
    problemas = []
    todas = cargar_anotado(modelo)
    # capturar correcciones ambiguas de ESTA corrida antes de re-llamar
    amb = list(getattr(cargar_anotado, "correcciones_ambiguas", []))
    polys = [(p, _poly(p)) for p in todas]

    # 1) HUECOS interiores
    _, gaps = _huecos(modelo)
    if gaps:
        problemas.append(f"{len(gaps)} hueco(s) interior(es) sin piso "
                         f"(p.ej. {gaps[0].centroid.x:.1f},{gaps[0].centroid.y:.1f})")

    # 2) SOLAPES
    n_sol = 0; area_sol = 0.0; ej = None
    for i in range(len(polys)):
        gi = polys[i][1]
        for j in range(i + 1, len(polys)):
            gj = polys[j][1]
            if not gi.intersects(gj):
                continue
            a = gi.intersection(gj).area
            if a > SOLAPE_TOL:
                n_sol += 1; area_sol += a
                if ej is None:
                    ej = (polys[i][0].get("id"), polys[j][0].get("id"), a)
    if n_sol:
        problemas.append(f"{n_sol} solape(s), {area_sol:.3f} m² "
                         f"(p.ej. {ej[0]}↔{ej[1]} = {ej[2]:.3f} m²)")

    # 3) PIEZAS DENTRO DE MURO
    muros = _mascara_muros(MODELOS[modelo])
    n_muro = 0
    if muros is not None and not muros.is_empty:
        for p, g in polys:
            if g.intersection(muros).area > MURO_TOL:
                n_muro += 1
        if n_muro:
            problemas.append(f"{n_muro} pieza(s) de piso dentro de un muro/escalera")

    # 4) ÁREA: suma vs unión
    suma = sum(g.area for _, g in polys)
    union = unary_union([g for _, g in polys]).area
    if union > 0 and abs(suma - union) / union > AREA_TOL:
        problemas.append(f"área no cuadra: suma {suma:.2f} vs unión {union:.2f} m² "
                         f"({100*(suma-union)/union:+.1f} %)")

    # 5) CORRECCIONES: "sin match" / "no hay piezas" = FATAL (corrección muerta o
    #    mal puesta); "empate" = AVISO (aplicó bien, pero el punto está cerca de 2
    #    piezas y conviene moverlo) — no tumba la entrega.
    avisos = []
    for c in amb:
        if "empate" in c:
            avisos.append(c)
        else:
            problemas.append(f"corrección sin aplicar: {c}")

    metr = {"piezas": len(todas), "huecos": len(gaps), "solapes": n_sol,
            "en_muro": n_muro, "suma_m2": round(suma, 2), "union_m2": round(union, 2)}
    return problemas, avisos, metr


def main(modelos):
    fallo = False
    for m in modelos:
        problemas, avisos, metr = validar(m)
        if problemas:
            fallo = True
            print(f"✗ {m}: {len(problemas)} problema(s)  {metr}")
            for pr in problemas:
                print(f"    ✗ {pr}")
        else:
            print(f"✓ {m}: OK  {metr}")
        for av in avisos:
            print(f"    ⚠ aviso: {av}")
    if fallo:
        print("\nVALIDACIÓN FALLÓ — no entregar hasta corregir.")
        sys.exit(1)
    print("\nVALIDACIÓN OK — los 3 modelos pasan todos los chequeos (huecos, "
          "solapes, muros, área y correcciones).")


if __name__ == "__main__":
    main(sys.argv[1:] or ["Cabernet", "Merlot", "Chardonnay"])
