# Zoznam opráv – poznatky pre patche hier na engine AGDS

Technická informačná báza z úprav **Black Mirror (Posel smrti)**, verzia 1.0.0 – 1.0.2. Je určená pre ďalšie patche hier na engine AGDS od Future Games (napr. **NiBiRu: Posel bohů**, **Reprobates**). Každá položka má štyri časti: problém, príčinu, riešenie a ako sa mu vyhnúť už počas vývoja. Podrobné merania a postupy sú v [DOKUMENTACIA.md](DOKUMENTACIA.md).

**Adresy** platia pre `agds.exe` Black Mirror (Steam, AGDS 2.299, build 8. 9. 2005, 671 744 B). V inej hre alebo verzii enginu budú iné. Funkcie a premenné sa dajú nájsť podľa reťazcov, volaní importov (`SetCursorPos`, `PeekMessage`, `Blt`) a rovnakých vzorov kódu. Doplnok musí pred každým hákom overiť pôvodné bajty a pri nezhode hák nevložiť.

---

## 0. Základy enginu, ktoré treba poznať skôr, než sa začne čokoľvek písať

- **Rozlíšenie a renderer:** DirectDraw 7, vnútorné rozlíšenie 800×600×32. Engine kreslí softvérovo do zadného povrchu (`0x597e60`) a funkcia zobrazenia (`0x43e78f`) ho cez `Blt` pošle do primárneho povrchu. Na moderných systémoch beží cez dgVoodoo2 (DirectDraw → Direct3D 11).
- **Krok hry:** logika beží pevne **25 krokov/s** (40 ms). Animácie, chôdza, časovače skriptov aj kurzor sú viazané na krok. Zrýchlenie kroku zrýchli celú hru. Hlavná slučka je `0x44218d` (PeekMessage → logika `0x402dfb` + zobrazenie). Logika čaká na ďalší krok aktívne (QPC + `SleepEx(0)`).
- **Tri súradnicové priestory** (najčastejší zdroj chýb, pozri 2.1 a 2.2):
  1. **obrazovka Windows** – fyzické pixely monitora (pri 1920×1080 a mierke 1,8 je obraz 4:3 na x 240–1679),
  2. **obraz hry 800×600** – to, čo hra vidí ako obrazovku; dgVoodoo drží fyzický kurzor v obdĺžniku 800×600 cez `ClipCursor`,
  3. **scéna** – môže byť širšia (alebo vyššia) ako 800×600. Posun scény je v `scéna+0x5d5` (x) a `+0x5d9` (y). **V súradniciach scény sú:** poloha myši hry `0x506ff0/0x506fa8` (už vrátane posunu!), animácie (`+0x1c/+0x20`), postavy (`+0x37e/+0x382`), regióny objektov. Prepočet na obraz = scéna − posun.
- **Scéna = objekty + animácie:** objekty sú v kruhovom zozname `scéna+0x40` (prvý `[+0x28]`, ďalší `[obj+0]`), animácie v kruhovom zozname `scéna+0x80`. Kurzor je tiež animácia (poradie −10). Ponuky sú tiež scény (`1006.*`).
- **Kontrola hráča:** `0x4305d1()` ≥ 1 (premenné `0x48b658 && 0x48b678`). Počas načítania pozície, rozhovoru a prechodu východom je 0.
- **Pamäť enginu:** engine pri uvoľnení scény uvoľňuje pixely všetkých animácií vlastným alokátorom (pozri 4.1).
- **Kódovanie textov:** Kamenických (š = 0xA8, í = 0xA1), nie cp1250 ani 852.

---

## 1. Obraz a zobrazenie

### 1.1 Okno posunuté a zväčšené pri škálovaní Windows (DPI)
- **Problém:** pri škálovaní Windows 125 % vzniklo okno 2400×1350 a obraz bol posunutý vpravo dole.
- **Príčina:** proces nie je DPI-aware, Windows ho virtualizuje.
- **Riešenie:** príznak `~ HIGHDPIAWARE` v `HKCU\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers` pre exe hry. Zapisuje ho inštalácia a odinštalovanie ho odstráni.
- **Ako sa vyhnúť:** testovať od začiatku pri škálovaní ≠ 100 %. Všetky výpočty polohy (okno kurzora, testy) robiť vo fyzických pixeloch a mierku brať z klientskej oblasti okna, nie z rozlíšenia monitora.

