# -*- coding: utf-8 -*-
"""Redibuja limpio un levantamiento de niveles desde su JSON transcrito."""
import json, os, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch
from matplotlib.lines import Line2D

NAVY="#1F3864"; INK="#1f2937"; GREY="#6B7280"; MUT="#9aa1ab"
REL="#1D4ED8"; COR="#B91C1C"          # relleno (neg) / corte (pos) — par divergente validado
REL_T="#DBEAFE"; COR_T="#FEE2E2"      # tintes de zona
WALL="#4b5563"

def hoja_digital(fig_or_pdf, d, titulo, sub, nota_footer):
    fig=plt.figure(figsize=(8.27,11.69)); fig.patch.set_facecolor("white")
    # encabezado
    fig.patches.append(Rectangle((0.0,0.945),1.0,0.055,transform=fig.transFigure,color=NAVY))
    fig.text(0.05,0.966,titulo,fontsize=15,weight="bold",color="white",va="center")
    fig.text(0.05,0.951,sub,fontsize=9,color="#c8d4ea",va="center")
    # plano
    ax=fig.add_axes([0.06,0.135,0.88,0.775]); ax.set_xlim(-2,102); ax.set_ylim(102,-2)
    ax.set_aspect("auto"); ax.axis("off")
    for w in d.get("walls",[]):
        x1,y1,x2,y2=w
        ax.plot([x1,x2],[y1,y2],color=WALL,lw=3.4,solid_capstyle="butt",zorder=2)
    for s in d.get("stairs",[]):
        x0,y0,x1,y1=s
        ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,facecolor="#f3f4f6",edgecolor=MUT,lw=0.8,hatch="|||",zorder=1))
        ax.text((x0+x1)/2,(y0+y1)/2,"ESC.",fontsize=6.5,color=GREY,ha="center",va="center",zorder=3,
                bbox=dict(boxstyle="round,pad=0.15",fc="white",ec="none",alpha=.8))
    for v in d.get("vacios",[]):
        x0,y0,x1,y1=v
        ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,facecolor="#fafafa",edgecolor=MUT,lw=0.8,hatch="xx",zorder=1))
        ax.text((x0+x1)/2,(y0+y1)/2,"VACÍO",fontsize=7,color=GREY,ha="center",va="center",rotation=0,zorder=3,
                bbox=dict(boxstyle="round,pad=0.2",fc="white",ec=MUT,alpha=.9))
    # puntos
    for p in d.get("points",[]):
        x,y,v=p[0],p[1],p[2]
        col = GREY if v==0 else (REL if v<0 else COR)
        ax.plot([x],[y],marker="o",ms=3.4,color=col,zorder=4)
        txt=f"{v:g}"
        ax.annotate(txt,(x,y),xytext=(3,3),textcoords="offset points",fontsize=6.0,color=INK,zorder=5)
    # zonas anotadas
    for z in d.get("zones",[]):
        col = REL if z.get("tipo")=="relleno" else COR
        tint= REL_T if z.get("tipo")=="relleno" else COR_T
        ax.text(z["x"],z["y"],z.get("label",""),fontsize=6.6,color=col,style="italic",ha="center",zorder=6,
                bbox=dict(boxstyle="round,pad=0.25",fc=tint,ec=col,lw=0.6,alpha=.92))
    # leyenda
    lx=fig.add_axes([0.06,0.055,0.88,0.062]); lx.axis("off")
    hs=[Line2D([],[],marker="o",ls="",color=REL,ms=6),
        Line2D([],[],marker="o",ls="",color=COR,ms=6),
        Line2D([],[],marker="o",ls="",color=GREY,ms=6),
        Rectangle((0,0),1,1,facecolor="#f3f4f6",edgecolor=MUT,hatch="|||"),
        Rectangle((0,0),1,1,facecolor="#fafafa",edgecolor=MUT,hatch="xx")]
    lx.legend(hs,["Relleno (cota negativa: falta nivel)","Corte (cota positiva: sobra)","A nivel (0)","Escalera","Vacío / losa sin colar"],
              loc="center",ncol=3,frameon=False,fontsize=7.4,handlelength=1.2,columnspacing=1.2)
    fig.text(0.06,0.028,nota_footer,fontsize=7.2,color=GREY)
    fig.text(0.94,0.028,"Levantó: Mauricio Gastelum Mora",fontsize=7.2,color=GREY,ha="right")
    if hasattr(fig_or_pdf,"savefig"):
        fig_or_pdf.savefig(fig); plt.close(fig); return None
    return fig
