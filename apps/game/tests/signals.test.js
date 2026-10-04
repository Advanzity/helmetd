import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as T from 'three';
import {World,roadRibbon} from '../src/world.js';
import {RoadTraffic,signalPhase} from '../src/traffic.js';
import {addTrafficLights} from '../src/traffic-lights.js';
import {laneCenter} from '../src/road-layout.js';
import {coversPavement} from '../src/signal-clearance.js';
import {signalArmsCross,approachPoint} from '../src/signal-layout.js';

const data=JSON.parse(fs.readFileSync(new URL('../public/assets/compact-world.json',import.meta.url)));
const world=new World(data),traffic=new RoadTraffic(world);

test('all rendered poles are clear of buildings and travel lanes',()=>{
 assert.ok(traffic.edges.filter(e=>e.signal).every(e=>e.visualControl),'every signal approach should have a visible controller');
 for(const s of traffic.signalLayouts){assert.ok(!world.collision(s.pole.x,s.pole.z));assert.ok(!world.ground(s.pole.x,s.pole.z).onRoad,`${s.e.road.name} pole is in the road`)}
});

test('a narrow nearest street cannot hide a pole inside wider crossing pavement',()=>{
 const x=-412.90309719009736,z=258.70123442651266;
 assert.equal(world.ground(x,z).onRoad,false);
 assert.equal(coversPavement(world,x,z),true);
});

test('every approach has a visible facing signal from a stopped helmet camera',()=>{
 const camera=new T.PerspectiveCamera(64,16/10,.1,900),up=new T.Vector3(0,1,0);
 for(const edge of traffic.edges.filter(e=>e.signal)){
  const layout=edge.visualControl,p=approachPoint(edge,edge.stopDistance,traffic.incoming),h=p.heading,lane=laneCenter(edge.road);
  camera.position.set(p.x+Math.cos(h)*lane-Math.sin(h)*1.1,p.y+1.49,p.z+Math.sin(h)*lane+Math.cos(h)*1.1);
  camera.lookAt(camera.position.x+Math.sin(h)*30,p.y+1.4,camera.position.z-Math.cos(h)*30);camera.updateMatrixWorld();
  const visible=layout.lanes.some(lane=>{
   const point=new T.Vector3(layout.pole.x+Math.cos(layout.pole.heading)*(lane-layout.right),layout.pole.y+5.42,layout.pole.z+Math.sin(layout.pole.heading)*(lane-layout.right));
   const normal=new T.Vector3(0,0,1).applyAxisAngle(up,-layout.pole.heading),facesRider=camera.position.clone().sub(point).dot(normal)>0;point.project(camera);
   return facesRider&&Math.abs(point.x)<.95&&Math.abs(point.y)<.95&&point.z<1;
  });assert.ok(visible,`no readable light when stopped at ${edge.road.name}, node ${edge.to}`);
 }
});

test('crossing mast arms have separate heights',()=>{
 let crossings=0;
 for(let i=0;i<traffic.signalLayouts.length;i++)for(let j=i+1;j<traffic.signalLayouts.length;j++){
  const a=traffic.signalLayouts[i],b=traffic.signalLayouts[j];if(!signalArmsCross(a,b))continue;
  assert.ok(Math.abs(a.mastHeight-b.mastHeight)>=.3);crossings++;
 }
 assert.ok(crossings>0);
});

test('all poles clear the actual rendered road ribbons, including intersecting roads',()=>{
 const material=new T.MeshBasicMaterial({side:T.DoubleSide}),meshes=new Map();
 const ray=new T.Raycaster(),origin=new T.Vector3(),down=new T.Vector3(0,-1,0);
 for(const {pole} of traffic.signalLayouts){
  const roads=new Set((world.grid.get(Math.floor(pole.x/50)+','+Math.floor(-pole.z/50))||[]).map(s=>s.road));
  for(const road of roads){
   if(!meshes.has(road)){const mesh=new T.Mesh(roadRibbon(road.points,road.width,road.pavementOffset||0),material);mesh.updateMatrixWorld();meshes.set(road,mesh)}
   ray.set(origin.set(pole.x,pole.y+1,pole.z),down);ray.far=2;
   assert.equal(ray.intersectObject(meshes.get(road)).length,0,`pole inside ${road.name} pavement`);
  }
 }
 for(const mesh of meshes.values())mesh.geometry.dispose();material.dispose();
});

