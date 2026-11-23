/* Black Mirror (agds.exe) – doplnok pohodlia: DDraw.dll, ktorá prepošle všetky exporty na bm_core.dll
 * (doterajší doplnok: filmy na celú šírku, plynulý kurzor, citlivosť) a ten ďalej na dgddraw.dll (dgVoodoo2).
 *
 * Háky (v pamäti agds.exe, exe na disku sa nemení; pred zápisom sa overia pôvodné bajty):
 *   0x402e21  call 0x431cf8   – začiatok tiku logiky (25/s, herné vlákno): hra_tik()
 *   0x440e9d  call 0x43f278   – WM_KEYDOWN v okennej procedúre: klaves_dole()
 *   0x44112b  call [DefWindowProcA] – ostatné správy okna (WM_MOUSEWHEEL): okno_ine()
 *   0x42e416, 0x43a228  call 0x433708 – načítanie uloženej hry: po ňom sa vrátia zapamätané nastavenia
 *   0x43e78f  začiatok funkcie zobrazenia (Blt zadného povrchu na obrazovku): značky hotspotov
 *
 * Preklad: doplnok/zostav.bat (zig cc, bez CRT).
 */
#include <windows.h>
#include <stdarg.h>

/* ---------- adresy v agds.exe ---------- */
#define SCENA          (*(unsigned char **)0x49eb1c)     /* objekt aktuálnej obrazovky: +0 meno, +0x40 zoznam objektov */
#define HWND_HRY       (*(HWND *)0x5850e8)
#define FILM_BEZI      (*(int *)0x58512c)
#define MYS_X          (*(int *)0x506ff0)                /* poloha myši v súradniciach hry (po tiku + posun scény) */
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

/* ---------- konfigurácia a log ---------- */
static char cesta_ini[MAX_PATH], cesta_log[MAX_PATH];
static int log_zapnuty;

