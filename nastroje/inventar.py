"""Pole inventára 0x578c10: 35 položiek po 0x28 B (meno[32], +0x20 príznak, +0x24), predmet na kurzore [0x49f3e0]."""
import pamat, struct
h = pamat.otvor(pamat.pid_hry())
d = pamat.citaj(h, 0x578c10, 0x578)
for i in range(35):
    e = d[i * 0x28:(i + 1) * 0x28]
    if e[0]: print(i, e[:32].split(b"\0")[0].decode(), struct.unpack_from("<ii", e, 0x20))
p = struct.unpack("<I", pamat.citaj(h, 0x49f3e0, 4))[0]
print("na kurzore:", pamat.citaj(h, p + 8, 24).split(b"\0")[0].decode() if p else "-")
