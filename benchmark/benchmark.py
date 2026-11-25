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
     (animácia kurzora − posun scény, prepočítané na obrazovku) – odchýlka najviac 2 px obrazovky; kurzor hry
     (animácia −10 − posun scény) musí byť pri bode (do 32 px) – kontroluje aj režimy smooth a original,
  0. kolieska ponuky – načítanie s myšou pri hornom okraji: kolieska musia byť vpravo hore (730, 2), aj po
     príchode myši k pravému hornému rohu; snímky horného pásu,
  5. značky + ESC – kombinácie načítania (Ctrl+L, ponuka), koliesok a medzerníka s ESC: hra nesmie spadnúť
     (pád v záhrade 24. 11. 2026), pozri znacky_a_esc,
  6. načítanie cez ponuku – ESC → Nahrát hru → pozícia 8: kolieska vpravo hore od prvej vzorky (každých 0,12 s),
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
SLOT_PONUKA = 8          # pozícia na prvej strane obrazovky Nahrát hru – načítanie cez ponuku
MENO_PONUKA = b"benchmark"

def hra_bezi():
    import subprocess
    return b"agds.exe" in subprocess.run("tasklist /fi \"imagename eq agds.exe\" /nh", shell=True, capture_output=True).stdout

def nahraj_cez_ponuku(h, subor, adr, meno):
    """ESC → Nahrát hru → pozícia 8 (súbor z pozicie/ skopírovaný do save.8). Kolieska z pozície uloženej cez ponuku
    sa obnovia ešte pri posune 0 – doplnok ich musí hneď presunúť vpravo hore (chyba 25. 11. 2026: ~1 s vľavo)."""
    shutil.copy(os.path.join(POZICIE, subor), os.path.join(HRA, f"save.{SLOT_PONUKA}"))
    presun(400, 300, 0.3); popredie(); klaves(0x1B); time.sleep(2.5)
    klik(400, 269); time.sleep(2.5); klik(322, 189 + round((SLOT_PONUKA - 1) * 30.2))
    vzorky = []; t = time.time()
    while time.time() - t < 3.5:
        time.sleep(0.12)
        try: st = stav_hry(h); k = kolieska(h)
        except Exception: continue
        if not st["scena"].startswith("1006"): vzorky.append((round(time.time() - t, 2), st["scena"], k))
    from PIL import ImageGrab
    ImageGrab.grab(all_screens=True).save(os.path.join(adr, f"{meno}_4_nacitanie_cez_ponuku.png"))
    return vzorky

def znacky_esc(h):
    """Podržaný medzerník (značky), hneď ESC (ponuka uvoľní scénu so značkami), ESC späť."""
    presun(400, 300, 0.2); drz(0x20, "Medzerník"); time.sleep(0.4); pusti(0x20)
    klaves(0x1B); time.sleep(2.5)
    if not hra_bezi(): return False
    klaves(0x1B); time.sleep(2.0)
    return hra_bezi()

def znacky_a_esc(h, subor):
    """Pád z 24. 11. 2026 (záhrada): kombinácia načítania, koliesok (uložených v pozícii) a medzerníka – pri uvoľnení
    scény hra uvoľnila aj pixely značiek doplnku. Kombinácie (po každej sa kontroluje, že hra beží):
      a) 3× medzerník + ESC + ESC v scéne,
      b) Ctrl+L a hneď medzerník + ESC (kolieska z pozície sú ešte v scéne),
      c) Ctrl+L počas značiek (načítanie uvoľní scénu so značkami),
      d) ESC → Nahrát hru → pozícia 8 a hneď medzerník + ESC."""
    scena0 = stav_hry(h)["scena"]; vysl = {}
    def skus(meno, fn):
        try: ok = fn()
        except Exception as e: ok = False; vysl[meno + "_chyba"] = repr(e)
        vysl[meno] = bool(ok) and hra_bezi(); return vysl[meno]
    shutil.copy(os.path.join(POZICIE, subor), os.path.join(HRA, f"save.{SLOT}"))
    shutil.copy(os.path.join(POZICIE, subor), os.path.join(HRA, f"save.{SLOT_PONUKA}"))
    if not skus("a_esc_3x", lambda: all(znacky_esc(h) for _ in range(3))): return dict(ok=False, **vysl)
    def b():
        popredie(); kombinacia(0x11, ord("L"), "Ctrl+L"); time.sleep(0.6); return znacky_esc(h)
    if not skus("b_ctrl_l_znacky_esc", b): return dict(ok=False, **vysl)
    def c():
        presun(400, 300, 0.2); drz(0x20, "Medzerník"); time.sleep(0.4)
        kombinacia(0x11, ord("L"), "Ctrl+L"); time.sleep(0.3); pusti(0x20); time.sleep(3); return hra_bezi()
    if not skus("c_ctrl_l_pocas_znaciek", c): return dict(ok=False, **vysl)
    def d():
        popredie(); klaves(0x1B); time.sleep(2.5)
        klik(400, 269); time.sleep(2.5); klik(322, 189 + round((SLOT_PONUKA - 1) * 30.2)); time.sleep(0.8)
        return znacky_esc(h)
    if not skus("d_ponuka_znacky_esc", d): return dict(ok=False, **vysl)
    for _ in range(3):                           # po načítaní cez ponuku môže ostať hlavná ponuka – späť do hry
        if not stav_hry(h)["scena"].startswith("1006"): break
        popredie(); klaves(0x1B); time.sleep(2.5)
    sc = stav_hry(h)["scena"]
    return dict(ok=sc == scena0 and all(v for k, v in vysl.items() if not k.endswith("_chyba")), scena=sc, **vysl)

