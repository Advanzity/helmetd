import * as T from 'three';
export async function addRoadside(scene,world,loader){
 const [lamp,rail]=await Promise.all([loader.loadAsync('/assets/streetlamp.glb'),loader.loadAsync('/assets/guardrail.glb')]);
 const lamps=[],rails=[];world.barriers=[];
 for(const road of world.data.roads){if(!['motorway','trunk'].includes(road.class))continue;let at=35;
 for(let i=1;i<road.points.length;i++){const a=road.points[i-1],b=road.points[i],dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy);if(len<1)continue;const heading=Math.atan2(dx,dy),right=new T.Vector3(Math.cos(heading),0,Math.sin(heading));
  if(road.class==='trunk')for(let d=at;d<len;d+=72){const t=d/len,x=a[0]+dx*t,z=-a[1]-dy*t,offset=road.width/2+3;lamps.push({x:x+right.x*offset,y:world.elevation(x+right.x*offset,z+right.z*offset),z:z+right.z*offset,rot:-heading+Math.PI/2})}
  at=(at-len)%72;if(at<0)at+=72;
  if(road.bridge||road.class==='motorway')for(const side of [-1,1]){const offset=side*(road.width/2+1.2);world.barriers.push({a:[a[0]+right.x*offset,-a[1]+right.z*offset,a[2]],b:[b[0]+right.x*offset,-b[1]+right.z*offset,b[2]]});for(let d=2;d<len-1;d+=4){const t=d/len;rails.push({x:a[0]+dx*t+right.x*offset,y:a[2]+(b[2]-a[2])*t,z:-a[1]-dy*t+right.z*offset,rot:-heading+Math.PI/2})}}
 }
 }
 function instances(asset,placements){asset.updateMatrixWorld(true);const dummy=new T.Object3D(),mat=new T.Matrix4();asset.traverse(o=>{if(!o.isMesh)return;const inst=new T.InstancedMesh(o.geometry,o.material,placements.length);placements.forEach((p,i)=>{dummy.position.set(p.x,p.y,p.z);dummy.rotation.set(0,p.rot,0);dummy.updateMatrix();mat.multiplyMatrices(dummy.matrix,o.matrixWorld);inst.setMatrixAt(i,mat)});inst.castShadow=true;inst.receiveShadow=true;scene.add(inst)})}
 world.lamps=lamps;lamp.scene.traverse(o=>{if(o.isMesh&&o.material.name==='Lamp lens'){o.material.emissive.set(0xffd69a);o.material.emissiveIntensity=3}});instances(lamp.scene,lamps);instances(rail.scene,rails);
 // Highway boards are normal manufactured planar panels, textured with road names.
 const board=document.createElement('canvas');board.width=1024;board.height=512;const c=board.getContext('2d');c.fillStyle='#164d3d';c.fillRect(0,0,1024,512);c.strokeStyle='#e7e9da';c.lineWidth=12;c.strokeRect(15,15,994,482);c.fillStyle='#f4f0e0';c.font='bold 63px Arial';c.fillText('NORTH',400,106);c.font='bold 150px Arial';c.fillText('M 53',350,270);c.font='50px Arial';c.fillText('Van Dyke Freeway',245,375);c.font='100px Arial';c.fillText('↗',85,275);const texture=new T.CanvasTexture(board);texture.colorSpace=T.SRGBColorSpace;
 const hall=world.data.roads.filter(r=>r.name==='Hall Road'&&r.length>150);for(let i=0;i<Math.min(2,hall.length);i++){const r=hall[i],a=r.points[0],b=r.points[1],heading=Math.atan2(b[0]-a[0],b[1]-a[1]),x=a[0]+Math.cos(heading)*(r.width/2+3),z=-a[1]+Math.sin(heading)*(r.width/2+3),y=world.elevation(x,z);const post=lamp.scene.clone(true);post.position.set(x,y,z);post.scale.set(.65,.65,.65);scene.add(post);const panel=new T.Mesh(new T.PlaneGeometry(4.5,2.25),new T.MeshStandardMaterial({map:texture,roughness:.65,side:T.DoubleSide}));panel.position.set(x,y+4,z);panel.rotation.y=-heading;panel.castShadow=true;scene.add(panel)}
}
export function hitBarrier(world,x,z,y){for(const s of world.barriers||[]){if(Math.abs(y-s.a[2])>2)continue;const dx=s.b[0]-s.a[0],dz=s.b[1]-s.a[1],l=dx*dx+dz*dz,t=T.MathUtils.clamp(((x-s.a[0])*dx+(z-s.a[1])*dz)/l,0,1);if(Math.hypot(x-s.a[0]-t*dx,z-s.a[1]-t*dz)<.5)return true}return false}
