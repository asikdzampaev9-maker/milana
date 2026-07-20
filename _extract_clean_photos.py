# -*- coding: utf-8 -*-
"""Вырезает ТОЛЬКО сам диван (основное фото) из каждой карточки PDF.
Берёт самое большое встроенное изображение в области товара и извлекает
его как есть — без таблиц, схем механизма, сложенных видов и подписей."""
import fitz, io, os
from PIL import Image

DESK = "/Users/aslanbekdzampaev/Desktop"
PDF = os.path.join(DESK, "Каталог НОВ.pdf")
OUT = os.path.join(DESK, "milana-store-main", "data", "images", "products-clean")
os.makedirs(OUT, exist_ok=True)
doc = fitz.open(PDF)

def names_of(p):
    ns = []
    for b in p.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            t = "".join(s["text"] for s in l["spans"]).strip()
            if l["spans"][0]["size"] > 18 and "«" in t:
                ns.append((round(l["bbox"][1], 1), t))
    return sorted(ns)

def page_image_rects(p):
    seen = set(); rects = []
    for img in p.get_images(full=True):
        xref = img[0]
        for r in p.get_image_rects(xref):
            k = (xref, round(r.x0), round(r.y0))
            if k in seen:
                continue
            seen.add(k); rects.append((xref, r))
    return rects

def largest_in(rects, x0, y0, x1, y1):
    inside = [(xref, r) for xref, r in rects
              if x0 <= (r.x0 + r.x1) / 2 <= x1 and y0 <= (r.y0 + r.y1) / 2 <= y1]
    inside.sort(key=lambda t: -t[1].width * t[1].height)
    return inside[0][0] if inside else None

def save_xref(xref, pid):
    d = doc.extract_image(xref)
    im = Image.open(io.BytesIO(d["image"]))
    if im.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        im = im.convert("RGBA")
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    im.save(os.path.join(OUT, pid + ".jpg"), "JPEG", quality=92)
    return im.size

count = 0
# --- страницы 3..26: 3 полосы по названиям ---
for pi in range(2, 26):
    p = doc[pi]
    names = names_of(p)
    rects = page_image_rects(p)
    bnds = [names[i][0] - 6 for i in range(len(names))] + [9999]
    for bi in range(len(names)):
        lo = 0 if bi == 0 else bnds[bi]
        hi = bnds[bi + 1]
        band = [(xref, r) for xref, r in rects if lo <= (r.y0 + r.y1) / 2 < hi]
        band.sort(key=lambda t: -t[1].width * t[1].height)
        pid = f"p{pi+1:02d}-{bi+1}"
        if band:
            save_xref(band[0][0], pid); count += 1
        else:
            print("НЕТ ФОТО:", pid)

# --- страница 27: сетка, ручные боксы (x0,y0,x1,y1) в pt ---
p27 = doc[26]
rects27 = page_image_rects(p27)
P27 = [
    ("p27-1", (0,   0,   330, 236)),  # Банкетка «Милана»
    ("p27-2", (0,   237, 335, 420)),  # Кресло «Парав»
    ("p27-3", (335, 237, 642, 424)),  # Кресло «Мини»
    ("p27-4", (0,   405, 168, 600)),  # Пуф «Алина»
    ("p27-5", (168, 405, 335, 600)),  # Пуф «Квадро»
    ("p27-6", (335, 405, 642, 615)),  # Кресло «Качалка»
]
for pid, box in P27:
    xref = largest_in(rects27, *box)
    if xref:
        save_xref(xref, pid); count += 1
    else:
        print("НЕТ ФОТО:", pid)

print(f"Готово: {count} чистых фото -> {OUT}")
