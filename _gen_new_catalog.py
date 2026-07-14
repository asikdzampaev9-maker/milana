# -*- coding: utf-8 -*-
"""Генерация нового каталога сайта из PDF «Каталог НОВ.pdf».
Формат карточек — как на сайте: data/items/*.json + data/images/products/*.jpg + catalog.json.
Пишет в data_new/ (проверка), без перезаписи текущих данных."""
import fitz, io, json, os, re
from PIL import Image

DESK = "/Users/aslanbekdzampaev/Desktop"
PDF = os.path.join(DESK, "Каталог НОВ.pdf")
ROOT = os.path.join(DESK, "milana-store-main")
OUT = os.path.join(ROOT, "data_new")
OUT_ITEMS = os.path.join(OUT, "items")
OUT_IMG = os.path.join(OUT, "images", "products")
for d in (OUT_ITEMS, OUT_IMG):
    os.makedirs(d, exist_ok=True)

Z = 4.0
PH = 642.0
doc = fitz.open(PDF)

def lines_of(p):
    out = []
    for b in p.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            txt = "".join(s["text"] for s in l["spans"]).strip()
            if not txt:
                continue
            out.append((round(l["bbox"][1], 1), round(l["bbox"][0], 1),
                        round(l["spans"][0]["size"], 1), txt))
    return out

def merge_colvet(lines):
    out, skip = [], set()
    for i, (y, x, s, t) in enumerate(lines):
        if i in skip:
            continue
        if t == "Цвет":
            for j, (y2, x2, s2, t2) in enumerate(lines):
                if j != i and t2 == "подлокотника:" and abs(x2 - x) < 8 and 0 < y2 - y < 16:
                    out.append((y, x, s, "Цвет подлокотника:")); skip.add(j); break
            else:
                out.append((y, x, s, t))
        else:
            out.append((y, x, s, t))
    return out

def is_name(s, t):
    return s > 18 and "«" in t

def parse_specs(plines):
    """plines — строки одного товара. Возвращает список (label, value)."""
    labels = [(y, x, t[:-1].strip()) for (y, x, s, t) in plines
              if t.endswith(":") and not is_name(s, t)]
    values = [(y, x, t) for (y, x, s, t) in plines
              if not t.endswith(":") and not is_name(s, t)]
    labels.sort()
    lv = {i: [] for i in range(len(labels))}
    used = set()
    # 1) значение на той же строке, что и метка, и правее неё
    for vi, (vy, vx, vt) in enumerate(values):
        best = None
        for li, (ly, lx, lt) in enumerate(labels):
            if abs(vy - ly) <= 5 and vx > lx:
                d = vx - lx
                if best is None or d < best[1]:
                    best = (li, d)
        if best:
            lv[best[0]].append((vy, vx, vt)); used.add(vi)
    # 2) перенос строки значения — к ближайшей метке выше, левее значения
    for vi, (vy, vx, vt) in enumerate(values):
        if vi in used:
            continue
        best = None
        for li, (ly, lx, lt) in enumerate(labels):
            if ly < vy and vx > lx:
                d = vy - ly
                if best is None or d < best[1]:
                    best = (li, d)
        if best:
            lv[best[0]].append((vy, vx, vt)); used.add(vi)
    specs = []
    for li, (ly, lx, lt) in enumerate(labels):
        parts = [t for (yy, xx, t) in sorted(lv[li])]
        val = re.sub(r"\s{2,}", " ", " ".join(parts).strip())
        if not val and "Цвет" in lt:
            val = "по каталогу"
        specs.append((lt, val))
    return specs

def category_of(name):
    n = name.lower()
    if n.startswith("диван"):    return "Диваны"
    if n.startswith("кровать"):  return "Кровати"
    if n.startswith("кресло"):   return "Кресла"
    if n.startswith("софа"):     return "Диваны"
    if n.startswith("комплект"): return "Комплекты"
    if n.startswith("банкетка"): return "Банкетки"
    if n.startswith("пуф"):      return "Пуфы"
    return "Мягкая мебель"

def make_short(specs):
    d = dict(specs)
    bits = []
    mech = d.get("Механизм")
    if mech:
        bits.append(mech.capitalize() + " механизм")
    nap = d.get("Наполнение", "")
    if nap:
        bits.append(nap.split(";")[0].strip())
    s = ", ".join(bits)
    return (s[0].upper() + s[1:] + ".") if s else ""

def save_card(pix, box_pt, out_path):
    """box_pt = (x0,y0,x1,y1) в pt; вырезает из pixmap и пишет jpg."""
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    x0, y0, x1, y1 = [int(round(v * Z)) for v in box_pt]
    x0 = max(0, x0); y0 = max(0, y0)
    x1 = min(pix.width, x1); y1 = min(pix.height, y1)
    crop = img.crop((x0, y0, x1, y1))
    crop.save(out_path, "JPEG", quality=90)

