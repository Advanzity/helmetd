// Query the union of road ribbons. The nearest centreline can belong to a
// narrow side street even when a wider crossing road covers the same point.
const envelopes=new WeakMap();
function ribbonEdges(road,clearance){
 const half=road.width/2+clearance,offset=road.pavementOffset||0;
 return road.points.map((p,i)=>{
  const a=road.points[Math.max(0,i-1)],b=road.points[Math.min(road.points.length-1,i+1)];
  let dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy)||1;dx/=len;dy/=len;
  const next=road.points[Math.min(road.points.length-1,i+1)],prev=road.points[Math.max(0,i-1)];
  const ex=i<road.points.length-1?next[0]-p[0]:p[0]-prev[0],ey=i<road.points.length-1?next[1]-p[1]:p[1]-prev[1],el=Math.hypot(ex,ey)||1;
  const miter=Math.min(1.7,1/Math.max(.59,Math.abs(dx*ex/el+dy*ey/el)));
  return [-1,1].map(side=>{const o=(offset+side*half)*miter;return [p[0]-dy*o,p[1]+dx*o]});
 });
}
const inTriangle=(p,a,b,c)=>{
 if(Math.abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))<1e-8)return false;
 const cross=(u,v)=>(v[0]-u[0])*(p[1]-u[1])-(v[1]-u[1])*(p[0]-u[0]);
 const d=[cross(a,b),cross(b,c),cross(c,a)];return !(d.some(v=>v<-.00001)&&d.some(v=>v>.00001));
};

export function coversPavement(world,x,z,height=0,clearance=.3,includeRoad=null){
 if(!world.grid)return Boolean(world.ground?.(x,z,height).onRoad);
 const p=[x,-z];
 for(const s of world.grid.get(Math.floor(x/50)+','+Math.floor(-z/50))||[]){
  if(includeRoad&&!includeRoad(s.road))continue;
  if(s.road.bridge&&Math.abs((s.a[2]+s.b[2])/2-height)>2)continue;
  let cache=envelopes.get(s.road);
  if(!cache||cache.clearance!==clearance){cache={clearance,edges:ribbonEdges(s.road,clearance)};envelopes.set(s.road,cache)}
  const a=cache.edges[s.index-1],b=cache.edges[s.index];
  if(inTriangle(p,a[0],b[0],a[1])||inTriangle(p,b[0],b[1],a[1]))return true;
 }
 return false;
}

export function clearSignalBase(world,pole){
 if(world.ground?.(pole.x,pole.z,pole.y).onRoad||coversPavement(world,pole.x,pole.z,pole.y))return false;
 // Include the base plate's footprint, rather than checking only its centre.
 for(const [dx,dz] of [[0,0],[.23,0],[-.23,0],[0,.23],[0,-.23]])if(world.collision?.(pole.x+dx,pole.z+dz))return false;
 return true;
}
