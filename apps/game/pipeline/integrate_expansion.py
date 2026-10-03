import json,pathlib,xml.etree.ElementTree as ET,math
import rasterio,numpy as np
from pyproj import Transformer
O=pathlib.Path('outputs/shelby-ride/public/assets/world.json');w=json.load(open(O));tr=Transformer.from_crs(4326,32617,always_xy=True);ox,oy=tr.transform(*w['origin'])
with rasterio.open('work/macomb-source-data/corridor-dem.tif') as ds:
 data=ds.read(1);print('DEM',data.min(),data.max(),ds.crs,flush=True)
 def height(x,y):
  row,col=ds.index(ox+x,oy+y);value=float(data[max(0,min(ds.height-1,row)),max(0,min(ds.width-1,col))]);return round(value-w['baseElevation'],3) if value>-100 else 0
 nx=121;ny=561;b=w['bounds'];h=[height(b[0]+(b[2]-b[0])*i/(nx-1),b[1]+(b[3]-b[1])*j/(ny-1)) for j in range(ny) for i in range(nx)];w['outerTerrain']={'nx':nx,'ny':ny,'heights':h,'bounds':b}
 for r in w['roads']:
  for p in r['points']:
   if abs(p[0])>1700 or abs(p[1])>1700:p[2]=height(*p[:2])+.06+(5 if r['bridge'] else 0)
 # Smooth bridge endpoints into adjoining approach segments.
 bridge={}
 for r in w['roads']:
  if r['bridge']:
   for n,p in zip(r['nodeIds'],r['points']):bridge[n]=p[2]
 for r in w['roads']:
  if r['bridge']:continue
  dist=[0]
  for a,q in zip(r['points'],r['points'][1:]):dist.append(dist[-1]+math.dist(a[:2],q[:2]))
  for idx in [0,-1]:
   if r['nodeIds'][idx] not in bridge:continue
   delta=bridge[r['nodeIds'][idx]]-r['points'][idx][2]
   for i,p in enumerate(r['points']):p[2]+=delta*max(0,1-abs(dist[i]-dist[idx])/100)
 nodes={};ways={}
 for f in pathlib.Path('work/macomb-source-data').glob('corridor-*.osm'):
  root=ET.parse(f).getroot();nodes.update({n.get('id'):n for n in root.findall('node')});ways.update({n.get('id'):n for n in root.findall('way')})
 existing=set(str(b['id']) for b in w['buildings'])
 for id,way in ways.items():
  if 'expanded-'+id in existing:continue
  tags={t.get('k'):t.get('v') for t in way.findall('tag')}
  if 'building' not in tags:continue
  pts=[]
  for ref in way.findall('nd'):
   n=nodes.get(ref.get('ref'))
   if n is None:continue
   x,y=tr.transform(float(n.get('lon')),float(n.get('lat')));pts.append([round(x-ox,2),round(y-oy,2)])
  if len(pts)<4:continue
  x=sum(p[0] for p in pts)/len(pts);y=sum(p[1] for p in pts)/len(pts)
  if abs(x)<1700 and abs(y)<1700 or not(w['bounds'][0]<x<w['bounds'][2] and w['bounds'][1]<y<w['bounds'][3]):continue
  try:h=float(tags.get('height',float(tags.get('building:levels',1))*3.4))
  except:h=3.4
  w['buildings'].append({'id':'expanded-'+id,'points':pts,'height':max(3,min(40,h)),'base':height(x,y)})
json.dump(w,open(O,'w'),separators=(',',':'));print('buildings',len(w['buildings']),flush=True)
