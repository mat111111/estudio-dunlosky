/* Estudio Dunlosky — interfaz (SPA sin dependencias) */
"use strict";

// ------------------------------------------------------------------------- //
// Utilidades
// ------------------------------------------------------------------------- //
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const main = $("#main");

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function safeHref(u) {
  // solo enlaces http(s): evita que un resultado externo traiga un "javascript:" u otro esquema
  return /^https?:\/\//i.test(String(u || "")) ? esc(u) : "#";
}
function strip(s) {
  return String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}
async function api(path, opts = {}) {
  const init = { headers: { "Content-Type": "application/json" }, ...opts };
  if (opts.body && typeof opts.body !== "string") init.body = JSON.stringify(opts.body);
  const r = await fetch(path, init);
  let data = null;
  try { data = await r.json(); } catch (e) { /* sin cuerpo */ }
  if (r.status === 401 && !path.startsWith("/api/auth/")) {
    viewLogin();  // la sesión venció o se cerró en otro lado
    throw new Error("Iniciá sesión para continuar.");
  }
  if (!r.ok) {
    const msg = data && (typeof data.detail === "string" ? data.detail : "Datos inválidos");
    throw new Error(msg || `Error ${r.status}`);
  }
  return data;
}
let toastTimer;
function toast(msg, err = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show" + (err ? " err" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.className = "toast"), 3200);
}
function pct(x) { return x == null ? "—" : Math.round(x * 100) + "%"; }
function plural(n, one, many) { return `${n} ${n === 1 ? one : many}`; }
function whenLabel(days) {
  if (!days) return "en 10 minutos";
  if (days < 1.5) return "mañana";
  return `en ${Math.round(days)} días`;
}
function dayShort(iso) {
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("es-AR", { weekday: "short" }).replace(".", "");
}
function highlightIn(text, term) {
  const safe = esc(text);
  if (!term || term.length < 2) return safe;
  const st = strip(text), tt = strip(term);
  const i = st.indexOf(tt);
  if (i < 0) return safe;
  return esc(text.slice(0, i)) + "<mark>" + esc(text.slice(i, i + term.length)) + "</mark>" + esc(text.slice(i + term.length));
}
function setTitle(t) { document.title = t ? `${t} | Estudio Dunlosky` : "Estudio Dunlosky"; }

const KIND = { mc: "Opción múltiple", cloze: "Completar", tf: "Verdadero o falso", open: "Respuesta abierta", why: "¿Por qué?", relate: "Relacionar conceptos" };

// Nivel de complejidad de las preguntas (se recuerda en este navegador)
const LEVELS = {
  basico: { label: "Básico", help: "Reconocer: verdadero o falso y opción múltiple." },
  intermedio: { label: "Intermedio", help: "Recordar sin opciones: completar y definir." },
  avanzado: { label: "Avanzado", help: "Explicar causas y relacionar conceptos, sin pistas." },
  mixto: { label: "Mixto", help: "Todos los niveles combinados." },
};
const LEVEL_NUM = { 1: "Básico", 2: "Intermedio", 3: "Avanzado" };
function getLevel() { try { return localStorage.getItem("nivel") || "mixto"; } catch (e) { return "mixto"; } }
function setLevel(v) { try { localStorage.setItem("nivel", v); } catch (e) { /* sin almacenamiento */ } }
function levelPicker() {
  const cur = getLevel();
  return `<div class="level-pick">
    <span class="small muted">Nivel de las preguntas</span>
    <div class="seg" role="group" aria-label="Nivel de complejidad">${Object.entries(LEVELS).map(([k, v]) =>
      `<button type="button" data-level="${k}" aria-pressed="${k === cur}" title="${esc(v.help)}">${v.label}</button>`).join("")}</div>
    <span class="small muted level-help">${esc(LEVELS[cur].help)}</span>
  </div>`;
}
function bindLevelPicker(root = document) {
  $$("[data-level]", root).forEach(b => b.addEventListener("click", () => {
    setLevel(b.dataset.level);
    $$("[data-level]", root).forEach(x => x.setAttribute("aria-pressed", x.dataset.level === b.dataset.level));
    $$(".level-help", root).forEach(h => (h.textContent = LEVELS[b.dataset.level].help));
  }));
}

