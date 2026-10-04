import {test} from 'node:test';
import assert from 'node:assert/strict';
import * as T from 'three';
import {World,carveGroundGeometry} from '../src/world.js';
import {clipGroundAtRoads,subtractConvex} from '../src/ground-geometry.js';

const area=poly=>Math.abs(poly.reduce((sum,p,i)=>{const q=poly[(i+1)%poly.length];return sum+p[0]*q[1]-q[0]*p[1]},0))/2;
const makeWorld=(bridge,points=[[0,-20,0],[0,20,0]])=>new World({roads:[{points,nodeIds:['a','b'],width:4,bridge}],buildings:[]});

test('ground clipping removes road coverage and interpolates vertex attributes',()=>{
 const pieces=clipGroundAtRoads(makeWorld(false),[[-10,-10,0],[10,-10,20],[10,10,20],[-10,10,0]]);
 assert.ok(Math.abs(pieces.reduce((sum,p)=>sum+area(p),0)-320)<1e-6);
 for(const piece of pieces){
  assert.ok(piece.every(p=>p[0]<=-2)||piece.every(p=>p[0]>=2));
  for(const p of piece)assert.ok(Math.abs(p[2]-(p[0]+10))<1e-6);
 }
});

test('ground clipping handles reversed road segments',()=>{
 const pieces=clipGroundAtRoads(makeWorld(false,[[0,20,0],[0,-20,0]]),[[-10,-10,0],[10,-10,20],[10,10,20],[-10,10,0]]);
 assert.ok(Math.abs(pieces.reduce((sum,p)=>sum+area(p),0)-320)<1e-6);
 for(const piece of pieces)assert.ok(piece.every(p=>p[0]<=-2)||piece.every(p=>p[0]>=2));
});

test('ground remains beneath bridges and touching edges do not create slivers',()=>{
 const polygon=[[-10,-10],[10,-10],[10,10],[-10,10]];
 assert.deepEqual(clipGroundAtRoads(makeWorld(true),polygon),[polygon]);
 const touching=[[-2,-2],[-2,2],[2,2],[2,-2]];
 assert.deepEqual(subtractConvex([[2,-2],[4,-2],[4,2],[2,2]],touching),[[[2,-2],[4,-2],[4,2],[2,2]]]);
});

test('rendered terrain triangles cannot protrude through the road',()=>{
 const source=new T.PlaneGeometry(20,20);source.rotateX(-Math.PI/2);source.computeVertexNormals();
 const geometry=carveGroundGeometry(makeWorld(false),source),p=geometry.getAttribute('position');
 const indices=geometry.index.array;
 for(let i=0;i<indices.length;i+=3){
  const x=[p.getX(indices[i]),p.getX(indices[i+1]),p.getX(indices[i+2])];
  assert.ok(x.every(v=>v<=-2)||x.every(v=>v>=2));
 }
 assert.equal(geometry.getAttribute('uv').count,p.count);
 assert.equal(geometry.getAttribute('normal').count,p.count);geometry.dispose();
});


test('road textures share world coordinates across adjoining segments',async()=>{
 const {roadRibbon}=await import('../src/world.js');
 const a=roadRibbon([[0,0,0],[0,20,0]],6),b=roadRibbon([[0,20,0],[0,40,0]],6);
 const auv=a.getAttribute('uv'),buv=b.getAttribute('uv');
 for(let side=0;side<2;side++){
  assert.equal(auv.getX(2+side),buv.getX(side));
  assert.equal(auv.getY(2+side),buv.getY(side));
 }
 a.dispose();b.dispose();
});
