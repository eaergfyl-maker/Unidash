// SyncFlow multi-shop Kitchen Display: Staged (held by Sync-Fire) -> Cooking -> Ready.
// URL options: ?shop=<shop_id> picks the stall, &embed=1 hides the tab bar (used by the split-screen hub).
const API = "/api";
const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (secs) => `${Math.floor(secs / 60)}:${String(Math.floor(secs % 60)).padStart(2, "0")}`;

const COLUMNS = ["STAGED", "COOKING", "READY"];
const FIRE_HIGHLIGHT_MS = 6000; // how long a just-fired ticket glows

const params = new URLSearchParams(location.search);
const embedded = Boolean(params.get("embed"));
let shops = [];
let currentShop = params.get("shop");

// Per-stall view state, reset when switching tabs.
let lastStatus = null;           // ticket id -> status from the previous poll (null = first poll)
let firedAt = new Map();         // ticket id -> time it moved STAGED -> COOKING
const pending = new Set();       // ticket ids with an action request in flight
const colSignature = {};         // column -> signature of what is rendered, to avoid needless rebuilds

// ---------- sound ----------
// Browsers only allow audio after a user gesture, so the chime stays off until the
// kitchen taps the sound button (or anywhere on the board).
let audioCtx = null;
let soundOn = false;

function unlockSound() {
  audioCtx = audioCtx || new AudioContext();
  if (audioCtx.state === "suspended") audioCtx.resume();
  soundOn = true;
  renderSoundButton();
}

function chime() {
  if (!soundOn || !audioCtx) return;
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

function renderSoundButton() {
  const btn = $("#sound-btn");
  btn.textContent = soundOn ? "🔔 Sound on" : "🔕 Tap for sound";
  btn.className = `px-3 py-1 rounded-full text-xs whitespace-nowrap ${soundOn ? "bg-white/5 text-mist/80" : "bg-ember/20 text-ember"}`;
}

// ---------- api ----------
async function api(path, options = {}) {
  const res = await fetch(API + path, { headers: { "Content-Type": "application/json" }, ...options });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : body.detail?.[0]?.msg || msg;
    } catch {}
    throw new Error(msg);
  }
  return res.json();
}

function showError(msg) {
  const el = $("#kds-error");
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(showError.timer);
  showError.timer = setTimeout(() => el.classList.add("hidden"), 4000);
}

// ---------- rendering ----------
function renderTabs() {
  const shop = shops.find((s) => s.id === currentShop);
  if (embedded) {
    $("#tabs").innerHTML = `<span class="px-3 py-1 rounded-full bg-sky text-navy font-semibold whitespace-nowrap">${esc(shop?.name)}</span>`;
    return;
  }
  $("#tabs").innerHTML = shops
    .map((s, i) => `<button data-shop="${esc(s.id)}" class="px-3 py-1 rounded-full whitespace-nowrap ${s.id === currentShop ? "bg-sky text-navy font-semibold" : "bg-white/5 text-mist hover:bg-white/10"}">Stall ${String.fromCharCode(65 + i)} · ${esc(s.name)}</button>`)
    .join("");
}

function ticketCard(t, isNew) {
  const lines = t.lines.map((l) => `<li>${l.quantity}× ${esc(l.name)}</li>`).join("");
  const busy = pending.has(t.id);
  const justFired = t.status === "COOKING" && firedAt.has(t.id) && Date.now() - firedAt.get(t.id) < FIRE_HIGHLIGHT_MS;
  let badge = "";
  let action = "";
  let border = "border-transparent";
  if (t.status === "STAGED") {
    badge = `<span class="inline-block text-xs px-2.5 py-0.5 rounded-full bg-sky/40 text-royal font-semibold">Held by AI · firing in <span data-timer="${esc(t.id)}">${fmt(t.seconds_until_fire)}</span></span>`;
    border = "border-sky";
    action = `<button data-cook="${esc(t.id)}" ${busy ? "disabled" : ""} class="mt-3 w-full py-2 rounded-full bg-royal hover:bg-navy-2 text-white text-sm font-semibold disabled:opacity-50">${busy ? "Saving..." : "Cook now"}</button>`;
  } else if (t.status === "COOKING") {
    badge = `<span class="cook-now inline-block font-display text-xs px-2.5 py-0.5 rounded-full bg-ember text-white">COOK NOW</span>
             <span class="text-xs text-navy/60 ml-1"><span data-timer="${esc(t.id)}">${fmt(t.seconds_until_ready)}</span> to sync point</span>`;
    action = `<button data-ready="${esc(t.id)}" ${busy ? "disabled" : ""} class="mt-3 w-full py-2 rounded-full bg-mint text-navy text-sm font-semibold disabled:opacity-50">${busy ? "Saving..." : "Mark as Ready"}</button>`;
    border = "border-ember";
  } else {
    badge = `<span class="inline-block text-xs px-2.5 py-0.5 rounded-full bg-mint/30 text-emerald-800 font-semibold">Waiting for pickup</span>`;
    action = `<button data-collected="${esc(t.id)}" ${busy ? "disabled" : ""} class="mt-3 w-full py-2 rounded-full bg-navy hover:bg-navy-2 text-cream text-sm font-medium disabled:opacity-50">${busy ? "Saving..." : "Collected"}</button>`;
    border = "border-mint";
  }
  const classes = ["rounded-[20px] bg-cream text-navy border-2 p-3.5", border];
  if (isNew) classes.push("fade-in");
  if (justFired) classes.push("just-fired");
  return `
    <div data-ticket="${esc(t.id)}" class="${classes.join(" ")}">
      <div class="flex justify-between items-baseline text-sm"><span class="font-display">${esc(t.order_id)}</span><span class="text-xs text-navy/50">${esc(t.id)}</span></div>
      <ul class="text-sm text-navy/80 my-2">${lines}</ul>
      ${badge}${action}
    </div>`;
}

