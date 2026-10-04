export const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
export const ratios=[0,2.667,2,1.6,1.3,1.13,1.04];
const primary=1.925,final=2.687,radius=.305,mass=268;
export function engineTorque(rpm){const points=[[1200,25],[3000,48],[5000,61],[6800,68],[8500,63],[10500,42],[11200,0]];for(let i=1;i<points.length;i++){if(rpm<points[i][0]){const [x,y]=points[i-1],[xx,yy]=points[i];return y+(yy-y)*clamp((rpm-x)/(xx-x),0,1)}}return 0}
export class MotorcyclePhysics{
 constructor(){this.reset({x:0,z:0,y:0,heading:0})}
 reset(spawn){Object.assign(this,{...spawn,speed:0,reversing:false,kickPhase:0,rpm:1300,gear:1,lean:0,pitch:0,slip:0,throttle:0,brake:0,steer:0,shiftCut:0,crashed:false,crashTime:0,distance:0,acceleration:0,suspension:0,suspensionVelocity:0,wheelie:0,lastShift:0,clutch:0,surface:'asphalt'})}
 shift(direction){const next=clamp(this.gear+direction,0,6);if(next===this.gear||this.shiftCut>0)return false;const old=this.gear;this.gear=next;this.shiftCut=.09;this.lastShift=direction;if(next&&old)this.rpm=clamp(this.rpm*ratios[next]/ratios[old],1300,11200);return true}
 crash(){if(this.crashed)return;this.crashed=true;this.crashTime=0;this.throttle=0}
 step(dt,input,ground){
  if(this.crashed){this.crashTime+=dt;this.speed*=Math.exp(-dt*1.8);this.x+=Math.sin(this.heading)*this.speed*dt;this.z-=Math.cos(this.heading)*this.speed*dt;this.lean+=(1.45-this.lean)*Math.min(1,dt*6);return}
  // Hold B to paddle backward only from a near stop. Braking never reverses.
  const push=!!input.reverse && !input.throttle && !input.brake && this.speed<.2;
  if(push||this.speed<0){
   this.reversing=true;this.throttle=0;this.clutch=1;this.brake=input.brake;
   this.steer+=(input.steer-this.steer)*Math.min(1,dt*6);
   const target=push?-1.15:0, rate=push?1.5:3.5;
   const before=this.speed;
   this.speed+=clamp(target-this.speed,-rate*dt,rate*dt);
   if(Math.abs(this.speed)<.01&&!push){this.speed=0;this.reversing=false;}
   this.acceleration=(this.speed-before)/dt;
   if(push)this.kickPhase+=dt*5.5;
   this.heading+=this.steer*this.speed*.24*dt;
   this.x+=Math.sin(this.heading)*this.speed*dt;this.z-=Math.cos(this.heading)*this.speed*dt;
   this.distance+=Math.abs(this.speed)*dt;
   this.lean*=Math.exp(-dt*8);this.pitch*=Math.exp(-dt*8);this.wheelie=0;this.slip=0;
   this.rpm+=(1300-this.rpm)*Math.min(1,dt*8);
   this.y+=(ground.height-this.y)*Math.min(1,dt*12);
   return;
  }
  this.reversing=false;
  this.shiftCut=Math.max(0,this.shiftCut-dt);this.throttle+=(input.throttle-this.throttle)*Math.min(1,dt*6);this.brake=input.brake;this.clutch=input.clutch||0;this.steer+=(input.steer-this.steer)*Math.min(1,dt*4);
  const mu=ground.surface==='grass'?.43:ground.surface==='gravel'?.6:1.08;this.surface=ground.surface;
  const ratio=ratios[this.gear]*primary*final;
  const wheelRpm=this.speed/radius*60/(2*Math.PI);const coupled=wheelRpm*ratio;
  const launchRpm=1300+this.throttle*3200;const target=this.gear&&!this.clutch?Math.max(launchRpm,coupled):1300+this.throttle*9600;
  this.rpm+=(target-this.rpm)*Math.min(1,dt*14);this.rpm=clamp(this.rpm,1200,11200);
  const limiter=this.rpm>10800?.05:1;const clutchTransfer=(1-this.clutch)*clamp((this.rpm-1200)/1200,0,1);
  let drive=engineTorque(this.rpm)*this.throttle*ratio*.93/radius*clutchTransfer*limiter*(this.shiftCut>0?0:1);
  const rearLoad=mass*9.81*.53+mass*this.acceleration*.57/1.4;const traction=mu*Math.max(400,rearLoad);
  this.slip=clamp((drive-traction)/1800,0,1);drive=Math.min(drive,traction);
  const maxBrake=mass*9.81*mu;const brake=this.brake*maxBrake*.9;this.slip=Math.max(this.slip,input.rearBrake*this.speed/20);
  const engineBrake=this.gear&&!this.clutch?(1-this.throttle)*ratio*1.9:0;
  const drag=.5*1.225*.36*this.speed*this.speed;const roll=mass*9.81*.014*(this.speed>.01?1:0);
  const slope=ground.slope||0;this.acceleration=(drive-brake-engineBrake-drag-roll-mass*9.81*slope)/mass;
  this.speed=clamp(this.speed+this.acceleration*dt,0,90);
  // Speed-sensitive countersteer/lean response with low-speed balancing assistance.
  const targetLean=-this.steer*clamp(this.speed/12,0,1)*.72;
  this.lean+=(targetLean-this.lean)*Math.min(1,dt*(3.5+1/(this.speed+1)));
  const yaw=this.speed>3?-9.81*Math.tan(this.lean)/this.speed:this.steer*this.speed*.16;
  this.heading+=yaw*dt;this.x+=Math.sin(this.heading)*this.speed*dt;this.z-=Math.cos(this.heading)*this.speed*dt;this.distance+=this.speed*dt;
  const loadPitch=clamp(-this.acceleration*.009,-.09,.075);this.pitch+=(loadPitch-this.pitch)*Math.min(1,dt*5);
  const springTarget=clamp(-this.acceleration*.0025,-.025,.03)+Math.sin(this.distance*1.3)*.002*Math.min(this.speed/8,1);
  this.suspensionVelocity+=(springTarget-this.suspension)*90*dt-this.suspensionVelocity*15*dt;this.suspension+=this.suspensionVelocity*dt;
  this.y+=(ground.height-this.y)*Math.min(1,dt*12);this.wheelie+=(Math.max(0,this.acceleration-7)*.02-this.wheelie)*Math.min(1,dt*3);
  if(Math.abs(this.lean)>.6&&mu<.5&&this.speed>17)this.crash();
 }
}
