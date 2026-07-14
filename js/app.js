const CATALOG_URL = "data/catalog.json";
const ITEM_BASE = "data/items/";
const OVERRIDES_URL = "data/overrides.json";
const CART_KEY = "milana_cart_v1";
// Приём заявок — Web3Forms (надёжный сервис). Ключ привязан к milanastore000@mail.ru.
// Ключ не секретный: он и так виден в HTML формы обратной связи. Тот же ключ — в index.html.
const WEB3FORMS_URL = "https://api.web3forms.com/submit";
const WEB3FORMS_KEY = "31809651-1475-483e-a58b-fcfd86ff660e";

/** Подпись для позиций без отдельного названия в JSON (не показываем служебный id вроде p27-1). */
const CATALOG_PLACEHOLDER_TITLE = "Модель из каталога";

/** @type {Map<string, object>} */
const itemCache = new Map();

/**
 * Правки цен/описаний из data/overrides.json (редактируются в админке).
 * Формат: { "p03-1": { "price": 45900, "description": "…" }, … }
 * @type {Record<string, {price?: number, description?: string}>}
 */
let overrides = {};

async function loadOverrides() {
  try {
    const res = await fetch(OVERRIDES_URL, { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    if (data && typeof data === "object") overrides = data;
  } catch {
    /* файла может не быть — работаем без правок */
  }
}

/** Накладывает правки из overrides.json поверх товара. */
function withOverrides(item) {
  const o = overrides[item.id];
  if (!o) return item;
  const merged = { ...item };
  if (typeof o.price === "number" && o.price > 0) merged.price = o.price;
  if (typeof o.description === "string" && o.description.trim()) {
    merged.description = o.description.trim();
    merged.descriptionOverridden = true;
  }
  return merged;
}

/** Форматирует цену: 45900 → «45 900 ₽». */
function formatPrice(v) {
  if (typeof v !== "number" || !(v > 0)) return "";
  return v.toLocaleString("ru-RU").replace(/,/g, " ") + " ₽";
}

function displayItemPrice(item) {
  return formatPrice(item.price);
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * Убирает из названия отсылки к страницам/блокам каталога.
 * Важно: не использовать \b перед кириллицей — в JS граница слова только для [A-Za-z0-9_].
 */
function stripPageRefsFromName(name) {
  if (!name || typeof name !== "string") return "";
  let s = name;
  let prev;
  do {
    prev = s;
    s = s
      .replace(/\s*\([^)]*стр\s*\.\s*[^)]*\)/gi, "")
      .replace(/\s*\([^)]*страниц[аея]\s+[^)]*\)/gi, "")
      .replace(/\s*\([^)]*(?:p\.|pg\.|page)\s*\d[^)]*\)/gi, "")
      .replace(/\s*\([^)]*блок\s*\d+[^)]*\)/gi, "")
      .replace(/\s*[,(]\s*блок\s*\d+\s*$/gi, "")
      .replace(/\s*[,;]\s*стр\s*\.\s*\d+.*$/i, "")
      .replace(/\s{2,}/g, " ")
      .trim();
  } while (s !== prev);
  return s;
}

function displayItemName(item) {
  const n = stripPageRefsFromName(item.name);
  if (!n || /^модель каталога$/i.test(n)) {
    return CATALOG_PLACEHOLDER_TITLE;
  }
  return n;
}

/** Не показываем служебный текст про фрагменты страниц PDF. */
function displayItemShort(item) {
  const s = item.short;
  if (!s) return "";
  if (/фрагмент\s+страницы|PDF-каталог|как\s+в\s+оригинале/i.test(s)) return "";
  return s;
}

function displayItemDescription(item) {
  const d = item.description;
  if (!d) return "";
  // Описание из админки показываем как есть.
  if (item.descriptionOverridden) return d.trim();
  if (/точная\s+вырезка\s+со\s+страницы|печатному\s+каталогу|фрагмент/i.test(d)) return "";
  return d
    .replace(/\s*—\s*каталог\s+Milana\s+Group\s*\d*\.?$/i, "")
    .trim();
}

function displayItemCategory(item) {
  const c = item.category;
  if (!c || c === "Milana Group") return "";
  return c;
}

function specsForDisplay(specs) {
  if (!specs || typeof specs !== "object") return null;
  const out = { ...specs };
  const source = out.Источник;
  delete out.Источник;
  if (Object.keys(out).length) return out;
  // Карточки только с «Источник» (стр. каталога): иначе блок скрывался целиком.
  if (source) {
    return {
      Характеристики: "См. таблицу на фото — размеры и параметры как в печатном каталоге.",
      Источник: source,
    };
  }
  return null;
}

