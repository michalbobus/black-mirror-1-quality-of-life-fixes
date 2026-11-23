# Black Mirror (Posel smrti) – bezokrajový fullscreen + pomer strán 4:3

Hra: `D:\Hry\Steam\steamapps\common\Black Mirror` (engine AGDS, `agds.exe`, DirectDraw 7, vnútorné rozlíšenie 800×600, `agds.cfg: videomode=800x600x32`).

## Riešenie
- **dgVoodoo2 2.87.6** (`dgvoodoo/DDraw.dll`, `D3DImm.dll` z `MS/x86`) – DirectDraw sa prekladá na Direct3D 11.
- `dgVoodoo.conf` (zmeny oproti predvolenému):
  - `ScalingMode = stretched_ar` – roztiahnutie so zachovaním pomeru 4:3 (pri 1920×1080 obraz 1440×1080, po bokoch čierne pásy 240 px)
  - `FullscreenAttributes = fake` – bezokrajové okno veľkosti obrazovky namiesto exkluzívneho fullscreenu (Alt+Tab bez prepínania režimu)
  - `dgVoodooWatermark = false`, `ForceVerticalSync = true`
  - `Resampling = lanczos-3` (od 23. 11. 2026, predtým bilinear) – ostrejšie zväčšenie; hrany postáv vyhladzuje FXAA v doplnku ešte pred zväčšením (pozri Vyhladzovanie postáv)
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

Plynulý kurzor rýchlosť nemení (Fps 60 = pôvodná hra), citlivosť 0.5 presne polovičná. Od 23. 11. 2026 je predvolená citlivosť **0.7** (config.ini aj predvolená hodnota v kóde, keď kľúč chýba).

## Doplnok pohodlia (DDraw.dll v C, 23. 11. 2026)
Reťaz knižníc: hra → `DDraw.dll` (nový doplnok, `doplnok/bm_qol.c`) → všetky exporty preposlané na `bm_core.dll` (doterajší doplnok v assembleri: filmy, plynulý kurzor, citlivosť – len premenovaný) → `dgddraw.dll` (dgVoodoo2). Prekladá sa cez `zig cc` (Python balík `ziglang`), bez CRT, importuje len kernel32/user32; `doplnok/zostav.bat`, oba doplnky naraz `build_plugin.bat`.

Háky (v pamäti, pred zápisom sa overia pôvodné bajty; iná verzia exe → nič):
| adresa | čo | použitie |
|---|---|---|
| 0x402e21 `call 0x431cf8` | začiatok tiku logiky (25/s) | ESC, hotspoty, preskakovanie, koliesko, ladiaci kanál |
| 0x440e9d `call 0x43f278` | WM_KEYDOWN | ESC a medzerník |
| 0x44112b `call [DefWindowProcA]` | ostatné správy okna | WM_MOUSEWHEEL |
| 0x42e416, 0x43a228 `call 0x433708` | načítanie uloženej hry (slot) | obnova zapamätaných nastavení |
| 0x42b8af `call 0x43a112` | skript zapisuje celočíselnú systémovú premennú (meno, hodnota) | zapamätanie nastavení |
| 0x43e78f (začiatok, 9 B → mostík) | zobrazenie (Blt zadného povrchu) | FXAA pred zväčšením, značky hotspotov |

### config.ini
```ini
[Controls]
EscapeMenu=1      ; ESC v hre = ponuka
SpaceHotspots=1   ; podržaný medzerník = hotspoty
HoldToSkip=1      ; podržaný ESC/medzerník v rozhovore = preskakovanie + zrýchlenie
WheelInventory=1  ; koliesko = predmety inventára
[Video]
Smoothing=1       ; FXAA pred zväčšením (SmoothingThreshold=25, SmoothingThresholdMin=16, SmoothingSubpixel=75)
[Settings]
Remember=1        ; nastavenia nezávislé od uloženej hry
[Remembered]      ; zapisuje doplnok (tell_mode, tell_volume, sound_volume, music_volume, gamma)
[Debug]
Log=1             ; bm_qol.log v priečinku hry
Explore=1         ; prieskumné háky: logovanie akcie use (0x4311f7) a predmetu na kurzor (0x408d5a)
```
Chýbajúci kľúč = predvolená hodnota (zapnuté; Debug = 0), takže `install.bat` nemusí prepisovať existujúci config.ini.

