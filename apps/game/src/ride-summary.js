export class RideSummary {
 constructor(){this.distance=0;this.hazards=new Set();this.reports=0;this.nearMisses=[];this.previous=null;this.events=new WeakSet();}
 update(p,active,hazards,events){
  if(active&&this.previous){const d=Math.hypot(p.x-this.previous.x,p.z-this.previous.z);if(d<10)this.distance+=d;}
  this.previous=active?{x:p.x,z:p.z}:null;
  if(!active)return;
  for(const h of hazards)this.hazards.add(h.id);
  for(const e of events)if(e.kind==='near_miss'&&!this.events.has(e)){this.events.add(e);this.nearMisses.push({x:e.x,z:e.z});}
 }
}
export function summaryText(s){return `${(s.distance/1609.34).toFixed(2)} miles · ${s.hazards.size} hazards encountered · ${s.reports} reports contributed\nNear misses: ${s.nearMisses.length}\n${s.nearMisses.map((p,i)=>`${i+1}. ${Math.round(p.x)}, ${Math.round(-p.z)} m`).join('\n')}`;}
