import bpy,math
R='/Users/david/Documents/Codex/2026-10-01/c';O=R+'/outputs/shelby-ride/public/assets'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
def mat(n,c,metal=0):
 m=bpy.data.materials.new(n);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*c,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=.4;return m
pole=mat('Signal galvanized mast',(.35,.38,.4),.8);yellow=mat('Signal yellow housing',(.8,.47,.045));black=mat('Signal backplate',(.018,.022,.024))
def tube(n,pts,r,m):
 c=bpy.data.curves.new(n,'CURVE');c.dimensions='3D';c.bevel_depth=r;c.bevel_resolution=3;s=c.splines.new('BEZIER');s.bezier_points.add(len(pts)-1)
 for b,p in zip(s.bezier_points,pts):b.co=p;b.handle_left_type='AUTO';b.handle_right_type='AUTO'
 o=bpy.data.objects.new(n,c);bpy.context.collection.objects.link(o);o.data.materials.append(m)
def housing(n,x,y,z,w,h,d,m):
 bpy.ops.mesh.primitive_cube_add(size=1,location=(x,y,z));o=bpy.context.object;o.name=n;o.scale=(w,d,h);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(m);be=o.modifiers.new('Rounded cast enclosure','BEVEL');be.width=.055;be.segments=4
# Roadside mast with overhead arm toward travel lane; faces approach behind local forward +Y.
tube('Curved signal mast',[(0,0,0),(0,0,5.6),(-.15,0,6.1),(-1,0,6.4),(-5,0,6.4)],.09,pole)
tube('Overhead signal mounting hanger',[(-4.5,0,6.4),(-4.5,0,6.05),(-4.5,.08,5.7)],.032,pole)
for x in [-4.5,0]:
 z=5.35 if x else 3.1;housing('Signal backboard',x,0,z,.55,1.45,.12,black);housing('Three aspect enclosure',x,-.10,z,.36,1.15,.22,yellow)
 for i,(name,col) in enumerate([('red',(1,.01,.005)),('yellow',(1,.5,.005)),('green',(.01,1,.2))]):
  m=mat('Signal '+name,col);p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Emission Color'].default_value=(*col,1);p.inputs['Emission Strength'].default_value=1
  zz=z+.37-i*.37;bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=1,location=(x,-.24,zz));o=bpy.context.object;o.name='Optical lens '+name;o.scale=(.125,.025,.125);o.data.materials.append(m)
  tube('Signal visor '+name,[(x-.15,-.22,zz),(x-.14,-.36,zz+.10),(x,-.39,zz+.15),(x+.14,-.36,zz+.10),(x+.15,-.22,zz)],.022,black)
for o in list(bpy.data.objects):
 if o.type in ['MESH','CURVE']:
  bpy.context.view_layer.objects.active=o;o.select_set(True)
  if o.type=='CURVE':bpy.ops.object.convert(target='MESH')
  else:
   for m in list(o.modifiers):bpy.ops.object.modifier_apply(modifier=m.name)
  o.select_set(False)
bpy.ops.object.select_all(action='SELECT');bpy.ops.export_scene.gltf(filepath=O+'/traffic-signal.glb',export_format='GLB');bpy.ops.wm.save_as_mainfile(filepath=R+'/outputs/shelby-ride/traffic-signal.blend')
