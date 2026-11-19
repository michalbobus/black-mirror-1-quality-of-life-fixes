"""Pre globálne ukazovatele na DirectDraw objekty vypíše, ktoré metódy (posun vo vtable) sa na nich volajú a odkiaľ."""
import sys, collections
import rozbor as r
glob = [int(x, 16) for x in sys.argv[1:]]
text = r.pe.sections[0]
zac = r.BASE + text.VirtualAddress
kod = r.data[text.VirtualAddress:text.VirtualAddress + text.Misc_VirtualSize]
r.cs.skipdata = True
ins = list(r.cs.disasm(kod, zac))
print("instrukcii", len(ins), hex(ins[-1].address))
for g in glob:
    c = collections.defaultdict(list)
    for i, x in enumerate(ins):
        if hex(g) in x.op_str and x.mnemonic == "mov":
            for y in ins[i + 1:i + 6]:
                if y.mnemonic == "call" and "dword ptr [" in y.op_str and "+" in y.op_str:
                    c[y.op_str.split("+ ")[1].rstrip("]")].append(hex(y.address)); break
    print(hex(g), {k: (len(v), v[:6]) for k, v in sorted(c.items())})
