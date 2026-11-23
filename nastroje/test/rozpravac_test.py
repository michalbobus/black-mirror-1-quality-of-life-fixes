"""rozpravac_test.py AKCIA – nová hra, preskočí úvodný film, počká na čiernu obrazovku s rozprávačom (scéna 123f)
a zmeria, za ako dlho prejde ďalej. AKCIA: nic | drz (ESC podržaný) | stlac (ESC raz za 2 s).
Predpoklad: hra beží v hlavnej ponuke (hra_save.sh)."""
import ctypes, time, sys, struct, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pamat
u = ctypes.windll.user32; u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
h = pamat.otvor(pamat.pid_hry())
def scena():
    p = struct.unpack("<I", pamat.citaj(h, 0x49eb1c, 4))[0]
    return pamat.citaj(h, p, 32).split(b"\0")[0].decode() if p else ""
def kl(vk, hore): u.keybd_event(vk, u.MapVirtualKeyW(vk, 0), 2 if hore else 0, 0)
g = u.FindWindowW(None, "Posel smrti"); u.SetForegroundWindow(g); time.sleep(0.2)
for k in range(8): u.SetCursorPos(390 + k, 197); time.sleep(0.03)
u.mouse_event(2, 0, 0, 0, 0); time.sleep(0.05); u.mouse_event(4, 0, 0, 0, 0); time.sleep(3)
u.SetCursorPos(799, 10); kl(0x1B, 0); time.sleep(0.05); kl(0x1B, 1)          # úvodný film
z = time.time()
while scena() != "123f" and time.time() - z < 60: time.sleep(0.05)
t0 = time.time(); print(f"123f po {t0 - z:.1f} s")
if sys.argv[1] == "drz": kl(0x1B, 0)
posl = 0
while scena() == "123f" and time.time() - t0 < 90:
    if sys.argv[1] == "stlac" and time.time() - posl > 2: kl(0x1B, 0); time.sleep(0.05); kl(0x1B, 1); posl = time.time()
    time.sleep(0.05)
if sys.argv[1] == "drz": kl(0x1B, 1)
print(f"{sys.argv[1]}: rozpravac {time.time() - t0:.1f} s, dalej {scena()}")
