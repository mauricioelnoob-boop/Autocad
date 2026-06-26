import json,re,sys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon,Rectangle
import datos_piezas as D
SP="/tmp/claude-0/-home-user-Autocad/d15acb21-ec3d-5e7a-85b6-2130d9969519/scratchpad"
def declean(t): t=re.sub(r"\\[A-Za-z][^;]*;","",t); return re.sub(r"[{}]","",t).strip()
def layers(d):
    cm={}
    for o in d['OBJECTS']:
        if o.get('object')=='LAYER':
            h=o.get('handle'); cm[h[-1] if isinstance(h,list) else h]=o.get('name')
    return cm
def lname(o,cm):
    l=o.get('layer'); return cm.get(l[-1],'?') if isinstance(l,list) else '?'
def render(modelo,jsonp,bbox,targets,fname,title):
    X0,X1,Y0,Y1=bbox
    ps=D.cargar_anotado(modelo)
    d=json.loads(open(jsonp,'rb').read().decode('utf-8','replace'))
    cm=layers(d)
    fig,ax=plt.subplots(figsize=(15,15))
    # walls
    try:
        for poly in json.load(open(f"muros_real_{modelo.lower()}.json")):
            xs=[p[0] for p in poly]; ys=[p[1] for p in poly]
            if max(xs)<X0 or min(xs)>X1 or max(ys)<Y0 or min(ys)>Y1: continue
            ax.add_patch(Polygon(poly,closed=True,facecolor='#555',edgecolor='#222',lw=0.3,alpha=0.55))
    except Exception as e: print('muros?',e)
    # doors + zoclo + acabados from dwg json
    for o in d['OBJECTS']:
        L=lname(o,cm); e=o.get('entity')
        if e=='LINE' and 'PUERTA' in L:
            s=o.get('start'); en=o.get('end')
            if s and en and X0<=s[0]<=X1 and Y0<=s[1]<=Y1:
                ax.plot([s[0],en[0]],[s[1],en[1]],color='saddlebrown',lw=1.4)
        if e=='ARC' and 'PUERTA' in L:
            c=o.get('center')
            if c and X0<=c[0]<=X1 and Y0<=c[1]<=Y1:
                import numpy as np
                a0=o.get('start_angle',0);a1=o.get('end_angle',6.28);r=o.get('radius',0)
                t=np.linspace(a0,a1,20); ax.plot(c[0]+r*np.cos(t),c[1]+r*np.sin(t),color='saddlebrown',lw=0.8,ls=':')
        if e=='LWPOLYLINE' and L=='A-ZOCLO':
            pts=o.get('points',[])
            if pts and X0<=pts[0][0]<=X1 and Y0<=pts[0][1]<=Y1:
                ax.add_patch(Polygon([(p[0],p[1]) for p in pts],closed=False,fill=False,edgecolor='red',lw=1.0))
        if e in('TEXT','MTEXT'):
            t=o.get('text_value') or o.get('text') or ''; pt=o.get('ins_pt') or [0,0]
            x,y=(pt[0],pt[1]) if isinstance(pt,list) else (0,0); tt=declean(t)
            if X0<=x<=X1 and Y0<=y<=Y1 and re.search(r'(?i)regadera|rec.mara|vest|ba.o|lava|cocina|comedor|sala|principal|alacena|closet|sube|baja',tt):
                ax.text(x,y,tt[:16],fontsize=8,color='darkgreen',ha='center',weight='bold',zorder=9)
    # pieces
    for p in ps:
        if not all(k in p for k in('x0','y0','wx','hy')): continue
        cx,cy=p['x'],p['y']
        if not(X0<=cx<=X1 and Y0<=cy<=Y1): continue
        col='#e0b074' if p['material']=='Moret' else '#7fa6cf'
        tgt=p.get('id') in targets
        ax.add_patch(Rectangle((p['x0'],p['y0']),p['wx'],p['hy'],facecolor='yellow' if tgt else col,
                     edgecolor='magenta' if tgt else '#333',lw=2.2 if tgt else 0.5,alpha=0.95 if tgt else 0.8,zorder=8 if tgt else 3))
        idtxt=p.get('id','').replace('PA-','').replace('PB-','')
        ax.text(cx,cy,idtxt,fontsize=5.2 if not tgt else 7,ha='center',va='center',
                color='black',weight='bold' if tgt else 'normal',rotation=90 if p['hy']>0.8 and p['wx']<0.3 else 0,zorder=10)
    ax.set_xlim(X0,X1);ax.set_ylim(Y0,Y1);ax.set_aspect('equal');ax.set_title(title,fontsize=11)
    ax.grid(True,alpha=0.2)
    fig.savefig(fname,dpi=115,bbox_inches='tight');plt.close()
    print('saved',fname)
if __name__=='__main__':
    pass
