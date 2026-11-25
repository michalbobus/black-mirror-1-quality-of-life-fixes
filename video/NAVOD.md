# Prezentačné video (trailer) – pôvodná hra a hra s úpravami

Trailer sa skladá z **dielov**. Každý diel je samostatný súbor v `diely/` a dá sa kedykoľvek znova nahrať a zostaviť bez ostatných.

## Rýchly postup
```
cd video
python nahraj.py kurzor          # nahrá diel kurzor: pôvodnú hru aj hru s úpravami
python nahraj.py kurzor po       # len verziu s úpravami (pred | po)
python zostav.py kurzor          # zostaví diel do vystup/diely/kurzor.mp4
python zostav.py                 # zostaví všetky diely a celý trailer vystup/trailer.mp4
```
Počas nahrávania sa nesmie hýbať myšou ani prepínať okná – hra musí byť v popredí (spúšťa ju nahrávač sám, aj ju ukončí).
Hlasitosť systému nevadí: zvuk sa nahráva cez WASAPI loopback pred systémovou hlasitosťou a celý trailer sa vyrovná na −16 LUFS.

## Súbory
| súbor | čo robí |
|---|---|
| `nahravac.py` | záznam obrazovky (ffmpeg ddagrab 60 snímok/s, x264) a zvuku hry (pyaudiowpatch), ovládanie hry (klávesy, myš v súradniciach hry 800×600), profily `PRED`/`PO` |
| `skladac.py` | skladanie zo záznamov: `vyrez`, `vedla` (pôvodná hra / s úpravami vedľa seba), `samostatne`, `karta`, `za_sebou`, `zastav`, odznaky klávesov, časovače |
| `nahraj.py` | spustí `nahraj(verzia)` dielu, na konci vráti nastavenia config.ini |
| `zostav.py` | zostaví diely; poradie dielov v traileri = zoznam `PORADIE` |
| `diely/*.py` | jeden diel = `NAZOV`, `nahraj(verzia)`, `zostav(s)`; `VERZIE = ()` = diel bez nahrávania (karta) |
| `ref_ponuka.png` | výrez nadpisu hlavnej ponuky – podľa neho nahrávač pozná, že hra je v ponuke |
| `zaznamy/` | nahraté záznamy `DIEL_pred|po.mkv/.wav/.json` (nie sú v gite) |
| `vystup/` | `diely/*.mp4`, `trailer.mp4`, `tmp/` = medzivýsledky (nie sú v gite) |

## Diely (poradie v traileri)
| diel | obsah | scéna |
|---|---|---|
| `uvod` | úvodná karta | rozmazaná hala |
| `obraz` | karta o bezokrajovom okne + záber celej obrazovky 16:9 (Alt+Tab sa vo videu neukazuje) | hala (záznam `kurzor_po`) |
| `filmy` | úvodný film novej hry vedľa seba | Nová hra |
| `kurzor` | krúženie a prechod po predmetoch + spomalené 4× | hala (save.1) |
| `hotspoty` | podržaný medzerník | hala + záhrada (save.3, len načítanie; záloha benchmark/pozicie/zahrada.save) |
| `dvojklik` | klik vs. dvojklik, potom k východu do jedálne | hala |
| `preskakovanie` | podržaný ESC v úvode novej hry, časovače, pôvodná hra zrýchlene 12× (2:54 → 0:02) | rozprávač + salón |
| `vyhladzovanie` | zväčšený detail Samuela, dva výrezy | hala |
| `rychle_ulozenie` | Ctrl+S / Ctrl+L vs. kolieska → Uložit hru → pozícia 8 → názov a Nahrát hru | hala |
| `koliesko` | koliesko vs. lišta inventára + pravý klik | hala |
| `zaver` | zoznam úprav + odkaz na GitHub | – |

## Nový diel
1. `diely/meno.py` s `NAZOV = ("slovensky", "english")`, `nahraj(verzia)` a `zostav(s)` (vzor: `hotspoty.py`).
2. V `nahraj` použiť `do_haly(profil(verzia))` alebo `spusti(...)` + `nahraj_poziciu(n)`, záznam `with Zaznam(f"meno_{verzia}") as z:` a značky `z.znacka("...")`.
3. V `zostav` časy podľa značiek: `a.znacka("start")`, udalosti `b.udalosti("klaves")`.
4. Pridať meno do `PORADIE` v `zostav.py`.

## Ochrana hry
- Profil mení len kľúče doplnku v config.ini. Pôvodné hodnoty sa pri prvom nahrávaní uložia do `zaznamy/povodne_nastavenia.json`; po nahrávaní sa vrátia a súbor sa zmaže. Ostane len pri prerušení a ďalší beh ho použije.
- Pozície, do ktorých diel ukladá (8 a 98), chráni `OchranaPozicii`: po dieli vráti save.N aj záznam N v savnames.txt (51 B na pozíciu).
- Pôvodná hra = rovnaký dgVoodoo, všetky doplnky vypnuté (`Mode=original`, `FullWidth=0`, `Smoothing=0`, `Controls` 0). Obraz hry je totožný s pôvodným; pôvodný exkluzívny režim 800×600 sa nahrať nedá (opisuje ho karta).
- V testoch je `Sensitivity=1.0`, aby SetCursorPos zodpovedal súradniciam hry.

## Úskalia
- Podržaný kláves musí posielať opakované stlačenia ako skutočná klávesnica (`drz` po 0,5 s 30×/s), inak hra značky medzerníka po 2 s skryje.
- Desktop Duplication (ddagrab) skončí chybou 887a0026 pri prepnutí z hry na plochu (Alt+Tab) – preto Alt+Tab nie je nahrávaný.
- Prvý klik po návrate z ponuky hra ignoruje – v dieli rýchle uloženie sa klikne dvakrát.
- Hra musí byť v popredí (`popredie()` stlačí Alt naprázdno, inak Windows SetForegroundWindow odmietne).
- NVENC na GTX 1060 s ovládačom 560 nejde (ffmpeg 9 chce 610+), záznam je cez x264 ultrafast.
