/* Estudio Dunlosky — Bloc de notas (con autoguardado) y nota rápida desde cualquier pantalla.
   Se carga antes que app.js; usa sus utilidades ($, api, esc, toast…) en tiempo de ejecución. */
"use strict";

const NOTE_COLORS = { "": "Sin color", amarillo: "Amarillo", verde: "Verde", azul: "Azul", rosa: "Rosa", violeta: "Violeta" };

function noteWhen(iso) {
  const d = new Date(iso);
  const mins = Math.round((Date.now() - d) / 60000);
  if (mins < 1) return "recién";
  if (mins < 60) return `hace ${mins} min`;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  if (d >= today) return `hoy ${d.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" })}`;
  return d.toLocaleDateString("es-AR", { day: "numeric", month: "short", year: d.getFullYear() === today.getFullYear() ? undefined : "numeric" });
}

function noteFileName(title) {
  return (strip(title).replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 60) || "nota");
}

async function viewNotebook(params) {
  setTitle("Bloc de notas");
  const topics = await api("/api/topics").catch(() => []);
  let notes = [];
  let current = null;       // nota abierta (completa)
  let dirty = false;
  let saving = null;        // promesa del guardado en curso
  let saveTimer = null;
  let query = "";
  let topicFilter = "";

  main.innerHTML = `
    <div class="page wide">
      <div class="page-head row" style="justify-content:space-between;align-items:flex-end">
        <div>
          <h1>Bloc de notas</h1>
          <p class="lead">Anotá dudas, ideas y resúmenes mientras estudiás. Se guarda solo mientras escribís.</p>
        </div>
        <button class="btn primary big" id="nb-new">Nueva nota</button>
      </div>
      <div class="notebook" id="notebook">
        <aside class="nb-list" aria-label="Notas">
          <div class="nb-tools">
            <input class="input" type="search" id="nb-q" placeholder="Buscar en tus notas" aria-label="Buscar en tus notas">
            <select class="input" id="nb-topic" aria-label="Filtrar por tema">
              <option value="">Todos los temas</option>
              ${topics.map(t => `<option value="${t.id}">${esc(t.title)}</option>`).join("")}
            </select>
          </div>
          <ul id="nb-items" class="nb-items"></ul>
        </aside>
        <section class="nb-editor" id="nb-editor" aria-label="Nota"></section>
      </div>
    </div>`;

  const list = $("#nb-items");
  const editor = $("#nb-editor");
  const nbRoot = $("#notebook");

  function renderList() {
    if (!notes.length) {
      list.innerHTML = `<li class="nb-empty muted small">${query || topicFilter ? "No hay notas que coincidan." : "Todavía no hay notas. Creá la primera con «Nueva nota»."}</li>`;
      return;
    }
    list.innerHTML = notes.map(n => `
      <li><button type="button" class="nb-item ${current && current.id === n.id ? "active" : ""}" data-id="${n.id}" data-color="${esc(n.color || "")}">
        <span class="nb-item-title">${n.pinned ? `<svg class="pin" viewBox="0 0 24 24" aria-label="Fijada"><path d="M9 3h6l-1 6 4 3v2h-5v6l-1 1-1-1v-6H5v-2l4-3z"/></svg>` : ""}${query ? highlightIn(n.title, query) : esc(n.title)}</span>
        ${n.snippet ? `<span class="nb-item-snip">${query ? highlightIn(n.snippet.slice(0, 110), query) : esc(n.snippet.slice(0, 110))}</span>` : n.words ? "" : `<span class="nb-item-snip"><i>Vacía</i></span>`}
        <span class="nb-item-meta">${esc(noteWhen(n.updated_at))}${n.topic_title ? ` · ${esc(n.topic_title)}` : ""}</span>
      </button></li>`).join("");
    $$(".nb-item", list).forEach(b => b.addEventListener("click", () => open(+b.dataset.id)));
  }

  async function load() {
    const qs = new URLSearchParams();
    if (query) qs.set("q", query);
    if (topicFilter) qs.set("topic_id", topicFilter);
    notes = await api("/api/notebook?" + qs);
    renderList();
  }

  function setStatus(text) { const s = $("#nb-status"); if (s) s.textContent = text; }

  async function saveNow() {
    clearTimeout(saveTimer);
    if (!current || !dirty) return saving;
    const body = { title: $("#nb-title").value, content: $("#nb-text").value };
    dirty = false;
    setStatus("Guardando…");
    saving = api(`/api/notebook/${current.id}`, { method: "PATCH", body })
      .then(n => {
        current = { ...current, ...n, content: body.content, raw_title: body.title };
        const i = notes.findIndex(x => x.id === n.id);
        if (i >= 0) notes[i] = n;
        if (!query && !topicFilter) { notes.sort((a, b) => (b.pinned - a.pinned) || (b.updated_at > a.updated_at ? 1 : -1)); }
        renderList();
        setStatus(dirty ? "Cambios sin guardar" : "Guardado");
      })
      .catch(e => { dirty = true; setStatus("No se pudo guardar: " + e.message); });
    return saving;
  }
  function scheduleSave() {
    dirty = true;
    setStatus("Cambios sin guardar");
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveNow, 700);
  }
  async function patch(fields, msg) {
    await saveNow();
    const n = await api(`/api/notebook/${current.id}`, { method: "PATCH", body: fields });
    current = { ...current, ...n };
    await load();
    drawEditor();
    if (msg) toast(msg);
  }

  function drawEditor() {
    nbRoot.classList.toggle("has-note", !!current);
    if (!current) {
      editor.innerHTML = `<div class="nb-placeholder"><p class="muted">Elegí una nota de la lista o creá una nueva.</p>
        <p class="small muted">Tip: con <kbd>#</kbd> al principio de una línea hacés un título, y con <kbd>-</kbd> una lista. Así queda prolija al pasarla a PDF.</p></div>`;
      return;
    }
    const n = current;
    editor.innerHTML = `
      <div class="nb-bar">
        <button type="button" class="btn ghost small nb-back" id="nb-back">← Notas</button>
        <select class="input nb-topic-pick" id="nb-topic-pick" aria-label="Tema de la nota">
          <option value="0">Sin tema</option>
          ${topics.map(t => `<option value="${t.id}" ${n.topic_id === t.id ? "selected" : ""}>${esc(t.title)}</option>`).join("")}
        </select>
        <div class="nb-colors" role="group" aria-label="Color">
          ${Object.entries(NOTE_COLORS).map(([k, v]) => `<button type="button" class="nb-color" data-c="${k}" title="${v}" aria-label="${v}" aria-pressed="${(n.color || "") === k}"></button>`).join("")}
        </div>
        <button type="button" class="btn ghost small" id="nb-pin" aria-pressed="${n.pinned}">${n.pinned ? "Desfijar" : "Fijar arriba"}</button>
      </div>
      <div class="nb-paper" data-color="${esc(n.color || "")}">
        <input class="nb-title" id="nb-title" maxlength="200" placeholder="Título" value="${esc(n.raw_title || "")}" aria-label="Título">
        <textarea class="nb-text" id="nb-text" maxlength="100000" placeholder="Escribí acá…" aria-label="Contenido de la nota" spellcheck="true">${esc(n.content || "")}</textarea>
      </div>
      <div class="nb-foot">
        <span class="small muted" id="nb-status">${n.updated_at ? "Guardado " + esc(noteWhen(n.updated_at)) : ""}</span>
        <span class="small muted" id="nb-count"></span>
        <span class="grow"></span>
        ${n.topic_id ? `<a class="btn ghost small" href="#/tema/${n.topic_id}">Ir al tema</a>` : ""}
        <button type="button" class="btn small" id="nb-txt">Descargar .txt</button>
        <button type="button" class="btn small" id="nb-pdf">Guardar PDF</button>
        <button type="button" class="btn ghost small danger" id="nb-del">Borrar</button>
      </div>`;
    const text = $("#nb-text");
    const count = () => {
      const w = text.value.trim() ? text.value.trim().split(/\s+/).length : 0;
      $("#nb-count").textContent = plural(w, "palabra", "palabras");
    };
    count();
    $("#nb-title").addEventListener("input", scheduleSave);
    text.addEventListener("input", () => { scheduleSave(); count(); });
    text.addEventListener("keydown", e => {
      // Tab inserta sangría en vez de salir del cuadro
      if (e.key === "Tab" && !e.shiftKey) {
        e.preventDefault();
        const { selectionStart: a, selectionEnd: b } = text;
        text.setRangeText("  ", a, b, "end");
        scheduleSave();
      }
    });
    $("#nb-back").addEventListener("click", async () => { await saveNow(); current = null; drawEditor(); renderList(); history.replaceState(null, "", "#/notas"); });
    $("#nb-topic-pick").addEventListener("change", e => patch({ topic_id: +e.target.value }, "Tema actualizado"));
    $$(".nb-color").forEach(b => b.addEventListener("click", () => patch({ color: b.dataset.c })));
    $("#nb-pin").addEventListener("click", () => patch({ pinned: !current.pinned }, current.pinned ? "Nota desfijada" : "Nota fijada arriba"));
    $("#nb-txt").addEventListener("click", () => {
      const t = $("#nb-title").value.trim();
      const blob = new Blob([(t ? t + "\n\n" : "") + text.value], { type: "text/plain;charset=utf-8" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = noteFileName(t || current.title) + ".txt";
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    });
    $("#nb-pdf").addEventListener("click", async () => {
      await saveNow();
      location.href = `/api/notebook/${current.id}/export.pdf`;
    });
    $("#nb-del").addEventListener("click", async () => {
      if (!confirm("¿Borrar esta nota? No se puede deshacer.")) return;
      clearTimeout(saveTimer); dirty = false;
      await api(`/api/notebook/${current.id}`, { method: "DELETE" });
      current = null;
      history.replaceState(null, "", "#/notas");
      await load();
      drawEditor();
      toast("Nota borrada");
    });
  }

  async function open(id) {
    await saveNow();
    current = await api(`/api/notebook/${id}`);
    history.replaceState(null, "", `#/notas?id=${id}`);
    renderList();
    drawEditor();
    $("#nb-text").focus();
  }

  async function create(topicId = null) {
    await saveNow();
    const n = await api("/api/notebook", { method: "POST", body: { title: "", content: "", topic_id: topicId } });
    query = ""; $("#nb-q").value = "";
    await load();
    current = n;
    history.replaceState(null, "", `#/notas?id=${n.id}`);
    renderList();
    drawEditor();
    $("#nb-title").focus();
  }

  $("#nb-new").addEventListener("click", () => create(topicFilter ? +topicFilter : null).catch(e => toast("No se pudo crear la nota: " + e.message, true)));
  const onRejection = ev => { if (location.hash.startsWith("#/notas")) { toast(String(ev.reason?.message || ev.reason), true); } };
  let qTimer;
  $("#nb-q").addEventListener("input", e => { clearTimeout(qTimer); qTimer = setTimeout(() => { query = e.target.value.trim(); load(); }, 250); });
  $("#nb-topic").addEventListener("change", e => { topicFilter = e.target.value; load(); });

  const onKey = e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s" && current) { e.preventDefault(); dirty = true; saveNow(); }
  };
  const onUnload = () => {
    // al cerrar la pestaña se manda lo pendiente sin esperar respuesta
    if (current && dirty) {
      fetch(`/api/notebook/${current.id}`, { method: "PATCH", keepalive: true, headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: $("#nb-title").value, content: $("#nb-text").value }) });
    }
  };
  document.addEventListener("keydown", onKey);
  window.addEventListener("beforeunload", onUnload);
  cleanup = () => {
    window.removeEventListener("unhandledrejection", onRejection);
    document.removeEventListener("keydown", onKey);
    window.removeEventListener("beforeunload", onUnload);
    if (current && dirty) saveNow();
  };

  try {
    await load();
  } catch (e) {
    // si el servidor es de una versión anterior (sin bloc de notas) se avisa qué hacer
    const old = /not found/i.test(e.message);
    main.innerHTML = `<div class="page narrow"><div class="empty"><h2>El bloc de notas no está disponible</h2>
      <p class="muted">${old ? "El servidor todavía tiene la versión anterior de la app. En tu computadora, cerrá la app con <b>detener.bat</b> y volvé a abrirla con <b>iniciar.bat</b> (reconstruye la app). En Render, esperá a que termine el deploy del último <i>push</i>." : esc(e.message)}</p></div></div>`;
    return;
  }
  // los botones "Nueva nota" no deben quedar sin respuesta si falla la creación
  window.addEventListener("unhandledrejection", onRejection);
  if (params.get("id")) {
    try { await open(+params.get("id")); } catch (e) { drawEditor(); }
  } else if (params.get("tema")) {
    await create(+params.get("tema"));
  } else {
    drawEditor();
  }
}

