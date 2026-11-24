"""Úvodná karta traileru (pozadie: rozmazaná hala zo záznamu dielu hotspoty, ak existuje)."""
import os
VERZIE = ()

def zostav(s):
    poz = None
    if os.path.exists(os.path.join(s.ZAZNAMY, "hotspoty_po.json")):
        z = s.Zaznam("hotspoty_po"); poz = s.snimka(z, z.start + 0.5)
    return s.karta([("Black Mirror", "nadpis"), ("Quality of Life Fixes", "podnadpis"), ("", "medzera"),
                    ("pôvodná hra a hra s úpravami", "text"), ("original game vs. with fixes", "en")], 5, pozadie=poz)