### 1.2 Zvyšky nápisov a kurzora na obrazovke
- **Problém:** po rýchlom pohybe myši ostávali na obraze zvyšky, napr. dva nápisy objektov cez seba.
- **Príčina:** pri `optimizedraw=1` (predvolené v `agds.cfg`) engine posiela na obrazovku len zmenené obdĺžniky. S dgVoodoo sa niektoré nedostanú na obraz.
- **Riešenie:** `optimizedraw=0`. Každá snímka pošle celý obraz jedným `Blt`, výkon je bez problému.
- **Ako sa vyhnúť:** v `agds.cfg` vždy nastaviť `optimizedraw=0`. Akýkoľvek vlastný zásah do obrazu robiť nad celou snímkou v háku zobrazenia.

### 1.3 Pomalé prekresľovanie pri vlastných zásahoch do snímky
- **Problém:** s prekresľovaním navyše (plynulý kurzor) hra spadla na 15 krokov/s.
- **Príčina:** pri `videomem=1` je zadný povrch v pamäti grafiky. Softvérový renderer ho cez dgVoodoo zamyká a jedno prekreslenie trvá ~33 ms.
- **Riešenie:** `videomem=0` – povrch v systémovej pamäti, prekreslenie trvá pár ms.
- **Ako sa vyhnúť:** `videomem=0` patrí do inštalácie spolu s `optimizedraw=0` a pri odinštalovaní sa oba riadky odstránia (pôvodný `agds.cfg` zálohovať).

### 1.4 Filmy na celú šírku
- **Problém:** širokouhlé CGI filmy engine kreslí do stredu 800×600 s čiernymi pásmi, po zväčšení sú malé.
- **Riešenie:** pri štarte filmu (`0x44198e`, obdĺžnik filmu v `0x58510c..0x585118`) nastaviť výrez dgVoodoo (`DisplayROI`, `dgddraw.dll+0x6c460`) na obdĺžnik filmu, pri konci (`0x441fea`) ho vrátiť. dgVoodoo číta výrez pri každej snímke.
- **Ako sa vyhnúť:** zásah do pamäte dgVoodoo je viazaný na jeho verziu (2.87.6). Pred zápisom overiť hodnoty 800/600 pred výrezom, pri inej verzii nič nerobiť. Film beží vo vlastnej slučke – krok hry počas neho nebeží (pozri 2.4).

### 1.5 Vyhladzovanie zmäkčovalo písmo a hromadilo sa
- **Problém:** FXAA nad celou snímkou zmäkčovalo a stmavovalo titulky a ponuky. Keď sa výsledok zapísal do zadného povrchu natrvalo, vyhladenie sa pri ďalších snímkach hromadilo.
- **Príčina:** engine prekresľuje len zmenené časti zadného povrchu, zvyšok berie z predchádzajúcej snímky.
- **Riešenie:** pred `Blt` snímku zálohovať, FXAA zapísať len do obdĺžnikov postáv (mimo pásov s textami y < 45 a y ≥ 544), po `Blt` vrátiť pôvodnú snímku. Výpočet v celých číslach, vo viacerých vláknach (~1 ms).
- **Ako sa vyhnúť:** **zadný povrch je zároveň pamäť enginu** – každú úpravu obrazu, ktorá sa nemá opakovať, po zobrazení vrátiť. Filtre obmedziť na obsah, ktorý ich potrebuje, nikdy nie na texty a ponuky.

### 1.6 Riadok enginu pri štarte
- Na jednu snímku sa ukáže „AGDS 2.299, (c) 1997-2002…“ v ľavom hornom rohu obrazovky. Je to pôvodné správanie enginu, nie chyba. V iných hrách AGDS treba počítať s tým istým.

---

## 2. Kurzor a myš

