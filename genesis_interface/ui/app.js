const $ = (id) => document.getElementById(id);
let running = false;
let history = [];
let selectedHistoryIndex = -1;
let selectedAssetId = null;
let selectedMeasurement = null;

function applyTheme(theme) {
  const resolved = theme === 'light' ? 'light' : 'dark';
  document.documentElement.dataset.theme = resolved;
  const toggle = $('theme-toggle');
  if (toggle) {
    toggle.setAttribute('aria-pressed', String(resolved === 'light'));
    toggle.setAttribute('aria-label', `Switch to ${resolved === 'dark' ? 'light' : 'dark'} theme`);
  }
  if ($('theme-label')) $('theme-label').textContent = resolved === 'dark' ? 'Light theme' : 'Dark theme';
  if ($('theme-icon')) $('theme-icon').textContent = resolved === 'dark' ? '☼' : '☾';
}

function initTheme() {
  let saved = 'dark';
  try { saved = localStorage.getItem('kordex-theme') || localStorage.getItem('genesis-theme') || 'dark'; } catch (_) {}
  applyTheme(saved);
  $('theme-toggle')?.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    try { localStorage.setItem('kordex-theme', next); } catch (_) {}
  });
}
initTheme();

async function api(path, options={}) {
  const response = await fetch(path, {headers:{"Content-Type":"application/json"}, ...options});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function stateClass(state){ return String(state||'').toLowerCase().replace(/[^a-z]/g,''); }
function latestTelemetry(result){ const normalized=(result.processing?.telemetry || [])[0] || {}; const captured=result.interface_capture?.telemetry || {}; return {...captured, ...normalized}; }
function setState(result){
  const state = result.reliability_state?.current || '—';
  const previous = result.reliability_state?.previous;
  const transition = result.reliability_state?.transition;
  $('state-value').textContent = state;
  $('state-value').style.color = state === 'CRITICAL' ? 'var(--red)' : state === 'CONCERN' ? 'var(--red)' : state === 'WATCH' ? 'var(--yellow)' : 'var(--green)';
  $('state-transition').textContent = transition?.changed ? `${previous || 'INITIAL'} → ${state}` : 'No state transition';
  $('asset-state').textContent = state;
  $('asset-state').className = `state-pill ${stateClass(state)}`;
}
function renderResult(result){
  setState(result);
  const robot = result.robot || {};
  $('asset-title').innerHTML = `${escapeHtml(robot.robot_id || '—')} <span>${escapeHtml(robot.robot_type || 'Asset')}</span>`;
  $('asset-subtitle').textContent = `${robot.manufacturer || 'Unknown manufacturer'} · Live engine session`;
  const q = result.observation_quality || {};
  $('quality-value').textContent = q.status || '—';
  $('count-value').textContent = result.processing?.observation_count ?? 0;
  const investigation = result.evidence_synthesis?.investigation_required;
  $('investigation-value').textContent = investigation === true ? 'REQUIRED' : investigation === false ? 'NO' : '—';
  const t = latestTelemetry(result);
  $('time-step').textContent = `t ${t.time_step ?? '—'}`;
  $('motor-temp').textContent = t.motor_temperature == null ? '—' : `${t.motor_temperature}°C`;
  $('ambient-temp').textContent = t.ambient_temperature == null ? '—' : `${t.ambient_temperature}°C`;
  $('battery').textContent = t.battery_level == null ? '—' : `${t.battery_level}%`;
  $('voltage').textContent = t.battery_voltage == null ? '—' : `${t.battery_voltage} V`;
  $('workload').textContent = t.workload == null ? '—' : `${t.workload}%`;
  const overview = { 'overview-measurement-title': robot.robot_id || 'Latest observation', 'overview-time-step': `t ${t.time_step ?? '—'}`, 'overview-ambient': t.ambient_temperature == null ? '—' : `${t.ambient_temperature} °C`, 'overview-battery': t.battery_level == null ? '—' : `${t.battery_level}%`, 'overview-voltage': t.battery_voltage == null ? '—' : `${t.battery_voltage} V`, 'overview-workload': t.workload == null ? '—' : `${t.workload}%` };
  for (const [id,value] of Object.entries(overview)) if ($(id)) $(id).textContent = value;

  const synthesis = result.evidence_synthesis || {};
  const assessment = synthesis.assessment || synthesis.summary || result.reliability_state?.current || 'No assessment returned.';
  $('assessment').className = 'assessment';
  $('assessment').textContent = assessment;
  const rec = result.recommendation?.recommendation || 'No recommendation returned.';
  $('recommendation').textContent = rec;

  const evidence = [];
  const add = (label, value) => { if(value !== undefined && value !== null && value !== '' && value !== false) evidence.push([label, typeof value === 'string' ? value : JSON.stringify(value)]); };
  add('Observation quality', q.status);
  add('Security', result.observation_security?.trust_status || result.observation_security?.status);
  add('Historical memory', result.historical_memory?.status);
  add('Sampling', result.sampling_analysis?.status);
  add('State', result.reliability_state?.current);
  if (result.limitations?.length) add('Limitations', result.limitations.join('; '));
  $('evidence-list').innerHTML = evidence.length ? evidence.map(([a,b]) => `<div class="evidence-item"><b>${escapeHtml(a)}</b><span>${escapeHtml(b)}</span></div>`).join('') : '<div class="muted">No evidence summary returned.</div>';

  const required = synthesis.investigation_required;
  $('investigation-title').textContent = required ? 'Additional evidence required' : 'No investigation requested by engine';
  $('investigation-body').textContent = required
    ? 'Genesis marked this result as requiring more evidence. Review the findings and limitations below before drawing a physical conclusion.'
    : 'Genesis did not mark further investigation as required for this evaluation. This does not independently confirm asset health; review the quality status and limitations below.';
  renderInvestigationFindings(result);
  $('inject-btn')?.classList.toggle('hidden', !required);

  renderInspector(result);
}


function renderInvestigationFindings(result) {
  const target = $('investigation-findings');
  if (!target) return;
  const synthesis = result.evidence_synthesis || {};
  const summary = synthesis.summary || {};
  const asList = value => Array.isArray(value) ? value : (value == null || value === '' ? [] : [value]);
  const readable = value => {
    if (typeof value === 'string') return value;
    if (value && typeof value === 'object') {
      const group = value.group ? `${value.group}: ` : '';
      const check = value.check || value.code || '';
      const fields = Array.isArray(value.fields) ? value.fields.join(', ') : '';
      const details = value.message || value.statement || value.description || '';
      const parts = [group + check, fields, details].filter(Boolean);
      return parts.length ? parts.join(' · ') : JSON.stringify(value);
    }
    return String(value);
  };
  const qualityItems = (synthesis.quality_evidence || []).flatMap(item => {
    const reasons = item?.supporting_data?.reasons;
    return Array.isArray(reasons) ? reasons : [];
  });
  const groups = [
    {title: 'Observed patterns', items: asList(summary.what_pattern_was_observed), empty: 'No pattern evidence was returned for this observation.'},
    {title: 'Unusual findings', items: asList(summary.what_is_unusual), empty: 'No unusual-finding statements were returned. This is not proof that the asset is healthy.'},
    {title: 'Data-quality flags', items: qualityItems, empty: 'No structured quality reasons were returned by this result.'},
    {title: 'Evidence gaps and unknowns', items: [...asList(summary.what_we_do_not_know), ...asList(synthesis.missing_evidence), ...asList(synthesis.limitations || result.limitations)], empty: 'No evidence-gap details were returned.'}
  ];
  target.innerHTML = groups.map(group => {
    const unique = [...new Set(group.items.map(readable).filter(Boolean))];
    const content = unique.length
      ? `<ul>${unique.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
      : `<p class="muted">${escapeHtml(group.empty)}</p>`;
    return `<section class="investigation-finding"><h3>${escapeHtml(group.title)}</h3>${content}</section>`;
  }).join('');
}

function renderInspector(result){
  const state = result.reliability_state?.current || 'UNKNOWN';
  const synthesis = result.evidence_synthesis || {};
  const summary = synthesis.summary || {};
  $('inspector-title').textContent = `${result.robot?.robot_id || 'Asset'} · Evidence at t ${latestTelemetry(result).time_step ?? '—'}`;
  $('inspector-state').textContent = state;
  $('inspector-state').className = `state-pill ${stateClass(state)}`;
  $('inspector-summary').textContent = summary.status ? `Synthesis status: ${summary.status}. Evidence available: ${summary.evidence_available === true ? 'yes' : summary.evidence_available === false ? 'no' : 'unknown'}. This is Genesis output; unavailable evidence is not treated as a negative finding.` : 'Genesis did not return a synthesis summary for this observation.';
  const list = (items, empty, max=8) => Array.isArray(items) && items.length ? items.slice(0,max).map(item => {
    const statement = typeof item === 'string' ? item : (item.statement || item.message || item.description || item.evidence_id || JSON.stringify(item));
    const meta = typeof item === 'string' ? '' : [item.availability, item.source, item.evidence_id].filter(Boolean).join(' · ');
    return `<div class="inspect-item"><span>${escapeHtml(statement)}</span>${meta ? `<small>${escapeHtml(meta)}</small>` : ''}</div>`;
  }).join('') : `<div class="muted">${escapeHtml(empty)}</div>`;
  $('inspect-observations').innerHTML = list(synthesis.observations || result.observations, 'No observation evidence returned.');
  const signals = [...(synthesis.engineering_evidence || []), ...(synthesis.pattern_evidence || []), ...(synthesis.temporal_evidence || []), ...(synthesis.quality_evidence || []), ...(synthesis.security_evidence || [])];
  $('inspect-signals').innerHTML = list(signals, 'No signal evidence returned.', 12);
  $('inspect-conflicts').innerHTML = list(synthesis.contradictions, 'Genesis reported no contradictions in this result.', 12);
  const missing = [...(synthesis.missing_evidence || []), ...(synthesis.limitations || result.limitations || [])];
  $('inspect-missing').innerHTML = list([...new Set(missing)], 'No missing evidence or limitations reported.', 12);
  renderObservationProvenance(result);
  renderEvidenceLineage(result);
  $('raw-result').textContent = JSON.stringify(result, null, 2);
}

function renderObservationProvenance(result) {
  const target = $('provenance-grid');
  if (!target) return;
  const captured = result.interface_capture || {};
  const submitted = captured.telemetry && typeof captured.telemetry === 'object' ? captured.telemetry : {};
  const processedRows = result.processing?.telemetry;
  const processed = Array.isArray(processedRows) && processedRows.length && typeof processedRows[processedRows.length - 1] === 'object'
    ? processedRows[processedRows.length - 1] : {};
  const format = value => value === undefined || value === null || value === '' ? 'Not exposed' : (typeof value === 'object' ? JSON.stringify(value) : String(value));
  const fields = (obj) => Object.keys(obj).length
    ? Object.entries(obj).map(([key,value]) => `<div class="provenance-field"><code>${escapeHtml(key)}</code><span>${escapeHtml(format(value))}</span></div>`).join('')
    : '<p class="muted">No fields exposed in this result.</p>';
  const synthesis = result.evidence_synthesis || {};
  const state = result.reliability_state || {};
  const outputs = {
    'Reliability state': state.current,
    'Observation quality': result.observation_quality?.status,
    'Assessment': synthesis.assessment || synthesis.summary?.status,
    'Recommendation': result.recommendation?.recommendation,
    'Investigation required': synthesis.investigation_required
  };
  const outputMarkup = Object.entries(outputs).map(([key,value]) => `<div class="provenance-field"><code>${escapeHtml(key)}</code><span>${escapeHtml(value === true ? 'Yes' : value === false ? 'No' : format(value))}</span></div>`).join('');
  const security = result.observation_security || {};
  const unknowns = [];
  if (!captured.status) unknowns.push('Submitted-input capture metadata was not returned.');
  if (!processedRows || !processedRows.length) unknowns.push('Engine-normalized telemetry was not exposed for this result.');
  if (!security.authentication || String(security.authentication).toUpperCase() === 'UNKNOWN') unknowns.push('Source authentication is unknown; payload values are not independently authenticated.');
  if (!security.integrity || String(security.integrity).toUpperCase() === 'UNKNOWN') unknowns.push('Source integrity is unknown; tamper/integrity verification is not established.');
  if (!result.source_metadata && !captured.source) unknowns.push('Original device/source identity and acquisition method are not exposed.');
  (result.limitations || []).forEach(item => unknowns.push(String(item)));
  const uniqueUnknowns = [...new Set(unknowns)];
  target.innerHTML = `
    <section class="provenance-card"><div class="section-label">01 / SUBMITTED INPUT</div><b>${escapeHtml(captured.status || 'Capture status not exposed')}</b><p class="muted">${escapeHtml(captured.source || 'Interface capture source not exposed')}</p><div class="provenance-fields">${fields(submitted)}</div></section>
    <section class="provenance-card"><div class="section-label">02 / ENGINE-PROCESSED</div><b>${processedRows?.length ? 'Telemetry returned by Genesis' : 'Not exposed'}</b><p class="muted">This is engine output, not a reconstruction of the submitted payload.</p><div class="provenance-fields">${fields(processed)}</div></section>
    <section class="provenance-card"><div class="section-label">03 / ENGINE OUTPUT</div><b>Returned assessment</b><div class="provenance-fields">${outputMarkup}</div><p class="muted">These values are returned by Genesis; they are not independently verified by the interface.</p></section>
    <section class="provenance-card provenance-unknowns"><div class="section-label">04 / UNKNOWN OR UNVERIFIED</div><b>${uniqueUnknowns.length} item(s) to keep visible</b><ul>${uniqueUnknowns.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul><p class="muted">Unknown means unverified or unavailable in this result, not proof that a fault or problem exists.</p></section>`;
}

function renderEvidenceLineage(result) {
  const target = $('evidence-lineage');
  if (!target) return;
  const synthesis = result.evidence_synthesis || {};
  const graph = synthesis.evidence_lineage || {};
  const graphCounts = graph.counts || {};
  const temporalWarnings = Array.isArray(graph.temporal_order_warnings) ? graph.temporal_order_warnings : [];
  const temporalSummary = temporalWarnings.length
    ? `<small class="lineage-temporal-warning">${temporalWarnings.length} temporal-order conflict(s) need review. A conflict is a traceability warning, not automatic proof that a finding is invalid.</small>`
    : '<small>Temporal order is checked only where both ends expose comparable numeric time steps; missing clock basis is left unresolved.</small>';
  const graphSummary = `<div class="lineage-graph-summary"><b>Engine lineage graph · ${escapeHtml(graph.status || 'NOT EXPOSED')}</b><span>${escapeHtml(String(graphCounts.nodes ?? 0))} nodes · ${escapeHtml(String(graphCounts.edges ?? 0))} links · ${escapeHtml(String(graphCounts.unlinked_evidence ?? 0))} unlinked · ${escapeHtml(String(graphCounts.unresolved_references ?? 0))} unresolved references · ${escapeHtml(String(graphCounts.temporal_order_warnings ?? 0))} temporal conflicts</span><small>Field/value links are associations, not proof of causation. Pattern-window links record embedded source-row membership; they do not prove causation.</small>${temporalSummary}</div>`;
  const groups = [
    ['Observation', synthesis.observations || []],
    ['Engineering signal', synthesis.engineering_evidence || []],
    ['Pattern', synthesis.pattern_evidence || []],
    ['Temporal', synthesis.temporal_evidence || []],
    ['Quality', synthesis.quality_evidence || []],
    ['Security', synthesis.security_evidence || []],
    ['Historical', synthesis.historical_evidence || []],
    ['ML', synthesis.ml_evidence || []],
    ['Fleet', synthesis.fleet_evidence || []],
    ['Contradiction', synthesis.contradictions || []]
  ];
  const findings = groups.flatMap(([group, items]) => items.map(item => ({group, item})))
    .filter(({item}) => item && typeof item === 'object');
  if (!findings.length) {
    target.innerHTML = '<div class="muted">No structured findings were returned for lineage inspection.</div>';
    return;
  }
  const rendered = findings.map(({group, item}) => {
    const data = item.supporting_data && typeof item.supporting_data === 'object' ? item.supporting_data : {};
    const declaredRefs = item.supporting_evidence_ids || item.input_evidence_ids || data.supporting_evidence_ids || data.input_evidence_ids;
    const refs = Array.isArray(declaredRefs) && declaredRefs.length
      ? `<div class="lineage-refs"><small>Upstream evidence references</small><div>${declaredRefs.map(ref => `<code>${escapeHtml(typeof ref === 'object' ? JSON.stringify(ref) : String(ref))}</code>`).join(' ')}</div></div>`
      : '<div class="lineage-unlinked">No upstream evidence IDs declared or conservatively matched</div>';
    const source = item.source || (Array.isArray(item.sources) ? item.sources.join(', ') : 'Source not exposed');
    const evidenceId = item.evidence_id || item.contradiction_id || 'ID not exposed';
    const supporting = Object.keys(data).length ? JSON.stringify(data, null, 2) : (item.supporting_evidence_ids ? JSON.stringify({supporting_evidence_ids:item.supporting_evidence_ids}, null, 2) : 'No supporting_data payload attached.');
    const relationship = item.lineage_relationship ? `<div><small>Relationship type</small><p>${escapeHtml(item.lineage_relationship)} · ${escapeHtml(item.lineage_basis || 'basis not exposed')}</p></div>` : '';
    const graphEdges = (graph.edges || []).filter(edge => edge.from_evidence_id === evidenceId || edge.to_evidence_id === evidenceId);
    const graphLinks = graphEdges.length ? `<div><small>Engine graph relationships</small><div class="lineage-refs">${graphEdges.map(edge => {
      const outgoing = edge.from_evidence_id === evidenceId;
      const otherId = outgoing ? edge.to_evidence_id : edge.from_evidence_id;
      const relation = outgoing ? `→ ${otherId}` : `${otherId} →`;
      const timeStatus = edge.temporal_order?.status ? ` · time: ${edge.temporal_order.status}` : '';
      return `<p><code>${escapeHtml(relation)}</code> <b>${escapeHtml(edge.relationship || 'RELATIONSHIP_NOT_EXPOSED')}</b><br><small>${escapeHtml(edge.basis || 'basis not exposed')}${escapeHtml(timeStatus)}</small></p>`;
    }).join('')}</div></div>` : '<div><small>Engine graph relationships</small><p>No graph edges currently reference this evidence item.</p></div>';
    const node = (graph.nodes || []).find(candidate => candidate.evidence_id === evidenceId);
    const temporal = node && node.temporal ? `<div><small>Temporal scope</small><p>${escapeHtml(node.temporal.scope || 'NOT EXPOSED')} · start t=${escapeHtml(String(node.temporal.start_time_step ?? 'NOT EXPOSED'))} · end t=${escapeHtml(String(node.temporal.end_time_step ?? 'NOT EXPOSED'))}${node.temporal.evaluation_time_step != null ? ` · evaluated at t=${escapeHtml(String(node.temporal.evaluation_time_step))}` : ''}</p></div>` : '<div><small>Temporal scope</small><p>NOT EXPOSED by lineage graph.</p></div>';
    const outgoingTemporal = (graph.edges || []).filter(edge => edge.to_evidence_id === evidenceId && edge.temporal_order).map(edge => `${edge.from_evidence_id}: ${edge.temporal_order.status}`).join(' · ');
    const temporalEdges = outgoingTemporal ? `<div><small>Upstream time checks</small><p>${escapeHtml(outgoingTemporal)}</p></div>` : '';
    const limitations = Array.isArray(item.limitations) && item.limitations.length ? item.limitations.map(escapeHtml).join(' · ') : 'No item-specific limitations returned.';
    return `<details class="lineage-node"><summary><span class="lineage-type">${escapeHtml(group)}</span><b>${escapeHtml(item.statement || item.message || evidenceId)}</b><small>${escapeHtml(evidenceId)} · ${escapeHtml(source)} · ${escapeHtml(item.availability || 'availability not exposed')}</small></summary><div class="lineage-body"><div><small>Declared upstream links</small>${refs}</div>${graphLinks}${relationship}${temporal}${temporalEdges}<div><small>Supporting data from engine</small><pre>${escapeHtml(supporting)}</pre></div><div><small>Limitations</small><p>${limitations}</p></div></div></details>`;
  }).join('');
  target.innerHTML = graphSummary + rendered;
}

function renderHistory(items){
  history = Array.isArray(items) ? items : [];
  $('timeline').innerHTML = history.length ? history.map((result,index) => {
    const t = latestTelemetry(result); const state = result.reliability_state?.current || 'UNKNOWN';
    const active = index === selectedHistoryIndex ? ' selected' : '';
    return `<button class="timeline-node${active}" data-history-index="${index}"><b>#${index+1} · ${escapeHtml(state)}</b><span>t ${escapeHtml(String(t.time_step ?? '—'))}</span><small>${escapeHtml(String(t.motor_temperature == null ? 'No motor temp' : `${t.motor_temperature}°C motor`))}</small></button>`;
  }).join('') : '<div class="muted">No observations processed.</div>';
  $('timeline').querySelectorAll('[data-history-index]').forEach(button => { button.onclick = () => { selectedHistoryIndex = Number(button.dataset.historyIndex); renderHistory(history); renderResult(history[selectedHistoryIndex]); }; });
}
function renderEvents(events){
  $('event-list').innerHTML = events.length ? events.slice(-12).reverse().map(e => `<div class="event"><b>${escapeHtml(e.type)}</b><span>${escapeHtml(e.robot_id || '')} · t ${escapeHtml(String(e.time_step ?? '—'))}${e.to ? ` · ${escapeHtml(e.to)}` : ''}</span></div>`).join('') : '<div class="muted">Waiting for Genesis...</div>';
}
function escapeHtml(value){return String(value).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}

async function refresh(){
  const data = await api('/api/state');
  if(data.latest) renderResult(data.latest);
  renderEvents(data.events || []);
  renderDecisionRecords(data.decision_records || []);
  if (Array.isArray(data.history)) { if (selectedHistoryIndex < 0 || selectedHistoryIndex >= data.history.length) selectedHistoryIndex = data.history.length - 1; renderHistory(data.history); }
}

$('run-btn').onclick = async () => {
  if(running) return;
  running = true; $('run-btn').disabled = true; $('run-btn').textContent = 'Kordex is assessing…';
  try {
    await api('/api/reset', {method:'POST', body:'{}'});
    const data = await api('/api/scenario', {method:'POST', body:'{}'});
    selectedHistoryIndex = -1;
    for(const result of data.results){ renderResult(result); await new Promise(r=>setTimeout(r,220)); }
    selectedHistoryIndex = data.state.history.length - 1;
    renderHistory(data.state.history);
    renderEvents(data.state.events || []);
    renderDecisionRecords(data.state.decision_records || []);
    await refreshMemory(); await refreshIncidents(); await refreshAssets();
  } catch(error){ $('assessment').textContent = error.message; }
  finally { running = false; $('run-btn').disabled = false; $('run-btn').textContent = 'Run Assessment'; }
};
$('reset-btn').onclick = async () => { selectedHistoryIndex = -1; history = []; await api('/api/reset',{method:'POST',body:'{}'}); await refresh(); await refreshMemory(); await refreshIncidents(); await refreshAssets(); };
const optionalNumber = (id) => {
  const raw = $(id).value.trim();
  return raw === '' ? null : Number(raw);
};
$('followup-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = $('submit-followup');
  button.disabled = true;
  $('followup-status').textContent = 'Submitting observation to Genesis…';
  const observation = {
    robot_id: $('followup-robot').value.trim(),
    time_step: Number($('followup-time').value),
    motor_temperature: optionalNumber('followup-temp'),
    ambient_temperature: optionalNumber('followup-ambient'),
    battery_level: optionalNumber('followup-battery'),
    battery_voltage: optionalNumber('followup-voltage'),
    workload: optionalNumber('followup-workload')
  };
  Object.keys(observation).forEach(key => { if (observation[key] === null) delete observation[key]; });
  try {
    const data = await api('/api/investigation/follow-up', {method:'POST', body:JSON.stringify(observation)});
    $('followup-status').textContent = data.note || 'Observation processed.';
    renderResult(data.result);
    await refresh();
    await refreshMemory();
    await refreshIncidents();
    await refreshAssets();
  } catch(error) { $('followup-status').textContent = `Submission rejected: ${error.message}`; }
  finally { button.disabled = false; }
});

async function refreshMemory(){
  const target=$('memory-records'); if(!target) return;
  try {
    const data=await api('/api/memory');
    $('memory-count').textContent=`${data.count} stored record${data.count===1?'':'s'} · live engine`;
    target.innerHTML=data.entries.length ? data.entries.map(entry=>{
      const type=entry.entry_type||'legacy';
      const identity=entry.identity||{};
      const investigation=entry.investigation||{};
      const title=identity.incident_id||investigation.investigation_id||'Memory record';
      const state=entry.lifecycle?.status||investigation.status||'STATUS UNAVAILABLE';
      const detail=entry.characterization?.diagnosis?.probable_cause||investigation.summary||investigation.claim||'No summary recorded';
      return `<article class="record-item"><div class="record-top"><b>${escapeHtml(title)}</b><span class="tag">${escapeHtml(type)}</span></div><div>${escapeHtml(String(state))}</div><p>${escapeHtml(String(detail))}</p><details><summary>Inspect stored record</summary><pre>${escapeHtml(JSON.stringify(entry,null,2))}</pre></details></article>`;
    }).join('') : '<div class="muted">Genesis memory is currently empty. No historical records are fabricated.</div>';
  } catch(error){ target.textContent=`Could not load Genesis memory: ${error.message}`; }
}
async function refreshIncidents(){
  const target=$('incident-records'); if(!target) return;
  try {
    const data=await api('/api/incidents');
    $('incident-count').textContent=`${data.count} incident${data.count===1?'':'s'} · live engine`;
    target.innerHTML=data.incidents.length ? data.incidents.map(incident=>{
      const title=incident.incident_id||'Incident';
      const status=incident.status||'UNKNOWN';
      const detail=incident.incident_type||incident.diagnosis?.probable_cause||'No incident type recorded';
      return `<article class="record-item"><div class="record-top"><b>${escapeHtml(title)}</b><span class="state-pill ${stateClass(status)}">${escapeHtml(status)}</span></div><div>Asset: ${escapeHtml(incident.robot_id||'Unknown')} · Start: ${escapeHtml(String(incident.start_time_step??'—'))}</div><p>${escapeHtml(String(detail))}</p><details><summary>Inspect incident record</summary><pre>${escapeHtml(JSON.stringify(incident,null,2))}</pre></details></article>`;
    }).join('') : '<div class="muted">No incidents have been recorded by this Genesis session yet.</div>';
  } catch(error){ target.textContent=`Could not load Genesis incidents: ${error.message}`; }
}

function renderAssetDetail(detail){
  const panel=$('asset-detail-panel');
  if(!detail){panel.innerHTML='<article class="panel card"><h2>No asset selected</h2><p class="muted">Run a scenario to create real engine observations.</p></article>';return;}
  const latest=detail.latest||{};
  const robot=latest.robot||{};
  const state=latest.reliability_state?.current||'UNKNOWN';
  const telemetry=latestTelemetry(latest);
  const synth=latest.evidence_synthesis||{};
  const list=(items,empty)=>Array.isArray(items)&&items.length?items.slice(0,8).map(item=>{
    const text=typeof item==='string'?item:(item.statement||item.message||item.description||item.evidence_id||JSON.stringify(item));
    return `<div class="inspect-item"><span>${escapeHtml(text)}</span></div>`;
  }).join(''):`<div class="muted">${escapeHtml(empty)}</div>`;
  panel.innerHTML=`
    <article class="panel card">
      <div class="card-head"><div><div class="section-label">ASSET DETAILS</div><h2>${escapeHtml(detail.asset_id)} <span class="muted">${escapeHtml(robot.robot_type||'Type unavailable')}</span></h2></div><span class="state-pill ${stateClass(state)}">${escapeHtml(state)}</span></div>
      <div class="asset-facts"><div><small>Manufacturer</small><b>${escapeHtml(robot.manufacturer||'Unknown')}</b></div><div><small>Observations</small><b>${detail.observations}</b></div><div><small>Latest time step</small><b>${escapeHtml(String(telemetry.time_step??'—'))}</b></div><div><small>Observation quality</small><b>${escapeHtml(latest.observation_quality?.status||'Unknown')}</b></div></div>
      <div class="section-label">LATEST MEASUREMENTS</div><div class="telemetry-grid"><div><span>Motor temperature</span><strong>${telemetry.motor_temperature==null?'—':escapeHtml(String(telemetry.motor_temperature))+'°C'}</strong></div><div><span>Ambient temperature</span><strong>${telemetry.ambient_temperature==null?'—':escapeHtml(String(telemetry.ambient_temperature))+'°C'}</strong></div><div><span>Battery level</span><strong>${telemetry.battery_level==null?'—':escapeHtml(String(telemetry.battery_level))+'%'}</strong></div><div><span>Battery voltage</span><strong>${telemetry.battery_voltage==null?'—':escapeHtml(String(telemetry.battery_voltage))+' V'}</strong></div><div><span>Workload</span><strong>${telemetry.workload==null?'—':escapeHtml(String(telemetry.workload))+'%'}</strong></div></div><p class="muted telemetry-source-note">Source note: engine-normalized telemetry takes precedence. Fields only available from the submitted observation are controller-captured inputs, not independently sensor-authenticated readings.</p>
      <div class="divider"></div><div class="section-label">ASSESSMENT FROM GENESIS</div><div class="assessment">${escapeHtml(String(synth.assessment||synth.summary?.status||state))}</div>
      <div class="divider"></div><div class="section-label">ASSOCIATED INCIDENTS</div>${detail.incidents?.length?detail.incidents.map(i=>`<div class="record-item"><b>${escapeHtml(i.incident_id||'Incident')}</b><p>${escapeHtml(i.status||'Status unavailable')} · ${escapeHtml(i.incident_type||i.diagnosis?.probable_cause||'No diagnosis recorded')}</p></div>`).join(''):'<p class="muted">No incident record for this asset in the current session.</p>'}
      <div class="divider"></div><div class="section-label">OBSERVATION / STATE HISTORY</div><div class="timeline">${detail.history.map((r,index)=>{const t=latestTelemetry(r);const st=r.reliability_state?.current||'UNKNOWN';return `<button class="timeline-node" data-asset-history="${index}"><b>${escapeHtml(st)}</b><span>t ${escapeHtml(String(t.time_step??'—'))}</span><small>${t.motor_temperature==null?'No motor temperature':escapeHtml(String(t.motor_temperature))+'°C'}</small></button>`;}).join('')}</div>
      <div class="divider"></div><div class="inspector-columns"><div><div class="section-label">EVIDENCE / SIGNALS</div><div class="inspect-list">${list([...(synth.engineering_evidence||[]),...(synth.pattern_evidence||[]),...(synth.temporal_evidence||[]),...(synth.quality_evidence||[]),...(synth.security_evidence||[])],'No evidence items returned.')}</div></div><div><div class="section-label">MISSING EVIDENCE / LIMITATIONS</div><div class="inspect-list">${list([...(synth.missing_evidence||[]),...(synth.limitations||latest.limitations||[])],'No limitations reported by this result.')}</div></div></div>
      <details class="raw-details"><summary>Inspect latest raw engine result</summary><pre>${escapeHtml(JSON.stringify(latest,null,2))}</pre></details>
      <div class="actions"><button id="asset-open-evidence" class="secondary">Open in Evidence Explorer</button><button id="asset-open-investigation" class="secondary">Open Investigations</button></div>
    </article>`;
  panel.querySelectorAll('[data-asset-history]').forEach(button=>button.addEventListener('click',()=>{
    const index=Number(button.dataset.assetHistory); const chosen=detail.history[index];
    const globalIndex=history.findIndex(r=>r===chosen || (r.robot?.robot_id===chosen.robot?.robot_id && JSON.stringify(r)===JSON.stringify(chosen)));
    if(globalIndex>=0){selectedHistoryIndex=globalIndex;renderHistory(history);renderResult(history[globalIndex]);}
    else {renderResult(chosen);}
    navigate('evidence');
  }));
  $('asset-open-evidence').onclick=()=>{const index=history.findIndex(r=>r.robot?.robot_id===detail.asset_id); if(index>=0){selectedHistoryIndex=index;renderHistory(history);renderResult(history[index]);} navigate('evidence');};
  $('asset-open-investigation').onclick=()=>{ $('followup-robot').value=detail.asset_id; navigate('investigations'); };
}
async function refreshAssets(){
  const listEl=$('asset-list'); if(!listEl)return;
  try{
    const data=await api('/api/assets');
    listEl.innerHTML=data.assets.length?data.assets.map(asset=>`<button class="asset ${asset.asset_id===selectedAssetId?'active':''}" data-asset-id="${escapeHtml(asset.asset_id)}"><b>${escapeHtml(asset.asset_id)}</b><span class="state-pill ${stateClass(asset.latest_state)}">${escapeHtml(asset.latest_state||'UNKNOWN')}</span><small>${escapeHtml(asset.robot_type||'Unknown type')} · ${asset.observations} observation(s)</small></button>`).join(''):'<div class="muted">No assets have been observed yet. Run the Genesis scenario first.</div>';
    listEl.querySelectorAll('[data-asset-id]').forEach(button=>button.addEventListener('click',async()=>{
      selectedAssetId=button.dataset.assetId;
      try{const detail=await api('/api/assets/'+encodeURIComponent(selectedAssetId));renderAssetDetail(detail);listEl.querySelectorAll('[data-asset-id]').forEach(b=>b.classList.toggle('active',b.dataset.assetId===selectedAssetId));}
      catch(error){listEl.textContent=`Could not load asset details: ${error.message}`;}
    }));
    if(selectedAssetId && data.assets.some(a=>a.asset_id===selectedAssetId)){const detail=await api('/api/assets/'+encodeURIComponent(selectedAssetId));renderAssetDetail(detail);}
    else if(data.assets.length){selectedAssetId=data.assets[0].asset_id;const detail=await api('/api/assets/'+encodeURIComponent(selectedAssetId));renderAssetDetail(detail);listEl.querySelectorAll('[data-asset-id]').forEach(b=>b.classList.toggle('active',b.dataset.assetId===selectedAssetId));}
    else renderAssetDetail(null);
  }catch(error){listEl.textContent=`Could not load observed assets: ${error.message}`;}
}
$('refresh-assets')?.addEventListener('click',refreshAssets);

$('refresh-memory')?.addEventListener('click', refreshMemory);
$('refresh-incidents')?.addEventListener('click', refreshIncidents);
refreshMemory();
refreshIncidents();
refreshAssets();
refresh().catch(error => { $('system-status').textContent = `SYSTEM ERROR: ${error.message}`; });

// Workspace navigation: the engine session stays alive while views change.
function navigate(page){
  const valid = new Set(['overview','assets','telemetry','recommendations','reports','settings','evidence','investigations','memory','incidents','audit']);
  if(!valid.has(page)) return;
  document.querySelectorAll('[data-view]').forEach(view => view.classList.toggle('active', view.dataset.view === page));
  document.querySelectorAll('.nav-item').forEach(button => button.classList.toggle('active', button.dataset.page === page));
  const titles = {overview:'Overview',assets:'Fleet & Assets',telemetry:'Telemetry',recommendations:'Recommendations',reports:'Reports',settings:'Settings',evidence:'Evidence Explorer',investigations:'Investigations',memory:'Reliability Memory',incidents:'Incidents',audit:'Audit Trail'};
  document.title = `KORDEX — ${titles[page]}`;
  if(page === 'recommendations') renderRecommendations();
  if(page === 'reports') renderReportSummary();
  if(page === 'settings') updateSettingsRuntimeStatus();
  if(page === 'evidence' && selectedHistoryIndex >= 0 && history[selectedHistoryIndex]) renderResult(history[selectedHistoryIndex]);
  if(page === 'assets') refreshAssets();
}
document.querySelectorAll('.nav-item').forEach(button => button.addEventListener('click', () => navigate(button.dataset.page)));
document.querySelectorAll('[data-go]').forEach(button => button.addEventListener('click', () => navigate(button.dataset.go)));

// Mirror session data into the dedicated workspaces without fabricating records.
const originalRenderHistory = renderHistory;
renderHistory = function(items){
  originalRenderHistory(items);
  const source = Array.isArray(items) ? items : [];
  for(const targetId of ['telemetry-history']){
    const target = $(targetId); if(!target) continue;
    target.innerHTML = source.length ? source.map((result,index)=>{
      const t=latestTelemetry(result), state=result.reliability_state?.current||'UNKNOWN';
      return `<button class="timeline-node${index===selectedHistoryIndex?' selected':''}" data-telemetry-index="${index}"><b>#${index+1} · ${escapeHtml(state)}</b><span>t ${escapeHtml(String(t.time_step??'—'))}</span><small>${escapeHtml(String(t.motor_temperature==null?'No motor temp':`${t.motor_temperature}°C motor`))}</small></button>`;
    }).join('') : '<div class="muted">No observations processed.</div>';
    target.querySelectorAll('[data-telemetry-index]').forEach(button=>button.addEventListener('click',()=>{
      selectedHistoryIndex=Number(button.dataset.telemetryIndex);
      renderHistory(history); renderResult(history[selectedHistoryIndex]); navigate('evidence');
    }));
  }
};
const originalRenderEvents = renderEvents;
renderEvents = function(events){
  originalRenderEvents(events);
  const target=$('audit-events'); if(target){
    target.innerHTML = events.length ? events.slice().reverse().map(e=>`<div class="event"><b>${escapeHtml(e.type||'EVENT')}</b><span>${escapeHtml(e.robot_id||'')} · t ${escapeHtml(String(e.time_step??'—'))}${e.to?` · ${escapeHtml(e.to)}`:''}</span></div>`).join('') : '<div class="muted">No events recorded.</div>';
  }
};
const originalRenderResult = renderResult;
renderResult = function(result){
  originalRenderResult(result);
  const assetState=$('asset-page-state'); if(assetState){const state=result.reliability_state?.current||'UNKNOWN';assetState.textContent=state;assetState.className=`state-pill ${stateClass(state)}`;}
};


// V0.7 telemetry observability: plots are derived only from recorded engine results.
function renderTelemetryCharts(items){
  const series = [
    {id:'chart-motor', key:'motor_temperature', label:'Motor temperature', unit:'°C'},
    {id:'chart-ambient', key:'ambient_temperature', label:'Ambient temperature', unit:'°C'},
    {id:'chart-battery', key:'battery_level', label:'Battery level', unit:'%'},
    {id:'chart-voltage', key:'battery_voltage', label:'Battery voltage', unit:'V'},
    {id:'chart-workload', key:'workload', label:'Workload', unit:'%'},
    {id:'overview-chart-motor', key:'motor_temperature', label:'Motor temperature', unit:'°C', compact:true},
    {id:'overview-chart-battery', key:'battery_level', label:'Battery level', unit:'%', compact:true},
    {id:'overview-chart-workload', key:'workload', label:'Workload', unit:'%', compact:true}
  ];
  for(const spec of series){
    const node=$(spec.id); if(!node) continue;
    const points=(Array.isArray(items)?items:[]).map((result,index)=>{
      const t=latestTelemetry(result); const value=t[spec.key];
      return {index, time:t.time_step, value:typeof value==='number'&&Number.isFinite(value)?value:null};
    }).filter(point=>point.value!==null);
    if(!points.length){node.innerHTML='<div class="muted">No recorded measurements for this signal.</div>';continue;}
    const width=spec.compact?420:640,height=spec.compact?78:170,left=spec.compact?8:42,right=14,top=12,bottom=spec.compact?8:28;
    const values=points.map(p=>p.value); let min=Math.min(...values),max=Math.max(...values);
    if(min===max){min-=1;max+=1;} const pad=(max-min)*0.12; min-=pad;max+=pad;
    const x=i=>left+(points.length===1?0:i/(points.length-1))*(width-left-right);
    const y=v=>top+(max-v)/(max-min)*(height-top-bottom);
    const path=points.map((p,i)=>`${i?'L':'M'} ${x(i).toFixed(2)} ${y(p.value).toFixed(2)}`).join(' ');
    const circles=points.map((p,i)=>`<circle class="measurement-point${selectedMeasurement?.index===p.index&&selectedMeasurement?.key===spec.key?' selected':''}" data-measurement-index="${p.index}" data-measurement-key="${spec.key}" cx="${x(i).toFixed(2)}" cy="${y(p.value).toFixed(2)}" r="5" tabindex="0" role="button" aria-label="Inspect ${escapeHtml(spec.label)} observation ${p.index+1}"><title>Click to inspect observation ${p.index+1} · t ${escapeHtml(String(p.time??'—'))} · ${p.value}</title></circle>`).join('');
    const yLabels=spec.compact?'':[min+(max-min)*0.0,min+(max-min)*0.5,max].map(v=>`<text x="${left-8}" y="${(y(v)+4).toFixed(2)}" text-anchor="end">${v.toFixed(1)}</text>`).join('');
    const xLabel=spec.compact?'':`<text x="${left}" y="${height-6}">#${points[0].index+1}</text><text x="${width-right}" y="${height-6}" text-anchor="end">#${points[points.length-1].index+1}</text>`;
    node.innerHTML=`<svg viewBox="0 0 ${width} ${height}" role="group" aria-label="${spec.label} recorded over observations"><g class="chart-grid"><line x1="${left}" y1="${top}" x2="${width-right}" y2="${top}"/><line x1="${left}" y1="${(height-bottom)/2}" x2="${width-right}" y2="${(height-bottom)/2}"/><line x1="${left}" y1="${height-bottom}" x2="${width-right}" y2="${height-bottom}"/></g><g class="chart-labels">${yLabels}${xLabel}</g><path class="chart-line" d="${path}"/>${circles}</svg>${spec.compact?`<div class="overview-chart-foot"><span>${points.length} points</span><b>${points[points.length-1].value} ${spec.unit}</b></div>`:`<div class="chart-foot"><span>${points.length} recorded point${points.length===1?'':'s'} · points are selectable</span><span>Latest: ${points[points.length-1].value} ${spec.unit}</span></div>`}`;
    node.querySelectorAll('[data-measurement-index]').forEach(point=>{const select=()=>selectMeasurement(Number(point.dataset.measurementIndex),point.dataset.measurementKey);point.addEventListener('click',select);point.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();select();}});});
  }
}
function selectMeasurement(index,key){
  const result=history[index]; if(!result)return;
  const t=latestTelemetry(result); const value=t[key];
  selectedHistoryIndex=index; selectedMeasurement={index,key,value};
  renderHistory(history); renderResult(result); renderMeasurementTrace(result,key,value,index);
}
function renderMeasurementTrace(result,key,value,index){
  const target=$('measurement-trace'); if(!target)return;
  const labels={motor_temperature:'Motor temperature',ambient_temperature:'Ambient temperature',battery_level:'Battery level',battery_voltage:'Battery voltage',workload:'Workload'};
  const units={motor_temperature:'°C',ambient_temperature:'°C',battery_level:'%',battery_voltage:'V',workload:'%'};
  const t=latestTelemetry(result)||{}; const q=result.observation_quality||{}; const sec=result.observation_security||{};
  const synth=result.evidence_synthesis||{}; const state=result.reliability_state||{};
  const shown=value==null?'MISSING':`${escapeHtml(String(value))} ${units[key]||''}`;
  const evidence=[];
  for(const [label,items] of [['Observation evidence',synth.observations],['Pattern evidence',synth.engineering_evidence||synth.pattern_evidence],['Contradictions',synth.contradictions],['Missing evidence',synth.missing_evidence]]){
    if(Array.isArray(items)&&items.length){
      for(const item of items.slice(0,4)) evidence.push(`<div class="inspect-item"><b>${escapeHtml(label)}</b><span>${escapeHtml(typeof item==='string'?item:(item.statement||item.message||item.description||item.evidence_id||JSON.stringify(item)))}</span></div>`);
    }
  }
  target.innerHTML=`<div class="trace-header"><div><small>OBSERVATION #${index+1} · TIME STEP ${escapeHtml(String(t.time_step??'—'))}</small><h3>${escapeHtml(labels[key]||key)}</h3></div><strong>${shown}</strong></div><div class="trace-facts"><div><small>Asset</small><b>${escapeHtml(String(result.robot?.robot_id||'UNKNOWN'))}</b></div><div><small>Reliability state</small><b>${escapeHtml(String(state.current||'UNKNOWN'))}</b></div><div><small>Observation quality</small><b>${escapeHtml(String(q.status||'NOT EXPOSED'))}</b></div><div><small>Source / provenance</small><b>NOT EXPOSED</b></div></div><p class="muted">Trace boundary: the normalized measurement present in Genesis processing.telemetry takes precedence. Values missing there are shown from the controller's captured submitted input (${escapeHtml(String(result.interface_capture?.status||'NOT EXPOSED'))}); this is not engine-normalized and does not establish sensor authenticity, calibration, or transport provenance.</p><div class="trace-section"><b>Related assessment</b><p>${escapeHtml(String(synth.assessment||synth.summary?.status||state.current||'No assessment returned'))}</p><small>Recommendation: ${escapeHtml(String(result.recommendation?.recommendation||'No recommendation returned'))}</small></div><div class="trace-section"><b>Returned evidence connected to this observation</b>${evidence.length?`<div class="inspect-list">${evidence.join('')}</div>`:'<p class="muted">No structured evidence items were returned for this result. The measurement is shown as telemetry, not upgraded into a causal finding.</p>'}</div><div class="trace-actions"><button class="secondary" id="trace-open-evidence">Open full evidence result</button><button class="secondary" id="trace-show-json">Show raw result JSON</button></div>`;
  $('trace-open-evidence')?.addEventListener('click',()=>navigate('evidence'));
  $('trace-show-json')?.addEventListener('click',()=>{navigate('evidence');const details=document.querySelector('.raw-details');if(details)details.open=true;});
}
function renderTelemetryQuality(result){
  const target=$('telemetry-quality'); if(!target)return;
  const q=result?.observation_quality||{}; const groups=q.groups||{}; const security=result?.observation_security||{};
  const rows=[
    ['Overall observation quality',q.status||'UNKNOWN','Returned by Genesis'],
    ['Thermal group',groups.thermal?.status||'UNKNOWN',(groups.thermal?.issues||[]).join('; ')||'No group issues reported'],
    ['Battery group',groups.battery?.status||'UNKNOWN',(groups.battery?.issues||[]).join('; ')||'No group issues reported'],
    ['Workload group',groups.workload?.status||'UNKNOWN',(groups.workload?.issues||[]).join('; ')||'No group issues reported'],
    ['Source authentication',security.authentication||'UNKNOWN','Security assessment'],
    ['Telemetry integrity',security.integrity||'UNKNOWN','Security assessment'],
    ['Freshness',security.freshness||'UNKNOWN','Security assessment'],
    ['Calibration validity','NOT EXPOSED','Current runtime provides no calibration assessment'],
    ['Measurement validity','NOT EXPOSED','Current runtime provides no dedicated measurement-validity assessment']
  ];
  target.innerHTML=rows.map(([label,value,note])=>`<div class="quality-item"><div><b>${escapeHtml(label)}</b><small>${escapeHtml(note)}</small></div><span class="quality-status ${stateClass(value)}">${escapeHtml(value)}</span></div>`).join('');
}
const renderHistoryBeforeCharts = renderHistory;
renderHistory = function(items){
  renderHistoryBeforeCharts(items);
  renderTelemetryCharts(Array.isArray(items)?items:[]);
  const selected=selectedHistoryIndex>=0&&items?.[selectedHistoryIndex]?items[selectedHistoryIndex]:items?.[items.length-1];
  if(selected){renderTelemetryQuality(selected);if(selectedMeasurement&&history[selectedMeasurement.index])renderMeasurementTrace(history[selectedMeasurement.index],selectedMeasurement.key,selectedMeasurement.value,selectedMeasurement.index);}
};
const renderResultBeforeTelemetryQuality = renderResult;
renderResult = function(result){
  renderResultBeforeTelemetryQuality(result);
  renderTelemetryQuality(result);
  if(selectedMeasurement){const selected=history[selectedMeasurement.index];if(selected)renderMeasurementTrace(selected,selectedMeasurement.key,selectedMeasurement.value,selectedMeasurement.index);}
};


