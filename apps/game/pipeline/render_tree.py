import bpy
from mathutils import Vector
R='/Users/david/Documents/Codex/2026-10-01/c';bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);bpy.ops.import_scene.gltf(filepath=R+'/outputs/shelby-ride/public/assets/tree.glb')
verts=[o.matrix_world@Vector(v) for o in bpy.data.objects if o.type=='MESH' for v in o.bound_box];lo=Vector([min(v[i] for v in verts) for i in range(3)]);hi=Vector([max(v[i] for v in verts) for i in range(3)]);center=(lo+hi)/2;print('TREE BOUNDS',lo,hi,flush=True)
s=bpy.context.scene;s.world.color=(.3,.3,.3)
bpy.ops.object.light_add(type='AREA',location=center+Vector((3,-5,7)));bpy.context.object.data.energy=1500;bpy.context.object.data.size=6;bpy.context.object.rotation_euler=(center-bpy.context.object.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=center+Vector((0,-20,0)));c=bpy.context.object;c.rotation_euler=(center-c.location).to_track_quat('-Z','Y').to_euler();c.data.type='ORTHO';c.data.ortho_scale=max(hi.z-lo.z,hi.x-lo.x)*1.05;s.camera=c;s.render.engine='CYCLES';s.cycles.samples=16;s.render.film_transparent=True;s.render.resolution_x=768;s.render.resolution_y=768;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.filepath=R+'/outputs/shelby-ride/public/assets/tree-impostor.png';bpy.ops.render.render(write_still=True)
