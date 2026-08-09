"use strict";

// Bornes d'affichage des jauges, en dBm.
const DBM_MIN = -100;
const DBM_MAX = -30;

// Largeur des vignettes demandée au serveur. Généreuse par rapport à la
// taille d'affichage pour rester net sur les écrans haute densité.
const THUMB_W = 560;

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
  scanned: [],
  heatmaps: [],
  dirty: false,
  scanning: false,
};

// ---------- Utilitaires ----------

const $ = (sel) => document.querySelector(sel);
const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function signalColor(dbm) {
  if (dbm >= -60) return COLORS.green;
  if (dbm >= -70) return COLORS.yellow;
  if (dbm >= -80) return COLORS.orange;
  return COLORS.red;
}

function signalLabel(dbm) {
  if (dbm >= -60) return "bon";
  if (dbm >= -70) return "correct";
  if (dbm >= -80) return "faible";
  return "très faible";
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
    throw new Error((data && data.error) || `Erreur ${res.status}`);
  }
  return data;
}

// ---------- Fragments réutilisables ----------

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
  const box = checkbox
    ? `<input type="checkbox" value="${esc(name)}">`
    : "";
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
  if (!rows.length) return `<p class="empty">Aucune donnée.</p>`;
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
    <thead><tr><th>Réseau</th><th>Min</th><th>Moy</th><th>Max</th><th>Pts</th></tr></thead>
    <tbody>${body}</tbody>
  </table>`;
}

// ---------- Chargement des données ----------

async function loadConfig() {
  state.config = await api("/api/config");
  $("#tag-iface").textContent = state.config.interface;
  $("#tag-status").textContent = state.config.valid ? "prêt" : state.config.status;
  $("#foot-iface").textContent = "interface : " + state.config.interface;
}

async function loadMeasurements() {
  const data = await api("/api/measurements");
  if (!state.dirty) state.measurements = data.measurements;
  state.ssids = data.ssids;
  state.stats = data.stats;
  $("#foot-points").textContent =
    `${state.measurements.length} point${state.measurements.length > 1 ? "s" : ""} mesuré${
      state.measurements.length > 1 ? "s" : ""
    }`;
}

// ---------- Vues ----------

function renderDashboard() {
  const stats = state.stats;
  const means = stats.map((s) => s.mean);
  const best = stats[0];
  const avg = means.length ? means.reduce((a, b) => a + b, 0) / means.length : null;

  $("#dash-stats").innerHTML =
    statCard("Points mesurés", state.measurements.length) +
    statCard("Réseaux suivis", stats.length, {
      sub: `${state.config.ssids.length} configurés`,
    }) +
    (best
      ? statCard("Meilleur réseau", best.mean.toFixed(0), {
          unit: "dBm",
          sub: best.ssid,
          color: signalColor(best.mean),
        })
      : statCard("Meilleur réseau", "--", { color: COLORS.dim })) +
    (avg !== null
      ? statCard("Signal moyen", avg.toFixed(1), {
          unit: "dBm",
          sub: signalLabel(avg),
          color: signalColor(avg),
        })
      : statCard("Signal moyen", "--", { color: COLORS.dim }));

  $("#dash-gauges").innerHTML = stats.length
    ? stats.map((s) => gauge(s.ssid, s.mean)).join("")
    : `<p class="empty">Aucune mesure. Commencez par la page Collecte.</p>`;

  $("#dash-table").innerHTML = statsTable(stats);
}

function renderConfig() {
  const c = state.config;
  $("#cfg-plan").value = c.plan_path;
  $("#cfg-measures").value = c.measurements_path;
  $("#cfg-timeout").value = c.scan_timeout;
  $("#cfg-dpi").value = c.heatmap_dpi;
  $("#cfg-res").value = c.heatmap_resolution;
  $("#lbl-timeout").textContent = c.scan_timeout;
  $("#lbl-dpi").textContent = c.heatmap_dpi;
  $("#lbl-res").textContent = c.heatmap_resolution;
  loadInterfaces();
}

async function loadInterfaces() {
  const select = $("#iface-select");
  select.innerHTML = `<option>...</option>`;
  try {
    const { interfaces } = await api("/api/interfaces");
    if (interfaces.length) {
      select.innerHTML = interfaces
        .map(
          (i) =>
            `<option ${i === state.config.interface ? "selected" : ""}>${esc(i)}</option>`
        )
        .join("");
      $("#iface-hint").textContent = `${interfaces.length} interface(s) détectée(s).`;
    } else {
      select.innerHTML = `<option>${esc(state.config.interface)}</option>`;
      $("#iface-hint").textContent =
        "Aucune interface détectée. Vérifiez que 'iw' est installé et que sudo fonctionne sans mot de passe.";
    }
  } catch (e) {
    select.innerHTML = `<option>${esc(state.config.interface)}</option>`;
    $("#iface-hint").textContent = "Détection impossible : " + e.message;
  }
}

function renderNetworks() {
  const list = state.config.ssids;
  $("#ssid-count").textContent = list.length;
  $("#ssid-list").innerHTML = list.length
    ? list
        .map(
          (s, i) => `<div class="list-row">
            <span style="color:var(--dim)">${i + 1}.</span>
            <span class="grow">${esc(s)}</span>
            <button class="danger" data-remove="${esc(s)}">Retirer</button>
          </div>`
        )
        .join("")
    : `<p class="empty">Aucun réseau suivi.</p>`;

  $("#ssid-list")
    .querySelectorAll("[data-remove]")
    .forEach((btn) => {
      btn.onclick = async () => {
        await api("/api/ssids/" + encodeURIComponent(btn.dataset.remove), {
          method: "DELETE",
        });
        await loadConfig();
        renderNetworks();
        toast("Réseau retiré.", "ok");
      };
    });
}

function renderScanResults() {
  const box = $("#scan-results");
  if (!state.scanned.length) {
    box.innerHTML = `<p class="empty">Aucun réseau détecté.</p>`;
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

// ---------- Collecte ----------

function renderCollect() {
  const points = state.measurements;
  const img = $("#plan-img");
  if (!img.src) img.src = "/plan?" + Date.now();

  $("#collect-stat").innerHTML = `
    <div class="label">Points collectés</div>
    <div class="value" style="color:${COLORS.orange}">${points.length}</div>
    <div class="sub">${state.dirty ? "modifications non enregistrées" : "synchronisé"}</div>
    <div class="glow" style="background:${COLORS.orange}"></div>`;

  $("#undo-btn").disabled = !points.length;
  $("#clear-btn").disabled = !points.length;
  $("#save-btn").disabled = !points.length || !state.dirty;

  $("#collect-hint").textContent = state.config.ssids.length
    ? "Seuls les réseaux suivis sont enregistrés."
    : "Aucun réseau suivi : ajoutez des SSID avant de collecter.";

  // Repères positionnés en pourcentage : ils suivent le redimensionnement.
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

  const last = points[points.length - 1];
  $("#last-point").innerHTML = last
    ? Object.entries(last.signaux)
        .sort((a, b) => b[1] - a[1])
        .map(([ssid, rssi]) => gauge(ssid, rssi))
        .join("")
    : `<p class="empty">Aucun point collecté.</p>`;
}

async function onPlanClick(event) {
  if (state.scanning) return;
  if (!state.config.ssids.length) {
    toast("Ajoutez d'abord des réseaux à suivre.", "warn");
    return;
  }

  const rect = $("#plan-img").getBoundingClientRect();
  const x = (event.clientX - rect.left) / rect.width;
  const y = (event.clientY - rect.top) / rect.height;
  if (x < 0 || x > 1 || y < 0 || y > 1) return;

  state.scanning = true;
  $("#plan-wrap").classList.add("busy");
  $("#scan-overlay").classList.remove("hidden");

  let elapsed = 0;
  const timeout = state.config.scan_timeout;
  const ticker = setInterval(() => {
    elapsed += 1;
    $("#scan-msg").textContent = `Scan en cours... ${elapsed} s / ${timeout} s max`;
  }, 1000);

  try {
    const { networks } = await api("/api/scan", {
      method: "POST",
      body: JSON.stringify({ only_targets: true }),
    });
    if (!networks.length) {
      toast("Aucun réseau suivi détecté ici. Recliquez pour réessayer.", "warn");
    } else {
      const signaux = {};
      networks.forEach((n) => (signaux[n.ssid] = n.rssi));
      state.measurements.push({ x, y, signaux });
      state.dirty = true;
      toast(`Point ${state.measurements.length} : ${networks.length} réseau(x).`, "ok");
      renderCollect();
    }
  } catch (e) {
    toast("Scan impossible : " + e.message, "err");
  } finally {
    clearInterval(ticker);
    state.scanning = false;
    $("#plan-wrap").classList.remove("busy");
    $("#scan-overlay").classList.add("hidden");
    $("#scan-msg").textContent = "Scan en cours...";
  }
}

// ---------- Statistiques ----------

function renderStats() {
  $("#stats-table").innerHTML = statsTable(state.stats);

  if (!state.stats.length) {
    $("#stats-range").innerHTML = `<p class="empty">Aucune mesure.</p>`;
    return;
  }

  // Barre du min au max, avec un repère sur la moyenne.
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
    grid.innerHTML = `<p class="empty">Aucune carte générée.</p>`;
    return;
  }

  // Un seul horodatage pour toutes les vignettes : le cache est invalidé
  // après une génération, mais les images restent mutualisées ensuite.
  const stamp = state.heatmapStamp || (state.heatmapStamp = Date.now());

  grid.innerHTML = state.heatmaps
    .map((h) => {
      const s = state.stats.find((r) => r.ssid === h.ssid);
      const color = s ? signalColor(s.mean) : COLORS.dim;
      const mean = s ? `${s.mean.toFixed(0)} dBm` : "";
      const meta = s ? `${s.count} points &middot; ${signalLabel(s.mean)}` : "";
      return `<div class="tile" data-file="${esc(h.file)}">
        <div class="tile-head">
          <span class="name" title="${esc(h.ssid)}">${esc(h.ssid)}</span>
          <span class="mean" style="color:${color}">${mean}</span>
        </div>
        <img src="/heatmap/${encodeURIComponent(h.file)}?w=${THUMB_W}&amp;t=${stamp}"
             alt="Heatmap ${esc(h.ssid)}">
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
  // La fenêtre affiche l'image pleine résolution, pas la vignette.
  $("#modal-img").src =
    "/heatmap/" + encodeURIComponent(entry.file) + "?t=" + (state.heatmapStamp || "");
  $("#modal-img").alt = "Heatmap " + entry.ssid;
  $("#modal-stats").innerHTML = s
    ? statCard("Minimum", s.min.toFixed(0), { unit: "dBm", color: signalColor(s.min) }) +
      statCard("Moyenne", s.mean.toFixed(1), {
        unit: "dBm",
        sub: signalLabel(s.mean),
        color: signalColor(s.mean),
      }) +
      statCard("Maximum", s.max.toFixed(0), { unit: "dBm", color: signalColor(s.max) }) +
      statCard("Points", s.count)
    : "";
  $("#modal").classList.remove("hidden");
}

