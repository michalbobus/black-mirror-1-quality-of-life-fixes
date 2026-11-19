"""Zostaví proxy DDraw.dll pre Black Mirror (agds.exe): filmy na celú šírku + plynulý kurzor.

Ako to funguje:
  * Hra importuje DDRAW.dll!DirectDrawCreateEx. Táto knižnica sa volá DDraw.dll a všetky exporty
    prepošle (forwarder) na dgVoodoo, ktorý je v priečinku hry premenovaný na dgddraw.dll.
  * Pri načítaní (DllMain) prečíta config.ini vedľa seba, overí bajty v agds.exe a vloží skoky do pamäte
    (exe na disku sa nemení):
      0x44198e  – štart filmu (hra práve uložila obdĺžnik filmu do 0x58510c..0x585118)
      0x441fea  – začiatok funkcie konca filmu
      0x43cfee  – obal SleepEx(0), volá sa len v slučke, kde logika čaká na ďalší tik (25 tikov/s)
  * [Movies] FullWidth=1: pri štarte filmu, ktorý zaberá celú šírku a má letterbox, nastaví výrez
    (DisplayROI) dgVoodoo na obdĺžnik filmu – dgVoodoo ho zväčší na celú šírku obrazovky; na konci výrez vráti.
    Výrez dgVoodoo 2.87.6: RECT v dgddraw.dll na RVA 0x6c460, 0x18 B pred ním šírka a výška režimu (800, 600).
  * [Cursor] Fps=60: počas čakania na tik najviac Fps-krát za sekundu prečíta polohu myši (GetCursorPos;
    dgVoodoo drží kurzor v súradniciach hry 800x600). Ak sa pohla a hra je v scéne, zapíše ju ako
    WM_MOUSEMOVE (0x507010/14), prepočíta ako tik (0x417a8d + posun scény), presunie objekt kurzora
    (0x4094de(0)), prekreslí scénu (0x426c43) a zobrazí ju (0x43e78f). Logika hry ostáva na 25 tikoch/s.
    Prekreslenie sa vynechá, ak do ďalšieho tiku ostávajú menej ako 2 ms (čas tiku: QPC v 0x49bda0).
  * Spolu s kurzorom: 0x402fa1 – plánovanie tiku. Hra po čakaní nastaví „posledný tik = teraz“, takže každé
    oneskorenie (napr. zobrazenie čakajúce na vsync) hru natrvalo spomalí. Hák nastaví „posledný = plánovaný čas“
    (oneskorenie sa dorovná pri ďalšom tiku); ak je oneskorenie aspoň 1 tik (načítanie a pod.), použije „teraz“. Pozor: bez videomem=0 v agds.cfg trvá prekreslenie ~33 ms a hru spomalí.
    Fps=0 -> prekresľovanie a hák plánovania tiku sa nevložia.
  * [Cursor] Sensitivity=0.5 (0.1..1.0): násobok pohybu myši, 1.0 = ako pôvodná hra. V tom istom háku (0x43cfee)
    sa pri každom volaní porovná GetCursorPos s naposledy nastavenou polohou, rozdiel sa vynásobí citlivosťou
    (presnosť 1/1000 px, zlomky sa zachovajú) a kurzor sa presunie SetCursorPos. Len keď je hra v popredí
    (GetForegroundWindow = okno hry 0x5850e8). Poloha sa znova načíta bez násobenia, keď hru presunie kurzor sama
    (hák na jej SetCursorPos v 0x43d203), po návrate do hry a po pauze dlhšej ako 5 tikov.

Použitie:  python zostav_dll.py VYSTUP.dll
"""
import re
import struct
import sys

import keystone

RVA = 0x1000
O_KOD, O_DATA, O_IMPORT, O_EXPORT, O_CESTA, O_KONIEC = 0x000, 0x800, 0xA00, 0xC00, 0x1000, 0x1200

