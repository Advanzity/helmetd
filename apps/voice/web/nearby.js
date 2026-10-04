import {localFetch} from './local-api.js';
import {RideAudio} from './ride-audio.js';
const $ = id => document.getElementById(id);
const meters = m => m == null ? '—' : m < 1000 ? `${Math.round(m)} m` : `${(m/1000).toFixed(1)} km`;
const minutes = s => s == null ? '—' : `${s === 0 ? 0 : Math.max(1,Math.ceil(s/60))} min`;
let current, map, tiles, position, accuracy, routeLine, previewLine, routeCasing, previewCasing, destinationMarker, points;
let busy=false, polling=false, watch=null, locationGeneration=0, timer=null, locating=false;
let resultsKey='', geometryKey='', lastNotice='', category='', locationError='';
let mapStyle='holo', expanded=false;
let viewMode='3d', earth3d=null, loading3d=false, mapGeneration=0;
const rideAudio=new RideAudio({onStatus:text=>{$('nav-audio-status').textContent=text;}});
window.addEventListener('helmetd-voice-volume',event=>{rideAudio.volume=event.detail.volume;if(rideAudio.volume===0)rideAudio.cancel();});
let hazardPoints=null,hazardKey='',pendingShare=null,audioChoice=false;
let terrainRelief=3;
try{const saved=Number(localStorage.getItem('helmetd-terrain-relief'));if([1,3,6].includes(saved))terrainRelief=saved;}catch{ /* Storage is optional. */ }
$('map-relief').value=String(terrainRelief);
try { const saved=localStorage.getItem('helmetd-map-style-3d');if(['holo','earth','streets'].includes(saved))mapStyle=saved; } catch { /* Storage is optional. */ }
const basemaps={
  holo:{caption:'3D Hologram'},
  earth:{url:'https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}',maxNativeZoom:16,
    attribution:'Imagery: USDA, <a href="https://www.usgs.gov/programs/national-geospatial-program/national-map" target="_blank" rel="noopener">USGS The National Map</a>',
    caption:'Earth imagery · Detailed coverage in the U.S. · Not live'},
  streets:{url:'https://tile.openstreetmap.org/{z}/{x}/{y}.png',maxNativeZoom:19,
    attribution:'© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',caption:'Street map · OpenStreetMap'}
};
const stateNames={idle:'Ready to explore',navigating:'Navigating',paused:'Paused',off_route:'Off route',location_lost:'Location unavailable',arrived:'Arrived'};
const arrows={left:'↰',right:'↱',straight:'↑',uturn:'↶',arrive:'⚑',stop:'•'};

