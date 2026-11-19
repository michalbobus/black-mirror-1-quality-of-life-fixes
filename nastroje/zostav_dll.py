"""Zostaví proxy DDraw.dll pre Black Mirror (agds.exe): filmy roztiahnuté na celú šírku obrazovky.

Ako to funguje:
  * Hra importuje DDRAW.dll!DirectDrawCreateEx. Táto knižnica sa volá DDraw.dll a všetky exporty
    prepošle (forwarder) na dgVoodoo, ktorý je v priečinku hry premenovaný na dgddraw.dll.
  * Pri načítaní (DllMain) overí bajty v agds.exe a vloží dva skoky (exe na disku sa nemení):
      0x44198e  – štart filmu, hneď po tom, čo hra uloží obdĺžnik filmu do 0x58510c..0x585118
      0x441fea  – začiatok funkcie konca filmu
  * Štart: ak film zaberá celú šírku (ľavý okraj <= 0, pravý >= 800) a nad ním je letterbox (horný > 0),
    zapíše obdĺžnik filmu do výrezu (DisplayROI) dgVoodoo – dgVoodoo ho potom zväčší so zachovaním
    pomeru strán, teda na celú šírku obrazovky. Pôvodný výrez si uloží.
  * Koniec: vráti pôvodný výrez.
  * Zapnutie/vypnutie: config.ini vedľa tejto knižnice, [Filmy] NaCeluSirku=1/0 (chýba -> 1).
    Pri 0 sa háky vôbec nevložia a filmy ostanú v rámci 4:3.
  * Výrez dgVoodoo 2.87.6 je v dgddraw.dll na RVA 0x6c460 (RECT), 0x18 bajtov pred ním šírka a výška
    režimu. Zapisuje sa len vtedy, keď tam je 800 a 600 (iná verzia dgVoodoo -> nerobí nič).

Použitie:  python zostav_dll.py VYSTUP.dll
"""
import re
import struct
import sys

import keystone

RVA = 0x1000
O_KOD, O_DATA, O_IMPORT, O_EXPORT, O_CESTA, O_KONIEC = 0x000, 0x400, 0x480, 0x600, 0xA00, 0xC00
# dáta
O_AKTIVNY = O_DATA            # adresa RECT v dgVoodoo počas filmu, inak 0
O_ULOZENY = O_DATA + 4        # pôvodný RECT (16 B)
O_DGMENO = O_DATA + 0x20      # "dgddraw.dll"
O_SEKCIA = O_DATA + 0x30      # "Filmy"
O_KLUC = O_DATA + 0x40        # "NaCeluSirku"
O_INIMENO = O_DATA + 0x50     # "config.ini"
# O_CESTA: vyrovnávacia pamäť na úplnú cestu k ini (512 B)
INI_SEKCIA, INI_KLUC, INI_MENO = "Filmy", "NaCeluSirku", "config.ini"
# importy KERNEL32
IMPORTY = ["VirtualProtect", "GetModuleHandleA", "GetModuleFileNameA", "GetPrivateProfileIntA"]
O_ILT, O_IAT, O_MENA = O_IMPORT + 0x30, O_IMPORT + 0x48, O_IMPORT + 0x60   # 2 deskriptory (40 B) + tabuľky
O_IAT_VP, O_IAT_GMH, O_IAT_GMFN, O_IAT_GPPI = (O_IAT + 4 * i for i in range(4))

CIEL = "dgddraw"
EXPORTY = ["AcquireDDThreadLock", "CompleteCreateSysmemSurface", "D3DParseUnknownCommand", "DDInternalLock",
           "DDInternalUnlock", "DirectDrawCreate", "DirectDrawCreateClipper", "DirectDrawCreateEx",
           "DirectDrawEnumerateA", "DirectDrawEnumerateExA", "DirectDrawEnumerateExW", "DirectDrawEnumerateW",
           "DllCanUnloadNow", "DllGetClassObject", "ReleaseDDThreadLock"]

