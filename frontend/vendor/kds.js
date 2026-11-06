// SyncFlow multi-shop Kitchen Display: Staged (held by Sync-Fire) -> Cooking -> Ready.
// URL options: ?shop=<shop_id> picks the stall, &embed=1 hides the tab bar (used by the split-screen hub).
const API = "/api";
const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (secs) => `${Math.floor(secs / 60)}:${String(Math.floor(secs % 60)).padStart(2, "0")}`;

let audioCtx = null;
function chime() {
audioCtx = audioCtx || new AudioContext();
const now = audioCtx.currentTime;
[880, 1320].forEach((freq, i) => {
const osc = audioCtx.createOscillator();
const gain = audioCtx.createGain();
osc.frequency.value = freq;
gain.gain.setValueAtTime(0.2, now + i * 0.15);
gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.15 + 0.3);
osc.connect(gain).connect(audioCtx.destination);
osc.start(now + i * 0.15);
osc.stop(now + i * 0.15 + 0.3);
});
}

const params = new URLSearchParams(location.search);
let shops = [];
let currentShop = params.get("shop");

async function api(path, options = {}) {
  const res = await fetch(API + path, { headers: { "Content-Type": "application/json" }, ...options });
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

function renderTabs() {
  const shop = shops.find((s) => s.id === currentShop);
  if (params.get("embed")) {
    $("#tabs").innerHTML = `<span class="px-3 py-1 rounded bg-cyan-500 text-slate-950 font-semibold">${esc(shop?.name)}</span>`;
    return;
  }
  $("#tabs").innerHTML = shops
    .map((s, i) => `<button data-shop="${s.id}" class="px-3 py-1 rounded ${s.id === currentShop ? "bg-cyan-500 text-slate-950 font-semibold" : "bg-slate-800"}">Stall ${String.fromCharCode(65 + i)} · ${esc(s.name)}</button>`)
    .join("");
}

function ticketCard(t) {
  const lines = t.lines.map((l) => `<li>${l.quantity}× ${esc(l.name)}</li>`).join("");
  let badge = "";
  let action = "";
  if (t.status === "STAGED") {
    badge = `<span class="text-xs px-2 py-0.5 rounded bg-amber-400/20 text-amber-300">Held by AI · firing in ${fmt(t.seconds_until_fire)}</span>`;
  } else if (t.status === "COOKING") {
    badge = `<span class="cook-now text-xs px-2 py-0.5 rounded bg-red-500 text-white font-bold">COOK NOW</span>
             <span class="text-xs text-slate-400 ml-1">${fmt(t.seconds_until_ready)} to sync point</span>`;
    action = `<button data-ready="${t.id}" class="mt-2 w-full py-1.5 rounded bg-green-400 text-slate-950 text-sm font-semibold">Mark as Ready</button>`;
  } else {
    badge = `<span class="text-xs px-2 py-0.5 rounded bg-green-400/20 text-green-300">Waiting for pickup</span>`;
    action = `<button data-collected="${t.id}" class="mt-2 w-full py-1.5 rounded bg-slate-700 text-sm">Collected</button>`;
  }
  return `
    <div class="rounded-xl bg-slate-800 border border-slate-700 p-3 fade-in">
      <div class="flex justify-between text-sm font-semibold"><span>${esc(t.order_id)}</span><span class="text-slate-400">${esc(t.id)}</span></div>
      <ul class="text-sm text-slate-300 my-2">${lines}</ul>
      ${badge}${action}
    </div>`;
}

async function refresh() {
  if (!currentShop) return;
  try {
    const tickets = await api(`/queue/vendor/${currentShop}`);
    for (const col of ["STAGED", "COOKING", "READY"]) {
      const list = tickets.filter((t) => t.status === col);
      $(`#col-${col}`).innerHTML = list.length ? list.map(ticketCard).join("") : `<p class="text-xs text-slate-600">No tickets</p>`;
    }
  } catch (e) {
    console.error(e);
  }
}

async function setStatus(ticketId, status) {
  await api(`/queue/ticket/${ticketId}/action`, { method: "POST", body: JSON.stringify({ status }) });
  refresh();
}

document.addEventListener("click", (e) => {
  const tab = e.target.closest("[data-shop]");
  if (tab) {
    currentShop = tab.dataset.shop;
    history.replaceState(null, "", `?shop=${currentShop}`);
    renderTabs();
    refresh();
  }
  const ready = e.target.closest("[data-ready]");
  if (ready) setStatus(ready.dataset.ready, "READY");
  const collected = e.target.closest("[data-collected]");
  if (collected) setStatus(collected.dataset.collected, "COLLECTED");
});

(async function init() {
  shops = await api("/shops");
  if (!shops.some((s) => s.id === currentShop)) currentShop = shops[0]?.id;
  renderTabs();
  refresh();
  setInterval(refresh, 1000);
})();
