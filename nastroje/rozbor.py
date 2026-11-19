"""Pomocné rozoberanie agds.exe: reťazce, odkazy na ne, disassembly."""
import sys, struct, re
import pefile, capstone

EXE = r"D:\Hry\Steam\steamapps\common\Black Mirror\agds.exe"
pe = pefile.PE(EXE)
BASE = pe.OPTIONAL_HEADER.ImageBase
data = pe.get_memory_mapped_image()
cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
cs.detail = False

def va_retazca(s):
    i = data.find(s.encode() + b"\0")
    return BASE + i if i >= 0 else None

def odkazy(va):
    """Miesta v kóde, kde sa vyskytuje 32-bit konštanta va."""
    b = struct.pack("<I", va)
    return [BASE + m.start() for m in re.finditer(re.escape(b), data)]

def dis(va, n=40):
    off = va - BASE
    for ins in cs.disasm(data[off:off + n * 8], va, n):
        print(f"{ins.address:08x}  {ins.mnemonic:6} {ins.op_str}")

def importy():
    d = {}
    for e in pe.DIRECTORY_ENTRY_IMPORT:
        for i in e.imports:
            d[i.address] = f"{e.dll.decode()}!{i.name.decode() if i.name else i.ordinal}"
    return d

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "str":
        for s in sys.argv[2:]:
            v = va_retazca(s); print(s, hex(v) if v else None, [hex(x) for x in odkazy(v)] if v else "")
    elif cmd == "dis":
        dis(int(sys.argv[2], 16), int(sys.argv[3]) if len(sys.argv) > 3 else 40)
    elif cmd == "imp":
        for a, n in sorted(importy().items()):
            if not sys.argv[2:] or any(k.lower() in n.lower() for k in sys.argv[2:]): print(hex(a), n)
    elif cmd == "ref":
        print([hex(x) for x in odkazy(int(sys.argv[2], 16))])