ROI_RVA = 0x6C460
HAK_START, HAK_START_SPAT = 0x44198E, 0x441995
HAK_KONIEC, HAK_KONIEC_SPAT = 0x441FEA, 0x441FF4
SIRKA, VYSKA = 800, 600

# Kód je nezávislý od polohy: každý blok si zistí vlastnú adresu (call/pop) a ostatné odvodí od nej.
# {X} sa nahradí posunom (O_X - poloha návestia) – rieši funkcia preloz().
KOD = """
dllmain:
    cmp dword ptr [esp+8], 1
    jne dm_von
    pushad
    call dm_tu
dm_tu:
    pop ebx
    mov esi, dword ptr [esp + 36]
    push 260
    lea edi, [ebx + {CESTA}]
    push edi
    push esi
    call dword ptr [ebx + {IAT_GMFN}]
    test eax, eax
    jz dm_hacky
    lea ecx, [edi + eax]
dm_lomka:
    dec ecx
    cmp ecx, edi
    jb dm_hacky
    cmp byte ptr [ecx], 0x5c
    jne dm_lomka
    inc ecx
    mov edi, ecx
    lea esi, [ebx + {INIMENO}]
dm_kopia:
    lodsb
    stosb
    test al, al
    jnz dm_kopia
    lea eax, [ebx + {CESTA}]
    push eax
    push 1
    lea eax, [ebx + {KLUC}]
    push eax
    lea eax, [ebx + {SEKCIA}]
    push eax
    call dword ptr [ebx + {IAT_GPPI}]
    test eax, eax
    jz dm_koniec
dm_hacky:
    cmp dword ptr [0x44198e], 0x51343d83
    jne dm_koniec
    cmp dword ptr [0x441fea], 0x83ec8b55
    jne dm_koniec
    cmp dword ptr [0x441fee], 0x5851203d
    jne dm_koniec
    push 0
    push esp
    push 0x40
    push 0x2000
    push 0x441000
    call dword ptr [ebx + {IAT_VP}]
    test eax, eax
    jz dm_uprac
    mov byte ptr [0x44198e], 0xe9
    lea eax, [ebx + {START}]
    sub eax, 0x441993
    mov dword ptr [0x44198f], eax
    mov word ptr [0x441993], 0x9090
    mov byte ptr [0x441fea], 0xe9
    lea eax, [ebx + {KONIEC}]
    sub eax, 0x441fef
    mov dword ptr [0x441feb], eax
    mov dword ptr [0x441fef], 0x90909090
    mov byte ptr [0x441ff3], 0x90
    mov eax, [esp]
    push esp
    push eax
    push 0x2000
    push 0x441000
    call dword ptr [ebx + {IAT_VP}]
dm_uprac:
    add esp, 4
dm_koniec:
    popad
dm_von:
    mov eax, 1
    ret 12

start:
    pushad
    call st_tu
st_tu:
    pop ebx
    cmp dword ptr [0x58510c], 0
    jg st_von
    cmp dword ptr [0x585114], 800
    jl st_von
    cmp dword ptr [0x585110], 0
    jle st_von
    lea eax, [ebx + {DGMENO}]
    push eax
    call dword ptr [ebx + {IAT_GMH}]
    test eax, eax
    jz st_von
    lea edi, [eax + 0x6c460]
    cmp dword ptr [edi - 0x18], 800
    jne st_von
    cmp dword ptr [edi - 0x14], 600
    jne st_von
    cmp dword ptr [ebx + {AKTIVNY}], 0
    jne st_nastav
    push edi
    mov esi, edi
    lea edi, [ebx + {ULOZENY}]
    mov ecx, 4
    cld
    .byte 0xf3, 0xa5
    pop edi
    mov dword ptr [ebx + {AKTIVNY}], edi
st_nastav:
    mov dword ptr [edi], 0
    mov eax, dword ptr [0x585110]
    mov dword ptr [edi + 4], eax
    mov dword ptr [edi + 8], 800
    mov eax, dword ptr [0x585118]
    cmp eax, 600
    jle st_ok
    mov eax, 600
st_ok:
    mov dword ptr [edi + 12], eax
st_von:
    popad
    cmp dword ptr [0x585134], 0
    push 0x441995
    ret

koniec:
    pushad
    call ko_tu
ko_tu:
    pop ebx
    mov edi, dword ptr [ebx + {AKTIVNY}]
    test edi, edi
    jz ko_von
    lea esi, [ebx + {ULOZENY}]
    mov ecx, 4
    cld
    .byte 0xf3, 0xa5
    mov dword ptr [ebx + {AKTIVNY}], 0
ko_von:
    popad
    push ebp
    mov ebp, esp
    cmp dword ptr [0x585120], 0
    push 0x441ff4
    ret
"""

