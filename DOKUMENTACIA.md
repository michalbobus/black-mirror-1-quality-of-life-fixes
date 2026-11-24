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
**Krok hry** = jeden krok logiky: hra 25-krát za sekundu (každých 40 ms) posunie animácie, chôdzu a časovače skriptov a spracuje vstupy. Nie je to snímka – vykreslený obraz sa s plynulým kurzorom posiela na obrazovku až 60-krát za sekundu, teda aj viackrát medzi dvoma krokmi.
- Hlavná slučka 0x44218d: PeekMessage → ak nie je správa, snímka 0x4413db = logika 0x402dfb + zobrazenie 0x43e78f.
- 0x402dfb pri `normalize_speed=1` (0x488078, predvolené) čaká aktívne (QPC + SleepEx(0)) na krok **1/25 s** (pri `slowcomp` 2/25 s). Zmerané za behu: 25 cyklov/s. Všetko (animácie, chôdza, kurzor) je viazané na tento krok – zrýchlenie kroku by zrýchlilo celú hru.
- Poloha myši: 0x506ff0 (x), 0x506fa8 (y) v súradniciach 800×600, nastavuje ju WM_MOUSEMOVE v okennej procedúre 0x440c79. Kurzor je softvérový, kreslí ho hra do snímky (systémový kurzor skrýva: ShowCursor(0), SetCursor(0) v 0x441446 a pri WM_SETCURSOR).
- Voľby agds.cfg (tabuľka v 0x4027xx): optimizeway, optimizedraw, slowcomp, debug, sound, normalize_sample, normalize_speed, oldscr, extedit, path, help, loglevel, freemem, videomode, transparency, precisemove, debug_grab, shadow_min, shadow_max, fade_type, videomem, loguseractions, widevideo, film_test, film_yuy2, film_switch, charset, empty_slot, force_soft_indent.

## Plynulý kurzor (config.ini [Cursor] Fps)
Logika hry beží na 25 krokoch/s (animácie, chôdza – tak je hra nakreslená, zrýchlenie kroku by zrýchlilo celú hru). Kurzor je však objekt scény a doplnok ho prekresľuje aj medzi krokmi:
- hák na 0x43cfee (obal `SleepEx(0)` – volá sa len v slučke, kde logika čaká na ďalší krok): najviac raz za 3/4 z 1/Fps prečíta `GetCursorPos` (dgVoodoo drží kurzor v súradniciach hry 800×600); ak sa myš pohla a hra je v scéne (0x584ff8 ≠ 0, nie film 0x58512c, 0x49bde0 = 0, 0x49eb48 = 0, `0x43cf49()` = 0), zapíše polohu ako WM_MOUSEMOVE (0x507010/14), zavolá 0x417a8d, pripočíta posun scény (`[0x49eb1c]+0x5d5/0x5d9`), presunie objekt kurzora `0x4094de(0)`, prekreslí `0x426c43([0x49eb1c])` a zobrazí `0x43e78f`,
- neprekresľuje, ak do kroku ostávajú < 2 ms (čas posledného kroku: QPC v 0x49bda0),
- hák na 0x402fa1 (plánovanie kroku): pôvodne „posledný krok = teraz“, takže každé oneskorenie (zobrazenie s vsync čaká až 16 ms) hru natrvalo spomalí; teraz „posledný = plánovaný čas“, pri oneskorení ≥ 1 krok (načítanie) „teraz“,
- `Fps=0` → háky kurzora a kroku sa nevložia.

**Nutné `videomem=0` v agds.cfg** (zadný povrch v systémovej pamäti). Pri predvolenom `videomem=1` je povrch v pamäti grafiky a softvérový renderer ho cez dgVoodoo zamyká → jedno prekreslenie ~33 ms (s plynulým kurzorom spadla hra na 15 krokov/s). Pri `videomem=0`: prekreslenie pár ms. `install.bat` dopíše `videomem=0` (ak chýba), `uninstall.bat` ho odstráni.

Merania (19. 11. 2026, save.1 hala, myš krúži cez SetCursorPos, vsync dgVoodoo zapnutý, monitor 60 Hz):
| verzia | slučka hry | prekreslení kurzora navyše | spolu |
|---|---|---|---|
| videomem=1 | 15,3/s | 15,3/s | hra spomalená |
| videomem=0, bez ochrany kroku, bez vsync | 24,3/s | 57,6/s | |
| + ochrana 8 ms pred krokom, bez vsync | 25,0/s | 43,6/s | 69/s |
| + vsync | 24,0/s | 36,3/s | logika spomalená o 4 % |
| + ochrana 1/Fps + 2 ms | 25,0/s | 25,0–30,3/s | 50–55/s |
| **+ plánovanie kroku, ochrana 2 ms (finálne)** | **25,0/s** | **35,0/s** | **60/s** |

Chôdza postavy (hala, 2 trasy, 3×): bez pohybu myši 3,95 / 3,35 s, s krúžiacou myšou 3,97–4,01 / 3,37–3,41 s – rozdiel v rámci presnosti merania (snímky ~70 ms). Animácie sa prekresľovaním nezrýchľujú. Overené aj inventár (lišta dole) – bez zvyškov.

Počítadlo prekreslení navyše: DDraw.dll + 0x1000 + 0x800 + 0x4C (na meranie, `nastroje/pamat.py`).

### Prieskum: ešte plynulejší kurzor (24. 11. 2026)
Otázka: dá sa kurzor zlepšiť nad súčasných 60 prekreslení za sekundu? Zmerané (myš krúži cez SetCursorPos 500×/s, snímanie obrazovky 60×/s cez mss, hala):
- **Fps=60 (súčasný stav):** obraz s kurzorom sa mení 60×/s = každú obnovu 60 Hz monitora. Na 60 Hz monitore sa viac snímok ukázať nedá (vsync dgVoodoo).
- **Systémový kurzor Windows cez dgVoodoo** (pokus: presmerované importy SetCursor/ShowCursor hry na šípku Windows): pri zväčšovaní obrazu dgVoodoo fyzický kurzor skryje a kreslí ho sám do obrazu („emulovaný hardvérový kurzor“, CursorScaleFactor) – ale len keď hra pošle snímku. Pri Fps=0 sa šípka hýbala len 25×/s, rovnako ako kurzor hry. Sám o sebe teda nepomôže.
- **FreeMouse=true** (dgVoodoo nepreváža myš do priestoru 800×600): Windows kreslí skutočný kurzor bez čakania na hru, ale hra dostáva súradnice obrazovky (zmerané 1320, 810 namiesto 0–799 × 0–599) – nepoužiteľné bez vlastného prepočtu.

