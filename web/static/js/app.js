/* DOKKÆBI van-os — frontend 100% offline : WS live, jauges, F(t)/X(Y), FEV/FT, van 3D. */
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];

const SENSORS = {};            // id -> meta (min/max/unit/alarm)
const hist = {};               // sensor -> {x:[], y:[]}
const MAXPTS = 600;
const charts = {};             // canvasId -> MiniPlot
const BAT_WH = 7700;           // 2×300Ah LiFePO4 @12.8V — hypothèse de dimensionnement

const fmt = (id, v) => (id === 'co_ppm' || id === 'heater_state' || id === 'smoke') ? String(Math.round(v)) : Number(v).toFixed(1);

function pushMeasure(m) {
  (hist[m.sensor] ||= { x: [], y: [] });
  const h = hist[m.sensor];
  h.x.push(m.ts); h.y.push(m.value);
  if (h.x.length > MAXPTS) { h.x.shift(); h.y.shift(); }
  updateGauge(m.sensor, m.value, m.unit);
  for (const p of Object.values(charts)) {
    if (p._sensor === m.sensor) p.setData([{ x: h.x, y: h.y, color: '#39ff6e' }]);
  }
  updateSyno(m.sensor, m.value);
  if (m.sensor === 'batt_soc' || m.sensor === 'load_w') updateAutonomy();
}

function updateGauge(id, value, unit) {
  const g = document.querySelector(`.gauge[data-sensor="${id}"]`);
  if (!g) return;
  g.querySelector('.v').textContent = fmt(id, value);
  const u = g.querySelector('.u'); if (u && unit) u.textContent = unit;
  const meta = SENSORS[id];
  const fill = g.querySelector('.fill');
  if (meta && fill) {
    const pct = Math.max(0, Math.min(100, (value - meta.min) / (meta.max - meta.min) * 100));
    fill.style.width = pct + '%';
  }
  g.classList.remove('warn', 'crit');
  if (meta && meta.alarm != null && value >= meta.alarm) {
    g.classList.add(value >= (meta.max > 100 ? meta.alarm * 3 : meta.alarm * 1.5) ? 'crit' : 'warn');
    if (meta.alarm >= meta.max / 2) g.classList.add('crit'); // CO, fumée : seuils absolus
  }
  if (id === 'heater_state') g.querySelector('.v').textContent = value > 0.5 ? 'MARCHE' : 'ARRÊT';
  if (id === 'smoke') g.querySelector('.v').textContent = value > 0.5 ? 'ALERTE' : 'OK';
}

function updateAutonomy() {
  const soc = hist.batt_soc?.y.at(-1), load = hist.load_w?.y.at(-1);
  const el = $('#g-autonomy'); if (!el) return;
  if (soc == null || load == null) return;
  const hAut = (soc / 100 * BAT_WH) / Math.max(load, 1);
  el.querySelector('.v').textContent = hAut > 99 ? '99+' : hAut.toFixed(1);
  el.querySelector('.fill').style.width = Math.min(100, hAut / 72 * 100) + '%';
}

/* ---------- synoptique ---------- */
const SYNO_MAP = {
  batt_voltage: 'sv', batt_current: 'sa', batt_soc: 'ssoc', solar_w: 'ssol', load_w: 'sload',
  water_fresh_l: 'sfresh', water_grey_l: 'sgrey', boiler_temp: 'sboiler',
  temp_int: 'stint', temp_ext: 'stext', heater_state: 'sheater', co_ppm: 'sco', smoke: 'ssmoke'
};
function updateSyno(sensor, value) {
  const el = document.getElementById(SYNO_MAP[sensor]);
  if (!el) return;
  if (sensor === 'heater_state') { el.textContent = value > 0.5 ? 'MARCHE' : 'ARRÊT'; el.style.fill = value > 0.5 ? '#ffb000' : '#39ff6e'; return; }
  if (sensor === 'smoke') { el.textContent = value > 0.5 ? 'ALERTE' : 'OK'; el.style.fill = value > 0.5 ? '#ff4455' : '#39ff6e'; return; }
  const unit = SENSORS[sensor]?.unit || '';
  el.textContent = `${fmt(sensor, value)} ${unit}`;
}

/* ---------- onglets + hotspots ---------- */
function goTab(name) {
  $$('.tab').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  $$('.page').forEach(p => p.classList.toggle('active', p.id === 'tab-' + name));
  if (name === 'fev') { loadFev(); loadFt(); }
}
$$('.tab').forEach(b => b.onclick = () => goTab(b.dataset.tab));
$$('.hs, .hs-link').forEach(h => h.addEventListener('click', () => goTab(h.dataset.tab)));

/* ---------- graphiques ---------- */
const CHART_DEFS = [
  { canvas: 'chart-elec', sel: 'sel-elec', sensors: ['batt_voltage', 'batt_current', 'batt_soc', 'solar_w', 'load_w'] },
  { canvas: 'chart-eau', sel: 'sel-eau', sensors: ['water_fresh_l', 'water_grey_l', 'boiler_temp'] },
  { canvas: 'chart-clim', sel: 'sel-clim', sensors: ['temp_int', 'temp_ext', 'co_ppm'] },
];
async function loadChart(def, sensor) {
  const p = charts[def.canvas];
  p._sensor = sensor;
  const r = await (await fetch(`/api/measures?sensor=${sensor}&limit=300`)).json();
  hist[sensor] = { x: r.map(m => m.ts), y: r.map(m => m.value) };
  p.setData([{ x: hist[sensor].x, y: hist[sensor].y }]);
}
function buildCharts() {
  for (const def of CHART_DEFS) {
    const p = new MiniPlot(document.getElementById(def.canvas), { fill: true });
    charts[def.canvas] = p;
    const sel = document.getElementById(def.sel);
    sel.innerHTML = '';
    for (const s of def.sensors) {
      const o = document.createElement('option');
      o.value = s; o.textContent = SENSORS[s]?.name || s;
      sel.appendChild(o);
    }
    sel.onchange = () => loadChart(def, sel.value);
    loadChart(def, def.sensors[0]);
  }
}

