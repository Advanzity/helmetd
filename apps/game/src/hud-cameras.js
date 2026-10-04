import * as T from 'three';

export const cameraViews=[
 {id:'front',label:'FRONT',yaw:0},
 {id:'left',label:'LEFT',yaw:-Math.PI/2},
 {id:'right',label:'RIGHT',yaw:Math.PI/2},
 {id:'back',label:'BACK',yaw:Math.PI},
];

export function positionHudCamera(camera,pose,yaw){
 const heading=pose.heading+yaw;
 camera.position.set(pose.x,pose.y+1.55,pose.z);
 camera.lookAt(pose.x+Math.sin(heading)*10,pose.y+1.35,pose.z-Math.cos(heading)*10);
}

// One small scene render at a time, with no catch-up bursts after a slow frame.
export class CameraFeedSchedule{
 constructor(){this.cursor=0;this.nextTime=0;this.frameTime=1/60}
 next(now,dt,quality){
  if(Number.isFinite(dt)&&dt>0)this.frameTime=this.frameTime*.85+Math.min(dt,.25)*.15;
  if(now<this.nextTime)return null;
  const fps=quality==='high'?8:5;
  this.nextTime=now+Math.max(1000/(fps*4),this.frameTime*2000);
  const index=this.cursor;this.cursor=(this.cursor+1)%4;return index;
 }
}

export class HudCameras{
 constructor(renderer,scene,hud){
  this.renderer=renderer;this.scene=scene;this.schedule=new CameraFeedSchedule();
  this.root=document.createElement('section');this.root.className='camera-rack';this.root.setAttribute('aria-label','Motorcycle surround cameras');
  this.root.innerHTML=cameraViews.map(view=>`<figure class="camera-feed" data-view="${view.id}"><figcaption><span>${view.label}</span><i aria-hidden="true"></i></figcaption><div class="camera-screen" role="img" aria-label="Live ${view.id} camera view"></div></figure>`).join('');
  hud.append(this.root);
  this.overlay=new T.Scene();this.overlayCamera=new T.OrthographicCamera(0,1,1,0,.1,10);this.overlayCamera.position.z=1;
  this.plane=new T.PlaneGeometry(1,1);this.viewport=new T.Vector4();this.scissor=new T.Vector4();
  this.feeds=cameraViews.map((view,index)=>{
   // Linear HDR color is tone-mapped once when the HUD quad reaches the screen.
   const target=new T.WebGLRenderTarget(192,108,{type:T.HalfFloatType,minFilter:T.LinearFilter,magFilter:T.LinearFilter,generateMipmaps:false,stencilBuffer:false});
   const material=new T.MeshBasicMaterial({map:target.texture,depthTest:false,depthWrite:false});
   const quad=new T.Mesh(this.plane,material);quad.visible=false;quad.frustumCulled=false;this.overlay.add(quad);
   const element=this.root.children[index];
   return {...view,target,quad,element,screen:element.querySelector('.camera-screen'),camera:new T.PerspectiveCamera(82,16/9,.15,180)};
  });
  this.quality='balanced';this.layoutDirty=true;this.wasVisible=false;
  this.onResize=()=>{this.layoutDirty=true};
  window.addEventListener('resize',this.onResize);
  this.resizeObserver=new ResizeObserver(()=>{this.layoutDirty=true});this.resizeObserver.observe(this.root);
 }

 async prepare(pose){
  // Compile the offscreen shader variants before riding, rather than hitching
  // the first live HUD update. compileAsync starts compilation synchronously.
  const renderer=this.renderer,target=renderer.getRenderTarget();positionHudCamera(this.feeds[0].camera,pose,0);
  let ready;
  try{renderer.setRenderTarget(this.feeds[0].target);ready=renderer.compileAsync(this.scene,this.feeds[0].camera)}
  finally{renderer.setRenderTarget(target)}
  await ready;
 }

 layout(){
  const width=innerWidth,height=innerHeight;
  Object.assign(this.overlayCamera,{right:width,top:height});this.overlayCamera.updateProjectionMatrix();
  for(const feed of this.feeds){
   const rect=feed.screen.getBoundingClientRect();
   feed.quad.position.set(rect.left+rect.width/2,height-rect.top-rect.height/2,0);feed.quad.scale.set(rect.width,rect.height,1);
  }
  this.layoutDirty=false;
 }

 render(now,dt,pose,{quality='balanced',view='all',visible=true,live=true}={}){
  this.root.classList.toggle('hidden',!visible);this.root.classList.toggle('camera-frozen',!live);
  if(!visible){this.wasVisible=false;return}
  if(this.view!==view){this.view=view;this.layoutDirty=true;this.schedule.nextTime=0;this.root.classList.toggle('single-camera',view!=='all');for(const feed of this.feeds){const selected=view==='all'||view===feed.id;feed.element.style.display=selected?'':'none';feed.quad.visible=selected&&feed.element.classList.contains('camera-ready');}}
  if(!this.wasVisible){this.layoutDirty=true;this.wasVisible=true}
  if(this.quality!==quality&&live){
   this.quality=quality;this.schedule.nextTime=0;
  }
  if(this.layoutDirty)this.layout();
  const renderer=this.renderer,target=renderer.getRenderTarget(),autoClear=renderer.autoClear,scissorTest=renderer.getScissorTest();
  const shadowAutoUpdate=renderer.shadowMap.autoUpdate,shadowNeedsUpdate=renderer.shadowMap.needsUpdate,matrixAutoUpdate=this.scene.matrixWorldAutoUpdate;
  renderer.getViewport(this.viewport);renderer.getScissor(this.scissor);
  try{
   // The main view already updated world matrices and shadows this frame.
   renderer.shadowMap.autoUpdate=false;renderer.shadowMap.needsUpdate=false;this.scene.matrixWorldAutoUpdate=false;
   const scheduled=live?this.schedule.next(now,dt,quality):null;
   const index=scheduled===null?null:view==='all'?scheduled:this.feeds.findIndex(feed=>feed.id===view);
   if(index!==null&&index>=0){
    const feed=this.feeds[index];positionHudCamera(feed.camera,pose,feed.yaw);
    // Resize a feed only when refreshing it; the other three keep their images.
    const width=quality==='high'?384:256;if(feed.target.width!==width)feed.target.setSize(width,width*9/16);
    const samples=Math.min(quality==='high'?4:2,renderer.capabilities.maxSamples);
    if(feed.target.samples!==samples){feed.target.dispose();feed.target.samples=samples;}
    renderer.setRenderTarget(feed.target);renderer.setScissorTest(false);renderer.autoClear=true;
    renderer.render(this.scene,feed.camera);feed.quad.visible=true;feed.element.classList.add('camera-ready');
   }
   renderer.setRenderTarget(null);renderer.setViewport(0,0,innerWidth,innerHeight);renderer.setScissorTest(false);renderer.autoClear=false;
   renderer.render(this.overlay,this.overlayCamera);
  }finally{
   this.scene.matrixWorldAutoUpdate=matrixAutoUpdate;renderer.shadowMap.autoUpdate=shadowAutoUpdate;renderer.shadowMap.needsUpdate=shadowNeedsUpdate;
   renderer.setRenderTarget(target);renderer.setViewport(this.viewport);renderer.setScissor(this.scissor);renderer.setScissorTest(scissorTest);renderer.autoClear=autoClear;
  }
 }

 dispose(){
  window.removeEventListener('resize',this.onResize);this.resizeObserver.disconnect();this.root.remove();this.plane.dispose();
  for(const feed of this.feeds){feed.target.dispose();feed.quad.material.dispose()}
 }
}
