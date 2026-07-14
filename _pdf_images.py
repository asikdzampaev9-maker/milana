import glob
import os

import fitz

desk = os.path.join(os.environ["USERPROFILE"], "Desktop")
pdfs = glob.glob(os.path.join(desk, "*.pdf"))
pdf_path = pdfs[0]
imgdir = os.path.join(desk, "milana-store", "data", "images-extracted")
os.makedirs(imgdir, exist_ok=True)
doc = fitz.open(pdf_path)
seen = set()
count = 0
for i in range(len(doc)):
    for img in doc.get_page_images(i, full=True):
        xref = img[0]
        if xref in seen:
            continue
        seen.add(xref)
        base = doc.extract_image(xref)
        ext = base["ext"]
        name = "p{:03d}_xref{}.{}".format(i + 1, xref, ext)
        path = os.path.join(imgdir, name)
        with open(path, "wb") as f:
            f.write(base["image"])
        count += 1
print("unique images", count, "dir", imgdir)
doc.close()
