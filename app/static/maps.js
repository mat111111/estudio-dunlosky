/* Estudio Dunlosky — Mapas conceptuales: lienzo con cuadros, círculos, rombos, notas y flechas con
   frases de enlace. Se carga antes que app.js; usa sus utilidades en tiempo de ejecución. */
"use strict";

const MAP_SHAPES = [
  ["round", "Cuadro redondeado"], ["rect", "Cuadro"], ["ellipse", "Óvalo"], ["circle", "Círculo"],
  ["diamond", "Rombo"], ["note", "Nota adhesiva"], ["text", "Texto suelto"],
];
const MAP_COLORS = [
  { fill: "#FFFFFF", stroke: "#1C2541", name: "Blanco" },
  { fill: "#E8ECFC", stroke: "#2340C8", name: "Azul" },
  { fill: "#E3F4EA", stroke: "#23824F", name: "Verde" },
  { fill: "#FFF3B0", stroke: "#B7791F", name: "Amarillo" },
  { fill: "#FDE8EB", stroke: "#D7263D", name: "Rojo" },
  { fill: "#F1E9FC", stroke: "#7A3FC8", name: "Violeta" },
  { fill: "#E2F5F6", stroke: "#0F7C86", name: "Turquesa" },
  { fill: "#1C2541", stroke: "#1C2541", name: "Oscuro" },
];
const MAP_FONT = '"Atkinson Hyperlegible", system-ui, "Segoe UI", sans-serif';
const SHAPE_ICONS = {
  round: '<rect x="3" y="6" width="18" height="12" rx="4"/>',
  rect: '<rect x="3" y="6" width="18" height="12"/>',
  ellipse: '<ellipse cx="12" cy="12" rx="9.5" ry="6.5"/>',
  circle: '<circle cx="12" cy="12" r="8"/>',
  diamond: '<path d="M12 3.5 21 12l-9 8.5L3 12z"/>',
  note: '<path d="M4 4h16v11l-5 5H4z"/><path d="M15 20v-5h5"/>',
  text: '<path d="M6 6h12M12 6v13M9 19h6"/>',
};

function mapUid() { return Math.random().toString(36).slice(2, 10); }
function mapTextColor(fill) {
  const h = (fill || "#FFFFFF").replace("#", "");
  const [r, g, b] = [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16) / 255);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.45 ? "#FFFFFF" : "#1C2541";
}
function xmlEsc(s) { return String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

// --------------------------------------------------------------------------- //
// Geometría y dibujo (se usa en el editor, en las miniaturas y al exportar)
// --------------------------------------------------------------------------- //
let _measureCtx = null;
function measure(text, size, bold) {
  if (!_measureCtx) _measureCtx = document.createElement("canvas").getContext("2d");
  _measureCtx.font = `${bold ? 700 : 400} ${size}px ${MAP_FONT}`;
  return _measureCtx.measureText(text).width;
}
function wrapLines(text, maxW, size, bold) {
  const out = [];
  for (const para of String(text || "").split("\n")) {
    const words = para.split(/\s+/).filter(Boolean);
    if (!words.length) { out.push(""); continue; }
    let line = "";
    for (const w of words) {
      const test = line ? line + " " + w : w;
      if (measure(test, size, bold) <= maxW || !line) line = test;
      else { out.push(line); line = w; }
    }
    out.push(line);
  }
  return out;
}
function innerWidth(n) {
  const f = { ellipse: 0.74, circle: 0.7, diamond: 0.56 }[n.shape] || 1;
  return Math.max(30, n.w * f - 20);
}
function nodeLayout(n) {
  const size = n.size || 16;
  const lh = Math.round(size * 1.25);
  const lines = wrapLines(n.text, innerWidth(n), size, n.bold);
  const pad = { ellipse: 22, circle: 24, diamond: 30 }[n.shape] || 12;
  const need = lines.length * lh + pad * 2;
  return { lines, lh, size, h: Math.max(n.h, need) };
}
function nodeBox(n) { const L = nodeLayout(n); return { x: n.x, y: n.y, w: n.shape === "circle" ? Math.max(n.w, L.h) : n.w, h: n.shape === "circle" ? Math.max(n.w, L.h) : L.h }; }
function center(n) { const b = nodeBox(n); return { x: b.x + b.w / 2, y: b.y + b.h / 2 }; }

/** Punto donde la recta desde el centro del nodo hacia (tx, ty) corta su borde. */
function boundaryPoint(n, tx, ty) {
  const b = nodeBox(n);
  const c = { x: b.x + b.w / 2, y: b.y + b.h / 2 };
  const dx = tx - c.x, dy = ty - c.y;
  if (!dx && !dy) return c;
  const a = b.w / 2, bb = b.h / 2;
  let t;
  if (n.shape === "ellipse" || n.shape === "circle") t = 1 / Math.sqrt((dx / a) ** 2 + (dy / bb) ** 2);
  else if (n.shape === "diamond") t = 1 / (Math.abs(dx) / a + Math.abs(dy) / bb);
  else t = Math.min(a / Math.abs(dx || 1e-9), bb / Math.abs(dy || 1e-9));
  return { x: c.x + dx * t, y: c.y + dy * t };
}

function shapeSVG(n, box, fill, stroke, extra = "") {
  const { x, y, w, h } = box;
  const sw = 2;
  switch (n.shape) {
    case "rect": return `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}" ${extra}/>`;
    case "ellipse": return `<ellipse cx="${x + w / 2}" cy="${y + h / 2}" rx="${w / 2}" ry="${h / 2}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}" ${extra}/>`;
    case "circle": return `<ellipse cx="${x + w / 2}" cy="${y + h / 2}" rx="${w / 2}" ry="${h / 2}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}" ${extra}/>`;
    case "diamond": return `<path d="M${x + w / 2} ${y} L${x + w} ${y + h / 2} L${x + w / 2} ${y + h} L${x} ${y + h / 2}Z" fill="${fill}" stroke="${stroke}" stroke-width="${sw}" stroke-linejoin="round" ${extra}/>`;
    case "note": {
      const f = Math.min(18, w / 5, h / 3);
      return `<path d="M${x} ${y} H${x + w} V${y + h - f} L${x + w - f} ${y + h} H${x}Z" fill="${fill}" stroke="${stroke}" stroke-width="1.5" ${extra}/>` +
        `<path d="M${x + w - f} ${y + h} V${y + h - f} H${x + w}" fill="none" stroke="${stroke}" stroke-width="1.5" opacity=".6"/>`;
    }
    case "text": return `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="transparent" stroke="none" ${extra}/>`;
    default: return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${Math.min(16, h / 2)}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}" ${extra}/>`;
  }
}

