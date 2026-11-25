"""Medzerník ukáže aktívne miesta scény (pôvodná hra: medzerník nerobí nič).
Dve scény: hala (save.1) a záhrada (save.3 – pozícia sa len načíta, neukladá sa)."""
from nahravac import *

NAZOV = ("Medzerník ukáže aktívne miesta", "Space shows hotspots")
SCENY = [("hala", 1, [(515, 300)]), ("zahrada", 3, [(250, 300), (600, 350)])]   # (meno, pozícia, kam s kurzorom)

def nahraj(verzia):
    for meno, slot, body in SCENY:
        spusti(profil(verzia)); nahraj_poziciu(slot); presun(400, 300, 0.3); time.sleep(1)
        with Zaznam(f"hotspoty_{meno}_{verzia}" if meno != "hala" else f"hotspoty_{verzia}") as z:
            presun(420, 330, 0.4); time.sleep(1.2)
            z.znacka("drz"); drz(0x20, "Medzerník"); time.sleep(1.2)
            for x, y in body: presun(x, y, 0.8); time.sleep(1.5)             # kurzor nad východom – červený
            pusti(0x20); z.znacka("pusti"); time.sleep(1.5); z.znacka("koniec")

def _cast(s, meno):
    a = s.Zaznam(f"hotspoty_{meno}_pred" if meno != "hala" else "hotspoty_pred")
    b = s.Zaznam(f"hotspoty_{meno}_po" if meno != "hala" else "hotspoty_po")
    l = s.vyrez(a, a.znacka("drz") - 1, a.znacka("koniec"))
    p = s.vyrez(b, b.znacka("drz") - 1, b.znacka("koniec"))
    odz = [("Medzerník", 1, 1 + a.znacka("pusti") - a.znacka("drz"), 0, "Space"),
           ("Medzerník", 1, 1 + b.znacka("pusti") - b.znacka("drz"), 1, "Space")]
    return s.vedla(l, p, NAZOV, odznaky=odz,
                   popis="východy ikonou dverí, ostatné miesta krúžkom  ·  exits marked with a door icon, other spots with a ring")

def zostav(s):
    return s.za_sebou(*[_cast(s, m) for m, _, _ in SCENY])
