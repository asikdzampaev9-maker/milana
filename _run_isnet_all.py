import os, glob
from PIL import Image, ImageChops
from rembg import remove, new_session
SRC="data/images/products-clean"; OUT="data/images/products-isnet"
os.makedirs(OUT,exist_ok=True); sess=new_session("isnet-general-use")
def trim(im,thr=10):
    d=ImageChops.difference(im,Image.new("RGB",im.size,(255,255,255))).convert("L")
    b=d.point(lambda p:255 if p>thr else 0).getbbox(); return im.crop(b) if b else im
ids=sorted(os.path.splitext(os.path.basename(f))[0] for f in glob.glob(f"{SRC}/*.jpg"))
for i,pid in enumerate(ids,1):
    try:
        im=Image.open(f"{SRC}/{pid}.jpg").convert("RGB")
        cut=remove(im,session=sess)
        w=Image.new("RGB",cut.size,(255,255,255)); w.paste(cut,mask=cut.split()[-1]); w=trim(w)
        CW,CH=1000,750; w.thumbnail((int(CW*0.9),int(CH*0.9)),Image.LANCZOS)
        c=Image.new("RGB",(CW,CH),(255,255,255)); c.paste(w,((CW-w.width)//2,(CH-w.height)//2))
        c.save(f"{OUT}/{pid}.jpg","JPEG",quality=90)
        print(f"[{i}/{len(ids)}] {pid}")
    except Exception as e:
        print(f"[{i}/{len(ids)}] ERR {pid}: {e}")
print("готово")
