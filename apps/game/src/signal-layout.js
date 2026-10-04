import {laneCenter,laneCount,priority} from './road-layout.js';
import {clearSignalBase,coversPavement} from './signal-clearance.js';

const angle=(a,b)=>Math.abs(Math.atan2(Math.sin(a-b),Math.cos(a-b)));
const corridor=road=>road.name&&road.name!=='Local road'?road.name:road.id;

export function signalArmsCross(a,b){
 const ends=s=>{const right=[Math.cos(s.pole.heading),Math.sin(s.pole.heading)];return [Math.sign(s.armEnd)*.45,s.armEnd].map(t=>[s.pole.x+right[0]*t,s.pole.z+right[1]*t])};
 const [p,q]=ends(a),[r,s]=ends(b),cross=(u,v,w)=>(v[0]-u[0])*(w[1]-u[1])-(v[1]-u[1])*(w[0]-u[0]);
 return cross(p,q,r)*cross(p,q,s)<0&&cross(r,s,p)*cross(r,s,q)<0;
}

export function configureSignals(edges){
 const incoming=new Map();
 for(const edge of edges){if(!incoming.has(edge.to))incoming.set(edge.to,[]);incoming.get(edge.to).push(edge)}
 const groups=new Map();
 for(const edge of edges.filter(e=>e.signal)){
  const group=edge.signal.group;if(!groups.has(group))groups.set(group,[]);groups.get(group).push(edge);
 }
 for(const [group,approaches] of groups){
  const axes=[];
  for(const e of approaches.slice().sort((a,b)=>priority(b.road)-priority(a.road)||b.road.width-a.road.width)){
   let axis=axes.findIndex(a=>a.roads.has(corridor(e.road))||Math.abs(Math.cos(e.heading-a.heading))>Math.cos(Math.PI/9));
   if(axis<0){axis=axes.length;axes.push({heading:e.heading,roads:new Set()})}
   axes[axis].roads.add(corridor(e.road));e.axis=axis;
   const crossing=approaches.filter(other=>Math.abs(Math.cos(other.heading-e.heading))<.94);
   e.stopDistance=Math.max(6,...crossing.map(other=>other.road.width/2/Math.max(.35,Math.abs(Math.sin(other.heading-e.heading)))+2.5));
  }
  group.axisCount=Math.max(2,axes.length);
 }
 return incoming;
}

// OSM often splits the last few metres of an approach into several segments.
// Follow its centreline back instead of extending a tiny segment past a bend.
export function approachPoint(edge,distance,incoming){
 const seen=new Set();let current=edge,remaining=distance;
 while(remaining>current.len&&!seen.has(current)){
  seen.add(current);const previous=(incoming.get(current.from)||[]).filter(e=>!seen.has(e)&&e.from!==current.to&&angle(e.heading,current.heading)<Math.PI/6);
  previous.sort((a,b)=>(corridor(b.road)===corridor(current.road))-(corridor(a.road)===corridor(current.road))||angle(a.heading,current.heading)-angle(b.heading,current.heading));
  if(!previous.length)break;
  remaining-=current.len;current=previous[0];
 }
 const t=Math.max(0,1-remaining/current.len);
 return {x:current.a[0]+(current.b[0]-current.a[0])*t,z:-current.a[1]-(current.b[1]-current.a[1])*t,y:current.a[2]+(current.b[2]-current.a[2])*t,heading:current.heading};
}

export function departurePoint(edge,distance,outgoing){
 let current=edge,remaining=distance;const seen=new Set([edge]);
 while(true){
  const options=(outgoing.get(current.to)||[]).filter(e=>!seen.has(e)&&e.to!==current.from&&angle(e.heading,current.heading)<Math.PI/6);
  options.sort((a,b)=>(corridor(b.road)===corridor(current.road))-(corridor(a.road)===corridor(current.road))||angle(a.heading,current.heading)-angle(b.heading,current.heading));
  const next=options[0];
  // A T junction has no continuation beyond the cross street. Its far-side
  // support still belongs opposite the incoming approach, on the far sidewalk.
  if(!next)return {x:current.b[0]+Math.sin(current.heading)*remaining,z:-current.b[1]-Math.cos(current.heading)*remaining,y:current.b[2],heading:current.heading,road:current.road};
  if(remaining<=next.len){const t=remaining/next.len;return {x:next.a[0]+(next.b[0]-next.a[0])*t,z:-next.a[1]-(next.b[1]-next.a[1])*t,y:next.a[2]+(next.b[2]-next.a[2])*t,heading:next.heading,road:next.road}}
  remaining-=next.len;current=next;seen.add(next);
 }
}

