"""Fetch an OSM API XML map as the JSON format consumed by the map builder."""
import argparse
import json
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--bbox', required=True, help='west,south,east,north')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
west,south,east,north=map(float,args.bbox.split(','))
mid_x,mid_y=(west+east)/2,(south+north)/2
roots=[]
for bbox in [(west,south,mid_x,mid_y),(mid_x,south,east,mid_y),(west,mid_y,mid_x,north),(mid_x,mid_y,east,north)]:
    request=urllib.request.Request('https://api.openstreetmap.org/api/0.6/map?bbox='+','.join(map(str,bbox)),headers={'User-Agent':'helmetd-game-map-builder/1.0'})
    with urllib.request.urlopen(request,timeout=50) as response:
        roots.append(ET.fromstring(response.read()))
    print('Fetched quadrant',bbox,flush=True)
elements = {}
for element in [element for root in roots for element in root]:
    if element.tag not in ('node', 'way', 'relation'):
        continue
    item = {'type': element.tag, 'id': int(element.attrib['id']),
            'tags': {tag.attrib['k']: tag.attrib['v'] for tag in element.findall('tag')}}
    if element.tag == 'node':
        item.update(lat=float(element.attrib['lat']), lon=float(element.attrib['lon']))
    elif element.tag == 'way':
        item['nodes'] = [int(node.attrib['ref']) for node in element.findall('nd')]
    else:
        item['members'] = [dict(member.attrib) for member in element.findall('member')]
    elements[(item['type'],item['id'])]=item
args.output.write_text(json.dumps({'elements': list(elements.values())}, separators=(',', ':')), encoding='utf-8')
print(f'Saved {len(elements)} map features to {args.output}')
