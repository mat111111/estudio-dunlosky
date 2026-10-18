/* Estudio Dunlosky — Pomodoro (temporizador, sonidos y mensajes)
   Se carga antes que app.js; usa sus utilidades ($, api, esc, toast…) en tiempo de ejecución. */
"use strict";

// Frases de Albert Einstein con su origen documentado (se evitaron las que circulan
// atribuidas a él sin fuente confiable).
const EINSTEIN = [
  { q: "La imaginación es más importante que el conocimiento. El conocimiento es limitado; la imaginación abarca el mundo entero.", src: "Entrevista con George S. Viereck, 1929" },
  { q: "Lo importante es no dejar de hacerse preguntas. La curiosidad tiene su propia razón de existir.", src: "Entrevista en la revista LIFE, 1955" },
  { q: "La vida es como andar en bicicleta: para mantener el equilibrio hay que seguir avanzando.", src: "Carta a su hijo Eduard, 1930" },
  { q: "No tengo talentos especiales. Solo soy apasionadamente curioso.", src: "Carta a Carl Seelig, 1952" },
  { q: "No intentes convertirte en una persona de éxito, sino en una persona de valor.", src: "Entrevista en la revista LIFE, 1955" },
  { q: "Lo más hermoso que podemos experimentar es lo misterioso. Es la fuente de todo arte y de toda ciencia verdaderos.", src: "Mi visión del mundo, 1931" },
  { q: "El valor de la educación no está en aprender muchos datos, sino en entrenar la mente para pensar.", src: "Citado por Philipp Frank en su biografía de Einstein, 1947" },
  { q: "Es casi un milagro que los métodos modernos de enseñanza no hayan ahogado todavía la sagrada curiosidad por investigar.", src: "Notas autobiográficas, 1949" },
  { q: "Todo debería hacerse tan simple como sea posible, pero no más simple.", src: "Paráfrasis de su conferencia en Oxford, 1933" },
];
const CHEERS = [
  "Un bloque más de concentración en tu cuenta.",
  "Tu cerebro está consolidando lo que estudiaste: el descanso también es parte del aprendizaje.",
  "La constancia le gana al talento cuando el talento no es constante.",
  "Cada pomodoro es una prueba de que podés sostener la atención.",
  "Paso a paso se llega lejos: ya diste uno más.",
];

const POMO_MODES = {
  focus: { label: "Concentración", short: "Foco" },
  short: { label: "Descanso corto", short: "Pausa" },
  long: { label: "Descanso largo", short: "Pausa larga" },
};
const ALARMS = { campana: "Campana", marimba: "Marimba", digital: "Digital", cuenco: "Cuenco tibetano", gong: "Gong", ninguna: "Sin sonido" };
const AMBIENTS = { ninguno: "Ninguno", lluvia: "Lluvia suave (ruido marrón)", rosa: "Ruido rosa", blanco: "Ruido blanco", tictac: "Tic-tac de reloj" };

const POMO_DEFAULTS = {
  focus: 25, short: 5, long: 15, every: 4, autoBreak: true, autoFocus: false,
  alarm: "campana", ambient: "ninguno", volume: 0.6, ambientVolume: 0.35, notify: false,
};

const POMO = {
  cfg: { ...POMO_DEFAULTS },
  st: { mode: "focus", running: false, endsAt: null, remaining: 25 * 60, cycle: 0, taskId: null, taskTitle: null },
  timer: null,
  listeners: new Set(),
};

function pomoLoad() {
  try {
    POMO.cfg = { ...POMO_DEFAULTS, ...(JSON.parse(localStorage.getItem("pomo_cfg")) || {}) };
    const st = JSON.parse(localStorage.getItem("pomo_state"));
    if (st) POMO.st = { ...POMO.st, ...st };
  } catch (e) { /* sin almacenamiento */ }
  // estado viejo trabado (por ejemplo, en 00:01 por el error anterior): se vuelve al inicio del modo
  if (!POMO.st.running && (POMO.st.remaining == null || POMO.st.remaining < 1)) POMO.st.remaining = pomoDuration();
}
function pomoSave() {
  try {
    localStorage.setItem("pomo_cfg", JSON.stringify(POMO.cfg));
    localStorage.setItem("pomo_state", JSON.stringify(POMO.st));
  } catch (e) { /* sin almacenamiento */ }
}
function pomoDuration(mode = POMO.st.mode) { return Math.round(POMO.cfg[mode] * 60); }
function pomoRemaining() {
  if (POMO.st.running && POMO.st.endsAt) return Math.max(0, (POMO.st.endsAt - Date.now()) / 1000);
  return POMO.st.remaining;
}
function fmtClock(sec) {
  sec = Math.ceil(sec);
  return `${String(Math.floor(sec / 60)).padStart(2, "0")}:${String(sec % 60).padStart(2, "0")}`;
}