Možnosti: (a) Fps podľa obnovovacej frekvencie monitora (120/144 Hz) – malá úprava, pomôže len na rýchlejších monitoroch; (b) skutočný kurzor Windows: FreeMouse=true + doplnok prepočíta súradnice všetkých správ myši (okenná procedúra 0x440c79), GetCursorPos/SetCursorPos v bm_core (plynulý kurzor, citlivosť) a 0x43d203, obmedzí kurzor na obraz 4:3 (ClipCursor), z obrázka kurzora hry (strieborný, červený, dvere, predmety, blikanie „fade mouse“) zostaví zväčšený HCURSOR pri každej zmene a kurzor hry skryje. Kurzor by sa hýbal s každým pohybom myši bez oneskorenia vykresľovania hry; je to však veľký zásah. Možnosť (b) je urobená inak – pozri „Najplynulejší (hardvérový) kurzor“.

### Najplynulejší (hardvérový) kurzor – `[Cursor] Mode=hardware` (predvolené od 24. 11. 2026)
Režimy `[Cursor] Mode`: `hardware` = najplynulejší (predvolený), `smooth` = plynulý (prekresľovanie hrou podľa `Fps`, ako doteraz), `original` = pôvodný (25/s). bm_core číta `Mode` tiež: pri `smooth` ponechá `Fps`, pri `original` nastaví Fps 0, pri `hardware` Fps 0 aj citlivosť 1.0 (nevloží žiadny hák kurzora – všetko robí DDraw.dll).
Riešenie bez FreeMouse (dgVoodoo ďalej drží fyzický kurzor v obdĺžniku 800×600 cez ClipCursor, hra dostáva správne súradnice):
- **skrytie kurzora hry:** kurzor je animácia scény s poradím −10 (`defmouse`, `mouse pic`, `mouse object` = predmet…). Doplnok v kroku aj pred zobrazením presmeruje jej pixely `+0x24` na vlastné priehľadné pole (purpurová); šablóny hry sa nemenia. Pôvodné pixely skopíruje pre okno kurzora; keď hra kurzor zmení (nová animácia alebo nový ukazovateľ), zopakuje to a scénu hneď prekreslí (`0x426c43`), aby na obrazovku nešla snímka s kurzorom hry. Posun obrázka voči myši = poloha animácie − posun scény − `0x506ff0/0x506fa8`.
- **okno kurzora:** samostatné vlákno vytvorí okno `WS_EX_LAYERED | TRANSPARENT | TOPMOST | NOACTIVATE | TOOLWINDOW` **bez vlastníka** (s vlastníkom = okno hry čakal každý `SetWindowPos` na herné vlákno → len 25 presunov/s). Obrázok zväčší bilineárne mierkou obrazu (výška klientskej oblasti / 600, obraz na stred), premultiplikovaná alfa, `UpdateLayeredWindow`. Každú 1 ms (`timeBeginPeriod(1)`) prečíta `GetCursorPos`, poloha v hre = poloha − ľavý horný roh `GetClipCursor` (800×600), a okno presunie (`SWP_NOZORDER`). Skryje sa, keď hra nie je v popredí, je minimalizovaná, beží film alebo kurzor hry neexistuje.
- **citlivosť** v tomto režime počíta to isté vlákno (ako bm_core: rozdiel × citlivosť v tisícinách, `SetCursorPos`), inak by okno ukazovalo striedavo nepreškálovanú a preškálovanú polohu. Keď kurzor presunie hra sama, import `SetCursorPos` (0x485280) je presmerovaný a nastaví znovunačítanie polohy bez násobenia.
Zmerané 24. 11. 2026 (myš krúži cez SetCursorPos, snímanie mss 60/s, hala): **hardware 59–60 zmien obrazu/s** (strop merania = 60 Hz monitor), smooth 35–38/s, original 25/s. Citlivosť 0.7: 40 × 5 mickey → 205 px pri 1.0, 144 px pri 0.7 (0,70). Overené: strieborný, červený nad obrazom, dvere nad východom, značky medzerníka s červeným kurzorom, predmet z kolieska, hlavná ponuka, Win+D skryje okno a návrat ho ukáže, obrazovka nahrávania.
Poznámka k meraniu z prieskumu: ranných „60/s“ pri Fps=60 ovplyvnila šípka dgVoodoo z pokusu; bez nej má smooth v tomto meraní 35–38 zmien/s.

## Citlivosť kurzora (config.ini [Cursor] Sensitivity)
`Sensitivity=0.5` (predvolené), rozsah 0.1–1.0 (mimo rozsahu sa orezá, nečitateľná hodnota = 0.5; desatinná bodka aj čiarka). Násobok pohybu myši: 1.0 = rýchlosť pôvodnej hry.
- V tom istom háku 0x43cfee: pri každom volaní (stovky za sekundu počas čakania na krok) porovná `GetCursorPos` s naposledy nastavenou polohou, rozdiel vynásobí citlivosťou (počíta v tisícinách pixela, zlomky sa nestrácajú) a presunie kurzor `SetCursorPos`.
- Iba keď je hra v popredí (`GetForegroundWindow` = okno hry `[0x5850e8]`).
- Polohu načíta znova bez násobenia: keď kurzor presunie hra sama (hák na jej `SetCursorPos` v 0x43d203, 6 B `call [0x485280]` → `call` do doplnku + `nop`), po návrate do hry a po pauze dlhšej ako 5 krokov (načítanie, film).
- Pri `Sensitivity=1.0` sa citlivosť nespracúva vôbec a hák 0x43d203 sa nevkladá; pri `Fps=0` a `Sensitivity=1.0` sa nevkladá ani hák 0x43cfee.

Meranie (19. 11. 2026, hlavná ponuka, relatívny pohyb cez `SendInput` vrátane akcelerácie Windows, posun kurzora v px hry):
| Fps | Sensitivity | 160 mickey pomaly | 180 mickey rýchlo |
|---|---|---|---|
| 0 (pôvodná hra) | 1.0 | 164–165 | 461–462 |
| 60 | 1.0 | 165 | 461 |
| 60 | 0.5 | 80–81 | 230 |
| 0 | 0.5 | 83 | 230–231 |

