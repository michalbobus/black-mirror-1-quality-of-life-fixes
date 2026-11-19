import ctypes, sys, ctypes.wintypes as W
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
from PIL import ImageGrab
img = ImageGrab.grab(all_screens=True)
img.save(sys.argv[1]); print(img.size)
# okna hry
u=ctypes.windll.user32
def cb(h,l):
    if u.IsWindowVisible(h):
        pid=W.DWORD(); u.GetWindowThreadProcessId(h,ctypes.byref(pid))
        n=ctypes.create_unicode_buffer(256); u.GetWindowTextW(h,n,256)
        r=W.RECT(); u.GetWindowRect(h,ctypes.byref(r))
        st=u.GetWindowLongW(h,-16)
        if n.value and ('agds' in n.value.lower() or 'black' in n.value.lower() or 'mirror' in n.value.lower() or r.right-r.left>=1900):
            print(pid.value, repr(n.value), r.left,r.top,r.right,r.bottom, hex(st & 0xffffffff))
    return True
u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool,W.HWND,W.LPARAM)(cb),0)