POSUNY = {"IAT_VP": O_IAT_VP, "IAT_GMH": O_IAT_GMH, "IAT_GMFN": O_IAT_GMFN, "IAT_GPPI": O_IAT_GPPI,
          "DGMENO": O_DGMENO, "AKTIVNY": O_AKTIVNY, "ULOZENY": O_ULOZENY,
          "SEKCIA": O_SEKCIA, "KLUC": O_KLUC, "INIMENO": O_INIMENO, "CESTA": O_CESTA}


def preloz():
    """Preloží KOD. Posuny k dátam sa počítajú od návestia *_tu bloku (adresa z call/pop).

    Návestia sa nájdu ako tri inštrukcie `call +0` (E8 00 00 00 00); všetky posuny sú > 127,
    takže majú vždy 32-bitový tvar (keystone pri rozdiele návestí počíta zle, preto sa nepoužíva) a dĺžka kódu sa medzi prechodmi nemení."""
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    poradie = ["dm_tu", "st_tu", "ko_tu"]
    bloky = dict.fromkeys(poradie, 0)
    for _ in range(3):
        riadky, aktualne = [], None
        for r in KOD.splitlines():
            if r.strip()[:-1] in bloky and r.strip().endswith(":"):
                aktualne = r.strip()[:-1]
            # štart/koniec = 6 bajtov pred svojím návestím *_tu (pushad + call)
            posuny = dict(POSUNY, START=bloky["st_tu"] - 6, KONIEC=bloky["ko_tu"] - 6)
            for k, v in posuny.items():
                r = r.replace("{" + k + "}", str(v - bloky[aktualne]) if aktualne else "")
            riadky.append(r)
        kod = bytes(ks.asm(chr(10).join(riadky), 0)[0])
        polohy = [m.start() + 5 for m in re.finditer(re.escape(bytes([0xE8, 0, 0, 0, 0])), kod)]
        assert len(polohy) == 3, polohy
        nove = dict(zip(poradie, polohy))
        if nove == bloky:
            return kod
        bloky = nove
    raise RuntimeError("návestia sa neustálili")


