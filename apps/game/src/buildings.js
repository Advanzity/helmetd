import {storefrontPlan,storefrontAtlas,atlasUV} from './storefronts.js';
import * as T from 'three';

const homes=new Set(['house','detached','residential','semidetached_house','terrace']);
const utility=new Set(['garage','shed','service','carport']);
const palette=[0xe0d5be,0xc9d1ce,0xd9c9b9,0xb9c4ca,0xd6d4c9,0xc5b7aa];

// Five shared materials per tile; façade details are baked into small textures.
export function buildingTiles(buildings,elevation,storefronts={plans:new Map(),shops:[]}){
 const tiles=new Map();
 for(const building of buildings){
  let points=building.points.slice();
  if(points.length>3&&Math.hypot(points[0][0]-points.at(-1)[0],points[0][1]-points.at(-1)[1])<.01)points.pop();
  if(points.length<3)continue;
  const signed=points.reduce((sum,p,i)=>{const q=points[(i+1)%points.length];return sum+p[0]*q[1]-q[0]*p[1]},0);
  if(signed<0)points.reverse();
  const x=points.reduce((sum,p)=>sum+p[0],0)/points.length,y=points.reduce((sum,p)=>sum+p[1],0)/points.length;
  const key=Math.floor(x/400)+','+Math.floor(y/400);
  if(!tiles.has(key))tiles.set(key,Array.from({length:5},()=>({positions:[],colors:[],uv:[]})));
  const buckets=tiles.get(key),house=homes.has(building.type),service=utility.has(building.type);
  let seed=0;for(const c of String(building.id??`${x},${y}`))seed=(seed*31+c.charCodeAt(0))>>>0;
  const wallColor=new T.Color(palette[seed%palette.length]);
  const storefront=storefronts.plans.get(building.id);
  const inferredHeight=storefront&&!building.heightTagged&&building.height===10&&building.type!=='office'?(seed%3===0?7.2:4.6):building.height;
  const base=building.base??elevation(x,-y),height=service?Math.min(building.height||3.2,3.5):Math.max(3,inferredHeight||7);
  const vec=(a,b)=>new T.Vector2(b[0]-a[0],b[1]-a[1]);
  const rectangular=points.length===4&&points.every((p,i)=>{const a=vec(p,points[(i+1)%4]).normalize(),b=vec(points[(i+1)%4],points[(i+2)%4]).normalize();return Math.abs(a.dot(b))<.08});
  const rise=house&&rectangular?Math.min(1.8,height*.25):0,top=base+height-rise;
  const wallMaterial=service?2:house?0:1,stories=Math.max(1,Math.round((top-base)/3));
  const triangle=(material,vertices,uv,color)=>{
   const bucket=buckets[material];
   vertices.forEach((p,i)=>{bucket.positions.push(...p);bucket.uv.push(...uv[i]);bucket.colors.push(color.r,color.g,color.b)});
  };
  const quad=(material,vertices,uv,color)=>{for(const ids of [[0,1,2],[0,2,3]])triangle(material,ids.map(i=>vertices[i]),ids.map(i=>uv[i]),color)};
  // Each featured tenant gets one bay on the wall nearest its street.
  const featuredBays=new Map();
  for(const shop of storefront?.featuredShops||[]){
   let best=null;
   points.forEach((a,i)=>{
    const b=points[(i+1)%points.length],dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy),nx=dy/length,ny=-dx/length;
    if(length<=3||nx*(storefront.target[0]-(a[0]+b[0])/2)+ny*(storefront.target[1]-(a[1]+b[1])/2)<=0)return;
    const t=T.MathUtils.clamp(((shop.point[0]-a[0])*dx+(shop.point[1]-a[1])*dy)/(length*length),0,1);
    const streetT=T.MathUtils.clamp(((storefront.target[0]-a[0])*dx+(storefront.target[1]-a[1])*dy)/(length*length),0,1);
    const distance=Math.hypot(a[0]+dx*streetT-storefront.target[0],a[1]+dy*streetT-storefront.target[1]);
    if(!best||distance<best.distance)best={edge:i,unit:Math.min(Math.ceil(length/10)-1,Math.floor(t*Math.ceil(length/10))),distance};
   });
   if(best)featuredBays.set(`${best.edge}:${best.unit}`,shop.index);
  }
  for(let i=0;i<points.length;i++){
   const a=points[i],b=points[(i+1)%points.length],length=vec(a,b).length(),bays=Math.max(1,Math.round(length/(service?5:house?3.6:4.2)));
   // Keep footprint walls facing outward after converting north to negative Z.
   const nx=(b[1]-a[1])/(length||1),ny=-(b[0]-a[0])/(length||1),mid=[(a[0]+b[0])/2,(a[1]+b[1])/2];
   const front=storefront&&length>3&&(nx*(storefront.target[0]-mid[0])+ny*(storefront.target[1]-mid[1]))>0;
   if(!front){quad(wallMaterial,[[a[0],base,-a[1]],[b[0],base,-b[1]],[b[0],top,-b[1]],[a[0],top,-a[1]]],[[0,0],[bays,0],[bays,stories],[0,stories]],wallColor);continue}
   const shopTop=Math.min(top,base+3.7),units=Math.max(1,Math.ceil(length/10)),count=storefronts.shops.length;
   const xyz=(t,h,depth=0)=>[a[0]+(b[0]-a[0])*t+nx*depth,h,-a[1]-(b[1]-a[1])*t-ny*depth];
   for(let unit=0;unit<units;unit++){
    const t0=unit/units,t1=(unit+1)/units,index=featuredBays.get(`${i}:${unit}`)??(storefront.shops.length?storefront.shops[unit%storefront.shops.length]:(seed+unit)%8);
    const face=[xyz(t0,base),xyz(t1,base),xyz(t1,shopTop),xyz(t0,shopTop)];
    quad(4,face,[[0,0],[1,0],[1,1],[0,1]].map(([u,v])=>atlasUV(index,u,v,count)),new T.Color(0xffffff));
    // Shallow canvas awnings add four triangles per shop, batched with the signs.
    const h=base+2.85,outer=base+2.55,colorUV=atlasUV(index,.02,.82,count),white=new T.Color(0xffffff);
    quad(4,[xyz(t0,h,.02),xyz(t1,h,.02),xyz(t1,outer,.72),xyz(t0,outer,.72)],Array(4).fill(colorUV),white);
    quad(4,[xyz(t0,outer,.72),xyz(t1,outer,.72),xyz(t1,outer-.13,.72),xyz(t0,outer-.13,.72)],Array(4).fill(colorUV),white);
   }
   if(top>shopTop+.05)quad(wallMaterial,[[a[0],shopTop,-a[1]],[b[0],shopTop,-b[1]],[b[0],top,-b[1]],[a[0],top,-a[1]]],[[0,0],[bays,0],[bays,Math.max(1,Math.round((top-shopTop)/3))],[0,Math.max(1,Math.round((top-shopTop)/3))]],wallColor);

  }
  const roofColor=new T.Color([0x8c8985,0x9e9185,0x858e94][seed%3]);
  const roofUV=p=>[p[0]/3,p[2]/3];
  const roofQuad=vertices=>quad(3,vertices,vertices.map(roofUV),roofColor);
  if(rise){
   // A two-plane gable adds only six roof triangles to rectangular houses.
   let [a,b,c,d]=points;if(vec(a,b).length()<vec(b,c).length())[a,b,c,d]=[b,c,d,a];
   const r0=[(a[0]+d[0])/2,top+rise,-(a[1]+d[1])/2],r1=[(b[0]+c[0])/2,top+rise,-(b[1]+c[1])/2];
   const A=[a[0],top,-a[1]],B=[b[0],top,-b[1]],C=[c[0],top,-c[1]],D=[d[0],top,-d[1]];
   roofQuad([A,B,r1,r0]);roofQuad([D,r0,r1,C]);
   triangle(wallMaterial,[A,r0,D],[[0,.95],[.5,.98],[1,.95]],wallColor);
   triangle(wallMaterial,[B,C,r1],[[0,.95],[1,.95],[.5,.98]],wallColor);
  }else{
   const contour=points.map(p=>new T.Vector2(...p));
   for(const face of T.ShapeUtils.triangulateShape(contour,[])){
    const vertices=face.map(i=>[points[i][0],top,-points[i][1]]);
    triangle(3,vertices,vertices.map(roofUV),roofColor);
   }
  }
 }
 return [...tiles.values()].map(buckets=>{
  const p=[],c=[],uv=[],g=new T.BufferGeometry();
  buckets.forEach((b,i)=>{if(!b.positions.length)return;const start=p.length/3;p.push(...b.positions);c.push(...b.colors);uv.push(...b.uv);g.addGroup(start,b.positions.length/3,i)});
  g.setAttribute('position',new T.Float32BufferAttribute(p,3));g.setAttribute('color',new T.Float32BufferAttribute(c,3));g.setAttribute('uv',new T.Float32BufferAttribute(uv,2));g.computeVertexNormals();g.computeBoundingSphere();return g;
 });
}

