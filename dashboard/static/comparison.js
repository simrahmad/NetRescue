// Baseline vs adaptive comparison page.
// Asks Flask for /api/results (already averaged per scenario and mode) and draws it.

const SCENARIO_ORDER = ["delay", "loss", "bandwidth", "link_fail"];
const MODE_ORDER = ["baseline", "adaptive"];
const MODE_COLOR = { baseline: "#6b7c85", adaptive: "#1b5fd6" };

const METRICS = [
  { key: "recovery_time_s", canvas: "recovery-chart", unit: "s" },
  { key: "packets_lost", canvas: "lost-chart", unit: "packets" },
  { key: "avg_latency_ms", canvas: "latency-chart", unit: "ms" },
  { key: "throughput_mbps", canvas: "throughput-chart", unit: "Mbps" },
];

const charts = {};

function sortScenarios(list) {
  const rank = (s) => {
    const i = SCENARIO_ORDER.indexOf(s);
    return i === -1 ? SCENARIO_ORDER.length : i;
  };
  return list.slice().sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
}

function findEntry(summary, scenario, mode) {
  return summary.find((e) => e.scenario === scenario && e.mode === mode);
}

function drawChart(metric, scenarios, summary) {
  if (charts[metric.key]) charts[metric.key].destroy();

  const datasets = MODE_ORDER.map((mode) => {
    const entries = scenarios.map((s) => findEntry(summary, s, mode));
    return {
      label: mode,
      data: entries.map((e) => (e ? e[metric.key].mean : null)),
      sd: entries.map((e) => (e ? e[metric.key].sd : null)),
      backgroundColor: MODE_COLOR[mode],
    };
  });

  charts[metric.key] = new Chart(document.getElementById(metric.canvas), {
    type: "bar",
    data: { labels: scenarios, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: { position: "bottom" },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const sd = ctx.dataset.sd[ctx.dataIndex];
              const value = ctx.parsed.y;
              const spread = sd === null ? "" : ` ± ${sd.toFixed(1)}`;
              return `${ctx.dataset.label}: ${value}${spread} ${metric.unit}`;
            },
          },
        },
      },
      scales: { y: { beginAtZero: true, title: { display: true, text: metric.unit } } },
    },
  });
}

function fmt(stat) {
  if (!stat || stat.mean === null) return "n/a";
  return `${stat.mean.toFixed(1)} ± ${stat.sd.toFixed(1)}`;
}

function cell(text, className) {
  const td = document.createElement("td");
  td.textContent = text;
  if (className) td.className = className;
  return td;
}

function drawTable(scenarios, summary) {
  const body = document.getElementById("result-rows");
  body.replaceChildren();
  for (const scenario of scenarios) {
    for (const mode of MODE_ORDER) {
      const e = findEntry(summary, scenario, mode);
      if (!e) continue;
      const tr = document.createElement("tr");
      tr.append(
        cell(scenario), cell(mode, `mode-${mode}`), cell(String(e.n)),
        cell(fmt(e.recovery_time_s)), cell(fmt(e.packets_lost)),
        cell(fmt(e.avg_latency_ms)), cell(fmt(e.throughput_mbps)),
        cell(fmt(e.route_changes)),
      );
      body.appendChild(tr);
    }
  }
}

async function load() {
  const status = document.getElementById("status");
  try {
    const res = await fetch("/api/results");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    document.getElementById("sample-banner").hidden = !data.sample;

    if (data.summary.length === 0) {
      status.textContent = "No results found in the CSV files yet.";
      return;
    }
    const scenarios = sortScenarios([...new Set(data.summary.map((e) => e.scenario))]);
    METRICS.forEach((m) => drawChart(m, scenarios, data.summary));
    drawTable(scenarios, data.summary);
    status.textContent = `Loaded ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    status.textContent = `Cannot load results: ${err.message}`;
  }
}

document.getElementById("reload").addEventListener("click", load);
load();