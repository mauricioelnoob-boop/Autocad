# -*- coding: utf-8 -*-
import os, sys, json, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
sys.path.insert(0, "/tmp/claude-0/-home-user-Autocad/d15acb21-ec3d-5e7a-85b6-2130d9969519/scratchpad")
from render_digit import hoja_digital

B="/root/.claude/uploads/d15acb21-ec3d-5e7a-85b6-2130d9969519/"
SP="/tmp/claude-0/-home-user-Autocad/d15acb21-ec3d-5e7a-85b6-2130d9969519/scratchpad"
OUT="/home/user/Autocad/Renivelacion"
FECHA="01/07/2026"
NAVY="#1F3864"; BLUE="#2E5496"; LT="#D9E2F3"; RED="#C00000"; GREY="#595959"; AMBER="#7F6000"

# lote,mza,modelo,planta,area,area_nota,esp,vol,vol_nota,estado,foto,rot,digit_json,nota_digit
D=[
 (33,14,"Cabernet","P.B.",72.63,"sin terraza (con terraza 91.24 m²; no colada)",1.84,1.34,"","Renivelado",B+"f72e3eba-1000289423.jpg",0,f"{SP}/digit/f2.json","Hoja de campo sin V escrito; V dictado: 1.34 m³."),
 (33,14,"Cabernet","P.A.",65.21,"",2.94,1.88,"","Renivelado",B+"a8c1f97f-1000289422.jpg",0,f"{SP}/digit/f1.json","Hoja de campo sin V escrito; V dictado: 1.88 m³."),
 (9,7,"Merlot","P.B.",74.86,"",3.1,2.56,"","Renivelado (completo)",B+"a8bd4639-1000289424.jpg",0,f"{SP}/digit/f3.json","V=2.56 m³ confirmado en hoja."),
 (9,7,"Merlot","P.A.",58.25,"",3.4,1.93,"","Renivelado (completo)",B+"5aa389ee-1000289425.jpg",0,f"{SP}/digit/f4.json","⚠ La hoja de campo dice 'P.B.' por error: es P.A. (V=1.93 = P.A.; cotas hasta −6.5)."),
 (10,7,"Merlot","P.B.",74.86,"",1.2,None,"Levantamiento = 1.06 m³; NO se renivela (desnivel mínimo)","No renivelado",B+"89ab954a-1000289426.jpg",0,f"{SP}/digit/f5.json","Levantada, sin ejecutar. Dígito del lote verificado con zoom: Lote 10."),
 (10,7,"Merlot","P.A.",58.25,"",2.5,1.5,"Hoja de campo: V=1.46 m³ (≈1.5)","Renivelado",B+"ee4969c5-1000289428.jpg",0,f"{SP}/digit/f7.json","Fotos 6 y 7 = MISMA hoja (una salió de cabeza). Dígito verificado: Lote 10. V=1.46 ≈ 58.25 m² × 2.5 cm."),
 (19,7,"Chardonnay","P.A.",59.86,"",3.4,1.5,"Teórico 2.0 m³; se rebajan puntos altos → 1.5 m³","Renivelado",None,0,None,None),
 (19,7,"Chardonnay","P.B.",85.79,"",1.71,1.46,"","Renivelado",None,0,None,None),
 (17,7,"Chardonnay","P.B.",85.79,"con terraza 101.14 m² (no colada; no entra)",1.45,1.28,"","Renivelado",None,0,None,None),
 (17,7,"Chardonnay","P.A.",59.86,"",2.24,2.59,"⚠ REVISAR: no cuadra con 2.24 cm × 59.86 m² (≈1.34 m³)","Por confirmar",None,0,None,None),
]

def cover(pdf,titulo,sub):
    fig=plt.figure(figsize=(8.27,11.69)); fig.patch.set_facecolor("white")
    fig.text(0.5,0.72,"VIÑAS NORTE",ha="center",fontsize=30,weight="bold",color=NAVY)
    fig.text(0.5,0.665,titulo,ha="center",fontsize=19,color=BLUE)
    if sub: fig.text(0.5,0.62,sub,ha="center",fontsize=13,color=GREY)
    fig.patches.append(plt.Rectangle((0.15,0.605),0.70,0.004,transform=fig.transFigure,color=BLUE))
    txt=("Levantamiento de niveles de losa (renivelación) previo a la colocación de piso.\n"
         "Se miden cotas en una malla de puntos; el promedio de desnivel define el espesor\n"
         "de mortero premezclado y su volumen (m³) por planta.\n\n"
         "Convención: cota negativa = falta nivel (RELLENO) · cota positiva = sobra (CORTE).\n"
         "Cada planta incluye su HOJA DIGITALIZADA y la hoja de campo original.")
    fig.text(0.5,0.49,txt,ha="center",fontsize=10.5,color="#333333",linespacing=1.6)
    fig.text(0.5,0.30,f"Fecha: {FECHA}",ha="center",fontsize=11,color=GREY)
    fig.text(0.5,0.27,"Levantó: Mauricio Gastelum Mora",ha="center",fontsize=11,color=GREY)
    pdf.savefig(fig); plt.close(fig)

