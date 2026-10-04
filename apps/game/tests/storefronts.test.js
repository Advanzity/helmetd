import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {storefrontPlan,atlasUV} from '../src/storefronts.js';
import {buildingTiles} from '../src/buildings.js';

const building={id:'shop',type:'yes',base:0,height:10,points:[[0,20],[20,20],[20,30],[0,30],[0,20]]};
const road={name:'Michigan Avenue',points:[[-100,0,0],[100,0,0]]};

test('featured West Dearborn businesses have unique signs facing their own streets',()=>{
 const data=JSON.parse(fs.readFileSync(new URL('../public/assets/compact-world.json',import.meta.url)));
 assert.deepEqual(data.businesses.map(b=>b.id),['qahwah-house','jabal','level-zero']);
 const plan=storefrontPlan(data,data.businesses),matched=new Set();
 for(const business of data.businesses){
  assert.equal(business.placement,'mapped');assert.ok(business.source.startsWith('https://'));
  const entries=[...plan.plans].filter(([,p])=>p.featuredShops?.some(s=>plan.shops[s.index].id===business.id));
  assert.equal(entries.length,1,`${business.name} should match one footprint`);
  const [id,front]=entries[0];assert.ok(!matched.has(id));matched.add(id);
  const onStreet=data.roads.filter(r=>r.name===business.street).some(r=>r.points.slice(1).some((b,i)=>{
   const a=r.points[i],dx=b[0]-a[0],dy=b[1]-a[1],t=((front.target[0]-a[0])*dx+(front.target[1]-a[1])*dy)/(dx*dx+dy*dy);
   return t>=-.000001&&t<=1.000001&&Math.hypot(a[0]+dx*t-front.target[0],a[1]+dy*t-front.target[1])<.001;
  }));assert.ok(onStreet,`${business.name} frontage should face ${business.street}`);
  const tiles=buildingTiles([data.buildings.find(b=>b.id===id)],()=>0,plan);
  const shopIndex=plan.shops.findIndex(s=>s.id===business.id),center=atlasUV(shopIndex,.5,.5,plan.shops.length),rows=Math.ceil(plan.shops.length/4);
  let vertices=0;
  for(const g of tiles){const uv=g.getAttribute('uv');for(const group of g.groups.filter(group=>group.materialIndex===4))for(let i=group.start;i<group.start+group.count;i++){
   if(Math.abs(uv.getX(i)-center[0])<.125&&Math.abs(uv.getY(i)-center[1])<.5/rows)vertices++;
  }g.dispose()}
  assert.equal(vertices,18,`${business.name} should occupy one bay including its awning`);
 }
});

test('avenue gets storefronts without converting homes or civic buildings',()=>{
 const data={roads:[road],buildings:[building,{...building,id:'home',type:'house'},{...building,id:'school',type:'school'},{...building,id:'far',points:building.points.map(p=>[p[0],p[1]+300])}]};
 const {plans}=storefrontPlan(data);
 assert.deepEqual([...plans.keys()],['shop']);
});

test('featured signs use the street frontage rather than a recessed wall',()=>{
 const b={...building,points:[[0,20],[20,20],[20,30],[10,30],[10,40],[0,40],[0,20]]};
 const plan=storefrontPlan({roads:[road],buildings:[b]},[{name:'Featured shop',kind:'cafe',brand:'test',point:[6,35],street:'Michigan Avenue'}]);
 const [g]=buildingTiles([b],()=>0,plan),index=plan.shops.length-1,center=atlasUV(index,.5,.5,plan.shops.length),rows=Math.ceil(plan.shops.length/4);
 const uv=g.getAttribute('uv'),pos=g.getAttribute('position'),normal=g.getAttribute('normal');let walls=0;
 for(const group of g.groups.filter(group=>group.materialIndex===4))for(let i=group.start;i<group.start+group.count;i++){
  if(Math.abs(uv.getX(i)-center[0])<.125&&Math.abs(uv.getY(i)-center[1])<.5/rows&&Math.abs(normal.getY(i))<.001&&(pos.getY(i)<.001||pos.getY(i)>3.69)){
   assert.ok(Math.abs(pos.getZ(i)+20)<.001);walls++;
  }
 }
 assert.equal(walls,6);g.dispose();
});

test('business names are placed only at matched building footprints',()=>{
 const plan=storefrontPlan({roads:[road],buildings:[building]},[{name:'Mapped Café',kind:'cafe',point:[10,25]},{name:'Distant Café',kind:'cafe',point:[900,900]}]);
 assert.equal(plan.shops[plan.plans.get('shop').shops[0]].name,'Mapped Café');
 assert.equal(plan.shops.some(s=>s.name==='Distant Café'),false);
});

test('storefronts have a ground-floor material and retain explicitly tagged heights',()=>{
 for(const heightTagged of [true,false]){
  const b={...building,heightTagged},data={roads:[road],buildings:[b]},plan=storefrontPlan(data);
  const [g]=buildingTiles(data.buildings,()=>0,plan);g.computeBoundingBox();
  assert.ok(g.groups.some(group=>group.materialIndex===4));
  assert.equal(g.boundingBox.max.y,heightTagged?10:Math.fround(4.6));g.dispose();
 }
});

test('atlas coordinates stay inside their own sign cells',()=>{
 for(let i=0;i<8;i++)for(const u of [0,1])for(const v of [0,1]){
  const [x,y]=atlasUV(i,u,v,8);assert.ok(x>i%4/4&&x<(i%4+1)/4);assert.ok(y>1-(Math.floor(i/4)+1)/2&&y<1-Math.floor(i/4)/2);
 }
});

test('restaurant detail adds less than ten percent to the whole map geometry',()=>{
 const data=JSON.parse(fs.readFileSync(new URL('../public/assets/compact-world.json',import.meta.url)));
 const old=buildingTiles(data.buildings,()=>0),updated=buildingTiles(data.buildings,()=>0,storefrontPlan(data,data.businesses));
 const triangles=tiles=>tiles.reduce((sum,g)=>sum+g.getAttribute('position').count/3,0);
 assert.ok(triangles(updated)<triangles(old)*1.1);
 for(const g of updated)assert.ok(g.groups.length<=5);
 for(const g of [...old,...updated])g.dispose();
});