# dáta (posuny od O_DATA)
DATA = {
    "AKTIVNY": 0x00,     # adresa RECT v dgVoodoo počas filmu, inak 0
    "ULOZENY": 0x04,     # pôvodný RECT (16 B)
    "TERAZ": 0x18, "TERAZ4": 0x1C,          # QPC teraz (8 B)
    "POSLEDNY": 0x20, "POSLEDNY4": 0x24,    # QPC posledného prekreslenia kurzora
    "PERIODA": 0x28,                        # najkratší odstup prekreslení: 3/4 z 1/Fps (tempo dáva vsync)
    "BOD": 0x30, "BOD4": 0x34,              # GetCursorPos
    "BODST": 0x38, "BODST4": 0x3C,          # posledná spracovaná poloha
    "FREKV": 0x40, "FREKV4": 0x44,          # QueryPerformanceFrequency
    "FPS": 0x48,
    "POCET": 0x4C,       # počet prekreslení kurzora mimo tiku (na meranie)
    "LIMIT": 0x50,       # QPC tiky od začiatku tiku, po ktorých sa už kurzor neprekresľuje (1/25 s - 2 ms)
    "TIK": 0x54,         # QPC tiky jedného tiku logiky (1/25 s)
    "CITL": 0x58,        # citlivosť v tisícinách (100..1000), 1000 = bez zmeny
    "RESYNC": 0x5C,      # 1 = znova načítať polohu kurzora (hra ho presunula, návrat do hry...)
    "VX": 0xC0, "VY": 0xC4,              # poloha kurzora v tisícinách pixela
    "LX": 0xC8, "LY": 0xCC,              # naposledy nastavená poloha kurzora (pixely)
    "CB": 0xD0, "CB4": 0xD4,             # GetCursorPos pre citlivosť
    "POSLV": 0xD8, "POSLV4": 0xDC,       # QPC posledného volania háku
    "TEXT": 0xE0,                        # text hodnoty Sensitivity (32 B)
    "K_SENS": 0x100, "D_SENS": 0x110,
    "DGMENO": 0x60,      # "dgddraw.dll"
    "S_MOVIES": 0x70, "K_FULLWIDTH": 0x80, "S_CURSOR": 0x90, "K_FPS": 0xA0, "INIMENO": 0xB0,
}
RETAZCE = {"DGMENO": "dgddraw.dll", "S_MOVIES": "Movies", "K_FULLWIDTH": "FullWidth",
           "S_CURSOR": "Cursor", "K_FPS": "Fps", "INIMENO": "config.ini",
           "K_SENS": "Sensitivity", "D_SENS": "0.5"}

IMPORTY = {
    "KERNEL32.dll": ["VirtualProtect", "GetModuleHandleA", "GetModuleFileNameA", "GetPrivateProfileIntA",
                     "QueryPerformanceCounter", "QueryPerformanceFrequency", "GetPrivateProfileStringA"],
    "USER32.dll": ["GetCursorPos", "SetCursorPos", "GetForegroundWindow"],
}
IAT_MENA = {"VirtualProtect": "IAT_VP", "GetModuleHandleA": "IAT_GMH", "GetModuleFileNameA": "IAT_GMFN",
            "GetPrivateProfileIntA": "IAT_GPPI", "QueryPerformanceCounter": "IAT_QPC",
            "QueryPerformanceFrequency": "IAT_QPF", "GetCursorPos": "IAT_GCP",
            "GetPrivateProfileStringA": "IAT_GPPS", "SetCursorPos": "IAT_SCP", "GetForegroundWindow": "IAT_GFW"}

CIEL = "dgddraw"
EXPORTY = ["AcquireDDThreadLock", "CompleteCreateSysmemSurface", "D3DParseUnknownCommand", "DDInternalLock",
           "DDInternalUnlock", "DirectDrawCreate", "DirectDrawCreateClipper", "DirectDrawCreateEx",
           "DirectDrawEnumerateA", "DirectDrawEnumerateExA", "DirectDrawEnumerateExW", "DirectDrawEnumerateW",
           "DllCanUnloadNow", "DllGetClassObject", "ReleaseDDThreadLock"]

