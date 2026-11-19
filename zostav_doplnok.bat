@echo off
chcp 65001 >nul
rem Znovu zostaví dgvoodoo\DDraw.dll (doplnok pre filmy) – treba Python s balíkom keystone-engine
python "%~dp0nastroje\zostav_dll.py" "%~dp0dgvoodoo\DDraw.dll"
pause
