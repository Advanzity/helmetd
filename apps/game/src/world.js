import {roadFrames,prepareRoadFrames,roadSection} from './road-frame.js';
import {prepareRoadWidths} from './road-widths.js';
import {addBuildings} from './buildings.js';
import {clipGroundAtRoads} from './ground-geometry.js';
import {laneCenter} from './road-layout.js';
import * as T from 'three';import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';
export class World{
 constructor(data){prepareRoadWidths(data.roads);prepareRoadFrames(data.roads);this.data=data;this.grid=new Map();this.nodeDegree=new Map();this.segments=[];this.buildingGrid=new Map();this.circleGrid=new Map();for(const c of data.turningCircles||[]){for(let x=Math.floor((c.point[0]-c.radius)/50);x<=Math.floor((c.point[0]+c.radius)/50);x++)for(let y=Math.floor((c.point[1]-c.radius)/50);y<=Math.floor((c.point[1]+c.radius)/50);y++){const k=x+','+y;if(!this.circleGrid.has(k))this.circleGrid.set(k,[]);this.circleGrid.get(k).push(c)}}for(const road of data.roads){road.bounds=[Math.min(...road.points.map(p=>p[0])),Math.min(...road.points.map(p=>p[1])),Math.max(...road.points.map(p=>p[0])),Math.max(...road.points.map(p=>p[1]))];road.length=0;road.distances=[0];for(let i=1;i<road.points.length;i++){const a=road.points[i-1],b=road.points[i],len=Math.hypot(b[0]-a[0],b[1]-a[1]);if(len<.01)continue;const s={a,b,len,road,index:i};for(const node of [road.nodeIds[i-1],road.nodeIds[i]])this.nodeDegree.set(node,(this.nodeDegree.get(node)||0)+1);this.segments.push(s);road.length+=len;road.distances.push(road.length);for(let x=Math.floor((Math.min(a[0],b[0])-Math.max(road.width,40))/50);x<=Math.floor((Math.max(a[0],b[0])+Math.max(road.width,40))/50);x++)for(let y=Math.floor((Math.min(a[1],b[1])-Math.max(road.width,40))/50);y<=Math.floor((Math.max(a[1],b[1])+Math.max(road.width,40))/50);y++){const key=x+','+y;if(!this.grid.has(key))this.grid.set(key,[]);this.grid.get(key).push(s)}}}
 for(const b of data.buildings){const xs=b.points.map(p=>p[0]),ys=b.points.map(p=>p[1]);b.bounds=[Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)];for(let x=Math.floor(b.bounds[0]/50);x<=Math.floor(b.bounds[2]/50);x++)for(let y=Math.floor(b.bounds[1]/50);y<=Math.floor(b.bounds[3]/50);y++){const k=x+','+y;if(!this.buildingGrid.has(k))this.buildingGrid.set(k,[]);this.buildingGrid.get(k).push(b)}}
 }
 elevation(x,z){if((Math.abs(x)>1700||Math.abs(z)>1700)&&this.data.outerTerrain){const d=this.data.outerTerrain,b=d.bounds,u=T.MathUtils.clamp((x-b[0])/(b[2]-b[0])*(d.nx-1),0,d.nx-1.001),v=T.MathUtils.clamp((-z-b[1])/(b[3]-b[1])*(d.ny-1),0,d.ny-1.001),i=Math.floor(u),j=Math.floor(v),a=u-i,c=v-j,h=d.heights,n=d.nx;return h[j*n+i]*(1-a)*(1-c)+h[j*n+i+1]*a*(1-c)+h[(j+1)*n+i]*(1-a)*c+h[(j+1)*n+i+1]*a*c}const d=this.data,n=d.resolution,u=T.MathUtils.clamp((x/d.size+.5)*(n-1),0,n-1.001),v=T.MathUtils.clamp((-z/d.size+.5)*(n-1),0,n-1.001),i=Math.floor(u),j=Math.floor(v),a=u-i,b=v-j,h=d.heights;return h[j*n+i]*(1-a)*(1-b)+h[j*n+i+1]*a*(1-b)+h[(j+1)*n+i]*(1-a)*b+h[(j+1)*n+i+1]*a*b}
 roadAt(x,z,previousHeight=null){const y=-z;let best=null,score=Infinity;for(const s of this.grid.get(Math.floor(x/50)+','+Math.floor(y/50))||[]){const {a,b,len,road}=s;const t=T.MathUtils.clamp(((x-a[0])*(b[0]-a[0])+(y-a[1])*(b[1]-a[1]))/(len*len),0,1),xx=a[0]+(b[0]-a[0])*t,yy=a[1]+(b[1]-a[1])*t,dist=Math.hypot(x-xx,y-yy),h=a[2]+(b[2]-a[2])*t;const value=dist+(previousHeight===null?0:Math.max(0,Math.abs(h-previousHeight)-2)*4);if(value<score){score=value;best={distance:dist,signedDistance:(x-xx)*(-(b[1]-a[1])/len)+(y-yy)*((b[0]-a[0])/len),height:h,surface:road.surface==='gravel'?'gravel':'asphalt',road,s,t,heading:Math.atan2(b[0]-a[0],b[1]-a[1])}}}return best}
 ground(x,z,previousHeight=null){for(const c of this.circleGrid.get(Math.floor(x/50)+','+Math.floor(-z/50))||[]){if(Math.hypot(x-c.point[0],-z-c.point[1])<c.radius)return {height:this.elevation(c.point[0],-c.point[1])+.06,surface:'asphalt',onRoad:true,road:null}}const r=this.roadAt(x,z,previousHeight);if(r&&Math.abs(r.signedDistance-(r.road.pavementOffset||0))<r.road.width/2+.8&&r.distance<r.road.width/2+1)return {...r,onRoad:true};return {height:this.elevation(x,z),surface:r&&r.distance<r.road.width/2+3?'gravel':'grass',onRoad:false,road:r?.road}}
 collision(x,z){const y=-z;for(const b of this.buildingGrid.get(Math.floor(x/50)+','+Math.floor(y/50))||[]){if(x<b.bounds[0]-.35||x>b.bounds[2]+.35||y<b.bounds[1]-.35||y>b.bounds[3]+.35)continue;let inside=false;const p=b.points;for(let i=0,j=p.length-1;i<p.length;j=i++){if(((p[i][1]>y)!=(p[j][1]>y))&&(x<(p[j][0]-p[i][0])*(y-p[i][1])/(p[j][1]-p[i][1])+p[i][0]))inside=!inside}if(inside)return true}return false}
 async build(scene,loader){
 const texture=async(n,srgb=true)=>{const t=await new T.TextureLoader().loadAsync('/assets/'+n);t.wrapS=t.wrapT=T.RepeatWrapping;t.anisotropy=8;if(srgb)t.colorSpace=T.SRGBColorSpace;return t};
 const surface=async name=>{
  const [map,normalMap,roughnessMap]=await Promise.all([texture(name+'-color.jpg'),texture(name+'-normal.jpg',false),texture(name+'-roughness.jpg',false)]);
  return new T.MeshStandardMaterial({map,normalMap,roughnessMap,normalScale:new T.Vector2(.22,.22),color:0xb4b8ba,roughness:1});
 };
 const [asphalt,concrete]=await Promise.all([surface('asphalt'),surface('concrete')]);
 concrete.color.set(0xb4b6b3);const shoulder=asphalt.clone();shoulder.color.set(0x858177);
 const n=this.data.resolution,d=this.data,verts=[],uv=[],indices=[],colors=[];
 for(let j=0;j<n;j++)for(let i=0;i<n;i++){const x=(i/(n-1)-.5)*d.size,z=-(j/(n-1)-.5)*d.size;let h=d.heights[j*n+i];const road=this.roadAt(x,z);if(road&&!road.road.bridge){const a=T.MathUtils.clamp((road.distance-road.road.width/2)/5,0,1);h=h*a+(road.height-.09)*(1-a)}verts.push(x,h,z);uv.push(i/(n-1),j/(n-1));const c=new T.Color().setHSL(.19+Math.sin(x*.03)*.008,.19,.24+Math.sin(x*.013+z*.027)*.025);colors.push(c.r,c.g,c.b);if(i<n-1&&j<n-1){const a=j*n+i;indices.push(a,a+1,a+n,a+1,a+n+1,a+n)}}
 let g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(verts,3));g.setAttribute('uv',new T.Float32BufferAttribute(uv,2));g.setIndex(indices);g.computeVertexNormals();
 g=carveGroundGeometry(this,g,{margin:.6});let terrainMaterial;
 if(this.data.aerialTexture===false){
  // Use the same world-space grass scale as mapped land, including gaps between parcels.
  const positions=g.getAttribute('position'),groundUV=g.getAttribute('uv');
  for(let i=0;i<positions.count;i++)groundUV.setXY(i,positions.getX(i)/3,-positions.getZ(i)/3);
  const [map,normalMap,roughnessMap]=await Promise.all([texture('grass-color.jpg'),texture('grass-normal.jpg',false),texture('grass-roughness.jpg',false)]);
  terrainMaterial=new T.MeshStandardMaterial({map,normalMap,roughnessMap,normalScale:new T.Vector2(.5,.5),color:0xb6bc8c,roughness:1,side:T.DoubleSide});
 }else{const aerial=await texture('aerial.jpg');aerial.wrapS=aerial.wrapT=T.ClampToEdgeWrapping;terrainMaterial=new T.MeshStandardMaterial({map:aerial,roughness:1,color:0x92998b,side:T.DoubleSide})}
 const terrain=new T.Mesh(g,terrainMaterial);terrain.receiveShadow=true;scene.add(terrain);
 if(this.data.simpleBuildings&&this.data.buildings.length)this.updateSimpleBuildings=await addBuildings(scene,this);
 const bounds=this.data.bounds;if(bounds&&this.data.outerTerrain){const geo=outerTerrainGeometry(this);const grass=await texture('grass-color.jpg');addTerrainTiles(scene,geo,new T.MeshStandardMaterial({map:grass,color:0x9a9d76,roughness:1}));}

 const groups=[[],[],[],[]];const stripe=[[],[]];const curbs=[],walks=[];
 const quad=roadStrip;for(const road of this.data.roads){groups[2].push(roadRibbon(road.points,road.renderWidths?.map(w=>w+1.2)||road.width+1.2,road.pavementOffset||0,-.045,road.renderFrames));const pavement=roadRibbon(road.points,road.renderWidths||road.width,road.pavementOffset||0,0,road.renderFrames);groups[road.surface==='concrete'?1:0].push(road.surface==='concrete'&&!road.bridge?carveGroundGeometry(this,pavement,{excludeRoad:road,matchHeight:true,roadFilter:r=>r.surface!=='concrete'}):pavement);}
 for(const s of this.segments){const {a,b,len,road}=s;
 const markStart=this.nodeDegree.get(road.nodeIds[s.index-1])>2?Math.min(8,len*.4):0,markEnd=this.nodeDegree.get(road.nodeIds[s.index])>2?Math.min(8,len*.4):0,markA=a.map((v,k)=>v+(b[k]-v)*markStart/len),markB=b.map((v,k)=>v-(b[k]-a[k])*markEnd/len);
 if(road.curb&&road.class!=='service'){const start=this.nodeDegree.get(road.nodeIds[s.index-1])>2?Math.min(8,len*.4):0,end=this.nodeDegree.get(road.nodeIds[s.index])>2?Math.min(8,len*.4):0,pa=a.map((v,k)=>v+(b[k]-v)*start/len),pb=b.map((v,k)=>v-(b[k]-a[k])*end/len);for(const side of [-1,1]){curbs.push(carveGroundGeometry(this,curbRibbon([pa,pb],side*(road.width/2-.10)),{excludeRoad:road,matchHeight:true}));if(['residential','tertiary','unclassified'].includes(road.class))walks.push(carveGroundGeometry(this,roadRibbon([pa,pb],1.52,side*(road.width/2+2.25),.12),{matchHeight:true}))}}
 if(['service','residential','living_street'].includes(road.class))continue;
 const laneWidth=road.laneWidth||3.35,usable=road.lanes*laneWidth;
 for(const edge of [-1,1]){const wa=road.renderWidths?.[s.index-1]||road.width,wb=road.renderWidths?.[s.index]||road.width;const startWidth=wa+(wb-wa)*markStart/len,endWidth=wb-(wb-wa)*markEnd/len;const q=roadPaint(road,s.index,markStart/len,1-markEnd/len,.12,(road.pavementOffset||0)+edge*(startWidth-1)/2,(road.pavementOffset||0)+edge*(endWidth-1)/2);if(q)stripe[road.oneway&&edge<0?1:0].push(q)}
 const medianA=road.medianWidths?.[s.index-1]??(road.lanes%2?laneWidth/2:.1),medianB=road.medianWidths?.[s.index]??(road.lanes%2?laneWidth/2:.1);
 const median=t=>medianA+(medianB-medianA)*t;
 if(!road.oneway)for(const side of [-1,1])stripe[1].push(roadPaint(road,s.index,markStart/len,1-markEnd/len,.10,side*median(markStart/len),side*median(1-markEnd/len),.021));
 const dividers=road.oneway?Array.from({length:Math.max(0,road.lanes-1)},(_,i)=>({offset:-usable/2+(i+1)*laneWidth})):Array.from({length:Math.max(0,Math.floor(road.lanes/2)-1)},(_,i)=>i+1).flatMap(lane=>[-1,1].map(side=>({lane,side})));
 for(const divider of dividers)for(let at=markStart-((road.distances[s.index-1]+markStart)%12);at<len-markEnd;at+=12){
  const end=Math.min(at+3,len-markEnd);if(end<=markStart)continue;const ta=Math.max(at,markStart)/len,tb=end/len;
  const offset=t=>divider.offset??divider.side*(Math.max(0,median(t)-.1)/(laneWidth/2-.1)*(laneWidth/2)+divider.lane*laneWidth);
  stripe[0].push(roadPaint(road,s.index,ta,tb,.12,offset(ta),offset(tb)));
 }

 }
 addTiles(scene,curbs,concrete);addTiles(scene,walks,concrete);
 const circleMeshes=[];for(const c of this.data.turningCircles||[]){const [x,y]=c.point,h=this.elevation(x,-y)+.06,vertices=[x,h,-y],indices=[],uv=[.5,.5];for(let i=0;i<=64;i++){const a=i/64*Math.PI*2;vertices.push(x+Math.cos(a)*c.radius,h,-y-Math.sin(a)*c.radius);uv.push(Math.cos(a)*c.radius/5,Math.sin(a)*c.radius/5);if(i)indices.push(0,i,i+1)}const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(vertices,3));g.setAttribute('uv',new T.Float32BufferAttribute(uv,2));g.setIndex(indices);g.computeVertexNormals();circleMeshes.push(g)}if(circleMeshes.length){const mesh=new T.Mesh(mergeGeometries(circleMeshes),concrete);mesh.receiveShadow=true;scene.add(mesh);circleMeshes.forEach(g=>g.dispose())}
 const mats=[asphalt,concrete,shoulder];groups.forEach((list,i)=>{if(!list.length)return;addTiles(scene,list,mats[i])});stripe.forEach((list,i)=>{if(!list.length)return;addTiles(scene,list,new T.MeshStandardMaterial({color:i?0xcbb361:0xdcdad0,roughness:.88,side:T.DoubleSide,polygonOffset:true,polygonOffsetFactor:-1,polygonOffsetUnits:-2}))});
 const [brickMap,brickNormal,brickRough]=await Promise.all([texture('masonry-color.jpg'),texture('masonry-normal.jpg',false),texture('masonry-roughness.jpg',false)]);
 for(const t of [brickMap,brickNormal,brickRough])t.repeat.set(1.6,1.6);
 this.buildingManifest=this.data.buildingTiles??await (await fetch('/assets/building-tiles.json')).json();this.loadedBuildingTiles=new Map();let loading=false,lastCheck=0;
 this.updateBuildings=async(p,force=false)=>{this.updateSimpleBuildings?.(p);if(loading||!force&&performance.now()-lastCheck<1000)return;lastCheck=performance.now();loading=true;try{const wanted=this.buildingManifest.filter(t=>Math.hypot(t.x-p.x,-t.y-p.z)<1000).sort((a,b)=>Math.hypot(a.x-p.x,-a.y-p.z)-Math.hypot(b.x-p.x,-b.y-p.z));for(const tile of wanted){if(this.loadedBuildingTiles.has(tile.file))continue;const buildings=(await loader.loadAsync('/assets/building-tiles/'+tile.file)).scene;
buildings.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;for(const m of (Array.isArray(o.material)?o.material:[o.material])){if(m.name==='Masonry brick'){m.map=brickMap;m.normalMap=brickNormal;m.roughnessMap=brickRough;m.normalScale=new T.Vector2(.65,.65);m.color.set(0xb5a99a);m.roughness=1;m.needsUpdate=true}if(m.map)m.map.anisotropy=8}}});scene.add(buildings);this.loadedBuildingTiles.set(tile.file,buildings)}for(const tile of this.buildingManifest){const object=this.loadedBuildingTiles.get(tile.file);if(object){const distance=Math.hypot(tile.x-p.x,-tile.y-p.z);object.visible=distance<1100;if(distance>1600){scene.remove(object);object.traverse(o=>{if(o.isMesh){o.geometry.dispose();for(const m of (Array.isArray(o.material)?o.material:[o.material]))m.dispose()}});this.loadedBuildingTiles.delete(tile.file)}}}}catch(error){console.warn('Building tile load failed; retrying',error)}finally{loading=false}};
 await this.updateBuildings(this.spawn(),true);
 }
 spawn(kind=0){
 const business=this.data.businesses?.[kind-10];
 if(business){
  let best=null;
  for(const {a,b,len,road} of this.segments){
   if(road.name!==business.street)continue;
   const dx=b[0]-a[0],dy=b[1]-a[1],t=T.MathUtils.clamp(((business.point[0]-a[0])*dx+(business.point[1]-a[1])*dy)/(len*len),0,1),x=a[0]+dx*t,y=a[1]+dy*t,distance=Math.hypot(x-business.point[0],y-business.point[1]);
   if(!best||distance<best.distance){const heading=Math.atan2(dx,dy),offset=laneCenter(road);best={distance,x:x+Math.cos(heading)*offset,z:-y+Math.sin(heading)*offset,y:a[2]+(b[2]-a[2])*t,heading}}
  }
  if(best)return best;
 }
 if(kind===8||kind===9){
  const name=kind===8?'Van Dyke Avenue':'25 Mile Road',target=kind===8?[-652.58,7647.45]:[-687.58,7682.45];
  let best=null;
  for(const segment of this.segments){if(segment.road.name!==name)continue;let {a,b,len,road}=segment;
   if(!road.oneway&&(kind===8?b[1]<a[1]:b[0]<a[0]))[a,b]=[b,a];
   const t=T.MathUtils.clamp(((target[0]-a[0])*(b[0]-a[0])+(target[1]-a[1])*(b[1]-a[1]))/(len*len),0,1),x=a[0]+(b[0]-a[0])*t,y=a[1]+(b[1]-a[1])*t,distance=Math.hypot(x-target[0],y-target[1]);
   if(!best||distance<best.distance){const heading=Math.atan2(b[0]-a[0],b[1]-a[1]),offset=laneCenter(road);best={distance,x:x+Math.cos(heading)*offset,z:-y+Math.sin(heading)*offset,y:a[2]+(b[2]-a[2])*t,heading}}
  }
  if(best)return best;
 }
 const routeName=kind===0?this.data.primaryRoadName:kind===1?this.data.freewayName:null;if(routeName){let closest=null;for(const segment of this.segments){if(segment.road.name!==routeName)continue;const {a,b,len,road}=segment,dx=b[0]-a[0],dy=b[1]-a[1],t=T.MathUtils.clamp(-(a[0]*dx+a[1]*dy)/(len*len),0,1),x=a[0]+dx*t,y=a[1]+dy*t,distance=Math.hypot(x,y);if(!closest||distance<closest.distance)closest={a,b,road,t,x,y,distance}}if(closest){const {a,b,road,t,x,y}=closest,heading=Math.atan2(b[0]-a[0],b[1]-a[1]),offset=laneCenter(road);return {x:x+Math.sin(heading)*12+Math.cos(heading)*offset,z:-y-Math.cos(heading)*12+Math.sin(heading)*offset,y:a[2]+(b[2]-a[2])*t,heading}}}
 const roads=this.data.roads.filter(r=>kind===4?r.name==='Althea Street':kind===5?/Dequindre/i.test(r.name):kind===6?/Hayes Road/i.test(r.name):kind===7?/Shelby Road/i.test(r.name):kind===2?/15 Mile/i.test(r.name):kind===3?/25 Mile/i.test(r.name):kind===1?r.class==='motorway'&&r.name.includes('Columbus')&&r.points.at(-1)[1]>r.points[0][1]:r.name==='Hall Road');const selected=roads.filter(r=>r.length>90).sort((a,b)=>{const c=r=>kind>=4?Math.abs(r.points[0][1]-4800):kind===1?Math.abs(r.points[0][0]-950)+Math.abs(r.points[0][1]-650):Math.abs(r.points[0][0])+Math.abs(r.points[0][1]+440);return c(a)-c(b)})[0]||roads[0];const a=selected.points[0],b=selected.points[1],heading=Math.atan2(b[0]-a[0],b[1]-a[1]);const laneOffset=laneCenter(selected);return {x:a[0]+Math.sin(heading)*12+Math.cos(heading)*laneOffset,z:-a[1]-Math.cos(heading)*12+Math.sin(heading)*laneOffset,y:a[2],heading}}
}