def zostav():
    kod = preloz()
    assert len(kod) <= O_DATA, len(kod)
    s = bytearray(O_KONIEC)
    s[O_KOD:O_KOD + len(kod)] = kod
    for o, t in ((O_DGMENO, CIEL + ".dll"), (O_SEKCIA, INI_SEKCIA), (O_KLUC, INI_KLUC), (O_INIMENO, INI_MENO)):
        b = (t + "\0").encode()
        assert len(b) <= 0x10
        s[o:o + len(b)] = b

    # import KERNEL32.dll (hint 0 + meno)
    p, mena = O_MENA, []
    for f in IMPORTY:
        b = b"\0\0" + f.encode() + b"\0"
        mena.append(p); s[p:p + len(b)] = b; p += (len(b) + 1) & ~1
    dllm = p
    s[dllm:dllm + 13] = b"KERNEL32.dll\0"
    assert dllm + 13 <= O_EXPORT and O_ILT + 4 * len(IMPORTY) + 4 <= O_IAT and O_IAT + 4 * len(IMPORTY) + 4 <= O_MENA
    struct.pack_into("<IIIII", s, O_IMPORT, RVA + O_ILT, 0, 0, RVA + dllm, RVA + O_IAT)
    for i, m in enumerate(mena):
        struct.pack_into("<I", s, O_ILT + 4 * i, RVA + m)
        struct.pack_into("<I", s, O_IAT + 4 * i, RVA + m)

    # export: všetko ako forwarder "dgddraw.Meno"
    n = len(EXPORTY)
    o_fn = O_EXPORT + 40
    o_mena = o_fn + 4 * n
    o_ord = o_mena + 4 * n
    o_txt = o_ord + 2 * n
    p = o_txt
    meno_dll = p
    s[p:p + 10] = b"DDraw.dll\0"; p += 10
    adr_mien, adr_fw = [], []
    for e in EXPORTY:
        b = (e + "\0").encode(); adr_mien.append(p); s[p:p + len(b)] = b; p += len(b)
        b = (f"{CIEL}.{e}\0").encode(); adr_fw.append(p); s[p:p + len(b)] = b; p += len(b)
    exp_dlzka = p - O_EXPORT
    assert p <= O_CESTA
    assert EXPORTY == sorted(EXPORTY)
    struct.pack_into("<IIHHIIIIIII", s, O_EXPORT, 0, 0, 0, 0, RVA + meno_dll, 1, n, n,
                     RVA + o_fn, RVA + o_mena, RVA + o_ord)
    for i in range(n):
        struct.pack_into("<I", s, o_fn + 4 * i, RVA + adr_fw[i])
        struct.pack_into("<I", s, o_mena + 4 * i, RVA + adr_mien[i])
        struct.pack_into("<H", s, o_ord + 2 * i, i)
    # prázdna tabuľka presunov (kód je nezávislý od polohy) – knižnica sa dá načítať kamkoľvek
    o_rel = (p + 3) & ~3
    struct.pack_into("<IIHH", s, o_rel, 0, 12, 0, 0)
    assert o_rel + 12 <= O_CESTA

    surove = (len(s) + 0x1FF) & ~0x1FF
    virt = (len(s) + 0xFFF) & ~0xFFF
    h = bytearray(0x200)
    h[0:2] = b"MZ"
    struct.pack_into("<I", h, 0x3C, 0x40)
    pe = 0x40
    h[pe:pe + 4] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", h, pe + 4, 0x14C, 1, 0, 0, 0, 0xE0, 0x2102)
    o = pe + 24
    struct.pack_into("<HBBIIIIII", h, o, 0x10B, 6, 0, surove, 0, 0, RVA + O_KOD, RVA, RVA)
    struct.pack_into("<IIIHHHHHHIIIIHHIIIIII", h, o + 28, 0x10000000, 0x1000, 0x200, 4, 0, 0, 0, 4, 0, 0,
                     RVA + virt, 0x200, 0, 2, 0x40, 0x100000, 0x1000, 0x100000, 0x1000, 0, 16)
    struct.pack_into("<II", h, o + 96 + 8 * 0, RVA + O_EXPORT, exp_dlzka)   # export
    struct.pack_into("<II", h, o + 96 + 8 * 1, RVA + O_IMPORT, 40)          # import
    struct.pack_into("<II", h, o + 96 + 8 * 5, RVA + o_rel, 12)             # presuny
    struct.pack_into("<II", h, o + 96 + 8 * 12, RVA + O_IAT, 4 * len(IMPORTY) + 4)            # IAT
    sek = o + 0xE0
    h[sek:sek + 8] = b".text\0\0\0"
    struct.pack_into("<IIIIIIHHI", h, sek + 8, len(s), RVA, surove, 0x200, 0, 0, 0, 0, 0xE0000060)
    return bytes(h) + bytes(s).ljust(surove, b"\0")


if __name__ == "__main__":
    vystup = sys.argv[1] if len(sys.argv) > 1 else "DDraw.dll"
    d = zostav()
    open(vystup, "wb").write(d)
    print(f"{vystup}: {len(d)} B")
