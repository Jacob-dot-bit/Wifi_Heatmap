"use strict";

// Gauge display bounds, in dBm.
const DBM_MIN = -100;
const DBM_MAX = -30;

// Thumbnail width requested from the server. Generous next to the display
// size so tiles stay sharp on high density screens.
const THUMB_W = 560;

const FALLBACK_LANG = "en";

const COLORS = {
  green: "#73bf69",
  yellow: "#f2cc0c",
  orange: "#ff9830",
  red: "#f2495c",
  blue: "#5794f2",
  dim: "#8e8e9b",
};

const state = {
  config: null,
  measurements: [],
  ssids: [],
  stats: [],
  scanned: null,
  heatmaps: [],
  dirty: false,
  scanning: false,
  view: "dashboard",
  lang: FALLBACK_LANG,
  catalogue: {},
  fallback: {},
};

// ---------- Helpers ----------

const $ = (sel) => document.querySelector(sel);
const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/** Look a key up in the active catalogue, then English, then the key itself. */
function t(key, params) {
  let text = state.catalogue[key] || state.fallback[key] || key;
  if (params) {
    for (const [name, value] of Object.entries(params)) {
      text = text.replaceAll("{" + name + "}", value);
    }
  }
  return text;
}

function signalColor(dbm) {
  if (dbm >= -60) return COLORS.green;
  if (dbm >= -70) return COLORS.yellow;
  if (dbm >= -80) return COLORS.orange;
  return COLORS.red;
}

function signalLabel(dbm) {
  if (dbm >= -60) return t("signal.good");
  if (dbm >= -70) return t("signal.fair");
  if (dbm >= -80) return t("signal.weak");
  return t("signal.verypoor");
}

function ratio(dbm) {
  const r = (dbm - DBM_MIN) / (DBM_MAX - DBM_MIN);
  return Math.max(0, Math.min(1, r));
}

function toast(message, kind = "") {
  const el = document.createElement("div");
  el.className = "toast " + kind;
  el.textContent = message;
  $("#toast").appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

async function api(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let data = null;
  try {
    data = await res.json();
  } catch (e) {
    data = null;
  }
  if (!res.ok) {
    throw new Error((data && data.error) || t("error.generic", { status: res.status }));
  }
  return data;
}

// ---------- Translations ----------

async function fetchCatalogue(code) {
  try {
    const res = await fetch(`/locales/${code}.json`);
    return res.ok ? await res.json() : {};
  } catch (e) {
    return {};
  }
}

async function loadLanguage(code) {
  if (!Object.keys(state.fallback).length) {
    state.fallback = await fetchCatalogue(FALLBACK_LANG);
  }
  state.lang = code || FALLBACK_LANG;
  state.catalogue =
    state.lang === FALLBACK_LANG ? state.fallback : await fetchCatalogue(state.lang);
  document.documentElement.lang = state.lang;
  applyStaticTranslations();
}

/** Fill every element carrying a data-i18n attribute. */
function applyStaticTranslations() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
  document.querySelectorAll("[data-i18n-alt]").forEach((el) => {
    el.alt = t(el.dataset.i18nAlt);
  });
  document.title = t("app.title");
}

// ---------- Reusable fragments ----------

function statCard(label, value, { unit = "", sub = "", color = COLORS.blue } = {}) {
  return `<div class="stat">
    <div class="label">${esc(label)}</div>
    <div class="value" style="color:${color}">${esc(value)}${
      unit ? `<span class="unit"> ${esc(unit)}</span>` : ""
    }</div>
    ${sub ? `<div class="sub">${esc(sub)}</div>` : ""}
    <div class="glow" style="background:${color}"></div>
  </div>`;
}

function gauge(name, dbm, { checkbox = false } = {}) {
  const color = signalColor(dbm);
  const pct = (ratio(dbm) * 100).toFixed(1);
  const box = checkbox ? `<input type="checkbox" value="${esc(name)}">` : "";
  return `<label class="gauge ${checkbox ? "selectable" : ""}">
    ${box}
    <span class="name" title="${esc(name)}">${esc(name)}</span>
    <span class="track">
      <span class="fill" style="width:${pct}%;
        background:linear-gradient(90deg,${color}55,${color})"></span>
    </span>
    <span class="num" style="color:${color}">${dbm.toFixed(0)} dBm</span>
  </label>`;
}

