// Preserve lane counts while joining the pavement envelope across mapped way boundaries.
export function prepareRoadWidths(roads){
 const ends=new Map();
 for(const road of roads){
  if(!road.name||road.curb||!['primary','trunk','secondary'].includes(road.class))continue;
  for(const i of [0,road.points.length-1]){
   const p=road.points[i],q=road.points[i===0?1:i-1],length=Math.hypot(q[0]-p[0],q[1]-p[1]);
   const key=road.nodeIds[i],entry={road,i,dx:(q[0]-p[0])/length,dy:(q[1]-p[1])/length};
   if(!ends.has(key))ends.set(key,[]);ends.get(key).push(entry);
  }
 }
 for(const entries of ends.values())for(const e of entries){
  if(!e.road.oneway){
   const base=e.road.lanes%2?(e.road.laneWidth||3.35)/2:.1;
   const matching=entries.filter(q=>q.road!==e.road&&!q.road.oneway&&q.road.name===e.road.name&&!!q.road.bridge===!!e.road.bridge&&e.dx*q.dx+e.dy*q.dy<-.95);
   const target=Math.max(base,...matching.map(q=>q.road.lanes%2?(q.road.laneWidth||3.35)/2:.1));
   e.road.medianWidths??=e.road.points.map(()=>base);
   let distance=0,previous=e.road.points[e.i];const step=e.i===0?1:-1;
   for(let i=e.i;i>=0&&i<e.road.points.length;i+=step){const p=e.road.points[i];distance+=Math.hypot(p[0]-previous[0],p[1]-previous[1]);previous=p;e.road.medianWidths[i]=Math.max(e.road.medianWidths[i],base+(target-base)*Math.max(0,1-distance/25));}
  }
  const width=Math.max(e.road.width,...entries.filter(q=>q.road!==e.road&&q.road.name===e.road.name&&!!q.road.bridge===!!e.road.bridge&&e.dx*q.dx+e.dy*q.dy<-.95).map(q=>q.road.width));
  if(width<=e.road.width)continue;
  e.road.renderWidths??=e.road.points.map(()=>e.road.width);
  let distance=0,previous=e.road.points[e.i];const step=e.i===0?1:-1;
  for(let i=e.i;i>=0&&i<e.road.points.length;i+=step){
   const p=e.road.points[i];distance+=Math.hypot(p[0]-previous[0],p[1]-previous[1]);previous=p;
   e.road.renderWidths[i]=Math.max(e.road.renderWidths[i],e.road.width+(width-e.road.width)*Math.max(0,1-distance/25));
  }
 }
}