# Kód je nezávislý od polohy: každý blok si zistí vlastnú adresu (call/pop) a dáta adresuje [ebx + {MENO}].
# Funkcie hry sa volajú cez register (mov eax, ADRESA / call eax), keystone prekladá od adresy 0.
# Bloky: dllmain, start (film), koniec (film), kurzor.
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
    jz dm_koniec
    lea ecx, [edi + eax]
dm_lomka:
    dec ecx
    cmp ecx, edi
    jb dm_koniec
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

    push 0
    push esp
    push 0x40
    push 0x41000
    push 0x402000
    call dword ptr [ebx + {IAT_VP}]
    test eax, eax
    jz dm_uprac

    lea eax, [ebx + {CESTA}]
    push eax
    push 1
    lea eax, [ebx + {K_FULLWIDTH}]
    push eax
    lea eax, [ebx + {S_MOVIES}]
    push eax
    call dword ptr [ebx + {IAT_GPPI}]
    test eax, eax
    jz dm_kurzor
    cmp dword ptr [0x44198e], 0x51343d83
    jne dm_kurzor
    cmp dword ptr [0x441fea], 0x83ec8b55
    jne dm_kurzor
    cmp dword ptr [0x441fee], 0x5851203d
    jne dm_kurzor
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

dm_kurzor:
    lea eax, [ebx + {CESTA}]
    push eax
    push 60
    lea eax, [ebx + {K_FPS}]
    push eax
    lea eax, [ebx + {S_CURSOR}]
    push eax
    call dword ptr [ebx + {IAT_GPPI}]
    test eax, eax
    jg dm_fps_ok
    xor eax, eax
dm_fps_ok:
    mov dword ptr [ebx + {FPS}], eax

    lea eax, [ebx + {CESTA}]
    push eax
    push 32
    lea eax, [ebx + {TEXT}]
    push eax
    lea eax, [ebx + {D_SENS}]
    push eax
    lea eax, [ebx + {K_SENS}]
    push eax
    lea eax, [ebx + {S_CURSOR}]
    push eax
    call dword ptr [ebx + {IAT_GPPS}]
    lea esi, [ebx + {TEXT}]
    xor eax, eax
    xor edi, edi
dm_cele:
    movzx ecx, byte ptr [esi]
    sub ecx, 0x30
    cmp ecx, 9
    ja dm_bodka
    imul eax, eax, 10
    add eax, ecx
    inc esi
    inc edi
    jmp dm_cele
dm_bodka:
    imul eax, eax, 1000
    movzx ecx, byte ptr [esi]
    cmp ecx, 0x2e
    je dm_desat
    cmp ecx, 0x2c
    jne dm_cislo
dm_desat:
    inc esi
    mov edx, 100
dm_desat_c:
    movzx ecx, byte ptr [esi]
    sub ecx, 0x30
    cmp ecx, 9
    ja dm_cislo
    imul ecx, edx
    add eax, ecx
    inc edi
    inc esi
    push eax
    mov eax, edx
    xor edx, edx
    mov ecx, 10
    div ecx
    mov edx, eax
    pop eax
    test edx, edx
    jnz dm_desat_c
dm_cislo:
    test edi, edi
    jnz dm_citl_rozsah
    mov eax, 500
dm_citl_rozsah:
    cmp eax, 100
    jge dm_citl_min
    mov eax, 100
dm_citl_min:
    cmp eax, 1000
    jle dm_citl_max
    mov eax, 1000
dm_citl_max:
    mov dword ptr [ebx + {CITL}], eax
    mov dword ptr [ebx + {RESYNC}], 1

    cmp dword ptr [ebx + {FPS}], 0
    jne dm_hak_kurzor
    cmp dword ptr [ebx + {CITL}], 1000
    jge dm_ochrana
