"""Skladanie dielov traileru zo záznamov (ffmpeg). Každá funkcia vracia Klip = súbor mp4 1920×1080, 60 snímok/s, AAC 48 kHz.

Časy: v záznamoch sú udalosti v sekundách perf_counter. Zaznam.v(T) prepočíta čas udalosti na čas vo videu
(podľa záblesku v rohu), Zaznam.a(T) na čas vo zvuku (zvuk začína zábleskom).
Rozloženia: vedla() = pôvodná hra a hra s úpravami vedľa seba, samostatne() = jeden záznam so štítkom, karta() = text."""
import os, json, subprocess, hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
KOREN = os.path.dirname(os.path.abspath(__file__))
ZAZNAMY = os.path.join(KOREN, "zaznamy")
VYSTUP = os.path.join(KOREN, "vystup"); TMP = os.path.join(VYSTUP, "tmp")
os.makedirs(TMP, exist_ok=True)
W, H, FPS = 1920, 1080, 60
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-r", str(FPS),
       "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart"]

# vzhľad
POZADIE = (11, 10, 12); CERVENA = (196, 30, 36); BIELA = (238, 232, 224); SIVA = (150, 144, 138)
PISMO_NADPIS = r"C:\Windows\Fonts\georgiab.ttf"; PISMO = r"C:\Windows\Fonts\segoeui.ttf"
PISMO_B = r"C:\Windows\Fonts\segoeuib.ttf"
STITOK_PRED = ("PÔVODNÁ HRA", "ORIGINAL GAME"); STITOK_PO = ("S ÚPRAVAMI", "WITH FIXES")

def ff(*args):
    """ffmpeg; výstup (posledný argument) sa zapíše najprv do .part, aby po chybe neostal rozbitý súbor vo vyrovnávacej pamäti."""
    args = list(map(str, args)); out = args[-1]; docasny = None
    if out.endswith((".mp4", ".png")): docasny = out[:-4] + ".part" + out[-4:]; args[-1] = docasny
    r = subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", *args], capture_output=True, text=True)
    if r.returncode: raise RuntimeError(r.stderr[-3000:])
    if docasny: os.replace(docasny, out)

_VERZIA = hashlib.md5(open(os.path.abspath(__file__), "rb").read()).hexdigest()[:8]   # zmena skladača = nové medzivýsledky
def _meno(*kluc):
    return os.path.join(TMP, hashlib.md5(repr((_VERZIA,) + kluc).encode()).hexdigest()[:12])

class Klip:
    def __init__(self, cesta, dlzka): self.cesta, self.dlzka = cesta, dlzka
    def __repr__(self): return f"Klip({os.path.basename(self.cesta)}, {self.dlzka:.2f} s)"

# ---------------- záznamy ----------------
class Zaznam:
    def __init__(self, meno):
        self.meno = meno; z = os.path.join(ZAZNAMY, meno)
        self.mkv, self.wav, self.jsn = z + ".mkv", z + ".wav", z + ".json"
        self.d = json.load(open(self.jsn))
        if "v_zablesk" not in self.d or self.d.get("v_mtime") != os.path.getmtime(self.mkv):
            self.d["v_zablesk"] = self._najdi_zablesk(); self.d["v_mtime"] = os.path.getmtime(self.mkv)
            json.dump(self.d, open(self.jsn, "w"), indent=1)
        self.t0 = self.d["t_zablesk"]; self.v0 = self.d["v_zablesk"]
    def _najdi_zablesk(self):
        r = subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-t", "8", "-i", self.mkv, "-vf",
                            "crop=80:80:20:20,scale=1:1,format=gray", "-f", "rawvideo", "-"], capture_output=True)
        a = np.frombuffer(r.stdout, np.uint8)
        i = int(np.argmax(a > 200))
        if a[i] <= 200: raise RuntimeError(f"{self.meno}: záblesk sa nenašiel")
        return i / FPS
    @property
    def start(self): return self.d["t_start"]
    @property
    def koniec(self): return self.d["t_koniec"]
    def v(self, T): return self.v0 + (T - self.t0)
    def a(self, T): return T - self.t0
    def udalosti(self, meno=None, **kw):
        return [e for e in self.d["udalosti"] if (meno is None or e["meno"] == meno)
                and all(e.get(k) == v for k, v in kw.items())]
    def znacka(self, nazov):
        return [e["t"] for e in self.d["udalosti"] if e["meno"] == "znacka" and e.get("nazov") == nazov][0]