function statsTable(rows) {
  if (!rows.length) return `<p class="empty">${esc(t("table.empty"))}</p>`;
  const body = rows
    .map(
      (r) => `<tr>
        <td>${esc(r.ssid)}</td>
        <td class="num">${r.min.toFixed(0)}</td>
        <td class="num" style="color:${signalColor(r.mean)};font-weight:600">
          ${r.mean.toFixed(1)}</td>
        <td class="num">${r.max.toFixed(0)}</td>
        <td class="num">${r.count}</td>
      </tr>`
    )
    .join("");
  return `<table>
    <thead><tr>
      <th>${esc(t("table.network"))}</th><th>${esc(t("table.min"))}</th>
      <th>${esc(t("table.mean"))}</th><th>${esc(t("table.max"))}</th>
      <th>${esc(t("table.points"))}</th>
    </tr></thead>
    <tbody>${body}</tbody>
  </table>`;
}

// ---------- Data loading ----------

async function loadConfig() {
  state.config = await api("/api/config");
  $("#tag-iface").textContent = state.config.interface;
  $("#tag-status").textContent = state.config.valid
    ? t("status.ready")
    : t(state.config.status_key);
  $("#foot-iface").textContent = t("topbar.interface", {
    interface: state.config.interface,
  });
}

async function loadMeasurements() {
  const data = await api("/api/measurements");
  if (!state.dirty) state.measurements = data.measurements;
  state.ssids = data.ssids;
  state.stats = data.stats;
  $("#foot-points").textContent = t("topbar.points", {
    count: state.measurements.length,
  });
}

// ---------- Views ----------

function renderDashboard() {
  const stats = state.stats;
  const means = stats.map((s) => s.mean);
  const best = stats[0];
  const avg = means.length ? means.reduce((a, b) => a + b, 0) / means.length : null;

  $("#dash-stats").innerHTML =
    statCard(t("dash.points"), state.measurements.length) +
    statCard(t("dash.networks"), stats.length, {
      sub: t("dash.networks.sub", { count: state.config.ssids.length }),
    }) +
    (best
      ? statCard(t("dash.best"), best.mean.toFixed(0), {
          unit: "dBm",
          sub: best.ssid,
          color: signalColor(best.mean),
        })
      : statCard(t("dash.best"), "--", { color: COLORS.dim })) +
    (avg !== null
      ? statCard(t("dash.average"), avg.toFixed(1), {
          unit: "dBm",
          sub: signalLabel(avg),
          color: signalColor(avg),
        })
      : statCard(t("dash.average"), "--", { color: COLORS.dim }));

  $("#dash-gauges").innerHTML = stats.length
    ? stats.map((s) => gauge(s.ssid, s.mean)).join("")
    : `<p class="empty">${esc(t("dash.empty"))}</p>`;

  $("#dash-table").innerHTML = statsTable(stats);
}

function renderConfig() {
  const c = state.config;
  $("#cfg-plan").value = c.plan_path;
  $("#cfg-measures").value = c.measurements_path;
  $("#cfg-timeout").value = c.scan_timeout;
  $("#cfg-dpi").value = c.heatmap_dpi;
  $("#cfg-res").value = c.heatmap_resolution;
  refreshSliderLabels();
  loadInterfaces();
}

function refreshSliderLabels() {
  $("#lbl-timeout").textContent = t("config.params.timeout", {
    value: $("#cfg-timeout").value,
  });
  $("#lbl-dpi").textContent = t("config.params.dpi", { value: $("#cfg-dpi").value });
  $("#lbl-res").textContent = t("config.params.grid", { value: $("#cfg-res").value });
}

