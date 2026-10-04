import {test} from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import {World,roadStrip,outerTerrainGeometry} from '../src/world.js';
const data=JSON.parse(fs.readFileSync(new URL('../public/assets/world.json',import.meta.url)));const world=new World(data);
test('both start points are on drivable surveyed road geometry',()=>{for(let i=0;i<2;i++){const p=world.spawn(i),g=world.ground(p.x,p.z);assert.ok(g.onRoad);assert.ok(Number.isFinite(g.height));assert.ok(!world.collision(p.x,p.z));assert.ok(Math.abs(p.x)<1700&&Math.abs(p.z)<1700)}});
test('Hall Road and M53 are present at real-world meter scale',()=>{assert.ok(data.roads.some(r=>r.name==='Hall Road'));assert.ok(data.roads.some(r=>r.name==='Christopher Columbus Freeway'));assert.equal(data.size,3600);assert.ok(data.roads.filter(r=>r.bridge).length>0);assert.ok(data.buildings.length>1000)});
test('building interiors collide and terrain heights are finite',()=>{const b=data.buildings.find(b=>b.points.length===5);const x=b.points.slice(0,-1).reduce((v,p)=>v+p[0],0)/4,z=-b.points.slice(0,-1).reduce((v,p)=>v+p[1],0)/4;assert.ok(world.collision(x,z));for(const x of [-1600,0,1600])for(const z of [-1600,0,1600])assert.ok(Number.isFinite(world.elevation(x,z)))});

test('road surface normals face upward for both travel directions',()=>{for(const b of [[0,20,0],[0,-20,0],[20,0,0],[-20,0,0]]){const g=roadStrip([0,0,0],b,7);const n=g.getAttribute('normal');for(let i=0;i<n.count;i++)assert.ok(n.getY(i)>.99);g.dispose()}});

test('outer terrain leaves the aerial square uncovered and has upward faces',()=>{
 const world={data:{bounds:[-50,-50,50,50],size:40,resolution:2,heights:[0,0,0,0]},elevation:()=>0,roadAt:()=>null};
 const g=outerTerrainGeometry(world),p=g.getAttribute('position'),indices=g.index.array;
 let area=0;
 for(let i=0;i<indices.length;i+=3){
  const ids=Array.from(indices.slice(i,i+3)),x=ids.reduce((s,k)=>s+p.getX(k),0)/3,z=ids.reduce((s,k)=>s+p.getZ(k),0)/3;
  assert.ok(Math.abs(x)>=20||Math.abs(z)>=20,'triangle overlaps central terrain');
  const [a,b,c]=ids,cross=(p.getZ(b)-p.getZ(a))*(p.getX(c)-p.getX(a))-(p.getX(b)-p.getX(a))*(p.getZ(c)-p.getZ(a));
  assert.ok(cross>0,'triangle faces downward');area+=cross/2;
 }
 assert.ok(Math.abs(area-(100*100-40*40))<.01,'outer terrain contains gaps');g.dispose();
});
