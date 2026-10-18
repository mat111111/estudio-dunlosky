/* Estudio Dunlosky — «Saltá y Aprendé»: juego de plataformas donde cada bloque de idea es una pregunta
   de tus temas. Las respuestas cuentan para el repaso espaciado (se corrigen con /api/answer).
   Personaje y mundo originales: un estudiante con birrete que recorre las hojas de un cuaderno.
   Se carga antes que app.js; usa sus utilidades en tiempo de ejecución. */
"use strict";

const G = {
  TILE: 32, W: 960, H: 544, GROUND: 14,
  GRAV: 2100, JUMP: 760, RUN: 250, ACC: 1900, AIR_ACC: 1300, FRIC: 2200,
  COYOTE: 0.1, BUFFER: 0.13, INVULN: 1.6, MAX_HEARTS: 5,
};
// tiles: 0 vacío, 1 piso (libros), 2 bloque sólido, 3 bloque de idea (pregunta), 4 bloque ya usado
const SOLID = new Set([1, 2, 3, 4]);

function seededRng(seed) {
  let s = seed >>> 0 || 1;
  return () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; return ((s >>> 0) % 100000) / 100000; };
}

// --------------------------------------------------------------------------- //
// Generación de niveles
// --------------------------------------------------------------------------- //
function buildLevel(level, seed) {
  const rnd = seededRng(seed * 7919 + level * 104729);
  const ri = (a, b) => a + Math.floor(rnd() * (b - a + 1));
  const cols = 120 + level * 22;
  const rows = G.H / G.TILE;  // 17
  const grid = Array.from({ length: rows }, () => new Uint8Array(cols));
  for (let c = 0; c < cols; c++) for (let r = G.GROUND; r < rows; r++) grid[r][c] = 1;
  const enemies = [], sheets = [], ideas = [];
  const flat = (c, len) => { for (let i = 0; i < len; i++) if (grid[G.GROUND][c + i] !== 1) return false; return true; };
  const arc = (c, r, n) => { for (let i = 0; i < n; i++) sheets.push({ x: (c + i) * G.TILE + 8, y: (r - (i === 0 || i === n - 1 ? 0 : 1)) * G.TILE + 6, got: false }); };
  let x = 12;
  let ideaCount = 0;
  const wantIdeas = 5 + Math.min(level, 6);
  while (x < cols - 26) {
    const f = rnd();
    if (f < 0.22 && x > 16) {                       // pozo
      const w = ri(2, Math.min(4, 2 + Math.floor(level / 2)));
      for (let i = 0; i < w; i++) for (let r = G.GROUND; r < rows; r++) grid[r][x + i] = 0;
      arc(x - 1, G.GROUND - 4, w + 2);
      x += w + ri(3, 5);
    } else if (f < 0.48 && ideaCount < wantIdeas) { // bloques de idea, a veces con bloques sólidos a los lados
      const n = ri(1, 3);
      const which = ri(0, n - 1);
      for (let i = 0; i < n; i++) {
        grid[10][x + i] = i === which ? 3 : 2;
        if (i === which) { ideas.push({ c: x + i, r: 10 }); ideaCount++; }
      }
      if (rnd() < 0.5) arc(x, 9 - 1, n);
      if (rnd() < 0.35 + level * 0.05) enemies.push({ type: "olvido", x: (x + n + 2) * G.TILE, y: (G.GROUND - 1) * G.TILE });
      x += n + ri(4, 6);
    } else if (f < 0.66) {                          // pila de libros (escalón)
      const h = ri(1, Math.min(3, 1 + Math.floor(level / 2) + 1));
      const w = ri(1, 2);
      for (let i = 0; i < w; i++) for (let k = 0; k < h; k++) grid[G.GROUND - 1 - k][x + i] = 2;
      sheets.push({ x: x * G.TILE + 8, y: (G.GROUND - h - 2) * G.TILE, got: false });
      x += w + ri(3, 5);
    } else if (f < 0.84) {                          // plataforma flotante con premio arriba
      const len = ri(3, 5);
      for (let i = 0; i < len; i++) grid[11][x + i] = 2;
      if (ideaCount < wantIdeas && rnd() < 0.6) { const c = x + ri(0, len - 1); grid[7][c] = 3; ideas.push({ c, r: 7 }); ideaCount++; }
      else arc(x, 9, len);
      if (level >= 2 && rnd() < 0.4) enemies.push({ type: "olvido", x: (x + 1) * G.TILE, y: 10 * G.TILE });
      x += len + ri(3, 6);
    } else {                                        // tramo plano con enemigos
      const len = ri(6, 9);
      const k = Math.min(3, 1 + Math.floor(rnd() * (1 + level / 2)));
      for (let i = 0; i < k; i++) enemies.push({ type: level >= 3 && rnd() < 0.35 ? "distraccion" : "olvido", x: (x + 2 + i * 3) * G.TILE, y: (G.GROUND - 1) * G.TILE });
      arc(x + 1, G.GROUND - 3, 3);
      x += len;
    }
  }
  // asegurar suficientes bloques de idea
  for (let c = 20; ideaCount < wantIdeas && c < cols - 30; c += 9) {
    if (flat(c - 1, 3) && grid[10][c] === 0 && grid[11][c] === 0 && grid[9][c] === 0) { grid[10][c] = 3; ideas.push({ c, r: 10 }); ideaCount++; }
  }
  // zona final plana, punto de control y meta
  for (let c = cols - 26; c < cols; c++) { for (let r = 0; r < G.GROUND; r++) grid[r][c] = 0; for (let r = G.GROUND; r < rows; r++) grid[r][c] = 1; }
  for (let r = 0; r < rows; r++) grid[r][cols - 1] = 1;
  let cp = Math.floor(cols / 2);
  while (!flat(cp - 1, 3) && cp < cols - 30) cp++;
  const enemiesSafe = enemies.filter(e => {
    const c = Math.floor(e.x / G.TILE), r = Math.floor(e.y / G.TILE) + 1;
    return grid[r] && SOLID.has(grid[r][c]) && Math.abs(e.x - cp * G.TILE) > 96 && e.x > 20 * G.TILE;
  });
  return { cols, rows, grid, enemies: enemiesSafe, sheets, ideas, checkpoint: { x: cp * G.TILE, reached: false }, goal: { x: (cols - 10) * G.TILE } };
}

