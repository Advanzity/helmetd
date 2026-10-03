import urllib.request,urllib.parse,json,concurrent.futures,pathlib
U='https://gis.semcog.org/server/rest/services/hosted/Building_Footprints/FeatureServer/14/query?'
base={'where':'1=1','geometry':'-83.10,42.624,-82.967,42.72','geometryType':'esriGeometryEnvelope','inSR':4326,'spatialRel':'esriSpatialRelIntersects','f':'json','returnIdsOnly':'true'}
d=json.load(urllib.request.urlopen(U+urllib.parse.urlencode(base),timeout=60));ids=d['objectIds'];print('IDs',len(ids),flush=True)
def batch(i):
 p=pathlib.Path(f'work/macomb-source-data/township-buildings-b{i}.json')
 if p.exists():return
 q={'objectIds':','.join(map(str,ids[i:i+250])),'outFields':'*','outSR':4326,'f':'geojson'}
 for attempt in range(3):
  try:
   data=urllib.request.urlopen(U+urllib.parse.urlencode(q),timeout=120).read();j=json.loads(data);assert 'features'in j;p.write_bytes(data);print(i,len(j['features']),flush=True);return
  except Exception as e:
   if attempt==2:raise
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(batch,range(0,len(ids),250)))
