import json,xml.etree.ElementTree as ET,pathlib,re
O=pathlib.Path('outputs/shelby-ride/public/assets/world.json');w=json.load(open(O));tags={}
for p in pathlib.Path('work/macomb-source-data').glob('corridor-*.osm'):
 for way in ET.parse(p).getroot().findall('way'):tags[way.get('id')]={t.get('k'):t.get('v') for t in way.findall('tag')}
for r in w['roads']:
 t=tags.get(r['id'],{});hw=r['class'];default=1 if hw.endswith('link') or hw=='service' else 2
 try:lanes=int(t.get('lanes',default).split(';')[0]) if isinstance(t.get('lanes',default),str) else default
 except:lanes=default
 if hw=='residential' and 'lanes' not in t:lanes=2
 laneWidth=3.65 if hw in ['motorway','trunk'] else 3.35 if hw in ['primary','secondary','tertiary'] else 2.9 if hw=='residential' else 3.1
 shoulder=2.4 if hw=='motorway' else .6 if hw in ['trunk','primary'] else .25
 width=lanes*laneWidth+shoulder*2
 if hw=='service' and 'lanes' not in t:width=5.5 if t.get('service')!='driveway' else 3.5
 if 'width' in t:
  m=re.search(r'[\d.]+',t['width'])
  if m:
   value=float(m.group())*(.3048 if 'ft' in t['width'] or "'" in t['width'] else 1)
   if 2<value<45:width=value;laneWidth=max(2.5,(width-shoulder*2)/lanes)
 r.update(lanes=lanes,width=round(width,2),laneWidth=laneWidth,shoulder=shoulder,widthSource='OSM width' if 'width' in t else 'OSM lanes + road-class estimate' if 'lanes' in t else 'road-class estimate',forwardLanes=int(t.get('lanes:forward',max(1,lanes//2))),backwardLanes=int(t.get('lanes:backward',max(1,lanes//2))))
json.dump(w,open(O,'w'),separators=(',',':'));print('width sources', {s:sum(r['widthSource']==s for r in w['roads']) for s in set(r['widthSource'] for r in w['roads'])})
