# -*- coding: utf-8 -*-
import os, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

B = "/root/.claude/uploads/d15acb21-ec3d-5e7a-85b6-2130d9969519/"
OUT = "/home/user/Autocad/Renivelacion"
os.makedirs(OUT, exist_ok=True)
FECHA = "01/07/2026"

# lote,mza,modelo,planta,area,area_nota,esp,vol,vol_nota,estado,foto,rot
D = [
 (33,14,"Cabernet","P.B.",72.63,"sin terraza (con terraza 91.24 m²; terraza aún no colada)",1.84,1.34,"","Renivelado",B+"f72e3eba-1000289423.jpg",0),
 (33,14,"Cabernet","P.A.",65.21,"",2.94,1.88,"","Renivelado",B+"a8c1f97f-1000289422.jpg",0),
 (9,7,"Merlot","P.B.",74.86,"",3.1,2.56,"","Renivelado (completo)",B+"a8bd4639-1000289424.jpg",0),
 (9,7,"Merlot","P.A.",58.25,"",3.4,1.93,"","Renivelado (completo)",B+"5aa389ee-1000289425.jpg",0),
 (10,7,"Merlot","P.B.",74.86,"",1.2,None,"Levantamiento = 1.06 m³, pero NO se renivela (desnivel mínimo)","No renivelado",B+"89ab954a-1000289426.jpg",0),
 (10,7,"Merlot","P.A.",58.25,"",2.5,1.5,"","Renivelado",None,0),
 (19,7,"Chardonnay","P.A.",59.86,"",3.4,1.5,"Teórico 2.0 m³; se rebajaron los puntos altos → 1.5 m³","Renivelado",B+"ee4969c5-1000289428.jpg",0),
 (19,7,"Chardonnay","P.B.",85.79,"",1.71,1.46,"","Renivelado",B+"04e9763c-1000289427.jpg",180),
 (17,7,"Chardonnay","P.B.",85.79,"con terraza 101.14 m² (terraza no colada; no entra)",1.45,1.28,"","Renivelado",None,0),
 (17,7,"Chardonnay","P.A.",59.86,"",2.24,2.59,"⚠ REVISAR: 2.59 m³ no cuadra con 2.24 cm × 59.86 m² (≈1.34 m³). ¿Espesor ≈4.3 cm o volumen ≈1.34 m³?","Por confirmar",None,0),
]

NAVY="#1F3864"; BLUE="#2E5496"; LT="#D9E2F3"; RED="#C00000"; GREEN="#375623"; AMBER="#7F6000"; GREY="#595959"

def cover(pdf, titulo, sub):
    fig=plt.figure(figsize=(8.27,11.69))  # A4
    fig.patch.set_facecolor("white")
    fig.text(0.5,0.72,"VIÑAS NORTE",ha="center",fontsize=30,weight="bold",color=NAVY)
    fig.text(0.5,0.665,titulo,ha="center",fontsize=19,color=BLUE)
    if sub: fig.text(0.5,0.62,sub,ha="center",fontsize=13,color=GREY)
    fig.add_axes([0.15,0.60,0.70,0.004]).axis("off")
    fig.patches.append(plt.Rectangle((0.15,0.605),0.70,0.004,transform=fig.transFigure,color=BLUE))
    txt=("Levantamiento de niveles de losa (renivelación) previo a la colocación de piso.\n"
         "Se miden cotas en una malla de puntos sobre la losa; el promedio de desnivel define\n"
         "el espesor de mortero premezclado de renivelación y su volumen (m³) por planta.\n\n"
         "Convención:  valor negativo = falta nivel (relleno) · valor positivo = sobra (corte).")
    fig.text(0.5,0.50,txt,ha="center",fontsize=10.5,color="#333333",linespacing=1.6)
    fig.text(0.5,0.30,f"Fecha: {FECHA}",ha="center",fontsize=11,color=GREY)
    fig.text(0.5,0.27,"Levantó: Mauricio Gastelum Mora",ha="center",fontsize=11,color=GREY)
    fig.text(0.5,0.06,"Mortero premezclado · medidas en cm (desnivel) y m³ (volumen)",ha="center",fontsize=9,color=GREY,style="italic")
    pdf.savefig(fig); plt.close(fig)

