"""Zvukové kanály: počet [0x4904c8], tabuľka 0x59afe8 po 16 B (+0 typ, +4 obsadený, +0xC vzorka)."""
import pamat, struct
h = pamat.otvor(pamat.pid_hry())
n = struct.unpack("<i", pamat.citaj(h, 0x4904c8, 4))[0]
d = pamat.citaj(h, 0x59afe8, 16 * n)
for i in range(n):
    e = struct.unpack_from("<4I", d, 16 * i)
    if not e[1] and not e[3]: continue
    v = pamat.citaj(h, e[3], 0x40) if e[3] else b""
    print(i, [hex(x) for x in e], v.hex(" ") if v else "")