const TECH = [
  { key: "practica", util: "alta", name: "Autoevaluación", en: "Practice testing",
    short: "Respondé preguntas sin mirar el texto. Recuperar de memoria es lo que más fija el aprendizaje.",
    how: "Genera preguntas de completar, opción múltiple, verdadero o falso y respuesta abierta a partir de la fuente. Cada respuesta se corrige contra la oración original y, si te equivocás, la pregunta vuelve en la misma sesión." },
  { key: "distribuida", util: "alta", name: "Práctica distribuida", en: "Distributed practice",
    short: "Repasá en sesiones espaciadas: cada pregunta vuelve justo antes de que la olvides.",
    how: "Cada pregunta tiene su propio calendario (algoritmo SM-2). Los aciertos alargan el intervalo (1 día, 3 días, una semana…) y los errores la traen de vuelta a los 10 minutos." },
  { key: "elaborativa", util: "moderada", name: "Interrogación elaborativa", en: "Elaborative interrogation",
    short: "Preguntate “¿por qué esto es cierto?” y respondelo con tus palabras.",
    how: "Busca en la fuente relaciones de causa y consecuencia (porque, ya que, por lo tanto…) y te pide que las expliques. Tu explicación se compara con lo que dice el texto." },
  { key: "autoexplicacion", util: "moderada", name: "Autoexplicación", en: "Self-explanation",
    short: "Avanzá oración por oración explicando qué significa y cómo se conecta con lo anterior.",
    how: "Muestra el texto de a una oración y te pide explicarla. Te avisa si no usaste los conceptos clave o si no la conectaste con lo que venías leyendo." },
  { key: "intercalada", util: "moderada", name: "Práctica intercalada", en: "Interleaved practice",
    short: "Mezclá preguntas de varios temas en la misma sesión para aprender a distinguirlos.",
    how: "Elegís dos o más temas y las preguntas se alternan entre ellos en lugar de ir en bloques." },
  { key: "resumen", util: "baja", name: "Resumen", en: "Summarization",
    short: "Leé una sección, ocultá el texto y escribí lo esencial con tus palabras.",
    how: "Compara tu resumen con los conceptos centrales de la sección y te muestra los que faltaron, con la oración donde aparecen. Después podés practicar justo esos conceptos." },
  { key: "subrayado", util: "baja", name: "Subrayado", en: "Highlighting",
    short: "Marcá las oraciones más importantes y compará con las ideas clave del texto.",
    how: "Tocá las oraciones para resaltarlas. La app te muestra cuáles ideas clave te quedaron afuera y convierte lo que subrayaste en preguntas, que es donde está el aprendizaje real." },
  { key: "mnemotecnia", util: "baja", name: "Palabra clave mnemotécnica", en: "Keyword mnemonic",
    short: "Asociá cada término difícil con una palabra o imagen que te lo recuerde.",
    how: "Lista los términos clave del tema con su definición en la fuente. Escribís tu asociación y después te evalúa esos términos; si fallás, te muestra tu propia pista." },
  { key: "imagenes", util: "baja", name: "Imágenes mentales", en: "Imagery for text",
    short: "Imaginá una escena para cada párrafo y describila antes de seguir.",
    how: "Te guía párrafo por párrafo para que describas la imagen mental y al final te evalúa la sección." },
  { key: "relectura", util: "baja", name: "Relectura", en: "Rereading",
    short: "Volvé a leer la sección con calma y comprobá cuánto quedó con una prueba corta.",
    how: "Mide el tiempo de lectura y termina con preguntas rápidas: así ves por qué releer solo da sensación de saber, y no necesariamente aprendizaje." },
];
const UTIL = {
  alta: { label: "Utilidad alta", text: "Las que más rinden según la evidencia. Usalas siempre." },
  moderada: { label: "Utilidad moderada", text: "Funcionan bien en ciertos contextos y como complemento." },
  baja: { label: "Utilidad baja", text: "Poco efectivas solas. Acá cada una termina en una prueba para que sí sumen." },
};
const UTIL_TEXT = { alta: "Alta", moderada: "Moderada", baja: "Baja" };
function meter(util) {
  return `<span class="meter ${util}" title="${esc(UTIL[util].label)} según Dunlosky y col. (2013)"><i></i><i></i><i></i><span>${UTIL_TEXT[util]}</span></span>`;
}
const ICON = {
  ok: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 12.5 5 5L20 6.5"/></svg>`,
  part: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14"/></svg>`,
  bad: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>`,
};

// ------------------------------------------------------------------------- //
// Router
// ------------------------------------------------------------------------- //
let cleanup = null;
let STATUS = null;  // estado del servidor (modo público, IA)
const PUBLIC_NOTE = `<p class="callout small" style="margin-top:16px">Versión de prueba en línea: tus temas y tu progreso quedan asociados a este navegador, pero el servidor gratuito los borra cuando se reinicia (por ejemplo, después de un rato sin visitas). Para guardarlos de forma permanente, instalá la app en tu computadora con Docker.</p>`;
const routes = [
  [/^\/?$/, viewHome, "inicio"],
  [/^\/nuevo$/, viewNew, "nuevo"],
  [/^\/tema\/(\d+)$/, viewTopic, null],
  [/^\/tecnica\/(\w+)\/(\d+)$/, viewTechnique, null],
  [/^\/practicar$/, viewSession, null],
  [/^\/intercalada$/, viewInterleave, "intercalada"],
  [/^\/guia$/, viewGuide, "guia"],
  [/^\/pomodoro$/, viewPomodoro, "pomodoro"],
  [/^\/tareas$/, viewTasks, "tareas"],
  [/^\/notas$/, viewNotebook, "notas"],
  [/^\/ajustes$/, viewSettings, "ajustes"],
];
function parseHash() {
  const raw = location.hash.replace(/^#/, "") || "/";
  const [path, qs] = raw.split("?");
  return { path, params: new URLSearchParams(qs || "") };
}
async function route() {
  if (cleanup) { cleanup(); cleanup = null; }
  if (!STATUS) { try { STATUS = await api("/api/status"); } catch (e) { STATUS = { public: false }; } }
  const { path, params } = parseHash();
  let nav = null;
  for (const [re, fn, n] of routes) {
    const m = path.match(re);
    if (m) {
      nav = n;
      if (path === "/practicar") nav = params.get("mode") === "review" ? "repaso" : params.get("mode") === "errors" ? "errores" : null;
      $$(".rail nav a").forEach(a => a.classList.toggle("active", a.dataset.nav === nav));
      main.innerHTML = `<div class="page"><span class="loader"></span></div>`;
      try {
        await fn(...m.slice(1), params);
      } catch (e) {
        main.innerHTML = `<div class="page narrow"><div class="empty"><h2>No se pudo cargar</h2><p class="muted">${esc(e.message)}</p><p style="margin-top:16px"><a class="btn" href="#/">Volver al inicio</a></p></div></div>`;
      }
      main.focus({ preventScroll: true });
      window.scrollTo(0, 0);
      refreshBadges();
      return;
    }
  }
  location.hash = "#/";
}
window.addEventListener("hashchange", route);

async function refreshBadges() {
  try {
    const d = await api("/api/dashboard");
    const due = $("#nav-due"), err = $("#nav-err");
    due.textContent = d.totals.due; due.hidden = !d.totals.due;
    err.textContent = d.totals.errors; err.hidden = !d.totals.errors;
  } catch (e) { /* silencioso */ }
}

// tema claro / oscuro
(function themeToggle() {
  const btn = $("#theme-toggle");
  const label = () => {
    const dark = document.documentElement.dataset.theme === "dark" ||
      (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
    btn.querySelector("span").textContent = dark ? "Modo claro" : "Modo oscuro";
    return dark;
  };
  label();
  btn.addEventListener("click", () => {
    const next = label() ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("tema", next); } catch (e) { /* sin almacenamiento */ }
    label();
  });
})();

// Sesión pendiente (para pasar listas de ítems sin ponerlas en la URL)
let pendingSession = null;
function startSession(opts) {
  pendingSession = opts;
  location.hash = "#/practicar?mode=" + encodeURIComponent(opts.mode) + "&from=mem&t=" + Date.now();
}

// ------------------------------------------------------------------------- //
// Inicio
// ------------------------------------------------------------------------- //
async function viewHome() {
  setTitle("");
  const [d, topics] = await Promise.all([api("/api/dashboard"), api("/api/topics")]);
  const t = d.totals;
  if (!topics.length) {
    main.innerHTML = `
      <div class="page narrow">
        <section class="today">
          <h1>¿Qué querés aprender hoy?</h1>
          <p class="lead">Escribí cualquier tema. La app busca la información en Wikipedia, arma preguntas a partir del texto y corrige tus respuestas contra la fuente.</p>
          <form class="search-bar" id="quick" style="margin-top:22px">
            <input class="input" name="q" placeholder="Por ejemplo: fotosíntesis, Revolución de Mayo, árbol binario" aria-label="Tema a estudiar" required minlength="2">
            <button class="btn primary big">Buscar</button>
          </form>
          <p class="small muted" style="margin-top:12px">¿Tenés tus propios apuntes? <a href="#/nuevo?tab=notas">Pegalos acá</a> y se estudian igual.</p>
        </section>
        ${STATUS.public ? PUBLIC_NOTE : ""}
        <h2 class="section-title">Cómo funciona</h2>
        <ol class="list" style="list-style:decimal inside">
          <li>Elegís un tema y la fuente (Wikipedia en español o inglés, o tus apuntes).</li>
          <li>Estudiás con las 10 técnicas que evaluaron Dunlosky y su equipo, empezando por las de mayor utilidad.</li>
          <li>Cada error queda registrado y vuelve con preguntas sobre ese mismo fragmento hasta que lo domines.</li>
        </ol>
      </div>`;
    $("#quick").addEventListener("submit", e => {
      e.preventDefault();
      location.hash = "#/nuevo?q=" + encodeURIComponent(new FormData(e.target).get("q"));
    });
    return;
  }

  const max = Math.max(1, ...d.activity.map(a => a.count));
  const todayIso = d.activity[d.activity.length - 1].day;
  const headline = t.due
    ? `Tenés ${plural(t.due, "pregunta", "preguntas")} para repasar hoy`
    : t.errors ? `Te quedan ${plural(t.errors, "error", "errores")} por corregir` : "Estás al día con tus repasos";
  main.innerHTML = `
    <div class="page">
      <section class="today">
        <h1>${esc(headline)}</h1>
        <p class="lead">${t.due ? "Repasar justo cuando la memoria empieza a fallar es lo que la consolida." : "Buen momento para sumar un tema nuevo o practicar uno que tengas flojo."}</p>
        <div class="today-actions">
          ${t.due ? `<a class="btn primary big" href="#/practicar?mode=review">Empezar repaso</a>` : ""}
          ${t.errors ? `<a class="btn big" href="#/practicar?mode=errors">Practicar mis errores (${t.errors})</a>` : ""}
          <a class="btn big ${t.due || t.errors ? "" : "primary"}" href="#/nuevo">Nuevo tema</a>
        </div>
      </section>
      <div class="stats">
        <div class="stat"><b>${d.streak}</b><span>${d.streak === 1 ? "día seguido" : "días seguidos"}</span></div>
        <div class="stat"><b>${pct(d.accuracy_7d)}</b><span>aciertos en 7 días</span></div>
        <div class="stat"><b>${t.mastered}<small class="muted" style="font-size:16px"> / ${t.items}</small></b><span>preguntas dominadas</span></div>
        <div class="stat"><b>${d.pomodoros.today}</b><span>${d.pomodoros.today === 1 ? "pomodoro hoy" : "pomodoros hoy"}</span></div>
      </div>
      ${d.urgent_tasks.length ? `
        <div class="panel" style="margin-top:16px">
          <div class="row"><h3>Tareas que vencen esta semana</h3><span class="spacer"></span><a class="btn ghost" href="#/tareas">Ver todas</a></div>
          <ul class="list tasks compact" style="margin-top:10px">${d.urgent_tasks.map(x => taskRow(x, true)).join("")}</ul>
        </div>` : ""}

      <div class="grid-2" style="margin-top:16px">
        <div class="panel">
          <h3>Actividad de las últimas dos semanas</h3>
          <div class="bars" role="img" aria-label="Respuestas por día en las últimas dos semanas">
            ${d.activity.map(a => `
              <div class="bar ${a.day === todayIso ? "today-bar" : ""}" title="${a.count} respuestas, ${a.correct} correctas">
                <i style="height:${(a.count / max) * 100}%"><em style="height:${a.count ? (a.correct / a.count) * 100 : 0}%"></em></i>
                <small>${dayShort(a.day).slice(0, 2)}</small>
              </div>`).join("")}
          </div>
          <div class="legend"><span><i style="background:var(--blue)"></i>Correctas</span><span><i style="background:var(--blue-soft)"></i>Respondidas</span></div>
        </div>
        <div class="panel">
          <h3>Secciones para reforzar</h3>
          ${d.weak_sections.length ? `<ul class="list" style="border:0;margin-top:8px">${d.weak_sections.map(w => `
            <li style="padding:10px 0">
              <div class="grow"><b><span class="dot" style="--hue:${w.hue}"></span>${esc(w.title)}</b><div class="small muted">${esc(w.topic)}, ${pct(w.accuracy)} de aciertos</div></div>
              <button class="btn" data-sec="${w.id}">Practicar</button>
            </li>`).join("")}</ul>`
            : `<p class="muted small" style="margin-top:10px">Cuando respondas al menos tres preguntas de una sección, acá vas a ver las que te cuestan más.</p>`}
        </div>
      </div>

      <div class="section-title"><h2>Tus temas</h2><span class="spacer"></span><a class="btn ghost" href="#/intercalada">Intercalar temas</a></div>
      <div class="grid-3">
        ${topics.map(topicCard).join("")}
      </div>
      ${STATUS.public ? PUBLIC_NOTE : ""}
    </div>`;
  $$("[data-sec]").forEach(b => b.addEventListener("click", () =>
    startSession({ mode: "section", section_id: +b.dataset.sec, n: 10, tech: "practica" })));
}

function topicCard(tp) {
  const s = tp.stats;
  return `
    <a class="topic-card" href="#/tema/${tp.id}" style="--hue:${tp.hue}">
      <h3>${esc(tp.title)}</h3>
      <div class="src">${esc(tp.sources.map(x => x.name).filter((v, i, a) => a.indexOf(v) === i).join(" y "))}</div>
      <div class="progress" title="Preguntas dominadas"><i style="width:${Math.round((s.progress || 0) * 100)}%"></i></div>
      <div class="meta-row">
        <span>${pct(s.progress)} dominado</span>
        ${s.due ? `<span>${s.due} para hoy</span>` : ""}
        ${s.errors ? `<span class="warn">${plural(s.errors, "error", "errores")}</span>` : ""}
      </div>
    </a>`;
}

// ------------------------------------------------------------------------- //
// Nuevo tema
// ------------------------------------------------------------------------- //
// Sitios recomendados para importar por URL (se abren en otra pestaña para buscar ahí)
const RECOMMENDED_SITES = [
  { name: "MDN Web Docs", url: "https://developer.mozilla.org/es/", about: "Programación web: HTML, CSS y JavaScript, en español." },
  { name: "Documentación de Python", url: "https://docs.python.org/es/3/", about: "Tutorial y referencia oficial de Python, en español." },
  { name: "cppreference", url: "https://es.cppreference.com/", about: "Referencia de C y C++ (parte en español, completa en inglés)." },
  { name: "SciELO", url: "https://scielo.org/es/", about: "Artículos académicos revisados de revistas de Iberoamérica." },
  { name: "Educ.ar", url: "https://www.educ.ar/", about: "Recursos educativos del Ministerio de Educación de Argentina." },
  { name: "OpenStax", url: "https://openstax.org/subjects", about: "Libros universitarios abiertos (en inglés)." },
];

async function viewNew(params) {
  setTitle("Nuevo tema");
  const addTo = params.get("agregar");
  const selected = new Map();  // clave → {site,title,url,label,source}
  const tab = ["notas", "web", "ia"].includes(params.get("tab")) ? params.get("tab") : "buscar";
  let sites = [];
  let cats = [];
  try { [sites, cats] = await Promise.all([api("/api/sources"), api("/api/categories")]); } catch (e) { /* lista por defecto */ }
  let category = null;
  try { category = localStorage.getItem("categoria"); } catch (e) { /* nada */ }
  if (!cats.some(c => c.key === category)) category = "otros";
  // la selección de buscadores se recuerda en este navegador
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem("buscadores") || "null"); } catch (e) { /* sin almacenamiento */ }
  const avail = new Set(sites.filter(s => s.available !== false).map(s => s.site));
  const catSites = key => (cats.find(c => c.key === key) || { sites: [] }).sites;
  const active = new Set((saved || catSites(category) || sites.filter(s => s.default).map(s => s.site)).filter(x => avail.has(x)));
  const saveActive = () => { try { localStorage.setItem("buscadores", JSON.stringify([...active])); } catch (e) { /* nada */ } };
  const GROUPS = [...new Set(sites.map(s => s.group || "Otros"))];

  main.innerHTML = `
    <div class="page narrow">
      <div class="page-head">
        <h1>${addTo ? "Agregar otra fuente" : "Nuevo tema"}</h1>
        <p class="lead">${addTo ? "Sumá otro artículo, una página web o tus apuntes al mismo tema: las preguntas se van a mezclar."
          : "Buscá en enciclopedias, libros de texto, artículos académicos, foros de programación y la web; importá una página o pegá tus apuntes. Podés combinar hasta cuatro fuentes."}</p>
      </div>
      <div class="tabs" role="tablist">
        <button role="tab" data-tab="buscar" aria-selected="${tab === "buscar"}">Buscar en fuentes</button>
        <button role="tab" data-tab="web" aria-selected="${tab === "web"}">Desde una página web</button>
        <button role="tab" data-tab="ia" aria-selected="${tab === "ia"}">Generar con IA</button>
        <button role="tab" data-tab="notas" aria-selected="${tab === "notas"}">Pegar mis apuntes</button>
      </div>

      <section id="tab-buscar" ${tab === "buscar" ? "" : "hidden"}>
        <form class="search-bar" id="search">
          <input class="input" name="q" placeholder="Escribí el tema que querés estudiar" aria-label="Tema" required minlength="2" value="${esc(params.get("q") || "")}">
          <button class="btn primary big">Buscar</button>
        </form>
        ${cats.length ? `<div class="cat-row" role="group" aria-label="Área del tema">
          <span class="small muted">¿De qué área es?</span>
          <div class="seg cat-seg">${cats.map(c => `<button type="button" data-cat="${c.key}" aria-pressed="${c.key === category}">${esc(c.label)}</button>`).join("")}</div>
        </div>` : ""}
        <details class="src-details"><summary>Fuentes de esta búsqueda (<span id="src-count">${active.size}</span>)</summary>
        <div class="src-panel">
          ${GROUPS.map(g => `
            <div class="src-row"><span class="src-group-name">${esc(g)}</span>
              <div class="src-chips" role="group" aria-label="${esc(g)}">
                ${sites.filter(s => (s.group || "Otros") === g).map(s => `<label class="src-chip ${s.available === false ? "off" : ""}" title="${esc(s.available === false ? (s.why_off || "No disponible") : s.about)}"><input type="checkbox" value="${s.site}" ${active.has(s.site) ? "checked" : ""} ${s.available === false ? "disabled" : ""}> ${esc(s.name)}</label>`).join("")}
              </div></div>`).join("")}
          ${sites.some(s => s.available === false) ? `<p class="small muted">Los buscadores en gris necesitan una clave: se cargan en <a href="#/ajustes">Ajustes</a>.</p>` : ""}
        </div></details>
        <div id="results" class="stack" style="--gap:22px;margin-top:22px"></div>
      </section>

      <section id="tab-web" ${tab === "web" ? "" : "hidden"}>
        <form class="search-bar" id="url-form">
          <input class="input" name="url" type="url" required placeholder="https://… (pegá el enlace de la página)" aria-label="Dirección de la página">
          <button class="btn primary big">Agregar</button>
        </form>
        <p class="small muted" style="margin-top:10px">Funciona con páginas de texto: documentación, artículos, apuntes de cátedra publicados. Si una página no se puede importar (porque pide iniciar sesión o se arma con JavaScript), copiá el texto y usá «Pegar mis apuntes».</p>
        <h2 class="section-title">Sitios recomendados para estudiar</h2>
        <ul class="list">${RECOMMENDED_SITES.map(r => `
          <li><div class="grow"><b>${esc(r.name)}</b><div class="small muted">${esc(r.about)}</div></div>
          <a class="btn" href="${esc(r.url)}" target="_blank" rel="noopener">Abrir sitio</a></li>`).join("")}</ul>
        <p class="small muted" style="margin-top:10px">Buscá ahí la página que necesitás, copiá su dirección y pegala arriba.</p>
      </section>

      <section id="tab-ia" ${tab === "ia" ? "" : "hidden"}>
        ${STATUS.ai_enabled ? `
        <form id="ia-form" class="stack">
          <label class="field"><span>¿Sobre qué querés el apunte?</span>
            <input class="input" name="query" required minlength="2" maxlength="200" placeholder="Por ejemplo: planificación de procesos en sistemas operativos"></label>
          <div class="row" style="align-items:flex-end">
            <label class="field"><span>Nivel</span><select class="input" name="level">
              <option value="basico">Básico: desde cero, con ejemplos simples</option>
              <option value="intermedio" selected>Intermedio: nivel universitario</option>
              <option value="avanzado">Avanzado: preparación de examen</option></select></label>
          </div>
          <label class="field"><span>Enfoque (opcional)</span>
            <textarea class="input" name="focus" maxlength="500" style="min-height:80px" placeholder="Por ejemplo: para el parcial de AySO, con foco en los algoritmos FIFO, SJF y Round Robin"></textarea></label>
          <p class="callout info small">La IA (${esc(STATUS.label)}) busca primero en Wikipedia, Wikilibros y Wikiversidad, y escribe el apunte <b>basándose en esos textos</b>. Las fuentes originales quedan guardadas en el tema para que puedas comprobar cualquier dato.</p>
          <div class="actions"><button class="btn primary big">Generar apunte y preguntas</button><span class="small muted" id="ia-msg"></span></div>
        </form>` : `<div class="empty"><h3>Necesitás activar la IA</h3><p class="muted">Configurá tu clave de Gemini o de Claude en Ajustes para generar apuntes de estudio.</p>
          <div class="actions"><a class="btn primary" href="#/ajustes">Ir a Ajustes</a></div></div>`}
      </section>

      <section id="tab-notas" ${tab === "notas" ? "" : "hidden"}>
        <form id="notes-form" class="stack">
          ${addTo ? "" : `<label class="field"><span>Nombre del tema</span><input class="input" name="title" required placeholder="Por ejemplo: Unidad 3, procesos e hilos"></label>`}
          <label class="field"><span>Tus apuntes</span>
            <textarea class="input" name="text" required style="min-height:260px" placeholder="Pegá el texto. Si usás títulos con # (por ejemplo: # Planificación), cada uno se convierte en una sección."></textarea>
          </label>
          <p class="callout info small">Con tus apuntes, las respuestas se comparan con lo que escribiste vos. Revisá que el texto sea correcto antes de estudiarlo.</p>
          <div class="actions"><button class="btn primary big">${addTo ? "Agregar apuntes" : "Crear tema"}</button><span class="small muted" id="notes-msg"></span></div>
        </form>
      </section>

      <div id="create-bar" class="panel" style="margin-top:22px" hidden>
        <h3>Fuentes elegidas</h3>
        <ul class="chosen" id="chosen"></ul>
        ${addTo ? "" : `<label class="field" style="margin-top:12px"><span>Nombre del tema</span><input class="input" id="topic-title" placeholder="Si lo dejás vacío, se usa el título de la primera fuente"></label>`}
        <div class="actions"><button class="btn primary big" id="create"></button><span class="small muted" id="create-msg"></span></div>
      </div>
    </div>`;

  $$("[data-tab]").forEach(b => b.addEventListener("click", () => {
    $$("[data-tab]").forEach(x => x.setAttribute("aria-selected", x === b));
    ["buscar", "web", "ia", "notas"].forEach(k => ($(`#tab-${k}`).hidden = b.dataset.tab !== k));
    $("#create-bar").hidden = ["notas", "ia"].includes(b.dataset.tab) || selected.size === 0;
  }));
  $$("[data-cat]").forEach(b => b.addEventListener("click", () => {
    category = b.dataset.cat;
    try { localStorage.setItem("categoria", category); } catch (e) { /* nada */ }
    $$("[data-cat]").forEach(x => x.setAttribute("aria-pressed", x === b));
    active.clear();
    catSites(category).filter(x => avail.has(x)).forEach(x => active.add(x));
    $$(".src-chip input").forEach(cb => (cb.checked = active.has(cb.value)));
    $("#src-count").textContent = active.size;
    saveActive();
    if ($("#search [name=q]").value.trim().length > 1) doSearch();
  }));
  $$(".src-chip input").forEach(cb => cb.addEventListener("change", () => {
    cb.checked ? active.add(cb.value) : active.delete(cb.value);
    $("#src-count").textContent = active.size;
    saveActive();
    if ($("#search [name=q]").value.trim().length > 1) doSearch();
  }));

  const ti = $("#topic-title");
  if (ti) ti.addEventListener("input", () => (ti.dataset.touched = "1"));

  function updateBar() {
    const bar = $("#create-bar");
    bar.hidden = selected.size === 0;
    $("#chosen").innerHTML = [...selected.entries()].map(([k, s]) =>
      `<li><span class="chip">${esc(s.source)}</span> ${esc(s.label)} <button class="btn ghost small" data-rm="${esc(k)}" aria-label="Quitar">Quitar</button></li>`).join("");
    $$("[data-rm]").forEach(b => b.addEventListener("click", () => {
      selected.delete(b.dataset.rm);
      $$(`.result-item input[data-key="${CSS.escape(b.dataset.rm)}"]`).forEach(cb => { cb.checked = false; cb.closest(".result-item").classList.remove("sel"); });
      updateBar();
    }));
    const first = [...selected.values()][0];
    if (ti && first && !ti.dataset.touched) ti.value = first.url ? "" : first.label;
    $("#create").textContent = addTo ? `Agregar ${plural(selected.size, "fuente", "fuentes")}` : `Crear tema con ${plural(selected.size, "fuente", "fuentes")}`;
  }
  function select(key, entry, on) {
    if (on) {
      if (selected.size >= 4 && !selected.has(key)) { toast("Podés combinar hasta 4 fuentes por tema."); return false; }
      selected.set(key, entry);
    } else selected.delete(key);
    updateBar();
    return true;
  }

  async function doSearch() {
    const q = $("#search [name=q]").value.trim();
    const box = $("#results");
    if (!active.size) { box.innerHTML = `<p class="muted">Elegí al menos una fuente donde buscar.</p>`; return; }
    box.innerHTML = `<p class="muted"><span class="loader"></span> Buscando “${esc(q)}”…</p>`;
    try {
      const res = await api(`/api/search?q=${encodeURIComponent(q)}&sites=${[...active].join(",")}&category=${encodeURIComponent(category || "")}`);
      const groups = res.groups.filter(g => g.results.length);
      const webg = res.groups.find(g => g.site === "web");
      if (!groups.length && !(webg && webg.error)) {
        box.innerHTML = `<div class="empty"><h3>Sin resultados</h3><p class="muted">Probá con otras palabras, con el nombre más general del tema o sumá más fuentes.</p></div>`;
        return;
      }
      const all = [];
      const ytq = q + (category && category !== "otros" ? " " + ($(`[data-cat="${category}"]`)?.textContent || "") : "") + " explicación";
      box.innerHTML = `<p class="yt-line"><a href="https://www.youtube.com/results?search_query=${encodeURIComponent(ytq.toLowerCase())}" target="_blank" rel="noopener"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="2.5" y="5.5" width="19" height="13" rx="4"/><path d="m10 9 5 3-5 3z"/></svg>Ver videos sobre «${esc(q)}» en YouTube</a><span class="small muted"> Al crear el tema, en la pestaña Videos vas a tener recomendaciones.</span></p>` +
        (res.fallback_en ? `<p class="callout small">No hubo resultados en español; se muestran artículos en inglés.</p>` : "") +
        groups.map(g => `
          <div class="src-group">
            <div class="row" style="margin-bottom:8px"><h3>${esc(g.name)}</h3><span class="small muted">${esc(g.about)}</span></div>
            ${g.summary ? `<p class="small muted" style="margin-bottom:8px">${esc(g.summary)}</p>` : ""}
            <div class="stack" style="--gap:8px">${g.results.map(r => {
              const i = all.push(r) - 1;
              const key = `${r.site}|${r.title}`;
              return `<label class="result-item ${selected.has(key) ? "sel" : ""}">
                <input type="checkbox" data-i="${i}" data-key="${esc(key)}" ${selected.has(key) ? "checked" : ""}>
                <div><h3>${esc(r.title)}</h3>${r.snippet ? `<p>${esc(r.snippet)}…</p>` : ""}
                <p class="small muted">${r.meta ? `${esc(r.meta)}, ` : ""}${r.words ? `${r.words.toLocaleString("es-AR")} palabras, ` : ""}<a href="${safeHref(r.url)}" target="_blank" rel="noopener">ver página</a></p></div>
              </label>`;
            }).join("")}</div>
            ${g.suggestions_html ? `<iframe class="g-suggest" sandbox="allow-popups allow-popups-to-escape-sandbox" title="Sugerencias de búsqueda de Google"></iframe>` : ""}
          </div>`).join("") +
        (webg && webg.error ? `<p class="callout small">Google: ${esc(webg.error)}</p>` : "") +
        (() => {
          const empty = res.groups.filter(g => !g.results.length && !g.error).map(g => g.name);
          return empty.length ? `<p class="small muted">También se buscó en ${esc(empty.join(", "))}, sin resultados para esta búsqueda. Probá con un término más general (por ejemplo, el nombre de la materia).</p>` : "";
        })() +
        res.errors.map(e => `<p class="small muted">No se pudo consultar ${esc(e.name)}.</p>`).join("");
      // Google exige mostrar sus sugerencias de búsqueda: se aíslan en un iframe
      $$("#results .g-suggest").forEach((fr, k) => {
        const g = groups.filter(x => x.suggestions_html)[k];
        if (g) fr.srcdoc = `<base target="_blank">${g.suggestions_html}`;
      });
      $$("#results input[type=checkbox]").forEach(cb => cb.addEventListener("change", () => {
        const r = all[+cb.dataset.i];
        const entry = r.site === "web" ? { url: r.url, label: r.title, source: "Google" }
          : r.ref || r.kind === "provider"
            ? { site: r.site, ref: r.ref, url: r.url, title: r.title, label: r.title, source: r.source_name, provider: true }
            : { site: r.site, title: r.title, label: r.title, source: r.source_name };
        const ok = select(cb.dataset.key, entry, cb.checked);
        if (!ok) cb.checked = false;
        cb.closest(".result-item").classList.toggle("sel", cb.checked);
      }));
    } catch (e) {
      box.innerHTML = `<div class="empty"><h3>No se pudo buscar</h3><p class="muted">${esc(e.message)}</p></div>`;
    }
  }
  $("#search").addEventListener("submit", e => { e.preventDefault(); doSearch(); });
  if (params.get("q")) doSearch();

  $("#url-form").addEventListener("submit", e => {
    e.preventDefault();
    const url = e.target.url.value.trim();
    let host = url;
    try { host = new URL(url).hostname.replace(/^www\./, ""); } catch (err) { /* se valida en el servidor */ }
    if (select(`url|${url}`, { url, label: url, source: host }, true)) {
      e.target.reset();
      toast("Página agregada a las fuentes");
    }
  });

  async function create(payload, msgEl, btn) {
    btn.disabled = true;
    msgEl.innerHTML = `<span class="loader"></span> Descargando las fuentes y generando preguntas…`;
    try {
      const res = addTo
        ? await api(`/api/topics/${addTo}/sources`, { method: "POST", body: payload })
        : await api("/api/topics", { method: "POST", body: payload });
      toast(addTo ? "Fuente agregada" : "Tema creado");
      location.hash = `#/tema/${res.id}`;
    } catch (e) {
      msgEl.textContent = "";
      btn.disabled = false;
      toast(e.message, true);
    }
  }
  $("#create").addEventListener("click", e => {
    const title = $("#topic-title")?.value.trim();
    const srcs = [...selected.values()].map(s => (s.provider ? { site: s.site, ref: s.ref, url: s.url, title: s.title }
      : s.url ? { url: s.url } : { site: s.site, title: s.title }));
    create({ title: title || null, sources: srcs }, $("#create-msg"), e.currentTarget);
  });
  $("#ia-form")?.addEventListener("submit", e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    create({ title: null, ai_material: { query: fd.get("query").trim(), level: fd.get("level"), focus: fd.get("focus") || "" } },
      $("#ia-msg"), e.submitter);
    $("#ia-msg").innerHTML = `<span class="loader"></span> Buscando fuentes y escribiendo el apunte. Puede tardar hasta un minuto…`;
  });
  $("#notes-form").addEventListener("submit", e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const title = (fd.get("title") || "").trim();
    create({ title: title || null, notes: { title, text: fd.get("text") } }, $("#notes-msg"), e.submitter);
  });
}

