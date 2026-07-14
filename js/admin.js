// Админка каталога Milana Group.
// Редактирует цены и описания товаров, хранит черновик в localStorage
// и выгружает data/overrides.json для публикации на сайте.
//
// ВНИМАНИЕ: это клиентская защита (пароль в коде виден любому, кто откроет
// исходники). Она отсекает случайных посетителей, но НЕ является настоящей
// защитой. Для серьёзной защиты нужен серверный вход.

const ADMIN_PASS = "milana2026"; // ← смените на свой пароль
const AUTH_KEY = "milana_admin_ok_v1";
const DRAFT_KEY = "milana_admin_draft_v1";

const CATALOG_URL = "data/catalog.json";
const ITEM_BASE = "data/items/";
const OVERRIDES_URL = "data/overrides.json";

/** @type {Array<object>} загруженные товары */
let products = [];
/** опубликованные правки (из overrides.json) */
let published = {};
/** текущий черновик правок */
let draft = {};

// ---------- утилиты ----------
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function cleanBaseDescription(d) {
  if (!d) return "";
  if (/точная\s+вырезка|печатному\s+каталогу|фрагмент/i.test(d)) return "";
  return d.replace(/\s*—\s*каталог\s+Milana\s+Group\s*\d*\.?$/i, "").trim();
}

function formatPrice(v) {
  if (typeof v !== "number" || !(v > 0)) return "";
  return v.toLocaleString("ru-RU").replace(/,/g, " ") + " ₽";
}

/** Итоговые правки: только непустые цены/описания. */
function buildOverrides(src) {
  const out = {};
  for (const [id, o] of Object.entries(src)) {
    const entry = {};
    if (typeof o.price === "number" && o.price > 0) entry.price = o.price;
    if (typeof o.description === "string" && o.description.trim())
      entry.description = o.description.trim();
    if (Object.keys(entry).length) out[id] = entry;
  }
  return out;
}

function draftDiffersFromPublished() {
  return JSON.stringify(buildOverrides(draft)) !== JSON.stringify(buildOverrides(published));
}

function saveDraft() {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  } catch { /* переполнение — игнорируем */ }
  updateDraftState();
}

function updateDraftState() {
  const el = document.getElementById("admin-draft-state");
  if (!el) return;
  const ov = buildOverrides(draft);
  const withPrice = Object.values(ov).filter((o) => o.price).length;
  const withDesc = Object.values(ov).filter((o) => o.description).length;
  const dirty = draftDiffersFromPublished();
  el.innerHTML =
    `Цен указано: <b>${withPrice}</b> · описаний: <b>${withDesc}</b>` +
    (dirty ? ` · <span class="admin-dirty">черновик не выгружен</span>` : ` · <span class="admin-clean">совпадает с сайтом</span>`);
}

// ---------- загрузка данных ----------
async function loadAll() {
  const res = await fetch(CATALOG_URL, { cache: "no-store" });
  if (!res.ok) throw new Error("catalog");
  const catalog = await res.json();

  try {
    const ovRes = await fetch(OVERRIDES_URL, { cache: "no-store" });
    if (ovRes.ok) {
      const data = await ovRes.json();
      if (data && typeof data === "object") published = data;
    }
  } catch { /* нет файла — ок */ }

  const settled = await Promise.all(
    catalog.items.map((id) =>
      fetch(`${ITEM_BASE}${id}.json`)
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null)
    )
  );
  products = settled.filter(Boolean);

  // черновик: из localStorage, иначе из опубликованного
  const saved = localStorage.getItem(DRAFT_KEY);
  if (saved) {
    try { draft = JSON.parse(saved) || {}; } catch { draft = {}; }
  } else {
    draft = structuredClone(published);
  }
}

