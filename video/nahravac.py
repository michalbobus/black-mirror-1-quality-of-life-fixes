"""Záznam obrazovky (ffmpeg ddagrab, 60 snímok/s, NVENC) + zvuku hry (WASAPI loopback) a ovládanie hry pre ukážkové video.

Synchronizácia: na začiatku záznamu sa v ľavom hornom rohu na 0,2 s ukáže biely štvorec (čierny pás 4:3);
čas záblesku sa zapíše do <meno>.json (perf_counter) – zostavenie videa podľa neho nájde snímku záblesku.
Zvuk sa ukladá po blokoch s časom príchodu, ticho (loopback vtedy neposiela nič) sa doplní nulami.
Všetky udalosti (klávesy, kliky) sa zapisujú s časom do <meno>.json – zostavenie podľa nich kreslí odznaky klávesov.
Súradnice myši sú súradnice hry 0–799 × 0–599 (dgVoodoo drží kurzor v obdĺžniku 800×600)."""
import ctypes, ctypes.wintypes as W, time, json, os, subprocess, threading, wave, struct, sys
import numpy as np

u = ctypes.windll.user32; u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
HRA = r"D:\Hry\Steam\steamapps\common\Black Mirror"
CFG = os.path.join(HRA, "config.ini")
ZAZNAMY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zaznamy")
os.makedirs(ZAZNAMY, exist_ok=True)
import imageio_ffmpeg
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# ---------- nastavenia doplnku ----------
PO = {("Movies", "FullWidth"): "1", ("Cursor", "Mode"): "hardware", ("Cursor", "Sensitivity"): "1.0",
      ("Controls", "EscapeMenu"): "1", ("Controls", "SpaceHotspots"): "1", ("Controls", "HoldToSkip"): "1",
      ("Controls", "SaveLoadKeys"): "1", ("Controls", "QuickSaveKeys"): "1", ("Controls", "WheelInventory"): "1",
      ("Controls", "DoubleClickWalk"): "1", ("Video", "Smoothing"): "1", ("Video", "SaveNamesTransparent"): "1"}
PRED = {k: "0" for k in PO}
PRED.update({("Cursor", "Mode"): "original", ("Cursor", "Sensitivity"): "1.0"})

def profil(verzia): return PRED if verzia == "pred" else PO

def nastav(profil):
    for (s, k), v in profil.items():
        ctypes.windll.kernel32.WritePrivateProfileStringW(s, k, v, CFG)

# ---------- hra ----------
def okno(): return u.FindWindowW(None, "Posel smrti")
def popredie():
    """Hru do popredia – Windows to procesu na pozadí dovolí len po stlačení klávesu (Alt), preto Alt naprázdno."""
    g = okno()
    if not g: return
    for _ in range(5):
        if u.GetForegroundWindow() == g: break
        u.keybd_event(0x12, 0, 0, 0); u.keybd_event(0x12, 0, 2, 0)
        u.ShowWindow(g, 5); u.SetForegroundWindow(g); u.BringWindowToTop(g); time.sleep(0.2)
    time.sleep(0.1)

def jas(bbox):
    from PIL import ImageGrab
    return np.asarray(ImageGrab.grab(bbox=bbox).convert("L")).mean()

REF_PONUKA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ref_ponuka.png")
def v_ponuke():
    """Hlavná ponuka = nadpis Posel smrti (obrazovka 730–1180 × 140–280) sa zhoduje s referenčným výrezom."""
    from PIL import ImageGrab, Image
    if u.GetForegroundWindow() != okno(): popredie()
    a = np.asarray(ImageGrab.grab(bbox=(730, 140, 1180, 280)).convert("L"), np.float32)
    if not os.path.exists(REF_PONUKA): return False
    b = np.asarray(Image.open(REF_PONUKA).convert("L"), np.float32)
    return float(np.abs(a - b).mean()) < 12

def spusti(profil):
    """Ukončí hru, nastaví profil, spustí hru a preskočí logá do hlavnej ponuky (nadpis Posel smrti svieti)."""
    subprocess.run("taskkill /f /im agds.exe", shell=True, capture_output=True); time.sleep(1.2)
    nastav(profil)
    subprocess.Popen([os.path.join(HRA, "agds.exe")], cwd=HRA); time.sleep(4)
    z = time.time(); posl = 0
    while time.time() - z < 60:
        if v_ponuke(): break
        if time.time() - posl > 3: popredie(); klaves(0x1B, log=False); posl = time.time()
        time.sleep(0.3)
    time.sleep(1.5)

def nahraj_poziciu(slot=1):
    """Z hlavnej ponuky načíta pozíciu 1–8 (prvá strana zoznamu) a počká na scénu."""
    klik(400, 269); time.sleep(2.5); klik(322, 189 + round((slot - 1) * 30.2)); time.sleep(5)