export function roadStrip(a,b,width,offset=0,raise=0){const dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy);if(len<.01)return null;const nx=-dy/len,ny=dx/len;const v=[];for(const [p,s] of [[a,-1],[b,-1],[a,1],[b,1]])v.push(p[0]+nx*(offset+s*width/2),p[2]+raise,-p[1]-ny*(offset+s*width/2));const q=new T.BufferGeometry();q.setAttribute('position',new T.Float32BufferAttribute(v,3));q.setAttribute('uv',new T.Float32BufferAttribute([0,0,len/5,0,0,width/5,len/5,width/5],2));q.setIndex([0,1,2,1,3,2]);q.computeVertexNormals();return q}

// Shared vertices eliminate cracks at bends; capped miters avoid spikes.
export function roadRibbon(points,width,offset=0,raise=0,frames=roadFrames(points)){
 const vertices=[],uv=[],indices=[];
 for(let i=0;i<points.length;i++){const p=points[i],f=frames[i];for(const side of [-1,1]){const o=offset+side*(Array.isArray(width)?width[i]:width)/2,x=p[0]+f[0]*o,z=-p[1]-f[1]*o;vertices.push(x,p[2]+raise,z);uv.push(x/5,z/5)}if(i){const k=(i-1)*2;indices.push(k,k+2,k+1,k+2,k+3,k+1)}}
 const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(vertices,3));g.setAttribute('uv',new T.Float32BufferAttribute(uv,2));g.setIndex(indices);g.computeVertexNormals();return g;
}
export function roadPaint(road,index,start,end,width,offsetA,offsetB=offsetA,raise=.02){
 const v=[];for(const [t,o] of [[start,offsetA],[end,offsetB]])for(const side of [-1,1]){const p=roadSection(road,index,t,o+side*width/2);v.push(p[0],p[2]+raise,-p[1])}
 const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(v,3));g.setAttribute('uv',new T.Float32BufferAttribute([0,0,1,0,0,1,1,1],2));g.setIndex([0,2,1,2,3,1]);g.computeVertexNormals();return g;
}