// --------------------------------------------------------------------------- //
// Sonido (sintetizado, sin archivos)
// --------------------------------------------------------------------------- //
let gameAudio = null;
let gameMuted = false;
try { gameMuted = localStorage.getItem("juego_mute") === "1"; } catch (e) { /* sin almacenamiento */ }
function sfx(kind) {
  if (gameMuted) return;
  try {
    gameAudio = gameAudio || new (window.AudioContext || window.webkitAudioContext)();
    const ctx = gameAudio;
    const notes = { jump: [[520, 0.07, "square"], [780, 0.06, "square"]], sheet: [[1320, 0.05, "triangle"], [1760, 0.08, "triangle"]],
      stomp: [[220, 0.08, "square"], [140, 0.08, "square"]], hurt: [[300, 0.1, "sawtooth"], [180, 0.18, "sawtooth"]],
      ok: [[660, 0.09, "triangle"], [880, 0.09, "triangle"], [1320, 0.18, "triangle"]], bad: [[330, 0.14, "square"], [220, 0.24, "square"]],
      bump: [[160, 0.06, "square"]], win: [[523, 0.12, "triangle"], [659, 0.12, "triangle"], [784, 0.12, "triangle"], [1046, 0.3, "triangle"]],
      check: [[784, 0.08, "triangle"], [988, 0.14, "triangle"]] }[kind] || [];
    let t = ctx.currentTime;
    for (const [f, d, type] of notes) {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.type = type; o.frequency.value = f;
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.12, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + d);
      o.connect(g).connect(ctx.destination); o.start(t); o.stop(t + d + 0.02);
      t += d * 0.85;
    }
  } catch (e) { /* sin audio */ }
}

// --------------------------------------------------------------------------- //
// Dibujo
// --------------------------------------------------------------------------- //
const PAL = { paper: "#FBFAF4", rule: "#C9D6EE", margin: "#F2A6B0", ink: "#1C2541", blue: "#2340C8", red: "#D7263D", green: "#23824F",
  yellow: "#FFE45C", amber: "#B7791F", gray: "#AEB6C8", purple: "#7A3FC8" };

function drawBackground(ctx, camX, t) {
  ctx.fillStyle = PAL.paper;
  ctx.fillRect(0, 0, G.W, G.H);
  ctx.strokeStyle = PAL.rule; ctx.lineWidth = 1;
  for (let y = 40; y < G.H; y += 32) { ctx.beginPath(); ctx.moveTo(0, y + 0.5); ctx.lineTo(G.W, y + 0.5); ctx.stroke(); }
  const mx = 72 - (camX * 0.3) % 1400;
  ctx.strokeStyle = PAL.margin; ctx.lineWidth = 2;
  for (let k = 0; k < 2; k++) { ctx.beginPath(); ctx.moveTo(mx + k * 1400, 0); ctx.lineTo(mx + k * 1400, G.H); ctx.stroke(); }
  // nubes y montañas dibujadas en lápiz (parallax)
  ctx.strokeStyle = "#9AA6C0"; ctx.lineWidth = 2; ctx.lineCap = "round";
  for (let i = -1; i < 6; i++) {
    const base = i * 420 - (camX * 0.15) % 420;
    const y = 90 + ((i * 53) % 4 + 4) % 4 * 18;
    ctx.beginPath();
    ctx.arc(base + 40, y, 18, Math.PI * 0.9, Math.PI * 1.95);
    ctx.arc(base + 70, y - 10, 24, Math.PI * 1.1, Math.PI * 1.9);
    ctx.arc(base + 104, y, 18, Math.PI * 1.1, Math.PI * 2.1);
    ctx.lineTo(base + 26, y + 16);
    ctx.stroke();
  }
  ctx.strokeStyle = "#B7C2D8";
  for (let i = -1; i < 5; i++) {
    const base = i * 560 - (camX * 0.4) % 560;
    ctx.beginPath(); ctx.moveTo(base, 448); ctx.quadraticCurveTo(base + 120, 300, base + 240, 448);
    ctx.moveTo(base + 180, 448); ctx.quadraticCurveTo(base + 300, 340, base + 420, 448); ctx.stroke();
  }
}