def _atempo(r):
    f = []
    while r > 2: f.append("atempo=2"); r /= 2
    while r < 0.5: f.append("atempo=0.5"); r /= 0.5
    f.append(f"atempo={r:.6f}"); return ",".join(f)

def vyrez(z, od, do, rychlost=1.0, orez=None, zvuk=True, hlasitost=1.0):
    """Úsek záznamu z (časy perf_counter od–do). orez = (x, y, š, v) v px obrazovky → zväčší sa na 1920×1080
    (alebo pomer orezu zachová, ak nie je 16:9: vtedy výstup š×v zväčšený na výšku 1080). rychlost > 1 = zrýchlene."""
    d = (do - od); dv = d / rychlost
    out = _meno("vyrez", z.mkv, os.path.getmtime(z.mkv), od, do, rychlost, orez, zvuk, hlasitost) + ".mp4"
    if not os.path.exists(out):
        vf = []
        if orez:
            x, y, s, v = orez; vf.append(f"crop={s}:{v}:{x}:{y}")
            vf.append(f"scale=-2:{H}:flags=lanczos" if abs(s / v - 16 / 9) > 0.01 else f"scale={W}:{H}:flags=lanczos")
        vf += [f"setpts=(PTS-STARTPTS)/{rychlost}", f"fps={FPS}"]
        args = ["-ss", f"{z.v(od):.4f}", "-t", f"{d:.4f}", "-i", z.mkv]
        if zvuk:
            args += ["-ss", f"{max(0, z.a(od)):.4f}", "-t", f"{d:.4f}", "-i", z.wav]
            af = f"[1:a]{_atempo(rychlost)},volume={hlasitost},apad,atrim=0:{dv:.4f},aresample=48000[a]"
        else:
            args += ["-f", "lavfi", "-t", f"{dv:.4f}", "-i", "anullsrc=r=48000:cl=stereo"]
            af = "[1:a]anull[a]"
        ff(*args, "-filter_complex", f"[0:v]{','.join(vf)},trim=0:{dv:.4f}[v];{af}", "-map", "[v]", "-map", "[a]",
           "-t", f"{dv:.4f}", *ENC, out)
    return Klip(out, dv)

def zastav(k, trvanie):
    """Na konci klipu podrží poslednú snímku (ticho) – napr. na porovnanie výsledku."""
    out = _meno("zastav", k.cesta, trvanie) + ".mp4"
    if not os.path.exists(out):
        ff("-i", k.cesta, "-filter_complex", f"[0:v]tpad=stop_mode=clone:stop_duration={trvanie}[v];[0:a]apad=pad_dur={trvanie}[a]",
           "-map", "[v]", "-map", "[a]", "-t", f"{k.dlzka + trvanie:.4f}", *ENC, out)
    return Klip(out, k.dlzka + trvanie)

def za_sebou(*klipy):
    """Spojí klipy (bez prechodov) – rovnaké parametre, preto stačí kopírovanie."""
    out = _meno("za_sebou", *[k.cesta for k in klipy]) + ".mp4"
    if not os.path.exists(out):
        zoz = out + ".txt"
        open(zoz, "w", encoding="utf-8").write("".join(f"file '{k.cesta.replace(os.sep, '/')}'\n" for k in klipy))
        ff("-f", "concat", "-safe", "0", "-i", zoz, "-c", "copy", out)
    return Klip(out, sum(k.dlzka for k in klipy))

# ---------------- grafika (PNG cez PIL) ----------------
def _pismo(cesta, v): return ImageFont.truetype(cesta, v)

def _text_stred(dr, x, y, text, pismo, farba):
    b = dr.textbbox((0, 0), text, font=pismo); dr.text((x - (b[2] - b[0]) / 2 - b[0], y), text, font=pismo, fill=farba)