### 2.1 Kurzor posunutý v scénach širších ako obraz (oprava 1.0.2)
- **Problém:** v širokej scéne (podkrovie hradu, posun 600 px) aktívne miesta nesedeli s kurzorom. Kurzor sa nedal dostať do pravej časti obrazu. Správne to bolo až keď postava došla na koniec scény.
- **Príčina:** hardvérový kurzor počítal posun obrázka voči myši ako `animácia kurzora − posun scény − 0x506ff0`. Lenže `0x506ff0` (poloha myši hry) **už obsahuje posun scény**, takže sa posun odčítal dvakrát. Okno kurzora bolo vľavo o celý posun (600 px hry = 1080 px obrazovky).
- **Riešenie:** posun obrázka = `animácia kurzora − 0x506ff0` (obe v súradniciach scény).
- **Ako sa vyhnúť:**
  - Pri každej premennej si zapísať, v ktorom priestore je (obrazovka / obraz 800×600 / scéna) a prepočty robiť na jednom mieste (pomocná funkcia).
  - **Testovať vždy aj v scéne s posunom** – v úzkych scénach je posun 0 a chyba sa neprejaví. V NiBiRu aj Reprobates sú posúvajúce sa scény bežné.
  - Benchmark (`benchmark/`) overuje kurzor na mriežke bodov vrátane okrajov x 0 a 799 pred posunom scény aj po ňom.

### 2.2 Kolieska ponuky na zlom mieste po načítaní v širokej scéne (oprava 1.0.2)
- **Problém:** po načítaní pozície v širokej scéne boli ozubené kolieska ponuky v ľavej časti horného pásu namiesto vpravo hore. Stávalo sa to pri rýchlom načítaní (Ctrl+L) s myšou pri hornom okraji a pri načítaní cez ponuku pozície uloženej cez ponuku.
- **Príčina:** kolieska sú postava objektu `1006.100c` (`objekt+0x82`) s polohou v súradniciach scény = posun scény + (730, 2). Engine ich pri načítaní vytvorí (alebo obnoví z pozície) **skôr, než nastaví posun scény** – teda pri posune 0. Po nastavení posunu 600 ostanú na x 730 scény, čo je x 130 na obrazovke.
- **Riešenie:** doplnok v každom kroku hernej scény udrží polohu koliesok na posun + (730, 2). **Bez ohľadu na kontrolu hráča:** po načítaní cez ponuku dostane hráč kontrolu až o ~1,5 s. Prvá verzia opravy (len pri kontrole hráča) preto nechala kolieska 1,1 s vľavo.
- **Ako sa vyhnúť:**
  - Prvky „prilepené k obrazovke“ (lišty, ikony ponuky, hlášky) treba v širokej scéne kontrolovať po každej zmene posunu, nielen pri vytvorení.
  - Načítanie pozície má viac ciest: z hlavnej ponuky, z ponuky počas hry, rýchle načítanie, s myšou na rôznych miestach. Testovať všetky.
  - Opravy, ktoré sa majú prejaviť hneď po načítaní, nesmú byť podmienené kontrolou hráča.

### 2.3 Hardvérový kurzor (vlastné okno) – plynulosť
- **Problém:** kurzor hry sa hýbe 25×/s, prekresľovanie hrou dalo najviac ~35–38 zmien/s.
- **Riešenie:** vlastné vrstvené okno (`WS_EX_LAYERED | TRANSPARENT | TOPMOST | NOACTIVATE | TOOLWINDOW`) v samostatnom vlákne, presun každú 1 ms podľa `GetCursorPos`. Kurzor hry sa skryje presmerovaním pixelov jeho animácie na priehľadné pole (šablóny enginu sa nemenia).
- **Úskalia, na ktoré sme narazili:**
  - **Okno s vlastníkom = oknom hry:** každý `SetWindowPos` čakal na herné vlákno, takže okno sa presúvalo len 25×/s. Okno musí byť **bez vlastníka**.
  - Keď hra zmení kurzor (nová animácia), treba to zachytiť v kroku aj pred zobrazením a scénu hneď prekresliť (`0x426c43`). Inak na obrazovku ide jedna snímka s kurzorom hry.
  - Citlivosť musí počítať to isté vlákno, inak okno ukazuje striedavo nepreškálovanú a preškálovanú polohu.
- **Ako sa vyhnúť:** všetko, čo sa má hýbať plynulejšie než 25/s, robiť mimo herného vlákna a bez väzby na jeho okno.

