import json,pathlib,xml.etree.ElementTree as ET,math,re
import numpy as np,rasterio
from pyproj import Transformer
from shapely.geometry import shape,Polygon,LineString,Point
from shapely.ops import transform
S=pathlib.Path('work/macomb-source-data');O=pathlib.Path('outputs/shelby-ride/public/assets');w=json.load(open(O/'world.json'));(S/'world-before-township.json').write_text(json.dumps(w)) if not(S/'world-before-township.json').exists() else None
tr=Transformer.from_crs(4326,32617,always_xy=True);ox,oy=tr.transform(*w['origin']);xy=lambda lon,lat:(tr.transform(lon,lat)[0]-ox,tr.transform(lon,lat)[1]-oy)
f=json.load(open(S/'shelby-township-boundary.geojson'));boundary=transform(xy,shape(f['geometry']));w['townshipBoundary']=[[round(x,2),round(y,2)] for x,y in boundary.exterior.coords];xmin,ymin,xmax,ymax=boundary.bounds;w['bounds']=[math.floor(xmin-200),-9700,math.ceil(xmax+200),math.ceil(ymax+200)]
ds=rasterio.open(S/'township-dem.tif');arr=ds.read(1)
def height(x,y):
 r,c=ds.index(x+ox,y+oy);v=float(arr[max(0,min(ds.height-1,r)),max(0,min(ds.width-1,c))]);return round(v-w['baseElevation'],3) if v>0 else 0
nodes={};ways={};relations={}
for file in list(S.glob('corridor-*.osm'))+list(S.glob('township-*.osm')):
 root=ET.parse(file).getroot();nodes.update({e.get('id'):e for e in root.findall('node')});ways.update({e.get('id'):e for e in root.findall('way')});relations.update({e.get('id'):e for e in root.findall('relation')})
coord={id:[round(v,2) for v in xy(float(n.get('lon')),float(n.get('lat')))] for id,n in nodes.items()};old={r['id']:r for r in w['roads']};roads={};signals=[];stops=[];circles=[];lands={};buildings={str(b['id']):b for b in w['buildings']};parking=[];buffer=boundary.buffer(220)
for id,n in nodes.items():
 t={a.get('k'):a.get('v') for a in n.findall('tag')};hw=t.get('highway')
 if hw=='traffic_signals':signals.append({'node':id,'point':coord[id]})
 if hw in ['stop','give_way']:stops.append({'node':id,'point':coord[id],'kind':hw})
 if hw=='turning_circle':circles.append({'node':id,'point':coord[id],'radius':13.4})
