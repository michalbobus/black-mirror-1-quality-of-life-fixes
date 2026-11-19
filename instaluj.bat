@echo off
chcp 65001 >nul
setlocal
set "HRA=D:\Hry\Steam\steamapps\common\Black Mirror"
if not "%~1"=="" set "HRA=%~1"
if not exist "%HRA%\agds.exe" (
  echo Nenašiel som agds.exe v "%HRA%".
  echo Použitie: instaluj.bat "cesta\k\hre"
  pause & exit /b 1
)
copy /y "%~dp0dgvoodoo\DDraw.dll"      "%HRA%\" >nul || goto chyba
copy /y "%~dp0dgvoodoo\D3DImm.dll"     "%HRA%\" >nul || goto chyba
copy /y "%~dp0dgvoodoo\dgVoodoo.conf"  "%HRA%\" >nul || goto chyba
rem Pri škálovaní Windows nad 100 % by okno vyšlo väčšie ako obrazovka – hra dostane príznak HIGHDPIAWARE
reg add "HKCU\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers" /v "%HRA%\agds.exe" /t REG_SZ /d "~ HIGHDPIAWARE" /f >nul || goto chyba
echo Hotovo: bezokrajový fullscreen + pomer strán 4:3 nainštalované do "%HRA%".
pause & exit /b 0
:chyba
echo Inštalácia zlyhala.
pause & exit /b 1