Plynulý kurzor rýchlosť nemení (Fps 60 = pôvodná hra), citlivosť 0.5 presne polovičná. Od 23. 11. 2026 je predvolená citlivosť **0.7** (config.ini aj predvolená hodnota v kóde, keď kľúč chýba); od 24. 11. 2026 pri hardvérovom kurzore **0.5** (pre smooth a original sa odporúča 0.7).

## Doplnok pohodlia (DDraw.dll v C, 23. 11. 2026)
Reťaz knižníc: hra → `DDraw.dll` (nový doplnok, `doplnok/bm_qol.c`) → všetky exporty preposlané na `bm_core.dll` (doterajší doplnok v assembleri: filmy, plynulý kurzor, citlivosť – len premenovaný) → `dgddraw.dll` (dgVoodoo2). Prekladá sa cez `zig cc` (Python balík `ziglang`), bez CRT, importuje kernel32/user32/gdi32 (winmm sa načíta za behu); `doplnok/zostav.bat`, oba doplnky naraz `build_plugin.bat`.

Háky (v pamäti, pred zápisom sa overia pôvodné bajty; iná verzia exe → nič):
| adresa | čo | použitie |
|---|---|---|
| 0x402e21 `call 0x431cf8` | začiatok kroku logiky (25/s) | ESC, F5/F8, hotspoty, preskakovanie, koliesko, ladiaci kanál |
| 0x438d58 (začiatok, 9 B → mostík) | začiatok repliky | koniec pretáčania |
| 0x440e9d `call 0x43f278` | WM_KEYDOWN | ESC a medzerník |
| 0x44112b `call [DefWindowProcA]` | ostatné správy okna | WM_MOUSEWHEEL |
| 0x42e416, 0x43a228 `call 0x433708` | načítanie uloženej hry (slot) | obnova zapamätaných nastavení |
| 0x42b8af `call 0x43a112` | skript zapisuje celočíselnú systémovú premennú (meno, hodnota) | zapamätanie nastavení |
| 0x43e78f (začiatok, 9 B → mostík) | zobrazenie (Blt zadného povrchu) | FXAA pred zväčšením, pretáčanie bez snímok, názvy pozícií, skrytie kurzora hry |
| 0x408c5c (začiatok, 7 B → mostík) | kurzor nad objektom | červený kurzor nad východom pri značkách |
| 0x4410c5 `call 0x417949` | udalosť dvojkliku | pretočenie chôdze |
| import SetCursorPos 0x485280 | hra presúva kurzor | hardvérový kurzor s citlivosťou: znovunačítanie polohy |

