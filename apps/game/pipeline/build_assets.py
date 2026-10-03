import bpy, math, json, os, sys
from mathutils import Vector, Matrix, Quaternion
from math import sin,cos,pi
ROOT='/Users/david/Documents/Codex/2026-10-01/c'
OUT=ROOT+'/outputs/shelby-ride/public/assets'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
M={}
def mat(n,c,metal=0,rough=.4):
 m=bpy.data.materials.new(n);m.diffuse_color=(*c,1);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*c,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough;M[n]=m;return m
mat('Pearl ceramic paint',(.72,.77,.79),.48,.26);mat('Graphite fairing',(.022,.027,.032),.3,.37);mat('Anodized aluminum',(.09,.11,.13),.85,.3);mat('Machined steel',(.37,.42,.46),.92,.27);mat('Titanium exhaust',(.32,.29,.23),.87,.36);mat('Bronze fork',(.46,.28,.10),.8,.28);mat('Tire rubber',(.013,.016,.019),0,.88);mat('Seat vinyl',(.018,.021,.025),0,.66);mat('Orange',(.92,.15,.025),.38,.3);mat('Glass',(.055,.09,.11),.7,.12);mat('Textile',(.027,.032,.039),0,.86);mat('Leather',(.012,.016,.019),0,.48);mat('White piping',(.42,.46,.48),0,.6)
for n,c in [('Headlight',(.76,.87,1)),('Brake light',(1,.018,.004)),('Dash',(.02,.7,.54))]:
 m=mat(n,c,.15,.2);p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Emission Color'].default_value=(*c,1);p.inputs['Emission Strength'].default_value=3
# Microstructure roughness and normals retained as authored Blender materials; runtime texture maps are added separately.
for name,scale,strength in [('Tire rubber',180,.12),('Textile',240,.23),('Seat vinyl',180,.17),('Leather',200,.1)]:
 m=M[name];nodes=m.node_tree.nodes;links=m.node_tree.links;p=nodes.get('Principled BSDF');noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=scale;b=nodes.new('ShaderNodeBump');b.inputs['Strength'].default_value=strength;b.inputs['Distance'].default_value=.002;links.new(noise.outputs['Fac'],b.inputs['Height']);links.new(b.outputs['Normal'],p.inputs['Normal'])
def mesh(n,v,f,material,smooth=True):
 me=bpy.data.meshes.new(n);me.from_pydata(v,[],f);me.update();o=bpy.data.objects.new(n,me);bpy.context.collection.objects.link(o);o.data.materials.append(M[material]);
 for p in me.polygons:p.use_smooth=smooth
 return o
def bevel(o,w=.003,s=3):
 m=o.modifiers.new('Manufactured edge radii','BEVEL');m.width=w;m.segments=s
 return o
def tube(n,pts,r,material):
 c=bpy.data.curves.new(n,'CURVE');c.dimensions='3D';c.resolution_u=10;c.bevel_depth=r;c.bevel_resolution=3;s=c.splines.new('BEZIER');s.bezier_points.add(len(pts)-1)
 for b,p in zip(s.bezier_points,pts):b.co=p;b.handle_left_type='AUTO';b.handle_right_type='AUTO'
 o=bpy.data.objects.new(n,c);bpy.context.collection.objects.link(o);o.data.materials.append(M[material]);return o
def rod(n,a,b,r,material,verts=24):
 a=Vector(a);b=Vector(b);bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=(b-a).length,location=(a+b)/2);o=bpy.context.object;o.name=n;o.rotation_mode='QUATERNION';o.rotation_quaternion=(b-a).to_track_quat('Z','Y');o.data.materials.append(M[material]);bevel(o,.0015,2)
 for p in o.data.polygons:p.use_smooth=True
 return o
def loft(n,rings,material,N=32):
 # each ring: longitudinal y, width, lower z, upper z; elliptical cross-section
 v=[];f=[]
 for y,w,lo,hi in rings:
  for j in range(N):
   a=2*pi*j/N;v.append((w*cos(a),y,(lo+hi)/2+(hi-lo)/2*sin(a)))
 for i in range(len(rings)-1):
  for j in range(N):a=i*N+j;b=i*N+(j+1)%N;f.append((a,b,b+N,a+N))
 f.append(tuple(reversed(range(N))));f.append(tuple((len(rings)-1)*N+j for j in range(N)))
 o=mesh(n,v,f,material);s=o.modifiers.new('Continuous curvature','SUBSURF');s.levels=2;return o
