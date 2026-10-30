const $ = (id) => document.getElementById(id);
let selectedScenario = "normal";
const canvas = $("traffic-chart");
const context = canvas.getContext("2d");
const particleContainer = $("traffic-particles");
const particleCount = 18;

for (let index = 0; index < particleCount; index += 1) {
  const particle = document.createElement("i");
  particle.className = "particle";
  particle.style.setProperty("--particle-delay", `${(index * 0.37).toFixed(2)}s`);
  particleContainer.appendChild(particle);
}

function resizeCanvas() {
  const scale = window.devicePixelRatio || 1;
  const box = canvas.getBoundingClientRect();
  canvas.width = box.width * scale;
  canvas.height = box.height * scale;
  context.setTransform(scale, 0, 0, scale, 0, 0);
}

function drawChart(history) {
  const box = canvas.getBoundingClientRect();
  const width = box.width;
  const height = box.height;
  context.clearRect(0, 0, width, height);
  const pad = { top: 18, right: 12, bottom: 28, left: 30 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const max = Math.max(10, ...history.flatMap((item) => [item.before, item.after])) * 1.15;
  context.font = "10px Inter, sans-serif";
  context.fillStyle = "#526783";
  context.strokeStyle = "#1d2c43";
  context.lineWidth = 1;
  for (let step = 0; step <= 4; step += 1) {
    const y = pad.top + (plotHeight * step) / 4;
    context.beginPath();
    context.moveTo(pad.left, y);
    context.lineTo(width - pad.right, y);
    context.stroke();
    context.fillText(`${Math.round(max - (max * step) / 4)}`, 2, y + 3);
  }
  if (!history.length) return;
  const drawLine = (key, color) => {
    context.beginPath();
    history.forEach((item, index) => {
      const x = pad.left + (plotWidth * index) / Math.max(1, history.length - 1);
      const y = pad.top + plotHeight - (item[key] / max) * plotHeight;
      if (index === 0) context.moveTo(x, y); else context.lineTo(x, y);
    });
    context.strokeStyle = color;
    context.lineWidth = 2;
    context.stroke();
  };
  drawLine("before", "#ff5d83");
  drawLine("after", "#42e5a5");
}

function renderFeed(reasons) {
  if (!reasons.length) {
    $("reasons").innerHTML = '<div class="feed-empty"><span>◌</span><p>Awaiting signal input</p><small>Start a simulation to inspect synthetic events</small></div>';
    return;
  }
  $("reasons").innerHTML = reasons.slice().reverse().map((reason, index) => {
    const threat = !reason.includes("within configured");
    return `<div class="feed-item"><i style="background:${threat ? "var(--pink)" : "var(--green)"};box-shadow:0 0 8px ${threat ? "var(--pink)" : "var(--green)"}"></i><div>${reason}<span>EVENT ${String(reasons.length - index).padStart(3, "0")} · ${threat ? "SIGNAL FLAGGED" : "PASSED"}</span></div></div>`;
  }).join("");
}

function render(data) {
  $("total").textContent = data.total;
  $("suspicious").textContent = data.suspicious;
  $("blocked").textContent = data.blocked;
  $("accepted").textContent = data.allowed_after_mitigation;
  $("before").textContent = data.before_load;
  $("after").textContent = data.after_load;
  $("capacity").textContent = data.capacity;
  $("elapsed").textContent = data.elapsed.toFixed(1);
  $("availability").innerHTML = `${data.availability.toFixed(1)}<span>%</span>`;
  $("threat-percent").textContent = `${data.total ? Math.round((data.suspicious / data.total) * 100) : 0}%`;
  $("preserved").textContent = `${data.availability.toFixed(0)}%`;
  $("preserved-bar").style.width = `${data.availability}%`;
  $("latency").textContent = Math.max(18, Math.round(18 + data.after_load * 1.7));
  $("system-cpu").textContent = `${data.system.cpu_percent.toFixed(1)}%`;
  $("system-memory").textContent = `${data.system.memory_percent.toFixed(1)}%`;
  $("status").textContent = data.status.toUpperCase();
  $("status").className = `status-badge ${data.status}`;
  $("run-state").textContent = data.running ? "RUNNING" : (data.total ? "PAUSED / COMPLETE" : "READY");
  $("core-status").textContent = data.running ? "PROCESSING" : data.status === "critical" ? "ALERT" : "STANDBY";
  const intensity = Math.min(1, Math.max(data.before_load / Math.max(data.capacity, 1), data.system.cpu_percent / 100));
  document.querySelector(".scene").style.setProperty("--traffic-intensity", intensity.toFixed(2));
  document.querySelector(".core").style.setProperty("--core-load", `${Math.round(intensity * 100)}%`);
  document.querySelectorAll(".node").forEach((node, index) => {
    const active = data.running || (data.total > 0 && (data.total + index) % 3 !== 0);
    node.classList.toggle("active", active);
    node.style.setProperty("--node-delay", `${index * 0.25}s`);
  });
  $("health-label").textContent = data.status === "critical" ? "AT RISK" : data.status === "warning" ? "ELEVATED" : "HEALTHY";
  $("chart-empty").style.display = data.history.length ? "none" : "block";
  drawChart(data.history);
  renderFeed(data.reasons);
}

async function post(path, body = {}) {
  const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Simulation request failed");
  render(payload);
}

async function refresh() {
  const response = await fetch("/api/state");
  render(await response.json());
}

document.querySelectorAll(".scenario-option").forEach((button) => {
  button.addEventListener("click", () => {
    selectedScenario = button.dataset.scenario;
    document.querySelectorAll(".scenario-option").forEach((item) => item.classList.toggle("active", item === button));
  });
});
$("start").addEventListener("click", () => post("/api/start", { scenario: selectedScenario }).catch((error) => alert(error.message)));
$("pause").addEventListener("click", () => post("/api/pause").catch((error) => alert(error.message)));
$("reset").addEventListener("click", () => post("/api/reset").catch((error) => alert(error.message)));
window.addEventListener("resize", () => { resizeCanvas(); refresh(); });
setInterval(() => { $("clock").textContent = new Date().toLocaleTimeString([], { hour12: false }); }, 1000);
setInterval(() => refresh().catch(() => {}), 250);
resizeCanvas();
refresh().catch(() => {});