// ------------------------------------------------------------------------- //
// Tema
// ------------------------------------------------------------------------- //
async function viewTopic(id, params) {
  const t = await api(`/api/topics/${id}`);
  setTitle(t.title);
  const tab = params.get("tab") || "tecnicas";
  const s = t.stats || {};
  const totalItems = Object.values(t.kinds).reduce((a, b) => a + b, 0);
  main.innerHTML = `
    <div class="page" style="--hue:${t.hue}">
      <div class="page-head">
        <div class="row small muted"><span class="dot"></span>${esc(t.sources.map(x => x.name).filter((v, i, a) => a.indexOf(v) === i).join(" y "))}${(t.ai_status || "").startsWith("generando") ? `<span><span class="loader" style="width:13px;height:13px"></span> Escribiendo preguntas con IA${t.ai_status.includes("/") ? ` (bloque ${esc(t.ai_status.split(" ")[1])})` : ""}</span>` : t.ai_items ? `<span class="chip">${plural(t.ai_items, "pregunta escrita con IA", "preguntas escritas con IA")}</span>` : ""}</div>
        <h1 style="margin-top:6px">${esc(t.title)}</h1>
        ${STATUS.ai_enabled && t.ai_items < 8 && !(t.ai_status || "").startsWith("generando") ? `
          <div class="callout info small row" style="margin-top:10px">
            <span class="grow">${t.ai_items ? `Este tema tiene solo ${plural(t.ai_items, "pregunta escrita", "preguntas escritas")} con IA; el resto se armó automáticamente a partir del texto.` : "Las preguntas de este tema se armaron automáticamente a partir del texto."} Con la IA tenés preguntas redactadas como en un examen, por niveles y con explicación.</span>
            <button class="btn primary" id="go-ai-q">${t.ai_items ? "Generar más con IA" : "Generar preguntas con IA"}</button>
          </div>` : ""}
        ${t.ai_generated ? `<p class="callout small" style="margin-top:10px">Este tema incluye un <b>apunte generado con IA</b> a partir de fuentes abiertas. Las fuentes originales están en la pestaña Fuentes: si algún dato no te cierra, verificalo ahí.</p>` : ""}
        <div class="progress" style="max-width:420px"><i style="width:${Math.round((s.progress || 0) * 100)}%"></i></div>
        <div class="meta-row">
          <span>${pct(s.progress)} dominado</span>
          <span>${plural(totalItems, "pregunta", "preguntas")}</span>
          <span>Aciertos: ${pct(s.accuracy)}</span>
          ${s.due ? `<span>${s.due} para hoy</span>` : ""}
          ${s.errors ? `<span class="warn">${plural(s.errors, "error pendiente", "errores pendientes")}</span>` : ""}
        </div>
        <div class="actions">
          <button class="btn primary big" id="go-practice">Practicar ahora</button>
          ${s.due ? `<button class="btn big" id="go-review">Repasar lo de hoy (${s.due})</button>` : ""}
          ${s.errors ? `<button class="btn big" id="go-errors">Practicar errores (${s.errors})</button>` : ""}
          <button class="btn ghost big" id="go-export" aria-expanded="false">Guardar PDF</button>
          <a class="btn ghost big" href="#/notas?tema=${t.id}">Anotar</a>
        </div>
        ${levelPicker()}
        <div class="panel export-panel" id="export-panel" hidden>
          <h3>Guardar como PDF</h3>
          <div class="row" style="margin-top:12px;align-items:flex-end">
            <label class="field"><span>Contenido</span><select class="input" id="ex-content">
              <option value="apunte">Apunte: el material generado</option>
              <option value="ambos">Apunte + preguntas y respuestas</option>
              <option value="preguntas">Solo preguntas y respuestas</option></select></label>
            <label class="field ex-q"><span>Nivel</span><select class="input" id="ex-level">
              ${Object.entries(LEVELS).map(([k, v]) => `<option value="${k}" ${k === getLevel() ? "selected" : ""}>${v.label}</option>`).join("")}</select></label>
            <label class="field ex-q ex-only-q"><span>Formato</span><select class="input" id="ex-layout">
              <option value="examen">Examen: respuestas al final</option>
              <option value="estudio">Guía de estudio: respuesta debajo de cada pregunta</option></select></label>
            <label class="field ex-q"><span>Preguntas por sección</span><select class="input" id="ex-max">
              ${[5, 8, 12, 20, 40].map(n => `<option ${n === 12 ? "selected" : ""}>${n}</option>`).join("")}</select></label>
            <a class="btn primary" id="ex-go" download>Descargar PDF</a>
          </div>
          <p class="small muted" id="ex-help" style="margin-top:10px"></p>
        </div>
      </div>
      <div class="tabs" role="tablist">
        ${[["tecnicas", "Técnicas"], ["leer", "Leer"], ["errores", `Errores${s.errors ? ` (${s.errors})` : ""}`], ["videos", "Videos"], ["fuentes", "Fuentes"]].map(([k, l]) =>
          `<button role="tab" data-tab="${k}" aria-selected="${tab === k}">${l}</button>`).join("")}
      </div>
      <div id="tab-body"></div>
    </div>`;
  bindLevelPicker();
  $("#go-ai-q")?.addEventListener("click", async e => {
    e.currentTarget.disabled = true;
    try {
      await api(`/api/topics/${t.id}/ai-questions`, { method: "POST" });
      toast("La IA está escribiendo las preguntas. Podés seguir usando la app.");
      viewTopic(String(t.id), params);
    } catch (err) { toast(err.message, true); e.currentTarget.disabled = false; }
  });
  // mientras la IA escribe preguntas, se actualiza el encabezado sola
  if ((t.ai_status || "").startsWith("generando")) {
    const here = location.hash;
    const timer = setTimeout(() => { if (location.hash === here) viewTopic(String(t.id), params); }, 6000);
    const prev = cleanup;
    cleanup = () => { clearTimeout(timer); if (prev) prev(); };
  }
  const EX_HELP = {
    apunte: "Incluye el texto de cada sección, lo que resaltaste (en amarillo), tus resúmenes y un glosario con los conceptos que abriste con «¿por qué?».",
    ambos: "El apunte completo y, al final, preguntas con su respuesta y la evidencia en la fuente.",
    preguntas: "El formato examen sirve para practicar en papel: respondé sin mirar y corregí con la clave del final.",
  };
  try { const c = localStorage.getItem("export_contenido"); if (c && EX_HELP[c]) $("#ex-content").value = c; } catch { /* sin almacenamiento */ }
  const exUrl = () => {
    const c = $("#ex-content").value;
    $$(".ex-q").forEach(el => (el.hidden = c === "apunte"));
    $$(".ex-only-q").forEach(el => (el.hidden = c !== "preguntas"));
    $("#ex-help").textContent = EX_HELP[c];
    try { localStorage.setItem("export_contenido", c); } catch { /* sin almacenamiento */ }
    return `/api/topics/${t.id}/export.pdf?content=${c}&level=${$("#ex-level").value}&layout=${$("#ex-layout").value}&max_per_section=${$("#ex-max").value}`;
  };
  $("#go-export").addEventListener("click", e => {
    const p = $("#export-panel");
    p.hidden = !p.hidden;
    e.currentTarget.setAttribute("aria-expanded", String(!p.hidden));
    $("#ex-go").href = exUrl();
  });
  ["#ex-content", "#ex-level", "#ex-layout", "#ex-max"].forEach(sel => $(sel).addEventListener("change", () => ($("#ex-go").href = exUrl())));
  $("#go-practice").addEventListener("click", () => startSession({ mode: "practice", topic_ids: [t.id], n: 12, tech: "practica", back: `#/tema/${t.id}` }));
  $("#go-review")?.addEventListener("click", () => startSession({ mode: "review", topic_ids: [t.id], n: 30, tech: "distribuida", back: `#/tema/${t.id}` }));
  $("#go-errors")?.addEventListener("click", () => startSession({ mode: "errors", topic_ids: [t.id], n: 12, tech: "errores", back: `#/tema/${t.id}` }));
  $$("[data-tab]").forEach(b => b.addEventListener("click", () => {
    history.replaceState(null, "", `#/tema/${t.id}?tab=${b.dataset.tab}`);
    $$("[data-tab]").forEach(x => x.setAttribute("aria-selected", x === b));
    renderTab(b.dataset.tab);
  }));

  async function renderTab(which) {
    const body = $("#tab-body");
    if (which === "tecnicas") {
      body.innerHTML = ["alta", "moderada", "baja"].map(u => `
        <div class="util-group">
          <div class="util-head">${meter(u)}<p>${esc(UTIL[u].text)}</p></div>
          <div class="grid-3">
            ${TECH.filter(x => x.util === u).map(x => `
              <a class="tech" href="#/tecnica/${x.key}/${t.id}">
                <h3>${esc(x.name)}</h3>
                <p>${esc(x.short)}</p>
                <span class="go">Empezar</span>
              </a>`).join("")}
          </div>
        </div>`).join("");
    } else if (which === "leer") {
      let terms = [];
      try { terms = (await api(`/api/topics/${t.id}/concepts`)).terms; } catch (e) { /* sin conceptos */ }
      body.innerHTML = `<p class="small muted" style="margin-bottom:10px">Los conceptos subrayados se pueden tocar: te muestran qué dice la fuente y por qué.</p>
      <div class="reader">${t.sections.map(sec => `
        <h3 id="sec-${sec.id}">${esc(sec.title)}</h3>
        <div class="sec-meta"><span>${sec.words} palabras</span><span>${plural(sec.stats.items, "pregunta", "preguntas")}</span>${sec.stats.accuracy != null ? `<span>Aciertos: ${pct(sec.stats.accuracy)}</span>` : ""}
          <button class="btn ghost small" data-practice="${sec.id}" style="padding:2px 8px">Practicar esta sección</button></div>
        ${sec.paragraphs.map(p => { const used = new Set(); return `<p>${p.map(x => linkConcepts(x.text, terms, used)).join(" ")}</p>`; }).join("")}`).join("")}
      </div>
      <p class="callout small" style="margin-top:14px">Leer y releer da sensación de dominio, pero lo que fija la información es recuperarla. Después de leer una sección, practicala.</p>`;
      $$("[data-practice]").forEach(b => b.addEventListener("click", () =>
        startSession({ mode: "section", section_id: +b.dataset.practice, n: 10, tech: "practica", back: `#/tema/${t.id}?tab=leer` })));
      bindConceptButtons(body, t.id);
    } else if (which === "errores") {
      const errs = await api(`/api/topics/${t.id}/errors`);
      body.innerHTML = errs.length ? `
        <div class="row" style="margin-bottom:14px"><p class="muted grow">Cada error vuelve junto con otras preguntas sobre el mismo fragmento de la fuente.</p>
          <button class="btn primary" id="err-go">Practicar estos errores</button></div>
        <ul class="list miss-list">${errs.map(e => `
          <li><div class="grow">
            <div class="small muted">${esc(e.section_title || "")}${e.lapses > 1 ? `, fallada ${e.lapses} veces` : ""}</div>
            <div style="margin:4px 0">${esc(e.prompt)}</div>
            ${e.last_answer ? `<div class="yours small">Tu respuesta: <s>${esc(e.last_answer)}</s></div>` : ""}
            <span class="pen">${esc(e.answer.length > 120 ? e.answer.slice(0, 120) + "…" : e.answer)}</span>
          </div></li>`).join("")}</ul>`
        : `<div class="empty"><h3>No hay errores pendientes</h3><p class="muted">Cuando falles una pregunta va a aparecer acá hasta que la respondas bien.</p></div>`;
      $("#err-go")?.addEventListener("click", () => startSession({ mode: "errors", topic_ids: [t.id], n: 14, tech: "errores", back: `#/tema/${t.id}?tab=errores` }));
    } else if (which === "videos") {
      await renderVideos(body, t);
    } else {
      body.innerHTML = `
        <ul class="list">${t.sources.map(src => `
          <li><div class="grow"><b>${esc(src.title)}</b>
            <div class="small muted">${esc(src.name)}${src.license ? `, licencia ${esc(src.license)}` : ""}${src.revised_at ? `, versión del ${new Date(src.revised_at).toLocaleDateString("es-AR")}` : ""}, descargado el ${new Date(src.retrieved_at).toLocaleDateString("es-AR")}</div></div>
            ${src.url ? `<a class="btn" href="${esc(src.revid ? src.url.split("/wiki/")[0] + "/w/index.php?oldid=" + src.revid : src.url)}" target="_blank" rel="noopener">${src.revid ? "Ver versión usada" : "Abrir página"}</a>` : ""}
          </li>`).join("")}</ul>
        <p class="small muted" style="margin-top:12px">Se guarda una copia del texto de cada fuente${t.sources.some(x => x.revid) ? " (y en los wikis, la revisión exacta)" : ""}: cada corrección se hace contra ese texto, aunque la página cambie después.</p>
        <div class="actions"><a class="btn" href="#/nuevo?agregar=${t.id}">Agregar otra fuente</a>
          ${STATUS.ai_enabled ? `<button class="btn" id="ai-q2" title="La IA escribe preguntas nuevas para todo el tema; tu progreso se conserva">Generar preguntas con IA</button>` : ""}
          <button class="btn" id="enrich" title="Suma preguntas conceptuales automáticas sin borrar tu progreso">Preguntas automáticas nuevas</button>
          <span class="spacer"></span><button class="btn danger" id="del">Eliminar tema</button></div>`;
      $("#ai-q2")?.addEventListener("click", async e => {
        e.currentTarget.disabled = true;
        try {
          await api(`/api/topics/${t.id}/ai-questions`, { method: "POST" });
          toast("La IA está escribiendo las preguntas. Podés seguir usando la app.");
          viewTopic(String(t.id), new URLSearchParams("tab=fuentes"));
        } catch (err) { toast(err.message, true); e.currentTarget.disabled = false; }
      });
      $("#enrich").addEventListener("click", async e => {
        e.currentTarget.disabled = true;
        e.currentTarget.innerHTML = `<span class="loader" style="width:14px;height:14px"></span> Generando…`;
        const r = await api(`/api/topics/${t.id}/enrich`, { method: "POST" });
        toast(`Se sumaron ${plural(r.added, "pregunta conceptual", "preguntas conceptuales")}${r.ai ? "; la IA sigue agregando más en segundo plano" : ""}`);
        viewTopic(String(t.id), new URLSearchParams("tab=fuentes"));
      });
      $("#del").addEventListener("click", async () => {
        if (!confirm(`¿Eliminar “${t.title}” con todo su progreso? No se puede deshacer.`)) return;
        await api(`/api/topics/${t.id}`, { method: "DELETE" });
        toast("Tema eliminado");
        location.hash = "#/";
      });
    }
  }
  renderTab(tab);
}

