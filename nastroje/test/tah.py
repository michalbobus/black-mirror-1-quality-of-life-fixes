"""Rýchly pohyb kurzora po scéne (súradnice hry). tah.py RYCHLOST_PX_ZA_KROK"""
import ctypes, time, sys, math
u = ctypes.windll.user32; u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
k = float(sys.argv[1]) if len(sys.argv) > 1 else 6
body = [(100, 150), (700, 150), (700, 450), (100, 450), (400, 300), (650, 120), (150, 500), (600, 350)]
x, y = body[0]
for bx, by in body[1:]:
    d = math.hypot(bx - x, by - y); n = max(1, int(d / k))
    for i in range(1, n + 1):
        u.SetCursorPos(int(x + (bx - x) * i / n), int(y + (by - y) * i / n)); time.sleep(0.004)
    x, y = bx, by
u.SetCursorPos(420, 560)
