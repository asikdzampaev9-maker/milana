# -*- coding: utf-8 -*-
"""Вырезает ТОЛЬКО сам товар из каждой карточки PDF.
Ключевой момент: у фото в PDF есть маска прозрачности (SMask), которая скрывает
студийный фон. Её обязательно нужно применить — иначе в кадр лезут витрина,
стёганые панели и «размножения» соседних объектов.
Результат: товар на чистом белом холсте 4:3."""
import fitz, os, glob
from PIL import Image, ImageChops

PDF = "/Users/aslanbekdzampaev/Downloads/Каталог НОВ.pdf"
ROOT = "/Users/aslanbekdzampaev/Desktop/milana-store-main"
OUT = os.path.join(ROOT, "data", "images", "products")
os.makedirs(OUT, exist_ok=True)
CW, CH = 1000, 750
doc = fitz.open(PDF)


def names_of(p):
    ns = []
    for b in p.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            t = "".join(s["text"] for s in l["spans"]).strip()
            if l["spans"][0]["size"] > 18 and "«" in t:
                ns.append((round(l["bbox"][1], 1), t))
    return sorted(ns)


def band_images(p, lo, hi):
    """Изображения, чей центр попадает в полосу товара: (площадь, xref, smask)."""
    seen, out = set(), []
    for img in p.get_images(full=True):
        xref, smask = img[0], img[1]
        for r in p.get_image_rects(xref):
            if not (lo <= (r.y0 + r.y1) / 2 < hi):
                continue
            k = (xref, round(r.x0), round(r.y0))
            if k in seen:
                continue
            seen.add(k)
            out.append((r.width * r.height, xref, smask))
    out.sort(reverse=True)
    return out


def load_rgba(xref, smask):
    """Пиксмап с применённой маской прозрачности."""
    pix = fitz.Pixmap(doc, xref)
    if pix.colorspace and pix.colorspace.n == 4:  # CMYK -> RGB
        pix = fitz.Pixmap(fitz.csRGB, pix)
    if smask:
        mask = fitz.Pixmap(doc, smask)
        try:
            pix = fitz.Pixmap(pix, mask)
        except Exception:
            pass
    mode = "RGBA" if pix.alpha else "RGB"
    return Image.frombytes(mode, (pix.width, pix.height), pix.samples)


def to_canvas(im):
    """Композит на белом, обрезка полей, центр на холсте 4:3."""
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    diff = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).convert("L")
    bbox = diff.point(lambda p: 255 if p > 11 else 0).getbbox()
    if bbox:
        im = im.crop(bbox)
    im.thumbnail((int(CW * 0.9), int(CH * 0.9)), Image.LANCZOS)
    canvas = Image.new("RGB", (CW, CH), (255, 255, 255))
    canvas.paste(im, ((CW - im.width) // 2, (CH - im.height) // 2))
    return canvas


def save(xref, smask, pid):
    to_canvas(load_rgba(xref, smask)).save(os.path.join(OUT, pid + ".jpg"), "JPEG", quality=92)


n = 0
# --- страницы 3..26: три полосы по названиям ---
for pi in range(2, 26):
    p = doc[pi]
    names = names_of(p)
    bnds = [names[i][0] - 6 for i in range(len(names))] + [9999]
    for bi in range(len(names)):
        lo = 0 if bi == 0 else bnds[bi]
        cand = band_images(p, lo, bnds[bi + 1])
        pid = f"p{pi+1:02d}-{bi+1}"
        if cand:
            save(cand[0][1], cand[0][2], pid)
            n += 1
        else:
            print("НЕТ ФОТО:", pid)

# --- страница 27: сетка, ручные боксы ---
p27 = doc[26]
P27 = [
    ("p27-1", (0, 0, 330, 236)),      # Банкетка «Милана»
    ("p27-2", (0, 237, 335, 420)),    # Кресло «Парав»
    ("p27-3", (335, 237, 642, 424)),  # Кресло «Мини»
    ("p27-4", (0, 405, 168, 600)),    # Пуф «Алина»
    ("p27-5", (168, 405, 335, 600)),  # Пуф «Квадро»
    ("p27-6", (335, 405, 642, 615)),  # Кресло «Качалка»
]
for pid, (x0, y0, x1, y1) in P27:
    seen, cand = set(), []
    for img in p27.get_images(full=True):
        xref, smask = img[0], img[1]
        for r in p27.get_image_rects(xref):
            cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
            if not (x0 <= cx <= x1 and y0 <= cy <= y1):
                continue
            k = (xref, round(r.x0), round(r.y0))
            if k in seen:
                continue
            seen.add(k)
            cand.append((r.width * r.height, xref, smask))
    cand.sort(reverse=True)
    if cand:
        save(cand[0][1], cand[0][2], pid)
        n += 1
    else:
        print("НЕТ ФОТО:", pid)

print(f"Готово: {n} фото (с применением маски прозрачности) -> {OUT}")
