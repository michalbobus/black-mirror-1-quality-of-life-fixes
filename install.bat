@echo off
rem Súbor je v kódovaní 852 (OEM slovenského/českého Windows), cmd ho vypíše bez chcp - chcp 65001 by prepol okno na staré bodové písmo
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
  echo Nenašiel som hru Black Mirror ^(agds.exe^) - ani v Steame.
  echo Black Mirror ^(agds.exe^) was not found, not even in Steam.
  echo Pretiahni priečinok hry na tento súbor alebo spusti: %~nx0 "cesta\k\hre"
  echo Drag the game folder onto this file or run: %~nx0 "path\to\game"
  pause & exit /b 1
)
echo Hra / Game: "%HRA%"
rem dgddraw.dll = dgVoodoo2 2.87.6 (premenovaný DDraw.dll); DDraw.dll = doplnok pohodlia (ESC, hotspoty, preskakovanie, koliesko, nastavenia)
rem -> bm_core.dll = filmy na celú šírku, plynulý kurzor, citlivosť -> dgddraw.dll
copy /y "%~dp0dgvoodoo\dgddraw.dll"    "%HRA%\" >nul || goto chyba
copy /y "%~dp0dgvoodoo\DDraw.dll"      "%HRA%\" >nul || goto chyba
copy /y "%~dp0dgvoodoo\bm_core.dll"    "%HRA%\" >nul || goto chyba
copy /y "%~dp0dgvoodoo\D3DImm.dll"     "%HRA%\" >nul || goto chyba
copy /y "%~dp0dgvoodoo\dgVoodoo.conf"  "%HRA%\" >nul || goto chyba
rem config.ini (zapnutie/vypnutie jednotlivých úprav): jazyk poznámok si vyberie hráč (config.sk/cs/en.ini).
rem Druhý parameter sk/cs/en výber preskočí (napr. install.bat "cesta" en). Existujúci config.ini sa prepíše
rem len ak si hráč výslovne vyberie jazyk (nastavenia sa tým vrátia na predvolené).
set "JAZYK=%~2"
if defined JAZYK goto config_zapis
echo.
if exist "%HRA%\config.ini" (
  echo config.ini už v hre je - 0 = ponechať ^(nastavenia ostanú^), alebo vyber jazyk nových predvolených nastavení.
  echo config.ini already exists - 0 = keep it ^(settings are kept^), or choose a language for new default settings.
  choice /c 0123 /n /m "0 = ponechať / keep, 1 = slovensky, 2 = česky, 3 = English: "
) else (
  echo Jazyk poznámok v config.ini / Language of the comments in config.ini:
  choice /c 123 /n /m "1 = slovensky, 2 = česky, 3 = English: "
)
set "VOLBA=%errorlevel%"
if exist "%HRA%\config.ini" set /a VOLBA-=1
if "%VOLBA%"=="1" set "JAZYK=sk"
if "%VOLBA%"=="2" set "JAZYK=cs"
if "%VOLBA%"=="3" set "JAZYK=en"
if not defined JAZYK goto config_hotovo
:config_zapis
if exist "%HRA%\config.ini" if not "%~2"=="" goto config_hotovo
if not exist "%~dp0dgvoodoo\config.%JAZYK%.ini" set "JAZYK=en"
copy /y "%~dp0dgvoodoo\config.%JAZYK%.ini" "%HRA%\config.ini" >nul || goto chyba
echo config.ini: %JAZYK%
:config_hotovo
rem Jazyk hlášok: česky + anglicky, ak je config.ini v hre český (slovo "kurzoru"), inak slovensky + anglicky
set "HL=sk"
if exist "%HRA%\config.ini" findstr /c:"kurzoru" "%HRA%\config.ini" >nul && set "HL=cs"
rem pri výbere jazyka v tejto inštalácii platí výber
if "%JAZYK%"=="cs" set "HL=cs"
if "%JAZYK%"=="sk" set "HL=sk"
if "%JAZYK%"=="en" set "HL=sk"
rem agds.cfg: optimizedraw=0 = hra posiela na obrazovku vždy celú snímku (inak ostávajú zvyšky nápisov a kurzora)
findstr /i /b "optimizedraw=" "%HRA%\agds.cfg" >nul || (>>"%HRA%\agds.cfg" echo optimizedraw=0) || goto chyba
rem agds.cfg: videomem=0 = zadný povrch v systémovej pamäti (rýchle kreslenie, potrebné pre plynulý kurzor)
findstr /i /b "videomem=" "%HRA%\agds.cfg" >nul || (>>"%HRA%\agds.cfg" echo videomem=0) || goto chyba
rem Pri škálovaní Windows nad 100 % by okno vyšlo väčšie ako obrazovka - hra dostane príznak HIGHDPIAWARE
reg add "HKCU\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers" /v "%HRA%\agds.exe" /t REG_SZ /d "~ HIGHDPIAWARE" /f >nul || goto chyba
if "%HL%"=="cs" goto hotovo_cs
echo Hotovo: úpravy pre Black Mirror nainštalované do "%HRA%".
echo Done: Black Mirror improvements installed to "%HRA%".
echo Jednotlivé úpravy sa zapínajú/vypínajú v "%HRA%\config.ini".
echo Each improvement can be switched on/off in "%HRA%\config.ini".
pause & exit /b 0
:hotovo_cs
echo Hotovo: úpravy pro Black Mirror nainstalovány do "%HRA%".
echo Done: Black Mirror improvements installed to "%HRA%".
echo Jednotlivé úpravy se zapínají/vypínají v "%HRA%\config.ini".
echo Each improvement can be switched on/off in "%HRA%\config.ini".
pause & exit /b 0
:chyba
if "%HL%"=="cs" (echo Instalace selhala. / Installation failed.) else (echo Inštalácia zlyhala. / Installation failed.)
pause & exit /b 1
