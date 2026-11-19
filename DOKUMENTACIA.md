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
- Exe hry ani `agds.cfg` sa nemenia.

## Myš
Hra číta myš zo správ okna (WM_MOUSEMOVE), `GetCursorPos` neimportuje. dgVoodoo drží fyzický kurzor v priestore 800×600 a mapuje ho na zväčšený obraz – v hre to funguje správne. Pri automatickom teste treba `SetCursorPos` volať so súradnicami hry (0–799, 0–599), nie obrazovky.

## Inštalácia
- `instaluj.bat` – skopíruje 3 súbory do hry a zapíše príznak DPI (voliteľný parameter: cesta k hre)
- `obnov.bat` – súbory zmaže a príznak odstráni

## Overené v hre (19. 11. 2026, 1920×1080, Windows 125 %)
- okno 0,0–1920×1080 bez rámu, obraz x 240–1679 (= 1440×1080, 4:3)
- logo Unknown Identity, hlavná ponuka, úvodný film (AVI cez YUY2) – správne a vycentrované
- myš: zvýraznenie položky ponuky a klik na „Nová hra“

Neskúšané: hranie samotné (scény, inventár, dialógy), ukladanie, Alt+Tab počas hry.