def panel(n,coords,material,thick=.008):
 o=mesh(n,coords,[tuple(range(len(coords)))],material,False);s=o.modifiers.new('Panel thickness','SOLIDIFY');s.thickness=thick;bevel(o,.008,3);return o
def empty(n,loc=(0,0,0)):
 o=bpy.data.objects.new(n,None);bpy.context.collection.objects.link(o);o.location=loc;return o
def parent_parts(objs,p):
 bpy.context.view_layer.update()
 for o in objs:
  mw=o.matrix_world.copy();o.parent=p;o.matrix_world=mw
bike=empty('Motorcycle')
# wheels: actual tire profile, rim barrel, spokes, vented rotors, visible tread grooves
wheelroots=[]
for front,y,w in [(False,-.70,.095),(True,.70,.062)]:
 before=set(bpy.data.objects);root=empty('FrontWheel' if front else 'RearWheel',(0,y,.305));wheelroots.append(root)
 def lathe(n,profile,material,steps=96):
  v=[];f=[]
  for x,r in profile:
   for i in range(steps):a=2*pi*i/steps;v.append((x,y+r*sin(a),.305+r*cos(a)))
  for j in range(len(profile)-1):
   for i in range(steps):a=j*steps+i;b=j*steps+(i+1)%steps;f.append((a,b,b+steps,a+steps))
  return mesh(n,v,f,material)
 profile=[(-w*.77,.216),(-w,.245),(-w*.94,.278),(-w*.63,.297),(-w*.28,.305),(0,.307),(w*.28,.305),(w*.63,.297),(w*.94,.278),(w,.245),(w*.77,.216)]
 lathe('Radial tire carcass',profile,'Tire rubber');lathe('Cast alloy rim',[(-w*.8,.212),(-w*.82,.226),(-w*.67,.231),(-w*.62,.215),(w*.62,.215),(w*.67,.231),(w*.82,.226),(w*.8,.212)],'Anodized aluminum')
 rod('Wheel hub',(-w,y,.305),(w,y,.305),.045,'Anodized aluminum')
 for i in range(5):
  a=2*pi*i/5
  for s in [-1,1]:
   tube('Swept cast wheel spoke',[(s*w*.58,y+.042*sin(a),.305+.042*cos(a)),(s*w*.52,y+.135*sin(a+.1),.305+.135*cos(a+.1)),(s*w*.55,y+.216*sin(a+.25),.305+.216*cos(a+.25))],.011,'Anodized aluminum')
 for s in [-1,1] if front else [1]:
  x=s*(w+.017);lathe('Floating brake rotor',[(x-.0015,.104),(x-.0015,.153),(x+.0015,.153),(x+.0015,.104)],'Machined steel',96)
  for k in range(24):
   a=k*2*pi/24
   # dark drilled recesses against steel rotor
   rod('Rotor drilled recess',(x+s*.002,y+.138*sin(a),.305+.138*cos(a)),(x+s*.0025,y+.138*sin(a),.305+.138*cos(a)),.004,'Graphite fairing',12)
  for k in range(6):
   a=k*2*pi/6;rod('Rotor bobbin',(x-.005,y+.105*sin(a),.305+.105*cos(a)),(x+.005,y+.105*sin(a),.305+.105*cos(a)),.008,'Bronze fork',12)
 for k in range(42):
  a=k*2*pi/42
  for s in [-1,1]:
   pts=[]
   for j in range(5):
    t=j/4;x=s*w*(.18+t*.66);r=.307-.025*t*t;aa=a+s*t*.11;pts.append((x,y+r*sin(aa),.305+r*cos(aa)))
   tube('Directional tire sipe',pts,.00135,'Graphite fairing')
 parent_parts([o for o in set(bpy.data.objects)-before if o!=root],root)
