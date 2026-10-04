import {canTurn} from './road-layout.js';
const distance=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
const heading=(a,b)=>Math.atan2(b[0]-a[0],b[1]-a[1]);
const wrap=a=>Math.atan2(Math.sin(a),Math.cos(a));
export function project(p,a,b){
 const dx=b[0]-a[0],dy=b[1]-a[1],t=Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy||1)));
 const point=[a[0]+dx*t,a[1]+dy*t];return {t,point,distance:distance(p,point)};
}
class Heap {
 constructor(){this.items=[];}
 push(item){let i=this.items.length;this.items.push(item);while(i){const p=(i-1)>>1;if(this.items[p].cost<=item.cost)break;this.items[i]=this.items[p];i=p;}this.items[i]=item;}
 pop(){const top=this.items[0],last=this.items.pop();if(this.items.length){let i=0;while(i*2+1<this.items.length){let c=i*2+1;if(c+1<this.items.length&&this.items[c+1].cost<this.items[c].cost)c++;if(this.items[c].cost>=last.cost)break;this.items[i]=this.items[c];i=c;}this.items[i]=last;}return top;}
}
export class GameNavigation {
 constructor(data){
  this.edges=[];this.out=new Map();this.restrictions=data.restrictions||[];this.clear();
  for(const road of data.roads)for(let i=1;i<road.points.length;i++){
   const a=road.points[i-1],b=road.points[i],len=distance(a,b);if(len<.01)continue;
   const edge={a,b,len,road,from:String(road.nodeIds[i-1]),to:String(road.nodeIds[i])};
   this.edges.push(edge);this.add(edge);
   if(!road.oneway)this.add({...edge,a:b,b:a,from:edge.to,to:edge.from});
  }
 }
 add(edge){if(!this.out.has(edge.from))this.out.set(edge.from,[]);this.out.get(edge.from).push(edge);}
 nearest(point){let best;for(const edge of this.edges){const p=project(point,edge.a,edge.b);if(!best||p.distance<best.distance)best={...p,edge};}return best;}
 clear(){this.points=[];this.steps=[];this.destination=null;this.state='idle';this.progress=0;this.lastReroute=-Infinity;this.lastUpdate=-Infinity;this.snapshot={state:'idle',maneuver:'none',distance_m:0,remaining_m:0,destination:'',points:[],position:[500,500]};}
 route(p,destination,label='Destination'){
  this.destination={point:destination,label};
  const start=this.nearest([p.x,-p.z]),end=this.nearest(destination);
  if(!start||!end||start.distance>80||end.distance>80){this.state='off_route';this.points=[];this.steps=[];this.length=0;return false;}
  const out=new Map([...this.out].map(([k,v])=>[k,[...v]]));
  const add=e=>{if(!out.has(e.from))out.set(e.from,[]);out.get(e.from).push(e);};
  const part=(base,from,to,a,b)=>({...base,from,to,a,b,len:distance(a,b)});
  add(part(start.edge,'@start',start.edge.to,start.point,start.edge.b));
  if(!start.edge.road.oneway)add(part(start.edge,'@start',start.edge.from,start.point,start.edge.a));
  add(part(end.edge,end.edge.from,'@end',end.edge.a,end.point));
  if(!end.edge.road.oneway)add(part(end.edge,end.edge.to,'@end',end.edge.b,end.point));
  if(start.edge===end.edge&&(end.t>=start.t||!start.edge.road.oneway))add(part(start.edge,'@start','@end',start.point,end.point));
  const heap=new Heap(),best=new Map(),root={node:'@start',road:null,cost:0,previous:null};heap.push(root);let finish;
  while(heap.items.length){
   const item=heap.pop(),key=item.node+'|'+(item.road?.id||'');if(best.has(key)&&best.get(key)<item.cost)continue;
   if(item.node==='@end'){finish=item;break;}
   for(const edge of out.get(item.node)||[]){
    if(item.road&&!canTurn(this.restrictions,item.road.id,edge.road.id,item.node))continue;
    const penalty=item.node==='@start'&&Math.cos(heading(edge.a,edge.b)-p.heading)<0?25:0;
    const cost=item.cost+edge.len+penalty,nextKey=edge.to+'|'+edge.road.id;
    if(best.has(nextKey)&&best.get(nextKey)<=cost)continue;
    best.set(nextKey,cost);heap.push({node:edge.to,road:edge.road,cost,previous:item,edge});
   }
  }
  if(!finish){this.points=[];this.steps=[];this.state='off_route';this.length=0;return false;}
  const edges=[];while(finish.edge){edges.push(finish.edge);finish=finish.previous;}edges.reverse();
  this.points=[start.point];this.steps=[];let length=0;
  for(const edge of edges){if(edge.len<.01)continue;this.steps.push({a:edge.a,b:edge.b,at:length,length:edge.len,heading:heading(edge.a,edge.b),name:edge.road.name});length+=edge.len;this.points.push(edge.b);}
  this.length=length;this.progress=0;this.state='navigating';this.lastUpdate=-Infinity;return true;
 }
 update(p,now,paused=false){
  if(now-this.lastUpdate<100)return this.snapshot;this.lastUpdate=now;
  if(!this.destination){this.clear();return this.snapshot;}
  if(this.points.length===1&&distance([p.x,-p.z],this.destination.point)<10){
   this.state='arrived';this.snapshot={state:paused?'paused':'arrived',maneuver:'arrive',distance_m:0,remaining_m:0,destination:this.destination.label,points:[],position:[500,500]};return this.snapshot;
  }
  let nearest;
  for(let i=0;i<this.steps.length;i++){
   const step=this.steps[i],q=project([p.x,-p.z],step.a,step.b);
   const along=step.at+q.t*step.length;
   const score=q.distance+Math.max(0,this.progress-along-35)*.1;
   if(!nearest||score<nearest.score)nearest={...q,score,along,index:i};
  }
  if((!nearest||nearest.distance>30)&&!paused&&now-this.lastReroute>3000){
   this.lastReroute=now;this.route(p,this.destination.point,this.destination.label);
   this.state='off_route';nearest=null;
  }
  let remaining=this.length||0,maneuver='straight',turnDistance=remaining;
  if(nearest){
   this.progress=nearest.along;remaining=Math.max(0,this.length-this.progress);turnDistance=remaining;
   this.state=nearest.distance>30?'off_route':remaining<10?'arrived':'navigating';
   for(let i=nearest.index+1;i<this.steps.length;i++){
    const angle=wrap(this.steps[i].heading-this.steps[i-1].heading);
    if(Math.abs(angle)<.55)continue;
    maneuver=Math.abs(angle)>2.5?'uturn':angle>0?'right':'left';turnDistance=Math.max(0,this.steps[i].at-this.progress);break;
   }
   if(turnDistance===remaining)maneuver='arrive';
  }
  const points=this.points.length?this.points:[];
  const xs=points.map(v=>v[0]),ys=points.map(v=>v[1]);
  const minX=Math.min(...xs),minY=Math.min(...ys),span=Math.max(Math.max(...xs)-minX,Math.max(...ys)-minY,50);
  const norm=v=>[Math.round(Math.max(0,Math.min(1000,50+(v[0]-minX)/span*900))),Math.round(Math.max(0,Math.min(1000,950-(v[1]-minY)/span*900)))];
  const compact=points.length<=32?points:Array.from({length:32},(_,i)=>points[Math.round(i*(points.length-1)/31)]);
  this.snapshot={state:paused?'paused':this.state,maneuver:paused?'none':maneuver,distance_m:Math.round(turnDistance),remaining_m:Math.round(remaining),destination:this.destination.label,points:compact.map(norm),position:points.length?norm([p.x,-p.z]):[500,500]};
  return this.snapshot;
 }
}
