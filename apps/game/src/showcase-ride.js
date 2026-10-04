// A bounded guided ride using actual scene actors and the normal detection pipeline.
export class ShowcaseRide {
 start(world,p){
  const s=world.segments.filter(s=>s.len>240&&!s.road.bridge).sort((a,b)=>b.len-a.len)[0];
  if(!s)return false;
  this.s=s;this.time=0;this.distance=0;this.active=true;this.saved=[];this.nearActor=null;return true;
 }
 stop(){this.active=false;for(const {actor,position} of this.saved)actor.obj.position.copy(position);this.saved=[];}
 update(dt,p,cars,people,hazards){
  if(!this.active)return;
  this.time+=dt;if(this.time>=36){this.stop();hazards.showcase=[];hazards.sync();return;}
  const s=this.s,heading=Math.atan2(s.b[0]-s.a[0],s.b[1]-s.a[1]);
  const speed=this.time>=30?Math.max(1,5-(this.time-30)*8):5;this.distance+=speed*dt;const t=Math.min(.9,.1+this.distance/s.len);
  Object.assign(p,{x:s.a[0]+(s.b[0]-s.a[0])*t,z:-s.a[1]-(s.b[1]-s.a[1])*t,y:s.a[2]+(s.b[2]-s.a[2])*t,heading,speed,crashed:false,gear:2,rpm:3500});
  const phase=Math.floor(this.time/6);
  const actor=phase===1?people[0]:phase===0||phase===5?cars[0]:null;
  if(actor){if(!this.saved.some(x=>x.actor===actor))this.saved.push({actor,position:actor.obj.position.clone()});const ahead=phase===5?8:15;if(phase!==5||!this.nearActor){actor.obj.position.set(p.x+Math.sin(heading)*ahead,p.y,p.z-Math.cos(heading)*ahead);if(phase===5)this.nearActor=actor.obj.position.clone();}else actor.obj.position.copy(this.nearActor);actor.obj.visible=true;}
  if(phase===5)p.speed=Math.max(1,5-(this.time-30)*8);
  const kind=phase===2?'roadworks':phase===3?'pothole':phase===4?'debris':null;
  hazards.showcase=kind?[{id:'showcase-'+kind,kind,x:p.x+Math.sin(heading)*18,z:p.z-Math.cos(heading)*18,y:p.y,source:'showcase'}]:[];
  hazards.sync();
 }
}
