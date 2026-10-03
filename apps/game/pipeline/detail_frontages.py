import bpy,json,math
from mathutils import Vector, Matrix
R='/Users/david/Documents/Codex/2026-10-01/c';O=R+'/outputs/shelby-ride/public/assets'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
def mat(n,c,metal=0,rough=.5):
 m=bpy.data.materials.new(n);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*c,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough;return m
stone=mat('Limestone surrounds',(.61,.56,.46),0,.82);metal=mat('Bronze storefront mullions',(.085,.074,.06),.8,.3);glass=mat('Storefront reflection glass',(.07,.13,.16),.7,.16);dark=mat('Recessed storefront panels',(.06,.075,.08),.2,.58);concrete=mat('Sidewalk concrete',(.49,.48,.43),0,.95);steel=mat('HVAC galvanized steel',(.37,.4,.4),.7,.48);light=mat('Warm shop lighting',(.8,.59,.3));p=light.node_tree.nodes.get('Principled BSDF');p.inputs['Emission Color'].default_value=(1,.65,.3,1);p.inputs['Emission Strength'].default_value=1.4
buckets={};current=None
def block(n,x,z,w,h,depth,ma,y=.15):
 # Local facade coordinates, x along the wall and y outward from it.
 pts=[(x+sx*w/2,y+sy*depth/2,z+sz*h/2) for sz in [-1,1] for sy in [-1,1] for sx in [-1,1]]
 verts=[(a[0]+u*dx+v*nx,a[1]+u*dy+v*ny,base+zz) for u,v,zz in pts];faces=[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]
 key=(current,ma.name);bucket=buckets.setdefault(key,{'v':[],'f':[],'m':ma});offset=len(bucket['v']);bucket['v'].extend(verts);bucket['f'].extend([tuple(i+offset for i in f) for f in faces])

world=json.load(open(O+'/world.json'));count=0
world['buildings'].sort(key=lambda b:abs(sum(p[0] for p in b['points'])/len(b['points']))+2*abs(sum(p[1] for p in b['points'])/len(b['points'])+420))
for bi,b in enumerate(world['buildings']):
 pts=b['points'][:-1]
 if len(pts)<3:continue
 area=abs(sum(a[0]*q[1]-q[0]*a[1] for a,q in zip(pts,pts[1:]+pts[:1])))/2
 if area<450 or count>=95:continue
 cx=sum(p[0] for p in pts)/len(pts);cy=sum(p[1] for p in pts)/len(pts)
 if abs(cy+420)>300 or abs(cx)>1600:continue
 if sum(a[0]*q[1]-q[0]*a[1] for a,q in zip(pts,pts[1:]+pts[:1]))<0:pts.reverse()
 base=b['base'];h=b['height'];current=(int(cx//250),int(cy//250));count+=1
 for a,q in zip(pts,pts[1:]+pts[:1]):
  length=math.dist(a,q)
  if length<6:continue
  dx=(q[0]-a[0])/length;dy=(q[1]-a[1])/length;nx=dy;ny=-dx
  # Detail only the side facing Hall Road, plus its perpendicular side frontage.
  if ny*(cy+420)>0.1:continue
  block('Walkway with curb',length/2,.025,length, .18,2.8,concrete,1.25)
  block('Foundation stone course',length/2,.30,length,.5,.22,stone)
  block('Continuous parapet coping',length/2,h+.18,length,.18,.45,metal)
  block('Architectural fascia',length/2,min(h-.4,3.3),length,.58,.25,dark,.20)
  for j in range(int(length/5)):
   x=j*5+2.5;top=min(2.65,h-.9)
   if top<1.6:continue
   block('Storefront glass bay',x,(.52+top)/2,4.1,top-.52,.075,glass,.23)
   for xx in [x-2.07,x,x+2.07]:block('Vertical glazing mullion',xx,(.52+top)/2,.075,top-.48,.16,metal,.29)
   for zz in [.5,top,top-.42]:block('Horizontal glazing transom',x,zz,4.2,.07,.16,metal,.29)
   block('Stone pilaster',x-2.4,h/2,.34,h,.38,stone,.20)
   if j%3==1:
    block('Entrance door frame',x,1.3,1.02,2.45,.19,metal,.31);block('Door glazing',x,1.3,.86,2.26,.035,glass,.42)
    block('Door pull handle',x+.3,1.15,.035,.5,.06,steel,.49)
    block('Entrance canopy',x,top+.18,2.2,.13,1.35,dark,.72)
   block('Warm recessed shop strip',x,top-.1,3.75,.045,.05,light,.33)
  if length>12:
   labels=['COFFEE & KITCHEN','MOTOR SUPPLY','MARKET','STUDIO','BAKERY']
   for at in range(8,int(length)-3,18):
    curve=bpy.data.curves.new('Storefront lettering','FONT');curve.body=labels[(bi+at//18)%len(labels)];curve.align_x='CENTER';curve.size=.25;curve.extrude=0;curve.bevel_depth=0;curve.resolution_u=2
    ob=bpy.data.objects.new('Illustrative retail sign',curve);bpy.context.collection.objects.link(ob);ob.location=(a[0]+at*dx+.36*nx,a[1]+at*dy+.36*ny,base+min(h-.4,3.3)-.10);ob.rotation_euler=Matrix(((dx,0,nx),(dy,0,ny),(0,1,0))).to_euler();ob.data.materials.append(light)
  for at in range(0,int(length),3):block('Sidewalk expansion joint',at,.121,.018,.006,2.8,dark,1.25)
 # Rooftop service equipment with louver strips.
 a=(cx,cy);dx=1;dy=0;nx=0;ny=1
 if h>3:
  block('Rooftop packaged air handler',0,h+.65,2.6,1.1,1.5,steel,0)
  for z in range(8):block('HVAC louver fin',0,h+.25+z*.09,2.35,.025,.04,dark,.78)
for (tile,material),data in buckets.items():
 me=bpy.data.meshes.new('Facade mesh');me.from_pydata(data['v'],[],data['f']);me.update();ob=bpy.data.objects.new('Commercial frontage '+str(tile)+' '+material,me);bpy.context.collection.objects.link(ob);ob.data.materials.append(data['m']);be=ob.modifiers.new('Architectural edge radii','BEVEL');be.width=.012;be.segments=1;bpy.context.view_layer.objects.active=ob;ob.select_set(True);bpy.ops.object.modifier_apply(modifier=be.name);ob.select_set(False)
bpy.ops.object.select_all(action='DESELECT')
for ob in list(bpy.data.objects):
 if ob.type=='FONT':
  bpy.context.view_layer.objects.active=ob;ob.select_set(True);bpy.ops.object.convert(target='MESH');ob.select_set(False)
bpy.ops.object.select_all(action='SELECT');bpy.ops.export_scene.gltf(filepath=O+'/frontages.glb',export_format='GLB',use_selection=True)
bpy.ops.wm.save_as_mainfile(filepath=R+'/outputs/shelby-ride/frontages.blend');print('Detailed buildings',count,flush=True)
