import {clipGroundAtRoads} from './ground-geometry.js';
import * as T from 'three';
import {HDRLoader} from 'three/addons/loaders/HDRLoader.js';

export async function eveningLighting(scene,renderer,sun,sky,hemisphere){
 const hdr=await new HDRLoader().loadAsync('/assets/evening-sky.hdr');hdr.mapping=T.EquirectangularReflectionMapping;
 const pmrem=new T.PMREMGenerator(renderer);const reflection=pmrem.fromEquirectangular(hdr);pmrem.dispose();scene.remove(sky);scene.background=hdr;scene.environment=reflection.texture;
 scene.backgroundRotation.y=.6;scene.environmentRotation.y=.6;
 const apply=mode=>{const dusk=mode==='dusk';scene.backgroundIntensity=dusk?.20:.68;scene.environmentIntensity=dusk?.38:.85;sun.intensity=dusk?.18:2.65;sun.color.set(dusk?0xe5a28b:0xffd5ad);hemisphere.intensity=dusk?.32:.75;hemisphere.color.set(dusk?0x91a8cf:0xc5d9ed);hemisphere.groundColor.set(0x5e6246);scene.fog.color.set(dusk?0x727c92:0xb8bbc0);scene.fog.density=dusk?.0008:.0005;renderer.toneMappingExposure=dusk?1.05:.96;scene.userData.dusk=dusk;};apply('golden');return apply;
}
export function insidePolygon(x,y,p){let c=false;for(let i=0,j=p.length-1;i<p.length;j=i++)if((p[i][1]>y)!==(p[j][1]>y)&&x<(p[j][0]-p[i][0])*(y-p[i][1])/(p[j][1]-p[i][1])+p[i][0])c=!c;return c}
function polygonMesh(points,world,material,offset=.035,flat=false){
 let p=points.slice();if(p.length>3&&Math.hypot(p[0][0]-p.at(-1)[0],p[0][1]-p.at(-1)[1])<.1)p.pop();if(p.length<3)return null;
 const faces=T.ShapeUtils.triangulateShape(p.map(v=>new T.Vector2(...v)),[]),verts=[],uv=[];
 const base=world.elevation(p[0][0],-p[0][1]);
 const add=(a,b,c,depth=0)=>{const ab=Math.hypot(a[0]-b[0],a[1]-b[1]),bc=Math.hypot(c[0]-b[0],c[1]-b[1]),ca=Math.hypot(a[0]-c[0],a[1]-c[1]);if(Math.max(ab,bc,ca)>22&&depth<7){const mid=(a,b)=>[(a[0]+b[0])/2,(a[1]+b[1])/2],d=mid(a,b),e=mid(b,c),f=mid(c,a);add(a,d,f,depth+1);add(d,b,e,depth+1);add(f,e,c,depth+1);add(d,e,f,depth+1);return}if((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])<0)[b,c]=[c,b];for(const piece of clipGroundAtRoads(world,[a,b,c]))for(let i=1;i<piece.length-1;i++)for(const q of [piece[0],piece[i],piece[i+1]]){verts.push(q[0],(flat?base:world.elevation(q[0],-q[1]))+offset,-q[1]);uv.push(q[0]/3,q[1]/3)}};
 for(const f of faces)add(p[f[0]],p[f[1]],p[f[2]]);const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(verts,3));g.setAttribute('uv',new T.Float32BufferAttribute(uv,2));g.computeVertexNormals();const m=new T.Mesh(g,material);m.receiveShadow=true;return m;
}
export async function enrichGround(scene,world,loader){
 const tl=new T.TextureLoader();const tx=async(name,color=false)=>{const t=await tl.loadAsync('/assets/'+name);t.wrapS=t.wrapT=T.RepeatWrapping;t.anisotropy=8;if(color)t.colorSpace=T.SRGBColorSpace;return t};
 const [map,normal,rough]=await Promise.all([tx('grass-color.jpg',true),tx('grass-normal.jpg'),tx('grass-roughness.jpg')]);const grass=new T.MeshStandardMaterial({map,normalMap:normal,roughnessMap:rough,normalScale:new T.Vector2(.5,.5),color:0xb6bc8c,roughness:1});
 const woodland=grass.clone();woodland.color.set(0x7a8760);const water=new T.MeshStandardMaterial({color:0x536d74,metalness:.48,roughness:.22});
 for(const land of world.data.land){if(!['grass','wood','forest','meadow','water','river'].includes(land.type))continue;const mesh=polygonMesh(land.points,world,['water','river'].includes(land.type)?water:land.type==='wood'?woodland:grass,.045,['water','river'].includes(land.type));if(mesh)scene.add(mesh)}
 world.parking=(await (await fetch('/assets/parking.json')).json()).filter(lot=>lot.points.every(p=>p[0]>=world.data.bounds[0]&&p[0]<=world.data.bounds[2]&&p[1]>=world.data.bounds[1]&&p[1]<=world.data.bounds[3]));const parkingGrid=new Map();for(const lot of world.parking){const xs=lot.points.map(p=>p[0]),ys=lot.points.map(p=>p[1]);for(let x=Math.floor(Math.min(...xs)/100);x<=Math.floor(Math.max(...xs)/100);x++)for(let y=Math.floor(Math.min(...ys)/100);y<=Math.floor(Math.max(...ys)/100);y++){const key=x+','+y;if(!parkingGrid.has(key))parkingGrid.set(key,[]);parkingGrid.get(key).push(lot)}}world.parkingAt=(x,y)=>(parkingGrid.get(Math.floor(x/100)+','+Math.floor(y/100))||[]).some(p=>insidePolygon(x,y,p.points));const pavement=new T.MeshStandardMaterial({color:0x414749,roughness:.95});
 for(const lot of world.parking){const mesh=polygonMesh(lot.points,world,pavement,.065);if(mesh)scene.add(mesh)}

 // Connect mapped homes to their nearest local street, retaining real setbacks.
 const drivewayVertices=[],drivewayUV=[];
 for(const b of world.data.buildings){if(!b.roofFaces)continue;const p=b.points,cx=p.reduce((a,q)=>a+q[0],0)/p.length,cy=p.reduce((a,q)=>a+q[1],0)/p.length;const road=world.roadAt(cx,-cy);if(!road||!['residential','unclassified','living_street','service'].includes(road.road.class)||road.distance>65||road.distance<8)continue;
 const a=road.s.a,q=road.s.b,rx=a[0]+(q[0]-a[0])*road.t,ry=a[1]+(q[1]-a[1])*road.t,dx=cx-rx,dy=cy-ry,len=Math.hypot(dx,dy),ux=dx/len,uy=dy/len;let edge=len;
 for(let d=road.road.width/2+1;d<len;d+=.4){if(insidePolygon(rx+ux*d,ry+uy*d,p)){edge=d;break}}
 const start=road.road.width/2-.1,end=Math.max(start,edge-.25),width=3.4,pts=[];
 for(const [d,side] of [[start,-1],[start,1],[end,-1],[end,1]]){const t=(d-start)/Math.max(1,end-start);pts.push([rx+ux*d-uy*side*width/2,road.height*(1-t)+(b.base+.08)*t+.025,-ry-uy*d-ux*side*width/2])}
 for(const i of [0,2,1,1,2,3]){drivewayVertices.push(...pts[i]);drivewayUV.push(pts[i][0]/3,pts[i][2]/3)}
 }
 const dg=new T.BufferGeometry();dg.setAttribute('position',new T.Float32BufferAttribute(drivewayVertices,3));dg.setAttribute('uv',new T.Float32BufferAttribute(drivewayUV,2));dg.computeVertexNormals();const dm=new T.Mesh(dg,new T.MeshStandardMaterial({color:0xa7a49a,roughness:.94,side:T.DoubleSide}));dm.receiveShadow=true;scene.add(dm);
 if(world.data.frontages!==false){const foreground=(await loader.loadAsync('/assets/frontages.glb')).scene;foreground.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true}});scene.add(foreground)}
 // Grass shoulders are tessellated and clipped at mapped roads and parking areas.
 const v=[],uv=[];for(const road of world.data.roads){if(!['trunk','primary','motorway','motorway_link'].includes(road.class)||road.bridge)continue;for(let i=1;i<road.points.length;i++){const a=road.points[i-1],b=road.points[i],dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy);if(len<1)continue;for(let at=0;at<len;at+=5)for(const side of [-1,1]){const end=Math.min(at+5,len),near=road.width/2+1.5,far=near+(road.class==='motorway'?9:5);const center=[a[0]+dx*(at+end)/2/len-dy/len*side*(near+far)/2,a[1]+dy*(at+end)/2/len+dx/len*side*(near+far)/2];const r=world.roadAt(center[0],-center[1]);if(r&&r.distance<r.road.width/2+1||world.collision(center[0],-center[1])||world.parkingAt(...center))continue;const pts=[];for(const [d,off] of [[at,near],[end,near],[at,far],[end,far]]){const x=a[0]+dx*d/len-dy/len*side*off,y=a[1]+dy*d/len+dx/len*side*off;pts.push([x,world.elevation(x,-y)+.08,-y])}for(const ix of side>0?[0,1,2,1,3,2]:[0,2,1,1,2,3]){v.push(...pts[ix]);uv.push(pts[ix][0]/3,-pts[ix][2]/3)}}}}
 const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(v,3));g.setAttribute('uv',new T.Float32BufferAttribute(uv,2));g.computeVertexNormals();const verges=new T.Mesh(g,grass);verges.receiveShadow=true;scene.add(verges);
}
export async function landscapeTrees(scene,world,loader){
 let seed=819;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296};const locations=[];const treeCells=new Set();
 function plant(x,y,height){const b=world.data.bounds||[-1670,-1670,1670,1670];if(x<b[0]||x>b[2]||y<b[1]||y>b[3]||world.collision(x,-y))return;const r=world.roadAt(x,-y);if(r&&r.distance<r.road.width/2+5)return;if(world.parkingAt(x,y))return;const key=Math.floor(x/8)+','+Math.floor(y/8);if(treeCells.has(key))return;treeCells.add(key);locations.push({x,y:world.elevation(x,-y),z:-y,height,angle:random()*Math.PI*2,tint:random()})}
 for(const land of world.data.land.filter(l=>['wood','forest','grass','residential'].includes(l.type))){const xs=land.points.map(p=>p[0]),ys=land.points.map(p=>p[1]),minX=Math.max(world.data.bounds[0],Math.min(...xs)),maxX=Math.min(world.data.bounds[2],Math.max(...xs)),minY=Math.max(world.data.bounds[1],Math.min(...ys)),maxY=Math.min(world.data.bounds[3],Math.max(...ys));if(maxX<=minX||maxY<=minY)continue;const wooded=['wood','forest'].includes(land.type);const count=Math.min(600,Math.floor((maxX-minX)*(maxY-minY)/(wooded?115:1200)));for(let k=0;k<count;k++){const x=minX+random()*(maxX-minX),y=minY+random()*(maxY-minY);if(insidePolygon(x,y,land.points))plant(x,y,wooded?8+random()*5:6+random()*4)}}
 for(const road of world.data.roads.filter(r=>['trunk','primary','secondary','motorway'].includes(r.class)&&!r.bridge)){for(let i=1;i<road.points.length;i++){const a=road.points[i-1],b=road.points[i],dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy);for(let at=12+random()*15;at<len;at+=28+random()*18)for(const side of [-1,1]){if(random()<.25)continue;const offset=road.width/2+(road.class==='motorway'?14:10)+random()*6;plant(a[0]+dx*at/len-dy/len*side*offset,a[1]+dy*at/len+dx/len*side*offset,7+random()*4)}}}
 // Sparse yard trees fill the residential canopy between mapped homes and streets.
 for(const b of world.data.buildings){if(!b.roofFaces||random()>.42)continue;const p=b.points,x=p.reduce((s,q)=>s+q[0],0)/p.length,y=p.reduce((s,q)=>s+q[1],0)/p.length,r=world.roadAt(x,-y);if(!r||r.distance<18||r.distance>70||r.road.class!=='residential')continue;const a=r.s.a,c=r.s.b,rx=a[0]+(c[0]-a[0])*r.t,ry=a[1]+(c[1]-a[1])*r.t;plant(rx+(x-rx)*.60+Math.cos(r.heading)*5,ry+(y-ry)*.60-Math.sin(r.heading)*5,5.5+random()*3)}
 const treeMap=await new T.TextureLoader().loadAsync('/assets/tree-impostor.png');treeMap.colorSpace=T.SRGBColorSpace;
 // Draw only a small nearby pool, rather than the entire forest or detailed tree meshes.
 const capacity=256,geo=new T.PlaneGeometry(1,1),mat=new T.MeshBasicMaterial({map:treeMap,alphaTest:.42,alphaToCoverage:true,side:T.DoubleSide,color:0x98a282});
 const billboards=new T.InstancedMesh(geo,mat,capacity);billboards.count=0;billboards.frustumCulled=false;scene.add(billboards);
 const dummy=new T.Object3D(),color=new T.Color();let lastX=Infinity,lastZ=Infinity;let nearby=[];
 return camera=>{const x=camera.position.x,z=camera.position.z;
  if(Math.hypot(x-lastX,z-lastZ)>=8){lastX=x;lastZ=z;
  nearby=locations.map(p=>({p,d:Math.hypot(p.x-x,p.z-z)})).filter(o=>o.d<450).sort((a,b)=>a.d-b.d).slice(0,capacity);
  }
  billboards.count=nearby.length;
  nearby.forEach(({p},i)=>{dummy.position.set(p.x,p.y+p.height*.48,p.z);dummy.rotation.set(0,Math.atan2(x-p.x,z-p.z),0);dummy.scale.set(p.height*.85,p.height,1);dummy.updateMatrix();billboards.setMatrixAt(i,dummy.matrix);billboards.setColorAt(i,color.setHSL(.21+p.tint*.025,.12,.70+p.tint*.17))});
  billboards.instanceMatrix.needsUpdate=true;if(billboards.instanceColor)billboards.instanceColor.needsUpdate=true;
 };
}