### 2.4 Kurzor visel nad CGI filmom (oprava 1.0.1)
- **Problém:** počas úvodného filmu ostal nad obrazom kurzor z hlavnej ponuky (červený nad „Nová hra“).
- **Príčina:** viditeľnosť okna kurzora nastavoval krok hry. Film má vlastnú slučku, krok počas neho nebeží a príznak „viditeľný“ ostal z ponuky.
- **Riešenie:** vlákno okna kontroluje príznak filmu (`0x58512c`) samo.
- **Ako sa vyhnúť:** pri všetkom, čo beží mimo kroku (vlákna, okná, prekryvy), počítať s tým, že **krok počas filmov a načítania nebeží**. Stav sa musí overovať priamo, nie cez hodnotu, ktorú nastavuje krok.

### 2.5 Súradnice myši pri dgVoodoo
- dgVoodoo drží fyzický kurzor v obdĺžniku 800×600 (`ClipCursor`), takže `GetCursorPos` − ľavý horný roh `GetClipCursor` = poloha v obraze hry. Pri `FreeMouse=true` dostáva hra súradnice obrazovky (napr. 1320, 810), čo je nepoužiteľné bez prepočtu všetkých správ myši.
- Hra číta myš len zo správ okna (`WM_MOUSEMOVE` v okennej procedúre `0x440c79`), `GetCursorPos` neimportuje.
- **Testy:** `SetCursorPos` treba volať so súradnicami 0–799 × 0–599, nie obrazovky.

### 2.6 Plynulý kurzor (prekresľovanie hrou) a plánovanie kroku
- **Problém 1:** každé oneskorenie (zobrazenie s vsync čaká až 16 ms) hru natrvalo spomalilo.
- **Príčina:** plánovanie kroku (`0x402fa1`) nastavuje „posledný krok = teraz“, oneskorenie sa preto nikdy nedobehne.
- **Riešenie:** „posledný = plánovaný čas“. Pri oneskorení ≥ 1 krok (načítanie) ostáva „teraz“, aby hra potom nebežala zrýchlene.
- **Problém 2:** prekreslenie tesne pred krokom krok oneskorilo.
- **Riešenie:** neprekresľovať, ak do kroku ostávajú < 2 ms.
- **Ako sa vyhnúť:** po každom zásahu do časovania merať kroky/s (musí byť 25,0) a trvanie chôdze po pevnej trase. Pomôže aj krúženie myšou počas merania.

### 2.7 Citlivosť myši a kurzor presúvaný hrou
- **Problém:** keď hra presunie kurzor sama (`SetCursorPos`), citlivosť by z toho počítala pohyb myši.
- **Riešenie:** import `SetCursorPos` (`0x485280`) presmerovať na funkciu, ktorá nastaví znovunačítanie polohy bez násobenia. Polohu načítať znova aj po návrate do hry a po pauze dlhšej ako 5 krokov.
- **Ako sa vyhnúť:** pri testoch dať `Sensitivity=1.0`, inak testovací `SetCursorPos` prepočíta citlivosť.

---

## 3. Ponuka, značky aktívnych miest a kurzor nad objektmi

### 3.1 Kolieska uložené v pozícii
- **Problém:** po uložení cez F5 (ponuka otvorená doplnkom) boli kolieska po načítaní pozície vidno stále.
- **Príčina:** doplnok objekt `1006.100c` načítal do scény (`0x430052`), aby mohol zavolať jeho „use“. Engine ukladá všetky objekty scény do pozície – aj tento.
- **Riešenie:** kolieska sa skryjú (`0x43040d`), keď je myš aspoň 1 s pod horným pásom (y ≥ 60), bez ohľadu na to, kto ich načítal.
- **Ako sa vyhnúť:** **čokoľvek, čo doplnok pridá do scény (objekty, animácie), sa môže dostať do uloženej pozície.** Buď to po použití odstrániť, alebo počítať s tým, že sa to načíta naspäť (aj so zlou polohou, pozri 2.2). Pozície uložené počas testov schovať do benchmarku.