function facadeTexture(kind,roughness=false){
 const canvas=document.createElement('canvas');canvas.width=canvas.height=256;const c=canvas.getContext('2d');
 let seed=71;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296};
 c.fillStyle=roughness?'#ededed':kind==='home'?'#aaa49a':'#9c8270';c.fillRect(0,0,256,256);
 for(let row=0;row<32;row++)for(let col=-1;col<8;col++){
  const x=col*40+(row%2)*20,shade=Math.round(120+random()*28);
  c.fillStyle=roughness?'#e5e5e5':kind==='home'?`rgb(${shade+45},${shade+40},${shade+30})`:`rgb(${shade+22},${shade},${shade-17})`;
  c.fillRect(x,row*8,39,7);
 }
 if(kind==='utility'){
  c.fillStyle=roughness?'#bbbbbb':'#b4b7b5';c.fillRect(27,43,202,213);
  for(let y=62;y<256;y+=24){c.fillStyle=roughness?'#bbbbbb':'#818781';c.fillRect(29,y,198,2)}
  c.fillStyle=roughness?'#888888':'#374148';c.fillRect(110,159,35,5);
 }else{
  const left=kind==='home'?73:27,width=kind==='home'?110:202;
  c.fillStyle=roughness?'#dddddd':'#514f4a';c.fillRect(left-9,57,width+18,133);
  c.fillStyle=roughness?'#999999':'#e2dfd5';c.fillRect(left-5,52,width+10,129);
  const gradient=c.createLinearGradient(0,57,0,175);gradient.addColorStop(0,'#657786');gradient.addColorStop(.5,'#8b989b');gradient.addColorStop(.53,'#454e53');gradient.addColorStop(1,'#263238');
  c.fillStyle=roughness?'#353535':gradient;c.fillRect(left,57,width,118);
  c.fillStyle=roughness?'#999999':'#d8d8cf';c.fillRect(left+width/2-2,55,4,122);c.fillRect(left,113,width,4);
  c.fillStyle=roughness?'#b0b0b0':'#ece5d8';c.fillRect(left-10,180,width+20,6);
  c.fillStyle=roughness?'#ededed':'#716d64';c.fillRect(0,239,256,17);
 }
 const t=new T.CanvasTexture(canvas);t.wrapS=t.wrapT=T.RepeatWrapping;t.anisotropy=4;if(!roughness)t.colorSpace=T.SRGBColorSpace;return t;
}

