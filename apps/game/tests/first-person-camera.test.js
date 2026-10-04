import {test} from 'node:test';
import assert from 'node:assert/strict';
import {FirstPersonCamera} from '../src/first-person-camera.js';
const pose={x:0,y:0,z:0,heading:0,speed:0,lean:0};
test('first person follows travel without position lag or speed zoom',()=>{
 const c=new FirstPersonCamera();c.update(pose,1/60);
 const v=c.update({...pose,x:2,speed:40,lean:1},1/60);
 assert.equal(v.x,2);assert.equal(v.fov,68);assert.equal(v.pitch,-.10);
});
test('heading follows shortest arc across wrap and is frame-rate independent',()=>{
 const run=hz=>{const c=new FirstPersonCamera();c.update({...pose,heading:Math.PI-.1},0);for(let i=0;i<hz;i++)c.update({...pose,heading:-Math.PI+.1},1/hz);return c.heading};
 assert.ok(Math.abs(run(30)-run(120))<1e-10);assert.ok(Math.abs(run(60)-(Math.PI+.1))<.001);
});
test('reset snaps the camera to a new rider pose',()=>{
 const c=new FirstPersonCamera();c.update(pose,.1);c.reset();const v=c.update({...pose,y:10,heading:2},0);
 assert.equal(v.heading,2);assert.equal(v.y,11.46);
});
