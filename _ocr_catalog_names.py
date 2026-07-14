"""
Распознавание названий моделей с JPG-карточек каталога и запись в data/items/*.json.

Установка (один раз):
  pip install easyocr opencv-python-headless pillow

Запуск из папки milana-store:
  python _ocr_catalog_names.py
  python _ocr_catalog_names.py --dry-run   # только показать, не писать JSON
  python _ocr_catalog_names.py --only p25-1,p26-2

Первый запуск EasyOCR скачает модели (~100+ МБ).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ITEMS = ROOT / "data" / "items"
CATALOG = ROOT / "data" / "catalog.json"

# Слова перед «…» в каталоге (расширяйте при необходимости)
TYPE_WORD = (
    "Диван",
    "Софа",
    "Кровать",
    "Кресло",
    "Комплект",
    "Модуль",
    "Пуф",
    "Тахта",
    "Кушетка",
    "Банкетка",
    "Шкаф",
    "Стол",
    "Консоль",
    "Тумба",
    "Полка",
)

TYPE_PREFIX = re.compile(
    r"^(?:Диван\s+угловой|Диван\s+для|Диван|Софа|Кровать|Кресло|Комплект|Модуль|Пуф|Тахта|Кушетка|Банкетка|Шкаф|Стол|Консоль|Тумба|Полка)\b",
    re.I | re.UNICODE,
)

# «ёлочки» и ASCII-кавычки как у OCR
QUOTE_OPEN = "«\"\u201c\u00ab"
QUOTE_CLOSE = "»\"\u201d\u00bb"


def normalize_ocr_quotes(s: str) -> str:
    s = re.sub(rf"[{re.escape(QUOTE_OPEN)}]", "«", s)
    s = re.sub(rf"[{re.escape(QUOTE_CLOSE)}]", "»", s)
    return s


def extract_titles_from_text(text: str) -> list[str]:
    text = normalize_ocr_quotes(text)
    found = []
    for m in re.finditer(r"«([^»]{1,80})»", text):
        inner = m.group(1).strip()
        if len(inner) < 2:
            continue
        found.append(inner)
    return found


def title_from_line(ln: str) -> str | None:
    """Одна строка OCR: «Диван … «Имя»» или префикс + ёлочки."""
    s = normalize_ocr_quotes(ln.strip())
    if "«" not in s:
        return None
    i = s.find("«")
    j = s.find("»", i)
    if j < 0:
        return None
    quoted = s[i : j + 1]
    inner = quoted[1:-1].strip()
    if len(inner) < 1:
        return None
    prefix = s[:i].strip()
    if TYPE_PREFIX.match(prefix):
        return f"{prefix} {quoted}".replace("  ", " ").strip()
    # префикс без regex (OCR мог съесть букву)
    pl = prefix.lower()
    for w in TYPE_WORD:
        if pl.startswith(w.lower()) or f" {w.lower()} " in f" {pl} ":
            return f"{prefix} {quoted}".replace("  ", " ").strip()
    return quoted


def pick_best_title(ocr_lines: list[str], raw_blob: str) -> str | None:
    """Сначала строки сверху с типом + «…», иначе лучшее «…» из текста."""
    for line in ocr_lines:
        t = title_from_line(line)
        if t:
            return t

    blob = normalize_ocr_quotes(raw_blob)
    from_blob = extract_titles_from_text(blob)
    best = None
    best_score = -1
    for inner in from_blob:
        score = len(inner)
        idx = blob.find(f"«{inner}»")
        if idx > 0:
            ctx = blob[max(0, idx - 50) : idx]
            if TYPE_PREFIX.search(ctx):
                score += 50
            for w in TYPE_WORD:
                if w.lower() in ctx.lower():
                    score += 80
                    break
        if score > best_score:
            best_score = score
            best = inner

    if best:
        idx = blob.find(f"«{best}»")
        if idx > 0:
            ctx = blob[max(0, idx - 55) : idx]
            m = TYPE_PREFIX.search(ctx)
            if m:
                return f"{m.group(0).strip()} «{best}»"
        return f"«{best}»"

    for line in ocr_lines:
        ln = line.strip()
        if TYPE_PREFIX.match(normalize_ocr_quotes(ln)) and 5 < len(ln) < 130:
            return normalize_ocr_quotes(ln)
    return None


def needs_ocr_name(name: str) -> bool:
    if not name:
        return True
    if re.search(r"стр\s*\.", name, re.I):
        return True
    if re.match(r"^модель каталога", name, re.I):
        return True
    return False


def run_ocr(reader, image_path: Path) -> tuple[list[str], str]:
    gray = None
    try:
        import cv2

        img = cv2.imread(str(image_path))
        if img is not None:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            h, w = gray.shape[:2]
            if w < 900:
                scale = 1.6
                gray = cv2.resize(
                    gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC
                )
    except Exception:
        gray = None

    if gray is None:
        results = reader.readtext(str(image_path), detail=1, paragraph=False)
    else:
        results = reader.readtext(gray, detail=1, paragraph=False)
    # сортировка: сверху вниз (y), слева направо
    def sort_key(item):
        box, _text, _conf = item
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        return (sum(ys) / len(ys), sum(xs) / len(xs))

    results = sorted(results, key=sort_key)
    lines = []
    for _box, text, conf in results:
        if conf < 0.25:
            continue
        t = text.strip()
        if len(t) < 2:
            continue
        lines.append(t)
    blob = "\n".join(lines)
    return lines, blob


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", type=str, default="", help="id через запятую")
    args = ap.parse_args()
    only = {x.strip() for x in args.only.split(",") if x.strip()}

    try:
        import easyocr
    except ImportError:
        print("Установите: pip install easyocr opencv-python-headless", file=sys.stderr)
        return 1

    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    ids = cat.get("items", [])
    if only:
        ids = [i for i in ids if i in only]

    print("Инициализация EasyOCR (ru, en)…")
    reader = easyocr.Reader(["ru", "en"], gpu=False, verbose=False)

    updated = 0
    skipped = 0
    failed = []

    for item_id in ids:
        jpath = ITEMS / f"{item_id}.json"
        if not jpath.is_file():
            continue
        data = json.loads(jpath.read_text(encoding="utf-8"))
        old_name = data.get("name", "")
        if not needs_ocr_name(old_name):
            skipped += 1
            continue

        rel = data.get("image", f"data/images/products/{item_id}.jpg")
        img_path = ROOT / Path(rel.replace("\\", "/"))
        if not img_path.is_file():
            failed.append((item_id, "нет файла изображения"))
            continue

        try:
            lines, blob = run_ocr(reader, img_path)
            title = pick_best_title(lines, blob)
        except Exception as e:
            failed.append((item_id, str(e)))
            continue

        if not title:
            failed.append((item_id, "не распознано «название»"))
            continue

        if title == old_name:
            skipped += 1
            continue

        print(f"  {item_id}: {old_name[:50]}… -> {title}")
        if not args.dry_run:
            data["name"] = title
            jpath.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        updated += 1

    print(f"\nГотово: обновлено {updated}, пропущено (уже ок) {skipped}, ошибок {len(failed)}")
    if failed:
        print("Не удалось:")
        for fid, reason in failed[:30]:
            print(f"  {fid}: {reason}")
        if len(failed) > 30:
            print(f"  … и ещё {len(failed) - 30}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