# Ручные характеристики для комбо-карточек (диван + кресла): у них в PDF
# двухуровневая таблица, которую автопарсер собирает с путаницей.
OVERRIDES = {
    "p18-1": [
        ("Габариты дивана", "235х105 см"), ("Спальное место дивана", "195х160 см"),
        ("Габариты кресла", "105х105 см"), ("Спальное место кресла", "70х160 см"),
        ("Механизм", "выкатной"),
        ("Наполнение", "независимый пружинный блок; войлок, ППУ; холлофайбер"),
        ("Каркас", "ДСП; ДВП; фанера; лес"),
    ],
    "p20-1": [
        ("Габариты дивана", "155х95 см"), ("Спальное место дивана", "120х190 см"),
        ("Габариты кресла", "107х95 см"), ("Спальное место кресла", "70х190 см"),
        ("Механизм", "выкатной"),
        ("Наполнение", "войлок, ППУ; холлофайбер"),
        ("Каркас", "ДСП; ДВП; фанера; лес"),
    ],
    "p22-1": [
        ("Габариты", "225х110 см"), ("Спальное место", "190х150 см"),
        ("Кресло-кровать", "100х100 см"), ("Спальное место кресла", "190х75 см"),
        ("Механизм", "дельфин"),
        ("Наполнение", "ППУ; холлофайбер"),
        ("Каркас", "ДСП; ДВП; фанера; лес"),
    ],
    "p22-2": [
        ("Габариты", "220х105 см"), ("Спальное место", "190х150 см"),
        ("Кресло-кровать", "100х105 см"), ("Спальное место кресла", "190х80 см"),
        ("Механизм", "тик-так и раскладной"),
        ("Наполнение", "независимый пружинный блок; войлок; ППУ; холлофайбер"),
        ("Каркас", "ДСП; ДВП; фанера; лес"),
    ],
    "p22-3": [
        ("Габариты", "275х186 см"), ("Спальное место", "220х145 см"),
        ("Кресло-кровать", "100х100 см"), ("Спальное место кресла", "190х75 см"),
        ("Механизм", "дельфин"),
        ("Наполнение", "ППУ; холлофайбер"),
        ("Каркас", "ДСП; ДВП; фанера; лес"),
    ],
}

def write_item(pid, name, specs, img_rel):
    if pid in OVERRIDES:
        specs = OVERRIDES[pid]
    item = {
        "id": pid,
        "name": name,
        "category": category_of(name),
        "short": make_short(specs),
        "description": f"{name} — каталог Milana Group 2026.",
        "specs": {k: v for k, v in specs if v},
        "image": img_rel,
    }
    with open(os.path.join(OUT_ITEMS, pid + ".json"), "w", encoding="utf-8") as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
    return item

order = []  # id список для catalog.json

# --- Регулярные страницы 3..26: 3 товара, вертикальные полосы по названиям ---
for pi in range(2, 26):
    p = doc[pi]
    lines = merge_colvet(lines_of(p))
    names = sorted([(y, x, t) for (y, x, s, t) in lines if is_name(s, t)])
    pix = p.get_pixmap(matrix=fitz.Matrix(Z, Z))
    for bi, (ny, nx, nt) in enumerate(names):
        y_lo = ny - 6
        y_hi = names[bi + 1][0] - 6 if bi + 1 < len(names) else 9999
        plines = [L for L in lines if y_lo <= L[0] < y_hi]
        specs = parse_specs(plines)
        pid = f"p{pi+1:02d}-{bi+1}"
        img_rel = f"data/images/products/{pid}.jpg"
        # обрезка полосы: линия реза чуть выше заголовка следующего товара,
        # чтобы карточка начиналась с названия и без «хвоста» предыдущей.
        top = 0 if bi == 0 else ny - 2
        bottom = names[bi + 1][0] - 2 if bi + 1 < len(names) else PH
        save_card(pix, (0, top, PH, bottom), os.path.join(OUT_IMG, pid + ".jpg"))
        write_item(pid, nt, specs, img_rel)
        order.append(pid)

# --- Страница 27: нестандартная сетка, ручные боксы ---
p27 = doc[26]
lines27 = merge_colvet(lines_of(p27))
pix27 = p27.get_pixmap(matrix=fitz.Matrix(Z, Z))

def specs_in_box(x0, y0, x1, y1):
    sub = [L for L in lines27 if x0 <= L[1] <= x1 and y0 <= L[0] <= y1]
    return parse_specs(sub)

# (id, имя, crop-бокс pt, бокс-для-текста pt)
P27 = [
    ("p27-1", "Банкетка «Милана»", (0,   0,   642, 236), (330,150, 642,236)),
    ("p27-2", "Кресло «Парав»",    (0,   236, 335, 415), (40, 290, 178,415)),
    ("p27-3", "Кресло «Мини»",     (335, 236, 642, 424), (330,290, 470,424)),
    ("p27-4", "Пуф «Алина»",       (0,   410, 170, 600), None),
    ("p27-5", "Пуф «Квадро»",      (168, 410, 330, 600), None),
    ("p27-6", "Кресло «Качалка»",  (335, 410, 642, 615), (330,470, 470,600)),
]
for pid, name, cbox, tbox in P27:
    specs = specs_in_box(*tbox) if tbox else []
    save_card(pix27, cbox, os.path.join(OUT_IMG, pid + ".jpg"))
    write_item(pid, name, specs, f"data/images/products/{pid}.jpg")
    order.append(pid)

catalog = {
    "brand": "Milana Group",
    "year": 2026,
    "source": "Каталог НОВ.pdf",
    "items": order,
}
with open(os.path.join(OUT, "catalog.json"), "w", encoding="utf-8") as f:
    json.dump(catalog, f, ensure_ascii=False, indent=2)

print(f"Готово: {len(order)} товаров -> {OUT}")
print("Категории:", {c: sum(1 for i in order) for c in []} or "см. файлы")
