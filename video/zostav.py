"""Zostaví diely a trailer.
  python zostav.py DIEL [DIEL...]  – zostaví len tieto diely do vystup/diely/DIEL.mp4
  python zostav.py                 – zostaví všetky diely z PORADIE a spojí ich do vystup/trailer.mp4
Poradie dielov v traileri je v zozname PORADIE nižšie – diel sa dá vynechať alebo presunúť bez ďalších zmien."""
import sys, importlib, os, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skladac as s

PORADIE = ["uvod", "obraz", "filmy", "kurzor", "hotspoty", "dvojklik", "preskakovanie",
           "vyhladzovanie", "rychle_ulozenie", "koliesko", "zaver"]

def zostav_diel(meno):
    diel = importlib.import_module("diely." + meno)
    k = s.prelinanie(diel.zostav(s), 0.35, 0.35)
    os.makedirs(os.path.join(s.VYSTUP, "diely"), exist_ok=True)
    out = os.path.join(s.VYSTUP, "diely", meno + ".mp4"); shutil.copy(k.cesta, out)
    print(f"{meno}: {k.dlzka:.1f} s -> {out}"); return s.Klip(out, k.dlzka)

if __name__ == "__main__":
    if sys.argv[1:]:
        for m in sys.argv[1:]: zostav_diel(m)
    else:
        klipy = [zostav_diel(m) for m in PORADIE]
        t = s.za_sebou(*klipy); out = os.path.join(s.VYSTUP, "trailer.mp4")
        # vyrovnanie hlasitosti celého traileru na -16 LUFS (nezáleží na úrovni nahraného zvuku)
        s.ff("-i", t.cesta, "-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k",
             "-ar", "48000", "-movflags", "+faststart", out)
        print(f"trailer: {t.dlzka:.1f} s ({t.dlzka // 60:.0f}:{t.dlzka % 60:04.1f}) -> {out}")