dm_hak_kurzor:
    cmp dword ptr [0x43cfee], 0x6aec8b55
    jne dm_ochrana
    cmp dword ptr [0x43cff2], 0x08458b00
    jne dm_ochrana
    lea eax, [ebx + {FREKV}]
    push eax
    call dword ptr [ebx + {IAT_QPF}]
    test eax, eax
    jz dm_ochrana
    mov eax, dword ptr [ebx + {FREKV}]
    mov edx, dword ptr [ebx + {FREKV4}]
    mov ecx, 500
    cmp edx, ecx
    jae dm_ochrana
    div ecx
    imul ecx, eax, 20
    mov dword ptr [ebx + {TIK}], ecx
    imul eax, eax, 19
    mov dword ptr [ebx + {LIMIT}], eax
    mov ecx, dword ptr [ebx + {FPS}]
    test ecx, ecx
    jz dm_bez_fps
    mov eax, dword ptr [ebx + {FREKV}]
    mov edx, dword ptr [ebx + {FREKV4}]
    cmp edx, ecx
    jae dm_ochrana
    div ecx
    lea eax, [eax + eax * 2]
    shr eax, 2
    mov dword ptr [ebx + {PERIODA}], eax
dm_bez_fps:
    mov dword ptr [ebx + {BODST}], 0xffffffff
    mov dword ptr [ebx + {BODST4}], 0xffffffff
    mov byte ptr [0x43cfee], 0xe9
    lea eax, [ebx + {KURZOR}]
    sub eax, 0x43cff3
    mov dword ptr [0x43cfef], eax

    cmp dword ptr [ebx + {CITL}], 1000
    jge dm_tik
    cmp dword ptr [0x43d203], 0x528015ff
    jne dm_tik
    cmp word ptr [0x43d207], 0x0048
    jne dm_tik
    mov byte ptr [0x43d203], 0xe8
    lea eax, [ebx + {SYNCHAK}]
    sub eax, 0x43d208
    mov dword ptr [0x43d204], eax
    mov byte ptr [0x43d208], 0x90

dm_tik:
    cmp dword ptr [ebx + {FPS}], 0
    je dm_ochrana
    cmp dword ptr [0x402fa1], 0x49bda8a1
    jne dm_ochrana
    cmp dword ptr [0x402fa5], 0xbda0a300
    jne dm_ochrana
    mov byte ptr [0x402fa1], 0xe9
    lea eax, [ebx + {TIKHAK}]
    sub eax, 0x402fa6
    mov dword ptr [0x402fa2], eax

dm_ochrana:
    mov eax, [esp]
    push esp
    push eax
    push 0x41000
    push 0x402000
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

kurzor:
    pushad
    call ku_tu
ku_tu:
    pop ebx
    lea eax, [ebx + {TERAZ}]
    push eax
    call dword ptr [ebx + {IAT_QPC}]

    mov eax, dword ptr [ebx + {TERAZ}]
    mov edx, dword ptr [ebx + {TERAZ4}]
    sub eax, dword ptr [ebx + {POSLV}]
    sbb edx, dword ptr [ebx + {POSLV4}]
    mov ecx, dword ptr [ebx + {TERAZ}]
    mov dword ptr [ebx + {POSLV}], ecx
    mov ecx, dword ptr [ebx + {TERAZ4}]
    mov dword ptr [ebx + {POSLV4}], ecx
    cmp dword ptr [ebx + {CITL}], 1000
    jge ku_fps
    test edx, edx
    jnz ku_cs_sync
    mov ecx, dword ptr [ebx + {TIK}]
    lea ecx, [ecx + ecx * 4]
    cmp eax, ecx
    jae ku_cs_sync
    call dword ptr [ebx + {IAT_GFW}]
    cmp eax, dword ptr [0x5850e8]
    jne ku_cs_sync
    lea eax, [ebx + {CB}]
    push eax
    call dword ptr [ebx + {IAT_GCP}]
    test eax, eax
    jz ku_fps
    cmp dword ptr [ebx + {RESYNC}], 0
    jne ku_cs_nacitaj
    mov ecx, dword ptr [ebx + {CB}]
    sub ecx, dword ptr [ebx + {LX}]
    mov esi, dword ptr [ebx + {CB4}]
    sub esi, dword ptr [ebx + {LY}]
    mov eax, ecx
    or eax, esi
    jz ku_fps
    imul ecx, dword ptr [ebx + {CITL}]
    add ecx, dword ptr [ebx + {VX}]
    jge ku_cs_x0
    xor ecx, ecx
