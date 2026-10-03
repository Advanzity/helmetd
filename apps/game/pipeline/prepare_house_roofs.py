import json,math
from shapely.geometry import Polygon,LineString,Point
from shapely.ops import split,triangulate
P='outputs/shelby-ride/public/assets/world.json';w=json.load(open(P));count=0
for b in w['buildings']:
 if b.get('type') not in ['house','residential','detached','semidetached_house','terrace']:continue
 poly=Polygon(b['points'])
 if not poly.is_valid or poly.area<35 or poly.area>700:continue
 rect=list(poly.minimum_rotated_rectangle.exterior.coords);a,q=rect[:2];c=poly.centroid;dx=q[0]-a[0];dy=q[1]-a[1];length=math.hypot(dx,dy);dx/=length;dy/=length
 if math.dist(rect[1],rect[2])>length:dx,dy=-dy,dx
 cross=[-(p[0]-c.x)*dy+(p[1]-c.y)*dx for p in b['points']];half=max(abs(min(cross)),abs(max(cross)));rise=min(2.8,half*.5)
 def z(x,y):return b['base']+b['height']+rise*max(0,1-abs(-(x-c.x)*dy+(y-c.y)*dx)/half)
 divider=LineString([(c.x-dx*100,c.y-dy*100),(c.x+dx*100,c.y+dy*100)])
 faces=[]
 for part in split(poly,divider).geoms:
  for t in triangulate(part):
   if not part.covers(t.representative_point()):continue
   faces.append([[x,y,z(x,y)] for x,y in list(t.exterior.coords)[:3]])
 b['roofFaces']=faces;b['roofEdges']=[[x,y,z(x,y)] for x,y in b['points']];count+=1
json.dump(w,open(P,'w'),separators=(',',':'));print(count,'pitched roofs',flush=True)
