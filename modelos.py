#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
modelos.py
==========

Configuración por prototipo de casa. Todo lo específico de cada modelo
(corte entre plantas, regiones de recámaras con Royal Walnut, piezas faltantes,
correcciones puntuales) vive aquí. Las medidas de pieza y las cajas son
compartidas (en optimizador_recortes.py: PISOS y CAJAS).

NOTA: las llaves `regiones_royal` y `excluir_royal_baja` son DOCUMENTALES (de
referencia): el pipeline NO las lee. La clasificación Royal/Moret se decide por
las claves de A-ACABADOS ('3'/'4'/'5') + ancho del tablón y por `forzar_material`.

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
            # UMBRAL de la puerta bajo PB-M-015: hay vano con piso (A-PISO +
            # cerramiento proyectado) y el despiece dejó la franja sin pieza
            _recorte("Moret", 493.1507, -83.2604, 0.5960, 0.1800),

            _recorte("Moret", 494.955, -91.520, 0.250, 1.194),   # der. de PB-M-147 hacia el baño
            _recorte("Moret", 495.389, -91.460, 0.170, 1.120),   # izq. de PB-M-135
            _recorte("Moret", 495.389, -92.530, 0.170, 1.068),   # izq. de PB-M-151
            _recorte("Moret", 502.654, -85.960, 0.090, 0.900),   # der. de PA-M-005 (junto al Royal)
            _recorte("Moret", 503.944, -90.810, 0.090, 0.900),   # der. de PA-M-039/037: tirita de continuidad con la tira Royal PA-R-149
            _recorte("Moret", 506.010, -89.730, 0.214, 0.600),   # debajo de PA-M-050 (izq. del muro/jamba)
            _recorte("Moret", 506.344, -89.730, 0.268, 0.600),   # debajo de PA-M-050 (der. del muro/jamba)
            _recorte("Moret", 495.205, -91.240, 0.184, 0.900),   # continuidad PB-M-136 <-> PB-M-122 (puerta)
            # bolsa der. de PA-M-009: ancho hasta la cara de la jamba (x504.35) para
            # NO pisar el muro/jamba (detalle del usuario):
            # PA-M-011: pieza grande de abajo; su tope sube hasta la boquilla de
            # PA-M-001/010 (y=-85.496). Llega a x504.466; la jamba (x504.35, debajo
            # de y-85.86) la muerde sola como entrante vía la máscara de muros.
            _recorte("Moret", 503.946, -86.555, 0.520, 1.059),
            # tira Royal de la orilla derecha (arriba de PA-R-177): una sola pieza
            # que llega hasta el tope de la columna Royal (incluye el recortito de
            # arriba que el usuario marcó como parte de la misma pieza).
            _recorte("Royal Walnut", 507.742, -91.022, 0.072, 1.112),
        ],
        # Tiritas de 3 cm que en realidad son piezas casi enteras de la 1a columna,
        # PB-M-150 hasta la esquina, y unir PA-M-003+009 (la línea no es muro) hasta PA-M-005:
        "redimensionar": [
            {"x": 490.12, "y": -83.77, "x0": 489.539, "y0": -84.346, "wx": 0.600, "hy": 1.146},  # arriba de PB-M-054
            {"x": 506.117, "y": -87.084, "x0": 506.010, "y0": -87.428, "wx": 0.634, "hy": 0.688},  # recorte esquina escalera = UNA sola pieza hasta el borde de piso (x506.644)
            # Fila inferior PB-M-143..146: el dibujo las llevó a la cara EXTERIOR del
            # muro (-92.572); el muro de abajo tiene 0.18 de grosor y su cara interior
            # está en -92.530 (donde sí quedaron PB-M-140..142). Se acortan las 4 al
            # paño interior (obs. del usuario: "grosor del muro").
            {"x": 489.839, "y": -92.047, "x0": 489.539, "y0": -92.530, "wx": 0.600, "hy": 1.008},  # PB-M-143
            {"x": 490.441, "y": -92.047, "x0": 490.141, "y0": -92.530, "wx": 0.600, "hy": 1.008},  # PB-M-144
            {"x": 491.043, "y": -92.047, "x0": 490.743, "y0": -92.530, "wx": 0.600, "hy": 1.008},  # PB-M-145
            {"x": 491.645, "y": -92.047, "x0": 491.345, "y0": -92.530, "wx": 0.600, "hy": 1.008},  # PB-M-146
            {"x": 497.47, "y": -91.94, "x0": 497.365, "y0": -92.530, "wx": 0.214, "hy": 1.068},  # PB-M-150 a la esquina
            {"x": 504.20, "y": -85.68, "x0": 503.946, "y0": -85.496, "wx": 0.520, "hy": 0.436},  # PA-M-003: chica arriba, junta alineada con boquilla de 001/010 (y-85.496)
        ],
        "eliminar": [
            (504.20, -85.28),    # PA-M-003: se absorbe en la pieza unida (009)
        ],
        # Vano de puerta bajo PB-M-015: hay PISO real (A-PISO + cerramiento
        # proyectado) pero la máscara de muros lo tapaba y borraba el umbral
        # agregado en piezas_extra. Se abre SOLO la franja del vano en la
        # máscara final (cancel_ignorar es quirúrgico: resta la caja; NO usar
        # muros_ignorar aquí porque desactiva el polígono de muro COMPLETO
        # cuyo centro caiga en la caja).
        "cancel_ignorar": [
            (493.145, 493.755, -83.270, -83.070),
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
            (499.70, 502.80, -89.10, -86.70),   # escalera planta alta = vacío (A-ESCALON)
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
        # Recorte Moret en "L" (sigue el muro) que el DWG dejó vacío: el bbox de la
        # polilínea entra a la región Royal y el pipeline lo descartó. Se repone como
        # dos rectángulos que trazan la L (img.2, cuadro cian).
        "piezas_extra": [
            # PA-M-008 (baño con el muro): se repone como 2 rectángulos LIMPIOS,
            # uno bajo el muro y otro sobre el muro (no una "L" con entrante raro).
            _recorte("Moret", 329.847, -124.210, 0.430, 0.406),   # bajo el muro
            _recorte("Moret", 329.847, -123.624, 0.596, 0.608),   # sobre el muro
            _recorte("Moret", 330.445, -123.624, 0.112, 0.608),   # tira angosta sobre el muro
            _recorte("Moret", 323.635, -128.774, 0.433, 0.354),   # recorte chico debajo de PB-M-095 (esquina)
            # --- correcciones del usuario (detalle "mitad Royal a la puerta") ---
            # PA-R-099: le falta el recortito Royal a su DERECHA; topa el Moret a
            # media puerta (umbral de 0.09 m hacia el pasillo Moret M-007/M-010).
            _recorte("Royal Walnut", 328.907, -124.829, 0.090, 1.200),
            # PA-R-157: le falta el recortito Royal a su IZQUIERDA; topa el Moret
            # (M-042) en el umbral. Ancho 0.065 (tras redondeo a 3 decimales) para
            # NO solapar la pieza original a su derecha (borde 330.2767): queda un
            # pelo de junta < 1 mm, nunca encimado. Ambas piezas quedan intactas.
            _recorte("Royal Walnut", 330.211, -129.954, 0.065, 1.200),
            # Umbral de la puerta entre PB-M-120 y PB-M-109: tira que cruza el
            # grosor del muro (0.18) dentro del vano; las dos piezas vecinas ya
            # quedan al paño de su lado (ver redimensionar).
            _recorte("Moret", 322.2983, -129.734, 0.180, 0.7361),
        ],
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
            (330.06, -123.61),   # baldosa que el DWG dibujó ENCIMA del muro (PA-M-008):
                                 # se quita y la reponen los 2 rectángulos limpios de piezas_extra
        ],
        # PA-M-043 salió como tira de 3 cm porque una LINTERNILLA (tragaluz) se
        # tomó como muro; en realidad es casi pieza completa.
        "redimensionar": [
            {"x": 331.09, "y": -126.79, "x0": 331.079, "y0": -127.385, "wx": 0.598, "hy": 1.194},
            # PB-M-120 y PB-M-109 cruzaban el muro del vano (grosor 0.18, caras en
            # x=322.2983 / x=322.4783) envolviéndolo con entrantes: cada una se corta
            # al paño de SU lado y el umbral de la puerta se repone como recorte
            # aparte (mismo criterio que la puerta PB-M-136 <-> PB-M-122 de Cabernet).
            {"x": 322.139, "y": -129.595, "x0": 321.8407, "y0": -130.1919, "wx": 0.4576, "hy": 1.1940},  # PB-M-120 al paño izq.
            {"x": 322.737, "y": -129.433, "x0": 322.4783, "y0": -129.8671, "wx": 0.5564, "hy": 0.8692},  # PB-M-109 al paño der.
        ],
        "muros_ignorar": [
            (331.05, 331.70, -127.70, -126.20),   # linternilla junto a PA-M-043
        ],
        # Baño de planta baja (claves 5/5 = Urbania): el despiece dejó el Moret
        # continuo; ese piso es otro material, se excluye (confirmado: el baño P.B.
        # se excluye por caja; los recortes del cuarto de lavado se reponen aparte).
        "cajas_excluir": [
            # (era "baño P.B." — en realidad es el cuarto de lavado con piso Moret;
            #  el piso sigue hasta el muro, no se excluye)
            # planta baja: el piso va POR DEBAJO de la escalera, no se excluye.
            (325.90, 329.10, -128.10, -125.35),   # escalera planta alta = vacío (A-ESCALON)
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
            _recorte("Royal Walnut", 287.70, -61.215, 0.180, 0.483),  # mitad Royal junto a PA-M-001
            # recortes del cuarto de lavado, debajo de PB-M-088/089/090
            _recorte("Moret", 279.075, -66.142, 0.600, 0.316),
            _recorte("Moret", 279.678, -66.142, 0.600, 0.316),
            _recorte("Moret", 280.279, -66.142, 0.302, 0.316),
            # --- corrección del usuario ---
            # Arribita de PA-M-032 falta un recorrido chiquito: tira corta hasta
            # el muro de arriba (recorte angosto del pasillo). El pipeline la
            # recorta al muro como notch (queda ~0.11 m de tira visible).
            # NOTA: "arriba de PB-M-111/112" ya queda enlosado en el build actual
            # (el umbral del baño P.B. está cubierto), por eso no se agrega ahí.
            _recorte("Moret", 286.578, -64.734, 0.350, 0.300),
        ],
        "redimensionar": [
            {"x": 288.32, "y": -60.97, "x0": 287.88, "y0": -61.215, "wx": 0.692, "hy": 0.483},  # PA-M-001 se extiende hasta la mitad
        ],
        # MUESCAS a la cara REAL del muro falso de tablaroca (el DWG las traía
        # cortas: arrancaban en x=290.25 y la tablaroca empieza en x=290.192,
        # dejando 6 cm de pieza dentro del muro). El recorte es UN solo bocado
        # desde el borde derecho de la pieza: sin astilla.
        "muescas": [
            {"x": 290.078, "y": -63.019,     # PA-M-020
             "notch": [[[290.3779, -63.0673], [290.192, -63.0673],
                        [290.192, -62.9473], [290.3779, -62.9473],
                        [290.3779, -63.0673]]]},
            {"x": 290.078, "y": -61.817,     # PA-M-012
             "notch": [[[290.3779, -61.8473], [290.192, -61.8473],
                        [290.192, -61.7273], [290.3779, -61.7273],
                        [290.3779, -61.8473]]]},
        ],
        # Columna de CANCELERÍA de ~1 cm (capa A-CANCELERIA) a x≈290.19-290.24:
        # tiras verticales de 1 cm que muerden PA-M-012/020 como "astilla" no
        # serruchable. Se RESTAN de la máscara de muros (ver _mascara_muros) para
        # que NO cuenten como obstáculo. El muro/tablaroca REAL horizontal (bandas
        # y≈-61.85..-61.73 y y≈-63.07..-62.95, que corren a lo ancho hasta x291.39)
        # se CONSERVA: la caja sólo raspa su pico izquierdo (< 6 cm), así PA-M-012/
        # 020 siguen con recorte de muro real (completa=False).
        "cancel_ignorar": [(290.185, 290.25, -64.0, -61.7)],
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
            # AR-101 es Moret (clave 1), no Royal.
            {"x": 287.71, "y": -64.63, "material": "Moret"},
        ],
        # "Cuadrito" debajo de PA-M-036 que conecta al baño de arriba = Moret
        # (clave 1). Las dos hileras (x288.0-289.05, y-67.05..-66.35). El override
        # por caja es robusto a la renumeración de piezas.
        "forzar_material": [
            # hilera BAJA del cuadrito (y-67.09..-66.84) -> Royal Walnut (recámara).
            {"box": (288.00, 289.05, -67.12, -66.84), "material": "Royal Walnut"},
            # hilera ALTA -> Moret (clave 1, conecta al baño de arriba).
            {"box": (288.00, 289.05, -66.84, -66.35), "material": "Moret"},
        ],
        # No rellenar tope Royal dentro del cuadrito (ya es Moret).
        "tope_royal_excluir": [
            (288.00, 289.05, -67.10, -66.30),
        ],
        # Fantasmas / donde va muro: se eliminan.
        "eliminar": [
            (286.75, -64.68),   # PA-M-026: ahí va muro (casi no debe existir)
        ],
        # Baño de planta baja (claves 5/5/2/4 = Urbania/Malla/concreto): el
        # despiece dejó el Moret continuo cruzando el muro; ese piso es otro
        # material, se excluye.
        "cajas_excluir": [
            # baño P.B.: zona de regadera/concreto/urbania. Los recortes de piso
            # Moret del cuarto de lavado (debajo de PB-M-088/089/090) se reponen
            # como piezas_extra, que NO se excluyen.
            (279.00, 281.30, -67.00, -65.78),
            # planta baja: el piso va POR DEBAJO de la escalera, no se excluye.
            (282.75, 285.70, -70.85, -67.75),   # escalera planta alta = vacío (A-ESCALON)
        ],
    },
}