function renderDecisionRecords(records){
  const target=$('decision-records'); if(!target) return;
  target.innerHTML = records.length ? records.slice().reverse().map(record => `<details class="decision-record"><summary><b>${escapeHtml(record.record_id)}</b><span>${escapeHtml(record.robot_id||'UNKNOWN ASSET')} · t ${escapeHtml(String(record.time_step??'—'))} · ${escapeHtml(record.reliability_state||'STATE UNKNOWN')}</span></summary><div class="decision-record-body"><div><small>Assessment</small><p>${escapeHtml(typeof record.assessment==='string'?record.assessment:JSON.stringify(record.assessment??'NOT EXPOSED'))}</p></div><div><small>Recommendation</small><p>${escapeHtml(record.recommendation||'NOT EXPOSED')}</p></div><div><small>Input SHA-256</small><code>${escapeHtml(record.input_sha256||'NOT EXPOSED')}</code></div><div><small>Returned result SHA-256</small><code>${escapeHtml(record.result_sha256||'NOT EXPOSED')}</code></div><div><small>Runtime / rule version</small><p>${escapeHtml(record.engine_version||'NOT EXPOSED')} · ${escapeHtml(record.rule_or_model_version||'NOT EXPOSED')}</p></div><div><small>Scope and limitations</small><p>${escapeHtml(record.record_scope||'NOT EXPOSED')}</p><ul>${(record.limitations||[]).map(item=>`<li>${escapeHtml(item)}</li>`).join('')}</ul></div></div></details>`).join('') : '<div class="muted">No decisions recorded.</div>';
}
$('refresh-decision-records')?.addEventListener('click', async()=>{try{const data=await api('/api/decision-records');renderDecisionRecords(data.records||[]);}catch(error){$('decision-records').textContent=error.message;}});


