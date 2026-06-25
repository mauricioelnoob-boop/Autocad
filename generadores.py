#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generadores.py — Números generadores por material y prototipo.

Cubre: Piso Moret, Piso Royal, Zoclo Moret, Zoclo Royal, Urbania White
(lavandería), Malla Lyndhurst (charola/regadera) y piso en muro de
regadera (Moret vertical).

Zoclo: metros lineales tomados del Excel del cliente; alto SIEMPRE 0.15 m,
largo 1.20 m (en esquinas se ajusta).  Pisos: área medida del despiece.
Urbania 0.30x0.45 (horizontal).  Malla ~1.5 m2 por charola.  Muro de
regadera: alto = NPT - losa (P.B. 2.75 m, P.A. 2.90 m), 3 caras, Moret.
"""
import math, json
from collections import defaultdict
from optimizador_recortes import PISOS
from datos_piezas import cargar_anotado

# Medidas de pieza (m)
MORET=(1.194,0.596); ROYAL=(1.200,0.200)
M_M2=MORET[0]*MORET[1]              # 0.7116 m2/pieza
R_M2=ROYAL[0]*ROYAL[1]             # 0.24
MORET_CAJA=1.4232; MORET_PZCAJA=2
ROYAL_CAJA=1.20;   ROYAL_PZCAJA=5
URB=(0.45,0.30); URB_M2=URB[0]*URB[1]  # 0.135 m2/pieza (Urbania White)
URB_PZCAJA=10; URB_CAJA=1.36
MALLA=(0.60,0.30); MALLA_M2=MALLA[0]*MALLA[1]   # 0.18 m2/pieza (Malla Lyndhurst)
ZOCLO_ALTO=0.15; ZOCLO_LARGO=1.20
MALLA_M2_CHAROLA=1.5

# Parámetros por modelo. zoclo ml = Excel del cliente. Urbania (lavandería) ~10 m2
# (dato del cliente). Regaderas: cantidad confirmada y su planta (altura = NPT-losa:
# P.B.=2.75 m, P.A.=2.90 m). Muro de regadera = 3 caras (ancho 1.20 + fondo 1.50 x2).
GEN={
 'Cabernet':  {'zoclo_m':77.69,'zoclo_r':41.42,'urbania_m2':10.0,
               'regaderas':[('P.A.',2.90),('P.A.',2.90)]},
 'Merlot':    {'zoclo_m':58.37,'zoclo_r':40.58,'urbania_m2':10.0,
               'regaderas':[('P.A.',2.90),('P.A.',2.90)]},
 'Chardonnay':{'zoclo_m':93.00,'zoclo_r':30.61,'urbania_m2':10.0,
               'regaderas':[('P.B.',2.75),('P.A.',2.90),('P.A.',2.90)]},
}
REG_PERIM=3.90    # ml de muro enchapado por regadera (3 caras: fondo 1.50 + 2 lados 1.20)
REG_FONDO=1.50    # ancho del muro de fondo de la regadera (m)
VENTANA_ALTO=0.90 # alto de la ventana (pegada al plafon, del ancho del fondo)
VENTANA_M2=REG_FONDO*VENTANA_ALTO  # ventana = ancho del fondo (1.50) x 0.90 = 1.35 m2
NICHO_PROF=0.09   # profundidad del nicho (m)
NICHO_ANCHO=0.90  # ancho del nicho (m)
NICHO_ALTO=0.30   # alto del nicho (m)

def area_piso(modelo):
    ps=cargar_anotado(modelo)
    am=sum(p['wx']*p['hy'] for p in ps if p['material']=='Moret')
    ar=sum(p['wx']*p['hy'] for p in ps if p['material']=='Royal Walnut')
    return am,ar

def zoclo(ml, caja_m2):
    pzas=math.ceil(ml/ZOCLO_LARGO)
    m2=pzas*ZOCLO_LARGO*ZOCLO_ALTO
    cajas=math.ceil(m2/caja_m2)
    return pzas,m2,cajas

def reporte(modelo):
    g=GEN[modelo]; am,ar=area_piso(modelo)
    R=[]
    R.append(('PISO Moret Arena (0.596x1.194)', f'{am:.2f} m2', f'{math.ceil(am*1.1/MORET_CAJA)} cajas (+10%)'))
    R.append(('PISO Royal Walnut (0.20x1.20)', f'{ar:.2f} m2', f'{math.ceil(ar*1.07/ROYAL_CAJA)} cajas (+7%)'))
    zp,zm2,zc=zoclo(g['zoclo_m'],MORET_CAJA)
    R.append(('ZOCLO Moret (1.20x0.15)', f'{g["zoclo_m"]:.1f} ml -> {zp} pzas / {zm2:.2f} m2', f'{math.ceil(zc*1.1)} cajas (+10%)'))
    zp,zm2,zc=zoclo(g['zoclo_r'],ROYAL_CAJA)
    R.append(('ZOCLO Royal (1.20x0.15)', f'{g["zoclo_r"]:.1f} ml -> {zp} pzas / {zm2:.2f} m2', f'{math.ceil(zc*1.07)} cajas (+7%)'))
    up=math.ceil(g['urbania_m2']/URB_M2)
    R.append(('URBANIA WHITE lavandería (0.30x0.45)', f'{g["urbania_m2"]:.2f} m2 -> {up} pzas', f'{math.ceil(g["urbania_m2"]*1.1/URB_CAJA)} cajas (+10%, 10 pz/caja)'))
    nch=len(g['regaderas']); mm2=nch*MALLA_M2_CHAROLA; mp=math.ceil(mm2/MALLA_M2)
    R.append(('MALLA LYNDHURST charolas (0.30x0.60)', f'{nch} charolas x 1.5 m2 = {mm2:.2f} m2 -> {mp} pzas', f'{mp} pzas (+desperdicio)'))
    # piso en muro de regadera y ESCALERA (Moret acostado) — del despiece real
    try:
        import despiece_extra as DE
        reg=DE.regadera_resumen(modelo); esc=DE.escalera_resumen(modelo)
        R.append(('PISO EN MURO DE REGADERA (Moret, 3 caras)',
                  f'{nch} reg (fondo 1.50 + 2 lados 1.20) - ventana = {reg["m2"]:.2f} m2',
                  f'{reg["cajas"]} cajas (+10%)'))
        R.append(('PISO EN ESCALERA (Moret, peralte 0.175)',
                  f'{esc["n_peraltes"]} peraltes + {esc["n_huellas"]} huellas x 1.20 m = {esc["m2"]:.2f} m2',
                  f'{esc["cajas"]} cajas (+10%)'))
    except Exception:
        bruto=sum(REG_PERIM*h for _,h in g['regaderas'])
        wm2=max(0.0, bruto - nch*VENTANA_M2); wp=math.ceil(wm2/M_M2)
        R.append(('PISO EN MURO DE REGADERA (Moret)', f'{nch} reg - ventana = {wm2:.2f} m2 -> {wp} pzas', f'{math.ceil(wm2*1.1/MORET_CAJA)} cajas (+10%)'))
    return R

if __name__=='__main__':
    import sys
    for m in (sys.argv[1:] or ['Cabernet','Merlot','Chardonnay']):
        print('='*70); print(m); print('='*70)
        for c,a,b in reporte(m):
            print(f'  {c:42}{a:34}{b}')