function loadCart() {
  try {
    const raw = localStorage.getItem(CART_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveCart(items) {
  localStorage.setItem(CART_KEY, JSON.stringify(items));
}

function cartCount(items) {
  return items.reduce((n, i) => n + i.qty, 0);
}

async function fetchItem(id) {
  if (itemCache.has(id)) return itemCache.get(id);
  const res = await fetch(`${ITEM_BASE}${id}.json`);
  if (!res.ok) throw new Error(`Не удалось загрузить ${id}`);
  const data = withOverrides(await res.json());
  itemCache.set(id, data);
  return data;
}

function renderCatalogMeta(catalog) {
  const el = document.getElementById("catalog-meta");
  if (!el) return;
  el.textContent = `${catalog.items.length} позиций · ${catalog.brand}`;
}

function resetOrderModal() {
  const block = document.getElementById("order-form-block");
  const panel = document.getElementById("order-success-panel");
  const status = document.getElementById("order-status");
  if (block) block.hidden = false;
  if (panel) panel.hidden = true;
  if (status) {
    status.textContent = "";
    status.className = "form-status";
  }
}

function cardTemplate(item) {
  const title = escapeHtml(displayItemName(item));
  const price = displayItemPrice(item);
  const priceHtml = price
    ? `<p class="card-price">${escapeHtml(price)}</p>`
    : `<p class="card-price card-price--muted">Цена по запросу</p>`;
  return `
    <button type="button" class="card" data-id="${item.id}" aria-label="${title}, подробнее">
      <div class="card-image-wrap">
        <img src="${item.image}" alt="" loading="lazy" width="400" height="300" />
      </div>
      <div class="card-body card-body--title-only">
        <h3 class="card-title">${title}</h3>
        ${priceHtml}
      </div>
    </button>
  `;
}

async function openProductModal(id) {
  const dlg = document.getElementById("modal-product");
  try {
    const item = await fetchItem(id);
    const img = document.getElementById("modal-product-img");
    img.src = item.image;
    img.alt = displayItemName(item);

    const catEl = document.getElementById("modal-product-category");
    const cat = displayItemCategory(item);
    catEl.textContent = cat;
    catEl.hidden = !cat;

    document.getElementById("modal-product-title").textContent = displayItemName(item);

    const shortEl = document.getElementById("modal-product-short");
    const shortText = displayItemShort(item);
    shortEl.textContent = shortText;
    shortEl.hidden = !shortText;

    const descEl = document.getElementById("modal-product-desc");
    const descText = displayItemDescription(item);
    descEl.textContent = descText;
    descEl.hidden = !descText;

    const specsEl = document.getElementById("modal-product-specs");
    specsEl.innerHTML = "";
    const specs = specsForDisplay(item.specs);
    if (specs) {
      for (const [k, v] of Object.entries(specs)) {
        const row = document.createElement("div");
        const dt = document.createElement("dt");
        dt.textContent = k;
        const dd = document.createElement("dd");
        dd.textContent = v;
        row.appendChild(dt);
        row.appendChild(dd);
        specsEl.appendChild(row);
      }
    }
    specsEl.hidden = !specs || Object.keys(specs).length === 0;

    const priceEl = document.getElementById("modal-product-price");
    const priceText = displayItemPrice(item);
    priceEl.textContent = priceText || "Цена по запросу";
    priceEl.classList.toggle("modal-price--muted", !priceText);

    document.getElementById("modal-add-cart").dataset.id = id;
    dlg.showModal();
  } catch (e) {
    console.error(e);
    alert("Не удалось открыть карточку. Проверьте файл в data/items.");
  }
}

function renderCart(items) {
  const list = document.getElementById("cart-list");
  const empty = document.getElementById("cart-empty");
  const badge = document.getElementById("cart-badge");
  const summaryEl = document.getElementById("cart-summary");
  const checkout = document.getElementById("btn-checkout");

  const count = cartCount(items);
  badge.hidden = count === 0;
  badge.textContent = String(count);
  empty.hidden = items.length > 0;
  list.innerHTML = "";
  checkout.disabled = items.length === 0;

  let total = 0;
  let hasAllPrices = items.length > 0;
  for (const line of items) {
    const li = document.createElement("li");
    li.className = "cart-item";
    const label = escapeHtml(displayItemName({ name: line.name, id: line.id }));
    const priceText = formatPrice(line.price);
    if (typeof line.price === "number" && line.price > 0) total += line.price * line.qty;
    else hasAllPrices = false;
    const priceLine = priceText
      ? `<div class="cart-item-meta">${priceText} × ${line.qty}</div>`
      : `<div class="cart-item-meta">Количество: ${line.qty} · цена по запросу</div>`;
    li.innerHTML = `
      <img src="${line.image}" alt="" />
      <div>
        <div class="cart-item-title">${label}</div>
        ${priceLine}
      </div>
      <button type="button" class="cart-item-remove btn-touch-min" data-id="${line.id}">Убрать</button>
    `;
    list.appendChild(li);
  }

  const pieces = cartCount(items);
  if (items.length === 0) {
    summaryEl.textContent = "";
  } else if (hasAllPrices) {
    summaryEl.textContent = `Итого: ${formatPrice(total)} · ${pieces} шт.`;
  } else {
    const partial = total > 0 ? ` · от ${formatPrice(total)}` : "";
    summaryEl.textContent = `В списке: ${pieces} шт.${partial}`;
  }
}

function addToCart(item) {
  const items = loadCart();
  const found = items.find((i) => i.id === item.id);
  if (found) {
    found.qty += 1;
    found.price = item.price; // на случай, если цена появилась/изменилась
  } else
    items.push({
      id: item.id,
      name: item.name,
      image: item.image,
      price: typeof item.price === "number" ? item.price : null,
      qty: 1,
    });
  saveCart(items);
  renderCart(items);
}

function removeFromCart(id) {
  let items = loadCart().filter((i) => i.id !== id);
  saveCart(items);
  renderCart(items);
}

function buildOrderText(items, comment) {
  let total = 0;
  let hasAllPrices = items.length > 0;
  const lines = items.map((i) => {
    const priceText = formatPrice(i.price);
    if (typeof i.price === "number" && i.price > 0) total += i.price * i.qty;
    else hasAllPrices = false;
    const priceStr = priceText ? ` — ${priceText} × ${i.qty}` : ` × ${i.qty} (цена по запросу)`;
    return `— ${i.name} (арт. ${i.id})${priceStr}`;
  });
  let text = `Заявка Milana Group\n\n${lines.join("\n")}`;
  if (hasAllPrices) text += `\n\nИтого: ${formatPrice(total)}`;
  if (comment?.trim()) text += `\n\nКомментарий:\n${comment.trim()}`;
  return text;
}

/** Универсальная отправка через Web3Forms. Бросает ошибку, если не success. */
async function submitViaWeb3Forms(fields) {
  const res = await fetch(WEB3FORMS_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ access_key: WEB3FORMS_KEY, ...fields }),
  });
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* не JSON */
  }
  if (data && data.success) return data;
  throw new Error(
    (data && data.message) ||
      "Сервис приёма заявок временно недоступен. Попробуйте ещё раз или позвоните нам."
  );
}