function closeHeatmap() {
  $("#modal").classList.add("hidden");
  $("#modal-img").removeAttribute("src");
}

// ---------- Navigation ----------

const VIEWS = {
  dashboard: { crumb: "Vue d'ensemble", render: renderDashboard },
  config: { crumb: "Configuration", render: renderConfig },
  networks: { crumb: "Réseaux", render: renderNetworks },
  collect: { crumb: "Collecte", render: renderCollect },
  stats: { crumb: "Statistiques", render: renderStats },
  heatmaps: { crumb: "Heatmaps", render: loadHeatmaps },
  export: { crumb: "Export", render: () => {} },
};

async function show(name) {
  document.querySelectorAll("main section").forEach((s) => s.classList.add("hidden"));
  $("#view-" + name).classList.remove("hidden");
  document
    .querySelectorAll("#nav button")
    .forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  $("#crumb").textContent = "/ " + VIEWS[name].crumb;

  await loadConfig();
  if (!state.dirty) await loadMeasurements();
  VIEWS[name].render();
}

// ---------- Événements ----------

function wire() {
  document.querySelectorAll("#nav button").forEach((btn) => {
    btn.onclick = () => show(btn.dataset.view);
  });

  // Configuration
  [["cfg-timeout", "lbl-timeout"], ["cfg-dpi", "lbl-dpi"], ["cfg-res", "lbl-res"]].forEach(
    ([input, label]) => {
      $("#" + input).oninput = (e) => ($("#" + label).textContent = e.target.value);
    }
  );
  $("#iface-refresh").onclick = loadInterfaces;
  $("#cfg-save").onclick = async () => {
    try {
      state.config = await api("/api/config", {
        method: "POST",
        body: JSON.stringify({
          interface: $("#iface-select").value,
          scan_timeout: +$("#cfg-timeout").value,
          heatmap_dpi: +$("#cfg-dpi").value,
          heatmap_resolution: +$("#cfg-res").value,
        }),
      });
      await loadConfig();
      toast("Configuration enregistrée.", "ok");
    } catch (e) {
      toast(e.message, "err");
    }
  };

  // Réseaux
  $("#ssid-add").onclick = async () => {
    const value = $("#ssid-input").value.trim();
    if (!value) return;
    await api("/api/ssids", { method: "POST", body: JSON.stringify({ ssid: value }) });
    $("#ssid-input").value = "";
    await loadConfig();
    renderNetworks();
    toast("Réseau ajouté.", "ok");
  };
  $("#ssid-input").onkeydown = (e) => {
    if (e.key === "Enter") $("#ssid-add").click();
  };

  $("#scan-btn").onclick = async () => {
    const btn = $("#scan-btn");
    btn.disabled = true;
    btn.textContent = "Scan en cours...";
    try {
      const { networks } = await api("/api/scan", {
        method: "POST",
        body: JSON.stringify({}),
      });
      state.scanned = networks;
      renderScanResults();
      toast(`${networks.length} réseau(x) détecté(s).`, networks.length ? "ok" : "warn");
    } catch (e) {
      toast("Scan impossible : " + e.message, "err");
    } finally {
      btn.disabled = false;
      btn.textContent = "Lancer un scan";
    }
  };

  $("#scan-add").onclick = async () => {
    const picked = [...$("#scan-results").querySelectorAll("input:checked:not(:disabled)")].map(
      (cb) => cb.value
    );
    if (!picked.length) return toast("Aucun nouveau réseau sélectionné.", "warn");
    await api("/api/ssids", { method: "POST", body: JSON.stringify({ ssids: picked }) });
    await loadConfig();
    renderNetworks();
    renderScanResults();
    toast(`${picked.length} réseau(x) ajouté(s).`, "ok");
  };

  // Collecte
  $("#plan-img").onclick = onPlanClick;
  $("#plan-img").onerror = () => {
    $("#plan-wrap").innerHTML =
      `<p class="empty">Plan introuvable (${esc(state.config.plan_path)}).</p>`;
  };

  $("#undo-btn").onclick = () => {
    state.measurements.pop();
    state.dirty = true;
    renderCollect();
  };

  $("#clear-btn").onclick = () => {
    if (!confirm("Effacer tous les points collectés ?")) return;
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
      toast(`${res.saved} points enregistrés.`, "ok");
    } catch (e) {
      toast("Enregistrement impossible : " + e.message, "err");
    }
  };

  // Heatmaps
  $("#gen-btn").onclick = async () => {
    const btn = $("#gen-btn");
    btn.disabled = true;
    btn.textContent = "Génération...";
    try {
      const res = await api("/api/heatmaps", { method: "POST" });
      toast(`${res.generated}/${res.total} cartes générées.`, "ok");
      state.heatmapStamp = Date.now(); // force le rechargement des vignettes
      await loadHeatmaps();
    } catch (e) {
      toast("Génération impossible : " + e.message, "err");
    } finally {
      btn.disabled = false;
      btn.textContent = "Générer les cartes";
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

  // Évite de perdre des points non enregistrés.
  window.addEventListener("beforeunload", (e) => {
    if (state.dirty) e.preventDefault();
  });
}

wire();
show("dashboard").catch((e) => toast("Chargement impossible : " + e.message, "err"));
