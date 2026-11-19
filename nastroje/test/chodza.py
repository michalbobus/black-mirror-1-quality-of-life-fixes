"""Zmeria trvanie chôdze postavy: klik na cieľ, potom snímky oblasti scény, kým sa neprestanú meniť.
chodza.py CIEL_X CIEL_Y krouz(0/1)"""
import ctypes, time, sys, math, threading
import numpy as np
from PIL import ImageGrab
u = ctypes.windll.user32; u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
cx, cy, krouz = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3] == "1"
g = u.FindWindowW(None, "Posel smrti"); u.SetForegroundWindow(g); time.sleep(0.3)
u.SetCursorPos(cx, cy); time.sleep(0.3)
u.mouse_event(2, 0, 0, 0, 0); time.sleep(0.05); u.mouse_event(4, 0, 0, 0, 0)
t0 = time.perf_counter(); stop = False
time.sleep(0.2)
def mys():
    while not stop:
        f = time.perf_counter() - t0
        if krouz: u.SetCursorPos(int(60 + 25 * math.cos(f * 12)), int(120 + 25 * math.sin(f * 12)))
        else: u.SetCursorPos(60, 120)
        time.sleep(0.003)
th = threading.Thread(target=mys); th.start()
box = (240, 100, 1680, 1080)   # scéna bez horného riadku s nápismi
pred = None; posl_zmena = 0
while time.perf_counter() - t0 < 15:
    a = np.asarray(ImageGrab.grab(bbox=box).convert("L"), dtype=np.int16).copy()
    a[0:380, 0:300] = 0   # oblasť krúžiaceho kurzora (hra x 0..166, y 55..266)
    t = time.perf_counter() - t0
    if pred is not None and np.abs(a - pred).max() > 40 and (np.abs(a - pred) > 40).sum() > 30:
        posl_zmena = t
    pred = a
    if t - posl_zmena > 1.5 and t > 2: break
    time.sleep(0.05)
stop = True; th.join()
print(f"chodza trvala ~{posl_zmena:.2f} s (krouzenie={krouz})")
