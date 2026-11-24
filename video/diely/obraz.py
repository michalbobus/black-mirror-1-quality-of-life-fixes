"""Obraz: bezokrajový fullscreen 16:9 s obrazom 4:3 (len karta – prepínanie okien sa vo videu neukazuje).
Pozadie karty: rozmazaná hala zo záznamu dielu hotspoty, ak existuje."""
import os
VERZIE = ()

def zostav(s):
    poz = None
    if os.path.exists(os.path.join(s.ZAZNAMY, "hotspoty_po.json")):
        z = s.Zaznam("hotspoty_po"); poz = s.snimka(z, z.start + 0.5)
    karta = s.karta([("Bezokrajový fullscreen", "podnadpis"), ("Borderless fullscreen", "en"), ("", "medzera"),
                    ("Pôvodne hra prepne celý monitor na 800 × 600.", "text"),
                    ("Originally the game switches the whole monitor to 800 × 600.", "en"), ("", "medzera"),
                    ("Teraz beží v bezokrajovom okne v rozlíšení obrazovky (16:9),", "text"),
                    ("obraz 4:3 bez deformácie, Alt+Tab bez prepínania režimu.", "text"),
                    ("Now it runs in a borderless window at desktop resolution (16:9),", "en"),
                    ("undistorted 4:3 image, Alt+Tab without mode switching.", "en")], 6, pozadie=poz)
    # celý rám 16:9 tak, ako ho vidí hráč (hala zo záznamu dielu kurzor)
    if not os.path.exists(os.path.join(s.ZAZNAMY, "kurzor_po.json")): return karta
    z = s.Zaznam("kurzor_po")
    k = s.vyrez(z, z.znacka("kruh_koniec"), z.znacka("kruh_koniec") + 6)
    return s.za_sebou(karta, s.samostatne(k, ("Celá obrazovka 16:9", "Full 16:9 screen"), stitok=None, orez43=False,
                                          popis="obraz 4:3 na stred, bez roztiahnutia  ·  4:3 image centred, not stretched"))
