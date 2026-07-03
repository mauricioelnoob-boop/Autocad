# -*- coding: utf-8 -*-
import os, sys, json, textwrap, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
sys.path.insert(0,"/tmp/claude-0/-home-user-Autocad/d15acb21-ec3d-5e7a-85b6-2130d9969519/scratchpad")
from render_digit3 import hoja_v3

B="/root/.claude/uploads/d15acb21-ec3d-5e7a-85b6-2130d9969519/"
SP="/tmp/claude-0/-home-user-Autocad/d15acb21-ec3d-5e7a-85b6-2130d9969519/scratchpad"
OUT="/home/user/Autocad/Renivelacion"; FECHA="02/07/2026"
NAVY="#1F3864"; BLUE="#2E5496"; LT="#D9E2F3"; RED="#C00000"; GREY="#595959"; AMBER="#7F6000"

# lote,mza,mod,planta,area,esp,vol,estado,foto,rot,digit_json,nota,espejo
D=[
 (33,14,"Cabernet","P.B.",72.63,1.84,1.34,"Renivelado",B+"f72e3eba-1000289423.jpg",0,f"{SP}/digit/f2.json","Hoja sin V escrito; V dictado 1.34 m³.",False),
 (33,14,"Cabernet","P.A.",65.21,2.94,1.88,"Renivelado",B+"a8c1f97f-1000289422.jpg",0,f"{SP}/digit/f1.json","Hoja sin V escrito. Baño sup-izq: contorno según levantamiento (zona de charola, sin piezas en DWG).",False),
 (9,7,"Merlot","P.B.",74.86,3.1,2.56,"Renivelado",B+"a8bd4639-1000289424.jpg",0,f"{SP}/digit/f3.json","V=2.56 m³ confirmado en hoja.",False),
 (9,7,"Merlot","P.A.",58.25,3.4,1.93,"Renivelado",B+"5aa389ee-1000289425.jpg",0,f"{SP}/digit/f4.json","⚠ La hoja de campo dice 'P.B.' por error: es P.A. (V=1.93).",False),
 (10,7,"Merlot","P.B.",74.86,1.2,None,"No renivelado",B+"89ab954a-1000289426.jpg",0,f"{SP}/digit/f5.json","Levantada (V=1.06), sin ejecutar: desnivel mínimo. Orientación igual al dibujo de campo.",False),
 (10,7,"Merlot","P.A.",58.25,2.5,1.5,"Renivelado",B+"ee4969c5-1000289428.jpg",0,f"{SP}/digit/f7.json","Zona con escombro: renivelada, valores promediados de cuartos vecinos. Orientación igual al dibujo de campo.",False),
 (19,7,"Chardonnay","P.B.",85.79,1.71,1.46,"Renivelado","/root/.claude/uploads/d15acb21-ec3d-5e7a-85b6-2130d9969519/59ebea00-1000289915.jpg",0,f"{SP}/digit/f9.json","Renivelado el jueves 2 de julio. Ref hoja −2 cm.",False),
 (19,7,"Chardonnay","P.A.",59.86,3.4,1.5,"Renivelado","/root/.claude/uploads/d15acb21-ec3d-5e7a-85b6-2130d9969519/fed7a705-1000289916.jpg",0,f"{SP}/digit/f8.json","Renivelado el jueves 2 de julio. Teórico 2.0 m³; con rebaje ≈1.5 m³. Ref hoja −3 cm.",False),
 (17,7,"Chardonnay","P.B.",85.79,1.45,1.28,"Por renivelar","/root/.claude/uploads/d15acb21-ec3d-5e7a-85b6-2130d9969519/778d575e-1000289705.jpg",0,f"{SP}/digit/f11.json","Por renivelar. Terraza punteada no colada: fuera de la renivelación.",False),
 (17,7,"Chardonnay","P.A.",59.86,2.24,2.59,"Por renivelar","/root/.claude/uploads/d15acb21-ec3d-5e7a-85b6-2130d9969519/1f9f3bb6-1000289704.jpg",0,f"{SP}/digit/f10.json","Por renivelar. ⚠ 2.59 m³ no cuadra con 2.24 cm × 59.86 m² (≈1.34 m³); ref hoja −3 cm. Confirmar antes de pedir mortero.",False),
]