// ------------------------------------------------------------------------- //
// Sesión de práctica (autoevaluación con corrección y reintento)
// ------------------------------------------------------------------------- //
async function viewSession(params) {
  let opts;
  if (params.get("from") === "mem" && pendingSession) {
    opts = pendingSession;
  } else {
    opts = { mode: params.get("mode") || "practice", n: 20,
      tech: params.get("mode") === "review" ? "distribuida" : params.get("mode") === "errors" ? "errores" : "practica" };
    const tp = params.get("topics");
    if (tp) opts.topic_ids = tp.split(",").map(Number);
  }
  pendingSession = null;
  const back = opts.back || "#/";
  const body = { mode: opts.mode, topic_ids: opts.topic_ids || [], section_id: opts.section_id || null,
    item_ids: opts.item_ids || [], terms: opts.terms || [], n: opts.n || 12,
    level: opts.level || (["practice", "section", "interleaved"].includes(opts.mode) ? getLevel() : "mixto") };
  const data = await api("/api/session", { method: "POST", body });
  const titles = { practice: "Autoevaluación", review: "Repaso de hoy", errors: "Práctica de errores", interleaved: "Práctica intercalada",
    elaborative: "Interrogación elaborativa", section: "Práctica de la sección", items: opts.title || "Práctica", terms: "Práctica de términos" };
  setTitle(titles[data.mode]);

  if (!data.items.length) {
    const empty = {
      review: ["No hay nada para repasar hoy", "Las preguntas que respondas van a volver acá cuando toque repasarlas."],
      errors: ["No tenés errores pendientes", "Cuando falles una pregunta, vas a poder practicarla desde acá."],
    }[data.mode] || ["No hay preguntas disponibles", "Probá con otra sección o agregá más fuentes al tema."];
    main.innerHTML = `<div class="page narrow"><div class="empty"><h2>${empty[0]}</h2><p class="muted">${empty[1]}</p>
      <div class="actions"><a class="btn primary" href="${esc(back)}">Volver</a><a class="btn" href="#/nuevo">Nuevo tema</a></div></div></div>`;
    return;
  }

  const S = {
    queue: data.items.slice(), i: 0, first: new Map(), retries: new Map(), log: [],
    hints: opts.hints || {}, tech: opts.tech || "practica", answered: false, usedHint: false,
  };

  function shell(inner) {
    const done = S.i + (S.answered ? 1 : 0);
    const totalNow = S.queue.length;
    main.innerHTML = `
      <div class="page narrow">
        <div class="session-top">
          <a class="btn ghost" href="${esc(back)}" aria-label="Salir de la sesión">Salir</a>
          <div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="${totalNow}" aria-valuenow="${done}"><i style="width:${(done / totalNow) * 100}%"></i></div>
          <span class="small muted">${Math.min(S.i + 1, totalNow)} de ${totalNow}</span>
        </div>
        ${S.i === 0 && data.intro && !S.answered ? `<p class="callout info small" style="margin-bottom:14px">${esc(data.intro)}</p>` : ""}
        ${inner}
      </div>`;
  }

  function render() {
    S.answered = false; S.usedHint = false;
    const it = S.queue[S.i];
    const isRetry = S.first.has(it.id);
    const prompt = it.kind === "cloze" || it.kind === "mc"
      ? esc(it.prompt).replace(/_____/g, `<span class="blank" aria-label="espacio en blanco"></span>`)
      : esc(it.prompt);
    let input = "";
    if (it.kind === "mc") {
      input = `<div class="options">${it.options.map((o, k) => `<button class="opt" data-opt="${esc(o)}"><span class="n">${k + 1}</span><span>${esc(o)}</span></button>`).join("")}</div>`;
    } else if (it.kind === "tf") {
      input = `<div class="options tf">${["Verdadero", "Falso"].map((o, k) => `<button class="opt" data-opt="${o}"><span class="n">${k + 1}</span><span>${o}</span></button>`).join("")}</div>`;
    } else if (it.kind === "cloze") {
      input = `<form class="answer-row" id="ans"><input class="input" name="a" autocomplete="off" placeholder="Escribí la palabra que falta" aria-label="Tu respuesta" autofocus>
        <button class="btn primary">Comprobar</button></form>`;
    } else {
      input = `<form id="ans"><textarea class="input" name="a" placeholder="Respondé con tus palabras, sin mirar el texto" aria-label="Tu respuesta" autofocus></textarea>
        <div class="actions"><button class="btn primary">Comprobar</button><span class="small muted">Ctrl + Enter para enviar</span></div></form>`;
    }
    const custom = it.term ? S.hints[strip(it.term)] : null;
    shell(`
      <article class="card-q" style="--hue:${it.hue}">
        <div class="q-meta">
          <span class="dot"></span><span>${esc(it.topic_title)}</span>
          ${it.section_title ? `<span>${esc(it.section_title)}</span>` : ""}
          <span class="spacer"></span>
          <span class="kind">${isRetry ? "Segundo intento" : KIND[it.kind]}</span>
          <span class="lvl lvl-${it.level}">${LEVEL_NUM[it.level] || ""}</span>
          ${it.origin === "ia" ? `<span class="chip" title="Pregunta generada con IA y verificada contra una cita de la fuente">IA</span>` : ""}
        </div>
        <div class="q-text">${prompt}</div>
        ${input}
        <div id="hint-slot">${(it.hint && data.level !== "avanzado") || custom ? `<button class="btn ghost small" id="hint-btn" style="margin-top:10px">Ver pista</button>` : ""}</div>
      </article>
      <div id="fb"></div>`);

    $$(".opt").forEach(b => b.addEventListener("click", () => submit(b.dataset.opt, b)));
    $("#ans")?.addEventListener("submit", e => { e.preventDefault(); submit(new FormData(e.target).get("a") || ""); });
    $("#ans textarea")?.addEventListener("keydown", e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) $("#ans").requestSubmit(); });
    $("#hint-btn")?.addEventListener("click", () => {
      S.usedHint = true;
      $("#hint-slot").innerHTML = `<p class="hint-box">${esc(custom ? "Tu pista: " + custom : it.hint)}</p>`;
    });
    $("#ans [name=a]")?.focus();
  }

  async function submit(answer, btn) {
    if (S.answered) return;
    S.answered = true;
    const it = S.queue[S.i];
    $$(".opt, #ans button, #ans [name=a]").forEach(el => (el.disabled = true));
    let res;
    try {
      res = await api("/api/answer", { method: "POST", body: { item_id: it.id, answer, technique: S.tech, used_hint: S.usedHint } });
    } catch (e) {
      S.answered = false;
      $$(".opt, #ans button, #ans [name=a]").forEach(el => (el.disabled = false));
      toast(e.message, true);
      return;
    }
    const firstTry = !S.first.has(it.id);
    if (firstTry) S.first.set(it.id, res.verdict);
    S.log.push({ it, res, answer, firstTry });

    if (it.kind === "mc" || it.kind === "tf") {
      $$(".opt").forEach(b => {
        if (strip(b.dataset.opt) === strip(res.correct_answer)) b.classList.add("is-right");
        else if (b === btn) b.classList.add("is-wrong");
      });
    }
    let requeued = false;
    if (res.verdict !== "correct") {
      const r = S.retries.get(it.id) || 0;
      if (r < 1) {
        S.retries.set(it.id, r + 1);
        const pos = Math.min(S.i + 4, S.queue.length);
        S.queue.splice(pos, 0, it);
        requeued = true;
      }
    }
    renderFeedback(it, res, answer, requeued);
  }

  function renderFeedback(it, res, answer, requeued) {
    const v = res.verdict;
    const title = { correct: "Correcto", partial: "Parcialmente correcto", incorrect: "Incorrecto" }[v];
    const icon = { correct: ICON.ok, partial: ICON.part, incorrect: ICON.bad }[v];
    const choice = it.kind === "mc" || it.kind === "tf";
    const showAnswer = !(v === "correct" && (choice || it.kind === "cloze"));
    const src = res.source;
    const link = src && (src.permalink || src.url);
    const custom = it.term ? S.hints[strip(it.term)] : null;
    $("#fb").innerHTML = `
      <section class="feedback ${v}" aria-live="polite">
        <div class="verdict">${icon}<span>${title}</span>${res.by === "ia" ? `<span class="chip" style="font-family:var(--font-body)">corregido con IA</span>` : ""}</div>
        <p class="fb-text">${esc(res.feedback)}</p>
        ${showAnswer ? `<div class="correction">
          ${!choice && answer.trim() && v !== "correct" ? `<div class="yours">Tu respuesta: <s>${esc(answer)}</s></div>` : ""}
          ${!choice ? `<div><span class="small muted">${["open", "why", "relate"].includes(it.kind) ? "Lo que dice la fuente:" : "Respuesta:"}</span><br><span class="pen">${esc(res.correct_answer)}</span></div>` : ""}
        </div>` : ""}
        ${res.matched?.length || res.missing?.length ? `<div class="chips">${(res.matched || []).map(m => `<span class="chip ok">${esc(m)}</span>`).join("")}${(res.missing || []).map(m => `<span class="chip no">Faltó: ${esc(m)}</span>`).join("")}</div>` : ""}
        ${res.errors?.length ? `<div class="chips">${res.errors.map(m => `<span class="chip no">Error: ${esc(m)}</span>`).join("")}</div>` : ""}
        ${custom && v !== "correct" ? `<p class="callout small" style="margin-top:12px">Tu asociación para recordarlo: ${esc(custom)}</p>` : ""}
        ${res.context ? `<div class="evidence">
          <div class="label">Evidencia en la fuente${src?.section_title ? `, sección “${esc(src.section_title)}”` : ""}</div>
          <q>${highlightIn(res.context, it.kind === "tf" ? "" : res.correct_answer)}</q>
          ${link ? `<div style="margin-top:6px"><a href="${esc(link)}" target="_blank" rel="noopener">Abrir en ${esc(src.name)}</a></div>` : ""}
        </div>` : ""}
        <div class="why-wrap"><button type="button" class="btn ghost" data-explain>¿Por qué es así?</button><div class="why-box" hidden></div></div>
        ${res.self_check ? `<div class="selfcheck"><span>¿Cómo te fue en realidad?</span>
          <button class="btn" data-ov="correct">Lo sabía</button><button class="btn" data-ov="partial">A medias</button><button class="btn" data-ov="incorrect">No lo sabía</button></div>` : ""}
        ${requeued ? `<p class="retry-note">Esta pregunta vuelve en unos minutos dentro de esta sesión.</p>` : ""}
        ${v !== "correct" && res.siblings ? `<p class="schedule-note">Hay ${plural(res.siblings, "pregunta más", "preguntas más")} sobre este mismo fragmento en “Mis errores”.</p>` : ""}
        <p class="schedule-note" id="sched">Próximo repaso: ${whenLabel(res.interval_days)}.</p>
        <div class="actions"><button class="btn primary" id="next">${S.i + 1 < S.queue.length ? "Siguiente" : "Ver resultados"} <span class="kbd">Enter</span></button></div>
      </section>`;
    $$("[data-ov]").forEach(b => b.addEventListener("click", async () => {
      try {
        const o = await api(`/api/attempts/${res.attempt_id}/override`, { method: "POST", body: { verdict: b.dataset.ov } });
        $$("[data-ov]").forEach(x => x.setAttribute("aria-pressed", x === b));
        $("#sched").textContent = `Próximo repaso: ${whenLabel(o.interval_days)}.`;
        const last = S.log[S.log.length - 1];
        last.res.verdict = b.dataset.ov;
        if (last.firstTry) S.first.set(it.id, b.dataset.ov);
        if (b.dataset.ov === "correct") {
          // si se había reencolado, se quita
          const idx = S.queue.indexOf(it, S.i + 1);
          if (idx > -1) S.queue.splice(idx, 1);
        }
        toast("Autoevaluación registrada");
      } catch (e) { toast(e.message, true); }
    }));
    bindExplainButton($("#fb"), it, res.explanation);
    $("#next").addEventListener("click", next);
    $("#next").focus({ preventScroll: true });
    $("#fb").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "nearest" });
  }

  function next() {
    S.i += 1;
    if (S.i >= S.queue.length) return finish();
    render();
    window.scrollTo(0, 0);
  }

  function finish() {
    const vals = [...S.first.values()];
    const right = vals.filter(v => v === "correct").length;
    const partial = vals.filter(v => v === "partial").length;
    const missed = [];
    const seen = new Set();
    for (const l of S.log) {
      if (l.firstTry && l.res.verdict !== "correct" && !seen.has(l.it.id)) { missed.push(l); seen.add(l.it.id); }
    }
    const fixed = missed.filter(m => S.log.some(l => l.it.id === m.it.id && !l.firstTry && l.res.verdict === "correct")).length;
    setTitle("Resultados");
    main.innerHTML = `
      <div class="page narrow">
        <div class="page-head">
          <div class="result-score">${right}<small> / ${vals.length} correctas al primer intento</small></div>
          <p class="lead">${partial ? `${plural(partial, "respuesta parcial", "respuestas parciales")}. ` : ""}${missed.length ? `Corregiste ${fixed} de ${missed.length} en el segundo intento. Las que fallaste vuelven en el repaso de hoy.` : "Sin errores: estas preguntas se espacian más en el calendario."}</p>
          <div class="actions">
            ${missed.length ? `<button class="btn primary big" id="fix">Practicar estos errores</button>` : ""}
            <button class="btn big" id="again">Otra ronda</button>
            <a class="btn ghost big" href="${esc(back)}">Terminar</a>
          </div>
        </div>
        ${missed.length ? `<h2 class="section-title">Para revisar</h2>
        <ul class="list miss-list">${missed.map(m => `
          <li><div class="grow">
            <div class="small muted">${esc(m.it.section_title || m.it.topic_title)}</div>
            <div style="margin:4px 0">${esc(m.it.prompt)}</div>
            ${m.answer && m.it.kind !== "mc" && m.it.kind !== "tf" ? `<div class="yours small">Respondiste: <s>${esc(m.answer)}</s></div>` : ""}
            <span class="pen">${esc(m.res.correct_answer.length > 140 ? m.res.correct_answer.slice(0, 140) + "…" : m.res.correct_answer)}</span>
          </div></li>`).join("")}</ul>` : ""}
      </div>`;
    $("#fix")?.addEventListener("click", () => startSession({
      mode: "errors", item_ids: missed.map(m => m.it.id), topic_ids: [...new Set(missed.map(m => m.it.topic_id))],
      n: 20, tech: "errores", back, hints: S.hints }));
    $("#again").addEventListener("click", () => startSession({ ...opts, back }));
  }

  function onKey(e) {
    if (e.target.tagName === "TEXTAREA" || (e.target.tagName === "INPUT" && !S.answered)) return;
    if (S.answered && e.key === "Enter" && $("#next")) { e.preventDefault(); $("#next").click(); return; }
    if (!S.answered && /^[1-4]$/.test(e.key)) {
      const b = $$(".opt")[+e.key - 1];
      if (b) b.click();
    }
  }
  document.addEventListener("keydown", onKey);
  cleanup = () => document.removeEventListener("keydown", onKey);
  render();
}

