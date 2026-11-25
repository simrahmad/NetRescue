// NetRescue dashboard front end.
// Every second: ask our Flask server for the 4 data sets, then redraw the page.

const POLL_MS = 1000;
const FETCH_TIMEOUT_MS = 5000;
const SVG_NS = "http://www.w3.org/2000/svg";

// Where each node is drawn inside the 640 x 300 SVG: [x, y]
const NODE_POS = {
  h1: [60, 150], s1: [190, 150],
  s2: [340, 60], s3: [340, 240],
  s4: [490, 150], h2: [580, 150],
};

const charts = {};
let topologyBuilt = false;

// Line charts keep the last MAX_POINTS readings (about 30 seconds of history).
const MAX_POINTS = 30;
// Path A links are blue, path B links are purple.
const LINK_COLOR = {
  "s1-s2": "#1b5fd6", "s2-s4": "#7aa5ee",
  "s1-s3": "#8a4fbf", "s3-s4": "#c79be3",
};
const CHART_DEFS = [
  { key: "latency", canvas: "latency-chart", field: "latency_ms", unit: "ms" },
  { key: "loss", canvas: "loss-chart", field: "loss_pct", unit: "%" },
  { key: "throughput", canvas: "throughput-chart", field: "throughput_mbps", unit: "Mbps" },
];
let lastSnapshotTime = null;

// Event log settings
const MAX_EVENTS = 50;          // show at most the latest 50 events
const HIGHLIGHT_MS = 4000;      // how long a new event stays highlighted
let allEvents = [];
let eventFilter = "all";
let eventSignature = null;
const seenEventKeys = new Set();
const freshEventKeys = new Set();

// ---------- helpers that survive missing or broken values ----------
// A failed link may report null for latency, so never call .toFixed on raw data.
function num(value, digits = 1) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "n/a";
}
function numOrNull(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

async function getJSON(name) {
  const res = await fetch(`/api/${name}`, { signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) });
  if (!res.ok) throw new Error(`${name} returned HTTP ${res.status}`);
  return res.json();
}

// ---------- main refresh ----------
async function refresh() {
  const updated = document.getElementById("updated");
  const banner = document.getElementById("connection-banner");
  try {
    const names = ["topology", "metrics", "current_route", "events"];
    // allSettled: if one endpoint fails, the other panels still update.
    const results = await Promise.allSettled(names.map(getJSON));

    const data = {};
    const failed = [];
    const reasons = [];
    results.forEach((r, i) => {
      if (r.status === "fulfilled") data[names[i]] = r.value;
      else { failed.push(names[i]); reasons.push(String(r.reason && r.reason.message)); }
    });

    if (data.topology && !topologyBuilt) { buildTopology(data.topology); topologyBuilt = true; }
    if (data.current_route) renderRoute(data.current_route);
    if (topologyBuilt && data.metrics && data.current_route) {
      renderTopology(data.metrics, data.current_route);
    }
    if (data.metrics) { renderTable(data.metrics); renderCharts(data.metrics); }
    if (Array.isArray(data.events)) renderEvents(data.events);

    if (failed.length === 0) {
      banner.hidden = true;
      updated.textContent = `Updated ${new Date().toLocaleTimeString()}`;
    } else {
      const controllerDown = reasons.some((m) => m.includes("HTTP 502"));
      if (failed.length === names.length) {
        banner.textContent = controllerDown
          ? "The controller is not responding. Showing the last data received. Retrying every second."
          : "Lost connection to the dashboard server. Showing the last data received. Retrying every second.";
      } else {
        banner.textContent = `Some data could not be loaded (${failed.join(", ")}). Retrying every second.`;
      }
      banner.hidden = false;
      if (failed.length < names.length) updated.textContent = `Updated ${new Date().toLocaleTimeString()}`;
    }
  } catch (err) {
    // Last line of defence: a bug here must not stop the refresh loop.
    banner.textContent = `Display error: ${err.message}`;
    banner.hidden = false;
  }
}

