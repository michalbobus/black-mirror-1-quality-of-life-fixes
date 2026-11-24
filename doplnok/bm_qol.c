/* Black Mirror (agds.exe) – doplnok pohodlia: DDraw.dll, ktorá prepošle všetky exporty na bm_core.dll
 * (doterajší doplnok: filmy na celú šírku, plynulý kurzor, citlivosť) a ten ďalej na dgddraw.dll (dgVoodoo2).
 *
 * Háky (v pamäti agds.exe, exe na disku sa nemení; pred zápisom sa overia pôvodné bajty):
 *   0x402e21  call 0x431cf8   – začiatok kroku logiky (25/s, herné vlákno): hra_krok()
 *   0x440e9d  call 0x43f278   – WM_KEYDOWN v okennej procedúre: klaves_dole()
 *   0x44112b  call [DefWindowProcA] – ostatné správy okna (WM_MOUSEWHEEL): okno_ine()
 *   0x42e416, 0x43a228  call 0x433708 – načítanie uloženej hry: po ňom sa vrátia zapamätané nastavenia
 *   0x43e78f  začiatok funkcie zobrazenia (Blt zadného povrchu na obrazovku): vyhladenie, pretáčanie bez snímok
 *   0x408c5c  začiatok nastavenia kurzora nad objektom: červený kurzor nad východom počas značiek hotspotov
 *   0x4410c5  call 0x417949   – udalosť dvojkliku (WM_LBUTTONDBLCLK + pustenie): pretočenie chôdze
 *   import SetCursorPos (0x485280) – hardvérový kurzor s citlivosťou; okno kurzora vo vlastnom vlákne (hw_vlakno)
 *
 * Preklad: doplnok/zostav.bat (zig cc, bez CRT).
 */
#include <windows.h>
#include <stdarg.h>

/* ---------- adresy v agds.exe ---------- */
#define SCENA          (*(unsigned char **)0x49eb1c)     /* objekt aktuálnej obrazovky: +0 meno, +0x40 zoznam objektov */
#define HWND_HRY       (*(HWND *)0x5850e8)
#define FILM_BEZI      (*(int *)0x58512c)
#define MYS_X          (*(int *)0x506ff0)                /* poloha myši v súradniciach hry (po kroku + posun scény) */
#define MYS_Y          (*(int *)0x506fa8)
#define VYBRANY_PREDMET (*(unsigned char **)0x49f3e0)    /* predmet na kurzore */
#define ZADNY_POVRCH   (*(IUnknown **)0x597e60)          /* IDirectDrawSurface7, systémová pamäť (videomem=0) */

typedef int (__cdecl *fn0)(void);
#define POUZIVATEL_POVOLENY() (((fn0)0x4305d1)())       /* 1 = hráč má kontrolu (0x48b658 && 0x48b678) */

/* ---------- pomocné funkcie bez CRT (prekladač sám generuje volania memcpy/memset) ---------- */
void *memcpy(void *c, const void *z, unsigned n) { void *r = c; __asm__ volatile("rep movsb" : "+D"(c), "+S"(z), "+c"(n) : : "memory"); return r; }
void *memset(void *c, int v, unsigned n) { void *r = c; __asm__ volatile("rep stosb" : "+D"(c), "+c"(n) : "a"(v) : "memory"); return r; }
static void kopiruj(void *c, const void *z, int n) { char *a = c; const char *b = z; while (n--) *a++ = *b++; }
static int rovnake(const void *a, const void *b, int n) { const unsigned char *x = a, *y = b; while (n--) if (*x++ != *y++) return 0; return 1; }
static int zacina(const char *s, const char *p) { while (*p) if (*s++ != *p++) return 0; return 1; }
static int obsahuje(const char *s, const char *p) { for (; *s; s++) if (zacina(s, p)) return 1; return 0; }

/* ---------- konfigurácia a log ---------- */
static char cesta_ini[MAX_PATH], cesta_log[MAX_PATH];
static int log_zapnuty;

static void loguj(const char *fmt, ...)
{
    if (!log_zapnuty) return;
    char b[1024]; int n = wsprintfA(b, "%6u ", GetTickCount() % 1000000);
    va_list a; va_start(a, fmt); n += wvsprintfA(b + n, fmt, a); va_end(a);
    b[n++] = '\r'; b[n++] = '\n';
    HANDLE h = CreateFileA(cesta_log, FILE_APPEND_DATA, FILE_SHARE_READ, 0, OPEN_ALWAYS, 0, 0);
    if (h != INVALID_HANDLE_VALUE) { DWORD w; WriteFile(h, b, n, &w, 0); CloseHandle(h); }
}

static int ini_cislo(const char *sekcia, const char *kluc, int predvolene)
{
    return GetPrivateProfileIntA(sekcia, kluc, predvolene, cesta_ini);
}

/* ---------- zápis do pamäte exe ---------- */
static int zapis(void *adresa, const void *data, int n)
{
    DWORD stara;
    if (!VirtualProtect(adresa, n, PAGE_EXECUTE_READWRITE, &stara)) return 0;
    kopiruj(adresa, data, n);
    VirtualProtect(adresa, n, stara, &stara);
    FlushInstructionCache(GetCurrentProcess(), adresa, n);
    return 1;
}

/* Prepíše `call povodny` na adrese na `call novy` (overí E8 a pôvodný cieľ). */
static int hak_volanie(unsigned adresa, unsigned povodny, void *novy)
{
    unsigned char *p = (unsigned char *)adresa;
    if (p[0] != 0xE8 || adresa + 5 + *(int *)(p + 1) != povodny) { loguj("hak %x: ine bajty", adresa); return 0; }
    int rel = (int)novy - (int)(adresa + 5);
    return zapis(p + 1, &rel, 4);
}

/* Prepíše 6-bajtové `call [iat]` (FF 15) na `call novy` + nop. */
static int hak_volanie_iat(unsigned adresa, unsigned iat, void *novy)
{
    unsigned char *p = (unsigned char *)adresa;
    if (p[0] != 0xFF || p[1] != 0x15 || *(unsigned *)(p + 2) != iat) { loguj("hak %x: ine bajty", adresa); return 0; }
    unsigned char b[6] = {0xE8, 0, 0, 0, 0, 0x90};
    *(int *)(b + 1) = (int)novy - (int)(adresa + 5);
    return zapis(p, b, 6);
}

/* Hák na začiatok funkcie: prvých n bajtov (celé, premiestniteľné inštrukcie, overené `ocakavane`) sa skopíruje
 * do mostíka + skok späť, na ich miesto skok na `novy` (rovnaká volacia konvencia). Vráti mostík = pôvodnú funkciu. */
static unsigned char mostiky[8][32];
static int pocet_mostikov;
static void *hak_zaciatok(unsigned adresa, const unsigned char *ocakavane, int n, void *novy)
{
    unsigned char *p = (unsigned char *)adresa;
    if (n < 5 || n > 24 || pocet_mostikov >= 8 || !rovnake(p, ocakavane, n)) { loguj("hak %x: ine bajty", adresa); return 0; }
    unsigned char *m = mostiky[pocet_mostikov++];
    DWORD stara; VirtualProtect(m, 32, PAGE_EXECUTE_READWRITE, &stara);
    kopiruj(m, p, n);
    m[n] = 0xE9; *(int *)(m + n + 1) = (int)(adresa + n) - (int)(m + n + 5);
    unsigned char b[24]; b[0] = 0xE9; *(int *)(b + 1) = (int)novy - (int)(adresa + 5);
    for (int i = 5; i < n; i++) b[i] = 0x90;
    return zapis(p, b, n) ? m : 0;
}

/* ---------- ladiaci kanál: Python zapíše príkaz, doplnok ho vykoná v hernom vlákne pri ďalšom kroku ---------- */
typedef struct {
    volatile int prikaz;        /* 1 = zavolaj funkciu `funkcia` (cdecl) s `argumenty`, potom 0 */
    unsigned funkcia;
    int pocet;
    int argumenty[8];
    int vysledok;
    char text[256];             /* pomocný buffer (napr. meno objektu ako argument) */
    volatile int udalosti[64];  /* počítadlá / posledné hodnoty z hákov (na meranie) */
} Ladenie;
__declspec(dllexport) Ladenie ladenie;

static void ladenie_krok(void)
{
    if (ladenie.prikaz != 1) return;
    typedef int (__cdecl *f8)(int, int, int, int, int, int, int, int);
    int *a = ladenie.argumenty;
    ladenie.vysledok = ((f8)ladenie.funkcia)(a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7]);
    ladenie.prikaz = 0;
}

/* ---------- stav hry ---------- */
typedef unsigned char *(__cdecl *fn_najdi)(unsigned char *scena, const char *meno);
#define NAJDI_OBJEKT(s, m) (((fn_najdi)0x406116)((s), (m)))     /* objekt v scéne podľa mena alebo 0 */
#define I32(p, o) (*(int *)((unsigned char *)(p) + (o)))

/* Hráč ovláda hru v scéne: nie film, nie obrazovky ponuky (1006.*), používateľ povolený. */
static int hra_v_scene(void)
{
    unsigned char *s = SCENA;
    return s && !FILM_BEZI && POUZIVATEL_POVOLENY() >= 1 && !zacina((char *)s, "1006.");
}

static int hra_v_popredi(void) { return HWND_HRY && GetForegroundWindow() == HWND_HRY; }
static int drzi(int vk) { return hra_v_popredi() && (GetAsyncKeyState(vk) & 0x8000); }

/* ---------- ESC: ponuka ako klik na ozubené kolieska (objekt 1006.100c, vpravo hore) ---------- */
static int cfg_esc_ponuka, cfg_hotspoty, cfg_preskakovanie, cfg_koliesko, cfg_nastavenia;
static int esc_ziadost;
static int kolieska_nacitane;       /* 1 = objekt 1006.100c načítal doplnok, 2 = ponuka sa už zobrazila */

static void otvor_ponuku(void)
{
    unsigned char *s = SCENA, *o;
    static const char meno[] = "1006.100c";
    if (!s) return;
    o = NAJDI_OBJEKT(s, meno);
    if (!o) {   /* lišta s kolieskami sa načíta až pri priblížení myši k hornému okraju */
        ((int (__cdecl *)(const char *, unsigned char *, int, int))0x430052)(meno, s, 1, 1);
        o = NAJDI_OBJEKT(s, meno);
        kolieska_nacitane = o != 0;
    }
    loguj("ESC -> ponuka, objekt %x", (unsigned)o);
    if (o) ((int (__cdecl *)(unsigned char *, int, int))0x4311f7)(o, 753 + I32(s, 0x5d5), 22 + I32(s, 0x5d9));
}

/* Kolieska (1006.100c) hra ukáže pri priblížení myši k hornému okraju. Ak ich načítal doplnok (ESC, F5/F8),
 * po návrate do hry by ostali viditeľné – a ak sa hra uložila cez F5, uložia sa s pozíciou a sú vidno stále
 * (pozícia 2 z 24. 11. 2026). Preto ich doplnok skryje vždy, keď je myš aspoň 1 s (25 krokov) pod horným pásom. */
static int kolieska_dole;
static void schovaj_kolieska(void)
{
    unsigned char *s = SCENA, *o;
    if (!hra_v_scene() || *(int *)0x507014 < 60) { kolieska_dole = 0; return; }
    if (++kolieska_dole < 25) return;
    kolieska_dole = 0;
    o = NAJDI_OBJEKT(s, "1006.100c");
    if (o) {
        ((int (__cdecl *)(void *, unsigned char *, unsigned char *))0x43040d)(0, o, s);
        kolieska_nacitane = 0;
        loguj("kolieska schovane %x", (unsigned)o);
    }
}

static int rec_bezi(void);
/* Značky sa po stlačení medzerníka ukážu na rovnaký čas ako ikony tabulátora: 2,04 s = 50 krokov (zmerané). */
#define KROKY_HOTSPOTOV 50
static unsigned pocet_krokov, hotspoty_do;

/* ---------- hotspoty (medzerník) ---------- */
/* Značky sú animácie scény (zoznam scéna+0x80, ako kurzor), takže ich hra kreslí sama – pod kurzor (poradie −9,
 * kurzor má −10) a s vlastným prekresľovaním. Východy (objekty s klávesovou obsluhou tabulátora, +0xE1) dostanú
 * ikonu dverí kurzor_dvere.flc ako pri tabulátore, ostatné objekty s názvom krúžok. Animácie sa spoznajú podľa mena,
 * takže sa dajú odstrániť aj po návrate do scény (napr. z ponuky). */
