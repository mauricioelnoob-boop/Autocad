#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generadores.py — Números generadores por material y prototipo.

Cubre: Piso Moret, Piso Royal, Zoclo Moret, Zoclo Royal, Urbania White
(lavandería), Malla Lyndhurst (charola/regadera) y piso en muro de
regadera (Moret vertical).

Zoclo: metros lineales tomados del Excel del cliente. El zoclo Moret se corta a
lo ALTO del mismo tablón (0.596 m). Council (APROBADO_CON_AJUSTE): a 0.146 m, con
kerf de sierra de 3 mm y 3 cortes internos, salen 4 tiras por tablón
(4*0.146 + 3*0.003 = 0.593 <= 0.596, con holgura). A 0.149 NO caben 4 (el kerf lo
tumba a 3) y a 0.15 sólo salen 3 (se tira 0.146 m, ~25%). El conteo es por
RENDIMIENTO-POR-TABLÓN (no por área): contar por área asume uso 100% del tablón y
SUBESTIMA cajas — fue una de las causas del faltante en Cabernet.
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
TABLON_W=0.596          # alto del tablón Moret (de donde se corta el zoclo a lo alto)
ZOCLO_KERF=0.003        # kerf de sierra (peor caso típico) — 3 cortes para 4 tiras
ZOCLO_ALTO=0.146        # Council: altura que SÍ rinde 4 tiras/tablón contando kerf
ZOCLO_LARGO=1.194       # largo real de la tira (= largo del tablón)
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

def tiras_por_tablon(alto_tablon, H=ZOCLO_ALTO, kerf=ZOCLO_KERF):
    """Cuántas tiras de alto H salen de un tablón de 'alto_tablon', contando el
    kerf de los cortes internos: n tiras necesitan (n-1) cortes, así que
    n*H + (n-1)*kerf <= alto_tablon  ->  n = floor((alto_tablon+kerf)/(H+kerf))."""
    return max(1, int((alto_tablon + kerf) / (H + kerf) + 1e-9))

def zoclo(ml, caja_m2):
    """Cajas de zoclo por RENDIMIENTO-POR-TABLÓN (no por área). El zoclo se corta a
    lo alto del tablón; Moret rinde 4 tiras/tablón a 0.146 con kerf (Council),
    Royal 1 tira/tablón (tablón de 0.20). Devuelve (pzas, m2, cajas)."""
    if abs(caja_m2 - MORET_CAJA) < 1e-6:
        alto_tablon, pzcaja, largo_tira = MORET[1], MORET_PZCAJA, ZOCLO_LARGO   # 0.596
    else:
        alto_tablon, pzcaja, largo_tira = ROYAL[1], ROYAL_PZCAJA, 1.20          # 0.20
    pzas=math.ceil(ml/largo_tira)
    zpt=tiras_por_tablon(alto_tablon)
    tablones=math.ceil(pzas/zpt)
    cajas=math.ceil(tablones/pzcaja)
    m2=pzas*largo_tira*ZOCLO_ALTO
    return pzas,m2,cajas

