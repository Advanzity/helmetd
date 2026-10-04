async function localFetch(...args){const api=await import('./local-api.js');return api.localFetch(...args);}
export const helmetAudio={enabled:false,queue:[],sending:false,generation:0,
 async configure(){const r=await localFetch('/api/audio/status',{method:'POST'});if(!r.ok)throw new Error('Helmet audio configuration unavailable');this.enabled=(await r.json()).configured;return this.enabled;},
 async cancel(source='conversation'){this.generation++;this.queue=[];if(this.enabled)await localFetch('/api/audio/cancel',{method:'POST',headers:{'X-Helmetd-Audio-Source':source},signal:AbortSignal.timeout(2000)});},
 async speak(text,volume){const r=await localFetch('/api/audio/speak',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,volume}),signal:AbortSignal.timeout(45000)});if(!r.ok)throw new Error('Helmet speech failed');return r.json();},
 push(encoded,lease,volume,onError){
  if(!this.enabled)return;
  const raw=atob(encoded),bytes=Uint8Array.from(raw,c=>c.charCodeAt(0)),view=new DataView(bytes.buffer);
  for(let i=0;i+1<bytes.length;i+=2)view.setInt16(i,Math.round(view.getInt16(i,true)*volume),true);
  if(bytes.length>48000||this.queue.reduce((n,item)=>n+item.bytes.length,bytes.length)>96000){this.queue=[];onError(new Error('Helmet audio fell behind'));return;}
  this.queue.push({bytes,lease,generation:this.generation,queuedAt:performance.now()});void this.drain(onError);
 },
 async drain(onError){
  if(this.sending)return;this.sending=true;
  try{while(this.queue.length){const item=this.queue.shift();if(item.generation!==this.generation||performance.now()-item.queuedAt>500)continue;
   const r=await localFetch('/api/audio/pcm',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Helmetd-Session':item.lease},body:item.bytes,signal:AbortSignal.timeout(2000)});
   if(!r.ok)throw new Error('Helmet audio link failed');
   if((await r.json()).status==='suppressed')this.queue=[];
  }}catch(e){this.queue=[];onError(e);}finally{this.sending=false;}
 }
};