#define MAX_HOTSPOTOV 64
#define MENO_ZNACKY "bmqol_hotspot"
#define ZN 21                                   /* veľkosť krúžku */
typedef struct { int x, y, vychod; } Hotspot;
static Hotspot hotspoty[MAX_HOTSPOTOV], zobrazene[MAX_HOTSPOTOV];
static int pocet_hotspotov, pocet_zobrazenych;
static unsigned char sablona_dvere[32], sablona_kruh[32];  /* šablóna obrázka (29 B): š, v, bity, x, y, pixely, typ */
static int sablony;                             /* 0 = nepripravené, 1 = krúžok, 2 = krúžok aj dvere */
static unsigned kruh_pixely[ZN * ZN];           /* 32 bit: B, G, R, 100 (purpurová = priehľadná) */

static unsigned farba_znacky(int dx, int dy)
{
    int r2 = dx * dx + dy * dy;
    if (r2 <= 2) return 0xF4E2B0;                    /* bodka v strede */
    if (r2 >= 30 && r2 <= 56) return 0xF4E2B0;       /* krúžok (svetlá zlatá) */
    if ((r2 >= 20 && r2 < 30) || (r2 > 56 && r2 <= 72) || (r2 > 2 && r2 <= 6)) return 0x201408;   /* tmavý lem */
    return 0xFF00FF;
}

/* Obrázok z archívov hry: 0x444f66 vráti pixely v pamäti, ktorú hra pri ďalšom načítaní obrázka použije znova
 * (zistené 24. 11. 2026: načítanie červeného kurzora prepísalo pixely ikony dverí), preto sa skopírujú do `pixely`
 * (najviac `max` pixelov, 32 bit). Vráti 1 pri úspechu. */
static int nacitaj_obrazok(unsigned char *t, const char *meno, unsigned *pixely, int max)
{
    memset(t, 0, 32);
    if (((int (__cdecl *)(void *, const char *))0x444f66)(t, meno) != 0) return 0;
    int s = *(int *)t, v = *(int *)(t + 4);
    unsigned *p = *(unsigned **)(t + 0x14);
    if (s <= 0 || v <= 0 || s * v > max || *(int *)(t + 8) != 32 || !p) { memset(t, 0, 32); return 0; }
    /* ako hra (0x419a0e): bez úplne priehľadných stĺpcov vpravo a riadkov dole (purpurová = priehľadná) */
    int s2 = s, v2 = v;
    for (; s2 > 1; s2--) { int y = 0; while (y < v && (p[y * s + s2 - 1] & 0xFFFFFF) == 0xFF00FF) y++; if (y < v) break; }
    for (; v2 > 1; v2--) { int x = 0; while (x < s2 && (p[(v2 - 1) * s + x] & 0xFFFFFF) == 0xFF00FF) x++; if (x < s2) break; }
    for (int y = 0; y < v2; y++) kopiruj(pixely + y * s2, p + y * s, s2 * 4);
    *(int *)t = s2; *(int *)(t + 4) = v2;
    *(unsigned **)(t + 0x14) = pixely;
    return 1;
}
static unsigned dvere_pixely[64 * 64], cerveny_pixely[64 * 64];

static void priprav_sablony(void)
{
    if (sablony) return;
    for (int y = 0; y < ZN; y++)
        for (int x = 0; x < ZN; x++) kruh_pixely[y * ZN + x] = 0x64000000u | farba_znacky(x - ZN / 2, y - ZN / 2);
    memset(sablona_kruh, 0, sizeof sablona_kruh);
    *(int *)(sablona_kruh + 0) = ZN; *(int *)(sablona_kruh + 4) = ZN; *(int *)(sablona_kruh + 8) = 32;
    *(unsigned **)(sablona_kruh + 0x14) = kruh_pixely;
    sablony = 1;
    /* ikona východu z tabulátora (načíta hra z archívov) */
    if (nacitaj_obrazok(sablona_dvere, "kurzor_dvere.flc", dvere_pixely, 64 * 64)) sablony = 2;
    loguj("sablony znaciek %d (dvere %dx%d)", sablony, *(int *)sablona_dvere, *(int *)(sablona_dvere + 4));
}

/* Miesto so stále viditeľnou ikonou nedostane značku: napr. šípka „zpět“ v detaile Marcusovho obrazu (19d5) je
 * miesto 19d5.10af bez obrázka a k nemu objekt main.11d2 s obrázkom Zoomzpet.bmp a presne tým istým regiónom.
 * Ikona = aktívny objekt s animáciou (+0x7e) a regiónom; zhoda = rovnaké ohraničenie regiónu (+0xA..+0x10). */
#define MAX_IKON 32
static int ikony_box[MAX_IKON][4], pocet_ikon;

static int ma_ikonu(unsigned char *o, unsigned char *reg)
{
    for (int i = 0; i < pocet_ikon; i++)
        if (ikony_box[i][0] == *(short *)(reg + 0xa) && ikony_box[i][1] == *(short *)(reg + 0xc) &&
            ikony_box[i][2] == *(short *)(reg + 0xe) && ikony_box[i][3] == *(short *)(reg + 0x10) && *(void **)(o + 0x7e) == 0)
            return 1;
    return 0;
}

static void zbieraj_hotspoty(void)
{
    unsigned char *s = SCENA;
    pocet_hotspotov = 0;
    if (!s) return;
    unsigned char *prvy = *(unsigned char **)(s + 0x40 + 0x28), *o = prvy;
    int n = 0;
    pocet_ikon = 0;
    while (o && n++ < 1000 && pocet_ikon < MAX_IKON) {           /* objekty s vlastným obrázkom a regiónom */
        unsigned char *reg = *(unsigned char **)(o + 0x72);
        if (I32(o, 0x34) && reg && *(void **)(o + 0x7e)) {
            int *b = ikony_box[pocet_ikon++];
            b[0] = *(short *)(reg + 0xa); b[1] = *(short *)(reg + 0xc); b[2] = *(short *)(reg + 0xe); b[3] = *(short *)(reg + 0x10);
        }
        o = *(unsigned char **)o;
        if (o == prvy) break;
    }
    o = prvy; n = 0;
    while (o && n++ < 1000 && pocet_hotspotov < MAX_HOTSPOTOV) {
        unsigned char *reg = *(unsigned char **)(o + 0x72), *nazov = *(unsigned char **)(o + 0x7a);
        if (I32(o, 0x34) && reg && nazov && nazov[0] && !zacina((char *)o + 8, "inv.") && o != VYBRANY_PREDMET &&
            !ma_ikonu(o, reg)) {
            /* inverzia prepočtu z hit-testu 0x4034b0: región = bod - animácia + obj[0x3a] - obj[0x42] */
            int x = *(short *)reg + I32(o, 0x42), y = *(short *)(reg + 2) + I32(o, 0x46);
            unsigned char *anim = *(unsigned char **)(o + 0x7e), *post = *(unsigned char **)(o + 0x82);
            if (anim) { x += I32(anim, 0x1c) - I32(o, 0x3a); y += I32(anim, 0x20) - I32(o, 0x3e); }
            else if (post) {
                unsigned char *a = *(unsigned char **)(*(unsigned char **)(post + 0x36a) + 0x61);
                x += I32(a, 0x37e) - I32(o, 0x3a); y += I32(a, 0x382) - I32(o, 0x3e);
            }
            int sx = x - I32(s, 0x5d5), sy = y - I32(s, 0x5d9);       /* na obrazovke */
            if (sx >= 0 && sx < 800 && sy >= 0 && sy < 600) {
                Hotspot *h = &hotspoty[pocet_hotspotov++];
                h->x = x; h->y = y;                                   /* súradnice scény */
                h->vychod = *(void **)(o + 0xe1) != 0;               /* má klávesovú obsluhu (tabulátor) */
            }
        }
        o = *(unsigned char **)o;
        if (o == prvy) break;
    }
}

/* Naše animácie v aktuálnej scéne (podľa mena). */
static int najdi_znacky(unsigned char *s, unsigned char **out, int max)
{
    unsigned char *prvy = *(unsigned char **)(s + 0x80 + 0x28), *a = prvy;
    int n = 0, k = 0;
    while (a && k++ < 5000) {
        if (!lstrcmpA((char *)a + 0x41, MENO_ZNACKY) && n < max) out[n++] = a;
        a = *(unsigned char **)a;
        if (a == prvy) break;
    }
    return n;
}

static void znacky_krok(void)
{
    unsigned char *s = SCENA;
    if (!s) return;
    int chce = cfg_hotspoty && pocet_krokov < hotspoty_do && hra_v_scene() && !rec_bezi();
    if (chce) zbieraj_hotspoty(); else pocet_hotspotov = 0;
    unsigned char *nase[MAX_HOTSPOTOV * 2];
    int n = najdi_znacky(s, nase, MAX_HOTSPOTOV * 2);
    if (n == pocet_zobrazenych && pocet_hotspotov == pocet_zobrazenych &&
        rovnake(hotspoty, zobrazene, pocet_hotspotov * (int)sizeof(Hotspot))) return;     /* bez zmeny */
    for (int i = 0; i < n; i++) {
        void *px = *(void **)(nase[i] + 0x24);          /* vlastná kópia pixelov v pamäti hry (pozri nižšie) */
        ((void (__cdecl *)(unsigned char *, unsigned char **))0x406b31)(s, &nase[i]);
        if (px && px != kruh_pixely && px != dvere_pixely) ((void (__cdecl *)(void *))0x44bb62)(px);
    }
    pocet_zobrazenych = 0;
    if (!pocet_hotspotov) return;
    priprav_sablony();
    for (int i = 0; i < pocet_hotspotov; i++) {
        unsigned char t[32];
        kopiruj(t, hotspoty[i].vychod && sablony == 2 ? sablona_dvere : sablona_kruh, 32);
        *(int *)(t + 0xc) = hotspoty[i].x - *(int *)t / 2;          /* stred značky na strede regiónu */
        *(int *)(t + 0x10) = hotspoty[i].y - *(int *)(t + 4) / 2;
        /* Pixely musia byť z pamäte hry: pri uvoľnení scény (0x40587e) hra uvoľní pixely všetkých jej animácií
         * (0x418d17 -> free) – s pixelmi v poli doplnku spadla (zistené 24. 11. 2026: medzerník, hneď ESC,
         * kolieska uložené v pozícii -> ponuka uvoľnila scénu). Kópiu pri odstránení uvoľní doplnok, inak hra. */
        int velk = *(int *)t * *(int *)(t + 4) * 4;
        void *kopia = ((void *(__cdecl *)(unsigned))0x44ba28)(velk);
        if (!kopia) continue;
        kopiruj(kopia, *(void **)(t + 0x14), velk);
        *(void **)(t + 0x14) = kopia;
        ((unsigned char *(__cdecl *)(unsigned char *, void *, int, int, const char *))0x406932)(s, t, -9, 0, MENO_ZNACKY);
    }
    kopiruj(zobrazene, hotspoty, pocet_hotspotov * (int)sizeof(Hotspot));
    pocet_zobrazenych = pocet_hotspotov;
}

/* Kurzor nad východom počas značiek: ikona dverí je už vidno ako značka, takže kurzor nad východom bude červený
 * (kurzor-cerveny.flc, ako nad ostatnými objektmi) – rovnako ako pri tabulátore, kde skript východom dočasne
 * zmení obrázok kurzora. Doplnok objekty nemení: hák na 0x408c5c (scéna, šablóna kurzora objektu +0x86, meno)
 * podstrčí červenú šablónu, ak je šablóna objektu ikona dverí. [0x49f01e] = šablóna práve zobrazeného kurzora
 * objektu (stav 2 v [0x49f404]); hra ju každý krok porovná s +0x86 objektu pod kurzorom a pri rozdiele volá 0x408c5c. */
static void (__cdecl *kurzor_objektu_povodne)(unsigned char *, unsigned char *, const char *);
static unsigned char sablona_cerveny[32];
static int cerveny;                             /* 0 = nenačítaný, 1 = načítaný, −1 = chyba */
#define KURZOR_OBJEKTU (*(unsigned char **)0x49f01e)

static int znacky_vidno(void) { return pocet_zobrazenych > 0 && pocet_krokov < hotspoty_do; }

static int je_ikona_dveri(unsigned char *t)
{
    if (!t || sablony != 2) return 0;
    int s = *(int *)t, v = *(int *)(t + 4);
    if (s != *(int *)sablona_dvere || v != *(int *)(sablona_dvere + 4) || *(int *)(t + 8) != 32) return 0;
    unsigned char *a = *(unsigned char **)(t + 0x14), *b = *(unsigned char **)(sablona_dvere + 0x14);
    return a && (a == b || rovnake(a, b, s * v * 4));
}

