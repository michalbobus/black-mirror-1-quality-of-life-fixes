"""Objekty aktuálnej scény: kruhový zoznam scéna+0x40 (prvý [+0x28], ďalší [obj+0]), región [obj+0x72]:
stred (+0,+2), ohraničenie x +0xA..+0xC, y +0xE..+0x10; posun objektu +0x42/+0x46, posun scény +0x5d5/+0x5d9."""
import pamat, struct
h = pamat.otvor(pamat.pid_hry())
rd = lambda a, n=4: pamat.citaj(h, a, n)
u32 = lambda a: struct.unpack('<I', rd(a))[0]
i32 = lambda a: struct.unpack('<i', rd(a))[0]
s = u32(0x49eb1c); zac = u32(s + 0x40 + 0x28)
print("scena", rd(s, 32).split(b"\0")[0], "posun", i32(s + 0x5d5), i32(s + 0x5d9))
o = zac; n = 0
while o and n < 300:
    d = rd(o, 0xd0)
    meno = d[8:40].split(b"\0")[0].decode(errors="replace")
    akt, z, reg = struct.unpack_from('<i', d, 0x34)[0], struct.unpack_from('<i', d, 0x2c)[0], struct.unpack_from('<I', d, 0x72)[0]
    dx, dy = struct.unpack_from('<ii', d, 0x42)
    use, info = struct.unpack_from('<i', d, 0xb5)[0], struct.unpack_from('<i', d, 0xc9)[0]
    r = ""
    if reg:
        cx, cy, cnt = struct.unpack('<hhh', rd(reg, 6)); x0, x1, y0, y1 = struct.unpack('<hhhh', rd(reg + 0xa, 8))
        r = f"stred {cx},{cy} box x{x0}-{x1} y{y0}-{y1} n{cnt}"
    print(f"{o:08x} {meno:14} akt{akt} z{z} posun {dx},{dy} use{use:x} c9{info:x} {r}")
    o = u32(o); n += 1
    if o == zac: break
