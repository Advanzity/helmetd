import {Vector3,Quaternion,PropertyBinding} from 'three';

export function kickTarget(side,phase){
 const t=phase+(side<0?Math.PI:0);
 return new Vector3(side*.34,.10+Math.max(0,Math.sin(t))*.10,.30+Math.cos(t)*.19);
}
// Solve the existing skinned leg chains; never replace the rider mesh.
export class ReverseRider {
 constructor(bike){
  this.bike=bike;this.blend=0;this.time=0;this.look=0;this.shift=0;this.nod=0;
  this.helmet=bike.getObjectByName('Helmet');
  this.parts=['RiderRig','Armored textile riding jacket','Helmet'].map(name=>bike.getObjectByName(PropertyBinding.sanitizeNodeName(name))).filter(Boolean).map(object=>({object,rest:object.position.clone()}));
  this.helmetRest=this.helmet?.quaternion.clone();
  this.legs=[1,-1].map(side=>{
   const suffix=side>0?'L':'R';
   const joints=['upperleg01','lowerleg01'].map(name=>bike.getObjectByName(PropertyBinding.sanitizeNodeName(name+'.'+suffix)));
   const foot=bike.getObjectByName(PropertyBinding.sanitizeNodeName('foot.'+suffix));
   return {side,joints,foot,rest:joints.map(b=>b?.quaternion.clone())};
  }).filter(l=>l.foot&&l.joints.every(Boolean));
 }
 update(dt,pose){
  if(dt<=0)return;
  this.time+=dt;
  const ease=1-Math.exp(-dt*6),steer=pose.steer||0,lean=pose.lean||0;
  this.look+=((pose.crashed?0:steer*.22)-this.look)*ease;
  this.shift+=((pose.crashed?0:-lean*.055)-this.shift)*ease;
  this.nod+=((pose.crashed?0:Math.max(-.045,Math.min(.045,(pose.acceleration||0)*.004)))-this.nod)*ease;
  const bob=pose.crashed?0:Math.sin(this.time*2)*.0025+(pose.reversing?Math.sin(pose.kickPhase*2)*.005:0);
  for(const {object,rest} of this.parts)object.position.copy(rest).add(new Vector3(this.shift,bob,0));
  if(this.helmet){this.helmet.quaternion.copy(this.helmetRest);this.helmet.rotateY(this.look);this.helmet.rotateX(this.nod);this.helmet.rotateZ(-lean*.10);}
  this.blend+=((pose.reversing&&!pose.crashed?1:0)-this.blend)*(1-Math.exp(-dt*10));
  for(const leg of this.legs){
   leg.joints.forEach((b,i)=>b.quaternion.copy(leg.rest[i]));
   if(this.blend<.001)continue;
   this.bike.updateMatrixWorld(true);
   const target=this.bike.localToWorld(kickTarget(leg.side,pose.kickPhase));
   for(let pass=0;pass<5;pass++)for(const joint of [...leg.joints].reverse()){
    const origin=joint.getWorldPosition(new Vector3());
    const from=leg.foot.getWorldPosition(new Vector3()).sub(origin).normalize();
    const to=target.clone().sub(origin).normalize();
    const parent=joint.parent.getWorldQuaternion(new Quaternion());
    const delta=new Quaternion().setFromUnitVectors(from,to);
    joint.quaternion.premultiply(parent.clone().invert().multiply(delta).multiply(parent));
    this.bike.updateMatrixWorld(true);
   }
   leg.joints.forEach((bone,i)=>bone.quaternion.slerpQuaternions(leg.rest[i],bone.quaternion.clone(),this.blend));
  }
 }
}
