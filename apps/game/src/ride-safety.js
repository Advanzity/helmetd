// Game-world kinematics, not camera-derived collision predictions. Seconds/metres.
const angle = a => Math.atan2(Math.sin(a), Math.cos(a));
export class RideSafety {
 constructor(){this.reset();}
 reset(){this.tracks=new Map();this.previous=null;this.cooldown=-Infinity;}
 update(now,p,cars){
  const prior=this.previous,dt=prior?(now-prior.now)/1000:0;
  this.previous={now,speed:p.speed,heading:p.heading,crashed:!!p.crashed};
  if(dt<=0||dt>.5){this.tracks.clear();return [];}
  const rider={x:Math.sin(p.heading)*p.speed,z:-Math.cos(p.heading)*p.speed};
  const braking=(prior.speed-p.speed)/dt>5,swerve=Math.abs(angle(p.heading-prior.heading))/dt>.65;
  const events=[];if(p.crashed&&!prior.crashed)events.push({kind:'impact',zone:'front',x:p.x,z:p.z});const seen=new Set();
  for(const car of cars){
   const q=car.obj?.position;if(!q||car.obj.visible===false||Math.abs(q.y-p.y)>2.5)continue;
   seen.add(car);const old=this.tracks.get(car);
   const track={x:q.x,z:q.z,now,changes:old?.changes||[],lateral:0};this.tracks.set(car,track);
   if(!old)continue;
   const vx=(q.x-old.x)/dt,vz=(q.z-old.z)/dt;if(Math.hypot(vx,vz)>65)continue;
   const dx=q.x-p.x,dz=q.z-p.z,distance=Math.hypot(dx,dz);if(distance>65)continue;
   const rx=vx-rider.x,rz=vz-rider.z,rv2=rx*rx+rz*rz;
   const closing=distance?-(dx*rx+dz*rz)/distance:0;
   const t=rv2>.01?-(dx*rx+dz*rz)/rv2:Infinity;
   const miss=Math.hypot(dx+rx*t,dz+rz*t);
   const side=dx*Math.cos(p.heading)+dz*Math.sin(p.heading);
   const forward=dx*Math.sin(p.heading)-dz*Math.cos(p.heading);
   const zone=Math.abs(side)>3?(side<0?'left':'right'):(forward<0?'rear':'front');
   track.lateral=vx*Math.cos(p.heading)+vz*Math.sin(p.heading);
   track.changes=track.changes.filter(t=>now-t<4000);
   if(Math.abs(track.lateral)>.7&&Math.abs(old.lateral)>.7&&track.lateral*old.lateral<0)track.changes.push(now);
   const conflict=t>0&&t<3&&miss<2.5&&closing>2;
   if(conflict)events.push({kind:'path_conflict',zone,time_to_closest:t,distance});
   if(distance<25&&((side*track.lateral<0&&Math.abs(track.lateral)>1.2)||track.changes.length>=3))events.push({kind:'unstable_vehicle',zone,distance});
   if(Math.hypot(vx,vz)<.5&&forward>0&&forward<35&&Math.abs(side)<2.5&&p.speed>3)events.push({kind:'stopped_vehicle',zone,distance});
   if(!p.crashed&&distance<15&&(conflict||closing>8)&&(braking||swerve)&&now-this.cooldown>10000){events.push({kind:'near_miss',zone,x:p.x,z:p.z,distance});this.cooldown=now;}
  }
  for(const key of this.tracks.keys())if(!seen.has(key))this.tracks.delete(key);
  return events;
 }
}
