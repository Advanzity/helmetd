import {localFetch} from './local-api.js';
import {helmetAudio} from './helmet-audio.js';
const { Conversation } = window.ElevenLabsClient;

const $ = (id) => document.getElementById(id);
let session = null, lease = '', phase = 'offline', volume = 1, muted = false;
let busy = false, stopping = false, pulseTimer = null, polling = false;
let lastMessage = '', hasMessages = false;
let cueAudio=false,audioSync=Promise.resolve();
function syncAudio(){
  audioSync=audioSync.catch(()=>{}).then(async()=>{
    const active=session;if(!active)return;
    await active.setVolume({volume:helmetAudio.enabled||cueAudio?0:volume});
    await active.setMicMuted(muted||cueAudio);
  });
  return audioSync;
}
window.addEventListener('helmetd-cue-audio',event=>{
  cueAudio=event.detail.active;
  if(cueAudio&&event.detail.text)message(event.detail.text,'agent');
  void syncAudio().catch(()=>status('Could not coordinate guidance and conversation audio.',true));
});

function status(text, error = false) {
  $('status').textContent = text;
  $('status').classList.toggle('error', error);
}

async function api(path, body = {}) {
  const response = await localFetch(`/api/${path}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-Helmetd-Session': lease},
    body: JSON.stringify(body), signal: AbortSignal.timeout(path === 'action' ? 65000 : path === 'start' ? 45000 : 10000),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Local control failed.');
  return data;
}

function message(text, source) {
  if (!text || lastMessage === `${source}:${text}`) return;
  lastMessage = `${source}:${text}`;
  if (!hasMessages) { $('messages').replaceChildren(); hasMessages = true; }
  const line = document.createElement('div');
  line.className = `message ${source}`;
  const author = document.createElement('b');
  author.textContent = source === 'user' ? 'YOU' : 'HELMETD';
  const content = document.createElement('span');
  content.textContent = text;
  line.append(author, content); $('messages').append(line);
  while ($('messages').children.length > 50) $('messages').firstChild.remove();
  $('messages').scrollTop = $('messages').scrollHeight;
}

function controls(active) {
  $('connect').textContent = active ? 'Stop conversation' : 'Talk to Helmetd';
  $('connect').disabled = busy;
  for (const id of ['mute', 'text', 'send']) $(id).disabled = !active;
  $('input').disabled = active || busy; $('output').disabled = active || busy;
  $('signal').classList.toggle('live', active);
}

async function stop(reason = 'Disconnected. Ready when you are.', error = false) {
  void helmetAudio.cancel().catch(()=>{});
  if (stopping) return;
  stopping = true;
  clearInterval(pulseTimer); pulseTimer = null;
  const previous = session; session = null; phase = 'offline';
  try { if (previous) await previous.endSession(); } catch { /* Already disconnected. */ }
  try { if (lease) await api('stop'); } catch { /* The server also expires abandoned sessions. */ }
  lease = ''; busy = false; muted = false;
  $('mute').textContent = 'Mute mic'; controls(false); status(reason, error);
  $('detail').textContent = 'Microphone is off. Your transcript remains here until you reload.';
  stopping = false;
}

async function devices() {
  const permission = await navigator.mediaDevices.getUserMedia({
    audio: {echoCancellation: true, noiseSuppression: true, autoGainControl: true},
  });
  try {
    const available = await navigator.mediaDevices.enumerateDevices();
    for (const [id, kind] of [['input', 'audioinput'], ['output', 'audiooutput']]) {
      const previous = $(id).value;
      const matches = available.filter(d => d.kind === kind);
      $(id).replaceChildren(...matches.map(d => new Option(d.label || 'System default', d.deviceId)));
      const preferred = matches.find(d => d.deviceId === previous) || matches.find(d => d.label.startsWith('MacBook'));
      if (preferred) $(id).value = preferred.deviceId;
    }
  } finally { permission.getTracks().forEach(track => track.stop()); }
}

async function pulse() {
  if (!lease || polling || stopping) return;
  polling = true;
  try {
    const result = await api('pulse', {phase: muted && phase !== 'speaking' ? 'offline' : phase, volume});
    if (result.ending) { await stop(); return; }
    if (result.context && session) session.sendContextualUpdate(result.context);
  } catch { await stop('Local controls disconnected. Click Talk to reconnect.', true); }
  finally { polling = false; }
}

async function start() {
  if (busy) return;
  busy = true; controls(false); status('Checking microphone permission…');
  try {
    await devices();
    await helmetAudio.configure();
    if(helmetAudio.enabled){
      $('output').replaceChildren(new Option('XREAL speakers via Raspberry Pi', ''));
      $('output').disabled=true;
    }
    status('Connecting to Helmetd…');
    const data = await api('start');
    lease = data.session; volume = 1; phase = 'offline';
    pulseTimer = setInterval(pulse, 1000);
    const clientTools = Object.fromEntries(data.tools.map(name => [name, async parameters => {
      const result = await api('action', {name, parameters});
      if(name==='navigation_control'&&parameters.action==='start'&&result.result.status==='ok')window.dispatchEvent(new CustomEvent('helmetd-navigation-start'));
      if(name==='navigation_control')result.result.spoken_guidance=document.getElementById('nav-audio')?.getAttribute('aria-pressed')==='true';
      if (result.result.status === 'ok' && name === 'set_voice_volume') {
        try { volume = result.volume;if(volume===0)await helmetAudio.cancel();window.dispatchEvent(new CustomEvent('helmetd-voice-volume',{detail:{volume}}));await syncAudio(); }
        catch { return JSON.stringify({status: 'error', reason: 'Speaker volume could not change'}); }
      }
      if (name === 'end_conversation' && result.result.ending) setTimeout(() => stop(), 250);
      $('detail').textContent = `Action: ${name.replaceAll('_', ' ')} · ${result.result.status}`;
      return JSON.stringify(result.result);
    }]));
    let endedDuringStart = false;
    const connected = await Conversation.startSession({
      conversationToken: data.token, connectionType: 'webrtc',
      inputDeviceId: $('input').value || undefined,
      outputDeviceId: $('output').value || undefined,
      clientTools,
      onAudio: encoded => {if(!cueAudio)helmetAudio.push(encoded,lease,volume,()=>status('Helmet audio link failed',true));},
      onMessage: ({message: text, source}) => message(text, source === 'user' ? 'user' : 'agent'),
      onModeChange: ({mode}) => {
        if(mode==='listening'&&!cueAudio)void helmetAudio.cancel().catch(()=>{});
        phase = mode;
        status(mode === 'speaking' ? 'Helmetd is speaking' : muted ? 'Microphone muted' : 'Listening');
      },
      onDisconnect: () => {
        endedDuringStart = true;
        if (!stopping) void stop('Connection ended. Click Talk to reconnect.');
      },
      onError: () => { endedDuringStart = true; void stop('Voice connection failed. Click Talk to retry.', true); },
    });
    if (endedDuringStart || !lease) {
      await connected.endSession();
      throw new Error('The voice connection ended during startup. Try again.');
    }
    session = connected; busy = false; controls(true);
    await syncAudio();
    phase = 'listening'; status('Listening');
    $('detail').textContent = helmetAudio.enabled ? 'Connected · Audio routed to XREAL via Pi · Mac microphone' : 'Connected · Mac audio';
    await pulse();
  } catch (error) {
    const reason = error.name === 'NotAllowedError' ? 'Allow microphone access, then try again.'
      : error.name === 'NotFoundError' ? 'No microphone found. Check your audio devices.'
      : 'Could not start voice. Check microphone access and your connection, then try again.';
    await stop(reason, true);
  }
}

$('connect').onclick = () => session ? stop() : start();
$('mute').onclick = async () => {
  if (!session) return;
  try {
    muted = !muted;await syncAudio();
    $('mute').textContent = muted ? 'Unmute mic' : 'Mute mic';
    status(muted ? 'Microphone muted' : 'Listening');
  } catch { status('Could not change microphone state.', true); }
};
$('text-form').onsubmit = (event) => {
  event.preventDefault();
  const text = $('text').value.trim();
  if (!session || !text) return;
  try {
    session.sendUserMessage(text); message(text, 'user'); $('text').value = '';
    phase = 'thinking'; status('Thinking…');
  } catch { status('Message could not be sent.', true); }
};
setInterval(() => {
  if (!session) return;
  const level = phase === 'speaking' ? session.getOutputVolume() : session.getInputVolume();
  $('signal').style.setProperty('--level', String(Math.min(1, Math.max(0, level * 4))));
}, 100);
window.addEventListener('pagehide', () => { void session?.endSession(); });
controls(false);
status('Ready to connect');