// ------------------------------------------------------------------------- //
// Sonido (todo sintetizado con Web Audio, sin archivos externos)
// ------------------------------------------------------------------------- //
let actx = null;
let ambientNode = null;
function audio() {
  if (!actx) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    actx = new Ctx();
  }
  if (actx.state === "suspended") actx.resume();
  return actx;
}
function tone(ctx, { freq, type = "sine", start = 0, dur = 1, gain = 0.3, attack = 0.005 }) {
  const t0 = ctx.currentTime + start;
  const osc = ctx.createOscillator();
  const g = ctx.createGain();
  osc.type = type;
  osc.frequency.value = freq;
  g.gain.setValueAtTime(0.0001, t0);
  g.gain.exponentialRampToValueAtTime(Math.max(gain * POMO.cfg.volume, 0.0002), t0 + attack);
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  osc.connect(g).connect(ctx.destination);
  osc.start(t0);
  osc.stop(t0 + dur + 0.05);
}
function playAlarm(name = POMO.cfg.alarm, repeat = 2) {
  const ctx = audio();
  if (!ctx || name === "ninguna") return;
  for (let r = 0; r < repeat; r++) {
    const o = r * ({ campana: 2.2, marimba: 1.4, digital: 1.1, cuenco: 3.5, gong: 3.5 }[name] || 2);
    if (name === "campana") {
      [[1, 0.32, 2.4], [2.76, 0.12, 1.6], [5.4, 0.06, 1.0], [8.93, 0.03, 0.6]].forEach(([m, g, d]) =>
        tone(ctx, { freq: 660 * m, gain: g, dur: d, start: o }));
    } else if (name === "marimba") {
      [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => tone(ctx, { freq: f, type: "triangle", gain: 0.3, dur: 0.7, start: o + i * 0.16 }));
    } else if (name === "digital") {
      for (let i = 0; i < 3; i++) {
        tone(ctx, { freq: 1046, type: "square", gain: 0.08, dur: 0.09, start: o + i * 0.3 });
        tone(ctx, { freq: 1046, type: "square", gain: 0.08, dur: 0.09, start: o + i * 0.3 + 0.12 });
      }
    } else if (name === "cuenco") {
      tone(ctx, { freq: 220, gain: 0.3, dur: 4.5, start: o, attack: 0.03 });
      tone(ctx, { freq: 222.5, gain: 0.2, dur: 4.5, start: o, attack: 0.03 });
      tone(ctx, { freq: 660.8, gain: 0.06, dur: 3, start: o, attack: 0.03 });
    } else if (name === "gong") {
      [[1, 0.35, 4], [1.47, 0.15, 3.2], [2.09, 0.1, 2.5], [2.9, 0.05, 1.8]].forEach(([m, g, d]) =>
        tone(ctx, { freq: 98 * m, gain: g, dur: d, start: o, attack: 0.02 }));
    }
  }
}
function noiseBuffer(ctx, kind) {
  const len = ctx.sampleRate * (kind === "tictac" ? 2 : 4);
  const buf = ctx.createBuffer(1, len, ctx.sampleRate);
  const d = buf.getChannelData(0);
  if (kind === "tictac") {
    for (const at of [0, 1]) {
      const i0 = Math.floor(at * ctx.sampleRate);
      const f = at === 0 ? 2400 : 1800;
      for (let i = 0; i < 900; i++) d[i0 + i] = Math.sin((2 * Math.PI * f * i) / ctx.sampleRate) * Math.exp(-i / 140) * 0.9;
    }
    return buf;
  }
  let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0, last = 0;
  for (let i = 0; i < len; i++) {
    const w = Math.random() * 2 - 1;
    if (kind === "blanco") d[i] = w * 0.5;
    else if (kind === "rosa") {
      b0 = 0.99886 * b0 + w * 0.0555179; b1 = 0.99332 * b1 + w * 0.0750759; b2 = 0.969 * b2 + w * 0.153852;
      b3 = 0.8665 * b3 + w * 0.3104856; b4 = 0.55 * b4 + w * 0.5329522; b5 = -0.7616 * b5 - w * 0.016898;
      d[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362) * 0.11; b6 = w * 0.115926;
    } else { // lluvia: ruido marrón
      last = (last + 0.02 * w) / 1.02;
      d[i] = last * 3.5;
    }
  }
  return buf;
}
function ambientStart(kind = POMO.cfg.ambient) {
  ambientStop();
  if (kind === "ninguno") return;
  const ctx = audio();
  if (!ctx) return;
  const src = ctx.createBufferSource();
  src.buffer = noiseBuffer(ctx, kind);
  src.loop = true;
  const g = ctx.createGain();
  g.gain.value = POMO.cfg.ambientVolume;
  src.connect(g).connect(ctx.destination);
  src.start();
  ambientNode = { src, g };
}
function ambientStop() {
  if (ambientNode) {
    try { ambientNode.src.stop(); } catch (e) { /* ya detenido */ }
    ambientNode = null;
  }
}
function ambientVolume(v) { if (ambientNode) ambientNode.g.gain.value = v; }

