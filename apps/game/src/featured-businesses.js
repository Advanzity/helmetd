// Official West Dearborn addresses matched to OSM points or building footprints.
export const featuredBusinesses=[
 {id:'qahwah-house',name:'Qahwah House',kind:'cafe',detail:'YEMENI COFFEE · ADENI TEA',accent:'#eee6d5',ink:'#4b3222',brand:'qahwah',
  address:'22000 Michigan Avenue, Dearborn, MI 48124',source:'https://qahwahhouse.com/locations'},
 {id:'jabal',name:'Jabal Coffee House',kind:'cafe',detail:'COFFEE · PASTRIES',accent:'#273b34',ink:'#eadebd',brand:'jabal',
  address:'1031 Mason Street, Dearborn, MI 48124',source:'https://jabalcoffeehouse.com/pages/locations'},
 {id:'level-zero',name:'Level Zero Smash Burgers',signName:'LEVEL ZERO',kind:'fast_food',detail:'SMASH BURGERS · FRIES · SHAKES',accent:'#242323',ink:'#f8d452',brand:'level-zero',
  address:'22224 Michigan Avenue, Dearborn, MI 48124',source:'https://zerosmash.com/locations'},
];

export function resolveFeaturedBusinesses(osm,origin){
 const nodes=new Map(osm.elements.filter(e=>e.type==='node').map(e=>[String(e.id),e]));
 const patterns=[/qahwah\s*house/i,/jabal/i,/level\s*(zero|0)|zero\s*smash/i];
 return featuredBusinesses.map((business,index)=>{
  let matches=osm.elements.filter(e=>patterns[index].test(e.tags?.name||e.tags?.brand||''));
  let pointSource='named-osm-feature';
  if(!matches.length&&index===0){matches=osm.elements.filter(e=>e.tags?.['addr:housenumber']==='22000'&&/michigan/i.test(e.tags?.['addr:street']||''));pointSource='official-address-matched-to-osm-building'}
  if(!matches.length)throw new Error(`No mapped location found for ${business.name}`);
  const element=matches.find(e=>e.tags?.amenity)||matches[0];
  const points=element.type==='node'?[element]:(element.nodes||[]).map(id=>nodes.get(String(id))).filter(Boolean);
  if(!points.length)throw new Error(`Missing coordinates for ${business.name}`);
  const lon=points.reduce((s,p)=>s+p.lon,0)/points.length,lat=points.reduce((s,p)=>s+p.lat,0)/points.length;
  return {...business,point:[(lon-origin[0])*111320*Math.cos(origin[1]*Math.PI/180),(lat-origin[1])*111320],coordinates:[lon,lat],osmId:String(element.id),placement:'mapped',pointSource,street:index===1?'Mason Street':'Michigan Avenue'};
 });
}
