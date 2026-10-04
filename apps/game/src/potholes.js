import * as T from 'three';
import {laneCenter} from './road-layout.js';
export function potholeAhead(p,holes){
 return holes.some(h=>{const dx=h.x-p.x,dz=h.z-p.z,forward=dx*Math.sin(p.heading)-dz*Math.cos(p.heading),side=dx*Math.cos(p.heading)+dz*Math.sin(p.heading);return Math.abs((h.y??p.y)-p.y)<2&&forward>0&&forward<Math.max(40,Math.abs(p.speed)*3)&&Math.abs(side)<3;});
}
export class Potholes {
 constructor(scene,world,telemetry){
  Object.assign(this,{scene,world,telemetry,holes:[],meshes:new Map(),next:0,busy:false});
  this.geometry=new T.CircleGeometry(.65,11);this.geometry.rotateX(-Math.PI/2);
  this.material=new T.MeshStandardMaterial({color:0x24221f,roughness:1,polygonOffset:true,polygonOffsetFactor:-2,polygonOffsetUnits:-2});
  const spawn=world.spawn();
  for(const s of world.segments.filter(s=>s.len>35&&!s.road.bridge&&s.road.name===world.data.primaryRoadName&&Math.hypot(s.a[0]-spawn.x,s.a[1]+spawn.z)<900).slice(0,18)){
   const t=.55,heading=Math.atan2(s.b[0]-s.a[0],s.b[1]-s.a[1]),offset=laneCenter(s.road);
   this.holes.push({id:'road-'+s.road.id+'-'+s.index,x:s.a[0]+(s.b[0]-s.a[0])*t+Math.cos(heading)*offset,z:-s.a[1]-(s.b[1]-s.a[1])*t+Math.sin(heading)*offset,y:s.a[2],source:'road'});
  }
  this.sync();
 }
 sync(){
  this.world.gameHazards=this.holes;
  for(const [id,m] of this.meshes)if(!this.holes.some(h=>h.id===id)){this.scene.remove(m);this.meshes.delete(id);}
  for(const h of this.holes)if(!this.meshes.has(h.id)){const m=new T.Mesh(this.geometry,this.material);m.position.set(h.x,h.y+.025,h.z);m.scale.set(1.3,1,.8);this.scene.add(m);this.meshes.set(h.id,m);}
 }
 async update(now){
  if(this.busy||now<this.next)return;this.busy=true;this.next=now+5000;
  try{const r=await fetch('/api/game/reports',{signal:AbortSignal.timeout(1500)});if(!r.ok)return;const {reports}=await r.json();this.holes=this.holes.filter(h=>h.source==='road');for(const h of reports){const road=this.world.roadAt(h.x,h.z);if(road&&road.distance<road.road.width/2+1)this.holes.push({...h,y:road.height});}this.sync();}catch{}finally{this.busy=false;}
 }
 async report(p){
  if(!this.telemetry.token)return false;
  try{const r=await fetch('/api/game/reports',{method:'POST',headers:{'Content-Type':'application/json','X-Helmetd':this.telemetry.token},body:JSON.stringify({x:p.x,z:p.z}),signal:AbortSignal.timeout(1500)});if(!r.ok)return false;this.next=0;await this.update(performance.now());return true;}catch{return false;}
 }
}