def do_haly(profil):
    """Spoločný začiatok väčšiny dielov: hra s profilom, save.1 = hala, Samuel stojí vpravo pri dverách."""
    spusti(profil); nahraj_poziciu(1); presun(400, 300, 0.3); time.sleep(1)

def nova_hra(profil):
    """Hlavná ponuka → Nová hra (začne úvodný film)."""
    spusti(profil); klik(400, 197)

class OchranaPozicii:
    """Zálohuje save.N a záznamy N v savnames.txt (51 B na pozíciu) a po dieli vráti len tieto pozície."""
    def __init__(self, *sloty): self.sloty = sloty
    def __enter__(self):
        self.mena = open(os.path.join(HRA, "savnames.txt"), "rb").read()
        self.subory = {}
        for s in self.sloty:
            p = os.path.join(HRA, f"save.{s}")
            self.subory[s] = open(p, "rb").read() if os.path.exists(p) else None
        return self
    def __exit__(self, *a):
        subprocess.run("taskkill /f /im agds.exe", shell=True, capture_output=True); time.sleep(1.2)
        p = os.path.join(HRA, "savnames.txt"); teraz = bytearray(open(p, "rb").read())
        for s in self.sloty:
            teraz[s * 51:(s + 1) * 51] = self.mena[s * 51:(s + 1) * 51]
            f = os.path.join(HRA, f"save.{s}")
            if self.subory[s] is None:
                if os.path.exists(f): os.remove(f)
            else: open(f, "wb").write(self.subory[s])
        open(p, "wb").write(teraz)

# ---------- záznam udalostí ----------
UDALOSTI = []
def udalost(meno, **kw):
    UDALOSTI.append(dict(t=time.perf_counter(), meno=meno, **kw))

# ---------- vstupy ----------
def kl(vk, hore):
    u.keybd_event(vk, u.MapVirtualKeyW(vk, 0), 2 if hore else 0, 0)
def klaves(vk, drz=0.08, log=True, meno=None):
    if log: udalost("klaves", vk=vk, meno_k=meno, trvanie=drz)
    kl(vk, False); time.sleep(drz); kl(vk, True)
_opakovanie = {}
def drz(vk, meno=None):
    """Podrží kláves ako skutočná klávesnica: po 0,5 s opakované stlačenia 30×/s (hra na ne čaká pri podržaní)."""
    udalost("drz", vk=vk, meno_k=meno); kl(vk, False)
    stop = threading.Event(); _opakovanie[vk] = stop
    def opakuj():
        if stop.wait(0.5): return
        while not stop.wait(0.033): kl(vk, False)
    threading.Thread(target=opakuj, daemon=True).start()
def pusti(vk):
    if vk in _opakovanie: _opakovanie.pop(vk).set(); time.sleep(0.04)
    udalost("pusti", vk=vk); kl(vk, True)
def kombinacia(vk1, vk2, meno):
    udalost("klaves", vk=vk2, meno_k=meno, trvanie=0.3)
    kl(vk1, False); time.sleep(0.05); kl(vk2, False); time.sleep(0.12); kl(vk2, True); time.sleep(0.05); kl(vk1, True)

def poloha():
    p = W.POINT(); u.GetCursorPos(ctypes.byref(p)); return p.x, p.y
def presun(x, y, trvanie=0.4, krok=0.004):
    """Plynulý presun kurzora (ako ruka) – krok 4 ms."""
    x0, y0 = poloha(); n = max(1, int(trvanie / krok))
    for i in range(1, n + 1):
        s = i / n; s = s * s * (3 - 2 * s)
        u.SetCursorPos(round(x0 + (x - x0) * s), round(y0 + (y - y0) * s)); time.sleep(krok)
def klik(x=None, y=None, prave=False, trvanie=0.4):
    if x is not None: presun(x, y, trvanie); time.sleep(0.15)
    udalost("klik", prave=prave, x=poloha()[0], y=poloha()[1])
    d, h = (8, 16) if prave else (2, 4)
    u.mouse_event(d, 0, 0, 0, 0); time.sleep(0.08); u.mouse_event(h, 0, 0, 0, 0)
def dvojklik(x, y, trvanie=0.4):
    presun(x, y, trvanie); time.sleep(0.15)
    udalost("dvojklik", x=x, y=y)
    for _ in range(2):
        u.mouse_event(2, 0, 0, 0, 0); time.sleep(0.04); u.mouse_event(4, 0, 0, 0, 0); time.sleep(0.06)
def koliesko(delta):
    udalost("koliesko", delta=delta); u.mouse_event(0x800, 0, 0, delta & 0xffffffff, 0)
