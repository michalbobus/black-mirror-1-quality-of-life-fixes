"""Dvojklik: Samuel je hneď v cieli (pôvodne len pomalá chôdza)."""
from nahravac import *

NAZOV = ("Dvojklik = rýchly presun", "Double-click = instant move")
CIEL = (330, 500)
VYCHOD = (430, 320)                                  # oblúk – východ do jedálne

def nahraj(verzia):
    do_haly(profil(verzia))
    with Zaznam(f"dvojklik_{verzia}") as z:
        presun(450, 420, 0.4); time.sleep(1)
        presun(*CIEL, 0.5); time.sleep(0.2)
        z.znacka("klik")
        if verzia == "pred": klik()
        else: dvojklik(*CIEL, 0.01)
        time.sleep(7); z.znacka("koniec")
        presun(*VYCHOD, 0.6); time.sleep(0.4); z.znacka("klik2")
        if verzia == "pred": klik()
        else: dvojklik(*VYCHOD, 0.01)
        time.sleep(8); z.znacka("koniec2")

def zostav(s):
    a, b = s.Zaznam("dvojklik_pred"), s.Zaznam("dvojklik_po")
    l = s.vyrez(a, a.znacka("klik") - 1.2, a.znacka("koniec"))
    p = s.vyrez(b, b.znacka("klik") - 1.2, b.znacka("klik") + 3.5)
    odz = [("Klik", 1.2, 2.4, 0, "Click"), ("Dvojklik", 1.2, 2.4, 1, "Double-click")]
    k1 = s.vedla(l, p, NAZOV, odznaky=odz, zvuk="l", popis="Samuel hneď v cieli  ·  Samuel is there at once")
    l2 = s.vyrez(a, a.znacka("klik2") - 1, a.znacka("koniec2"))
    p2 = s.vyrez(b, b.znacka("klik2") - 1, b.znacka("koniec2"))
    odz2 = [("Klik", 1, 2.2, 0, "Click"), ("Dvojklik", 1, 2.2, 1, "Double-click")]
    k2 = s.vedla(l2, p2, NAZOV, odznaky=odz2, zvuk="p", popis="aj k východu do ďalšej miestnosti  ·  also to an exit into the next room")
    return s.za_sebou(k1, k2)
