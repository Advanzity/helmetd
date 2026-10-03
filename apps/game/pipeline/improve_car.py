import bpy,math
from mathutils import Vector
R='/Users/david/Documents/Codex/2026-10-01/c';O=R+'/outputs/shelby-ride/public/assets'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
def mat(n,c,m=0,r=.4):
 a=bpy.data.materials.new(n);a.use_nodes=True;p=a.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*c,1);p.inputs['Metallic'].default_value=m;p.inputs['Roughness'].default_value=r;return a
paint=mat('Automotive graphite blue',(.08,.15,.19),.7,.26);glass=mat('Tinted automotive glass',(.008,.027,.037),.35,.13);rubber=mat('Radial tire rubber',(.012,.014,.015),0,.9);alloy=mat('Machined alloy',(.4,.43,.46),.9,.28);dark=mat('Grille and trim',(.016,.02,.021),.3,.4);red=mat('Tail lamp',(0.8,.01,.004),.2,.25);white=mat('Headlamp',(0.85,.9,.98),.15,.16)
def mesh(n,v,f,m):
 d=bpy.data.meshes.new(n);d.from_pydata(v,[],f);d.update();o=bpy.data.objects.new(n,d);bpy.context.collection.objects.link(o);o.data.materials.append(m);return o
def bevel(o,w=.015):
 m=o.modifiers.new('Edge radius','BEVEL');m.width=w;m.segments=3
 return o
def curve(n,points,r,ma):
 d=bpy.data.curves.new(n,'CURVE');d.dimensions='3D';d.bevel_depth=r;d.bevel_resolution=3;s=d.splines.new('BEZIER');s.bezier_points.add(len(points)-1)
 for b,p in zip(s.bezier_points,points):b.co=p;b.handle_left_type='AUTO';b.handle_right_type='AUTO'
 o=bpy.data.objects.new(n,d);bpy.context.collection.objects.link(o);o.data.materials.append(ma);return o
# Quadrangulated automotive body with supporting edge loops and real wheel arches.
rings=[(-2.25,.65,.70),(-2.23,.81,.80),(-2.12,.87,.84),(-1.75,.91,.88),(-1.3,.92,.91),(-.7,.91,.94),(.1,.90,.91),(.7,.89,.86),(1.25,.89,.84),(1.85,.86,.77),(2.13,.80,.70),(2.18,.64,.61)]
v=[];f=[]
for y,w,h in rings:
 for x,z in [(-w*.8,.31),(-w,.38),(-w,.63),(-w*.94,h-.03),(-w*.83,h),(0,h+.015),(w*.83,h),(w*.94,h-.03),(w,.63),(w,.38),(w*.8,.31),(0,.31)]:v.append((x,y,z))
N=12
for i in range(len(rings)-1):
 for j in range(N):a=i*N+j;b=i*N+(j+1)%N;f.append((a,b,b+N,a+N))
f+=[tuple(reversed(range(N))),tuple((len(rings)-1)*N+j for j in range(N))];body=mesh('Sedan formed body',v,f,paint);bevel(body,.025)
bpy.context.view_layer.objects.active=body;body.select_set(True);bpy.ops.object.modifier_apply(modifier=body.modifiers[0].name)
for y in [-1.35,1.30]:
 bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=.365,depth=2.5,location=(0,y,.36),rotation=(0,math.pi/2,0));c=bpy.context.object;m=body.modifiers.new('Wheel arch cutout','BOOLEAN');m.operation='DIFFERENCE';m.object=c;bpy.context.view_layer.objects.active=body;bpy.ops.object.modifier_apply(modifier=m.name);bpy.data.objects.remove(c,do_unlink=True)
for p in body.data.polygons:p.use_smooth=True
# Glass cabin with flatter roof and sloping A/C pillars, material-separated continuous shell
v=[];f=[]
for y,w,h in [(-1.45,.75,.89),(-.93,.67,1.37),(-.70,.65,1.45),(.12,.64,1.45),(.34,.66,1.39),(.97,.77,.875)]:
 v.extend([(-w-.05,y,.89),(-w,y,h-.06),(-w*.8,y,h),(0,y,h+.012),(w*.8,y,h),(w,y,h-.06),(w+.05,y,.89)])
for i in range(5):
 for j in range(6):a=i*7+j;f.append((a,a+1,a+8,a+7))
cabin=mesh('Cabin glass and roof',v,f,glass);cabin.data.materials.append(paint)
for p in cabin.data.polygons:
 if p.index//6 in [1,2,3] and p.index%6 in [1,2,3,4]:p.material_index=1
