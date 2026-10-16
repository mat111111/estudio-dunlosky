/* Estudio Dunlosky — Lista de tareas (día, mes, año) con aviso de urgencia por color.
   Se carga antes que app.js; usa sus utilidades en tiempo de ejecución. */
"use strict";

const HORIZONS = { dia: "Día", mes: "Mes", anio: "Año" };
const UNITS = { dias: "días", semanas: "semanas", meses: "meses" };

function isoLocal(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function parseLocal(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}
function todayLocal() { const d = new Date(); d.setHours(0, 0, 0, 0); return d; }
function daysBetween(a, b) { return Math.round((b - a) / 86400000); }
function fmtDate(iso) {
  return parseLocal(iso).toLocaleDateString("es-AR", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
}

/** Urgencia de una tarea.
 *  - 7 días o más: tranquila (verde).
 *  - menos de una semana: el color pasa de amarillo (6 días) a rojo (vence hoy).
 *  - vencida: rojo intenso. */
function taskUrgency(t) {
  const left = daysBetween(todayLocal(), parseLocal(t.due_date));
  if (t.done) return { left, hue: 150, level: "done", label: "Completada" };
  if (left < 0) return { left, hue: 356, level: "overdue", label: `Venció hace ${plural(-left, "día", "días")}` };
  if (left === 0) return { left, hue: 2, level: "urgent", label: "Vence hoy" };
  if (left < 7) {
    const hue = Math.round(4 + (48 * (left - 1)) / 5); // 1 día: rojo, 6 días: amarillo
    return { left, hue, level: "urgent", label: left === 1 ? "Vence mañana" : `Faltan ${left} días` };
  }
  let label = `Faltan ${left} días`;
  if (left >= 60) label = `Faltan ${Math.round(left / 30)} meses`;
  else if (left >= 14) label = `Faltan ${Math.round(left / 7)} semanas`;
  return { left, hue: 150, level: "calm", label };
}

function taskRow(t, compact = false) {
  const u = taskUrgency(t);
  const created = new Date(t.created_at);
  created.setHours(0, 0, 0, 0);
  const total = Math.max(1, daysBetween(created, parseLocal(t.due_date)));
  const elapsed = Math.min(1, Math.max(0, daysBetween(created, todayLocal()) / total));
  return `
    <li class="task ${u.level}" style="--h:${u.hue}" data-id="${t.id}">
      ${compact ? "" : `<input type="checkbox" class="t-done" ${t.done ? "checked" : ""} aria-label="Marcar “${esc(t.title)}” como hecha">`}
      <div class="grow">
        <div class="t-title">${esc(t.title)}</div>
        <div class="t-meta">
          <span>${HORIZONS[t.horizon] || ""}</span>
          <span>Vence el ${esc(fmtDate(t.due_date))}</span>
          ${t.topic_title ? `<span><span class="dot" style="--hue:${t.topic_hue}"></span>${esc(t.topic_title)}</span>` : ""}
          ${t.pomodoros ? `<span>${plural(t.pomodoros, "pomodoro", "pomodoros")}</span>` : ""}
        </div>
        ${!t.done && !compact ? `<div class="t-bar" title="Tiempo transcurrido"><i style="width:${Math.round(elapsed * 100)}%"></i></div>` : ""}
      </div>
      <span class="t-badge">${esc(u.label)}</span>
      ${compact || t.done ? "" : `
        <button class="btn ghost t-pomo" title="Empezar un pomodoro para esta tarea">Pomodoro</button>
        <label class="btn ghost t-date" title="Cambiar la fecha límite">Fecha<input type="date" value="${t.due_date}" aria-label="Nueva fecha límite"></label>`}
      ${compact ? "" : `<button class="btn ghost t-del" aria-label="Eliminar tarea">Eliminar</button>`}
    </li>`;
}

function defaultAmount(horizon) {
  const today = todayLocal();
  if (horizon === "mes") {
    const end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
    return { amount: Math.max(1, daysBetween(today, end)), unit: "dias" };
  }
  if (horizon === "anio") {
    const end = new Date(today.getFullYear(), 11, 31);
    return { amount: Math.max(1, Math.round(daysBetween(today, end) / 30)), unit: "meses" };
  }
  return { amount: 0, unit: "dias" };
}
function addTime(amount, unit) {
  const d = todayLocal();
  if (unit === "meses") d.setMonth(d.getMonth() + amount);
  else d.setDate(d.getDate() + amount * (unit === "semanas" ? 7 : 1));
  return d;
}

async function viewTasks(params) {
  setTitle("Tareas");
  const tab = params.get("periodo") || "todas";
  const [tasks, topics] = await Promise.all([api("/api/tasks"), api("/api/topics").catch(() => [])]);
  const open = tasks.filter(t => !t.done);
  const done = tasks.filter(t => t.done);
  const shown = open.filter(t => tab === "todas" || t.horizon === tab);
  const counts = { todas: open.length, dia: 0, mes: 0, anio: 0 };
  open.forEach(t => counts[t.horizon]++);
  const urgent = open.filter(t => taskUrgency(t).left < 7).length;
  let horizon = tab === "todas" ? "dia" : tab;
  const def = defaultAmount(horizon);

  main.innerHTML = `
    <div class="page narrow">
      <div class="page-head">
        <h1>Tareas</h1>
        <p class="lead">Organizá lo que tenés que hacer en el día, el mes y el año. Cuando a una tarea le queda menos de una semana, su color pasa de amarillo a rojo.</p>
      </div>

      <form class="panel stack" id="t-form">
        <label class="field"><span>Qué tenés que hacer</span>
          <input class="input" name="title" required maxlength="200" placeholder="Por ejemplo: estudiar la Unidad 3 para el parcial"></label>
        <div class="row" style="align-items:flex-end;gap:18px">
          <div class="field"><span>Periodo</span>
            <div class="seg" role="group" aria-label="Periodo">${Object.entries(HORIZONS).map(([k, v]) =>
              `<button type="button" data-h="${k}" aria-pressed="${k === horizon}">${v}</button>`).join("")}</div></div>
          <div class="field"><span>Tiempo disponible</span>
            <div class="row" style="gap:8px">
              <input class="input" type="number" min="0" max="999" name="amount" value="${def.amount}" style="width:90px" aria-label="Cantidad">
              <select class="input" name="unit" style="width:auto" aria-label="Unidad">${Object.entries(UNITS).map(([k, v]) =>
                `<option value="${k}" ${k === def.unit ? "selected" : ""}>${v}</option>`).join("")}</select>
            </div></div>
          <label class="field"><span>Fecha límite</span><input class="input" type="date" name="due" required></label>
        </div>
        ${topics.length ? `<label class="field"><span>Tema relacionado (opcional)</span>
          <select class="input" name="topic"><option value="">Ninguno</option>${topics.map(tp => `<option value="${tp.id}">${esc(tp.title)}</option>`).join("")}</select></label>` : ""}
        <div class="actions"><button class="btn primary">Agregar tarea</button><span class="small muted" id="t-left"></span></div>
      </form>

      <div class="tabs" role="tablist">
        ${[["todas", "Todas"], ["dia", "Día"], ["mes", "Mes"], ["anio", "Año"]].map(([k, l]) =>
          `<button role="tab" data-tab="${k}" aria-selected="${tab === k}">${l}${counts[k] ? ` (${counts[k]})` : ""}</button>`).join("")}
      </div>
      ${urgent ? `<p class="callout small" style="margin-bottom:14px">${plural(urgent, "tarea vence", "tareas vencen")} en menos de una semana.</p>` : ""}
      ${shown.length ? `<ul class="list tasks">${shown.map(t => taskRow(t)).join("")}</ul>`
        : `<div class="empty"><h3>No hay tareas pendientes ${tab === "todas" ? "" : `en «${HORIZONS[tab]}»`}</h3><p class="muted">Agregá una arriba con su fecha límite.</p></div>`}
      <div class="urg-legend" aria-hidden="true"><span>Vencida</span><i></i><span>1 semana</span><b></b><span>Con tiempo</span></div>
      ${done.length ? `<details class="done-list"><summary>Completadas (${done.length})</summary><ul class="list tasks">${done.map(t => taskRow(t)).join("")}</ul></details>` : ""}
    </div>`;

  const form = $("#t-form");
  const syncDate = () => {
    const d = addTime(Math.max(0, +form.amount.value || 0), form.unit.value);
    form.due.value = isoLocal(d);
    showLeft();
  };
  const showLeft = () => {
    if (!form.due.value) return;
    const u = taskUrgency({ due_date: form.due.value, done: false });
    $("#t-left").textContent = u.left < 0 ? "La fecha ya pasó." : u.left === 0 ? "Vence hoy." : `Tenés ${plural(u.left, "día", "días")}.`;
  };
  syncDate();
  form.amount.addEventListener("input", syncDate);
  form.unit.addEventListener("change", syncDate);
  form.due.addEventListener("change", () => {
    const left = daysBetween(todayLocal(), parseLocal(form.due.value));
    form.amount.value = Math.max(0, left);
    form.unit.value = "dias";
    showLeft();
  });
  $$("[data-h]").forEach(b => b.addEventListener("click", () => {
    horizon = b.dataset.h;
    $$("[data-h]").forEach(x => x.setAttribute("aria-pressed", x === b));
    const d = defaultAmount(horizon);
    form.amount.value = d.amount;
    form.unit.value = d.unit;
    syncDate();
  }));
  form.addEventListener("submit", async e => {
    e.preventDefault();
    try {
      await api("/api/tasks", { method: "POST", body: {
        title: form.elements.title.value.trim(), horizon, due_date: form.due.value,
        topic_id: form.topic && form.topic.value ? +form.topic.value : null } });
      toast("Tarea agregada");
      viewTasks(new URLSearchParams(`periodo=${tab}`));
    } catch (err) { toast(err.message, true); }
  });
  $$("[data-tab]").forEach(b => b.addEventListener("click", () => { location.hash = `#/tareas?periodo=${b.dataset.tab}`; }));
  bindTaskRows(tasks, () => viewTasks(new URLSearchParams(`periodo=${tab}`)));
}

function bindTaskRows(tasks, refresh) {
  const byId = Object.fromEntries(tasks.map(t => [t.id, t]));
  $$(".task").forEach(li => {
    const t = byId[+li.dataset.id];
    if (!t) return;
    li.querySelector(".t-done")?.addEventListener("change", async e => {
      await api(`/api/tasks/${t.id}`, { method: "PATCH", body: { done: e.target.checked } });
      if (e.target.checked) toast("¡Bien hecho! Tarea completada");
      refresh();
    });
    li.querySelector(".t-del")?.addEventListener("click", async () => {
      if (!confirm(`¿Eliminar “${t.title}”?`)) return;
      await api(`/api/tasks/${t.id}`, { method: "DELETE" });
      refresh();
    });
    li.querySelector(".t-pomo")?.addEventListener("click", () => startPomodoroForTask(t));
    li.querySelector(".t-date input")?.addEventListener("change", async e => {
      if (!e.target.value) return;
      await api(`/api/tasks/${t.id}`, { method: "PATCH", body: { due_date: e.target.value } });
      toast("Fecha actualizada");
      refresh();
    });
  });
}