def cover(pdf,titulo,sub):
    fig=plt.figure(figsize=(8.27,11.69)); fig.patch.set_facecolor("white")
    fig.text(0.5,0.72,"VIÑAS NORTE",ha="center",fontsize=30,weight="bold",color=NAVY)
    fig.text(0.5,0.665,titulo,ha="center",fontsize=18,color=BLUE)
    if sub: fig.text(0.5,0.62,sub,ha="center",fontsize=12,color=GREY)
    fig.patches.append(plt.Rectangle((0.15,0.605),0.70,0.004,transform=fig.transFigure,color=BLUE))
    txt=("Levantamiento de niveles de losa (renivelación) previo a la colocación de piso.\n"
         "Cotas medidas en malla de puntos; el promedio define el espesor de mortero\n"
         "premezclado y su volumen (m³) por planta.\n\n"
         "Convención: cota negativa = falta nivel (RELLENO) · cota positiva = sobra (CORTE).\n"
         "Hojas digitalizadas con la GEOMETRÍA EXACTA de muros del despiece (DWG).")
    fig.text(0.5,0.47,txt,ha="center",fontsize=10.5,color="#333333",linespacing=1.6)
    fig.text(0.5,0.29,f"Fecha: {FECHA}",ha="center",fontsize=11,color=GREY)
    fig.text(0.5,0.26,"Levantó: Mauricio Gastelum Mora",ha="center",fontsize=11,color=GREY)
    pdf.savefig(fig); plt.close(fig)

