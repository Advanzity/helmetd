import bpy,math
from mathutils import Vector
R='/Users/david/Documents/Codex/2026-10-01/c';O=R+'/outputs/shelby-ride/public/assets'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
def mat(n,c,metal=0,rough=.5):
 m=bpy.data.materials.new(n);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*c,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough;return m
steel=mat('Galvanized steel',(.42,.45,.46),.85,.38);base=mat('Concrete footing',(.35,.33,.29),0,.9);housing=mat('Powdercoated housing',(.1,.13,.14),.5,.43);light=mat('Lamp lens',(.8,.85,.8),.1,.25)
def mesh(n,v,f,m):
 d=bpy.data.meshes.new(n);d.from_pydata(v,[],f);d.update();o=bpy.data.objects.new(n,d);bpy.context.collection.objects.link(o);o.data.materials.append(m);return o
def profile(n,rings,m):
 v=[];f=[];N=24
 for z,r in rings:
  for i in range(N):a=i*2*math.pi/N;v.append((r*math.cos(a),r*math.sin(a),z))
 for j in range(len(rings)-1):
  for i in range(N):a=j*N+i;b=j*N+(i+1)%N;f.append((a,b,b+N,a+N))
 f+=[tuple(range(N-1,-1,-1)),tuple((len(rings)-1)*N+i for i in range(N))];o=mesh(n,v,f,m)
 for p in o.data.polygons:p.use_smooth=True
 return o
def tube(n,pts,r,ma):
 d=bpy.data.curves.new(n,'CURVE');d.dimensions='3D';d.resolution_u=12;d.bevel_depth=r;d.bevel_resolution=3;s=d.splines.new('BEZIER');s.bezier_points.add(len(pts)-1)
 for b,p in zip(s.bezier_points,pts):b.co=p;b.handle_left_type='AUTO';b.handle_right_type='AUTO'
 o=bpy.data.objects.new(n,d);bpy.context.collection.objects.link(o);o.data.materials.append(ma);return o
profile('Tapered pole',[(0,.11),(.2,.11),(.24,.09),(8.5,.055),(8.55,.055)],steel);profile('Cast concrete footing',[(-.5,.23),(0,.23),(.16,.22),(.2,.19)],base)
tube('Curved cobra arm',[(0,0,8.3),(0,.25,8.65),(0,.8,8.95),(0,1.8,9.05)],.045,steel)
v=[(-.17,1.6,8.96),(.17,1.6,8.96),(.23,2.0,8.94),(.17,2.45,8.9),(-.17,2.45,8.9),(-.23,2.,8.94),(-.1,1.6,9.06),(.1,1.6,9.06),(.18,2,9.1),(.1,2.45,9.02),(-.1,2.45,9.02),(-.18,2,9.1)];f=[tuple(range(6)),tuple(range(6,12))]+[(i,(i+1)%6,(i+1)%6+6,i+6) for i in range(6)];o=mesh('Cobra head lamp',v,f,housing);be=o.modifiers.new('Housing edge radius','BEVEL');be.width=.045;be.segments=3
mesh('LED diffuser',[(-.13,1.83,8.922),(.13,1.83,8.922),(.13,2.25,8.9),(-.13,2.25,8.9)],[(0,1,2,3)],light)
bpy.ops.object.select_all(action='SELECT');bpy.ops.export_scene.gltf(filepath=O+'/streetlamp.glb',export_format='GLB',export_apply=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
# W-beam guardrail 4m module, with corrugated cross section and rolled edges.
v=[];f=[]
for x in [-2,2]:
 for y,z in [(0,.54),(-.035,.565),(.03,.63),(.04,.685),(-.03,.735),(-.04,.79),(0,.85),(.0,.875)]:v.append((x,y,z))
for i in range(7):f.append((i,i+1,i+9,i+8))
o=mesh('W beam highway barrier',v,f,steel);m=o.modifiers.new('Steel sheet thickness','SOLIDIFY');m.thickness=.003;m=o.modifiers.new('Rounded folds','BEVEL');m.width=.008;m.segments=2
for x in [-1,1]:
 o=profile('Guardrail post',[(-.5,.05),(.82,.05)],steel);o.location.x=x
bpy.ops.object.select_all(action='SELECT');bpy.ops.export_scene.gltf(filepath=O+'/guardrail.glb',export_format='GLB',export_apply=True)
# Rendering for inspection
s=bpy.context.scene;s.world.color=(.3,.3,.3);bpy.ops.object.light_add(type='AREA',location=(2,-3,4));bpy.context.object.data.energy=800;bpy.context.object.data.size=5;bpy.ops.object.camera_add(location=(3,-4,2));c=bpy.context.object;c.rotation_euler=(Vector((0,0,.5))-c.location).to_track_quat('-Z','Y').to_euler();c.data.type='ORTHO';c.data.ortho_scale=4.5;s.camera=c;s.render.engine='CYCLES';s.cycles.samples=12;s.render.resolution_x=1000;s.render.resolution_y=550;s.render.resolution_percentage=100;s.render.filepath=R+'/work/guardrail.png';bpy.ops.render.render(write_still=True)
