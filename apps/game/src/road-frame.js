// One cross-section for pavement, paint, and ground clipping.
export function roadFrames(points){
 const direction=(a,b)=>{const x=b[0]-a[0],y=b[1]-a[1],l=Math.hypot(x,y)||1;return [x/l,y/l]};
 return points.map((p,i)=>{
  const a=direction(points[Math.max(0,i-1)],p),b=direction(p,points[Math.min(points.length-1,i+1)]);
  if(i===0)return [-b[1],b[0]];if(i===points.length-1)return [-a[1],a[0]];
  const dot=1+a[0]*b[0]+a[1]*b[1];
  if(dot<.2)return [-b[1],b[0]];
  return [-(a[1]+b[1])/dot,(a[0]+b[0])/dot];
 });
}
export function prepareRoadFrames(roads){
 const nodes=new Map();
 for(const road of roads){road.renderFrames=roadFrames(road.points);for(const i of [0,road.points.length-1]){const key=road.nodeIds[i];if(!nodes.has(key))nodes.set(key,[]);nodes.get(key).push({road,i})}}
 for(const entries of nodes.values()){
  if(entries.length!==2)continue;
  const [a,b]=entries;if(!a.road.name||a.road.name!==b.road.name||!!a.road.bridge!==!!b.road.bridge)continue;
  const neighbor=e=>e.road.points[e.i===0?1:e.i-1],p=a.road.points[a.i],pa=neighbor(a),pb=neighbor(b);
  const ax=pa[0]-p[0],ay=pa[1]-p[1],bx=pb[0]-p[0],by=pb[1]-p[1];
  if((ax*bx+ay*by)/Math.hypot(ax,ay)/Math.hypot(bx,by)>-.95)continue;
  for(const [e,other] of [[a,b],[b,a]])e.road.renderFrames[e.i]=roadFrames(e.i===0?[neighbor(other),p,neighbor(e)]:[neighbor(e),p,neighbor(other)])[1];
 }
}
export function roadSection(road,index,t,offset){
 const a=road.points[index-1],b=road.points[index],fa=road.renderFrames[index-1],fb=road.renderFrames[index];
 return [a[0]+(b[0]-a[0])*t+(fa[0]+(fb[0]-fa[0])*t)*offset,a[1]+(b[1]-a[1])*t+(fa[1]+(fb[1]-fa[1])*t)*offset,a[2]+(b[2]-a[2])*t];
}
