@echo off
chcp 65001 >nul
setlocal
rem Cesta k hre: parameter (aj pretiahnutie priečinka hry na tento súbor), inak priečinok nad týmto,
rem inak tento priečinok, inak hľadanie v Steame (najdi_hru.ps1).
set "HRA="
if not "%~1"=="" set "HRA=%~1"
if not defined HRA if exist "%~dp0..\agds.exe" set "HRA=%~dp0.."
if not defined HRA if exist "%~dp0agds.exe" set "HRA=%~dp0."
if not defined HRA for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0najdi_hru.ps1"`) do set "HRA=%%P"
if not defined HRA set "HRA=(nenájdená)"
if not exist "%HRA%\agds.exe" (
  echo Nenašiel som hru Black Mirror ^(agds.exe^) – ani v Steame.
  echo Pretiahni priečinok hry na tento súbor alebo spusti: %~nx0 "cesta\k\hre"
  pause & exit /b 1
)
echo Hra: "%HRA%"
rem dgddraw.dll = dgVoodoo2 2.87.6 (premenovaný DDraw.dll); DDraw.dll = doplnok pohodlia (ESC, hotspoty, preskakovanie, koliesko, nastavenia)
rem -> bm_core.dll = filmy na celú šírku, plynulý kurzor, citlivosť -> dgddraw.dll
copy /y "%~dp0dgvoodoo\dgddraw.dll"    "%HRA%\" >nul || goto chyba
copy /y "%~dp0dgvoodoo\DDraw.dll"      "%HRA%\" >nul || goto chyba
copy /y "%~dp0dgvoodoo\bm_core.dll"    "%HRA%\" >nul || goto chyba
copy /y "%~dp0dgvoodoo\D3DImm.dll"     "%HRA%\" >nul || goto chyba
copy /y "%~dp0dgvoodoo\dgVoodoo.conf"  "%HRA%\" >nul || goto chyba
rem config.ini (zapnutie/vypnutie jednotlivých úprav) – existujúce nastavenie sa neprepíše
if not exist "%HRA%\config.ini" copy /y "%~dp0dgvoodoo\config.ini" "%HRA%\" >nul || goto chyba
rem agds.cfg: optimizedraw=0 = hra posiela na obrazovku vždy celú snímku (inak ostávajú zvyšky nápisov a kurzora)
findstr /i /b "optimizedraw=" "%HRA%\agds.cfg" >nul || (>>"%HRA%\agds.cfg" echo optimizedraw=0) || goto chyba
rem agds.cfg: videomem=0 = zadný povrch v systémovej pamäti (rýchle kreslenie, potrebné pre plynulý kurzor)
findstr /i /b "videomem=" "%HRA%\agds.cfg" >nul || (>>"%HRA%\agds.cfg" echo videomem=0) || goto chyba
rem Pri škálovaní Windows nad 100 % by okno vyšlo väčšie ako obrazovka – hra dostane príznak HIGHDPIAWARE
reg add "HKCU\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers" /v "%HRA%\agds.exe" /t REG_SZ /d "~ HIGHDPIAWARE" /f >nul || goto chyba
echo Hotovo: úpravy pre Black Mirror nainštalované do "%HRA%".
echo Jednotlivé úpravy sa zapínajú/vypínajú v "%HRA%\config.ini".
pause & exit /b 0
:chyba
echo Inštalácia zlyhala.
pause & exit /b 1
