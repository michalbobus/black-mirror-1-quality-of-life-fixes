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
  echo Black Mirror ^(agds.exe^) was not found, not even in Steam.
  echo Pretiahni priečinok hry na tento súbor alebo spusti: %~nx0 "cesta\k\hre"
  echo Drag the game folder onto this file or run: %~nx0 "path\to\game"
  pause & exit /b 1
)
echo Hra / Game: "%HRA%"
for %%S in (DDraw.dll bm_core.dll bm_qol.log dgddraw.dll D3DImm.dll dgVoodoo.conf config.ini) do if exist "%HRA%\%%S" del "%HRA%\%%S"
if exist "%HRA%\agds.cfg" (
  findstr /i /v /b "optimizedraw= videomem=" "%HRA%\agds.cfg" > "%HRA%\agds.cfg.tmp" && move /y "%HRA%\agds.cfg.tmp" "%HRA%\agds.cfg" >nul
)
reg delete "HKCU\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers" /v "%HRA%\agds.exe" /f >nul 2>nul
echo Hotovo: hra je vrátená do pôvodného stavu.
echo Done: the game is restored to its original state.
pause