// ------------------------------------------------------------------------- //
// Motor del temporizador
// ------------------------------------------------------------------------- //
function pomoEmit() { POMO.listeners.forEach(fn => { try { fn(); } catch (e) { /* vista cerrada */ } }); pomoBadge(); }
function pomoStart() {
  audio();
  const rem = pomoRemaining() || pomoDuration();
  POMO.st.running = true;
  POMO.st.endsAt = Date.now() + rem * 1000;
  if (POMO.st.mode === "focus") ambientStart(); else ambientStop();
  pomoSave(); pomoEmit();
}
function pomoPause() {
  POMO.st.remaining = pomoRemaining();
  POMO.st.running = false;
  POMO.st.endsAt = null;
  ambientStop();
  pomoSave(); pomoEmit();
}
function pomoReset(mode = POMO.st.mode) {
  POMO.st.mode = mode;
  POMO.st.running = false;
  POMO.st.endsAt = null;
  POMO.st.remaining = pomoDuration(mode);
  ambientStop();
  pomoSave(); pomoEmit();
}
function pomoNextMode() {
  if (POMO.st.mode === "focus") return POMO.st.cycle % POMO.cfg.every === 0 ? "long" : "short";
  return "focus";
}
function pomoComplete(skipped = false) {
  // Todo el cambio de estado es inmediato. Antes se esperaba a que el servidor registrara el
  // pomodoro y, si tardaba (por ejemplo, Render despertando), el reloj quedaba clavado en 00:01.
  const finished = POMO.st.mode;
  const minutes = POMO.cfg.focus;
  const taskId = POMO.st.taskId;
  ambientStop();
  if (!skipped) playAlarm();
  if (finished === "focus" && !skipped) POMO.st.cycle += 1;
  const next = pomoNextMode();
  pomoReset(next);
  const auto = !skipped && (next === "focus" ? POMO.cfg.autoFocus : POMO.cfg.autoBreak);
  if (auto) pomoStart();
  if (skipped) return;
  pomoNotify(finished, next);
  pomoCelebrate(finished, next, null, auto);
  if (finished === "focus") pomoRegister(minutes, taskId);
}
async function pomoRegister(minutes, taskId) {
  let stats = null;
  try { stats = await api("/api/pomodoros", { method: "POST", body: { minutes, task_id: taskId } }); }
  catch (e) { return; /* sin conexión: no se registra */ }
  if (!stats) return;
  const txt = `Hoy: ${plural(stats.today, "pomodoro", "pomodoros")}, ${plural(stats.minutes_today, "minuto", "minutos")} de concentración.`;
  const el = document.getElementById("p-today");
  if (el) el.textContent = txt;
  const extra = document.querySelector("#pomo-dialog [data-stats]");
  if (extra) extra.textContent = ` Hoy llevás ${plural(stats.today, "pomodoro", "pomodoros")} (${plural(stats.minutes_today, "minuto", "minutos")}).`;
}
function pomoTick() {
  if (POMO.st.running && pomoRemaining() <= 0) { pomoComplete(); return; }
  if (POMO.st.running) pomoEmit();
}
function pomoBadge() {
  const b = document.getElementById("nav-pomo");
  if (!b) return;
  const active = POMO.st.running || POMO.st.remaining < pomoDuration();
  b.hidden = !active;
  b.textContent = fmtClock(pomoRemaining());
  b.classList.toggle("paused", !POMO.st.running);
  b.classList.toggle("break", POMO.st.mode !== "focus");
  if (POMO.st.running) {
    const base = document.title.replace(/^\(\d\d:\d\d\) /, "");
    document.title = `(${fmtClock(pomoRemaining())}) ${base}`;
  } else {
    document.title = document.title.replace(/^\(\d\d:\d\d\) /, "");
  }
}
function pomoNotify(finished, next) {
  if (!POMO.cfg.notify || !("Notification" in window) || Notification.permission !== "granted" || !document.hidden) return;
  const body = finished === "focus" ? "¡Seguí así, lo estás logrando! Tomate un descanso." : "Descanso terminado: a concentrarse.";
  try { new Notification(finished === "focus" ? "Pomodoro completo" : "Fin del descanso", { body }); } catch (e) { /* bloqueado */ }
}
function pomoCelebrate(finished, next, stats, autoStarted) {
  const dlg = document.getElementById("pomo-dialog");
  if (!dlg) return;
  const quote = EINSTEIN[Math.floor(Math.random() * EINSTEIN.length)];
  const cheer = CHEERS[Math.floor(Math.random() * CHEERS.length)];
  const nextLabel = POMO_MODES[next].label.toLowerCase();
  if (finished === "focus") {
    dlg.innerHTML = `
      <div class="pomo-done">
        <p class="pomo-cheer">¡Seguí así, lo estás logrando!</p>
        <p class="muted">${esc(cheer)}<span data-stats></span></p>
        <blockquote class="quote"><p>${esc(quote.q)}</p><footer>Albert Einstein, ${esc(quote.src)}</footer></blockquote>
        <div class="actions">
          ${autoStarted ? `<button class="btn primary" data-close>Ya empezó tu ${esc(nextLabel)}</button>`
            : `<button class="btn primary" data-start>Empezar ${esc(nextLabel)}</button><button class="btn" data-close>Ahora no</button>`}
        </div>
      </div>`;
  } else {
    dlg.innerHTML = `
      <div class="pomo-done">
        <p class="pomo-cheer">Descanso terminado</p>
        <p class="muted">Volvé con la mente fresca. Si podés, empezá respondiendo preguntas: recuperar lo estudiado es lo que más fija.</p>
        <div class="actions">
          ${autoStarted ? `<button class="btn primary" data-close>Ya empezó la concentración</button>`
            : `<button class="btn primary" data-start>Empezar a concentrarme</button><button class="btn" data-close>Ahora no</button>`}
        </div>
      </div>`;
  }
  dlg.querySelector("[data-start]")?.addEventListener("click", () => { pomoStart(); dlg.close(); });
  dlg.querySelectorAll("[data-close]").forEach(b => b.addEventListener("click", () => dlg.close()));
  if (!dlg.open) dlg.showModal();
}

