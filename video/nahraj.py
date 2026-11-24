"""Nahrá diel traileru: python nahraj.py DIEL [pred|po]  (bez verzie = obe).
Diel = súbor diely/DIEL.py s funkciou nahraj(verzia). Záznamy: zaznamy/DIEL_pred.* a DIEL_po.*
Počas nahrávania nehýbať myšou ani neprepínať okná (hra musí byť v popredí)."""
import sys, importlib, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nahravac
diel = importlib.import_module("diely." + sys.argv[1])
verzie = sys.argv[2:] or ["pred", "po"]
try:
    for v in verzie:
        if v in getattr(diel, "VERZIE", ("pred", "po")): diel.nahraj(v)
finally:
    nahravac.koniec()
