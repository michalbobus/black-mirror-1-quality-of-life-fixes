"""Koliesko myši listuje predmetmi inventára (pôvodne: lišta dole, klik, pravým späť)."""
from nahravac import *

NAZOV = ("Koliesko myši = predmety inventára", "Mouse wheel cycles inventory items")
DOKUMENT, KLUC = (107, 572), (173, 572)

def nahraj(verzia):
    do_haly(profil(verzia))
    with Zaznam(f"koliesko_{verzia}") as z:
        presun(420, 380, 0.4); time.sleep(1); z.znacka("start")
        if verzia == "pred":
            for predmet in (DOKUMENT, KLUC):
                presun(400, 597, 0.5); time.sleep(1.0); klik(*predmet, trvanie=0.5); time.sleep(0.4)
                presun(420, 380, 0.5); time.sleep(1.0); klik(prave=True); time.sleep(0.5)
        else:
            for d in (-120, -120, -120, 120):
                koliesko(d); time.sleep(1.4)
            klik(prave=True); time.sleep(0.5)
        time.sleep(0.8); z.znacka("koniec")

def zostav(s):
    a, b = s.Zaznam("koliesko_pred"), s.Zaznam("koliesko_po")
    l = s.vyrez(a, a.znacka("start") - 0.5, a.znacka("koniec"))
    p = s.vyrez(b, b.znacka("start") - 0.5, b.znacka("koniec"))
    t0 = b.znacka("start") - 0.5
    odz = [("Koliesko", e["t"] - t0, e["t"] - t0 + 0.9, 1, "Wheel") for e in b.udalosti("koliesko")]
    return s.vedla(l, p, NAZOV, odznaky=odz,
                   popis="predmet hneď na kurzore, bez lišty inventára  ·  item straight on the cursor, no inventory bar")