def reporte(modelo):
    g=GEN[modelo]; am,ar=area_piso(modelo)
    R=[]
    R.append(('PISO Moret Arena (0.596x1.194)', f'{am:.2f} m2', f'{math.ceil(am*1.1/MORET_CAJA)} cajas (+10%)'))
    R.append(('PISO Royal Walnut (0.20x1.20)', f'{ar:.2f} m2', f'{math.ceil(ar*1.07/ROYAL_CAJA)} cajas (+7%)'))
    zp,zm2,zc=zoclo(g['zoclo_m'],MORET_CAJA)
    R.append(('ZOCLO Moret (1.194x0.146, 4 tiras/tablón con kerf)', f'{g["zoclo_m"]:.1f} ml -> {zp} pzas / {math.ceil(zp/4)} tablones', f'{math.ceil(zc*1.1)} cajas (+10%)'))
    zp,zm2,zc=zoclo(g['zoclo_r'],ROYAL_CAJA)
    R.append(('ZOCLO Royal (1.20x0.146, 1 tira/tabla)', f'{g["zoclo_r"]:.1f} ml -> {zp} pzas', f'{math.ceil(zc*1.07)} cajas (+7%)'))
    up=math.ceil(g['urbania_m2']/URB_M2)
    R.append(('URBANIA WHITE lavandería (0.30x0.45)', f'{g["urbania_m2"]:.2f} m2 -> {up} pzas', f'{math.ceil(g["urbania_m2"]*1.1/URB_CAJA)} cajas (+10%, 10 pz/caja)'))
    nch=len(g['regaderas']); mm2=nch*MALLA_M2_CHAROLA; mp=math.ceil(mm2/MALLA_M2)
    R.append(('MALLA LYNDHURST charolas (0.30x0.60)', f'{nch} charolas x 1.5 m2 = {mm2:.2f} m2 -> {mp} pzas', f'{mp} pzas (+desperdicio)'))
    # piso en muro de regadera y ESCALERA (Moret acostado) — del despiece real
    try:
        import despiece_extra as DE
        reg=DE.regadera_resumen(modelo); esc=DE.escalera_resumen(modelo)
        R.append(('PISO MURO DE REGADERA (Moret, 3 caras)',
                  f'{nch} reg, 3 caras - ventana = {reg["m2"]:.1f} m2',
                  f'{reg["cajas"]} cajas (+10%)'))
        tr='+'.join(str(t) for t in esc['tramos'])
        R.append(('PISO EN ESCALERA (Moret)',
                  f'1.15m, peralte 0.175, huella 0.27, esc {tr} = {esc["m2"]:.1f} m2',
                  f'{esc["cajas"]} cajas (+15%)'))
        if esc.get('zoclo_orilla'):
            zml=5.0   # ml aprox. de la orilla de la escalera desde el 1er descanso (Chardonnay)
            zp,zm2,zc=zoclo(zml,MORET_CAJA)
            R.append(('ZOCLO ESCALERA Chardonnay (0.146, orilla al muro)',
                      f'~{zml:.1f} ml -> {zp} pzas', f'{math.ceil(zc*1.1)} cajas (+10%)'))
    except Exception:
        bruto=sum(REG_PERIM*h for _,h in g['regaderas'])
        wm2=max(0.0, bruto - nch*VENTANA_M2); wp=math.ceil(wm2/M_M2)
        R.append(('PISO EN MURO DE REGADERA (Moret)', f'{nch} reg - ventana = {wm2:.2f} m2 -> {wp} pzas', f'{math.ceil(wm2*1.1/MORET_CAJA)} cajas (+10%)'))
    # --- Totales y FALTANTE vs lo suministrado por el presupuesto ---
    t=totales(modelo); f=faltante(modelo)
    R.append(('TOTAL Moret REQUERIDO (con desperdicio real de corte)',
              f'piso {t["Moret"]["piso"]} + zoclo {t["Moret"]["zoclo"]} + regadera {t["Moret"]["regadera"]} + escalera {t["Moret"]["escalera"]+t["Moret"]["zoclo_esc"]}',
              f'{t["Moret"]["total"]} cajas'))
    R.append(('TOTAL Royal REQUERIDO',
              f'piso {t["Royal"]["piso"]} + zoclo {t["Royal"]["zoclo"]}', f'{t["Royal"]["total"]} cajas'))
    for mat in ('Moret','Royal'):
        fm=f[mat]; falta=fm['falta']
        est = f'FALTAN {falta} cajas' if falta>0 else (f'sobran {-falta}' if falta<0 else 'EXACTO')
        R.append((f'FALTANTE {mat} (vs suministrado)',
                  f'requerido {fm["req"]} - suministrado {fm["sum"]}', est))
    return R

def totales(modelo):
    """Cajas REQUERIDAS por material, ya con margen, contando el desperdicio real
    de corte (zoclo/regadera/escalera por rendimiento-por-tablón, no por área)."""
    import despiece_extra as DE
    g=GEN[modelo]; am,ar=area_piso(modelo)
    piso_m=math.ceil(am*1.1/MORET_CAJA)
    piso_r=math.ceil(ar*1.07/ROYAL_CAJA)
    _,_,zm=zoclo(g['zoclo_m'],MORET_CAJA); zm=math.ceil(zm*1.1)
    _,_,zr=zoclo(g['zoclo_r'],ROYAL_CAJA); zr=math.ceil(zr*1.07)
    e=DE.escalera_resumen(modelo); reg=DE.regadera_resumen(modelo)['cajas']; esc=e['cajas']
    zesc=0
    if e.get('zoclo_orilla'):
        _,_,zc=zoclo(5.0,MORET_CAJA); zesc=math.ceil(zc*1.1)
    return {
        'Moret':{'piso':piso_m,'zoclo':zm,'regadera':reg,'escalera':esc,'zoclo_esc':zesc,
                 'total':piso_m+zm+reg+esc+zesc},
        'Royal':{'piso':piso_r,'zoclo':zr,'total':piso_r+zr},
    }

def faltante(modelo):
    """Compara lo REQUERIDO (totales, con desperdicio real) contra lo SUMINISTRADO
    por el presupuesto. Positivo en 'falta' = cajas que harán falta en obra."""
    from datos_cliente import SUMINISTRADO
    t=totales(modelo); s=SUMINISTRADO[modelo]
    return {'Moret':{'req':t['Moret']['total'],'sum':s['Moret'],'falta':t['Moret']['total']-s['Moret']},
            'Royal':{'req':t['Royal']['total'],'sum':s['Royal'],'falta':t['Royal']['total']-s['Royal']}}

if __name__=='__main__':
    import sys
    for m in (sys.argv[1:] or ['Cabernet','Merlot','Chardonnay']):
        print('='*70); print(m); print('='*70)
        for c,a,b in reporte(m):
            print(f'  {c:52}{a:40}{b}')