// ------------------------------------------------------------------------- //
// Nota rápida: botón flotante disponible en todas las pantallas
// ------------------------------------------------------------------------- //
function quickNoteInit() {
  const btn = document.getElementById("quick-note");
  const dlg = document.getElementById("quick-note-dialog");
  if (!btn || !dlg) return;
  btn.hidden = false;
  const sync = () => { btn.hidden = location.hash.startsWith("#/notas"); };
  window.addEventListener("hashchange", sync);
  sync();
  btn.addEventListener("click", () => {
    const m = location.hash.match(/^#\/(?:tema|tecnica\/\w+)\/(\d+)/);
    const topicId = m ? +m[1] : null;
    let draft = "";
    try { draft = localStorage.getItem("nota_rapida") || ""; } catch (e) { /* sin almacenamiento */ }
    dlg.innerHTML = `
      <form method="dialog" class="qn">
        <h3>Nota rápida</h3>
        <p class="small muted">${topicId ? "Se guarda en tu bloc de notas, asociada a este tema." : "Se guarda en tu bloc de notas."}</p>
        <textarea class="input" id="qn-text" rows="7" maxlength="100000" placeholder="Una duda, una idea, algo para repasar…">${esc(draft)}</textarea>
        <div class="actions">
          <button class="btn primary" value="save" id="qn-save">Guardar</button>
          <button class="btn" value="cancel" formnovalidate>Cerrar</button>
          <a class="small" href="#/notas" id="qn-all">Abrir el bloc</a>
        </div>
      </form>`;
    const ta = $("#qn-text", dlg);
    ta.addEventListener("input", () => { try { localStorage.setItem("nota_rapida", ta.value); } catch (e) { /* nada */ } });
    $("#qn-all", dlg).addEventListener("click", () => dlg.close());
    $("#qn-save", dlg).addEventListener("click", async e => {
      e.preventDefault();
      const content = ta.value.trim();
      if (!content) { dlg.close(); return; }
      try {
        await api("/api/notebook", { method: "POST", body: { title: "", content, topic_id: topicId } });
        try { localStorage.removeItem("nota_rapida"); } catch (err) { /* nada */ }
        dlg.close();
        toast("Nota guardada en tu bloc");
      } catch (err) { toast(err.message, true); }
    });
    dlg.showModal();
    ta.focus();
  });
}