### ESC → ponuka
Klik na ozubené kolieska = akcia „use“ objektu `1006.100c` (`0x4311f7(objekt, x, y)`). Objekt je v scéne len keď je myš pri hornom okraji, preto ho doplnok nájde (`0x406116(scéna, meno)`), prípadne načíta (`0x430052(meno, scéna, 1, 1)`) a zavolá jeho „use“. Po návrate do hry ho odstráni (`0x43040d(0, objekt, scéna)`), ak ho načítal sám a myš nie je hore (inak by kolieska ostali viditeľné). ESC v ponuke vracia do hry natívne. ESC sa takto správa len keď hráč ovláda hru (`0x4305d1() ≥ 1`, nie film, obrazovka nie je `1006.*`); inak ide hre (preskakovanie replík, filmov).

Obrazovky: `1006.100e` hlavná ponuka, `1006.1037` Nastavení, `1006.101b` nahrávanie, `10a1` hala; aktuálna = meno na začiatku objektu `[0x49eb1c]` (`nastroje/scena.py`).

### Hotspoty (medzerník)
Zoznam objektov scény: kruhový zoznam `scéna+0x40` (prvý `[+0x28]`, ďalší `[objekt+0]`). Objekt: meno `+8`, aktívny `+0x34`, poradie `+0x2c`, región `+0x72`, názov (text pri prejdení myšou) `+0x7a`, obsluha use `+0xb5`, posuny `+0x3a/+0x3e/+0x42/+0x46`, animácia `+0x7e`, postava `+0x82`. Región: stred `(+0, +2)` (short), ohraničenie x `+0xA..+0xC`, y `+0xE..+0x10`. Hit-test 0x4034b0 (x, y, scéna, 0) → objekt pod kurzorom (`scéna+0x5ed`).
Hotspot = aktívny objekt s regiónom a neprázdnym názvom, okrem `inv.*` a predmetu na kurzore. Poloha = stred regiónu prepočítaný opačne ako v hit-teste (+0x42/+0x46, animácia/postava, mínus posun scény +0x5d5/+0x5d9). Zbierajú sa každý tik, kým je medzerník držaný; značka (krúžok 21×21 px, svetlá zlatá s tmavým lemom) sa nakreslí do zadného povrchu tesne pred Blt a hneď potom sa pôvodné pixely vrátia (hra prekresľuje len zmenené časti). Vyžaduje 32-bit povrch (videomode …x32).
Overené: hala – obraz, tabuľka podstavca, východy, dvere, stolík; po pustení bez zvyškov (`nastroje/objekty.py` vypíše objekty aj s regiónmi).

### Podržanie ESC / medzerníka v rozhovore
Natívne: ESC aj medzerník počas reči preskočia repliku (cesta 0x43f278 → udalosť 0x4c). Doplnok počas držania (hráč nemá kontrolu, nie film, nie ponuka) v každom tiku pošle hre stlačenie ESC (`0x43f278(VK_ESCAPE, skenkód 1)`) a posunie čas posledného tiku (`[0x49bda0]`, QPC) o 1/25 s dozadu, takže logika nečaká na ďalší tik – animácie medzi replikami bežia čo najrýchlejšie (obmedzuje ich zobrazenie s vsync).
Meranie (úvodný rozhovor po Nová hra, od scény po kontrolu hráča, `nastroje/test/uvod_test.py`):
| akcia | čas |
|---|---|
| nič | 158,0 s |
| ESC / medzerník stláčané každých 0,4 s (pôvodná hra) | 44,7 s |
| **ESC / medzerník podržaný (doplnok)** | **15,6 s** |
Po preskočení je hra v rovnakom stave ako bez neho (hala, ako save.1).

`tell_mode` (0x48d458) je bitová maska: bit 0 = text, bit 1 = hlas (3 = titulky zapnuté, 2 = vypnuté). Funkcia reči 0x438d58.

