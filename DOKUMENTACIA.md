# Black Mirror (Posel smrti) – bezokrajový fullscreen + pomer strán 4:3

Hra: `D:\Hry\Steam\steamapps\common\Black Mirror` (engine AGDS, `agds.exe`, DirectDraw 7, vnútorné rozlíšenie 800×600, `agds.cfg: videomode=800x600x32`).

## Riešenie
- **dgVoodoo2 2.87.6** (`dgvoodoo/DDraw.dll`, `D3DImm.dll` z `MS/x86`) – DirectDraw sa prekladá na Direct3D 11.
- `dgVoodoo.conf` (zmeny oproti predvolenému):
  - `ScalingMode = stretched_ar` – roztiahnutie so zachovaním pomeru 4:3 (pri 1920×1080 obraz 1440×1080, po bokoch čierne pásy 240 px)
  - `FullscreenAttributes = fake` – bezokrajové okno veľkosti obrazovky namiesto exkluzívneho fullscreenu (Alt+Tab bez prepínania režimu)
  - `dgVoodooWatermark = false`, `ForceVerticalSync = true`
  - `Resampling = bilinear` (predvolené) – mierka 1,8× nie je celočíselná, preto vyhladenie
- **Príznak `~ HIGHDPIAWARE`** v `HKCU\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers` pre `agds.exe`. Bez neho pri škálovaní Windows 125 % vyšlo okno 2400×1350 a obraz bol posunutý vpravo dole.
- `DisplayROI = (800|600), pos:(0|0)` – výslovne celý obraz; doplnok pre filmy tento výrez počas filmu mení (pri prázdnej hodnote by dgVoodoo výrez nemusel používať).
- Exe hry ani `agds.cfg` sa na disku nemenia.

## Filmy na celú šírku (doplnok DDraw.dll)
CGI filmy sú širokouhlé (napr. úvod 800×363), hra ich kreslí do stredu obrazu 800×600 s čiernymi pásmi. Počas filmu sa preto zväčšuje len pás filmu – pri 1920×1080 na 1920×870, bez deformácie.

- Hra (agds.exe) pri štarte filmu uloží obdĺžnik filmu do `0x58510c..0x585118` (ľavý, horný, pravý, dolný) vo funkcii `0x4416bb`; film končí funkciou `0x441fea`.
- dgVoodoo 2.87.6 má výrez (DisplayROI) ako RECT v `dgddraw.dll` + `0x6c460`, 0x18 bajtov pred ním je šírka a výška režimu (800, 600). Výrez sa číta pri každom snímku, takže zmena za behu sa prejaví okamžite.
- `nastroje/zostav_dll.py` vyrobí malú `DDraw.dll` (3 kB, skladaná v Pythone cez keystone, bez prekladača):
  - všetkých 15 exportov prepošle na `dgddraw.dll` (pôvodný dgVoodoo DDraw.dll, len premenovaný),
  - pri načítaní overí bajty v agds.exe a v pamäti vloží 2 skoky: `0x44198e` (štart filmu, po nastavení obdĺžnika) a `0x441fea` (koniec filmu),
  - štart: ak film zaberá celú šírku (ľavý ≤ 0, pravý ≥ 800) a má letterbox (horný > 0), uloží pôvodný výrez a nastaví výrez = obdĺžnik filmu; koniec: vráti pôvodný výrez,
  - iná verzia hry alebo dgVoodoo → nerobí nič (kontrola bajtov exe a hodnôt 800/600 pri výreze).
- **Zapnutie/vypnutie:** `config.ini` v priečinku hry (vedľa `DDraw.dll`):
  ```ini
  [Movies]
  FullWidth=1     ; 1 = filmy na celú šírku, 0 = filmy v rámci 4:3 ako v pôvodnej hre
  ```
  Číta sa pri štarte hry (`GetPrivateProfileIntA`, cesta sa skladá z umiestnenia knižnice cez `GetModuleFileNameA`, takže nezáleží na pracovnom priečinku). Pri 0 sa háky vôbec nevložia. Keď súbor chýba, platí 1. `install.bat` existujúci `config.ini` neprepíše, `uninstall.bat` ho zmaže.
  Overené 19. 11. 2026: pri 0 sú v pamäti pôvodné bajty exe, pri 1 aj bez súboru sú háky vložené.
- Znovuzostavenie: `build_plugin.bat`. Pozor: keystone zle počíta rozdiel návestí (`a - b`) a nepozná `rep movsd` – v zdroji sa to obchádza.
- Pomocné nástroje: `nastroje/rozbor.py` (reťazce, odkazy, disassembly exe), `nastroje/pamat.py` (čítanie/zápis pamäte bežiacej hry, moduly 32-bit procesu).

