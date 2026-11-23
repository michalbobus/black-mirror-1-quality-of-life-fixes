"""uvod_test.py AKCIA [PERIODA] – po príchode prvej scény (salón) opakuje akciu, kým hráč nedostane kontrolu
(user_enabled: [0x48b658] == 1 a [0x48b678] == 1). AKCIA: nic | esc | medzera | lavy | pravy | drzesc | drzmedzera (kláves stále stlačený).
Predpoklad: hra beží v hlavnej ponuke (hra_save.sh). Vypíše čas od scény po kontrolu."""
import ctypes, time, sys, struct, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pamat
from PIL import ImageGrab
u = ctypes.windll.user32; u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
akcia = sys.argv[1]; perioda = float(sys.argv[2]) if len(sys.argv) > 2 else 0.4
h = pamat.otvor(pamat.pid_hry())
def kontrola():
    a, b = struct.unpack("<i", pamat.citaj(h, 0x48b658, 4))[0], struct.unpack("<i", pamat.citaj(h, 0x48b678, 4))[0]
    return a == 1 and b == 1
def klaves(vk):
    sc = u.MapVirtualKeyW(vk, 0); u.keybd_event(vk, sc, 0, 0); time.sleep(0.05); u.keybd_event(vk, sc, 2, 0)
def klik(d, up):
    u.mouse_event(d, 0, 0, 0, 0); time.sleep(0.05); u.mouse_event(up, 0, 0, 0, 0)
g = u.FindWindowW(None, "Posel smrti"); u.SetForegroundWindow(g); time.sleep(0.2)
for k in range(8): u.SetCursorPos(390 + k, 197); time.sleep(0.03)
klik(2, 4); time.sleep(3)                       # Nová hra
u.SetCursorPos(799, 10); klaves(0x1B); time.sleep(3)
z = time.perf_counter(); posl = z
while time.perf_counter() - z < 90:            # preskakuj filmy, kým nesvietia lampy
    im = ImageGrab.grab(bbox=(270, 150, 450, 330)).convert("L")
    if sum(im.getdata()) / (180 * 180) > 70: break
    if time.perf_counter() - posl > 6: klaves(0x1B); posl = time.perf_counter()
    time.sleep(0.5)
t0 = time.perf_counter(); print(f"scena po {t0 - z:.0f} s")
u.SetCursorPos(400, 300)
if akcia.startswith("drz"):
    vk = 0x1B if akcia == "drzesc" else 0x20; u.keybd_event(vk, u.MapVirtualKeyW(vk, 0), 0, 0)
while time.perf_counter() - t0 < 240:
    if kontrola(): print(f"{akcia}: kontrola po {time.perf_counter() - t0:.1f} s"); break
    if akcia == "esc": klaves(0x1B)
    elif akcia == "medzera": klaves(0x20)
    elif akcia == "lavy": klik(2, 4)
    elif akcia == "pravy": klik(8, 16)
    time.sleep(perioda)
else: print(akcia, "kontrola neprisla")
if akcia.startswith("drz"): u.keybd_event(vk, u.MapVirtualKeyW(vk, 0), 2, 0)
