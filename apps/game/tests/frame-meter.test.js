import {test} from 'node:test';
import assert from 'node:assert/strict';
import {FrameMeter} from '../src/frame-meter.js';
test('reports delivered frame cadence at 30, 60 and 120 fps',()=>{
 for(const fps of [30,60,120]){const meter=new FrameMeter();for(let i=0;i<fps*2;i++)meter.sample(i*1000/fps);const result=meter.snapshot();assert.ok(Math.abs(result.fps-fps)<.001);assert.ok(Math.abs(result.ms-1000/fps)<.001);}
});
test('slow rendered frames reduce fps and returning from background clears the old window',()=>{
 const meter=new FrameMeter();for(let i=0;i<=10;i++)meter.sample(i*100);assert.equal(meter.snapshot().fps,10);
 meter.sample(10000);assert.equal(meter.snapshot(),null);meter.sample(10020);assert.equal(meter.snapshot().fps,50);
 meter.reset();assert.equal(meter.snapshot(),null);
});
