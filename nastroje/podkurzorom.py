"""Vypíše objekt pod kurzorom (scéna+0x5ed): adresa, meno (+8), obsluhy use (+0xb5) a info."""
import pamat, struct
h = pamat.otvor(pamat.pid_hry())
rd = lambda a, n=4: pamat.citaj(h, a, n)
u32 = lambda a: struct.unpack('<I', rd(a))[0]
s = u32(0x49eb1c); o = u32(s + 0x5ed)
print("scena", rd(s, 32).split(b"\0")[0], "objekt", hex(o))
if o:
    d = rd(o, 0x100)
    print("  meno", d[8:40].split(b"\0")[0], "+0:", d[0:8].hex(), "use(+b5)", hex(struct.unpack_from('<i', d, 0xb5)[0]), "c9", hex(struct.unpack_from('<i', d, 0xc9)[0]))