export function curbRibbon(points,offset){const top=roadRibbon(points,.22,offset,.14),p=top.getAttribute('position'),v=Array.from(p.array),indices=Array.from(top.index.array),count=p.count;for(let i=0;i<count;i++)v.push(p.getX(i),p.getY(i)-.15,p.getZ(i));for(let i=0;i<count-2;i+=2){indices.push(i,i+count,i+2,i+2,i+count,i+count+2,i+1,i+3,i+count+1,i+3,i+count+3,i+count+1)}const geo=new T.BufferGeometry();geo.setAttribute('position',new T.Float32BufferAttribute(v,3));const uv=Array.from(top.getAttribute('uv').array);geo.setAttribute('uv',new T.Float32BufferAttribute([...uv,...uv],2));geo.setIndex(indices);geo.computeVertexNormals();top.dispose();return geo}

function addTiles(scene,list,material){const tiles=new Map();for(const g of list){g.computeBoundingBox();const c=g.boundingBox.getCenter(new T.Vector3()),key=Math.floor(c.x/300)+','+Math.floor(c.z/300);if(!tiles.has(key))tiles.set(key,[]);tiles.get(key).push(g)}for(const parts of tiles.values()){const g=mergeGeometries(parts);g.computeBoundingSphere();const mesh=new T.Mesh(g,material);mesh.receiveShadow=true;scene.add(mesh);parts.forEach(p=>p.dispose())}}

