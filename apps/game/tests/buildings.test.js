import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {buildingTiles} from '../src/buildings.js';

const house={id:'home',type:'house',base:0,height:6,points:[[0,0],[12,0],[12,8],[0,8],[0,0]]};

test('houses gain pitched roofs with outward walls and upward roofs',()=>{
 for(const points of [house.points,house.points.slice().reverse()]){
  const [g]=buildingTiles([{...house,points}],()=>0),p=g.getAttribute('position'),n=g.getAttribute('normal');
  g.computeBoundingBox();assert.equal(g.boundingBox.max.y,6);
  const roofs=g.groups.find(group=>group.materialIndex===3);
  for(let i=roofs.start;i<roofs.start+roofs.count;i++)assert.ok(n.getY(i)>.5);
  for(let i=0;i<24;i++)assert.ok(n.getX(i)*(p.getX(i)-6)+n.getZ(i)*(p.getZ(i)+4)>0);
  assert.equal(p.count/3,14);assert.equal(g.getAttribute('uv').count,p.count);g.dispose();
 }
});

test('concave footprints keep flat roofs and correct triangulation',()=>{
 const b={...house,type:'retail',points:[[0,0],[10,0],[10,4],[4,4],[4,10],[0,10],[0,0]]};
 const [g]=buildingTiles([b],()=>0),n=g.getAttribute('normal'),roof=g.groups.find(group=>group.materialIndex===3);
 for(let i=roof.start;i<roof.start+roof.count;i++)assert.ok(n.getY(i)>.99);g.dispose();
});

test('full Dearborn map stays batched with a bounded geometry budget',()=>{
 const data=JSON.parse(fs.readFileSync(new URL('../public/assets/dearborn-world.json',import.meta.url)));
 const tiles=buildingTiles(data.buildings,()=>0);
 assert.ok(tiles.length<150);
 let triangles=0;
 for(const g of tiles){assert.ok(g.groups.length<=4);triangles+=g.getAttribute('position').count/3;for(const v of g.getAttribute('position').array)assert.ok(Number.isFinite(v));g.dispose()}
 assert.ok(triangles<150000,`${triangles} triangles exceeds the map budget`);
});
