import copy
import json
import os
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB_FILE = "nanoparticles_db.json"
REQUIRED_FIELDS = ("source", "kind", "np_type", "reference")
ALLOWED_TYPES = {"Silver", "Gold", "Zinc oxide", "Copper oxide"}
# Records whose values were read from the cited paper. Any record added later is flagged 'unverified' in the UI.
VERIFIED_IDS = ["np%03d" % i for i in range(1, 28)]
LOCK = threading.Lock()

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GreenNanoBench — Green-Synthesized Nanoparticle Intelligence Platform</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  :root {
    --bg: #f3f6f5; --surface: #ffffff; --primary: #143628; --accent: #2d6a4f;
    --accent-light: #e8f3ee; --border: #d8e2dc; --text: #1b262c; --muted: #5c6b73;
  }
  * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  body { margin: 0; background: var(--bg); color: var(--text); }
  header { background: linear-gradient(135deg, #143628 0%, #2d6a4f 100%); color: white; padding: 22px 32px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
  header h1 { margin: 0; font-size: 1.55rem; letter-spacing: -0.3px; }
  header p { margin: 4px 0 0; font-size: 0.9rem; opacity: 0.88; }
  .container { max-width: 1380px; margin: 20px auto; padding: 0 20px; }
  .filters { background: var(--surface); padding: 16px; border-radius: 10px; border: 1px solid var(--border); display: grid; grid-template-columns: repeat(auto-fit, minmax(175px, 1fr)); gap: 12px; margin-bottom: 18px; }
  .fg label { display: block; font-size: 0.74rem; font-weight: 700; color: var(--muted); margin-bottom: 4px; text-transform: uppercase; }
  .fg select, .fg input { width: 100%; padding: 8px 10px; border: 1px solid var(--border); border-radius: 6px; font-size: 0.88rem; background: #fff; }
  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 18px; }
  .kpi { background: var(--surface); padding: 15px 18px; border-radius: 10px; border: 1px solid var(--border); border-left: 4px solid var(--accent); }
  .kpi .val { font-size: 1.55rem; font-weight: 700; color: var(--primary); }
  .kpi .lbl { font-size: 0.8rem; color: var(--muted); margin-top: 2px; }
  .tabs { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
  .tab-btn { padding: 10px 16px; border: 1px solid var(--border); background: var(--surface); border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 0.88rem; color: var(--text); transition: 0.15s; }
  .tab-btn:hover { background: var(--accent-light); }
  .tab-btn.active { background: var(--primary); color: white; border-color: var(--primary); }
  .panel { display: none; background: var(--surface); padding: 22px; border-radius: 10px; border: 1px solid var(--border); }
  .panel.active { display: block; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  th, td { padding: 10px 11px; text-align: left; border-bottom: 1px solid var(--border); }
  th { background: #eef3f0; font-weight: 700; color: var(--primary); position: sticky; top: 0; z-index: 2; }
  tr:hover { background: #f8fbf9; }
  .badge { padding: 3px 8px; border-radius: 12px; font-size: 0.74rem; font-weight: 700; color: white; display: inline-block; }
  .b-Silver { background: #6c757d; } .b-Gold { background: #d4a017; } .b-Zinc { background: #4682b4; } .b-Copper { background: #b22222; } .b-Other { background: #2d6a4f; }
  .stab-high { color: #1b7a3e; font-weight: 700; } .stab-mod { color: #b57c00; font-weight: 600; } .stab-low { color: #b22222; }
  .charts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(430px, 1fr)); gap: 22px; }
  .chart-box { background: #fbfdfc; border: 1px solid var(--border); border-radius: 8px; padding: 15px; }
  .cards-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(330px, 1fr)); gap: 16px; }
  .card { border: 1px solid var(--border); border-radius: 8px; padding: 16px; background: #fbfdfc; }
  .card h3 { margin: 0 0 6px; font-size: 1.05rem; color: var(--primary); }
  .card p { margin: 4px 0; font-size: 0.84rem; }
  .card .ref { margin-top: 8px; font-size: 0.77rem; color: var(--muted); border-top: 1px dashed var(--border); padding-top: 6px; }
  .btn { background: var(--accent); color: white; border: none; padding: 9px 15px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 0.86rem; }
  .btn:hover { background: var(--primary); }
  .btn-outline { background: white; color: var(--primary); border: 1px solid var(--primary); padding: 6px 11px; border-radius: 6px; cursor: pointer; font-size: 0.8rem; font-weight: 600; }
  .btn-outline:hover { background: var(--accent-light); }
  .table-wrap { overflow-x: auto; max-height: 540px; }
  .tool-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 20px; }
  .tool-box { border: 1px solid var(--border); border-radius: 8px; padding: 18px; background: #fbfdfc; }
  .result-banner { margin-top: 14px; padding: 14px; border-radius: 8px; background: var(--accent-light); border-left: 4px solid var(--accent); font-size: 0.88rem; line-height: 1.5; }
  .lit-item { border: 1px solid var(--border); border-radius: 8px; padding: 14px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; gap: 14px; flex-wrap: wrap; }
  .modal-bg { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 50; align-items: center; justify-content: center; }
  .modal { background: white; max-width: 650px; width: 92%; border-radius: 10px; padding: 24px; max-height: 88vh; overflow-y: auto; }
</style>
</head>
<body>

<header>
  <div>
    <h1>GreenNanoBench — Green Nanoparticle Research Platform</h1>
    <p>Literature-backed synthesis database, protocol recommender, UV-Vis/FTIR validator & live Europe PMC literature fetcher</p>
  </div>
  <div style="display:flex;gap:10px;">
    <button class="btn" style="background:#40916c;" onclick="exportCSV()">Export Filtered CSV</button>
    <button class="btn" style="background:#1b4332;border:1px solid #74c69d;" onclick="exportJSON()">Export JSON</button>
  </div>
</header>

<div class="container">
  <div class="filters">
    <div class="fg"><label>Biological Source</label><select id="f-source" onchange="updateAll()"><option value="ALL">All Sources</option></select></div>
    <div class="fg"><label>Kingdom / Kind</label><select id="f-kind" onchange="updateAll()"><option value="ALL">All Kinds</option></select></div>
    <div class="fg"><label>Plant / Bio Part</label><select id="f-part" onchange="updateAll()"><option value="ALL">All Parts</option></select></div>
    <div class="fg"><label>Nanoparticle Type</label><select id="f-type" onchange="updateAll()"><option value="ALL">All Types</option></select></div>
    <div class="fg"><label>Max Size (nm)</label><input type="number" id="f-max" placeholder="e.g. 25" oninput="updateAll()"></div>
    <div class="fg"><label>Keyword Search</label><input type="text" id="f-search" placeholder="e.g. flavonoid, AgNO3" oninput="updateAll()"></div>
  </div>

  <div class="kpis">
    <div class="kpi"><div class="val" id="k-count">0</div><div class="lbl">Curated Records</div></div>
    <div class="kpi"><div class="val" id="k-sources">0</div><div class="lbl">Unique Bio-Sources</div></div>
    <div class="kpi"><div class="val" id="k-size">-</div><div class="lbl">Mean Particle Size</div></div>
    <div class="kpi"><div class="val" id="k-zone">-</div><div class="lbl">Mean Inhibition Zone</div></div>
    <div class="kpi"><div class="val" id="k-stable">-</div><div class="lbl">Colloidally Stable (|ζ|≥25mV)</div></div>
  </div>

  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('tab-table', this)">1. Curated Database</button>
    <button class="tab-btn" onclick="switchTab('tab-recommender', this)">2. Protocol Recommender</button>
    <button class="tab-btn" onclick="switchTab('tab-validator', this)">3. UV-Vis & FTIR Lab Validator</button>
    <button class="tab-btn" onclick="switchTab('tab-charts', this)">4. Structure-Property Analytics</button>
    <button class="tab-btn" onclick="switchTab('tab-fetch', this)">5. Fetch Live Literature</button>
    <button class="tab-btn" onclick="switchTab('tab-add', this)">+ Manual Entry</button>
  </div>

  <div id="tab-table" class="panel active">
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th><th>Biological Source</th><th>Part</th><th>NP Type</th><th>Precursor</th>
            <th>Size (nm)</th><th>UV Peak</th><th>Zeta (mV)</th><th>Stability</th><th>Zone (mm)</th><th>SOP</th>
          </tr>
        </thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
  </div>

  <div id="tab-recommender" class="panel">
    <h3 style="margin-top:0;color:var(--primary);">Target Nanoparticle Synthesis Recommender</h3>
    <p style="color:var(--muted);font-size:0.88rem;">Specify your desired nanoparticle properties to rank the best matching green synthesis protocols from the literature.</p>
    <div class="filters" style="background:#fbfdfc;">
      <div class="fg"><label>Target NP Metal/Oxide</label><select id="r-type"><option value="Silver">Silver (AgNPs)</option><option value="Gold">Gold (AuNPs)</option><option value="Zinc oxide">Zinc oxide (ZnO NPs)</option><option value="Copper oxide">Copper oxide (CuO NPs)</option></select></div>
      <div class="fg"><label>Max Target Size (nm)</label><input type="number" id="r-size" value="25"></div>
      <div class="fg"><label>Min Antibacterial Zone (mm)</label><input type="number" id="r-zone" value="0"></div>
      <div class="fg" style="display:flex;align-items:flex-end;"><button class="btn" style="width:100%;" onclick="runRecommender()">Find Optimal Protocols</button></div>
    </div>
    <div class="cards-grid" id="rec-results"></div>
  </div>

  <div id="tab-validator" class="panel">
    <h3 style="margin-top:0;color:var(--primary);">Experimental Characterization Diagnostic Tool</h3>
    <div class="tool-grid">
      <div class="tool-box">
        <h4 style="margin-top:0;">UV-Vis Surface Plasmon Resonance (SPR) Checker</h4>
        <div class="fg"><label>Observed UV-Vis Peak Wavelength (nm)</label><input type="number" id="v-uv" placeholder="e.g. 418"></div>
        <br>
        <button class="btn" onclick="checkUV()">Diagnose UV-Vis Peak</button>
        <div id="uv-out" class="result-banner" style="display:none;"></div>
      </div>
      <div class="tool-box">
        <h4 style="margin-top:0;">FTIR Capping Phytochemical Identifier</h4>
        <div class="fg"><label>Observed FTIR Peak Wavenumber (cm⁻¹)</label><input type="number" id="v-ftir" placeholder="e.g. 3436 or 1604"></div>
        <br>
        <button class="btn" onclick="checkFTIR()">Identify Functional Group</button>
        <div id="ftir-out" class="result-banner" style="display:none;"></div>
      </div>
    </div>
  </div>

  <div id="tab-charts" class="panel">
    <div class="charts-grid">
      <div class="chart-box"><canvas id="chartSize"></canvas></div>
      <div class="chart-box"><canvas id="chartZoneBar"></canvas></div>
      <div class="chart-box"><canvas id="chartZoneSize"></canvas></div>
      <div class="chart-box"><canvas id="chartZeta"></canvas></div>
      <div class="chart-box"><canvas id="chartParts"></canvas></div>
    </div>
  </div>

  <div id="tab-fetch" class="panel">
    <h3 style="margin-top:0;color:var(--primary);">Live Literature Search & Auto-Import (Europe PMC API)</h3>
    <p style="color:var(--muted);font-size:0.88rem;">Query real peer-reviewed green nanotechnology papers directly from Europe PMC and import citations into your local database.</p>
    <div style="display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap;">
      <input type="text" id="lit-query" style="flex:1;min-width:260px;padding:10px;border:1px solid var(--border);border-radius:6px;" value="green synthesis silver nanoparticles leaf extract">
      <button class="btn" onclick="searchLiterature()">Fetch Papers from Europe PMC</button>
    </div>
    <div id="lit-results"></div>
  </div>

  <div id="tab-add" class="panel">
    <h3 style="margin-top:0;color:var(--primary);">Add Curated Study Record (Auto-Saves to Disk)</h3>
    <form id="add-form" onsubmit="addRecord(event)">
      <div class="filters" style="background:#fbfdfc;">
        <div class="fg"><label>Biological Source *</label><input id="n-source" required placeholder="e.g. Ocimum basilicum"></div>
        <div class="fg"><label>Kind *</label><select id="n-kind"><option value="plant">plant</option><option value="microbe">microbe</option><option value="algae">algae</option><option value="fungi">fungi</option></select></div>
        <div class="fg"><label>Part Used</label><input id="n-part" placeholder="e.g. leaf"></div>
        <div class="fg"><label>NP Type *</label><select id="n-type"><option value="Silver">Silver</option><option value="Gold">Gold</option><option value="Zinc oxide">Zinc oxide</option><option value="Copper oxide">Copper oxide</option></select></div>
        <div class="fg"><label>Precursor</label><input id="n-prec" placeholder="e.g. AgNO3"></div>
        <div class="fg"><label>Conc (mM)</label><input type="number" step="any" id="n-conc"></div>
        <div class="fg"><label>pH</label><input type="number" step="any" id="n-ph"></div>
        <div class="fg"><label>Temp (°C)</label><input type="number" step="any" id="n-temp"></div>
        <div class="fg"><label>Time (min)</label><input type="number" step="any" id="n-time"></div>
        <div class="fg"><label>UV Peak (nm)</label><input type="number" step="any" id="n-uv"></div>
        <div class="fg"><label>TEM Size (nm)</label><input type="number" step="any" id="n-tem"></div>
        <div class="fg"><label>XRD Size (nm)</label><input type="number" step="any" id="n-xrd"></div>
        <div class="fg"><label>Zeta (mV)</label><input type="number" step="any" id="n-zeta"></div>
        <div class="fg"><label>FTIR Groups</label><input id="n-ftir" placeholder="e.g. O-H, C=O"></div>
        <div class="fg"><label>Zone (mm)</label><input type="number" step="any" id="n-zone"></div>
        <div class="fg"><label>Citation / DOI *</label><input id="n-ref" required placeholder="Author et al. Year, DOI"></div>
      </div>
      <button type="submit" class="btn">Save Permanently to Database</button>
    </form>
  </div>
</div>

<div class="modal-bg" id="sop-modal" onclick="if(event.target===this)this.style.display='none'">
  <div class="modal" id="sop-content"></div>
</div>

<script>
const DB = __RECORDS_JSON__;
const TYPE_COLORS = __COLORS_JSON__;
const VERIFIED = new Set(__VERIFIED_JSON__);
function verBadge(id) { return VERIFIED.has(id) ? '<span class="badge" style="background:#1b7a3e">source checked</span>' : '<span class="badge" style="background:#b57c00">unverified</span>'; }
let charts = {};

function esc(v) { return String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
function getSize(r) { return r.tem_size_nm !== null ? r.tem_size_nm : r.xrd_size_nm; }
function badgeClass(t) {
  if (t.includes("Silver")) return "b-Silver";
  if (t.includes("Gold")) return "b-Gold";
  if (t.includes("Zinc")) return "b-Zinc";
  if (t.includes("Copper")) return "b-Copper";
  return "b-Other";
}
function stabilityLabel(z) {
  if (z === null || z === undefined) return '<span style="color:var(--muted)">Not reported</span>';
  const az = Math.abs(z);
  if (az >= 25) return '<span class="stab-high">High Stability</span>';
  if (az >= 15) return '<span class="stab-mod">Moderate</span>';
  return '<span class="stab-low">Low / Aggregating</span>';
}

function populateDropdowns() {
  const sets = { source: new Set(), kind: new Set(), part: new Set(), type: new Set() };
  Object.values(DB).forEach(r => {
    if (r.source) sets.source.add(r.source);
    if (r.kind) sets.kind.add(r.kind);
    if (r.part) sets.part.add(r.part);
    if (r.np_type) sets.type.add(r.np_type);
  });
  fillSelect("f-source", "All Sources", Array.from(sets.source).sort());
  fillSelect("f-kind", "All Kinds", Array.from(sets.kind).sort());
  fillSelect("f-part", "All Parts", Array.from(sets.part).sort());
  fillSelect("f-type", "All Types", Array.from(sets.type).sort());
}

function fillSelect(id, allLabel, items) {
  const el = document.getElementById(id);
  const curr = el.value;
  el.innerHTML = `<option value="ALL">${allLabel}</option>` + items.map(i => `<option value="${i}">${i}</option>`).join("");
  if (items.includes(curr)) el.value = curr;
}

function getFiltered() {
  const s = document.getElementById("f-source").value;
  const k = document.getElementById("f-kind").value;
  const p = document.getElementById("f-part").value;
  const t = document.getElementById("f-type").value;
  const maxS = parseFloat(document.getElementById("f-max").value);
  const q = document.getElementById("f-search").value.trim().toLowerCase();

  return Object.entries(DB).filter(([id, r]) => {
    const sz = getSize(r);
    if (s !== "ALL" && r.source !== s) return false;
    if (k !== "ALL" && r.kind !== k) return false;
    if (p !== "ALL" && r.part !== p) return false;
    if (t !== "ALL" && r.np_type !== t) return false;
    if (!isNaN(maxS) && (sz === null || sz > maxS)) return false;
    if (q && !JSON.stringify(r).toLowerCase().includes(q)) return false;
    return true;
  });
}

function updateAll() {
  const rows = getFiltered();
  document.getElementById("k-count").innerText = rows.length;
  document.getElementById("k-sources").innerText = new Set(rows.map(([_, r]) => r.source)).size;
  const sizes = rows.map(([_, r]) => getSize(r)).filter(v => v !== null);
  document.getElementById("k-size").innerText = sizes.length ? (sizes.reduce((a, b) => a + b, 0) / sizes.length).toFixed(1) + " nm" : "-";
  const zones = rows.map(([_, r]) => r.zone_mm).filter(v => v !== null);
  document.getElementById("k-zone").innerText = zones.length ? (zones.reduce((a, b) => a + b, 0) / zones.length).toFixed(1) + " mm" : "-";
  const stableCount = rows.filter(([_, r]) => r.zeta_mv !== null && Math.abs(r.zeta_mv) >= 25).length;
  document.getElementById("k-stable").innerText = stableCount;

  document.getElementById("tbody").innerHTML = rows.map(([id, r]) => {
    const sz = getSize(r);
    const m = r.tem_size_nm !== null ? "TEM" : (r.xrd_size_nm !== null ? "XRD" : "");
    return `<tr>
      <td><strong>${id}</strong></td>
      <td><em>${esc(r.source)}</em> ${verBadge(id)}<br><span style="font-size:0.75rem;color:var(--muted);">${esc((r.reference||"").slice(0,55))}...</span></td>
      <td>${esc(r.part) || "-"}</td>
      <td><span class="badge ${badgeClass(r.np_type)}">${esc(r.np_type)}</span></td>
      <td>${esc(r.precursor) || "-"}</td>
      <td>${sz !== null ? sz + " (" + m + ")" : "-"}</td>
      <td>${r.uv_peak_nm ? r.uv_peak_nm + " nm" : "-"}</td>
      <td>${r.zeta_mv ?? "-"}</td>
      <td>${stabilityLabel(r.zeta_mv)}</td>
      <td>${r.zone_mm ?? "-"}</td>
      <td><button class="btn-outline" onclick="openSOP('${id}')">View SOP</button></td>
    </tr>`;
  }).join("");

  renderCharts(rows);
}

function openSOP(id) {
  const r = DB[id];
  const sz = getSize(r);
  document.getElementById("sop-content").innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <h2 style="margin:0;color:var(--primary);">Synthesis Standard Operating Procedure (${id.toUpperCase()})</h2>
      <button class="btn-outline" onclick="window.print()">Print SOP</button>
    </div>
    <hr style="border:none;border-top:1px solid var(--border);margin:14px 0;">
    <p><strong>Biological Reducing/Capping Agent:</strong> <em>${esc(r.source)}</em> (${esc(r.kind)}, ${esc(r.part)})</p>
    <p><strong>Target Nanomaterial:</strong> ${r.np_type} Nanoparticles</p>
    <h4>1. Reaction Conditions</h4>
    <ul>
      <li><strong>Metal Precursor Salt:</strong> ${r.precursor || "Standard metal salt precursor"} ${r.conc_mM ? "(" + r.conc_mM + " mM)" : ""}</li>
      <li><strong>Reaction pH:</strong> ${r.ph ?? "Unadjusted native extract pH (~6.8–7.2)"}</li>
      <li><strong>Incubation Temperature & Time:</strong> ${r.temp_c ? r.temp_c + " °C" : "Room temperature / mild heating"} ${r.time_min ? "for " + r.time_min + " min" : ""}</li>
    </ul>
    <h4>2. Expected Characterization Benchmarks</h4>
    <ul>
      <li><strong>UV-Vis SPR Peak:</strong> ${r.uv_peak_nm ? r.uv_peak_nm + " nm" : "Not reported"}</li>
      <li><strong>Expected Core Particle Size:</strong> ${sz ? sz + " nm" : "Not reported"} (TEM: ${r.tem_size_nm ?? "-"} nm | XRD: ${r.xrd_size_nm ?? "-"} nm)</li>
      <li><strong>Surface Charge (Zeta Potential):</strong> ${r.zeta_mv != null ? r.zeta_mv + " mV" : "Not reported"}</li>
      <li><strong>FTIR Phytochemical Capping Bands:</strong> ${esc(r.ftir_groups) || "Not reported"}</li>
      <li><strong>Antibacterial Inhibition Zone:</strong> ${r.zone_mm ? r.zone_mm + " mm" : "Not reported"}</li>
    </ul>
    <p style="font-size:0.82rem;color:var(--muted);background:#f4f7f6;padding:10px;border-radius:6px;"><strong>Primary Literature Reference:</strong> ${esc(r.reference)} ${verBadge(id)}</p>
  `;
  document.getElementById("sop-modal").style.display = "flex";
}

function runRecommender() {
  const t = document.getElementById("r-type").value;
  const maxSz = parseFloat(document.getElementById("r-size").value) || 999;
  const minZn = parseFloat(document.getElementById("r-zone").value) || 0;

  const matches = Object.entries(DB).map(([id, r]) => {
    const sz = getSize(r);
    if (r.np_type !== t) return null;
    if (sz !== null && sz > maxSz) return null;
    if ((r.zone_mm || 0) < minZn) return null;
    const score = (sz ? (100 - sz) : 40) + (r.zeta_mv != null ? Math.abs(r.zeta_mv) : 0) + ((r.zone_mm || 0) * 2);
    return { id, r, sz, score };
  }).filter(Boolean).sort((a, b) => b.score - a.score);

  const el = document.getElementById("rec-results");
  if (!matches.length) {
    el.innerHTML = "<p>No protocols matched those strict thresholds. Try increasing Max Target Size.</p>";
    return;
  }
  el.innerHTML = matches.map((m, idx) => `
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <h3>#${idx + 1} <em>${esc(m.r.source)}</em> ${verBadge(m.id)}</h3>
        <span class="badge ${badgeClass(m.r.np_type)}">Match Score: ${Math.round(m.score)}</span>
      </div>
      <p><strong>Extract Part:</strong> ${m.r.part} | <strong>Precursor:</strong> ${m.r.precursor || "-"} ${m.r.conc_mM ? "(" + m.r.conc_mM + " mM)" : ""}</p>
      <p><strong>Conditions:</strong> pH ${m.r.ph ?? "-"}, Temp ${m.r.temp_c ?? "-"} °C</p>
      <p><strong>Measured Size:</strong> ${m.sz ?? "-"} nm | <strong>Zeta:</strong> ${m.r.zeta_mv ?? "-"} mV | <strong>Zone:</strong> ${m.r.zone_mm ?? "-"} mm</p>
      <div style="margin-top:10px;"><button class="btn-outline" onclick="openSOP('${m.id}')">Open Full Synthesis SOP</button></div>
      <div class="ref">${esc(m.r.reference)}</div>
    </div>
  `).join("");
}

function checkUV() {
  const nm = parseFloat(document.getElementById("v-uv").value);
  const out = document.getElementById("uv-out");
  if (isNaN(nm)) return;
  out.style.display = "block";
  let msg = "";
  if (nm >= 220 && nm <= 340) msg = `<strong>Copper Oxide (CuO NPs) Band:</strong> Typical interband transition / SPR region for green-synthesized CuO nanostructures (e.g., <em>Aegle marmelos</em> at 330 nm, <em>Dalbergia sissoo</em> at 290 nm).`;
  else if (nm > 340 && nm < 380) msg = `<strong>Zinc Oxide (ZnO NPs) Bandgap Absorption:</strong> Characteristic wurtzite ZnO excitonic peak (e.g., <em>Moringa oleifera</em> seed ZnO at 375 nm).`;
  else if (nm >= 380 && nm < 395) msg = `<strong>Ambiguous (380–395 nm):</strong> Overlaps the ZnO band edge and the blue-shifted AgNP SPR region; confirm with XRD or TEM.`;
  else if (nm >= 395 && nm <= 460) msg = `<strong>Silver Nanoparticles (AgNPs) SPR Band:</strong> Classic spherical AgNP Surface Plasmon Resonance! Peaks near 405–420 nm indicate small, well-dispersed particles (&lt;20 nm), whereas peaks &gt;435 nm indicate larger size or mild aggregation.`;
  else if (nm >= 500 && nm <= 570) msg = `<strong>Gold Nanoparticles (AuNPs) SPR Band:</strong> Characteristic ruby-red AuNP plasmon resonance (e.g., <em>Cryptolepis buchanani</em> and <em>Zingiber officinale</em> at 530 nm).`;
  else msg = `<strong>Outside Standard Monometallic SPR Windows:</strong> Peak at ${nm} nm may indicate anisotropic nanorods/nanotriangles, bimetallic alloys, or unreacted plant polyphenols.`;
  out.innerHTML = msg;
}

function checkFTIR() {
  const cm = parseFloat(document.getElementById("v-ftir").value);
  const out = document.getElementById("ftir-out");
  if (isNaN(cm)) return;
  out.style.display = "block";
  let msg = "";
  if (cm >= 3200 && cm <= 3600) msg = `<strong>${cm} cm⁻¹ → O–H / N–H Stretching:</strong> Polyphenols, flavonoids, alcohols, or primary amines responsible for metal ion bioreduction.`;
  else if (cm >= 2850 && cm <= 2980) msg = `<strong>${cm} cm⁻¹ → C–H Aliphatic Stretching:</strong> Alkane chains from terpenoids, lipids, or organic acids.`;
  else if (cm >= 1600 && cm <= 1740) msg = `<strong>${cm} cm⁻¹ → C=O Carbonyl / Amide I Band:</strong> Flavonoid ketones, carboxylic acids, or protein peptide bonds capping the nanoparticle surface.`;
  else if (cm >= 1350 && cm <= 1460) msg = `<strong>${cm} cm⁻¹ → C–N / Aromatic Ring / O–H Bending:</strong> Aromatic polyphenols and nitro/amine capping groups.`;
  else if (cm >= 1000 && cm <= 1280) msg = `<strong>${cm} cm⁻¹ → C–O / C–O–C Stretching:</strong> Polysaccharides, glycosides, and phenolic ethers stabilizing the colloid.`;
  else if (cm >= 400 && cm <= 600) msg = `<strong>${cm} cm⁻¹ → Metal–Oxygen (M–O) Stretching:</strong> Direct confirmation of metal oxide lattice formation (Zn–O and Cu–O bands typically lie below 600 cm⁻¹).`;
  else msg = `<strong>${cm} cm⁻¹:</strong> Fingerprint region vibration; compare against crude plant extract FTIR to confirm peak shift after bioreduction.`;
  out.innerHTML = msg;
}

async function searchLiterature() {
  const q = document.getElementById("lit-query").value.trim();
  const box = document.getElementById("lit-results");
  if (!q) return;
  box.innerHTML = "<p>Querying Europe PMC...</p>";
  try {
    const res = await fetch("fetch_lit?q=" + encodeURIComponent(q));
    const data = await res.json();
    if (!data.results || !data.results.length) {
      box.innerHTML = "<p>No papers returned. Try broader keywords.</p>";
      return;
    }
    box.innerHTML = data.results.map(item => `
      <div class="lit-item">
        <div style="flex:1;">
          <strong>${esc(item.title)}</strong>
          <div style="font-size:0.8rem;color:var(--muted);margin-top:4px;">${esc(item.citation)}</div>
        </div>
        <button class="btn-outline" onclick='prefillFromLit(${JSON.stringify(item).replace(/'/g, "&#39;").replace(/</g, "\\u003c")})'>+ Import to Form</button>
      </div>
    `).join("");
  } catch (e) {
    box.innerHTML = "<p style='color:#b22222;'>Could not reach Europe PMC API (check internet connection).</p>";
  }
}

function prefillFromLit(item) {
  switchTab("tab-add", document.querySelectorAll(".tab-btn")[5]);
  document.getElementById("n-ref").value = item.citation;
  const t = item.title.toLowerCase();
  if (t.includes("gold")) document.getElementById("n-type").value = "Gold";
  else if (t.includes("zinc")) document.getElementById("n-type").value = "Zinc oxide";
  else if (t.includes("copper")) document.getElementById("n-type").value = "Copper oxide";
  else document.getElementById("n-type").value = "Silver";
}

function renderCharts(rows) {
  Object.values(charts).forEach(c => c.destroy());

  const sizeItems = rows.map(([_, r]) => ({
    label: r.source, val: getSize(r), color: TYPE_COLORS[r.np_type] || "#2d6a4f"
  })).filter(x => x.val !== null).sort((a, b) => a.val - b.val).slice(0, 18);

  charts.size = new Chart(document.getElementById("chartSize"), {
    type: "bar",
    data: { labels: sizeItems.map(x => x.label), datasets: [{ label: "Particle Size (nm)", data: sizeItems.map(x => x.val), backgroundColor: sizeItems.map(x => x.color) }] },
    options: { indexAxis: "y", plugins: { title: { display: true, text: "Particle Size Comparison Across Bio-Sources (nm)" } } }
  });
  const zoneItems = rows.map(([_, r]) => ({
    label: r.source + " (" + r.np_type + ")", val: r.zone_mm, color: TYPE_COLORS[r.np_type] || "#2d6a4f"
  })).filter(x => x.val !== null && x.val !== undefined).sort((a, b) => b.val - a.val);

  charts.zoneBar = new Chart(document.getElementById("chartZoneBar"), {
    type: "bar",
    data: {
      labels: zoneItems.map(x => x.label),
      datasets: [{ label: "Inhibition Zone (mm)", data: zoneItems.map(x => x.val), backgroundColor: zoneItems.map(x => x.color) }]
    },
    options: {
      indexAxis: "y",
      plugins: { title: { display: true, text: "Antibacterial Inhibition Zone by Species (mm)" } },
      scales: { x: { beginAtZero: true, title: { display: true, text: "Zone Diameter (mm)" } } }
    }
  });

  const zsPts = rows.map(([_, r]) => ({
    x: getSize(r), y: r.zone_mm, label: r.source, color: TYPE_COLORS[r.np_type] || "#2d6a4f"
  })).filter(p => p.x !== null && p.y !== null);

  charts.zoneSize = new Chart(document.getElementById("chartZoneSize"), {
    type: "scatter",
    data: { datasets: [{ label: "Bio-Source Studies", data: zsPts, backgroundColor: zsPts.map(p => p.color), pointRadius: 7 }] },
    options: {
      plugins: { title: { display: true, text: "Antibacterial Zone (mm) vs Particle Size (nm)" }, tooltip: { callbacks: { label: c => `${c.raw.label}: ${c.raw.x} nm, ${c.raw.y} mm` } } },
      scales: { x: { title: { display: true, text: "Particle Size (nm)" } }, y: { title: { display: true, text: "Inhibition Zone (mm)" } } }
    }
  });

  const zetaPts = rows.map(([_, r]) => ({
    x: getSize(r), y: r.zeta_mv, label: r.source, color: TYPE_COLORS[r.np_type] || "#2d6a4f"
  })).filter(p => p.x !== null && p.y !== null);

  charts.zeta = new Chart(document.getElementById("chartZeta"), {
    type: "scatter",
    data: { datasets: [{ label: "Colloidal Stability", data: zetaPts, backgroundColor: zetaPts.map(p => p.color), pointRadius: 7 }] },
    options: {
      plugins: { title: { display: true, text: "Zeta Potential (mV) vs Particle Size (nm)" }, tooltip: { callbacks: { label: c => `${c.raw.label}: ${c.raw.x} nm, ${c.raw.y} mV` } } },
      scales: { x: { title: { display: true, text: "Size (nm)" } }, y: { title: { display: true, text: "Zeta Potential (mV)" } } }
    }
  });

  const partCounts = {};
  rows.forEach(([_, r]) => { const p = r.part || "other"; partCounts[p] = (partCounts[p] || 0) + 1; });
  const sortedParts = Object.entries(partCounts).sort((a, b) => b[1] - a[1]);

  charts.parts = new Chart(document.getElementById("chartParts"), {
    type: "doughnut",
    data: {
      labels: sortedParts.map(x => x[0]),
      datasets: [{ data: sortedParts.map(x => x[1]), backgroundColor: ["#2d6a4f","#40916c","#52b788","#74c69d","#d4a017","#4682b4","#b22222","#6c757d"] }]
    },
    options: { plugins: { title: { display: true, text: "Distribution of Biological Parts Used" } } }
  });
}

function switchTab(id, btn) {
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.getElementById(id).classList.add("active");
  btn.classList.add("active");
}

async function addRecord(e) {
  e.preventDefault();
  const numVal = id => { const v = parseFloat(document.getElementById(id).value); return isNaN(v) ? null : v; };
  const strVal = id => { const v = document.getElementById(id).value.trim(); return v === "" ? null : v; };
  const payload = {
    source: strVal("n-source"), kind: strVal("n-kind"), part: strVal("n-part") || "leaf",
    np_type: strVal("n-type"), precursor: strVal("n-prec"), conc_mM: numVal("n-conc"),
    ph: numVal("n-ph"), temp_c: numVal("n-temp"), time_min: numVal("n-time"),
    uv_peak_nm: numVal("n-uv"), tem_size_nm: numVal("n-tem"), xrd_size_nm: numVal("n-xrd"),
    zeta_mv: numVal("n-zeta"), ftir_groups: strVal("n-ftir"), zone_mm: numVal("n-zone"),
    reference: strVal("n-ref")
  };
  const res = await fetch("add", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const json = await res.json();
  if (!res.ok || json.error) { alert(json.error || "Could not save record."); return; }
  DB[json.id] = payload;
  document.getElementById("add-form").reset();
  populateDropdowns();
  updateAll();
  switchTab("tab-table", document.querySelector(".tab-btn"));
}

function exportCSV() {
  const rows = getFiltered();
  const cols = ["id","source","kind","part","np_type","precursor","conc_mM","ph","temp_c","time_min","uv_peak_nm","xrd_size_nm","tem_size_nm","size_nm","zeta_mv","ftir_groups","zone_mm","reference"];
  const lines = [cols.join(",")];
  rows.forEach(([id, r]) => {
    const obj = { id, ...r, size_nm: getSize(r) };
    lines.push(cols.map(c => `"${obj[c] !== null && obj[c] !== undefined ? String(obj[c]).replace(/"/g, '""') : ""}"`).join(","));
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
  a.download = "green_nanoparticle_dataset.csv";
  a.click();
}

function exportJSON() {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(DB, null, 2)], { type: "application/json" }));
  a.download = "nanoparticles_db.json";
  a.click();
}