async function loadInterfaces() {
  const select = $("#iface-select");
  select.innerHTML = "<option>...</option>";
  try {
    const { interfaces } = await api("/api/interfaces");
    if (interfaces.length) {
      select.innerHTML = interfaces
        .map(
          (i) =>
            `<option ${i === state.config.interface ? "selected" : ""}>${esc(i)}</option>`
        )
        .join("");
      $("#iface-hint").textContent = t("config.interface.found", {
        count: interfaces.length,
      });
    } else {
      select.innerHTML = `<option>${esc(state.config.interface)}</option>`;
      $("#iface-hint").textContent = t("config.interface.none");
    }
  } catch (e) {
    select.innerHTML = `<option>${esc(state.config.interface)}</option>`;
    $("#iface-hint").textContent = t("config.interface.error", { error: e.message });
  }
}

function renderNetworks() {
  const list = state.config.ssids;
  $("#ssid-title").textContent = t("networks.tracked", { count: list.length });
  $("#ssid-list").innerHTML = list.length
    ? list
        .map(
          (s, i) => `<div class="list-row">
            <span style="color:var(--dim)">${i + 1}.</span>
            <span class="grow">${esc(s)}</span>
            <button class="danger" data-remove="${esc(s)}">${esc(
            t("networks.remove")
          )}</button>
          </div>`
        )
        .join("")
    : `<p class="empty">${esc(t("networks.tracked.empty"))}</p>`;

  $("#ssid-list")
    .querySelectorAll("[data-remove]")
    .forEach((btn) => {
      btn.onclick = async () => {
        await api("/api/ssids/" + encodeURIComponent(btn.dataset.remove), {
          method: "DELETE",
        });
        await loadConfig();
        renderNetworks();
        toast(t("networks.removed"), "ok");
      };
    });

  renderScanResults();
}

function renderScanResults() {
  const box = $("#scan-results");
  if (state.scanned === null) {
    box.innerHTML = `<p class="empty">${esc(t("networks.scan.empty"))}</p>`;
    $("#scan-add").disabled = true;
    return;
  }
  if (!state.scanned.length) {
    box.innerHTML = `<p class="empty">${esc(t("networks.scan.none"))}</p>`;
    $("#scan-add").disabled = true;
    return;
  }
  box.innerHTML = state.scanned
    .map((n) => gauge(n.ssid, n.rssi, { checkbox: true }))
    .join("");
  const known = new Set(state.config.ssids);
  box.querySelectorAll("input[type=checkbox]").forEach((cb) => {
    if (known.has(cb.value)) {
      cb.checked = true;
      cb.disabled = true;
    }
  });
  $("#scan-add").disabled = false;
}

// ---------- Survey ----------

function drawMarkers(points) {
  const wrap = $("#plan-wrap");
  wrap.querySelectorAll(".marker").forEach((m) => m.remove());
  points.forEach((p, i) => {
    const dot = document.createElement("div");
    dot.className = "marker" + (i === points.length - 1 ? " latest" : "");
    dot.style.left = p.x * 100 + "%";
    dot.style.top = p.y * 100 + "%";
    dot.textContent = i + 1;
    wrap.appendChild(dot);
  });
}

function renderCollect() {
  const points = state.measurements;
  const img = $("#plan-img");
  if (img && !img.src) img.src = "/plan?" + Date.now();

  $("#collect-stat").innerHTML = `
    <div class="label">${esc(t("collect.points"))}</div>
    <div class="value" style="color:${COLORS.orange}">${points.length}</div>
    <div class="sub">${esc(state.dirty ? t("collect.dirty") : t("collect.synced"))}</div>
    <div class="glow" style="background:${COLORS.orange}"></div>`;

  $("#undo-btn").disabled = !points.length;
  $("#clear-btn").disabled = !points.length;
  $("#save-btn").disabled = !points.length || !state.dirty;

  $("#collect-hint").textContent = state.config.ssids.length
    ? t("collect.hint.ready")
    : t("collect.hint.nossid");

  // Markers are positioned in percent so they follow any resize.
  drawMarkers(points);

  const last = points[points.length - 1];
  $("#last-point").innerHTML = last
    ? Object.entries(last.signaux)
        .sort((a, b) => b[1] - a[1])
        .map(([ssid, rssi]) => gauge(ssid, rssi))
        .join("")
    : `<p class="empty">${esc(t("collect.last.empty"))}</p>`;
}

