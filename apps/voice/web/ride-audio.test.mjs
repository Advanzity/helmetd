import test from 'node:test';
import assert from 'node:assert/strict';
import {CuePlanner, RideAudio} from './ride-audio.js';
import {helmetAudio} from './helmet-audio.js';

const data=()=>({route_generation:1,route_reason:'started',repeat_serial:0,state:'navigating',fix:{guidance_usable:true},next_turn:{id:1,distance_m:550,instruction:'Turn left.'},hazards:{reports:[]}});

test('one cue per threshold, explicit repeat, and new maneuver',()=>{
  const planner=new CuePlanner(),d=data();
  assert.match(planner.update(d)[0].text,/Guidance started/);
  assert.equal(planner.update(d).length,0);
  for(const meters of [490,95,30]){
    d.next_turn.distance_m=meters;assert.equal(planner.update(d).length,1);
    assert.equal(planner.update(d).length,0);
  }
  d.next_turn.distance_m=45;assert.equal(planner.update(d).length,0);
  d.repeat_serial++;assert.equal(planner.update(d).length,1);
  d.next_turn.id=2;assert.equal(planner.update(d).length,1);
});

test('pause, stale fix, uncertain route suppress turns and reroute explains change',()=>{
  const planner=new CuePlanner(),d=data();planner.update(d);
  d.fix.guidance_usable=false;d.next_turn.distance_m=20;
  assert.equal(planner.update(d).length,0);
  d.state='location_lost';assert.match(planner.update(d)[0].text,/suspended/);
  assert.equal(planner.update(d).length,0);
  d.fix.guidance_usable=true;d.state='paused';
  assert.equal(planner.update(d)[0].kind,'state');
  d.state='navigating';d.next_turn=null;assert.equal(planner.update(d).length,0);
  d.next_turn={id:0,distance_m:180,instruction:'Turn right.'};d.route_generation++;d.route_reason='rerouted';
  assert.match(planner.update(d)[0].text,/Route updated/);
});

test('only unexpired, matched upcoming hazards warn, and reports deduplicate',()=>{
  const planner=new CuePlanner(),d=data();planner.update(d);
  d.hazards.reports=[{id:'ahead',kind:'debris',lane:'right',ahead_m:230,expires_at:Date.now()/1000+100},
    {id:'behind',kind:'pothole',lane:'unknown',ahead_m:null,expires_at:Date.now()/1000+100},
    {id:'expired',kind:'debris',lane:'left',ahead_m:200,expires_at:1}];
  const cues=planner.update(d);assert.equal(cues.length,1);
  assert.match(cues[0].text,/reported near your route/);assert.match(cues[0].text,/right lane/);
  assert.equal(planner.update(d).length,0);
});

test('active speech is cancelled when route becomes stale; disconnected cues do not play',async()=>{
  helmetAudio.configure=async()=>false;
  const spoken=[];let cancels=0;
  globalThis.window={speechSynthesis:{cancel:()=>cancels++,getVoices:()=>[],speak:u=>spoken.push(u)},dispatchEvent:()=>{}};
  globalThis.CustomEvent=class{constructor(name,detail){Object.assign(this,{name,...detail});}};
  globalThis.SpeechSynthesisUtterance=class{constructor(text){this.text=text;}};
  const audio=new RideAudio({onStatus:()=>{}}),d=data();audio.update(d);await audio.enable();
  assert.equal(spoken.length,1);
  d.state='location_lost';d.fix.guidance_usable=false;d.next_turn=null;audio.update(d);
  assert.ok(cancels>0);assert.match(spoken.at(-1).text,/suspended/);
  audio.disconnect();assert.equal(audio.active,null);audio.destroy();
});
