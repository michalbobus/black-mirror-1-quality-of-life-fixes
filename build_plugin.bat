@echo off
chcp 65001 >nul
rem Znovu zostaví oba doplnky:
rem   dgvoodoo\bm_core.dll – filmy na celú šírku, plynulý kurzor, citlivosť (assembler v Pythone, balík keystone-engine)
rem   dgvoodoo\DDraw.dll   – doplnok pohodlia v C (doplnok\bm_qol.c, balík ziglang)
python "%~dp0nastroje\zostav_dll.py" "%~dp0dgvoodoo\bm_core.dll" || goto chyba
call "%~dp0doplnok\zostav.bat" || goto chyba
pause & exit /b 0
:chyba
echo Zostavenie zlyhalo.
pause & exit /b 1
