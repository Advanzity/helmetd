import xml.etree.ElementTree as ET,json
from pyproj import Transformer
from shapely.geometry import Polygon
tr=Transformer.from_crs(4326,32617,always_xy=True);ex,ny=tr.transform(-83.0245,42.6295)
r=ET.parse('work/macomb-source-data/shelby.osm').getroot();nodes={}
for n in r.findall('node'):
 x,y=tr.transform(float(n.get('lon')),float(n.get('lat')));nodes[n.get('id')]=[round(x-ex,2),round(y-ny,2)]
out=[]
for w in r.findall('way'):
 tags={t.get('k'):t.get('v') for t in w.findall('tag')}
 if tags.get('amenity')!='parking':continue
 p=[nodes[n.get('ref')] for n in w.findall('nd') if n.get('ref') in nodes]
 if len(p)<4:continue
 poly=Polygon(p)
 if not poly.is_valid or poly.area<50 or any(abs(v)>1660 for xy in p for v in xy):continue
 out.append({'points':p,'area':round(poly.area)})
json.dump(out,open('outputs/shelby-ride/public/assets/parking.json','w'),separators=(',',':'));print(len(out),'mapped parking lots')
