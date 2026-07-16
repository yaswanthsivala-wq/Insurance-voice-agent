"use strict";

/* ---------- element refs ---------- */
const els = {
  record: document.getElementById("record"),
  stop: document.getElementById("stop"),
  pick: document.getElementById("pick"),
  file: document.getElementById("file"),
  filename: document.getElementById("filename"),
  speak: document.getElementById("speak-toggle"),
  state: document.getElementById("state"),
  stateText: document.getElementById("state-text"),
  waveHint: document.getElementById("wave-hint"),
  canvas: document.getElementById("wave"),
  log: document.getElementById("log"),
  total: document.getElementById("total"),
  reviewStrip: document.getElementById("review-strip"),
  reviewItems: document.getElementById("review-items"),
  recTimer: document.getElementById("rec-timer"),
  timerText: document.getElementById("timer-text"),
  openHistory: document.getElementById("open-history"),
  closeHistory: document.getElementById("close-history"),
  clearHistory: document.getElementById("clear-history"),
  historyModal: document.getElementById("history-modal"),
  historyList: document.getElementById("history-list"),
  historySub: document.getElementById("history-sub"),
};

const HINT = "Press record and speak — it listens until you press Stop";
const LANES = { Auto: "lane-auto", Health: "lane-health", Life: "lane-life", Property: "lane-property" };
const COUNTS = { Auto: 0, Health: 0, Life: 0, Property: 0 };
let total = 0;

/* ---------- audio state ---------- */
let recorder = null, chunks = [], stream = null;
let audioCtx = null, analyser = null, rafId = null;
let timerId = null, startTime = 0;

/* ---------- status helpers ---------- */
function setState(text, mode) {
  els.stateText.textContent = text;
  els.state.className = "state" + (mode ? " " + mode : "");
}

/* ---------- recording timer ---------- */
function fmt(ms) {
  const s = Math.floor(ms / 1000);
  return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
}
function startTimer() {
  startTime = Date.now();
  els.recTimer.classList.add("show");
  els.timerText.textContent = "00:00";
  timerId = setInterval(() => {
    els.timerText.textContent = fmt(Date.now() - startTime);
  }, 250);
}
function stopTimer() {
  if (timerId) clearInterval(timerId);
  timerId = null;
  els.recTimer.classList.remove("show");
}

/* ---------- transcript log ---------- */
function clearLogEmpty() {
  const e = els.log.querySelector(".log-empty");
  if (e) e.remove();
}
function addLine(kind, tag, body, type) {
  clearLogEmpty();
  const line = document.createElement("div");
  line.className = "line " + kind;
  const t = document.createElement("span");
  t.className = "tag";
  t.textContent = tag;
  const b = document.createElement("div");
  b.className = "body";
  b.textContent = body;
  line.appendChild(t);
  line.appendChild(b);
  if (type && LANES[type]) {
    line.style.setProperty("--hue", `var(--${type.toLowerCase()})`);
    const chip = document.createElement("span");
    chip.className = "chip-type";
    chip.textContent = type;
    line.appendChild(chip);
  }
  els.log.appendChild(line);
  els.log.scrollTop = els.log.scrollHeight;
}