populateDropdowns();
updateAll();
</script>
</body>
</html>"""


class Nanoparticles:
    default_records = {
        "np001": {"source": "Camellia sinensis", "kind": "plant", "part": "leaf (green tea)", "np_type": "Silver", "precursor": "AgNO3", "conc_mM": None, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": None, "xrd_size_nm": 61.24, "tem_size_nm": None, "zeta_mv": -30.31, "ftir_groups": None, "zone_mm": None, "reference": "Salih 2024, Baghdad Sci J 21(5): Art. 11, doi:10.21123/bsj.2023.8344 (aqueous extract)"},
        "np002": {"source": "Camellia sinensis", "kind": "plant", "part": "leaf (tea)", "np_type": "Silver", "precursor": "AgNO3", "conc_mM": 1.0, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": None, "xrd_size_nm": None, "tem_size_nm": 4.0, "zeta_mv": None, "ftir_groups": None, "zone_mm": None, "reference": "Loo et al. 2012, Int J Nanomedicine 7:4263-4267, doi:10.2147/IJN.S33344 (approx. 4 nm by TEM)"},
        "np003": {"source": "Zingiber officinale", "kind": "plant", "part": "rhizome", "np_type": "Gold", "precursor": "HAuCl4", "conc_mM": 1.0, "ph": 8.0, "temp_c": 60, "time_min": 60, "uv_peak_nm": 530, "xrd_size_nm": 18.0, "tem_size_nm": 15.11, "zeta_mv": -28.8, "ftir_groups": "3423, 1620, 1417, 1128, 1047 cm-1 (shifted extract bands)", "zone_mm": 20.7, "reference": "Fouda et al. 2022, Appl Sci 12(24):12879, doi:10.3390/app122412879 (zone: E. coli at 200 ug/mL)"},
        "np004": {"source": "Cryptolepis buchanani", "kind": "plant", "part": "not stated", "np_type": "Gold", "precursor": "HAuCl4", "conc_mM": 1.0, "ph": 7.0, "temp_c": 80, "time_min": 30, "uv_peak_nm": 530, "xrd_size_nm": None, "tem_size_nm": 11.0, "zeta_mv": -30.28, "ftir_groups": "phenolic compounds", "zone_mm": None, "reference": "Wongyai et al. 2020, J Nanomaterials 2020:1320274, doi:10.1155/2020/1320274"},
        "np005": {"source": "Zingiber officinale", "kind": "plant", "part": "root", "np_type": "Gold", "precursor": "HAuCl4.3H2O", "conc_mM": None, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": None, "xrd_size_nm": None, "tem_size_nm": None, "zeta_mv": -31.7, "ftir_groups": "phenolic and aromatic compounds", "zone_mm": None, "reference": "Kalantari & Turner 2024, Front Chem 12:1482102, doi:10.3389/fchem.2024.1482102"},
        "np006": {"source": "Moringa oleifera", "kind": "plant", "part": "seed", "np_type": "Zinc oxide", "precursor": None, "conc_mM": None, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": 375, "xrd_size_nm": None, "tem_size_nm": 27.5, "zeta_mv": None, "ftir_groups": None, "zone_mm": None, "reference": "Albarakaty et al. 2023, J King Saud Univ Sci (TEM 25-30 nm; midpoint used)"},
        "np007": {"source": "Moringa oleifera", "kind": "plant", "part": "seed", "np_type": "Zinc oxide", "precursor": None, "conc_mM": None, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": None, "xrd_size_nm": 24.9, "tem_size_nm": None, "zeta_mv": None, "ftir_groups": None, "zone_mm": None, "reference": "Jose & Shinde 2024, Sci Rep, doi:10.1038/s41598-024-52093-5 (W-H plot size)"},
        "np008": {"source": "Moringa oleifera", "kind": "plant", "part": "leaf", "np_type": "Zinc oxide", "precursor": None, "conc_mM": None, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": None, "xrd_size_nm": 13.82, "tem_size_nm": None, "zeta_mv": None, "ftir_groups": None, "zone_mm": None, "reference": "Bhalla et al. 2023, Arabian J Chem (XRD crystallite size)"},
        "np009": {"source": "Aegle marmelos", "kind": "plant", "part": "leaf", "np_type": "Copper oxide", "precursor": None, "conc_mM": None, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": 330, "xrd_size_nm": None, "tem_size_nm": 32.0, "zeta_mv": None, "ftir_groups": None, "zone_mm": None, "reference": "Ali et al. 2023, Molecules 28(22):7499, doi:10.3390/molecules28227499"},
        "np010": {"source": "Dalbergia sissoo", "kind": "plant", "part": "leaf", "np_type": "Copper oxide", "precursor": None, "conc_mM": None, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": 290, "xrd_size_nm": None, "tem_size_nm": None, "zeta_mv": None, "ftir_groups": None, "zone_mm": 24.0, "reference": "Siddique et al. 2024, Sci Rep (zone: maximum reported, 24 mm)"},
        "np011": {"source": "Camellia sinensis", "kind": "plant", "part": "leaf (green tea)", "np_type": "Silver", "precursor": None, "conc_mM": None, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": None, "xrd_size_nm": None, "tem_size_nm": None, "zeta_mv": None, "ftir_groups": None, "zone_mm": 7.0, "reference": "Mohamed et al. 2021, J Nanotechnology (zone vs S. aureus)"},
        "np012": {"source": "Azadirachta indica", "kind": "plant", "part": "leaf", "np_type": "Silver", "precursor": None, "conc_mM": None, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": 455, "xrd_size_nm": None, "tem_size_nm": None, "zeta_mv": None, "ftir_groups": None, "zone_mm": None, "reference": "Regmi et al. 2021, Int J Appl Sci Biotechnol 9(3):220-226, doi:10.3126/ijasbt.v9i3.39069"},
        "np013": {"source": "Buchanania lanzan", "kind": "plant", "part": "leaf", "np_type": "Silver", "precursor": "AgNO3", "conc_mM": 0.5, "ph": None, "temp_c": 70, "time_min": 60, "uv_peak_nm": None, "xrd_size_nm": None, "tem_size_nm": None, "zeta_mv": -27.6, "ftir_groups": None, "zone_mm": None, "reference": "Buchanania lanzan AgNP study 2022, doi:10.1155/2022/6825150 (size 23-62 nm, not used)"},
        "np014": {"source": "Thuja orientalis", "kind": "plant", "part": "not stated", "np_type": "Silver", "precursor": "AgNO3", "conc_mM": None, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": 424, "xrd_size_nm": None, "tem_size_nm": 85.77, "zeta_mv": -21.73, "ftir_groups": None, "zone_mm": None, "reference": "Polymers 2022, 14(17):3453, doi:10.3390/polym14173453"},
        "np015": {"source": "Diospyros malabarica", "kind": "plant", "part": "fruit", "np_type": "Silver", "precursor": None, "conc_mM": None, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": None, "xrd_size_nm": None, "tem_size_nm": 17.4, "zeta_mv": None, "ftir_groups": None, "zone_mm": 13.1, "reference": "Nanomaterials 2021, 11(8):1999, doi:10.3390/nano11081999 (zone: max at 1000 ug/mL)"},
        "np016": {"source": "Malva parviflora", "kind": "plant", "part": "fruit", "np_type": "Silver", "precursor": None, "conc_mM": None, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": 477, "xrd_size_nm": None, "tem_size_nm": None, "zeta_mv": -21.2, "ftir_groups": "-OH, C=O, amide groups", "zone_mm": 20.33, "reference": "Int J Mol Sci 2025, 26(17):8135, doi:10.3390/ijms26178135 (zone: MRSA)"},
        "np017": {"source": "Cryptolepis buchanani", "kind": "plant", "part": "latex", "np_type": "Gold", "precursor": "HAuCl4", "conc_mM": None, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": 510, "xrd_size_nm": None, "tem_size_nm": 5.0, "zeta_mv": None, "ftir_groups": None, "zone_mm": None, "reference": "Tongsuk 2018, Chulalongkorn Univ. thesis, doi:10.58837/CHULA.THE.2018.102"},
        "np018": {"source": "Morinda citrifolia", "kind": "plant", "part": "leaf", "np_type": "Copper oxide", "precursor": "CuSO4.5H2O", "conc_mM": None, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": None, "xrd_size_nm": None, "tem_size_nm": None, "zeta_mv": None, "ftir_groups": None, "zone_mm": 14.3, "reference": "Priya et al. 2023, Sci Rep 13:18838, doi:10.1038/s41598-023-46002-5 (zone: A. niger)"},
        "np019": {"source": "Nicotiana plumbaginifolia", "kind": "plant", "part": "whole plant", "np_type": "Copper oxide", "precursor": None, "conc_mM": None, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": None, "xrd_size_nm": None, "tem_size_nm": 13.0, "zeta_mv": None, "ftir_groups": None, "zone_mm": 22.0, "reference": "Pawar et al. 2024, JOTCSA 11(3):1005-1016 (size 12-14 nm, midpoint; zone: S. aureus max)"},
        "np020": {"source": "Bergenia ciliata", "kind": "plant", "part": "leaf", "np_type": "Copper oxide", "precursor": "CuSO4.5H2O", "conc_mM": None, "ph": None, "temp_c": 70, "time_min": None, "uv_peak_nm": None, "xrd_size_nm": None, "tem_size_nm": 50.05, "zeta_mv": None, "ftir_groups": None, "zone_mm": None, "reference": "Crystals 2022, 12(12):1796, doi:10.3390/cryst12121796"},
        "np021": {"source": "Melia azedarach", "kind": "plant", "part": "leaf", "np_type": "Silver", "precursor": None, "conc_mM": None, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": 434, "xrd_size_nm": None, "tem_size_nm": None, "zeta_mv": None, "ftir_groups": None, "zone_mm": None, "reference": "Melia azedarach AgNP study (microwave-assisted), PMC7076090 (TEM 12-46 nm, not used)"},
        "np022": {"source": "Chromolaena odorata", "kind": "plant", "part": "leaf", "np_type": "Silver", "precursor": None, "conc_mM": None, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": 429, "xrd_size_nm": None, "tem_size_nm": 15.27, "zeta_mv": None, "ftir_groups": None, "zone_mm": None, "reference": "Chromolaena odorata AgNP study, PMC10980689"},
        "np023": {"source": "Thymus vulgaris", "kind": "plant", "part": "aerial part (Syrian source)", "np_type": "Silver", "precursor": "AgNO3", "conc_mM": 1.0, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": None, "xrd_size_nm": None, "tem_size_nm": 13.38, "zeta_mv": -26.9, "ftir_groups": None, "zone_mm": None, "reference": "PeerJ 2026, doi:10.7717/peerj.21583"},
        "np024": {"source": "Camellia sinensis", "kind": "plant", "part": "leaf (green tea)", "np_type": "Silver", "precursor": "AgNO3", "conc_mM": 1.0, "ph": None, "temp_c": None, "time_min": 1440, "uv_peak_nm": None, "xrd_size_nm": None, "tem_size_nm": 52.0, "zeta_mv": None, "ftir_groups": None, "zone_mm": None, "reference": "Materials 2022, 15(19):6978, doi:10.3390/ma15196978"},
        "np025": {"source": "Moringa oleifera", "kind": "plant", "part": "leaf", "np_type": "Zinc oxide", "precursor": None, "conc_mM": None, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": 365, "xrd_size_nm": None, "tem_size_nm": None, "zeta_mv": None, "ftir_groups": None, "zone_mm": None, "reference": "Food Sci Nutr 2026, doi:10.1002/fsn3.72443"},
        "np026": {"source": "Moringa oleifera", "kind": "plant", "part": "not stated", "np_type": "Zinc oxide", "precursor": None, "conc_mM": None, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": 356, "xrd_size_nm": None, "tem_size_nm": None, "zeta_mv": None, "ftir_groups": "3341 to 650 cm-1 bands", "zone_mm": 16.0, "reference": "React Chem Eng, doi:10.1039/D3RE00568B (zone: E. coli on painted panel)"},
        "np027": {"source": "Plumbago zeylanica", "kind": "plant", "part": "leaf", "np_type": "Copper oxide", "precursor": None, "conc_mM": None, "ph": None, "temp_c": None, "time_min": None, "uv_peak_nm": None, "xrd_size_nm": 25.15, "tem_size_nm": None, "zeta_mv": None, "ftir_groups": None, "zone_mm": 20.3, "reference": "Plumbago zeylanica CuO study (zone: P. aeruginosa)"}
    }

    colors = {"Silver": "#6c757d", "Gold": "#d4a017", "Zinc oxide": "#4682b4", "Copper oxide": "#b22222"}

    def __init__(self):
        # Built-in verified records always load from the script; records saved by the
        # user (ids not in the defaults) are kept from the JSON file.
        self.records = copy.deepcopy(self.default_records)
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                for k, v in saved.items():
                    if k not in self.records:
                        self.records[k] = v
            except Exception:
                pass
        self.save_to_disk()

    def save_to_disk(self):
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(self.records, f, indent=2)

    def add_record(self, data):
        with LOCK:
            nums = [int(k[2:]) for k in self.records if k[2:].isdigit()]
            new_id = f"np{(max(nums) if nums else 0) + 1:03d}"
            self.records[new_id] = data
            self.save_to_disk()
        return new_id

    @staticmethod
    def validate(data):
        if not isinstance(data, dict):
            return "Invalid payload"
        for f in REQUIRED_FIELDS:
            if not data.get(f):
                return f"Missing required field: {f}"
        if data["np_type"] not in ALLOWED_TYPES:
            return "Unsupported nanoparticle type"
        return None

    def fetch_literature(self, query):
        encoded = urllib.parse.quote(query)
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={encoded}&format=json&pageSize=10"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        items = payload.get("resultList", {}).get("result", [])
        results = []
        for it in items:
            title = it.get("title", "Untitled").rstrip(".")
            doi = it.get("doi", "")
            authors = it.get("authorString", "Unknown")
            year = it.get("pubYear", "")
            journal = it.get("journalTitle", "")
            cite = f"{authors} ({year}), {journal}" + (f", doi:{doi}" if doi else "")
            results.append({
                "title": title,
                "doi": doi,
                "citation": cite.strip(", "),
                "year": year
            })
        return results

    def build_website_html(self):
        html = HTML_TEMPLATE.replace("__RECORDS_JSON__", json.dumps(self.records).replace("</", "<\\/"))
        html = html.replace("__COLORS_JSON__", json.dumps(self.colors))
        return html.replace("__VERIFIED_JSON__", json.dumps(VERIFIED_IDS))


db = Nanoparticles()


class NanoparticleWebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.endswith("/fetch_lit"):
            qs = urllib.parse.parse_qs(parsed.query)
            q = qs.get("q", ["green synthesis nanoparticles"])[0]
            try:
                results = db.fetch_literature(q)
                self._send_json({"results": results})
            except Exception as e:
                self._send_json({"results": [], "error": "Literature service unavailable"})
            return

        if parsed.path not in ("/", "/index.html"):
            self._send_json({"error": "Not found"}, 404)
            return
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(db.build_website_html().encode("utf-8"))

    def do_POST(self):
        if not self.path.endswith("/add"):
            self._send_json({"error": "Not found"}, 404)
            return
        try:
            length = min(int(self.headers.get("Content-Length", 0)), 100_000)
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._send_json({"error": "Invalid JSON"}, 400)
            return
        err = db.validate(body)
        if err:
            self._send_json({"error": err}, 400)
            return
        new_id = db.add_record(body)
        self._send_json({"status": "saved", "id": new_id})

    def _send_json(self, obj, code=200):
        self.send_response(code)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode("utf-8"))

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    PORT = 8000
    server = ThreadingHTTPServer(("127.0.0.1", PORT), NanoparticleWebHandler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"GreenNanoBench live at: {url}")
    print(f"Database file saved at: {os.path.abspath(DB_FILE)}")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
        print("\nServer stopped.")