for id,way in ways.items():
 t={a.get('k'):a.get('v') for a in way.findall('tag')};ids=[n.get('ref') for n in way.findall('nd')];pts=[coord[n] for n in ids if n in coord]
 if len(pts)!=len(ids) or len(pts)<2:continue
 inTown=buffer.intersects(LineString(pts));inCorridor=id in old
 if not inTown and not inCorridor:continue
 hw=t.get('highway');one=t.get('oneway') in ['yes','-1'] or t.get('junction')=='roundabout'
 if hw in ['motorway','motorway_link','trunk','trunk_link','primary','primary_link','secondary','tertiary','residential','unclassified','service','living_street']:
  if t.get('access')=='no':continue
  default=1 if hw.endswith('link') or hw in ['service','living_street'] else 2
  try:lanes=int(t.get('lanes',str(default)).split(';')[0])
  except:lanes=default
  lw=3.6576 if hw in ['motorway','trunk'] else 3.3528;left=right=.3;width=lanes*lw+.6;source='mapped lanes, estimated cross-section' if 'lanes' in t else 'class-based estimate';curb=hw not in ['motorway','motorway_link'] and t.get('surface') not in ['gravel','unpaved']
  if hw=='motorway':lw=3.65;left=1.2;right=3;width=lanes*lw+left+right
  elif hw in ['residential','living_street','unclassified']:
   lanes=1 if one else 2;lw=3.3528;width=6.096 if one else 8.5344;left=right=(width-lanes*lw)/2;source='MCDR 28 ft subdivision fallback' if not one else 'Shelby 20 ft boulevard fallback'
   if t.get('surface') in ['gravel','unpaved']:width=7.3152;left=right=(width-lanes*lw)/2;curb=False;source='MCDR 24 ft open-ditch fallback'
  elif hw=='service':lw=3.1;width=3.66 if t.get('service')=='driveway' else 7.3152;lanes=1 if t.get('service')=='driveway' or one else 2;left=right=max(0,(width-lanes*lw)/2);source='service access estimate'
  if t.get('width'):
   m=re.search(r'[\d.]+',t['width'])
   if m:
    v=float(m.group())*(.3048 if 'ft' in t['width'] else 1)
    if 2<v<50:width=v;left=right=max(0,(width-lanes*lw)/2);source='mapped width'
  if t.get('oneway')=='-1':pts=list(reversed(pts));ids=list(reversed(ids))
  bridge=t.get('bridge')=='yes';existing=old.get(id);points=[]
  for i,(x,y) in enumerate(pts):
   z=height(x,y)+.06+(5 if bridge else 0)
   if existing and ids[i] in existing['nodeIds']:z=existing['points'][existing['nodeIds'].index(ids[i])][2]
   points.append([x,y,z])
  roads[id]={'id':id,'name':t.get('name',t.get('ref','Local road')),'class':hw,'lanes':lanes,'laneWidth':lw,'width':round(width,4),'leftShoulder':left,'rightShoulder':right,'shoulder':right,'pavementOffset':(left-right)/2,'widthSource':source,'curb':curb,'oneway':one,'bridge':bridge,'surface':t.get('surface','concrete' if hw=='residential' else 'asphalt'),'points':points,'nodeIds':ids,'maxspeed':t.get('maxspeed','25' if hw in ['residential','living_street','unclassified'] else '15' if hw=='service' else ''),'junction':t.get('junction',''),'turnLanes':t.get('turn:lanes',t.get('turn:lanes:forward',''))}
 elif len(pts)>3 and inTown:
  typ=t.get('landuse',t.get('natural',t.get('waterway')))
  if typ:lands[id]={'type':typ,'points':pts}
 if inTown and 'building' in t and len(pts)>3:
  poly=Polygon(pts)
  if not poly.is_valid or poly.area<30:continue
  x,y=poly.centroid.coords[0]
  if abs(x)<1700 and abs(y)<1700:continue
  try:h=float(t.get('height',float(t.get('building:levels',1))*3.4))
  except:h=3.4
  buildings['expanded-'+id]={'id':'expanded-'+id,'points':pts,'height':max(3,min(40,h)),'base':height(x,y),'type':t['building']}
 if inTown and t.get('amenity')=='parking' and len(pts)>3:
  poly=Polygon(pts)
  if poly.is_valid:parking.append({'points':pts,'area':round(poly.area)})
# Store turn restrictions for the traffic routing graph.
restrictions=[]
for rel in relations.values():
 t={a.get('k'):a.get('v') for a in rel.findall('tag')}
 if t.get('type')!='restriction':continue
 members={a.get('role'):a.get('ref') for a in rel.findall('member')};kind=t.get('restriction','')
 if members.get('from') in roads and members.get('to') in roads:restrictions.append({**members,'kind':kind})
w.update(roads=list(roads.values()),buildings=list(buildings.values()),signals=signals,stops=stops,turningCircles=circles,restrictions=restrictions,land=list(lands.values())+w['land'],coverage='Full Shelby Township boundary plus the 15–25 Mile connector corridor',townshipAreaSquareMiles=f['properties']['SQMILES'])
b=w['bounds'];nx=math.ceil((b[2]-b[0])/25)+1;ny=math.ceil((b[3]-b[1])/25)+1;h=[height(b[0]+(b[2]-b[0])*i/(nx-1),b[1]+(b[3]-b[1])*j/(ny-1)) for j in range(ny) for i in range(nx)];w['outerTerrain']={'nx':nx,'ny':ny,'bounds':b,'heights':h}
json.dump(w,open(O/'world.json','w'),separators=(',',':'));json.dump(parking,open(O/'parking.json','w'),separators=(',',':'));print('FINAL',len(roads),'roads',sum(r['class']=='residential' for r in roads.values()),'residential',len(buildings),'buildings',len(signals),'signals',len(stops),'stops',len(restrictions),'restrictions',w['bounds'],flush=True)