async function onPlanClick(event) {
  if (state.scanning) return;
  if (!state.config.ssids.length) {
    toast(t("collect.needssid"), "warn");
    return;
  }

  const rect = $("#plan-img").getBoundingClientRect();
  const x = (event.clientX - rect.left) / rect.width;
  const y = (event.clientY - rect.top) / rect.height;
  if (x < 0 || x > 1 || y < 0 || y > 1) return;

  state.scanning = true;
  $("#plan-wrap").classList.add("busy");
  $("#scan-overlay").classList.remove("hidden");
  $("#scan-msg").textContent = t("collect.scanning");

  let elapsed = 0;
  const timeout = state.config.scan_timeout;
  const ticker = setInterval(() => {
    elapsed += 1;
    $("#scan-msg").textContent = t("collect.scanning.progress", { elapsed, timeout });
  }, 1000);

  try {
    const { networks } = await api("/api/scan", {
      method: "POST",
      body: JSON.stringify({ only_targets: true }),
    });
    if (!networks.length) {
      toast(t("collect.point.none"), "warn");
    } else {
      const signaux = {};
      networks.forEach((n) => (signaux[n.ssid] = n.rssi));
      state.measurements.push({ x, y, signaux });
      state.dirty = true;
      toast(
        t("collect.point.added", {
          index: state.measurements.length,
          count: networks.length,
        }),
        "ok"
      );
      renderCollect();
    }
  } catch (e) {
    toast(t("networks.scan.failed", { error: e.message }), "err");
  } finally {
    clearInterval(ticker);
    state.scanning = false;
    $("#plan-wrap").classList.remove("busy");
    $("#scan-overlay").classList.add("hidden");
  }
}

// ---------- Statistics ----------

function renderStats() {
  $("#stats-table").innerHTML = statsTable(state.stats);

  if (!state.stats.length) {
    $("#stats-range").innerHTML = `<p class="empty">${esc(t("stats.empty"))}</p>`;
    return;
  }

  // Bar from minimum to maximum, with a marker on the mean.
  $("#stats-range").innerHTML = state.stats
    .map((s) => {
      const left = ratio(s.min) * 100;
      const width = Math.max(1, (ratio(s.max) - ratio(s.min)) * 100);
      const mean = ratio(s.mean) * 100;
      const color = signalColor(s.mean);
      return `<div class="gauge">
        <span class="name" title="${esc(s.ssid)}">${esc(s.ssid)}</span>
        <span class="track" style="position:relative">
          <span style="position:absolute;left:${left}%;width:${width}%;top:0;bottom:0;
            background:${color}44;border-left:1px solid ${color};
            border-right:1px solid ${color}"></span>
          <span style="position:absolute;left:${mean}%;top:0;bottom:0;width:2px;
            background:${color};transform:translateX(-1px)"></span>
        </span>
        <span class="num" style="color:${color}">${s.mean.toFixed(1)} dBm</span>
      </div>`;
    })
    .join("");
}

// ---------- Heatmaps ----------

async function loadHeatmaps() {
  const { heatmaps } = await api("/api/heatmaps");
  state.heatmaps = heatmaps;
  renderHeatmapGrid();
}

function renderHeatmapGrid() {
  const grid = $("#heatmap-grid");
  if (!state.heatmaps.length) {
    grid.innerHTML = `<p class="empty">${esc(t("heatmaps.empty"))}</p>`;
    return;
  }

  // One timestamp for every tile: the cache is invalidated after a run,
  // and the images stay shared afterwards.
  const stamp = state.heatmapStamp || (state.heatmapStamp = Date.now());

  grid.innerHTML = state.heatmaps
    .map((h) => {
      const s = state.stats.find((r) => r.ssid === h.ssid);
      const color = s ? signalColor(s.mean) : COLORS.dim;
      const mean = s ? `${s.mean.toFixed(0)} dBm` : "";
      const meta = s
        ? `${t("heatmaps.points", { count: s.count })} &middot; ${signalLabel(s.mean)}`
        : "";
      return `<div class="tile" data-file="${esc(h.file)}">
        <div class="tile-head">
          <span class="name" title="${esc(h.ssid)}">${esc(h.ssid)}</span>
          <span class="mean" style="color:${color}">${mean}</span>
        </div>
        <img src="/heatmap/${encodeURIComponent(h.file)}?w=${THUMB_W}&amp;t=${stamp}"
             alt="${esc(h.ssid)}">
        <div class="meta">${meta}</div>
      </div>`;
    })
    .join("");

  grid.querySelectorAll(".tile").forEach((tile) => {
    tile.onclick = () => openHeatmap(tile.dataset.file);
  });
}

