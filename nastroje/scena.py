"""Vypíše meno aktuálnej a predchádzajúcej obrazovky (objekt scény [0x49eb1c]: +0 meno, +0x20 predchádzajúca)."""
import pamat, struct
h = pamat.otvor(pamat.pid_hry())
p = struct.unpack('<I', pamat.citaj(h, 0x49eb1c, 4))[0]
d = pamat.citaj(h, p, 0x40) if p else b""
print(d[:32].split(b"\0")[0].decode(), "| predch.", d[32:64].split(b"\0")[0].decode())