function nodeSVG(n, opts = {}) {
  const box = nodeBox(n);
  const L = nodeLayout(n);
  const pal = MAP_COLORS[0];
  const fill = n.fill || pal.fill, stroke = n.stroke || pal.stroke;
  const tc = n.shape === "text" ? (opts.inkText || "#1C2541") : mapTextColor(fill);
  const cx = box.x + box.w / 2;
  const top = box.y + box.h / 2 - (L.lines.length * L.lh) / 2 + L.size * 0.95;
  const text = L.lines.map((ln, i) => `<tspan x="${cx}" y="${top + i * L.lh}">${xmlEsc(ln) || " "}</tspan>`).join("");
  const shadow = opts.shadow && n.shape !== "text" ? shapeSVG(n, { ...box, x: box.x + 2, y: box.y + 3 }, "rgba(28,37,65,.10)", "none") : "";
  return `<g ${opts.attrs || ""}>${shadow}${shapeSVG(n, box, fill, stroke)}` +
    `<text font-family='${MAP_FONT}' font-size="${L.size}" font-weight="${n.bold ? 700 : 400}" fill="${tc}" text-anchor="middle">${text}</text></g>`;
}

function edgeGeometry(e, nodes, edges) {
  const a = nodes.get(e.from), b = nodes.get(e.to);
  if (!a || !b) return null;
  const ca = center(a), cb = center(b);
  // si hay flechas en los dos sentidos entre los mismos nodos, se curvan para que no se superpongan
  const twin = edges.some(o => o.id !== e.id && o.from === e.to && o.to === e.from);
  let bend = 0;
  if (twin) bend = e.from < e.to ? 26 : -26;
  const mx = (ca.x + cb.x) / 2, my = (ca.y + cb.y) / 2;
  const len = Math.hypot(cb.x - ca.x, cb.y - ca.y) || 1;
  const nx = -(cb.y - ca.y) / len, ny = (cb.x - ca.x) / len;
  const ctrl = { x: mx + nx * bend * 2, y: my + ny * bend * 2 };
  const p1 = boundaryPoint(a, bend ? ctrl.x : cb.x, bend ? ctrl.y : cb.y);
  const p2 = boundaryPoint(b, bend ? ctrl.x : ca.x, bend ? ctrl.y : ca.y);
  const d = bend ? `M${p1.x} ${p1.y} Q${ctrl.x} ${ctrl.y} ${p2.x} ${p2.y}` : `M${p1.x} ${p1.y} L${p2.x} ${p2.y}`;
  const mid = bend ? { x: (p1.x + 2 * ctrl.x + p2.x) / 4, y: (p1.y + 2 * ctrl.y + p2.y) / 4 } : { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 };
  return { d, mid };
}

function markerId(color, start) { return `m${start ? "s" : "e"}${color.replace("#", "")}`; }
function markersSVG(colors) {
  return [...colors].map(c => `
    <marker id="${markerId(c, false)}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="${c}"/></marker>
    <marker id="${markerId(c, true)}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="${c}"/></marker>`).join("");
}

function edgeSVG(e, geo, opts = {}) {
  const color = e.stroke || opts.edgeColor || "#4A5470";
  const ends = (e.arrow === "end" || e.arrow === "both" ? `marker-end="url(#${markerId(color, false)})"` : "") +
    (e.arrow === "both" ? ` marker-start="url(#${markerId(color, true)})"` : "");
  let label = "";
  if (e.label) {
    const size = 13.5;
    const lines = wrapLines(e.label, 160, size, false);
    const w = Math.max(...lines.map(l => measure(l, size, false))) + 12;
    const h = lines.length * 17 + 6;
    label = `<rect x="${geo.mid.x - w / 2}" y="${geo.mid.y - h / 2}" width="${w}" height="${h}" rx="5" fill="${opts.labelBg || "#F7F8FB"}"/>` +
      `<text font-family='${MAP_FONT}' font-size="${size}" font-style="italic" fill="${opts.labelInk || "#4A5470"}" text-anchor="middle">` +
      lines.map((l, i) => `<tspan x="${geo.mid.x}" y="${geo.mid.y - h / 2 + 16 + i * 17}">${xmlEsc(l)}</tspan>`).join("") + "</text>";
  }
  return `<g ${opts.attrs || ""}><path d="${geo.d}" fill="none" stroke="transparent" stroke-width="16" class="edge-hit"/>` +
    `<path d="${geo.d}" fill="none" stroke="${color}" stroke-width="2" ${e.dash ? 'stroke-dasharray="7 6"' : ""} ${ends} stroke-linecap="round"/>${label}</g>`;
}

function mapBounds(data) {
  if (!data.nodes.length) return { x: 0, y: 0, w: 400, h: 300 };
  let x1 = Infinity, y1 = Infinity, x2 = -Infinity, y2 = -Infinity;
  for (const n of data.nodes) {
    const b = nodeBox(n);
    x1 = Math.min(x1, b.x); y1 = Math.min(y1, b.y); x2 = Math.max(x2, b.x + b.w); y2 = Math.max(y2, b.y + b.h);
  }
  return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 };
}

/** SVG completo e independiente (miniaturas y exportación). */
function mapToSVG(data, { pad = 40, bg = "#FFFFFF", maxW = null } = {}) {
  const B = mapBounds(data);
  const nodes = new Map(data.nodes.map(n => [n.id, n]));
  const colors = new Set(data.edges.map(e => e.stroke || "#4A5470"));
  const vb = `${B.x - pad} ${B.y - pad} ${B.w + pad * 2} ${B.h + pad * 2}`;
  const size = maxW ? `width="${maxW}"` : `width="${B.w + pad * 2}" height="${B.h + pad * 2}"`;
  const edges = data.edges.map(e => { const g = edgeGeometry(e, nodes, data.edges); return g ? edgeSVG(e, g, { labelBg: bg === "transparent" ? "#FFFFFF" : bg }) : ""; }).join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb}" ${size}>` +
    `<defs>${markersSVG(colors)}</defs><rect x="${B.x - pad}" y="${B.y - pad}" width="${B.w + pad * 2}" height="${B.h + pad * 2}" fill="${bg}"/>` +
    edges + data.nodes.map(n => nodeSVG(n)).join("") + "</svg>";
}

