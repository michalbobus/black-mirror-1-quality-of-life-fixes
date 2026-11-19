"""profil.py MENO RESAMPLING ISF – nastaví dgVoodoo.conf v hre (Resampling, ImageScaleFactor)."""
import re, sys
p = r'D:/Hry/Steam/steamapps/common/Black Mirror/dgVoodoo.conf'
d = open(p, 'rb').read().decode('latin-1')
d = re.sub(r'(?m)^(Resampling\s*=).*?(\r?)$', r'\1 ' + sys.argv[2] + r'\2', d)
d = re.sub(r'(?m)^(ImageScaleFactor\s*=).*?(\r?)$', r'\1 ' + sys.argv[3] + r'\2', d)
open(p, 'wb').write(d.encode('latin-1'))
print([l.strip() for l in d.splitlines() if l.startswith(('Resampling', 'ImageScaleFactor'))])