### config.ini
```ini
[Controls]
EscapeMenu=1      ; ESC v hre = ponuka
SpaceHotspots=1   ; medzerník = hotspoty na 2 s (ako tabulátor)
HoldToSkip=1      ; ESC/medzerník v rozhovore = preskočenie po ďalšiu repliku (aj animácie, hudba)
SaveLoadKeys=1    ; F5 = uložiť, F8 = nahrať
QuickSaveKeys=1   ; Ctrl+S / Ctrl+L = rýchle uloženie / načítanie (QuickSaveSlot=98)
WheelInventory=1  ; koliesko = predmety inventára
DoubleClickWalk=1 ; dvojklik = pretočenie chôdze (postava hneď v cieli)
[Cursor]
Mode=hardware     ; hardware = najplynulejší (vlastné okno), smooth = prekresľovanie hrou (Fps), original
[Video]
SaveNamesTransparent=1 ; názvy pozícií bez čierneho obdĺžnika
Smoothing=1       ; FXAA pred zväčšením (1 = postavy, 2 = plocha scény) (SmoothingThreshold=25, SmoothingThresholdMin=16, SmoothingSubpixel=75)
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
Zoznam objektov scény: kruhový zoznam `scéna+0x40` (prvý `[+0x28]`, ďalší `[objekt+0]`). Objekt: meno `+8`, aktívny `+0x34`, poradie `+0x2c`, región `+0x72`, názov (text pri prejdení myšou) `+0x7a`, obsluha use `+0xb5`, posuny `+0x3a/+0x3e/+0x42/+0x46`, animácia `+0x7e`, postava `+0x82`, klávesové obsluhy `+0xe1` (východy: tabulátor), ďalšia obsluha `+0xd1` (len východy). Región: stred `(+0, +2)` (short), ohraničenie x `+0xA..+0xC`, y `+0xE..+0x10`. Hit-test 0x4034b0 (x, y, scéna, 0) → objekt pod kurzorom (`scéna+0x5ed`).
Hotspot = aktívny objekt s regiónom a neprázdnym názvom, okrem `inv.*` a predmetu na kurzore; poloha = stred regiónu prepočítaný opačne ako v hit-teste.

**Tabulátor (natívne):** východy majú vlastnú obsluhu klávesu Tab – skript k objektu pripojí animáciu `kurzor_dvere.flc` (ikona dverí 24×32) na stred regiónu (`+0x7e`, posun `+0x42/+0x46`) a asi po 2,5 s ju odstráni. Hra stav klávesu nesleduje (GetKeyboardState len pri WM_KEYDOWN). Zmerané: ikona je vidno 2,04 s po stlačení (50 krokov); pri držaní ju predlžuje automatické opakovanie klávesu.

**Čas zobrazenia značiek** je rovnaký: každé stlačenie medzerníka (aj automatické opakovanie pri držaní) nastaví koniec na aktuálny krok + 50. Zmerané: jedno stlačenie 1,9 s; držanie 4 s → značky do 6,0 s (2 s po pustení), ako tabulátor.

**Značky ako animácie scény:** zoznam animácií `scéna+0x80` (prvá `[+0x28]`, ďalšia `[a+0]`; animácia: poradie `+0xC`, š/v `+0x10/+0x14`, x/y `+0x1C/+0x20` v súradniciach scény, pixely `+0x24`, meno `+0x41`, postava `+0x61`, vlastník `+0x71`; `nastroje/animacie.py`). Kurzor je animácia „mouse pic“ s poradím −10. Doplnok po stlačení medzerníka vytvára vlastné animácie `0x406932(scéna, šablóna, −9, 0, "bmqol_hotspot")` – hra ich kreslí sama **pod kurzor** a sama prekresľuje; po uplynutí času ich odstráni `0x406b31(scéna, &animácia)` (odstráni uzol, označí oblasť na prekreslenie, pixely šablóny nemení). Animácie sa hľadajú podľa mena, takže sa odstránia aj po návrate do scény z ponuky.
Šablóna obrázka (29 B): šírka, výška, bity (32), x, y, ukazovateľ na pixely, typ. Pixely 4 B: B, G, R, 100; purpurová (255, 0, 255) = priehľadná. Ikona východu sa načíta `0x444f66(&šablóna, "kurzor_dvere.flc")` (ako ju načítava hra), krúžok (21×21, svetlá zlatá s tmavým lemom) má vlastné pixely.
Východ = objekt s klávesovými obsluhami (`+0xe1` ≠ 0) → ikona dverí; ostatné → krúžok. Animácie sa prerobia len pri zmene zoznamu alebo polohy značiek. Overené v hale: 5 východov s dverami (zhodne s tabulátorom), obraz, tabuľka a stolík s krúžkom; kurzor je nad značkou; po pustení v scéne nezostane žiadna naša animácia. Nad východom sa kurzor v pôvodnej hre mení na dvere – pri značkách by to bola druhá ikona dverí, preto je počas značiek nad východom **červený kurzor** ako pri tabulátore (pozri nižšie).
Počas reči (obsadený kanál so vzorkou repliky 0x49ef58) medzerník hotspoty neukazuje a preskakuje repliku.

**Pád pri ESC so značkami (opravený 24. 11. 2026):** pozícia 2 (záhrada 10ab), medzerník a hneď ESC → pád v ntdll. Príčina: pri uvoľnení scény (`0x40587e`, tu cez ponuku s kolieskami uloženými v pozícii) hra uvoľní pixely všetkých animácií scény (`0x418d17(animácia+0x10)` → free, okrem typov 6/7 a troch špeciálnych bufferov) – aj značiek, ktoré ukazovali do polí doplnku (zachytené vlastným VEH: free na `dvere_pixely`). Teraz má každá značka kópiu pixelov z pamäte hry (`0x44ba28`), doplnok ju pri odstránení uvoľní (`0x44bb62`), pri uvoľnení scény ju uvoľní hra. Kurzor (hardvérový, červený) sa takto neuvoľňuje – `0x40587e` najprv odstráni kurzor (`0x408b2d`, bez uvoľnenia pixelov). Overené: 3× medzerník + ESC v pozícii 2, medzerník + odchod východom.
**Miesta so stálou ikonou bez značky:** šípka „zpět“ v detaile Marcusovho obrazu (19d5) je miesto `19d5.10af` bez obrázka a objekt `main.11d2` s obrázkom `Zoomzpet.bmp` a rovnakým ohraničením regiónu. Miesto bez vlastnej animácie, ktorého región má rovnaké ohraničenie ako aktívny objekt s animáciou (+0x7e), značku nedostane. Overené: detail obrazu bez značky, hala stále 5 dverí + 3 krúžky.
**Kolieska uložené v pozícii:** ESC a F5/F8 načítajú kolieska (`1006.100c`) do scény; pri uložení cez F5 sa uložia s pozíciou a po načítaní boli vidno stále. Doplnok ich teraz skryje (`0x43040d`), keď je myš aspoň 1 s (25 krokov) pod horným pásom (y ≥ 60), bez ohľadu na to, kto ich načítal. Pri myši hore ich hra ukáže ako predtým.

**Kurzor nad objektom:** stav kurzora `[0x49f404]` (1 = základný `kurzor-stribrny.flc`, 2 = nad objektom), šablóna obrázka kurzora objektu `objekt+0x86` (východy `kurzor_dvere.flc` 24×32, ostatné `kurzor-cerveny.flc` 17×26), šablóna práve zobrazeného kurzora `[0x49f01e]`. Hra každý krok porovná `+0x86` objektu pod kurzorom s `[0x49f01e]` a pri rozdiele zavolá `0x408c5c(scéna, šablóna, meno)` (odstráni starý kurzor `0x408b2d`, vytvorí animáciu „mouse pic“ s poradím −10). Tabulátor: skript východu volá `0x4052ca(scéna, objekt, súbor)` – obrázok kurzora objektu dočasne nahradí červeným (zmerané: `+0x86` východov 24×32 → 17×26 a späť).
Doplnok objekty nemení: hák na začiatok `0x408c5c` (7 B) – ak sú značky vidno a šablóna je ikona dverí (rozmery a pixely ako `kurzor_dvere.flc`), podstrčí vlastnú šablónu `kurzor-cerveny.flc`; ak už je červený, nerobí nič. Keď sa značky ukážu a kurzor už je nad východom, doplnok vynuluje `[0x49f01e]`, aby ho hra nastavila znova. Po zmiznutí značiek sa hra sama vráti k dverám (šablóna sa líši). Overené 24. 11. 2026 v hale: s medzerníkom nad východom červený kurzor + ikona dverí, nad obrazom červený, po 2 s nad východom znova dvere.
**Chyba z 24. 11. (opravená):** `0x444f66(&šablóna, súbor)` vracia pixely v pamäti, ktorú hra pri ďalšom načítaní obrázka použije znova – načítanie `kurzor-cerveny.flc` prepísalo pixely ikony dverí značiek (pruhy). `nacitaj_obrazok()` preto pixely skopíruje do poľa doplnku a ako hra (`0x419a0e`) oreže úplne priehľadné stĺpce vpravo a riadky dole (červený kurzor 18×26 → 17×26).

### Preskakovanie (ESC / medzerník, keď hráč nemá kontrolu)
Natívne: počas reči preskočí repliku **ktorýkoľvek kláves** (aj písmená) – cesta 0x43f278 → udalosť 0x4c; animácie a hudba medzi replikami bežia ďalej.
Doplnok v herných scénach (meno z hexadecimálnych číslic ako `123f`, `109f`; nie `main`, `new_game_tmp_screen`, `1006.*`, nie počas filmu), keď hráč nemá kontrolu (`0x4305d1() < 1`):
- **ostatné klávesy** sa hre neposielajú (nepreskakujú nič),
- **medzerník** ide hre → preskočí presne jednu repliku; opakovanie pri držaní sa zahadzuje (držaný = jedna replika); nič sa nepretáča,
- **ESC** ide hre (preskočí repliku) a spustí **pretáčanie**: logika nečaká na krok (`[0x49bda0]` QPC posledného kroku o 1/25 s dozadu), na obrazovku ide len jedna snímka za 100 ms a **jednorazové zvuky sa zastavia** – kanály `0x59afe8` po 16 B (+4 obsadený, +8 pozícia v bajtoch, +0xC vzorka), počet `[0x4904c8]`, vzorka: +0 dáta, +4 dĺžka, +8 frekvencia, +0xC kanály, +0x10 bajty/vzorku, +0x18 priorita, +0x1C = 1 slučka; zastavujú sa len neslučkové okrem reči (vzorka 0x49ef58), `0x445cb6(kanál)`; slučky (atmosféra scény) ostanú. Pretáčanie skončí, keď začne ďalšia replika (hák 0x438d58), keď hráč dostane kontrolu, alebo po 60 s. Podržaný ESC pretáča ďalej a každú novú repliku hneď preskočí.
Rozprávač na čiernej obrazovke (scéna `123f`): hudobný podklad je jedna stopa (kanál 0, 44,1 kHz stereo, 27,2 s, priorita 50), hlas každej vety je samostatná vzorka repliky (kanál 1) – medzerník preto preskakuje po vetách a hlas ostáva v súlade s textom (ďalšia veta ~0,5 s po stlačení); podklad dohrá (spolu 27,2 s namiesto 32,6 s). ESC zastaví podklad a preskočí celé rozprávanie. Pozícia kanála (+8) sa dá zapisovať (hra ju rešpektuje), ale titulky rozprávača na nej nezávisia.
Overené: v salóne 10× písmeno A za 3,5 s nepreskočilo nič (1 replika prirodzeným tempom), medzerník presne 1 replika, medzerník držaný 3 s tiež 1 replika; pri rozprávačovi 5 stlačení = 5 viet.

Meranie (nová hra; `nastroje/test/uvod_test.py`, `nastroje/test/rozpravac_test.py`):
| úsek | bez zásahu | pôvodná hra, ESC každých 0,4 s | doplnok 23. 11. ráno (zrýchlenie) | **doplnok – pretáčanie** |
|---|---|---|---|---|
| rozprávač 123f | 32,6 s | – | – | **0,1 s** ESC (podržaný aj 1 stlačenie); medzerník po vetách 27,2 s |
| úvodný rozhovor v salóne (od scény po kontrolu) | 158,0 s | 44,7 s | 15,6 s | **2,4 s** podržané; stlačenie každé 2 s: 59,5 s |
Od stlačenia po začiatok ďalšej repliky: 16–172 ms (prechod do inej scény ~1,6 s). Po preskočení je hra v rovnakom stave (hala, ako save.1).

`tell_mode` (0x48d458) je bitová maska: bit 0 = text, bit 1 = hlas (3 = titulky zapnuté, 2 = vypnuté). Funkcia repliky 0x438d58.

### F5 / F8 – uloženie a nahratie hry
Natívne skratky: engine číta z agds.cfg `use_key`, `info_key`, `move_key`, `testmove_key`, `load_key` (predvolene F3), `save_key` (F2), `options_key`, `inventory_key`, `leftbutton`, `rightbutton`, `centerbutton`, `moveaction` (0x432317). F2/F3 však spúšťajú skripty zo systémových premenných `save_scr`/`load_scr`, ktoré sú v Black Mirror prázdne – v hre nerobia nič (overené). F5 ani iné klávesy tiež nič.
Doplnok (`[Controls] SaveLoadKeys=1`): F5/F8 v hre otvorí ponuku (ako ESC) a po jej nabehnutí (hráč povolený) vyberie položku – Uložit hru `1006.100e.100b`, Nahrát hru `1006.100e.1020` (položky sú v scéne len pri prejdení myšou, preto ich doplnok načíta `0x430052` a zavolá ich „use“). F5/F8 v hlavnej ponuke vyberie položku hneď. ESC na obrazovke otvorenej skratkou: hra sa natívne vráti do hlavnej ponuky a doplnok po jej nabehnutí pošle ďalší ESC → rovno do hry.
ESC natívne funguje zo všetkých obrazoviek ponuky: Nastavení (`1006.1037`), Nahrát/Uložit (`1006.101b`), Tvůrci (`1006.103a`) → hlavná ponuka; hlavná ponuka (`1006.100e`) → hra. Overené 23. 11. 2026, nič nebolo treba pridávať.

### Koliesko myši – inventár
Pole inventára `0x578c10`: 35 položiek po 0x28 B (meno[32], `+0x20` = 1 obsadené, `+0x24` = −1). Predmet na kurzore `[0x49f3e0]`; pripnutím sa z poľa vyberie (miesto ostane prázdne), vrátením (pravý klik) sa vráti na to isté miesto – poradie je stabilné. Inventár povolený: `[0x48d2d8] > 0`.
Koliesko dole = ďalší predmet, hore = predchádzajúci (cyklicky; bez predmetu na kurzore dole = prvý, hore = posledný). Zárezy sa hromadia a spracujú naraz (n zárezov = n-tý predmet, jedno vrátenie + jeden výber).
Postup (stavový automat v kroku): ak je predmet na kurzore, vráti sa udalosťou pravého tlačidla (`0x417949(0x50703c)`, ako skutočný pravý klik) → čaká sa, kým kurzor nie je prázdny a predmet je späť na svojom mieste v poli → **pauza 12 krokov (~0,5 s)** → výber cieľa: objekt predmetu sa nájde alebo načíta do scény a zavolá sa jeho „use“ (to isté ako klik na predmet v lište; skript predmet vyradí z poľa a zavolá `0x408d5a(scéna, objekt, 1)`) → čaká sa, kým je cieľ na kurzore → pauza 8 krokov.
**Chyba z 23. 11. (opravená):** bez páuz sa pri rýchlom točení vybral predmet, ktorého vrátenie ešte dobiehalo – skript ho vyradil z inventára, ale nepripol na kurzor, a predmet sa stratil (smuteční list). Výber tesne po vrátení zlyhal v ~0,25 s okne, vrátenie tesne po výbere sa ignorovalo. Poistka: ak cieľ do 25 krokov nie je na kurzore a v poli chýba, doplnok vráti jeho položku poľa (záloha 0x28 B pred výberom) a výber raz zopakuje.
Záťažový test `nastroje/test/koliesko_test.py 40` (1–3 zárezy za sebou s odstupom 30–300 ms, rôzne miesta vrátane obrazu a lišty, kontrola, že žiadny predmet nezmizol): pred opravou sa list stratil; po oprave 40/40 bez chyby, 58 výberov, poistka nebola potrebná. Lišta potom zobrazuje oba predmety.

### Dvojklik – postava hneď v cieli (24. 11. 2026)
Hra dvojklik pozná sama: okno má CS_DBLCLKS, pri pustení ľavého tlačidla po WM_LBUTTONDBLCLK (`[0x585018] = 0x203`) volá udalosť `0x417949(0x50705c)` namiesto `0x50702c` (akcie doublemove/doubleuse/doubleinfo). Natívne: dvojklik na východ skráti cestu (zmerané: hala → 10b5 po ~1,5 s chôdze), dvojklik na podlahu = obyčajná chôdza.
Hlavná postava: poloha `0x49be28`/`0x49be2c`, stav `[0x49be3a]` – 0 stojí, 1 chôdza na miesto, 2 chôdza k objektu, 5 k predmetu (dvojklik), 7 dvojklik na východ.
Doplnok: hák na `call 0x417949` v 0x4410c5 (len udalosť dvojkliku) – v hernej scéne (hex meno, hráč má kontrolu, nebeží pretáčanie) zapne režim pretáčania chôdze. V kroku: kým stav ≠ 0, logika nečaká na ďalší krok (`0x49bda0 -= krok`), jednorazové zvuky (kroky) sa zastavia a funkcia zobrazenia nič neposiela na obrazovku. Koniec: postava zastaví, zmena scény, film, preskakovanie, 500 krokov, alebo ak chôdza do 5 krokov nezačne. Ďalší dej (replika pri predmete, prechod do inej scény) beží normálne.
Zmerané 24. 11. 2026 v hale: podlaha 96 krokov chôdze za 78 ms (pôvodne 3,7 s), obraz 118 krokov → Samuel hneď pri obraze a hovorí repliku, zamknuté dvere do spoločenskej miestnosti 161 krokov → replika, východ vľavo dole 32 krokov → hneď scéna 10b5. Jednoduchý klik = normálna chôdza. Dvojklik v detailnom zábere (19d5) nič nemení.
`[Controls] DoubleClickWalk=0` hák nevloží.

### Obrazovka Uložit/Nahrát hru – názvy pozícií bez čierneho obdĺžnika (24. 11. 2026)
Obrazovka `1006.101b` (uloženie aj nahrávanie). Názvy pozícií sú animácie `1006.101b.100b.N` (text na čiernom pozadí 0,0,0; poradie 10), bodkovaná čiara za nimi je priamo v pozadí `ulozit_hru.bmp` (800×600, 2 riadky bodiek 12–13 px pod vrchom názvu); čierny obdĺžnik ju pod textom zakrýval.
Doplnok (každý krok aj pred zobrazením – editovaný názov hra s blikajúcim kurzorom vytvára každý krok nanovo a hneď ho vykreslí): čisté čierne pixely názvov → priehľadná purpurová; v pozadí si uloží pôvodný pás (x 280–640, y 150–460) a pod šírkou každého názvu nahradí riadky s bodkami (viac ako 15 svetlých pixelov) najbližším riadkom bez bodiek nad nimi; pri zmene šírky názvu (písanie) sa pás obnoví. Pri zmene sa scéna prekreslí (`0x426c43`). `[Video] SaveNamesTransparent=0` vypne.
Overené: nahrávanie (8 pozícií), ukladanie s písaním názvu „abc d“ a mazaním (po zmazaní sa bodky vrátia), bez uloženia (ESC).

### Ľavé tlačidlo myši v rozhovore
Overené 24. 11. 2026 (úvodný rozhovor v salóne, vstup každých 1,5 s, 15 s): bez vstupu 6 replík, ľavé tlačidlo 11, medzerník 11 – ľavé tlačidlo preskakuje repliky natívne rovnako ako medzerník, doplnok ho nemení.

### Rýchle uloženie a načítanie – Ctrl+S / Ctrl+L (24. 11. 2026)
- Hra ukladá `0x433bb0(slot)` (save.N, savepic.N, a z poľa mien `0x5776e8` – 99 položiek po 0x33 B, index = číslo pozície – prepíše `savnames.txt`), načítava `0x433708(slot)` (vrátane krokov uloženia sa začína `0x409360()` ≠ 0 → nič). Bežne to volá skript obrazovky Uložit/Nahrát.
- Doplnok: Ctrl+S/L v `klaves_dole` (pred blokovaním kláves počas rozhovoru), vykoná sa v kroku. Uloženie: len v hernej scéne s kontrolou hráča (inak hláška „Teraz sa nedá uložiť“), meno pozície do poľa mien a `0x433bb0([Controls] QuickSaveSlot, predvolene 98)`. Načítanie: ak `save.N` existuje, cez `nacitaj_hru` (obnova zapamätaných nastavení); aj z hlavnej ponuky `1006.100e`.
- **Hláška:** `0x446c75(&šablóna, x, y, 1 = na stred, text, písmo, −1)` vykreslí text písmom titulkov (tell_font `[0x584e48]`) – tak ako titulky v `0x438d58` (`0x447593` = to isté + animácia). Poloha subtitle_x/y `[0x584e38]/[0x584e3c]` + posun scény; x šablóny je ľavý okraj (hláška bola posunutá vpravo), doplnok ho nastaví na subtitle_x − šírka/2. Overené: sk, cs aj en config (voľba 1/2/3 v inštalácii) – správny jazyk, na stred.
- **Rýchlosť kurzora (24. 11. 2026):** pri citlivosti 0.7 je hardvérový kurzor rovnako rýchly ako plynulý a pôvodný – rovnaký vstup (mouse_event, 1000 Hz po 1 a 3 bodoch, pomaly/stredne/rýchlo) posunie kurzor hry o rovnaký počet pixelov (napr. 198/203, 373/372, 236/236 px). Animácia `0x406932(scéna, šablóna, −8, 0, "bmqol_hlaska")`, pixely z pamäte hry; po 50 krokoch (2 s, ako značky medzerníka) `0x418d17` + `0x406b31`; pri zmene scény ju uvoľní hra.
- **Kódovanie textov hry = Kamenických** (zistené z pamäte: „ke schodišti“ š = 0xA8, „jídelny“ í = 0xA1; cp1250 ž 0x9E sa kreslilo ako Ř, š ako ?). Texty hlášok a meno pozície sa prevádzajú tabuľkou `KAMENICKI` (0x80–0xAB).
- Jazyk hlášok podľa poznámok v config.ini (ako inštalácia): „kurzoru“ česky, „kurzora“ slovensky, inak anglicky.
- Overené: Ctrl+L bez pozície → „Rýchla pozícia ešte nie je uložená“, Ctrl+S → save.98 + „Rýchle uloženie“, presun, Ctrl+L → Samuel späť na uloženom mieste + „Rýchle načítanie“, Ctrl+L z hlavnej ponuky po spustení hry, Ctrl+S v úvodnom rozhovore → „Teraz sa nedá uložiť“ (save.98 nezmenený). V savnames.txt sa zmenila len pozícia 98.
- **Ctrl+L počas chôdze (opravené 24. 11. 2026):** načítanie nastaví polohu a stav postavy (0x49be28/2c, 0x49be3a), nie jej obrázok – Samuel ostal na uloženom mieste v póze kroku. Nepomohlo: `0x41fcc9` (postava, x, y, smer), pohyb na vlastné miesto až po načítaní. Načítanie z ponuky (ESC, potom Ctrl+L) je v poriadku, ale cez ponuku by obraz stál ~3 s (ponuka nabehne až po ~1,7 s a hra ju dokončuje). Riešenie: ak Samuel kráča, doplnok mu dá príkaz `0x41c193(0x49bde8, x, y, 0, −1, 1, 0)` na aktuálnu polohu (akcia move – zruší aj cieľ, napr. východ alebo obraz), chôdzu pretočí ako po dvojkliku (bez snímok, ~110 ms) a načíta, keď stojí (stav 0). Overené: cieľ podlaha, východ vľavo dole, obraz – vždy stojí na uloženom mieste, nikam neodíde. Počas prechodu cez východ (bez kontroly) hláška „Teraz sa nedá načítať“.
- **Inventár po Ctrl+L z hlavnej ponuky (opravené 24. 11. 2026):** lišta inventára sa neukázala (predmety v poli `0x578c10` boli). Hlavná ponuka (aj ponuka cez ESC) inventár vypne skriptovým príkazom `0x43793d` (počítadlo `[0x48d2d8]` −1, 0 = vypnutý) a zapne ho až skript obrazovky nahrávania (`0x437986`, +1, najviac 1). Načítanie samo ho nemení – po Ctrl+L z ponuky ostal 0. Doplnok po každom rýchlom načítaní zavolá `0x437986`, ak je `[0x48d2d8]` < 1. Overené: Ctrl+L z hlavnej ponuky po spustení hry aj z ponuky cez ESC → 1, lišta s predmetmi.
- **Citlivosť:** predvolená 0.5 pri hardvérovom kurzore (config aj predvolená hodnota v DDraw.dll, keď kľúč chýba), pre smooth/original sa odporúča 0.7 (bm_core má predvolenú 0.7).
- Pozícia vytvorená mimo obrazovky ukladania má starý náhľad (savepic z naposledy otvorenej obrazovky Uložit) – obrazovka nahrávania náhľady neukazuje.

### Zapamätané nastavenia
Štartovací skript `main` pri **každom spustení hry** nastaví `tell_mode=2` (titulky vypnuté), `tell_volume=85`, `sound_volume=100`, `music_volume=80`; uložená hra obsahuje systémové premenné a pri načítaní ich prepíše (napr. save.1 mal `sound_volume=5`).
Tabuľka systémových premenných: `0x48d470`, záznamy po 0x2D B (meno[32], ukazovateľ na hodnotu, ukazovateľ 2, príznak 1 = číslo, funkcia pri zmene), `nastroje/sysvar.py` ju vypíše aj s hodnotami. Zápis zo skriptu `0x43a112(meno, hodnota)`, čítanie `0x43a19f`, návrat na predvolenú `0x439f81`, nová hra `0x43a627`.
Doplnok: zmena na obrazovke Nastavení (`1006.1037`) sa zapíše do `[Remembered]`; zápis zo skriptu mimo Nastavení sa zablokuje pri `tell_mode` vždy, pri hlasitostiach a game len počas štartovacieho skriptu `main` (neskoršie zámerné zmeny počas hry ostanú); po prvom kroku a po načítaní hry sa zapamätané hodnoty vrátia a zavolá sa funkcia premennej (hlasitosť zvuku 0x439c6d, hudby 0x439c47; gamu prepočítava hra pri prekreslení, použitá hodnota v 0x650a30).
Posuvník zvuku mení `sound_volume` aj `music_volume`. Posuvníky sa ovládajú klikom na guľku a potom na čiaru.
Overené 23. 11. 2026: titulky, reč 69, zvuk 79/hudba 63, gama −19 → reštart hry aj načítanie save.1 → hodnoty ostali.

### Ladenie
`nastroje/ladenie.py call ADRESA arg…` – doplnok exportuje štruktúru `ladenie`; Python do nej zapíše funkciu a argumenty (`s:text` = reťazec), doplnok ju zavolá v hernom vlákne pri ďalšom kroku a vráti výsledok. Ďalšie nástroje: `scena.py`, `objekty.py`, `podkurzorom.py`, `inventar.py`, `sysvar.py`; testy `test/seq.py` (klik, pravý klik, ťahanie, koliesko, klávesy, snímky + priebeh hlasitosti a titulkov), `test/hra_save.sh`, `test/uvod_test.py`.

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
Plynulosť (krúženie myšou v hale, `nastroje/test/plynulost.py`): s FXAA aj bez 25,0 krokov/s a 59,4–60,0 zobrazení/s.

**Výber:** `Resampling = lanczos-3` + FXAA s prahom 25 %. Hrany postáv, stoličiek a rámov sú hladké, textúry (koberec, tapety) ostávajú detailné (`snimky/porovnanie/4_lanczos3_vs_fxaa25_1na1.png`). Alternatívy: mäkšie `bicubic` alebo pôvodné `bilinear` v dgVoodoo.conf; vyšší `SmoothingThreshold` = menej vyhladených hrán.

**Len postavy (`Smoothing=1`, predvolené):** FXAA nad celou snímkou zmäkčovalo a stmavovalo písmo (titulky, ponuky). Teraz sa vyhladzuje len v herných scénach a len v obdĺžnikoch postáv, nikdy v ponukách a v pásoch s textami (y < 45 a y ≥ 544):
- NPC: animácie scény s ukazovateľom na postavu `+0x61`; obdĺžnik ako pri prekresľovaní v 0x406b31: x = post[0x4a] + post[0x37e], y = post[0x4e] + post[0x382], š = post[0x52], v = post[0x56], mínus posun scény,
- hlavná postava (Samuel): pomenovaná animácia bez vlastníka a bez postavy (napr. `108f.1090`), obdĺžnik z animácie (x, y, š, v); vylúčené mená s `.bmp`, `.flc`, „animation“, „mouse pic“, „BWWorkArea“ a naše značky,
- okraj 2 px; jas sa počíta pre celú snímku (okolie hrany), FXAA len vnútri obdĺžnikov.
Overené v salóne: obdĺžniky sedia na všetkých 4 NPC aj na Samuelovi (`snimky/profily/postavy_fxaa.png` vs `postavy_bez.png`), titulok je bez zmeny, pozadie mimo postáv tiež. V hale 1 obdĺžnik, FXAA 0,9 ms (predtým 4,5 ms), 25 krokov/s, 59,7 zobrazení/s. `Smoothing=2` = celá plocha scény (y 45–543), stále bez ponúk a textov.

Neskúšané (nebolo treba): ReShade (FXAA/SMAA by pracovalo až na zväčšenom obraze z dgVoodoo, nie pred zväčšením), zväčšovače xBR/ScaleFX/FSR (dgVoodoo vlastné shadery nepodporuje).

## Inštalácia
- `install.bat` – skopíruje do hry `dgddraw.dll`, `DDraw.dll`, `bm_core.dll`, `D3DImm.dll`, `dgVoodoo.conf` a `config.ini` (jazyk podľa výberu, existujúci len so súhlasom) a zapíše príznak DPI (voliteľný parameter: cesta k hre)
- `uninstall.bat` – súbory zmaže a príznak odstráni
- **Kódovanie dávok (24. 11. 2026):** dávky sú na disku v kódovaní **852** (OEM slovenského a českého Windows), v gite v UTF-8 (`.gitattributes`: `*.bat text eol=crlf working-tree-encoding=CP852`). Predtým boli v UTF-8 s `chcp 65001` – to prepne okno konzoly na staré bodové písmo Terminal 12 (zmerané `GetCurrentConsoleFontEx`: bez chcp Consolas 16 / CP 852, s chcp Terminal 12 / CP 65001). Pokus vrátiť písmo cez `SetCurrentConsoleFontEx` z PowerShellu nefungoval spoľahlivo (každé ďalšie spustenie PowerShellu písmo vrátilo) – správne riešenie je chcp nepoužívať. Na Windows s inou OEM stránkou (napr. anglický 437) bude slovenská diakritika v hláškach skomolená, anglické hlášky sú v poriadku.
- **Jazyk hlášok (24. 11. 2026):** do výberu jazyka slovensky + anglicky; potom podľa jazyka config.ini: český → česky + anglicky, slovenský aj anglický → slovensky + anglicky. Inštalácia: platí výber (aj parameter `sk`/`cs`/`en`), pri voľbe 0 (ponechať) jazyk existujúceho config.ini. Odinštalovanie: jazyk config.ini v hre zistený pred zmazaním. Jazyk config.ini sa spozná podľa slova „kurzoru“ (len český config; slovenský má „kurzora“). Overené: odinštalovanie so sk, inštalácia cs, odinštalovanie s cs, inštalácia sk.
- **Konce riadkov CRLF:** dávky boli v gite a v balíku s LF – cmd potom pri skokoch na návestia číta súbor zle (po dlhšom riadku sa rozpadla na kúsky „'t' is not recognized…“). Teraz CRLF (`eol=crlf`).
- `config.ini`: jazyk poznámok si vyberie hráč (`choice`): 1 = `dgvoodoo/config.sk.ini`, 2 = `config.cs.ini`, 3 = `config.en.ini` (rovnaké kľúče a hodnoty, v hre vždy ako `config.ini`). Ak `config.ini` v hre už je, ponuka má navyše 0 = ponechať (predvolené po stlačení 0); výber jazyka ho prepíše predvolenými hodnotami. Druhý parameter `sk`/`cs`/`en` výber preskočí a existujúci `config.ini` neprepíše (`install.bat "cesta" cs`). Riadok voľby je bez diakritiky (výstup `choice` v UTF-8 konzole). Overené 24. 11. 2026: parameter cs, nový config + 3, existujúci + 0 (ponechaný), existujúci + 1 (prepísaný slovenským). Hlášky dávok sú slovensky aj anglicky.
- Cesta k hre (obe dávky): parameter / pretiahnutý priečinok, inak priečinok nad dávkou alebo priečinok dávky (ak obsahuje `agds.exe`), inak `najdi_hru.ps1` – cesta Steamu z registra (HKCU/HKLM `Valve\Steam` SteamPath/InstallPath) a všetky knižnice z `steamapps\libraryfolders.vdf`, hľadá `steamapps\common\Black Mirrorgds.exe`. Overené 24. 11. 2026: inštalácia bez parametra našla hru, odinštalovanie odstránilo všetky súbory aj riadky v agds.cfg, nová inštalácia ich vrátila.

## Overené v hre (19. 11. 2026, 1920×1080, Windows 125 %)
- okno 0,0–1920×1080 bez rámu, obraz x 240–1679 (= 1440×1080, 4:3)
- logo Unknown Identity, hlavná ponuka, úvodný film (AVI cez YUY2) – správne a vycentrované
- myš: zvýraznenie položky ponuky a klik na „Nová hra“

Filmy (19. 11. 2026): úvod po „Nová hra“ a „Kapitola I“ roztiahnuté na 1920×870 (y 104–974), po filme sa obraz vráti na 4:3 (prvá scéna x 240–1680). Logá na začiatku zostávajú malé v strede. Po kapitole je chvíľu čierna obrazovka s rozprávačom – to je pôvodné správanie hry.

Neskúšané: dlhšie hranie (ďalšie kapitoly), ukladanie cez ESC → Uložit hru, Alt+Tab počas hry.