# (meno, súbor v pozicie/, popis) – nová scéna = pridať riadok a súbor pozície
SCENY = [
    ("hala",       "hala.save",         "hala zámku (save.1 pôvodnej hry), úzka scéna, 5 východov"),
    ("podkrovie",  "puda_hrad.save",    "podkrovie hradu 10c8 – scéna širšia ako obraz (posun 600 px), chyba kurzora 25. 11. 2026"),
    ("podkrovie2", "puda_hrad_2.save",  "podkrovie 10c8 uložené cez ponuku (pozícia 4 používateľa) – kolieska vľavo pri načítaní cez ponuku"),
    ("zahrada",    "zahrada.save",      "záhrada 10ab s kolieskami uloženými v pozícii (save.3) – pád pri medzerníku + ESC 24. 11. 2026, diel hotspoty vo videu"),
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
        opakovane = False
        if (st["mys"][0] - sx, st["mys"][1] - sy) != (x, y):   # hra polohu ešte neprevzala (napr. dosúvanie scény) – raz znova
            time.sleep(0.6); st = stav_hry(h); sx, sy = st["posun"]; opakovane = True
        gx, gy = st["mys"][0] - sx, st["mys"][1] - sy
        r = dict(bod=(x, y), mys_v_hre=(gx, gy), posun=(sx, sy), ok_mys=(gx, gy) == (x, y))
        if opakovane: r["opakovane"] = True
        if st["kurzor"]:   # kurzor hry (animácia −10) na obrazovke: pri bode, posun obrázka voči myši najviac 32 px
            kx, ky = st["kurzor"][0] - sx, st["kurzor"][1] - sy
            r["kurzor_hry"] = (kx, ky); r["ok_kurzor_hry"] = abs(kx - x) <= 32 and abs(ky - y) <= 32
        if rezim == "hardware" and st["kurzor"]:
            ok = okno_kurzora()
            ocak = (ox + (st["kurzor"][0] - sx) * m, oy + (st["kurzor"][1] - sy) * m)
            r["okno"] = ok; r["okno_ocak"] = (round(ocak[0]), round(ocak[1]))
            r["ok_okno"] = ok is not None and abs(ok[0] - ocak[0]) <= 2 and abs(ok[1] - ocak[1]) <= 2
        vysl.append(r)
    return vysl

KOLIESKA = (730, 2)     # kolieska ponuky (objekt 1006.100c) na obrazovke vpravo hore
def kolieska(h):
    """Poloha koliesok na obrazovke (postava objektu +0x82: +0x37e/+0x382 v súradniciach scény) alebo None."""
    s = u32(h, 0x49eb1c); sx, sy = i32(h, s + 0x5d5), i32(h, s + 0x5d9)
    prvy = u32(h, s + 0x40 + 0x28); o = prvy; obj = 0
    for _ in range(3000):
        if not o: break
        if pamat.citaj(h, o + 8, 32).split(bytes(1))[0] == b"1006.100c": obj = o; break
        o = u32(h, o)
        if o == prvy: break
    if not obj: return None
    p = u32(h, obj + 0x82)          # postava objektu: poloha +0x37e/+0x382 v súradniciach scény
    return (i32(h, p + 0x37e) - sx, i32(h, p + 0x382) - sy) if p else None

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
    """save z pozicie/ → save.98, Ctrl+L (prvá scéna z hlavnej ponuky, ďalšie z predchádzajúcej scény), čakanie na
    scénu. Myš je pri načítaní zámerne pri hornom okraji: hra vtedy vytvorí kolieska ponuky ešte pred posunom scény
    (chyba 25. 11. 2026 – v podkroví boli kolieska vľavo)."""
    shutil.copy(os.path.join(POZICIE, subor), os.path.join(HRA, f"save.{SLOT}"))
    presun(400, 8, 0.3); time.sleep(0.3)
    popredie(); kombinacia(0x11, ord("L"), "Ctrl+L"); time.sleep(5)

def scena(meno, subor, popis, rezim, h, kanal, adr):
    print(f"--- {meno}: {popis}")
    nahraj(subor)
    st = stav_hry(h); v = dict(meno=meno, popis=popis, scena=st["scena"], posun_start=st["posun"])
    # kolieska ponuky po načítaní s myšou hore, potom aj po príchode myši k pravému hornému rohu
    v["kolieska_po_nacitani"] = kolieska(h)
    from PIL import ImageGrab
    ox, oy, m = obraz_hry()
    pas = (round(ox), round(oy), round(ox + 800 * m), round(oy + 70 * m))
    ImageGrab.grab(bbox=pas).save(os.path.join(adr, f"{meno}_0_kolieska_po_nacitani.png"))
    presun(400, 300, 0.3); time.sleep(1.5); presun(760, 10, 0.4); time.sleep(1.5)
    v["kolieska_vpravo_hore"] = kolieska(h)
    ImageGrab.grab(bbox=pas).save(os.path.join(adr, f"{meno}_0_kolieska_vpravo_hore.png"))
    v["ok_kolieska"] = all(k is None or tuple(k) == KOLIESKA for k in (v["kolieska_po_nacitani"], v["kolieska_vpravo_hore"]))
    presun(400, 300, 0.3); time.sleep(1.5)
    snimka(os.path.join(adr, f"{meno}_1_start.png"))
    mriezka = [(x, y) for y in (60, 300, 540) for x in (0, 200, 400, 600, 799)] + [(400, 0), (400, 599)]
    v["zarovnanie"] = zarovnanie(h, mriezka, rezim)
    # posun scény: klik na opačnú stranu obrazu vo výške postavy (v úzkej scéne sa posun nezmení)
    px, py = stav_hry(h)["postava"]; cx = 60 if px > 400 else 740; cy = max(150, min(520, py - 10))
    klik(cx, cy); time.sleep(0.3)
    for _ in range(60):
        if stav_hry(h)["stav_postavy"] == 0: break
        time.sleep(0.2)
    time.sleep(0.8)
    for _ in range(20):                          # posun scény sa po chôdzi ešte dosúva
        p1 = stav_hry(h)["posun"]; time.sleep(0.3)
        if stav_hry(h)["posun"] == p1: break
    st2 = stav_hry(h)
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
    v["znacky_esc"] = znacky_a_esc(h, subor)
    if hra_bezi():
        v["nacitanie_cez_ponuku"] = nahraj_cez_ponuku(h, subor, adr, meno)
        v["ok_kolieska"] = v["ok_kolieska"] and all(k is None or tuple(k) == KOLIESKA for _, _, k in v["nacitanie_cez_ponuku"])
    zar = v["zarovnanie"] + v.get("zarovnanie_po_posune", [])
    v["ok_mys"] = all(r["ok_mys"] for r in zar)
    v["ok_okno"] = all(r.get("ok_okno", True) for r in zar)
    v["ok_kurzor_hry"] = all(r.get("ok_kurzor_hry", True) for r in zar)
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
        with OchranaPozicii(SLOT, SLOT_PONUKA):
            mena = os.path.join(HRA, "savnames.txt"); d = bytearray(open(mena, "rb").read())
            d[SLOT_PONUKA * 51:(SLOT_PONUKA + 1) * 51] = MENO_PONUKA + bytes(51 - len(MENO_PONUKA)); open(mena, "wb").write(d)
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
        zle = [r for r in v["zarovnanie"] + v.get("zarovnanie_po_posune", []) if not (r["ok_mys"] and r.get("ok_okno", True) and r.get("ok_kurzor_hry", True))]
        p = v["plynulost"]
        riadky.append(f"{v['meno']} ({v['scena']}): posun {v['posun_start'][0]} → {v['posun_po_chodzi'][0]}  "
                      f"myš {'OK' if v['ok_mys'] else 'ZLE'}  kurzor hry {'OK' if v['ok_kurzor_hry'] else 'ZLE'}  "
                      f"okno kurzora {('OK' if v['ok_okno'] else 'ZLE') if rezim == 'hardware' else '–'}  "
                      f"kolieska {'OK' if v['ok_kolieska'] else 'ZLE'} {v['kolieska_po_nacitani']}  "
                      f"značky+ESC {'OK (hra nespadla)' if v.get('znacky_esc', {}).get('ok') else 'ZLE ' + str(v.get('znacky_esc'))}  "
                      f"značky {len(v['znacky'])} {'OK' if v['ok_znacky'] else 'ZLE'}  "
                      f"kroky {p['kroky_s']}/s  zobrazenia {p['zobrazenia_s']}/s  okno {p['presuny_okna_s']}/s")
        for r in zle: riadky.append(f"    bod {r['bod']}: myš v hre {r['mys_v_hre']}, okno {r.get('okno')} (čakané {r.get('okno_ocak')}), kurzor hry {r.get('kurzor_hry')}")
    open(os.path.join(adr, "vysledok.txt"), "w", encoding="utf-8").write("\n".join(riadky) + "\n")
    print("\n".join(riadky)); print("výsledky:", adr)

if __name__ == "__main__":
    main()