// ------------------------------------------------------------------------- //
// Técnicas específicas
// ------------------------------------------------------------------------- //
async function viewTechnique(key, topicId, params) {
  const tech = TECH.find(x => x.key === key);
  if (!tech) { location.hash = `#/tema/${topicId}`; return; }
  const back = `#/tema/${topicId}`;
  if (key === "practica") { startSession({ mode: "practice", topic_ids: [+topicId], n: 12, tech: "practica", back }); return; }
  if (key === "elaborativa") { startSession({ mode: "elaborative", topic_ids: [+topicId], n: 8, tech: "elaborativa", back }); return; }
  if (key === "intercalada") { location.hash = `#/intercalada?con=${topicId}`; return; }

  const t = await api(`/api/topics/${topicId}`);
  setTitle(`${tech.name}: ${t.title}`);
  const head = `
    <div class="page-head">
      <a class="btn ghost" href="${back}" style="margin-left:-14px">${esc(t.title)}</a>
      <div class="row" style="margin-top:8px"><h1>${esc(tech.name)}</h1>${meter(tech.util)}</div>
      <p class="lead">${esc(tech.how)}</p>
    </div>`;

  if (key === "distribuida") {
    const max = Math.max(1, ...t.upcoming.map(u => u.count));
    main.innerHTML = `<div class="page narrow">${head}
      <div class="panel">
        <h3>Calendario de repasos de este tema</h3>
        <div class="cal" style="margin-top:12px">${t.upcoming.map((u, i) => `
          <div class="${i === 0 ? "now" : ""}"><small>${i === 0 ? "hoy" : i === 1 ? "mañana" : dayShort(u.day)}</small><b>${u.count}</b>
          <i style="display:block;height:4px;border-radius:2px;margin-top:6px;background:var(--blue);opacity:${0.2 + 0.8 * (u.count / max)}"></i></div>`).join("")}</div>
        <p class="small muted" style="margin-top:12px">${t.stats.seen ? `Ya respondiste ${t.stats.seen} de ${t.stats.items} preguntas. Las que no viste todavía entran con “Practicar ahora”.` : "Todavía no respondiste preguntas de este tema: empezá con una sesión de autoevaluación y el calendario se arma solo."}</p>
        <div class="actions">
          ${t.upcoming[0].count ? `<button class="btn primary big" id="rev">Repasar ahora (${t.upcoming[0].count})</button>` : ""}
          <button class="btn big ${t.upcoming[0].count ? "" : "primary"}" id="newq">Practicar preguntas nuevas</button>
        </div>
      </div>
      <p class="callout info small" style="margin-top:16px">Estudiar en varias sesiones cortas separadas por días rinde mucho más que una sola sesión larga, aunque el total de horas sea el mismo.</p>
    </div>`;
    $("#rev")?.addEventListener("click", () => startSession({ mode: "review", topic_ids: [t.id], n: 30, tech: "distribuida", back }));
    $("#newq").addEventListener("click", () => startSession({ mode: "practice", topic_ids: [t.id], n: 12, tech: "distribuida", back }));
    return;
  }

  if (key === "mnemotecnia") {
    const terms = await api(`/api/topics/${topicId}/terms`);
    main.innerHTML = `<div class="page">${head}
      <p class="callout small">Dunlosky y su equipo encontraron que esta técnica sirve para vocabulario y términos sueltos, pero el efecto se pierde rápido. Usala para los términos que más te cuestan y siempre probate después.</p>
      <div class="panel" style="padding:0;margin-top:16px">
        ${terms.map((x, i) => `
          <div class="term-row">
            <div><h3>${esc(x.term)}</h3>${x.sentence ? `<p>${highlightIn(x.sentence, x.term)}</p>` : ""}</div>
            <label class="field"><span class="small">Tu palabra clave o imagen</span>
              <input class="input" data-term="${i}" value="${esc(x.mnemonic || "")}" placeholder="Por ejemplo: “estomas” suena a “estómago”: la hoja come aire por la boca">
            </label>
          </div>`).join("")}
      </div>
      <div class="actions"><button class="btn primary big" id="save-test">Guardar y probarme</button><button class="btn big" id="save">Guardar</button></div>
    </div>`;
    async function save() {
      const ops = [];
      $$("[data-term]").forEach(inp => {
        const x = terms[+inp.dataset.term];
        const v = inp.value.trim();
        if (v && v !== (x.mnemonic || "")) {
          ops.push(api("/api/notes", { method: "POST", body: { topic_id: t.id, technique: "mnemonic", ref: x.term, content: v } }));
          x.mnemonic = v;
        }
      });
      await Promise.all(ops);
      return ops.length;
    }
    $("#save").addEventListener("click", async () => { const n = await save(); toast(n ? `Guardaste ${plural(n, "asociación", "asociaciones")}` : "No hay cambios para guardar"); });
    $("#save-test").addEventListener("click", async () => {
      await save();
      const chosen = terms.filter(x => x.mnemonic);
      const list = (chosen.length ? chosen : terms).slice(0, 12);
      // tu propia asociación aparece como pista y, si fallás, junto a la corrección
      const hints = {};
      list.forEach(x => { if (x.mnemonic) hints[strip(x.term)] = x.mnemonic; });
      startSession({ mode: "terms", topic_ids: [t.id], terms: list.map(x => x.term), n: list.length, tech: "mnemotecnia", back: `#/tecnica/mnemotecnia/${t.id}`, hints });
    });
    return;
  }

  // Técnicas que trabajan sobre una sección
  const secId = +params.get("seccion") || null;
  if (!secId) {
    main.innerHTML = `<div class="page narrow">${head}
      <h2 class="section-title">Elegí una sección</h2>
      <ul class="list">${t.sections.map(s => `
        <li><div class="grow"><b>${esc(s.title)}</b><div class="small muted">${s.words} palabras${s.stats.accuracy != null ? `, ${pct(s.stats.accuracy)} de aciertos` : ""}</div></div>
          <a class="btn" href="#/tecnica/${key}/${t.id}?seccion=${s.id}">Elegir</a></li>`).join("")}</ul>
    </div>`;
    return;
  }
  const sec = t.sections.find(s => s.id === secId);
  if (!sec) { location.hash = `#/tecnica/${key}/${t.id}`; return; }
  const sents = sec.paragraphs.flat();
  const secBack = `#/tecnica/${key}/${t.id}`;
  const quiz = (n, tech) => startSession({ mode: "section", section_id: sec.id, n, tech, back: secBack });

  if (key === "resumen") {
    main.innerHTML = `<div class="page narrow">${head}
      <div id="stage">
        <div class="reader"><h3>${esc(sec.title)}</h3>${sec.paragraphs.map(p => `<p>${p.map(x => esc(x.text)).join(" ")}</p>`).join("")}</div>
        <div class="actions"><button class="btn primary big" id="hide">Ya lo leí: ocultar el texto y resumir</button></div>
      </div>
    </div>`;
    $("#hide").addEventListener("click", () => {
      $("#stage").innerHTML = `
        <form id="sum" class="stack">
          <label class="field"><span>Tu resumen de “${esc(sec.title)}”</span>
            <textarea class="input" name="text" required style="min-height:220px" placeholder="Con tus palabras: ¿cuáles son las ideas principales y cómo se relacionan?"></textarea></label>
          <div class="actions"><button class="btn primary big">Comparar con la fuente</button><span class="small muted">Sin mirar el texto</span></div>
        </form><div id="out"></div>`;
      $("#sum [name=text]").focus();
      $("#sum").addEventListener("submit", async e => {
        e.preventDefault();
        const fb = await api("/api/summary", { method: "POST", body: { section_id: sec.id, text: new FormData(e.target).get("text") } });
        const v = fb.coverage >= 0.6 ? "correct" : fb.coverage >= 0.3 ? "partial" : "incorrect";
        $("#out").innerHTML = `
          <section class="feedback ${v}">
            <div class="verdict">${{ correct: ICON.ok, partial: ICON.part, incorrect: ICON.bad }[v]}<span>Cubriste ${pct(fb.coverage)} de los conceptos centrales</span></div>
            <p class="fb-text">${fb.words} palabras (la sección tiene ${fb.source_words}).</p>
            ${fb.notes.map(n => `<p class="callout small" style="margin-top:10px">${esc(n)}</p>`).join("")}
            <div class="chips">${fb.covered.map(c => `<span class="chip ok">${esc(c)}</span>`).join("")}${fb.missing.map(c => `<span class="chip no">Faltó: ${esc(c)}</span>`).join("")}</div>
            ${Object.keys(fb.evidence).length ? `<div class="evidence"><div class="label">Dónde aparece lo que faltó</div>
              ${[...new Set(Object.values(fb.evidence))].map(s => `<p style="margin:6px 0"><q>${Object.keys(fb.evidence).filter(k => fb.evidence[k] === s).reduce((acc, k) => acc.replace(new RegExp(esc(k).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i"), m => `<mark>${m}</mark>`), esc(s))}</q></p>`).join("")}</div>` : ""}
            <div class="actions">
              ${fb.practice_ids.length ? `<button class="btn primary" id="prac">Practicar lo que faltó (${fb.practice_ids.length})</button>` : ""}
              <button class="btn" id="secq">Probarme con la sección</button>
            </div>
          </section>`;
        $("#prac")?.addEventListener("click", () => startSession({ mode: "items", item_ids: fb.practice_ids, tech: "resumen", back: secBack, title: "Conceptos que faltaron" }));
        $("#secq").addEventListener("click", () => quiz(8, "resumen"));
      });
    });
    return;
  }

  if (key === "subrayado") {
    const sel = new Set();
    main.innerHTML = `<div class="page narrow">${head}
      <p class="small muted" style="margin-bottom:10px">Tocá las oraciones que te parecen esenciales. Intentá no pasar de un tercio del texto.</p>
      <div class="reader selectable" id="txt"><h3>${esc(sec.title)}</h3>${sec.paragraphs.map(p => `<p>${p.map(x => `<span class="sent" data-i="${x.i}" tabindex="0" role="button" aria-pressed="false">${esc(x.text)}</span>`).join(" ")}</p>`).join("")}</div>
      <div class="actions"><button class="btn primary big" id="cmp" disabled>Comparar con las ideas clave</button><span class="small muted" id="cnt">Nada subrayado</span></div>
      <div id="out"></div>
    </div>`;
    const toggle = el => {
      const i = +el.dataset.i;
      sel.has(i) ? sel.delete(i) : sel.add(i);
      el.classList.toggle("on", sel.has(i));
      el.setAttribute("aria-pressed", sel.has(i));
      $("#cnt").textContent = sel.size ? `${plural(sel.size, "oración", "oraciones")} de ${sents.length} (${pct(sel.size / sents.length)})` : "Nada subrayado";
      $("#cmp").disabled = !sel.size;
    };
    $$(".sent").forEach(el => {
      el.addEventListener("click", () => toggle(el));
      el.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(el); } });
    });
    $("#cmp").addEventListener("click", async () => {
      const fb = await api("/api/highlight", { method: "POST", body: { section_id: sec.id, selected: [...sel] } });
      $("#txt").classList.remove("selectable");
      $$(".sent").forEach(el => {
        const i = +el.dataset.i;
        el.classList.toggle("missed", fb.missed.includes(i));
        el.classList.toggle("extra", fb.extra.includes(i));
        el.replaceWith(Object.assign(el.cloneNode(true), { tabIndex: -1 }));
      });
      const v = fb.recall >= 0.6 && fb.precision >= 0.5 ? "correct" : fb.recall >= 0.3 ? "partial" : "incorrect";
      $("#cmp").closest(".actions").remove();
      $("#out").innerHTML = `
        <section class="feedback ${v}">
          <div class="verdict">${{ correct: ICON.ok, partial: ICON.part, incorrect: ICON.bad }[v]}<span>Encontraste ${fb.hits.length} de ${fb.key.length} ideas clave</span></div>
          <p class="fb-text">Precisión ${pct(fb.precision)}: de lo que subrayaste, cuánto era central. Las ideas clave que te faltaron tienen borde punteado; lo tachado en rojo era secundario.</p>
          ${fb.notes.map(n => `<p class="callout small" style="margin-top:10px">${esc(n)}</p>`).join("")}
          <p class="callout info small" style="margin-top:10px">Subrayar solo no alcanza: el paso que sí funciona es convertir lo subrayado en preguntas y responderlas.</p>
          <div class="actions">
            ${fb.practice_ids.length ? `<button class="btn primary" id="prac">Convertir lo subrayado en preguntas (${fb.practice_ids.length})</button>` : ""}
            <button class="btn" id="secq">Probarme con toda la sección</button>
            <a class="btn ghost" href="#/tecnica/subrayado/${t.id}?seccion=${sec.id}&r=${Date.now()}">Volver a intentar</a>
          </div>
        </section>`;
      $("#prac")?.addEventListener("click", () => startSession({ mode: "items", item_ids: fb.practice_ids, tech: "subrayado", back: secBack, title: "Tus subrayados" }));
      $("#secq").addEventListener("click", () => quiz(10, "subrayado"));
    });
    return;
  }

  if (key === "autoexplicacion") {
    let idx = 0;
    const draw = () => {
      main.innerHTML = `<div class="page narrow">${head}
        <div class="reader"><h3>${esc(sec.title)}</h3>${sec.paragraphs.map(p => `<p>${p.map(x => `<span class="sent ${x.i < idx ? "past" : x.i === idx ? "current" : "future"}">${esc(x.text)}</span>`).join(" ")}</p>`).join("")}</div>
        <form id="se" class="stack" style="margin-top:16px">
          <label class="field"><span>Oración ${idx + 1} de ${sents.length}: ¿qué significa y cómo se conecta con lo que ya leíste?</span>
            <textarea class="input" name="e" required placeholder="Esto quiere decir que… y se relaciona con… porque…"></textarea></label>
          <div class="actions"><button class="btn primary">Revisar mi explicación</button><button type="button" class="btn ghost" id="skip">Saltear</button></div>
        </form>
        <div id="out"></div></div>`;
      $(".sent.current")?.scrollIntoView({ block: "center" });
      $("#se [name=e]").focus({ preventScroll: true });
      $("#skip").addEventListener("click", advance);
      $("#se").addEventListener("submit", async e => {
        e.preventDefault();
        const fb = await api("/api/self-explain", { method: "POST", body: { section_id: sec.id, idx, explanation: new FormData(e.target).get("e") } });
        const v = fb.quality >= 0.7 ? "correct" : fb.quality >= 0.4 ? "partial" : "incorrect";
        $("#se button.primary").disabled = true;
        $("#out").innerHTML = `
          <section class="feedback ${v}">
            <div class="verdict">${{ correct: ICON.ok, partial: ICON.part, incorrect: ICON.bad }[v]}<span>${{ correct: "Buena explicación", partial: "Se puede profundizar", incorrect: "Falta desarrollo" }[v]}</span></div>
            ${fb.terms.length ? `<div class="chips">${fb.terms.map(x => `<span class="chip ${fb.used.includes(x) ? "ok" : "no"}">${fb.used.includes(x) ? "" : "Sin usar: "}${esc(x)}</span>`).join("")}</div>` : ""}
            ${fb.connections.length ? `<p class="fb-text" style="margin-top:10px">Bien conectado con lo anterior a través de: ${fb.connections.map(esc).join(", ")}.</p>` : ""}
            ${fb.tips.map(x => `<p class="callout small" style="margin-top:10px">${esc(x)}</p>`).join("")}
            <div class="actions"><button class="btn primary" id="adv">${idx + 1 < sents.length ? "Siguiente oración" : "Terminar y probarme"} <span class="kbd">Enter</span></button></div>
          </section>`;
        $("#adv").addEventListener("click", advance);
        $("#adv").focus();
      });
    };
    const advance = () => { idx += 1; if (idx >= sents.length) quiz(8, "autoexplicacion"); else draw(); };
    draw();
    return;
  }

  if (key === "imagenes") {
    let p = 0;
    const draw = () => {
      main.innerHTML = `<div class="page narrow">${head}
        <div class="reader"><h3>${esc(sec.title)}</h3><p class="small muted">Párrafo ${p + 1} de ${sec.paragraphs.length}</p>
        <p>${sec.paragraphs[p].map(x => esc(x.text)).join(" ")}</p></div>
        <form id="im" class="stack" style="margin-top:16px">
          <label class="field"><span>Cerrá los ojos un momento. ¿Qué escena o esquema te imaginás? Describila.</span>
            <textarea class="input" name="c" required placeholder="Veo una hoja enorme con pequeñas bocas que se abren de noche…"></textarea></label>
          <div class="actions"><button class="btn primary">${p + 1 < sec.paragraphs.length ? "Guardar y seguir" : "Guardar y probarme"}</button></div>
        </form></div>`;
      $("#im [name=c]").focus();
      $("#im").addEventListener("submit", async e => {
        e.preventDefault();
        await api("/api/notes", { method: "POST", body: { topic_id: t.id, section_id: sec.id, technique: "imagery", ref: String(p), content: new FormData(e.target).get("c") } });
        p += 1;
        if (p >= sec.paragraphs.length) quiz(8, "imagenes"); else draw();
      });
    };
    draw();
    return;
  }

  if (key === "relectura") {
    const start = Date.now();
    main.innerHTML = `<div class="page narrow">${head}
      <div class="row small muted" style="margin-bottom:10px"><span>Tiempo de lectura:</span><b id="clock">0:00</b></div>
      <div class="reader"><h3>${esc(sec.title)}</h3>${sec.paragraphs.map(p => `<p>${p.map(x => esc(x.text)).join(" ")}</p>`).join("")}</div>
      <div class="actions"><button class="btn primary big" id="done">Terminé de leer: probarme</button></div>
      <p class="callout small" style="margin-top:14px">Antes de la prueba, estimá cuántas de 5 preguntas vas a acertar. Comparar tu estimación con el resultado te muestra cuánto engaña la sensación de “ya lo sé”.</p>
    </div>`;
    const timer = setInterval(() => {
      const s = Math.floor((Date.now() - start) / 1000);
      const c = $("#clock"); if (c) c.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
    }, 1000);
    cleanup = () => clearInterval(timer);
    $("#done").addEventListener("click", async () => {
      await api("/api/notes", { method: "POST", body: { topic_id: t.id, section_id: sec.id, technique: "reread", content: String(Math.round((Date.now() - start) / 1000)) } });
      quiz(5, "relectura");
    });
  }
}