export function streetLighting(scene,world){const lights=[];for(let i=0;i<2;i++){const s=new T.SpotLight(0xffd59c,0,28,.94,.75,1.7);s.target=new T.Object3D();scene.add(s,s.target);lights.push(s)}return p=>{const closest=(world.lamps||[]).map(l=>({l,d:Math.hypot(l.x-p.x,l.z-p.z)})).filter(o=>o.d<130).sort((a,b)=>a.d-b.d).slice(0,2);lights.forEach((s,i)=>{const l=closest[i]?.l;s.intensity=l?(scene.userData.dusk?240:35):0;if(l){s.position.set(l.x-Math.sin(l.rot)*2,l.y+8.8,l.z-Math.cos(l.rot)*2);s.target.position.set(s.position.x,l.y,s.position.z);s.target.updateMatrixWorld()}})}}

export function parkedVehicles(scene,world,asset){
 const positions=[];const linePositions=[];const line=(x,z,dx,dz)=>linePositions.push(x,world.elevation(x,z)+.09,z,x+dx,world.elevation(x+dx,z+dz)+.09,z+dz);
 for(const lot of world.parking){if(lot.area<300||lot.area>30000)continue;const p=lot.points,cx=p.reduce((s,q)=>s+q[0],0)/p.length,cy=p.reduce((s,q)=>s+q[1],0)/p.length;if(Math.abs(cy+420)>360)continue;
 const minX=Math.min(...p.map(v=>v[0])),maxX=Math.max(...p.map(v=>v[0])),minY=Math.min(...p.map(v=>v[1])),maxY=Math.max(...p.map(v=>v[1]));
 for(let y=minY+6;y<maxY-4;y+=16)for(let x=minX+4;x<maxX-3;x+=2.9){if(![[x-1.4,y-2.8],[x+1.4,y+2.8]].every(q=>insidePolygon(...q,p))||world.collision(x,-y))continue;const r=world.roadAt(x,-y);if(r&&r.distance<r.road.width/2+3)continue;line(x-1.4,-y-2.7,0,5.4);line(x-1.4,-y-2.7,2.8,0);if(positions.length<24&&Math.sin(x*.23+y*.4)>.35)positions.push([x,world.elevation(x,-y)+.07,-y]);}}
 const geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.Float32BufferAttribute(linePositions,3));const stripes=new T.LineSegments(geometry,new T.LineBasicMaterial({color:0xb9b7a6}));scene.add(stripes);
 asset.updateMatrixWorld(true);const dummy=new T.Object3D(),matrix=new T.Matrix4();asset.traverse(o=>{if(!o.isMesh)return;const material=o.material.clone();const inst=new T.InstancedMesh(o.geometry,material,positions.length);positions.forEach((p,i)=>{dummy.position.set(...p);dummy.rotation.set(0,i%2?Math.PI:0,0);dummy.updateMatrix();matrix.multiplyMatrices(dummy.matrix,o.matrixWorld);inst.setMatrixAt(i,matrix);if(material.name.toLowerCase().includes('paint'))inst.setColorAt(i,new T.Color([0x637b8b,0xe1ded3,0x35383b,0x93443c,0x939695][i%5]))});inst.castShadow=true;inst.receiveShadow=true;scene.add(inst)});
}
