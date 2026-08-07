# -*- coding: utf-8 -*-
"""Вырезает предмет мебели с фона нейросетью (rembg/u2net) и кладёт на белый
холст 4:3. Источник — исходные извлечённые фото data/images/products-clean.
Результат — data/images/products-rembg (для проверки перед заменой)."""
import os, glob, io
from PIL import Image, ImageChops
from rembg import remove, new_session

SRC = "data/images/products-clean"
OUT = "data/images/products-rembg"
os.makedirs(OUT, exist_ok=True)
CW, CH = 1000, 750
session = new_session("u2net")

def trim(im, thr=10):
    diff = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).convert("L")
    bbox = diff.point(lambda p: 255 if p > thr else 0).getbbox()
    return im.crop(bbox) if bbox else im

def process(pid):
    im = Image.open(f"{SRC}/{pid}.jpg").convert("RGB")
    cut = remove(im, session=session,
                 alpha_matting=True, alpha_matting_foreground_threshold=250,
                 alpha_matting_background_threshold=15, alpha_matting_erode_size=8)
    # композит на белом
    white = Image.new("RGB", cut.size, (255, 255, 255))
    white.paste(cut, mask=cut.split()[-1])
    white = trim(white)
    # холст 4:3
    white.thumbnail((int(CW * 0.9), int(CH * 0.9)), Image.LANCZOS)
    canvas = Image.new("RGB", (CW, CH), (255, 255, 255))
    canvas.paste(white, ((CW - white.width) // 2, (CH - white.height) // 2))
    canvas.save(f"{OUT}/{pid}.jpg", "JPEG", quality=90)

if __name__ == "__main__":
    ids = sorted(os.path.splitext(os.path.basename(f))[0] for f in glob.glob(f"{SRC}/*.jpg"))
    for i, pid in enumerate(ids, 1):
        try:
            process(pid)
            print(f"[{i}/{len(ids)}] {pid}")
        except Exception as e:
            print(f"[{i}/{len(ids)}] ОШИБКА {pid}: {e}")
    print("готово")