### 3.2 Pád hry pri značkách a ESC (záhrada, oprava 24. 11. 2026, vo vydaní 1.0.1)
- **Problém:** pozícia so záhradou a kolieskami uloženými v pozícii, podržaný medzerník (značky aktívnych miest) a hneď ESC → pád v `ntdll`.
- **Príčina:** pri uvoľnení scény (`0x40587e`, tu cez ponuku) engine uvoľní pixely **všetkých animácií scény** vlastným `free` (`0x418d17`). Značky doplnku mali pixely v statických poliach doplnku, takže engine volal `free` na pamäť, ktorú nealokoval. Zachytené vlastným VEH (výnimka pri `free` na `dvere_pixely`).
- **Riešenie:** každá značka má kópiu pixelov z alokátora enginu (`0x44ba28`). Doplnok ju pri odstránení uvoľní sám (`0x44bb62`), pri uvoľnení scény ju uvoľní engine.
- **Ako sa vyhnúť:**
  - **Všetka pamäť, ktorú doplnok odovzdá enginu (pixely animácií, šablóny, reťazce v štruktúrach enginu), musí byť z alokátora enginu.** Inak ju engine skôr či neskôr uvoľní.
  - Výnimka: kurzor. `0x40587e` najprv odstráni kurzor (`0x408b2d`) bez uvoľnenia pixelov, preto presmerovanie pixelov kurzora na pole doplnku (2.3) je bezpečné.
  - Testovať kombinácie načítania, koliesok a medzerníka: načítanie z hlavnej ponuky, z ponuky počas hry aj Ctrl+L, značky pred ESC, Ctrl+L počas značiek, odchod východom so značkami. To isté sa robí v benchmarku a so starou DLL sa tam pád zopakuje pri prvom pokuse.

### 3.3 Pixely obrázkov načítaných enginom sú zdieľané
- **Problém:** ikona dverí na značkách sa zmenila na pruhy.
- **Príčina:** `0x444f66(&šablóna, súbor)` vracia pixely v pamäti, ktorú engine pri ďalšom načítaní obrázka použije znova. Načítanie `kurzor-cerveny.flc` prepísalo dvere.
- **Riešenie:** pixely hneď skopírovať (a ako engine `0x419a0e` orezať priehľadné stĺpce vpravo a riadky dole).
- **Ako sa vyhnúť:** výsledok načítania obrázka enginom vždy skopírovať. Do animácie dať kópiu z alokátora enginu (3.2).

### 3.4 Dvojité ikony a ikony na miestach bez obrázka
- **Problém:** nad východom so značkou boli dve ikony dverí (značka + kurzor dverí). V detaile obrazu mala šípka „späť“ navyše krúžok.
- **Riešenie:** počas značiek nad východom podstrčiť červený kurzor (hák na začiatok `0x408c5c`, ako tabulátor v pôvodnej hre). Miesto bez vlastnej animácie, ktorého región má rovnaké ohraničenie ako aktívny objekt s animáciou, značku nedostane.
- **Ako sa vyhnúť:** prekryvy nad scénou porovnať s tým, čo engine kreslí sám (kurzor nad objektom, ikony objektov). Značky kresliť ako animácie scény pod kurzorom (poradie −9), nie priamo do snímky.

### 3.5 Hláška posunutá vpravo
- **Problém:** hláška rýchleho uloženia nebola na stred.
- **Príčina:** pri `0x446c75` s príznakom „na stred“ je x šablóny ľavý okraj, nie stred.
- **Riešenie:** x = subtitle_x − šírka/2 (+ posun scény).

### 3.6 Texty v zlom kódovaní
- **Problém:** ž sa kreslilo ako Ř a š ako „?“.
- **Príčina:** písma enginu sú v kódovaní Kamenických, nie cp1250.
- **Riešenie:** prevodná tabuľka 0x80–0xAB.
- **Ako sa vyhnúť:** kódovanie zistiť z textov v pamäti hneď na začiatku (porovnať známe slovo s diakritikou). V iných hrách AGDS to môže byť inak (lokalizácia).

---

## 4. Ukladanie, načítanie a stav hry

### 4.1 Pamäť a uvoľnenie scény (zhrnutie)
Engine pri uvoľnení scény uvoľní pixely animácií (okrem typov 6/7 a troch špeciálnych bufferov). Pravidlo z 3.2 platí všeobecne. Zároveň sa po uvoľnení scény nesmie pracovať so starými ukazovateľmi (animácie doplnku hľadať podľa mena, nie podľa uloženého ukazovateľa).

