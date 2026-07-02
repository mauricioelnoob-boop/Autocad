# -*- coding: utf-8 -*-
"""Hoja digitalizada v4: MUROS REALES del despiece, mostrados en la ORIENTACIÓN de la hoja de campo."""
import json, sys, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.patches import Rectangle, Polygon as MplPoly, PathPatch
from matplotlib.path import Path as MplPath

def _pathpatch(g, m2d, **kw):
    verts=[]; codes=[]
    def ring(coords):
        xs,ys=zip(*coords); dx,dy=m2d(xs,ys)
        pts=list(zip(dx,dy))
        verts.extend(pts); codes.extend([MplPath.MOVETO]+[MplPath.LINETO]*(len(pts)-2)+[MplPath.CLOSEPOLY])
    ring(g.exterior.coords)
    for hole in g.interiors: ring(hole.coords)
    return PathPatch(MplPath(verts,codes), **kw)
from matplotlib.lines import Line2D
from shapely.geometry import Polygon as ShPoly, Point
from shapely.ops import unary_union
sys.path.insert(0, "/home/user/Autocad")
from modelos import MODELOS

NAVY="#1F3864"; INK="#1f2937"; GREY="#6B7280"; MUT="#9aa1ab"
REL="#1D4ED8"; COR="#B91C1C"; REL_T="#DBEAFE"; COR_T="#FEE2E2"; WALL="#4b5563"

def _crecer(seed_objs, pool):
    """expande por conectividad: agrega del pool lo que toque la unión actual"""
    sel=list(seed_objs); resto=[o for o in pool if o not in sel]
    for _ in range(4):
        if not resto: break
        Us=unary_union(sel).buffer(0.12)
        nuevos=[o for o in resto if o.intersects(Us)]
        if not nuevos: break
        sel+=nuevos; resto=[o for o in resto if o not in nuevos]
    return sel

def geometria(modelo, planta):
    cfg=MODELOS[modelo]; xc=cfg["x_corte"]
    lado=(lambda c: c>xc) if planta=="P.A." else (lambda c: c<xc)
    muros=[ShPoly(p).buffer(0) for p in json.load(open(f"/home/user/Autocad/{cfg['muros']}")) if len(p)>=3]
    # Igual que _mascara_muros del pipeline: solo BANDAS de muro (ancho medio < 0.35 m).
    bandas=[m for m in muros if not m.is_empty and m.area>0.001 and m.length>0
            and (2*m.area/m.length)<0.35]
    # asignación por conectividad desde las bandas claramente de esta planta
    semilla=[m for m in bandas if lado(m.centroid.x)]
    otra=[m for m in bandas if not lado(m.centroid.x)]
    muros=_crecer(semilla, otra) if semilla else semilla
    from shapely.geometry import box as _box
    # PERÍMETRO EXTERIOR exacto: contorno de la unión de las piezas de piso del despiece.
    from shapely.geometry import box as _box
    raw=json.load(open(f"/home/user/Autocad/{cfg['piezas']}"))
    bv=cfg.get("bbox_valido")
    cajas=[]
    pool=[]
    for p in raw:
        if not all(k in p for k in ("x0","y0","wx","hy")): continue
        c=_box(p["x0"],p["y0"],p["x0"]+p["wx"],p["y0"]+p["hy"])
        cx,cy=c.centroid.x,c.centroid.y
        if bv and not (bv[0]<=cx<=bv[1] and bv[2]<=cy<=bv[3]): continue
        pool.append(c)
    semc=[c for c in pool if lado(c.centroid.x)]
    otrc=[c for c in pool if not lado(c.centroid.x)]
    cajas=_crecer(semc+muros, otrc)
    cajas=[c for c in cajas if c not in muros]
    if cajas:
        piso=unary_union(cajas).buffer(0.07).buffer(-0.07)
        pb=piso.bounds
        env=_box(pb[0]-0.25,pb[1]-0.25,pb[2]+0.25,pb[3]+0.25)   # caja recta: los cortes quedan ortogonales
        muros=[m.intersection(env) for m in muros if m.intersects(env)]
        muros=[m for m in muros if not m.is_empty and m.area>0.001]
        foot=unary_union(muros+[piso])
        filled=unary_union([ShPoly(g.exterior) for g in (foot.geoms if foot.geom_type=="MultiPolygon" else [foot])]).simplify(0.01).buffer(0)
        per=filled.buffer(0.14, join_style=2).difference(filled.buffer(0.002))
        muros.append(per.buffer(0))
        piso=filled
    else:
        piso=None
    esc=[]
    try:
        esc=[ShPoly(p).buffer(0) for p in json.load(open(f"/home/user/Autocad/escalon_{modelo.lower()}.json"))]
        esc=[e for e in esc if not e.is_empty and lado(e.centroid.x)]
    except Exception: pass
    return muros, esc, piso

