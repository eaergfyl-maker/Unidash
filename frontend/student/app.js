// SyncFlow student app: catalog, global cart, single checkout, live Sync-Prep tracker, schedule sync.
const API = "/api";
const $ = (sel) => document.querySelector(sel);
const money = (n) => `$${n.toFixed(2)}`;
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const state = {
  shops: [],
  filter: "All",
  cart: [], // [{shop_id, item_id, quantity}]
  breakWindow: null,
  orderId: null,
  orderCreatedAt: null, // detects an order ID reused after a demo reset
  pollTimer: null,
  secPerMin: 60, // from /api/health; lower = faster demo clock
  student: { name: "", id: "" }, // captured via identity modal before checkout
  checkingOut: false, // true while a checkout request is in flight
};

async function api(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.detail || res.statusText);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

function findItem(shopId, itemId) {
  const shop = state.shops.find((s) => s.id === shopId);
  return { shop, item: shop?.menu.find((i) => i.id === itemId) };
}

// ---------- catalog ----------
function renderFilters() {
  const cats = ["All", "Food", "Coffee", "Quick Bites"];
  $("#filters").innerHTML = cats
    .map((c) => `<button data-cat="${c}" class="px-3 py-1 rounded-full ${c === state.filter ? "bg-cyan-500 text-slate-950" : "bg-slate-800"}">${c}</button>`)
    .join("");
}

function renderShops() {
  $("#shops").innerHTML = state.shops
    .map((shop) => {
      const items = shop.menu.filter((i) => state.filter === "All" || i.category === state.filter);
      if (!items.length) return "";
      return `
        <div class="rounded-2xl bg-slate-800/60 border border-slate-700 p-4">
          <div class="flex justify-between items-baseline">
            <h3 class="font-semibold">${esc(shop.name)}</h3>
            <span class="text-xs text-slate-400">${shop.prep_range_minutes[0]}-${shop.prep_range_minutes[1]} min</span>
          </div>
          <p class="text-xs text-slate-400 mb-3">📍 ${esc(shop.location)} · ${shop.walk_minutes} min walk</p>
          ${items
            .map(
              (i) => `
            <div class="flex justify-between items-center py-2 border-t border-slate-700/60">
              <div>
                <p class="text-sm">${esc(i.name)}</p>
                <p class="text-xs text-slate-400">${money(i.price)} · ${i.prep_minutes} min</p>
              </div>
              <button data-add="${shop.id}|${i.id}" class="w-8 h-8 rounded-full bg-cyan-500 text-slate-950 font-bold">+</button>
            </div>`
            )
            .join("")}
        </div>`;
    })
    .join("");
}

// ---------- cart ----------
function addToCart(shopId, itemId) {
  const line = state.cart.find((l) => l.shop_id === shopId && l.item_id === itemId);
  if (line) line.quantity += 1;
  else state.cart.push({ shop_id: shopId, item_id: itemId, quantity: 1 });
  renderCartBar();
}

function cartTotals() {
  let count = 0, total = 0;
  for (const l of state.cart) {
    const { item } = findItem(l.shop_id, l.item_id);
    count += l.quantity;
    total += item.price * l.quantity;
  }
  return { count, total };
}

function renderCartBar() {
  const { count, total } = cartTotals();
  $("#cart-bar").classList.toggle("hidden", count === 0 || state.orderId);
  $("#cart-count").textContent = `${count} item${count === 1 ? "" : "s"} · ${new Set(state.cart.map((l) => l.shop_id)).size} stall(s)`;
  $("#cart-total").textContent = money(total);
}

function renderCartDrawer() {
  const byShop = {};
  for (const l of state.cart) (byShop[l.shop_id] ||= []).push(l);
  $("#cart-lines").innerHTML = Object.entries(byShop)
    .map(([shopId, lines]) => {
      const shop = state.shops.find((s) => s.id === shopId);
      return `
        <div class="rounded-xl bg-slate-800 p-3">
          <p class="font-semibold mb-1">${esc(shop.name)}</p>
          ${lines
            .map((l) => {
              const { item } = findItem(l.shop_id, l.item_id);
              return `<p class="flex justify-between text-slate-300"><span>${l.quantity}× ${esc(item.name)}</span><span>${money(item.price * l.quantity)} · ${item.prep_minutes} min</span></p>`;
            })
            .join("")}
        </div>`;
    })
    .join("");
}

