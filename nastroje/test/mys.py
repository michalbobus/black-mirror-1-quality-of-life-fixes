"""Ovládanie myši v hre: súradnice hry 0-799 x 0-599. Použitie: mys.py k X Y (klik) | m X Y (presun) | w SEK"""
import ctypes, time, sys
u = ctypes.windll.user32; u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
g = u.FindWindowW(None, "Posel smrti"); u.SetForegroundWindow(g); time.sleep(0.2)
a = sys.argv[1:]; i = 0
while i < len(a):
    c = a[i]
    if c == "w": time.sleep(float(a[i+1])); i += 2; continue
    x, y = int(a[i+1]), int(a[i+2]); i += 3
    p = ctypes.wintypes.POINT() if hasattr(ctypes, "wintypes") else None
    for k in range(8): u.SetCursorPos(x - 8 + k, y); time.sleep(0.03)
    u.SetCursorPos(x, y); time.sleep(0.3)
    if c == "k":
        u.mouse_event(2, 0, 0, 0, 0); time.sleep(0.25); u.mouse_event(4, 0, 0, 0, 0); time.sleep(0.3)
