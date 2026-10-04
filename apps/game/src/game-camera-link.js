import * as T from 'three';
import {positionHudCamera} from './hud-cameras.js';
// Bounded, sequential uploads: one front or selected surround frame at a time.
export class GameCameraLink {
 constructor(renderer,scene,telemetry){
  Object.assign(this,{renderer,scene,telemetry,busy:false,next:0,cursor:0});
  this.target=new T.WebGLRenderTarget(640,360,{type:T.UnsignedByteType,depthBuffer:true});
  this.target.texture.colorSpace=T.SRGBColorSpace;
  this.camera=new T.PerspectiveCamera(82,16/9,.15,300);
  this.rgba=new Uint8Array(640*360*4);this.bgra=new Uint8Array(this.rgba.length);
 }
 async update(now,pose,active){
  if(!active||!this.telemetry.connected||!this.telemetry.token||this.busy||now<this.next)return;
  this.next=now+80;this.busy=true;
  const selected=pose.reversing?'rear':this.telemetry.signal;
  const views=['front',selected==='off'?'front':selected,'left','right','rear'];
  const view=views[this.cursor++%views.length];
  const yaw={front:0,left:-Math.PI/2,right:Math.PI/2,rear:Math.PI}[view];
  const r=this.renderer,old=r.getRenderTarget(),auto=r.autoClear,scissor=r.getScissorTest();
  const viewport=r.getViewport(new T.Vector4()),rect=r.getScissor(new T.Vector4());
  try{
   positionHudCamera(this.camera,pose,yaw);r.setRenderTarget(this.target);r.setScissorTest(false);r.autoClear=true;
   r.render(this.scene,this.camera);r.readRenderTargetPixels(this.target,0,0,640,360,this.rgba);
   for(let y=0;y<360;y++)for(let x=0;x<640;x++){const dst=(y*640+x)*4,src=((359-y)*640+x)*4;this.bgra[dst]=this.rgba[src+2];this.bgra[dst+1]=this.rgba[src+1];this.bgra[dst+2]=this.rgba[src];this.bgra[dst+3]=255;}
  }catch{this.busy=false;return;}finally{r.setRenderTarget(old);r.setViewport(viewport);r.setScissor(rect);r.setScissorTest(scissor);r.autoClear=auto;}
  try{await fetch(`/api/game/camera/${view}`,{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Helmetd':this.telemetry.token,'X-Game-Session':this.telemetry.session},body:this.bgra,signal:AbortSignal.timeout(1000)});}catch{}finally{this.busy=false;}
 }
}