# frame and engine construction
for s in [-1,1]:
 tube('Perimeter frame rail',[(s*.115,.39,.89),(s*.20,.05,.72),(s*.19,-.27,.56),(s*.10,-.39,.43)],.034,'Anodized aluminum')
 tube('Rear subframe',[(s*.15,-.15,.63),(s*.115,-.75,.94),(s*.075,-.92,.96)],.018,'Anodized aluminum')
 tube('Braced swingarm',[(s*.17,-.18,.41),(s*.14,-.42,.36),(s*.12,-.70,.305)],.03,'Anodized aluminum')
 tube('Swingarm upper rib',[(s*.17,-.18,.41),(s*.15,-.52,.44),(s*.12,-.70,.305)],.018,'Anodized aluminum')
 rod('Rear axle adjuster',(s*.11,-.70,.305),(s*.145,-.70,.305),.025,'Machined steel')
 rod('Fork stanchion',(s*.095,.41,.96),(s*.095,.61,.50),.023,'Bronze fork')
 rod('Fork slider',(s*.095,.59,.56),(s*.095,.70,.305),.027,'Anodized aluminum')
 rod('Axle bolt',(s*.08,.70,.305),(s*.135,.70,.305),.014,'Machined steel')
 # engine covers with stepped profiles
 rod('Engine case',(s*.09,-.035,.41),(s*.165,-.035,.41),.12,'Anodized aluminum',48)
 rod('Engine cover',(s*.164,-.035,.41),(s*.177,-.035,.41),.093,'Titanium exhaust',48)
 for k in range(8):
  a=2*pi*k/8;rod('Case fastener',(s*.18,-.035+.102*sin(a),.41+.102*cos(a)),(s*.187,-.035+.102*sin(a),.41+.102*cos(a)),.006,'Machined steel',6)
 rod('Brake caliper',(s*.093,.62,.365),(s*.134,.62,.365),.042,'Bronze fork')
 tube('Brake hose',[(s*.12,.60,.40),(s*.13,.5,.7),(s*.22,.38,1.0)],.004,'Tire rubber')
 # actual foot pegs and rearset triangular brackets
 panel('Rearset bracket',[(s*.18,-.26,.50),(s*.18,-.41,.38),(s*.18,-.17,.35)],'Machined steel')
 rod('Knurled foot peg',(s*.18,-.36,.39),(s*.28,-.36,.39),.012,'Machined steel')
 tube('Foot control lever',[(s*.23,-.37,.39),(s*.24,-.18,.38)],.007,'Anodized aluminum')
 rod('Toe control rubber',(s*.22,-.18,.38),(s*.275,-.18,.38),.012,'Tire rubber')
 # controls
 tube('Clip-on bar',[(s*.085,.43,.98),(s*.17,.40,.99),(s*.36,.30,.98)],.012,'Machined steel')
 rod('Textured grip',(s*.28,.344,.983),(s*.37,.29,.98),.018,'Tire rubber')
 tube('Control lever',[(s*.19,.41,.99),(s*.31,.39,.99),(s*.39,.34,.98)],.006,'Machined steel')
 tube('Mirror stalk',[(s*.21,.65,.96),(s*.30,.59,1.12),(s*.36,.57,1.15)],.009,'Anodized aluminum')
 o=loft('Mirror housing',[(.54,.025,1.11,1.16),(.55,.06,1.10,1.18),(.59,.06,1.10,1.18),(.60,.025,1.11,1.16)],'Graphite fairing',16);o.location.x=s*.36
 # triple clamps
 tube('Triple clamp',[(s*.10,.43,.97),(0,.43,.965)],.026,'Anodized aluminum')
 rod('Fork cap',(s*.095,.43,.966),(s*.095,.43,.99),.023,'Machined steel')
# cylinders, fins, intake and headers
for x in [-.06,.06]:
 rod('Cylinder barrel',(x,.055,.44),(x,.13,.64),.074,'Anodized aluminum',32)
 for z in [.49,.52,.55,.58,.61]:rod('Cooling fin',(x,.08,z),(x,.08,z+.012),.079,'Machined steel',32)
 tube('Exhaust header',[(x,.20,.59),(x,.29,.42),(x,.24,.22),(x,-.19,.19),(.21,-.40,.24)],.023,'Titanium exhaust')
tube('Exhaust collector',[(.20,-.20,.20),(.24,-.40,.24),(.25,-.60,.34)],.046,'Titanium exhaust')
rod('Muffler',(.25,-.42,.27),(.25,-.81,.48),.059,'Titanium exhaust',48);rod('Exhaust outlet',(.25,-.805,.478),(.25,-.83,.49),.043,'Graphite fairing',32)
# radiator lamellas
for k in range(18):tube('Radiator fin',[(-.16,.29,.44+k*.012),(.16,.29,.44+k*.012)],.004,'Anodized aluminum')
for x in [-.17,.17]:rod('Radiator side tank',(x,.29,.43),(x,.29,.67),.018,'Graphite fairing')
# chain, sprockets accurately placed outside wheel
for y,r in [(-.70,.112),(-.20,.05)]:
 rod('Drive sprocket',(-.13,y,.305),(-.14,y,.305),r,'Machined steel',48)
 for i in range(28):
  a=i*2*pi/28;rod('Sprocket tooth',(-.145,y+r*sin(a),.305+r*cos(a)),(-.13,y+r*sin(a),.305+r*cos(a)),.008,'Machined steel',6)
