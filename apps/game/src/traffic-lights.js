import * as T from 'three';
import {laneCount} from './road-layout.js';

function visorGeometry(){
 const p=[],indices=[];
 for(let i=0;i<=10;i++)for(const z of [0,.19]){const a=i/10*Math.PI;p.push(Math.cos(a)*.145,Math.sin(a)*.145,z)}
 for(let i=0;i<10;i++){const j=i*2;indices.push(j,j+1,j+2,j+1,j+3,j+2)}
 const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(p,3));g.setIndex(indices);g.computeVertexNormals();return g;
}

// Shared geometry and instanced batches for every pole, head and lens in town.
export function addTrafficLights(scene,layouts){
 const metal=new T.MeshStandardMaterial({color:0x929c9f,metalness:.65,roughness:.5});
 const dark=new T.MeshStandardMaterial({color:0x202322,roughness:.85});
 const yellow=new T.MeshStandardMaterial({color:0xe6ac35,roughness:.65});
 // Unlit lenses keep their individual signal colors in daylight and at dusk.
 const lens=new T.MeshBasicMaterial({color:0xffffff,toneMapped:false});
 const parts={metal:{geometry:new T.CylinderGeometry(1,1,1,8),material:metal,items:[]},base:{geometry:new T.BoxGeometry(1,1,1),material:metal,items:[]},back:{geometry:new T.BoxGeometry(1,1,1),material:dark,items:[]},housing:{geometry:new T.BoxGeometry(1,1,1),material:yellow,items:[]},visor:{geometry:visorGeometry(),material:dark,items:[]},lens:{geometry:new T.CircleGeometry(.115,16),material:lens,items:[]},line:{geometry:new T.BoxGeometry(1,1,1),material:new T.MeshStandardMaterial({color:0xe5dfca,roughness:.9}),items:[]}};
 const records=[],up=new T.Vector3(0,1,0),dummy=new T.Object3D();
 for(const layout of layouts){
  const {e,pole,right,lanes,armEnd,mastHeight,stop}=layout,root=new T.Object3D();root.position.set(pole.x,pole.y,pole.z);root.rotation.y=-pole.heading;root.updateMatrix();
  const record={layout,lenses:[],parts:[],visible:true,phase:null};records.push(record);
  const add=(kind,position,scale=[1,1,1],rotation=null,color=null)=>{
   dummy.position.set(...position);dummy.scale.set(...scale);dummy.quaternion.identity();if(rotation)dummy.quaternion.copy(rotation);dummy.updateMatrix();
   const item={matrix:new T.Matrix4().multiplyMatrices(root.matrix,dummy.matrix),record,color};parts[kind].items.push(item);record.parts.push(item);if(kind==='lens')record.lenses.push(item);
  };
  const tube=(a,b,r)=>{const start=new T.Vector3(...a),end=new T.Vector3(...b),delta=end.clone().sub(start);add('metal',start.add(end).multiplyScalar(.5).toArray(),[r,delta.length(),r],new T.Quaternion().setFromUnitVectors(up,delta.normalize()))};
  const elbow=Math.sign(armEnd)*.45;
  tube([0,0,0],[0,mastHeight-.25,0],.085);tube([0,mastHeight-.25,0],[elbow,mastHeight,0],.085);tube([elbow,mastHeight,0],[armEnd,mastHeight,0],.075);add('base',[0,.09,0],[.32,.18,.32]);
  const head=(x,height)=>{
   add('back',[x,height,0],[.53,1.38,.12]);add('housing',[x,height,.095],[.38,1.12,.2]);
   ['red','yellow','green'].forEach((color,i)=>{const y=height+.35-i*.35;add('lens',[x,y,.203],[1,1,1],null,color);add('visor',[x,y,.207])});
  };
  for(const lane of lanes){const x=lane-right;tube([x,mastHeight,0],[x,6.12,0],.025);head(x,5.42)}
  head(0,3.05);
  // The stripe covers only the incoming half of a two-way road.
  const width=laneCount(e.road)*(e.road.laneWidth||3.35),center=(lanes[0]+lanes.at(-1))/2,fx=Math.sin(stop.heading),fy=Math.cos(stop.heading);
  dummy.position.set(stop.x+fx*.2+Math.cos(stop.heading)*center,stop.y+.055,stop.z-fy*.2+Math.sin(stop.heading)*center);dummy.rotation.set(0,-stop.heading,0);dummy.scale.set(width,.025,.4);dummy.updateMatrix();
  const marking={matrix:dummy.matrix.clone(),record};parts.line.items.push(marking);record.parts.push(marking);
 }
 for(const [kind,part] of Object.entries(parts)){
  if(!part.items.length)continue;
  const mesh=new T.InstancedMesh(part.geometry,part.material,part.items.length);mesh.instanceMatrix.setUsage(T.DynamicDrawUsage);mesh.castShadow=kind!=='lens';mesh.frustumCulled=false;scene.add(mesh);part.mesh=mesh;
  part.items.forEach((item,i)=>{item.mesh=mesh;item.index=i;mesh.setMatrixAt(i,item.matrix);if(kind==='lens')mesh.setColorAt(i,new T.Color(0x080a08))});
 }
 const off=new T.Color(0x080a08),colors={red:new T.Color(0xff1605),yellow:new T.Color(0xffb500),green:new T.Color(0x16e65c)},hidden=new T.Matrix4().makeScale(0,0,0);
 return {records,update(p,phaseFor){
  for(const record of records){
   const pole=record.layout.pole,visible=Math.hypot(pole.x-p.x,pole.z-p.z)<850;
   if(visible!==record.visible){for(const item of record.parts){item.mesh.setMatrixAt(item.index,visible?item.matrix:hidden);item.mesh.instanceMatrix.needsUpdate=true}record.visible=visible}
   if(!visible)continue;
   const phase=phaseFor(record.layout.e);if(record.phase===phase)continue;
   for(const item of record.lenses){item.mesh.setColorAt(item.index,item.color===phase?colors[item.color]:off);item.mesh.instanceColor.needsUpdate=true}record.phase=phase;
  }
 }};
}