### 4.2 Rýchle načítanie počas chôdze
- **Problém:** po Ctrl+L počas chôdze ostala postava na uloženom mieste v póze kroku.
- **Príčina:** načítanie nastaví polohu a stav postavy (`0x49be28/2c`, `0x49be3a`), ale nie jej obrázok.
- **Riešenie:** najprv dať postave príkaz ísť na aktuálne miesto (`0x41c193`, zruší aj cieľ), chôdzu pretočiť bez snímok (~110 ms) a načítať, keď stojí.
- **Ako sa vyhnúť:** načítanie a uloženie volať len v pokojnom stave (postava stojí, hráč má kontrolu, nie film). Inak zobraziť hlášku „Teraz sa nedá…“.

### 4.3 Inventár chýbal po rýchlom načítaní z hlavnej ponuky
- **Problém:** lišta inventára sa po Ctrl+L z hlavnej ponuky neukázala.
- **Príčina:** ponuka inventár vypne skriptom (počítadlo `0x48d2d8` −1). Zapne ho až skript obrazovky nahrávania, ktorý sa pri priamom volaní načítania nespustí.
- **Riešenie:** po rýchlom načítaní zavolať `0x437986`, ak je počítadlo < 1.
- **Ako sa vyhnúť:** keď doplnok obchádza obrazovku enginu (ponuku, nahrávanie), zistiť, čo jej skript nastavuje okrem samotnej akcie, a urobiť to tiež.

### 4.4 Nastavenia sa prepisovali pri štarte a načítaní
- **Problém:** titulky, hlasitosti a gama sa po reštarte a po načítaní pozície vracali.
- **Príčina:** štartovací skript `main` ich nastaví pri každom spustení a pozícia obsahuje systémové premenné.
- **Riešenie:** hák na zápis systémovej premennej (`0x43a112`): zmeny z Nastavení zapamätať do `config.ini`, zápisy štartovacieho skriptu zablokovať, po načítaní vrátiť zapamätané hodnoty a zavolať funkciu premennej.

### 4.5 Koliesko myši – strata predmetu
- **Problém:** pri rýchlom točení kolieskom sa predmet stratil z inventára.
- **Príčina:** výber predmetu tesne po vrátení (~0,25 s okno) zlyhal – skript predmet vyradil z poľa, ale nepripol na kurzor.
- **Riešenie:** stavový automat s pauzami (12 a 8 krokov), zárezy zlúčiť, poistka vráti položku poľa a výber zopakuje.
- **Ako sa vyhnúť:** akcie skriptov enginu nie sú okamžité – medzi dvoma akciami čakať na potvrdenie stavu (predmet na kurzore, položka v poli). Záťažový test s náhodnými odstupmi.

### 4.6 Kontrola hráča nie je „koniec scény“
- `0x48b658/0x48b678` hlási kontrolu už pred niektorými monológmi (hala po úvode). Na zistenie konca rozhovoru treba kombinovať aj ticho titulkov alebo začiatok ďalšej repliky (hák `0x438d58`).

---

## 5. Preskakovanie a ovládanie

### 5.1 Preskakovanie rozhovorov
- Natívne každý kláves preskočí repliku (aj písmená), animácie a hudba medzi replikami bežia ďalej.
- **Riešenie:** pretáčanie – logika nečaká na krok, na obrazovku ide snímka len raz za 100 ms, jednorazové zvuky sa zastavia (slučky atmosféry nie, reč nie). Koniec pri začiatku ďalšej repliky, pri kontrole hráča alebo po 60 s.
- **Úskalia:**
  - Pretáčať len v herných scénach (hex meno), nie v ponukách a filmoch.
  - Zastavovať len neslučkové zvuky (`vzorka+0x1C`), inak zmizne atmosféra scény.
  - Podržaný kláves posiela opakované stlačenia – pri medzerníku (1 replika) ich zahadzovať.

### 5.2 Dvojklik
- Engine dvojklik pozná sám (`CS_DBLCLKS`, udalosť `0x50705c`). Pretáčanie chôdze sa zapína hákom na túto udalosť. Ukončiť ho pri zastavení postavy, zmene scény, filme alebo po limite krokov.

---

## 6. Doplnok, zostavenie a inštalácia