function openIdentityModal() {
  $("#student-name-input").value = state.student.name;
  $("#student-id-input").value = state.student.id;
  $("#identity-modal").classList.remove("hidden");
}

async function checkout() {
  // Keep the modal open while the request runs so the loading state is visible,
  // and lock every button that could start a second checkout.
  if (state.checkingOut) return;
  state.checkingOut = true;
  const btn = $("#identity-confirm");
  const lockIds = ["#identity-confirm", "#identity-cancel", "#checkout-btn"];
  lockIds.forEach((id) => ($(id).disabled = true));
  btn.textContent = "Processing Campus Pay...";
  try {
    const order = await api("/order/checkout", {
      method: "POST",
      body: JSON.stringify({
        student_name: state.student.name,
        student_id: state.student.id,
        items: state.cart,
      }),
    });
    state.orderId = order.id;
    state.orderCreatedAt = order.created_at;
    $("#order-notice").classList.add("hidden");
    state.cart = [];
    $("#identity-modal").classList.add("hidden");
    $("#cart-drawer").classList.add("hidden");
    $("#catalog-view").classList.add("hidden");
    $("#tracker-view").classList.remove("hidden");
    renderCartBar();
    renderTracker(order);
    state.pollTimer = setInterval(pollOrder, 1000);
  } catch (e) {
    alert(`Checkout failed: ${e.message}`);
  } finally {
    lockIds.forEach((id) => ($(id).disabled = false));
    btn.textContent = "Confirm & Pay";
    state.checkingOut = false;
  }
}

// ---------- live tracker ----------
const fmt = (secs) => `${Math.floor(secs / 60)}:${String(Math.floor(secs % 60)).padStart(2, "0")}`;

async function pollOrder() {
  const id = state.orderId;
  if (!id) return;
  try {
    const order = await api(`/order/${id}/status`);
    if (state.orderId !== id) return; // user left the tracker while the request ran
    // Demo reset restarts numbering at ORD-8801, so the same ID can come back as a
    // different order. A changed created_at means our order was wiped.
    if (order.created_at !== state.orderCreatedAt) return orderWiped();
    renderTracker(order);
  } catch (e) {
    if (e.status === 404 && state.orderId === id) return orderWiped();
    console.error(e);
  }
}

// The order no longer exists on the server (demo reset): stop the timer and go back to the menu.
function orderWiped() {
  resetToCatalog();
  const notice = $("#order-notice");
  notice.textContent = "Your order was cleared because the demo was reset. Start a new order.";
  notice.classList.remove("hidden");
}

