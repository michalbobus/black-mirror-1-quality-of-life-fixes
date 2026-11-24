"""ESC preskakuje rozhovory a animácie postáv až po ďalšiu repliku – podržaný, kým hráč nedostane kontrolu.
Úvod novej hry: rozprávač (scéna 123f) a rozhovor v salóne. Pôvodná hra: všetko sa prehrá."""
import sys, os, struct
from nahravac import *
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "nastroje"))
import pamat

NAZOV = ("ESC preskočí rozhovory aj animácie", "ESC skips dialogues and animations")

def _stav(h):
    p = struct.unpack("<I", pamat.citaj(h, 0x49eb1c, 4))[0]
    scena = pamat.citaj(h, p, 32).split(b"\0")[0].decode(errors="replace") if p else ""
    a = struct.unpack("<i", pamat.citaj(h, 0x48b658, 4))[0]; b = struct.unpack("<i", pamat.citaj(h, 0x48b678, 4))[0]
    return scena, a == 1 and b == 1

def nahraj(verzia):
    spusti(profil(verzia)); h = pamat.otvor(pamat.pid_hry())
    klik(400, 197); time.sleep(3)
    posl = 0; z0 = time.time()
    while _stav(h)[0] != "123f" and time.time() - z0 < 90:        # preskoč úvodný film
        if time.time() - posl > 5: klaves(0x1B, log=False); posl = time.time()
        time.sleep(0.05)
    with Zaznam(f"preskakovanie_{verzia}") as z:
        presun(400, 300, 0.2)
        z.znacka("rozpravac")
        if verzia == "po": drz(0x1B, "ESC")
        z0 = time.time()
        while _stav(h)[0] == "123f" and time.time() - z0 < 400: time.sleep(0.03)    # rozprávač
        z.znacka("salon")
        while not _stav(h)[1] and time.time() - z0 < 400: time.sleep(0.03)          # rozhovor v salóne
        if verzia == "po": pusti(0x1B)
        z.znacka("kontrola")
        time.sleep(2); klik(330, 500); time.sleep(4)
        if verzia == "po": klik(600, 470); time.sleep(4); klik(250, 520); time.sleep(3)
        z.znacka("koniec")

def zostav(s):
    a, b = s.Zaznam("preskakovanie_pred"), s.Zaznam("preskakovanie_po")
    da = a.znacka("kontrola") - a.znacka("rozpravac"); db = b.znacka("kontrola") - b.znacka("rozpravac")
    # 1) obe naraz, kým hra s úpravami nedá hráčovi kontrolu (+ chôdza)
    d1 = b.znacka("koniec") - b.znacka("rozpravac") + 0.5
    l1 = s.vyrez(a, a.znacka("rozpravac") - 0.5, a.znacka("rozpravac") + d1 - 0.5)
    p1 = s.vyrez(b, b.znacka("rozpravac") - 0.5, b.znacka("koniec"))
    odz = [("ESC", 0.5, 0.5 + db, 1, "podržaný · held")]
    cas = [(0, 0.5, 9999, 1), (1, 0.5, 0.5 + db, 1)]
    k1 = s.vedla(l1, p1, NAZOV, odznaky=odz, casovace=cas, zvuk="mix")
    # 2) pôvodná hra zrýchlene do konca, hra s úpravami stojí
    r = 12
    l2 = s.vyrez(a, a.znacka("rozpravac") + d1 - 0.5, a.znacka("kontrola") + 1, rychlost=r, zvuk=False)
    p2 = s.vyrez(b, b.znacka("koniec") - 0.05, b.znacka("koniec"), zvuk=False)
    cas2 = [(0, 0, l2.dlzka - 1 / r, r, d1 - 1.0), (1, 0, 0, 1, db)]
    k2 = s.vedla(l2, p2, NAZOV, casovace=cas2, zvuk="l",
                 popis=f"úvod novej hry: {da // 60:.0f}:{da % 60:02.0f} → {db // 60:.0f}:{db % 60:02.0f}   ·   zrýchlené {r}×  ·  sped up {r}×")
    return s.za_sebou(k1, s.zastav(k2, 1.5))