pts=[(-.145,-.70,.42),(-.145,-.20,.355),(-.145,-.15,.305),(-.145,-.20,.255),(-.145,-.70,.193),(-.145,-.81,.305),(-.145,-.70,.42)]
tube('O-ring drive chain',pts,.008,'Titanium exhaust')
for i in range(34):
 t=i/33;y=-.70+.50*t
 for z in [.42-.065*t,.193+.062*t]:rod('Chain pin',(-.158,y,z),(-.133,y,z),.004,'Machined steel',8)
# smooth sculpted tank and seat, custom lofts instead of stacked primitive silhouette
loft('Fuel tank',[(-.34,.09,.74,.79),(-.30,.12,.72,.85),(-.14,.19,.71,.99),(.05,.205,.71,1.035),(.22,.17,.76,1.01),(.30,.105,.80,.94),(.32,.055,.83,.88)],'Pearl ceramic paint')
rod('Fuel cap',(0,.05,1.015),(0,.05,1.028),.046,'Machined steel',48)
loft('Rider saddle',[(-.72,.105,.825,.845),(-.64,.145,.80,.86),(-.46,.15,.775,.84),(-.31,.10,.77,.80)],'Seat vinyl')
loft('Tail cowl',[(-1.00,.015,.97,.99),(-.94,.07,.93,1.01),(-.82,.105,.85,.98),(-.64,.13,.80,.91),(-.58,.08,.80,.86)],'Pearl ceramic paint')
loft('Rear light lens',[(-1.005,.015,.963,.98),(-.96,.068,.934,.961),(-.90,.083,.91,.935)],'Brake light')
# fairing surfaces: longitudinal cross-section strips maintaining a open fork tunnel
for s in [-1,1]:
 v=[];f=[]
 rings=[(-.38,.135,.27,.53),(-.27,.195,.22,.64),(-.10,.245,.22,.77),(.13,.255,.26,.89),(.36,.245,.41,1.025),(.64,.215,.72,1.08),(.86,.15,.78,.94),(.94,.08,.84,.87)]
 for y,w,lo,hi in rings:
  for j in range(7):
   t=j/6;v.append((s*(w+sin(t*pi)*.035),y,lo+(hi-lo)*t))
 for i in range(len(rings)-1):
  for j in range(6):a=i*7+j;f.append((a,a+1,a+8,a+7) if s>0 else (a+7,a+8,a+1,a))
 o=mesh('Sculpted side fairing',v,f,'Pearl ceramic paint');m=o.modifiers.new('Fairing curvature','SUBSURF');m.levels=2;m=o.modifiers.new('Shell thickness','SOLIDIFY');m.thickness=.005
 panel('Graphite belly pan',[(s*.15,-.38,.26),(s*.22,-.1,.22),(s*.27,.20,.29),(s*.28,.05,.51),(s*.24,-.14,.64)],'Graphite fairing')
 panel('Air extraction vent',[(s*.276,.04,.63),(s*.276,.32,.79),(s*.283,.37,.65),(s*.276,.12,.47)],'Graphite fairing')
 panel('Orange accent blade',[(s*.279,.06,.68),(s*.264,.34,.85),(s*.285,.22,.71)],'Orange')
 tube('Panel separation seam',[(s*.18,-.30,.63),(s*.255,-.11,.77),(s*.27,.13,.89)],.002,'Graphite fairing')
 tube('LED headlight housing',[(s*.07,.922,.86),(s*.17,.85,.88),(s*.218,.72,.93)],.022,'Graphite fairing')
 tube('LED headlight strip',[(s*.075,.944,.868),(s*.165,.876,.889),(s*.207,.755,.936)],.0055,'Headlight')
 for y,z,x in [(-.23,.61,.22),(.17,.87,.263),(.39,.98,.25),(-.15,.28,.22)]:rod('Flush fairing screw',(s*x,y,z),(s*(x+.007),y,z),.004,'Machined steel',6)
