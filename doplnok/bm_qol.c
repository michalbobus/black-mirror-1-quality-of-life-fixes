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

/* ---------- preskakovanie (ESC / medzerník, keď hráč nemá kontrolu) ---------- */
/* Stlačenie: hra natívne preskočí práve hovorenú repliku; doplnok potom „pretáča“ – logika nečaká na tik,
 * snímky sa (okrem jednej za 100 ms) neposielajú na obrazovku a jednorazové zvuky (nie slučky, nie reč) sa zastavia,
 * aby skript nečakal na ich dohranie (napr. hudba pod rozprávačom) – až kým nezačne ďalšia replika alebo hráč
 * nedostane kontrolu. Držanie: pokračuje cez ďalšie repliky. */
static unsigned tik_qpc;            /* QPC tiky jedného tiku logiky (1/25 s) */
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

static void preskakovanie_tik(void)
{
    int drzane = cfg_preskakovanie && (drzi(VK_ESCAPE) || drzi(VK_SPACE));
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
    if (tik_qpc) *(LONGLONG *)0x49bda0 -= tik_qpc;          /* logika nečaká na ďalší tik */
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

/* ---------- F5 = uložiť hru, F9 = nahrať hru (otvorí ponuku a vyberie položku) ---------- */
/* Stav: 1/2 = čaká sa na hlavnú ponuku (1006.100e) po kliku na kolieska, 3 = obrazovka otvorená skratkou,
 * 4 = ESC na nej (hra sa vráti do hlavnej ponuky) – ďalší ESC z hlavnej ponuky vráti rovno do hry. */
static int cfg_skratky, skratka_ziadost, skratka_stav, skratka_polozka;
static DWORD skratka_cas;

static void skratky_tik(void)
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
    skratky_tik();
    return ((fn0)0x431cf8)();
}

static void __cdecl klaves_dole(WPARAM w, LPARAM l)
{
    int opakovanie = (l >> 30) & 1;
    ladenie.udalosti[1] = (int)w;
    loguj("klaves %x opak %d scena %s pouz %d", (int)w, opakovanie, SCENA ? (char *)SCENA : "-", POUZIVATEL_POVOLENY());
    if (w == VK_ESCAPE && cfg_esc_ponuka && hra_v_scene()) { if (!opakovanie) esc_ziadost = 1; return; }
    if (w == VK_SPACE && cfg_hotspoty && hra_v_scene()) return;      /* hotspoty sa zbierajú v tiku */
    if ((w == VK_ESCAPE || w == VK_SPACE) && !opakovanie && bez_kontroly()) spusti_preskok();   /* + pôvodné preskočenie */
    if ((w == VK_F5 || w == VK_F9) && cfg_skratky && !opakovanie) { skratka_ziadost = w == VK_F5 ? 1 : 2; return; }
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
/* [Video] Smoothing: 0 = vypnuté, 1 = FXAA. Snímka sa skopíruje (zdroj filtra aj záloha), výsledok sa zapíše do
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
static void fxaa_pas(int y0, int y1)
{
    if (y0 < 1) y0 = 1;
    if (y1 > 599) y1 = 599;
    static const int kroky_i[] = {1, 1, 1, 2, 2, 4, 8};
    #define KROKOV 7
    const float sub = cfg_fxaa_sila / 100.0f;
    int hran = 0;
    for (int y = y0; y < y1; y++) {
        unsigned *riadok = vystup[y];
        const unsigned char *jh = jas[y - 1], *js = jas[y], *jd = jas[y + 1];
        for (int x = 1; x < 799; x++) {
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
}

static int vyhlad_snimku(void)
{
    DDSD2 d;
    if (!cfg_vyhladenie || FILM_BEZI || !SCENA || !zamkni(&d)) return 0;
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
    LARGE_INTEGER t0, t1; QueryPerformanceCounter(&t0);
    int vyhladene = vyhlad_snimku();
    QueryPerformanceCounter(&t1); ladenie.udalosti[5] = (int)(t1.QuadPart - t0.QuadPart);
    int n = pocet_hotspotov;
    if (n) kresli_znacky(0);
    zobraz_povodne();
    if (vyhladene) obnov_snimku();            /* vráti aj pixely pod značkami */
    else if (n) kresli_znacky(1);
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
    static const unsigned char zac_replika[] = {0x55, 0x8b, 0xec, 0x81, 0xec, 0x90, 0x00, 0x00, 0x00};
    replika_povodne = hak_zaciatok(0x438d58, zac_replika, 9, replika);
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
