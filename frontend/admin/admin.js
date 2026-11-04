// SyncFlow admin / helpdesk terminal: call next ticket, mark in-service / complete, add walk-ins.
const API = "/api";
const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let counters = [];

async function api(path, options = {}) {
  const res = await fetch(API + path, { headers: { "Content-Type": "application/json" }, ...options });
  if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
  return res.json();
}

const counterId = () => $("#counter").value;

const STATUS_STYLE = {
  WAITING: "text-slate-400",
  CALLED: "text-amber-300",
  IN_SERVICE: "text-cyan-300",
  COMPLETED: "text-green-400",
};

function actionsFor(t) {
  if (t.status === "CALLED") return `<button data-act="${t.id}|IN_SERVICE" class="px-2 py-1 rounded bg-cyan-600 text-xs">Start service</button>`;
  if (t.status === "IN_SERVICE") return `<button data-act="${t.id}|COMPLETED" class="px-2 py-1 rounded bg-green-500 text-slate-950 text-xs font-semibold">Mark Complete</button>`;
  return "";
}

async function refresh() {
  const tickets = await api(`/queue/admin?counter_id=${counterId()}`);
  const serving = tickets.filter((t) => t.status === "CALLED" || t.status === "IN_SERVICE").at(-1);
  $("#now-serving").textContent = serving ? serving.number : "--";
  $("#queue").innerHTML = tickets
    .map(
      (t) => `
      <tr class="border-t border-slate-800 ${t.status === "COMPLETED" ? "opacity-50" : ""}">
        <td class="py-2 font-mono font-bold">${esc(t.number)}</td>
        <td>${esc(t.student_name)}</td>
        <td class="font-mono">${esc(t.matric_no)}</td>
        <td><span class="text-slate-300">${esc(t.option_name)}</span><br/><span class="text-xs text-slate-500">${esc(t.inquiry)}</span></td>
        <td class="${STATUS_STYLE[t.status]}">${t.status.replace("_", " ")}</td>
        <td class="text-right">${actionsFor(t)}</td>
      </tr>`
    )
    .join("");
}

function renderOptions() {
  const counter = counters.find((c) => c.id === counterId());
  $("#option").innerHTML = counter.options.map((o) => `<option value="${o.id}">${esc(o.name)}</option>`).join("");
}

document.addEventListener("click", async (e) => {
  const act = e.target.closest("[data-act]");
  if (act) {
    const [id, status] = act.dataset.act.split("|");
    await api(`/queue/ticket/${id}/action`, { method: "POST", body: JSON.stringify({ status }) });
    refresh();
  }
});

$("#call-next").addEventListener("click", async () => {
  await api(`/queue/admin/${counterId()}/call-next`, { method: "POST" });
  refresh();
});

$("#counter").addEventListener("change", () => {
  renderOptions();
  refresh();
});

$("#join-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target));
  await api("/queue/admin/join", { method: "POST", body: JSON.stringify({ ...data, counter_id: counterId() }) });
  e.target.reset();
  renderOptions();
  refresh();
});

(async function init() {
  counters = await api("/services");
  $("#counter").innerHTML = counters.map((c) => `<option value="${c.id}">${esc(c.name)} · ${esc(c.location)}</option>`).join("");
  renderOptions();
  refresh();
  setInterval(refresh, 2000);
})();
