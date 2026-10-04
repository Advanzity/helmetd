const $ = id => document.getElementById(id);
const guard = document.querySelector('meta[name="helmetd-token"]').content;
const ns = 'http://www.w3.org/2000/svg';
let current, busy = false, polling = false, lastNotice = '', mapped = false;
const distance = m => m == null ? '—' : m < 1000 ? `${m} m` : `${(m / 1000).toFixed(1)} km`;
const duration = s => s == null ? '—' : `${s === 0 ? 0 : Math.max(1, Math.ceil(s / 60))} min`;
const arrows = {left:'↰', right:'↱', straight:'↑', uturn:'↶', arrive:'⚑', stop:'•'};
const states = {idle:'Ready to plan', navigating:'Navigating', paused:'Paused', off_route:'Off route', location_lost:'Location lost', arrived:'Arrived'};

async function request(name, parameters = {}) {
  const response = await fetch('/api/navigation', {
    method: 'POST', headers: {'Content-Type':'application/json', 'X-Helmetd':guard},
    body: JSON.stringify({name, parameters}), signal: AbortSignal.timeout(4000),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Navigation command failed.');
  return result;
}
function svg(type, attributes, text) {
  const element = document.createElementNS(ns, type);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
  if (text) element.textContent = text;
  return element;
}
function routePoints(route) {
  return route?.legs.length ? [route.legs[0].a, ...route.legs.map(leg => leg.b)].map(p => p.join(',')).join(' ') : '';
}
function drawBase(data) {
  if (mapped) return;
  mapped = true;
  for (const road of data.roads) {
    const a = data.nodes[road.a], b = data.nodes[road.b];
    $('roads').append(svg('line', {x1:a[0], y1:a[1], x2:b[0], y2:b[1], class:road.highway ? 'road highway' : 'road'}));
  }
  for (const [id, label] of Object.entries(data.places)) {
    const [x,y] = data.nodes[id];
    $('places').append(svg('circle',{cx:x,cy:y,r:5}), svg('text',{x:id === 'lookout' ? x+20 : x,y:y + (id === 'lookout' ? -20 : 28),'text-anchor':id === 'lookout' ? 'end' : 'middle'},label));
  }
}
function render(data) {
  if (current && data.revision < current.revision) return;
  current = data; drawBase(data);
  const draft = data.preview, route = draft || data.route;
  $('nav-state').textContent = draft ? 'Route preview' : states[data.state];
  $('route-legend').textContent = draft ? (data.route ? 'Solid: current route · Dashed: preview' : 'Dashed: route preview') : data.route ? 'Solid: current route' : 'Choose a destination';
  $('nav-destination').textContent = route?.destination || 'Where are we riding?';
  $('nav-distance').textContent = distance(draft ? draft.distance_m : data.remaining_m);
  $('nav-time').textContent = duration(draft ? draft.duration_s : data.remaining_s);
  $('nav-preference').textContent = route?.preference === 'avoid_highways' ? 'Avoid highways' : route ? 'Fastest' : 'Motorcycle';
  $('nav-stop').textContent = route?.stop_id ? `Via ${data.places[route.stop_id]}` : 'No added stop';
  const blocked = ['location_lost','off_route'].includes(data.state);
  $('turn-arrow').textContent = blocked ? '—' : data.next_turn ? arrows[data.next_turn.maneuver] : '↗';
  $('turn-distance').textContent = blocked ? 'Guidance suspended' : data.next_turn ? `${draft ? 'Current route · ' : ''}In ${distance(data.next_turn.distance_m)}` : data.state === 'arrived' ? 'Destination reached' : 'Next turn';
  $('turn-instruction').textContent = blocked ? (data.state === 'location_lost' ? 'Waiting for a position' : 'Reroute to continue') : data.next_turn?.instruction || (data.state === 'arrived' ? `At ${data.route.destination} in the demo.` : 'Start a route to see turn guidance.');
  $('route-active').setAttribute('points', routePoints(data.route));
  $('route-active').classList.toggle('uncertain', blocked);
  $('route-preview').setAttribute('points', routePoints(draft));
  $('rider').style.display = data.location ? '' : 'none';
  if (data.location) { $('rider').setAttribute('cx', data.location[0]); $('rider').setAttribute('cy', data.location[1]); }
  $('map-description').textContent = `Fictional motorcycle road network. ${states[data.state]}. ${route ? `Destination ${route.destination}.` : 'No route selected.'}`;
  $('nav-start').hidden = !draft;
  $('nav-start').textContent = data.route ? 'Use this route' : 'Start route';
  $('nav-dismiss').hidden = !draft;
  $('nav-pause').hidden = !['navigating','paused'].includes(data.state);
  $('nav-pause').textContent = data.state === 'paused' ? 'Resume navigation' : 'Pause navigation';
  $('nav-reroute').hidden = data.state !== 'off_route';
  $('nav-cancel').hidden = !data.route && !draft;
  $('nav-add-stop').disabled = busy || !route || blocked;
  $('nav-remove-stop').hidden = !route?.stop_id;
  $('demo-play').textContent = data.playing ? 'Pause demo movement' : 'Play demo · 4×';
  for (const id of ['demo-play','demo-next','demo-miss']) $(id).disabled = busy || data.state !== 'navigating';
  $('demo-location').disabled = busy || !['navigating','paused','off_route','location_lost'].includes(data.state);
  $('demo-location').textContent = data.state === 'location_lost' ? 'Restore location' : 'Lose location';
  $('nav-hud').textContent = data.hud_connected ? 'HUD connected' : 'HUD unavailable · Console works';
  if (lastNotice !== data.notice) {
    lastNotice = data.notice;
    $('nav-notice').textContent = data.notice;
    $('nav-notice').classList.remove('error');
  }
}
async function act(name, parameters = {}) {
  if (busy) return;
  busy = true;
  document.querySelectorAll('#navigation button').forEach(button => button.disabled = true);
  try { const data = await request(name, parameters); lastNotice = ''; render(data); }
  catch (error) { $('nav-notice').textContent = error.message; $('nav-notice').classList.add('error'); }
  finally {
    busy = false;
    document.querySelectorAll('#navigation button').forEach(button => button.disabled = false);
    if (current) render(current);
  }
}
$('nav-form').onsubmit = event => { event.preventDefault(); void act('plan',{destination:$('destination').value, preference:$('preference').value}); };
$('nav-start').onclick = () => act('control',{action:'start'});
$('nav-dismiss').onclick = () => act('control',{action:'cancel_preview'});
$('nav-pause').onclick = () => act('control',{action:current?.state === 'paused' ? 'resume' : 'pause'});
$('nav-reroute').onclick = () => act('control',{action:'reroute'});
$('nav-cancel').onclick = () => act('control',{action:'cancel'});
$('nav-add-stop').onclick = () => act('stop',{action:'add', place:$('stop-place').value});
$('nav-remove-stop').onclick = () => act('stop',{action:'remove', place:''});
$('demo-play').onclick = () => act('demo',{event:'play'});
$('demo-next').onclick = () => act('demo',{event:'next_turn'});
$('demo-miss').onclick = () => act('demo',{event:'miss_turn'});
$('demo-location').onclick = () => act('demo',{event:current?.state === 'location_lost' ? 'restore_location' : 'lose_location'});
$('demo-reset').onclick = () => act('demo',{event:'reset'});
async function poll() {
  if (polling || busy) return;
  polling = true;
  try { render(await request('status')); }
  catch {
    $('nav-state').textContent = 'Disconnected';
    $('nav-hud').textContent = 'Navigation disconnected';
    $('nav-notice').textContent = 'Local navigation is unavailable. Reload after the server reconnects.';
    $('nav-notice').classList.add('error');
    $('turn-distance').textContent = 'Guidance unavailable';
    $('turn-instruction').textContent = 'Waiting for the navigation service';
    $('turn-arrow').textContent = '—';
    $('nav-distance').textContent = $('nav-time').textContent = '—';
    $('rider').style.display = 'none';
    $('route-active').classList.add('uncertain');
    lastNotice = '';
  } finally { polling = false; }
}
void poll();
setInterval(poll, 1000);
