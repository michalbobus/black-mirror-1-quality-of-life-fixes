"""Ladiaci kanál doplnku DDraw.dll (štruktúra `ladenie`): volanie funkcií hry v hernom vlákne pri ďalšom tiku.
  python ladenie.py call ADRESA [arg ...]   – arg: číslo (0x..), alebo "s:text" (text sa uloží do bufferu, odovzdá sa adresa)
  python ladenie.py udalosti                – počítadlá z hákov"""
import sys, struct, time, os
import pefile
import pamat

DLL = r"D:\Hry\Steam\steamapps\common\Black Mirror\DDraw.dll"

class Kanal:
    def __init__(self):
        pid = pamat.pid_hry(); self.h = pamat.otvor(pid)
        baza = next(b for b, n, m in pamat.moduly32(pid) if m.lower() == "ddraw.dll")
        pe = pefile.PE(DLL)
        rva = next(s.address for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name == b"ladenie")
        self.a = baza + rva
    # rozloženie: prikaz, funkcia, pocet, argumenty[8], vysledok, text[256], udalosti[64]
    def volaj(self, fn, *args, text=None, cakaj=2.0):
        a = list(args) + [0] * (8 - len(args))
        if text is not None:
            pamat.zapis(self.h, self.a + 48, text.encode("latin-1") + b"\0")
        a = [self.a + 48 if x == "TEXT" else x for x in a]
        pamat.zapis(self.h, self.a + 4, struct.pack("<Ii8I", fn, len(args), *[x & 0xffffffff for x in a[:8]]))
        pamat.zapis(self.h, self.a, struct.pack("<i", 1))
        t = time.time()
        while time.time() - t < cakaj:
            if struct.unpack("<i", pamat.citaj(self.h, self.a, 4))[0] == 0:
                return struct.unpack("<i", pamat.citaj(self.h, self.a + 44, 4))[0]
            time.sleep(0.01)
        raise TimeoutError("hra príkaz nevykonala (beží tik?)")
    def udalosti(self):
        return struct.unpack("<64i", pamat.citaj(self.h, self.a + 48 + 256, 256))

if __name__ == "__main__":
    k = Kanal()
    if sys.argv[1] == "call":
        args, text = [], None
        for x in sys.argv[3:]:
            if x.startswith("s:"): text = x[2:]; args.append("TEXT")
            else: args.append(int(x, 0))
        r = k.volaj(int(sys.argv[2], 16), *args, text=text)
        print(hex(r & 0xffffffff), r)
    else:
        print(k.udalosti()[:16])
