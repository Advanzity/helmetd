import * as gl from './maplibre-gl.mjs';
import {localFetch} from './local-api.js';

gl.setWorkerUrl(new URL('./maplibre-gl-worker.mjs', import.meta.url).href);
gl.setWorkerCount(2);
const lngLat = point => [point[1], point[0]];
const collection = features => ({type:'FeatureCollection', features});
const line = route => collection(route ? [{type:'Feature',properties:{},geometry:{type:'LineString',coordinates:route.geometry.map(lngLat)}}] : []);
const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const osmCredit = '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>';
const terrainSource = maxzoom => ({type:'raster-dem',tiles:['https://tiles.mapterhorn.com/{z}/{x}/{y}.webp'],tileSize:512,encoding:'terrarium',maxzoom,
  attribution:'Terrain: <a href="https://mapterhorn.com/attribution" target="_blank" rel="noopener">Mapterhorn</a>'});
const skyStyle = hologram => ({'sky-color':hologram?'#020910':'#162f45',
  'horizon-color':hologram?'#0b3144':'#adc7c2','fog-color':hologram?'#061b29':'#adc7c2',
  'atmosphere-blend':['interpolate',['linear'],['zoom'],0,1,5,0]});

// The graphics view only consumes navigation snapshots. Camera movement never
// updates device location, route progress, arrival, or the native HUD.
export class EarthMap {
  constructor({container, fix, basemap, relief=3, publishHud=false, onReady, onStatus, onFailure}) {
    this.container=container; this.publishHud=publishHud; this.basemap=basemap; this.onStatus=onStatus;
    this.markers=[]; this.hazardMarkers=[]; this.hazardKey=''; this.routeKey=''; this.markerKey=''; this.fixKey='';
    this.ready=false; this.destroyed=false; this.hasLocation=Boolean(fix);
    this.terrainReady=false; this.terrainError=false; this.buildingError=false;
    this.relief=relief; this.terrainSource='terrain'; this.coarseTerrain=false;
    this.map=new gl.Map({
      container, center:fix?lngLat(fix.point):[0,20], zoom:fix?17.2:1.4,
      pitch:fix?65:0, bearing:fix?-24:0, maxPitch:75, maxZoom:19, minZoom:0,
      scrollZoom:false, canvasContextAttributes:{antialias:true},
      attributionControl:false, pixelRatio:Math.min(devicePixelRatio||1,2),
      style:{version:8, projection:{type:'globe'},
        sky:skyStyle(basemap==='holo'),
        sources:{
          earth:{type:'raster',tiles:['https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}'],tileSize:256,maxzoom:16,
            attribution:'Imagery: USDA, <a href="https://www.usgs.gov/programs/national-geospatial-program/national-map" target="_blank" rel="noopener">USGS</a>'},
          streets:{type:'raster',tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],tileSize:256,maxzoom:19,attribution:osmCredit},
          terrain:terrainSource(15),
          // Hillshading and geometry need separate DEM caches in MapLibre.
          'terrain-shading':terrainSource(15),
          buildings:{type:'vector',url:'https://tiles.openfreemap.org/planet'},
          active:{type:'geojson',data:collection([])}, preview:{type:'geojson',data:collection([])},
          grid:{type:'geojson',data:collection([])},
          accuracy:{type:'geojson',data:collection([])}
        },
        terrain:{source:'terrain',exaggeration:relief},
        light:{anchor:'viewport',color:'#ffffff',intensity:.65,position:[1.5,225,55]},
        layers:[
          {id:'space',type:'background',paint:{'background-color':'#0b1520'}},
          {id:'earth',type:'raster',source:'earth',layout:{visibility:basemap==='earth'?'visible':'none'},paint:{'raster-fade-duration':250}},
          {id:'streets',type:'raster',source:'streets',layout:{visibility:basemap==='streets'?'visible':'none'}},
          {id:'holo-ground',type:'background',layout:{visibility:basemap==='holo'?'visible':'none'},paint:{'background-color':'#000000'}},
          {id:'holo-hills',type:'hillshade',source:'terrain-shading',layout:{visibility:basemap==='holo'?'visible':'none'},paint:{'hillshade-shadow-color':'#00040c','hillshade-highlight-color':'#989d9f','hillshade-accent-color':'#434749','hillshade-exaggeration':.85,'hillshade-illumination-direction':315,'hillshade-illumination-anchor':'map'}},
          {id:'holo-water',type:'fill',source:'buildings','source-layer':'water',layout:{visibility:basemap==='holo'?'visible':'none'},paint:{'fill-color':'#1a2227','fill-opacity':.75}},
          {id:'holo-grid',type:'line',source:'grid',layout:{visibility:basemap==='holo'?'visible':'none'},paint:{'line-color':'#d9dfe1','line-opacity':.05,'line-width':.5}},
          {id:'holo-roads-glow',type:'line',source:'buildings','source-layer':'transportation',layout:{visibility:basemap==='holo'?'visible':'none','line-cap':'round','line-join':'round'},paint:{'line-color':'#d5dbdd','line-opacity':.18,'line-width':['interpolate',['linear'],['zoom'],10,1,16,9,19,16],'line-blur':3}},
          {id:'holo-roads',type:'line',source:'buildings','source-layer':'transportation',layout:{visibility:basemap==='holo'?'visible':'none','line-cap':'round','line-join':'round'},paint:{'line-color':'#e2e6e7','line-opacity':.4,'line-width':['interpolate',['linear'],['zoom'],10,.4,16,1.4,19,3]}},
          {id:'accuracy',type:'fill',source:'accuracy',paint:{'fill-color':'#70ffdb','fill-opacity':.09}},
          {id:'accuracy-outline',type:'line',source:'accuracy',paint:{'line-color':'#a0f4da','line-opacity':.4,'line-width':1}},
          {id:'buildings',type:'fill-extrusion',source:'buildings','source-layer':'building',minzoom:13,
            filter:['!=',['get','hide_3d'],true],paint:{'fill-extrusion-color':'#bddacf',
              'fill-extrusion-height':['max',0,['coalesce',['get','render_height'],3]],
              'fill-extrusion-base':['max',0,['coalesce',['get','render_min_height'],0]],
              'fill-extrusion-opacity':.82}},
          {id:'holo-building-edges',type:'line',source:'buildings','source-layer':'building',minzoom:13,layout:{visibility:basemap==='holo'?'visible':'none'},paint:{'line-color':'#f0f2f3','line-width':.6,'line-opacity':.38}},
          ...['active','preview'].flatMap(source=>[
            {id:`${source}-glow`,type:'line',source,layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':'#49eaff','line-width':17,'line-blur':7,'line-opacity':.4}},
            {id:`${source}-outline`,type:'line',source,layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':'#093d30','line-width':9}},
            {id:source,type:'line',source,layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':source==='active'?'#63ffd2':'#effff9','line-width':5,...(source==='preview'?{'line-dasharray':[2,1.5]}:{})}}
          ])
        ]}
    });
    this.map.addControl(new gl.NavigationControl({visualizePitch:true}), 'bottom-right');
    this.map.addControl(new gl.ScaleControl({maxWidth:80,unit:'metric'}), 'bottom-left');
    this.map.addControl(new gl.AttributionControl({compact:true}), 'bottom-right');
    this.map.getCanvas().setAttribute('aria-label','3D Earth map. Drag to pan; Control-drag to rotate and tilt.');
    const output=document.createElement('canvas');output.width=640;output.height=360;
    const context=output.getContext('2d',{willReadFrequently:true});
    this.map.on('render',()=>{
      if(!publishHud||!this.ready||this.destroyed||this.hudBusy||performance.now()-(this.hudSent||0)<100||
          !(this.data?.route||this.data?.preview))return;
      this.hudSent=performance.now();this.hudBusy=true;
      try {
        const canvas=this.map.getCanvas();
        const scale=Math.max(640/canvas.clientWidth,306/canvas.clientHeight);
        const ox=(640-canvas.clientWidth*scale)/2,oy=38+(306-canvas.clientHeight*scale)/2;
        context.fillStyle='#000';context.fillRect(0,0,640,360);
        context.save();context.beginPath();context.rect(0,38,640,306);context.clip();
        context.drawImage(canvas,ox,oy,canvas.clientWidth*scale,canvas.clientHeight*scale);
        const selected=this.data.route||this.data.preview;
        const projected=selected.geometry.map(point=>{
          const p=this.map.project(lngLat(point));
          return {x:ox+p.x*scale,y:oy+p.y*scale};
        });
        // Route-direction chevrons follow the geometry, never inferred device heading.
        context.save();context.lineCap='round';context.lineJoin='round';
        const routePath=new Path2D();
        projected.forEach((p,i)=>i?routePath.lineTo(p.x,p.y):routePath.moveTo(p.x,p.y));
        const stale=this.data.route&&['location_lost','off_route','paused'].includes(this.data.state);
        context.globalAlpha=stale?.4:1;
        context.strokeStyle='#021318';context.lineWidth=12;context.stroke(routePath);
        context.strokeStyle='#37b7d9';context.shadowColor='#35d8ff';context.shadowBlur=9;
        context.lineWidth=6;context.stroke(routePath);context.shadowBlur=0;
        context.strokeStyle='#b8f8ff';context.lineWidth=2;
        if(!this.data.route)context.setLineDash([10,7]);
        context.stroke(routePath);context.setLineDash([]);
        let spacing=28,arrows=0;
        for(let i=1;i<projected.length&&arrows<14;i++){
          const a=projected[i-1],b=projected[i],dx=b.x-a.x,dy=b.y-a.y,length=Math.hypot(dx,dy);
          if(length<.01)continue;
          while(spacing<length&&arrows<14){
            const x=a.x+dx*spacing/length,y=a.y+dy*spacing/length;
            if(x>16&&x<624&&y>20&&y<324){
              context.save();context.translate(x,y);context.rotate(Math.atan2(dy,dx));
              context.beginPath();context.moveTo(-6,-5);context.lineTo(1,0);context.lineTo(-6,5);
              context.strokeStyle='#001b22';context.lineWidth=6;context.stroke();
              context.strokeStyle='#b7ffff';context.lineWidth=3;context.stroke();context.restore();arrows++;
            }
            spacing+=48;
          }
          spacing-=length;
        }
        const end=projected.at(-1);
        if(end&&end.x>14&&end.x<626&&end.y>30&&end.y<325){
          context.strokeStyle='#a4ffff';context.lineWidth=2;
          context.beginPath();context.moveTo(end.x,end.y);context.lineTo(end.x,end.y-20);context.stroke();
          context.fillStyle='#a4ffff';context.fillRect(end.x,end.y-28,14,10);
          context.fillStyle='#001319';context.fillRect(end.x+3,end.y-25,4,4);context.fillRect(end.x+8,end.y-21,4,3);
        }
        context.restore();
        // DOM markers do not belong to the WebGL canvas; project the actual fix.
        const fix=this.data.fix;
        if(fix?.guidance_usable){
          const point=this.map.project(lngLat(fix.point)),canvas=this.map.getCanvas();
          context.fillStyle='#ffffff';context.beginPath();
          context.arc(ox+point.x*scale,oy+point.y*scale,5,0,Math.PI*2);context.fill();
        }
        context.restore();
        context.fillStyle='#000';context.fillRect(0,0,640,38);
        context.fillStyle='#edffff';context.font='600 20px sans-serif';
        context.fillText(selected.destination.slice(0,26),12,26);
        const distance=this.data.route?this.data.remaining_m:selected.distance_m;
        const duration=this.data.route?this.data.remaining_s:selected.duration_s;
        if(Number.isFinite(distance)&&Number.isFinite(duration)){
          context.textAlign='right';context.fillStyle='#8eeeff';context.font='18px sans-serif';
          context.fillText(`${(distance/1000).toFixed(1)} km · ${Math.ceil(duration/60)} min`,628,26);
          context.textAlign='left';
        }
        context.fillStyle='#000';context.fillRect(0,344,640,16);
        context.fillStyle='#ddd';context.font='10px sans-serif';
        context.fillText('© OpenStreetMap · © OpenMapTiles · OpenFreeMap · Mapterhorn · USGS',8,356);
        const pixels=context.getImageData(0,0,640,360).data;
        for(let i=0;i<pixels.length;i+=4){const red=pixels[i];pixels[i]=pixels[i+2];pixels[i+2]=red;}
        localFetch('/api/hud/map-frame',{method:'POST',headers:{'Content-Type':'application/octet-stream'},
          body:pixels,signal:AbortSignal.timeout(1500)}).catch(()=>{}).finally(()=>{this.hudBusy=false;});
      }catch{this.hudBusy=false;}
    });
    this.hudTimer=setInterval(()=>{if(!this.destroyed){if(this.publishHud)this.map.redraw();else this.map.triggerRepaint();}},100);
    this.map.on('load',()=>{
      if(this.destroyed)return;
      this.ready=true;
      if(this.data)this.update(this.data);
      this.caption(); onReady();
    });
    this.map.on('sourcedata',event=>{
      if(event.sourceId===this.terrainSource&&event.sourceDataType==='content'){
        this.terrainReady=true;this.terrainError=false;this.caption();
      }
    });
    this.map.on('error',event=>{
      if(this.destroyed)return;
      if(event.sourceId===this.terrainSource||event.sourceId===`${this.terrainSource}-shading`){
        if(!this.coarseTerrain)this.useCoarseTerrain();
        else{this.terrainError=true;this.caption();}
      }
      else if(event.sourceId==='buildings'){this.buildingError=true;this.caption();}
      else if(['earth','streets'].includes(event.sourceId))onStatus('Imagery unavailable here · Try the other map view');
      else if(!event.sourceId)onStatus('A 3D layer could not load · 2D view is available');
    });
    this.map.on('webglcontextlost',()=>{if(!this.destroyed)onFailure('3D graphics stopped. Showing the 2D map.');});
    this.map.on('moveend',()=>{this.cameraStatus();this.updateGrid();});
    this.map.on('idle',()=>{
      if(this.destroyed)return;
      if(Number.isFinite(this.map.queryTerrainElevation(this.map.getCenter()))){
        this.terrainReady=true;this.terrainError=false;
      }
      this.caption();this.cameraStatus();this.terrainStatus();
    });
    // Initialization can fail asynchronously (for example a worker couldn't start).
    this.loadTimer=setTimeout(()=>{if(!this.ready&&!this.destroyed)onFailure('3D did not finish loading. Showing the 2D map.');},20000);
  }
  caption(){
    if(this.destroyed)return;
    const terrain=this.terrainError?'Terrain unavailable':this.terrainReady?`${this.coarseTerrain?'Standard':'Detailed'} terrain · ${this.relief}× height`:'Terrain loading…';
    this.onStatus(`3D ${this.basemap==='holo'?'Hologram':this.basemap==='earth'?'Earth':'Streets'} · ${terrain}${this.buildingError?' · Buildings unavailable':''}`);
  }
  cameraStatus(){
    if(this.destroyed)return;
    const tilt=Math.round(this.map.getPitch()), bearing=Math.round((this.map.getBearing()+360)%360);
    const readout=document.getElementById('map-camera');
    readout.textContent=`TILT ${tilt}° · BEARING ${bearing}°`;
  }
  useCoarseTerrain(){
    // High-resolution DEM coverage is regional. Keep real global terrain when
    // a detailed tile is missing, rather than silently replacing it with a plane.
    this.coarseTerrain=true;this.terrainReady=false;this.terrainSource='terrain-coarse';
    this.map.addSource(this.terrainSource,terrainSource(12));
    this.map.addSource(`${this.terrainSource}-shading`,terrainSource(12));
    const hills=this.map.getStyle().layers.find(layer=>layer.id==='holo-hills');
    this.map.removeLayer('holo-hills');
    this.map.addLayer({...hills,source:`${this.terrainSource}-shading`},'holo-water');
    this.map.setTerrain({source:this.terrainSource,exaggeration:this.relief});
    this.caption();
  }
  setRelief(value){
    const relief=Number(value);
    if(![1,3,6].includes(relief))return;
    this.relief=relief;
    if(!this.ready)return;
    this.map.setTerrain({source:this.terrainSource,exaggeration:relief});
    this.caption();this.terrainStatus();
  }
  terrainStatus(){
    const readout=document.getElementById('map-elevation');
    if(!this.ready||this.terrainError||!this.terrainReady){readout.textContent='Ground elevation unavailable';return;}
    if(this.map.getZoom()<10){readout.textContent='Zoom in to inspect ground elevation';return;}
    const elevation=this.map.queryTerrainElevation(this.map.getCenter());
    // MapLibre returns exaggerated elevation; the displayed measurement must
    // always remain the unscaled DEM value, never a device altitude reading.
    readout.textContent=Number.isFinite(elevation)?`Ground at map center ≈ ${Math.round(elevation/this.relief)} m above sea level`:'Ground elevation unavailable';
  }
  setBasemap(style){
    this.basemap=style;
    if(!this.ready||this.appliedBasemap===style)return;
    this.appliedBasemap=style;
    this.map.setSky(skyStyle(style==='holo'));
    for(const id of ['earth','streets'])this.map.setLayoutProperty(id,'visibility',id===style?'visible':'none');
    for(const id of ['holo-ground','holo-hills','holo-water','holo-grid','holo-roads-glow','holo-roads','holo-building-edges'])this.map.setLayoutProperty(id,'visibility',style==='holo'?'visible':'none');
    this.container.classList.toggle('hologram',style==='holo');
    this.map.setPaintProperty('active','line-color',style==='holo'?'#78f3ff':style==='earth'?'#63ffd2':'#007b60');
    this.map.setPaintProperty('preview','line-color',style==='holo'?'#c6faff':style==='earth'?'#effff9':'#baffdf');
    this.map.setPaintProperty('buildings','fill-extrusion-color',style==='holo'?['interpolate',['linear'],['coalesce',['get','render_height'],3],0,'#35383c',8,'#646a70',25,'#969da3',80,'#e7eaec']:'#bddacf');
    this.map.setPaintProperty('buildings','fill-extrusion-opacity',style==='holo' ? 0.92 : 0.82);
    for(const id of ['active','preview']){
      this.map.setPaintProperty(`${id}-outline`,'line-color',style==='holo'?'#324b50':'#093d30');
      this.map.setPaintProperty(`${id}-glow`,'line-opacity',style==='holo' ? 0.18 : 0);
    }
    this.updateGrid();
    this.caption();
  }
  update(data){
    this.data=data;
    if(!this.ready)return;
    this.setBasemap(this.basemap);
    const hazardKey=JSON.stringify(data.hazards?.reports||[]);
    if(hazardKey!==this.hazardKey){
      this.hazardKey=hazardKey;this.hazardMarkers.forEach(marker=>marker.remove());this.hazardMarkers=[];
      for(const report of data.hazards?.reports||[]){
        const element=document.createElement('button');element.className='hazard-marker';element.textContent='!';
        const label=`Reported ${report.kind.replaceAll('_',' ')}${report.lane==='unknown'?'':` · ${report.lane} lane`}`;
        element.setAttribute('aria-label',label);element.title=label;
        const popup=document.createElement('div');popup.textContent=`${label}. Expires ${new Date(report.expires_at*1000).toLocaleTimeString([], {hour:'numeric',minute:'2-digit'})}. Rider observation, unverified.`;
        this.hazardMarkers.push(new gl.Marker({element}).setLngLat(lngLat(report.point)).setPopup(new gl.Popup({offset:18}).setDOMContent(popup)).addTo(this.map));
      }
    }
    const firstLocation=data.fix&&!this.hasLocation;
    if(firstLocation){this.hasLocation=true;this.center();}
    const routeKey=JSON.stringify([data.route?.geometry,data.preview?.geometry]);
    if(routeKey!==this.routeKey){
      this.routeKey=routeKey;
      this.map.getSource('active').setData(line(data.route));
      this.map.getSource('preview').setData(line(data.preview));
      if(data.preview||data.route){if(data.fix)this.center();else this.overview(false);}
    }
    const opacity=['location_lost','off_route'].includes(data.state)?0.35:1;
    for(const id of ['active','active-outline'])this.map.setPaintProperty(id,'line-opacity',opacity);
    this.map.setPaintProperty('active-glow','line-opacity',this.basemap==='holo'?opacity*.18:0);
    this.updatePosition(data.fix);
    if(this.publishHud&&data.route&&data.fix?.guidance_usable){
      const previous=this.followPoint,point=data.fix.point;
      if(!previous||Math.hypot(point[0]-previous[0],(point[1]-previous[1])*Math.cos(point[0]*Math.PI/180))>.00005){
        this.followPoint=[...point];
        // Orient to the local route segment, never pretend this is measured head pose.
        const geometry=data.route.geometry;
        let bearing=this.map.getBearing();
        if(geometry?.length>1){
          let nearest=0,best=Infinity;
          for(let i=0;i<geometry.length-1;i++){
            const d=Math.hypot(geometry[i][0]-point[0],(geometry[i][1]-point[1])*Math.cos(point[0]*Math.PI/180));
            if(d<best){best=d;nearest=i;}
          }
          const a=geometry[nearest];let b=geometry[nearest+1];
          for(let i=nearest+1;i<geometry.length;i++){b=geometry[i];if(Math.hypot(b[0]-a[0],b[1]-a[1])>.00015)break;}
          const target=Math.atan2((b[1]-a[1])*Math.cos(point[0]*Math.PI/180),b[0]-a[0])*180/Math.PI;
          bearing+=((target-bearing+540)%360)-180;
        }
        this.map.easeTo({center:lngLat(point),bearing,zoom:17.2,pitch:65,offset:[0,45],duration:650});
      }
    }
    const selected=data.preview||data.route;
    const markerKey=JSON.stringify([data.results,selected?.destination_id,selected?.geometry.at(-1)]);
    if(markerKey!==this.markerKey){
      this.markerKey=markerKey;
      this.markers.forEach(marker=>marker.remove());this.markers=[];
      data.results.forEach((place,index)=>{
        const element=document.createElement('button');
        element.className=`place-marker${place.id===selected?.destination_id?' selected':''}`;
        element.textContent=String(index+1);element.setAttribute('aria-label',place.name);element.title=place.name;
        const popup=document.createElement('div'),title=document.createElement('b');title.textContent=place.name;
        popup.append(title,document.createTextNode(place.address||'Nearby place'));
        this.markers.push(new gl.Marker({element,pitchAlignment:'viewport',rotationAlignment:'viewport'})
          .setLngLat(lngLat(place.point)).setPopup(new gl.Popup({offset:18}).setDOMContent(popup)).addTo(this.map));
      });
      if(selected&&!data.results.some(place=>place.id===selected.destination_id)){
        const element=document.createElement('div');element.className='destination-marker';element.textContent='⚑';element.title=selected.destination;
        this.markers.push(new gl.Marker({element}).setLngLat(lngLat(selected.geometry.at(-1))).addTo(this.map));
      }
    }
  }
  updateGrid(){
    if(!this.ready||this.basemap!=='holo'||this.destroyed)return;
    const bounds=this.map.getBounds(), zoom=this.map.getZoom();
    const step=zoom<4?30:zoom<8?5:zoom<11 ? 0.1 : zoom<14 ? 0.005 : 0.001;
    const west=Math.max(-180,Math.floor(bounds.getWest()/step)*step),east=Math.min(180,Math.ceil(bounds.getEast()/step)*step);
    const south=Math.max(-85,Math.floor(bounds.getSouth()/step)*step),north=Math.min(85,Math.ceil(bounds.getNorth()/step)*step);
    const features=[];
    for(let x=west;x<=east&&features.length<160;x+=step)features.push({type:'Feature',properties:{},geometry:{type:'LineString',coordinates:[[x,south],[x,north]]}});
    for(let y=south;y<=north&&features.length<240;y+=step)features.push({type:'Feature',properties:{},geometry:{type:'LineString',coordinates:[[west,y],[east,y]]}});
    this.map.getSource('grid').setData(collection(features));
  }
  updatePosition(fix){
    if(!fix){this.position?.remove();this.position=null;this.fixKey='';this.map.getSource('accuracy').setData(collection([]));return;}
    if(!this.position){
      const element=document.createElement('div');element.className='device-position';element.title='Device location';
      this.position=new gl.Marker({element}).setLngLat(lngLat(fix.point)).addTo(this.map);
    }
    this.position.setLngLat(lngLat(fix.point));
    this.position.getElement().classList.toggle('stale',!fix.guidance_usable);
    this.map.setPaintProperty('accuracy','fill-opacity',fix.guidance_usable?.05:0);
    this.map.setPaintProperty('accuracy-outline','line-opacity',fix.guidance_usable?.2:0);
    const key=JSON.stringify([fix.point,fix.accuracy_m]);
    if(key!==this.fixKey){
      this.fixKey=key;
      const ring=[],radius=Math.min(3000,fix.accuracy_m)/6371000,lat=fix.point[0]*Math.PI/180,lon=fix.point[1]*Math.PI/180;
      for(let n=0;n<=48;n++){
        const angle=n/48*Math.PI*2;
        const y=Math.asin(Math.sin(lat)*Math.cos(radius)+Math.cos(lat)*Math.sin(radius)*Math.cos(angle));
        const x=lon+Math.atan2(Math.sin(angle)*Math.sin(radius)*Math.cos(lat),Math.cos(radius)-Math.sin(lat)*Math.sin(y));
        ring.push([x*180/Math.PI,y*180/Math.PI]);
      }
      this.map.getSource('accuracy').setData(collection([{type:'Feature',properties:{},geometry:{type:'Polygon',coordinates:[ring]}}]));
    }
  }
  overview(animate=true){
    const selected=this.data?.preview||this.data?.route;
    if(!selected){this.center();return;}
    const bounds=new gl.LngLatBounds();selected.geometry.forEach(point=>bounds.extend(lngLat(point)));
    this.map.fitBounds(bounds,{padding:{top:80,bottom:70,left:45,right:45},pitch:68,bearing:-24,maxZoom:16,duration:animate&&!reducedMotion()?1000:0});
  }
  center(){
    if(!this.data?.fix)return;
    const geometry=(this.data.route||this.data.preview)?.geometry;
    let bearing=-24;
    if(geometry?.length>1){
      const origin=geometry[0];
      const ahead=geometry.find(point=>Math.hypot(point[0]-origin[0],point[1]-origin[1])>.0003);
      if(ahead)bearing=Math.atan2((ahead[1]-origin[1])*Math.cos(origin[0]*Math.PI/180),ahead[0]-origin[0])*180/Math.PI;
    }
    // Align the preview to route travel, not an unavailable head/vehicle heading.
    this.map.easeTo({center:lngLat(this.data.fix.point),zoom:17.2,pitch:65,bearing,
      offset:[0,70],duration:reducedMotion()?0:900});
  }
  terrainView(){
    this.map.easeTo({zoom:13.5,pitch:72,bearing:-24,duration:reducedMotion()?0:1000});
  }
  globe(){
    this.map.flyTo({center:this.data?.fix?lngLat(this.data.fix.point):this.map.getCenter(),zoom:1.1,pitch:0,bearing:0,duration:reducedMotion()?0:1800});
  }
  tilt(){this.map.easeTo({pitch:this.map.getPitch()<30?68:0,duration:reducedMotion()?0:700});}
  rotate(){this.map.easeTo({bearing:this.map.getBearing()+45,duration:reducedMotion()?0:600});}
  resize(){this.map.resize();}
  destroy(){this.destroyed=true;clearInterval(this.hudTimer);clearTimeout(this.loadTimer);this.markers.forEach(marker=>marker.remove());this.hazardMarkers.forEach(marker=>marker.remove());this.position?.remove();this.map.remove();}
}