function openHeatmap(file) {
  const entry = state.heatmaps.find((h) => h.file === file);
  if (!entry) return;
  const s = state.stats.find((r) => r.ssid === entry.ssid);

  $("#modal-title").textContent = entry.ssid;
  $("#modal-dl").href = "/heatmap/" + encodeURIComponent(entry.file);
  // The dialog shows the full resolution image, not the thumbnail.
  $("#modal-img").src =
    "/heatmap/" + encodeURIComponent(entry.file) + "?t=" + (state.heatmapStamp || "");
  $("#modal-img").alt = entry.ssid;
  $("#modal-stats").innerHTML = s
    ? statCard(t("stat.minimum"), s.min.toFixed(0), {
        unit: "dBm",
        color: signalColor(s.min),
      }) +
      statCard(t("stat.average"), s.mean.toFixed(1), {
        unit: "dBm",
        sub: signalLabel(s.mean),
        color: signalColor(s.mean),
      }) +
      statCard(t("stat.maximum"), s.max.toFixed(0), {
        unit: "dBm",
        color: signalColor(s.max),
      }) +
      statCard(t("stat.points"), s.count)
    : "";
  $("#modal").classList.remove("hidden");
}

function closeHeatmap() {
  $("#modal").classList.add("hidden");
  $("#modal-img").removeAttribute("src");
}

// ---------- Navigation ----------

const VIEWS = {
  dashboard: { crumb: "nav.dashboard", render: renderDashboard },
  config: { crumb: "nav.config", render: renderConfig },
  networks: { crumb: "nav.networks", render: renderNetworks },
  collect: { crumb: "nav.collect", render: renderCollect },
  stats: { crumb: "nav.stats", render: renderStats },
  heatmaps: { crumb: "nav.heatmaps", render: loadHeatmaps },
  export: { crumb: "nav.export", render: () => {} },
};

async function show(name) {
  state.view = name;
  document.querySelectorAll("main section").forEach((s) => s.classList.add("hidden"));
  $("#view-" + name).classList.remove("hidden");
  document
    .querySelectorAll("#nav button")
    .forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  $("#crumb").textContent = "/ " + t(VIEWS[name].crumb);

  await loadConfig();
  if (!state.dirty) await loadMeasurements();
  await VIEWS[name].render();
}

function fillLanguageSelect() {
  const select = $("#lang-select");
  select.innerHTML = (state.config.languages || [])
    .map(
      (l) =>
        `<option value="${esc(l.code)}" ${
          l.code === state.lang ? "selected" : ""
        }>${esc(l.name)}</option>`
    )
    .join("");
}

// ---------- Events ----------

