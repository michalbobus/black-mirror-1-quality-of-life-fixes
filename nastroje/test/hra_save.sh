# hra_save.sh – ukončí hru, spustí ju a načíta save.1 (hala); pozície myši v súradniciach hry 800×600
S="$(cd "$(dirname "$0")" && pwd)"; H="/d/Hry/Steam/steamapps/common/Black Mirror"
taskkill //f //im agds.exe >/dev/null 2>&1; python -c "import time;time.sleep(1)"
(cd "$H" && cmd //c start "" agds.exe); python -c "import time;time.sleep(5)"
python "$S/klaves.py" 1B w2 1B w2 1B w3 >/dev/null
