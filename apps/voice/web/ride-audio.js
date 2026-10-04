import {helmetAudio} from './helmet-audio.js';
// Deterministic cues from local route state. Never ask an LLM to invent a turn.
export function turnText(turn) {
  const distance=turn.distance_m;
  const prefix=distance<=35?'Coming up: ':`In about ${Math.max(10,Math.round(distance/10)*10)} meters, `;
  return prefix+turn.instruction;
}

export class CuePlanner {
  constructor(){this.route=null;this.state=null;this.turn=null;this.band=Infinity;this.repeat=0;this.hazards=new Set();}
  reset(){this.route=null;this.state=null;this.turn=null;this.band=Infinity;this.hazards.clear();}
  update(data){
    const cues=[];
    const changed=data.route_generation!==this.route;
    if(changed){this.turn=null;this.band=Infinity;this.hazards.clear();}
    if(this.state!==data.state&&['location_lost','off_route','paused','arrived'].includes(data.state)){
      const text={location_lost:'Location lost. Turn guidance is suspended.',off_route:'You appear off route. Ask me to reroute.',paused:'Guidance paused.',arrived:'You have arrived near your destination.'}[data.state];
      cues.push({key:`state:${data.state}`,text,priority:3,kind:'state'});
    }
    if(data.state==='navigating'&&data.fix?.guidance_usable&&data.next_turn){
      const turn=data.next_turn,band=turn.distance_m<=35?0:turn.distance_m<=100?1:turn.distance_m<=500?2:3;
      const repeat=data.repeat_serial!==this.repeat;
      if(changed||turn.id!==this.turn||band<this.band||repeat||this.state!=='navigating'){
        const intro=changed?(data.route_reason==='rerouted'?'Route updated from your current position. ':'Guidance started. '):'';
        cues.push({key:`turn:${data.route_generation}:${turn.id}:${band}:${data.repeat_serial}`,text:intro+turnText(turn),priority:band<=1?3:1,kind:'turn',turnId:turn.id,route:data.route_generation});
        this.turn=turn.id;this.band=band;
      }
      for(const report of data.hazards?.reports||[]){
        if(report.ahead_m==null||report.expires_at*1000<=Date.now()||this.hazards.has(report.id))continue;
        const lane=report.lane==='unknown'?'':report.lane==='shoulder'?' Reported on the shoulder.':` Reported in the ${report.lane} lane.`;
        cues.push({key:`hazard:${report.id}`,text:`${report.kind.replaceAll('_',' ')} reported near your route, about ${Math.round(report.ahead_m/50)*50} meters ahead.${lane}`,priority:2,kind:'hazard',reportId:report.id});
        this.hazards.add(report.id);
      }
    }
    this.route=data.route_generation;this.repeat=data.repeat_serial;this.state=data.state;
    return cues;
  }
}