### 6.1 Reťaz knižníc a háky
- Hra → `DDraw.dll` (doplnok v C) → `bm_core.dll` (assembler) → `dgddraw.dll` (dgVoodoo). Exporty sa preposielajú.
- Pred každým hákom overiť pôvodné bajty. Pri inej verzii exe sa nevloží nič, hra beží ako bez doplnku.
- Každá funkcia sa dá vypnúť v `config.ini`. Keď je vypnutá, hák sa vôbec nevkladá.

### 6.2 Nástroje
- **keystone** zle počíta rozdiel návestí (`a - b`) a nepozná `rep movsd` → v ďalších projektoch radšej C (`zig cc`, bez CRT).
- Prekladač bez CRT sám generuje volania `memcpy`/`memset` – treba ich dodať.

### 6.3 Dávky .bat
- **Problém:** `chcp 65001` prepne konzolu na bodové písmo Terminal. Dávky s koncami riadkov LF sa pri skokoch na návestia rozpadali („'t' is not recognized…“).
- **Riešenie:** dávky v kódovaní 852 a CRLF (`.gitattributes`: `working-tree-encoding=CP852`, `eol=crlf`), bez `chcp`.

### 6.4 Inštalácia
- Hru nájsť cez Steam (register + `libraryfolders.vdf`), existujúci `config.ini` neprepisovať bez súhlasu, zálohovať `agds.cfg`. Odinštalovanie musí vrátiť hru do pôvodného stavu.

---

## 7. Testovanie – čo robiť od začiatku

1. **Benchmark** (`benchmark/benchmark.py`, návod `benchmark/NAVOD.md`) spúšťať po každej zmene doplnku pred vydaním. Pri chybe ho najprv spustiť so starou DLL a overiť, že chybu zachytí.
2. **Scény do benchmarku** vyberať podľa rizika, nie podľa poradia v hre:
   - úzka scéna (posun 0),
   - **široká posúvajúca sa scéna** (pred posunom aj po ňom),
   - pozícia **uložená cez ponuku** (objekty ponuky uložené v pozícii),
   - scéna, kde už raz niečo padalo.
3. **Pozície z hlásení chýb** hneď zálohovať do `benchmark/pozicie/` – hráč ich môže prepísať.
4. **Všetky cesty načítania:** hlavná ponuka, ponuka počas hry, rýchle načítanie. Myš pri načítaní v strede aj pri hornom okraji.
5. **Všetky režimy kurzora** (`--profil hardware | smooth | original`).
6. **Pády** testovať kombináciami (načítanie + ponuka + značky + ESC), nie jednotlivými funkciami.
7. Merať, nie odhadovať: kroky/s (25,0), zobrazenia/s, trvanie chôdze, poloha kurzora v súradniciach hry aj obrazovky.
8. Testovacie nastavenia (`Sensitivity=1.0`, `[Debug]`) a pozície (98, 8) po teste vrátiť. Nikdy neobnovovať celý `config.ini` alebo `savnames.txt` zo staršej zálohy.
9. Automatické testy: hru dostať do popredia stlačením Alt naprázdno. Podržaný kláves musí posielať opakované stlačenia ako skutočná klávesnica. Prvý klik po návrate z ponuky engine ignoruje.

---

## 8. Kontrolný zoznam pre novú hru na AGDS

- [ ] Verzia enginu a exe (reťazec „AGDS x.xxx“, dátum zostavenia), kontrolné bajty pre háky.
- [ ] Adresy: aktuálna scéna, posun scény, poloha myši, zoznamy objektov a animácií, kurzor (poradie −10), funkcia zobrazenia, krok, kontrola hráča, film, alokátor a `free` enginu, načítanie/uloženie pozície.
- [ ] Súradnicový priestor každej premennej (obrazovka / 800×600 / scéna).
- [ ] Zoznam širokých (posúvajúcich sa) scén a pozície v nich.
- [ ] `agds.cfg`: `optimizedraw=0`, `videomem=0`, záloha.
- [ ] Kódovanie textov a písiem.
- [ ] Čo sa ukladá do pozície (objekty ponuky, animácie doplnku).
- [ ] Správanie počas filmu a načítania (krok nebeží).
- [ ] Benchmark so scénami podľa bodu 7.2 skôr, než sa začnú písať nové funkcie.
