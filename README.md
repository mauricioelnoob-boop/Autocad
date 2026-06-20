# Optimizador de recortes de piso

Programa para sacar, a partir del **despiece ya dibujado en el plano de AutoCAD**,
qué piezas de piso hay que **recortar** y **dónde reusar esos recortes** para no
cortar baldosas enteras y desperdiciar menos material.

Pisos considerados:

| Piso          | Medida baldosa completa |
|---------------|-------------------------|
| Moret         | 0.596 m × 1.194 m       |
| Royal Walnut  | 0.200 m × 1.200 m       |

El despiece está dibujado en la capa **`A-PISO`** del plano `plano_pisos.dwg`
(cada baldosa/recorte es una polilínea rectangular).

---

## Resultado con este plano

```
Baldosas completas        : 189   (100 Moret + 89 Royal Walnut)
Piezas a recortar         : 217
  -> sin optimizar         = 217 baldosas (una entera por cada recorte)
  -> reusando recortes     = 165 baldosas
AHORRO                    : 52 baldosas
TOTAL BALDOSAS A COMPRAR  : 354  (189 completas + 165 para recortes)
Merma (desperdicio)       : ~6 %
```

Detalle por material en [`reporte_recortes.txt`](reporte_recortes.txt),
el plan pieza-por-pieza en [`plan_corte.csv`](plan_corte.csv) y los dibujos de
cada baldosa con sus cortes en [`diagramas_corte.pdf`](diagramas_corte.pdf).

---

## Cómo funciona

Son dos pasos:

### 1. Extraer el despiece del DWG  →  `extraer_despiece.py`

AutoCAD guarda en binario (DWG), que Python no lee directo. Primero se convierte
a JSON con **[LibreDWG](https://github.com/LibreDWG/libredwg)**:

```bash
dwgread -O JSON -o pisos.json plano_pisos.dwg
python3 extraer_despiece.py pisos.json            # capa por defecto: A-PISO
# para otra capa:  python3 extraer_despiece.py pisos.json --capa MI-CAPA
```

Mide cada polilínea, decide si es **Moret** (ancho ≈0.6) o **Royal Walnut**
(ancho ≈0.2), y si es **completa** o **recorte** (y de qué tipo: a lo largo,
a lo ancho o en esquina). Genera:

- `piezas_piso.json` — lista de piezas (la entrada del optimizador)
- `piezas_piso.csv` — la misma lista para Excel, con la ubicación (x,y) en el plano

> El `piezas_piso.json` ya está incluido en el repo, así que el paso 2 corre
> aunque no tengas LibreDWG instalado.

### 2. Optimizar el reuso de recortes  →  `optimizador_recortes.py`

```bash
python3 optimizador_recortes.py                   # usa piezas_piso.json
python3 optimizador_recortes.py --kerf 0.003      # considerar 3 mm de sierra
python3 optimizador_recortes.py --rotar           # permitir girar piezas 90°
```

Cada baldosa completa es un "contenedor". Las piezas recortadas se acomodan
dentro con un empaquetado tipo **guillotina** (cortes rectos de lado a lado,
como una cortadora de piso) usando la heurística *First-Fit-Decreasing*: las
piezas grandes primero, y cada sobrante (offcut) se reutiliza para piezas
siguientes. Así varias piezas pequeñas salen de **una sola** baldosa.

Genera:

- `reporte_recortes.txt` — resumen: cuántas baldosas comprar y cuánto se ahorra
- `plan_corte.csv` — de qué baldosa sale cada pieza (con su ubicación en el plano)
- `diagramas_corte.pdf` — dibujo de cada baldosa con sus cortes y el sobrante

En el plan, cada pieza viene con su ubicación `@(x,y)` (el centro de la pieza en
coordenadas del plano), para que la encuentres en AutoCAD y sepas exactamente
qué recorte va en cada lugar.

---

## Requisitos

- **Python 3** (sólo librería estándar para extraer y optimizar).
- **matplotlib** — *opcional*, sólo para generar el PDF de diagramas:
  `pip install matplotlib`
- **LibreDWG** (`dwgread`) — sólo si quieres regenerar desde el DWG.
  El `piezas_piso.json` ya incluido evita necesitarlo.

## Notas / supuestos

- Los materiales se distinguen por el **ancho** de la pieza (0.2 vs 0.6), porque
  en el plano todo está en color "ByLayer" y no se separan por color.
- El plano dibuja la baldosa Moret como 0.6 × 1.194; el programa la ajusta al
  tamaño real 0.596 × 1.194 (una pieza nunca es más grande que la baldosa de la
  que se cortó).
- Por defecto **no** se giran las piezas (respeta el sentido de la veta de la
  madera). Usa `--rotar` si tu material lo permite para ahorrar todavía más.
