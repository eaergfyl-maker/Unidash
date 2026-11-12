// SyncFlow admin / helpdesk terminal: call next ticket, mark in-service / complete, add walk-ins.
const API = "/api";
const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let counters = [];

async function api(path, options = {}) {
  const res = await fetch(API + path, { headers: { "Content-Type": "application/json" }, ...options });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      // FastAPI sends a string for 404s and a list of errors for 422s.
      msg = typeof body.detail === "string" ? body.detail : body.detail?.[0]?.msg || msg;
    } catch {}
    throw new Error(msg);
  }
  return res.json();
}

// Short status line under the header: kind = "ok" | "info" | "error".
function notify(msg, kind = "ok") {
  const el = $("#admin-msg");
  const styles = { ok: "bg-mint/15 text-mint", info: "bg-white/5 text-mist", error: "bg-ember/20 text-ember" };
  el.className = `relative z-10 mx-6 mb-3 px-4 py-2 rounded-2xl text-sm ${styles[kind]}`;
  el.textContent = msg;
  clearTimeout(notify.timer);
  notify.timer = setTimeout(() => el.classList.add("hidden"), 4000);
}

// Disable a button while its request runs, so double clicks don't fire twice.
async function withBusy(btn, fn) {
  if (btn.disabled) return;
  btn.disabled = true;
  try {
    await fn();
  } catch (e) {
    notify(e.message, "error");
  } finally {
    btn.disabled = false;
  }
}

const counterId = () => $("#counter").value;

const STATUS_STYLE = {
  WAITING: "bg-navy/10 text-navy/70",
  CALLED: "bg-ember/25 text-[#b4471a]",
  IN_SERVICE: "bg-royal/15 text-royal",
  COMPLETED: "bg-mint/30 text-emerald-800",
};

function actionsFor(t) {
  if (t.status === "CALLED") return `<button data-act="${esc(t.id)}|IN_SERVICE" class="px-3 py-1.5 rounded-full bg-royal hover:bg-navy-2 text-white text-xs font-semibold whitespace-nowrap disabled:opacity-50">Start service</button>`;
  if (t.status === "IN_SERVICE") return `<button data-act="${esc(t.id)}|COMPLETED" class="px-3 py-1.5 rounded-full bg-mint text-navy text-xs font-semibold whitespace-nowrap disabled:opacity-50">Mark Complete</button>`;
  return "";
}

async function refresh() {
  let tickets;
  try {
    tickets = await api(`/queue/admin?counter_id=${encodeURIComponent(counterId())}`);
  } catch (e) {
    console.error(e);
    return;
  }
  const waiting = tickets.filter((t) => t.status === "WAITING").length;
  $("#waiting-count").textContent = `${waiting} waiting`;
  const serving = tickets.filter((t) => t.status === "CALLED" || t.status === "IN_SERVICE").at(-1);
  $("#now-serving").textContent = serving ? serving.number : "--";
  const html = tickets
    .map(
      (t) => `
      <tr class="border-t border-navy/10 ${t.status === "COMPLETED" ? "opacity-50" : ""}">
        <td class="py-3 font-display text-royal">${esc(t.number)}</td>
        <td class="font-medium">${esc(t.student_name)}</td>
        <td class="font-mono text-navy/70">${esc(t.matric_no)}</td>
        <td><span>${esc(t.option_name)}</span><br/><span class="text-xs text-navy/50">${esc(t.inquiry)}</span></td>
        <td><span class="px-2.5 py-0.5 rounded-full text-xs font-semibold whitespace-nowrap ${STATUS_STYLE[t.status]}">${t.status.replace("_", " ")}</span></td>
        <td class="text-right">${actionsFor(t)}</td>
      </tr>`
    )
    .join("") || `<tr><td colspan="6" class="py-6 text-center text-navy/50">No tickets at this counter yet</td></tr>`;
  // Only touch the table when something changed, so the 2 s poll can't swallow a button click.
  if (html !== refresh.lastHtml) {
    $("#queue").innerHTML = html;
    refresh.lastHtml = html;
  }
}

function renderOptions() {
  const counter = counters.find((c) => c.id === counterId());
  $("#option").innerHTML = counter.options.map((o) => `<option value="${o.id}">${esc(o.name)}</option>`).join("");
}

document.addEventListener("click", async (e) => {
  const act = e.target.closest("[data-act]");
  if (act) {
    const [id, status] = act.dataset.act.split("|");
    await withBusy(act, async () => {
      const t = await api(`/queue/ticket/${id}/action`, { method: "POST", body: JSON.stringify({ status }) });
      notify(status === "COMPLETED" ? `${t.number} completed` : `${t.number} now in service`);
    });
    refresh();
  }
});

$("#call-next").addEventListener("click", (e) =>
  withBusy(e.currentTarget, async () => {
    const t = await api(`/queue/admin/${encodeURIComponent(counterId())}/call-next`, { method: "POST" });
    if (t) notify(`Calling ${t.number} · ${t.student_name}`);
    else notify("Nobody is waiting at this counter", "info");
    await refresh();
  })
);

$("#counter").addEventListener("change", () => {
  renderOptions();
  refresh();
});

$("#join-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const data = Object.fromEntries(new FormData(form));
  data.student_name = data.student_name.trim();
  data.matric_no = data.matric_no.trim();
  if (!data.student_name || !data.matric_no) {
    notify("Student name and matric no. are required", "error");
    return;
  }
  await withBusy(form.querySelector("button"), async () => {
    const t = await api("/queue/admin/join", { method: "POST", body: JSON.stringify({ ...data, counter_id: counterId() }) });
    notify(`${t.student_name} joined as ${t.number}`);
    form.reset();
    renderOptions();
    await refresh();
  });
});

(async function init() {
  try {
    counters = await api("/services");
  } catch (e) {
    notify(`Could not load counters: ${e.message}`, "error");
    return;
  }
  $("#counter").innerHTML = counters.map((c) => `<option value="${c.id}">${esc(c.name)} · ${esc(c.location)}</option>`).join("");
  renderOptions();
  refresh();
  setInterval(refresh, 2000);
})();
