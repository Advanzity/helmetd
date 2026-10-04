import {localFetch} from './local-api.js';
const status=document.querySelector('#road-report-status'),list=document.querySelector('#road-report-list'),button=document.querySelector('#refresh-road-reports');
let busy=false;
async function refresh(){
 if(busy)return;busy=true;button.disabled=true;
 try{
  const response=await fetch('/api/game/reports',{cache:'no-store',signal:AbortSignal.timeout(2500)});if(!response.ok)throw Error();
  const {reports}=await response.json();list.replaceChildren();
  status.textContent=reports.length?`${reports.length} active pothole report${reports.length===1?'':'s'} · Game roads`:'No rider reports yet. Press H while riding to add one.';
  for(const report of reports){const row=document.createElement('li'),name=document.createElement('strong'),detail=document.createElement('span');name.textContent='Pothole';detail.textContent=`${Math.round(report.x)}, ${Math.round(-report.z)} m · ${new Date(report.created*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}`;row.append(name,detail);list.append(row);}
 }catch{status.textContent='Reports unavailable. Retry when the local console reconnects.';}finally{busy=false;button.disabled=false;}
}
button.addEventListener('click',refresh);refresh();setInterval(()=>{if(!document.hidden)refresh()},5000);

for(const button of document.querySelectorAll('[data-road-warning]'))button.addEventListener('click',async()=>{
 const output=document.querySelector('#road-warning-status');button.disabled=true;
 try{const response=await localFetch('/api/hud',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'preview',value:button.dataset.roadWarning}),signal:AbortSignal.timeout(3000)});const result=await response.json();if(!response.ok||result.status!=='ok')throw Error('HUD unavailable. Use Start / recover, then retry.');output.textContent=button.dataset.roadWarning==='off'?'Warning cleared.':'Sent to HUD for 5 seconds. Live detections take priority.';}catch(error){output.textContent=error.message;}finally{button.disabled=false;}
});