static void __cdecl kurzor_objektu(unsigned char *s, unsigned char *t, const char *meno)
{
    if (znacky_vidno() && je_ikona_dveri(t)) {
        if (!cerveny) {
            cerveny = nacitaj_obrazok(sablona_cerveny, "kurzor-cerveny.flc", cerveny_pixely, 64 * 64) ? 1 : -1;
            loguj("kurzor-cerveny %d (%dx%d)", cerveny, *(int *)sablona_cerveny, *(int *)(sablona_cerveny + 4));
        }
        if (cerveny == 1) {
            if (KURZOR_OBJEKTU == sablona_cerveny && *(int *)0x49f404 == 2) return;      /* už je červený */
            t = sablona_cerveny;
        }
    }
    kurzor_objektu_povodne(s, t, meno);
}

/* Po zobrazení značiek: ak je kurzor práve nad východom (dvere), hra ho prekreslí až pri zmene objektu –
 * vynulovaním [0x49f01e] ho prinúti znova zavolať 0x408c5c (hák ho zmení na červený). */
static void kurzor_nad_vychodom_krok(void)
{
    if (kurzor_objektu_povodne && znacky_vidno() && *(int *)0x49f404 == 2 && je_ikona_dveri(KURZOR_OBJEKTU))
        KURZOR_OBJEKTU = 0;
}

/* ---------- zámok zadného povrchu (vyhladzovanie) ---------- */
typedef struct { unsigned char b[124]; } DDSD2;     /* DDSURFACEDESC2: dwSize 0, lPitch 0x10, lpSurface 0x24, bity 0x54 */
typedef long (__stdcall *fn_lock)(void *, RECT *, DDSD2 *, unsigned, void *);
typedef long (__stdcall *fn_unlock)(void *, RECT *);

static int zamkni(DDSD2 *d)
{
    void *p = ZADNY_POVRCH;
    if (!p) return 0;
    memset(d, 0, sizeof *d); *(unsigned *)d->b = 124;
    void **vt = *(void ***)p;
    if (((fn_lock)vt[25])(p, 0, d, 1 /* DDLOCK_WAIT */, 0) < 0) return 0;
    if (*(unsigned *)(d->b + 0x54) != 32) { ((fn_unlock)vt[32])(p, 0); return 0; }
    return 1;
}
static void odomkni(void) { void *p = ZADNY_POVRCH; ((fn_unlock)(*(void ***)p)[32])(p, 0); }

/* ---------- zapamätané nastavenia (platia bez ohľadu na uloženú hru) ---------- */
/* Celočíselné systémové premenné z tabuľky 0x48d470: meno, ukazovateľ na hodnotu, funkcia pri zmene. */
static const struct { const char *meno; int *hodnota; unsigned funkcia; } NASTAVENIA[] = {
    {"tell_mode",    (int *)0x48d458, 0},          /* bit 0 = titulky, bit 1 = hlas (3 = oboje, 2 = bez titulkov) */
    {"tell_volume",  (int *)0x48d3f8, 0},          /* hlasitosť reči */
    {"sound_volume", (int *)0x48d3f0, 0x439c6d},
    {"music_volume", (int *)0x48d400, 0x439c47},
    {"gamma",        (int *)0x584e30, 0},
};
#define POCET_NASTAVENI (int)(sizeof NASTAVENIA / sizeof NASTAVENIA[0])
static int zapamatane[POCET_NASTAVENI], ma_zapamatane[POCET_NASTAVENI];

static int obrazovka_nastaveni(void) { return SCENA && zacina((char *)SCENA, "1006.1037"); }

static void nacitaj_zapamatane(void)
{
    for (int i = 0; i < POCET_NASTAVENI; i++) {
        int v = GetPrivateProfileIntA("Remembered", NASTAVENIA[i].meno, -12345, cesta_ini);
        ma_zapamatane[i] = v != -12345; zapamatane[i] = v;
    }
}

static void zapamataj(int i, int v)
{
    if (ma_zapamatane[i] && zapamatane[i] == v) return;
    char t[16]; wsprintfA(t, "%d", v);
    WritePrivateProfileStringA("Remembered", NASTAVENIA[i].meno, t, cesta_ini);
    zapamatane[i] = v; ma_zapamatane[i] = 1;
    loguj("zapamatane %s = %d", NASTAVENIA[i].meno, v);
}

static void obnov_nastavenia(const char *preco)
{
    if (!cfg_nastavenia) return;
    for (int i = 0; i < POCET_NASTAVENI; i++) {
        if (!ma_zapamatane[i] || *NASTAVENIA[i].hodnota == zapamatane[i]) continue;
        loguj("%s: %s %d -> %d", preco, NASTAVENIA[i].meno, *NASTAVENIA[i].hodnota, zapamatane[i]);
        *NASTAVENIA[i].hodnota = zapamatane[i];
        if (NASTAVENIA[i].funkcia) ((void (__cdecl *)(void))NASTAVENIA[i].funkcia)();
    }
}

/* ---------- preskakovanie (ESC, keď hráč nemá kontrolu; medzerník preskočí len jednu repliku – natívne) ---------- */
/* ESC: hra natívne preskočí práve hovorenú repliku; doplnok potom „pretáča“ – logika nečaká na krok,
 * snímky sa (okrem jednej za 100 ms) neposielajú na obrazovku a jednorazové zvuky (nie slučky, nie reč) sa zastavia,
 * aby skript nečakal na ich dohranie (napr. hudba pod rozprávačom) – až kým nezačne ďalšia replika alebo hráč
 * nedostane kontrolu. Držanie: pokračuje cez ďalšie repliky. */
static unsigned krok_qpc;            /* jednotky časovača QPC na jeden krok hry (1/25 s) */
static int preskakuje;              /* pretáčanie práve beží */
static volatile int pocet_replik;   /* zvyšuje hák repliky 0x438d58 */
static int preskok_repliky;         /* pocet_replik pri spustení pretáčania */
static DWORD preskok_start;

/* Herná scéna má meno z hexadecimálnych číslic (10a1, 109f, 123f); ponuky sú 1006.*, ďalej main, new_game_tmp_screen. */
static int herna_scena(void)
{
    const char *m = (const char *)SCENA;
    if (!m || !*m) return 0;
    for (int i = 0; m[i]; i++)
        if (i > 8 || !((m[i] >= '0' && m[i] <= '9') || (m[i] >= 'a' && m[i] <= 'f'))) return 0;
    return 1;
}

static int bez_kontroly(void)
{
    return herna_scena() && !FILM_BEZI && POUZIVATEL_POVOLENY() < 1;
}

static void spusti_preskok(void)
{
    if (!cfg_preskakovanie || !bez_kontroly()) return;
    preskakuje = 1; preskok_repliky = pocet_replik; preskok_start = GetTickCount();
    loguj("preskok start (repliky %d, scena %s, esc %d medzera %d)", pocet_replik, (char *)SCENA,
          drzi(VK_ESCAPE), drzi(VK_SPACE));
}

/* Zastaví jednorazové zvuky: kanály 0x59afe8 po 16 B (+4 obsadený, +0xC vzorka), počet [0x4904c8];
 * vzorka +0x1C = 1 slučka. Reč (vzorka 0x49ef58) nechá – tú preskočí hra sama. */
static void zastav_jednorazove_zvuky(void)
{
    int n = *(int *)0x4904c8;
    for (int i = 0; i < n && i < 64; i++) {
        unsigned char *k = (unsigned char *)0x59afe8 + 16 * i, *v = *(unsigned char **)(k + 0xc);
        if (!*(int *)(k + 4) || !v || v == (unsigned char *)0x49ef58 || *(int *)(v + 0x1c)) continue;
        loguj("  zastaveny zvuk kanal %d prio %d", i, *(int *)(v + 0x18));
        ((void (__cdecl *)(int))0x445cb6)(i);
    }
}

/* Práve niekto hovorí: niektorý obsadený kanál prehráva vzorku repliky 0x49ef58. */
static int rec_bezi(void)
{
    int n = *(int *)0x4904c8;
    for (int i = 0; i < n && i < 64; i++) {
        unsigned char *k = (unsigned char *)0x59afe8 + 16 * i;
        if (*(int *)(k + 4) && *(unsigned char **)(k + 0xc) == (unsigned char *)0x49ef58) return 1;
    }
    return 0;
}

static void preskakovanie_krok(void)
{
    int drzane = cfg_preskakovanie && drzi(VK_ESCAPE);
    if (drzane && !preskakuje) spusti_preskok();
    if (!preskakuje) return;
    if (!bez_kontroly() || GetTickCount() - preskok_start > 60000 ||
        (!drzane && pocet_replik != preskok_repliky)) {
        loguj("preskok koniec (repliky %d, kontrola %d)", pocet_replik, POUZIVATEL_POVOLENY());
        preskakuje = 0; return;
    }
    /* držanie: aj nové repliky sa hneď preskočia (pôvodné preskočenie repliky, WM_KEYDOWN ESC) */
    if (drzane && pocet_replik != preskok_repliky) {
        ((void (__cdecl *)(WPARAM, LPARAM))0x43f278)(VK_ESCAPE, 0x00010001);
        preskok_repliky = pocet_replik;
    }
    zastav_jednorazove_zvuky();
    if (krok_qpc) *(LONGLONG *)0x49bda0 -= krok_qpc;          /* logika nečaká na ďalší krok */
}

/* ---------- dvojklik: postava je hneď v cieli ---------- */
/* Hra dvojklik pozná sama (WM_LBUTTONDBLCLK → pri pustení tlačidla udalosť 0x50705c namiesto 0x50702c; akcie
 * doublemove/doubleuse – dvojklik na východ skráti cestu). Na podlahe postava ide normálne. Doplnok po dvojkliku
 * v hernej scéne chôdzu pretočí: kým hlavná postava ide (stav [0x49be3a] ≠ 0: 1 = chôdza na miesto, 2 = k objektu,
 * 7 = dvojklik na východ; poloha x/y 0x49be28/0x49be2c), logika nečaká na ďalší krok a na obrazovku sa nič neposiela
 * – postava sa objaví v cieli (ďalší dej, napr. použitie objektu alebo prechod do inej scény, beží normálne). */
#define CHODZA (*(int *)0x49be3a)
static int cfg_dvojklik;
static int chodza_rezim;            /* 0 = nič, 1 = čaká sa na začiatok chôdze po dvojkliku, 2 = pretáča sa */
static unsigned chodza_od;
static unsigned char *chodza_scena;

static void __cdecl dvojklik_mysi(void *udalost)
{
    ((void (__cdecl *)(void *))0x417949)(udalost);
    if (cfg_dvojklik && herna_scena() && hra_v_scene() && !preskakuje) {
        chodza_rezim = 1; chodza_od = pocet_krokov; chodza_scena = SCENA;
        loguj("dvojklik %d,%d stav chodze %d", *(int *)0x49be28, *(int *)0x49be2c, CHODZA);
    }
}

static void chodza_krok(void)
{
    if (!chodza_rezim) return;
    int ide = CHODZA != 0;
    if (SCENA != chodza_scena || !herna_scena() || FILM_BEZI || preskakuje ||
        pocet_krokov - chodza_od > 500 || (!ide && (chodza_rezim == 2 || pocet_krokov - chodza_od > 5))) {
        loguj("dvojklik koniec po %u krokoch (%d,%d stav %d, scena %s)", pocet_krokov - chodza_od,
              *(int *)0x49be28, *(int *)0x49be2c, CHODZA, SCENA ? (char *)SCENA : "-");
        chodza_rezim = 0; return;
    }
    if (!ide) return;
    chodza_rezim = 2;
    zastav_jednorazove_zvuky();                          /* kroky by inak zazneli naraz */
    if (krok_qpc) *(LONGLONG *)0x49bda0 -= krok_qpc;      /* logika nečaká na ďalší krok */
}

/* ---------- koliesko myši: listovanie predmetmi inventára na kurzore ---------- */
/* Pole inventára 0x578c10: 35 položiek po 0x28 B (meno[32], +0x20 = 1 obsadené). Predmet pripnutý na kurzor sa
 * z poľa vyberie (jeho miesto ostane prázdne) a po vrátení (pravý klik) sa vráti na to isté miesto. */
#define INVENTAR ((unsigned char *)0x578c10)
#define INVENTAR_POVOLENY (*(int *)0x48d2d8 > 0)
static int koliesko_kroky;          /* nahromadené zárezy kolieska (+ dole = ďalší predmet) */
static int koliesko_stav, koliesko_cakanie, koliesko_slot, koliesko_drzany, koliesko_pokus;
static char koliesko_ciel[32];
static unsigned char koliesko_zaloha[0x28];  /* položka inventára cieľa pred výberom (poistka) */

static int obsadene(int i) { unsigned char *e = INVENTAR + i * 0x28; return e[0] && *(int *)(e + 0x20) == 1; }
static int na_kurzore(const char *meno) { return VYBRANY_PREDMET && !lstrcmpA((char *)VYBRANY_PREDMET + 8, meno); }

