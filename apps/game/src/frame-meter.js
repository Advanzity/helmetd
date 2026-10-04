// Measures completed main-view frames, independent of physics substeps.
export class FrameMeter {
 constructor(){this.reset();}
 reset(){this.times=[];}
 sample(now){
  if(!Number.isFinite(now))return;
  if(this.times.length&&now<=this.times.at(-1))return;
  if(this.times.length&&now-this.times.at(-1)>2000)this.reset();
  this.times.push(now);
  while(this.times.length>2&&this.times[1]<now-1000)this.times.shift();
 }
 snapshot(){
  if(this.times.length<2)return null;
  const ms=(this.times.at(-1)-this.times[0])/(this.times.length-1);
  return {fps:1000/ms,ms};
 }
}
