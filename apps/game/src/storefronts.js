import * as T from 'three';

export const genericShops=[
 {name:'RESTAURANT',kind:'restaurant',detail:'GRILL · FRESH KITCHEN'},
 {name:'COFFEE & TEA',kind:'cafe',detail:'COFFEE · PASTRIES'},
 {name:'BAKERY',kind:'bakery',detail:'FRESH BREAD · SWEETS'},
 {name:'PIZZA & SUBS',kind:'fast_food',detail:'TAKEOUT · DINE IN'},
 {name:'NEIGHBORHOOD MARKET',kind:'market',detail:'GROCERIES · PRODUCE'},
 {name:'GRILL & SHAWARMA',kind:'restaurant',detail:'DINE IN · TAKEOUT'},
 {name:'BARBER SHOP',kind:'shop',detail:'CUTS · GROOMING'},
 {name:'DESSERTS',kind:'ice_cream',detail:'SWEETS · COFFEE'},
];

const contains=(p,poly)=>{let inside=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){const a=poly[i],b=poly[j];if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside}return inside};
const closest=(p,a,b)=>{const dx=b[0]-a[0],dy=b[1]-a[1],t=T.MathUtils.clamp(((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy||1),0,1);return [a[0]+dx*t,a[1]+dy*t]};
const edges=poly=>poly.map((a,i)=>[a,poly[(i+1)%poly.length]]);

export function storefrontPlan(data,businesses=[]){
 const roadEdges=data.roads.filter(r=>r.name==='Michigan Avenue').flatMap(r=>r.points.slice(1).map((p,i)=>[r.points[i],p]));
 const plans=new Map(),shops=genericShops.slice();
 for(const building of data.buildings){
  if(!['yes','retail','commercial','office','restaurant','cafe','fast_food'].includes(building.type))continue;
  const points=building.points,center=[points.reduce((s,p)=>s+p[0],0)/points.length,points.reduce((s,p)=>s+p[1],0)/points.length];
  let target=null,distance=Infinity;
  for(const [a,b] of roadEdges){const p=closest(center,a,b),d=Math.hypot(p[0]-center[0],p[1]-center[1]);if(d<distance){distance=d;target=p}}
  const frontageDistance=Math.min(...points.map(p=>target?Math.hypot(p[0]-target[0],p[1]-target[1]):Infinity));
  if(frontageDistance<75){
   const named=building.name&&['restaurant','cafe','fast_food','bar','pub','ice_cream'].includes(building.amenity);
   const names=[];if(named){names.push(shops.length);shops.push({name:building.name,kind:building.amenity})}
   plans.set(building.id,{target,shops:names,inferred:!named});
  }
 }
 for(const business of businesses){
  if(!business.name)continue;
  let match=null,best=Infinity;
  for(const building of data.buildings){
   const p=business.point,poly=building.points;
   if(p[0]<building.bounds?.[0]-25||p[0]>building.bounds?.[2]+25||p[1]<building.bounds?.[1]-25||p[1]>building.bounds?.[3]+25)continue;
   const d=contains(p,poly)?0:Math.min(...edges(poly).map(([a,b])=>{const q=closest(p,a,b);return Math.hypot(q[0]-p[0],q[1]-p[1])}));
   if(d<best){best=d;match=building}
  }
  if(!match||best>20)continue;
  if(business.brand){
   let target=null,nearest=Infinity;
   for(const road of data.roads.filter(r=>r.name===(business.street||'Michigan Avenue')))for(const [a,b] of road.points.slice(1).map((p,i)=>[road.points[i],p])){
    const q=closest(business.point,a,b),distance=Math.hypot(q[0]-business.point[0],q[1]-business.point[1]);if(distance<nearest){nearest=distance;target=q}
   }
   if(!target)continue;
   if(!plans.has(match.id))plans.set(match.id,{target,shops:[],inferred:false});
   plans.get(match.id).target=target;
  }
  const plan=plans.get(match.id);if(!plan)continue;
  const index=shops.length;shops.push(business);plan.inferred=false;
  if(business.brand){(plan.featuredShops??=[]).push({index,point:business.point})}else plan.shops.push(index);
 }
 return {plans,shops};
}

// One opaque atlas for all restaurant/retail façades and their awning colors.
export function storefrontAtlas(shops){
 const columns=4,cellWidth=512,cellHeight=256,rows=Math.ceil(shops.length/columns),canvas=document.createElement('canvas');
 canvas.width=columns*cellWidth;canvas.height=rows*cellHeight;const c=canvas.getContext('2d');
 const colors=['#722f2a','#254e48','#303d54','#9d6737','#526237','#582c3f','#292b2d','#456176'];
 shops.forEach((shop,index)=>{
  c.save();c.translate(index%columns*cellWidth,Math.floor(index/columns)*cellHeight);
  const accent=shop.accent||colors[index%colors.length];c.fillStyle='#a28e76';c.fillRect(0,0,512,256);
  for(let y=0;y<256;y+=12)for(let x=-24;x<512;x+=48){c.fillStyle=(x+y)%3?'#b0a08b':'#998c7b';c.fillRect(x+(y%24?24:0),y,47,11)}
  c.fillStyle=accent;c.fillRect(8,20,496,61);
  c.fillStyle=shop.ink||'#f2e7cf';c.textAlign='center';c.textBaseline='middle';c.font='bold 30px Arial';
  const name=(shop.signName||shop.name).toUpperCase();const width=c.measureText(name).width;if(width>465)c.font=`bold ${Math.floor(30*465/width)}px Arial`;
  if(shop.brand==='qahwah'){c.font='bold 30px Georgia';c.fillText(name,256,43)}else if(shop.brand==='jabal'){
   c.font='bold 38px Georgia';c.fillText('JABAL',256,40);c.font='12px Arial';c.fillText('COFFEE HOUSE',256,61);
  }else{c.fillText(name,256,42)}
  c.font='11px Arial';c.fillText(shop.detail||shop.kind.replaceAll('_',' ').toUpperCase(),256,shop.brand==='jabal'?77:66);
  const glass=c.createLinearGradient(0,95,0,239);glass.addColorStop(0,'#597780');glass.addColorStop(.45,'#78918e');glass.addColorStop(.48,'#293633');glass.addColorStop(1,'#3a4037');
  c.fillStyle='#ded8c7';c.fillRect(16,93,480,150);c.fillStyle=glass;c.fillRect(23,99,318,138);c.fillRect(351,99,138,138);
  c.fillStyle='#b6b3a7';for(const x of [126,232,341,348])c.fillRect(x,96,5,144);
  c.fillRect(24,157,317,4);c.fillStyle='#e6dfcd';c.fillRect(359,172,5,33);
  // A menu board and warm interior silhouettes are baked into the glazing.
  c.fillStyle='#e7d8af';c.fillRect(56,175,40,41);c.fillStyle='#373b32';c.font='9px Arial';c.fillText('MENU',76,183);
  c.fillStyle='#b7aa86';for(const x of [148,264]){c.fillRect(x,201,44,3);c.fillRect(x+21,204,3,30)}
  c.fillStyle='#8b7e69';c.fillRect(0,244,512,12);c.restore();
 });
 const map=new T.CanvasTexture(canvas);map.colorSpace=T.SRGBColorSpace;map.anisotropy=4;
 return {map,columns,rows};
}

export function atlasUV(index,u,v,shopCount){
 const columns=4,rows=Math.ceil(shopCount/columns),padding=.004;
 return [(index%columns+padding+u*(1-2*padding))/columns,1-(Math.floor(index/columns)+padding+(1-v)*(1-2*padding))/rows];
}