static void vyber_predmet(void)
{
    unsigned char *s = SCENA, *o = NAJDI_OBJEKT(s, koliesko_ciel);
    if (!o) { ((int (__cdecl *)(const char *, unsigned char *, int, int))0x430052)(koliesko_ciel, s, 1, 1); o = NAJDI_OBJEKT(s, koliesko_ciel); }
    loguj("koliesko: vyber %s (%x)", koliesko_ciel, (unsigned)o);
    kopiruj(koliesko_zaloha, INVENTAR + koliesko_slot * 0x28, 0x28);
    koliesko_stav = 3; koliesko_cakanie = 25;
    if (o) ((int (__cdecl *)(unsigned char *, int, int))0x4311f7)(o, *(int *)0x507010, *(int *)0x507014);
}

/* Stavy: 0 = nič, 1 = čaká sa, kým sa predmet z kurzora vráti na svoje miesto v poli, 2 = pauza ~0,5 s,
 * 3 = čaká sa, kým sa cieľ pripne na kurzor (inak poistka vráti jeho položku do poľa a výber raz zopakuje),
 * 4 = pauza po výbere. Zárezy počas toho sa hromadia a spracujú naraz (jedno vrátenie + jeden výber). */
static void koliesko_krok(void)
{
    if (koliesko_stav == 1) {
        if ((VYBRANY_PREDMET || !obsadene(koliesko_drzany)) && --koliesko_cakanie > 0) return;
        if (VYBRANY_PREDMET) { loguj("koliesko: vratenie zlyhalo"); koliesko_stav = 0; return; }
        koliesko_stav = 2; koliesko_cakanie = 12;   /* skript vrátenia ešte dobieha (~0,5 s) – inak výber zlyhá */
        return;
    }
    if (koliesko_stav == 2) {
        if (--koliesko_cakanie > 0) return;
        if (!hra_v_scene() || !obsadene(koliesko_slot)) { koliesko_stav = 0; return; }
        vyber_predmet();
        return;
    }
    if (koliesko_stav == 3) {
        if (na_kurzore(koliesko_ciel)) { koliesko_stav = 4; koliesko_cakanie = 8; return; }
        if (--koliesko_cakanie > 0) return;
        koliesko_stav = 0;
        if (!VYBRANY_PREDMET && !obsadene(koliesko_slot)) {   /* skript predmet vyradil, ale nepripol – vrátiť */
            kopiruj(INVENTAR + koliesko_slot * 0x28, koliesko_zaloha, 0x28);
            loguj("koliesko: vyber zlyhal, %s vrateny do inventara%s", koliesko_ciel, koliesko_pokus ? "" : ", opakujem");
            if (!koliesko_pokus++) { koliesko_stav = 2; koliesko_cakanie = 12; }
        }
        return;
    }
    if (koliesko_stav == 4) {                       /* po výbere krátka pauza, kým skript výberu dobehne */
        if (--koliesko_cakanie <= 0) koliesko_stav = 0;
        return;
    }
    if (!koliesko_kroky) return;
    int kroky = koliesko_kroky; koliesko_kroky = 0;
    if (!hra_v_scene() || !INVENTAR_POVOLENY) return;
    int smer = kroky > 0 ? 1 : -1, n = kroky * smer;
    int drzany = -1;                                /* miesto predmetu na kurzore = prvé prázdne */
    if (VYBRANY_PREDMET) for (int i = 0; i < 35; i++) if (!obsadene(i)) { drzany = i; break; }
    int poloha = drzany >= 0 ? drzany : (smer > 0 ? -1 : 35), ciel = -1;
    for (int krok = 0; krok < n; krok++) {          /* n-tý obsadený slot v smere (cyklicky, ak niečo drží) */
        int najdeny = -1;
        for (int k = 1; k <= 35; k++) {
            int i = poloha + smer * k;
            if (drzany >= 0 || ciel >= 0) i = (i % 35 + 35) % 35;
            else if (i < 0 || i >= 35) break;
            if (i != drzany && obsadene(i)) { najdeny = i; break; }
        }
        if (najdeny < 0) break;
        ciel = poloha = najdeny;
    }
    if (ciel < 0) return;
    kopiruj(koliesko_ciel, INVENTAR + ciel * 0x28, 31); koliesko_ciel[31] = 0;
    koliesko_slot = ciel; koliesko_pokus = 0;
    if (VYBRANY_PREDMET) {                          /* najprv vrátiť predmet (ako pravý klik) */
        loguj("koliesko: vratit %s, ciel %s", (char *)VYBRANY_PREDMET + 8, koliesko_ciel);
        koliesko_drzany = drzany >= 0 ? drzany : 0;
        ((int (__cdecl *)(void *))0x417949)((void *)0x50703c);
        koliesko_stav = 1; koliesko_cakanie = 25;
    } else vyber_predmet();
}

/* ---------- F5 = uložiť hru, F8 = nahrať hru (otvorí ponuku a vyberie položku) ---------- */
/* Stav: 1/2 = čaká sa na hlavnú ponuku (1006.100e) po kliku na kolieska, 3 = obrazovka otvorená skratkou,
 * 4 = ESC na nej (hra sa vráti do hlavnej ponuky) – ďalší ESC z hlavnej ponuky vráti rovno do hry. */
static int cfg_skratky, skratka_ziadost, skratka_stav, skratka_polozka;
static DWORD skratka_cas;

static void skratky_krok(void)
{
    unsigned char *s = SCENA;
    if (skratka_ziadost) {
        int z = skratka_ziadost; skratka_ziadost = 0;
        if (s && !lstrcmpA((char *)s, "1006.100e")) { skratka_polozka = z; skratka_stav = 2; skratka_cas = GetTickCount(); }
        else if (hra_v_scene()) { otvor_ponuku(); skratka_polozka = z; skratka_stav = 1; skratka_cas = GetTickCount(); }
        return;
    }
    if (!skratka_stav) return;
    if (skratka_stav <= 2) {
        if (s && !lstrcmpA((char *)s, "1006.100e") && POUZIVATEL_POVOLENY() >= 1) {   /* ponuka už nabehla */
            const char *m = skratka_polozka == 1 ? "1006.100e.100b" : "1006.100e.1020";     /* Uložit / Nahrát */
            unsigned char *o = NAJDI_OBJEKT(s, m);
            if (!o) {           /* položka je v scéne len pri prejdení myšou */
                ((int (__cdecl *)(const char *, unsigned char *, int, int))0x430052)(m, s, 1, 1);
                o = NAJDI_OBJEKT(s, m);
            }
            if (o) {
                loguj("skratka -> %s", m);
                ((int (__cdecl *)(unsigned char *, int, int))0x4311f7)(o, 397, skratka_polozka == 1 ? 233 : 269);
                skratka_stav = 3; return;
            }
        }
        if (GetTickCount() - skratka_cas > 5000) { loguj("skratka: ponuka neprisla"); skratka_stav = 0; }
        return;
    }
    if (skratka_stav == 4 && s && !lstrcmpA((char *)s, "1006.100e") && POUZIVATEL_POVOLENY() >= 1) {   /* späť do hry */
        loguj("skratka: ESC -> hra");
        ((void (__cdecl *)(WPARAM, LPARAM))0x43f278)(VK_ESCAPE, 0x00010001);
        skratka_stav = 0; return;
    }
    if (hra_v_scene()) skratka_stav = 0;                    /* po uložení/nahratí je hráč späť v hre */
}

/* ---------- hardvérový kurzor ([Cursor] Mode=hardware) ---------- */
/* Kurzor hry je animácia scény s poradím −10 („defmouse“, „mouse pic“, „mouse object“ = predmet...). Doplnok jej
 * pixely (+0x24) presmeruje na priehľadné pole (šablóny hry ostanú nedotknuté), takže ho hra ani dgVoodoo nekreslia,
 * a pôvodný obrázok ukáže vo vlastnom priehľadnom okne nad hrou. To okno presúva samostatné vlákno 1000× za sekundu
 * podľa GetCursorPos – Windows ho skladá nezávisle od snímok hry (hra 25/s, dgVoodoo vsync). dgVoodoo drží fyzický
 * kurzor v obdĺžniku 800×600 (ClipCursor), takže poloha v hre = GetCursorPos − ľavý horný roh obdĺžnika.
 * Citlivosť (Sensitivity) v tomto režime počíta to isté vlákno (bm_core ju vtedy vynechá), aby okno neposkakovalo
 * medzi nepreškálovanou a preškálovanou polohou. */
static int cfg_hw, cfg_citl = 700;
static unsigned hw_prazdne[256 * 256];          /* priehľadné pixely (purpurová) pre animáciu kurzora */
static unsigned hw_pix[128 * 128];              /* obrázok kurzora hry (B, G, R, 100; purpurová = priehľadná) */
static volatile LONG hw_verzia, hw_viditelny, hw_resync = 1;
static int hw_w, hw_h, hw_dx, hw_dy;            /* rozmery, posun obrázka voči polohe myši (px hry) */
static CRITICAL_SECTION hw_cs;
static HANDLE hw_vlakno_h;

/* V hernom vlákne (krok, zobrazenie): skryje kurzor hry a odovzdá jeho obrázok. Vráti 1, ak niečo zmenil
 * (vtedy treba scénu prekresliť, inak by na obrazovku išla snímka ešte s kurzorom hry). */
static int hw_kurzor_hra(void)
{
    unsigned char *s = SCENA;
    if (!cfg_hw || !hw_vlakno_h) return 0;
    if (!s || FILM_BEZI) { hw_viditelny = 0; return 0; }
    unsigned char *prvy = *(unsigned char **)(s + 0x80 + 0x28), *a = prvy, *kurzor = 0;
    int k = 0, zmena = 0;
    while (a && k++ < 5000) {
        if (I32(a, 0xc) == -10 && I32(a, 0x18) == 32) {
            int w = I32(a, 0x10), h = I32(a, 0x14);
            unsigned *p = *(unsigned **)(a + 0x24);
            if (p && p != hw_prazdne && w > 0 && h > 0 && w <= 128 && h <= 128) {
                EnterCriticalSection(&hw_cs);
                kopiruj(hw_pix, p, w * h * 4); hw_w = w; hw_h = h;
                LeaveCriticalSection(&hw_cs);
                *(unsigned **)(a + 0x24) = hw_prazdne;
                InterlockedIncrement(&hw_verzia); zmena = 1;
            }
            if (*(unsigned **)(a + 0x24) == hw_prazdne) kurzor = a;
        }
        a = *(unsigned char **)a;
        if (a == prvy) break;
    }
    if (kurzor) {
        int dx = I32(kurzor, 0x1c) - I32(s, 0x5d5) - MYS_X, dy = I32(kurzor, 0x20) - I32(s, 0x5d9) - MYS_Y;
        if (dx != hw_dx || dy != hw_dy) { hw_dx = dx; hw_dy = dy; InterlockedIncrement(&hw_verzia); }
    }
    hw_viditelny = kurzor != 0;
    return zmena;
}

static BOOL WINAPI hw_setcursorpos(int x, int y) { hw_resync = 1; return SetCursorPos(x, y); }   /* hra presúva kurzor */

static void hw_obrazok(unsigned *bity, int nw, int nh)
{
    int w = hw_w, h = hw_h;
    for (int y = 0; y < nh; y++)
        for (int x = 0; x < nw; x++) {
            int sx = ((2 * x + 1) * w * 128) / nw - 128, sy = ((2 * y + 1) * h * 128) / nh - 128;   /* 1/256 px */
            int x0 = sx >> 8, y0 = sy >> 8, fx = sx & 255, fy = sy & 255;
            int vahy[4] = {(256 - fx) * (256 - fy), fx * (256 - fy), (256 - fx) * fy, fx * fy};
            unsigned sa = 0, sr = 0, sg = 0, sb = 0;
            for (int i = 0; i < 4; i++) {
                int xx = x0 + (i & 1), yy = y0 + (i >> 1);
                if (xx < 0 || yy < 0 || xx >= w || yy >= h) continue;
                unsigned c = hw_pix[yy * w + xx];
                if ((c & 0xFFFFFF) == 0xFF00FF) continue;
                sa += 255 * vahy[i]; sr += ((c >> 16) & 255) * vahy[i];
                sg += ((c >> 8) & 255) * vahy[i]; sb += (c & 255) * vahy[i];
            }
            bity[y * nw + x] = ((sa >> 16) << 24) | ((sr >> 16) << 16) | ((sg >> 16) << 8) | (sb >> 16);
        }
}