function addTerrainTiles(scene,source,material){const position=source.getAttribute('position'),normal=source.getAttribute('normal'),uv=source.getAttribute('uv'),index=source.index.array,tiles=new Map();for(let i=0;i<index.length;i+=3){const first=index[i],key=Math.floor(position.getX(first)/360)+','+Math.floor(position.getZ(first)/360);let tile=tiles.get(key);if(!tile){tile={lookup:new Map(),p:[],n:[],u:[],ix:[]};tiles.set(key,tile)}for(let j=0;j<3;j++){const id=index[i+j];if(!tile.lookup.has(id)){tile.lookup.set(id,tile.p.length/3);tile.p.push(position.getX(id),position.getY(id),position.getZ(id));tile.n.push(normal.getX(id),normal.getY(id),normal.getZ(id));tile.u.push(uv.getX(id),uv.getY(id))}tile.ix.push(tile.lookup.get(id))}}for(const t of tiles.values()){const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(t.p,3));g.setAttribute('normal',new T.Float32BufferAttribute(t.n,3));g.setAttribute('uv',new T.Float32BufferAttribute(t.u,2));g.setIndex(t.ix);g.computeBoundingSphere();const m=new T.Mesh(g,material);m.receiveShadow=true;scene.add(m)}source.dispose()}

