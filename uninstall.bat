@echo off
chcp 65001 >nul
setlocal
set "HRA=D:\Hry\Steam\steamapps\common\Black Mirror"
if not "%~1"=="" set "HRA=%~1"
for %%S in (DDraw.dll dgddraw.dll D3DImm.dll dgVoodoo.conf config.ini) do if exist "%HRA%\%%S" del "%HRA%\%%S"
if exist "%HRA%\agds.cfg" (
  findstr /i /v /b "optimizedraw=" "%HRA%\agds.cfg" > "%HRA%\agds.cfg.tmp" && move /y "%HRA%\agds.cfg.tmp" "%HRA%\agds.cfg" >nul
)
reg delete "HKCU\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers" /v "%HRA%\agds.exe" /f >nul 2>nul
echo Hotovo: hra je vrátená do pôvodného stavu.
pause