# windscreen double curved surface
v=[];f=[]
for i in range(10):
 t=i/9
 for j in range(17):
  a=(j/16-.5)*pi;x=.18*cos(t*pi*.32)*sin(a);v.append((x,.68-.23*t+.10*cos(a),1.005+.20*t-.09*(abs(sin(a))**2)))
for i in range(9):
 for j in range(16):a=i*17+j;f.append((a,a+1,a+18,a+17))
o=mesh('Smoked windscreen',v,f,'Glass');m=o.modifiers.new('Screen thickness','SOLIDIFY');m.thickness=.002
# front fender over tire as curved shell
v=[];f=[]
for i in range(28):
 a=-.8+i/27*1.8
 for j in range(9):
  t=(j/8-.5)*2;r=.343-.018*t*t;v.append((t*.078,.70+r*sin(a),.305+r*cos(a)))
for i in range(27):
 for j in range(8):a=i*9+j;f.append((a,a+1,a+10,a+9))
o=mesh('Front wheel mudguard',v,f,'Graphite fairing');s=o.modifiers.new('Mudguard shell','SOLIDIFY');s.thickness=.004
panel('TFT instrument housing',[(-.077,.47,1.00),(.077,.47,1.00),(.065,.52,1.075),(-.065,.52,1.075)],'Graphite fairing',.018)
panel('TFT instrument display',[(-.065,.466,1.013),(.065,.466,1.013),(.056,.507,1.064),(-.056,.507,1.064)],'Dash',.001)
# Split-tone side panels follow the outer fairing surface, with an open engine reveal.
for ob in list(bpy.data.objects):
 if ob.name.startswith('Sculpted side fairing'):
  ob.data.materials.append(M['Graphite fairing'])
  for p in ob.data.polygons:
   if p.index%6<3:p.material_index=1
# Steering assembly rotates around the steering head; wheels keep their spin pivots.
steering=empty('SteeringAssembly',(0,.43,.97))
steered=[o for o in list(bpy.data.objects) if o.parent is None and any(o.name.startswith(n) for n in ['Fork stanchion','Fork slider','Axle bolt','Brake caliper','Brake hose','Clip-on bar','Textured grip','Control lever','Triple clamp','Fork cap','Front wheel mudguard'])]
parent_parts(steered+[wheelroots[1]],steering)
# parent bike objects
parent_parts([o for o in list(bpy.data.objects) if o!=bike and o.parent is None],bike)
# save bike first; rider is based on CC0 MakeHuman topology and rig weight map
print('BIKE COMPLETE',len(bpy.data.objects),flush=True)
# Load all source vertices with body faces, preserve UVs
raw=[];faces=[];uv=[];fuv=[];group=''
for l in open(ROOT+'/work/references/human-base.obj'):
 p=l.split()
 if not p:continue
 if p[0]=='v':raw.append(Vector((float(p[1])*.105,float(p[3])*.105,float(p[2])*.105)))
 elif p[0]=='vt':uv.append(tuple(map(float,p[1:3])))
 elif p[0]=='g':group=p[1]
 elif p[0]=='f' and group=='body':
  faces.append([int(x.split('/')[0])-1 for x in p[1:]]);fuv.append([int(x.split('/')[1])-1 for x in p[1:]])
r=json.load(open(ROOT+'/work/references/default.mhskel'));weights=json.load(open(ROOT+'/work/references/default_weights.mhw'))['weights']
rest={}
for n,b in r['bones'].items():rest[n]=[sum((raw[i] for i in r['joints'][b[k]]),Vector())/len(r['joints'][b[k]]) for k in ['head','tail']]
# Construct posed skeleton by fitting exact endpoints to seat, grips and pegs.
target={};hip=Vector((0,-.47,.93));spine_rot=Quaternion(Vector((1,0,0)),math.radians(-38));root_rest=rest['spine05'][0]
for n in ['root','spine05','spine04','spine03','spine02','spine01','neck01','neck02','neck03','head']:
 target[n]=[hip+spine_rot@(p-root_rest) for p in rest[n]]
