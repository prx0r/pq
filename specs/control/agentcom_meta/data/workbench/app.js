const labels={0:'GO',1:'ORDERS',2:'STATUS',3:'BLOCK',4:'OPTION',5:'APPROVE',6:'DENY',7:'ANSWER',8:'EXPAND',9:'HALT'};
let inputKind='text',currentTask=null,presentedAt=performance.now(),lastPayloadId=null;
const post=async(u,d)=>{const r=await fetch(u,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(d)});return {status:r.status,...await r.json()}};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const keypad=document.querySelector('#keypad');
for(let i=0;i<10;i++){
  const b=document.createElement('button');b.className='key';b.innerHTML=`${i}<small>${labels[i]}</small>`;
  b.onclick=async()=>{if(!currentTask)return;navigator.vibrate?.(18);const sec=Math.max(.05,(performance.now()-presentedAt)/1000);await post('/api/key',{task_id:currentTask,key:i,human_seconds:sec,payload_id:lastPayloadId});lastPayloadId=null;await refresh()};keypad.appendChild(b)
}
document.querySelectorAll('.tab').forEach(x=>x.onclick=()=>{document.querySelectorAll('.tab').forEach(y=>y.classList.remove('active'));x.classList.add('active');inputKind=x.dataset.kind});
document.querySelector('#send').onclick=async()=>{const t=document.querySelector('#input');if(!currentTask||!t.value.trim())return;const raw=t.value;t.value='';const r=await post('/api/input',{task_id:currentTask,kind:inputKind,text:raw});lastPayloadId=r.payload?.id||null;document.querySelector('#payloadState').textContent=lastPayloadId?`payload sealed ${r.payload.sha256.slice(0,10)}… · press 7/5/etc to submit the decision`:'payload not stored';};
function rows(xs,fn){return (xs||[]).map(fn).join('')||'<div class="row"><span>—</span><span>none</span></div>'}
async function runDecision(id,decision){navigator.vibrate?.(15);await post('/api/run-decision',{run_id:id,decision});await refresh()}
window.runDecision=runDecision;
async function refresh(){
 const s=await fetch('/api/state',{cache:'no-store'}).then(r=>r.json());const t=(s.human_tasks||[])[0];const changed=(t?.id||null)!==currentTask;currentTask=t?.id||null;if(changed){presentedAt=performance.now();lastPayloadId=null;document.querySelector('#payloadState').textContent='payloads are sealed locally; raw text/code is not in logs'}
 document.querySelector('#taskTitle').textContent=t?.summary||'No task queued';
 document.querySelector('#taskMeta').textContent=t?`${t.class||''} · risk ${t.risk??'?'} · wait-cost ${t.cost_of_wait??0} · ${t.learning?.stage||'HUMAN'} ${(100*Number(t.learning?.progress??0)).toFixed(0)}% · support ${t.learning?.support??0}`:'Autonomous branches continue while you are idle.';
 document.querySelector('#options').innerHTML=t?.options?.length?'<div class="options">'+t.options.map((o,i)=>`<span>${i+1}. ${esc(o)}</span>`).join('')+'</div>':'';
 const money=(s.runs||[]).reduce((a,r)=>a+Number(r.expected_money??r.cost??0),0);document.querySelector('#budget').textContent=`${money.toFixed(3)} planned`;
 document.querySelector('#runs').innerHTML=rows(s.runs,r=>`<div class="run"><div class="runhead"><b>${esc(r.id||'run')}</b><span class="status">${esc(r.status||'')}</span></div><div class="meta">${esc(r.processor||r.policy||'')} ${esc(r.model||'')} · proof ${esc(r.proof_target||'?')} · $${Number(r.expected_money??r.cost??0).toFixed(3)} · ${Number(r.expected_tokens??0)} tok · ${Number(r.expected_seconds??0)}s</div><div class="meta">authority: ${esc(r.authority||r.capability||'none')}</div>${r.status==='PROPOSED'?`<div class="runbuttons"><button onclick="runDecision('${esc(r.id)}','approve')">APPROVE</button><button onclick="runDecision('${esc(r.id)}','deny')">DENY</button></div>`:''}</div>`);
 document.querySelector('#wallet').innerHTML=rows(s.wallet,w=>`<div class="row"><span>${esc(w.capability||'grant')}</span><span>${esc(w.status||'')} ${w.value!=null?esc(w.value)+' '+esc(w.asset||''):''}</span></div>`);
 const m=s.learning?.metrics||{};document.querySelector('#learning').textContent=`policy n=${m.n??0} · acc=${Number(m.accuracy??0).toFixed(3)} · brier=${Number(m.brier??0).toFixed(3)} · autonomy-eff=${Number(m.autonomy_efficiency??0).toFixed(3)}`;
 document.querySelector('#logs').textContent=(s.logs||[]).slice(-80).map(x=>JSON.stringify(x)).join('\n');
}
setInterval(refresh,1200);refresh();if('serviceWorker'in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
