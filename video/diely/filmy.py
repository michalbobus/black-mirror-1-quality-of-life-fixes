"""CGI filmy na celú šírku obrazovky (úvodný film novej hry)."""
from nahravac import *

NAZOV = ("Filmy na celú šírku", "Full-width cinematics")

def nahraj(verzia):
    spusti(profil(verzia))
    with Zaznam(f"filmy_{verzia}") as z:
        klik(400, 197); z.znacka("nova_hra")                  # Nová hra → úvodný film
        time.sleep(26); klaves(0x1B, log=False); time.sleep(1); z.znacka("koniec")

def zostav(s):
    a, b = s.Zaznam("filmy_pred"), s.Zaznam("filmy_po")
    l = s.vyrez(a, a.znacka("nova_hra") + 4, a.znacka("nova_hra") + 26)
    p = s.vyrez(b, b.znacka("nova_hra") + 4, b.znacka("nova_hra") + 26)
    return s.vedla(l, p, NAZOV, orez43=False, zvuk="p",
                   popis="širokouhlý film bez čiernych pásov po bokoch  ·  widescreen film without side bars")
