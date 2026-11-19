# Rozpracované – vyhladzovanie postáv (stav 19. 11. 2026)

## Zadanie
Preskúmať profily vyhladzovania postáv na obrazovke: niečo decentné, čo vyhladí hrany z interného 800×600, aby to vyzeralo dobre na Full HD a vyššom rozlíšení. Najlepšie vidno v novej hre po preskočení CGI filmov (prvá scéna – salón so štyrmi postavami).

## Hotové pred touto úlohou (commit 67a4773)
- citlivosť kurzora `[Cursor] Sensitivity` (0.1–1.0, predvolené 0.5), overené meraním,
- overené: plynulý kurzor (Fps=60) rýchlosť kurzora nemení.

## Postup záberu (automatizovaný)
Skripty v `nastroje/test/` (cesty v nich vedú do scratchpadu relácie – pri ďalšom použití upraviť premennú `S` / cesty):
- `profil.py MENO RESAMPLING ISF` – zapíše `Resampling` a `ImageScaleFactor` do dgVoodoo.conf v hre,
- `zaber.sh MENO RESAMPLING ISF` – ukončí hru, nastaví profil, spustí hru, 3× ESC (logá), klik „Nová hra“ (hra 397,197), ESC (úvodný film), potom `cakaj_scenu.py`,
- `cakaj_scenu.py VYSTUP.png` – čaká, kým svietia lampy vľavo (jas výrezu x270–450, y150–330 > 70), kým nie, stláča ESC každých 6 s; potom 2 s a snímka celej obrazovky.
- Postavy v zábere: približne x 480–960, y 380–760 (obrazovka 1920×1080).
- Po teste vrátiť dgVoodoo.conf z `dgvoodoo/` do hry.

## Plán
1. Nasnímať profily dgVoodoo (`Resampling`): `pointsampled` (hotové: snimky/profily/point.png), `bilinear` (súčasné), `bicubic`, `lanczos-2`, `lanczos-3`, a `ImageScaleFactor=2` + `bilinear` (predzväčšenie 1600×1200 najbližším bodom, potom zmenšenie na 1440×1080).
2. Porovnať výrezy postáv vedľa seba (zväčšené 2×), vybrať 2–3 kandidátov.
3. Ak dgVoodoo filtre nestačia (hrany postáv ostanú zubaté/rozmazané): preskúmať vyhladzovanie hrán pred zväčšením – napr. ReShade nad výstupom dgVoodoo (D3D11) s FXAA/SMAA alebo upscaler typu xBR/ScaleFX/FSR (EASU), prípadne vlastné vyhladenie 800×600 snímky v doplnku DDraw.dll (zadný povrch je teraz v systémovej pamäti – videomem=0, pred Blt do primárneho povrchu 0x43e78f).
4. Vybraný profil (alebo voľbu profilov) dať do `config.ini` / dgVoodoo.conf, doplniť install/uninstall, DOKUMENTACIA.md, commit.