static void loguj(const char *fmt, ...)
{
    if (!log_zapnuty) return;
    char b[1024]; va_list a; va_start(a, fmt); int n = wvsprintfA(b, fmt, a); va_end(a);
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

/* ---------- ladiaci kanál: Python zapíše príkaz, doplnok ho vykoná v hernom vlákne pri ďalšom tiku ---------- */
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

static void ladenie_tik(void)
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

/* Po návrate z ponuky kolieska schová (inak by ostali viditeľné), ak ich načítal doplnok a myš nie je hore. */
static void schovaj_kolieska(void)
{
    unsigned char *s = SCENA, *o;
    if (kolieska_nacitane == 1 && s && zacina((char *)s, "1006.")) kolieska_nacitane = 2;
    if (kolieska_nacitane != 2 || !hra_v_scene() || *(int *)0x507014 < 60) return;
    kolieska_nacitane = 0;
    o = NAJDI_OBJEKT(s, "1006.100c");
    if (o) ((int (__cdecl *)(void *, unsigned char *, unsigned char *))0x43040d)(0, o, s);
    loguj("kolieska schovane %x", (unsigned)o);
}

/* ---------- hotspoty (medzerník): značky v strede regiónov objektov, ktoré majú názov ---------- */
#define MAX_HOTSPOTOV 64
static struct { int x, y; } hotspoty[MAX_HOTSPOTOV];
static int pocet_hotspotov;

static void zbieraj_hotspoty(void)
{
    unsigned char *s = SCENA;
    pocet_hotspotov = 0;
    if (!s) return;
    unsigned char *prvy = *(unsigned char **)(s + 0x40 + 0x28), *o = prvy;
    int n = 0;
    while (o && n++ < 1000 && pocet_hotspotov < MAX_HOTSPOTOV) {
        unsigned char *reg = *(unsigned char **)(o + 0x72), *nazov = *(unsigned char **)(o + 0x7a);
        if (I32(o, 0x34) && reg && nazov && nazov[0] && !zacina((char *)o + 8, "inv.") && o != VYBRANY_PREDMET) {
            /* inverzia prepočtu z hit-testu 0x4034b0: región = bod - animácia + obj[0x3a] - obj[0x42] */
            int x = *(short *)reg + I32(o, 0x42), y = *(short *)(reg + 2) + I32(o, 0x46);
            unsigned char *anim = *(unsigned char **)(o + 0x7e), *post = *(unsigned char **)(o + 0x82);
            if (anim) { x += I32(anim, 0x1c) - I32(o, 0x3a); y += I32(anim, 0x20) - I32(o, 0x3e); }
            else if (post) {
                unsigned char *a = *(unsigned char **)(*(unsigned char **)(post + 0x36a) + 0x61);
                x += I32(a, 0x37e) - I32(o, 0x3a); y += I32(a, 0x382) - I32(o, 0x3e);
            }
            x -= I32(s, 0x5d5); y -= I32(s, 0x5d9);
            if (x >= 0 && x < 800 && y >= 0 && y < 600) {
                hotspoty[pocet_hotspotov].x = x; hotspoty[pocet_hotspotov].y = y; pocet_hotspotov++;
            }
        }
        o = *(unsigned char **)o;
        if (o == prvy) break;
    }
}

/* Značka: krúžok (polomer 7, hrúbka 2) svetlej farby s tmavým lemom a bodkou v strede. Kreslí sa do zadného
 * povrchu tesne pred Blt na obrazovku a hneď potom sa pôvodné pixely vrátia (hra prekresľuje len zmeny). */
#define ZN 21                        /* veľkosť štvorca značky */
static unsigned zaloha_pixelov[MAX_HOTSPOTOV][ZN * ZN];

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

static unsigned farba_znacky(int dx, int dy)
{
    int r2 = dx * dx + dy * dy;
    if (r2 <= 2) return 0xFFF4E2B0;                    /* bodka v strede */
    if (r2 >= 30 && r2 <= 56) return 0xFFF4E2B0;       /* krúžok (svetlá zlatá) */
    if ((r2 >= 20 && r2 < 30) || (r2 > 56 && r2 <= 72) || (r2 > 2 && r2 <= 6)) return 0xFF201408;   /* tmavý lem */
    return 0;
}

static void kresli_znacky(int obnov)
{
    DDSD2 d;
    if (!pocet_hotspotov || !zamkni(&d)) return;
    int pitch = *(int *)(d.b + 0x10);
    unsigned char *pix = *(unsigned char **)(d.b + 0x24);
    for (int i = 0; i < pocet_hotspotov; i++) {
        for (int dy = 0; dy < ZN; dy++) {
            int y = hotspoty[i].y + dy - ZN / 2;
            if (y < 0 || y >= 600) continue;
            unsigned *riadok = (unsigned *)(pix + y * pitch);
            for (int dx = 0; dx < ZN; dx++) {
                int x = hotspoty[i].x + dx - ZN / 2;
                if (x < 0 || x >= 800) continue;
                unsigned *z = &zaloha_pixelov[i][dy * ZN + dx];
                if (obnov) { riadok[x] = *z; continue; }
                *z = riadok[x];
                unsigned f = farba_znacky(dx - ZN / 2, dy - ZN / 2);
                if (f) riadok[x] = f;
            }
        }
    }
    odomkni();
}

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

/* ---------- podržanie ESC / medzerníka počas rozhovoru: preskakovanie replík + zrýchlenie hry ---------- */
static unsigned tik_qpc;        /* QPC tiky jedného tiku logiky (1/25 s) */
static int preskakuje;

static void preskakovanie_tik(void)
{
    int drzane = cfg_preskakovanie && (drzi(VK_ESCAPE) || drzi(VK_SPACE));
    preskakuje = drzane && SCENA && !FILM_BEZI && POUZIVATEL_POVOLENY() < 1 && !zacina((char *)SCENA, "1006.");
    if (!preskakuje) return;
    /* ESC = pôvodné preskočenie repliky (WM_KEYDOWN, skenkód 1) */
    ((void (__cdecl *)(WPARAM, LPARAM))0x43f278)(VK_ESCAPE, 0x00010001);
    /* zrýchlenie: posledný tik o 1/25 s skôr -> logika nečaká na ďalší tik (rýchlosť obmedzí zobrazenie/vsync) */
    if (tik_qpc) *(LONGLONG *)0x49bda0 -= tik_qpc;
}

/* ---------- koliesko myši: listovanie predmetmi inventára na kurzore ---------- */
/* Pole inventára 0x578c10: 35 položiek po 0x28 B (meno[32], +0x20 = 1 obsadené). Predmet pripnutý na kurzor sa
 * z poľa vyberie (jeho miesto ostane prázdne) a po vrátení (pravý klik) sa vráti na to isté miesto. */
#define INVENTAR ((unsigned char *)0x578c10)
#define INVENTAR_POVOLENY (*(int *)0x48d2d8 > 0)
static int koliesko_kroky;          /* nahromadené zárezy kolieska (+ dole = ďalší predmet) */
static int koliesko_stav, koliesko_cakanie;
static char koliesko_ciel[32];

static int obsadene(int i) { unsigned char *e = INVENTAR + i * 0x28; return e[0] && *(int *)(e + 0x20) == 1; }

static void vyber_predmet(const char *meno)
{
    unsigned char *s = SCENA, *o = NAJDI_OBJEKT(s, meno);
    if (!o) { ((int (__cdecl *)(const char *, unsigned char *, int, int))0x430052)(meno, s, 1, 1); o = NAJDI_OBJEKT(s, meno); }
    loguj("koliesko: vyber %s (%x)", meno, (unsigned)o);
    if (o) ((int (__cdecl *)(unsigned char *, int, int))0x4311f7)(o, *(int *)0x507010, *(int *)0x507014);
}

static void koliesko_tik(void)
{
    if (koliesko_stav == 1) {                       /* čaká sa na vrátenie predmetu z kurzora */
        if (VYBRANY_PREDMET && --koliesko_cakanie > 0) return;
        koliesko_stav = 0;
        if (!VYBRANY_PREDMET && hra_v_scene()) vyber_predmet(koliesko_ciel);
        return;
    }
    if (!koliesko_kroky) return;
    int smer = koliesko_kroky > 0 ? 1 : -1;
    koliesko_kroky -= smer;
    if (!hra_v_scene() || !INVENTAR_POVOLENY) { koliesko_kroky = 0; return; }
    int drzany = -1;                                /* miesto predmetu na kurzore = prvé prázdne */
    if (VYBRANY_PREDMET) for (int i = 0; i < 35; i++) if (!obsadene(i)) { drzany = i; break; }
    int start = drzany >= 0 ? drzany : (smer > 0 ? -1 : 35), ciel = -1;
    for (int k = 1; k <= 35; k++) {
        int i = start + smer * k;
        if (drzany >= 0) i = (i % 35 + 35) % 35;
        else if (i < 0 || i >= 35) break;
        if (i != drzany && obsadene(i)) { ciel = i; break; }
    }
    if (ciel < 0) return;
    kopiruj(koliesko_ciel, INVENTAR + ciel * 0x28, 31); koliesko_ciel[31] = 0;
    if (VYBRANY_PREDMET) {                          /* najprv vrátiť predmet (ako pravý klik) */
        ((int (__cdecl *)(void *))0x417949)((void *)0x50703c);
        koliesko_stav = 1; koliesko_cakanie = 25;
    } else vyber_predmet(koliesko_ciel);
}

/* ---------- háky ---------- */
static int prvy_tik = 1;
static int __cdecl hra_tik(void)
{
    ladenie.udalosti[0]++;
    ladenie_tik();
    if (prvy_tik) { prvy_tik = 0; obnov_nastavenia("start"); }
    if (esc_ziadost) { esc_ziadost = 0; if (hra_v_scene()) otvor_ponuku(); }
    else schovaj_kolieska();
    if (cfg_hotspoty && drzi(VK_SPACE) && hra_v_scene()) zbieraj_hotspoty();
    else pocet_hotspotov = 0;
    preskakovanie_tik();
    ladenie.udalosti[4] = preskakuje;
    if (cfg_koliesko) koliesko_tik();
    return ((fn0)0x431cf8)();
}

static void __cdecl klaves_dole(WPARAM w, LPARAM l)
{
    int opakovanie = (l >> 30) & 1;
    ladenie.udalosti[1] = (int)w;
    loguj("klaves %x opak %d scena %s pouz %d", (int)w, opakovanie, SCENA ? (char *)SCENA : "-", POUZIVATEL_POVOLENY());
    if (w == VK_ESCAPE && cfg_esc_ponuka && hra_v_scene()) { if (!opakovanie) esc_ziadost = 1; return; }
    if (w == VK_SPACE && cfg_hotspoty && hra_v_scene()) return;      /* hotspoty sa zbierajú v tiku */
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
static void __cdecl zobraz(void)
{
    ladenie.udalosti[3]++;
    int n = pocet_hotspotov;
    if (n) kresli_znacky(0);
    zobraz_povodne();
    if (n) kresli_znacky(1);
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
    /* overenie verzie hry: bajty na začiatku tiku logiky */
    static const unsigned char tik[] = {0x55, 0x8b, 0xec, 0x83, 0xec, 0x48};
    if (!rovnake((void *)0x402dfb, tik, 6)) { loguj("ina verzia agds.exe"); return; }

    hak_volanie(0x402e21, 0x431cf8, hra_tik);
    hak_volanie(0x440e9d, 0x43f278, klaves_dole);
    hak_volanie_iat(0x44112b, 0x485274, okno_ine);
    hak_volanie(0x42e416, 0x433708, nacitaj_hru);
    hak_volanie(0x43a228, 0x433708, nacitaj_hru);
    hak_volanie(0x42b8af, 0x43a112, nastav_premennu);
    static const unsigned char zac_zobraz[] = {0x55, 0x8b, 0xec, 0x81, 0xec, 0xa8, 0x00, 0x00, 0x00};
    zobraz_povodne = hak_zaciatok(0x43e78f, zac_zobraz, 9, zobraz);
    if (ini_cislo("Debug", "Explore", 0)) {
        static const unsigned char zac_pouzi[] = {0x55, 0x8b, 0xec, 0x83, 0xec, 0x10};
        pouzi_povodne = hak_zaciatok(0x4311f7, zac_pouzi, 6, pouzi);
        static const unsigned char zac_predmet[] = {0x55, 0x8b, 0xec, 0x51, 0x83, 0x7d, 0x0c, 0x00};
        predmet_povodne = hak_zaciatok(0x408d5a, zac_predmet, 8, predmet_na_kurzor);
    }
    cfg_esc_ponuka = ini_cislo("Controls", "EscapeMenu", 1);
    cfg_hotspoty = ini_cislo("Controls", "SpaceHotspots", 1);
    cfg_preskakovanie = ini_cislo("Controls", "HoldToSkip", 1);
    cfg_koliesko = ini_cislo("Controls", "WheelInventory", 1);
    cfg_nastavenia = ini_cislo("Settings", "Remember", 1);
    nacitaj_zapamatane();
    LARGE_INTEGER f; QueryPerformanceFrequency(&f);
    if (!f.HighPart) tik_qpc = f.LowPart / 25;
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