static DWORD WINAPI hw_vlakno(LPVOID nic)
{
    (void)nic;
    HMODULE wm = LoadLibraryA("winmm.dll");                  /* Sleep(1) = 1 ms */
    FARPROC tbp = wm ? GetProcAddress(wm, "timeBeginPeriod") : 0;
    if (tbp) ((UINT (WINAPI *)(UINT))tbp)(1);
    while (!HWND_HRY) Sleep(50);
    WNDCLASSA wc; memset(&wc, 0, sizeof wc);
    wc.lpfnWndProc = DefWindowProcA; wc.hInstance = GetModuleHandleA(0); wc.lpszClassName = "bmqol_kurzor";
    RegisterClassA(&wc);
    HWND okno = CreateWindowExA(WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW,
                                "bmqol_kurzor", "", WS_POPUP, 0, 0, 1, 1, 0, 0, wc.hInstance, 0);   /* bez vlastníka: presun nečaká na herné vlákno */
    loguj("hw kurzor: okno %x", (unsigned)(size_t)okno);
    if (!okno) return 0;
    HDC obr = GetDC(0), pam = CreateCompatibleDC(obr);
    HBITMAP bmp = 0; unsigned *bity = 0;
    int verzia = -1, mierka_obr = 0, bw = 0, bh = 0, ukazane = 0, px = -9999, py = -9999;
    int vx = 0, vy = 0, lx = 0, ly = 0;
    for (;;) {
        MSG m;
        while (PeekMessageA(&m, 0, 0, 0, PM_REMOVE)) DispatchMessageA(&m);
        Sleep(1);
        HWND hra = HWND_HRY;
        /* FILM_BEZI aj tu: film má vlastnú slučku, krok hry (hw_kurzor_hra) počas neho nebeží a hw_viditelny
         * by ostalo z ponuky – nad filmom by visel kurzor (napr. červený z Nová hra) */
        int vid = hw_viditelny && !FILM_BEZI && hra && GetForegroundWindow() == hra && !IsIconic(hra);
        if (!vid) { if (ukazane) { ShowWindow(okno, SW_HIDE); ukazane = 0; } hw_resync = 1; continue; }
        /* obraz hry v okne: 800×600 zväčšené so zachovaným pomerom, na stred klientskej oblasti */
        RECT rc; GetClientRect(hra, &rc);
        POINT o = {0, 0}; ClientToScreen(hra, &o);
        int cw = rc.right, ch = rc.bottom;
        int mierka = cw * 1000 / 800 < ch * 1000 / 600 ? cw * 1000 / 800 : ch * 1000 / 600;   /* v tisícinách */
        if (mierka <= 0) continue;
        int ox = o.x + (cw - 800 * mierka / 1000) / 2, oy = o.y + (ch - 600 * mierka / 1000) / 2;
        /* poloha v hre: fyzický kurzor v obdĺžniku 800×600 dgVoodoo */
        RECT kl; GetClipCursor(&kl);
        int klip = kl.right - kl.left == 800 && kl.bottom - kl.top == 600;
        int zx = klip ? kl.left : 0, zy = klip ? kl.top : 0;
        POINT p; GetCursorPos(&p);
        if (cfg_citl < 1000) {
            if (hw_resync) { hw_resync = 0; vx = p.x * 1000; vy = p.y * 1000; lx = p.x; ly = p.y; }
            else if (p.x != lx || p.y != ly) {
                vx += (p.x - lx) * cfg_citl; vy += (p.y - ly) * cfg_citl;
                if (vx < zx * 1000) vx = zx * 1000;
                if (vx > (zx + 799) * 1000) vx = (zx + 799) * 1000;
                if (vy < zy * 1000) vy = zy * 1000;
                if (vy > (zy + 599) * 1000) vy = (zy + 599) * 1000;
                lx = vx / 1000; ly = vy / 1000;
                SetCursorPos(lx, ly);
                p.x = lx; p.y = ly;
            }
        }
        /* obrázok: zväčšený bilineárne, premultiplikovaná alfa (purpurová = priehľadná) */
        if (hw_verzia != verzia || mierka != mierka_obr) {
            EnterCriticalSection(&hw_cs);
            verzia = hw_verzia; mierka_obr = mierka;
            int nw = (hw_w * mierka + 999) / 1000, nh = (hw_h * mierka + 999) / 1000;
            if (nw < 1) nw = 1;
            if (nh < 1) nh = 1;
            if (!bmp || nw != bw || nh != bh) {
                if (bmp) DeleteObject(bmp);
                BITMAPINFO bi; memset(&bi, 0, sizeof bi);
                bi.bmiHeader.biSize = sizeof bi.bmiHeader; bi.bmiHeader.biWidth = nw; bi.bmiHeader.biHeight = -nh;
                bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 32;
                bmp = CreateDIBSection(pam, &bi, DIB_RGB_COLORS, (void **)&bity, 0, 0);
                SelectObject(pam, bmp); bw = nw; bh = nh;
            }
            if (bity) hw_obrazok(bity, nw, nh);
            LeaveCriticalSection(&hw_cs);
            POINT nula = {0, 0}; SIZE vel = {bw, bh};
            BLENDFUNCTION mi = {AC_SRC_OVER, 0, 255, AC_SRC_ALPHA};
            POINT kam = {ox + (p.x - zx + hw_dx) * mierka / 1000, oy + (p.y - zy + hw_dy) * mierka / 1000};
            UpdateLayeredWindow(okno, obr, &kam, &vel, pam, &nula, 0, &mi, ULW_ALPHA);
            px = kam.x; py = kam.y;
        }
        int nx = ox + (p.x - zx + hw_dx) * mierka / 1000, ny = oy + (p.y - zy + hw_dy) * mierka / 1000;
        if (nx != px || ny != py || !ukazane) {
            if (ukazane) SetWindowPos(okno, 0, nx, ny, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOZORDER | SWP_NOOWNERZORDER);
            else SetWindowPos(okno, HWND_TOPMOST, nx, ny, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW);
            px = nx; py = ny; ukazane = 1;
        }
    }
}

static void hw_start(void)
{
    if (!cfg_hw || hw_vlakno_h) return;
    for (int i = 0; i < 256 * 256; i++) hw_prazdne[i] = 0x64FF00FF;
    InitializeCriticalSection(&hw_cs);
    hw_vlakno_h = CreateThread(0, 0, hw_vlakno, 0, 0, 0);
}

/* ---------- obrazovka Uložit/Nahrát hru: názvy pozícií bez čierneho obdĺžnika ---------- */
/* Názvy pozícií sú animácie „1006.101b.100b.N“ (text vykreslený na čiernom pozadí, 0,0,0). Čisté čierne pixely sa
 * zmenia na priehľadnú purpurovú (ako okraje bodiek a ikon), text ostane. Hra obrázok nanovo vytvorí pri zmene
 * (napr. písanie názvu), preto sa kontroluje každý krok; pri zmene sa scéna prekreslí (0x426c43). */
static int cfg_nazvy;
/* Bodkovaná čiara za názvom je priamo v pozadí „ulozit_hru.bmp“ (800×600) a čierny obdĺžnik ju pod textom zakrýval.
 * Doplnok si uloží pôvodný pás pozadia (B_X0..B_X1 × B_Y0..B_Y1) a pod šírkou každého názvu nahradí riadky
 * s bodkami pixelmi z najbližšieho riadku nad nimi bez bodiek. */
#define B_X0 280
#define B_X1 640
#define B_Y0 150
#define B_Y1 460
static unsigned pozadie_orig[B_Y1 - B_Y0][B_X1 - B_X0];
static unsigned *pozadie_p;                     /* pixely pozadia, z ktorých je uložený pôvodný pás */
static int pozadie_stav[16];                    /* posledná šírka názvu (na zistenie zmeny) */

static int jas_r(unsigned c) { return (c >> 16) & 255; }
static int riadok_bodiek(int y, int x0)          /* v pôvodnom pozadí sú na riadku bodky (veľa svetlých pixelov) */
{
    int n = 0;
    if (y < B_Y0 || y >= B_Y1) return 0;
    for (int x = x0; x < B_X1 && x < x0 + 200; x++) if (jas_r(pozadie_orig[y - B_Y0][x - B_X0]) > 100) n++;
    return n > 15;
}

static void priehladne_nazvy(void)
{
    unsigned char *s = SCENA;
    if (!cfg_nazvy || !s || !zacina((char *)s, "1006.101b")) { pozadie_p = 0; return; }
    unsigned char *prvy = *(unsigned char **)(s + 0x80 + 0x28), *a = prvy, *poz = 0;
    int k = 0;
    while (a && k++ < 2000) {                      /* pozadie */
        if (!lstrcmpA((char *)a + 0x41, "ulozit_hru.bmp") && I32(a, 0x10) == 800 && I32(a, 0x14) == 600 && I32(a, 0x18) == 32) poz = a;
        a = *(unsigned char **)a;
        if (a == prvy) break;
    }
    unsigned *bg = poz ? *(unsigned **)(poz + 0x24) : 0;
    if (bg && bg != pozadie_p) {
        for (int y = B_Y0; y < B_Y1; y++) kopiruj(pozadie_orig[y - B_Y0], bg + y * 800 + B_X0, (B_X1 - B_X0) * 4);
        pozadie_p = bg;
        for (int i = 0; i < 16; i++) pozadie_stav[i] = -1;
    }
    int zmena = 0;
    a = prvy; k = 0;
    while (a && k++ < 2000) {
        if (zacina((char *)a + 0x41, "1006.101b.100b.") && I32(a, 0x18) == 32) {
            int w = I32(a, 0x10), h = I32(a, 0x14), n = w * h;
            unsigned *p = *(unsigned **)(a + 0x24);
            if (p && n > 0 && n <= 800 * 64)
                for (int i = 0; i < n; i++)
                    if ((p[i] & 0xFFFFFF) == 0) { p[i] |= 0xFF00FF; zmena = 1; }
            int slot = ((char *)a)[0x41 + 15] - '0';
            int x = I32(a, 0x1c), y = I32(a, 0x20);
            if (bg && slot >= 0 && slot < 16 && pozadie_stav[slot] != w && x >= B_X0 && y >= B_Y0 && y + h <= B_Y1) {
                int x1 = x + w > B_X1 ? B_X1 : x + w;
                for (int yy = y; yy < y + h; yy++) {
                    int zdroj = yy;                                 /* riadok bez bodiek nad (alebo pod) */
                    if (riadok_bodiek(yy, x)) {
                        while (zdroj > y && riadok_bodiek(zdroj, x)) zdroj--;
                        if (riadok_bodiek(zdroj, x)) { zdroj = yy; while (zdroj < y + h - 1 && riadok_bodiek(zdroj, x)) zdroj++; }
                    }
                    for (int xx = B_X0; xx < B_X1; xx++)            /* pôvodný riadok, pod názvom bez bodiek */
                        bg[yy * 800 + xx] = pozadie_orig[(xx >= x && xx < x1 ? zdroj : yy) - B_Y0][xx - B_X0];
                }
                pozadie_stav[slot] = w; zmena = 1;
            }
        }
        a = *(unsigned char **)a;
        if (a == prvy) break;
    }
    if (zmena) ((void (__cdecl *)(unsigned char *))0x426c43)(s);
}

/* ---------- rýchle uloženie / načítanie (Ctrl+S / Ctrl+L) a hláška dole ---------- */
/* Hra ukladá 0x433bb0(slot) -> save.N (+ savepic.N, mená všetkých pozícií do savnames.txt z poľa 0x5776e8,
 * 99 položiek po 0x33 B, index = číslo pozície), načítava 0x433708(slot). Rýchla pozícia = [Controls] QuickSaveSlot
 * (predvolene 98, v zozname pozícií je na konci). Hláška: text písmom titulkov (tell_font [0x584e48]) cez
 * 0x446c75(&šablóna, x, y, 1 = na stred, text, písmo, -1) – ako titulky, na ich mieste (subtitle_x/y [0x584e38/3c]);
 * animácia s pixelmi z pamäte hry, zobrazená 50 krokov (2 s) ako značky medzerníka. */
static int __cdecl nacitaj_hru(int slot);
static int cfg_rychle, cfg_rychla_pozicia = 98, jazyk;     /* jazyk hlášok: 0 sk, 1 cs, 2 en (podľa config.ini) */
static int rychle_ziadost;                                  /* 1 = uložiť, 2 = načítať */
static unsigned cez_ponuku;                                 /* krok, od ktorého rýchle načítanie čaká, kým Samuel zastane */
static unsigned char *hlaska_anim, *hlaska_scena;
static unsigned hlaska_do;
static const wchar_t *const TEXTY[3][6] = {
    {L"Rýchle uloženie", L"Rýchle načítanie", L"Rýchla pozícia ešte nie je uložená", L"Teraz sa nedá uložiť", L"Rýchle uloženie", L"Teraz sa nedá načítať"},
    {L"Rychlé uložení", L"Rychlé nahrání", L"Rychlá pozice ještě není uložená", L"Teď nelze uložit", L"Rychlé uložení", L"Teď nelze nahrát"},
    {L"Quick save", L"Quick load", L"No quick save yet", L"Cannot save now", L"Quick save", L"Cannot load now"},
};
enum { T_ULOZENE, T_NACITANE, T_NIE_JE, T_NEDA_SA, T_MENO, T_NEDA_SA_NACITAT };

