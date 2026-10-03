import urllib.request,urllib.parse,json
q={'bbox':'-83.10,42.54,-82.967,42.72','bboxSR':4326,'size':'660,1200','imageSR':32617,'format':'tiff','pixelType':'F32','f':'json'}
u='https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage?'+urllib.parse.urlencode(q);d=json.load(urllib.request.urlopen(u,timeout=120));urllib.request.urlretrieve(d['href'],'work/macomb-source-data/township-dem.tif');print('DEM ready',flush=True)
