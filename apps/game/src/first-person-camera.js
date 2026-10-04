// Follow translation directly; filter heading and road height independently.
export class FirstPersonCamera {
 reset(){this.heading=undefined;}
 update(p,dt,mode=2){
  if(this.heading===undefined||this.mode!==mode||Math.hypot(p.x-this.x,p.z-this.z)>10){this.heading=p.heading;this.height=p.y;}
  this.mode=mode;this.x=p.x;this.z=p.z;
  const delta=Math.atan2(Math.sin(p.heading-this.heading),Math.cos(p.heading-this.heading));
  this.heading+=delta*(1-Math.exp(-12*dt));
  this.height+=(p.y-this.height)*(1-Math.exp(-10*dt));
  const forward=mode===2?-.18:.12,eye=mode===2?1.46:1.22;
  return {x:p.x+Math.sin(p.heading)*forward,y:this.height+eye,z:p.z-Math.cos(p.heading)*forward,heading:this.heading,pitch:mode===2?-.10:-.22,fov:68};
 }
}
