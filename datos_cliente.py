#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
datos_cliente.py
================
FUENTE ÚNICA DE VERDAD de todos los datos que NO se calculan del DWG, sino que
vienen del presupuesto/cliente o son supuestos de obra. Antes estaban duplicados
y dispersos (PRESUP en pdf_extra.py, RECIBIDO en inventario_excel.py, BUDGET_PCT
suelto), lo que permitía que el paquete se contradijera a sí mismo. Todo módulo
que necesite estos números los importa DE AQUÍ.

PROCEDENCIA (de dónde sale cada dato — actualizar si cambia el presupuesto):
  - SUMINISTRADO  : cajas/piezas que el PRESUPUESTO del cliente surte por modelo
                    (base + % de desperdicio presupuestado). Capturado del Excel
                    de presupuesto entregado por el cliente.
  - BUDGET_PCT    : % de desperdicio que el presupuesto aplica sobre la base
                    (declarado por el cliente: 3%). La "base" se deriva como
                    SUMINISTRADO / (1 + BUDGET_PCT).
  - LOTES         : lotes físicos suministrados y su modelo (control de obra).

Lo MEDIDO del plano (m² de piso, recortes, etc.) NO va aquí: se calcula del DWG.
Los m² de zoclo, urbania y las charolas viven en generadores.py (G.GEN) — un solo
lugar — y se documentan ahí; este módulo no los duplica.
"""

# % de desperdicio que trae el presupuesto sobre la base (dato del cliente).
BUDGET_PCT = 0.03

# Suministrado por modelo (cajas; Malla en piezas). Una sola definición.
# keys: Moret, Royal, Urbania, Malla
SUMINISTRADO = {
    "Cabernet":   {"Moret": 117, "Royal": 41, "Urbania": 8, "Malla": 28},
    "Merlot":     {"Moret": 98,  "Royal": 37, "Urbania": 8, "Malla": 17},
    "Chardonnay": {"Moret": 127, "Royal": 32, "Urbania": 8, "Malla": 28},
}

# Lotes físicos suministrados: (lote, manzana, modelo). Agregar cada lote nuevo.
LOTES = [
    (34, 14, "Cabernet"),
    (9,   7, "Merlot"),
    (10,  7, "Merlot"),
]


def presup(modelo):
    """Suministrado del modelo con las llaves históricas (incluye 'Malla_pz')."""
    s = SUMINISTRADO[modelo]
    return {"Moret": s["Moret"], "Royal": s["Royal"],
            "Urbania": s["Urbania"], "Malla_pz": s["Malla"]}


# Compatibilidad: PRESUP con el mismo esquema que usaba pdf_extra.py.
PRESUP = {m: presup(m) for m in SUMINISTRADO}
