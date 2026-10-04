import {test} from 'node:test';
import assert from 'node:assert/strict';
import {potholeAhead} from '../src/potholes.js';
test('pothole warning uses travel direction, lane, and height',()=>{
 const p={x:0,z:0,y:0,heading:0,speed:10};
 assert.equal(potholeAhead(p,[{x:0,z:-25,y:0}]),true);
 for(const h of [{x:0,z:10,y:0},{x:8,z:-10,y:0},{x:0,z:-10,y:8}])assert.equal(potholeAhead(p,[h]),false);
});