/* Texty hry sú v kódovaní Kamenických (zistené z pamäte: „ke schodišti“ š = 0xA8, „jídelny“ í = 0xA1),
 * písmo titulkov má znaky na týchto pozíciách (cp1250 ž 0x9E sa kreslilo ako Ř). */
static const wchar_t KAMENICKI[44] = {
    L'Č', L'ü', L'é', L'ď', L'ä', L'Ď', L'Ť', L'č', L'ě', L'Ě', L'Ĺ', L'Í', L'ľ', L'ĺ', L'Ä', L'Á',
    L'É', L'ž', L'Ž', L'ô', L'ö', L'Ó', L'ů', L'Ú', L'ý', L'Ö', L'Ü', L'Š', L'Ľ', L'Ý', L'Ř', L'ť',
    L'á', L'í', L'ó', L'ú', L'ň', L'Ň', L'Ů', L'Ô', L'š', L'ř', L'ŕ', L'Ŕ'};
static void do_kamenickych(const wchar_t *z, char *c, int max)
{
    int i = 0;
    for (; *z && i < max - 1; z++) {
        unsigned char b = '?';
        if (*z < 128) b = (unsigned char)*z;
        else for (int k = 0; k < 44; k++) if (KAMENICKI[k] == *z) { b = (unsigned char)(0x80 + k); break; }
        c[i++] = (char)b;
    }
    c[i] = 0;
}

/* Rýchle načítanie: hlavná ponuka (aj ponuka ESC) vypne inventár skriptovým príkazom 0x43793d (počítadlo
 * [0x48d2d8] -1) a zapne ho až skript obrazovky nahrávania (0x437986) – po Ctrl+L z hlavnej ponuky bol 0
 * a lišta inventára sa neukázala (24. 11. 2026). Po rýchlom načítaní sa preto zapne, ak je vypnutý. */
static void po_nacitani(void)
{
    if (*(int *)0x48d2d8 < 1) {
        ((void (__cdecl *)(void))0x437986)();
        loguj("po nacitani: inventar zapnuty (%d)", *(int *)0x48d2d8);
    }
}

static void hlaska_zrus(void)
{
    if (hlaska_anim && SCENA == hlaska_scena) {
        ((void (__cdecl *)(void *))0x418d17)(hlaska_anim + 0x10);                 /* pixely (pamäť hry) */
        ((void (__cdecl *)(unsigned char *, unsigned char **))0x406b31)(SCENA, &hlaska_anim);
    }
    hlaska_anim = 0;                    /* v inej scéne ju hra uvoľnila s celou scénou */
}

static void hlaska(int i)
{
    unsigned char *s = SCENA, t[32];
    char a[128];
    hlaska_zrus();
    if (!s) return;
    do_kamenickych(TEXTY[jazyk][i], a, sizeof a);
    memset(t, 0, sizeof t);
    unsigned char *v = ((unsigned char *(__cdecl *)(void *, int, int, int, const char *, int, int))0x446c75)(
        t, I32(s, 0x5d5) + *(int *)0x584e38, I32(s, 0x5d9) + *(int *)0x584e3c, 1, a, *(int *)0x584e48, -1);
    if (!v || !*(void **)(v + 0x14)) { loguj("hlaska: text sa nevykreslil"); return; }
    *(int *)(v + 0xc) = I32(s, 0x5d5) + *(int *)0x584e38 - *(int *)v / 2;   /* x = ľavý okraj -> na stred okolo subtitle_x */
    hlaska_anim = ((unsigned char *(__cdecl *)(unsigned char *, void *, int, int, const char *))0x406932)(s, v, -8, 0, "bmqol_hlaska");
    hlaska_scena = s; hlaska_do = pocet_krokov + KROKY_HOTSPOTOV;
    loguj("hlaska %d: %s (%dx%d)", i, a, *(int *)v, *(int *)(v + 4));
}

static void rychle_krok(void)
{
    if (hlaska_anim && (pocet_krokov >= hlaska_do || SCENA != hlaska_scena)) hlaska_zrus();
    int ponuka = SCENA && !lstrcmpA((char *)SCENA, "1006.100e") && POUZIVATEL_POVOLENY() >= 1;   /* hlavná ponuka */
    int slot = cfg_rychla_pozicia;
    /* Načítanie počas chôdze: načítanie nastaví polohu a stav postavy, nie jej obrázok – Samuel by ostal v póze
     * kroku (zistené 24. 11. 2026). Preto ho doplnok najprv zastaví príkazom „choď na miesto, kde stojíš“
     * (0x41c193 ako akcia move, zruší aj cieľ, napr. východ), chôdzu pretočí (bez snímok, ako po dvojkliku)
     * a načíta, až keď stojí. Načítanie cez ponuku by fungovalo tiež, ale obraz by stál ~3 s. */
    if (cez_ponuku) {
        if (CHODZA && pocet_krokov - cez_ponuku < 250) {
            if (!chodza_rezim) { chodza_rezim = 1; chodza_od = pocet_krokov; chodza_scena = SCENA; }
            return;
        }
        cez_ponuku = 0;
        hlaska_zrus();
        nacitaj_hru(slot);
        po_nacitani();
        loguj("rychle nacitanie save.%d (po zastaveni), scena %s", slot, SCENA ? (char *)SCENA : "-");
        hlaska(T_NACITANE);
        return;
    }
    if (!rychle_ziadost) return;
    int z = rychle_ziadost; rychle_ziadost = 0;
    if (z == 2 && ponuka) { /* načítanie aj z hlavnej ponuky (hneď po spustení hry) */ }
    else if (!herna_scena()) return;
    else if (!hra_v_scene()) { hlaska(z == 1 ? T_NEDA_SA : T_NEDA_SA_NACITAT); return; }   /* rozhovor, animácia, prechod */
    if (z == 1) {
        if (((fn0)0x409360)()) { hlaska(T_NEDA_SA); return; }       /* hra by uloženie odmietla */
        char *meno = (char *)0x5776e8 + slot * 0x33;
        do_kamenickych(TEXTY[jazyk][T_MENO], meno, 0x32);
        ((void (__cdecl *)(int))0x433bb0)(slot);
        loguj("rychle ulozenie -> save.%d", slot);
        hlaska(T_ULOZENE);
    } else {
        char subor[MAX_PATH]; int n = lstrlenA(cesta_ini);
        kopiruj(subor, cesta_ini, n + 1);
        while (n > 0 && subor[n - 1] != '\\') n--;
        wsprintfA(subor + n, "save.%d", slot);
        if (GetFileAttributesA(subor) == INVALID_FILE_ATTRIBUTES) { hlaska(T_NIE_JE); return; }
        if (ponuka) {
            hlaska_zrus();
            nacitaj_hru(slot);
            po_nacitani();
            loguj("rychle nacitanie save.%d (z ponuky), scena %s", slot, SCENA ? (char *)SCENA : "-");
            hlaska(T_NACITANE);
        } else if (CHODZA) {
            int *p = (int *)0x49be28;
            ((int (__cdecl *)(void *, int, int, int, int, int, int))0x41c193)((void *)0x49bde8, p[0], p[1], 0, -1, 1, 0);
            cez_ponuku = pocet_krokov ? pocet_krokov : 1;
            if (!chodza_rezim) { chodza_rezim = 1; chodza_od = pocet_krokov; chodza_scena = SCENA; }
            loguj("rychle nacitanie: zastavenie chodze na %d,%d", p[0], p[1]);
        } else {
            hlaska_zrus();
            nacitaj_hru(slot);
            po_nacitani();
            loguj("rychle nacitanie save.%d, scena %s", slot, SCENA ? (char *)SCENA : "-");
            hlaska(T_NACITANE);
        }
    }
}

/* Jazyk hlášok podľa poznámok v config.ini (ako inštalácia): „kurzoru“ = česky, „kurzora“ = slovensky, inak anglicky. */
static void zisti_jazyk(void)
{
    static char b[8192];
    DWORD n = 0;
    HANDLE f = CreateFileA(cesta_ini, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, 0, OPEN_EXISTING, 0, 0);
    jazyk = 2;
    if (f == INVALID_HANDLE_VALUE) return;
    ReadFile(f, b, sizeof b - 1, &n, 0); CloseHandle(f); b[n] = 0;
    if (obsahuje(b, "kurzoru")) jazyk = 1;
    else if (obsahuje(b, "kurzora")) jazyk = 0;
}

/* ---------- háky ---------- */
static int prvy_krok = 1;
static int __cdecl hra_krok(void)
{
    ladenie.udalosti[0]++;
    pocet_krokov++;
    if (cfg_hw && !hw_vlakno_h) hw_start();
    hw_kurzor_hra();
    ladenie_krok();
    if (prvy_krok) { prvy_krok = 0; obnov_nastavenia("start"); }
    if (esc_ziadost) { esc_ziadost = 0; if (hra_v_scene()) otvor_ponuku(); }
    else schovaj_kolieska();
    znacky_krok();
    kurzor_nad_vychodom_krok();
    preskakovanie_krok();
    chodza_krok();
    priehladne_nazvy();
    ladenie.udalosti[4] = preskakuje;
    if (cfg_koliesko) koliesko_krok();
    skratky_krok();
    rychle_krok();
    return ((fn0)0x431cf8)();
}

static void __cdecl klaves_dole(WPARAM w, LPARAM l)
{
    int opakovanie = (l >> 30) & 1;
    ladenie.udalosti[1] = (int)w;
    loguj("klaves %x opak %d scena %s pouz %d", (int)w, opakovanie, SCENA ? (char *)SCENA : "-", POUZIVATEL_POVOLENY());
    if ((w == 'S' || w == 'L') && cfg_rychle && (GetKeyState(VK_CONTROL) & 0x8000)) {     /* Ctrl+S / Ctrl+L */
        if (!opakovanie) rychle_ziadost = w == 'S' ? 1 : 2;
        return;
    }
    if (w == VK_ESCAPE && cfg_esc_ponuka && hra_v_scene()) { if (!opakovanie) esc_ziadost = 1; return; }
    if (w == VK_SPACE && cfg_hotspoty && hra_v_scene() && !rec_bezi()) {   /* hotspoty sa zbierajú v kroku */
        hotspoty_do = pocet_krokov + KROKY_HOTSPOTOV;      /* ako tabulátor; opakovanie pri držaní predlžuje */
        return;
    }
    if (cfg_preskakovanie && bez_kontroly()) {
        /* rozhovor / animácia: ESC = preskočenie repliky + pretáčanie po ďalšiu repliku, medzerník = len jedna
         * replika (bez opakovania pri držaní), ostatné klávesy nič (hra by nimi tiež preskakovala repliky) */
        if (w == VK_ESCAPE) { if (!opakovanie) spusti_preskok(); }
        else if (w != VK_SPACE || opakovanie) return;
    }
    if ((w == VK_F5 || w == VK_F8) && cfg_skratky && !opakovanie) { skratka_ziadost = w == VK_F5 ? 1 : 2; return; }
    if (w == VK_ESCAPE && !opakovanie && skratka_stav == 3 && SCENA && zacina((char *)SCENA, "1006.101b")) skratka_stav = 4;
    ((void (__cdecl *)(WPARAM, LPARAM))0x43f278)(w, l);
}

static LRESULT WINAPI okno_ine(HWND h, UINT sprava, WPARAM w, LPARAM l)
{
    if (sprava == WM_MOUSEWHEEL) {
        static int zvysok;                      /* jemné kolieska posielajú menej ako 120 na zárez */
        zvysok += (short)HIWORD(w);
        while (zvysok >= 120) { zvysok -= 120; if (koliesko_kroky > -4) koliesko_kroky--; }   /* hore = predchádzajúci */
        while (zvysok <= -120) { zvysok += 120; if (koliesko_kroky < 4) koliesko_kroky++; }   /* dole = ďalší */
        ladenie.udalosti[2] = koliesko_kroky;
        return 0;
    }
    return DefWindowProcA(h, sprava, w, l);
}

static int __cdecl nacitaj_hru(int slot)
{
    int r = ((int (__cdecl *)(int))0x433708)(slot);
    loguj("nacitanie hry %d -> %d", slot, r);
    obnov_nastavenia("nacitanie");      /* uložená hra prepíše systémové premenné vrátane nastavení */
    return r;
}

