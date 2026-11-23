"""Animácie aktuálnej scény (zoznam scéna+0x80): poradie +0xC, š/v +0x10/+0x14, x/y +0x1C/+0x20, meno +0x41,
+0x61 (postava), +0x71 (objekt)."""
import pamat, struct
h = pamat.otvor(pamat.pid_hry())
rd = lambda a, n=4: pamat.citaj(h, a, n)
u32 = lambda a: struct.unpack('<I', rd(a))[0]
i32 = lambda a: struct.unpack('<i', rd(a))[0]
s = u32(0x49eb1c); prvy = u32(s + 0x80 + 0x28); a = prvy; n = 0
while a and n < 500:
    d = rd(a, 0x80)
    z, w, hh, x, y = struct.unpack_from("<5i", d, 0xc)[0], *struct.unpack_from("<2i", d, 0x10), *struct.unpack_from("<2i", d, 0x1c)
    meno = d[0x41:0x60].split(b"\0")[0].decode(errors="replace")
    p61, p71 = struct.unpack_from("<I", d, 0x61)[0], struct.unpack_from("<I", d, 0x71)[0]
    print(f"{a:08x} z{z:4} {w}x{hh} @{x},{y} {meno:24} p61={p61:x} p71={p71:x}")
    a = u32(a); n += 1
    if a == prvy: break
