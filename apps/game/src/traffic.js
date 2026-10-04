import {laneCenter,laneCount,defaultSpeed,canTurn,priority,turnPosition} from './road-layout.js';
import {configureSignals,signalLayouts} from './signal-layout.js';
import {addTrafficLights} from './traffic-lights.js';
import * as T from 'three';
const arterial=new Set(['motorway','trunk','primary','secondary','tertiary','motorway_link','trunk_link','primary_link','secondary_link','tertiary_link','residential','unclassified','living_street','service']);
const needsBend=(a,b)=>Math.abs(Math.atan2(Math.sin(a.heading-b.heading),Math.cos(a.heading-b.heading)))>.05||Math.abs(laneCenter(a.road)-laneCenter(b.road))>.1;
export function signalPhase(time,axis,offset=0,axisCount=2){const cycle=33*axisCount,phase=((time+offset-axis*33)%cycle+cycle)%cycle;return phase<28?'green':phase<31?'yellow':'red'}
export function followingSpeed(cruise,gap,leaderSpeed){return Math.max(0,Math.min(cruise,leaderSpeed+Math.max(-8,(gap-5-cruise*1.15)*.55),Math.sqrt(Math.max(0,2*3.5*(gap-3)))))}
export class RoadTraffic{
 constructor(world){this.world=world;this.time=0;this.edges=[];this.out=new Map();this.cars=[];this.signals=[];this.seed=135;const groups=[];
 for(const signal of world.data.signals||[]){let group=groups.find(g=>Math.hypot(g.x-signal.point[0],g.y-signal.point[1])<65);if(!group){group={x:signal.point[0],y:signal.point[1],offset:groups.length*7%66};groups.push(group)}signal.group=group}
 const stopsByNode=new Map((world.data.stops||[]).map(s=>[s.node,s]));this.restrictions=world.data.restrictions||[];this.reservations=new Map();const signalByNode=new Map((world.data.signals||[]).map(s=>[s.node,s]));
 for(const road of world.data.roads){if(!arterial.has(road.class))continue;for(let i=1;i<road.points.length;i++){for(const reverse of road.oneway?[false]:[false,true]){const a=road.points[reverse?i:i-1],b=road.points[reverse?i-1:i],from=road.nodeIds[reverse?i:i-1],to=road.nodeIds[reverse?i-1:i],len=Math.hypot(b[0]-a[0],b[1]-a[1]);if(len<1)continue;const heading=Math.atan2(b[0]-a[0],b[1]-a[1]),mph=parseFloat(road.maxspeed)||(['motorway','motorway_link'].includes(road.class)?65:40);const edge={a,b,from,to,len,heading,road,speed:Math.min(31,defaultSpeed(road)),stop:stopsByNode.get(to),signal:signalByNode.get(to),axis:Math.abs(b[0]-a[0])>Math.abs(b[1]-a[1])?0:1};this.edges.push(edge);if(!this.out.has(from))this.out.set(from,[]);this.out.get(from).push(edge)}}}
 this.incoming=configureSignals(this.edges);
 this.signalLayouts=signalLayouts(this.edges,this.incoming,world);
 }
 random(){this.seed=(Math.imul(this.seed,1664525)+1013904223)>>>0;return this.seed/4294967296}
 next(edge){const options=(this.out.get(edge.to)||[]).filter(e=>e.to!==edge.from&&canTurn(this.restrictions,edge.road.id,e.road.id,edge.to));if(!options.length)return null;options.sort((a,b)=>Math.cos(b.heading-edge.heading)-Math.cos(a.heading-edge.heading));return this.random()<.84?options[0]:options[Math.floor(this.random()*options.length)]}
 phase(edge){const group=edge.signal.group;return signalPhase(this.time,edge.axis,group.offset,group.axisCount)}
 planRoute(car){
  if(!car.route||car.route[0]!==car.next)car.route=car.next?[car.next]:[];
  let length=car.edge.len-car.distance+car.route.reduce((sum,e)=>sum+e.len,0);
  while(length<120&&car.route.length<24){const last=car.route.at(-1)||car.edge,next=this.next(last);if(!next||next===car.edge||car.route.includes(next))break;car.route.push(next);length+=next.len}
 }
 signalAhead(car){
  let distance=-car.distance;
  for(const edge of [car.edge,...car.route]){distance+=edge.len;if(edge.signal){const stop=distance-edge.stopDistance-2.9;if(stop>=-.001)return {edge,distance:Math.max(0,stop)};return null}if(distance>120)break}
  return null;
 }
 async build(scene,loader,carAsset){this.scene=scene;this.lightRenderer=addTrafficLights(scene,this.signalLayouts);this.signals=this.lightRenderer.records;
 const stopAsset=(await loader.loadAsync('/assets/stop-sign.glb')).scene;const stopSeen=new Set();this.stopObjects=[];for(const e of this.edges){if(!e.stop||e.stop.kind!=='stop'||stopSeen.has(e.to))continue;stopSeen.add(e.to);const obj=stopAsset.clone(true),right=e.road.width/2+.7;obj.position.set(e.b[0]-Math.sin(e.heading)*4+Math.cos(e.heading)*right,e.b[2],-e.b[1]+Math.cos(e.heading)*4+Math.sin(e.heading)*right);obj.rotation.y=-e.heading;scene.add(obj);this.stopObjects.push(obj)}
 this.carAsset=carAsset;
 for(let i=0;i<16;i++){const obj=carAsset.clone(true);const brake=[];obj.traverse(o=>{if(o.isMesh){o.castShadow=true;o.material=o.material.clone();if(/tail|rear lens/i.test(o.material.name)){o.material.emissive=new T.Color(0xb31505);brake.push(o.material)}}});scene.add(obj);this.cars.push({id:i,obj,wait:0,released:null,edge:null,distance:0,speed:0,next:null,brake})}
 }
 respawn(car,p){const candidates=this.edges.filter(e=>e.len>25&&Math.hypot(e.a[0]-p.x,-e.a[1]-p.z)<700&&Math.hypot(e.a[0]-p.x,-e.a[1]-p.z)>100);for(let i=0;i<20&&candidates.length;i++){const edge=candidates[Math.floor(this.random()*candidates.length)],distance=this.random()*edge.len;if(this.cars.some(c=>c!==car&&c.edge===edge&&Math.abs(c.distance-distance)<20))continue;Object.assign(car,{edge,distance,speed:0,next:this.next(edge),previous:null,wait:0,released:null});car.obj.rotation.y=-edge.heading;return}car.edge=null;car.obj.visible=false}
 updateSignals(p){for(const obj of this.stopObjects||[])obj.visible=Math.hypot(obj.position.x-p.x,obj.position.z-p.z)<500;this.lightRenderer?.update(p,e=>this.phase(e))}
 update(dt,p){this.time+=dt;
 for(const c of this.cars){if(!c.edge||Math.hypot(c.obj.position.x-p.x,c.obj.position.z-p.z)>950)this.respawn(c,p);if(!c.edge)continue;c.obj.visible=true;this.planRoute(c);const e=c.edge;let desired=e.speed,stopRequired=false;
 const upcoming=this.signalAhead(c);let distanceToSignal=upcoming?.distance??Infinity;
 if(upcoming){const phase=this.phase(upcoming.edge);if(phase==='red'||phase==='yellow'&&distanceToSignal>c.speed*c.speed/7+2){stopRequired=true;desired=Math.min(desired,Math.sqrt(Math.max(0,2*3.2*distanceToSignal)))}}
 for(const other of this.cars){if(other===c||!other.edge)continue;let gap=Infinity;if(other.edge===e&&other.distance>c.distance)gap=other.distance-c.distance-4.6;else if(other.edge===c.next)gap=e.len-c.distance+other.distance-4.6;if(gap<90)desired=Math.min(desired,followingSpeed(e.speed,gap,other.speed))}
 const fx=Math.sin(e.heading),fz=-Math.cos(e.heading),vx=p.x-c.obj.position.x,vz=p.z-c.obj.position.z,forward=vx*fx+vz*fz,lateral=Math.abs(vx*fz-vz*fx);if(forward>0&&forward<70&&lateral<2.1&&Math.abs(p.y-c.obj.position.y)<2)desired=Math.min(desired,followingSpeed(e.speed,forward-4,p.speed));
 if(c.next){const turn=Math.acos(Math.max(-1,Math.min(1,Math.cos(c.next.heading-e.heading))));if(turn>.35&&e.len-c.distance<40)desired=Math.min(desired,Math.sqrt(6*6+4*Math.max(0,e.len-c.distance-4)))}
 if(c.next&&e.len-c.distance<32){const turn=Math.atan2(Math.sin(c.next.heading-e.heading),Math.cos(c.next.heading-e.heading));if(turn<-.35){for(const other of this.cars){if(other===c||!other.edge||other.speed<.3)continue;const opposing=Math.cos(other.edge.heading-e.heading)<-.55,near=Math.hypot(other.obj.position.x-e.b[0],other.obj.position.z+e.b[1])<28;if(opposing&&near&&Math.abs(other.obj.position.y-e.b[2])<2)desired=Math.min(desired,Math.sqrt(Math.max(0,5*(e.len-c.distance-8))))}}}
 const junction=this.out.get(e.to)||[];const controlled=e.stop?.kind==='stop';const needsYield=e.stop?.kind==='give_way'||c.next&&priority(e.road)<priority(c.next.road);const remaining=e.len-c.distance;let hold=false;
 if(controlled&&c.released!==e.to){if(remaining<6&&c.speed<.2)c.wait=(c.wait||0)+dt;if(c.wait>=1.1)c.released=e.to;else hold=true}
 if((needsYield||controlled||junction.length>2)&&remaining<35&&!e.signal){const occupied=this.reservations.get(e.to);if(occupied&&occupied.until>this.time&&occupied.id!==c.id)hold=true;else if(remaining<15&&!hold)this.reservations.set(e.to,{id:c.id,until:this.time+3});if(needsYield){for(const other of this.cars){if(other===c||!other.edge||other.speed<.2||priority(other.edge.road)<priority(e.road))continue;if(Math.abs(other.obj.position.y-e.b[2])<2&&Math.hypot(other.obj.position.x-e.b[0],other.obj.position.z+e.b[1])<22)hold=true}}}
 if(hold){desired=Math.min(desired,Math.sqrt(Math.max(0,6*(remaining-4))));if(remaining>=4){distanceToSignal=Math.min(distanceToSignal,remaining-4);stopRequired=true}}
 const old=c.speed;c.speed+=Math.max(-4.5*dt,Math.min(2*dt,desired-c.speed));let advance=c.speed*dt;if(stopRequired&&distanceToSignal>=0&&advance>=distanceToSignal){advance=distanceToSignal;c.speed=0}c.distance+=advance;
 if(c.distance>=e.len){if(c.next){c.distance-=e.len;c.previous=e;c.edge=c.next;c.route.shift();c.next=c.route[0]||this.next(c.edge);c.wait=0;c.released=null}else{this.respawn(c,p);continue}}
 const r=c.edge,t=Math.min(1,c.distance/r.len),offset=laneCenter(r.road),x=r.a[0]+(r.b[0]-r.a[0])*t+Math.cos(r.heading)*offset,z=-r.a[1]-(r.b[1]-r.a[1])*t+Math.sin(r.heading)*offset;let pose={x,z,heading:r.heading};if(c.next&&needsBend(r,c.next)){const radius=Math.min(8,r.len*.4,c.next.len*.4);if(c.distance>r.len-radius)pose=turnPosition(r,c.next,(c.distance-r.len+radius)/(2*radius))}if(c.previous&&needsBend(c.previous,r)){const radius=Math.min(8,c.previous.len*.4,r.len*.4);if(c.distance<radius)pose=turnPosition(c.previous,r,.5+c.distance/(2*radius))}c.obj.position.set(pose.x,r.a[2]+(r.b[2]-r.a[2])*t,pose.z);const target=-pose.heading,delta=Math.atan2(Math.sin(target-c.obj.rotation.y),Math.cos(target-c.obj.rotation.y));c.obj.rotation.y+=delta*Math.min(1,dt*7);for(const m of c.brake)m.emissiveIntensity=old-c.speed>.015||c.speed<.2?2.5:.2;
 if(!p.crashed&&Math.abs(c.obj.position.y-p.y)<2&&Math.hypot(x-p.x,z-p.z)<2)p.crash();
 }
 }
}
