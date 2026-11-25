"""Benchmark doplnkov na viacerých scénach (pozície v benchmark/pozicie/).

  python benchmark.py                 – všetky scény zo zoznamu SCENY
  python benchmark.py podkrovie hala  – len vybrané scény
  python benchmark.py --profil smooth – iný režim kurzora (hardware | smooth | original)

Pozícia sa nahrá cez rýchle načítanie: súbor z pozicie/ sa skopíruje do save.98 hry a v hlavnej ponuke sa stlačí
Ctrl+L. Pozícia 98 (save.98 aj jej meno v savnames.txt) sa po behu vráti – pozície používateľa sa nemenia.
Kľúče config.ini, ktoré benchmark mení, sa po behu vrátia (rovnako ako pri nahrávaní videa).

Pre každú scénu:
  1. zarovnanie – kurzor na mriežku bodov vrátane okrajov 0 a 799: poloha myši v hre (0x506ff0 − posun scény) sa musí
     rovnať zadanému bodu a okno hardvérového kurzora musí byť tam, kde by kurzor nakreslila hra
     (animácia kurzora − posun scény, prepočítané na obrazovku) – odchýlka najviac 2 px obrazovky,
  2. posun scény – v širokej scéne klik na opačnú stranu (postava ide, scéna sa posunie) a znova zarovnanie,
  3. značky medzerníka – podržaný medzerník: počet značiek, všetky musia byť v hernej ploche, snímka obrazovky,
  4. plynulosť – krúženie myšou 3 s: kroky logiky/s, zobrazenia/s, presuny okna kurzora/s.
Výsledok: benchmark/vysledky/RRRR-MM-DD_HHMM/ (vysledok.json, vysledok.txt, snímky *.png)."""
import sys, os, time, json, struct, shutil, math, ctypes, ctypes.wintypes as W, datetime, threading

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(KOREN, "video"), os.path.join(KOREN, "nastroje")]
from nahravac import *          # spusti, popredie, presun, klik, drz, pusti, OchranaPozicii, PO, nastav, koniec, HRA
import pamat
from ladenie import Kanal

POZICIE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pozicie")
SLOT = 98

# (meno, súbor v pozicie/, popis) – nová scéna = pridať riadok a súbor pozície
SCENY = [
    ("hala",      "hala.save",       "hala zámku (save.1 pôvodnej hry), úzka scéna, 5 východov"),
    ("podkrovie", "puda_hrad.save",  "podkrovie hradu 10c8 – scéna širšia ako obraz (posun 600 px), chyba kurzora 25. 11. 2026"),
    ("zahrada",   "zahrada.save",    "záhrada 10ab (save.3 používateľa z 24. 11. 2026, scéna dielu hotspoty vo videu)"),
]

def i32(h, a): return struct.unpack("<i", pamat.citaj(h, a, 4))[0]
def u32(h, a): return struct.unpack("<I", pamat.citaj(h, a, 4))[0]

def stav_hry(h):
    s = u32(h, 0x49eb1c)
    meno = pamat.citaj(h, s, 16).split(b"\0")[0].decode(errors="replace")
    sx, sy = i32(h, s + 0x5d5), i32(h, s + 0x5d9)
    kurzor, znacky = None, []
    prvy = u32(h, s + 0x80 + 0x28); a = prvy
    for _ in range(5000):
        if not a: break
        d = pamat.citaj(h, a, 0x60)
        z = struct.unpack_from("<i", d, 0xc)[0]; x, y = struct.unpack_from("<2i", d, 0x1c)
        if z == -10: kurzor = (x, y)
        if d[0x41:0x60].split(b"\0")[0] == b"bmqol_hotspot": znacky.append((x - sx, y - sy))
        a = u32(h, a)
        if a == prvy: break
    return dict(scena=meno, posun=(sx, sy), mys=(i32(h, 0x506ff0), i32(h, 0x506fa8)), kurzor=kurzor, znacky=znacky,
                postava=(i32(h, 0x49be28) - sx, i32(h, 0x49be2c) - sy), stav_postavy=pamat.citaj(h, 0x49be3a, 1)[0])

