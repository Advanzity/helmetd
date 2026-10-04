import {localFetch} from './local-api.js';
const health = document.getElementById('helmet-health');
let pending = false, refreshing = false, requestVersion = 0;
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
function feedback(element, text, error = false) {
  if (element.textContent !== text) {
    element.textContent = text;
    if (!reducedMotion.matches) {
      element.getAnimations().forEach(animation => animation.cancel());
      element.animate([{opacity: .35, transform: 'translateY(3px)'}, {opacity: 1, transform: 'translateY(0)'}], {duration: 220, easing: 'ease-out'});
    }
  }
  element.classList.toggle('interaction-error', error);
}
function select(button, selected) {
  const value = String(selected);
  if (button.getAttribute('aria-pressed') === value) return;
  button.setAttribute('aria-pressed', value);
  if (selected && !reducedMotion.matches) button.animate(
    [{transform: 'scale(.97)'}, {transform: 'scale(1)'}],
    {duration: 220, easing: 'cubic-bezier(.2,.8,.2,1)'});
}
const buttons=[...document.querySelectorAll('[data-helmet-signal], [data-helmet-camera], [data-helmet-mode]')];

async function control(action = 'status', value = '') {
  const version = ++requestVersion;
  const response = await localFetch('/api/hud', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action, value}),
    signal: AbortSignal.timeout(3000),
  });
  const state = await response.json();
  if (version !== requestVersion) return;
  if (!response.ok || state.status !== 'ok') throw new Error('Helmet disconnected');
  feedback(health, (state.cameras || []).map(camera =>
    `${camera.label}: ${camera.fresh ? 'live' : camera.visible ? 'video delayed' : camera.failed ? 'reconnecting' : 'offline'}`).join(' · '));
  for (const button of document.querySelectorAll('[data-helmet-signal]'))
    select(button, button.dataset.helmetSignal === state.signal);
  for (const button of document.querySelectorAll('[data-helmet-mode]'))
    select(button, button.dataset.helmetMode === (state.quiet ? 'quiet' : state.panels===7 ? 'full' : ''));
  for (const button of document.querySelectorAll('[data-helmet-camera]'))
    select(button, button.dataset.helmetCamera === state.camera_view);
}

for (const button of document.querySelectorAll('[data-helmet-signal], [data-helmet-camera], [data-helmet-mode]')) {
  button.addEventListener('click', async () => {
    if (pending) return;
    pending = true;
    buttons.forEach(item=>item.disabled=true);
    button.setAttribute('aria-busy','true');
    feedback(health, 'Applying…');
    try {
      await control(button.dataset.helmetMode !== undefined ? 'mode' : button.dataset.helmetSignal !== undefined ? 'signal' : 'camera',
        button.dataset.helmetMode ?? button.dataset.helmetSignal ?? button.dataset.helmetCamera);
    } catch (error) { feedback(health, error.message, true); }
    finally { pending = false;buttons.forEach(item=>item.disabled=false);button.removeAttribute('aria-busy'); }
  });
}

async function refresh() {
  if (!pending && !refreshing && !document.hidden) {
    refreshing=true;
    try { await control(); }
    catch { if (!pending) feedback(health, 'Helmet disconnected · Reconnecting…', true); }
    finally{refreshing=false;}
  }
  setTimeout(refresh, 1500);
}
refresh();

const saveButton=document.getElementById('save-video');
saveButton.addEventListener('click',async()=>{
 saveButton.disabled=true;saveButton.setAttribute('aria-busy','true');
 const status=document.getElementById('save-video-status');feedback(status, 'Saving footage…');
 try{const response=await localFetch('/api/recordings/save',{method:'POST',signal:AbortSignal.timeout(10000)});
 const result=await response.json();feedback(status, response.ok&&result.saved?`Saved ${Object.keys(result.cameras).join(', ')} clips`:result.reason||'Save unavailable', !(response.ok&&result.saved));}
 catch{feedback(status, 'Could not confirm save', true);}finally{saveButton.disabled=false;saveButton.removeAttribute('aria-busy');}
});