def _var(a,b,vi):
    return [(a,b),(b,a),(1-a,b),(b,1-a),(a,1-b),(1-b,a),(1-a,1-b),(1-b,1-a)][vi]

def _inv(u,v,vi):
    if   vi==0: return u,v
    elif vi==1: return v,u
    elif vi==2: return 1-u,v
    elif vi==3: return 1-v,u
    elif vi==4: return u,1-v
    elif vi==5: return v,1-u
    elif vi==6: return 1-u,1-v
    else:       return 1-v,1-u

def calibrar(d, muros, esc, piso=None):
    U=unary_union(muros)
    mx0,my0,mx1,my1=(piso.buffer(0.16).bounds if piso is not None else U.bounds)
    samples=[]
    for (x1,y1,x2,y2) in d.get("walls",[]):
        for t in np.linspace(0,1,8): samples.append((x1+(x2-x1)*t,y1+(y2-y1)*t))
    S=np.array(samples,float); a=S[:,0]/100.0; b=S[:,1]/100.0
    pts=np.array([[p[0],p[1]] for p in d.get("points",[])],float)
    pa=pts[:,0]/100.0 if len(pts) else np.array([]); pb=pts[:,1]/100.0 if len(pts) else np.array([])
    st=d.get("stairs",[]); esc_c=unary_union(esc).centroid if esc else None
    # prior de aspecto: la hoja es A4 vertical (relación física alto/ancho ≈1.414 del área de dibujo)
    Ea=max(a.max()-a.min(),1e-6); Eb=max(b.max()-b.min(),1e-6)
    R_photo=(Eb*1.414)/Ea
    W_=mx1-mx0; H_=my1-my0
    best=None
    for vi in range(8):
        u,v=_var(a,b,vi); u0,u1,v0,v1=u.min(),u.max(),v.min(),v.max()
        if u1-u0<1e-6 or v1-v0<1e-6: continue
        X=mx0+(u-u0)/(u1-u0)*(mx1-mx0); Y=my0+(v-v0)/(v1-v0)*(my1-my0)
        w=np.mean([U.distance(Point(x,y)) for x,y in zip(X,Y)])
        pen=0.0
        if len(pts):
            pu,pv=_var(pa,pb,vi)
            PX=mx0+(pu-u0)/(u1-u0)*(mx1-mx0); PY=my0+(pv-v0)/(v1-v0)*(my1-my0)
            pen+=2.0*sum(1 for x,y in zip(PX,PY) if U.contains(Point(x,y)))/len(pts)
        if st and esc_c is not None:
            su,sv=_var(np.array([st[0][0],st[0][2]])/100.0,np.array([st[0][1],st[0][3]])/100.0,vi)
            SX=mx0+(su-u0)/(u1-u0)*(mx1-mx0); SY=my0+(sv-v0)/(v1-v0)*(my1-my0)
            pen+=0.6*esc_c.distance(Point((SX[0]+SX[1])/2,(SY[0]+SY[1])/2))
        SA_=H_ if vi in (1,3,5,7) else W_
        SB_=W_ if vi in (1,3,5,7) else H_
        pen+=1.2*abs(np.log((SB_/SA_)/R_photo))
        sc=w+pen
        if best is None or sc<best[0]: best=(sc,vi,(u0,u1,v0,v1))
    # refinado fino: ajusta (u0,u1,v0,v1) minimizando distancia de muros transcritos a muros reales
    sc,vi,(u0,u1,v0,v1)=best
    u,v=_var(a,b,vi)
    def _cost(p):
        uu0,uu1,vv0,vv1=p
        X=mx0+(u-uu0)/(uu1-uu0)*(mx1-mx0); Y=my0+(v-vv0)/(vv1-vv0)*(my1-my0)
        return np.mean([U.distance(Point(x,y)) for x,y in zip(X,Y)])
    p=[u0,u1,v0,v1]; base=_cost(p)
    for _ in range(2):
        for i in range(4):
            for dlt in (-0.03,-0.015,0.015,0.03):
                q=p[:]; q[i]+=dlt
                if q[1]-q[0]<0.2 or q[3]-q[2]<0.2: continue
                c=_cost(q)
                if c<base: base,p=c,q
    return (base,vi,tuple(p))

