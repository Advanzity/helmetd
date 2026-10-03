import json
from shapely.geometry import Polygon
from shapely.strtree import STRtree
p='outputs/shelby-ride/public/assets/world.json';w=json.load(open(p));lands=[Polygon(l['points']).buffer(0) for l in w['land'] if l['type']=='residential'];tree=STRtree(lands);n=0
for b in w['buildings']:
 if b.get('type') not in [None,'yes']:continue
 poly=Polygon(b['points']).buffer(0)
 if 65<poly.area<420 and b['height']<8 and any(lands[i].covers(poly.centroid) for i in tree.query(poly.centroid)):
  b['type']='house';b['typeSource']='inferred from residential land use and footprint';n+=1
json.dump(w,open(p,'w'),separators=(',',':'));print('Classified',n)