/** Ubica automáticamente un grafo (conceptos + relaciones) en niveles, de lo general a lo particular. */
function layoutGraph(graph) {
  const names = graph.concepts;
  const idOf = new Map(names.map(c => [c.toLowerCase(), "n" + mapUid()]));
  const root = names[0].toLowerCase();
  const children = new Map(names.map(c => [c.toLowerCase(), []]));
  for (const l of graph.links) children.get(l.from.toLowerCase())?.push(l.to.toLowerCase());
  const depth = new Map([[root, 0]]);
  const queue = [root];
  while (queue.length) {
    const c = queue.shift();
    for (const k of children.get(c) || []) if (!depth.has(k)) { depth.set(k, depth.get(c) + 1); queue.push(k); }
  }
  const links = [...graph.links];
  for (const c of names) {
    const k = c.toLowerCase();
    if (!depth.has(k)) { depth.set(k, 1); links.push({ from: names[0], to: c, label: "" }); }
  }
  const levels = [];
  for (const c of names) { const d = depth.get(c.toLowerCase()); (levels[d] = levels[d] || []).push(c); }
  const nodes = [];
  const pos = new Map();
  let yRow = 0;
  levels.forEach((fullRow, d) => {
    if (!fullRow) return;
    // filas de hasta 5 conceptos: si un nivel tiene más, se reparte en varias filas
    for (let k = 0; k < fullRow.length; k += 5) placeRow(fullRow.slice(k, k + 5), d, yRow++);
  });
  function placeRow(row, d, yi) {
    // ordenar cada fila según la posición de sus padres, para que las flechas no se crucen tanto
    row.sort((a, b) => {
      const px = c => { const ps = links.filter(l => l.to.toLowerCase() === c.toLowerCase() && pos.has(l.from.toLowerCase())).map(l => pos.get(l.from.toLowerCase())); return ps.length ? ps.reduce((s, x) => s + x, 0) / ps.length : 0; };
      return px(a) - px(b);
    });
    const widths = row.map(c => Math.min(230, Math.max(120, measure(c, d === 0 ? 19 : 16, d === 0) + 40)));
    const gap = 70;
    const total = widths.reduce((s, w) => s + w, 0) + gap * (row.length - 1);
    let x = -total / 2;
    row.forEach((c, i) => {
      const w = widths[i];
      const n = { id: idOf.get(c.toLowerCase()), x: Math.round(x), y: yi * 150, w, h: d === 0 ? 64 : 54, shape: d === 0 ? "ellipse" : "round",
        text: c, fill: d === 0 ? MAP_COLORS[1].fill : (d === 1 ? MAP_COLORS[2].fill : MAP_COLORS[0].fill),
        stroke: d === 0 ? MAP_COLORS[1].stroke : (d === 1 ? MAP_COLORS[2].stroke : MAP_COLORS[0].stroke),
        bold: d === 0, size: d === 0 ? 19 : 16 };
      nodes.push(n);
      pos.set(c.toLowerCase(), x + w / 2);
      x += w + gap;
    });
  }
  const edges = links.filter(l => idOf.has(l.from.toLowerCase()) && idOf.has(l.to.toLowerCase()) && l.from.toLowerCase() !== l.to.toLowerCase())
    .map(l => ({ id: "e" + mapUid(), from: idOf.get(l.from.toLowerCase()), to: idOf.get(l.to.toLowerCase()), label: l.label || "", arrow: "end", dash: false }));
  return { nodes, edges, view: { x: 0, y: 0, zoom: 1 } };
}

// --------------------------------------------------------------------------- //
// Lista de mapas
// --------------------------------------------------------------------------- //
async function viewMaps(params) {
  setTitle("Mapas conceptuales");
  if (params.get("tema")) { await newMapFromTopic(+params.get("tema")); return; }
  const [maps, topics] = await Promise.all([api("/api/maps"), api("/api/topics").catch(() => [])]);
  main.innerHTML = `
    <div class="page wide">
      <div class="page-head">
        <h1>Mapas conceptuales</h1>
        <p class="lead">Organizá los conceptos de un tema con cuadros, círculos y flechas que digan cómo se relacionan. Armar el mapa con tus palabras es una forma de elaboración: te obliga a entender las conexiones, no solo a recordar datos.</p>
      </div>
      <div class="map-start">
        <button class="map-start-card" id="map-blank">
          <svg viewBox="0 0 64 40" aria-hidden="true"><rect x="22" y="3" width="20" height="10" rx="3"/><rect x="4" y="27" width="20" height="10" rx="3"/><rect x="40" y="27" width="20" height="10" rx="3"/><path d="M28 13 16 27M36 13l12 14"/></svg>
          <b>Mapa en blanco</b><span>Empezá desde cero con tus propios conceptos.</span></button>
        <div class="map-start-card as-form">
          <svg viewBox="0 0 64 40" aria-hidden="true"><path d="M8 20h14M42 20h14" stroke-dasharray="3 3"/><circle cx="32" cy="20" r="10"/><path d="m28 20 3 3 5-6"/></svg>
          <b>Generar desde un tema</b>
          <span>La app arma un borrador con los conceptos del tema${STATUS && STATUS.ai_enabled ? " (con IA)" : ""}; después lo corregís y completás.</span>
          ${topics.length ? `<div class="row" style="margin-top:10px;gap:8px">
            <select class="input" id="map-topic" style="flex:1;min-width:0">${topics.map(t => `<option value="${t.id}">${esc(t.title)}</option>`).join("")}</select>
            <button class="btn primary" id="map-gen">Generar</button></div>`
            : `<p class="small muted" style="margin-top:8px">Primero creá un tema en <a href="#/nuevo">Nuevo tema</a>.</p>`}
        </div>
      </div>
      <h2 class="section-title">Tus mapas</h2>
      ${maps.length ? `<div class="map-grid">${maps.map(m => `
        <a class="map-card" href="#/mapas/${m.id}">
          <span class="map-thumb" data-thumb="${m.id}"></span>
          <span class="map-card-body"><b>${esc(m.title)}</b>
          <span class="small muted">${plural(m.nodes, "concepto", "conceptos")} · ${plural(m.edges, "relación", "relaciones")}${m.topic_title ? ` · ${esc(m.topic_title)}` : ""}</span></span>
        </a>`).join("")}</div>`
        : `<div class="empty"><h3>Todavía no hay mapas</h3><p class="muted">Creá uno en blanco o generá un borrador desde un tema.</p></div>`}
    </div>`;
  $("#map-blank").addEventListener("click", async () => {
    const m = await api("/api/maps", { method: "POST", body: { title: "Mapa sin título", data: { nodes: [{ id: "n" + mapUid(), x: -90, y: -30, w: 180, h: 60, shape: "ellipse", text: "Concepto central", fill: MAP_COLORS[1].fill, stroke: MAP_COLORS[1].stroke, bold: true, size: 18 }], edges: [] } } });
    location.hash = `#/mapas/${m.id}`;
  });
  $("#map-gen")?.addEventListener("click", () => newMapFromTopic(+$("#map-topic").value));
  // miniaturas
  for (const m of maps.slice(0, 40)) {
    api(`/api/maps/${m.id}`).then(full => {
      const el = $(`[data-thumb="${m.id}"]`);
      if (el && full.data.nodes?.length) el.innerHTML = mapToSVG(full.data, { pad: 24, bg: "transparent" }).replace(/width="[^"]*"( height="[^"]*")?/, 'width="100%" height="100%"');
    }).catch(() => {});
  }
}

async function newMapFromTopic(topicId) {
  main.innerHTML = `<div class="page narrow"><p class="muted"><span class="loader"></span> Armando el borrador del mapa con los conceptos del tema…</p></div>`;
  const g = await api(`/api/topics/${topicId}/concept-map`, { method: "POST" });
  const data = layoutGraph(g);
  const m = await api("/api/maps", { method: "POST", body: { title: `Mapa: ${g.title}`, topic_id: topicId, data } });
  toast(g.by === "heuristica" ? "Borrador listo: revisá las relaciones y completá las frases de enlace" : `Borrador generado con ${g.by}: revisalo y ajustalo`);
  location.hash = `#/mapas/${m.id}?nuevo=1`;
}