def obraz_hry():
    """Ľavý horný roh a mierka obrazu 800×600 na obrazovke (ako vlákno kurzora v doplnku)."""
    g = okno(); rc = W.RECT(); u.GetClientRect(g, ctypes.byref(rc))
    o = W.POINT(0, 0); u.ClientToScreen(g, ctypes.byref(o))
    m = min(rc.right / 800, rc.bottom / 600)
    return o.x + (rc.right - 800 * m) / 2, o.y + (rc.bottom - 600 * m) / 2, m

def okno_kurzora():
    k = u.FindWindowW("bmqol_kurzor", None)
    if not k or not u.IsWindowVisible(k): return None
    r = W.RECT(); u.GetWindowRect(k, ctypes.byref(r)); return r.left, r.top

def zarovnanie(h, body, rezim):
    ox, oy, m = obraz_hry(); vysl = []
    for x, y in body:
        presun(x, y, 0.25); time.sleep(0.35)
        st = stav_hry(h); sx, sy = st["posun"]
        gx, gy = st["mys"][0] - sx, st["mys"][1] - sy
        r = dict(bod=(x, y), mys_v_hre=(gx, gy), posun=(sx, sy), ok_mys=(gx, gy) == (x, y))
        if rezim == "hardware" and st["kurzor"]:
            ok = okno_kurzora()
            ocak = (ox + (st["kurzor"][0] - sx) * m, oy + (st["kurzor"][1] - sy) * m)
            r["okno"] = ok; r["okno_ocak"] = (round(ocak[0]), round(ocak[1]))
            r["ok_okno"] = ok is not None and abs(ok[0] - ocak[0]) <= 2 and abs(ok[1] - ocak[1]) <= 2
        vysl.append(r)
    return vysl

def plynulost(h, kanal, trvanie=3.0):
    k = u.FindWindowW("bmqol_kurzor", None); presuny = [0]; koniec_ = threading.Event()
    def sleduj():
        posl = None
        while not koniec_.is_set():
            p = okno_kurzora()
            if p != posl: presuny[0] += 1; posl = p
            time.sleep(0.0005)
    t = threading.Thread(target=sleduj, daemon=True); t.start()
    a = kanal.udalosti(); z = time.perf_counter()
    while (f := time.perf_counter() - z) < trvanie:
        u.SetCursorPos(round(400 + 200 * math.cos(f * 4)), round(300 + 150 * math.sin(f * 4))); time.sleep(0.002)
    b = kanal.udalosti(); dt = time.perf_counter() - z; koniec_.set(); t.join()
    return dict(kroky_s=round((b[0] - a[0]) / dt, 1), zobrazenia_s=round((b[3] - a[3]) / dt, 1),
                presuny_okna_s=round(presuny[0] / dt, 1) if k else None)

def snimka(cesta):
    from PIL import ImageGrab
    ImageGrab.grab(all_screens=True).save(cesta)

def nahraj(subor):
    """save z pozicie/ → save.98, Ctrl+L v hlavnej ponuke, čakanie na hernú scénu."""
    shutil.copy(os.path.join(POZICIE, subor), os.path.join(HRA, f"save.{SLOT}"))
    popredie(); kombinacia(0x11, ord("L"), "Ctrl+L"); time.sleep(5)

