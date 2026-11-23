"""porovnaj.py VYSTUP.png MENO... – výrezy postáv zo snimky/profily/MENO.png vedľa seba (zväčšené 2× najbližším bodom).
Výrez: obrazovka x 540–780, y 420–720 (postavy vľavo v salóne), alebo X0 Y0 X1 Y1 cez premennú VYREZ."""
import sys, os
from PIL import Image, ImageDraw
D = os.path.join(os.path.dirname(__file__), "..", "..", "snimky", "profily")
box = tuple(int(v) for v in os.environ.get("VYREZ", "540 420 780 720").split())
mena = sys.argv[2:]; w, h = (box[2] - box[0]) * 2, (box[3] - box[1]) * 2
out = Image.new("RGB", (w * len(mena), h + 24), "black"); d = ImageDraw.Draw(out)
for i, m in enumerate(mena):
    im = Image.open(os.path.join(D, m + ".png")).crop(box).resize((w, h), Image.NEAREST)
    out.paste(im, (i * w, 24)); d.text((i * w + 6, 5), m, fill="white")
out.save(sys.argv[1]); print(out.size)