function renderTracker(order) {
  const ready = order.status === "READY" || order.status === "COLLECTED";
  const remaining = Math.max(...order.sub_tickets.map((t) => t.seconds_until_ready));
  const walk = Math.max(...order.sub_tickets.map((t) => state.shops.find((s) => s.id === t.shop_id)?.walk_minutes || 0));
  const startWalking = remaining <= walk * state.secPerMin || ready;

  $("#tracker-view").innerHTML = `
    <div class="text-center mb-4">
      <p class="text-xs text-slate-400">Order ${esc(order.id)} · ${money(order.total)}</p>
      <div class="radar my-4 flex items-center justify-center">
        <span class="text-2xl font-bold">${ready ? "✅" : fmt(remaining)}</span>
      </div>
      <p class="text-sm text-cyan-300">${ready ? "Everything is ready for pickup!" : "Syncing kitchen timers so everything finishes together..."}</p>
    </div>
    <div class="space-y-2 mb-4">
      ${order.sub_tickets
        .map((t) => {
          const label =
            t.status === "STAGED" ? `Held by AI · fires in ${fmt(t.seconds_until_fire)}` :
            t.status === "COOKING" ? `Cooking now · ${fmt(t.seconds_until_ready)} left` : "Ready ✅";
          return `<div class="rounded-xl bg-slate-800 p-3 flex justify-between text-sm"><span>${esc(t.shop_name)}</span><span class="text-slate-300">${label}</span></div>`;
        })
        .join("")}
    </div>
    <div class="rounded-2xl p-4 mb-4 ${startWalking ? "bg-green-400 text-slate-950 glow-green" : "bg-slate-800"}">
      <p class="font-bold">${startWalking ? `🚶 Start walking now (${walk} min walk)` : "📚 Relax, we'll tell you when to walk"}</p>
    </div>
    <div class="rounded-2xl bg-white text-slate-900 p-4 text-center">
      <div id="qr-canvas" class="mx-auto" style="width:128px;height:128px"></div>
      <p class="text-xs mt-2">One code for every stall</p>
    </div>
    <button id="new-order" class="mt-4 w-full py-2 text-sm text-slate-400">Start a new order</button>`;

  drawQr(order.id);
}

// Draw the real QR code (qrcodejs renders into a div). If the CDN script did not
// load (offline demo, blocked network), show the order ID instead of crashing the tracker.
function drawQr(text) {
  const box = $("#qr-canvas");
  box.innerHTML = "";
  try {
    new QRCode(box, { text, width: 128, height: 128 });
  } catch (e) {
    box.className = "mx-auto border-4 border-slate-900 grid place-items-center font-mono text-xs";
    box.innerHTML = `QR<br/>${esc(text)}`;
  }
}

function resetToCatalog() {
  clearInterval(state.pollTimer);
  state.pollTimer = null;
  state.orderId = null;
  state.orderCreatedAt = null;
  $("#order-notice").classList.add("hidden");
  $("#tracker-view").classList.add("hidden");
  $("#catalog-view").classList.remove("hidden");
  renderCartBar();
}

// ---------- schedule sync (Person 3) ----------
async function showBreak(out, bw, label, importedBreak) {
  const recs = await api(`/timetable/recommendations?max_prep_minutes=${bw.max_prep_minutes}&class_label=${encodeURIComponent(label)}`);
  state.breakWindow = bw;
  const colour = { SAFE: "text-green-400", TIGHT: "text-amber-300", HIGH: "text-red-400" };
  const destination = importedBreak
    ? `${esc(importedBreak.date)}${importedBreak.next_room ? ` · Next class in ${esc(importedBreak.next_room)}` : ""} · `
    : "";
  const timing = importedBreak
    ? `Allow ${bw.walk_buffer_minutes} min to reach class. Shop estimates include the walk to each shop.`
    : `After a ${bw.walk_buffer_minutes} min walk you have <b>${bw.max_prep_minutes} min</b> for food.`;
  out.innerHTML = `
    <p class="mb-2">${destination}Break <b>${esc(bw.start)}–${esc(bw.end)}</b> (${bw.break_minutes} min). ${timing}</p>
    ${recs.map((r) => `<p class="text-xs ${colour[r.risk]}">• ${esc(r.shop_name)}: ${esc(r.message)}</p>`).join("")}`;
}

async function readSchedule(action, out = $("#gap-result")) {
  const buttons = [$("#parse-btn"), $("#upload-timetable-btn")];
  if (buttons.some((button) => button.disabled)) return;
  buttons.forEach((button) => { button.disabled = true; });
  state.breakWindow = null;
  out.classList.remove("hidden");
  out.textContent = "Reading your schedule...";
  try {
    await action(out);
  } catch (error) {
    out.textContent = `Error: ${error.message}`;
  } finally {
    buttons.forEach((button) => { button.disabled = false; });
  }
}