bevel(cabin,.025)
for s in [-1,1]:
 for y in [-1.35,1.30]:
  bpy.ops.mesh.primitive_torus_add(major_radius=.255,minor_radius=.085,major_segments=64,minor_segments=16,location=(s*.83,y,.35),rotation=(0,math.pi/2,0));o=bpy.context.object;o.name='Tire';o.data.materials.append(rubber)
  for p in o.data.polygons:p.use_smooth=True
  bpy.ops.mesh.primitive_torus_add(major_radius=.226,minor_radius=.012,major_segments=48,minor_segments=8,location=(s*.917,y,.35),rotation=(0,math.pi/2,0));bpy.context.object.data.materials.append(alloy)
  for k in range(10):
   a=k*math.pi/5;curve('Alloy spoke',[(s*.92,y+.045*math.sin(a),.35+.045*math.cos(a)),(s*.919,y+.22*math.sin(a+.12),.35+.22*math.cos(a+.12))],.014,alloy)
  bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=.057,depth=.03,location=(s*.917,y,.35),rotation=(0,math.pi/2,0));bpy.context.object.data.materials.append(alloy)
 # side door shut lines, belt trim, B pillar, handles and mirrors
 curve('Door shutline',[(s*.897,-.32,.92),(s*.914,-.33,.67),(s*.905,-.38,.39)],.0025,dark)
 curve('Beltline',[(s*.80,-1.39,.9),(s*.83,-.8,.9),(s*.83,.6,.9),(s*.78,.97,.89)],.008,alloy)
 curve('B pillar',[(s*.83,-.25,.9),(s*.65,-.25,1.44)],.026,dark)
 for y in [-.65,.38]:curve('Door handle',[(s*.924,y-.07,.80),(s*.94,y,.80),(s*.924,y+.07,.80)],.012,alloy)
 curve('Mirror stem',[(s*.83,.66,.93),(s*.98,.61,1.02)],.02,dark)
 o=mesh('Mirror housing',[(s*x,y,z) for x,y,z in [(1.0,.48,.98),(1.15,.5,1.0),(1.16,.66,1.04),(.97,.68,1.07)]],[(0,1,2,3)],paint);m=o.modifiers.new('Housing thickness','SOLIDIFY');m.thickness=.06;bevel(o)
 curve('Front LED',[(s*.38,2.15,.665),(s*.68,2.10,.69),(s*.80,1.99,.70)],.024,white)
 curve('Rear LED',[(s*.37,-2.245,.74),(s*.67,-2.225,.77),(s*.80,-2.16,.77)],.023,red)
for i in range(5):curve('Front intake grille',[(-.49,2.16,.39+i*.027),(.49,2.16,.39+i*.027)],.008,dark)
# apply transforms/material joins for efficient traffic instancing
for o in list(bpy.data.objects):
 if o.type in ['MESH','CURVE']:
  bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o;bpy.ops.object.convert(target='MESH')
for ma in [paint,glass,rubber,alloy,dark,red,white]:
 objs=[o for o in bpy.data.objects if o.type=='MESH' and len(o.data.materials)==1 and o.data.materials[0]==ma]
 if not objs:continue
 bpy.ops.object.select_all(action='DESELECT')
 for o in objs:o.select_set(True)
 bpy.context.view_layer.objects.active=objs[0];bpy.ops.object.join()
bpy.ops.object.select_all(action='SELECT');bpy.ops.export_scene.gltf(filepath=O+'/sedan.glb',export_format='GLB',export_apply=True)
bpy.ops.wm.save_as_mainfile(filepath=R+'/outputs/shelby-ride/sedan.blend')
# two-angle material and proportion inspection
s=bpy.context.scene;s.world.color=(.22,.22,.22)
for loc,power in [((3,2,6),1400),((-4,-2,5),1200)]:
 bpy.ops.object.light_add(type='AREA',location=loc);bpy.context.object.data.energy=power;bpy.context.object.data.size=5;bpy.context.object.rotation_euler=(Vector((0,0,.7))-bpy.context.object.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=5.2;s.camera=cam;s.render.engine='CYCLES';s.cycles.samples=20;s.render.resolution_x=1100;s.render.resolution_y=750;s.render.resolution_percentage=100
for name,loc in [('sedan-v2',(5,6,3)),('sedan-rear',(-5,-6,2.5))]:
 cam.location=loc;cam.rotation_euler=(Vector((0,0,.7))-cam.location).to_track_quat('-Z','Y').to_euler();s.render.filepath=R+'/work/'+name+'.png';bpy.ops.render.render(write_still=True)
