"""Vyhladzovanie hrán postáv (FXAA pred zväčšením) – zväčšený detail Samuela."""
from nahravac import *

NAZOV = ("Vyhladené hrany postáv", "Character anti-aliasing")

def nahraj(verzia):
    do_haly(profil(verzia))
    with Zaznam(f"vyhladzovanie_{verzia}") as z:
        presun(60, 560, 0.4); time.sleep(0.5)            # kurzor mimo postavy
        z.znacka("start"); time.sleep(5); z.znacka("koniec")

def zostav(s):
    a, b = s.Zaznam("vyhladzovanie_pred"), s.Zaznam("vyhladzovanie_po")
    orez = (1129, 500, 400, 300)                          # Samuel pri dverách (stred obrazovky 1329, 660)
    l = s.vyrez(a, a.znacka("start"), a.znacka("start") + 4.5, orez=orez)
    p = s.vyrez(b, b.znacka("start"), b.znacka("start") + 4.5, orez=orez)
    k1 = s.vedla(l, p, NAZOV, popis="zväčšený detail  ·  zoomed in")
    orez2 = (1229, 540, 200, 150)                          # hlava a ramená
    l2 = s.vyrez(a, a.znacka("start"), a.znacka("start") + 4.5, orez=orez2, zvuk=False)
    p2 = s.vyrez(b, b.znacka("start"), b.znacka("start") + 4.5, orez=orez2, zvuk=False)
    return s.za_sebou(k1, s.vedla(l2, p2, NAZOV, popis="ešte väčší detail  ·  closer zoom"))