// ------------------------------------------------------------------------- //
// Intercalada
// ------------------------------------------------------------------------- //
async function viewInterleave(params) {
  setTitle("Práctica intercalada");
  const topics = await api("/api/topics");
  const pre = params.get("con");
  const tech = TECH.find(x => x.key === "intercalada");
  main.innerHTML = `
    <div class="page narrow">
      <div class="page-head">
        <div class="row"><h1>Práctica intercalada</h1>${meter("moderada")}</div>
        <p class="lead">${esc(tech.how)} Te obliga a reconocer de qué tema es cada pregunta, igual que en un examen.</p>
      </div>
      ${topics.length < 2 ? `<div class="empty"><h3>Necesitás al menos dos temas</h3><p class="muted">Creá otro tema para poder mezclarlos.</p><div class="actions"><a class="btn primary" href="#/nuevo">Nuevo tema</a></div></div>` : `
      <div class="stack" style="--gap:10px">${topics.map(tp => `
        <label class="result-item ${pre == tp.id ? "sel" : ""}" style="--hue:${tp.hue}">
          <input type="checkbox" value="${tp.id}" ${pre == tp.id ? "checked" : ""}>
          <div><h3><span class="dot"></span>${esc(tp.title)}</h3><p>${tp.stats.items} preguntas, ${pct(tp.stats.progress)} dominado</p></div>
        </label>`).join("")}</div>
      <div style="margin-top:18px">${levelPicker()}</div>
      <div class="actions"><button class="btn primary big" id="go" disabled>Mezclar y practicar</button><span class="small muted" id="msg">Elegí al menos dos temas</span></div>`}
    </div>`;
  const update = () => {
    const n = $$(".result-item input:checked").length;
    $$(".result-item").forEach(l => l.classList.toggle("sel", l.querySelector("input").checked));
    if ($("#go")) { $("#go").disabled = n < 2; $("#msg").textContent = n < 2 ? "Elegí al menos dos temas" : `${n} temas`; }
  };
  $$(".result-item input").forEach(i => i.addEventListener("change", update));
  bindLevelPicker();
  update();
  $("#go")?.addEventListener("click", () => startSession({
    mode: "interleaved", topic_ids: $$(".result-item input:checked").map(i => +i.value), n: 16, tech: "intercalada", back: "#/intercalada" }));
}