# Keep head looking along road instead of into the tank
h=target['head'][0];target['head']=[h,h+Vector((0,.025,(rest['head'][1]-rest['head'][0]).length))]
for side,s in [('L',1),('R',-1)]:
 for n in ['pelvis','clavicle','shoulder01']:
  key=n+'.'+side;target[key]=[hip+spine_rot@(p-root_rest) for p in rest[key]]
 def chain(names,a,b):
  lengths=[(rest[n+'.'+side][1]-rest[n+'.'+side][0]).length for n in names];total=sum(lengths);pos=Vector(a)
  for n,length in zip(names,lengths):end=pos+(Vector(b)-Vector(a))*(length/total);target[n+'.'+side]=[pos.copy(),end.copy()];pos=end
 thigh=Vector((s*.14,-.46,.91));knee=Vector((s*.235,-.055,.58));ankle=Vector((s*.24,-.405,.46))
 chain(['upperleg01','upperleg02'],thigh,knee);chain(['lowerleg01','lowerleg02'],knee,ankle)
 target['foot.'+side]=[ankle,Vector((s*.24,-.285,.40))]
 shoulder=target['shoulder01.'+side][1];elbow=Vector((s*.28,.015,1.12));wrist=Vector((s*.325,.26,1.015))
 chain(['upperarm01','upperarm02'],shoulder,elbow);chain(['lowerarm01','lowerarm02'],elbow,wrist)
 target['wrist.'+side]=[wrist,Vector((s*.34,.315,.985))]
# Curl the four finger chains around each grip instead of leaving an open hand.
for side,s in [('L',1),('R',-1)]:
 for finger in range(2,6):
  x=s*(.31+(finger-2)*.014)
  for segment in range(1,4):
   a=(segment-1)*.85; b=segment*.85
   target[f'finger{finger}-{segment}.'+side]=[Vector((x,.335+.02*cos(a),.971+.021*sin(a))),Vector((x,.335+.02*cos(b),.971+.021*sin(b)))]
# Affine rigid skin matrices for every authored bone; child fingers retain topology.
trans={}
def transform(n):
 if n in trans:return trans[n]
 a,b=rest[n]
 if n in target:
  c,d=target[n];q=(b-a).rotation_difference(d-c);ma=q.to_matrix().to_4x4();ma.translation=c-ma.to_3x3()@a
 else:
  par=r['bones'][n]['parent'];ma=transform(par).copy() if par else Matrix.Identity(4);target[n]=[ma@a,ma@b]
 trans[n]=ma;return ma
for n in rest:transform(n)
posed=[Vector() for v in raw];tot=[0.0]*len(raw)
for n,ws in weights.items():
 if n not in trans:continue
 for i,w in ws:posed[i]+= (trans[n]@raw[i])*w;tot[i]+=w
for i in range(len(posed)):
 if tot[i]>0:posed[i]/=tot[i]
 else:posed[i]=trans['root']@raw[i]
# Remove hidden face/head inside helmet; keep a continuous clothed anatomical mesh.
keep=[i for i,f in enumerate(faces) if -.71 < sum(raw[v].z for v in f)/len(f)<.735]
used=sorted(set(v for i in keep for v in faces[i]));mapping={v:i for i,v in enumerate(used)}
o=mesh('Rider tailored suit',[posed[v] for v in used],[[mapping[v] for v in faces[i]] for i in keep],'Textile');o.data.materials.append(M['Leather']);o.data.materials.append(M['White piping'])
uvlayer=o.data.uv_layers.new(name='UVMap')
for poly,fi in zip(o.data.polygons,keep):
 z=sum(raw[v].z for v in faces[fi])/len(faces[fi]);x=sum(abs(raw[v].x) for v in faces[fi])/len(faces[fi]);poly.material_index=1 if z<-.55 or x>.40 else 0
 for li,ui in zip(poly.loop_indices,fuv[fi]):uvlayer.data[li].uv=uv[ui]
# Inflate suit subtly; subdivision maintains human surface anatomy.
solid=o.modifiers.new('Protective garment thickness','SOLIDIFY');solid.thickness=.009
sub=o.modifiers.new('Suit surface continuity','SUBSURF');sub.levels=1
# A separate motorcycle jacket is tailored over the skinned anatomical base.
jacket_ids=[i for i,f in enumerate(faces) if .07<sum(raw[v].z for v in f)/len(f)<.58 and max(abs(raw[v].x) for v in f)<.31]
jacket_used=sorted(set(v for i in jacket_ids for v in faces[i]));jm={v:i for i,v in enumerate(jacket_used)}
jacket=mesh('Armored textile riding jacket',[posed[v] for v in jacket_used],[[jm[v] for v in faces[i]] for i in jacket_ids],'Textile')
jacket.data.materials.append(M['Leather'])
for poly,fi in zip(jacket.data.polygons,jacket_ids):
 x=sum(abs(raw[v].x) for v in faces[fi])/len(faces[fi]);z=sum(raw[v].z for v in faces[fi])/len(faces[fi]);poly.material_index=1 if x>.15 and z>.40 else 0
