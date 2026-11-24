// NetRescue dashboard front end.
// Every second: ask our Flask server for the 4 data sets, then redraw the page.

const POLL_MS = 1000;
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

async function getJSON(name) {
  const res = await fetch(`/api/${name}`);
  if (!res.ok) throw new Error(`${name} returned HTTP ${res.status}`);
  return res.json();
}

async function refresh() {
  const updated = document.getElementById("updated");
  try {
    const [topology, metrics, route, events] = await Promise.all([
      getJSON("topology"), getJSON("metrics"),
      getJSON("current_route"), getJSON("events"),
    ]);

    if (!topologyBuilt) { buildTopology(topology); topologyBuilt = true; }
    renderRoute(route);
    renderTopology(metrics, route);
    renderTable(metrics);
    renderCharts(metrics);
    renderEvents(events);
    updated.textContent = `Updated ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    updated.textContent = `Cannot load data: ${err.message}. Is the controller running?`;
  }
}

// ---------- header: mode, path name, cost ----------
function renderRoute(route) {
  const mode = document.getElementById("mode");
  mode.textContent = route.mode;
  mode.className = "pill " + route.mode;
  document.getElementById("path-name").textContent = route.path_name;
  document.getElementById("path-cost").textContent = route.cost;
  document.getElementById("path-text").textContent = route.path.join(" > ");
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
    const [x1, y1] = NODE_POS[a];
    const [x2, y2] = NODE_POS[b];
    const coords = { x1, y1, x2, y2 };
    svg.appendChild(svgEl("line", { ...coords, class: "halo", "data-halo": link.id }));
    svg.appendChild(svgEl("line", { ...coords, class: "link", "data-link": link.id }));
  }

  for (const node of topology.nodes) {
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
  for (const l of metrics.links) status[l.link] = l.status;

  const lines = document.querySelectorAll("#topology line[data-link]");
  const known = new Set([...lines].map((el) => el.dataset.link));
  const active = activeLinkIds(route.path, known);

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
  for (const l of metrics.links) {
    const tr = document.createElement("tr");
    tr.appendChild(cell(l.link));

    const statusTd = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = `badge ${l.status}`;
    badge.textContent = l.status;
    statusTd.appendChild(badge);
    tr.appendChild(statusTd);

    tr.appendChild(cell(l.latency_ms.toFixed(1)));
    tr.appendChild(cell(l.loss_pct.toFixed(1)));
    tr.appendChild(cell(`${Math.round(l.util * 100)}%`));
    tr.appendChild(cell(l.throughput_mbps.toFixed(1)));
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

  const label = new Date(metrics.timestamp).toLocaleTimeString();
  const byLink = {};
  for (const l of metrics.links) byLink[l.link] = l;

  for (const def of CHART_DEFS) {
    const chart = charts[def.key] || createLineChart(def, metrics.links.map((l) => l.link));
    chart.data.labels.push(label);
    for (const ds of chart.data.datasets) {
      const l = byLink[ds.label];
      ds.data.push(l ? l[def.field] : null);   // null leaves a gap if a link is missing
    }
    if (chart.data.labels.length > MAX_POINTS) {
      chart.data.labels.shift();
      chart.data.datasets.forEach((ds) => ds.data.shift());
    }
    chart.update("none");
  }
}

// ---------- event log ----------
function renderEvents(events) {
  const list = document.getElementById("event-list");
  list.replaceChildren();

  if (events.length === 0) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = "No events yet. Events appear when the route changes or a link degrades.";
    list.appendChild(li);
    return;
  }

  // The contract says newest is last, so reverse to show newest first.
  for (const e of events.slice().reverse()) {
    const li = document.createElement("li");

    const time = document.createElement("span");
    time.className = "time";
    time.textContent = new Date(e.timestamp).toLocaleTimeString();

    const type = document.createElement("span");
    type.className = `type ${e.type}`;
    type.textContent = e.type.replace("_", " ");

    const text = document.createElement("span");
    const move = e.type === "route_change" ? `Path ${e.from_path ?? "none"} to ${e.to_path}: ` : "";
    text.textContent = move + e.reason;

    li.append(time, type, text);
    list.appendChild(li);
  }
}

refresh();
setInterval(refresh, POLL_MS);