export function signalLayouts(edges,incoming,world){
 const layouts=[],outgoing=new Map(),signalGroups=new Map();
 for(const edge of edges){
  if(!outgoing.has(edge.from))outgoing.set(edge.from,[]);outgoing.get(edge.from).push(edge);
  if(edge.signal){const group=edge.signal.group;if(!signalGroups.has(group))signalGroups.set(group,[]);signalGroups.get(group).push(edge)}
 }
 for(const e of edges){
  if(!e.signal||e.road.bridge||e.road.class==='motorway')continue;
  const duplicate=layouts.find(s=>s.e.signal.group===e.signal.group&&s.e.axis===e.axis&&angle(s.e.heading,e.heading)<Math.PI/9&&Math.hypot(s.e.b[0]-e.b[0],s.e.b[1]-e.b[1])<25);
  if(duplicate){
   // Several OSM nodes can describe the same physical approach. Their cars
   // must obey the same painted stop bar as the single visible signal.
   e.visualControl=duplicate;e.stopDistance=(e.b[0]-duplicate.stop.x)*Math.sin(e.heading)+(e.b[1]+duplicate.stop.z)*Math.cos(e.heading);continue;
  }
  if(world.grid){
   const crossings=new Set(signalGroups.get(e.signal.group).filter(other=>corridor(other.road)!==corridor(e.road)&&Math.abs(Math.cos(other.heading-e.heading))<.94).map(other=>corridor(other.road)));
   if(crossings.size){
    // Follow the curved approach out of the actual crossing pavement. Width
    // divided by a final-segment angle is unreliable on short turn lanes.
    for(let distance=0;distance<=60;distance+=.5){
     const point=approachPoint(e,distance,incoming);
     if(!coversPavement(world,point.x,point.z,point.y,0,road=>crossings.has(corridor(road)))){e.stopDistance=Math.max(3,distance+2.5);break}
    }
   }
  }
  const curb=e.road.width/2+1.2-(e.road.oneway?e.road.pavementOffset||0:0);
  const stop=approachPoint(e,e.stopDistance,incoming),farDistance=Math.max(6,e.stopDistance-1);
  let pole,right,headRoad;
  for(const setback of [0,-.6,-1.2,-2,2,4,6,8,10,14,18,24,30,40]){
   const p=departurePoint(e,farDistance+setback,outgoing);
   const farCurb=Math.max(curb,p.road.width/2+1.2-(p.road.oneway?p.road.pavementOffset||0:0));
   for(const offset of [farCurb,farCurb-.3,farCurb+.4,farCurb+1,farCurb+2,farCurb+4,-farCurb,-farCurb-.4,-farCurb-2]){
    const candidate={x:p.x+Math.cos(p.heading)*offset,z:p.z+Math.sin(p.heading)*offset,y:p.y,heading:p.heading};
    if(clearSignalBase(world,candidate)&&!layouts.some(s=>Math.hypot(s.pole.x-candidate.x,s.pole.z-candidate.z)<1)){
     pole=candidate;right=offset;headRoad=p.road;break;
    }
   }
   if(pole)break;
  }
  if(!pole)continue;
  const lanes=Array.from({length:Math.min(laneCount(e.road),laneCount(headRoad))},(_,i)=>laneCenter(headRoad,i));
  const reach=lanes.map(lane=>lane-right).sort((a,b)=>Math.abs(b)-Math.abs(a))[0],armEnd=reach+Math.sign(reach)*.4;
  const layout={e,pole,right,stop,lanes,armEnd,armLength:Math.abs(armEnd)};layouts.push(layout);e.visualControl=layout;
 }
 // Adjacent skew approaches can share a corner. Separate the mast arms in
 // height while keeping the signal heads at the same readable elevation.
 for(let i=0;i<layouts.length;i++){
  const layout=layouts[i],crossing=layouts.slice(0,i).filter(other=>signalArmsCross(layout,other));layout.mastHeight=6.5;
  while(crossing.some(other=>Math.abs(other.mastHeight-layout.mastHeight)<.3))layout.mastHeight+=.35;
 }
 return layouts;
}