ku_cs_x0:
    cmp ecx, 799999
    jle ku_cs_x1
    mov ecx, 799999
ku_cs_x1:
    mov dword ptr [ebx + {VX}], ecx
    imul esi, dword ptr [ebx + {CITL}]
    add esi, dword ptr [ebx + {VY}]
    jge ku_cs_y0
    xor esi, esi
ku_cs_y0:
    cmp esi, 599999
    jle ku_cs_y1
    mov esi, 599999
ku_cs_y1:
    mov dword ptr [ebx + {VY}], esi
    mov eax, ecx
    xor edx, edx
    mov ecx, 1000
    div ecx
    mov edi, eax
    mov eax, esi
    xor edx, edx
    div ecx
    mov dword ptr [ebx + {LX}], edi
    mov dword ptr [ebx + {LY}], eax
    cmp edi, dword ptr [ebx + {CB}]
    jne ku_cs_nastav
    cmp eax, dword ptr [ebx + {CB4}]
    je ku_fps
ku_cs_nastav:
    push eax
    push edi
    call dword ptr [ebx + {IAT_SCP}]
    jmp ku_fps
ku_cs_sync:
    mov dword ptr [ebx + {RESYNC}], 1
    jmp ku_fps
ku_cs_nacitaj:
    mov eax, dword ptr [ebx + {CB}]
    mov dword ptr [ebx + {LX}], eax
    imul eax, eax, 1000
    add eax, 500
    mov dword ptr [ebx + {VX}], eax
    mov eax, dword ptr [ebx + {CB4}]
    mov dword ptr [ebx + {LY}], eax
    imul eax, eax, 1000
    add eax, 500
    mov dword ptr [ebx + {VY}], eax
    mov dword ptr [ebx + {RESYNC}], 0

ku_fps:
    cmp dword ptr [ebx + {FPS}], 0
    je ku_von
    mov eax, dword ptr [ebx + {TERAZ}]
    mov edx, dword ptr [ebx + {TERAZ4}]
    sub eax, dword ptr [ebx + {POSLEDNY}]
    sbb edx, dword ptr [ebx + {POSLEDNY4}]
    jnz ku_cas
    cmp eax, dword ptr [ebx + {PERIODA}]
    jb ku_von
ku_cas:
    mov eax, dword ptr [ebx + {TERAZ}]
    mov dword ptr [ebx + {POSLEDNY}], eax
    mov eax, dword ptr [ebx + {TERAZ4}]
    mov dword ptr [ebx + {POSLEDNY4}], eax
    mov eax, dword ptr [ebx + {TERAZ}]
    mov edx, dword ptr [ebx + {TERAZ4}]
    sub eax, dword ptr [0x49bda0]
    sbb edx, dword ptr [0x49bda4]
    jnz ku_von
    cmp eax, dword ptr [ebx + {LIMIT}]
    jae ku_von
    lea eax, [ebx + {BOD}]
    push eax
    call dword ptr [ebx + {IAT_GCP}]
    test eax, eax
    jz ku_von
    mov eax, dword ptr [ebx + {BOD}]
    mov edx, dword ptr [ebx + {BOD4}]
    cmp eax, dword ptr [ebx + {BODST}]
    jne ku_zmena
    cmp edx, dword ptr [ebx + {BODST4}]
    je ku_von
ku_zmena:
    mov dword ptr [ebx + {BODST}], eax
    mov dword ptr [ebx + {BODST4}], edx
    cmp eax, 0
    jl ku_von
    cmp eax, 800
    jge ku_von
    cmp edx, 0
    jl ku_von
    cmp edx, 600
    jge ku_von
    cmp dword ptr [0x584ff8], 0
    je ku_von
    cmp dword ptr [0x58512c], 0
    jne ku_von
    cmp dword ptr [0x49bde0], 0
    jne ku_von
    cmp dword ptr [0x49eb48], 0
    jne ku_von
    cmp dword ptr [0x49eb1c], 0
    je ku_von
    mov eax, 0x43cf49
    call eax
    test eax, eax
    jnz ku_von
    mov eax, dword ptr [ebx + {BOD}]
    mov dword ptr [0x507010], eax
    mov eax, dword ptr [ebx + {BOD4}]
    mov dword ptr [0x507014], eax
    mov eax, 0x417a8d
    call eax
    mov eax, dword ptr [0x49eb1c]
    mov ecx, dword ptr [eax + 0x5d5]
    add dword ptr [0x506ff0], ecx
    mov ecx, dword ptr [eax + 0x5d9]
    add dword ptr [0x506fa8], ecx
    push 0
    mov eax, 0x4094de
    call eax
    add esp, 4
    push dword ptr [0x49eb1c]
    mov eax, 0x426c43
    call eax
    add esp, 4
    mov eax, 0x43e78f
    call eax
    inc dword ptr [ebx + {POCET}]
