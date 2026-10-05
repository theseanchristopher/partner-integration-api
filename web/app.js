'use strict';
const $ = id => document.getElementById(id);
const form = $('lookup-form');
let busy = false;
let lastResponse = null;
const pick = name => form.elements[name].value;
const json = value => JSON.stringify(value, null, 2);
const newKey = () => `web-${crypto.randomUUID()}`;
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
function event(message) {
  const list = $('activity');
  list.querySelector('.empty-event')?.remove();
  const item = document.createElement('li');
  const time = document.createElement('time');
  time.textContent = new Date().toLocaleTimeString([], {hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit'});
  const text = document.createElement('span'); text.textContent = message;
  item.append(time, text); list.append(item); list.scrollTop = list.scrollHeight;
}
function badge(label, state = '') { $('status-badge').textContent = label; $('status-badge').className = `status-badge ${state}`; }
function showResponse(status, data) { lastResponse = data; $('http-status').textContent = `HTTP ${status}`; $('response-json').textContent = json(data); }
async function api(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 25000);
  try {
    const result = await fetch(path, {...options, signal:controller.signal, cache:'no-store'});
    const text = await result.text();
    let data;
    try { data = JSON.parse(text); } catch { throw new Error('The demonstration API did not return JSON. Check that the backend is deployed.'); }
    return {status:result.status, ok:result.ok, data};
  } finally { clearTimeout(timer); }
}
function refreshRequest() {
  const mode = pick('mode');
  $('key-field').hidden = mode !== 'async';
  $('idempotency-key').required = mode === 'async';
  $('request-path').textContent = mode === 'sync' ? '/partner-eligibility' : '/eligibility-requests';
  $('request-json').textContent = json({merchantId:'merchant-1001',component:pick('component')});
  drawArchitecture(mode);
}
function lock(value) {
  busy = value;
  for (const element of form.elements) element.disabled = value;
  $('run-button').textContent = value ? 'Request in progress…' : 'Run lookup ↗';
}
form.addEventListener('change', refreshRequest);
$('new-key').addEventListener('click', () => { $('idempotency-key').value = newKey(); });
$('copy-response').addEventListener('click', async () => {
  if (lastResponse === null) return;
  try { await navigator.clipboard.writeText(json(lastResponse)); $('copy-response').textContent = 'Copied'; setTimeout(() => {$('copy-response').textContent='Copy';},1500); }
  catch { $('result-summary').textContent = 'Select the response text to copy it.'; }
});
form.addEventListener('submit', async e => {
  e.preventDefault(); if (busy) return;
  const mode = pick('mode'), component = pick('component'), key = $('idempotency-key').value.trim();
  if (mode === 'async' && !/^[A-Za-z0-9_-]{1,128}$/.test(key)) { $('result-summary').textContent='Use 1–128 letters, numbers, underscores, or hyphens for the key.'; return; }
  lock(true); $('activity').replaceChildren(); $('result-summary').textContent=''; lastResponse=null;
  $('response-json').textContent='Waiting for the API…'; $('http-status').textContent='Sending'; badge('Sending','busy');
  const start = performance.now();
  try {
    event(`Submitted ${mode} lookup for ${component}.`);
    const headers = {'Content-Type':'application/json'}; if(mode==='async') headers['Idempotency-Key']=key;
    let result = await api('/demo/lookup',{method:'POST',headers,body:JSON.stringify({mode,component})});
    showResponse(result.status,result.data);
    event(`Submission returned HTTP ${result.status}.`);
    if (!result.ok) { badge('Request rejected','error'); $('result-summary').textContent=result.data.message || 'Request was rejected.'; return; }
    if(mode==='sync') {
      badge('Completed','success');
      $('result-summary').textContent=`Lookup complete · ${result.data.status} · Eligible: ${result.data.eligible}`;
      event('Received the eligibility result on the original request.'); return;
    }
    const requestId = result.data.requestId;
    if(!/^req-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$/.test(requestId || '')) throw new Error('The API returned an invalid request ID.');
    badge('Accepted','busy'); event(`Accepted request ${requestId}.`);
    let previousStatus = '';
    for(let i=0;i<20;i++) {
      await sleep(3000);
      result = await api(`/demo/requests/${encodeURIComponent(requestId)}`);
      showResponse(result.status,result.data);
      if(!result.ok) {badge('Status unavailable','error'); $('result-summary').textContent=result.data.message || 'Status lookup failed.'; event(`Status lookup returned HTTP ${result.status}.`); return;}
      const state = result.data.status;
      if(state !== previousStatus){event(`Status endpoint reports ${state}.`);previousStatus=state;}
      if(state==='SUCCEEDED'){badge('Succeeded','success');const saved=result.data.result;$('result-summary').textContent=`Saved result · ${saved.status} · Eligible: ${saved.eligible}`;return;}
      if(state==='FAILED'){badge('Failed','error');$('result-summary').textContent=result.data.error?.message || 'Processing failed.';return;}
      badge(state==='PROCESSING'?'Processing':'Pending','busy');
    }
    badge('Still pending','busy'); $('result-summary').textContent=`Polling stopped after 20 checks. Request ${requestId} remains available through the status API. Processing has not been cancelled.`; event('Reached the polling limit; no terminal result was observed.');
  } catch(error) {
    badge('Unavailable','error'); const message=error.name==='AbortError'?'The browser request timed out. An asynchronous submission may still have been accepted; retry with the same idempotency key.':error.message;
    $('result-summary').textContent=message;event(message);
  } finally { $('elapsed').textContent=`${((performance.now()-start)/1000).toFixed(1)}s elapsed`; lock(false); }
});
function node(title,detail) { const el=document.createElement('div');el.className='flow-node';el.textContent=title;const small=document.createElement('small');small.textContent=detail;el.append(small);return el; }
function arrow() { const el=document.createElement('div');el.className='flow-arrow';el.textContent='↓';el.setAttribute('aria-hidden','true');return el; }
function drawArchitecture(mode) {
  $('sync-tab').setAttribute('aria-pressed',String(mode==='sync'));$('async-tab').setAttribute('aria-pressed',String(mode==='async'));
  const sequence=document.createElement('div');sequence.className='flow-sequence';
  const add=(title,detail)=>{if(sequence.childElementCount)sequence.append(arrow());sequence.append(node(title,detail));};
  add('Client → Unified API Gateway','Cognito JWT · scope validation');
  if(mode==='sync')add('Synchronous Lambda','partner-api-service-eligibility · authorize and map');
  else {
    add('Ingestion/status Lambda','partner-api-async-api · validate and authorize');
    add('DynamoDB → DynamoDB Streams','Atomic request + idempotency records · HTTP 202 returned separately');
    add('Dispatcher Lambda → SQS ProcessingQueue','partner-api-async-dispatcher');
    add('Worker Lambda','partner-api-async-worker · claim in DynamoDB and map');
  }
  sequence.append(arrow()); const branches=document.createElement('div');branches.className='flow-branches';
  const a=document.createElement('div');a.className='flow-branch';a.append(node('Component A API Gateway','IAM role credentials · SigV4'),arrow(),node('Component A Lambda','partner-api-components-component-a'));
  const b=document.createElement('div');b.className='flow-branch';b.append(node('SSM → Component B API Gateway','Encrypted credentials · mTLS · S3 CA truststore'),arrow(),node('Component B Lambda','partner-api-component-b-lookup'));
  branches.append(a,b);sequence.append(branches);
  add('Calling Lambda maps component response','A: merchant_id / status · B: accountReference / enabled');
  if(mode==='sync')add('Unified API Gateway → Client','HTTP 200 · unified eligibility result');
  else {add('DynamoDB saves processing outcome','SUCCEEDED + result or FAILED + error');add('Client polls → Gateway → Ingestion/status Lambda','Separate GET request · saved outcome returned');}
  $('flow-diagram').replaceChildren(sequence);
  const info=document.createElement('div');info.className='failure-info';const title=document.createElement('h3');const body=document.createElement('p');
  title.textContent=mode==='async'?'Independent failure paths':'Same request, complete result';
  body.textContent=mode==='async'?'DispatchFailureQueue receives exhausted stream-dispatch failure metadata. Worker failures retry through ProcessingQueue; after five unsuccessful deliveries, ProcessingDLQ invokes partner-api-async-dlq-handler to archive the message and record FAILED. Polling is independent of processing.':'No processing queue or status database is used in this path. A completed lookup returns 200, including an inactive merchant. Component 404 responses are mapped to merchant-not-found; connection failures currently return 500.';
  info.append(title,body);$('failure-notes').replaceChildren(info);
}
$('sync-tab').addEventListener('click',()=>drawArchitecture('sync'));
$('async-tab').addEventListener('click',()=>drawArchitecture('async'));
$('idempotency-key').value=newKey();refreshRequest();