## Myš
Hra číta myš zo správ okna (WM_MOUSEMOVE), `GetCursorPos` neimportuje. dgVoodoo drží fyzický kurzor v priestore 800×600 a mapuje ho na zväčšený obraz – v hre to funguje správne. Pri automatickom teste treba `SetCursorPos` volať so súradnicami hry (0–799, 0–599), nie obrazovky.

## Zvyšky na obrazovke (optimizedraw=0)
Hra štandardne posiela na obrazovku len zmenené obdĺžniky (voľba `optimizedraw=1` v agds.cfg, premenná 0x488080; funkcia zobrazenia 0x43e78f robí Blt zadného povrchu 0x597e60 do primárneho 0x597e5c). S dgVoodoo pritom ostávali zvyšky – napr. nápis „do spcke knihovněstnosti“ (dva nápisy cez seba) po rýchlom pohybe kurzora v hale. Pri `optimizedraw=0` sa každú snímku pošle celý obraz jedným Blt – po troch rýchlych prechodoch kurzorom žiadne zvyšky (overené 19. 11. 2026, save.1, hala).
`install.bat` dopíše `optimizedraw=0` a `videomem=0` na koniec agds.cfg (každú len ak tam ešte nie je), `uninstall.bat` tieto riadky odstráni (súbor je potom zhodný s pôvodným, záloha v `zaloha/agds.cfg`).

## Časovanie enginu
- Hlavná slučka 0x44218d: PeekMessage → ak nie je správa, snímka 0x4413db = logika 0x402dfb + zobrazenie 0x43e78f.
- 0x402dfb pri `normalize_speed=1` (0x488078, predvolené) čaká aktívne (QPC + SleepEx(0)) na tik **1/25 s** (pri `slowcomp` 2/25 s). Zmerané za behu: 25 cyklov/s. Všetko (animácie, chôdza, kurzor) je viazané na tento tik – zrýchlenie tiku by zrýchlilo celú hru.
- Poloha myši: 0x506ff0 (x), 0x506fa8 (y) v súradniciach 800×600, nastavuje ju WM_MOUSEMOVE v okennej procedúre 0x440c79. Kurzor je softvérový, kreslí ho hra do snímky (systémový kurzor skrýva: ShowCursor(0), SetCursor(0) v 0x441446 a pri WM_SETCURSOR).
- Voľby agds.cfg (tabuľka v 0x4027xx): optimizeway, optimizedraw, slowcomp, debug, sound, normalize_sample, normalize_speed, oldscr, extedit, path, help, loglevel, freemem, videomode, transparency, precisemove, debug_grab, shadow_min, shadow_max, fade_type, videomem, loguseractions, widevideo, film_test, film_yuy2, film_switch, charset, empty_slot, force_soft_indent.

## Plynulý kurzor (config.ini [Cursor] Fps)
Logika hry beží na 25 tikoch/s (animácie, chôdza – tak je hra nakreslená, zrýchlenie tiku by zrýchlilo celú hru). Kurzor je však objekt scény a doplnok ho prekresľuje aj medzi tikmi:
- hák na 0x43cfee (obal `SleepEx(0)` – volá sa len v slučke, kde logika čaká na ďalší tik): najviac raz za 3/4 z 1/Fps prečíta `GetCursorPos` (dgVoodoo drží kurzor v súradniciach hry 800×600); ak sa myš pohla a hra je v scéne (0x584ff8 ≠ 0, nie film 0x58512c, 0x49bde0 = 0, 0x49eb48 = 0, `0x43cf49()` = 0), zapíše polohu ako WM_MOUSEMOVE (0x507010/14), zavolá 0x417a8d, pripočíta posun scény (`[0x49eb1c]+0x5d5/0x5d9`), presunie objekt kurzora `0x4094de(0)`, prekreslí `0x426c43([0x49eb1c])` a zobrazí `0x43e78f`,
- neprekresľuje, ak do tiku ostávajú < 2 ms (čas posledného tiku: QPC v 0x49bda0),
- hák na 0x402fa1 (plánovanie tiku): pôvodne „posledný tik = teraz“, takže každé oneskorenie (zobrazenie s vsync čaká až 16 ms) hru natrvalo spomalí; teraz „posledný = plánovaný čas“, pri oneskorení ≥ 1 tik (načítanie) „teraz“,
- `Fps=0` → háky kurzora a tiku sa nevložia.

**Nutné `videomem=0` v agds.cfg** (zadný povrch v systémovej pamäti). Pri predvolenom `videomem=1` je povrch v pamäti grafiky a softvérový renderer ho cez dgVoodoo zamyká → jedno prekreslenie ~33 ms (s plynulým kurzorom spadla hra na 15 tikov/s). Pri `videomem=0`: prekreslenie pár ms. `install.bat` dopíše `videomem=0` (ak chýba), `uninstall.bat` ho odstráni.

