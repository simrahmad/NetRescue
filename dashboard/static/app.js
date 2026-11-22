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

// Same colours as style.css
const STATUS_COLOR = { up: "#1f8a5b", congested: "#c77a0a", down: "#c0392b" };

const charts = {};
let topologyBuilt = false;

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

// ---------- charts ----------
function drawBarChart(key, canvasId, label, values, labels, colors) {
  if (!charts[key]) {
    charts[key] = new Chart(document.getElementById(canvasId), {
      type: "bar",
      data: { labels, datasets: [{ label, data: values, backgroundColor: colors }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } },
      },
    });
  } else {
    const chart = charts[key];
    chart.data.labels = labels;
    chart.data.datasets[0].data = values;
    chart.data.datasets[0].backgroundColor = colors;
    chart.update("none");
  }
}

function renderCharts(metrics) {
  const labels = metrics.links.map((l) => l.link);
  const colors = metrics.links.map((l) => STATUS_COLOR[l.status] || "#9aa9ae");
  drawBarChart("latency", "latency-chart", "Latency (ms)",
               metrics.links.map((l) => l.latency_ms), labels, colors);
  drawBarChart("loss", "loss-chart", "Loss (%)",
               metrics.links.map((l) => l.loss_pct), labels, colors);
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