// --------------------------------------------------------------------------- //
// Editor
// --------------------------------------------------------------------------- //
async function viewMapEditor(id, params) {
  const [m, topics] = await Promise.all([api(`/api/maps/${id}`), api("/api/topics").catch(() => [])]);
  setTitle(m.title);
  document.body.classList.add("map-mode");
  const data = { nodes: m.data.nodes || [], edges: m.data.edges || [], view: m.data.view || { x: 0, y: 0, zoom: 1 } };
  let tool = "select";
  let selected = new Set();       // ids de nodos y flechas seleccionados
  let editing = null;
  const undo = [], redo = [];
  let saveTimer = null, dirty = false;
  let ptr = null;                 // gesto en curso

  main.innerHTML = `
    <div class="map-editor">
      <div class="map-top">
        <a class="btn ghost small" href="#/mapas">← Mapas</a>
        <input class="map-title" id="map-title" value="${esc(m.title)}" maxlength="200" aria-label="Título del mapa">
        <select class="input map-topic-pick" id="map-topic-pick" aria-label="Tema">
          <option value="0">Sin tema</option>${topics.map(t => `<option value="${t.id}" ${m.topic_id === t.id ? "selected" : ""}>${esc(t.title)}</option>`).join("")}
        </select>
        <span class="small muted" id="map-status">Guardado</span>
        <span class="grow"></span>
        <button class="btn small" id="map-png">Descargar PNG</button>
        <button class="btn small" id="map-svg">SVG</button>
        <button class="btn ghost small danger" id="map-del">Borrar</button>
      </div>
      <div class="map-tools" role="toolbar" aria-label="Herramientas">
        <button class="tool" data-tool="select" title="Seleccionar y mover (V)"><svg viewBox="0 0 24 24"><path d="M5 3l14 8-6 2-2 6z"/></svg></button>
        <span class="tool-sep"></span>
        ${MAP_SHAPES.map(([k, l]) => `<button class="tool" data-tool="${k}" title="${l}: tocá el lienzo para ubicarlo"><svg viewBox="0 0 24 24">${SHAPE_ICONS[k]}</svg></button>`).join("")}
        <span class="tool-sep"></span>
        <button class="tool" data-tool="connect" title="Flecha: arrastrá de un concepto a otro (C)"><svg viewBox="0 0 24 24"><path d="M4 18 18 6M11 6h7v7"/></svg></button>
        <span class="tool-sep"></span>
        <button class="tool" id="t-undo" title="Deshacer (Ctrl+Z)"><svg viewBox="0 0 24 24"><path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/></svg></button>
        <button class="tool" id="t-redo" title="Rehacer (Ctrl+Y)"><svg viewBox="0 0 24 24"><path d="m15 14 5-5-5-5"/><path d="M20 9H10a6 6 0 0 0 0 12h3"/></svg></button>
        <span class="tool-sep"></span>
        <button class="tool" id="t-zout" title="Alejar"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6"/><path d="m16 16 4 4M8 11h6"/></svg></button>
        <button class="tool zoom-label" id="t-zfit" title="Ver todo el mapa">100%</button>
        <button class="tool" id="t-zin" title="Acercar"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6"/><path d="m16 16 4 4M8 11h6M11 8v6"/></svg></button>
      </div>
      <div class="map-body">
        <div class="map-canvas" id="map-canvas" tabindex="0" aria-label="Lienzo del mapa conceptual">
          <svg id="map-svg-el" xmlns="http://www.w3.org/2000/svg"></svg>
        </div>
        <aside class="map-props" id="map-props" aria-label="Propiedades"></aside>
      </div>
    </div>`;

  const canvas = $("#map-canvas");
  const svg = $("#map-svg-el");
  const props = $("#map-props");
  const nodeById = () => new Map(data.nodes.map(n => [n.id, n]));

  // ---------- historial y guardado ----------
  const snap = () => JSON.stringify({ nodes: data.nodes, edges: data.edges });
  function record() { undo.push(snap()); if (undo.length > 120) undo.shift(); redo.length = 0; }
  function restore(s) { const o = JSON.parse(s); data.nodes = o.nodes; data.edges = o.edges; selected = new Set([...selected].filter(i => data.nodes.some(n => n.id === i) || data.edges.some(e => e.id === i))); changed(); }
  function changed() { render(); renderProps(); scheduleSave(); }
  function scheduleSave() {
    dirty = true;
    $("#map-status").textContent = "Cambios sin guardar";
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveNow, 800);
  }
  async function saveNow() {
    clearTimeout(saveTimer);
    if (!dirty) return;
    dirty = false;
    $("#map-status").textContent = "Guardando…";
    try { await api(`/api/maps/${id}`, { method: "PUT", body: { data } }); $("#map-status").textContent = dirty ? "Cambios sin guardar" : "Guardado"; }
    catch (e) { dirty = true; $("#map-status").textContent = "No se pudo guardar: " + e.message; }
  }

  // ---------- coordenadas ----------
  function toWorld(ev) {
    const r = canvas.getBoundingClientRect();
    return { x: (ev.clientX - r.left - data.view.x) / data.view.zoom, y: (ev.clientY - r.top - data.view.y) / data.view.zoom };
  }
  function toScreen(p) { return { x: p.x * data.view.zoom + data.view.x, y: p.y * data.view.zoom + data.view.y }; }
  function fit() {
    const r = canvas.getBoundingClientRect();
    if (!data.nodes.length) { data.view = { x: r.width / 2, y: r.height / 2, zoom: 1 }; return; }
    const B = mapBounds(data);
    const z = Math.min(1.4, Math.max(0.2, Math.min((r.width - 80) / (B.w || 1), (r.height - 80) / (B.h || 1))));
    data.view = { zoom: z, x: r.width / 2 - (B.x + B.w / 2) * z, y: r.height / 2 - (B.y + B.h / 2) * z };
  }

  // ---------- dibujo ----------
  const dark = () => document.documentElement.dataset.theme === "dark" ||
    (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
  function render() {
    const nodes = nodeById();
    const D = dark();
    const edgeColor = D ? "#B4BCD3" : "#4A5470";
    const colors = new Set([edgeColor, "#2340C8", ...data.edges.map(e => e.stroke || edgeColor)]);
    const v = data.view;
    const grid = 24 * v.zoom;
    let out = `<defs>${markersSVG(colors)}
      <pattern id="dots" width="${grid}" height="${grid}" patternUnits="userSpaceOnUse" x="${v.x % grid}" y="${v.y % grid}">
        <circle cx="1" cy="1" r="1" fill="${D ? "#2B3552" : "#D3DAE8"}"/></pattern></defs>
      <rect width="100%" height="100%" fill="url(#dots)"/>
      <g transform="translate(${v.x} ${v.y}) scale(${v.zoom})">`;
    for (const e of data.edges) {
      const g = edgeGeometry(e, nodes, data.edges);
      if (!g) continue;
      const sel = selected.has(e.id);
      out += edgeSVG({ ...e, stroke: sel ? "#2340C8" : e.stroke }, g, { attrs: `data-edge="${e.id}" class="m-edge${sel ? " sel" : ""}"`, edgeColor,
        labelBg: D ? "#121726" : "#F7F8FB", labelInk: D ? "#B4BCD3" : "#4A5470" });
    }
    for (const n of data.nodes) {
      const sel = selected.has(n.id);
      out += nodeSVG(n, { attrs: `data-node="${n.id}" class="m-node${sel ? " sel" : ""}"`, shadow: true, inkText: D ? "#E6EAF5" : "#1C2541" });
      if (sel) {
        const b = nodeBox(n);
        out += `<rect x="${b.x - 5}" y="${b.y - 5}" width="${b.w + 10}" height="${b.h + 10}" rx="8" fill="none" stroke="#2340C8" stroke-width="${1.5 / v.zoom}" stroke-dasharray="${5 / v.zoom} ${4 / v.zoom}" pointer-events="none"/>`;
        if (selected.size === 1) {
          const hs = 10 / v.zoom;
          out += `<rect data-resize="${n.id}" x="${b.x + b.w - hs / 2 + 5}" y="${b.y + b.h - hs / 2 + 5}" width="${hs}" height="${hs}" fill="#fff" stroke="#2340C8" stroke-width="${1.5 / v.zoom}" style="cursor:nwse-resize"/>`;
          out += `<g data-link="${n.id}" style="cursor:crosshair"><circle cx="${b.x + b.w + 20 / v.zoom}" cy="${b.y + b.h / 2}" r="${11 / v.zoom}" fill="#2340C8"/>` +
            `<path d="M${b.x + b.w + 15 / v.zoom} ${b.y + b.h / 2}h${10 / v.zoom}m${-4 / v.zoom} ${-4 / v.zoom}l${4 / v.zoom} ${4 / v.zoom}l${-4 / v.zoom} ${4 / v.zoom}" stroke="#fff" stroke-width="${2 / v.zoom}" fill="none"/></g>`;
        }
      }
    }
    if (ptr && ptr.kind === "link" && ptr.to) {
      const a = nodes.get(ptr.from);
      const p1 = boundaryPoint(a, ptr.to.x, ptr.to.y);
      out += `<path d="M${p1.x} ${p1.y} L${ptr.to.x} ${ptr.to.y}" stroke="#2340C8" stroke-width="${2 / v.zoom}" stroke-dasharray="${6 / v.zoom} ${5 / v.zoom}" marker-end="url(#${markerId("#2340C8", false)})"/>`;
    }
    if (ptr && ptr.kind === "marquee") {
      const x = Math.min(ptr.start.x, ptr.cur.x), y = Math.min(ptr.start.y, ptr.cur.y);
      out += `<rect x="${x}" y="${y}" width="${Math.abs(ptr.cur.x - ptr.start.x)}" height="${Math.abs(ptr.cur.y - ptr.start.y)}" fill="rgba(35,64,200,.08)" stroke="#2340C8" stroke-width="${1 / v.zoom}"/>`;
    }
    out += "</g>";
    svg.innerHTML = out;
    $("#t-zfit").textContent = Math.round(v.zoom * 100) + "%";
    $$(".tool[data-tool]").forEach(b => b.setAttribute("aria-pressed", b.dataset.tool === tool));
    canvas.dataset.tool = tool;
    if (!data.nodes.length) {
      svg.insertAdjacentHTML("beforeend", `<text x="50%" y="50%" text-anchor="middle" fill="${D ? "#8790AB" : "#7A839C"}" font-family='${MAP_FONT}' font-size="16">Hacé doble clic en el lienzo para crear el primer concepto</text>`);
    }
  }

  // ---------- panel de propiedades ----------
  function renderProps() {
    const nodes = data.nodes.filter(n => selected.has(n.id));
    const edges = data.edges.filter(e => selected.has(e.id));
    if (!nodes.length && !edges.length) {
      props.innerHTML = `<h3>Cómo se usa</h3>
        <ul class="map-help">
          <li><b>Doble clic</b> en el lienzo: nuevo concepto.</li>
          <li>Elegí una forma arriba y tocá el lienzo para ubicarla.</li>
          <li><b>Arrastrá el punto azul</b> de un concepto hasta otro para unirlos con una flecha; si lo soltás en el vacío, se crea un concepto nuevo ya conectado.</li>
          <li><b>Doble clic</b> en un concepto o en una flecha: escribir. En las flechas va la <b>frase de enlace</b> («es un», «produce», «se divide en»).</li>
          <li>Arrastrá el fondo para moverte; rueda del mouse para acercar. <kbd>Shift</kbd> + arrastrar selecciona varios.</li>
          <li><kbd>Tab</kbd> crea un concepto hijo; <kbd>Supr</kbd> borra; <kbd>Ctrl</kbd>+<kbd>D</kbd> duplica; <kbd>Ctrl</kbd>+<kbd>Z</kbd> deshace.</li>
        </ul>
        <p class="small muted">Consejo: leé cada flecha en voz alta como una oración («la fotosíntesis <i>ocurre en</i> los cloroplastos»). Si no tiene sentido, la relación está mal planteada.</p>`;
      return;
    }
    if (nodes.length) {
      const n = nodes[0];
      props.innerHTML = `
        <h3>${nodes.length > 1 ? plural(nodes.length, "concepto", "conceptos") : "Concepto"}</h3>
        <div class="prop-label">Forma</div>
        <div class="shape-pick">${MAP_SHAPES.map(([k, l]) => `<button data-shape="${k}" title="${l}" aria-label="${l}" aria-pressed="${nodes.every(x => x.shape === k)}"><svg viewBox="0 0 24 24">${SHAPE_ICONS[k]}</svg></button>`).join("")}</div>
        <div class="prop-label">Color</div>
        <div class="color-pick">${MAP_COLORS.map((c, i) => `<button data-color="${i}" title="${c.name}" aria-label="${c.name}" style="background:${c.fill};border-color:${c.stroke}" aria-pressed="${(n.fill || "#FFFFFF") === c.fill}"></button>`).join("")}</div>
        <div class="prop-label">Texto</div>
        <div class="seg small-seg">${[[13, "Chico"], [16, "Normal"], [20, "Grande"], [26, "Título"]].map(([s, l]) => `<button data-size="${s}" aria-pressed="${(n.size || 16) === s}">${l}</button>`).join("")}</div>
        <label class="check" style="margin-top:8px"><input type="checkbox" id="p-bold" ${n.bold ? "checked" : ""}> Negrita</label>
        <div class="stack" style="--gap:8px;margin-top:16px">
          ${nodes.length === 1 ? `<button class="btn small" id="p-edit">Escribir texto</button><button class="btn small" id="p-child">Agregar concepto hijo (Tab)</button>` : ""}
          <button class="btn small" id="p-dup">Duplicar</button>
          <button class="btn ghost small danger" id="p-del">Borrar</button>
        </div>`;
      $$("[data-shape]", props).forEach(b => b.addEventListener("click", () => { record(); nodes.forEach(x => { x.shape = b.dataset.shape; if (x.shape === "circle") x.h = x.w; }); changed(); }));
      $$("[data-color]", props).forEach(b => b.addEventListener("click", () => { record(); const c = MAP_COLORS[+b.dataset.color]; nodes.forEach(x => { x.fill = c.fill; x.stroke = c.stroke; }); changed(); }));
      $$("[data-size]", props).forEach(b => b.addEventListener("click", () => { record(); nodes.forEach(x => { x.size = +b.dataset.size; }); changed(); }));
      $("#p-bold").addEventListener("change", e => { record(); nodes.forEach(x => { x.bold = e.target.checked; }); changed(); });
      $("#p-edit")?.addEventListener("click", () => startEditNode(n));
      $("#p-child")?.addEventListener("click", () => addChild(n));
      $("#p-dup").addEventListener("click", duplicate);
      $("#p-del").addEventListener("click", removeSelected);
      return;
    }
    const e = edges[0];
    props.innerHTML = `
      <h3>Flecha</h3>
      <label class="field"><span>Frase de enlace</span><input class="input" id="p-label" value="${esc(e.label)}" maxlength="120" placeholder="es un, produce, se divide en…"></label>
      <div class="prop-label">Puntas</div>
      <div class="seg small-seg">${[["end", "→"], ["both", "↔"], ["none", "—"]].map(([k, l]) => `<button data-arrow="${k}" aria-pressed="${e.arrow === k}" title="${{ end: "Una punta", both: "Dos puntas", none: "Sin puntas" }[k]}">${l}</button>`).join("")}</div>
      <label class="check" style="margin-top:10px"><input type="checkbox" id="p-dash" ${e.dash ? "checked" : ""}> Línea punteada</label>
      <div class="prop-label">Color</div>
      <div class="color-pick">${MAP_COLORS.map((c, i) => `<button data-ecolor="${i}" title="${c.name}" aria-label="${c.name}" style="background:${c.stroke};border-color:${c.stroke}"></button>`).join("")}</div>
      <div class="stack" style="--gap:8px;margin-top:16px">
        <button class="btn small" id="p-flip">Invertir sentido</button>
        <button class="btn ghost small danger" id="p-del">Borrar flecha</button>
      </div>`;
    const lab = $("#p-label");
    lab.addEventListener("focus", () => record(), { once: true });
    lab.addEventListener("input", () => { edges.forEach(x => { x.label = lab.value; }); render(); scheduleSave(); });
    $$("[data-arrow]", props).forEach(b => b.addEventListener("click", () => { record(); edges.forEach(x => { x.arrow = b.dataset.arrow; }); changed(); }));
    $("#p-dash").addEventListener("change", ev => { record(); edges.forEach(x => { x.dash = ev.target.checked; }); changed(); });
    $$("[data-ecolor]", props).forEach(b => b.addEventListener("click", () => { record(); const c = MAP_COLORS[+b.dataset.ecolor]; edges.forEach(x => { x.stroke = c.stroke === "#1C2541" ? null : c.stroke; }); changed(); }));
    $("#p-flip").addEventListener("click", () => { record(); edges.forEach(x => { [x.from, x.to] = [x.to, x.from]; }); changed(); });
    $("#p-del").addEventListener("click", removeSelected);
  }

  // ---------- acciones ----------
  function addNode(p, shape = "round", text = "", extra = {}) {
    const w = shape === "circle" ? 110 : shape === "text" ? 160 : 170;
    const h = shape === "circle" ? 110 : shape === "diamond" ? 90 : 56;
    const pal = shape === "note" ? MAP_COLORS[3] : MAP_COLORS[0];
    const n = { id: "n" + mapUid(), x: Math.round(p.x - w / 2), y: Math.round(p.y - h / 2), w, h, shape, text, fill: pal.fill, stroke: pal.stroke, bold: false, size: 16, ...extra };
    data.nodes.push(n);
    return n;
  }
  function addChild(parent, at = null) {
    record();
    const b = nodeBox(parent);
    const kids = data.edges.filter(e => e.from === parent.id).length;
    const p = at || { x: b.x + b.w / 2 + (kids % 2 ? 1 : -1) * Math.ceil(kids / 2) * 200, y: b.y + b.h + 120 };
    const n = addNode(p, "round", "", { fill: parent.fill === MAP_COLORS[1].fill ? MAP_COLORS[2].fill : parent.fill, stroke: parent.fill === MAP_COLORS[1].fill ? MAP_COLORS[2].stroke : parent.stroke });
    data.edges.push({ id: "e" + mapUid(), from: parent.id, to: n.id, label: "", arrow: "end", dash: false });
    selected = new Set([n.id]);
    changed();
    startEditNode(n, true);
  }
  function removeSelected() {
    if (!selected.size) return;
    record();
    data.nodes = data.nodes.filter(n => !selected.has(n.id));
    const alive = new Set(data.nodes.map(n => n.id));
    data.edges = data.edges.filter(e => !selected.has(e.id) && alive.has(e.from) && alive.has(e.to));
    selected.clear();
    changed();
  }
  function duplicate() {
    const nodes = data.nodes.filter(n => selected.has(n.id));
    if (!nodes.length) return;
    record();
    const map = new Map();
    for (const n of nodes) { const c = { ...n, id: "n" + mapUid(), x: n.x + 30, y: n.y + 30 }; map.set(n.id, c.id); data.nodes.push(c); }
    for (const e of data.edges.filter(e => map.has(e.from) && map.has(e.to))) data.edges.push({ ...e, id: "e" + mapUid(), from: map.get(e.from), to: map.get(e.to) });
    selected = new Set(map.values());
    changed();
  }

  // ---------- edición de texto en el lugar ----------
  function startEditNode(n, isNew = false) {
    finishEdit();
    const b = nodeBox(n);
    const tl = toScreen({ x: b.x, y: b.y });
    const ta = document.createElement("textarea");
    ta.className = "map-edit";
    ta.value = n.text;
    const z = data.view.zoom;
    Object.assign(ta.style, { left: tl.x + "px", top: tl.y + "px", width: b.w * z + "px", minHeight: b.h * z + "px", fontSize: (n.size || 16) * z + "px", fontWeight: n.bold ? 700 : 400 });
    canvas.appendChild(ta);
    ta.focus(); ta.select();
    const before = snap();
    editing = { el: ta, commit: () => {
      const v = ta.value.trim();
      if (v !== n.text) { undo.push(before); redo.length = 0; n.text = v; }
      if (isNew && !v) { data.nodes = data.nodes.filter(x => x.id !== n.id); data.edges = data.edges.filter(e => e.from !== n.id && e.to !== n.id); selected.delete(n.id); }
      changed();
    } };
    ta.addEventListener("keydown", ev => {
      ev.stopPropagation();
      if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); finishEdit(); canvas.focus(); }
      else if (ev.key === "Escape") { ta.value = n.text; finishEdit(); canvas.focus(); }
      else if (ev.key === "Tab") { ev.preventDefault(); finishEdit(); addChild(n); }
    });
    ta.addEventListener("blur", () => finishEdit());
  }
  function startEditEdge(e) {
    selected = new Set([e.id]);
    render(); renderProps();
    const lab = $("#p-label");
    if (lab) { lab.focus(); lab.select(); }
  }
  function finishEdit() {
    if (!editing) return;
    const ed = editing;
    editing = null;
    ed.el.remove();
    ed.commit();
  }

  // ---------- gestos con el puntero ----------
  const pointers = new Map();
  let lastDown = { t: 0, x: 0, y: 0 };
  function doubleClick(ev) {
    const nodeEl = ev.target.closest("[data-node]");
    const edgeEl = ev.target.closest("[data-edge]");
    if (nodeEl) { const n = data.nodes.find(x => x.id === nodeEl.dataset.node); selected = new Set([n.id]); render(); renderProps(); startEditNode(n); return; }
    if (edgeEl) { startEditEdge(data.edges.find(e => e.id === edgeEl.dataset.edge)); return; }
    record();
    const n = addNode(toWorld(ev), "round");
    selected = new Set([n.id]);
    changed();
    startEditNode(n, true);
  }
  canvas.addEventListener("pointerdown", ev => {
    if (ev.target.closest(".map-edit")) return;
    finishEdit();
    // el SVG se redibuja en cada clic, así que el doble clic se detecta acá (y funciona igual con el dedo)
    const now = performance.now();
    const isDouble = now - lastDown.t < 380 && Math.hypot(ev.clientX - lastDown.x, ev.clientY - lastDown.y) < 8 && pointers.size === 0;
    lastDown = { t: isDouble ? 0 : now, x: ev.clientX, y: ev.clientY };
    if (isDouble && !ev.target.closest("[data-link],[data-resize]")) { ev.preventDefault(); doubleClick(ev); return; }
    canvas.focus({ preventScroll: true });
    pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
    if (pointers.size === 2) {  // dos dedos: zoom
      const [a, b] = [...pointers.values()];
      ptr = { kind: "pinch", dist: Math.hypot(a.x - b.x, a.y - b.y), zoom: data.view.zoom, view: { ...data.view } };
      return;
    }
    canvas.setPointerCapture(ev.pointerId);
    const p = toWorld(ev);
    const resize = ev.target.closest("[data-resize]");
    const link = ev.target.closest("[data-link]");
    const nodeEl = ev.target.closest("[data-node]");
    const edgeEl = ev.target.closest("[data-edge]");
    if (resize) { const n = data.nodes.find(x => x.id === resize.dataset.resize); ptr = { kind: "resize", n, start: p, w: n.w, h: nodeBox(n).h, before: snap() }; return; }
    if (link || (tool === "connect" && nodeEl)) { ptr = { kind: "link", from: (link || nodeEl).dataset.link || nodeEl.dataset.node, to: p }; render(); return; }
    if (MAP_SHAPES.some(([k]) => k === tool) && !nodeEl) {
      record();
      const n = addNode(p, tool);
      selected = new Set([n.id]);
      tool = "select";
      changed();
      startEditNode(n, true);
      return;
    }
    if (nodeEl) {
      const id = nodeEl.dataset.node;
      if (ev.shiftKey || ev.ctrlKey || ev.metaKey) { selected.has(id) ? selected.delete(id) : selected.add(id); }
      else if (!selected.has(id)) selected = new Set([id]);
      const moving = data.nodes.filter(n => selected.has(n.id));
      ptr = { kind: "move", start: p, orig: moving.map(n => [n, n.x, n.y]), before: snap(), moved: false };
      render(); renderProps();
      return;
    }
    if (edgeEl) { selected = new Set([edgeEl.dataset.edge]); render(); renderProps(); ptr = null; return; }
    if (ev.shiftKey) { ptr = { kind: "marquee", start: p, cur: p }; return; }
    selected.clear();
    render(); renderProps();
    ptr = { kind: "pan", sx: ev.clientX, sy: ev.clientY, view: { ...data.view } };
  });
  canvas.addEventListener("pointermove", ev => {
    if (pointers.has(ev.pointerId)) pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
    if (!ptr) return;
    if (ptr.kind === "pinch" && pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      const z = Math.min(4, Math.max(0.15, ptr.zoom * Math.hypot(a.x - b.x, a.y - b.y) / ptr.dist));
      const r = canvas.getBoundingClientRect();
      const cx = (a.x + b.x) / 2 - r.left, cy = (a.y + b.y) / 2 - r.top;
      const wx = (cx - ptr.view.x) / ptr.view.zoom, wy = (cy - ptr.view.y) / ptr.view.zoom;
      data.view = { zoom: z, x: cx - wx * z, y: cy - wy * z };
      render();
      return;
    }
    const p = toWorld(ev);
    if (ptr.kind === "pan") { data.view.x = ptr.view.x + ev.clientX - ptr.sx; data.view.y = ptr.view.y + ev.clientY - ptr.sy; render(); }
    else if (ptr.kind === "move") {
      const dx = p.x - ptr.start.x, dy = p.y - ptr.start.y;
      if (Math.abs(dx) + Math.abs(dy) > 2) ptr.moved = true;
      const snapTo = v => (ev.altKey ? v : Math.round(v / 6) * 6);
      ptr.orig.forEach(([n, x, y]) => { n.x = snapTo(x + dx); n.y = snapTo(y + dy); });
      render();
    } else if (ptr.kind === "resize") {
      ptr.n.w = Math.max(40, Math.round(ptr.w + p.x - ptr.start.x));
      ptr.n.h = Math.max(30, Math.round(ptr.h + p.y - ptr.start.y));
      if (ptr.n.shape === "circle") ptr.n.h = ptr.n.w;
      render();
    } else if (ptr.kind === "link") { ptr.to = p; render(); }
    else if (ptr.kind === "marquee") { ptr.cur = p; render(); }
  });
  const endPointer = ev => {
    pointers.delete(ev.pointerId);
    if (!ptr) return;
    const g = ptr;
    ptr = null;
    if (g.kind === "pinch") { scheduleSave(); return; }
    if (g.kind === "move" && g.moved) { undo.push(g.before); redo.length = 0; scheduleSave(); }
    else if (g.kind === "resize") { undo.push(g.before); redo.length = 0; scheduleSave(); }
    else if (g.kind === "pan") scheduleSave();
    else if (g.kind === "link") {
      const target = document.elementFromPoint(ev.clientX, ev.clientY)?.closest("[data-node]");
      const from = data.nodes.find(n => n.id === g.from);
      if (target && target.dataset.node !== g.from) {
        if (!data.edges.some(e => e.from === g.from && e.to === target.dataset.node)) {
          record();
          const e = { id: "e" + mapUid(), from: g.from, to: target.dataset.node, label: "", arrow: "end", dash: false };
          data.edges.push(e);
          changed();
          startEditEdge(e);
        }
      } else if (from && g.to && Math.hypot(g.to.x - center(from).x, g.to.y - center(from).y) > 60) {
        addChild(from, g.to);  // soltado en el vacío: concepto nuevo ya conectado
      } else render();
    } else if (g.kind === "marquee") {
      const x1 = Math.min(g.start.x, g.cur.x), x2 = Math.max(g.start.x, g.cur.x), y1 = Math.min(g.start.y, g.cur.y), y2 = Math.max(g.start.y, g.cur.y);
      selected = new Set(data.nodes.filter(n => { const b = nodeBox(n); return b.x >= x1 && b.y >= y1 && b.x + b.w <= x2 && b.y + b.h <= y2; }).map(n => n.id));
      render(); renderProps();
    }
  };
  canvas.addEventListener("pointerup", endPointer);
  canvas.addEventListener("pointercancel", endPointer);
  canvas.addEventListener("wheel", ev => {
    ev.preventDefault();
    const r = canvas.getBoundingClientRect();
    const cx = ev.clientX - r.left, cy = ev.clientY - r.top;
    if (ev.shiftKey) {
      data.view.x -= ev.deltaY || ev.deltaX;  // Shift + rueda: desplazar de costado
    } else {
      const unit = ev.deltaMode === 1 ? 40 : 1;  // algunos mouse informan líneas en vez de píxeles
      const z = Math.min(4, Math.max(0.15, data.view.zoom * Math.exp(-ev.deltaY * unit * (ev.ctrlKey ? 0.01 : 0.0015))));
      const wx = (cx - data.view.x) / data.view.zoom, wy = (cy - data.view.y) / data.view.zoom;
      data.view = { zoom: z, x: cx - wx * z, y: cy - wy * z };
    }
    render();
    scheduleSave();
  }, { passive: false });

  // ---------- teclado ----------
  canvas.addEventListener("keydown", ev => {
    if (editing) return;
    const ctrl = ev.ctrlKey || ev.metaKey;
    const k = ev.key.toLowerCase();
    if ((ev.key === "Delete" || ev.key === "Backspace") && selected.size) { ev.preventDefault(); removeSelected(); }
    else if (ctrl && k === "z" && !ev.shiftKey) { ev.preventDefault(); if (undo.length) { redo.push(snap()); restore(undo.pop()); } }
    else if (ctrl && (k === "y" || (k === "z" && ev.shiftKey))) { ev.preventDefault(); if (redo.length) { undo.push(snap()); restore(redo.pop()); } }
    else if (ctrl && k === "d") { ev.preventDefault(); duplicate(); }
    else if (ctrl && k === "a") { ev.preventDefault(); selected = new Set(data.nodes.map(n => n.id)); render(); renderProps(); }
    else if (ev.key === "Tab") {
      ev.preventDefault();
      const n = data.nodes.find(x => selected.has(x.id));
      if (n) addChild(n);
    } else if (ev.key === "Enter" || ev.key === "F2") {
      const n = data.nodes.find(x => selected.has(x.id));
      if (n) { ev.preventDefault(); startEditNode(n); }
    } else if (ev.key === "Escape") { selected.clear(); tool = "select"; render(); renderProps(); }
    else if (ev.key.startsWith("Arrow") && selected.size) {
      ev.preventDefault();
      record();
      const d = ev.shiftKey ? 24 : 6;
      const [dx, dy] = { ArrowLeft: [-d, 0], ArrowRight: [d, 0], ArrowUp: [0, -d], ArrowDown: [0, d] }[ev.key];
      data.nodes.filter(n => selected.has(n.id)).forEach(n => { n.x += dx; n.y += dy; });
      changed();
    } else if (!ctrl && k === "v") { tool = "select"; render(); }
    else if (!ctrl && k === "c") { tool = "connect"; render(); }
  });

  // ---------- barra de herramientas ----------
  $$(".tool[data-tool]").forEach(b => b.addEventListener("click", () => { tool = b.dataset.tool; render(); canvas.focus(); }));
  $("#t-undo").addEventListener("click", () => { if (undo.length) { redo.push(snap()); restore(undo.pop()); } });
  $("#t-redo").addEventListener("click", () => { if (redo.length) { undo.push(snap()); restore(redo.pop()); } });
  const zoomBy = f => {
    const r = canvas.getBoundingClientRect();
    const cx = r.width / 2, cy = r.height / 2;
    const z = Math.min(4, Math.max(0.15, data.view.zoom * f));
    const wx = (cx - data.view.x) / data.view.zoom, wy = (cy - data.view.y) / data.view.zoom;
    data.view = { zoom: z, x: cx - wx * z, y: cy - wy * z };
    render(); scheduleSave();
  };
  $("#t-zin").addEventListener("click", () => zoomBy(1.2));
  $("#t-zout").addEventListener("click", () => zoomBy(1 / 1.2));
  $("#t-zfit").addEventListener("click", () => { fit(); render(); scheduleSave(); });
  $("#map-title").addEventListener("change", async e => {
    const t = await api(`/api/maps/${id}`, { method: "PUT", body: { title: e.target.value } });
    setTitle(t.title);
  });
  $("#map-topic-pick").addEventListener("change", e => api(`/api/maps/${id}`, { method: "PUT", body: { topic_id: +e.target.value } }));
  $("#map-del").addEventListener("click", async () => {
    if (!confirm("¿Borrar este mapa? No se puede deshacer.")) return;
    clearTimeout(saveTimer); dirty = false;
    await api(`/api/maps/${id}`, { method: "DELETE" });
    location.hash = "#/mapas";
  });
  const fileName = () => (strip($("#map-title").value).replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || "mapa");
  const download = (blob, name) => { const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1500); };
  $("#map-svg").addEventListener("click", () => download(new Blob([mapToSVG(data)], { type: "image/svg+xml" }), fileName() + ".svg"));
  $("#map-png").addEventListener("click", () => {
    const src = mapToSVG(data);
    const B = mapBounds(data);
    const scale = Math.min(2, 8000 / Math.max(B.w + 80, B.h + 80));
    const img = new Image();
    img.onload = () => {
      const c = document.createElement("canvas");
      c.width = Math.ceil((B.w + 80) * scale); c.height = Math.ceil((B.h + 80) * scale);
      const ctx = c.getContext("2d");
      ctx.drawImage(img, 0, 0, c.width, c.height);
      c.toBlob(b => download(b, fileName() + ".png"), "image/png");
      URL.revokeObjectURL(img.src);
    };
    img.onerror = () => toast("No se pudo generar la imagen", true);
    img.src = URL.createObjectURL(new Blob([src], { type: "image/svg+xml" }));
  });

  const onResize = () => render();
  window.addEventListener("resize", onResize);
  const onUnload = () => {
    if (dirty) fetch(`/api/maps/${id}`, { method: "PUT", keepalive: true, headers: { "Content-Type": "application/json" }, body: JSON.stringify({ data }) });
  };
  window.addEventListener("beforeunload", onUnload);
  cleanup = () => {
    document.body.classList.remove("map-mode");
    window.removeEventListener("resize", onResize);
    window.removeEventListener("beforeunload", onUnload);
    finishEdit();
    if (dirty) saveNow();
  };

  if (params.get("nuevo") || (data.view.x === 0 && data.view.y === 0)) fit();
  render();
  renderProps();
  canvas.focus({ preventScroll: true });
}
