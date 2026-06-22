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


def _recorte(material, x0, y0, wx, hy):
    """Recorte faltante (el DWG no cerró la polilínea); _retipo lo completa."""
    return {"material": material, "x0": round(x0, 3), "y0": round(y0, 3),
            "wx": round(wx, 3), "hy": round(hy, 3),
            "x": round(x0 + wx / 2, 3), "y": round(y0 + hy / 2, 3), "extra": True}

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
        "piezas_extra": [
            _ARRANQUE_CABERNET,
            # Recortes de Moret que el DWG dejó vacíos (terminar hasta el muro):
            _recorte("Moret", 504.526, -86.254, 0.540, 1.194),   # izq. de PA-M-006 (≈ idéntico)
            _recorte("Moret", 502.744, -85.498, 0.600, 0.520),   # arriba de PA-M-010
            _recorte("Moret", 506.008, -88.624, 0.210, 1.194),   # der. de PA-M-035 (corte de muro)
            _recorte("Moret", 494.955, -91.520, 0.250, 1.194),   # der. de PB-M-147 hacia el baño
            _recorte("Moret", 495.389, -91.460, 0.170, 1.120),   # izq. de PB-M-135
            _recorte("Moret", 495.389, -92.530, 0.170, 1.068),   # izq. de PB-M-151
            _recorte("Moret", 502.654, -85.960, 0.090, 0.900),   # der. de PA-M-005 (junto al Royal)
            _recorte("Moret", 506.010, -89.730, 0.214, 0.600),   # debajo de PA-M-050 (izq. del muro/jamba)
            _recorte("Moret", 506.344, -89.730, 0.268, 0.600),   # debajo de PA-M-050 (der. del muro/jamba)
            _recorte("Moret", 495.205, -91.240, 0.184, 0.900),   # continuidad PB-M-136 <-> PB-M-122 (puerta)
        ],
        # Tiritas de 3 cm que en realidad son piezas casi enteras de la 1a columna,
        # PB-M-150 hasta la esquina, y unir PA-M-003+009 (la línea no es muro) hasta PA-M-005:
        "redimensionar": [
            {"x": 490.12, "y": -83.77, "x0": 489.539, "y0": -84.346, "wx": 0.600, "hy": 1.146},  # arriba de PB-M-054
            {"x": 490.12, "y": -92.05, "x0": 489.539, "y0": -92.572, "wx": 0.600, "hy": 1.050},  # izq. de PB-M-159
            {"x": 497.47, "y": -91.94, "x0": 497.365, "y0": -92.530, "wx": 0.214, "hy": 1.068},  # PB-M-150 a la esquina
            {"x": 504.20, "y": -85.68, "x0": 503.946, "y0": -85.860, "wx": 0.580, "hy": 0.800},  # unir PA-M-009+003 y dar continuidad a PA-M-005
        ],
        "eliminar": [
            (504.20, -85.28),    # PA-M-003: se absorbe en la pieza unida (009)
        ],
        # Recámaras: alinear el tope de cada columna de Royal con el muro de arriba.
        "tope_royal_regiones": [
            (499.70, 502.75, -87.0, -82.0),   # recámara 1 (izquierda)
            (502.80, 508.00, -85.0, -82.0),   # recámara principal (derecha)
        ],
        "reclasificar": [
            {"x": 503.04, "y": -84.90, "material": "Moret", "completa": False},
            # Tiras delgadas en la orilla de las recámaras: son Royal Walnut, no Moret.
            {"x": 507.79, "y": -83.17, "material": "Royal Walnut", "completa": False},
            {"x": 507.79, "y": -84.33, "material": "Royal Walnut", "completa": False},
            {"x": 502.61, "y": -85.51, "material": "Royal Walnut", "completa": False},
            {"x": 504.08, "y": -90.36, "material": "Royal Walnut", "completa": False},
            {"x": 507.76, "y": -90.47, "material": "Royal Walnut", "completa": False},
            {"x": 507.78, "y": -91.62, "material": "Royal Walnut", "completa": False},
            {"x": 507.78, "y": -92.78, "material": "Royal Walnut", "completa": False},
        ],
        # Zonas que NO se despiezan: escalera (dos hileras), boiler y el hueco de
        # cancelería (tira de 8 cm). Se excluyen por ubicación.
        "cajas_excluir": [
            (499.70, 502.80, -89.10, -86.70),   # escalera
            (496.70, 497.60, -88.65, -88.00),   # boiler
            (489.00, 497.00, -83.21, -83.11),   # hueco de cancelería (tira de 8 cm)
            (496.10, 496.60, -91.47, -91.40),   # tiritas de 4 cm (polilínea no cerrada) der. de PB-M-135
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
        "reclasificar": [
            # Tiras de orilla de recámaras que salieron Moret -> son Royal Walnut.
            {"x": 326.05, "y": -125.05, "material": "Royal Walnut"},
            {"x": 326.05, "y": -124.23, "material": "Royal Walnut"},
            {"x": 326.05, "y": -123.03, "material": "Royal Walnut"},
            {"x": 326.05, "y": -121.83, "material": "Royal Walnut"},
            {"x": 326.05, "y": -121.05, "material": "Royal Walnut"},
            {"x": 333.56, "y": -125.05, "material": "Royal Walnut"},
            {"x": 333.56, "y": -124.23, "material": "Royal Walnut"},
            {"x": 333.56, "y": -123.03, "material": "Royal Walnut"},
            {"x": 333.56, "y": -121.83, "material": "Royal Walnut"},
            {"x": 333.56, "y": -121.05, "material": "Royal Walnut"},
            {"x": 333.56, "y": -131.62, "material": "Royal Walnut"},
            {"x": 333.56, "y": -130.56, "material": "Royal Walnut"},
            {"x": 333.56, "y": -129.35, "material": "Royal Walnut"},
            {"x": 333.56, "y": -128.71, "material": "Royal Walnut"},
        ],
        # Pasillo (x≈329) = Moret, no Royal. Incluye su parte de arriba.
        "forzar_material": [
            {"box": (328.85, 329.30, -130.60, -121.00), "material": "Moret"},
        ],
        # Fantasmas (polilínea mal cerrada): se eliminan.
        "eliminar": [
            (330.04, -123.82),   # tira de 3.7 cm
            (326.05, -125.36),   # fragmento suelto en orilla
        ],
        # PA-M-043 salió como tira de 3 cm porque una LINTERNILLA (tragaluz) se
        # tomó como muro; en realidad es casi pieza completa.
        "redimensionar": [
            {"x": 331.09, "y": -126.79, "x0": 331.079, "y0": -127.385, "wx": 0.598, "hy": 1.194},
        ],
        "muros_ignorar": [
            (331.05, 331.70, -127.70, -126.20),   # linternilla junto a PA-M-043
        ],
        # Baño de planta baja (claves 5/5 = Urbania): el despiece dejó el Moret
        # continuo; ese piso es otro material, se excluye. (Por confirmar.)
        "cajas_excluir": [
            (322.30, 324.10, -129.05, -128.00),   # baño P.B.
        ],
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
        "piezas_extra": [
            _recorte("Moret", 277.503, -67.672, 0.180, 0.750),   # continuidad PB-M-120 <-> PB-M-106 (puerta)
        ],
        "reclasificar": [
            # Tiras de orilla de recámaras que salieron Moret -> Royal Walnut.
            {"x": 282.84, "y": -64.26, "material": "Royal Walnut"},
            {"x": 282.84, "y": -63.47, "material": "Royal Walnut"},
            {"x": 282.84, "y": -62.27, "material": "Royal Walnut"},
            {"x": 282.84, "y": -61.20, "material": "Royal Walnut"},
            {"x": 289.20, "y": -66.41, "material": "Royal Walnut"},
            {"x": 288.02, "y": -70.24, "material": "Royal Walnut"},
            {"x": 291.33, "y": -70.09, "material": "Royal Walnut"},
            {"x": 291.33, "y": -68.89, "material": "Royal Walnut"},
            {"x": 291.33, "y": -67.69, "material": "Royal Walnut"},
            {"x": 291.33, "y": -66.71, "material": "Royal Walnut"},
            # Piezas que salieron Royal pero son de pasillo/transición -> Moret.
            {"x": 287.23, "y": -64.63, "material": "Moret"},
            {"x": 288.14, "y": -64.78, "material": "Moret"},
            {"x": 288.14, "y": -65.54, "material": "Moret"},
            {"x": 288.14, "y": -66.49, "material": "Moret"},
            {"x": 288.89, "y": -66.49, "material": "Moret"},
        ],
        # Fantasmas / donde va muro: se eliminan.
        "eliminar": [
            (272.75, -70.78),   # PB: va muro
            (273.36, -70.78),   # PB: va muro
            (272.75, -60.64),   # PB: no debe existir
        ],
        # Baño de planta baja (claves 5/5/2/4 = Urbania/Malla/concreto): el
        # despiece dejó el Moret continuo cruzando el muro; ese piso es otro
        # material, se excluye.
        "cajas_excluir": [
            (277.85, 281.25, -67.00, -65.78),   # baño P.B.
        ],
    },
}
