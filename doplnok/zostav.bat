@echo off
chcp 65001 >nul
rem Zostaví dgvoodoo\DDraw.dll (doplnok pohodlia, zdroj doplnok\bm_qol.c) – treba Python s balíkom ziglang (pip install ziglang)
cd /d "%~dp0"
python -m ziglang cc -target x86-windows-gnu -mcpu=pentium4 -O2 -Wall -fno-stack-protector -c -o "%TEMP%\bm_qol.o" bm_qol.c || goto chyba
python -m ziglang cc -target x86-windows-gnu -shared -nostdlib -Wl,--entry=DllMain@12 -o ..\dgvoodoo\DDraw.dll "%TEMP%\bm_qol.o" bm_qol.def -lkernel32 -luser32 || goto chyba
del "%TEMP%\bm_qol.o" 2>nul
del ..\dgvoodoo\DDraw.lib ..\dgvoodoo\DDraw.pdb ..\dgvoodoo\bm_qol.lib 2>nul
echo Hotovo: dgvoodoo\DDraw.dll
exit /b 0
:chyba
echo Zostavenie zlyhalo.
exit /b 1
