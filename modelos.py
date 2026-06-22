#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
modelos.py
==========

Configuración por prototipo de casa. Todo lo específico de cada modelo
(corte entre plantas, regiones de recámaras con Royal Walnut, piezas faltantes,
correcciones puntuales) vive aquí. Las medidas de pieza y las cajas son
compartidas (en optimizador_recortes.py: PISOS y CAJAS).

Regla de material (planta alta):
  * Una pieza es Royal Walnut sólo si es un tablón de ~0.20 m DENTRO de una
    región de recámara. Las piezas de ~0.60 m (baño/vestidor) siempre son Moret,
    aunque caigan dentro de la caja de la recámara (esto protege el baño).
  * Todo lo demás (planta baja, pasillo, vestidor, escalera) es Moret.
"""

# Arranque de Moret en planta baja de Cabernet que no quedó dibujado.
_ARRANQUE_CABERNET = {
    "material": "Moret", "ancho": 0.596, "largo": 1.194, "completa": True,
    "tipo_corte": "completa", "x": 489.84, "y": -86.14,
    "x0": 489.539, "y0": -86.738, "wx": 0.600, "hy": 1.194, "extra": True,
}

MODELOS = {
    "Cabernet": {
        "dwg": "planos/cabernet.dwg",
        "json": "/tmp/cabernet.json",
        "piezas": "piezas_cabernet.json",
        "muros": "muros_cabernet.json",
        "claves": "claves_cabernet.json",
        "capa": "A-PISO",
        "x_corte": 498.7,            # planta baja: x < x_corte
        "bbox_valido": None,         # sin bloques sueltos
        "regiones_royal": [
            (499.4, 508.2, -86.70, -81.80),   # Recámara 1 + principal (baño 0.6 = Moret)
            (504.0, 508.2, -93.50, -89.60),   # Recámara 2
        ],
        "excluir_royal_baja": True,  # charolas de baño en planta baja = otro piso
        "piezas_extra": [_ARRANQUE_CABERNET],
        "reclasificar": [
            {"x": 503.04, "y": -84.90, "material": "Moret", "completa": False},
        ],
    },
    "Merlot": {
        "dwg": "planos/merlot.dwg",
        "json": "/tmp/merlot.json",
        "piezas": "piezas_merlot.json",
        "muros": "muros_merlot.json",
        "claves": "claves_merlot.json",
        "capa": "A-PISO",
        "x_corte": 325.0,
        "bbox_valido": (300.0, 400.0, -200.0, 100.0),   # descarta bloque suelto en (145,58)
        "regiones_royal": [
            (325.9, 329.4, -125.6, -120.6),
            (330.1, 333.8, -125.5, -120.6),
            (329.6, 333.8, -132.3, -128.4),
        ],
        "excluir_royal_baja": True,
        "piezas_extra": [],
        "reclasificar": [],
    },
    "Chardonnay": {
        "dwg": "planos/chardonnay.dwg",
        "json": "/tmp/chardonnay.json",
        "piezas": "piezas_chardonnay.json",
        "muros": "muros_chardonnay.json",
        "claves": "claves_chardonnay.json",
        "capa": "A-PISO",
        "x_corte": 281.9,
        "bbox_valido": None,
        "regiones_royal": [
            (282.6, 288.1, -64.85, -60.55),
            (287.9, 291.45, -70.85, -66.15),
        ],
        "excluir_royal_baja": True,
        "piezas_extra": [],
        "reclasificar": [],
    },
}