ku_von:
    popad
    push ebp
    mov ebp, esp
    push 0
    push 0x43cff3
    ret

tikhak:
    pushad
    call ti_tu
ti_tu:
    pop ebx
    mov eax, dword ptr [0x49bda8]
    mov edx, dword ptr [0x49bdac]
    sub eax, dword ptr [ebp - 0x44]
    sbb edx, dword ptr [ebp - 0x40]
    jnz ti_teraz
    cmp eax, dword ptr [ebx + {TIK}]
    jae ti_teraz
    mov eax, dword ptr [ebp - 0x44]
    mov dword ptr [0x49bda0], eax
    mov eax, dword ptr [ebp - 0x40]
    mov dword ptr [0x49bda4], eax
    jmp ti_von
ti_teraz:
    mov eax, dword ptr [0x49bda8]
    mov dword ptr [0x49bda0], eax
    mov eax, dword ptr [0x49bdac]
    mov dword ptr [0x49bda4], eax
ti_von:
    popad
    mov eax, dword ptr [0x49bda8]
    mov ecx, dword ptr [0x49bdac]
    push 0x402fb7
    ret

synchak:
    pushad
    call sy_tu
sy_tu:
    pop ebx
    mov dword ptr [ebx + {RESYNC}], 1
    popad
    jmp dword ptr [0x485280]
