"""Relatívny pohyb myši (SendInput) a odčítanie posunu kurzora v hre. Výstup: posun pri pomalom a rýchlom pohybe."""
import ctypes, ctypes.wintypes as W, time, sys, struct
sys.path.insert(0, r"D:\.claude\projects\black mirror 1 borderless fullscreen+aspect ratio\nastroje")
import pamat
u = ctypes.windll.user32; u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
class MI(ctypes.Structure): _fields_ = [("dx", W.LONG), ("dy", W.LONG), ("mouseData", W.DWORD), ("dwFlags", W.DWORD), ("time", W.DWORD), ("dwExtraInfo", ctypes.c_size_t)]
class INP(ctypes.Structure): _fields_ = [("type", W.DWORD), ("mi", MI)]
def pohyb(dx, dy):
    i = INP(); i.type = 0; i.mi.dx = dx; i.mi.dy = dy; i.mi.dwFlags = 1
    assert u.SendInput(1, ctypes.byref(i), ctypes.sizeof(i)) == 1, ctypes.sizeof(i)
h = pamat.otvor(pamat.pid_hry())
hra = lambda: struct.unpack("<2i", pamat.citaj(h, 0x507010, 8))
g = u.FindWindowW(None, "Posel smrti"); u.SetForegroundWindow(g); time.sleep(0.3)
vys = []
for krok, n, pauza in ((4, 40, 0.012), (30, 6, 0.012)):
    u.SetCursorPos(150, 150); time.sleep(0.6)
    for _ in range(3): pohyb(0, 0); time.sleep(0.05)
    x0, y0 = hra()
    for _ in range(n): pohyb(krok, krok // 2); time.sleep(pauza)
    time.sleep(0.5)
    x1, y1 = hra()
    vys.append((x1 - x0, y1 - y0))
print("pomaly (160,80 mickey):", vys[0], " rychlo (180,90 mickey):", vys[1])