export async function addBuildings(scene,world){
 const businesses=world.data.businesses||[];
 const plan=storefrontPlan(world.data,businesses);
 const materials=['home','commercial','utility'].map(kind=>new T.MeshStandardMaterial({map:facadeTexture(kind),roughnessMap:facadeTexture(kind,true),roughness:1,vertexColors:true}));
 const roof=await new T.TextureLoader().loadAsync('/assets/roof.jpg');roof.colorSpace=T.SRGBColorSpace;roof.wrapS=roof.wrapT=T.RepeatWrapping;roof.anisotropy=4;
 materials.push(new T.MeshStandardMaterial({map:roof,vertexColors:true,roughness:.94}));
 const atlas=storefrontAtlas(plan.shops);materials.push(new T.MeshStandardMaterial({map:atlas.map,roughness:.72,vertexColors:true,side:T.DoubleSide}));
 const meshes=buildingTiles(world.data.buildings,(x,z)=>world.elevation(x,z),plan).map(geometry=>{const mesh=new T.Mesh(geometry,materials);mesh.castShadow=true;mesh.receiveShadow=true;scene.add(mesh);return mesh});
 // Nearby tiles only. No individual building objects, transparent glazing, or lights.
 const update=p=>{for(const mesh of meshes){const sphere=mesh.geometry.boundingSphere;mesh.visible=Math.hypot(sphere.center.x-p.x,sphere.center.z-p.z)-sphere.radius<850}};
 update(world.spawn());return update;
}
