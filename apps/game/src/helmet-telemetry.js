import {RideSafety} from './ride-safety.js';
// World axes: forward=(sin(heading), -cos(heading)); right=(cos, sin).
export function vehicleWarnings(p, cars) {
 const zones=new Set();
 for(const car of cars){
  const q=car.obj?.position;if(!q||car.obj.visible===false||Math.abs(q.y-p.y)>2.5)continue;
  const zone=name=>car.kind==='person'?'person_'+name:name;
  const dx=q.x-p.x,dz=q.z-p.z;
  const forward=dx*Math.sin(p.heading)-dz*Math.cos(p.heading);
  const right=dx*Math.cos(p.heading)+dz*Math.sin(p.heading);
  if(forward>-14&&forward<10&&Math.abs(right)>1.5&&Math.abs(right)<8)
   zones.add(zone(right<0?'left':'right'));
  if(Math.abs(right)<3&&forward>0&&forward<Math.max(30,Math.abs(p.speed)*2))zones.add(zone('front'));
  if(Math.abs(right)<3&&forward<0&&forward>-35)zones.add(zone('rear'));
 }
 return [...zones].sort();
}
export class HelmetTelemetry {
 constructor({fetcher=(...args)=>fetch(...args),session=crypto.randomUUID()}={}){
  this.fetcher=fetcher;this.session=session;this.sequence=0;this.signal='off';
  this.safety=new RideSafety();this.safetyEvents=[];this.held=new Map();this.last= -Infinity;this.busy=false;this.token=null;this.connected=false;
 }
 toggle(side){this.signal=this.signal===side?'off':side;}
 reset(){this.safety.reset();this.held.clear();this.signal='off';this.session=crypto.randomUUID();this.sequence=0;}
 async update(now,p,cars,paused,navigation=null,pothole=false,hazards=[]){
  if(this.busy||now-this.last<100)return;
  this.last=now;this.busy=true;
  if(paused){this.held.clear();this.safety.reset();this.safetyEvents=[];}
  else for(const zone of vehicleWarnings(p,cars))this.held.set(zone,now+1800);
  if(!paused){this.safetyEvents=this.safety.update(now,p,cars);for(const event of this.safetyEvents)this.held.set(event.zone,now+1800);}
  if(!paused)for(const kind of hazards)this.held.set(kind,now+1800);
  if(!paused&&pothole)this.held.set('pothole',now+1000);
  for(const [zone,until] of this.held)if(now>=until)this.held.delete(zone);
  const packet={session:this.session,sequence:++this.sequence,paused,
   speed_mps:Math.abs(p.speed),gear:p.reversing?-1:p.gear,rpm:p.rpm,
   signal:paused?'off':this.signal,crashed:!!p.crashed,
   warnings:[...this.held.keys()],navigation};
  try{
   if(!this.token){const r=await this.fetcher('/api/game/session',{signal:AbortSignal.timeout(1200)});if(!r.ok)throw Error();this.token=(await r.json()).token;}
   const r=await this.fetcher('/api/game/telemetry',{method:'POST',headers:{'Content-Type':'application/json','X-Helmetd':this.token},body:JSON.stringify(packet),signal:AbortSignal.timeout(1200)});
   for(const event of this.safetyEvents.filter(e=>['near_miss','impact'].includes(e.kind))){
    await this.fetcher('/api/game/reports',{method:'POST',headers:{'Content-Type':'application/json','X-Helmetd':this.token},body:JSON.stringify({x:event.x,z:event.z,kind:event.kind,reporter:this.session}),signal:AbortSignal.timeout(1200)});
   }
   if(r.status===403)this.token=null;
   if(!r.ok)throw Error('HTTP '+r.status);this.connected=(await r.json()).status==='ok';
  }catch(error){this.connected=false;this.error=error.message;}finally{this.busy=false;}
 }
}
