@echo off
chcp 65001 >nul
setlocal
set "HRA=D:\Hry\Steam\steamapps\common\Black Mirror"
if not "%~1"=="" set "HRA=%~1"
if not exist "%HRA%\agds.exe" (
  echo Nenašiel som agds.exe v "%HRA%".
  echo Použitie: install.bat "cesta\k\hre"
  pause & exit /b 1
)
rem dgddraw.dll = dgVoodoo2 2.87.6 (premenovaný DDraw.dll), DDraw.dll = doplnok pre filmy na celú šírku
copy /y "%~dp0dgvoodoo\dgddraw.dll"    "%HRA%\" >nul || goto chyba
copy /y "%~dp0dgvoodoo\DDraw.dll"      "%HRA%\" >nul || goto chyba
copy /y "%~dp0dgvoodoo\D3DImm.dll"     "%HRA%\" >nul || goto chyba
copy /y "%~dp0dgvoodoo\dgVoodoo.conf"  "%HRA%\" >nul || goto chyba
rem config.ini (zapnutie/vypnutie filmov na celú šírku) – existujúce nastavenie sa neprepíše
if not exist "%HRA%\config.ini" copy /y "%~dp0dgvoodoo\config.ini" "%HRA%\" >nul || goto chyba
rem Pri škálovaní Windows nad 100 % by okno vyšlo väčšie ako obrazovka – hra dostane príznak HIGHDPIAWARE
reg add "HKCU\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers" /v "%HRA%\agds.exe" /t REG_SZ /d "~ HIGHDPIAWARE" /f >nul || goto chyba
echo Hotovo: bezokrajový fullscreen, pomer strán 4:3 a filmy na celú šírku nainštalované do "%HRA%".
echo Filmy na celú šírku sa zapínajú/vypínajú v "%HRA%\config.ini" (FullWidth=1/0).
pause & exit /b 0
:chyba
echo Inštalácia zlyhala.
pause & exit /b 1