/* Zobrazenie (Blt zadného povrchu na obrazovku). */
static void (__cdecl *zobraz_povodne)(void);
/* ---------- vyhladenie hrán pred zväčšením (FXAA nad snímkou 800×600) ---------- */
/* [Video] Smoothing: 0 = vypnuté, 1 = FXAA na postavách, 2 = FXAA na celej ploche scény (nikdy ponuky a texty). Snímka sa skopíruje (zdroj filtra aj záloha), výsledok sa zapíše do
 * zadného povrchu, po Blt na obrazovku sa pôvodná snímka vráti (hra prekresľuje len zmenené časti). */
static int cfg_vyhladenie, cfg_fxaa_sila, cfg_fxaa_prah, cfg_fxaa_min;   /* sila subpixelového vyhladenia v % (FXAA 3.11: 75), prahy hrany */
static unsigned snimka[600][800], vystup[600][800];
static unsigned char jas[600][800], zmeneny[600];

static int abs_i(int x) { return x < 0 ? -x : x; }

static void fxaa_jas(int y0, int y1)
{
    /* jas (zelená prevažuje ako vo FXAA) */
    for (int y = y0; y < y1; y++)
        for (int x = 0; x < 800; x++) {
            unsigned c = snimka[y][x];
            jas[y][x] = (unsigned char)((((c >> 16) & 255) * 77 + ((c >> 8) & 255) * 150 + (c & 255) * 29) >> 8);
        }
}

static volatile LONG pocet_hran;
#define MAX_OBLASTI 16
static RECT oblasti[MAX_OBLASTI];
static int pocet_oblasti;

/* Obdĺžniky na vyhladenie: Smoothing=1 – postavy (animácie scény s ukazovateľom na postavu +0x61; obdĺžnik ako
 * pri prekresľovaní v 0x406b31: x = post[0x4a] + post[0x37e], y = post[0x4e] + post[0x382], š = post[0x52],
 * v = post[0x56], mínus posun scény), Smoothing=2 – celá plocha scény (bez horného a dolného pásu s textami). */
static int zbieraj_oblasti(void)
{
    unsigned char *s = SCENA;
    pocet_oblasti = 0;
    if (cfg_vyhladenie == 2) { RECT r = {0, 45, 800, 544}; oblasti[pocet_oblasti++] = r; return 1; }
    unsigned char *prvy = *(unsigned char **)(s + 0x80 + 0x28), *a = prvy;
    int k = 0;
    while (a && k++ < 5000 && pocet_oblasti < MAX_OBLASTI) {
        unsigned char *p = *(unsigned char **)(a + 0x61);
        const char *meno = (const char *)a + 0x41;
        int x = 0, y = 0, w = 0, h = 0;
        if (p) {                                        /* NPC: obdĺžnik z údajov postavy */
            x = I32(p, 0x4a) + I32(p, 0x37e) - I32(s, 0x5d5); y = I32(p, 0x4e) + I32(p, 0x382) - I32(s, 0x5d9);
            w = I32(p, 0x52); h = I32(p, 0x56);
        } else if (!*(void **)(a + 0x71) && I32(a, 0xc) > 0 && meno[0] && !obsahuje(meno, ".bmp") &&
                   !obsahuje(meno, ".flc") && lstrcmpA(meno, "animation") && lstrcmpA(meno, "mouse pic") &&
                   lstrcmpA(meno, "BWWorkArea") && lstrcmpA(meno, MENO_ZNACKY)) {
            /* hlavná postava: pomenovaná animácia bez vlastníckeho objektu (napr. 108f.1090) */
            x = I32(a, 0x1c) - I32(s, 0x5d5); y = I32(a, 0x20) - I32(s, 0x5d9); w = I32(a, 0x10); h = I32(a, 0x14);
            if (w > 400 || h > 500) w = 0;
        }
        {
            if (w > 0 && h > 0 && w <= 800 && h <= 600 && x < 800 && y < 600 && x + w > 0 && y + h > 0) {
                RECT r = {x - 2, y - 2, x + w + 2, y + h + 2};
                if (r.top < 45) r.top = 45;                 /* texty hore a dole sa nevyhladzujú */
                if (r.bottom > 544) r.bottom = 544;
                if (r.top < r.bottom) oblasti[pocet_oblasti++] = r;
            }
        }
        a = *(unsigned char **)a;
        if (a == prvy) break;
    }
    return pocet_oblasti;
}
static void fxaa_pas(int y0, int y1)
{
    if (y0 < 1) y0 = 1;
    if (y1 > 599) y1 = 599;
    static const int kroky_i[] = {1, 1, 1, 2, 2, 4, 8};
    #define KROKOV 7
    const float sub = cfg_fxaa_sila / 100.0f;
    int hran = 0;
    for (int r = 0; r < pocet_oblasti; r++) {           /* len vo vybraných obdĺžnikoch (postavy / plocha scény) */
    int ry0 = oblasti[r].top > y0 ? oblasti[r].top : y0, ry1 = oblasti[r].bottom < y1 ? oblasti[r].bottom : y1;
    int rx0 = oblasti[r].left > 1 ? oblasti[r].left : 1, rx1 = oblasti[r].right < 799 ? oblasti[r].right : 799;
    for (int y = ry0; y < ry1; y++) {
        unsigned *riadok = vystup[y];
        const unsigned char *jh = jas[y - 1], *js = jas[y], *jd = jas[y + 1];
        for (int x = rx0; x < rx1; x++) {
            /* rýchle vylúčenie pixelov bez hrany v celých číslach (prah: max(SmoothingThresholdMin, SmoothingThreshold % maxima)) */
            int iM = js[x], iN = jh[x], iS = jd[x], iW = js[x - 1], iE = js[x + 1];
            int imx = iM, imn = iM;
            if (iN > imx) imx = iN; if (iN < imn) imn = iN;
            if (iS > imx) imx = iS; if (iS < imn) imn = iS;
            if (iW > imx) imx = iW; if (iW < imn) imn = iW;
            if (iE > imx) imx = iE; if (iE < imn) imn = iE;
            int prah = imx * cfg_fxaa_prah / 100; if (prah < cfg_fxaa_min) prah = cfg_fxaa_min;
            if (imx - imn < prah) continue;
            hran++;
            int rozsah = imx - imn;
            const unsigned char *j = &jas[y][x];
            int iNW = j[-801], iNE = j[-799], iSW = j[799], iSE = j[801];
            /* subpixelové vyhladenie: f = (smoothstep(|priemer - M| / rozsah))^2 * sila */
            int dif = (2 * (iN + iS + iW + iE) + iNW + iNE + iSW + iSE) - 12 * iM; if (dif < 0) dif = -dif;
            float f = (float)dif / (12 * rozsah); if (f > 1) f = 1;
            f = f * f * (3 - 2 * f); f = f * f * sub;
            /* smer hrany */
            int horiz = abs_i(iNW - 2 * iW + iSW) + 2 * abs_i(iN - 2 * iM + iS) + abs_i(iNE - 2 * iE + iSE);
            int vert  = abs_i(iNW - 2 * iN + iNE) + 2 * abs_i(iW - 2 * iM + iE) + abs_i(iSW - 2 * iS + iSE);
            int vodorovna = horiz >= vert;
            int l1 = vodorovna ? iN : iW, l2 = vodorovna ? iS : iE;
            int g1 = abs_i(l1 - iM), g2 = abs_i(l2 - iM), krok, lokal2, grad;     /* lokal2 = 2 × priemer cez hranu */
            if (g1 >= g2) { krok = -1; lokal2 = l1 + iM; grad = g1; } else { krok = 1; lokal2 = l2 + iM; grad = g2; }
            grad = grad >> 1;                    /* prah konca hrany: 1/4 gradientu, v jednotkách 2 × jas */
            if (grad < 1) grad = 1;
            /* hľadanie koncov hrany pozdĺž nej: súčet jasu dvojice pixelov cez hranu sa líši od lokal2 */
            int pozdlz = vodorovna ? 1 : 800, cez = vodorovna ? krok * 800 : krok;
            int poz = vodorovna ? x : y, lim = vodorovna ? 800 : 600;
            int d1 = 0, d2 = 0, k1 = 0, k2 = 0, hot1 = 0, hot2 = 0;
            for (int i = 0; i < KROKOV && !(hot1 && hot2); i++) {
                if (!hot1) {
                    d1 += kroky_i[i];
                    if (poz - d1 < 0) { d1 = poz; hot1 = 1; }
                    else { const unsigned char *q = j - d1 * pozdlz; k1 = q[0] + q[cez] - lokal2; hot1 = abs_i(k1) >= grad; }
                }
                if (!hot2) {
                    d2 += kroky_i[i];
                    if (poz + d2 >= lim) { d2 = lim - 1 - poz; hot2 = 1; }
                    else { const unsigned char *q = j + d2 * pozdlz; k2 = q[0] + q[cez] - lokal2; hot2 = abs_i(k2) >= grad; }
                }
            }
            int dlzka = d1 + d2, bliz = d1 < d2 ? d1 : d2;
            int stred_mensi = 2 * iM < lokal2;
            int spravny = ((d1 < d2 ? k1 : k2) < 0) != stred_mensi;
            float okraj = (spravny && dlzka) ? 0.5f - (float)bliz / dlzka : 0;
            float b = okraj > f ? okraj : f;
            if (b <= 0.01f) continue;
            /* zmiešanie s pixelom cez hranu v pomere b */
            unsigned c = snimka[y][x], d = vodorovna ? snimka[y + krok][x] : snimka[y][x + krok];
            int w = (int)(b * 256);
            unsigned r = ((((c >> 16) & 255) * (256 - w) + ((d >> 16) & 255) * w) >> 8);
            unsigned g = ((((c >> 8) & 255) * (256 - w) + ((d >> 8) & 255) * w) >> 8);
            unsigned bl = (((c & 255) * (256 - w) + (d & 255) * w) >> 8);
            riadok[x] = (c & 0xFF000000) | (r << 16) | (g << 8) | bl;
            zmeneny[y] = 1;
        }
    }
    }
    InterlockedExchangeAdd(&pocet_hran, hran);
}

/* Pracovné vlákna: snímka sa delí na pásy riadkov, fáza 0 = jas, fáza 1 = FXAA (potrebuje hotový jas okolia). */
#define MAX_VLAKIEN 8
static int pocet_vlakien;
static HANDLE vlakno_start[MAX_VLAKIEN], vlakno_hotovo[MAX_VLAKIEN];
static volatile int faza;

static DWORD WINAPI pracovne_vlakno(LPVOID p)
{
    int i = (int)p;
    for (;;) {
        WaitForSingleObject(vlakno_start[i], INFINITE);
        int y0 = 600 * i / pocet_vlakien, y1 = 600 * (i + 1) / pocet_vlakien;
        if (faza == 0) fxaa_jas(y0, y1); else fxaa_pas(y0, y1);
        SetEvent(vlakno_hotovo[i]);
    }
    return 0;
}

static void spusti_fazu(int f)
{
    faza = f;
    for (int i = 1; i < pocet_vlakien; i++) SetEvent(vlakno_start[i]);
    int y1 = 600 / pocet_vlakien;
    if (f == 0) fxaa_jas(0, y1); else fxaa_pas(0, y1);       /* prvý pás robí herné vlákno */
    if (pocet_vlakien > 1) WaitForMultipleObjects(pocet_vlakien - 1, vlakno_hotovo + 1, TRUE, INFINITE);
}

static void fxaa(unsigned char *pix, int pitch)
{
    if (!pocet_vlakien) {
        SYSTEM_INFO si; GetSystemInfo(&si);
        int n = si.dwNumberOfProcessors > 1 ? (int)si.dwNumberOfProcessors - 1 : 1;    /* jedno jadro nechať hre */
        if (n > MAX_VLAKIEN) n = MAX_VLAKIEN;
        if (n > 4) n = 4;
        pocet_vlakien = 1;
        for (int i = 1; i < n; i++) {
            vlakno_start[i] = CreateEventA(0, FALSE, FALSE, 0); vlakno_hotovo[i] = CreateEventA(0, FALSE, FALSE, 0);
            HANDLE h = CreateThread(0, 0, pracovne_vlakno, (LPVOID)i, 0, 0);
            if (!h) break;
            CloseHandle(h); pocet_vlakien = i + 1;
        }
    }
    pocet_hran = 0;
    spusti_fazu(0);
    spusti_fazu(1);
    /* do povrchu (môže byť nekešovaná pamäť) sa zapíšu len zmenené riadky, celé naraz */
    for (int y = 0; y < 600; y++) if (zmeneny[y]) memcpy(pix + y * pitch, vystup[y], 800 * 4);
    ladenie.udalosti[6] = pocet_hran;
    ladenie.udalosti[10] = pocet_vlakien;
    ladenie.udalosti[12] = pocet_oblasti;
    if (pocet_oblasti) { ladenie.udalosti[13] = oblasti[0].left; ladenie.udalosti[14] = oblasti[0].top;
                         ladenie.udalosti[15] = oblasti[0].right; ladenie.udalosti[16] = oblasti[0].bottom; }
}

