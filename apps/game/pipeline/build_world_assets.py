import bpy,json,math,os
from mathutils import Vector
R='/Users/david/Documents/Codex/2026-10-01/c';O=R+'/outputs/shelby-ride/public/assets'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
def mat(name,c,rough=.7,metal=0,tex=None):
 m=bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*c,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal
 if tex:
  t=m.node_tree.nodes.new('ShaderNodeTexImage');t.image=bpy.data.images.load(O+'/'+tex);m.node_tree.links.new(t.outputs['Color'],p.inputs['Base Color'])
 return m
brick=mat('Masonry brick',(.5,.4,.3),tex='brick.jpg');concrete=mat('Architectural concrete',(.48,.46,.41));roof=mat('Roof membrane',(.14,.15,.15),tex='roof.jpg');glass=mat('Architectural tinted glass',(.065,.13,.16),.2,.58);trim=mat('Metal coping',(.23,.25,.26),.37,.7)
def mesh(name,verts,faces,material):
 me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update();o=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(o);o.data.materials.append(material);return o
data=json.load(open(O+'/world.json'));buckets={}
# Real footprint walls, inset parapets, window reveals, roof membrane and metal coping.
for b in data['buildings']:
 pts=b['points'][:-1];h=b['height'];base=b['base'];cx=sum(p[0] for p in pts)/len(pts);cy=sum(p[1] for p in pts)/len(pts);tile=(int(cx//350),int(cy//350));n=len(pts)
 if n<3:continue
 v=[(x,y,base+z) for z in [0,h,h+.22] for x,y in pts];f=[]
 for i in range(n):j=(i+1)%n;f.append((i,j,n+j,n+i));f.append((n+i,n+j,2*n+j,2*n+i))
 f.append(tuple(n+i for i in range(n)))
 o=mesh('Surveyed footprint '+str(b['id']),v,f,brick if h<8 else concrete);o.data.materials.append(roof);o.data.materials.append(trim)
 for p in o.data.polygons:
  if p.index==len(f)-1:p.material_index=1
  elif p.index%2:p.material_index=2
 uv=o.data.uv_layers.new()
 for p in o.data.polygons:
  for li in p.loop_indices:
   vert=o.data.vertices[o.data.loops[li].vertex_index].co
   if p.index==len(f)-1:uv.data[li].uv=(vert.x/5,vert.y/5)
   else:
    axis=0 if abs(p.normal.x)<abs(p.normal.y) else 1;uv.data[li].uv=(vert[axis]/4,vert.z/4)
 bevel=o.modifiers.new('Subtle edge bevel','BEVEL');bevel.width=.06;bevel.segments=1
 buckets.setdefault(tile,[]).append(o)
 # Near Hall Road the commercial frontage gets recessed window assemblies.
 if abs(cy+420)<400:
  verts=[];faces=[]
  for a,bb in zip(pts,pts[1:]+pts[:1]):
   dx=bb[0]-a[0];dy=bb[1]-a[1];length=math.hypot(dx,dy)
   if length<4:continue
   nx=dy/length;ny=-dx/length
   for j in range(int(length/4)):
    t0=(j*4+.5)/length;t1=min((j*4+3.4)/length,.98)
    for z in range(1,max(2,int(h-1)),3):
     if z+1.8>h:continue
     quad=[(a[0]+dx*t+nx*.065,a[1]+dy*t+ny*.065,base+zz) for t,zz in [(t0,z),(t1,z),(t1,z+1.8),(t0,z+1.8)]];i=len(verts);verts+=quad;faces.append((i,i+1,i+2,i+3))
  if verts:buckets[tile].append(mesh('Window glazing',verts,faces,glass))
for tile,objs in buckets.items():
 bpy.ops.object.select_all(action='DESELECT')
 for o in objs:o.select_set(True)
 bpy.context.view_layer.objects.active=objs[0];bpy.ops.object.join();objs[0].name='Buildings_%s_%s'%tile
bpy.ops.object.select_all(action='SELECT');bpy.ops.export_scene.gltf(filepath=O+'/buildings.glb',export_format='GLB',use_selection=True,export_apply=True)
# car and roadside props in a separate reusable file
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
paint=mat('Car paint',(.11,.18,.23),.28,.65);rubber=mat('Rubber',(.015,.018,.02),.85);metal=mat('Alloy',(.4,.43,.45),.3,.9);red=mat('Tail lamps',(.7,.015,.005),.3);white=mat('Lamp lens',(.85,.90,.95),.2)
def loft(name,rings,ma):
 N=32;v=[];f=[]
 for y,w,lo,hi in rings:
  for j in range(N):a=2*math.pi*j/N;v.append((w*math.cos(a),y,(lo+hi)/2+(hi-lo)/2*math.sin(a)))
 for i in range(len(rings)-1):
  for j in range(N):a=i*N+j;b=i*N+(j+1)%N;f.append((a,b,b+N,a+N))
 f+=[tuple(reversed(range(N))),tuple((len(rings)-1)*N+j for j in range(N))];o=mesh(name,v,f,ma)
 for p in o.data.polygons:p.use_smooth=True
 m=o.modifiers.new('Body curvature','SUBSURF');m.levels=2;return o
loft('Sedan body',[(-2.22,.3,.47,.62),(-2.16,.77,.35,.77),(-1.85,.91,.32,.88),(-1.2,.93,.32,.94),(-.4,.92,.32,.99),(.5,.91,.32,.92),(1.35,.88,.32,.88),(1.95,.82,.37,.74),(2.18,.65,.45,.66),(2.20,.25,.49,.59)],paint)
loft('Cabin glazing',[(-1.4,.7,.83,.90),(-.85,.70,.84,1.40),(-.40,.72,.85,1.51),(.32,.70,.85,1.48),(.98,.73,.82,.94)],glass)
loft('Roof panel',[(-.91,.58,1.33,1.39),(-.65,.67,1.43,1.47),(-.1,.68,1.46,1.51),(.35,.60,1.41,1.48)],paint)
for s in [-1,1]:
 for y in [-1.32,1.28]:
  bpy.ops.mesh.primitive_torus_add(major_radius=.24,minor_radius=.09,major_segments=48,minor_segments=12,location=(s*.83,y,.34),rotation=(0,math.pi/2,0));o=bpy.context.object;o.name='Profiled tire';o.data.materials.append(rubber)
  bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.215,depth=.02,location=(s*.929,y,.34),rotation=(0,math.pi/2,0));o=bpy.context.object;o.name='Alloy wheel';o.data.materials.append(metal)
 for y in [-2.12,2.08]:
  o=loft('Rear lens' if y<0 else 'Headlamp',[(y-.035,.12,.58,.62),(y,.23,.57,.69),(y+.035,.12,.59,.66)],red if y<0 else white);o.location.x=s*.5
bpy.ops.object.select_all(action='SELECT');bpy.ops.export_scene.gltf(filepath=O+'/sedan.glb',export_format='GLB',use_selection=True,export_apply=True)
# Studio inspection for car
world=bpy.context.scene.world;world.color=(.2,.2,.2)
bpy.ops.object.light_add(type='AREA',location=(3,2,6));bpy.context.object.data.energy=1600;bpy.context.object.data.size=5
bpy.ops.object.camera_add(location=(5,6,3));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,.8))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=5.3;s=bpy.context.scene;s.camera=cam;s.render.engine='CYCLES';s.cycles.samples=16;s.render.resolution_x=1000;s.render.resolution_y=700;s.render.resolution_percentage=100;s.render.filepath=R+'/work/sedan.png';bpy.ops.render.render(write_still=True)
