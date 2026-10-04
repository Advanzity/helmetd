import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RideSummary} from '../src/ride-summary.js';
test('summary excludes teleports and paused movement and deduplicates events',()=>{
 const s=new RideSummary(),e={kind:'near_miss',x:2,z:0};s.update({x:0,z:0},true,[],[]);s.update({x:2,z:0},true,[{id:'a'}],[e]);s.update({x:3,z:0},true,[{id:'a'}],[e]);s.update({x:1000,z:0},true,[],[]);s.update({x:1002,z:0},false,[],[]);
 assert.equal(s.distance,3);assert.equal(s.hazards.size,1);assert.equal(s.nearMisses.length,1);
});