// ---------- header: mode, path name, cost ----------
function renderRoute(route) {
  const mode = document.getElementById("mode");
  mode.textContent = route.mode ?? "-";
  mode.className = "pill " + (route.mode ?? "");
  document.getElementById("path-name").textContent = route.path_name ?? "-";
  document.getElementById("path-cost").textContent = route.cost ?? "-";
  document.getElementById("path-text").textContent = (route.path || []).join(" > ");
}

// ---------- topology drawing ----------
function svgEl(tag, attrs) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

function buildTopology(topology) {
  const svg = document.getElementById("topology");
  svg.replaceChildren();

  // Links first so nodes are drawn on top of them.
  for (const link of topology.links) {
    const [a, b] = link.id.split("-");
    if (!NODE_POS[a] || !NODE_POS[b]) continue;   // unknown node name, skip it
    const [x1, y1] = NODE_POS[a];
    const [x2, y2] = NODE_POS[b];
    const coords = { x1, y1, x2, y2 };
    svg.appendChild(svgEl("line", { ...coords, class: "halo", "data-halo": link.id }));
    svg.appendChild(svgEl("line", { ...coords, class: "link", "data-link": link.id }));
  }

  for (const node of topology.nodes) {
    if (!NODE_POS[node.id]) continue;
    const [x, y] = NODE_POS[node.id];
    const kind = node.type === "host" ? "host" : "switch";
    svg.appendChild(svgEl("circle", { cx: x, cy: y, r: 20, class: `node ${kind}` }));
    const label = svgEl("text", { x, y: y + 5, class: `node-label ${kind}` });
    label.textContent = node.id;
    svg.appendChild(label);
  }
}

// Turn ["h1","s1","s3"] into the set of link ids {"h1-s1","s1-s3"}
function activeLinkIds(path, knownIds) {
  const active = new Set();
  for (let i = 0; i < path.length - 1; i++) {
    const forward = `${path[i]}-${path[i + 1]}`;
    const backward = `${path[i + 1]}-${path[i]}`;
    if (knownIds.has(forward)) active.add(forward);
    else if (knownIds.has(backward)) active.add(backward);
  }
  return active;
}

function renderTopology(metrics, route) {
  const status = {};
  for (const l of metrics.links || []) status[l.link] = l.status;

  const lines = document.querySelectorAll("#topology line[data-link]");
  const known = new Set([...lines].map((el) => el.dataset.link));
  const active = activeLinkIds(route.path || [], known);

  lines.forEach((el) => {
    const id = el.dataset.link;
    const classes = ["link"];
    if (status[id]) classes.push(status[id]);
    if (active.has(id)) classes.push("active");
    el.setAttribute("class", classes.join(" "));
  });
  document.querySelectorAll("#topology line[data-halo]").forEach((el) => {
    el.setAttribute("class", active.has(el.dataset.halo) ? "halo active" : "halo");
  });
}

// ---------- link metrics table ----------
function cell(text, className) {
  const td = document.createElement("td");
  td.textContent = text;
  if (className) td.className = className;
  return td;
}

function renderTable(metrics) {
  const body = document.getElementById("link-rows");
  body.replaceChildren();
  for (const l of metrics.links || []) {
    const tr = document.createElement("tr");
    tr.appendChild(cell(l.link));

    const statusTd = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = `badge ${l.status}`;
    badge.textContent = l.status ?? "unknown";
    statusTd.appendChild(badge);
    tr.appendChild(statusTd);

    tr.appendChild(cell(num(l.latency_ms)));
    tr.appendChild(cell(num(l.loss_pct)));
    tr.appendChild(cell(typeof l.util === "number" ? `${Math.round(l.util * 100)}%` : "n/a"));
    tr.appendChild(cell(num(l.throughput_mbps)));
    body.appendChild(tr);
  }
}