def tabla(pdf,rows,titulo):
    fig=plt.figure(figsize=(8.27,11.69)); fig.patch.set_facecolor("white")
    fig.text(0.06,0.95,titulo,fontsize=16,weight="bold",color=NAVY)
    fig.patches.append(plt.Rectangle((0.06,0.935),0.88,0.003,transform=fig.transFigure,color=BLUE))
    ax=fig.add_axes([0.045,0.34,0.91,0.56]); ax.axis("off")
    cols=["Lote","Mza","Modelo","Planta","Área m²","Prom. cm","Mortero m³","Estado"]
    cw=[0.075,0.075,0.135,0.09,0.115,0.115,0.13,0.265]
    LOTE_COL={33:"#FCE9D6", 9:"#E2EFDA", 10:"#EBE6F7", 19:"#DEEBF7", 17:"#FFF4CC"}
    EST_COL={"Renivelado":"#C6EFCE","No renivelado":"#FFD966","Por renivelar":"#9DC3E6"}
    cells=[];colors=[];tot_e=0.0;tot_p=0.0
    for r in rows:
        (lote,mza,mod,pl,area,esp,vol,est)=r[:8]
        vtxt=f"{vol:.2f}" if vol is not None else "—"
        if vol is not None:
            if est=="Renivelado": tot_e+=vol
            elif est=="Por renivelar": tot_p+=vol
        cells.append([f"L{lote}",f"M{mza}",mod,pl,f"{area:.2f}",f"{esp:.2f}",vtxt,est])
        base=LOTE_COL.get(lote,"white")
        fila=[base]*8; fila[7]=EST_COL.get(est,base)
        colors.append(fila)
    cells.append(["","","","","","",f"{tot_e:.2f}","TOTAL EJECUTADO"]); colors.append([LT]*8)
    cells.append(["","","","","","",f"{tot_p:.2f}","TOTAL POR RENIVELAR"]); colors.append(["#DEEBF7"]*8)
    t=ax.table(cellText=cells,colLabels=cols,loc="upper center",cellLoc="center",colWidths=cw)
    t.auto_set_font_size(False); t.set_fontsize(8.5); t.scale(1,1.62)
    for (r_,c_),cell in t.get_celld().items():
        cell.set_edgecolor("#BBBBBB")
        if r_==0: cell.set_facecolor(NAVY); cell.set_text_props(color="white",weight="bold")
        else:
            cell.set_facecolor(colors[r_-1][c_])
            if r_>=len(cells)-1: cell.set_text_props(weight="bold")
    y=0.315
    fig.text(0.06,y,"Notas y verificación",fontsize=12,weight="bold",color=NAVY); y-=0.02
    fig.text(0.07,y,"Color de fila = lote · color de la celda Estado: verde=renivelado, ámbar=no renivelado, azul=por renivelar.",fontsize=8.0,color=GREY,style="italic"); y-=0.022
    notas=[
      ("Verificación foto por foto (zoom + aritmética + geometría): f1=L33 P.A. · f2=L33 P.B. · f3=L9 P.B. (V=2.56) · f4=L9 P.A. (V=1.93; hoja dice 'P.B.' por error) · f5=L10 P.B. (V=1.06) · f6=f7=misma hoja, L10 P.A. (V=1.46).",BLUE),
      ("L10 M7: P.B. levantada (1.06 m³) pero NO se renivela (prom. 1.2 cm). P.A. renivelada (1.46 ≈ 1.5 m³). Planos en la orientación del dibujo de campo.",AMBER),
      ("L19 M7 (Chardonnay): RENIVELADO el jueves 2 de julio (ambas plantas). L17 M7 (Chardonnay): POR RENIVELAR, sin fecha. Referencias de hoja: L19 P.A. −3 cm, L19 P.B. −2 cm, L17 P.A. −3 cm.",BLUE),
      ("Terrazas (no coladas): fuera de la renivelación.",GREY),
      ("⚠ L17 M7 P.A.: 2.59 m³ no cuadra con 2.24 cm × 59.86 m² (≈1.34 m³). Confirmar antes de pedir mortero.",RED),
    ]
    for tx,col in notas:
        for i,ln in enumerate(textwrap.wrap(tx,108)):
            fig.text(0.07 if i==0 else 0.095,y,("• " if i==0 else "")+ln,fontsize=8.2,color=col)
            y-=0.0165
        y-=0.008
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

def build(rows,path,titulo,sub):
    with PdfPages(path) as pdf:
        cover(pdf,titulo,sub); tabla(pdf,rows,"Resumen de renivelación")
        for r in rows:
            (lote,mza,mod,pl,area,esp,vol,est,foto,rot,dj,nota,esp_flag)=r
            if dj and os.path.exists(dj):
                d=json.load(open(dj))
                vtxt=f"{vol:.2f} m³" if vol is not None else "levantada, sin ejecutar"
                tit=f"LOTE {lote} · MZA {mza} ({mod.upper()}) — {'PLANTA ALTA' if pl=='P.A.' else 'PLANTA BAJA'}"
                sub2=f"Hoja digitalizada · {area:.2f} m² · prom. {esp:.2f} cm · mortero {vtxt}"+(f" · hoja: {d.get('V')}" if d.get("V") else "")
                hoja_v3(pdf,d,mod,pl,tit,sub2,nota or "",espejo=esp_flag)
            if foto: foto_pag(pdf,foto,rot,f"Lote {lote} · Mza {mza} ({mod}) — {pl}")
    print("->",os.path.basename(path))

os.makedirs(OUT,exist_ok=True)
build(D,f"{OUT}/Viñas Norte - Renivelación (GENERAL).pdf","Renivelación de Losas — Resumen General","Manzana 7 y Manzana 14 · hojas digitalizadas con muros exactos")
grp={}
for r in D: grp.setdefault((r[0],r[1]),[]).append(r)
for (lote,mza),rows in grp.items():
    build(rows,f"{OUT}/Viñas Norte - Renivelación L{lote} M{mza} ({rows[0][2]}).pdf",
          f"Renivelación — Lote {lote}, Manzana {mza}",rows[0][2])
print("LISTO")
