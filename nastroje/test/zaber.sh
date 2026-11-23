# zaber.sh MENO RESAMPLING ISF [SMOOTHING] – SMOOTHING = [Video] Smoothing v config.ini hry (0 = vypnuté, 1 = FXAA)
S="$(cd "$(dirname "$0")" && pwd)"; H="/d/Hry/Steam/steamapps/common/Black Mirror"
taskkill //f //im agds.exe >/dev/null 2>&1; python -c "import time;time.sleep(1)"
python "$S/profil.py" "$1" "$2" "$3"
python -c "import ctypes,sys;ctypes.windll.kernel32.WritePrivateProfileStringW('Video','Smoothing',sys.argv[1],sys.argv[2])" "${4:-0}" "D:\Hry\Steam\steamapps\common\Black Mirror\config.ini"
(cd "$H" && cmd //c start "" agds.exe); python -c "import time;time.sleep(5)"
python "$S/klaves.py" 1B w2 1B w2 1B w3 >/dev/null
python "$S/mys.py" k 397 197 w 3
python -c "import ctypes;u=ctypes.windll.user32;u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4));u.SetCursorPos(799,10)"
python "$S/klaves.py" 1B w3 >/dev/null
python "$S/cakaj_scenu.py" "$S/../../snimky/profily/$1.png"
