# Benchmark doplnkov

Automatická kontrola úprav na viacerých scénach – spúšťať po každej zmene doplnku (`DDraw.dll`, `bm_core.dll`) pred vydaním.

## Spustenie
```
cd benchmark
python benchmark.py                   # všetky scény, kurzor hardware (predvolený)
python benchmark.py podkrovie         # len vybrané scény (mená zo zoznamu SCENY)
python benchmark.py --profil smooth   # iný režim kurzora: hardware | smooth | original
```
Beží asi 1,5 minúty na scénu. Počas behu nehýbať myšou a neprepínať okná – benchmark hru sám spustí aj ukončí.
Predtým skopírovať novú `dgvoodoo/DDraw.dll` do hry (benchmark testuje DLL nainštalovanú v hre).

## Čo sa kontroluje (pre každú scénu)
| krok | kontrola | OK |
|---|---|---|
| zarovnanie | kurzor na 17 bodov vrátane okrajov (x 0 a 799, y 0 a 599) | poloha myši v hre (`0x506ff0` − posun scény) = zadaný bod; okno hardvérového kurzora je tam, kde by kurzor nakreslila hra (±2 px obrazovky) |
| posun scény | klik na opačnú stranu obrazu, postava ide (v širokej scéne sa scéna posunie), znova 4 body | rovnako ako zarovnanie |
| značky | podržaný medzerník | značky (`bmqol_hotspot`) v hernej ploche, snímka |
| plynulosť | krúženie myšou 3 s | kroky logiky/s (25), zobrazenia/s, presuny okna kurzora/s (stovky) |

Výsledok: `vysledky/RRRR-MM-DD_HHMM/vysledok.txt` (prehľad, pri chybe vypíše zlé body), `vysledok.json` (všetky hodnoty) a snímky `SCENA_1_start.png`, `SCENA_2_po_chodzi.png`, `SCENA_3_znacky.png` na kontrolu očami.

## Pozície (`pozicie/`)
| súbor | scéna | prečo |
|---|---|---|
| `hala.save` | hala zámku `10a1` (save.1 z pôvodnej hry) | základná scéna, 5 východov, video |
| `puda_hrad.save` | podkrovie hradu `10c8` | scéna širšia ako obraz (posun 600 px) – chyba kurzora 25. 11. 2026 |
| `zahrada.save` | záhrada `10ab` | druhá scéna dielu hotspoty vo videu |

Pozície sú zároveň záloha: keď sa pozícia v hre prepíše, dá sa skopírovať späť (`copy pozicie\zahrada.save "...\Black Mirror\save.3"`).
Benchmark ich nahráva cez pozíciu 98 (rýchle načítanie Ctrl+L z hlavnej ponuky); save.98 a jej meno v savnames.txt po behu vráti. Kľúče config.ini, ktoré mení (profil ako vo videu, `Sensitivity=1.0`), po behu vráti tiež.

**Nová scéna:** uložiť pozíciu v hre, skopírovať `save.N` do `pozicie/meno.save` a pridať riadok do `SCENY` v `benchmark.py`.

## Výsledky
| dátum | stav |
|---|---|
| 25. 11. 2026 | hala, podkrovie (posun 600 → 428), záhrada: myš OK, okno kurzora OK, značky 8/6/6, 25 krokov/s, ~405 presunov okna/s. So starou DLL (pred opravou) podkrovie: okno kurzora o −1080 px vedľa. |
