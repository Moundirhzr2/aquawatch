"use strict";
const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const number = value => new Intl.NumberFormat("en-GB").format(value);
const euro = cents => new Intl.NumberFormat("en-GB", {style:"currency",currency:"EUR",maximumFractionDigits:2}).format(cents/100);
const names = {sustained_usage:"Sustained consumption",meter_reset:"Counter reset",missing_reading:"Missing reading",billing_mismatch:"Billing mismatch",duplicate_reading:"Duplicate reading"};
const states = {open:"Open",investigating:"Investigating",resolved:"Resolved",dismissed:"Dismissed"};
let token = "", selectedCase = null, toastTimer, queueRequest = 0;
let overviewDaily = [], chartPoints = [], chartRange = 90, chartIndex = 0;

async function api(path, options = {}) {
  const headers = {...options.headers};
  if (options.method && options.method !== "GET") headers["X-AquaWatch-Token"] = token;
  const response = await fetch(path, {...options, headers});
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const message = typeof data.detail === "string" ? data.detail : data.detail?.[0]?.msg;
    throw new Error(message || `Request failed (${response.status}). Please try again.`);
  }
  return response.json();
}
function toast(message, error = false) {
  clearTimeout(toastTimer);
  const node = $("#toast"); node.textContent = message; node.classList.toggle("error", error); node.hidden = false;
  toastTimer = setTimeout(() => { node.hidden = true; }, error ? 10000 : 6500);
}
function metric(label, value, note, icon, accent = false) {
  return `<article class="metric ${accent ? "accent" : ""}"><div class="metric-head"><span>${esc(label)}</span><span class="metric-symbol" aria-hidden="true"><span class="icon icon-${icon}"></span></span></div><strong>${esc(value)}</strong><p class="metric-note">${note}</p></article>`;
}
function badge(status) { return `<span class="badge ${esc(status)}">${esc(states[status] || status[0].toUpperCase()+status.slice(1))}</span>`; }
function chart(points, {height=200, threshold=null, label="Daily consumption in cubic meters", interactive=false} = {}) {
  if (points.length < 2) return '<p class="empty">Not enough readings to show a trend.</p>';
  const w=720,h=height,pad={t:16,r:12,b:30,l:42}, innerW=w-pad.l-pad.r, innerH=h-pad.t-pad.b;
  const values=points.map(p=>p.value).filter(v=>v!==null);
  const max=Math.max(1,...values,threshold||0)*1.15;
  const x=i=>pad.l+i/(points.length-1)*innerW, y=v=>pad.t+(1-v/max)*innerH;
  let path="", segment=false;
  points.forEach((p,i)=>{if(p.value===null){segment=false;return;} path+=`${segment?"L":"M"}${x(i).toFixed(1)},${y(p.value).toFixed(1)} `;segment=true;});
  const area=points.every(p=>p.value!==null) ? `<path d="${path} L${x(points.length-1)},${y(0)} L${x(0)},${y(0)} Z" fill="#e7f0e5" opacity=".8"/>` : "";
  const grid=[0,1,2,3].map(i=>{const v=max*i/3;return `<line x1="${pad.l}" y1="${y(v)}" x2="${w-pad.r}" y2="${y(v)}" stroke="#e7ede6" stroke-dasharray="3 4"/><text x="${pad.l-9}" y="${y(v)+4}" text-anchor="end">${v<10?v.toFixed(1):Math.round(v)}</text>`;}).join("");
  const ticks=[0,Math.floor((points.length-1)/3),Math.floor(2*(points.length-1)/3),points.length-1].map(i=>`<text x="${x(i)}" y="${h-7}" text-anchor="${i===0?"start":i===points.length-1?"end":"middle"}">${esc(new Date(points[i].date+"T12:00:00").toLocaleDateString("en-GB",{day:"numeric",month:"short"}))}</text>`).join("");
  const marker=interactive?`<line id="chart-guide" y1="${pad.t}" y2="${h-pad.b}" stroke="#167d78" stroke-width="1" stroke-dasharray="3 5" visibility="hidden"/><circle id="chart-dot" r="5" fill="#e5f7ce" stroke="#126b63" stroke-width="3" visibility="hidden"/>`:"";
  return `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)}"><title>${esc(label)}</title><desc>${points.length} observations. Range ${Math.min(...values).toFixed(2)} to ${Math.max(...values).toFixed(2)} m³. Missing or invalid daily intervals are gaps in the line.</desc>${grid}${area}${threshold!==null?`<line x1="${pad.l}" y1="${y(threshold)}" x2="${w-pad.r}" y2="${y(threshold)}" stroke="#b38242" stroke-dasharray="5 4"/>`:""}<path d="${path}" stroke="#347354" stroke-width="2.4" fill="none" stroke-linejoin="round"/>${ticks}${marker}</svg>`;
}
function setChartCursor(index) {
  if (!chartPoints.length) return;
  chartIndex=Math.max(0,Math.min(index,chartPoints.length-1));
  const point=chartPoints[chartIndex], x=42+chartIndex/(chartPoints.length-1)*666;
  const value=point.value===null?"No valid interval":`${point.value.toFixed(2)} m³`;
  $("#chart-reading").textContent=`${new Date(point.date+"T12:00:00").toLocaleDateString("en-GB",{day:"numeric",month:"long",year:"numeric"})} · ${value}`;
  const guide=$("#chart-guide"), dot=$("#chart-dot");
  if (!guide || !dot) return;
  guide.setAttribute("x1",x);guide.setAttribute("x2",x);guide.setAttribute("visibility","visible");
  dot.setAttribute("cx",x);
  if (point.value===null) {dot.setAttribute("visibility","hidden");return;}
  const max=Math.max(1,...chartPoints.map(p=>p.value).filter(v=>v!==null))*1.15;
  dot.setAttribute("cy",16+(1-point.value/max)*154);dot.setAttribute("visibility","visible");
}
function renderOverviewChart() {
  chartPoints=overviewDaily.slice(-chartRange);
  $("#network-chart").innerHTML=chart(chartPoints,{label:`Network daily consumption in m³ over ${chartRange} days, excluding invalid intervals`,interactive:true});
  $$("[data-range]").forEach(button=>button.setAttribute("aria-pressed",String(Number(button.dataset.range)===chartRange)));
  setChartCursor(chartPoints.length-1);
}
function casesTable(rows) {
  if (!rows.length) return '<div class="empty"><h3>No cases in this view.</h3><p>Try another filter, or review your completed investigations.</p></div>';
  return `<table><thead><tr><th scope="col">Investigation</th><th scope="col">Meter / district</th><th scope="col">Priority</th><th scope="col">Status</th><th scope="col">Amount to review</th><th scope="col"><span class="sr-only">Open case</span></th></tr></thead><tbody>${rows.map(r=>`<tr><td><button class="row-button" data-case="${esc(r.id)}">${esc(r.title)}</button><small>${esc(names[r.kind])} · ${esc(r.event_date)}</small></td><td><span class="mono">${esc(r.meter_id)}</span><small>${esc(r.district)} · ${esc(r.segment)}</small></td><td>${badge(r.severity)}</td><td>${badge(r.status)}</td><td>${r.amount_cents?euro(r.amount_cents):'<span class="muted">—</span>'}</td><td><button class="table-arrow" data-case="${esc(r.id)}" aria-label="Open ${esc(r.meter_id)} ${esc(r.title)}">↗</button></td></tr>`).join("")}</tbody></table>`;
}
async function loadOverview() {
  const [data, rows] = await Promise.all([api("/api/overview"),api("/api/cases?status=active")]);
  $("#metrics").innerHTML = metric("Connected meters", number(data.meters), `${number(data.readings)} accepted readings`,"gauge") + metric("Active investigations",number(data.active_cases),"<b>Explainable</b> · awaiting operator action","clipboard-list") + metric("Invoice amount to review",euro(data.review_amount_cents),"Discrepancies, not confirmed savings","badge-euro") + metric("Row acceptance rate",`${data.quality_rate.toFixed(2)}%`,`${number(data.rejected_rows)} rows safely quarantined`,"circle-check",true);
  $("#nav-count").textContent=data.active_cases;
  $("#priority-count").textContent=rows.length;
  $("#hero-meter-count").textContent=`${number(data.meters)} connected meters`;
  const firstDay=data.daily[0]?.date;
  $("#period").textContent=firstDay?`${new Date(firstDay+"T12:00:00").toLocaleDateString("en-GB",{day:"numeric",month:"short"})} – ${new Date(data.as_of+"T12:00:00").toLocaleDateString("en-GB",{day:"numeric",month:"short",year:"numeric"})}`:"No observation period yet";
  overviewDaily=data.daily.map(r=>({date:r.date,value:r.valid_intervals?r.liters/1000:null}));
  renderOverviewChart();
  const max=Math.max(1,...data.kinds.map(r=>r.count));
  $("#kind-breakdown").innerHTML=data.kinds.map(r=>`<button type="button" class="kind-row" data-kind="${esc(r.kind)}" aria-label="Show ${r.count} active ${esc(names[r.kind])} investigations"><span class="kind-row-label"><span>${esc(names[r.kind])}</span><strong>${r.count}</strong></span><span class="bar-track"><span class="bar-fill" style="width:${r.count/max*100}%"></span></span></button>`).join("");
  $("#priority-table").innerHTML=casesTable(rows.slice(0,5));
  $("#connection").textContent="Network connected";
}
async function loadQueue() {
  const id=++queueRequest;
  const query=new URLSearchParams({status:$("#status-filter").value,kind:$("#kind-filter").value,q:$("#case-search").value});
  const rows=await api(`/api/cases?${query}`);
  if(id!==queueRequest) return;
  $("#case-table").innerHTML=casesTable(rows);$("#queue-label").textContent=`${rows.length} investigation${rows.length===1?"":"s"}`;
}
async function loadRuns() {
  const rows=await api("/api/runs");
  $("#runs-table").innerHTML=rows.length?`<table><thead><tr><th>Source file</th><th>Status</th><th>Accepted</th><th>Quarantined</th><th>Duplicates</th><th>Imported</th></tr></thead><tbody>${rows.map(r=>`<tr><td><button class="row-button" data-run="${esc(r.id)}">${esc(r.file_name)}</button><small class="mono">SHA-256 ${esc(r.sha256.slice(0,16))}…</small>${r.error?`<small>${esc(r.error)}</small>`:""}</td><td>${badge(r.status)}</td><td>${number(r.accepted)}</td><td>${number(r.rejected)}</td><td>${number(r.duplicates)}</td><td>${esc(new Date(r.started_at).toLocaleString("en-GB"))}</td></tr>`).join("")}</tbody></table>`:'<p class="empty">No import history yet.</p>';
}
async function loadEvaluation() {
  const result=await api("/api/evaluation");
  $("#evaluation-metrics").innerHTML=metric("Synthetic precision",result.precision===null?"N/A":`${(result.precision*100).toFixed(1)}%`,"Correctly matched / detected events","target")+metric("Synthetic recall",result.recall===null?"N/A":`${(result.recall*100).toFixed(1)}%`,"Correctly matched / labeled events","trending-up")+metric("Matched events",result.true_positives,"Exact meter, type and onset date","circle-check")+metric("Missed events",result.false_negatives,"Limitations included in evaluation","triangle-alert",true);
  $("#evaluation-table").innerHTML=`<table><caption class="sr-only">Synthetic event detection benchmark</caption><thead><tr><th>Exception</th><th>Matched</th><th>False alerts</th><th>Missed</th></tr></thead><tbody>${Object.entries(result.by_kind).map(([k,v])=>`<tr><td>${esc(names[k])}</td><td>${v.tp}</td><td>${v.fp}</td><td>${v.fn}</td></tr>`).join("")}</tbody></table>`;
}
async function showCase(id) {
  const item=await api(`/api/cases/${encodeURIComponent(id)}`); selectedCase=item;
  $("#case-meter").textContent=`${item.meter_id} / ${names[item.kind]}`;
  const transitions={open:["investigating","dismissed"],investigating:["resolved","dismissed","open"],resolved:["open"],dismissed:["open"]};
  const meaningful=Object.entries(item.evidence).filter(([k])=>k!=="rule_version");
  $("#case-content").innerHTML=`<h2 id="case-title" style="font-size:25px;letter-spacing:-.7px">${esc(item.title)}</h2><div class="case-meta">${badge(item.severity)}${badge(item.status)}<span class="pill">Event ${esc(item.event_date)}</span></div><p class="case-explanation">${esc(item.explanation)}</p><div class="case-evidence">${meaningful.map(([k,v])=>`<div class="evidence-cell"><span>${esc(k.replaceAll("_"," "))}</span><strong>${esc(Array.isArray(v)?v.join(" · "):v)}</strong></div>`).join("")}</div><h3>Meter consumption history <span class="muted">· m³ / day</span></h3><div class="case-chart">${chart(item.readings.slice(-35).map(r=>({date:r.reading_date,value:r.consumption_liters===null?null:r.consumption_liters/1000})),{height:190,threshold:item.evidence.threshold_liters?item.evidence.threshold_liters/1000:null,label:`Daily consumption for ${item.meter_id} in m³`})}</div><p class="muted" style="font-size:10px">Gaps indicate unavailable daily consumption. ${item.evidence.threshold_liters?"Dashed line: detection threshold.":""}</p><form id="case-form" class="case-form"><h3>Record your investigation</h3><label>Next status<select id="next-status">${transitions[item.status].map(s=>`<option value="${s}">${states[s]}</option>`).join("")}</select></label><div></div><label class="full">Investigation note<textarea id="case-note" minlength="5" maxlength="1000" required placeholder="What did you check, and why are you changing this status?"></textarea></label><button class="button primary" type="submit">Save decision →</button><span class="muted" style="font-size:10px">Local demo operator · revision ${item.version}</span></form><div style="margin-top:25px"><h3>Decision history</h3>${item.history.length?`<ol class="history-list">${item.history.map(h=>`<li><strong>${esc(states[h.from_status])} → ${esc(states[h.to_status])}</strong><p>${esc(h.note)}</p><time>${esc(new Date(h.at).toLocaleString("en-GB"))} · ${esc(h.actor)}</time></li>`).join("")}</ol>`:'<p class="muted" style="font-size:11px;margin-top:12px">No operator decisions yet.</p>'}</div>`;
  if(!$("#case-dialog").open) $("#case-dialog").showModal();
  $("#case-form").addEventListener("submit",saveDecision);
}
async function saveDecision(event) {
  event.preventDefault();const button=$("button[type=submit]",event.target);button.disabled=true;
  try {
    const id=selectedCase.id;
    await api(`/api/cases/${encodeURIComponent(id)}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({status:$("#next-status").value,note:$("#case-note").value,version:selectedCase.version})});
    await Promise.all([showCase(id),loadOverview(),loadQueue()]);toast("Decision saved. Your note is recorded in the case history.");
  } catch(error) {toast(error.message,true);} finally {button.disabled=false;}
}
async function showRun(id) {
  const rows=await api(`/api/runs/${encodeURIComponent(id)}/rejections`);
  $("#run-content").innerHTML=rows.length?`<p class="muted">${rows.length} quarantined rows. Original accepted records are preserved.</p>${rows.map(r=>`<article class="rejected-record"><p><strong>Row ${r.row_number}</strong> · ${esc(r.reason.replaceAll("_"," "))}</p><pre>${esc(JSON.stringify(r.payload,null,2))}</pre></article>`).join("")}`:'<p class="empty">No quarantined rows in this import.</p>';
  $("#run-dialog").showModal();
}
async function navigate() {
  const requested=location.hash.slice(1)||"overview", view=["overview","investigations","pipeline","methodology"].includes(requested)?requested:"overview";
  $$(".view").forEach(el=>{el.hidden=el.id!==`view-${view}`;});
  $$(".nav-link").forEach(el=>{el.classList.toggle("active",el.dataset.view===view);if(el.dataset.view===view)el.setAttribute("aria-current","page");else el.removeAttribute("aria-current");});
  $("#breadcrumb").textContent={overview:"Overview",investigations:"Investigations",pipeline:"Data pipeline",methodology:"Model & evidence"}[view];
  try {if(view==="investigations")await loadQueue();else if(view==="pipeline")await loadRuns();else if(view==="methodology")await loadEvaluation();} catch(error){toast(error.message,true);}
}
async function dailyImport() {
  const buttons=$$(".import-demo");buttons.forEach(b=>{b.disabled=true;$("span",b).textContent="Importing…";});
  try {const result=await api("/api/import/demo",{method:"POST"});await Promise.all([loadOverview(),loadQueue(),loadRuns()]);toast(result.replayed?"Already imported. Replay verified: no new readings or duplicate cases.":`${number(result.accepted)} readings imported · ${result.rejected} quarantined · ${result.cases_added} new cases.`);}
  catch(error){toast(error.message,true);}finally{buttons.forEach(b=>{b.disabled=false;$("span",b).textContent="Run daily import";});}
}
async function initialize() {
  try {
    token=(await api("/api/session")).token;
    await loadOverview();await navigate();
  } catch(error) {$("#load-error").textContent=`Could not load AquaWatch. ${error.message}`;$("#load-error").hidden=false;$("#connection").textContent="Connection unavailable";}
}
window.addEventListener("hashchange",navigate);
document.addEventListener("click",event=>{const caseButton=event.target.closest("[data-case]"),runButton=event.target.closest("[data-run]"),kindButton=event.target.closest("[data-kind]"),rangeButton=event.target.closest("[data-range]");if(caseButton)showCase(caseButton.dataset.case).catch(e=>toast(e.message,true));if(runButton)showRun(runButton.dataset.run).catch(e=>toast(e.message,true));if(kindButton){$("#kind-filter").value=kindButton.dataset.kind;$("#status-filter").value="active";$("#case-search").value="";location.hash="investigations";}if(rangeButton){chartRange=Number(rangeButton.dataset.range);renderOverviewChart();}});
$("#network-chart").addEventListener("pointermove",event=>{const svg=$("svg",event.currentTarget);if(!svg || !chartPoints.length)return;const rect=svg.getBoundingClientRect(),relative=(event.clientX-rect.left)/rect.width;setChartCursor(Math.round((relative*720-42)/666*(chartPoints.length-1)));});
$("#network-chart").addEventListener("keydown",event=>{if(!["ArrowLeft","ArrowRight","Home","End"].includes(event.key))return;event.preventDefault();setChartCursor(event.key==="Home"?0:event.key==="End"?chartPoints.length-1:chartIndex+(event.key==="ArrowLeft"?-1:1));});
$("#clear-filters").addEventListener("click",()=>{$("#case-search").value="";$("#status-filter").value="active";$("#kind-filter").value="all";loadQueue().catch(e=>toast(e.message,true));});
$$(".close-dialog").forEach(button=>button.addEventListener("click",()=>button.closest("dialog").close()));
$$("dialog").forEach(dialog=>dialog.addEventListener("click",event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}}));
$$(".import-demo").forEach(button=>button.addEventListener("click",dailyImport));
["#status-filter","#kind-filter"].forEach(s=>$(s).addEventListener("change",()=>loadQueue().catch(e=>toast(e.message,true))));
let searchTimer;$("#case-search").addEventListener("input",()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>loadQueue().catch(e=>toast(e.message,true)),180);});
$("#upload-form").addEventListener("submit",async event=>{event.preventDefault();const form=event.target,button=$("button",form),file=$("#csv-file").files[0];if(!file)return;if(file.size>5*1024*1024){toast("Please choose a CSV smaller than 5 MB.",true);return;}button.disabled=true;try{const body=new FormData();body.append("file",file);const result=await api(`/api/import?as_of=${encodeURIComponent($("#as-of").value)}`,{method:"POST",body});await Promise.all([loadOverview(),loadRuns()]);toast(result.replayed?`File already processed: ${result.status}. No records changed.`:`${result.accepted} accepted, ${result.rejected} quarantined.`);}catch(error){toast(error.message,true);await loadRuns().catch(()=>{});}finally{button.disabled=false;}});
initialize();
