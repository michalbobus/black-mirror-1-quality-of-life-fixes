"""Rýchle uloženie Ctrl+S a načítanie Ctrl+L (pôvodne: kolieska → Uložit hru → pozícia → názov → Enter).
Pozície 8 (pôvodná hra) a 98 (rýchla) sa po nahrávaní vrátia do stavu pred ním."""
from nahravac import *

NAZOV = ("Rýchle uloženie a načítanie", "Quick save and quick load")

def nahraj(verzia):
    with OchranaPozicii(8, 98):
        do_haly(profil(verzia))
        with Zaznam(f"rychle_ulozenie_{verzia}") as z:
            presun(420, 380, 0.4); time.sleep(1); z.znacka("start")
            if verzia == "pred":
                presun(755, 8, 0.6); time.sleep(0.7); klik(755, 19); time.sleep(1.8)   # ozubené kolieska
                klik(400, 233); time.sleep(1.8); klik(322, 400); time.sleep(0.8)        # Uložit hru, pozícia 8
                for _ in range(13): klaves(0x08, 0.03, log=False); time.sleep(0.03)
                for c in "HALA": klaves(ord(c), 0.04, log=False); time.sleep(0.12)
                klaves(0x0D, meno="Enter"); time.sleep(2.8); z.znacka("ulozene")
                time.sleep(0.8); presun(300, 480, 0.4); klik(330, 500); time.sleep(0.6); klik(330, 500); time.sleep(4.5)   # Samuel odíde (prvý klik po ponuke hra ignoruje)
                presun(755, 8, 0.6); time.sleep(0.7); klik(755, 19); time.sleep(1.8)
                klik(400, 269); time.sleep(1.8); klik(322, 400); time.sleep(4); z.znacka("nacitane")   # Nahrát hru, pozícia 8
            else:
                kombinacia(0x11, 0x53, "Ctrl+S"); time.sleep(2.2); z.znacka("ulozene")
                time.sleep(0.8); presun(300, 480, 0.4); klik(330, 500); time.sleep(0.6); klik(330, 500); time.sleep(4.5)   # Samuel odíde (prvý klik po ponuke hra ignoruje)
                kombinacia(0x11, 0x4C, "Ctrl+L"); time.sleep(4); z.znacka("nacitane")
            time.sleep(1); z.znacka("koniec")

def zostav(s):
    a, b = s.Zaznam("rychle_ulozenie_pred"), s.Zaznam("rychle_ulozenie_po")
    la, lb = a.znacka("start") - 0.5, b.znacka("start") - 0.5
    l = s.vyrez(a, la, a.znacka("koniec"))
    p = s.vyrez(b, lb, b.znacka("koniec"))
    odz = [(e["meno_k"], e["t"] - lb, e["t"] - lb + 1.5, 1) for e in b.udalosti("klaves") if e.get("meno_k")]
    odz += [("Enter", e["t"] - la, e["t"] - la + 1, 0) for e in a.udalosti("klaves", meno_k="Enter")]
    return s.vedla(l, p, NAZOV, odznaky=odz,
                   popis="pôvodne len cez ponuku a pozíciu s názvom  ·  originally only through the menu and a named slot")
