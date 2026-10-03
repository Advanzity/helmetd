import json,pathlib,urllib.request,xml.etree.ElementTree as ET,time,math
from concurrent.futures import ThreadPoolExecutor
S=pathlib.Path('work/macomb-source-data');d=json.load(open(S/'shelby-boundaries.geojson'));f=next(f for f in d['features'] if f['properties']['FIPSCODE']=='72820');json.dump(f,open(S/'shelby-township-boundary.geojson','w'));p=f['geometry']['coordinates'][0];bounds=[min(v[0] for v in p),min(v[1] for v in p),max(v[0] for v in p),max(v[1] for v in p)];print('BOUNDARY',bounds,f['properties']['SQMILES'],flush=True)
west,south,east,north=bounds;nx=math.ceil((east-west)/.022);ny=math.ceil((north-south)/.018);tiles=[]
for iy in range(ny):
 for ix in range(nx):tiles.append((ix,iy,[west+(east-west)*ix/nx-.001,south+(north-south)*iy/ny-.001,west+(east-west)*(ix+1)/nx+.001,south+(north-south)*(iy+1)/ny+.001]))
def fetch(tile):
 ix,iy,b=tile;p=S/f'township-{ix}-{iy}.osm'
 if p.exists():return
 for retry in range(4):
  try:
   u='https://api.openstreetmap.org/api/0.6/map?bbox='+','.join(map(str,b));req=urllib.request.Request(u,headers={'User-Agent':'ShelbyRide-local-map/1.0'});data=urllib.request.urlopen(req,timeout=70).read();ET.fromstring(data);p.write_bytes(data);print('tile',ix,iy,len(data),flush=True);return
  except Exception as e:
   if retry==3:raise
   time.sleep(2+retry*2)
with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(fetch,tiles))
print('COMPLETE',len(tiles),flush=True)