### Koliesko myši – inventár
Pole inventára `0x578c10`: 35 položiek po 0x28 B (meno[32], `+0x20` = 1 obsadené, `+0x24` = −1). Predmet na kurzore `[0x49f3e0]`; pripnutím sa z poľa vyberie (miesto ostane prázdne), vrátením (pravý klik) sa vráti na to isté miesto – poradie je stabilné. Inventár povolený: `[0x48d2d8] > 0`.
Koliesko dole = ďalší predmet, hore = predchádzajúci (cyklicky; bez predmetu na kurzore dole = prvý, hore = posledný). Ak je predmet na kurzore, najprv sa vráti udalosťou pravého tlačidla (`0x417949(0x50703c)`, ako skutočný pravý klik), počká sa, kým kurzor nie je prázdny, a potom sa vyberie cieľ: objekt predmetu sa nájde alebo načíta do scény a zavolá sa jeho „use“ (to isté ako klik na predmet v lište; skript potom volá `0x408d5a(scéna, objekt, 1)`). Overené: listovanie oboma smermi, lišta potom zobrazuje predmety správne, v scéne neostávajú navyše objekty.

### Zapamätané nastavenia
Štartovací skript `main` pri **každom spustení hry** nastaví `tell_mode=2` (titulky vypnuté), `tell_volume=85`, `sound_volume=100`, `music_volume=80`; uložená hra obsahuje systémové premenné a pri načítaní ich prepíše (napr. save.1 mal `sound_volume=5`).
Tabuľka systémových premenných: `0x48d470`, záznamy po 0x2D B (meno[32], ukazovateľ na hodnotu, ukazovateľ 2, príznak 1 = číslo, funkcia pri zmene), `nastroje/sysvar.py` ju vypíše aj s hodnotami. Zápis zo skriptu `0x43a112(meno, hodnota)`, čítanie `0x43a19f`, návrat na predvolenú `0x439f81`, nová hra `0x43a627`.
Doplnok: zmena na obrazovke Nastavení (`1006.1037`) sa zapíše do `[Remembered]`; zápis zo skriptu mimo Nastavení sa zablokuje pri `tell_mode` vždy, pri hlasitostiach a game len počas štartovacieho skriptu `main` (neskoršie zámerné zmeny počas hry ostanú); po prvom tiku a po načítaní hry sa zapamätané hodnoty vrátia a zavolá sa funkcia premennej (hlasitosť zvuku 0x439c6d, hudby 0x439c47; gamu prepočítava hra pri prekreslení, použitá hodnota v 0x650a30).
Posuvník zvuku mení `sound_volume` aj `music_volume`. Posuvníky sa ovládajú klikom na guľku a potom na čiaru.
Overené 23. 11. 2026: titulky, reč 69, zvuk 79/hudba 63, gama −19 → reštart hry aj načítanie save.1 → hodnoty ostali.

### Ladenie
`nastroje/ladenie.py call ADRESA arg…` – doplnok exportuje štruktúru `ladenie`; Python do nej zapíše funkciu a argumenty (`s:text` = reťazec), doplnok ju zavolá v hernom vlákne pri ďalšom tiku a vráti výsledok. Ďalšie nástroje: `scena.py`, `objekty.py`, `podkurzorom.py`, `inventar.py`, `sysvar.py`; testy `test/seq.py` (klik, pravý klik, ťahanie, koliesko, klávesy, snímky + priebeh hlasitosti a titulkov), `test/hra_save.sh`, `test/uvod_test.py`.

## Vyhladzovanie postáv (23. 11. 2026)
Postavy sú v 800×600 so „schodíkmi“ na hranách; pri zväčšení na 1440×1080 (mierka 1,8×) to bije do očí. Zábery prvej scény (salón, štyri postavy) automaticky: `nastroje/test/zaber.sh MENO RESAMPLING ISF [SMOOTHING]` (nová hra, preskočenie filmov, čakanie na scénu), porovnanie výrezov `nastroje/test/porovnaj.py`. Zábery v `snimky/profily`, porovnania v `snimky/porovnanie`.

