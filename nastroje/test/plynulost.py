"""plynulost.py SEKUNDY – počas krúženia myšou zmeria tiky logiky/s a zobrazenia/s (počítadlá doplnku DDraw.dll)."""
import sys, time, subprocess, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ladenie import Kanal
t = float(sys.argv[1]) if len(sys.argv) > 1 else 5
k = Kanal()
p = subprocess.Popen([sys.executable, os.path.join(os.path.dirname(__file__), "krouz.py"), "400", "300", "120", str(t + 1)])
time.sleep(0.5); a = k.udalosti(); z = time.perf_counter(); time.sleep(t); b = k.udalosti(); dt = time.perf_counter() - z
p.wait()
print(f"tiky/s {(b[0]-a[0])/dt:.1f}  zobrazenia/s {(b[3]-a[3])/dt:.1f}  vyhladenie {b[5]/1e4:.1f} ms")
