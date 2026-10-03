import json,xml.etree.ElementTree as ET,math,pathlib
import numpy as np,rasterio
from pyproj import Transformer
from shapely.geometry import Polygon,box
ROOT=pathlib.Path('/Users/david/Documents/Codex/2026-10-01/c');out=ROOT/'outputs/shelby-ride/public/assets';src=ROOT/'work/macomb-source-data'
lon0,lat0=-83.0245,42.6295
tr=Transformer.from_crs(4326,32617,always_xy=True);e0,n0=tr.transform(lon0,lat0)
def xy(lon,lat):
 e,n=tr.transform(lon,lat);return e-e0,n-n0
with rasterio.open(src/'shelby-dem.tif') as ds:
 print('DEM',ds.crs,ds.bounds)
 dt=Transformer.from_crs(32617,ds.crs,always_xy=True)
 size=3600;N=241;coords=[dt.transform(e0-size/2+i*size/(N-1),n0-size/2+j*size/(N-1)) for j in range(N) for i in range(N)]
 vals=np.array([float(v[0]) for v in ds.sample(coords)]).reshape((N,N));valid=vals[vals>-100];base=float(np.median(valid));vals[vals<-100]=base;vals-=base
 def height(x,y):
  u=min(N-1,max(0,(x/size+.5)*(N-1)));v=min(N-1,max(0,(y/size+.5)*(N-1)));i=min(N-2,int(u));j=min(N-2,int(v));a=u-i;b=v-j;return float(vals[j,i]*(1-a)*(1-b)+vals[j,i+1]*a*(1-b)+vals[j+1,i]*(1-a)*b+vals[j+1,i+1]*a*b)
 root=ET.parse(src/'shelby.osm').getroot();nodes={n.get('id'):xy(float(n.get('lon')),float(n.get('lat'))) for n in root.findall('node')};roads=[];land=[];osmBuildings=[]
 for w in root.findall('way'):
  tags={t.get('k'):t.get('v') for t in w.findall('tag')};pts=[nodes[n.get('ref')] for n in w.findall('nd') if n.get('ref') in nodes]
  if len(pts)<2 or not any(abs(x)<1750 and abs(y)<1750 for x,y in pts):continue
  hw=tags.get('highway')
  if hw in ['motorway','motorway_link','trunk','trunk_link','primary','primary_link','secondary','tertiary','residential','unclassified','service','living_street']:
   lanes=int(tags.get('lanes','1' if hw.endswith('link') or hw=='service' else '2').split(';')[0]);width=lanes*3.6+(2 if hw=='motorway' else 1)
   coords=[]
   for i,(x,y) in enumerate(pts):
    h=height(x,y)+.06
    # Bridges have measured ground elevation plus an approximate 5m deck clearance.
    if tags.get('bridge')=='yes':h+=5
    coords.append([round(x,2),round(y,2),round(h,3)])
   roads.append({'id':w.get('id'),'name':tags.get('name',tags.get('ref','Ramp' if hw.endswith('link') else 'Local road')),'class':hw,'lanes':lanes,'width':width,'oneway':tags.get('oneway')=='yes','bridge':tags.get('bridge')=='yes','surface':tags.get('surface','asphalt'),'points':coords,'nodeIds':[n.get('ref') for n in w.findall('nd')]})
  elif tags.get('landuse') or tags.get('natural') or tags.get('waterway'):
   if len(pts)>3:land.append({'type':tags.get('landuse',tags.get('natural',tags.get('waterway'))),'points':[[round(x,2),round(y,2)] for x,y in pts]})
  if 'building' in tags and len(pts)>3:osmBuildings.append((pts,tags))
 # continuous endpoint heights propagated to adjoining approaches to avoid vertical lips
 bridges={}
 for r in roads:
  if r['bridge']:
   for node,p in zip(r['nodeIds'],r['points']):bridges[node]=p[2]
 for r in roads:
  if r['bridge']:continue
  pts=r['points'];distance=[0]
  for a,b in zip(pts,pts[1:]):distance.append(distance[-1]+math.dist(a[:2],b[:2]))
  for end,idx in [(0,0),(-1,-1)]:
   if r['nodeIds'][idx] in bridges:
    delta=bridges[r['nodeIds'][idx]]-pts[idx][2]
    for i,p in enumerate(pts):p[2]+=delta*max(0,1-abs(distance[i]-distance[idx])/100)
 # SEMCOG records filtered to the playable square; heights are feet in the source.
 buildings=[]
 for f in json.load(open(src/'shelby-buildings.geojson'))['features']:
  geom=f['geometry'];polys=geom['coordinates'] if geom['type']=='MultiPolygon' else [geom['coordinates']]
  for poly in polys:
   pts=[xy(*v[:2]) for v in poly[0]];p=Polygon(pts)
   if p.is_empty or not p.is_valid or p.area<35 or not box(-1700,-1700,1700,1700).contains(p):continue
   x,y=p.centroid.coords[0];h=max(3,float(f['properties'].get('median_hgt') or 16)*.3048)
   buildings.append({'id':f['properties']['building_id'],'points':[[round(x,2),round(y,2)] for x,y in pts],'height':round(min(h,35),2),'base':round(height(x,y),2)})
 # OSM provides current geometry in the southern edge if SEMCOG result truncates.
 existing=[Polygon(b['points']) for b in buildings]
 for pts,tags in osmBuildings:
  p=Polygon(pts)
  if not p.is_valid or p.area<35 or not box(-1700,-1700,1700,1700).contains(p):continue
  if any(q.contains(p.representative_point()) for q in existing):continue
  x,y=p.centroid.coords[0];h=float(tags.get('building:levels','1'))*3.5
  buildings.append({'id':'osm','points':[[round(x,2),round(y,2)] for x,y in pts],'height':h,'base':round(height(x,y),2)})
 data={'origin':[lon0,lat0],'baseElevation':base,'size':size,'resolution':N,'heights':np.round(vals,3).flatten().tolist(),'roads':roads,'buildings':buildings,'land':land,'sources':['OpenStreetMap contributors, ODbL','SEMCOG Building Footprints (2019)','USGS 3DEP Macomb 2016']}
 (out/'world.json').write_text(json.dumps(data,separators=(',',':')));print('WORLD',len(roads),'roads',len(buildings),'buildings',len(land),'land polygons', 'height range',vals.min(),vals.max())
 print('HALL',[(r['id'],r['points'][0],r['points'][-1]) for r in roads if r['name']=='Hall Road'][:12])
