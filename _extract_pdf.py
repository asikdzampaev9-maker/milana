"""One-off: dump PDF text + render pages to PNG for catalog import."""
import glob
import os
import re

import fitz

desk = os.path.join(os.environ["USERPROFILE"], "Desktop")
pdfs = [p for p in glob.glob(os.path.join(desk, "*.pdf")) if "Milana" in os.path.basename(p)]
if not pdfs:
    pdfs = glob.glob(os.path.join(desk, "*.pdf"))
pdf_path = pdfs[0]
out_dir = os.path.join(desk, "milana-store", "data", "catalog-source")
os.makedirs(out_dir, exist_ok=True)

doc = fitz.open(pdf_path)
text_parts = []
for i in range(len(doc)):
    page = doc[i]
    text_parts.append(f"\n--- page {i+1} ---\n")
    text_parts.append(page.get_text("text"))
    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
    pix.save(os.path.join(out_dir, f"page-{i+1:03d}.png"))

with open(os.path.join(out_dir, "extracted-text.txt"), "w", encoding="utf-8") as f:
    f.write("".join(text_parts))

print("pages", len(doc), "pdf", pdf_path, "out", out_dir)
doc.close()