function pomoInit() {
  pomoLoad();
  // si la app se cerró con el temporizador corriendo y el tiempo ya pasó, se da por terminado
  if (POMO.st.running && pomoRemaining() <= 0) {
    POMO.st.running = false; POMO.st.endsAt = null; POMO.st.remaining = 0;
    setTimeout(() => pomoComplete(), 500);
  } else if (POMO.st.running) {
    // el audio necesita un gesto del usuario: el sonido ambiente se retoma al tocar la página
    document.addEventListener("pointerdown", () => { if (POMO.st.running && POMO.st.mode === "focus") ambientStart(); }, { once: true });
  }
  POMO.timer = setInterval(pomoTick, 250);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) pomoTick(); });
  pomoBadge();
}

// ------------------------------------------------------------------------- //
// Vista del pomodoro
// ------------------------------------------------------------------------- //
async function viewPomodoro() {
  setTitle("Pomodoro");
  let tasks = [];
  let stats = { today: 0, minutes_today: 0 };
  try { [tasks, stats] = await Promise.all([api("/api/tasks"), api("/api/pomodoros/stats")]); } catch (e) { /* sin datos */ }
  const open = tasks.filter(t => !t.done);
  const c = POMO.cfg;
  const R = 108, CIRC = 2 * Math.PI * R;
  main.innerHTML = `
    <div class="page narrow">
      <div class="page-head">
        <h1>Pomodoro</h1>
        <p class="lead">Bloques de concentración con descansos programados. Elegí la duración, el sonido y, si querés, la tarea en la que vas a trabajar.</p>
      </div>
      <section class="pomo" id="pomo">
        <div class="seg pomo-modes" role="group" aria-label="Modo">
          ${Object.entries(POMO_MODES).map(([k, v]) => `<button type="button" data-pomo-mode="${k}">${v.label}</button>`).join("")}
        </div>
        <div class="pomo-dial">
          <svg viewBox="0 0 240 240" aria-hidden="true">
            <circle cx="120" cy="120" r="${R}" class="ring-bg"/>
            <circle cx="120" cy="120" r="${R}" class="ring" id="ring" stroke-dasharray="${CIRC}" transform="rotate(-90 120 120)"/>
          </svg>
          <div class="pomo-time"><b id="clock" aria-live="off"></b><span id="pomo-mode"></span></div>
        </div>
        <div class="actions pomo-actions">
          <button class="btn primary big" id="p-toggle"></button>
          <button class="btn big" id="p-reset">Reiniciar</button>
          <button class="btn ghost big" id="p-skip">Saltear</button>
        </div>
        <p class="small muted" id="p-cycle"></p>
        <label class="field pomo-task"><span>Tarea en la que estás trabajando</span>
          <select class="input" id="p-task">
            <option value="">Sin tarea</option>
            ${open.map(t => `<option value="${t.id}" ${POMO.st.taskId === t.id ? "selected" : ""}>${esc(t.title)}</option>`).join("")}
          </select>
        </label>
        <p class="small muted" id="p-today">Hoy: ${plural(stats.today, "pomodoro", "pomodoros")}, ${plural(stats.minutes_today, "minuto", "minutos")} de concentración.</p>
      </section>

      <h2 class="section-title">Configuración</h2>
      <form class="panel pomo-cfg" id="p-cfg">
        <div class="grid-3">
          <label class="field"><span>Concentración (min)</span><input class="input" type="number" min="1" max="180" name="focus" value="${c.focus}"></label>
          <label class="field"><span>Descanso corto (min)</span><input class="input" type="number" min="1" max="60" name="short" value="${c.short}"></label>
          <label class="field"><span>Descanso largo (min)</span><input class="input" type="number" min="1" max="90" name="long" value="${c.long}"></label>
          <label class="field"><span>Descanso largo cada</span><select class="input" name="every">${[2, 3, 4, 5, 6].map(n => `<option value="${n}" ${c.every === n ? "selected" : ""}>${n} pomodoros</option>`).join("")}</select></label>
          <label class="field"><span>Sonido al terminar</span><select class="input" name="alarm">${Object.entries(ALARMS).map(([k, v]) => `<option value="${k}" ${c.alarm === k ? "selected" : ""}>${v}</option>`).join("")}</select></label>
          <label class="field"><span>Sonido de fondo al concentrarte</span><select class="input" name="ambient">${Object.entries(AMBIENTS).map(([k, v]) => `<option value="${k}" ${c.ambient === k ? "selected" : ""}>${v}</option>`).join("")}</select></label>
          <label class="field"><span>Volumen de la alarma</span><input type="range" min="0" max="1" step="0.05" name="volume" value="${c.volume}"></label>
          <label class="field"><span>Volumen del fondo</span><input type="range" min="0" max="1" step="0.05" name="ambientVolume" value="${c.ambientVolume}"></label>
        </div>
        <div class="row" style="margin-top:14px">
          <label class="check"><input type="checkbox" name="autoBreak" ${c.autoBreak ? "checked" : ""}> Empezar el descanso automáticamente</label>
          <label class="check"><input type="checkbox" name="autoFocus" ${c.autoFocus ? "checked" : ""}> Empezar el siguiente pomodoro automáticamente</label>
          <label class="check"><input type="checkbox" name="notify" ${c.notify ? "checked" : ""}> Avisarme con una notificación si estoy en otra pestaña</label>
        </div>
        <div class="actions">
          <button type="button" class="btn" id="p-test">Probar sonido</button>
          <button type="button" class="btn ghost" id="p-defaults">Volver a 25 / 5 / 15</button>
        </div>
      </form>
    </div>`;

  const ring = $("#ring");
  const render = () => {
    const rem = pomoRemaining();
    const total = pomoDuration();
    $("#clock").textContent = fmtClock(rem);
    $("#pomo-mode").textContent = POMO_MODES[POMO.st.mode].label;
    ring.style.strokeDashoffset = String(CIRC * (1 - rem / total));
    $("#pomo").dataset.phase = POMO.st.mode;
    $("#p-toggle").textContent = POMO.st.running ? "Pausar" : (rem < total ? "Continuar" : "Empezar");
    $$("[data-pomo-mode]").forEach(b => b.setAttribute("aria-pressed", b.dataset.pomoMode === POMO.st.mode));
    const inCycle = POMO.st.cycle % c.every;
    $("#p-cycle").textContent = `Pomodoros en este ciclo: ${inCycle} de ${c.every} antes del descanso largo.`;
  };
  POMO.listeners.add(render);
  cleanup = () => POMO.listeners.delete(render);
  render();

  $("#p-toggle").addEventListener("click", () => (POMO.st.running ? pomoPause() : pomoStart()));
  $("#p-reset").addEventListener("click", () => pomoReset());
  $("#p-skip").addEventListener("click", () => pomoComplete(true));
  // Antes, el atributo data-mode también estaba en el contenedor #pomo: cualquier clic adentro
  // (por ejemplo en «Empezar») se tomaba como cambio de modo y pedía confirmación.
  $$("[data-pomo-mode]").forEach(b => b.addEventListener("click", () => {
    const mode = b.dataset.pomoMode;
    if (mode === POMO.st.mode && POMO.st.running) return;
    const started = POMO.st.running || pomoRemaining() < pomoDuration();
    if (started && mode !== POMO.st.mode && !confirm("Hay un temporizador en curso. ¿Cambiar de modo y reiniciarlo?")) return;
    pomoReset(mode);
  }));
  $("#p-task").addEventListener("change", e => {
    const v = e.target.value;
    POMO.st.taskId = v ? +v : null;
    POMO.st.taskTitle = v ? e.target.selectedOptions[0].textContent : null;
    pomoSave();
  });
  $("#p-cfg").addEventListener("change", async e => {
    const f = new FormData($("#p-cfg"));
    const num = (k, d, max) => Math.min(max, Math.max(1, Math.round(+f.get(k) || d)));
    Object.assign(c, {
      focus: num("focus", 25, 180), short: num("short", 5, 60), long: num("long", 15, 90), every: +f.get("every"),
      alarm: f.get("alarm"), ambient: f.get("ambient"), volume: +f.get("volume"), ambientVolume: +f.get("ambientVolume"),
      autoBreak: f.has("autoBreak"), autoFocus: f.has("autoFocus"), notify: f.has("notify"),
    });
    if (e.target.name === "notify" && c.notify && "Notification" in window && Notification.permission === "default") {
      await Notification.requestPermission();
    }
    if (e.target.name === "ambientVolume") ambientVolume(c.ambientVolume);
    if (e.target.name === "ambient" && POMO.st.running && POMO.st.mode === "focus") ambientStart();
    if (e.target.name === "alarm") playAlarm(c.alarm, 1);
    // si el temporizador no está corriendo, se ajusta a la nueva duración
    if (!POMO.st.running && ["focus", "short", "long"].includes(e.target.name)) POMO.st.remaining = pomoDuration();
    pomoSave(); pomoEmit(); render();
  });
  $("#p-test").addEventListener("click", () => playAlarm(c.alarm, 1));
  $("#p-defaults").addEventListener("click", () => {
    Object.assign(c, { focus: 25, short: 5, long: 15, every: 4 });
    if (!POMO.st.running) POMO.st.remaining = pomoDuration();
    pomoSave();
    viewPomodoro();
  });
}

function startPomodoroForTask(task) {
  POMO.st.taskId = task.id;
  POMO.st.taskTitle = task.title;
  if (POMO.st.mode !== "focus") pomoReset("focus");
  pomoStart();
  location.hash = "#/pomodoro";
}
