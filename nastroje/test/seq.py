"""seq.py PREFIX akcie... – postupnosť akcií v hre so záznamom hlasitosti zvuku hry.
Akcie: r X Y = pravý klik, l X Y = ľavý klik, m X Y = presun (súradnice hry 800×600),
t X1 Y1 X2 Y2 = ťahanie, c DELTA = koliesko, k VK = stlač kláves (hex), d VK = drž kláves, u VK = pusti kláves, s = snímka PREFIXn.png, w T = čakaj.
Na konci vypíše priebeh hlasitosti (agds.exe) a prítomnosť titulkov po 0,1 s."""
import ctypes, time, sys, threading
from PIL import ImageGrab
u = ctypes.windll.user32; u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
from comtypes import CoInitialize

zaznam = []; titulky = []; koniec = False
def sleduj_titulky():
    """Pás titulkov (hra y 556–600 = obrazovka y 1000–1080): počet svetlých pixelov každých 0,1 s."""
    import numpy as np
    while not koniec:
        a = np.asarray(ImageGrab.grab(bbox=(240, 1000, 1680, 1080)).convert("L"))
        titulky.append((time.perf_counter() - t0, int((a > 120).sum()))); time.sleep(0.07)
def meraj():
    CoInitialize()
    m = None
    for s in AudioUtilities.GetAllSessions():
        if s.Process and s.Process.name().lower() == "agds.exe":
            m = s._ctl.QueryInterface(IAudioMeterInformation)
    while not koniec:
        zaznam.append((time.perf_counter() - t0, m.GetPeakValue() if m else -1)); time.sleep(0.02)

g = u.FindWindowW(None, "Posel smrti"); u.SetForegroundWindow(g); time.sleep(0.2)
t0 = time.perf_counter(); th = threading.Thread(target=meraj); th.start()
th2 = threading.Thread(target=sleduj_titulky); th2.start()
a = sys.argv[2:]; i = 0; n = 0
def kl(vk, hore):
    u.keybd_event(vk, u.MapVirtualKeyW(vk, 0), 2 if hore else 0, 0)
while i < len(a):
    c = a[i]
    if c == "w": time.sleep(float(a[i+1])); i += 2
    elif c == "s":
        ImageGrab.grab().save(f"{sys.argv[1]}{n}.png"); print(f"snimka {n} {time.perf_counter()-t0:.1f}"); n += 1; i += 1
    elif c in "kdu":
        vk = int(a[i+1], 16); i += 2
        if c in "kd": kl(vk, False)
        if c == "k": time.sleep(0.08)
        if c in "ku": kl(vk, True)
        print(f"{c} {vk:x} {time.perf_counter()-t0:.1f}")
    elif c == "c":                                   # koliesko: c DELTA (-120 = zárez dole)
        u.mouse_event(0x800, 0, 0, int(a[i+1]) & 0xffffffff, 0); print(f"c {a[i+1]} {time.perf_counter()-t0:.1f}"); i += 2
    elif c == "t":                                   # ťahanie ľavým tlačidlom: t X1 Y1 X2 Y2
        x1, y1, x2, y2 = map(int, a[i+1:i+5]); i += 5
        u.SetCursorPos(x1, y1); time.sleep(0.3); u.mouse_event(2, 0, 0, 0, 0); time.sleep(0.2)
        for k in range(1, 21): u.SetCursorPos(x1 + (x2 - x1) * k // 20, y1 + (y2 - y1) * k // 20); time.sleep(0.03)
        time.sleep(0.2); u.mouse_event(4, 0, 0, 0, 0); print(f"t {x1},{y1} -> {x2},{y2} {time.perf_counter()-t0:.1f}")
    else:
        x, y = int(a[i+1]), int(a[i+2]); i += 3
        for k in range(6): u.SetCursorPos(x - 6 + k, y); time.sleep(0.03)
        u.SetCursorPos(x, y); time.sleep(0.2)
        if c != "m":
            d, up = (2, 4) if c == "l" else (8, 16)
            u.mouse_event(d, 0, 0, 0, 0); time.sleep(0.25); u.mouse_event(up, 0, 0, 0, 0)
        print(f"{c} {x} {y} {time.perf_counter()-t0:.1f}")
koniec = True; th.join(); th2.join()
riadok = []
for k in range(int(zaznam[-1][0] * 10) + 1):
    v = [p for t, p in zaznam if k / 10 <= t < (k + 1) / 10]
    riadok.append(" .:-=+*#%@"[min(9, int(max(v) * 20))] if v and max(v) >= 0 else "?")
print("zvuk po 0,1 s:")
s = "".join(riadok)
for k in range(0, len(s), 50): print(f"{k/10:5.1f} {s[k:k+50]}")
riadok = []
for k in range(int(zaznam[-1][0] * 10) + 1):
    v = [p for t, p in titulky if k / 10 <= t < (k + 1) / 10]
    riadok.append(("T" if max(v) > 200 else "_") if v else " ")
print("titulky po 0,1 s (T = text):")
s = "".join(riadok)
for k in range(0, len(s), 50): print(f"{k/10:5.1f} {s[k:k+50]}")