"""

BLOKY = ["dm_tu", "st_tu", "ko_tu", "ku_tu", "ti_tu", "sy_tu"]


def rozlozenie_importov():
    """Vráti offsety IAT podľa mena funkcie a polohy tabuliek importov."""
    n_desk = len(IMPORTY) + 1
    o_ilt = O_IMPORT + 20 * n_desk
    pocet = sum(len(f) + 1 for f in IMPORTY.values())
    o_iat = o_ilt + 4 * pocet
    o_mena = o_iat + 4 * pocet
    iat = {}
    i = 0
    for dll, funkcie in IMPORTY.items():
        for f in funkcie:
            iat[IAT_MENA[f]] = o_iat + 4 * i
            i += 1
        i += 1
    return iat, o_ilt, o_iat, o_mena, 4 * pocet


IAT, O_ILT, O_IAT, O_MENA, IAT_DLZKA = rozlozenie_importov()


def preloz():
    """Preloží KOD. Posuny k dátam sa počítajú od návestia *_tu bloku (adresa z call/pop).

    Návestia sa nájdu ako inštrukcie `call +0` (E8 00 00 00 00). Rozdiel návestí (a - b) keystone
    počíta zle, preto sa posuny dopočítavajú tu; prekladá sa opakovane, kým sa polohy neustália."""
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    bloky = dict.fromkeys(BLOKY, 0x100)
    for _ in range(6):
        posuny = {k: O_DATA + v for k, v in DATA.items()}
        posuny.update(IAT)
        posuny["CESTA"] = O_CESTA
        # vstupy hákov = 6 bajtov pred návestím *_tu (pushad + call)
        posuny.update(START=bloky["st_tu"] - 6, KONIEC=bloky["ko_tu"] - 6, KURZOR=bloky["ku_tu"] - 6,
                      TIKHAK=bloky["ti_tu"] - 6, SYNCHAK=bloky["sy_tu"] - 6)
        riadky, aktualne = [], None
        for r in KOD.splitlines():
            s = r.strip()
            if s.endswith(":") and s[:-1] in bloky:
                aktualne = s[:-1]
            for k, v in posuny.items():
                if "{" + k + "}" in r:
                    r = r.replace("{" + k + "}", str(v - bloky[aktualne]))
            riadky.append(r)
        assert "{" not in "\n".join(riadky), [r for r in riadky if "{" in r]
        kod = bytes(ks.asm(chr(10).join(riadky), 0)[0])
        polohy = [m.start() + 5 for m in re.finditer(re.escape(bytes([0xE8, 0, 0, 0, 0])), kod)]
        assert len(polohy) == len(BLOKY), polohy
        nove = dict(zip(BLOKY, polohy))
        if nove == bloky:
            return kod
        bloky = nove
    raise RuntimeError("návestia sa neustálili")


def zostav():
    kod = preloz()
    assert len(kod) <= O_DATA, hex(len(kod))
    s = bytearray(O_KONIEC)
    s[O_KOD:O_KOD + len(kod)] = kod
    for k, t in RETAZCE.items():
        b = (t + "\0").encode()
        assert len(b) <= 0x10
        o = O_DATA + DATA[k]
        s[o:o + len(b)] = b

    # importy: deskriptory, ILT a IAT (rovnaký obsah), mená (hint 0 + meno), mená knižníc
    p = O_MENA
    i = 0
    for d, (dll, funkcie) in enumerate(IMPORTY.items()):
        zac = i
        for f in funkcie:
            b = b"\0\0" + f.encode() + b"\0"
            s[p:p + len(b)] = b
            struct.pack_into("<I", s, O_ILT + 4 * i, RVA + p)
            struct.pack_into("<I", s, O_IAT + 4 * i, RVA + p)
            p += (len(b) + 1) & ~1
            i += 1
        i += 1                      # nulová položka na konci zoznamu knižnice
        b = dll.encode() + b"\0"
        s[p:p + len(b)] = b
        struct.pack_into("<IIIII", s, O_IMPORT + 20 * d, RVA + O_ILT + 4 * zac, 0, 0, RVA + p,
                         RVA + O_IAT + 4 * zac)
        p += (len(b) + 1) & ~1
    assert p <= O_EXPORT, hex(p)

    # export: všetko ako forwarder "dgddraw.Meno"
    n = len(EXPORTY)
    o_fn = O_EXPORT + 40
    o_mena = o_fn + 4 * n
    o_ord = o_mena + 4 * n
    p = o_ord + 2 * n
    meno_dll = p
    s[p:p + 10] = b"DDraw.dll\0"
    p += 10
    adr_mien, adr_fw = [], []
    for e in EXPORTY:
        b = (e + "\0").encode(); adr_mien.append(p); s[p:p + len(b)] = b; p += len(b)
        b = (f"{CIEL}.{e}\0").encode(); adr_fw.append(p); s[p:p + len(b)] = b; p += len(b)
    exp_dlzka = p - O_EXPORT
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
    struct.pack_into("<II", h, o + 96 + 8 * 0, RVA + O_EXPORT, exp_dlzka)                # export
    struct.pack_into("<II", h, o + 96 + 8 * 1, RVA + O_IMPORT, 20 * (len(IMPORTY) + 1))  # import
    struct.pack_into("<II", h, o + 96 + 8 * 5, RVA + o_rel, 12)                          # presuny
    struct.pack_into("<II", h, o + 96 + 8 * 12, RVA + O_IAT, IAT_DLZKA)                  # IAT
    sek = o + 0xE0
    h[sek:sek + 8] = b".text\0\0\0"
    struct.pack_into("<IIIIIIHHI", h, sek + 8, len(s), RVA, surove, 0x200, 0, 0, 0, 0, 0xE0000060)
    return bytes(h) + bytes(s).ljust(surove, b"\0")


if __name__ == "__main__":
    vystup = sys.argv[1] if len(sys.argv) > 1 else "DDraw.dll"
    d = zostav()
    open(vystup, "wb").write(d)
    print(f"{vystup}: {len(d)} B")
