import {test} from 'node:test';
import assert from 'node:assert/strict';
import * as T from 'three';
import {cameraViews,positionHudCamera,CameraFeedSchedule} from '../src/hud-cameras.js';

test('surround cameras face front, left, right and back relative to the motorcycle',()=>{
 const expected=[[0,-1],[-1,0],[1,0],[0,1]],camera=new T.PerspectiveCamera(),direction=new T.Vector3();
 for(const heading of [0,Math.PI/2,-Math.PI/3,Math.PI])for(let i=0;i<cameraViews.length;i++){
  const pose={x:83,y:14,z:-121,heading};positionHudCamera(camera,pose,cameraViews[i].yaw);camera.getWorldDirection(direction);
  const horizontal=Math.hypot(direction.x,direction.z),[x,z]=expected[i];
  const worldX=x*Math.cos(heading)-z*Math.sin(heading),worldZ=x*Math.sin(heading)+z*Math.cos(heading);
  assert.ok(Math.abs(direction.x/horizontal-worldX)<1e-6);
  assert.ok(Math.abs(direction.z/horizontal-worldZ)<1e-6);
  assert.equal(camera.position.x,pose.x);assert.equal(camera.position.z,pose.z);
  assert.ok(camera.position.y>pose.y+1.4&&camera.position.y<pose.y+1.7);
  assert.ok(direction.y<0&&direction.y>-.05,'road views keep a level horizon with a slight downward angle');
 }
});

test('feed updates share a bounded round-robin budget, independent of main frame rate',()=>{
 for(const frameRate of [60,120]){
  const schedule=new CameraFeedSchedule(),counts=[0,0,0,0];
  for(let frame=0;frame<frameRate*2;frame++){
   const index=schedule.next(frame*1000/frameRate,1/frameRate,'balanced');if(index!==null)counts[index]++;
  }
  assert.ok(counts.every(count=>count>=8),'all four views continue refreshing');
  assert.ok(counts.reduce((a,b)=>a+b,0)<=40,'balanced mode must not render four extra views every frame');
  assert.ok(Math.max(...counts)-Math.min(...counts)<=1,'no direction starves');
 }
});

test('slow main frames reduce the feed rate and a long pause never produces a catch-up burst',()=>{
 const updates=dt=>{const schedule=new CameraFeedSchedule();let count=0;for(let now=0;now<3000;now+=dt*1000)if(schedule.next(now,dt,'high')!==null)count++;return count};
 assert.ok(updates(1/15)<updates(1/60)/2);
 const schedule=new CameraFeedSchedule();schedule.next(0,1/60,'balanced');
 assert.notEqual(schedule.next(60000,1/60,'balanced'),null);
 for(let i=0;i<4;i++)assert.equal(schedule.next(60000,1/60,'balanced'),null);
});