/* ---------- caméras ---------- */
async function buildCams() {
  const cams = await (await fetch('/api/cameras')).json();
  $('#cam-grid').innerHTML = cams.map(c =>
    `<figure class="cam"><figcaption>${c.name} — ${c.src}</figcaption><img src="${c.src}" alt="${c.name}"></figure>`).join('');
}

/* ---------- FEV / FT ---------- */
const STATUS_FT = ['brouillon', 'en_cours', 'realise', 'valide', 'archive'];
async function loadFev() {
  const fevs = await (await fetch('/api/fev')).json();
  const tb = $('#fev-table tbody');
  tb.innerHTML = fevs.map(f => `<tr>
    <td><b>${f.num}</b></td><td>${f.date}</td><td>ATA ${f.ata}</td><td>${esc(f.title)}</td>
    <td><span class="badge ${f.status}">${f.status}${f.ft_link ? ' → ' + f.ft_link : ''}</span></td>
    <td>
      <button class="btn small" onclick="showFev(${f.id})">voir</button>
      ${f.status === 'ouvert' ? `<button class="btn small danger" onclick="closeFev(${f.id})">clôturer</button>
      <button class="btn small" onclick="convertFev(${f.id},'${f.ata}')">→ FT</button>` : ''}
    </td></tr>`).join('');
}
async function loadFt() {
  const fts = await (await fetch('/api/ft')).json();
  $('#ft-table tbody').innerHTML = fts.map(t => `<tr>
    <td><b>${t.num}</b></td><td>ATA ${t.ata}</td><td>${esc(t.title)}</td>
    <td><span class="badge ${t.status}">${t.status}</span></td>
    <td>${t.fev_source_id ? 'FEV #' + t.fev_source_id : '—'}</td>
    <td><select class="mini-sel" data-ft="${t.num}">${STATUS_FT.map(s =>
      `<option ${s === t.status ? 'selected' : ''}>${s}</option>`).join('')}</select></td></tr>`).join('');
  $$('.mini-sel').forEach(s => s.onchange = async () => {
    await fetch(`/api/ft/${s.dataset.ft}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: s.value }) });
    loadFt();
  });
}
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

$('#fev-form').onsubmit = async e => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = Object.fromEntries(fd.entries());
  const r = await fetch('/api/fev', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (r.ok) { e.target.reset(); $('#fev-form date').value = today(); loadFev(); }
};
async function showFev(id) {
  const f = await (await fetch(`/api/fev/${id}`)).json();
  $('#fev-detail').hidden = false;
  $('#fev-detail-title').textContent = `${f.num} — ATA ${f.ata} — ${f.title} — ${f.status}${f.ft_link ? ' → ' + f.ft_link : ''}`;
  $('#fev-detail-body').innerHTML = `<p><b>DATE :</b> ${f.date}</p><p><b>SYMPTÔMES :</b> ${esc(f.symptoms || '—')}</p><p><b>DESCRIPTION :</b> ${esc(f.description || '—')}</p>`;
  $('#photo-form').dataset.fev = id;
  renderPhotos(f.photos);
}
function renderPhotos(photos) {
  $('#fev-photos').innerHTML = (photos || []).map(p => `<img src="/api/photos/${p.filename}" title="${esc(p.original)}">`).join('');
}
$('#photo-form').onsubmit = async e => {
  e.preventDefault();
  const fd = new FormData(e.target);
  await fetch(`/api/fev/${e.target.dataset.fev}/photos`, { method: 'POST', body: fd });
  showFev(e.target.dataset.fev);
};
window.closeFev = async id => { await fetch(`/api/fev/${id}/close`, { method: 'POST' }); loadFev(); };
window.convertFev = async (id, ata) => {
  const a = prompt('Chapitre ATA de la FT résultante :', ata);
  if (a == null) return;
  const r = await fetch(`/api/fev/${id}/convert`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ata: a.trim() }) });
  const j = await r.json();
  alert(r.ok ? `FEV convertie en ${j.ft}` : `Erreur : ${j.detail}`);
  loadFev(); loadFt();
};

/* ---------- boot ---------- */
const today = () => new Date().toISOString().slice(0, 10);
function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss://' : 'ws://';
  const ws = new WebSocket(proto + location.host + '/ws');
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.type === 'measure') pushMeasure(m);
  };
  ws.onclose = () => setTimeout(connectWS, 2000);
}
async function boot() {
  $('#fev-form date').value = today();
  const sensors = await (await fetch('/api/sensors')).json();
  sensors.forEach(s => SENSORS[s.id] = s);
  buildCharts();
  buildCams();
  const latest = await (await fetch('/api/latest')).json();
  for (const [k, v] of Object.entries(latest)) pushMeasure({ sensor: k, value: v.value, unit: v.unit, ts: v.ts });
  connectWS();
  loadFev(); loadFt();
  setInterval(() => $('#clock').textContent = new Date().toLocaleTimeString(), 1000);
}
boot();
