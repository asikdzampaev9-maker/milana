"""
Извлечение таблицы характеристик с JPG (EasyOCR) в формате как у «Виктория 3-D».

Запуск из папки milana-store:
  pip install -r requirements-ocr.txt
  python _ocr_catalog_specs.py
  python _ocr_catalog_specs.py --dry-run
  python _ocr_catalog_specs.py --only p09-1,p16-1

Дописывает в data/items/*.json поля Габариты, Спальное место, Механизм, Наполнение, Каркас
и сохраняет «Источник», если он уже был.
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

# (каноническое имя, regex для строки-метки в OCR)
MARKERS: list[tuple[str, re.Pattern[str]]] = [
    ("Габариты", re.compile(r"абарит", re.I)),
    ("Спальное место", re.compile(r"спальн.*мест", re.I)),
    ("Механизм", re.compile(r"еханизм", re.I)),
    ("Наполнение", re.compile(r"аполнен", re.I)),
    ("Каркас", re.compile(r"аркас", re.I)),
]


def clean_value(s: str) -> str:
    s = s.strip()
    if not s:
        return s
    t = s
    # Только «цифра х цифра» — не трогаем «холлофайбер», «механизм» и т.д.
    t = re.sub(r"(?<=\d)\s*х\s*(?=\d)", "×", t, flags=re.I)
    t = re.sub(r"(?<=\d)\s*[xX]\s*(?=\d)", "×", t)
    t = re.sub(r"(\d)\s*×\s*(\d)", r"\1×\2", t)
    # OCR: буква О/о вместо нуля только рядом с цифрами (не трогаем слова в «Наполнение»)
    if re.search(r"\d", t):
        prev = None
        while prev != t:
            prev = t
            t = re.sub(r"(?<=\d)[ОоO](?=\d)", "0", t)
            t = re.sub(r"(?<=\d)[ОоO](?=\D|$)", "0", t)
    if re.search(r"\d+×\d+", t) and not re.search(r"см|мм|м\b", t, re.I):
        t = t.rstrip(".") + " см"
    t = re.sub(r"\s+", " ", t)
    return t


def is_marker_line(line: str) -> bool:
    return any(p.search(line) for _, p in MARKERS)


def extract_specs_from_lines(lines: list[str]) -> dict[str, str]:
    flat: list[str] = []
    for ln in lines:
        s = ln.strip()
        if s:
            flat.append(s)

    hits: list[tuple[int, str]] = []
    for i, ln in enumerate(flat):
        for name, pat in MARKERS:
            if pat.search(ln):
                hits.append((i, name))
                break

    if not hits:
        return {}

    # Один снимок — берём первый полный набор из пяти (на полосе с несколькими моделями)
    by_name: dict[str, str] = {}
    for j, (start_i, name) in enumerate(hits):
        if name in by_name:
            continue
        end_i = hits[j + 1][0] if j + 1 < len(hits) else len(flat)
        chunk = flat[start_i:end_i]
        val = value_from_chunk(chunk, name)
        val = clean_value(val)
        if val and len(val) > 1:
            by_name[name] = val
        if len(by_name) >= 5:
            break

    return by_name


def value_from_chunk(chunk: list[str], name: str) -> str:
    first = chunk[0]
    if ":" in first:
        after = first.split(":", 1)[1].strip()
        rest = "\n".join(chunk[1:]).strip()
        if after and not is_marker_tail(after):
            return (after + (" " + rest if rest else "")).strip()
    rest = "\n".join(chunk[1:]).strip()
    return rest


def is_marker_tail(s: str) -> bool:
    return bool(s) and len(s) < 3


def needs_specs(specs: dict) -> bool:
    if not specs or not isinstance(specs, dict):
        return True
    if "Габариты" in specs and specs["Габариты"]:
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", type=str, default="", help="p09-1,p10-2")
    ap.add_argument(
        "--missing",
        action="store_true",
        help="только JSON без поля «Габариты» (удобно дозаполнять после прерывания)",
    )
    args = ap.parse_args()

    try:
        import easyocr
    except ImportError:
        print("Нужен easyocr: pip install -r requirements-ocr.txt", file=sys.stderr)
        return 1

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    ids: list[str] = catalog.get("items", [])
    if args.only.strip():
        allow = {x.strip() for x in args.only.split(",") if x.strip()}
        ids = [i for i in ids if i in allow]
    elif args.missing:
        keep: list[str] = []
        for i in ids:
            p = ITEMS / f"{i}.json"
            if not p.is_file():
                continue
            data = json.loads(p.read_text(encoding="utf-8"))
            if needs_specs(data.get("specs") or {}):
                keep.append(i)
        ids = keep

    reader = easyocr.Reader(["ru", "en"], gpu=False)
    updated = 0
    skipped = 0
    failed = 0

    for pid in ids:
        path = ITEMS / f"{pid}.json"
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        specs = data.get("specs") or {}
        if not needs_specs(specs):
            skipped += 1
            continue

        rel = (data.get("image") or "").lstrip("/")
        img_path = ROOT / rel if rel else None
        if not img_path or not img_path.is_file():
            print(pid, "— нет файла изображения")
            failed += 1
            continue

        lines = reader.readtext(str(img_path), detail=0, paragraph=False)
        extracted = extract_specs_from_lines(lines if isinstance(lines, list) else list(lines))
        if len(extracted) < 2:
            print(pid, "— мало полей OCR:", list(extracted.keys()))
            failed += 1
            continue

        source = specs.get("Источник")
        new_specs: dict[str, str] = {**extracted}
        if source:
            new_specs["Источник"] = source

        if args.dry_run:
            print(pid, "->", json.dumps(new_specs, ensure_ascii=True))
            updated += 1
            continue

        data["specs"] = new_specs
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(pid, "OK", len(extracted), "полей")
        updated += 1

    print("--- готово: обновлено", updated, "пропущено (уже есть Габариты)", skipped, "ошибок", failed)
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