Filtre dgVoodoo (`Resampling`):
| profil | výsledok |
|---|---|
| pointsampled | kockaté, nerovnomerné pixely (1,8×) |
| bilinear (pôvodné) | mäkké, schody len rozmazané |
| bicubic, lanczos-2, lanczos-3 | ostrejšie, schody na hranách vlasov a oblečenia ostávajú viditeľné |
| ImageScaleFactor=2 + bilinear | skoro ako pointsampled – nevhodné |

Žiadny filter dgVoodoo hrany nevyhladí, preto **vyhladenie pred zväčšením v doplnku DDraw.dll** (`[Video] Smoothing=1`): FXAA 3.11 (kvalitná verzia s hľadaním koncov hrany) nad snímkou 800×600 v háku zobrazenia 0x43e78f:
- snímka zo zadného povrchu sa skopíruje (zdroj filtra aj záloha), FXAA počíta do vlastného buffera, do povrchu sa zapíšu len zmenené riadky, po Blt na obrazovku sa pôvodná snímka vráti (hra prekresľuje len zmenené časti, inak by sa vyhladenie hromadilo),
- jas = (77 R + 150 G + 29 B) / 256; hrana, ak rozdiel jasu v okolí ≥ max(`SmoothingThresholdMin` = 16, `SmoothingThreshold` = 25 % maxima); subpixelové vyhladenie `SmoothingSubpixel` = 75 %; hľadanie konca hrany 7 krokov (1, 1, 1, 2, 2, 4, 8 px),
- výpočet v celých číslach, 2 fázy (jas, FXAA) rozdelené na pásy riadkov: herné vlákno + 2 pracovné vlákna (počet jadier − 1, najviac 4),
- počas filmov sa nepoužíva.
Prah 25 % v hale: ~116 tisíc hranových pixelov, 4,4–4,7 ms na snímku; prah 35 %: 66 tisíc, 3,2 ms. Prvá verzia (desatinné čísla, jedno vlákno, prah 1/8) trvala 22–25 ms – nepoužiteľné.
Plynulosť (krúženie myšou v hale, `nastroje/test/plynulost.py`): s FXAA aj bez 25,0 tikov/s a 59,4–60,0 zobrazení/s.

**Výber:** `Resampling = lanczos-3` + FXAA s prahom 25 % (predvolené). Hrany postáv, stoličiek a rámov sú hladké, textúry (koberec, tapety) ostávajú detailné (`snimky/porovnanie/4_lanczos3_vs_fxaa25_1na1.png`). Alternatívy: mäkšie `bicubic` alebo pôvodné `bilinear` v dgVoodoo.conf; vyšší `SmoothingThreshold` = menej vyhladených hrán. Overené aj spolu s hotspotmi (značky sa kreslia po FXAA, potom sa vráti celá snímka).

Neskúšané (nebolo treba): ReShade (FXAA/SMAA by pracovalo až na zväčšenom obraze z dgVoodoo, nie pred zväčšením), zväčšovače xBR/ScaleFX/FSR (dgVoodoo vlastné shadery nepodporuje).

## Inštalácia
- `install.bat` – skopíruje do hry `dgddraw.dll`, `DDraw.dll`, `bm_core.dll`, `D3DImm.dll`, `dgVoodoo.conf` a `config.ini` (ten len ak ešte neexistuje) a zapíše príznak DPI (voliteľný parameter: cesta k hre)
- `uninstall.bat` – súbory zmaže a príznak odstráni

## Overené v hre (19. 11. 2026, 1920×1080, Windows 125 %)
- okno 0,0–1920×1080 bez rámu, obraz x 240–1679 (= 1440×1080, 4:3)
- logo Unknown Identity, hlavná ponuka, úvodný film (AVI cez YUY2) – správne a vycentrované
- myš: zvýraznenie položky ponuky a klik na „Nová hra“

Filmy (19. 11. 2026): úvod po „Nová hra“ a „Kapitola I“ roztiahnuté na 1920×870 (y 104–974), po filme sa obraz vráti na 4:3 (prvá scéna x 240–1680). Logá na začiatku zostávajú malé v strede. Po kapitole je chvíľu čierna obrazovka s rozprávačom – to je pôvodné správanie hry.

Neskúšané: dlhšie hranie (ďalšie kapitoly), ukladanie cez ESC → Uložit hru, Alt+Tab počas hry.
