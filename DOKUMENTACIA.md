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
  [Filmy]
  FullWidth=1     ; 1 = filmy na celú šírku, 0 = filmy v rámci 4:3 ako v pôvodnej hre
  ```
  Číta sa pri štarte hry (`GetPrivateProfileIntA`, cesta sa skladá z umiestnenia knižnice cez `GetModuleFileNameA`, takže nezáleží na pracovnom priečinku). Pri 0 sa háky vôbec nevložia. Keď súbor chýba, platí 1. `instaluj.bat` existujúci `config.ini` neprepíše, `obnov.bat` ho zmaže.
  Overené 19. 11. 2026: pri 0 sú v pamäti pôvodné bajty exe, pri 1 aj bez súboru sú háky vložené.
- Znovuzostavenie: `zostav_doplnok.bat`. Pozor: keystone zle počíta rozdiel návestí (`a - b`) a nepozná `rep movsd` – v zdroji sa to obchádza.
- Pomocné nástroje: `nastroje/rozbor.py` (reťazce, odkazy, disassembly exe), `nastroje/pamat.py` (čítanie/zápis pamäte bežiacej hry, moduly 32-bit procesu).

## Myš
Hra číta myš zo správ okna (WM_MOUSEMOVE), `GetCursorPos` neimportuje. dgVoodoo drží fyzický kurzor v priestore 800×600 a mapuje ho na zväčšený obraz – v hre to funguje správne. Pri automatickom teste treba `SetCursorPos` volať so súradnicami hry (0–799, 0–599), nie obrazovky.

## Inštalácia
- `instaluj.bat` – skopíruje do hry `dgddraw.dll`, `DDraw.dll`, `D3DImm.dll`, `dgVoodoo.conf` a `config.ini` (ten len ak ešte neexistuje) a zapíše príznak DPI (voliteľný parameter: cesta k hre)
- `obnov.bat` – súbory zmaže a príznak odstráni

## Overené v hre (19. 11. 2026, 1920×1080, Windows 125 %)
- okno 0,0–1920×1080 bez rámu, obraz x 240–1679 (= 1440×1080, 4:3)
- logo Unknown Identity, hlavná ponuka, úvodný film (AVI cez YUY2) – správne a vycentrované
- myš: zvýraznenie položky ponuky a klik na „Nová hra“

Filmy (19. 11. 2026): úvod po „Nová hra“ a „Kapitola I“ roztiahnuté na 1920×870 (y 104–974), po filme sa obraz vráti na 4:3 (prvá scéna x 240–1680). Logá na začiatku zostávajú malé v strede. Po kapitole je chvíľu čierna obrazovka s rozprávačom – to je pôvodné správanie hry.

Neskúšané: hranie samotné (scény, inventár, dialógy), ukladanie, Alt+Tab počas hry.