// New mockup-aligned workspaces. They present only session data actually returned by the engine.
function renderRecommendations(){
  const target=$('recommendation-workspace'); if(!target) return;
  const latest=history.length ? history[history.length-1] : null;
  const rec=latest && (latest.recommendation || (latest.assessment && latest.assessment.recommendation));
  if(!rec){target.innerHTML='<div class="empty-state-icon">✧</div><p>No engine recommendation is available yet. Run an assessment first; this workspace will not generate advice without returned evidence.</p>';return;}
  const text=typeof rec==='string'?rec:JSON.stringify(rec,null,2);
  target.innerHTML=''; const box=document.createElement('div'); box.className='notice'; const title=document.createElement('b'); title.textContent='Latest engine recommendation'; const body=document.createElement('pre'); body.className='recommendation-output'; body.textContent=text; box.append(title,body); target.append(box);
}
function renderReportSummary(){
  const target=$('report-summary'); if(!target) return;
  const latest=history.length ? history[history.length-1] : null;
  if(!latest){target.innerHTML='<div class="muted">No assessment records available. Run an assessment to create a session report.</div>';return;}
  const state=(latest.reliability_state && (latest.reliability_state.state || latest.reliability_state.status)) || latest.state || 'Not returned';
  const quality=(latest.observation_quality && (latest.observation_quality.status || latest.observation_quality.label)) || 'Not returned';
  const rows=[['Asset',latest.asset_id || latest.robot_id || 'Not returned'],['Assessment state',state],['Observation quality',quality],['Session observations',String(history.length)],['Generated',new Date().toLocaleString()],['Scope','Current local session']];
  target.innerHTML=rows.map(([label,value])=>`<div class="report-item"><small>${escapeHtml(label)}</small><b>${escapeHtml(String(value))}</b></div>`).join('');
}
function escapeHtml(value){return String(value).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));}
function updateSettingsRuntimeStatus(){const el=$('settings-runtime-status');if(el) el.textContent=($('system-status')?.textContent||'Runtime status unavailable');}
$('refresh-report')?.addEventListener('click',renderReportSummary);
$('export-report')?.addEventListener('click',()=>{
  const latest=history.length ? history[history.length-1] : null; const status=$('report-status');
  if(!latest){if(status)status.textContent='No report to export. Run an assessment first.';return;}
  const report={product:'KORDEX',scope:'Current local interface session',generated_at:new Date().toISOString(),observations_processed:history.length,latest_result:latest};
  const blob=new Blob([JSON.stringify(report,null,2)],{type:'text/plain;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='kordex-session-report.txt';document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);if(status)status.textContent='Session report exported. It contains only records available in this session.';
});
$('settings-theme-toggle')?.addEventListener('click',()=>$('theme-toggle')?.click());
