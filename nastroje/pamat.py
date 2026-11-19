"""Čítanie/zápis pamäte bežiacej hry (agds.exe) – na hľadanie premenných dgVoodoo."""
import ctypes, ctypes.wintypes as W, struct, sys, subprocess

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p), ("AllocationProtect", W.DWORD),
                ("PartitionId", W.WORD), ("RegionSize", ctypes.c_size_t), ("State", W.DWORD), ("Protect", W.DWORD), ("Type", W.DWORD)]

def pid_hry(meno="agds.exe"):
    out = subprocess.run(["tasklist", "/fi", f"imagename eq {meno}", "/fo", "csv", "/nh"], capture_output=True, text=True).stdout
    for r in out.splitlines():
        if meno.lower() in r.lower(): return int(r.split('","')[1])
    raise SystemExit("hra nebeží")

def otvor(pid):
    return k32.OpenProcess(0x1F0FFF, False, pid)

def oblasti(h):
    a = 0; m = MBI()
    while a < 0x7FFF0000 and k32.VirtualQueryEx(h, ctypes.c_void_p(a), ctypes.byref(m), ctypes.sizeof(m)):
        if m.State == 0x1000 and m.Protect & 0xEE and not m.Protect & 0x100:
            yield m.BaseAddress, m.RegionSize, m.Type
        a = (m.BaseAddress or 0) + m.RegionSize

def citaj(h, a, n):
    b = ctypes.create_string_buffer(n); r = ctypes.c_size_t()
    k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)); return b.raw[:r.value]

def zapis(h, a, data):
    r = ctypes.c_size_t()
    return k32.WriteProcessMemory(h, ctypes.c_void_p(a), data, len(data), ctypes.byref(r))

def hladaj(h, vzor):
    for a, n, t in oblasti(h):
        d = citaj(h, a, n); i = d.find(vzor)
        while i >= 0:
            yield a + i, t; i = d.find(vzor, i + 1)

def moduly(pid):
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
        f"(Get-Process -Id {pid}).Modules | % {{ '{{0:x}} {{1:x}} {{2}}' -f [int64]$_.BaseAddress, $_.ModuleMemorySize, $_.ModuleName }}"],
        capture_output=True, text=True).stdout
    return [(int(a, 16), int(n, 16), m) for a, n, m in (l.split(None, 2) for l in out.splitlines() if l.strip())]

if __name__ == "__main__":
    pid = pid_hry(); h = otvor(pid)
    mods = moduly(pid)
    def kde(a):
        for b, n, m in mods:
            if b <= a < b + n: return f"{m}+{a-b:x}"
        return "?"
    vals = [int(x) for x in sys.argv[1:]]
    vzor = struct.pack("<%di" % len(vals), *vals)
    for a, t in hladaj(h, vzor):
        print(hex(a), hex(t), kde(a), citaj(h, a - 16, 48).hex())

class ME32(ctypes.Structure):
    _fields_ = [("dwSize", W.DWORD), ("th32ModuleID", W.DWORD), ("th32ProcessID", W.DWORD), ("GlblcntUsage", W.DWORD),
                ("ProccntUsage", W.DWORD), ("modBaseAddr", ctypes.c_void_p), ("modBaseSize", W.DWORD), ("hModule", W.HMODULE),
                ("szModule", ctypes.c_char * 256), ("szExePath", ctypes.c_char * 260)]

def moduly32(pid):
    """Moduly 32-bitového procesu (Toolhelp, SNAPMODULE | SNAPMODULE32)."""
    s = k32.CreateToolhelp32Snapshot(0x18, pid); m = ME32(); m.dwSize = ctypes.sizeof(m); r = []
    ok = k32.Module32First(s, ctypes.byref(m))
    while ok:
        r.append((m.modBaseAddr, m.modBaseSize, m.szModule.decode())); ok = k32.Module32Next(s, ctypes.byref(m))
    k32.CloseHandle(s); return r