function drawTile(ctx, kind, x, y, r, c, t, bumpOff) {
  const T = G.TILE;
  if (kind === 1) {
    const top = r === G.GROUND;
    const colors = ["#2340C8", "#D7263D", "#23824F", "#B7791F"];
    ctx.fillStyle = colors[(c + r) % 4];
    ctx.fillRect(x, y, T, T);
    ctx.fillStyle = "rgba(255,255,255,.35)";
    ctx.fillRect(x + 3, y + 6, T - 6, 3); ctx.fillRect(x + 3, y + T - 9, T - 6, 3);
    ctx.strokeStyle = "rgba(28,37,65,.55)"; ctx.lineWidth = 1; ctx.strokeRect(x + 0.5, y + 0.5, T - 1, T - 1);
    if (top) { ctx.fillStyle = "#FFFFFF"; ctx.fillRect(x, y, T, 4); ctx.fillStyle = PAL.ink; ctx.fillRect(x, y + 4, T, 1.5); }
  } else if (kind === 2) {
    ctx.fillStyle = "#F4E3C1"; ctx.fillRect(x, y, T, T);
    ctx.fillStyle = "#E0C690"; ctx.fillRect(x, y + T / 2 - 1, T, 2);
    ctx.strokeStyle = "#8C6A2A"; ctx.lineWidth = 1.5; ctx.strokeRect(x + 1, y + 1, T - 2, T - 2);
    ctx.fillStyle = "#8C6A2A"; ctx.fillRect(x + 6, y + 6, 8, 2); ctx.fillRect(x + 18, y + 22, 8, 2);
  } else if (kind === 3 || kind === 4) {
    const yy = y - bumpOff;
    const used = kind === 4;
    ctx.fillStyle = used ? "#D5DAE6" : PAL.yellow;
    ctx.fillRect(x, yy, T, T);
    ctx.strokeStyle = used ? "#8790AB" : PAL.amber; ctx.lineWidth = 2; ctx.strokeRect(x + 1, yy + 1, T - 2, T - 2);
    if (!used) {  // lamparita: «idea»
      const glow = 0.5 + 0.5 * Math.sin(t * 4 + c);
      ctx.fillStyle = `rgba(255,255,255,${0.35 + glow * 0.35})`;
      ctx.beginPath(); ctx.arc(x + 16, yy + 13, 7, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = PAL.ink; ctx.lineWidth = 1.8;
      ctx.beginPath(); ctx.arc(x + 16, yy + 13, 7, Math.PI * 0.75, Math.PI * 2.25); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(x + 12, yy + 22); ctx.lineTo(x + 20, yy + 22); ctx.moveTo(x + 13, yy + 25.5); ctx.lineTo(x + 19, yy + 25.5); ctx.stroke();
    } else {
      ctx.fillStyle = "#8790AB"; ctx.fillRect(x + 8, yy + 14, 16, 4);
    }
  }
}

function drawPlayer(ctx, p, t) {
  const x = Math.round(p.x), y = Math.round(p.y);
  if (p.invuln > 0 && Math.floor(t * 20) % 2) return;
  ctx.save();
  ctx.translate(x + p.w / 2, y);
  ctx.scale(p.face, 1);
  const run = p.onGround && Math.abs(p.vx) > 30 ? Math.sin(t * 18) : 0;
  // piernas
  ctx.strokeStyle = PAL.ink; ctx.lineWidth = 4; ctx.lineCap = "round";
  ctx.beginPath(); ctx.moveTo(-4, 30); ctx.lineTo(-4 - run * 5, 37); ctx.moveTo(4, 30); ctx.lineTo(4 + run * 5, 37); ctx.stroke();
  // mochila
  ctx.fillStyle = PAL.red; ctx.fillRect(-13, 15, 6, 13);
  // cuerpo (buzo azul)
  ctx.fillStyle = PAL.blue;
  ctx.beginPath(); ctx.roundRect(-9, 13, 18, 19, 6); ctx.fill();
  // brazo
  ctx.strokeStyle = "#F3C9A2"; ctx.lineWidth = 3.5;
  ctx.beginPath(); ctx.moveTo(4, 18); ctx.lineTo(10 + (p.onGround ? -run * 3 : 3), p.onGround ? 26 : 12); ctx.stroke();
  // cabeza
  ctx.fillStyle = "#F3C9A2";
  ctx.beginPath(); ctx.arc(0, 8, 9, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = PAL.ink;
  ctx.beginPath(); ctx.arc(4, 7, 1.6, 0, Math.PI * 2); ctx.fill();
  ctx.fillRect(2, 11, 4, 1.4);
  // birrete
  ctx.fillStyle = PAL.ink;
  ctx.beginPath(); ctx.moveTo(-12, 0); ctx.lineTo(0, -5); ctx.lineTo(12, 0); ctx.lineTo(0, 4); ctx.closePath(); ctx.fill();
  ctx.fillRect(-6, 0, 12, 4);
  ctx.strokeStyle = PAL.yellow; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(0, -1); ctx.lineTo(-10, 1); ctx.lineTo(-10, 8); ctx.stroke();
  if (p.shield) {
    ctx.strokeStyle = "rgba(255,228,92,.85)"; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.ellipse(0, 18, 20, 24, 0, 0, Math.PI * 2); ctx.stroke();
  }
  ctx.restore();
}

function drawEnemy(ctx, e, t) {
  const x = Math.round(e.x), y = Math.round(e.y);
  if (e.dead) {
    ctx.globalAlpha = Math.max(0, e.dead);
    ctx.fillStyle = e.type === "olvido" ? PAL.purple : PAL.red;
    ctx.fillRect(x, y + e.h - 8, e.w, 8);
    ctx.globalAlpha = 1;
    return;
  }
  if (e.type === "olvido") {  // «Olvido»: manchita violeta con ojos de sueño
    const wob = Math.sin(t * 8 + e.x) * 2;
    ctx.fillStyle = PAL.purple;
    ctx.beginPath();
    ctx.moveTo(x, y + e.h);
    ctx.quadraticCurveTo(x - 2, y + 4 + wob, x + e.w / 2, y + wob);
    ctx.quadraticCurveTo(x + e.w + 2, y + 4 + wob, x + e.w, y + e.h);
    for (let i = 4; i >= 0; i--) ctx.lineTo(x + (e.w / 4) * i, y + e.h - (i % 2 ? 4 : 0));
    ctx.fill();
    ctx.strokeStyle = "#fff"; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(x + 7, y + 13); ctx.lineTo(x + 12, y + 13); ctx.moveTo(x + 16, y + 13); ctx.lineTo(x + 21, y + 13); ctx.stroke();
    ctx.fillStyle = "#7A839C"; ctx.font = "bold 10px system-ui"; ctx.fillText("z", x + e.w - 2, y - 2 + Math.sin(t * 3) * 3);
  } else {  // «Distracción»: burbuja de notificación que salta
    ctx.fillStyle = PAL.red;
    ctx.beginPath(); ctx.roundRect(x, y, e.w, e.h - 4, 8); ctx.fill();
    ctx.beginPath(); ctx.moveTo(x + 6, y + e.h - 5); ctx.lineTo(x + 4, y + e.h); ctx.lineTo(x + 12, y + e.h - 5); ctx.fill();
    ctx.fillStyle = "#fff"; ctx.font = "bold 16px system-ui"; ctx.textAlign = "center"; ctx.fillText("1", x + e.w / 2, y + 17); ctx.textAlign = "left";
  }
}

function drawSheet(ctx, s, t) {
  const sx = Math.abs(Math.cos(t * 3 + s.x * 0.01));
  ctx.save();
  ctx.translate(s.x + 8, s.y + 10);
  ctx.scale(Math.max(0.15, sx), 1);
  ctx.fillStyle = "#FFFFFF"; ctx.strokeStyle = PAL.blue; ctx.lineWidth = 1.5;
  ctx.fillRect(-7, -10, 14, 19); ctx.strokeRect(-7, -10, 14, 19);
  ctx.strokeStyle = PAL.rule; ctx.lineWidth = 1;
  for (let i = -5; i < 8; i += 4) { ctx.beginPath(); ctx.moveTo(-5, i); ctx.lineTo(5, i); ctx.stroke(); }
  ctx.restore();
}

function drawFlag(ctx, x, reached, label) {
  const base = G.GROUND * G.TILE;
  ctx.fillStyle = "#F4C542"; ctx.fillRect(x, base - 120, 6, 120);
  ctx.fillStyle = "#F3B6BE"; ctx.fillRect(x, base - 128, 6, 8);
  ctx.fillStyle = PAL.ink; ctx.beginPath(); ctx.moveTo(x, base); ctx.lineTo(x + 3, base + 8); ctx.lineTo(x + 6, base); ctx.fill();
  ctx.fillStyle = reached ? PAL.green : "#C9CFDC";
  ctx.beginPath(); ctx.moveTo(x + 6, base - 118); ctx.lineTo(x + 46, base - 106); ctx.lineTo(x + 6, base - 94); ctx.fill();
  if (label) { ctx.fillStyle = PAL.ink; ctx.font = "bold 12px system-ui"; ctx.fillText(label, x - 22, base - 136); }
}

function drawGoal(ctx, x, t) {
  const base = G.GROUND * G.TILE;
  ctx.fillStyle = "#1C2541"; ctx.fillRect(x, base - 128, 80, 128);
  ctx.fillStyle = "#FFF6C2"; ctx.fillRect(x + 8, base - 120, 64, 120);
  ctx.fillStyle = PAL.blue; ctx.font = "bold 14px system-ui"; ctx.textAlign = "center";
  ctx.fillText("EXAMEN", x + 40, base - 92); ctx.fillText("FINAL", x + 40, base - 74);
  ctx.textAlign = "left";
  ctx.strokeStyle = PAL.red; ctx.lineWidth = 3;
  const by = base - 46 + Math.sin(t * 3) * 2;
  ctx.beginPath(); ctx.arc(x + 40, by, 10, 0, Math.PI * 2); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(x + 34, by + 8); ctx.lineTo(x + 30, by + 24); ctx.moveTo(x + 46, by + 8); ctx.lineTo(x + 50, by + 24); ctx.stroke();
}

function drawHud(ctx, s) {
  ctx.fillStyle = "rgba(255,255,255,.88)";
  ctx.fillRect(0, 0, G.W, 38);
  ctx.fillStyle = PAL.rule; ctx.fillRect(0, 38, G.W, 1);
  for (let i = 0; i < G.MAX_HEARTS; i++) {
    const x = 16 + i * 24, y = 12;
    ctx.fillStyle = i < s.hearts ? PAL.red : "#D5DAE6";
    ctx.beginPath(); ctx.moveTo(x + 9, y + 15); ctx.bezierCurveTo(x - 4, y + 6, x + 1, y - 3, x + 9, y + 3); ctx.bezierCurveTo(x + 17, y - 3, x + 22, y + 6, x + 9, y + 15); ctx.fill();
  }
  ctx.fillStyle = PAL.ink; ctx.font = "bold 16px system-ui";
  ctx.fillText(`Nivel ${s.level}`, 150, 25);
  drawSheet(ctx, { x: 240, y: 9 }, 0);
  ctx.fillText(`× ${s.sheetsGot}`, 262, 25);
  ctx.fillText(`Puntos ${s.score}`, 330, 25);
  ctx.fillStyle = PAL.green; ctx.fillText(`✓ ${s.correct}`, 480, 25);
  ctx.fillStyle = PAL.red; ctx.fillText(`✗ ${s.wrong}`, 540, 25);
  if (s.shield) { ctx.fillStyle = PAL.amber; ctx.fillText("Escudo", 600, 25); }
  ctx.fillStyle = "#7A839C"; ctx.font = "13px system-ui"; ctx.textAlign = "right";
  ctx.fillText("Flechas o A/D: moverse · Espacio: saltar · P: pausa", G.W - 14, 25);
  ctx.textAlign = "left";
}

// --------------------------------------------------------------------------- //
// Pantalla de inicio
// --------------------------------------------------------------------------- //
async function viewGame(params) {
  setTitle("Saltá y Aprendé");
  const topics = await api("/api/topics");
  let picked = new Set((params.get("temas") || "").split(",").filter(Boolean).map(Number));
  if (!picked.size) { try { picked = new Set(JSON.parse(localStorage.getItem("juego_temas") || "[]")); } catch (e) { /* nada */ } }
  picked = new Set([...picked].filter(id => topics.some(t => t.id === id)));
  if (!picked.size && topics[0]) picked.add(topics[0].id);
  let level = "mixto";
  try { level = localStorage.getItem("juego_nivel") || "mixto"; } catch (e) { /* nada */ }
  main.innerHTML = `
    <div class="page">
      <div class="page-head">
        <h1>Saltá y Aprendé</h1>
        <p class="lead">Un juego de plataformas con tus temas: corré, saltá y golpeá los <b>bloques de idea</b> (los amarillos con una lamparita). Cada uno es una pregunta. Si acertás, sumás puntos y escudo; si te equivocás, perdés una vida y esa pregunta vuelve en tu repaso. Al final te espera el <b>examen final</b>.</p>
      </div>
      ${topics.length ? `
      <div class="game-setup panel">
        <div>
          <div class="prop-label">Temas de las preguntas</div>
          <div class="chips game-topics">${topics.map(t => `<label class="src-chip"><input type="checkbox" value="${t.id}" ${picked.has(t.id) ? "checked" : ""}> ${esc(t.title)}</label>`).join("")}</div>
        </div>
        <div class="row" style="margin-top:16px;align-items:flex-end;gap:16px">
          <label class="field"><span>Dificultad de las preguntas</span>
            <select class="input" id="g-level">${[["mixto", "Mixto"], ["basico", "Básico"], ["intermedio", "Intermedio"], ["avanzado", "Avanzado"]].map(([k, l]) => `<option value="${k}" ${k === level ? "selected" : ""}>${l}</option>`).join("")}</select></label>
          <button class="btn primary big" id="g-play">Jugar</button>
          <span class="small muted" id="g-best"></span>
        </div>
        <p class="small muted" style="margin-top:14px">Controles: <kbd>←</kbd> <kbd>→</kbd> o <kbd>A</kbd> <kbd>D</kbd> para moverte, <kbd>Espacio</kbd> o <kbd>↑</kbd> para saltar (mantenelo para saltar más alto), <kbd>P</kbd> para pausar, <kbd>1</kbd>–<kbd>4</kbd> para responder. En el celular aparecen botones en pantalla. Saltá encima de los «Olvidos» (manchas violetas) y de las «Distracciones» (burbujas rojas) para sacarlos del camino.</p>
      </div>` : `<div class="empty"><h3>Primero necesitás un tema</h3><p class="muted">El juego usa las preguntas de tus temas. Creá uno en <a href="#/nuevo">Nuevo tema</a> y volvé.</p></div>`}
    </div>`;
  if (!topics.length) return;
  const ids = () => $$(".game-topics input:checked").map(i => +i.value);
  const best = async () => {
    const b = await api(`/api/game/best?topic_ids=${ids().join(",")}`).catch(() => null);
    $("#g-best").textContent = b && b.best_score ? `Tu récord con estos temas: ${b.best_score} puntos (nivel ${b.best_level})` : "";
  };
  $$(".game-topics input").forEach(i => i.addEventListener("change", best));
  best();
  $("#g-play").addEventListener("click", async () => {
    const chosen = ids();
    if (!chosen.length) { toast("Elegí al menos un tema", true); return; }
    const lvl = $("#g-level").value;
    try { localStorage.setItem("juego_temas", JSON.stringify(chosen)); localStorage.setItem("juego_nivel", lvl); } catch (e) { /* nada */ }
    const d = await api(`/api/game/questions?topic_ids=${chosen.join(",")}&level=${lvl}&n=60`);
    if (d.questions.length < 3) {
      toast("Esos temas tienen pocas preguntas de opción múltiple o verdadero/falso. Sumá otro tema o generá preguntas con IA.", true);
      return;
    }
    playGame(d.questions, chosen, lvl);
  });
}

// --------------------------------------------------------------------------- //
// Juego
// --------------------------------------------------------------------------- //
function playGame(questions, topicIds, qLevel) {
  document.body.classList.add("game-mode");
  main.innerHTML = `
    <div class="game-wrap">
      <div class="game-bar">
        <a class="btn ghost small" href="#/juego" id="g-exit">← Salir</a>
        <span class="grow"></span>
        <button class="btn ghost small" id="g-mute">${gameMuted ? "Activar sonido" : "Silenciar"}</button>
        <button class="btn ghost small" id="g-pause">Pausa</button>
      </div>
      <div class="game-area">
        <div class="game-stage" id="g-stage">
          <canvas id="g-canvas" width="${G.W}" height="${G.H}" aria-label="Juego de plataformas"></canvas>
          <div class="game-overlay" id="g-over" hidden></div>
        </div>
        <div class="game-touch" id="g-touch" aria-hidden="true">
          <button data-k="left">◀</button><button data-k="right">▶</button><span class="grow"></span><button data-k="jump" class="jump">Saltar</button>
        </div>
      </div>
      <p class="game-rotate small muted">Girá el celular para jugar en pantalla más grande.</p>
    </div>`;
  const canvas = $("#g-canvas");
  const ctx = canvas.getContext("2d");
  const over = $("#g-over");
  const keys = { left: false, right: false, jump: false };
  let queue = questions.slice();
  let used = [];
  const nextQuestion = () => {
    if (!queue.length) { queue = used.sort(() => Math.random() - 0.5); used = []; }
    const q = queue.shift();
    used.push(q);
    return q;
  };

  const S = { level: 1, hearts: 3, score: 0, sheetsGot: 0, correct: 0, wrong: 0, shield: false, wrongIds: new Set() };
  let L, P, enemies, cam = 0, t = 0, paused = false, modal = false, raf = 0, last = 0, acc = 0, bumps = new Map(), ended = false;
  let jumpHeld = false, jumpBuffer = 0, coyote = 0, respawn = null, finalPending = false;

  function startLevel() {
    L = buildLevel(S.level, Date.now() % 100000);
    P = { x: 3 * G.TILE, y: (G.GROUND - 2) * G.TILE, w: 22, h: 38, vx: 0, vy: 0, face: 1, onGround: false, invuln: 0, get shield() { return S.shield; } };
    enemies = L.enemies.map(e => ({ ...e, w: 28, h: 26, vx: e.type === "olvido" ? -55 - S.level * 6 : -80, vy: 0, dead: 0, hop: Math.random() }));
    enemies.forEach(e => { e.y = e.y + G.TILE - e.h; });
    respawn = { x: P.x, y: P.y };
    cam = 0;
    finalPending = false;
    bumps = new Map();
  }

  // ---------- física ----------
  const tileAt = (px, py) => {
    const c = Math.floor(px / G.TILE), r = Math.floor(py / G.TILE);
    if (c < 0 || c >= L.cols) return 1;
    if (r < 0 || r >= L.rows) return 0;
    return L.grid[r][c];
  };
  function collide(o, axis, onHead) {
    const x1 = Math.floor(o.x / G.TILE), x2 = Math.floor((o.x + o.w - 0.01) / G.TILE);
    const y1 = Math.floor(o.y / G.TILE), y2 = Math.floor((o.y + o.h - 0.01) / G.TILE);
    for (let r = y1; r <= y2; r++) for (let c = x1; c <= x2; c++) {
      if (!SOLID.has(tileAt(c * G.TILE + 1, r * G.TILE + 1))) continue;
      if (axis === "x") {
        if (o.vx > 0) o.x = c * G.TILE - o.w; else if (o.vx < 0) o.x = (c + 1) * G.TILE;
        o.hitWall = true; o.vx = o.vx && o.isEnemy ? -o.vx : 0;
        return;
      }
      if (o.vy > 0) { o.y = r * G.TILE - o.h; o.vy = 0; o.onGround = true; }
      else if (o.vy < 0) {
        o.y = (r + 1) * G.TILE; o.vy = 0;
        if (onHead) {  // golpe desde abajo: el bloque del medio de la cabeza
          const mid = Math.floor((o.x + o.w / 2) / G.TILE);
          onHead(L.grid[r][mid] !== undefined && SOLID.has(L.grid[r][mid]) ? mid : c, r);
        }
      }
      return;
    }
  }
  function hurt(force = false) {
    if (P.invuln > 0 && !force) return;
    if (S.shield && !force) { S.shield = false; P.invuln = G.INVULN; sfx("hurt"); return; }
    S.hearts -= 1;
    P.invuln = G.INVULN;
    sfx("hurt");
    if (S.hearts <= 0) gameOver();
  }

  function step(dt) {
    t += dt;
    // movimiento horizontal
    const dir = (keys.right ? 1 : 0) - (keys.left ? 1 : 0);
    const a = P.onGround ? G.ACC : G.AIR_ACC;
    if (dir) { P.vx += dir * a * dt; P.face = dir; }
    else if (P.onGround) { const f = G.FRIC * dt; P.vx = Math.abs(P.vx) <= f ? 0 : P.vx - Math.sign(P.vx) * f; }
    P.vx = Math.max(-G.RUN, Math.min(G.RUN, P.vx));
    // salto con margen («coyote time») y salto anticipado
    coyote = P.onGround ? G.COYOTE : Math.max(0, coyote - dt);
    jumpBuffer = Math.max(0, jumpBuffer - dt);
    if (jumpBuffer > 0 && coyote > 0) { P.vy = -G.JUMP; P.onGround = false; coyote = 0; jumpBuffer = 0; sfx("jump"); }
    if (!keys.jump && P.vy < -260) P.vy = -260;  // soltar antes = salto más bajo
    P.vy = Math.min(P.vy + G.GRAV * dt, 1100);
    P.x += P.vx * dt; collide(P, "x");
    P.onGround = false;
    P.y += P.vy * dt; collide(P, "y", hitBlock);
    P.x = Math.max(0, Math.min(P.x, L.cols * G.TILE - P.w - G.TILE));
    if (P.invuln > 0) P.invuln -= dt;
    // caída a un pozo
    if (P.y > G.H + 40) {
      hurt(true);
      if (S.hearts > 0) { P.x = respawn.x; P.y = respawn.y; P.vx = P.vy = 0; P.invuln = G.INVULN; }
    }
    // hojas
    for (const s of L.sheets) {
      if (!s.got && P.x < s.x + 16 && P.x + P.w > s.x && P.y < s.y + 20 && P.y + P.h > s.y) { s.got = true; S.sheetsGot++; S.score += 10; sfx("sheet"); }
    }
    // enemigos
    for (const e of enemies) {
      if (e.dead) { e.dead -= dt * 2; continue; }
      if (Math.abs(e.x - P.x) > G.W) continue;  // fuera de pantalla quedan quietos
      e.isEnemy = true;
      e.vy = Math.min(e.vy + G.GRAV * dt, 1100);
      if (e.type === "distraccion" && e.onGround) { e.hop += dt; if (e.hop > 1.1) { e.vy = -520; e.hop = 0; } }
      e.x += e.vx * dt; e.hitWall = false; collide(e, "x");
      e.onGround = false;
      e.y += e.vy * dt; collide(e, "y");
      // dar la vuelta en los bordes
      if (e.onGround && e.type === "olvido") {
        const ahead = e.vx > 0 ? e.x + e.w + 2 : e.x - 2;
        if (!SOLID.has(tileAt(ahead, e.y + e.h + 4))) e.vx = -e.vx;
      }
      if (e.y > G.H + 60) { e.dead = 0.01; continue; }
      if (P.x < e.x + e.w && P.x + P.w > e.x && P.y < e.y + e.h && P.y + P.h > e.y) {
        if (P.vy > 60 && P.y + P.h - e.y < 18) { e.dead = 1; P.vy = keys.jump ? -G.JUMP * 0.85 : -420; S.score += 50; sfx("stomp"); }
        else { hurt(); P.vx = (P.x < e.x ? -1 : 1) * 260; P.vy = -300; }
      }
    }
    // punto de control
    if (!L.checkpoint.reached && P.x > L.checkpoint.x) { L.checkpoint.reached = true; respawn = { x: L.checkpoint.x, y: (G.GROUND - 2) * G.TILE }; sfx("check"); }
    // meta: examen final
    if (!finalPending && P.x + P.w > L.goal.x + 10) { finalPending = true; P.vx = 0; askFinal(); }
    // cámara
    const target = P.x - G.W * 0.4 + P.face * 40;
    cam += (target - cam) * Math.min(1, dt * 6);
    cam = Math.max(0, Math.min(cam, L.cols * G.TILE - G.W));
    for (const [k, v] of bumps) { if (v <= 0) bumps.delete(k); else bumps.set(k, v - dt * 60); }
  }

  function hitBlock(c, r) {
    const kind = L.grid[r]?.[c];
    if (kind === 3) {
      bumps.set(`${c},${r}`, 10);
      L.grid[r][c] = 4;
      ask(nextQuestion(), ok => {
        if (ok) { S.score += 100; if (!S.shield) S.shield = true; else if (S.hearts < G.MAX_HEARTS) S.hearts++; }
        else hurt(true);
      });
    } else if (kind === 2 || kind === 4) { bumps.set(`${c},${r}`, 5); sfx("bump"); }
  }

  // ---------- preguntas ----------
  function ask(q, done, title = "Bloque de idea") {
    modal = true;
    keys.left = keys.right = keys.jump = false;
    const opts = q.options;
    over.hidden = false;
    over.innerHTML = `
      <div class="game-q" role="dialog" aria-modal="true" aria-label="${esc(title)}">
        <div class="small muted">${esc(title)}${q.topic ? ` · ${esc(q.topic)}` : ""}</div>
        <p class="game-q-prompt">${q.kind === "tf" ? "<span class=\"game-q-kind\">¿Verdadero o falso?</span> " : q.fill ? "<span class=\"game-q-kind\">Completá el espacio:</span> " : ""}${esc(q.prompt)}</p>
        <div class="game-q-opts">${opts.map((o, i) => `<button class="opt" data-i="${i}"><kbd>${i + 1}</kbd> ${esc(o)}</button>`).join("")}</div>
        <div class="game-q-fb" id="g-fb" hidden></div>
      </div>`;
    let answered = false;
    const onKey = ev => {
      if (answered) {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); $("#g-cont")?.click(); }
        return;
      }
      const n = parseInt(ev.key, 10);
      if (n >= 1 && n <= opts.length) { ev.preventDefault(); choose(n - 1); }
      if (q.kind === "tf" && (ev.key.toLowerCase() === "v")) choose(0);
      if (q.kind === "tf" && (ev.key.toLowerCase() === "f")) choose(1);
    };
    document.addEventListener("keydown", onKey, true);
    $$(".opt", over).forEach(b => b.addEventListener("click", () => choose(+b.dataset.i)));
    $(".opt", over)?.focus();
    async function choose(i) {
      if (answered) return;
      answered = true;
      $$(".opt", over).forEach(b => (b.disabled = true));
      let res = null;
      try { res = await api("/api/answer", { method: "POST", body: { item_id: q.id, answer: opts[i], technique: "juego" } }); }
      catch (e) { res = null; }
      const fb = $("#g-fb", over);
      fb.hidden = false;
      if (!res) {
        fb.innerHTML = `<p>No se pudo corregir (¿sin conexión?). Seguimos sin penalizar.</p><button class="btn primary" id="g-cont">Continuar</button>`;
      } else {
        const ok = res.verdict === "correct";
        if (ok) { S.correct++; sfx("ok"); } else { S.wrong++; S.wrongIds.add(q.id); sfx("bad"); }
        $$(".opt", over).forEach(b => {
          const txt = opts[+b.dataset.i];
          if (strip(txt) === strip(res.correct_answer)) b.classList.add("right");
          else if (+b.dataset.i === i) b.classList.add("wrong");
        });
        fb.innerHTML = `<p class="${ok ? "ok" : "bad"}"><b>${ok ? "¡Correcto!" : "No era esa."}</b> ${ok ? "" : `La respuesta es: <b>${esc(res.correct_answer)}</b>.`}</p>
          ${res.explanation ? `<p class="small">${esc(res.explanation)}</p>` : res.context && !ok ? `<p class="small muted">Según la fuente: «${esc(res.context)}»</p>` : ""}
          ${ok ? "" : `<p class="small muted">Esta pregunta quedó en tu repaso de hoy.</p>`}
          <button class="btn primary" id="g-cont">Continuar <kbd>Enter</kbd></button>`;
        res.ok = ok;
      }
      $("#g-cont", over).focus();
      $("#g-cont", over).addEventListener("click", () => {
        document.removeEventListener("keydown", onKey, true);
        over.hidden = true; over.innerHTML = "";
        modal = false;
        last = performance.now();
        canvas.focus();
        done(res ? res.ok : null);
      });
    }
  }
  function askFinal() {
    ask(nextQuestion(), ok => {
      if (ok === false) {
        hurt(true);
        if (S.hearts > 0) setTimeout(askFinal, 50);
      } else levelComplete();
    }, "Examen final");
  }

  // ---------- pantallas ----------
  function overlay(html) { over.hidden = false; over.innerHTML = `<div class="game-q game-card">${html}</div>`; }
  function levelComplete() {
    sfx("win");
    const bonus = 300 + S.level * 100 + S.hearts * 50;
    S.score += bonus;
    modal = true;
    overlay(`<h2>¡Nivel ${S.level} superado!</h2>
      <p>Bonificación: <b>+${bonus}</b> puntos. Llevás <b>${S.score}</b>.</p>
      <p class="small muted">Preguntas: ${S.correct} correctas y ${S.wrong} incorrectas. Hojas juntadas: ${S.sheetsGot}.</p>
      <div class="actions"><button class="btn primary" id="g-next">Siguiente nivel <kbd>Enter</kbd></button><a class="btn" href="#/juego">Terminar</a></div>`);
    saveScore();
    const go = () => { document.removeEventListener("keydown", k, true); over.hidden = true; S.level++; startLevel(); modal = false; last = performance.now(); canvas.focus(); };
    const k = ev => { if (ev.key === "Enter") { ev.preventDefault(); go(); } };
    document.addEventListener("keydown", k, true);
    $("#g-next").addEventListener("click", go);
    $("#g-next").focus();
  }
  function gameOver() {
    if (ended) return;
    ended = true;
    modal = true;
    setTimeout(() => {
      overlay(`<h2>Fin del juego</h2>
        <p>Llegaste al nivel <b>${S.level}</b> con <b>${S.score}</b> puntos.</p>
        <p class="small muted">Preguntas: ${S.correct} correctas y ${S.wrong} incorrectas.</p>
        ${S.wrongIds.size ? `<p class="small">Las ${plural(S.wrongIds.size, "pregunta que fallaste quedó", "preguntas que fallaste quedaron")} en tu repaso. Practicarlas ahora es lo que más te va a servir.</p>` : ""}
        <div class="actions">
          <button class="btn primary" id="g-retry">Jugar de nuevo</button>
          ${S.wrongIds.size ? `<button class="btn" id="g-errs">Practicar mis errores</button>` : ""}
          <a class="btn ghost" href="#/juego">Salir</a>
        </div>`);
      saveScore();
      $("#g-retry").addEventListener("click", () => { Object.assign(S, { level: 1, hearts: 3, score: 0, sheetsGot: 0, correct: 0, wrong: 0, shield: false }); ended = false; over.hidden = true; startLevel(); modal = false; last = performance.now(); canvas.focus(); });
      $("#g-errs")?.addEventListener("click", () => startSession({ mode: "items", item_ids: [...S.wrongIds], n: S.wrongIds.size, tech: "errores", back: "#/juego" }));
      $("#g-retry").focus();
    }, 400);
  }
  let savedFor = -1;
  function saveScore() {
    if (savedFor === S.score) return;
    savedFor = S.score;
    api("/api/game/score", { method: "POST", body: { topic_ids: topicIds, level: S.level, score: S.score, correct: S.correct, wrong: S.wrong } }).catch(() => {});
  }
  function togglePause(force) {
    if (modal && !paused) return;
    paused = force ?? !paused;
    $("#g-pause").textContent = paused ? "Seguir" : "Pausa";
    if (paused) overlay(`<h2>Pausa</h2><p class="small muted">Tomate un respiro. Tocá <kbd>P</kbd> o el botón para seguir.</p><div class="actions"><button class="btn primary" id="g-resume">Seguir</button></div>`);
    else { over.hidden = true; last = performance.now(); canvas.focus(); }
    $("#g-resume")?.addEventListener("click", () => togglePause(false));
    modal = paused;
  }

  // ---------- dibujo ----------
  function draw() {
    drawBackground(ctx, cam, t);
    ctx.save();
    ctx.translate(-Math.round(cam), 0);
    const c1 = Math.max(0, Math.floor(cam / G.TILE) - 1), c2 = Math.min(L.cols, c1 + G.W / G.TILE + 3);
    for (let r = 0; r < L.rows; r++) for (let c = c1; c < c2; c++) {
      const k = L.grid[r][c];
      if (k) drawTile(ctx, k, c * G.TILE, r * G.TILE, r, c, t, Math.max(0, bumps.get(`${c},${r}`) || 0));
    }
    drawFlag(ctx, L.checkpoint.x, L.checkpoint.reached, "Control");
    drawGoal(ctx, L.goal.x, t);
    for (const s of L.sheets) if (!s.got && s.x > cam - 40 && s.x < cam + G.W + 40) drawSheet(ctx, s, t);
    for (const e of enemies) if (e.x > cam - 60 && e.x < cam + G.W + 60 && (e.dead === 0 || e.dead > 0)) drawEnemy(ctx, e, t);
    drawPlayer(ctx, P, t);
    ctx.restore();
    drawHud(ctx, S);
  }

  function frame(now) {
    raf = requestAnimationFrame(frame);
    if (!last) last = now;
    let dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (!paused && !modal && !ended) {
      acc += dt;
      while (acc >= 1 / 120) { step(1 / 120); acc -= 1 / 120; }
    } else acc = 0;
    draw();
  }

  // ---------- controles ----------
  const KEYMAP = { ArrowLeft: "left", a: "left", A: "left", ArrowRight: "right", d: "right", D: "right", " ": "jump", ArrowUp: "jump", w: "jump", W: "jump", z: "jump", Z: "jump" };
  const down = ev => {
    if (modal && !paused) return;
    if (ev.key === "p" || ev.key === "P" || ev.key === "Escape") { ev.preventDefault(); togglePause(); return; }
    const k = KEYMAP[ev.key];
    if (!k || paused) return;
    ev.preventDefault();
    if (k === "jump" && !keys.jump) jumpBuffer = G.BUFFER;
    keys[k] = true;
  };
  const up = ev => { const k = KEYMAP[ev.key]; if (k) keys[k] = false; };
  document.addEventListener("keydown", down);
  document.addEventListener("keyup", up);
  const blur = () => { keys.left = keys.right = keys.jump = false; if (!modal && !ended) togglePause(true); };
  window.addEventListener("blur", blur);
  $$("#g-touch [data-k]").forEach(b => {
    const k = b.dataset.k;
    b.addEventListener("pointerdown", ev => { ev.preventDefault(); if (k === "jump") jumpBuffer = G.BUFFER; keys[k] = true; b.setPointerCapture(ev.pointerId); });
    const rel = () => { keys[k] = false; };
    b.addEventListener("pointerup", rel); b.addEventListener("pointercancel", rel); b.addEventListener("lostpointercapture", rel);
  });
  $("#g-pause").addEventListener("click", () => togglePause());
  $("#g-mute").addEventListener("click", e => {
    gameMuted = !gameMuted;
    try { localStorage.setItem("juego_mute", gameMuted ? "1" : "0"); } catch (err) { /* nada */ }
    e.currentTarget.textContent = gameMuted ? "Activar sonido" : "Silenciar";
  });
  canvas.tabIndex = 0;

  cleanup = () => {
    cancelAnimationFrame(raf);
    document.removeEventListener("keydown", down);
    document.removeEventListener("keyup", up);
    window.removeEventListener("blur", blur);
    document.body.classList.remove("game-mode");
    if (S.score > 0 && !ended) saveScore();
  };

  startLevel();
  canvas.focus();
  raf = requestAnimationFrame(frame);
  // para las pruebas automáticas
  window.__juego = { S, get P() { return P; }, get L() { return L; }, keys, get modal() { return modal; } };
}