// The aerial mesh owns the central square. Align the outer grid to its edges
// so the two surfaces never overlap or leave partially covered cells.
export function outerTerrainGeometry(world){
 const bounds=world.data.bounds,half=world.data.size/2;
 const axis=(min,max)=>{
  const count=Math.ceil((max-min)/18),values=Array.from({length:count+1},(_,i)=>min+(max-min)*i/count);
  for(const edge of [-half,half])if(edge>min&&edge<max)values.push(edge);
  return [...new Set(values)].sort((a,b)=>a-b);
 };
 const xs=axis(bounds[0],bounds[2]),ys=axis(bounds[1],bounds[3]),v=[],uv=[],ix=[],nx=xs.length;
 for(const y of ys)for(const x of xs){
  let height=world.elevation(x,-y)-.18;const road=world.roadAt(x,-y);
  if(road&&!road.road.bridge){const blend=T.MathUtils.clamp((road.distance-road.road.width/2-12)/18,0,1);height=height*blend+(road.height-.24)*(1-blend)}
  // Match the aerial mesh's boundary heights, including its road flattening.
  if((Math.abs(x)===half&&Math.abs(y)<=half)||(Math.abs(y)===half&&Math.abs(x)<=half)){
   const d=world.data,n=d.resolution,u=(x/d.size+.5)*(n-1),w=(y/d.size+.5)*(n-1),i=Math.min(Math.floor(u),n-2),j=Math.min(Math.floor(w),n-2),a=u-i,b=w-j,h=d.heights;
   height=h[j*n+i]*(1-a)*(1-b)+h[j*n+i+1]*a*(1-b)+h[(j+1)*n+i]*(1-a)*b+h[(j+1)*n+i+1]*a*b;
   if(road&&!road.road.bridge){const blend=T.MathUtils.clamp((road.distance-road.road.width/2)/5,0,1);height=height*blend+(road.height-.09)*(1-blend)}
  }
  v.push(x,height,-y);uv.push(x/8,y/8);
 }
 for(let j=0;j<ys.length-1;j++)for(let i=0;i<nx-1;i++){
  if(xs[i]>=-half&&xs[i+1]<=half&&ys[j]>=-half&&ys[j+1]<=half)continue;
  const k=j*nx+i;ix.push(k,k+1,k+nx,k+1,k+nx+1,k+nx);
 }
 const geo=new T.BufferGeometry();geo.setAttribute('position',new T.Float32BufferAttribute(v,3));geo.setAttribute('uv',new T.Float32BufferAttribute(uv,2));geo.setIndex(ix);geo.computeVertexNormals();return geo;
}