def hoja_v3(pdf, d, modelo, planta, titulo, sub, nota_footer):
    muros, esc, piso = geometria(modelo, planta)
    score,vi,(u0,u1,v0,v1)=calibrar(d,muros,esc,piso)
    U=unary_union(muros)
    mx0,my0,mx1,my1=(piso.buffer(0.16).bounds if piso is not None else U.bounds)
    W=mx1-mx0; H=my1-my0
    SA=H if vi in (1,3,5,7) else W
    SB=W if vi in (1,3,5,7) else H

    def m2d(X,Y):
        """modelo -> display (misma orientación que la hoja de campo, escala real)."""
        u=(np.asarray(X,float)-mx0)/W; v=(np.asarray(Y,float)-my0)/H
        a,b=_inv(u,v,vi)
        return a*SA, b*SB
    def f2d(px,py):
        """foto (0-100) -> display, pasando por la calibración (modelo)."""
        a=np.asarray(px,float)/100.0; b=np.asarray(py,float)/100.0
        u,v=_var(a,b,vi)
        X=mx0+(u-u0)/(u1-u0)*W; Y=my0+(v-v0)/(v1-v0)*H
        return m2d(X,Y)

    pad=0.045*max(SA,SB)
    fig=plt.figure(figsize=(8.27,11.69)); fig.patch.set_facecolor("white")
    fig.patches.append(Rectangle((0.0,0.945),1.0,0.055,transform=fig.transFigure,color=NAVY))
    fig.text(0.05,0.9695,titulo,fontsize=14,weight="bold",color="white",va="center")
    fig.text(0.05,0.9525,sub,fontsize=8.6,color="#c8d4ea",va="center")
    ax=fig.add_axes([0.05,0.13,0.90,0.79])
    ax.set_xlim(-pad,SA+pad); ax.set_ylim(SB+pad,-pad)   # y hacia abajo, como la hoja
    ax.set_aspect("equal"); ax.axis("off")

    for m in muros:
        for g in ([m] if m.geom_type=="Polygon" else m.geoms):
            ax.add_patch(_pathpatch(g,m2d,facecolor=WALL,edgecolor=WALL,lw=0.4,zorder=2))
    # esc real: solo los polígonos que se traslapan con la escalera/vacío transcritos
    rects=[]
    for s in d.get("stairs",[])+d.get("vacios",[]):
        a=np.array([s[0],s[2]])/100.0; b=np.array([s[1],s[3]])/100.0
        u,v=_var(a,b,vi)
        RX=mx0+(u-u0)/(u1-u0)*W; RY=my0+(v-v0)/(v1-v0)*H
        from shapely.geometry import box as _box
        rects.append(_box(min(RX),min(RY),max(RX),max(RY)))
    zona_st=unary_union(rects) if rects else None
    esc_draw=[e for e in esc if zona_st is None or e.intersects(zona_st.buffer(0.5))]
    for e in esc_draw:
        for g in ([e] if e.geom_type=="Polygon" else e.geoms):
            ax.add_patch(_pathpatch(g,m2d,facecolor="#f3f4f6",edgecolor=MUT,lw=0.7,hatch="///",zorder=1))
    for s in d.get("stairs",[]):
        X,Y=f2d([s[0],s[2]],[s[1],s[3]]); x0,x1=sorted(X); y0,y1=sorted(Y)
        ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,facecolor="none",edgecolor=MUT,lw=0.8,hatch="|||",zorder=1))
    for s in d.get("vacios",[]):
        X,Y=f2d([s[0],s[2]],[s[1],s[3]]); x0,x1=sorted(X); y0,y1=sorted(Y)
        ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,facecolor="#fcfcfb",edgecolor=MUT,lw=0.8,hatch="xx",zorder=1))
        ax.text((x0+x1)/2,(y0+y1)/2,"VACÍO",fontsize=6.5,color=GREY,ha="center",va="center",zorder=3,
                bbox=dict(boxstyle="round,pad=0.2",fc="white",ec=MUT,alpha=.9))

    from shapely.ops import nearest_points as _np_
    def f2m(px,py):
        a=np.asarray(px,float)/100.0; b=np.asarray(py,float)/100.0
        u,v=_var(a,b,vi)
        return mx0+(u-u0)/(u1-u0)*W, my0+(v-v0)/(v1-v0)*H
    ocupados=[]
    for p in d.get("points",[]):
        MX,MY=f2m([p[0]],[p[1]]); mxp,myp=MX[0],MY[0]
        pt=Point(mxp,myp)
        if piso is not None and not piso.buffer(0.05).contains(pt):
            q=_np_(piso.buffer(-0.15),pt)[0]
            if pt.distance(q)<=0.90:
                # desvío chico de calibración: jalarlo al interior
                mxp,myp=q.x,q.y; pt=Point(mxp,myp)
            # lejos del piso modelado = cuarto sin piezas en el DWG (p.ej. baño de
            # charola): se respeta la posición de campo, sin aplastarlo al muro
        if U.contains(pt) or U.distance(pt)<0.05:   # dentro o pegado a muro: empujar a espacio libre
            q=_np_(U.boundary,pt)[0]
            if U.contains(pt):
                dxn,dyn=q.x-mxp,q.y-myp
            else:
                dxn,dyn=mxp-q.x,myp-q.y
            n=(dxn**2+dyn**2)**0.5 or 1.0
            cand=Point(q.x+dxn/n*0.16,q.y+dyn/n*0.16)
            if U.contains(cand):   # salió del lado equivocado: invertir
                cand=Point(q.x-dxn/n*0.16,q.y-dyn/n*0.16)
            mxp,myp=cand.x,cand.y
        X,Y=m2d([mxp],[myp]); x,y=X[0],Y[0]; v=p[2]
        col=GREY if v==0 else (REL if v<0 else COR)
        ax.plot([x],[y],marker="o",ms=3.0,color=col,zorder=4,clip_on=True)
        dx=-3 if x>SA*0.9 else 3; ha="right" if dx<0 else "left"
        dy=-3 if y>SB*0.93 else 3
        # anti-colisión: si hay otra etiqueta muy cerca, desplazar más
        extra=0
        for (ox,oy) in ocupados:
            if abs(x-ox)<0.30 and abs(y-oy)<0.22: extra+=5
        extra=min(extra,10)
        ocupados.append((x,y))
        ax.annotate(f"{v:g}",(x,y),xytext=(dx,-dy-extra),textcoords="offset points",
                    fontsize=5.8,color=INK,ha=ha,zorder=5,clip_on=True,annotation_clip=True,
                    path_effects=[pe.withStroke(linewidth=1.4,foreground="white")])
    puntos_m=[Point(*f2m([p[0]],[p[1]])[0:1][0] if False else (f2m([p[0]],[p[1]])[0][0],f2m([p[0]],[p[1]])[1][0])) for p in d.get("points",[])]
    def _spot_libre(zpt):
        import math
        cands=[zpt]+[Point(zpt.x+r*math.cos(t),zpt.y+r*math.sin(t))
                     for r in (0.35,0.6,0.9,1.3) for t in [k*math.pi/4 for k in range(8)]]
        for c in cands:
            if piso is not None and not piso.buffer(-0.12).contains(c): continue
            if U.buffer(0.06).contains(c): continue
            if any(c.distance(pm)<0.34 for pm in puntos_m): continue
            return c
        return zpt
    for z in d.get("zones",[]):
        MZX,MZY=f2m([z["x"]],[z["y"]]); zpt=_spot_libre(Point(MZX[0],MZY[0]))
        X,Y=m2d([zpt.x],[zpt.y]); x=min(max(X[0],pad),SA-pad); y=min(max(Y[0],pad),SB-pad)
        col=REL if z.get("tipo")=="relleno" else COR
        tint=REL_T if z.get("tipo")=="relleno" else COR_T
        ax.text(x,y,z.get("label",""),fontsize=6.4,color=col,style="italic",ha="center",zorder=6,clip_on=True,
                bbox=dict(boxstyle="round,pad=0.25",fc=tint,ec=col,lw=0.6,alpha=.93))

    lx=fig.add_axes([0.05,0.052,0.90,0.062]); lx.axis("off")
    lx.add_patch(Rectangle((0,0),1,1,transform=lx.transAxes,facecolor="#fafafa",edgecolor="#d5d9df",lw=0.8))
    vals=[p[2] for p in d.get("points",[])]
    hs=[];labs=[]
    if any(v<0 for v in vals): hs.append(Line2D([],[],marker="o",ls="",color=REL,ms=6)); labs.append("Relleno (cota −)")
    if any(v>0 for v in vals): hs.append(Line2D([],[],marker="o",ls="",color=COR,ms=6)); labs.append("Corte (cota +)")
    if any(v==0 for v in vals): hs.append(Line2D([],[],marker="o",ls="",color=GREY,ms=6)); labs.append("A nivel (0)")
    if d.get("stairs") or esc_draw: hs.append(Rectangle((0,0),1,1,facecolor="#f3f4f6",edgecolor=MUT,hatch="///")); labs.append("Escalera (hueco)")
    if d.get("vacios"): hs.append(Rectangle((0,0),1,1,facecolor="none",edgecolor=MUT,hatch="xx")); labs.append("Vacío / sin losa")
    lx.legend(hs,labs,loc="center",ncol=len(hs),frameon=False,fontsize=7.0,handlelength=1.1,columnspacing=1.0,borderaxespad=0.2)
    ft=nota_footer if len(nota_footer)<=118 else nota_footer[:115]+"..."
    fig.text(0.05,0.026,ft,fontsize=7.0,color=GREY)
    fig.text(0.95,0.026,"Levantó: Mauricio Gastelum Mora",fontsize=7.0,color=GREY,ha="right")
    fig.text(0.95,0.012,"Muros: geometría exacta del despiece (DWG)",fontsize=6.2,color=MUT,ha="right")
    if pdf is None: return fig,score
    pdf.savefig(fig); plt.close(fig); return None,score
