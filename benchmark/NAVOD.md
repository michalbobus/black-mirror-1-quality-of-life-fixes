# Benchmark doplnkov

Automatická kontrola úprav na viacerých scénach – spúšťať po každej zmene doplnku (`DDraw.dll`, `bm_core.dll`) pred vydaním.

## Spustenie
```
cd benchmark
python benchmark.py                   # všetky scény, kurzor hardware (predvolený)
python benchmark.py podkrovie         # len vybrané scény (mená zo zoznamu SCENY)
python benchmark.py --profil smooth   # iný režim kurzora: hardware | smooth | original
```
Beží asi 2,5 minúty na scénu. Počas behu nehýbať myšou a neprepínať okná – benchmark hru sám spustí aj ukončí.
Predtým skopírovať novú `dgvoodoo/DDraw.dll` do hry (benchmark testuje DLL nainštalovanú v hre).

## Čo sa kontroluje (pre každú scénu)
| krok | kontrola | OK |
|---|---|---|
| kolieska | načítanie (Ctrl+L) s myšou pri hornom okraji, potom myš vpravo hore | kolieska ponuky (`1006.100c`, postava `+0x82`) na obrazovke na (730, 2), snímky horného pásu `SCENA_0_kolieska_*.png`; `None` = kolieska nie sú v scéne (v poriadku) |
| značky + ESC | kombinácie načítania, koliesok a medzerníka: a) 3× medzerník + ESC + ESC, b) Ctrl+L a hneď medzerník + ESC, c) Ctrl+L počas značiek, d) ESC → Nahrát hru → pozícia 8 a hneď medzerník + ESC | hra nespadne a vráti sa do scény (pád v záhrade 24. 11. 2026 – pozícia s kolieskami uloženými v pozícii, medzerník a hneď ESC) |
| načítanie cez ponuku | ESC → Nahrát hru → pozícia 8 (benchmark ju dočasne pomenuje „benchmark“), kolieska každých 0,12 s | kolieska vždy (730, 2) alebo nie sú |
| zarovnanie | kurzor na 17 bodov vrátane okrajov (x 0 a 799, y 0 a 599) | poloha myši v hre (`0x506ff0` − posun scény) = zadaný bod; okno hardvérového kurzora je tam, kde by kurzor nakreslila hra (±2 px obrazovky); kurzor hry (animácia −10) pri bode do 32 px – platí aj pre smooth a original |
| posun scény | klik na opačnú stranu obrazu, postava ide (v širokej scéne sa scéna posunie), znova 4 body | rovnako ako zarovnanie |
| značky | podržaný medzerník | značky (`bmqol_hotspot`) v hernej ploche, snímka |
| plynulosť | krúženie myšou 3 s | kroky logiky/s (25), zobrazenia/s, presuny okna kurzora/s (stovky) |

Výsledok: `vysledky/RRRR-MM-DD_HHMM/vysledok.txt` (prehľad, pri chybe vypíše zlé body), `vysledok.json` (všetky hodnoty) a snímky `SCENA_1_start.png`, `SCENA_2_po_chodzi.png`, `SCENA_3_znacky.png` na kontrolu očami.

## Pozície (`pozicie/`)
| súbor | scéna | prečo |
|---|---|---|
| `hala.save` | hala zámku `10a1` (save.1 z pôvodnej hry) | základná scéna, 5 východov, video |
| `puda_hrad.save` | podkrovie hradu `10c8` | scéna širšia ako obraz (posun 600 px) – chyba kurzora 25. 11. 2026 |
| `puda_hrad_2.save` | podkrovie `10c8` uložené cez ponuku (pozícia 4 používateľa) | kolieska vľavo pri načítaní cez ponuku |
| `zahrada.save` | záhrada `10ab`, kolieska uložené v pozícii | pád pri medzerníku + ESC (24. 11. 2026), druhá scéna dielu hotspoty vo videu |

Pozície sú zároveň záloha: keď sa pozícia v hre prepíše, dá sa skopírovať späť (`copy pozicie\zahrada.save "...\Black Mirror\save.3"`).
Benchmark ich nahráva cez pozíciu 98 a pri načítaní cez ponuku cez pozíciu 8 (rýchle načítanie Ctrl+L z hlavnej ponuky); save.98, save.8 a ich mená v savnames.txt po behu vráti. Kľúče config.ini, ktoré mení (profil ako vo videu, `Sensitivity=1.0`), po behu vráti tiež.

**Nová scéna:** uložiť pozíciu v hre, skopírovať `save.N` do `pozicie/meno.save` a pridať riadok do `SCENY` v `benchmark.py`.

## Výsledky
| dátum | stav |
|---|---|
| 25. 11. 2026 | hala, podkrovie (posun 600 → 428), záhrada: myš OK, okno kurzora OK, značky 8/6/6, 25 krokov/s, ~405 presunov okna/s. So starou DLL (pred opravou) podkrovie: okno kurzora o −1080 px vedľa. |
| 25. 11. 2026 (načítanie cez ponuku, pád) | hala, podkrovie, podkrovie2, záhrada: všetko OK, značky + ESC vo všetkých kombináciách bez pádu. Kontrola pádu: s DLL spred opravy ce219c2 záhrada (hlavná ponuka → Nahrát hru → medzerník a hneď ESC) hra spadla pri 1. pokuse, s novou DLL 3/3 bez pádu. Prvá oprava koliesok (len pri kontrole hráča): pri načítaní cez ponuku 1,1 s (130, 2). |
| 25. 11. 2026 (oprava koliesok) | hardware: hala, podkrovie, záhrada všetko OK, kolieska (730, 2); smooth podkrovie: všetko OK, 25 krokov/s, 60 zobrazení/s. So DLL pred opravou koliesok: podkrovie kolieska (130, 2) = ZLE. |
