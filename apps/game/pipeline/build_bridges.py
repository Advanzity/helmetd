import bpy,json,math
from mathutils import Vector
R='/Users/david/Documents/Codex/2026-10-01/c';O=R+'/outputs/shelby-ride/public/assets';data=json.load(open(O+'/world.json'))
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
def material(n,c,rough):
 m=bpy.data.materials.new(n);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*c,1);p.inputs['Roughness'].default_value=rough;return m
concrete=material('Weathered bridge concrete',(.39,.37,.32),.9);steel=material('Bridge girder steel',(.18,.19,.17),.7)
def mesh(n,v,f,m):
 me=bpy.data.meshes.new(n);me.from_pydata(v,[],f);me.update();o=bpy.data.objects.new(n,me);bpy.context.collection.objects.link(o);o.data.materials.append(m);be=o.modifiers.new('Concrete corner bevel','BEVEL');be.width=.06;be.segments=2;return o
def beam(a,b,w,depth,material,name):
 dx=b[0]-a[0];dy=b[1]-a[1];l=math.hypot(dx,dy);nx=-dy/l;ny=dx/l;v=[]
 for dz in [0,-depth]:
  for p,s in [(a,-1),(b,-1),(b,1),(a,1)]:v.append((p[0]+nx*s*w/2,p[1]+ny*s*w/2,p[2]+dz))
 return mesh(name,v,[(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)],material)
def terrain(x,y):
 n=data['resolution'];size=data['size'];i=max(0,min(n-1,round((x/size+.5)*(n-1))));j=max(0,min(n-1,round((y/size+.5)*(n-1))));return data['heights'][j*n+i]
for road in data['roads']:
 if not road['bridge']:continue
 for a,b in zip(road['points'],road['points'][1:]):
  l=math.dist(a[:2],b[:2])
  if l<.1:continue
  beam([a[0],a[1],a[2]-.035],[b[0],b[1],b[2]-.035],road['width']+1.8,.65,concrete,'Surveyed bridge deck')
  dx=(b[0]-a[0])/l;dy=(b[1]-a[1])/l
  for offset in [-road['width']*.3,0,road['width']*.3]:
   aa=[a[0]-dy*offset,a[1]+dx*offset,a[2]-.65];bb=[b[0]-dy*offset,b[1]+dx*offset,b[2]-.65];beam(aa,bb,.35,.45,steel,'Longitudinal deck girder')
  for d in range(8,int(l),25):
   t=d/l;x=a[0]+(b[0]-a[0])*t;y=a[1]+(b[1]-a[1])*t;z=a[2]+(b[2]-a[2])*t;ground=terrain(x,y)
   if z-ground<2:continue
   aa=[x-dy*road['width']*.36,y+dx*road['width']*.36,z-.9];bb=[x+dy*road['width']*.36,y-dx*road['width']*.36,z-.9];beam(aa,bb,1,.7,concrete,'Bridge cap beam')
   for side in [-1,1]:
    xx=x-dy*side*road['width']*.26;yy=y+dx*side*road['width']*.26;beam([xx-.35,yy,z-1.6],[xx+.35,yy,z-1.6],.8,max(.2,z-1.6-ground),concrete,'Chamfered bridge pier')
bpy.ops.object.select_all(action='SELECT');bpy.ops.export_scene.gltf(filepath=O+'/bridges.glb',export_format='GLB',export_apply=True)
