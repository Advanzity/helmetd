import bpy
R='/Users/david/Documents/Codex/2026-10-01/c';bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);bpy.ops.import_scene.gltf(filepath=R+'/work/polyhaven-tree-source/tree.gltf')
for o in bpy.data.objects:
 if o.type=='MESH':
  print(o.name,len(o.data.polygons),flush=True)
  if len(o.data.polygons)>30000:
   m=o.modifiers.new('Game LOD','DECIMATE');m.ratio=.025
bpy.ops.export_scene.gltf(filepath=R+'/outputs/shelby-ride/public/assets/tree-lod.glb',export_format='GLB',export_apply=True)
