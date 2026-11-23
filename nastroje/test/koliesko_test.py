"""koliesko_test.py N – N náhodných zárezov kolieska (rôzne miesta, rýchlo za sebou); po každej dávke kontrola,
že sa žiadny predmet nestratil (pole inventára 0x578c10 + predmet na kurzore [0x49f3e0])."""
import ctypes, time, random, struct, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pamat
u = ctypes.windll.user32; u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
h = pamat.otvor(pamat.pid_hry())
def predmety():
    d = pamat.citaj(h, 0x578c10, 0x578); m = set()
    for i in range(35):
        e = d[i * 0x28:(i + 1) * 0x28]
        if e[0] and struct.unpack_from("<i", e, 0x20)[0] == 1: m.add(e[:32].split(b"\0")[0].decode())
    p = struct.unpack("<I", pamat.citaj(h, 0x49f3e0, 4))[0]
    k = pamat.citaj(h, p + 8, 24).split(b"\0")[0].decode() if p else None
    return m, k
g = u.FindWindowW(None, "Posel smrti"); u.SetForegroundWindow(g); time.sleep(0.2)
zac, k = predmety(); vsetky = zac | ({k} if k else set()); print("na zaciatku", sorted(vsetky))
random.seed(1); chyby = 0
for n in range(int(sys.argv[1])):
    u.SetCursorPos(*random.choice([(400, 300), (289, 167), (400, 590), (107, 572), (700, 400)]))
    for z in range(random.randint(1, 3)):
        u.mouse_event(0x800, 0, 0, random.choice([120, -120]) & 0xffffffff, 0); time.sleep(random.choice([0.03, 0.1, 0.3]))
    time.sleep(random.choice([0.2, 1.5]))
    time.sleep(1.5); m, k = predmety(); teraz = m | ({k} if k else set())
    if teraz != vsetky: chyby += 1; print(n, "CHYBA", sorted(m), k)
print("davok", sys.argv[1], "chyb", chyby, "koniec", sorted(m), "kurzor", k)