def kruh(cx, cy, r, trvanie, otacky=1.0, krok=0.002):
    """Kurzor krúži – na ukážku plynulosti kurzora."""
    import math
    t0 = time.perf_counter()
    while (t := time.perf_counter() - t0) < trvanie:
        a = 2 * math.pi * otacky * t / trvanie
        u.SetCursorPos(round(cx + r * math.cos(a)), round(cy + r * math.sin(a))); time.sleep(krok)

# ---------- záblesk na synchronizáciu ----------
def zablesk():
    import tkinter as tk
    r = tk.Tk(); r.overrideredirect(True); r.attributes("-topmost", True)
    r.geometry("120x120+0+0"); r.configure(bg="white"); r.update()
    t = time.perf_counter(); time.sleep(0.25); r.destroy()
    popredie()
    return t

# ---------- zvuk ----------
class Zvuk:
    def __init__(self):
        import pyaudiowpatch as pa
        self.pa = pa.PyAudio(); d = self.pa.get_default_wasapi_loopback()
        self.sr = int(d["defaultSampleRate"]); self.ch = d["maxInputChannels"]; self.bloky = []
        def cb(data, n, info, st):
            self.bloky.append((time.perf_counter(), n, data)); return (None, pa.paContinue)
        self.st = self.pa.open(format=pa.paInt16, channels=self.ch, rate=self.sr, input=True,
                               input_device_index=d["index"], frames_per_buffer=480, stream_callback=cb)
        self.t0 = time.perf_counter()
    def stop(self, cesta, t_ref):
        self.st.stop_stream(); self.st.close(); self.pa.terminate()
        koniec = self.bloky[-1][0] if self.bloky else t_ref
        out = np.zeros((int((koniec - t_ref + 1) * self.sr), self.ch), np.int16)
        poz = None
        for t, n, data in self.bloky:
            a = np.frombuffer(data, np.int16).reshape(-1, self.ch)
            ocak = int((t - t_ref) * self.sr) - n
            if poz is None or abs(ocak - poz) > self.sr * 0.03: poz = ocak   # medzera (ticho) – skok podľa času
            if poz >= 0 and poz + n <= len(out): out[poz:poz + n] = a
            poz += n
        with wave.open(cesta, "wb") as w:
            w.setnchannels(self.ch); w.setsampwidth(2); w.setframerate(self.sr); w.writeframes(out.tobytes())

# ---------- záznam ----------
class Zaznam:
    def __init__(self, meno):
        self.meno = meno; self.cesta = os.path.join(ZAZNAMY, meno)
    def __enter__(self):
        UDALOSTI.clear()
        self.ff = subprocess.Popen([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
            "-i", "ddagrab=output_idx=0:framerate=60:draw_mouse=0,hwdownload,format=bgra", "-c:v", "libx264",
            "-preset", "ultrafast", "-crf", "15", "-pix_fmt", "yuv420p", self.cesta + ".mkv"], stdin=subprocess.PIPE)
        self.zv = Zvuk(); time.sleep(1.5)
        self.t_zablesk = zablesk(); time.sleep(0.5)
        self.t_start = time.perf_counter()
        return self
    def __exit__(self, *a):
        time.sleep(0.5)
        self.ff.stdin.write(b"q"); self.ff.stdin.flush(); self.ff.wait(20)
        self.zv.stop(self.cesta + ".wav", self.t_zablesk)
        json.dump(dict(t_zablesk=self.t_zablesk, t_start=self.t_start, t_koniec=time.perf_counter(),
                       udalosti=UDALOSTI), open(self.cesta + ".json", "w"), indent=1)
        print("zaznam", self.meno, f"{time.perf_counter() - self.t_start:.1f} s")
    def znacka(self, meno):
        udalost("znacka", nazov=meno)

POVODNE = os.path.join(ZAZNAMY, "povodne_nastavenia.json")

def _precitaj_profil():
    b = ctypes.create_unicode_buffer(64); p = {}
    for (s, k) in PO:
        ctypes.windll.kernel32.GetPrivateProfileStringW(s, k, "", b, 64, CFG)
        p[f"{s}|{k}"] = b.value
    return p

def _povodne():
    """Hodnoty config.ini pred prvým nahrávaním – uložia sa do súboru, aby ich neprepísal ani prerušený beh."""
    if not os.path.exists(POVODNE): json.dump(_precitaj_profil(), open(POVODNE, "w"), indent=1)
    return json.load(open(POVODNE))
_povodne()

def koniec():
    """Po nahrávaní: ukončí hru a vráti kľúče, ktoré mení profil, na hodnoty pred nahrávaním (chýbajúci kľúč zmaže)."""
    subprocess.run("taskkill /f /im agds.exe", shell=True, capture_output=True); time.sleep(1)
    for sk, v in _povodne().items():
        s, k = sk.split("|")
        ctypes.windll.kernel32.WritePrivateProfileStringW(s, k, None if v == "" else v, CFG)
    os.remove(POVODNE)
