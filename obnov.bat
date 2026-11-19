@echo off
chcp 65001 >nul
setlocal
set "HRA=D:\Hry\Steam\steamapps\common\Black Mirror"
if not "%~1"=="" set "HRA=%~1"
for %%S in (DDraw.dll D3DImm.dll dgVoodoo.conf) do if exist "%HRA%\%%S" del "%HRA%\%%S"
reg delete "HKCU\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers" /v "%HRA%\agds.exe" /f >nul 2>nul
echo Hotovo: hra je vrátená do pôvodného stavu.
pause
