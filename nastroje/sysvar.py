"""Tabuľka systémových premenných AGDS v agds.exe (záznamy po 0x2D B od 0x48d470):
meno[32], ukazovateľ na hodnotu, ukazovateľ 2, príznak (1 = číslo), funkcia pri zmene.
Bez parametra vypíše tabuľku aj s hodnotami z bežiacej hry."""
import struct
import rozbor as r

def tabulka():
    a = 0x48d470; out = []
    while True:
        o = a - r.BASE
        meno = r.data[o:o + 32].split(b"\0")[0]
        if not meno or not all(32 < c < 127 for c in meno): break
        p1, p2, f, fn = struct.unpack_from("<IIBI", r.data, o + 32)
        out.append((a, meno.decode(), p1, p2, f, fn)); a += 0x2D
    return out

if __name__ == "__main__":
    try:
        import pamat; h = pamat.otvor(pamat.pid_hry())
    except BaseException: h = None
    for a, m, p1, p2, f, fn in tabulka():
        v = ""
        if h and p1:
            raw = pamat.citaj(h, p1, 32)
            v = struct.unpack("<i", raw[:4])[0] if f else raw.split(b"\0")[0]
            if not f and p2:
                pass
        print(f"{a:x} {m:18} hodnota@{p1:x} p2@{p2:x} {f} fn={fn:x}  {v}")
