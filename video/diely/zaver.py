"""Záverečná karta: zoznam úprav a odkaz na stiahnutie."""
import os
VERZIE = ()
UPRAVY = [("bezokrajový fullscreen 16:9, Alt+Tab", "borderless 16:9 fullscreen, Alt+Tab"),
          ("CGI filmy na celú šírku", "full-width CGI movies"),
          ("hardvérový kurzor", "hardware cursor"),
          ("medzerník ukáže aktívne miesta", "Space shows hotspots"),
          ("dvojklik = rýchly presun", "double-click = instant move"),
          ("ESC preskočí rozhovory aj animácie", "ESC skips dialogues and animations"),
          ("vyhladené hrany postáv", "character anti-aliasing"),
          ("rýchle uloženie Ctrl+S / načítanie Ctrl+L", "quick save Ctrl+S / quick load Ctrl+L"),
          ("koliesko myši = predmety inventára", "mouse wheel cycles inventory items")]

def zostav(s):
    poz = None
    if os.path.exists(os.path.join(s.ZAZNAMY, "hotspoty_po.json")):
        z = s.Zaznam("hotspoty_po"); poz = s.snimka(z, z.start + 0.5)
    r = [("Black Mirror – Quality of Life Fixes", "podnadpis"), ("", "medzera")]
    for sk, en in UPRAVY: r.append((f"{sk}   ·   {en}", "en"))
    r += [("", "medzera"), ("github.com/michalbobus/black-mirror-1-quality-of-life-fixes", "text")]
    return s.karta(r, 9, pozadie=poz)
