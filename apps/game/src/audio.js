export class BikeAudio{
 constructor(){this.ctx=null;this.muted=false;this.available=true}
 async start(){if(this.ctx){await this.ctx.resume();return}const c=this.ctx=new AudioContext();this.master=c.createGain();this.master.gain.value=.55;this.master.connect(c.destination);
 try{await c.audioWorklet.addModule('/engine-worklet.js');this.engine=new AudioWorkletNode(c,'twin-engine',{outputChannelCount:[2]});this.engine.connect(this.master)}catch(e){this.available=false;console.warn('Engine audio unavailable',e)}
 const buffer=c.createBuffer(1,c.sampleRate*.5,c.sampleRate),data=buffer.getChannelData(0);let prev=0;for(let i=0;i<data.length;i++){prev=.75*prev+.25*(Math.random()*2-1);data[i]=prev}this.buffer=buffer;
 }
 update(p,camera){if(!this.ctx)return;const t=this.ctx.currentTime;this.master.gain.setTargetAtTime(this.muted?0:.55,t,.08);this.engine?.port.postMessage({rpm:p.rpm,load:p.crashed?0:p.throttle,speed:p.speed,cut:p.crashed||p.shiftCut>0||(p.rpm>10800&&Math.sin(t*60)>0),slip:p.slip,cam:camera})}
 impact(strength=.5){if(!this.ctx||!this.buffer)return;const c=this.ctx,n=c.createBufferSource(),g=c.createGain();n.buffer=this.buffer;n.connect(g);g.connect(this.master);g.gain.setValueAtTime(strength,c.currentTime);g.gain.exponentialRampToValueAtTime(.001,c.currentTime+.28);n.start();n.stop(c.currentTime+.30)}
}