// ---------- live line charts ----------
function createLineChart(def, linkIds) {
  const chart = new Chart(document.getElementById(def.canvas), {
    type: "line",
    data: {
      labels: [],
      datasets: linkIds.map((id) => ({
        label: id,
        data: [],
        borderColor: LINK_COLOR[id] || "#9aa9ae",
        backgroundColor: LINK_COLOR[id] || "#9aa9ae",
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.25,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "bottom", labels: { usePointStyle: true } } },
      scales: {
        y: { beginAtZero: true, title: { display: true, text: def.unit } },
        x: { ticks: { maxTicksLimit: 6 } },
      },
    },
  });
  charts[def.key] = chart;
  return chart;
}

function renderCharts(metrics) {
  // The page polls every second, but the monitor may publish less often.
  // Only add a point when the snapshot is new.
  if (metrics.timestamp === lastSnapshotTime) return;
  lastSnapshotTime = metrics.timestamp;

  const links = metrics.links || [];
  const label = new Date(metrics.timestamp).toLocaleTimeString();
  const byLink = {};
  for (const l of links) byLink[l.link] = l;

  for (const def of CHART_DEFS) {
    const chart = charts[def.key] || createLineChart(def, links.map((l) => l.link));
    chart.data.labels.push(label);
    for (const ds of chart.data.datasets) {
      const l = byLink[ds.label];
      ds.data.push(l ? numOrNull(l[def.field]) : null);   // null leaves a gap in the line
    }
    if (chart.data.labels.length > MAX_POINTS) {
      chart.data.labels.shift();
      chart.data.datasets.forEach((ds) => ds.data.shift());
    }
    chart.update("none");
  }
}

// ---------- event log ----------
function eventKey(e) {
  return e.id ?? `${e.timestamp}-${e.type}`;
}

function renderEvents(events) {
  // Only redraw when the list of events actually changed, so the highlight
  // animation on a new event is not restarted every second.
  const signature = events.map(eventKey).join(",");
  if (signature === eventSignature) return;

  const firstLoad = eventSignature === null;
  eventSignature = signature;

  for (const e of events) {
    const key = eventKey(e);
    if (!seenEventKeys.has(key)) {
      seenEventKeys.add(key);
      if (!firstLoad) {                       // do not highlight the history on page load
        freshEventKeys.add(key);
        setTimeout(() => freshEventKeys.delete(key), HIGHLIGHT_MS);
      }
    }
  }
  allEvents = events;
  drawEvents();
}

function drawEvents() {
  const list = document.getElementById("event-list");
  const count = document.getElementById("event-count");
  list.replaceChildren();

  const matching = eventFilter === "all"
    ? allEvents
    : allEvents.filter((e) => e.type === eventFilter);
  // The contract says newest is last: keep the last MAX_EVENTS, show newest first.
  const shown = matching.slice(-MAX_EVENTS).reverse();

  count.textContent = matching.length > shown.length
    ? `Showing the latest ${shown.length} of ${matching.length} events`
    : `Showing ${shown.length} of ${allEvents.length} events`;

  if (shown.length === 0) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = allEvents.length === 0
      ? "No events yet. Events appear when the route changes or a link degrades."
      : "No events of this type.";
    list.appendChild(li);
    return;
  }

  for (const e of shown) {
    const li = document.createElement("li");
    if (freshEventKeys.has(eventKey(e))) li.className = "new";

    const time = document.createElement("span");
    time.className = "time";
    time.textContent = new Date(e.timestamp).toLocaleTimeString();

    const type = document.createElement("span");
    type.className = `type ${e.type}`;
    type.textContent = String(e.type).replaceAll("_", " ");

    const text = document.createElement("span");
    const move = e.type === "route_change" ? `Path ${e.from_path ?? "none"} to ${e.to_path}: ` : "";
    text.textContent = move + (e.reason ?? "");

    li.append(time, type, text);
    list.appendChild(li);
  }
}

document.querySelectorAll(".filters button").forEach((btn) => {
  btn.addEventListener("click", () => {
    eventFilter = btn.dataset.filter;
    document.querySelectorAll(".filters button").forEach((b) => {
      b.setAttribute("aria-pressed", String(b === btn));
    });
    drawEvents();
  });
});

// Wait for one refresh to finish before scheduling the next, so slow
// responses never pile up on top of each other.
async function loop() {
  await refresh();
  setTimeout(loop, POLL_MS);
}
loop();