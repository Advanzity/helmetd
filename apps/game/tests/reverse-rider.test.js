import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {Group,Object3D,PropertyBinding,Vector3} from 'three';
import {ReverseRider} from '../src/reverse-rider.js';
test('the shipped rider rig lowers both feet and restores its seated pose',()=>{
 const bytes=readFileSync(new URL('../public/assets/motorcycle.glb',import.meta.url));
 const data=JSON.parse(bytes.subarray(20,20+bytes.readUInt32LE(12)).toString());
 const nodes=data.nodes.map(n=>{const o=new Object3D();o.name=PropertyBinding.sanitizeNodeName(n.name||'');if(n.translation)o.position.fromArray(n.translation);if(n.rotation)o.quaternion.fromArray(n.rotation);if(n.scale)o.scale.fromArray(n.scale);return o;});
 data.nodes.forEach((n,i)=>(n.children||[]).forEach(c=>nodes[i].add(nodes[c])));
 const root=new Group();data.scenes[data.scene||0].nodes.forEach(i=>root.add(nodes[i]));root.updateMatrixWorld(true);
 const rider=new ReverseRider(root);assert.equal(rider.legs.length,2);
 const heights=rider.legs.map(l=>l.foot.getWorldPosition(new Vector3()).y);
 for(let i=0;i<120;i++)rider.update(1/60,{reversing:true,crashed:false,kickPhase:0});
 rider.legs.forEach((leg,i)=>assert.ok(leg.foot.getWorldPosition(new Vector3()).y<heights[i]-.15));
 for(let i=0;i<120;i++)rider.update(1/60,{reversing:false,crashed:false,kickPhase:0});
 rider.legs.forEach((leg,i)=>assert.ok(Math.abs(leg.foot.getWorldPosition(new Vector3()).y-heights[i])<.01));
});