def _nadpis(dr, nadpis, y=38):
    """Nadpis dielu: slovensky veľký, anglicky menší pod ním, červená linka."""
    if not nadpis: return
    _text_stred(dr, W / 2, y, nadpis[0], _pismo(PISMO_NADPIS, 54), BIELA)
    _text_stred(dr, W / 2, y + 70, nadpis[1], _pismo(PISMO, 28), SIVA)

def _stitok(dr, x, y, stitok, po):
    """Štítok nad panelom: PÔVODNÁ HRA (sivá) / S ÚPRAVAMI (červená)."""
    p = _pismo(PISMO_B, 26); p2 = _pismo(PISMO, 22)
    t = stitok[0]; b = dr.textbbox((0, 0), t, font=p); s = b[2] - b[0]
    dr.rounded_rectangle((x - s / 2 - 18, y, x + s / 2 + 18, y + 42), 8, fill=CERVENA if po else (70, 66, 64))
    _text_stred(dr, x, y + 4, t, p, BIELA)
    _text_stred(dr, x, y + 48, stitok[1], p2, SIVA)

def odznak_png(text, popis=None):
    """Odznak klávesu (napr. ESC, Medzerník, Ctrl+S) – PNG s priehľadnosťou."""
    p = _pismo(PISMO_B, 34); p2 = _pismo(PISMO, 22)
    b = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), text, font=p); s = b[2] - b[0] + 44
    im = Image.new("RGBA", (max(s, 120) + 8, 92), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    x0 = (im.width - s) / 2
    dr.rounded_rectangle((x0 + 3, 7, x0 + s + 3, 63), 10, fill=(0, 0, 0, 160))
    dr.rounded_rectangle((x0, 3, x0 + s, 59), 10, fill=(245, 240, 232, 255), outline=CERVENA, width=3)
    _text_stred(dr, im.width / 2, 6, text, p, (20, 18, 18))
    if popis: _text_stred(dr, im.width / 2, 64, popis, p2, BIELA)
    out = _meno("odznak", text, popis) + ".png"; im.save(out); return out

def _uloz_png(im, *kluc):
    out = _meno("png", *kluc) + ".png"; im.save(out); return out

# ---------------- rozloženia ----------------
PANEL43 = (936, 702); PANEL169 = (928, 522)

def _overlay_odznakov(odznaky, stredy, y_odznak, vstup, n0):
    """odznaky = [(text, od, do, panel, popis?)], panel = index do stredy. Vracia (vstupy, filtre, posledný štítok)."""
    vst, flt, akt = [], [], vstup
    for i, o in enumerate(odznaky):
        text, od, do, panel = o[:4]; popis = o[4] if len(o) > 4 else None
        png = odznak_png(text, popis); w = Image.open(png).width
        vst += ["-i", png]; nove = f"o{i}"
        flt.append(f"[{akt}][{n0 + i}:v]overlay={stredy[panel] - w / 2:.0f}:{y_odznak}:enable='between(t,{od:.3f},{do:.3f})'[{nove}]")
        akt = nove
    return vst, flt, akt

def _casovace(casovace, stredy, y, akt):
    """casovace = [(panel, t_od, t_stop, rychlost, zaklad=0)] – čas mm:ss od t_od (v čase klipu) + zaklad, zastaví sa v t_stop."""
    flt = []
    for i, c in enumerate(casovace):
        panel, od, stop, r = c[:4]; zaklad = c[4] if len(c) > 4 else 0
        e = f"(max(0\\,min(t\\,{stop:.3f})-{od:.3f})*{r}+{zaklad:.3f})"
        txt = f"%{{eif\\:floor({e}/60)\\:d}}\\:%{{eif\\:mod(floor({e})\\,60)\\:d\\:2}}"
        nove = f"c{i}"
        flt.append(f"[{akt}]drawtext=fontfile='C\\:/Windows/Fonts/segoeuib.ttf':text='{txt}':fontsize=40:"
                   f"fontcolor=0xEEE8E0:x={stredy[panel]}-tw/2:y={y}:box=1:boxcolor=0x000000@0.55:boxborderw=12[{nove}]")
        akt = nove
    return flt, akt

def vedla(lavy, pravy, nadpis, orez43=True, zvuk="p", odznaky=(), casovace=(), stitky=(STITOK_PRED, STITOK_PO), popis=None):
    """Dva klipy vedľa seba (vľavo pôvodná hra, vpravo s úpravami). orez43 = len obraz hry 4:3 (bez čiernych pásov).
    zvuk: 'l', 'p' alebo 'mix'. Kratší klip na konci podrží poslednú snímku."""
    D = max(lavy.dlzka, pravy.dlzka)
    pw, ph = PANEL43 if orez43 else PANEL169
    y = 250 if orez43 else 300; xl, xp = (W // 2 - pw) // 2 + 4, W // 2 + (W // 2 - pw) // 2 - 4
    stredy = [xl + pw // 2, xp + pw // 2]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    _nadpis(dr, nadpis); _stitok(dr, stredy[0], y - 100 + 6, stitky[0], False); _stitok(dr, stredy[1], y - 100 + 6, stitky[1], True)
    if popis: _text_stred(dr, W / 2, H - 52, popis, _pismo(PISMO, 26), SIVA)
    png = _uloz_png(im, "vedla", nadpis, stitky, orez43, popis)
    out = _meno("vedla", lavy.cesta, pravy.cesta, nadpis, orez43, zvuk, odznaky, casovace, stitky, popis) + ".mp4"
    if not os.path.exists(out):
        orez = "crop='min(iw,ih*4/3)':ih:'(iw-min(iw,ih*4/3))/2':0," if orez43 else ""
        orez += f"scale={pw}:{ph}:force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos,pad={pw}:{ph}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f = [f"color=c=0x{POZADIE[0]:02x}{POZADIE[1]:02x}{POZADIE[2]:02x}:s={W}x{H}:r={FPS}:d={D:.4f}[bg]",
             f"[0:v]{orez}tpad=stop_mode=clone:stop_duration={D - lavy.dlzka + 0.1:.4f}[l]",
             f"[1:v]{orez}tpad=stop_mode=clone:stop_duration={D - pravy.dlzka + 0.1:.4f}[r]",
             f"[bg][l]overlay={xl}:{y}[t1]", f"[t1][r]overlay={xp}:{y}[t2]", "[t2][2:v]overlay=0:0[t3]"]
        vst, fo, akt = _overlay_odznakov(odznaky, stredy, y + ph - 104, "t3", 3)
        fc, akt = _casovace(casovace, stredy, y + 14, akt)
        a = {"l": "[0:a]apad[a]", "p": "[1:a]apad[a]", "mix": "[0:a][1:a]amix=inputs=2:duration=longest:normalize=0,apad[a]"}[zvuk]
        sk = os.path.join(TMP, os.path.basename(out) + ".filter")
        open(sk, "w", encoding="utf-8").write(";\n".join(f + fo + fc + [f"[{akt}]null[v]", a]))
        ff("-i", lavy.cesta, "-i", pravy.cesta, "-i", png, *vst, "-/filter_complex", sk,
           "-map", "[v]", "-map", "[a]", "-t", f"{D:.4f}", *ENC, out)
    return Klip(out, D)

def samostatne(k, nadpis, stitok=STITOK_PO, orez43=True, odznaky=(), casovace=(), popis=None, po=True):
    """Jeden klip v strede pod nadpisom so štítkom (PÔVODNÁ HRA / S ÚPRAVAMI)."""
    ph = 798; pw = 1064 if orez43 else 1418
    x, y = (W - pw) // 2, 205; stredy = [W // 2]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    _nadpis(dr, nadpis, 20)
    if stitok:   # štítok vľavo od panela, zvisle na stred
        _stitok(dr, (x) // 2, y + 20, stitok, po)
    if popis: _text_stred(dr, W / 2, H - 52, popis, _pismo(PISMO, 26), SIVA)
    png = _uloz_png(im, "samostatne", nadpis, stitok, orez43, popis, po)
    out = _meno("samostatne", k.cesta, nadpis, stitok, orez43, odznaky, casovace, popis, po) + ".mp4"
    if not os.path.exists(out):
        orez = "crop='min(iw,ih*4/3)':ih:'(iw-min(iw,ih*4/3))/2':0," if orez43 else ""
        f = [f"color=c=0x{POZADIE[0]:02x}{POZADIE[1]:02x}{POZADIE[2]:02x}:s={W}x{H}:r={FPS}:d={k.dlzka:.4f}[bg]",
             f"[0:v]{orez}scale={pw}:{ph}:force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos,pad={pw}:{ph}:(ow-iw)/2:(oh-ih)/2:color=black[p]", f"[bg][p]overlay={x}:{y}[t1]", "[t1][1:v]overlay=0:0[t2]"]
        # odznaky vpravo od panela
        st = [x + pw + (W - x - pw) // 2]
        vst, fo, akt = _overlay_odznakov(odznaky, st, y + 20, "t2", 2)
        fc, akt = _casovace(casovace, [x // 2], y + 140, akt)
        sk = os.path.join(TMP, os.path.basename(out) + ".filter")
        open(sk, "w", encoding="utf-8").write(";\n".join(f + fo + fc + [f"[{akt}]null[v]", "[0:a]anull[a]"]))
        ff("-i", k.cesta, "-i", png, *vst, "-/filter_complex", sk, "-map", "[v]", "-map", "[a]",
           "-t", f"{k.dlzka:.4f}", *ENC, out)
    return Klip(out, k.dlzka)

def snimka(z, T, cesta=None):
    """Jedna snímka záznamu v čase T (perf_counter) ako PIL obrázok."""
    out = cesta or _meno("snimka", z.mkv, T) + ".png"
    ff("-ss", f"{z.v(T):.4f}", "-i", z.mkv, "-frames:v", "1", out); return Image.open(out)

def karta(riadky, trvanie, pozadie=None, zvuk=None):
    """Textová karta. riadky = [(text, 'nadpis'|'podnadpis'|'text'|'en'|'medzera')], pozadie = PIL obrázok (rozmaže sa a stmaví)."""
    if pozadie is not None:
        im = pozadie.convert("RGB").resize((W, H)).filter(ImageFilter.GaussianBlur(14))
        im = Image.blend(im, Image.new("RGB", (W, H), POZADIE), 0.72)
    else: im = Image.new("RGB", (W, H), POZADIE)
    dr = ImageDraw.Draw(im)
    styl = {"nadpis": (PISMO_NADPIS, 84, BIELA, 112), "podnadpis": (PISMO_NADPIS, 44, CERVENA, 70),
            "text": (PISMO, 36, BIELA, 52), "en": (PISMO, 28, SIVA, 48), "medzera": (PISMO, 10, BIELA, 26)}
    vyska = sum(styl[s][3] for _, s in riadky); y = (H - vyska) / 2
    for t, s in riadky:
        p, v, farba, krok = styl[s]
        if t: _text_stred(dr, W / 2, y, t, _pismo(p, v), farba)
        y += krok
    png = _uloz_png(im, "karta", riadky, pozadie is not None and pozadie.tobytes()[:2000])
    out = _meno("karta", png, trvanie) + ".mp4"
    if not os.path.exists(out):
        ff("-loop", "1", "-framerate", FPS, "-t", f"{trvanie}", "-i", png, "-f", "lavfi", "-t", f"{trvanie}",
           "-i", "anullsrc=r=48000:cl=stereo", "-vf", "format=yuv420p", "-map", "0:v", "-map", "1:a", *ENC, out)
    return Klip(out, trvanie)

def prelinanie(k, dnu=0.4, von=0.4):
    """Stmievanie na začiatku a na konci (obraz aj zvuk)."""
    out = _meno("prelinanie", k.cesta, dnu, von) + ".mp4"
    if not os.path.exists(out):
        ff("-i", k.cesta, "-vf", f"fade=t=in:st=0:d={dnu},fade=t=out:st={k.dlzka - von:.4f}:d={von}",
           "-af", f"afade=t=in:st=0:d={dnu},afade=t=out:st={k.dlzka - von:.4f}:d={von}", *ENC, out)
    return Klip(out, k.dlzka)