sol=jacket.modifiers.new('Tailored jacket volume','SOLIDIFY');sol.thickness=.024;sol.offset=1
sub=jacket.modifiers.new('Garment curvature','SUBSURF');sub.levels=1;jacket.parent=bike
# Seams follow the actual posed human topology instead of guessed primitive limbs.
for side in [-1,1]:
 pts=[]
 for z in [.10,.16,.22,.28,.34,.40,.46,.52]:
  candidates=[i for i in used if abs(raw[i].z-z)<.016 and abs(raw[i].x-side*.065)<.022]
  if candidates:
   i=min(candidates,key=lambda i:raw[i].y);pt=posed[i]+Vector((0,-.018,.006));pts.append(tuple(pt))
 if len(pts)>2:tube('Back jacket stitching',pts,.0025,'White piping').parent=bike
pts=[]
for z in [.11,.17,.23,.29,.35,.41,.47,.53]:
 candidates=[i for i in used if abs(raw[i].z-z)<.018 and abs(raw[i].x)<.018]
 if candidates:
  i=max(candidates,key=lambda i:raw[i].y);pt=posed[i]+Vector((0,.025,.007));pts.append(tuple(pt))
if len(pts)>2:tube('Jacket zipper',pts,.003,'Anodized aluminum').parent=bike
# Real armature in posed bind space, original weights retained for runtime secondary motion.
arm=bpy.data.armatures.new('Rider skeleton');rig=bpy.data.objects.new('RiderRig',arm);bpy.context.collection.objects.link(rig);bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
for n,(a,b) in target.items():
 eb=arm.edit_bones.new(n);eb.head=a;eb.tail=b if (b-a).length>.001 else a+Vector((0,0,.01))
for n,b in r['bones'].items():
 if b['parent']:arm.edit_bones[n].parent=arm.edit_bones[b['parent']]
bpy.ops.object.mode_set(mode='OBJECT')
for n,ws in weights.items():
 vg=o.vertex_groups.new(name=n)
 for i,w in ws:
  if i in mapping:vg.add([mapping[i]],w,'REPLACE')
m=o.modifiers.new('Rider skeletal deformation','ARMATURE');m.object=rig;o.parent=rig;rig.parent=bike
# Helmet sculpted by rings, chinbar and visor; based on helmet proportions in reference.
headpos=target['head'][0]+Vector((0,.015,.08));hy=headpos.y;hz=headpos.z
before=set(bpy.data.objects)
helmet=loft('Helmet shell',[(hy-.14,.025,hz-.08,hz+.08),(hy-.12,.105,hz-.12,hz+.14),(hy-.05,.135,hz-.145,hz+.18),(hy+.055,.13,hz-.14,hz+.155),(hy+.135,.095,hz-.125,hz+.08),(hy+.17,.025,hz-.085,hz-.02)],'Pearl ceramic paint',32)
# curved visor patch wrapping front of full face
v=[];f=[]
for i in range(9):
 t=i/8
 for j in range(25):
  a=-1.25+j/24*2.5;v.append((.136*sin(a),hy+.190*cos(a)+.012,hz-.01+t*.081-.024*abs(sin(a))))
for i in range(8):
 for j in range(24):a=i*25+j;f.append((a,a+1,a+26,a+25))
mesh('Helmet smoked visor',v,f,'Glass')
for s in [-1,1]:
 tube('Helmet chin vent',[(s*.04,hy+.158,hz-.075),(s*.065,hy+.145,hz-.056)],.008,'Graphite fairing')
 rod('Visor hinge',(s*.124,hy+.03,hz+.025),(s*.141,hy+.03,hz+.025),.018,'Anodized aluminum')
