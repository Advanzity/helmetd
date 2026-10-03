import json,glob,math
import rasterio
from pyproj import Transformer
from shapely.geometry import Polygon,Point,LineString
from shapely.strtree import STRtree
P='outputs/shelby-ride/public/assets/world.json';w=json.load(open(P));tr=Transformer.from_crs(4326,32617,always_xy=True);ox,oy=tr.transform(*w['origin']);ds=rasterio.open('work/macomb-source-data/township-dem.tif');arr=ds.read(1)
existing=[Polygon(b['points']).buffer(0) for b in w['buildings']];tree=STRtree(existing);ids=set(str(b['id']) for b in w['buildings']);local=[r for r in w['roads'] if r['class']=='residential'];roads=STRtree([LineString([p[:2] for p in r['points']]) for r in local]);n=0
for file in glob.glob('work/macomb-source-data/township-buildings-*.json'):
 for f in json.load(open(file))['features']:
  g=f['geometry'];polys=g['coordinates'] if g['type']=='MultiPolygon' else [g['coordinates']]
  for raw in polys:
   points=[]
   for p in raw[0]:
    x,y=tr.transform(*p[:2]);points.append([round(x-ox,2),round(y-oy,2)])
   poly=Polygon(points)
   if not poly.is_valid or poly.area<30:continue
   if any(existing[i].intersection(poly).area>poly.area*.35 for i in tree.query(poly)):continue
   prop=f['properties'];id=prop['building_id']
   if str(id) in ids:continue
   x,y=poly.centroid.coords[0];r,c=ds.index(x+ox,y+oy);base=float(arr[max(0,min(ds.height-1,r)),max(0,min(ds.width-1,c))])-w['baseElevation'];h=max(2.7,min(35,float(prop.get('median_hgt') or 13)*.3048));near=roads.nearest(poly.centroid);distance=roads.geometries[near].distance(poly.centroid);house=65<poly.area<500 and h<8 and distance<85
   w['buildings'].append({'id':id,'points':points,'height':round(h,2),'base':round(base,2),'type':'house' if house else 'yes','typeSource':'inferred from footprint and nearby residential road','source':'SEMCOG 2019'});ids.add(str(id));n+=1
json.dump(w,open(P,'w'),separators=(',',':'));print('Added',n,'total',len(w['buildings']),flush=True)