async function submitOrder(phone, email, comment, items) {
  if (!items?.length) {
    throw new Error("Корзина пуста — добавьте позиции и снова нажмите «Оставить заявку».");
  }
  const message = buildOrderText(items, comment);
  return submitViaWeb3Forms({
    subject: "Milana Group — заявка с каталога",
    from_name: "Каталог Milana Group",
    email: email || undefined, // reply-to для менеджера
    Телефон: phone,
    Почта: email || "—",
    Комментарий: comment || "—",
    Заявка: message,
  });
}

function initContactForm() {
  const form = document.getElementById("contact-form");
  if (!form) return;
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const status = document.getElementById("contact-status");
    const btn = document.getElementById("contact-submit");
    const fd = new FormData(form);
    const name = String(fd.get("Имя") || "").trim();
    const phone = String(fd.get("Телефон") || "").trim();
    const msg = String(fd.get("Сообщение") || "").trim();
    status.textContent = "";
    status.className = "form-status";
    if (!phone) {
      status.textContent = "Укажите телефон для связи.";
      status.classList.add("err");
      return;
    }
    btn.disabled = true;
    status.textContent = "Отправляем…";
    try {
      await submitViaWeb3Forms({
        subject: "Milana Group — обратная связь с сайта",
        from_name: "Сайт Milana Group",
        Имя: name || "—",
        Телефон: phone,
        Сообщение: msg || "—",
      });
      form.reset();
      status.textContent = "Спасибо! Заявка отправлена — мы перезвоним вам.";
      status.classList.add("ok");
    } catch (err) {
      console.error(err);
      status.textContent =
        "Не удалось отправить. Позвоните нам напрямую или попробуйте ещё раз.";
      status.classList.add("err");
    } finally {
      btn.disabled = false;
    }
  });
}

