import urllib.request,xml.etree.ElementTree as ET,json,math,time,pathlib
from pyproj import Transformer
R=pathlib.Path('/Users/david/Documents/Codex/2026-10-01/c');O=R/'outputs/shelby-ride/public/assets';S=R/'work/macomb-source-data';w=json.load(open(O/'world.json'));(S/'world-before-expansion.json').write_text(json.dumps(w)) if not (S/'world-before-expansion.json').exists() else None
nodes={};ways={}
for i in range(9):
 lo=42.545+i*.018;hi=lo+.019;p=S/f'corridor-{i}.osm'
 if not p.exists():
  url=f'https://api.openstreetmap.org/api/0.6/map?bbox=-83.047,{lo},-83.004,{hi}'
  for attempt in range(3):
   try:urllib.request.urlretrieve(url,p);break
   except Exception:
    if attempt==2:raise
    time.sleep(2)
 root=ET.parse(p).getroot();nodes.update({n.get('id'):n for n in root.findall('node')});ways.update({n.get('id'):n for n in root.findall('way')});print('tile',i,flush=True)
tr=Transformer.from_crs(4326,32617,always_xy=True);ox,oy=tr.transform(*w['origin'])
def xy(n):
 x,y=tr.transform(float(n.get('lon')),float(n.get('lat')));return [round(x-ox,2),round(y-oy,2)]
def height(x,y):
 d=w;n=d['resolution'];u=max(0,min(n-1.001,(x/d['size']+.5)*(n-1)));v=max(0,min(n-1.001,(y/d['size']+.5)*(n-1)));i=int(u);j=int(v);a=u-i;b=v-j;h=d['heights'];return h[j*n+i]*(1-a)*(1-b)+h[j*n+i+1]*a*(1-b)+h[(j+1)*n+i]*(1-a)*b+h[(j+1)*n+i+1]*a*b
roads={r['id']:r for r in w['roads']};signals=[]
for id,n in nodes.items():
 tags={t.get('k'):t.get('v') for t in n.findall('tag')}
 if tags.get('highway')=='traffic_signals':signals.append({'node':id,'point':xy(n)})
for id,way in ways.items():
 tags={t.get('k'):t.get('v') for t in way.findall('tag')};hw=tags.get('highway');ids=[n.get('ref') for n in way.findall('nd')];pts=[xy(nodes[n]) for n in ids if n in nodes]
 if len(pts)!=len(ids) or len(pts)<2:continue
 if hw not in ['motorway','motorway_link','trunk','trunk_link','primary','primary_link','secondary','tertiary','residential','unclassified','service']:continue
 if id in roads:roads[id]['maxspeed']=tags.get('maxspeed','');continue
 lanes=int(tags.get('lanes','1' if hw.endswith('link') or hw=='service' else '2').split(';')[0]);one=tags.get('oneway') in ['yes','-1'];bridge=tags.get('bridge')=='yes'
 if tags.get('oneway')=='-1':pts.reverse();ids.reverse()
 roads[id]={'id':id,'name':tags.get('name',tags.get('ref','Local road')),'class':hw,'lanes':lanes,'width':lanes*3.6+(2 if hw=='motorway' else 1),'oneway':one,'bridge':bridge,'surface':tags.get('surface','asphalt'),'points':[[x,y,round(height(x,y)+.06+(5 if bridge else 0),3)] for x,y in pts],'nodeIds':ids,'maxspeed':tags.get('maxspeed','')}
w['roads']=list(roads.values());w['signals']=signals;w['bounds']=[-1780,-9700,1780,9100];w['coverage']='15 Mile Road through 25 Mile Road, Van Dyke / M-53 corridor';json.dump(w,open(O/'world.json','w'),separators=(',',':'));print('ROADS',len(roads),'SIGNALS',len(signals),flush=True)