static int vyhlad_snimku(void)
{
    DDSD2 d;
    if (!cfg_vyhladenie || FILM_BEZI || !herna_scena() || !zbieraj_oblasti() || !zamkni(&d)) return 0;
    LARGE_INTEGER t[4]; QueryPerformanceCounter(&t[0]);
    int pitch = *(int *)(d.b + 0x10);
    unsigned char *pix = *(unsigned char **)(d.b + 0x24);
    if (*(unsigned *)(d.b + 8) < 600 || *(unsigned *)(d.b + 0xc) < 800) { odomkni(); return 0; }
    for (int y = 0; y < 600; y++) memcpy(snimka[y], pix + y * pitch, 800 * 4);
    memcpy(vystup, snimka, sizeof vystup); memset(zmeneny, 0, sizeof zmeneny);
    QueryPerformanceCounter(&t[1]);
    fxaa(pix, pitch);
    QueryPerformanceCounter(&t[2]);
    odomkni();
    QueryPerformanceCounter(&t[3]);
    ladenie.udalosti[7] = (int)(t[1].QuadPart - t[0].QuadPart);    /* kópia */
    ladenie.udalosti[8] = (int)(t[2].QuadPart - t[1].QuadPart);    /* FXAA */
    ladenie.udalosti[9] = (int)(t[3].QuadPart - t[2].QuadPart);    /* odomknutie */
    return 1;
}

static void obnov_snimku(void)
{
    DDSD2 d;
    if (!zamkni(&d)) return;
    int pitch = *(int *)(d.b + 0x10);
    unsigned char *pix = *(unsigned char **)(d.b + 0x24);
    for (int y = 0; y < 600; y++) kopiruj(pix + y * pitch, snimka[y], 800 * 4);
    odomkni();
}

static void __cdecl zobraz(void)
{
    ladenie.udalosti[3]++;
    if (preskakuje) {                                   /* pretáčanie: na obrazovku len jedna snímka za 100 ms */
        static DWORD posledna;
        DWORD t = GetTickCount();
        if (t - posledna < 100) { ladenie.udalosti[11]++; return; }
        posledna = t;
    }
    if (chodza_rezim == 2) return;                      /* pretáčanie chôdze po dvojkliku: nič na obrazovku */
    if (cez_ponuku) return;                             /* rýchle načítanie čaká na zastavenie: bez snímok */
    priehladne_nazvy();                                 /* editovaný názov hra vytvára každý krok nanovo */
    if (hw_kurzor_hra() && SCENA && *(int *)0x584ff8) ((void (__cdecl *)(unsigned char *))0x426c43)(SCENA);  /* bez kurzora hry */
    LARGE_INTEGER t0, t1; QueryPerformanceCounter(&t0);
    int vyhladene = vyhlad_snimku();
    QueryPerformanceCounter(&t1); ladenie.udalosti[5] = (int)(t1.QuadPart - t0.QuadPart);
    zobraz_povodne();
    if (vyhladene) obnov_snimku();
}

/* Akcia „use“ na objekte (ľavý klik): 0x4311f7(objekt, x, y) – na prieskum. */
static int (__cdecl *pouzi_povodne)(unsigned char *, int, int);
static int __cdecl pouzi(unsigned char *o, int x, int y)
{
    loguj("use %s %d,%d vybrany %s", o ? (char *)o + 8 : "-", x, y, VYBRANY_PREDMET ? (char *)VYBRANY_PREDMET + 8 : "-");
    return pouzi_povodne(o, x, y);
}

/* Predmet na kurzor: 0x408d5a(scena, objekt, rezim) – na prieskum. */
static void (__cdecl *predmet_povodne)(void *, unsigned char *, int);
static void __cdecl predmet_na_kurzor(void *s, unsigned char *o, int rezim)
{
    loguj("predmet na kurzor %s rezim %d", o ? (char *)o + 8 : "-", rezim);
    predmet_povodne(s, o, rezim);
}

/* Replika postavy (reč + titulok): 0x438d58 – volajú ju skriptové príkazy. */
static int (__cdecl *replika_povodne)(int, int, int, int, int, int, int, int);
static int __cdecl replika(int a, int b, int c, int d, int e, int f, int g, int h)
{
    pocet_replik++;
    loguj("replika %x %x %x %x %x %x scena %s", a, b, c, d, e, f, SCENA ? (char *)SCENA : "-");
    return replika_povodne(a, b, c, d, e, f, g, h);
}

/* Štart zvuku: 0x445b66(typ?, vzorka) – na prieskum. */
static int (__cdecl *zvuk_povodne)(int, unsigned char *, int, int, int, int);
static int __cdecl zvuk_start(int t, unsigned char *v, int c, int d, int e, int f)
{
    int r = zvuk_povodne(t, v, c, d, e, f);
    char *meno = v ? *(char **)(v + 0x28) : 0;
    loguj("zvuk %d %s prio %d -> kanal %d", t, meno && !IsBadStringPtrA(meno, 64) ? meno : "?", v ? *(int *)(v + 0x18) : 0, r);
    return r;
}

/* Skript zapisuje celočíselnú systémovú premennú: 0x43a112(meno, hodnota), volá sa len z 0x42b8af. */
static void __cdecl nastav_premennu(const char *meno, int hodnota)
{
    loguj("sysvar %s = %d (scena %s)", meno, hodnota, SCENA ? (char *)SCENA : "-");
    for (int i = 0; cfg_nastavenia && i < POCET_NASTAVENI; i++) {
        if (lstrcmpA(meno, NASTAVENIA[i].meno)) continue;
        if (obrazovka_nastaveni()) { zapamataj(i, hodnota); break; }      /* zmena hráčom v Nastaveniach */
        /* titulky skripty inak nemenia; hlasitosti a gamu nastavuje štartovací skript „main“ – neskoršie zmeny
         * počas hry (napr. zámerné stíšenie) sa nechajú tak */
        int start = !SCENA || !lstrcmpA((char *)SCENA, "main");
        if (ma_zapamatane[i] && (i == 0 || start)) { loguj("  zablokovane (zapamatane %d)", zapamatane[i]); return; }
        break;
    }
    ((void (__cdecl *)(const char *, int))0x43a112)(meno, hodnota);
}

static void instaluj(void)
{
    /* overenie verzie hry: bajty na začiatku kroku logiky */
    static const unsigned char krok[] = {0x55, 0x8b, 0xec, 0x83, 0xec, 0x48};
    if (!rovnake((void *)0x402dfb, krok, 6)) { loguj("ina verzia agds.exe"); return; }

    hak_volanie(0x402e21, 0x431cf8, hra_krok);
    hak_volanie(0x440e9d, 0x43f278, klaves_dole);
    hak_volanie_iat(0x44112b, 0x485274, okno_ine);
    hak_volanie(0x42e416, 0x433708, nacitaj_hru);
    hak_volanie(0x43a228, 0x433708, nacitaj_hru);
    hak_volanie(0x42b8af, 0x43a112, nastav_premennu);
    {
        char t[16]; GetPrivateProfileStringA("Cursor", "Mode", "hardware", t, sizeof t, cesta_ini);
        cfg_hw = (t[0] | 0x20) == 'h';
        GetPrivateProfileStringA("Cursor", "Sensitivity", cfg_hw ? "0.5" : "0.7", t, sizeof t, cesta_ini);   /* hardvérový kurzor: 0.5 */
        int c = 0, d = 1000, des = 0, cisla = 0;            /* „0.7“ -> 700 (tisíciny) */
        for (char *q = t; *q; q++) {
            if (*q >= '0' && *q <= '9') { cisla = 1; if (!des) c = c * 10 + (*q - '0'); else { d /= 10; c += (*q - '0') * d; } }
            else if ((*q == '.' || *q == ',') && !des) { c *= 1000; des = 1; }
            else break;
        }
        if (!des) c *= 1000;
        cfg_citl = !cisla ? (cfg_hw ? 500 : 700) : c < 100 ? 100 : c > 1000 ? 1000 : c;
        if (cfg_hw && cfg_citl < 1000) { void *f = (void *)hw_setcursorpos; zapis((void *)0x485280, &f, 4); }
        loguj("kurzor: hardware %d citlivost %d", cfg_hw, cfg_citl);
    }
    cfg_rychle = ini_cislo("Controls", "QuickSaveKeys", 1);
    cfg_rychla_pozicia = ini_cislo("Controls", "QuickSaveSlot", 98);
    if (cfg_rychla_pozicia < 1 || cfg_rychla_pozicia > 98) cfg_rychla_pozicia = 98;
    zisti_jazyk();
    cfg_nazvy = ini_cislo("Video", "SaveNamesTransparent", 1);
    cfg_dvojklik = ini_cislo("Controls", "DoubleClickWalk", 1);
    if (cfg_dvojklik) hak_volanie(0x4410c5, 0x417949, dvojklik_mysi);     /* udalosť dvojkliku (0x50705c) */
    static const unsigned char zac_zobraz[] = {0x55, 0x8b, 0xec, 0x81, 0xec, 0xa8, 0x00, 0x00, 0x00};
    zobraz_povodne = hak_zaciatok(0x43e78f, zac_zobraz, 9, zobraz);
    static const unsigned char zac_replika[] = {0x55, 0x8b, 0xec, 0x81, 0xec, 0x90, 0x00, 0x00, 0x00};
    replika_povodne = hak_zaciatok(0x438d58, zac_replika, 9, replika);
    if (ini_cislo("Controls", "SpaceHotspots", 1)) {
        static const unsigned char zac_kurzor[] = {0x55, 0x8b, 0xec, 0x83, 0x7d, 0x0c, 0x00};
        kurzor_objektu_povodne = hak_zaciatok(0x408c5c, zac_kurzor, 7, kurzor_objektu);
    }
    if (ini_cislo("Debug", "Explore", 0)) {
        static const unsigned char zac_pouzi[] = {0x55, 0x8b, 0xec, 0x83, 0xec, 0x10};
        pouzi_povodne = hak_zaciatok(0x4311f7, zac_pouzi, 6, pouzi);
        static const unsigned char zac_predmet[] = {0x55, 0x8b, 0xec, 0x51, 0x83, 0x7d, 0x0c, 0x00};
        predmet_povodne = hak_zaciatok(0x408d5a, zac_predmet, 8, predmet_na_kurzor);
        static const unsigned char zac_zvuk[] = {0x55, 0x8b, 0xec, 0x83, 0xec, 0x0c};
        zvuk_povodne = hak_zaciatok(0x445b66, zac_zvuk, 6, zvuk_start);
    }
    cfg_esc_ponuka = ini_cislo("Controls", "EscapeMenu", 1);
    cfg_hotspoty = ini_cislo("Controls", "SpaceHotspots", 1);
    cfg_preskakovanie = ini_cislo("Controls", "HoldToSkip", 1);
    cfg_koliesko = ini_cislo("Controls", "WheelInventory", 1);
    cfg_skratky = ini_cislo("Controls", "SaveLoadKeys", 1);
    cfg_nastavenia = ini_cislo("Settings", "Remember", 1);
    cfg_vyhladenie = ini_cislo("Video", "Smoothing", 1);
    cfg_fxaa_sila = ini_cislo("Video", "SmoothingSubpixel", 75);
    cfg_fxaa_prah = ini_cislo("Video", "SmoothingThreshold", 25);       /* % maxima jasu okolia */
    cfg_fxaa_min = ini_cislo("Video", "SmoothingThresholdMin", 16);     /* najmenší rozdiel jasu 0–255 */
    nacitaj_zapamatane();
    LARGE_INTEGER f; QueryPerformanceFrequency(&f);
    if (!f.HighPart) krok_qpc = f.LowPart / 25;
    loguj("haky vlozene");
}

BOOL WINAPI DllMain(HINSTANCE modul, DWORD dovod, LPVOID r)
{
    if (dovod != DLL_PROCESS_ATTACH) return TRUE;
    int n = GetModuleFileNameA(modul, cesta_ini, MAX_PATH);
    while (n > 0 && cesta_ini[n - 1] != '\\') n--;
    kopiruj(cesta_log, cesta_ini, n);
    kopiruj(cesta_ini + n, "config.ini", 11);
    kopiruj(cesta_log + n, "bm_qol.log", 11);
    log_zapnuty = ini_cislo("Debug", "Log", 0);
    loguj("--- start");
    instaluj();
    return TRUE;
}
