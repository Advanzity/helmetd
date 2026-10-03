import bpy,json,math,os
R='/Users/david/Documents/Codex/2026-10-01/c';O=R+'/outputs/shelby-ride/public/assets'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
materials={}
for name,col,rough,metal in [('Masonry brick',(.6,.55,.48),.9,0),('Architectural concrete',(.48,.46,.41),.9,0),('Roof membrane',(.14,.15,.15),.9,0),('Architectural tinted glass',(.065,.13,.16),.2,.58),('Roof shingles',(.095,.10,.105),.94,0),('House siding',(.55,.52,.46),.85,0),('Window trim',(.72,.70,.64),.58,0),('Entry door',(.19,.22,.22),.65,0),('Metal coping',(.23,.25,.26),.37,.7)]:
 m=bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*col,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal;materials[name]=m
buckets={}
def face(tile,ma,points):
 d=buckets.setdefault((tile,ma),{'v':[],'f':[]});n=len(d['v']);d['v'].extend(points);d['f'].append(tuple(range(n,n+len(points))))
w=json.load(open(O+'/world.json'))
for b in w['buildings']:
 pts=b['points'][:-1]
 if len(pts)<3:continue
 if sum(a[0]*q[1]-q[0]*a[1] for a,q in zip(pts,pts[1:]+pts[:1]))<0:pts.reverse()
 h=b['height'];base=b['base'];cx=sum(p[0] for p in pts)/len(pts);cy=sum(p[1] for p in pts)/len(pts);tile=(int(cx//1000),int(cy//1000));house=bool(b.get('roofFaces'));ma=('Masonry brick' if int(abs(cx+cy))%3 else 'House siding') if house else 'Masonry brick' if h<8 else 'Architectural concrete'
 for a,q in zip(pts,pts[1:]+pts[:1]):
  face(tile,ma,[(a[0],a[1],base),(q[0],q[1],base),(q[0],q[1],base+h),(a[0],a[1],base+h)])
  if not house:face(tile,'Metal coping',[(a[0],a[1],base+h),(q[0],q[1],base+h),(q[0],q[1],base+h+.16),(a[0],a[1],base+h+.16)])
  dx=q[0]-a[0];dy=q[1]-a[1];length=math.hypot(dx,dy)
  if length<4:continue
  nx=dy/length;ny=-dx/length
  for j in range(int(length/5)):
   t0=(j*5+1)/length;t1=min((j*5+(2.15 if house else 3.9))/length,.98)
   for z in range(1,max(2,int(h-1)),3):
    if z+1.7>h:continue
    face(tile,'Architectural tinted glass',[(a[0]+dx*t+nx*.035,a[1]+dy*t+ny*.035,base+zz) for t,zz in [(t0,z),(t1,z),(t1,z+1.7),(t0,z+1.7)]])
    if not house:continue
    # Recessed glazing, projecting sill and four-sided window surrounds.
    def panel(u0,u1,z0,z1,depth,material):
     face(tile,material,[(a[0]+dx*t+nx*depth,a[1]+dy*t+ny*depth,base+zz) for t,zz in [(u0,z0),(u1,z0),(u1,z1),(u0,z1)]])
    border=.075/length
    for u0,u1,z0,z1 in [(t0-border,t0,z-.08,z+1.78),(t1,t1+border,z-.08,z+1.78),(t0,t1,z-.08,z),(t0,t1,z+1.7,z+1.78)]:panel(u0,u1,z0,z1,.075,'Window trim')
    panel((t0+t1)/2-.022/length,(t0+t1)/2+.022/length,z,z+1.7,.085,'Window trim')
    panel(t0,t1,z+.83,z+.875,.085,'Window trim')
  if house and length>6:
   # One plausible entry per house, on its longest footprint edge.
   longest=max(math.hypot(v[0]-u[0],v[1]-u[1]) for u,v in zip(pts,pts[1:]+pts[:1]))
   if abs(length-longest)<.001:
    t=.5;hw=.48/length
    face(tile,'Entry door',[(a[0]+dx*tt+nx*.045,a[1]+dy*tt+ny*.045,base+zz) for tt,zz in [(t-hw,.08),(t+hw,.08),(t+hw,2.15),(t-hw,2.15)]])

 if house:
  for roof in b['roofFaces']:face(tile,'Roof shingles',roof)
  for a,q in zip(b['roofEdges'],b['roofEdges'][1:]):face(tile,ma,[(a[0],a[1],base+h),(q[0],q[1],base+h),q,a])
 else:face(tile,'Roof membrane',[(x,y,base+h) for x,y in pts])
print('Building tiles',len(buckets),flush=True)
tile_objects={}
for (tile,name),d in buckets.items():
 me=bpy.data.meshes.new(name);me.from_pydata(d['v'],[],d['f']);me.update();ob=bpy.data.objects.new('Buildings '+str(tile)+' '+name,me);bpy.context.collection.objects.link(ob);tile_objects.setdefault(tile,[]).append(ob);me.materials.append(materials[name]);uv=me.uv_layers.new()
 for p in me.polygons:
  for li in p.loop_indices:
   v=me.vertices[me.loops[li].vertex_index].co;axis=0 if abs(p.normal.x)<abs(p.normal.y) else 1;uv.data[li].uv=(v.x/4,v.y/4) if name=='Roof membrane' else (v[axis]/4,v.z/4)
os.makedirs(O+'/building-tiles',exist_ok=True)
manifest=[]
bpy.ops.object.select_all(action='DESELECT')
for tile,objects in tile_objects.items():
 for ob in objects:ob.select_set(True)
 name=str(tile[0])+'_'+str(tile[1])+'.glb'
 bpy.ops.export_scene.gltf(filepath=O+'/building-tiles/'+name,export_format='GLB',use_selection=True)
 for ob in objects:ob.select_set(False)
 manifest.append({'file':name,'x':tile[0]*1000+500,'y':tile[1]*1000+500})
json.dump(manifest,open(O+'/building-tiles.json','w'))
print('EXPORTED',len(w['buildings']),len(manifest),'tiles',flush=True)