Merania (19. 11. 2026, save.1 hala, myš krúži cez SetCursorPos, vsync dgVoodoo zapnutý, monitor 60 Hz):
| verzia | slučka hry | prekreslení kurzora navyše | spolu |
|---|---|---|---|
| videomem=1 | 15,3/s | 15,3/s | hra spomalená |
| videomem=0, bez ochrany tiku, bez vsync | 24,3/s | 57,6/s | |
| + ochrana 8 ms pred tikom, bez vsync | 25,0/s | 43,6/s | 69/s |
| + vsync | 24,0/s | 36,3/s | logika spomalená o 4 % |
| + ochrana 1/Fps + 2 ms | 25,0/s | 25,0–30,3/s | 50–55/s |
| **+ plánovanie tiku, ochrana 2 ms (finálne)** | **25,0/s** | **35,0/s** | **60/s** |

Chôdza postavy (hala, 2 trasy, 3×): bez pohybu myši 3,95 / 3,35 s, s krúžiacou myšou 3,97–4,01 / 3,37–3,41 s – rozdiel v rámci presnosti merania (snímky ~70 ms). Animácie sa prekresľovaním nezrýchľujú. Overené aj inventár (lišta dole) – bez zvyškov.

Počítadlo prekreslení navyše: DDraw.dll + 0x1000 + 0x800 + 0x4C (na meranie, `nastroje/pamat.py`).

## Citlivosť kurzora (config.ini [Cursor] Sensitivity)
`Sensitivity=0.5` (predvolené), rozsah 0.1–1.0 (mimo rozsahu sa orezá, nečitateľná hodnota = 0.5; desatinná bodka aj čiarka). Násobok pohybu myši: 1.0 = rýchlosť pôvodnej hry.
- V tom istom háku 0x43cfee: pri každom volaní (stovky za sekundu počas čakania na tik) porovná `GetCursorPos` s naposledy nastavenou polohou, rozdiel vynásobí citlivosťou (počíta v tisícinách pixela, zlomky sa nestrácajú) a presunie kurzor `SetCursorPos`.
- Iba keď je hra v popredí (`GetForegroundWindow` = okno hry `[0x5850e8]`).
- Polohu načíta znova bez násobenia: keď kurzor presunie hra sama (hák na jej `SetCursorPos` v 0x43d203, 6 B `call [0x485280]` → `call` do doplnku + `nop`), po návrate do hry a po pauze dlhšej ako 5 tikov (načítanie, film).
- Pri `Sensitivity=1.0` sa citlivosť nespracúva vôbec a hák 0x43d203 sa nevkladá; pri `Fps=0` a `Sensitivity=1.0` sa nevkladá ani hák 0x43cfee.

Meranie (19. 11. 2026, hlavná ponuka, relatívny pohyb cez `SendInput` vrátane akcelerácie Windows, posun kurzora v px hry):
| Fps | Sensitivity | 160 mickey pomaly | 180 mickey rýchlo |
|---|---|---|---|
| 0 (pôvodná hra) | 1.0 | 164–165 | 461–462 |
| 60 | 1.0 | 165 | 461 |
| 60 | 0.5 | 80–81 | 230 |
| 0 | 0.5 | 83 | 230–231 |

Plynulý kurzor rýchlosť nemení (Fps 60 = pôvodná hra), citlivosť 0.5 presne polovičná.

## Inštalácia
- `install.bat` – skopíruje do hry `dgddraw.dll`, `DDraw.dll`, `D3DImm.dll`, `dgVoodoo.conf` a `config.ini` (ten len ak ešte neexistuje) a zapíše príznak DPI (voliteľný parameter: cesta k hre)
- `uninstall.bat` – súbory zmaže a príznak odstráni

## Overené v hre (19. 11. 2026, 1920×1080, Windows 125 %)
- okno 0,0–1920×1080 bez rámu, obraz x 240–1679 (= 1440×1080, 4:3)
- logo Unknown Identity, hlavná ponuka, úvodný film (AVI cez YUY2) – správne a vycentrované
- myš: zvýraznenie položky ponuky a klik na „Nová hra“

Filmy (19. 11. 2026): úvod po „Nová hra“ a „Kapitola I“ roztiahnuté na 1920×870 (y 104–974), po filme sa obraz vráti na 4:3 (prvá scéna x 240–1680). Logá na začiatku zostávajú malé v strede. Po kapitole je chvíľu čierna obrazovka s rozprávačom – to je pôvodné správanie hry.

Neskúšané: hranie samotné (scény, inventár, dialógy), ukladanie, Alt+Tab počas hry.
