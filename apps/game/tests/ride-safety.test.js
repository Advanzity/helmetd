import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RideSafety} from '../src/ride-safety.js';
const rider=(speed=10)=>({x:0,y:0,z:0,heading:0,speed,crashed:false});
const car=(x,z)=>({obj:{visible:true,position:{x,y:0,z}}});
test('cross traffic on an intersecting trajectory triggers a path conflict',()=>{
 const s=new RideSafety(),c=car(-11,-10);s.update(0,rider(),[c]);s.update(100,rider(),[c]);c.obj.position.x=-10;
 assert.ok(s.update(200,rider(),[c]).some(e=>e.kind==='path_conflict'));
});
test('receding vehicles and stale history do not produce conflicts',()=>{
 const s=new RideSafety(),c=car(0,-20);s.update(0,rider(),[c]);s.update(100,rider(),[c]);c.obj.position.z=-22;
 assert.equal(s.update(200,rider(),[c]).length,0);
 assert.equal(s.update(2000,rider(),[c]).length,0);
});
test('near miss requires an evasive action and has a cooldown',()=>{
 const s=new RideSafety(),c=car(0,-8);s.update(0,rider(12),[c]);s.update(100,rider(12),[c]);
 assert.ok(s.update(200,rider(10),[c]).some(e=>e.kind==='near_miss'));
 assert.ok(!s.update(300,rider(9),[c]).some(e=>e.kind==='near_miss'));
});
