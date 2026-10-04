// Coordinates are [east, north, height]. Interpolate height when clipping.
export function subtractConvex(polygon, clip){
 const bounds=p=>[Math.min(...p.map(v=>v[0])),Math.min(...p.map(v=>v[1])),Math.max(...p.map(v=>v[0])),Math.max(...p.map(v=>v[1]))];
 const pbox=bounds(polygon),cbox=bounds(clip);
 if(pbox[2]<=cbox[0]||pbox[0]>=cbox[2]||pbox[3]<=cbox[1]||pbox[1]>=cbox[3])return [polygon];
 // Keep vertical curb faces: their XY footprint has zero area, but XYZ does not.
 const area=p=>{const sum=[0,0,0];for(let i=0;i<p.length;i++){const a=p[i],b=p[(i+1)%p.length],az=a[2]||0,bz=b[2]||0;sum[0]+=a[1]*bz-az*b[1];sum[1]+=az*b[0]-a[0]*bz;sum[2]+=a[0]*b[1]-a[1]*b[0];}return Math.hypot(...sum);};
 const winding=clip.reduce((sum,v,i)=>{const q=clip[(i+1)%clip.length];return sum+v[0]*q[1]-q[0]*v[1]},0)<0?1:-1;
 let inside=polygon;const outside=[];
 for(let i=0;i<clip.length&&inside.length;i++){
  const a=clip[i],b=clip[(i+1)%clip.length];
  const distance=p=>winding*((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]));
  const keep=[],reject=[];
  for(let j=0;j<inside.length;j++){
   const p=inside[j],q=inside[(j+1)%inside.length],dp=distance(p),dq=distance(q);
   if(dp<=0)keep.push(p);if(dp>=0)reject.push(p);
   if((dp<0&&dq>0)||(dp>0&&dq<0)){
    const t=dp/(dp-dq),hit=p.map((v,k)=>v+(q[k]-v)*t);keep.push(hit);reject.push(hit);
   }
  }
  if(reject.length>=3&&area(reject)>1e-6)outside.push(reject);
  inside=keep.length>=3&&area(keep)>1e-6?keep:[];
 }
 return outside;
}

export function clipGroundAtRoads(world,polygon,options={}){
 const xs=polygon.map(p=>p[0]),ys=polygon.map(p=>p[1]),segments=new Set();
 const box=[Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)];
 for(let x=Math.floor(Math.min(...xs)/50);x<=Math.floor(Math.max(...xs)/50);x++)
 for(let y=Math.floor(Math.min(...ys)/50);y<=Math.floor(Math.max(...ys)/50);y++)
 for(const s of world.grid.get(x+','+y)||[])if(!s.road.bridge&&s.road!==options.excludeRoad&&(!options.roadFilter||options.roadFilter(s.road)))segments.add(s);
 let pieces=[polygon];
 for(const s of segments){
  if(options.matchHeight){const heights=polygon.map(p=>p[2]||0),low=Math.min(...heights),high=Math.max(...heights);
   if(Math.min(s.a[2],s.b[2])>high+1||Math.max(s.a[2],s.b[2])<low-1)continue;
  }
  if(!s.groundClip){
   const {a,b,len,road}=s,dx=(b[0]-a[0])/len,dy=(b[1]-a[1])/len,half=road.width/2,offset=road.pavementOffset||0;
   s.groundClip=[[a,offset+half],[b,offset+half],[b,offset-half],[a,offset-half]].map(([p,o])=>[p[0]-dy*o,p[1]+dx*o]);
   const cx=s.groundClip.map(p=>p[0]),cy=s.groundClip.map(p=>p[1]);s.groundClipBounds=[Math.min(...cx),Math.min(...cy),Math.max(...cx),Math.max(...cy)];
  }
  const cb=s.groundClipBounds;
  if(box[2]<=cb[0]||box[0]>=cb[2]||box[3]<=cb[1]||box[1]>=cb[3])continue;
  const clip=s.groundClip;
  pieces=pieces.flatMap(p=>subtractConvex(p,clip));
  if(!pieces.length)break;
 }
 return pieces;
}
