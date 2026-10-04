import {test} from 'node:test';import assert from 'node:assert/strict';import {MotorcyclePhysics,ratios} from '../src/physics.js';
const road={height:0,surface:'asphalt'};const input={throttle:1,brake:0,steer:0,clutch:0,rearBrake:0};
test('six ratios decrease and shifts affect coupled engine RPM',()=>{const p=new MotorcyclePhysics();p.speed=20;for(let i=0;i<120;i++)p.step(1/120,input,road);const before=p.rpm;p.shift(1);assert.equal(p.gear,2);assert.ok(p.rpm<before);assert.equal(ratios.length,7)});
test('neutral decouples engine from rear wheel',()=>{const p=new MotorcyclePhysics();p.gear=0;for(let i=0;i<600;i++)p.step(1/120,input,road);assert.equal(p.speed,0);assert.ok(p.rpm>9000)});
test('throttle accelerates, braking stops without reversing',()=>{const p=new MotorcyclePhysics();for(let i=0;i<600;i++)p.step(1/120,input,road);assert.ok(p.speed>10);for(let i=0;i<900;i++)p.step(1/120,{...input,throttle:0,brake:1},road);assert.equal(p.speed,0)});
test('lean and turn directions agree; state stays finite',()=>{const p=new MotorcyclePhysics();for(let i=0;i<1200;i++)p.step(1/120,{...input,steer:.5},road);assert.ok(p.heading>0);assert.ok(p.lean<0);for(const n of ['x','z','rpm','speed','lean'])assert.ok(Number.isFinite(p[n]))});

test('foot reverse is capped, stops on release, and cannot engage at speed',()=>{
 const p=new MotorcyclePhysics(),back={...input,throttle:0,reverse:true};
 for(let i=0;i<480;i++)p.step(1/120,back,road);
 assert.ok(p.speed<0&&p.speed>=-1.15);assert.ok(p.z>0);assert.ok(p.reversing&&p.kickPhase>0);
 for(let i=0;i<120;i++)p.step(1/120,{...back,reverse:false},road);
 assert.equal(p.speed,0);assert.equal(p.reversing,false);
 p.speed=10;p.step(1/120,back,road);assert.ok(p.speed>0);assert.equal(p.reversing,false);
});
test('brake overrides the foot push and reset clears its animation',()=>{
 const p=new MotorcyclePhysics();p.step(.1,{...input,throttle:0,reverse:true},road);
 for(let i=0;i<60;i++)p.step(1/120,{...input,throttle:0,reverse:true,brake:1},road);
 assert.equal(p.speed,0);p.reset({x:0,z:0,y:0,heading:0});assert.equal(p.kickPhase,0);
});