// ---------- отрисовка ----------
function cardRow(item) {
  const d = draft[item.id] || {};
  const basePrice = typeof d.price === "number" ? d.price : "";
  const baseDesc = typeof d.description === "string" ? d.description : "";
  const placeholder = cleanBaseDescription(item.description) || "Описание товара…";
  return `
    <div class="admin-card" data-id="${item.id}" data-name="${escapeHtml((item.name || "").toLowerCase())}">
      <img class="admin-card-img" src="${item.image}" alt="" loading="lazy" />
      <div class="admin-card-main">
        <div class="admin-card-head">
          <h3>${escapeHtml(item.name || item.id)}</h3>
          <span class="admin-card-cat">${escapeHtml(item.category || "")} · ${item.id}</span>
        </div>
        <div class="admin-field admin-field-price">
          <label for="price-${item.id}">Цена, ₽</label>
          <input type="number" min="0" step="100" inputmode="numeric"
                 id="price-${item.id}" data-id="${item.id}" data-field="price"
                 value="${basePrice}" placeholder="напр. 45900" />
          <span class="admin-price-preview" id="pp-${item.id}">${formatPrice(Number(basePrice)) || "цена по запросу"}</span>
        </div>
        <div class="admin-field">
          <label for="desc-${item.id}">Описание</label>
          <textarea id="desc-${item.id}" data-id="${item.id}" data-field="description"
                    rows="2" placeholder="${escapeHtml(placeholder)}">${escapeHtml(baseDesc)}</textarea>
        </div>
      </div>
    </div>
  `;
}

function render() {
  const grid = document.getElementById("admin-grid");
  grid.innerHTML = products.map(cardRow).join("");
  document.getElementById("admin-meta").textContent = `${products.length} позиций`;
  updateDraftState();
}

// ---------- обработчики редактирования ----------
function onFieldInput(e) {
  const el = e.target;
  const id = el.dataset.id;
  const field = el.dataset.field;
  if (!id || !field) return;
  if (!draft[id]) draft[id] = {};
  if (field === "price") {
    const v = parseInt(el.value, 10);
    if (Number.isFinite(v) && v > 0) draft[id].price = v;
    else delete draft[id].price;
    const pp = document.getElementById(`pp-${id}`);
    if (pp) pp.textContent = formatPrice(draft[id].price) || "цена по запросу";
  } else if (field === "description") {
    const v = el.value.trim();
    if (v) draft[id].description = el.value;
    else delete draft[id].description;
  }
  if (draft[id] && Object.keys(draft[id]).length === 0) delete draft[id];
  saveDraft();
}

function initEditing() {
  const grid = document.getElementById("admin-grid");
  grid.addEventListener("input", onFieldInput);

  document.getElementById("admin-search").addEventListener("input", (e) => {
    const q = e.target.value.trim().toLowerCase();
    for (const card of grid.querySelectorAll(".admin-card")) {
      card.hidden = q && !card.dataset.name.includes(q);
    }
  });

  document.getElementById("admin-download").addEventListener("click", () => {
    const data = buildOverrides(draft);
    const blob = new Blob([JSON.stringify(data, null, 2) + "\n"], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "overrides.json";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    // считаем выгруженное «опубликованным ориентиром»
    published = structuredClone(data);
    updateDraftState();
  });

  document.getElementById("admin-reset").addEventListener("click", () => {
    if (!confirm("Сбросить черновик к последней загруженной версии? Несохранённые правки будут потеряны.")) return;
    draft = structuredClone(published);
    localStorage.removeItem(DRAFT_KEY);
    render();
  });

  document.getElementById("admin-import").addEventListener("change", (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(String(reader.result));
        if (!data || typeof data !== "object") throw new Error("format");
        published = structuredClone(data);
        draft = structuredClone(data);
        saveDraft();
        render();
        alert("Файл загружен. Можно продолжать редактирование.");
      } catch {
        alert("Не удалось прочитать файл. Убедитесь, что это overrides.json.");
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  });

  document.getElementById("admin-logout").addEventListener("click", () => {
    sessionStorage.removeItem(AUTH_KEY);
    location.reload();
  });
}

// ---------- вход ----------
async function startApp() {
  document.getElementById("admin-gate").hidden = true;
  document.getElementById("admin-app").hidden = false;
  try {
    await loadAll();
    render();
    initEditing();
  } catch (err) {
    console.error(err);
    const el = document.getElementById("admin-error");
    el.hidden = false;
    el.textContent =
      "Не удалось загрузить каталог. Откройте админку через локальный сервер (например: python3 -m http.server), а не как файл с диска.";
  }
}

function initGate() {
  if (sessionStorage.getItem(AUTH_KEY) === "1") {
    startApp();
    return;
  }
  const form = document.getElementById("admin-gate-form");
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const val = document.getElementById("admin-pass").value;
    const status = document.getElementById("admin-gate-status");
    if (val === ADMIN_PASS) {
      sessionStorage.setItem(AUTH_KEY, "1");
      startApp();
    } else {
      status.textContent = "Неверный пароль.";
      status.className = "form-status err";
    }
  });
}

initGate();