for (const button of document.querySelectorAll('[data-alert-preview]')) {
  button.addEventListener('click', async () => {
    const status = document.getElementById('alert-preview-status');
    button.disabled = true;
    try {
      await control('preview', button.dataset.alertPreview);
      feedback(status, button.dataset.alertPreview === 'off' ? 'Preview stopped' : 'Look through the glasses · preview lasts 5 seconds');
    } catch (error) { feedback(status, error.message, true); }
    finally { button.disabled = false; }
  });
}

const sequence = ['turn','left','person','rear','message'];
let demoStep = 0, demoTimer, demoPaused = false, demoRunning = false, demoVersion = 0;
const demoStart = document.getElementById('demo-sequence');
const demoPause = document.getElementById('demo-sequence-pause');
const demoStop = document.getElementById('demo-sequence-stop');
const demoStatus = document.getElementById('sequence-status');
async function stepDemo(version) {
  if (!demoRunning || demoPaused || version !== demoVersion) return;
  try {
    if (demoStep >= sequence.length) { await stopDemo(); feedback(demoStatus, 'Preview complete · ride view restored'); return; }
    await control('preview', sequence[demoStep]);
    if (version !== demoVersion) return;
    feedback(demoStatus, `Preview ${demoStep+1}/${sequence.length} · ${sequence[demoStep]}`);
    demoStep++;
    demoTimer = setTimeout(()=>stepDemo(version), 5500);
  } catch(error) { await stopDemo(); feedback(demoStatus,error.message,true); }
}
async function stopDemo() {
  demoRunning=false; demoPaused=false; demoVersion++; clearTimeout(demoTimer);
  demoPause.disabled=demoStop.disabled=true; demoPause.textContent='Pause';
  try { await control('preview','off'); } catch {}
  feedback(demoStatus,'Preview stopped');
}
demoStart.addEventListener('click',()=>{
  clearTimeout(demoTimer);demoVersion++;demoStep=0;demoPaused=false;demoRunning=true;
  demoStart.textContent='Replay demo';demoPause.textContent='Pause';demoPause.disabled=demoStop.disabled=false;
  stepDemo(demoVersion);
});
demoPause.addEventListener('click',async()=>{
  demoPaused=!demoPaused; clearTimeout(demoTimer); demoVersion++;
  demoPause.textContent=demoPaused?'Resume':'Pause';
  if(demoPaused){demoStep=Math.max(0,demoStep-1);await control('preview','off');feedback(demoStatus,'Preview paused');}
  else stepDemo(demoVersion);
});
demoStop.addEventListener('click',stopDemo);
async function readiness(recover=false) {
  const output=document.getElementById('readiness-status');
  const button=document.getElementById(recover?'recover-helmet':'check-helmet');button.disabled=true;
  feedback(output,recover?'Starting services and checking Pi…':'Checking…');
  try {
    const response=await localFetch(recover?'/api/recover':'/api/ready',{method:'POST',signal:AbortSignal.timeout(12000)});
    const state=await response.json();if(!response.ok)throw new Error(state.detail||'Check failed');
    feedback(output,recover?`${state.local} · Pi: ${state.pi} · ${state.glasses}`:
      `HUD: ${state.hud?'ready':'offline'} · ${state.cameras.map(c=>`${c.label}: ${c.live?'live':'offline'}`).join(' · ')} · Map: ${state.map?'ready':'unavailable'} · Audio: ${state.audio_configured?'configured (playback unverified)':'not configured'} · ${state.glasses}`);
  }catch(error){feedback(output,error.message,true);}finally{button.disabled=false;}
}
document.getElementById('recover-helmet').addEventListener('click',()=>readiness(true));
document.getElementById('check-helmet').addEventListener('click',()=>readiness());