async function init() {
  const grid = document.getElementById("catalog-grid");
  const errEl = document.getElementById("catalog-error");
  const modalProduct = document.getElementById("modal-product");
  const drawerCart = document.getElementById("drawer-cart");
  const modalOrder = document.getElementById("modal-order");

  document.getElementById("btn-scroll-catalog").addEventListener("click", () => {
    grid.scrollIntoView({ behavior: "smooth" });
  });

  document.getElementById("btn-open-cart").addEventListener("click", () => {
    drawerCart.showModal();
  });

  document.getElementById("drawer-cart-close").addEventListener("click", () => drawerCart.close());
  document.getElementById("modal-product-close").addEventListener("click", () => modalProduct.close());
  document.getElementById("modal-order-close").addEventListener("click", () => modalOrder.close());

  modalOrder.addEventListener("close", () => resetOrderModal());

  document.getElementById("order-success-close").addEventListener("click", () => {
    modalOrder.close();
  });

  drawerCart.addEventListener("click", (e) => {
    if (e.target === drawerCart) drawerCart.close();
  });
  modalProduct.addEventListener("click", (e) => {
    if (e.target === modalProduct) modalProduct.close();
  });
  modalOrder.addEventListener("click", (e) => {
    if (e.target === modalOrder) modalOrder.close();
  });

  document.getElementById("modal-add-cart").addEventListener("click", async (e) => {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    const item = await fetchItem(id);
    addToCart(item);
    modalProduct.close();
    drawerCart.showModal();
  });

  document.getElementById("cart-list").addEventListener("click", (e) => {
    const btn = e.target.closest(".cart-item-remove");
    if (btn?.dataset.id) removeFromCart(btn.dataset.id);
  });

  document.getElementById("btn-checkout").addEventListener("click", () => {
    if (loadCart().length === 0) return;
    drawerCart.close();
    resetOrderModal();
    modalOrder.showModal();
  });

  document.getElementById("order-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const status = document.getElementById("order-status");
    const submitBtn = document.getElementById("order-submit");
    const fd = new FormData(form);
    const phone = String(fd.get("phone") || "").trim();
    const email = String(fd.get("email") || "").trim();
    const comment = String(fd.get("comment") || "").trim();
    status.textContent = "";
    status.className = "form-status";
    submitBtn.disabled = true;
    const itemsSnapshot = loadCart();
    if (itemsSnapshot.length === 0) {
      status.textContent = "Сначала добавьте товары в корзину.";
      status.classList.add("err");
      submitBtn.disabled = false;
      return;
    }
    status.textContent = "Отправляем заявку…";
    try {
      await submitOrder(phone, email, comment, itemsSnapshot);
      saveCart([]);
      renderCart([]);
      form.reset();
      document.getElementById("order-form-block").hidden = true;
      const successPanel = document.getElementById("order-success-panel");
      successPanel.hidden = false;
      requestAnimationFrame(() => document.getElementById("order-success-close").focus());
    } catch (err) {
      console.error(err);
      const hint =
        err instanceof Error && err.message
          ? err.message
          : "Проверьте интернет. Если сайт открыт как файл с диска — заявка открывается в новой вкладке; для AJAX-отправки без вкладки запустите локальный сервер (например: npx serve . в папке milana-store).";
      status.textContent = `Не удалось отправить. ${hint}`;
      status.classList.add("err");
    } finally {
      submitBtn.disabled = false;
    }
  });

  grid.addEventListener("click", (e) => {
    const card = e.target.closest(".card[data-id]");
    if (card) openProductModal(card.dataset.id);
  });

  renderCart(loadCart());
  initContactForm();

  await loadOverrides();

  fetch(CATALOG_URL)
    .then((r) => {
      if (!r.ok) throw new Error("catalog");
      return r.json();
    })
    .then(async (catalog) => {
      renderCatalogMeta(catalog);
      const settled = await Promise.all(
        catalog.items.map((id) =>
          fetchItem(id)
            .then((item) => ({ ok: true, item }))
            .catch((e) => {
              console.warn(id, e);
              return { ok: false };
            })
        )
      );
      const fragments = [];
      for (const r of settled) {
        if (r.ok) fragments.push(cardTemplate(r.item));
      }
      grid.innerHTML = fragments.join("");
    })
    .catch(() => {
      errEl.hidden = false;
      errEl.textContent =
        "Каталог не загрузился. Запустите локальный сервер из папки milana-store (например: npx serve .), иначе браузер блокирует fetch к JSON.";
    });
}

init();