// ------------------------------------------------------------------------- //
// Guía
// ------------------------------------------------------------------------- //
function viewGuide() {
  setTitle("Guía de técnicas");
  main.innerHTML = `
    <div class="page narrow">
      <div class="page-head">
        <h1>Las 10 técnicas de estudio</h1>
        <p class="lead">En 2013, John Dunlosky y cuatro colegas revisaron cientos de estudios sobre técnicas de estudio y calificaron su utilidad. Dos salieron muy bien paradas; las más populares entre estudiantes, como releer y subrayar, quedaron últimas.</p>
      </div>
      ${["alta", "moderada", "baja"].map(u => `
        <h2 class="section-title">${UTIL[u].label}<span class="spacer"></span>${meter(u)}</h2>
        <div class="panel" style="padding:4px 22px">
          ${TECH.filter(x => x.util === u).map(x => `
            <div class="guide-item">
              <h3>${esc(x.name)} <span class="muted small" style="font-family:var(--font-body);font-weight:400">${esc(x.en)}</span></h3>
              <p>${esc(x.short)}</p>
              <p class="how">En la app: ${esc(x.how)}</p>
            </div>`).join("")}
        </div>`).join("")}
      <p class="ref">Dunlosky, J., Rawson, K. A., Marsh, E. J., Nathan, M. J. y Willingham, D. T. (2013). Improving students’ learning with effective learning techniques: Promising directions from cognitive and educational psychology. <i>Psychological Science in the Public Interest, 14</i>(1), 4–58.</p>
    </div>`;
}

// ------------------------------------------------------------------------- //
// Ajustes
// ------------------------------------------------------------------------- //
function passwordPanel() {
  if (!ME || !ME.user) return "";
  return `<div class="panel" style="margin-top:16px">
    <h3>Tu cuenta: ${esc(ME.user.username)}</h3>
    <form id="pw-form" class="stack" style="--gap:10px;margin-top:10px">
      <label class="field"><span>Contraseña actual</span><input class="input" type="password" name="current" required autocomplete="current-password"></label>
      <label class="field"><span>Contraseña nueva</span><input class="input" type="password" name="new" required minlength="8" autocomplete="new-password"></label>
      <div class="actions"><button class="btn">Cambiar contraseña</button><button type="button" class="btn ghost" id="logout2">Cerrar sesión</button></div>
    </form></div>`;
}
function bindPasswordPanel() {
  $("#logout2")?.addEventListener("click", logout);
  $("#pw-form")?.addEventListener("submit", async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api("/api/auth/password", { method: "POST", body: { current: fd.get("current"), new: fd.get("new") } });
      toast("Contraseña cambiada. Se cerraron tus otras sesiones.");
      e.target.reset();
    } catch (err) { toast(err.message, true); }
  });
}

