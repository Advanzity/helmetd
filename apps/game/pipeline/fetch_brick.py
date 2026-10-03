import urllib.request,json,concurrent.futures
req=urllib.request.Request('https://api.polyhaven.com/files/brick_wall_001',headers={'User-Agent':'ShelbyRide-development/1.0'})
d=json.load(urllib.request.urlopen(req));print(d.keys(),flush=True)
def get(pair):
 names,out=pair;k=next(k for k in names if k in d);f=d[k]['2k'];url=(f.get('jpg') or next(iter(f.values())))['url'];urllib.request.urlretrieve(url,'outputs/shelby-ride/public/assets/'+out)
with concurrent.futures.ThreadPoolExecutor(3) as e:list(e.map(get,[(['diff','Diffuse'],'masonry-color.jpg'),(['nor_gl'],'masonry-normal.jpg'),(['rough','Rough'],'masonry-roughness.jpg')]))
