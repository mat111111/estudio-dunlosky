/* Estudio Dunlosky — Conceptos clicables y explicaciones "¿por qué?".
   Se carga antes que app.js; usa sus utilidades en tiempo de ejecución. */
"use strict";

function escRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

/** Marca como clicables los conceptos clave dentro de un texto (solo la primera aparición de cada uno
 *  por párrafo, para no llenar todo de enlaces). Devuelve HTML seguro. */
function linkConcepts(text, terms, used) {
  if (!terms || !terms.length) return esc(text);
  const sorted = [...terms].sort((a, b) => b.length - a.length);
  const re = new RegExp(`(?<![\\p{L}\\d])(${sorted.map(escRe).join("|")})(?![\\p{L}\\d])`, "giu");
  let out = "";
  let last = 0;
  for (const m of text.matchAll(re)) {
    const key = m[0].toLowerCase();
    if (used.has(key)) continue;
    used.add(key);
    out += esc(text.slice(last, m.index)) +
      `<button type="button" class="concept" data-term="${esc(m[0])}" title="Tocá para ver qué es y por qué">${esc(m[0])}</button>`;
    last = m.index + m[0].length;
  }
  return out + esc(text.slice(last));
}

function bindConceptButtons(root, topicId) {
  root.querySelectorAll(".concept").forEach(b => b.addEventListener("click", () => openConcept(topicId, b.dataset.term)));
}

async function openConcept(topicId, term) {
  const dlg = document.getElementById("concept-dialog");
  dlg.innerHTML = `<div class="concept-box"><div class="row"><h2>${esc(term)}</h2><span class="spacer"></span>
    <button class="btn ghost" data-close aria-label="Cerrar">Cerrar</button></div>
    <p class="muted" style="margin-top:12px"><span class="loader"></span> Buscando en la fuente…</p></div>`;
  dlg.querySelector("[data-close]").addEventListener("click", () => dlg.close());
  if (!dlg.open) dlg.showModal();
  let d;
  try {
    d = await api(`/api/topics/${topicId}/concept?term=${encodeURIComponent(term)}`);
  } catch (e) {
    dlg.querySelector(".concept-box").insertAdjacentHTML("beforeend", `<p class="callout">${esc(e.message)}</p>`);
    return;
  }
  const ex = d.explanation;
  dlg.innerHTML = `
    <div class="concept-box">
      <div class="row"><h2>${esc(d.term)}</h2><span class="spacer"></span>
        <button class="btn ghost" data-close aria-label="Cerrar">Cerrar</button></div>
      ${d.definition ? `<div class="evidence"><div class="label">Qué dice la fuente</div><q>${highlightIn(d.definition, d.term)}</q></div>` : ""}
      ${ex ? `
        <div class="explain">
          ${ex.que_es ? `<h3>Qué es</h3><p>${esc(ex.que_es)}</p>` : ""}
          ${ex.por_que ? `<h3>Por qué</h3><p>${esc(ex.por_que)}</p>` : ""}
          ${ex.ejemplo ? `<h3>Ejemplo</h3><p>${esc(ex.ejemplo)}</p>` : ""}
          ${ex.relacion ? `<h3>Se relaciona con</h3><p>${esc(ex.relacion)}</p>` : ""}
          <p class="small muted">Explicación generada con IA (${esc(d.by || "")}) a partir de las oraciones de la fuente. Ante una duda, la fuente manda.</p>
        </div>`
      : d.reasons.length ? `
        <div class="explain"><h3>Por qué, según la fuente</h3>
          ${d.reasons.map(r => `<p>«${highlightIn(r.text, d.term)}»</p>`).join("")}</div>`
      : ""}
      ${!ex && !d.ai_enabled ? `<p class="callout info small">Para una explicación con tus propias palabras (qué es, por qué y un ejemplo), activá la IA en <a href="#/ajustes">Ajustes</a>.</p>` : ""}
      ${d.mentions.length > 1 ? `<details class="mentions"><summary>Aparece ${plural(d.total_mentions, "vez", "veces")} en el tema</summary>
        <ul>${d.mentions.map(m => `<li><span class="small muted">${esc(m.section_title)}</span><br>${highlightIn(m.text, d.term)}</li>`).join("")}</ul></details>` : ""}
      <div class="actions">
        <button class="btn primary" data-practice>Practicar este concepto</button>
      </div>
    </div>`;
  dlg.querySelector("[data-close]").addEventListener("click", () => dlg.close());
  dlg.querySelector("[data-practice]").addEventListener("click", () => {
    dlg.close();
    startSession({ mode: "terms", topic_ids: [topicId], terms: [d.term], n: 1, tech: "practica", back: location.hash });
  });
}

/** Botón "¿Por qué es así?" debajo de la corrección de una pregunta. */
function bindExplainButton(container, item, preset) {
  const btn = container.querySelector("[data-explain]");
  const box = container.querySelector(".why-box");
  if (!btn || !box) return;
  const show = d => {
    if (d.explanation) {
      box.innerHTML = `<h3>Por qué</h3><p>${esc(d.explanation)}</p>${d.by === "ia" ? `<p class="small muted">Explicación generada con IA a partir de la fuente.</p>` : ""}`;
    } else if (d.around && d.around.length) {
      box.innerHTML = `<h3>El contexto en la fuente</h3><p>${d.around.map(esc).join(" ")}</p>
        ${d.ai_enabled === false ? `<p class="small muted">Con la IA activada en Ajustes, acá aparece una explicación de por qué la respuesta es esa.</p>` : ""}`;
    } else {
      box.innerHTML = `<p class="small muted">No hay más contexto para esta pregunta.</p>`;
    }
    box.hidden = false;
    btn.remove();
  };
  if (preset) { btn.addEventListener("click", () => show({ explanation: preset, by: "ia" })); return; }
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    btn.innerHTML = `<span class="loader" style="width:14px;height:14px"></span> Pensando…`;
    try { show(await api(`/api/items/${item.id}/explain`, { method: "POST" })); }
    catch (e) { btn.disabled = false; btn.textContent = "¿Por qué es así?"; toast(e.message, true); }
  });
}
