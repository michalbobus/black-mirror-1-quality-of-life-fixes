"""readme_obrazky.py – zostaví porovnania pred/po pre README do snimky/readme.
Vstupy: snimky/profily (zábery salónu), snimky/readme/zdroj (zábery haly s hotspotmi, filmy, ponuka)."""
import os
from PIL import Image, ImageDraw, ImageFont

P = os.path.join(os.path.dirname(__file__), "..", "..", "snimky")
PROF, ZDROJ, VYST = os.path.join(P, "profily"), os.path.join(P, "readme", "zdroj"), os.path.join(P, "readme")
PISMO = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 20)

def panel(obrazky, popisy, sirka):
    """Obrázky vedľa seba, každý zmenšený/zväčšený na danú šírku, nad každým popisok."""
    upr = [im.resize((sirka, round(im.height * sirka / im.width)), Image.LANCZOS) for im in obrazky]
    v = max(im.height for im in upr)
    out = Image.new("RGB", (sirka * len(upr) + 8 * (len(upr) - 1), v + 36), (20, 20, 20))
    d = ImageDraw.Draw(out)
    for i, (im, t) in enumerate(zip(upr, popisy)):
        x = i * (sirka + 8)
        out.paste(im, (x, 36)); d.text((x + 8, 4), t, font=PISMO, fill=(235, 225, 200))
    return out

def zv(im, box, k=2):
    """Výrez zväčšený k-krát najbližším bodom (aby boli vidno pixely)."""
    c = im.crop(box)
    return c.resize((c.width * k, c.height * k), Image.NEAREST)

# 1. vyhladenie postáv: pôvodná hra (bilinear) / ostrejší filter (lanczos-3) / lanczos-3 + vyhladené postavy
a, b, c = (Image.open(os.path.join(PROF, n + ".png")) for n in ("bilinear", "postavy_bez", "postavy_fxaa"))
box = (560, 400, 800, 700)
panel([zv(a, box), zv(b, box), zv(c, box)],
      ["Pôvodná hra / Original", "Ostrejšie / Sharper (lanczos-3)", "+ vyhladené postavy / smoothed characters"], 480).save(os.path.join(VYST, "vyhladenie.png"))
box = (885, 450, 1125, 750)                         # druhé porovnanie: stará pani
panel([zv(a, box), zv(b, box), zv(c, box)],
      ["Pôvodná hra / Original", "Ostrejšie / Sharper (lanczos-3)", "+ vyhladené postavy / smoothed characters"], 480).save(os.path.join(VYST, "vyhladenie2.png"))
# titulky sa nemenia
panel([zv(b, (740, 1000, 1190, 1050)), zv(c, (740, 1000, 1190, 1050))],
      ["Bez vyhladenia / No smoothing", "S vyhladením postáv – bez zmeny / With character smoothing – unchanged"], 900).save(os.path.join(VYST, "titulky.png"))

# 2. hotspoty
bez, s = (Image.open(os.path.join(ZDROJ, n + ".png")) for n in ("hala", "hala_hotspoty"))
panel([bez.crop((240, 80, 1680, 980)), s.crop((240, 80, 1680, 980))],
      ["Hala / Hall", "Medzerník: východy (dvere), ostatné (krúžky) / Space: exits (doors), others (rings)"], 720).save(os.path.join(VYST, "hotspoty.png"))

# 3. filmy na celú šírku
f0, f1 = (Image.open(os.path.join(ZDROJ, n + ".png")) for n in ("film_43", "film_sirka"))
panel([f0, f1], ["Pôvodne / Original: 4:3", "S úpravou / Improved: full width"], 720).save(os.path.join(VYST, "filmy.png"))
print("hotovo", os.listdir(VYST))
