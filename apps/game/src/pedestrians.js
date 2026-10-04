import * as T from 'three';
// Lightweight walkers stay on roadside paths and turn around before obstacles.
export class Pedestrians {
 constructor(scene,world){
  this.world=world;this.people=[];this.time=0;this.seed=71;
  const skin=new T.MeshStandardMaterial({color:0xb98a68,roughness:1}),pants=new T.MeshStandardMaterial({color:0x293544,roughness:1});
  const head=new T.SphereGeometry(.12,8,6),body=new T.CapsuleGeometry(.17,.36,3,8),limb=new T.CapsuleGeometry(.055,.48,3,6);
  for(let i=0;i<24;i++){
   const obj=new T.Group(),shirt=new T.MeshStandardMaterial({color:[0x536e87,0x963f39,0xd0bb8a,0x4e6952][i%4],roughness:1});
   const face=new T.Mesh(head,skin);face.position.y=1.62;obj.add(face);
   const torso=new T.Mesh(body,shirt);torso.position.y=1.23;obj.add(torso);
   const limbs=[];
   for(const side of [-1,1])for(const arm of [false,true]){const pivot=new T.Group();pivot.position.set(side*(arm?.23:.1),arm?1.42:.85,0);const mesh=new T.Mesh(limb,arm?shirt:pants);mesh.position.y=-.27;pivot.add(mesh);obj.add(pivot);limbs.push({pivot,side,arm});}
   obj.visible=false;scene.add(obj);this.people.push({obj,limbs,kind:'person',edge:null,distance:0,direction:i%2?1:-1});
  }
 }
 random(){this.seed=(Math.imul(this.seed,1664525)+1013904223)>>>0;return this.seed/4294967296}
 position(person,distance){const e=person.edge,t=distance/e.len,dx=(e.b[0]-e.a[0])/e.len,dy=(e.b[1]-e.a[1])/e.len,offset=person.side*((e.road.renderWidths?Math.max(...e.road.renderWidths):e.road.width)/2+2);return {x:e.a[0]+dx*distance-dy*offset,z:-e.a[1]-dy*distance-dx*offset,y:e.a[2]+(e.b[2]-e.a[2])*t};}
 update(dt,rider){
  this.time+=dt;
  for(const person of this.people){
   if(!person.edge||Math.hypot(person.obj.position.x-rider.x,person.obj.position.z-rider.z)>350){
    person.edge=null;person.obj.visible=false;
    const candidates=this.world.segments.filter(e=>e.len>15&&!e.road.bridge&&['primary','secondary','tertiary','residential'].includes(e.road.class)&&Math.hypot(e.a[0]-rider.x,-e.a[1]-rider.z)<250);
    for(let i=0;i<20&&candidates.length;i++){person.edge=candidates[Math.floor(this.random()*candidates.length)];person.side=this.random()<.5?-1:1;person.distance=2+this.random()*(person.edge.len-4);const p=this.position(person,person.distance),road=this.world.roadAt(p.x,p.z);if(!this.world.collision(p.x,p.z)&&!(road&&road.distance<road.road.width/2+.5)&&Math.hypot(p.x-rider.x,p.z-rider.z)>10)break;person.edge=null;}
   }
   if(!person.edge)continue;
   let next=person.distance+person.direction*dt*.95;
   if(next<2||next>person.edge.len-2){person.direction*=-1;next=person.distance;}
   const p=this.position(person,next),road=this.world.roadAt(p.x,p.z);
   if(this.world.collision(p.x,p.z)||road&&road.distance<road.road.width/2+.5)person.direction*=-1;else person.distance=next;
   const point=this.position(person,person.distance);person.obj.position.set(point.x,point.y,point.z);person.obj.visible=true;
   person.obj.rotation.y=-Math.atan2(person.edge.b[0]-person.edge.a[0],person.edge.b[1]-person.edge.a[1])+(person.direction<0?Math.PI:0);
   for(const limb of person.limbs)limb.pivot.rotation.x=Math.sin(this.time*5+person.distance)*.4*limb.side*(limb.arm?-1:1);
  }
 }
}