export class RideAudio {
  constructor({onStatus,now=()=>Date.now()}){
    this.planner=new CuePlanner();this.onStatus=onStatus;this.now=now;
    this.enabled=false;this.pending=[];this.active=null;this.generation=0;this.lastUpdate=0;this.volume=1;this.watchdog=null;
    this.timer=setInterval(()=>{if(this.enabled&&this.now()-this.lastUpdate>4000)this.disconnect();},1000);
  }
  async enable(){
    try{await helmetAudio.configure();}catch{this.onStatus('Audio routing unavailable');return;}
    if(!('speechSynthesis' in window))throw new Error('Spoken guidance is unavailable in this browser.');
    this.enabled=true;this.planner.reset();this.onStatus(helmetAudio.enabled?'Spoken guidance on · XREAL via Pi':'Spoken guidance on · Mac system voice');
    if(this.data)this.update(this.data);
  }
  disable(){this.enabled=false;this.cancel();this.onStatus('Spoken guidance off');}
  cancel(){
    void helmetAudio.cancel('navigation').catch(()=>{});
    this.generation++;clearTimeout(this.watchdog);this.pending=[];this.active=null;
    window.speechSynthesis?.cancel();window.dispatchEvent(new CustomEvent('helmetd-cue-audio',{detail:{active:false}}));
  }
  valid(cue){
    if(cue.kind==='test')return true;
    const d=this.data;
    if(!d||this.now()-this.lastUpdate>4000)return false;
    if(cue.kind==='state')return cue.key===`state:${d.state}`;
    if(d.state!=='navigating'||!d.fix?.guidance_usable||!d.next_turn)return false;
    if(cue.kind==='turn')return d.route_generation===cue.route&&d.next_turn.id===cue.turnId;
    return d.hazards?.reports.some(r=>r.id===cue.reportId&&r.ahead_m!=null&&r.expires_at*1000>this.now());
  }
  update(data){
    this.data=data;this.lastUpdate=this.now();
    if(!this.enabled)return;
    if(this.active&&!this.valid(this.active)){
      const queued=this.pending.filter(cue=>this.valid(cue));this.cancel();this.pending=queued;
    }
    this.pending=this.pending.filter(cue=>this.valid(cue));
    const cues=this.planner.update(data);
    for(const cue of cues){
      if(cue.kind==='turn')this.pending=this.pending.filter(p=>p.kind!=='turn');
      if(this.active&&(cue.priority>this.active.priority||(cue.kind==='turn'&&this.active.kind==='turn'))){
        const deferred=this.active.kind==='hazard'?[this.active]:[];
        const queued=this.pending;this.cancel();this.pending=[...deferred,...queued];
      }
      this.pending.push(cue);
    }
    this.pending.sort((a,b)=>b.priority-a.priority);this.play();
  }
  play(){
    if(this.active||!this.enabled)return;
    while(this.pending.length&&!this.valid(this.pending[0]))this.pending.shift();
    const cue=this.pending.shift();if(!cue)return;
    this.active=cue;const generation=++this.generation;
    if(helmetAudio.enabled){
      window.dispatchEvent(new CustomEvent('helmetd-cue-audio',{detail:{active:true,text:cue.text}}));
      this.onStatus(cue.text);
      helmetAudio.cancel('navigation').then(()=>generation===this.generation&&this.enabled?helmetAudio.speak(cue.text,this.volume):undefined).then(result=>{if(generation===this.generation)this.onStatus(result?.status==='sent'?`Sent to glasses: ${cue.text}`:'Detection alert took priority · turn remains visible');})
        .catch(()=>{if(generation===this.generation)this.onStatus('Helmet audio unavailable · visual guidance remains');})
        .finally(()=>{if(generation!==this.generation)return;this.active=null;window.dispatchEvent(new CustomEvent('helmetd-cue-audio',{detail:{active:false}}));this.play();});
      return;
    }
    const utterance=new SpeechSynthesisUtterance(cue.text);
    utterance.lang='en-US';utterance.rate=1.04;utterance.volume=this.volume;
    const local=window.speechSynthesis.getVoices().find(v=>v.localService&&v.lang==='en-US');
    if(local)utterance.voice=local;
    const finish=()=>{if(generation!==this.generation)return;clearTimeout(this.watchdog);this.active=null;window.dispatchEvent(new CustomEvent('helmetd-cue-audio',{detail:{active:false}}));this.play();};
    utterance.onend=()=>{if(generation!==this.generation)return;this.onStatus(`Last spoken: ${cue.text}`);finish();};
    utterance.onerror=()=>{if(generation!==this.generation)return;this.onStatus('Speech unavailable · visual guidance remains');finish();};
    window.dispatchEvent(new CustomEvent('helmetd-cue-audio',{detail:{active:true,text:cue.text}}));
    this.onStatus(cue.text);window.speechSynthesis.speak(utterance);
    this.watchdog=setTimeout(()=>{if(generation!==this.generation)return;this.cancel();this.onStatus('Speech did not finish · visual guidance remains');},30000);
  }
  async test(){
    await this.enable();this.pending.push({key:'test',kind:'test',priority:1,text:'Spoken turns and approaching hazard reports are enabled.'});this.play();
  }
  disconnect(){this.cancel();this.data=null;this.onStatus('Navigation disconnected · spoken cues suspended');}
  destroy(){clearInterval(this.timer);this.disable();}
}