async function api(name,parameters={}) {
  const response=await localFetch('/api/navigation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,parameters}),signal:AbortSignal.timeout(['plan','search','stop','control'].includes(name)?30000:5000)});
  const result=await response.json();
  if(!response.ok) throw new Error(typeof result.detail==='string'?result.detail:'Navigation request failed.');
  return result;
}
function note(text,error=false){$('nav-notice').textContent=text;$('nav-notice').classList.toggle('error',error);}
function enable(){
  const located=Boolean(current?.fix && current.fix.age_s<300 && current.fix.accuracy_m<=3000);
  document.querySelectorAll('#search,#search-form input,.categories button').forEach(button=>button.disabled=busy||!located);
  document.querySelectorAll('.place-actions button,.nav-actions button').forEach(button=>button.disabled=busy);
  $('locate').disabled=locating;
  const available=Boolean(map||earth3d?.ready);
  document.querySelectorAll('[data-map-style],#map-expand').forEach(button=>button.disabled=!available);
  document.querySelector('[data-map-style="holo"]').disabled=!earth3d?.ready;
  $('map-dimension').disabled=false;
  document.querySelectorAll('#map-3d-controls button').forEach(button=>button.disabled=!earth3d?.ready);
  $('map-relief').disabled=!earth3d?.ready;$('map-terrain').disabled=!earth3d?.ready;
  $('map-center').disabled=!available||!current?.fix;
  $('hazard-save').disabled=busy||!current?.fix?.guidance_usable;
}
function setMapStyle(style){
  if(!basemaps[style])return;
  mapStyle=style;
  try{localStorage.setItem('helmetd-map-style-3d',style);}catch{ /* Storage is optional. */ }
  document.querySelectorAll('[data-map-style]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.mapStyle===style)));
  if(viewMode==='3d'){earth3d?.setBasemap(style);return;}
  if(!map)return;
  if(tiles)map.removeLayer(tiles);
  const source=basemaps[style];
  tiles=L.tileLayer(source.url,{maxZoom:19,maxNativeZoom:source.maxNativeZoom,attribution:source.attribution,keepBuffer:1}).addTo(map);
  const activeTiles=tiles;
  $('map-state').textContent=source.caption;
  tiles.on('tileerror',()=>{if(tiles===activeTiles)$('map-state').textContent=`${style==='earth'?'Earth imagery':'Street map'} unavailable here · Try the other map view`;});
  document.querySelectorAll('[data-map-style]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.mapStyle===style)));
  routeLine.setStyle({color:style==='earth'?'#70ffed':'#007f83',weight:6});
  previewLine.setStyle({color:style==='earth'?'#f6ffff':'#006268',weight:5});
  position.setStyle({fillColor:style==='earth'?'#13cec5':'#007f83'});
  accuracy.setStyle({color:style==='earth'?'#70ffed':'#087f83'});
}
function setMapMode(mode,reason=''){
  mapGeneration++;
  loading3d=false;
  earth3d?.destroy();earth3d=null;
  map?.remove();map=null;tiles=null;points=null;
  hazardPoints=null;hazardKey='';
  $('map').replaceChildren();
  viewMode=mode;geometryKey='';resultsKey='';
  $('map').classList.remove('hologram');
  if(mode==='2d'&&mapStyle==='holo')mapStyle='earth';
  $('map-dimension').textContent=mode==='3d'?'3D':'2D';
  $('map-dimension').setAttribute('aria-pressed',String(mode==='3d'));
  $('map-dimension').setAttribute('aria-label',mode==='3d'?'Switch to 2D map':'Switch to 3D Earth');
  $('map-3d-controls').hidden=mode!=='3d';$('map-help').hidden=mode!=='3d';
  $('map-camera').hidden=mode!=='3d';
  $('map-ground-controls').hidden=mode!=='3d';
  if(current)render(current);
  if(reason)note(reason,true);
}
function makeMap(fix){
  if(viewMode==='3d'){
    if(earth3d||loading3d)return;
    loading3d=true;
    const generation=mapGeneration;
    $('map-state').textContent='Loading 3D Earth…';
    import('./earth-map.js').then(({EarthMap})=>{
      if(generation!==mapGeneration||viewMode!=='3d')return;
      $('map').replaceChildren();
      earth3d=new EarthMap({container:$('map'),fix,basemap:mapStyle,relief:terrainRelief,
        onReady:()=>{loading3d=false;enable();},
        onStatus:text=>{$('map-state').textContent=text;},
        onFailure:reason=>{if(generation===mapGeneration)setMapMode('2d',reason);}});
      if(current)earth3d.update(current);
    }).catch(()=>{if(generation===mapGeneration)setMapMode('2d','3D graphics are unavailable. Showing the 2D map.');});
    return;
  }
  if(map||!window.L)return;
  if(!fix){$('map').textContent='Share your location to open the 2D map.';return;}
  $('map').replaceChildren();
  map=L.map('map',{scrollWheelZoom:false,zoomControl:false}).setView(fix.point,15);
  L.control.zoom({position:'bottomright'}).addTo(map);
  L.control.scale({position:'bottomleft',imperial:false}).addTo(map);
  points=L.layerGroup().addTo(map);
  routeCasing=L.polyline([],{color:'#052b24',weight:10,opacity:.85,interactive:false}).addTo(map);
  previewCasing=L.polyline([],{color:'#052b24',weight:9,opacity:.8,interactive:false}).addTo(map);
  routeLine=L.polyline([],{color:'#007f83',weight:6}).addTo(map);
  previewLine=L.polyline([],{color:'#006268',weight:5,dashArray:'9 8',className:'preview-route'}).addTo(map);
  accuracy=L.circle(fix.point,{radius:fix.accuracy_m,color:'#087f83',weight:1,fillOpacity:.07}).addTo(map);
  position=L.circleMarker(fix.point,{radius:7,color:'#fff',weight:3,fillColor:'#007f83',fillOpacity:1}).addTo(map);
  setMapStyle(mapStyle);
  resultsKey=''; // Rebuild markers if a result list arrived before location.
}
function renderResults(data){
  const selectedId=(data.preview||data.route)?.destination_id;
  const key=JSON.stringify([data.results,selectedId]);
  if(key===resultsKey)return;
  resultsKey=key;
  $('place-results').replaceChildren();
  $('result-count').textContent=String(data.results.length);
  if(points)points.clearLayers();
  if(!data.results.length){const li=document.createElement('li');li.className='empty';li.textContent='Search for a destination or choose a category.';$('place-results').append(li);}
  for(const [index,place] of data.results.entries()){
    const li=document.createElement('li'),copy=document.createElement('div'),name=document.createElement('strong'),detail=document.createElement('p'),actions=document.createElement('div');
    const number=document.createElement('span');number.className='place-number';number.textContent=String(index+1);number.setAttribute('aria-hidden','true');li.classList.toggle('place-selected',selectedId===place.id);
    copy.className='place-copy';actions.className='place-actions';name.textContent=place.name;
    detail.textContent=`${meters(place.distance_m)} away · ${place.address||'Listed in OpenStreetMap'}`;
    copy.append(name,detail);
    const route=document.createElement('button');route.textContent=selectedId===place.id?'Selected':'Preview';route.setAttribute('aria-label',`Preview route to ${place.name}`);route.onclick=()=>act('plan',{destination:place.id,preference:$('preference').value});actions.append(route);
    if(data.route||data.preview){const stop=document.createElement('button');stop.textContent='+ Stop';stop.setAttribute('aria-label',`Add ${place.name} as a stop`);stop.onclick=()=>act('stop',{action:'add',place:place.id});actions.append(stop);}
    li.append(number,copy,actions);$('place-results').append(li);
    if(points){const popup=document.createElement('div');const title=document.createElement('b');title.textContent=place.name;popup.append(title,document.createTextNode(place.address||`${meters(place.distance_m)} away`));L.marker(place.point,{icon:L.divIcon({className:`place-marker${selectedId===place.id?' selected':''}`,html:String(index+1),iconSize:[28,28],iconAnchor:[14,14]}),title:place.name}).bindPopup(popup).addTo(points);}
  }
}
function render(data){
  if(current&&data.revision<current.revision)return;
  current=data;
  rideAudio.update(data);renderHazards(data.hazards);
  $('nav-repeat').disabled=!data.next_turn||!data.fix?.guidance_usable;
  makeMap(data.fix);
  earth3d?.update(data);
  if(map){
    if(data.fix){position.setLatLng(data.fix.point).setStyle({opacity:data.fix.guidance_usable?1:.45,fillOpacity:data.fix.guidance_usable?1:.4});accuracy.setLatLng(data.fix.point).setRadius(Math.min(3000,data.fix.accuracy_m));}
    const newKey=JSON.stringify([data.route?.geometry,data.preview?.geometry]);
    if(newKey!==geometryKey){
      geometryKey=newKey;
      routeLine.setLatLngs(data.route?.geometry||[]);routeCasing.setLatLngs(data.route?.geometry||[]);
      previewLine.setLatLngs(data.preview?.geometry||[]);previewCasing.setLatLngs(data.preview?.geometry||[]);
      if(destinationMarker){map.removeLayer(destinationMarker);destinationMarker=null;}
      const selected=data.preview||data.route;
      if(selected){
        destinationMarker=L.marker(selected.geometry.at(-1),{icon:L.divIcon({className:'destination-marker',html:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 21V4m0 0c4-4 8 4 12 0v9c-4 4-8-4-12 0"/></svg>',iconSize:[32,32],iconAnchor:[16,16]}),title:'Route destination'}).addTo(map);
        const line=data.preview?previewLine:routeLine;
        map.fitBounds(line.getBounds(),{paddingTopLeft:[35,75],paddingBottomRight:[35,45],maxZoom:16,animate:false});
      }
    }
    routeLine.setStyle({opacity:['location_lost','off_route'].includes(data.state) ? 0.35 : 1});
    routeCasing.setStyle({opacity:['location_lost','off_route'].includes(data.state) ? 0.25 : 0.85});
    if(!data.fix){position.setStyle({opacity:0,fillOpacity:0});accuracy.setStyle({opacity:0,fillOpacity:0});}
    else accuracy.setStyle({opacity:1,fillOpacity:.07});
  }
  renderResults(data);
  const selected=data.preview||data.route;
  document.querySelector('.route-origin').hidden=!selected;
  $('locate').textContent=data.fix?'Refresh location':'Use my location';
  $('nav-state').textContent=data.preview?'Route preview':stateNames[data.state];
  $('nav-destination').textContent=selected?.destination||'Find your next stop.';
  $('nav-distance').textContent=meters(data.preview?selected.distance_m:data.remaining_m);
  $('nav-time').textContent=minutes(data.preview?selected.duration_s:data.remaining_s);
  $('route-note').textContent=selected?`${selected.preference==='avoid_highways'?'Prefers local roads':'Fastest motorcycle route'}${selected.has_highway?' · Includes highway sections':''}${selected.has_toll?' · Includes tolls':''}${selected.stop_place?` · Via ${selected.stop_place.name}`:''}. Estimate excludes live traffic.`:'Choose a nearby place to preview a motorcycle route.';
  const turn=data.next_turn;
  $('turn-arrow').textContent=turn?arrows[turn.maneuver]:'—';
  $('turn-distance').textContent=turn?`${data.preview?'Current route · ':''}In ${meters(turn.distance_m)}`:data.state==='arrived'?'Destination reached':'Guidance';
  $('turn-instruction').textContent=turn?.instruction||(data.state==='arrived'?`Near ${data.route.destination}.`:data.state==='paused'?'Resume when ready.':data.state==='location_lost'?'Waiting for a fresh, accurate location.':data.state==='off_route'?'Reroute from your position.':'Start a route with a fresh location to see your next turn.');
  $('nav-start').hidden=!data.preview;$('nav-start').textContent=data.route?'Use this route':'Start guidance';
  $('nav-dismiss').hidden=!data.preview;$('nav-cancel').hidden=!data.route&&!data.preview;
  $('nav-pause').hidden=!['paused','navigating'].includes(data.state);$('nav-pause').textContent=data.state==='paused'?'Resume guidance':'Pause guidance';
  $('nav-reroute').hidden=!data.route||data.state==='arrived';$('nav-remove-stop').hidden=!selected?.stop_place;
  if(!locating)$('location-status').textContent=locationError||(data.fix?`Device location · ±${meters(data.fix.accuracy_m)}${data.fix.age_s>15?' · stale':''}`:'Location is off');
  $('nav-hud').textContent=data.hud_connected?'HUD connected':'HUD unavailable · Map still works';
  if(!busy&&lastNotice!==data.notice){lastNotice=data.notice;note(data.notice);}
  enable();
}
function renderHazards(feed){
  if(!feed)return;
  $('hazard-count').textContent=feed.reports.length;
  $('hazard-feed-status').textContent=`${feed.status}${feed.location_required?' · Refresh location to view nearby reports':''}`;
  const key=JSON.stringify(feed.reports.map(r=>[r.id,r.sharing,r.ahead_m,Math.ceil((r.expires_at-Date.now()/1000)/60)]));
  if(key===hazardKey&&(!map||hazardPoints))return;
  hazardKey=key;$('hazard-results').replaceChildren();
  if(map){if(!hazardPoints)hazardPoints=L.layerGroup().addTo(map);hazardPoints.clearLayers();}
  for(const report of feed.reports){
    const row=document.createElement('li'),body=document.createElement('div'),title=document.createElement('b'),detail=document.createElement('span');
    const name=report.kind.replaceAll('_',' ');title.textContent=`${name[0].toUpperCase()+name.slice(1)}${report.lane==='unknown'?'':` · ${report.lane}${report.lane==='shoulder'?'':' lane'}`}`;
    detail.textContent=`${report.ahead_m!=null?`${meters(report.ahead_m)} along upcoming route`:`${meters(report.distance_m)} nearby`} · expires in ${Math.max(1,Math.ceil((report.expires_at-Date.now()/1000)/60))} min · ${report.sharing==='local'?'Saved locally':report.sharing==='unconfirmed'?'Sharing unconfirmed':'Shared report'}`;
    body.append(title,detail);row.append(body);
    if(report.sharing==='local'){
      const share=document.createElement('button');share.textContent='Share';share.setAttribute('aria-label',`Share ${name} report`);
      share.onclick=()=>{pendingShare=report.id;$('hazard-share-dialog').showModal();};row.append(share);
    }
    $('hazard-results').append(row);
    if(map){const label=document.createElement('span');label.textContent=`Reported ${title.textContent}. Unverified.`;L.marker(report.point,{icon:L.divIcon({className:'hazard-leaflet',html:'<b class="hazard-marker">!</b>',iconSize:[28,28]})}).bindPopup(label).addTo(hazardPoints);}
  }
  if(!feed.reports.length){const empty=document.createElement('li');empty.className='empty';empty.textContent=feed.location_required?'Refresh location to load nearby reports.':'No unexpired reports nearby.';$('hazard-results').append(empty);}
}
async function hazardAction(name,parameters){
  const response=await localFetch('/api/hazards',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,parameters}),signal:AbortSignal.timeout(name==='share'?65000:10000)});
  const data=await response.json();if(!response.ok)throw new Error(data.detail||'Hazard action failed');return data;
}
$('hazard-form').onsubmit=async event=>{
  event.preventDefault();$('hazard-save').disabled=true;
  try{const result=await hazardAction('report',{kind:$('hazard-kind').value,lane:$('hazard-lane').value});$('hazard-notice').textContent=result.duplicate?'That report is already saved.':'Saved locally for 15 minutes. Choose Share to warn other riders.';await poll();}
  catch(error){$('hazard-notice').textContent=error.message;}finally{enable();}
};
$('hazard-share-cancel').onclick=()=>{$('hazard-share-dialog').close();pendingShare=null;};
$('hazard-share-confirm').onclick=async()=>{
  if(!pendingShare)return;const id=pendingShare;pendingShare=null;$('hazard-share-dialog').close();
  $('hazard-notice').textContent='Sharing report on devnet…';
  try{const result=await hazardAction('share',{report_id:id,confirmed:true});$('hazard-notice').textContent=result.status==='confirmed'?'Shared with the trusted-rider feed.':result.reason||result.note;await poll();}
  catch{$('hazard-notice').textContent='Sharing could not be confirmed. Check the outbox before retrying.';}
};
function audioControls(){
  $('nav-audio').setAttribute('aria-pressed',String(rideAudio.enabled));
  $('nav-audio').textContent=rideAudio.enabled?'Mute spoken guidance':'Enable spoken guidance';
}
$('nav-audio').onclick=async()=>{audioChoice=true;try{rideAudio.enabled?rideAudio.disable():await rideAudio.enable();audioControls();}catch(error){$('nav-audio-status').textContent=error.message;}};
$('nav-audio-test').onclick=async()=>{try{await rideAudio.test();audioControls();}catch(error){$('nav-audio-status').textContent=error.message;}};
$('nav-repeat').onclick=async()=>{try{if(!rideAudio.enabled)await rideAudio.enable();audioControls();void act('control',{action:'repeat'});}catch(error){$('nav-audio-status').textContent=error.message;}};
async function enableRouteAudio(){
  if(audioChoice||rideAudio.enabled)return;
  try{await rideAudio.enable();audioControls();}catch(error){$('nav-audio-status').textContent=error.message;}
}
window.addEventListener('helmetd-navigation-start',enableRouteAudio);
async function act(name,parameters={}){
  if(busy)return;busy=true;enable();
  note(name==='search'?'Finding nearby places…':name==='plan'||name==='stop'?'Calculating motorcycle route…':'Updating navigation…');
  try{const data=await api(name,parameters);busy=false;lastNotice='';render(data);}
  catch(error){busy=false;note(error.message,true);enable();}
}
async function sendLocation(fix,generation){
  if(generation!==locationGeneration)return;
  try{const data=await api('location',{lat:fix.coords.latitude,lon:fix.coords.longitude,accuracy_m:fix.coords.accuracy,timestamp_ms:fix.timestamp});if(generation!==locationGeneration)return;locating=false;locationError='';clearTimeout(timer);$('stop-location').hidden=false;render(data);}
  catch(error){locating=false;note(error.message,true);enable();}
}
function locate(){
  if(!navigator.geolocation){note('Location is unavailable in this browser.',true);return;}
  if(watch!==null)navigator.geolocation.clearWatch(watch);
  const generation=++locationGeneration;locating=true;locationError='';enable();$('location-status').textContent='Allow location access in your browser…';
  timer=setTimeout(()=>{if(generation!==locationGeneration)return;locating=false;$('location-status').textContent='Waiting for location permission or a position…';note('Allow location access. If no prompt appears, open this local page in Safari or Chrome and try again.',true);enable();},12000);
  watch=navigator.geolocation.watchPosition(fix=>void sendLocation(fix,generation),error=>{if(generation!==locationGeneration)return;locating=false;clearTimeout(timer);locationError=error.code===1?'Location permission denied':'Location unavailable';$('location-status').textContent=locationError;note(error.code===1?'Allow location for this page in your browser, then try again.':'Your device could not locate you. Try near a window or in Safari/Chrome.',true);enable();},{enableHighAccuracy:true,maximumAge:0,timeout:10000});
}
$('locate').onclick=locate;
document.querySelectorAll('[data-map-style]').forEach(button=>button.onclick=()=>setMapStyle(button.dataset.mapStyle));
$('map-center').onclick=()=>{if(viewMode==='3d')earth3d?.center();else if(map&&current?.fix)map.setView(current.fix.point,Math.max(15,map.getZoom()),{animate:!matchMedia('(prefers-reduced-motion: reduce)').matches});};
$('map-expand').onclick=()=>{expanded=!expanded;$('navigation').classList.toggle('map-expanded',expanded);$('map-expand').textContent=expanded?'Collapse':'Expand';$('map-expand').setAttribute('aria-pressed',String(expanded));map?.invalidateSize({pan:false});earth3d?.resize();};
$('map-dimension').onclick=()=>setMapMode(viewMode==='3d'?'2d':'3d');
$('map-tilt').onclick=()=>earth3d?.tilt();$('map-rotate').onclick=()=>earth3d?.rotate();
$('map-terrain').onclick=()=>earth3d?.terrainView();
$('map-relief').onchange=()=>{
  terrainRelief=Number($('map-relief').value);earth3d?.setRelief(terrainRelief);
  try{localStorage.setItem('helmetd-terrain-relief',String(terrainRelief));}catch{ /* Storage is optional. */ }
};
$('map-globe').onclick=()=>earth3d?.globe();$('map-route').onclick=()=>earth3d?.overview();
$('stop-location').onclick=async()=>{locationGeneration++;if(watch!==null)navigator.geolocation.clearWatch(watch);watch=null;clearTimeout(timer);locating=false;locationError='';$('stop-location').hidden=true;try{render(await api('clear_location'));}catch(error){note(error.message,true);}};
$('search-form').onsubmit=event=>{event.preventDefault();category='';document.querySelectorAll('[data-category]').forEach(button=>button.classList.remove('active'));void act('search',{query:$('place-query').value.trim()});};
document.querySelectorAll('[data-category]').forEach(button=>button.onclick=()=>{category=button.dataset.category;document.querySelectorAll('[data-category]').forEach(item=>item.classList.toggle('active',item===button));void act('search',{query:category});});
$('nav-start').onclick=()=>{enableRouteAudio();void act('control',{action:'start'});};$('nav-dismiss').onclick=()=>act('control',{action:'cancel_preview'});$('nav-cancel').onclick=()=>act('control',{action:'cancel'});$('nav-pause').onclick=()=>act('control',{action:current?.state==='paused'?'resume':'pause'});$('nav-reroute').onclick=()=>act('control',{action:'reroute'});$('nav-remove-stop').onclick=()=>act('stop',{action:'remove',place:''});
$('preference').onchange=()=>{const selected=current?.preview||current?.route;if(selected)void act('plan',{destination:selected.destination_id,preference:$('preference').value});};
async function poll(){if(polling||busy)return;polling=true;try{render(await api('status'));}catch{rideAudio.disconnect();$('nav-state').textContent='Disconnected';$('turn-distance').textContent='Guidance unavailable';$('turn-instruction').textContent='Reconnect to the local navigation service.';$('nav-time').textContent=$('nav-distance').textContent='—';$('turn-arrow').textContent='—';lastNotice='';}finally{polling=false;}}
window.addEventListener('pagehide',()=>{rideAudio.destroy();locationGeneration++;mapGeneration++;earth3d?.destroy();if(watch!==null)navigator.geolocation.clearWatch(watch);});
void poll();setInterval(poll,1000);