def tabla(pdf, rows, titulo):
    fig=plt.figure(figsize=(8.27,11.69)); fig.patch.set_facecolor("white")
    fig.text(0.06,0.95,titulo,fontsize=16,weight="bold",color=NAVY)
    fig.patches.append(plt.Rectangle((0.06,0.935),0.88,0.003,transform=fig.transFigure,color=BLUE))
    ax=fig.add_axes([0.04,0.30,0.92,0.60]); ax.axis("off")
    cols=["Lote","Mza","Modelo","Planta","Área m²","Prom. cm","Mortero m³","Estado"]
    cells=[]; colors=[]
    tot=0.0
    for (lote,mza,mod,pl,area,an,esp,vol,vn,est,foto,rot) in rows:
        vtxt = f"{vol:.2f}" if vol is not None else "—"
        if vol is not None and "REVISAR" not in vn: tot+=vol
        cells.append([f"L{lote}",f"M{mza}",mod,pl,f"{area:.2f}",f"{esp:.2f}",vtxt,est])
        c="#FDECEA" if est=="Por confirmar" else ("#FFF2CC" if est=="No renivelado" else "white")
        colors.append([c]*8)
    cells.append(["","","","","","TOTAL",f"{tot:.2f}",""])
    colors.append([LT]*8)
    t=ax.table(cellText=cells,colLabels=cols,loc="upper center",cellLoc="center")
    t.auto_set_font_size(False); t.set_fontsize(8.5); t.scale(1,1.7)
    for (r,c),cell in t.get_celld().items():
        cell.set_edgecolor("#BBBBBB")
        if r==0:
            cell.set_facecolor(NAVY); cell.set_text_props(color="white",weight="bold")
        else:
            cell.set_facecolor(colors[r-1][c])
            if r==len(cells): cell.set_text_props(weight="bold")
    # notas
    y=0.27
    fig.text(0.06,y,"Notas y observaciones",fontsize=12,weight="bold",color=NAVY); y-=0.028
    notas=[
      ("Terraza (Cabernet L33 y L34, Chardonnay L17): NO colada aún; no entra en la renivelación. El m³ corresponde al área SIN terraza.",GREY),
      ("L10 M7 P.B.: se levantó (≈1.06 m³) pero NO se renivela por desnivel mínimo (prom. 1.2 cm). Sólo se reniveló P.A.",AMBER),
      ("L19 M7 P.A.: teórico 2.0 m³ (3.4 cm); se rebajaron los puntos altos y se ocupó 1.5 m³. (En la hoja de campo quedó anotado 1.46, que es el valor de P.B.)",GREY),
      ("⚠ L17 M7 P.A.: 2.59 m³ NO cuadra con 2.24 cm × 59.86 m² (daría ≈1.34 m³). Revisar si el promedio es ≈4.3 cm o el volumen ≈1.34 m³.",RED),
      ("L34 M14 (Cabernet): PENDIENTE — se agregará cuando llegue el levantamiento.",BLUE),
    ]
    for tx,col in notas:
        fig.text(0.07,y,"•",fontsize=10,color=col)
        fig.text(0.095,y,tx,fontsize=8.6,color=col,wrap=True,va="top")
        y-=0.043
    pdf.savefig(fig); plt.close(fig)

def foto_pag(pdf, foto, rot, cap):
    if not foto or not os.path.exists(foto): return
    fig=plt.figure(figsize=(8.27,11.69)); fig.patch.set_facecolor("white")
    fig.text(0.06,0.955,cap,fontsize=13,weight="bold",color=NAVY)
    fig.patches.append(plt.Rectangle((0.06,0.945),0.88,0.0025,transform=fig.transFigure,color=BLUE))
    ax=fig.add_axes([0.05,0.05,0.90,0.86]); ax.axis("off")
    im=plt.imread(foto)
    if rot==180: im=np.rot90(im,2)
    ax.imshow(im); ax.set_title("Levantamiento de campo",fontsize=9,color=GREY)
    pdf.savefig(fig); plt.close(fig)

def build(rows, path, titulo, sub):
    with PdfPages(path) as pdf:
        cover(pdf, titulo, sub)
        tabla(pdf, rows, "Resumen de renivelación")
        for r in rows:
            foto=r[10]; rot=r[11]
            cap=f"Lote {r[0]} · Mza {r[1]} ({r[2]}) — {r[3]}   ·   Mortero: "+(f"{r[7]:.2f} m³" if r[7] is not None else "no renivelado")
            foto_pag(pdf, foto, rot, cap)
    print("->",path)

# General
build(D, f"{OUT}/Viñas Norte - Renivelación (GENERAL).pdf", "Renivelación de Losas — Resumen General", "Manzana 7 y Manzana 14")
# Por lote+mza
grp={}
for r in D: grp.setdefault((r[0],r[1]),[]).append(r)
for (lote,mza),rows in grp.items():
    mod=rows[0][2]
    build(rows, f"{OUT}/Viñas Norte - Renivelación L{lote} M{mza} ({mod}).pdf",
          f"Renivelación — Lote {lote}, Manzana {mza}", mod)
print("LISTO")