headroot=empty('Helmet',headpos);parent_parts([x for x in set(bpy.data.objects)-before if x!=headroot],headroot);headroot.parent=bike
# boots over human feet and knee armor with nonuniform loft cross-sections
for s in [-1,1]:
 o=loft('Armored boot',[(-.49,.033,.39,.48),(-.46,.059,.36,.54),(-.39,.065,.36,.53),(-.27,.061,.365,.44),(-.20,.03,.38,.41)],'Leather',24);o.location.x=s*.24;o.parent=bike
 o=loft('Knee armor',[(-.13,.035,.57,.61),(-.08,.067,.535,.64),(-.02,.053,.535,.615),(.00,.022,.555,.59)],'Leather',20);o.location.x=s*.24;o.parent=bike
 tube('Suit shoulder reflective seam',[(s*.10,-.15,1.35),(s*.18,-.10,1.32),(s*.235,-.02,1.24)],.003,'White piping').parent=bike
# Select all game objects, apply non-armature modifiers and curve conversion for export
bpy.ops.object.select_all(action='DESELECT')
for ob in list(bpy.data.objects):
 if ob.type in ['MESH','CURVE']:
  bpy.context.view_layer.objects.active=ob;ob.select_set(True)
  if ob.type=='CURVE':bpy.ops.object.convert(target='MESH')
  else:
   for mod in list(ob.modifiers):
    if mod.type!='ARMATURE':
     try:bpy.ops.object.modifier_apply(modifier=mod.name)
     except:pass
  ob.select_set(False)
# Correct orientation after generated surface and modifier evaluation.
for ob in list(bpy.data.objects):
 if ob.type=='MESH':
  bpy.context.view_layer.objects.active=ob;ob.select_set(True);bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.normals_make_consistent(inside=False);bpy.ops.object.mode_set(mode='OBJECT');ob.select_set(False)
# UV unwrap manufactured pieces where missing, including profile-based bodywork
for ob in list(bpy.data.objects):
 if ob.type=='MESH' and not ob.data.uv_layers:
  bpy.context.view_layer.objects.active=ob;ob.select_set(True);bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=1.15,island_margin=.025);bpy.ops.object.mode_set(mode='OBJECT');ob.select_set(False)
for ob in list(bpy.data.objects):
 if ob.type=='MESH' and ob.name.startswith('TFT instrument display'):
  layer=ob.data.uv_layers.active
  for poly in ob.data.polygons:
   for li,uv in zip(poly.loop_indices,[(0,0),(1,0),(1,1),(0,1)]):layer.data[li].uv=uv
# Merge by material within static groups to limit draw calls; keep wheels and rig separate.
for p in [bike,steering]+wheelroots+[headroot]:
 candidates=[ob for ob in list(bpy.data.objects) if ob.type=='MESH' and ob.parent==p and not any(m.type=='ARMATURE' for m in ob.modifiers)]
 for material in M.values():
  same=[ob for ob in list(bpy.data.objects) if ob.type=="MESH" and ob.parent==p and not any(m.type=="ARMATURE" for m in ob.modifiers) and len(ob.data.materials)==1 and ob.data.materials[0]==material]
  if len(same)>1:
   bpy.ops.object.select_all(action='DESELECT')
   for ob in same:ob.select_set(True)
   bpy.context.view_layer.objects.active=same[0];bpy.ops.object.join();same[0].name=p.name+' — '+material.name
# Export clean asset before studio objects.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT+'/motorcycle.glb',export_format='GLB',use_selection=True,export_yup=True,export_animations=False)
bpy.ops.wm.save_as_mainfile(filepath=ROOT+'/outputs/shelby-ride/motorcycle.blend')
# studio multiangle renders
floor=mat('Studio',(.12,.14,.16),0,.8)
bpy.ops.mesh.primitive_plane_add(size=200);bpy.context.object.data.materials.append(floor)
scene.world.color=(.18,.18,.18)
for loc,power,size in [((3,2,5),800,4),((-3,1,3),650,3),((1,-4,4),1100,3)]:
 bpy.ops.object.light_add(type='AREA',location=loc);light=bpy.context.object;light.data.energy=power;light.data.shape='DISK';light.data.size=size;light.rotation_euler=(Vector((0,0,.8))-light.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(3.6,3.1,2.0));cam=bpy.context.object;scene.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=2.8
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.render.resolution_x=1200;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
for n,loc in [('front',(3,3,1.8)),('side',(4,0,1.2)),('rear',(-3,-3,1.8))]:
 cam.location=loc;cam.rotation_euler=(Vector((0,0,.83))-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=ROOT+'/work/'+n+'.png';bpy.ops.render.render(write_still=True)
print('ASSET FINISHED',flush=True)
