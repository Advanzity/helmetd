import bpy,math
R='/Users/david/Documents/Codex/2026-10-01/c';bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
def mat(n,c,metal=0):
 m=bpy.data.materials.new(n);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*c,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=.38;return m
red=mat('Reflective stop red',(.58,.015,.008));white=mat('Reflective sign white',(.82,.84,.77));steel=mat('Galvanized sign post',(.3,.33,.34),.8)
bpy.ops.mesh.primitive_cylinder_add(vertices=16,radius=.035,depth=2.7,location=(0,0,1.35));bpy.context.object.data.materials.append(steel)
for r,y,m in [(.41,0,white),(.377,-.014,red)]:
 verts=[(r*math.sin(math.pi/8+i*math.pi/4),y,2.45+r*math.cos(math.pi/8+i*math.pi/4)) for i in range(8)];me=bpy.data.meshes.new('Octagonal sign');me.from_pydata(verts,[],[tuple(range(8))]);me.update();o=bpy.data.objects.new('Rolled aluminum stop sign',me);bpy.context.collection.objects.link(o);me.materials.append(m);solid=o.modifiers.new('Aluminum sheet','SOLIDIFY');solid.thickness=.003;be=o.modifiers.new('Rolled perimeter','BEVEL');be.width=.002;be.segments=2
font=bpy.data.curves.new('STOP','FONT');font.body='STOP';font.align_x='CENTER';font.align_y='CENTER';font.size=.21;font.extrude=.001;font.resolution_u=2;o=bpy.data.objects.new('STOP lettering',font);bpy.context.collection.objects.link(o);o.location=(0,-.019,2.45);o.rotation_euler=(math.pi/2,0,0);o.data.materials.append(white)
for ob in list(bpy.data.objects):
 bpy.context.view_layer.objects.active=ob;ob.select_set(True)
 if ob.type=='FONT':bpy.ops.object.convert(target='MESH')
 else:
  for mod in list(ob.modifiers):bpy.ops.object.modifier_apply(modifier=mod.name)
 ob.select_set(False)
bpy.ops.object.select_all(action='SELECT');bpy.ops.export_scene.gltf(filepath=R+'/outputs/shelby-ride/public/assets/stop-sign.glb',export_format='GLB')