async function viewSettings() {
  setTitle("Ajustes");
  const st = await api("/api/status");
  if (st.public) {
    main.innerHTML = `
      <div class="page narrow">
        <div class="page-head"><h1>Ajustes</h1>
          <p class="lead">Estás usando la versión de prueba en línea.</p></div>
        <div class="panel stack">
          <div class="row"><h3>Corrección con IA</h3><span class="spacer"></span>
            <span class="chip ${st.ai_enabled ? "ok" : ""}">${st.ai_enabled ? "Activa" : "Desactivada"}</span></div>
          <p class="small muted">En esta versión la corrección con IA la configura quien administra el servidor. Sin IA, la app funciona completa: genera las preguntas y corrige comparando con la fuente.</p>
        </div>
        <div class="panel" style="margin-top:16px">
          <h3>Tus datos</h3>
          <p class="small muted" style="margin-top:6px">Cada cuenta tiene su propio espacio: nadie más ve tus temas ni tus respuestas. El servidor gratuito borra los datos cuando se reinicia, así que no los uses como único lugar para guardar tu progreso. Si querés conservarlos, instalá la app en tu computadora con Docker (instrucciones en el repositorio).</p>
        </div>
        ${passwordPanel()}
      </div>`;
    bindPasswordPanel();
    return;
  }
  let prov = st.provider || "anthropic";
  const INFO = {
    anthropic: {
      keyLabel: "Clave de la API de Anthropic", keyPh: "sk-ant-…",
      where: `Se crea en <a href="https://platform.claude.com" target="_blank" rel="noopener">platform.claude.com</a>, sección API Keys. La API se paga aparte de la suscripción de claude.ai.`,
      models: ["claude-haiku-5-5", "claude-sonnet-5-5"],
    },
    gemini: {
      keyLabel: "Clave de la API de Gemini", keyPh: "AIza…",
      where: `Se crea en <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener">Google AI Studio</a>, en «Get API key». La suscripción a Google AI Pro no incluye la API: la clave tiene que estar en un proyecto con facturación activada.`,
      models: ["gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.8-flash"],
    },
  };
  const draw = () => {
    const p = st.providers[prov];
    const inf = INFO[prov];
    main.innerHTML = `
    <div class="page narrow">
      <div class="page-head">
        <h1>Ajustes</h1>
        <p class="lead">La app funciona completa sin configurar nada. Opcionalmente podés conectar una IA, Claude o Gemini, para corregir respuestas abiertas por significado y sumar preguntas de comprensión.</p>
      </div>
      <div class="panel stack">
        <div class="row"><h3>Corrección con IA</h3><span class="spacer"></span>
          <span class="chip ${st.ai_enabled ? "ok" : ""}">${st.ai_enabled ? `Activa: ${esc(st.label)}` : "Desactivada"}</span></div>
        <p class="small muted">Las preguntas generadas con IA deben citar un fragmento literal de la fuente; si la cita no aparece en el artículo descargado, se descartan. La corrección siempre se hace contra el texto de la fuente.</p>
        <div class="field"><span>Proveedor</span>
          <div class="seg" role="group" aria-label="Proveedor de IA">${Object.entries(st.providers).map(([k, v]) =>
            `<button type="button" data-prov="${k}" aria-pressed="${k === prov}">${esc(v.name)}${v.has_key ? " ✓" : ""}</button>`).join("")}</div></div>
        <form id="ai" class="stack">
          <label class="field"><span>${inf.keyLabel}</span>
            <input class="input" type="password" name="key" autocomplete="off" placeholder="${p.has_key ? "Hay una clave guardada" + (p.key_from === "entorno" ? " en el archivo .env" : "") : inf.keyPh}"></label>
          <p class="small muted">${inf.where}</p>
          <label class="field"><span>Modelo</span>
            <input class="input" name="model" list="models" value="${esc(p.model)}" placeholder="${esc(p.default_model)}">
            <datalist id="models">${inf.models.map(m => `<option value="${m}">`).join("")}</datalist></label>
          <p class="small muted">Los modelos «lite» o «haiku» son los más baratos y alcanzan para corregir. Para que la IA escriba preguntas de mejor calidad, conviene uno más capaz: <b>gemini-3.6-flash</b> o <b>claude-sonnet-5-5</b>.</p>
          <div class="actions">
            <button class="btn primary">Guardar y usar ${esc(p.name)}</button>
            <button type="button" class="btn" id="test" ${p.has_key && st.provider === prov ? "" : "disabled"}>Probar conexión</button>
            ${p.key_from === "ajustes" ? `<button type="button" class="btn danger" id="clear">Quitar clave</button>` : ""}
            <span class="small muted" id="ai-msg"></span>
          </div>
        </form>
      </div>
      <div class="panel" style="margin-top:16px">
        <h3>Buscadores con clave</h3>
        <p class="small muted" style="margin-top:6px">Opcionales. Wikipedia, Wikilibros, Wikiversidad, Google Libros, arXiv, Europe PMC y Stack Overflow funcionan sin clave. «Google (vía Gemini)» usa tu clave de Gemini y «Web (vía Claude)», la de Claude. Con cualquiera de estas claves también se recomiendan videos de YouTube en cada tema.</p>
        <form id="sk" class="stack" style="--gap:12px;margin-top:12px">
          ${[["google", "YouTube (clave de Google Cloud)", "AIza…", `Para recomendar videos en cada tema (100 búsquedas gratis por día). En <a href="https://console.cloud.google.com/apis/library/youtube.googleapis.com" target="_blank" rel="noopener">Google Cloud</a> activá la «YouTube Data API v3» y creá una clave en Credenciales. La clave de Gemini sirve solo si le habilitás también esa API.`],
             ["serper", "Serper: Google y Google Académico", "Clave de serper.dev", `Resultados de Google, Google Académico y videos. 2.500 búsquedas gratis al registrarte, sin tarjeta, en <a href="https://serper.dev" target="_blank" rel="noopener">serper.dev</a>.`],
             ["serpapi", "SerpApi: Google, Google Académico y YouTube", "Clave de serpapi.com", `250 búsquedas gratis por mes, sin tarjeta, en <a href="https://serpapi.com" target="_blank" rel="noopener">serpapi.com</a>.`],
             ["tavily", "Tavily", "tvly-…", `Buscador web para IA, 1.000 búsquedas gratis por mes sin tarjeta. Clave en <a href="https://app.tavily.com" target="_blank" rel="noopener">app.tavily.com</a>.`],
             ["brave", "Brave Search", "Clave de la API", `Buscador independiente. Clave en <a href="https://brave.com/search/api/" target="_blank" rel="noopener">brave.com/search/api</a> (revisá allí sus planes vigentes).`],
             ["openalex", "OpenAlex (opcional)", "Clave gratuita", `Sin clave funciona con un límite diario bajo; con la clave gratuita de <a href="https://openalex.org/settings/api" target="_blank" rel="noopener">openalex.org</a> el límite es 10 veces mayor.`]]
            .map(([k, label, ph, help]) => `
            <label class="field"><span>${label} ${st.searchers?.[k]?.has_key ? `<span class="chip ok">configurada</span>` : ""}</span>
              <input class="input" type="password" name="${k}" autocomplete="off" placeholder="${st.searchers?.[k]?.has_key ? "Hay una clave guardada" + (st.searchers[k].key_from === "entorno" ? " en el archivo .env" : "") : esc(ph)}"></label>
            <p class="small muted" style="margin-top:-6px">${help}${st.searchers?.[k]?.key_from === "ajustes" ? ` <button type="button" class="btn ghost small" data-clear-sk="${k}" style="padding:2px 8px">Quitar clave</button>` : ""}</p>`).join("")}
          <div class="actions"><button class="btn primary">Guardar claves</button></div>
        </form>
      </div>
      <div class="panel" style="margin-top:16px">
        <h3>Qué preguntas mostrar</h3>
        <label class="check" style="margin-top:10px"><input type="checkbox" id="only-ai" ${st.only_ai_questions ? "checked" : ""}>
          Cuando un tema tiene preguntas escritas por IA, ocultar las automáticas</label>
        <p class="small muted" style="margin-top:6px">Las preguntas automáticas se arman cortando oraciones del texto y a veces quedan pobres. Ocultarlas no borra tu progreso: si desmarcás la opción, vuelven.</p>
      </div>
      <div class="panel" style="margin-top:16px">
        <h3>Tus datos</h3>
        <p class="small muted" style="margin-top:6px">${ME && ME.user ? "Cada cuenta tiene su propia base de datos dentro de la carpeta <b>data/usuarios</b>. " : ""}Todo se guarda en la carpeta <b>data</b> junto al proyecto (archivo estudio.db), incluidas las claves que cargues acá: no compartas esa carpeta. Para hacer una copia de seguridad, copiala. Si borrás el contenedor de Docker, tus temas y tu progreso siguen ahí.</p>
      </div>
    </div>`;
    $$("[data-prov]").forEach(b => b.addEventListener("click", () => { prov = b.dataset.prov; draw(); }));
    $("#sk")?.addEventListener("submit", async e => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const keys = {};
      for (const k of ["google", "serper", "serpapi", "tavily", "brave", "openalex"]) { const v = (fd.get(k) || "").trim(); if (v) keys[k] = v; }
      if (!Object.keys(keys).length) { toast("No escribiste ninguna clave nueva"); return; }
      await api("/api/settings", { method: "POST", body: { search_keys: keys } });
      toast("Claves guardadas");
      viewSettings();
    });
    $$("[data-clear-sk]").forEach(b => b.addEventListener("click", async () => {
      await api("/api/settings", { method: "POST", body: { search_keys: { [b.dataset.clearSk]: "" } } });
      toast("Clave eliminada");
      viewSettings();
    }));
    $("#only-ai")?.addEventListener("change", async e => {
      await api("/api/settings", { method: "POST", body: { only_ai_questions: e.target.checked } });
      toast(e.target.checked ? "Se muestran solo las preguntas de IA en los temas que las tienen" : "Se muestran todas las preguntas");
    });
    $("#ai").addEventListener("submit", async e => {
      e.preventDefault();
      const fd = new FormData(e.target);
      try {
        await api("/api/settings", { method: "POST", body: { provider: prov, key: fd.get("key") || null, model: fd.get("model") || "" } });
        toast("Ajustes guardados");
        STATUS = null;
        viewSettings();
      } catch (err) { toast(err.message, true); }
    });
    $("#test")?.addEventListener("click", async () => {
      $("#ai-msg").innerHTML = `<span class="loader"></span>`;
      const r = await api("/api/settings/test-ai", { method: "POST" });
      $("#ai-msg").textContent = r.message;
    });
    $("#clear")?.addEventListener("click", async () => {
      await api("/api/settings", { method: "POST", body: { provider: prov, clear_key: true } });
      toast("Clave eliminada");
      viewSettings();
    });
    main.querySelector(".page").insertAdjacentHTML("beforeend", passwordPanel());
    bindPasswordPanel();
  };
  draw();
}

// ------------------------------------------------------------------------- //
// Videos de YouTube recomendados
// ------------------------------------------------------------------------- //
async function renderVideos(body, t, refresh = false) {
  body.innerHTML = `<p class="muted"><span class="loader"></span> Buscando videos que expliquen «${esc(t.title)}»…</p>`;
  let d;
  try { d = await api(`/api/topics/${t.id}/videos${refresh ? "?refresh=1" : ""}`); }
  catch (e) { body.innerHTML = `<div class="empty"><h3>No se pudieron buscar videos</h3><p class="muted">${esc(e.message)}</p></div>`; return; }
  const cards = d.videos.map(v => `
    <a class="video" href="${safeHref(v.url)}" target="_blank" rel="noopener">
      <span class="video-thumb"><img src="${safeHref(v.thumb)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">${v.duration ? `<b>${esc(v.duration)}</b>` : ""}</span>
      <span class="video-body">
        <span class="video-title">${esc(v.title)}</span>
        <span class="video-meta">${[v.channel, v.views, /^\d{4}-\d{2}-\d{2}$/.test(v.published || "") ? new Date(v.published + "T12:00:00").toLocaleDateString("es-AR", { month: "short", year: "numeric" }) : v.published].filter(Boolean).map(esc).join(" · ")}</span>
        ${v.description ? `<span class="video-desc">${esc(v.description)}</span>` : ""}
      </span>
    </a>`).join("");
  const sectionLinks = d.sections.length ? `
    <h3 style="margin-top:26px">Buscar por parte del tema</h3>
    <p class="small muted" style="margin-top:4px">Cada enlace abre la búsqueda en YouTube para esa sección.</p>
    <div class="chips" style="margin-top:10px">${d.sections.map(x => `<a class="chip yt-chip" href="${safeHref(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a>`).join("")}</div>` : "";
  body.innerHTML = `
    <div class="row" style="margin-bottom:14px;align-items:flex-start">
      <p class="muted grow">${d.videos.length
        ? `Videos recomendados para comprender el tema${d.via ? ` (encontrados con ${esc(d.via)})` : ""}. Se descartan los Shorts y los de menos de 2 minutos y medio. Mirá uno y después ponete a prueba con preguntas: así el video suma de verdad.`
        : d.needs_key
          ? `Para recomendar videos concretos hace falta una clave de búsqueda (en <a href="#/ajustes">Ajustes</a>): la de <b>YouTube</b> (gratis, 100 búsquedas por día) o la de Serper, SerpApi, Brave o Tavily si ya tenés alguna. Mientras tanto, podés buscar directo en YouTube.`
          : `No se encontraron videos.${d.errors.length ? " " + esc(d.errors.join(" ")) : ""}`}</p>
      <a class="btn" href="${safeHref(d.search_url)}" target="_blank" rel="noopener">Buscar en YouTube</a>
      ${d.providers.length ? `<button class="btn ghost" id="vid-refresh">Buscar otros</button>` : ""}
    </div>
    ${d.videos.length ? `<div class="videos">${cards}</div>` : ""}
    ${sectionLinks}
    <p class="small muted" style="margin-top:22px">Los videos son de terceros: contrastá lo que dicen con las fuentes del tema.</p>`;
  $("#vid-refresh")?.addEventListener("click", () => renderVideos(body, t, true));
}

// ------------------------------------------------------------------------- //
// Login
// ------------------------------------------------------------------------- //
let ME = null;

function viewLogin(mode) {
  document.body.classList.add("no-rail");
  const register = mode === "register" || (ME && ME.first_user);
  setTitle(register ? "Crear cuenta" : "Iniciar sesión");
  main.innerHTML = `
    <div class="login">
      <div class="login-brand"><span class="brand-word">Estudio</span><span class="brand-mark">Dunlosky</span></div>
      <h1>${register ? "Creá tu cuenta" : "Iniciá sesión"}</h1>
      <p class="lead">${register
        ? (ME && ME.first_user ? "Es la primera cuenta de esta app: si ya tenías temas guardados, quedan en esta cuenta." : "Tus temas, tu progreso y tus claves quedan separados de los de otras personas.")
        : "Entrá para ver tus temas y seguir estudiando."}</p>
      <form id="login-form" class="stack" autocomplete="on">
        <label class="field"><span>Usuario</span>
          <input class="input" name="username" required minlength="3" maxlength="32" pattern="[A-Za-z0-9._\\-]{3,32}"
            autocomplete="username" autocapitalize="none" spellcheck="false" title="Letras sin tilde, números, punto, guion o guion bajo"></label>
        <label class="field"><span>Contraseña</span>
          <input class="input" type="password" name="password" required minlength="8" maxlength="256"
            autocomplete="${register ? "new-password" : "current-password"}"></label>
        ${register ? `<label class="field"><span>Repetí la contraseña</span>
          <input class="input" type="password" name="password2" required minlength="8" maxlength="256" autocomplete="new-password"></label>
          <p class="small muted">Mínimo 8 caracteres. Usá una contraseña que no uses en otros sitios.</p>` : ""}
        <p class="login-error" id="login-error" role="alert" hidden></p>
        <button class="btn primary big">${register ? "Crear cuenta" : "Entrar"}</button>
      </form>
      ${ME && ME.first_user ? "" : register
        ? `<p class="small" style="margin-top:16px">¿Ya tenés cuenta? <a href="#" id="to-login">Iniciá sesión</a></p>`
        : (ME && ME.can_register ? `<p class="small" style="margin-top:16px">¿No tenés cuenta? <a href="#" id="to-register">Creá una</a></p>` : "")}
    </div>`;
  $("#to-login")?.addEventListener("click", e => { e.preventDefault(); viewLogin("login"); });
  $("#to-register")?.addEventListener("click", e => { e.preventDefault(); viewLogin("register"); });
  $("[name=username]").focus();
  $("#login-form").addEventListener("submit", async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const err = $("#login-error");
    err.hidden = true;
    if (register && fd.get("password") !== fd.get("password2")) {
      err.textContent = "Las contraseñas no coinciden."; err.hidden = false; return;
    }
    e.submitter.disabled = true;
    try {
      await api(register ? "/api/auth/register" : "/api/auth/login", { method: "POST",
        body: { username: fd.get("username").trim(), password: fd.get("password") } });
      location.hash = "#/";
      location.reload();
    } catch (ex) {
      err.textContent = ex.message; err.hidden = false;
      e.submitter.disabled = false;
    }
  });
}

async function logout() {
  try { await api("/api/auth/logout", { method: "POST" }); } catch (e) { /* igual se sale */ }
  try { localStorage.removeItem("pomo_state"); } catch (e) { /* nada */ }
  location.hash = "#/";
  location.reload();
}

(async function start() {
  try { ME = await api("/api/auth/me"); } catch (e) { ME = { auth_enabled: false }; }
  if (ME.auth_enabled && !ME.user) { viewLogin(); return; }
  if (ME.user) {
    const box = document.getElementById("user-box");
    box.hidden = false;
    box.querySelector("b").textContent = ME.user.username;
    box.querySelector("button").addEventListener("click", logout);
  }
  pomoInit();
  quickNoteInit();
  route();
})();
