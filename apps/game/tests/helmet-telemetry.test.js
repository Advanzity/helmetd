import {test} from 'node:test';
import assert from 'node:assert/strict';
import {vehicleWarnings,HelmetTelemetry} from '../src/helmet-telemetry.js';
const p={x:0,y:0,z:0,heading:0,speed:10,gear:2,rpm:4000,crashed:false};
const car=(x,z,y=0)=>({obj:{position:{x,y,z}}});
test('traffic zones respect heading, distance, and elevated roads',()=>{
 assert.deepEqual(vehicleWarnings(p,[car(-3,0),car(3,0),car(0,10),car(0,-10),car(1,-3,8)]),['front','left','rear','right']);
 assert.deepEqual(vehicleWarnings({...p,heading:Math.PI/2},[car(0,-3)]),['left']);
 assert.deepEqual(vehicleWarnings(p,[car(100,100),car(0,-10,8)]),[]);
});
test('bounded bridge sends paused clear state and reports HUD availability',async()=>{
 const sent=[];const bridge=new HelmetTelemetry({session:'test',fetcher:async(url,options)=>{
  if(!options?.body)return {ok:true,json:async()=>({token:'guard'})};
  sent.push(JSON.parse(options.body));return {ok:true,json:async()=>({status:'ok'})};
 }});
 bridge.toggle('left');await bridge.update(0,p,[car(-3,0)],false);
 await bridge.update(50,p,[],false);assert.equal(sent.length,1);
 assert.equal(sent[0].signal,'left');assert.deepEqual(sent[0].warnings,['left']);
 await bridge.update(100,p,[car(-3,0)],true);
 assert.equal(sent[1].signal,'off');assert.deepEqual(sent[1].warnings,[]);
 assert.equal(bridge.connected,true);
});
