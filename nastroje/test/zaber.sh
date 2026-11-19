# zaber.sh MENO RESAMPLING ISF
S="C:/Users/MICHAL~1/AppData/Local/Temp/claude/4a7b9532acc0dc69/5e5203e9-5456-450c-b393-4bd1dec1d019/scratchpad"; H="/d/Hry/Steam/steamapps/common/Black Mirror"
taskkill //f //im agds.exe >/dev/null 2>&1; python -c "import time;time.sleep(1)"
python "$S/profil.py" "$1" "$2" "$3"
(cd "$H" && cmd //c start "" agds.exe); python -c "import time;time.sleep(5)"
python "$S/klaves.py" 1B w2 1B w2 1B w3 >/dev/null
python "$S/mys.py" k 397 197 w 3
python -c "import ctypes;u=ctypes.windll.user32;u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4));u.SetCursorPos(799,10)"
python "$S/klaves.py" 1B w3 >/dev/null
python "$S/cakaj_scenu.py" "$S/profily/$1.png"