export function carveGroundGeometry(world,source,options={}){
 const p=source.getAttribute('position'),uv=source.getAttribute('uv'),n=source.getAttribute('normal'),ix=source.index?.array||Array.from({length:p.count},(_,i)=>i),v=Array.from(p.array),u=Array.from(uv.array),normals=Array.from(n.array),indices=[];
 for(let i=0;i<ix.length;i+=3){
  const triangle=Array.from(ix.slice(i,i+3),k=>[p.getX(k),-p.getZ(k),p.getY(k),uv.getX(k),uv.getY(k),n.getX(k),n.getY(k),n.getZ(k)]);
  const pieces=clipGroundAtRoads(world,triangle,options);
  if(pieces.length===1&&pieces[0]===triangle){indices.push(ix[i],ix[i+1],ix[i+2]);continue}
  for(const piece of pieces){
   const start=v.length/3;
   for(const q of piece){v.push(q[0],q[2],-q[1]);u.push(q[3],q[4]);normals.push(q[5],q[6],q[7])}
   for(let j=1;j<piece.length-1;j++)indices.push(start,start+j,start+j+1);
  }
 }
 const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(v,3));g.setAttribute('uv',new T.Float32BufferAttribute(u,2));g.setAttribute('normal',new T.Float32BufferAttribute(normals,3));g.setIndex(indices);source.dispose();return g;
}

export function roadEdgeStrip(a,b,startOffset,endOffset){
 const g=roadStrip(a,b,.12,startOffset,.018);if(!g)return null;
 const p=g.getAttribute('position'),dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy),delta=endOffset-startOffset;
 for(const i of [1,3])p.setXYZ(i,p.getX(i)-dy/len*delta,p.getY(i),p.getZ(i)-dx/len*delta);
 return g;
}
