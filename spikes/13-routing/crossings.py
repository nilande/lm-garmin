import sys
from collections import Counter
import numpy as np, pyogrio, shapely
G=sys.argv[1]
AREAS={"taby":(664000,6584000,680000,6600000),"tarnaby":(490000,7265000,540000,7315000)}
for area,bbox in AREAS.items():
    geoms=[];info=[]
    for layer,cols in (("vaglinje",["objekttypnr","bro_och_tunnel"]),("ovrig_vag",["objekttypnr"])):
        _,_,wkb,f=pyogrio.raw.read(G,layer=layer,bbox=bbox,columns=cols)
        for n,g in enumerate(shapely.from_wkb(wkb)):
            for p in shapely.get_parts(g):
                geoms.append(p); info.append((layer[:4], f[1][n] if len(f)>1 else None))
    verts={}
    for i,g in enumerate(geoms):
        for xy in shapely.get_coordinates(g): verts.setdefault(tuple(np.round(xy*1000).astype(int)),set()).add(i)
    tree=shapely.STRtree(geoms); c=Counter()
    a,b=tree.query(geoms,predicate="crosses")
    for i,j in zip(a,b):
        if i>=j: continue
        for pt in shapely.get_coordinates(shapely.intersection(geoms[i],geoms[j])):
            shared = verts.get(tuple(np.round(pt*1000).astype(int)),set())>={i,j}
            bridge = any(x[1] not in (None,"Ingen information") for x in (info[i],info[j]))
            pair="-".join(sorted([info[i][0],info[j][0]]))
            c[(pair,"shared" if shared else "bare","bridge/tunnel" if bridge else "level")]+=1
    print(area); [print("  ",k,v) for k,v in sorted(c.items())]
    print("   bro_och_tunnel values:",Counter(x[1] for x in info if x[0]=="vagl").most_common(6))
