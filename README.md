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
TOTAL PIEZAS A COMPRAR    : 354  (189 completas + 165 para recortes)
Merma (desperdicio)       : ~6 %
```

### Cantidades a comprar (piezas / cajas / m²)

| Material      | Piezas | Cajas | Pzas/caja | m²/caja | m² a comprar |
|---------------|:------:|:-----:|:---------:|:-------:|:------------:|
| Moret         | 179    | 90    | 2         | 1.42    | 127.80 m²    |
| Royal Walnut  | 175    | 35    | 5         | 1.20    | 42.00 m²     |
| **TOTAL**     | **354**| **125** |         |         | **169.80 m²**|

> Material suministrado (dato informativo): Moret 166.52 m², Royal Walnut 49.2 m².
> No se calcula si alcanza o no — falta sumar zoclo y piso en muro.

Detalle por material en [`reporte_recortes.txt`](reporte_recortes.txt),
el plan pieza-por-pieza en [`plan_corte.csv`](plan_corte.csv) y el **PDF con el
resumen de compra + diagramas** de cada baldosa en
[`reporte_recortes.pdf`](reporte_recortes.pdf).

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

- `reporte_recortes.txt` — resumen: piezas, cajas y m² a comprar, y cuánto se ahorra
- `plan_corte.csv` — de qué baldosa sale cada pieza (con su ubicación en el plano)
- `reporte_recortes.pdf` — PDF con la tabla de compra (piezas/cajas/m²) y el
  dibujo de cada baldosa con sus cortes y el sobrante reutilizable

En el plan, cada pieza viene con su ubicación `@(x,y)` (el centro de la pieza en
coordenadas del plano), para que la encuentres en AutoCAD y sepas exactamente
qué recorte va en cada lugar.

---

### 3. Plano general de corte  →  `generar_plano.py`

```bash
python3 generar_plano.py            # genera plano_corte.dxf y plano_corte.pdf
```

Dibuja **todas** las baldosas que se van a recortar (una por una, a escala real),
y dentro de cada una marca por color:

- **verde** = pieza que se corta y se usa en el piso (con su medida),
- **amarillo** = sobrante reutilizable (lado ≥ 10 cm),
- **rojo** = desperdicio / merma (tira demasiado chica).

Incluye totales (piezas, cajas, m², desperdicio) y leyenda. Genera:

- `plano_corte.dxf` — se abre directo en **AutoCAD** (capas: BALDOSA, PIEZA,
  SOBRANTE, DESPERDICIO, TITULO), cada baldosa a escala real en metros.
- `plano_corte.pdf` — el mismo plano como póster (un material por hoja).

Resumen de este plano: desperdicio real **≈ 3.4 m²**; sobrante reutilizable
**≈ 6.8 m²** (que podrías guardar para otra obra).

### 4. Plano de la casa con piezas identificadas  →  `plano_casa.py`

```bash
python3 plano_casa.py               # genera plano_casa.dxf, plano_casa.pdf, lista_piezas.csv
```

Dibuja el despiece **en su posición real** dentro de la casa y le pone a cada
pieza un **ID** (`M-042` = Moret pieza 42, `R-118` = Royal Walnut pieza 118),
para que sepas pieza por pieza cuál recortar, cómo y dónde va instalada. Cada
recorte se **enlaza** con su baldosa del plano de corte (columna `corte_de`).

- gris = baldosa completa · naranja = recorte Moret · turquesa = recorte Royal.

Genera:

- `plano_casa.dxf` — plano para **AutoCAD**, cada pieza con su ID; capas por
  material y por completa/recorte (puedes apagar las completas y dejar sólo los
  recortes).
- `plano_casa.pdf` — el plano de la casa + una **tabla de recortes**
  (ID → medida a cortar → tipo → de qué baldosa sale → ubicación).
- `lista_piezas.csv` — las 406 piezas con todo el detalle, para Excel.

### 5. Plano de recortes por material (sobrante coloreado)  →  `plano_recortes_material.py`

```bash
python3 plano_recortes_material.py
```

Genera **un PDF por material** con cada baldosa que se corta, mostrando cada
pieza con su ID y **a dónde va** (`→ va a (x,y)`), y el sobrante coloreado:

- amarillo = **sobrante reutilizable** (lado ≥ 10 cm),
- rojo = **desperdicio**.

Salidas: `plano_recortes_moret.pdf` y `plano_recortes_royal_walnut.pdf`.

### Demostración de faltante de material  →  `demostracion_faltante.py`

```bash
python3 demostracion_faltante.py Numeros_Generadores_....xlsx
```

Consolida las 6 hojas del Excel de generadores (Moret/Royal × Chardonnay/
Cabernet/Merlot), aplica el factor de desperdicio del propio generador y suma
piso + escalera + zoclo vs lo suministrado. Demuestra el faltante:
**Moret −30 cajas, Royal Walnut −11 cajas**. Salidas: `demostracion_faltante.pdf`
y `demostracion_faltante.csv`.

### 6. Plano por planta (versión corregida)  →  `plano_por_planta.py`

```bash
python3 plano_por_planta.py          # genera planta_baja.pdf y planta_alta.pdf
```

Separa el despiece por **nivel** (las dos plantas vienen dibujadas lado a lado
en el plano, se parten por la coordenada X):

- **Planta baja**: SOLO piso Moret.
- **Planta alta**: Moret + Royal Walnut (las 3 recámaras).

Aplica la regla real de la obra: **el Royal Walnut sólo va en las recámaras**;
las piezas de 0.20 m que aparecían en baños de planta baja son las **charolas**
(otro piso) y se **excluyen** (7 piezas). La lógica está en `datos_piezas.py`.

Cada PDF (`planta_baja.pdf`, `planta_alta.pdf`) trae: (1) el plano de la planta
con cada pieza identificada (`PB-M-001`, `PA-R-014`…), (2) un resumen de compra
de esa planta, y (3) el detalle de recortes (qué cortar, a dónde va, qué sobra).

Cantidades corregidas (sin charolas):

| Planta | Material | Piezas | Cajas |
|--------|----------|:------:|:-----:|
| Baja   | Moret    | 133    | 67    |
| Alta   | Moret    | 47     | 24    |
| Alta   | Royal Walnut | 168 | 34   |

### 7. Cruce de área real vs generador  →  `cruce_area_generador.py`

```bash
python3 cruce_area_generador.py Numeros_Generadores_....xlsx
```

Mide el área real del despiece (pieza por pieza, sin charolas) y la compara con
el "Área a revestir" del generador (Cabernet):

| Material | Real (plano) | Generador | Diferencia |
|----------|:------------:|:---------:|:----------:|
| Moret        | 119.68 m² | 134.78 m² | −15.10 m² |
| Royal Walnut |  37.87 m² |  40.20 m² |  −2.33 m² |

El despiece dibujado da menos área que el generador (revisa si falta despiece de
algún cuarto o si el generador usó área bruta). Salida: `cruce_area.csv`.

### 8. PDF por material (plano + desperdicios)  →  `pdf_material.py`

```bash
python3 pdf_material.py        # genera piso_moret.pdf y piso_royal_walnut.pdf
```

Dos PDF, uno por material, con el estilo del plano de la casa:

- **Página 1**: el plano completo con ese material coloreado e identificado por
  pieza; el otro piso se dibuja tenue como contexto. (Royal Walnut ya **no**
  aparece en planta baja; sólo en las recámaras de planta alta.)
- **Página 2**: resumen (piezas, cajas, m², sobrante reutilizable, desperdicio).
- **Páginas 3+**: los desperdicios/recortes — cada baldosa que se corta, qué
  piezas salen, a dónde van y qué sobra (amarillo = reutilizable, rojo = merma).

Usa los datos corregidos (`datos_piezas.py`, sin charolas de baño). Salidas:
`piso_moret.pdf` (179 pzas / 90 cajas) y `piso_royal_walnut.pdf` (168 pzas / 34 cajas).

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
