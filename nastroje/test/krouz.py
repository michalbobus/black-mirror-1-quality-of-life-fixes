import ctypes, time, math, sys
u = ctypes.windll.user32; u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
cx, cy, r, t = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4])
z = time.perf_counter()
while time.perf_counter() - z < t:
    f = time.perf_counter() - z
    u.SetCursorPos(int(cx + r * math.cos(f * 6)), int(cy + r * math.sin(f * 6))); time.sleep(0.003)