def tabla(pdf,rows,titulo):
    fig=plt.figure(figsize=(8.27,11.69)); fig.patch.set_facecolor("white")
    fig.text(0.06,0.95,titulo,fontsize=16,weight="bold",color=NAVY)
    fig.patches.append(plt.Rectangle((0.06,0.935),0.88,0.003,transform=fig.transFigure,color=BLUE))
    ax=fig.add_axes([0.04,0.34,0.92,0.56]); ax.axis("off")
    cols=["Lote","Mza","Modelo","Planta","Área m²","Prom. cm","Mortero m³","Estado"]
    cells=[];colors=[];tot=0.0
    for r in rows:
        (lote,mza,mod,pl,area,an,esp,vol,vn,est)=r[:10]
        vtxt=f"{vol:.2f}" if vol is not None else "—"
        if vol is not None and est!="Por confirmar": tot+=vol
        cells.append([f"L{lote}",f"M{mza}",mod,pl,f"{area:.2f}",f"{esp:.2f}",vtxt,est])
        c="#FDECEA" if est=="Por confirmar" else ("#FFF2CC" if est=="No renivelado" else "white")
        colors.append([c]*8)
    cells.append(["","","","","","TOTAL",f"{tot:.2f}",""]); colors.append([LT]*8)
    t=ax.table(cellText=cells,colLabels=cols,loc="upper center",cellLoc="center")
    t.auto_set_font_size(False); t.set_fontsize(8.5); t.scale(1,1.65)
    for (r_,c_),cell in t.get_celld().items():
        cell.set_edgecolor("#BBBBBB")
        if r_==0: cell.set_facecolor(NAVY); cell.set_text_props(color="white",weight="bold")
        else:
            cell.set_facecolor(colors[r_-1][c_])
            if r_==len(cells): cell.set_text_props(weight="bold")
    y=0.315
    fig.text(0.06,y,"Notas y verificación de hojas de campo",fontsize=12,weight="bold",color=NAVY); y-=0.027
    notas=[
      ("Verificación foto por foto (encabezado con zoom + aritmética + geometría del plano): f1=L33 P.A. · f2=L33 P.B. · f3=L9 P.B. (V=2.56) · f4=L9 P.A. (V=1.93; la hoja dice 'P.B.' por error) · f5=L10 P.B. (V=1.06) · f6 y f7=MISMA hoja, L10 P.A. (V=1.46).",BLUE),
      ("L10 M7: P.B. levantada (1.06 m³) pero NO se renivela (prom. 1.2 cm, mínimo). P.A. sí: V hoja 1.46 ≈ 1.5 m³.",AMBER),
      ("L19 y L17 (Chardonnay): datos dictados del levantamiento; hojas de campo NO incluidas en las fotos recibidas.",GREY),
      ("Terrazas (L33/L34 Cabernet, L17 Chardonnay): sin colar; NO entran en la renivelación.",GREY),
      ("⚠ L17 M7 P.A.: 2.59 m³ no cuadra con 2.24 cm × 59.86 m² (≈1.34 m³). Por confirmar; fuera del total.",RED),
      ("L34 M14 (Cabernet): PENDIENTE — se agrega cuando llegue su levantamiento.",BLUE),
    ]
    for tx,col in notas:
        fig.text(0.07,y,"•",fontsize=10,color=col)
        fig.text(0.095,y,tx,fontsize=8.2,color=col,va="top",wrap=True)
        y-=0.047
    pdf.savefig(fig); plt.close(fig)

def foto_pag(pdf,foto,rot,cap):
    if not foto or not os.path.exists(foto): return
    fig=plt.figure(figsize=(8.27,11.69)); fig.patch.set_facecolor("white")
    fig.text(0.06,0.955,cap,fontsize=12,weight="bold",color=NAVY)
    fig.patches.append(plt.Rectangle((0.06,0.945),0.88,0.0025,transform=fig.transFigure,color=BLUE))
    ax=fig.add_axes([0.05,0.05,0.90,0.86]); ax.axis("off")
    im=plt.imread(foto)
    if rot==180: im=np.rot90(im,2)
    ax.imshow(im); ax.set_title("Hoja de campo original",fontsize=9,color=GREY)
    pdf.savefig(fig); plt.close(fig)

def pag_digit(pdf,row):
    dj=row[12]
    if not dj or not os.path.exists(dj): return
    d=json.load(open(dj))
    (lote,mza,mod,pl,area,an,esp,vol,vn,est)=row[:10]
    vtxt=f"{vol:.2f} m³" if vol is not None else "levantada, sin ejecutar"
    titulo=f"LOTE {lote} · MZA {mza} ({mod.upper()}) — {'PLANTA ALTA' if pl=='P.A.' else 'PLANTA BAJA'}"
    sub=f"Hoja digitalizada · {area:.2f} m² · prom. {esp:.2f} cm · mortero {vtxt}" + (f" · hoja: {d.get('V')}" if d.get("V") else "")
    hoja_digital(pdf,d,titulo,sub,row[13] or "")
def build(rows,path,titulo,sub):
    with PdfPages(path) as pdf:
        cover(pdf,titulo,sub)
        tabla(pdf,rows,"Resumen de renivelación")
        for r in rows:
            pag_digit(pdf,r)
            if r[10]:
                cap=f"Lote {r[0]} · Mza {r[1]} ({r[2]}) — {r[3]}"
                foto_pag(pdf,r[10],r[11],cap)
    print("->",os.path.basename(path))

os.makedirs(OUT,exist_ok=True)
build(D,f"{OUT}/Viñas Norte - Renivelación (GENERAL).pdf","Renivelación de Losas — Resumen General","Manzana 7 y Manzana 14 · con hojas digitalizadas")
grp={}
for r in D: grp.setdefault((r[0],r[1]),[]).append(r)
for (lote,mza),rows in grp.items():
    build(rows,f"{OUT}/Viñas Norte - Renivelación L{lote} M{mza} ({rows[0][2]}).pdf",
          f"Renivelación — Lote {lote}, Manzana {mza}",rows[0][2])
print("LISTO")