test('opposing motorists each get correctly oriented lights at Michigan and Mason',()=>{
 const signals=traffic.signalLayouts.filter(s=>s.e.to==='62822469');assert.equal(signals.length,4);
 for(const layout of signals){
  assert.ok(!world.collision(layout.pole.x,layout.pole.z));
  assert.equal(layout.lanes.length,Math.max(1,Math.floor(layout.e.road.lanes/2)));
  assert.ok(layout.lanes.every((lane,i)=>Math.abs(lane-laneCenter(layout.e.road,i))<.001));
  const back=new T.Vector3(0,0,1).applyAxisAngle(new T.Vector3(0,1,0),-layout.pole.heading);
  const approaching=new T.Vector3(-Math.sin(layout.pole.heading),0,Math.cos(layout.pole.heading));
  assert.ok(back.dot(approaching)>.999);
 }
});

test('skew junctions use separate phases even when both roads run mostly east-west',()=>{
 const edges=traffic.edges.filter(e=>e.to==='62744063');
 const main=edges.find(e=>e.road.name==='Oakwood Boulevard'),side=edges.find(e=>e.road.name==='Beech Street');
 assert.notEqual(main.axis,side.axis);
 for(let time=0;time<100;time+=.25){traffic.time=time;assert.ok(!(traffic.phase(main)==='green'&&traffic.phase(side)==='green'))}
});

test('three signal stages each get green, yellow and an all-red clearance',()=>{
 const observed=Array.from({length:3},()=>new Set());let clearance=0;
 for(let time=0;time<99;time+=.25){const phases=observed.map((s,axis)=>{const p=signalPhase(time,axis,0,3);s.add(p);return p});assert.ok(phases.filter(p=>p!=='red').length<=1);if(phases.every(p=>p==='red'))clearance++}
 assert.ok(clearance>=24);for(const phases of observed)assert.deepEqual([...phases].sort(),['green','red','yellow']);
});

test('lights and stop bars use a bounded number of shared batches with one active lens',()=>{
 const scene=new T.Scene(),renderer=addTrafficLights(scene,traffic.signalLayouts);
 assert.equal(scene.children.length,7);assert.ok(scene.children.every(o=>o.isInstancedMesh));
 renderer.update({x:0,z:0},e=>signalPhase(10,e.axis,e.signal.group.offset,e.signal.group.axisCount));
 const color=new T.Color();
 for(const record of renderer.records.filter(r=>r.visible)){
  let active=0;for(const item of record.lenses){item.mesh.getColorAt(item.index,color);if(Math.max(color.r,color.g,color.b)>.5)active++}
  assert.equal(active,record.lenses.length/3);
 }
 const pole=renderer.records[0].layout.pole;renderer.update({x:10000,z:10000},()=> 'green');
 assert.ok(renderer.records.every(r=>!r.visible));renderer.update(pole,()=> 'yellow');assert.equal(renderer.records[0].phase,'yellow');
 for(const o of scene.children){o.geometry.dispose();o.material.dispose()}
});

test('cars stop before a wide intersection even across several short OSM segments',()=>{
 const main={id:'main',name:'Main',class:'primary',lanes:2,width:7.7,laneWidth:3.35,points:[[0,-100,0],[0,-15,0],[0,-10,0],[0,-5,0],[0,0,0],[0,100,0]],nodeIds:['a','b','c','d','cross','e']};
 const side={...main,id:'side',name:'Side',lanes:6,width:21.1,points:[[-100,0,0],[0,0,0],[100,0,0]],nodeIds:['f','cross','g']};
 const t=new RoadTraffic({data:{roads:[main,side],signals:[{node:'cross',point:[0,0]}]}});
 const edge=t.edges.find(e=>e.from==='a'&&e.to==='b'),car={id:0,obj:new T.Object3D(),edge,next:t.out.get('b').find(e=>e.to==='c'),distance:45,speed:12,brake:[]};
 t.cars=[car];t.time=36-t.edges.find(e=>e.road===main&&e.signal).axis*33;
 const rider={x:300,z:300,y:0,speed:0,crashed:false,crash(){}};
 for(let i=0;i<900;i++)t.update(1/60,rider);
 assert.ok(car.obj.position.z-2.4>=13.05-.01,`front bumper crossed stop line: ${car.obj.position.z}`);assert.ok(car.speed<.05);
 const control=t.edges.find(e=>e.road===main&&e.signal);t.time=control.axis*33;
 for(let i=0;i<300;i++)t.update(1/60,rider);assert.ok(car.speed>3);assert.ok(car.obj.position.z<13);
});
