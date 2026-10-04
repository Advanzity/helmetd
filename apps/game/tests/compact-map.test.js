import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {World} from '../src/world.js';
import {RoadTraffic} from '../src/traffic.js';

const read=name=>JSON.parse(fs.readFileSync(new URL(`../public/assets/${name}`,import.meta.url)));
const data=read('compact-world.json'),world=new World(data);

test('compact map covers Dearborn around Michigan Avenue',()=>{
 assert.equal(data.locationName,'Dearborn');
 assert.equal(data.primaryRoadName,'Michigan Avenue');
 assert.equal(data.regionName,'Wayne County');
 assert.equal(data.districtName,'West Dearborn');
 assert.ok(Math.abs(data.origin[0]+83.246)<.001&&Math.abs(data.origin[1]-42.3061)<.001);
 assert.ok(data.roads.length>1000);
 assert.ok(data.buildings.length>3000);
 assert.ok(data.signals.length>0);
 assert.deepEqual(data.bounds,[-1800,-1800,1800,1800]);
 assert.equal(data.outerTerrain,undefined);
 for(const r of data.roads){
  assert.ok(!['footway','path','steps','cycleway','pedestrian'].includes(r.class));
  assert.equal(r.points.length,r.nodeIds.length);
  for(const p of r.points){assert.ok(p.every(Number.isFinite));assert.ok(Math.abs(p[0])<=1800.000001&&Math.abs(p[1])<=1800.000001)}
 }
});

test('Michigan Avenue and featured business starts are drivable with connected traffic',()=>{
 for(const kind of [0,1,10,11,12]){
  const p=world.spawn(kind),g=world.ground(p.x,p.z,p.y);
  assert.ok(g.onRoad);assert.ok(!world.collision(p.x,p.z));assert.ok(Number.isFinite(g.height));
 }
 for(let i=0;i<data.businesses.length;i++){
  const business=data.businesses[i],p=world.spawn(10+i);
  assert.equal(world.ground(p.x,p.z).road.name,business.street);
  assert.ok(Math.hypot(p.x-business.point[0],-p.z-business.point[1])<80);
 }
 assert.equal(world.ground(world.spawn(0).x,world.spawn(0).z).road.name,'Michigan Avenue');
 const traffic=new RoadTraffic(world);
 const connected=traffic.edges.filter(e=>(traffic.out.get(e.to)||[]).some(next=>next.to!==e.from));
 assert.ok(connected.length>traffic.edges.length*.8);
 const nodes=new Set(data.roads.flatMap(r=>r.nodeIds));
 for(const s of [...data.signals,...data.stops])assert.ok(nodes.has(s.node));
});