function wire() {
  document.querySelectorAll("#nav button").forEach((btn) => {
    btn.onclick = () => show(btn.dataset.view);
  });

  $("#lang-select").onchange = async (e) => {
    await api("/api/config", {
      method: "POST",
      body: JSON.stringify({ language: e.target.value }),
    });
    await loadLanguage(e.target.value);
    await show(state.view);
  };

  // Settings
  ["cfg-timeout", "cfg-dpi", "cfg-res"].forEach((id) => {
    $("#" + id).oninput = refreshSliderLabels;
  });
  $("#iface-refresh").onclick = loadInterfaces;
  $("#cfg-save").onclick = async () => {
    try {
      await api("/api/config", {
        method: "POST",
        body: JSON.stringify({
          interface: $("#iface-select").value,
          scan_timeout: +$("#cfg-timeout").value,
          heatmap_dpi: +$("#cfg-dpi").value,
          heatmap_resolution: +$("#cfg-res").value,
        }),
      });
      await loadConfig();
      toast(t("config.saved"), "ok");
    } catch (e) {
      toast(e.message, "err");
    }
  };

  // Networks
  $("#ssid-add").onclick = async () => {
    const value = $("#ssid-input").value.trim();
    if (!value) return;
    const res = await api("/api/ssids", {
      method: "POST",
      body: JSON.stringify({ ssid: value }),
    });
    $("#ssid-input").value = "";
    await loadConfig();
    renderNetworks();
    toast(res.added.length ? t("networks.add.done") : t("networks.add.duplicate"),
          res.added.length ? "ok" : "warn");
  };
  $("#ssid-input").onkeydown = (e) => {
    if (e.key === "Enter") $("#ssid-add").click();
  };

  $("#scan-btn").onclick = async () => {
    const btn = $("#scan-btn");
    btn.disabled = true;
    btn.textContent = t("networks.scan.running");
    try {
      const { networks } = await api("/api/scan", {
        method: "POST",
        body: JSON.stringify({}),
      });
      state.scanned = networks;
      renderScanResults();
      toast(t("networks.scan.found", { count: networks.length }),
            networks.length ? "ok" : "warn");
    } catch (e) {
      toast(t("networks.scan.failed", { error: e.message }), "err");
    } finally {
      btn.disabled = false;
      btn.textContent = t("networks.scan.run");
    }
  };

  $("#scan-add").onclick = async () => {
    const picked = [
      ...$("#scan-results").querySelectorAll("input:checked:not(:disabled)"),
    ].map((cb) => cb.value);
    if (!picked.length) return toast(t("networks.add.nothing"), "warn");
    await api("/api/ssids", { method: "POST", body: JSON.stringify({ ssids: picked }) });
    await loadConfig();
    renderNetworks();
    toast(t("networks.add.selected", { count: picked.length }), "ok");
  };

  // Survey
  $("#plan-img").onclick = onPlanClick;
  $("#plan-img").onerror = () => {
    $("#plan-wrap").innerHTML = `<p class="empty">${esc(
      t("collect.plan.missing", { path: state.config.plan_path })
    )}</p>`;
  };

  $("#undo-btn").onclick = () => {
    state.measurements.pop();
    state.dirty = true;
    renderCollect();
  };

  $("#clear-btn").onclick = () => {
    if (!confirm(t("collect.clear.confirm"))) return;
    state.measurements = [];
    state.dirty = true;
    renderCollect();
  };

  $("#save-btn").onclick = async () => {
    try {
      const res = await api("/api/measurements", {
        method: "POST",
        body: JSON.stringify({ measurements: state.measurements }),
      });
      state.dirty = false;
      await loadMeasurements();
      renderCollect();
      toast(t("collect.saved", { count: res.saved }), "ok");
    } catch (e) {
      toast(t("collect.save.failed", { error: e.message }), "err");
    }
  };

  // Heatmaps
  $("#gen-btn").onclick = async () => {
    const btn = $("#gen-btn");
    btn.disabled = true;
    btn.textContent = t("heatmaps.generating");
    try {
      const res = await api("/api/heatmaps", { method: "POST" });
      toast(t("heatmaps.generated", { done: res.generated, total: res.total }), "ok");
      state.heatmapStamp = Date.now(); // force the thumbnails to reload
      await loadHeatmaps();
    } catch (e) {
      toast(t("heatmaps.generate.failed", { error: e.message }), "err");
    } finally {
      btn.disabled = false;
      btn.textContent = t("heatmaps.generate.button");
    }
  };

  const cols = $("#grid-cols");
  const applyCols = () => {
    $("#heatmap-grid").style.setProperty("--cols", cols.value);
    localStorage.setItem("gridCols", cols.value);
  };
  cols.value = localStorage.getItem("gridCols") || "4";
  cols.onchange = applyCols;
  applyCols();

  $("#modal-close").onclick = closeHeatmap;
  $("#modal").onclick = (e) => {
    if (e.target === $("#modal")) closeHeatmap();
  };
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeHeatmap();
  });

  // Avoid losing points that were never saved.
  window.addEventListener("beforeunload", (e) => {
    if (state.dirty) e.preventDefault();
  });
}

async function start() {
  const config = await api("/api/config");
  state.config = config;
  await loadLanguage(config.language);
  fillLanguageSelect();
  wire();
  await show("dashboard");
}

start().catch((e) => toast("Startup failed: " + e.message, "err"));
