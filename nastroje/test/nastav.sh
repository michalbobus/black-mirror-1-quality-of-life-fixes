# nastav.sh FPS SENS – zapíše config.ini do hry, spustí ju a dostane sa do hlavnej ponuky
H="/d/Hry/Steam/steamapps/common/Black Mirror"; S="C:/Users/MICHAL~1/AppData/Local/Temp/claude/4a7b9532acc0dc69/5e5203e9-5456-450c-b393-4bd1dec1d019/scratchpad"
taskkill //f //im agds.exe >/dev/null 2>&1; python -c "import time;time.sleep(1)"
printf '[Movies]\r\nFullWidth=1\r\n[Cursor]\r\nFps=%s\r\nSensitivity=%s\r\n' "$1" "$2" > "$H/config.ini"
(cd "$H" && cmd //c start "" agds.exe); python -c "import time;time.sleep(5)"
python "$S/klaves.py" 1B w2 1B w2 1B w3 >/dev/null