async function parseNotice() {
  const text = $("#notice").value.trim();
  if (!text) return;
  await readSchedule(async (out) => {
    const res = await api("/timetable/parse", { method: "POST", body: JSON.stringify({ text }) });
    if (!res.break_window) {
      out.textContent = "Couldn't find a class time in that text.";
      return;
    }
    const label = res.slots.at(-1)?.label || "your next class";
    await showBreak(out, res.break_window, label);
  });
}

async function uploadTimetable(event) {
  event.preventDefault();
  const file = $("#timetable-file").files[0];
  if (!file) return;
  await readSchedule(async (out) => {
    const body = new FormData();
    body.append("file", file);
    const { slots, breaks } = await api("/timetable/import", { method: "POST", headers: {}, body });
    out.textContent = `Imported ${slots.length} ${slots.length === 1 ? "class" : "classes"}.`;
    if (!breaks.length) {
      out.append(" No breaks between classes on the same day.");
      return;
    }

    const label = document.createElement("label");
    label.className = "block my-2";
    label.textContent = "Choose a break";
    const select = document.createElement("select");
    select.className = "block w-full mt-1 rounded bg-slate-900 p-2";
    for (const [index, gap] of breaks.entries()) {
      const { start, end } = gap.break_window;
      select.add(new Option(`${gap.date} · ${start}–${end}`, index));
    }
    label.append(select);
    const result = document.createElement("div");
    out.append(label, result);

    const showSelectedBreak = () => {
      const gap = breaks[select.selectedIndex];
      const classLabel = gap.next_room ? `class in ${gap.next_room}` : "your next class";
      return showBreak(result, gap.break_window, classLabel, gap);
    };
    select.addEventListener("change", async () => {
      select.disabled = true;
      try {
        await readSchedule(showSelectedBreak, result);
      } finally {
        select.disabled = false;
      }
    });
    select.disabled = true;
    try {
      await showSelectedBreak();
    } catch (error) {
      result.textContent = `Error: ${error.message}`;
    } finally {
      select.disabled = false;
    }
  });
}

async function loadSample() {
  const samples = await api("/timetable/samples");
  $("#notice").value = samples[0] || "";
}

// ---------- wiring ----------
document.addEventListener("click", (e) => {
  const add = e.target.closest("[data-add]");
  if (add) return addToCart(...add.dataset.add.split("|"));
  const cat = e.target.closest("[data-cat]");
  if (cat) {
    state.filter = cat.dataset.cat;
    renderFilters();
    renderShops();
  }
  if (e.target.id === "new-order") resetToCatalog();
});
$("#cart-bar").addEventListener("click", () => {
  renderCartDrawer();
  $("#cart-drawer").classList.remove("hidden");
});
$("#close-cart").addEventListener("click", () => $("#cart-drawer").classList.add("hidden"));

$("#checkout-btn").addEventListener("click", openIdentityModal);

$("#identity-cancel").addEventListener("click", () => {
  if (state.checkingOut) return;
  $("#identity-modal").classList.add("hidden");
});
$("#identity-confirm").addEventListener("click", async () => {
  const name = $("#student-name-input").value.trim();
  const id = $("#student-id-input").value.trim();
  if (!name || !id) {
    alert("Please enter your name and student ID.");
    return;
  }
  state.student = { name, id };
  await checkout();
});

$("#parse-btn").addEventListener("click", parseNotice);
$("#timetable-upload").addEventListener("submit", uploadTimetable);
$("#load-sample").addEventListener("click", loadSample);

async function init() {
  try {
    const [shops, health] = await Promise.all([api("/shops"), api("/health")]);
    state.shops = shops;
    state.secPerMin = health.sim_seconds_per_minute;
    renderFilters();
    renderShops();
  } catch (e) {
    $("#shops").innerHTML = `
      <div class="text-center text-sm text-slate-400 py-8">
        <p class="mb-3">Couldn't load the menu. Check your connection and try again.</p>
        <button id="retry-init" class="px-4 py-2 rounded-lg bg-cyan-500 text-slate-950 font-semibold">Retry</button>
      </div>`;
    $("#retry-init").addEventListener("click", init);
  }
}
init();