/* ---------- dashboard ---------- */
function timeLabel(iso) {
  const d = iso ? new Date(iso) : new Date();
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function renderIntake(intake) {
  const { summary, type, language, created_at } = intake;
  if (LANES[type]) {
    const lane = document.getElementById(LANES[type]);
    const empty = lane.querySelector(".empty");
    if (empty) empty.remove();

    const card = document.createElement("div");
    card.className = "card";
    const p = document.createElement("p");
    p.textContent = summary;
    const meta = document.createElement("div");
    meta.className = "meta";
    const lang = document.createElement("span");
    lang.className = "lang";
    lang.textContent = language || "—";
    const time = document.createElement("span");
    time.textContent = timeLabel(created_at);
    meta.appendChild(lang);
    meta.appendChild(time);
    card.appendChild(p);
    card.appendChild(meta);
    lane.prepend(card);

    COUNTS[type] += 1;
    document.getElementById("count-" + type.toLowerCase()).textContent = COUNTS[type];
  } else {
    els.reviewStrip.classList.add("show");
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = summary;
    els.reviewItems.prepend(chip);
  }
  total += 1;
  els.total.textContent = total;
}

function resetDashboard() {
  Object.keys(LANES).forEach((type) => {
    const lane = document.getElementById(LANES[type]);
    lane.innerHTML = `<div class="empty">No ${type.toLowerCase()} intakes yet</div>`;
    COUNTS[type] = 0;
    document.getElementById("count-" + type.toLowerCase()).textContent = 0;
  });
  els.reviewItems.innerHTML = "";
  els.reviewStrip.classList.remove("show");
  total = 0;
  els.total.textContent = 0;
}

/* ---------- history ---------- */
async function loadHistory(rebuildDashboard) {
  let intakes = [];
  try {
    const res = await fetch("/history");
    const data = await res.json();
    intakes = data.intakes || [];
  } catch (err) {
    return intakes;
  }
  if (rebuildDashboard) {
    resetDashboard();
    // oldest first so newest ends on top after prepend
    intakes.slice().reverse().forEach(renderIntake);
  }
  return intakes;
}

function renderHistoryModal(intakes) {
  els.historySub.textContent =
    intakes.length + (intakes.length === 1 ? " intake recorded" : " intakes recorded");
  if (!intakes.length) {
    els.historyList.innerHTML = `<div class="log-empty">No intakes recorded yet.</div>`;
    return;
  }
  els.historyList.innerHTML = "";
  intakes.forEach((it) => {
    const row = document.createElement("div");
    row.className = "hrow";
    const hue = LANES[it.type] ? `var(--${it.type.toLowerCase()})` : "var(--review)";
    row.style.setProperty("--hue", hue);

    const top = document.createElement("div");
    top.className = "hrow-top";
    const type = document.createElement("span");
    type.className = "htype";
    type.textContent = it.type;
    const meta = document.createElement("span");
    meta.className = "hmeta";
    const when = it.created_at ? new Date(it.created_at).toLocaleString() : "";
    meta.textContent = [it.language, it.source, when].filter(Boolean).join("  •  ");
    top.appendChild(type);
    top.appendChild(meta);

    const sum = document.createElement("p");
    sum.className = "hsum";
    sum.textContent = it.summary;

    row.appendChild(top);
    row.appendChild(sum);

    if (it.transcript) {
      const det = document.createElement("details");
      const sm = document.createElement("summary");
      sm.textContent = "Show full transcript";
      const tp = document.createElement("p");
      tp.textContent = it.transcript;
      det.appendChild(sm);
      det.appendChild(tp);
      row.appendChild(det);
    }
    els.historyList.appendChild(row);
  });
}

async function openHistory() {
  els.historyModal.classList.add("show");
  els.historyModal.setAttribute("aria-hidden", "false");
  renderHistoryModal(await loadHistory(false));
}
function closeHistory() {
  els.historyModal.classList.remove("show");
  els.historyModal.setAttribute("aria-hidden", "true");
}
async function clearHistory() {
  if (!confirm("Delete all recorded intakes? This cannot be undone.")) return;
  try {
    await fetch("/history", { method: "DELETE" });
  } catch (err) {}
  resetDashboard();
  renderHistoryModal([]);
}

/* ---------- speak ---------- */
function speak(text) {
  if (!els.speak.checked || !("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  speechSynthesis.cancel();
  speechSynthesis.speak(u);
}

/* ---------- waveform ---------- */
function fitCanvas() {
  const c = els.canvas;
  const dpr = window.devicePixelRatio || 1;
  c.width = c.clientWidth * dpr;
  c.height = c.clientHeight * dpr;
  c.getContext("2d").setTransform(dpr, 0, 0, dpr, 0, 0);
}
window.addEventListener("resize", fitCanvas);

function drawWave() {
  const c = els.canvas, ctx = c.getContext("2d");
  const w = c.clientWidth, h = c.clientHeight;
  const bins = new Uint8Array(analyser.frequencyBinCount);
  function frame() {
    rafId = requestAnimationFrame(frame);
    analyser.getByteFrequencyData(bins);
    ctx.clearRect(0, 0, w, h);
    const bars = 56, step = Math.floor(bins.length / bars), gap = 3;
    const bw = (w - gap * (bars - 1)) / bars, mid = h / 2;
    for (let i = 0; i < bars; i++) {
      let v = 0;
      for (let j = 0; j < step; j++) v += bins[i * step + j];
      v = v / step / 255;
      const bh = Math.max(2, v * (h * 0.9));
      const x = i * (bw + gap);
      const grad = ctx.createLinearGradient(0, mid - bh / 2, 0, mid + bh / 2);
      grad.addColorStop(0, "rgba(245,165,36,0.95)");
      grad.addColorStop(1, "rgba(245,165,36,0.35)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.roundRect(x, mid - bh / 2, bw, bh, bw / 2);
      ctx.fill();
    }
  }
  frame();
}
function stopWave() {
  if (rafId) cancelAnimationFrame(rafId);
  rafId = null;
  const c = els.canvas, ctx = c.getContext("2d");
  ctx.clearRect(0, 0, c.clientWidth, c.clientHeight);
}

/* ---------- recording (continuous until Stop) ---------- */
async function startRecording() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    setState("Mic blocked", "");
    addLine("sys", "system", "Microphone permission was denied. Allow it and try again.");
    return;
  }
  chunks = [];
  recorder = new MediaRecorder(stream);
  recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
  recorder.onstop = handleStop;
  recorder.start(1000); // flush a chunk every second so long recordings are safe

  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const src = audioCtx.createMediaStreamSource(stream);
  analyser = audioCtx.createAnalyser();
  analyser.fftSize = 512;
  src.connect(analyser);
  fitCanvas();
  drawWave();

  els.waveHint.style.display = "none";
  els.record.disabled = true;
  els.stop.disabled = false;
  els.stop.classList.add("armed");
  setState("Listening", "is-rec");
  startTimer();
}

function teardownAudio() {
  stopWave();
  stopTimer();
  if (stream) stream.getTracks().forEach((t) => t.stop());
  if (audioCtx) audioCtx.close();
  stream = null; audioCtx = null; analyser = null;
  els.stop.classList.remove("armed");
  els.stop.disabled = true;
  els.record.disabled = false;
}

function stopRecording() {
  if (recorder && recorder.state !== "inactive") recorder.stop();
}

async function handleStop() {
  teardownAudio();
  els.waveHint.textContent = HINT;
  els.waveHint.style.display = "grid";
  const blob = new Blob(chunks, { type: "audio/webm" });
  if (blob.size === 0) {
    setState("Ready", "");
    addLine("sys", "system", "No audio was captured. Try recording again.");
    return;
  }
  const form = new FormData();
  form.append("audio", blob, "recording.webm");
  await sendToServer("/transcribe", form);
}

/* ---------- upload ---------- */
els.pick.addEventListener("click", () => els.file.click());
els.file.addEventListener("change", async () => {
  const f = els.file.files[0];
  if (!f) return;
  els.filename.textContent = f.name;
  const form = new FormData();
  form.append("file", f);
  await sendToServer("/upload", form);
  els.file.value = "";
});

/* ---------- server round-trip ---------- */
async function sendToServer(url, form) {
  setState("Transcribing", "is-busy");
  try {
    const res = await fetch(url, { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok || data.error) {
      setState("Error", "");
      addLine("sys", "system", data.error || "Something went wrong. Try again.");
      return;
    }
    if (data.transcript) addLine("you", "caller", data.transcript, data.type);
    addLine("sum", "summary", data.summary, data.type);
    renderIntake(data);
    speak(data.summary);
    setState("Ready", "");
  } catch (err) {
    setState("Error", "");
    addLine("sys", "system", "Couldn't reach the server. Check your connection.");
  }
}

/* ---------- wire up ---------- */
els.record.addEventListener("click", startRecording);
els.stop.addEventListener("click", stopRecording);

// THE FOLLOWING LINES ARE COMMENTED OUT TO PREVENT ERRORS SINCE YOU REMOVED THE HTML BUTTONS[cite: 1]
// els.openHistory.addEventListener("click", openHistory);[cite: 1]
// els.closeHistory.addEventListener("click", closeHistory);[cite: 1]
// els.clearHistory.addEventListener("click", clearHistory);[cite: 1]
// els.historyModal.addEventListener("click", (e) => {[cite: 1]
//   if (e.target === els.historyModal) closeHistory();[cite: 1]
// });[cite: 1]

fitCanvas();

// THE FOLLOWING LINE IS COMMENTED OUT SO THE APP DOESN'T PULL OLD DATA ON LOAD[cite: 1]
// loadHistory(true); [cite: 1]

// polyfill roundRect for older browsers
if (!CanvasRenderingContext2D.prototype.roundRect) {
  CanvasRenderingContext2D.prototype.roundRect = function (x, y, w, h, r) {
    if (w < 2 * r) r = w / 2;
    if (h < 2 * r) r = h / 2;
    this.beginPath();
    this.moveTo(x + r, y);
    this.arcTo(x + w, y, x + w, y + h, r);
    this.arcTo(x + w, y + h, x, y + h, r);
    this.arcTo(x, y + h, x, y, r);
    this.arcTo(x, y, x + w, y, r);
    this.closePath();
    return this;
  };
}