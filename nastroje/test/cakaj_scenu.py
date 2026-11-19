"""Čaká na prvú scénu (lampy vľavo svietia), kým nie je, stláča ESC každých 6 s. Potom 2 s a snímka."""
import ctypes, time, sys
from PIL import ImageGrab
u = ctypes.windll.user32; u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
def esc():
    g = u.FindWindowW(None, "Posel smrti"); u.SetForegroundWindow(g); time.sleep(0.1)
    sc = u.MapVirtualKeyW(0x1B, 0); u.keybd_event(0x1B, sc, 0, 0); time.sleep(0.08); u.keybd_event(0x1B, sc, 2, 0)
z = time.perf_counter(); posl = z
while time.perf_counter() - z < 90:
    im = ImageGrab.grab(bbox=(270, 150, 450, 330)).convert("L")
    jas = sum(im.getdata()) / (180 * 180)
    if jas > 70:
        time.sleep(2); ImageGrab.grab().save(sys.argv[1]); print(f"scena po {time.perf_counter()-z:.0f} s, jas {jas:.0f}"); break
    if time.perf_counter() - posl > 6: esc(); posl = time.perf_counter()
    time.sleep(1)
else:
    print("scena neprisla")