async function refresh() {
  if (!currentShop) return;
  let tickets;
  try {
    tickets = await api(`/queue/vendor/${currentShop}`);
  } catch (e) {
    console.error(e);
    return;
  }

  const now = Date.now();
  let newlyFired = false;
  for (const t of tickets) {
    const prev = lastStatus?.get(t.id);
    if (t.status === "COOKING" && lastStatus && prev !== "COOKING") {
      // Fired since the last poll (STAGED -> COOKING, or a brand-new ticket that fires immediately).
      firedAt.set(t.id, now);
      newlyFired = true;
    }
  }
  if (newlyFired) chime();

  for (const col of COLUMNS) {
    const list = tickets.filter((t) => t.status === col);
    const isJustFired = (t) => firedAt.has(t.id) && now - firedAt.get(t.id) < FIRE_HIGHLIGHT_MS;
    const signature = list.map((t) => `${t.id}:${pending.has(t.id)}:${isJustFired(t)}`).join(",");
    if (signature === colSignature[col]) {
      // Same tickets in the same state: only tick the countdowns. Rebuilding the cards every
      // second would swallow clicks that land mid-rebuild and restart animations.
      for (const t of list) {
        const timer = document.querySelector(`[data-timer="${CSS.escape(t.id)}"]`);
        if (timer) timer.textContent = fmt(col === "STAGED" ? t.seconds_until_fire : t.seconds_until_ready);
      }
    } else {
      // Only animate cards that just entered this column.
      $(`#col-${col}`).innerHTML = list.length
        ? list.map((t) => ticketCard(t, lastStatus?.get(t.id) !== col)).join("")
        : `<p class="text-xs text-mist/40">No tickets</p>`;
      colSignature[col] = signature;
    }
    $(`#count-${col}`).textContent = list.length;
  }
  lastStatus = new Map(tickets.map((t) => [t.id, t.status]));
}

async function setStatus(ticketId, status) {
  if (pending.has(ticketId)) return;
  pending.add(ticketId);
  refresh();
  try {
    await api(`/queue/ticket/${ticketId}/action`, { method: "POST", body: JSON.stringify({ status }) });
  } catch (e) {
    showError(`Could not update ${ticketId}: ${e.message}`);
  } finally {
    pending.delete(ticketId);
    refresh();
  }
}

function switchShop(shopId) {
  currentShop = shopId;
  lastStatus = null;
  firedAt = new Map();
  for (const col of COLUMNS) delete colSignature[col];
  history.replaceState(null, "", `?shop=${currentShop}${embedded ? "&embed=1" : ""}`);
  renderTabs();
  refresh();
}

// ---------- events ----------
document.addEventListener("click", (e) => {
  if (!soundOn) unlockSound(); // any tap on the board enables the chime
  const tab = e.target.closest("[data-shop]");
  if (tab) switchShop(tab.dataset.shop);
  const ready = e.target.closest("[data-ready]");
  if (ready) setStatus(ready.dataset.ready, "READY");
  const collected = e.target.closest("[data-collected]");
  if (collected) setStatus(collected.dataset.collected, "COLLECTED");
  const cook = e.target.closest("[data-cook]");
  if (cook) setStatus(cook.dataset.cook, "COOKING");
});

$("#reset-demo").addEventListener("click", async () => {
  if (!confirm("Wipe all demo orders and tickets?")) return;
  try {
    await api("/demo/reset", { method: "POST" });
    switchShop(currentShop);
  } catch (e) {
    showError(`Could not reset demo: ${e.message}`);
  }
});

(async function init() {
  if (embedded) document.body.classList.add("kds-embed");
  if (embedded) $("#reset-demo").classList.add("hidden");
  renderSoundButton();
  try {
    shops = await api("/shops");
  } catch (e) {
    showError(`Could not load stalls: ${e.message}`);
    return;
  }
  if (!shops.some((s) => s.id === currentShop)) currentShop = shops[0]?.id;
  renderTabs();
  refresh();
  setInterval(refresh, 1000);
})();
