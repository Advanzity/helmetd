import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {GameNavigation} from '../src/game-navigation.js';
const road=(id,nodes,points,oneway=false)=>({id,nodeIds:nodes,points,oneway,name:id});
const pose={x:10,z:0,heading:Math.PI/2};
const data={roads:[road('east',['a','b'],[[0,0],[100,0]]),road('north',['b','c'],[[100,0],[100,100]])]};
test('routes from projected rider position with turn and remaining distance',()=>{
 const nav=new GameNavigation(data);assert.ok(nav.route(pose,[100,90],'Cafe'));
 const state=nav.update(pose,0);assert.equal(state.maneuver,'left');assert.equal(state.distance_m,90);assert.equal(state.remaining_m,180);
 assert.equal(nav.update({...pose,x:100,z:-88},200).state,'arrived');
 assert.equal(nav.update(pose,400,true).state,'paused');nav.clear();assert.equal(nav.update(pose,600).state,'idle');
});
test('does not route backward along a one-way road or across disconnected roads',()=>{
 const nav=new GameNavigation({roads:[road('east',['a','b'],[[0,0],[100,0]],true),road('other',['c','d'],[[0,100],[100,100]])]});
 assert.equal(nav.route({...pose,x:90},[10,0]),false);
 assert.equal(nav.route(pose,[50,100]),false);
});
test('turn restrictions are respected',()=>{
 const nav=new GameNavigation({...data,restrictions:[{from:'east',to:'north',via:'b',kind:'no_left_turn'}]});
 assert.equal(nav.route(pose,[100,90]),false);
});
test('the shipped map has a connected route along its road graph',()=>{
 const world=JSON.parse(readFileSync(new URL('../public/assets/compact-world.json',import.meta.url)));
 const nav=new GameNavigation(world),road=world.roads.find(r=>r.points.length>5&&!r.oneway);
 const a=road.points[1],b=road.points.at(-2);
 assert.ok(nav.route({x:a[0],z:-a[1],heading:0},b,road.name));
 const snapshot=nav.update({x:a[0],z:-a[1]},0);
 assert.ok(snapshot.remaining_m>0);assert.ok(snapshot.points.length<=32);
 assert.ok(snapshot.points.flat().every(v=>Number.isFinite(v)&&v>=0&&v<=1000));
});
