import sys, time, math, struct, ctypes
sys.path.insert(0, r"D:\.claude\projects\black mirror 1 borderless fullscreen+aspect ratio\nastroje")
import pamat
u = ctypes.windll.user32; u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
pid = pamat.pid_hry(); h = pamat.otvor(pid)
moj = [b for b, n, m in pamat.moduly32(pid) if m.lower() == "ddraw.dll"][0]
POCET = moj + 0x1000 + 0x800 + 0x4C
print("hak kurzor", pamat.citaj(h, 0x43cfee, 1).hex(), "tik", pamat.citaj(h, 0x402fa1, 1).hex(), "film", pamat.citaj(h, 0x44198e, 1).hex())
r = lambda a: struct.unpack("<i", pamat.citaj(h, a, 4))[0]
p0, t0 = r(POCET), r(0x597e8c); z = time.perf_counter()
while time.perf_counter() - z < 3:
    f = time.perf_counter() - z
    u.SetCursorPos(int(400 + 200 * math.cos(f * 3)), int(300 + 150 * math.sin(f * 3))); time.sleep(0.002)
d = time.perf_counter() - z
print(f"prekreslenia kurzora navyse: {(r(POCET)-p0)/d:.1f}/s, cykly hlavnej slucky: {(r(0x597e8c)-t0)/d:.1f}/s")
p0 = r(POCET); time.sleep(2); print("bez pohybu mysi navyse:", (r(POCET) - p0) / 2, "/s")