def scena(meno, subor, popis, rezim, h, kanal, adr):
    print(f"--- {meno}: {popis}")
    nahraj(subor); presun(400, 300, 0.3); time.sleep(1)
    st = stav_hry(h); v = dict(meno=meno, popis=popis, scena=st["scena"], posun_start=st["posun"])
    snimka(os.path.join(adr, f"{meno}_1_start.png"))
    mriezka = [(x, y) for y in (60, 300, 540) for x in (0, 200, 400, 600, 799)] + [(400, 0), (400, 599)]
    v["zarovnanie"] = zarovnanie(h, mriezka, rezim)
    # posun scény: klik na opačnú stranu obrazu vo výške postavy (v úzkej scéne sa posun nezmení)
    px, py = stav_hry(h)["postava"]; cx = 60 if px > 400 else 740; cy = max(150, min(520, py - 10))
    klik(cx, cy); time.sleep(0.3)
    for _ in range(60):
        if stav_hry(h)["stav_postavy"] == 0: break
        time.sleep(0.2)
    time.sleep(0.8); st2 = stav_hry(h)
    v["posun_po_chodzi"] = st2["posun"]; v["scena_po_chodzi"] = st2["scena"]
    if st2["scena"] == st["scena"]:
        v["zarovnanie_po_posune"] = zarovnanie(h, [(0, 300), (400, 300), (799, 300), (799, 540)], rezim)
    snimka(os.path.join(adr, f"{meno}_2_po_chodzi.png"))
    # značky medzerníka
    presun(400, 300, 0.3); drz(0x20, "Medzerník"); time.sleep(1.0)
    st3 = stav_hry(h); snimka(os.path.join(adr, f"{meno}_3_znacky.png")); pusti(0x20)
    v["znacky"] = st3["znacky"]
    v["ok_znacky"] = all(-30 <= x <= 800 and -30 <= y <= 600 for x, y in st3["znacky"])
    time.sleep(2.5)
    v["plynulost"] = plynulost(h, kanal)
    zar = v["zarovnanie"] + v.get("zarovnanie_po_posune", [])
    v["ok_mys"] = all(r["ok_mys"] for r in zar)
    v["ok_okno"] = all(r.get("ok_okno", True) for r in zar)
    return v

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    arg = sys.argv[1:]; rezim = "hardware"
    if "--profil" in arg: i = arg.index("--profil"); rezim = arg[i + 1]; del arg[i:i + 2]
    vybrane = [s for s in SCENY if not arg or s[0] in arg]
    adr = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vysledky",
                       datetime.datetime.now().strftime("%Y-%m-%d_%H%M") + ("" if rezim == "hardware" else "_" + rezim))
    os.makedirs(adr, exist_ok=True)
    profil_ = dict(PO); profil_[("Cursor", "Mode")] = rezim
    vysledky = []
    try:
        with OchranaPozicii(SLOT):
            spusti(profil_)
            h = pamat.otvor(pamat.pid_hry()); kanal = Kanal()
            for meno, subor, popis in vybrane:
                try: vysledky.append(scena(meno, subor, popis, rezim, h, kanal, adr))
                except Exception as e: vysledky.append(dict(meno=meno, chyba=repr(e))); print("CHYBA", e)
    finally:
        koniec()
    json.dump(dict(rezim=rezim, cas=datetime.datetime.now().isoformat(timespec="seconds"), sceny=vysledky),
              open(os.path.join(adr, "vysledok.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    riadky = [f"Benchmark {datetime.date.today()} – kurzor {rezim}", ""]
    for v in vysledky:
        if "chyba" in v: riadky.append(f"{v['meno']}: CHYBA {v['chyba']}"); continue
        zle = [r for r in v["zarovnanie"] + v.get("zarovnanie_po_posune", []) if not (r["ok_mys"] and r.get("ok_okno", True))]
        p = v["plynulost"]
        riadky.append(f"{v['meno']} ({v['scena']}): posun {v['posun_start'][0]} → {v['posun_po_chodzi'][0]}  "
                      f"myš {'OK' if v['ok_mys'] else 'ZLE'}  okno kurzora {'OK' if v['ok_okno'] else 'ZLE'}  "
                      f"značky {len(v['znacky'])} {'OK' if v['ok_znacky'] else 'ZLE'}  "
                      f"kroky {p['kroky_s']}/s  zobrazenia {p['zobrazenia_s']}/s  okno {p['presuny_okna_s']}/s")
        for r in zle: riadky.append(f"    bod {r['bod']}: myš v hre {r['mys_v_hre']}, okno {r.get('okno')} (čakané {r.get('okno_ocak')})")
    open(os.path.join(adr, "vysledok.txt"), "w", encoding="utf-8").write("\n".join(riadky) + "\n")
    print("\n".join(riadky)); print("výsledky:", adr)

if __name__ == "__main__":
    main()
