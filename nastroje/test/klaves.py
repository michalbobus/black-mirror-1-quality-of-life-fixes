import ctypes, time, sys
u=ctypes.windll.user32
h=u.FindWindowW(None,"Posel smrti"); print("okno",h, "popredie", u.GetForegroundWindow()==h)
for k in sys.argv[1:]:
    if k.startswith('w'): time.sleep(float(k[1:])); continue
    vk=int(k,16); sc=u.MapVirtualKeyW(vk,0)
    u.keybd_event(vk,sc,0,0); time.sleep(0.08); u.keybd_event(vk,sc,2,0); time.sleep(0.5)
