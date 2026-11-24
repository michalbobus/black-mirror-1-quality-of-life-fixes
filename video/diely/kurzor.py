"""Hardvérový kurzor: v hale kurzor krúži a prechádza po objektoch; potom spomalený detail (pôvodne 25 pohybov/s)."""
from nahravac import *

NAZOV = ("Hardvérový kurzor", "Hardware cursor")

def nahraj(verzia):
    do_haly(PRED if verzia == "pred" else PO)
    with Zaznam(f"kurzor_{verzia}") as z:
        presun(400, 260, 0.5); time.sleep(0.4)
        z.znacka("kruh"); kruh(400, 260, 170, 5, 2.5); z.znacka("kruh_koniec")
        for x, y in [(225, 120), (130, 230), (330, 230), (420, 330), (600, 330), (700, 300), (560, 130), (400, 260)]:
            presun(x, y, 0.8); time.sleep(0.7)                                       # obraz, glóbus, východy, socha...
        z.znacka("koniec")

def zostav(s):
    a, b = s.Zaznam("kurzor_pred"), s.Zaznam("kurzor_po")
    # 1) celý pohyb vedľa seba
    l = s.vyrez(a, a.znacka("kruh") - 0.3, a.znacka("koniec"))
    p = s.vyrez(b, b.znacka("kruh") - 0.3, b.znacka("koniec"))
    k1 = s.vedla(l, p, NAZOV, popis="pôvodne 25 pohybov za sekundu, teraz pri každom pohybe myši  ·  originally 25 updates per second, now every mouse move")
    # 2) spomalený detail krúženia (štvrtinová rýchlosť), výrez okolo kruhu (stred hry 400,260 = obrazovka 960,468)
    orez = (960 - 400, 468 - 300, 800, 600)
    l2 = s.vyrez(a, a.znacka("kruh") + 1, a.znacka("kruh") + 2.5, rychlost=0.25, orez=orez, zvuk=False)
    p2 = s.vyrez(b, b.znacka("kruh") + 1, b.znacka("kruh") + 2.5, rychlost=0.25, orez=orez, zvuk=False)
    k2 = s.vedla(l2, p2, ("Spomalené 4×", "4× slow motion"))
    return s.za_sebou(k1, k2)
