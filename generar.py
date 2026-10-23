"""Bursio · vídeos diarios para TikTok (economía y política).

1. Pide al Apps Script de Bursio los textos del día (ya generados en los
   lotes de la mañana: no gasta API de Claude).
2. Locución con Google Text-to-Speech (voz Chirp 3 HD en castellano),
   con 1 s de pausa entre temas.
3. Monta el vídeo vertical 1080x1920 con la plantilla de Bursio y música
   propia, y deja en salida/: economia.mp4, politica.mp4 y textos.json.

Los guiones y la voz (Google Chirp 3 HD) los prepara el Apps Script cada
mañana (prepararVideosDia) y se piden con ?videos=2: aquí no hace falta
ninguna clave.

Variables de entorno: APPS_URL (URL /exec del Apps Script).
Opcional: DATOS (json local para pruebas).
"""
import os, sys, re, json, math, time, base64, subprocess, datetime, urllib.request, io
import numpy as np, soundfile as sf
from PIL import Image, ImageDraw

import plantilla as P
from plantilla import (W, H, FPS, GOLD, GOLD2, CREAM, MUTED, RED, GREEN, BLUE, clamp, ease, back,
                       text_img, put, appear, chip, background, icon_car, icon_bank, icon_house,
                       icon_eu, arrow, footer, inter)

SR = 44100
LEAD, GAP = 0.3, 1.0
VOZ = os.environ.get("VOZ", "es-ES-Chirp3-HD-Charon")
OUT = "salida"
MESES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]

TEMAS = {
    "economia": {
        "etiqueta": "ECONOMÍA GLOBAL", "acento": GREEN,
        "intro_voz": "Esto es lo que mueve hoy la economía.",
        "intro": ("Lo que mueve hoy", "la economía mundial"),
        "hashtags": "#economia #noticias #finanzas #bolsa #inversion #mercados",
        "texto": "La economía global que importa hoy, en poco más de un minuto.",
    },
    "internacional": {
        "etiqueta": "INTERNACIONAL", "acento": BLUE,
        "intro_voz": "Esto es lo más importante de la política internacional hoy.",
        "intro": ("Lo que importa hoy", "en el mundo"),
        "hashtags": "#noticias #politica #actualidad #internacional #geopolitica",
        "texto": "La política internacional que importa hoy, en poco más de un minuto.",
    },
}
CTA_VOZ = "Esto es Bursio: lo que importa, cada mañana en tu correo. Síguenos para no perderte nada."

# ───────────────────────── datos ─────────────────────────
def hoy_madrid():
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat()
    except Exception:
        return datetime.date.today().isoformat()

def leer_datos():
    if os.environ.get("DATOS"):
        return json.load(open(os.environ["DATOS"], encoding="utf-8"))
    url = os.environ["APPS_URL"] + "?videos=2"
    d = {}
    for intento in range(12):  # el Apps Script los prepara hacia las 6:00
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                d = json.loads(r.read().decode("utf-8"))
            if d.get("listo") and d.get("fecha") == hoy_madrid():
                return d
            print("Aún no están los vídeos de hoy (", d.get("fecha"), "), espero…", flush=True)
        except Exception as e:
            print("Fallo al pedir los textos:", e, flush=True)
        time.sleep(240)
    return d

def limpiar(s):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s.replace("…", ".").replace(" ,", ",")

def frases(texto):
    return [f.strip() for f in re.split(r"(?<=[.!?])\s+", limpiar(texto)) if f.strip()]

def locucion(item, maxpal=34):
    """Una o dos frases del resumen, hasta ~34 palabras."""
    out, n = [], 0
    for f in frases(item.get("resumen") or item.get("titulo")):
        w = len(f.split())
        if out and n + w > maxpal: break
        out.append(f); n += w
        if n >= 22: break
    t = " ".join(out) or limpiar(item.get("titulo"))
    if len(t.split()) > maxpal + 8:
        t = " ".join(t.split()[:maxpal]).rstrip(",;:") + "."
    return t

def primera_frase(item, maxpal=26):
    f = (frases(item.get("resumen")) or [limpiar(item.get("titulo"))])[0]
    p = f.split()
    return f if len(p) <= maxpal else " ".join(p[:maxpal]).rstrip(",;:") + "…"

NUM = re.compile(r"(−|-)?\d[\d.,]*\s?(%|por ciento|millones de euros|millones|mil millones|billones|€|euros|dólares)", re.I)
def cifra(item):
    for txt in (item.get("titulo", ""), item.get("resumen", "")):
        m = NUM.search(txt or "")
        if m:
            s = m.group(0).replace("por ciento", "%").replace("millones de euros", "M€").replace(" millones", " M")
            s = s.replace("mil millones", "mil M").replace(" euros", " €").replace("dólares", "$")
            return s.replace("-", "−").strip()
    return None

def tendencia(item):
    t = (item.get("titulo", "") + " ").lower()
    if re.search(r"\b(cae|caen|cayó|baja|bajan|hunde|desplom|recort|pierde|retroced|abarat|frena)", t): return "baja"
    if re.search(r"\b(sube|suben|subirá|gana|dispar|crece|récord|eleva|dispara|avanza|repunt|máximo)", t): return "sube"
    return None

def icono(item, t):
    s = (item.get("titulo", "") + " " + item.get("resumen", "")).lower()
    if re.search(r"coche|automo|volkswagen|tesla|vehícul", s): return lambda: icon_car(0.95, CREAM + (255,))
    if re.search(r"hipotec|vivienda|alquiler|euríbor|casa", s): return lambda: icon_house(0.8, BLUE + (255,))
    if re.search(r"europa|\bue\b|bruselas|comisión europea|eurozona|bce", s): return lambda: icon_eu(1.0, (90, 130, 230, 255), t)
    if re.search(r"banc|fed\b|reserva federal|tipos|bolsa|ibex|wall street|beneficio", s): return lambda: icon_bank(0.62, GOLD + (255,))
    if re.search(r"gobierno|congreso|senado|constitucional|tribunal|parlament|elecci|ministr|president", s): return lambda: icon_bank(0.62, BLUE + (255,))
    return lambda: icon_globo(t)

def icon_globo(t, s=1.0):
    """Globo terráqueo de líneas, como el logo de Bursio (recurso por defecto)."""
    R = int(150 * s); im = Image.new("RGBA", (2 * R + 20, 2 * R + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    c = R + 10; col = (61, 191, 207, 255)
    d.ellipse([c - R, c - R, c + R, c + R], outline=col, width=8)
    for k in range(3):  # meridianos que giran despacio
        w = abs(math.cos(t * 0.6 + k * 1.05)) * R
        d.ellipse([c - w, c - R, c + w, c + R], outline=(61, 191, 207, 140), width=4)
    for f in (-0.5, 0, 0.5):
        y = c + f * R; x = math.sqrt(max(0, R * R - (f * R) ** 2))
        d.line([(c - x, y), (c + x, y)], fill=(61, 191, 207, 140), width=4)
    return im

# ───────────────────────── voz ─────────────────────────
def audio_b64(b64, ruta):
    """MP3 en base64 (del Apps Script) -> wav sin silencios en los extremos. Devuelve la duración."""
    mp3 = ruta[:-4] + ".mp3"
    open(mp3, "wb").write(base64.b64decode(b64))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-ar", str(SR), "-ac", "1", ruta], check=True)
    a, sr = sf.read(ruta, dtype="float32")
    e = np.abs(a) > 0.01
    if e.any():
        i0, i1 = np.argmax(e), len(a) - np.argmax(e[::-1])
        a = a[max(0, i0 - int(0.02 * sr)):min(len(a), i1 + int(0.05 * sr))]
    sf.write(ruta, a, sr)
    return len(a) / sr

# ───────────────────────── escenas ─────────────────────────
def kicker_title(im, lt, k, title):
    a, y = appear(lt, 0.0, 0.35, 40); put(im, text_img(k, 800, 36, GOLD), 80, 320 + y, a)
    size = 84 if len(title) < 70 else 72
    a, y = appear(lt, 0.15, 0.4); t = text_img(title, "p800", size, CREAM, maxw=920)
    put(im, t, 80, 375 + y, a)
    return 375 + t.height

def escena_item(n, item, tema):
    fuente = (item.get("fuente") or "").upper()
    titulo = limpiar(item.get("titulo"))
    if len(titulo) > 110: titulo = titulo[:107].rsplit(" ", 1)[0] + "…"
    num, ten = cifra(item), tendencia(item)
    cuerpo = primera_frase(item)
    def dib(im, lt, L):
        fin_t = kicker_title(im, lt, f"0{n} · {fuente}" if fuente else f"0{n}", titulo)
        y0 = max(700, fin_t + 60)
        ic = icono(item, lt)
        if num:
            col = RED if ten == "baja" else GREEN if ten == "sube" else CREAM
            p = clamp((lt - 0.6) / 0.45)
            if p > 0:
                sh = math.sin(lt * 70) * 8 * max(0, 1 - (lt - 0.6) / 0.4)
                timg = text_img(num, 900, 130 if len(num) < 9 else 100, col)
                put(im, timg, 80 + sh, y0 + (1 - ease(p)) * 30, ease(p))
                if ten: put(im, arrow(100, col, up=(ten == "sube")), 80 + timg.width + 30, y0 + 20 + math.sin(lt * 4) * 8, ease(p))
        elif ic:
            p = ease((lt - 0.4) / 0.6); put(im, ic(), W // 2, y0 + (1 - p) * 40, p, anchor="ct")
        elif ten:
            p = ease((lt - 0.5) / 0.5); put(im, arrow(160, RED if ten == "baja" else GREEN, up=(ten == "sube")), W // 2, y0, p, anchor="ct")
        p = clamp((lt - min(2.2, L * 0.35)) / 0.5)
        if p > 0:
            put(im, text_img(cuerpo, 500, 46, CREAM, maxw=920, lh=1.3), 80, max(1060, y0 + 260) + (1 - ease(p)) * 30, ease(p))
        a, _ = appear(lt, 1.5, 0.5, 0)
        if item.get("fuente"): put(im, text_img("Fuente: " + item["fuente"], 500, 30, MUTED), 80, 1480, a)
    return dib

def escena_intro(tema):
    l1, l2 = TEMAS[tema]["intro"]
    def dib(im, lt, L):
        a, y = appear(lt, 0.0, 0.4); put(im, text_img(l1, "p800", 96, CREAM, align="center", maxw=980), W // 2, 640 + y, a, anchor="ct")
        a, y = appear(lt, 0.25, 0.4); put(im, text_img(l2, "p800", 96, GOLD2, align="center", maxw=980), W // 2, 760 + y, a, anchor="ct")
    return dib

def escena_cta(im, lt, L):
    a, y = appear(lt, 0.0, 0.4); put(im, text_img("Esto es", 600, 52, MUTED), W // 2, 520 + y, a, anchor="ct")
    p = clamp((lt - 0.15) / 0.5); put(im, text_img("Bursio", "p800", 200, CREAM), W // 2, 600, ease(p), 0.9 + 0.1 * back(p), anchor="ct")
    p = clamp((lt - 1.2) / 0.4)
    if p > 0:
        put(im, text_img("Lo que importa,", 600, 60, CREAM), W // 2, 900 + (1 - ease(p)) * 40, ease(p), anchor="ct")
        put(im, text_img("cada mañana en tu correo", 600, 60, GOLD2), W // 2, 985 + (1 - ease(p)) * 40, ease(p), anchor="ct")
    p = clamp((lt - 2.6) / 0.4)
    if p > 0:
        put(im, chip("bursio.org", GOLD, 58, pad=(48, 24)), W // 2, 1150, ease(p), back(p) * (1 + 0.04 * math.sin(lt * 5)), anchor="ct")
        put(im, text_img("Síguenos para no perderte nada", 600, 38, MUTED), W // 2, 1320, ease(p), anchor="ct")

# ───────────────────────── montaje ─────────────────────────
def montar(tema, segmentos, fecha, carpeta):
    os.makedirs(carpeta, exist_ok=True)
    cfg = TEMAS[tema]
    intro = [x for x in segmentos if x.get("tipo") == "intro"][:1]
    cierre = [x for x in segmentos if x.get("tipo") == "cierre"][:1]
    noticias = [x for x in segmentos if x.get("tipo") == "noticia"]
    durs = [audio_b64(intro[0]["audio"], f"{carpeta}/v0.wav")]
    items = []
    for x in noticias:  # se añaden noticias mientras el vídeo no pase de ~85 s
        d = audio_b64(x["audio"], f"{carpeta}/v{len(durs)}.wav")
        if len(items) >= 3 and sum(durs) + d + 7 + (len(durs) + 2) * (LEAD + GAP) > 85:
            break
        items.append({"titulo": x.get("titulo", ""), "resumen": x.get("texto", ""), "fuente": x.get("fuente", "")}); durs.append(d)
    durs.append(audio_b64(cierre[0]["audio"], f"{carpeta}/v{len(durs)}.wav"))
    cuts = [0.0]
    for d in durs[:-1]: cuts.append(round(cuts[-1] + LEAD + d + GAP, 2))
    DUR = round(cuts[-1] + LEAD + durs[-1] + 1.8, 2); cuts.append(DUR)
    escenas = [(escena_intro(tema), GOLD)] + [(escena_item(i + 1, it, tema), cfg["acento"] if i % 2 == 0 else GOLD) for i, it in enumerate(items)] + [(escena_cta, GOLD)]
    # pista de voz
    v = np.zeros(int(DUR * SR) + SR, np.float32)
    for i, st in enumerate(cuts[:-1]):
        a, sr = sf.read(f"{carpeta}/v{i}.wav", dtype="float32")
        if sr != SR: a = np.interp(np.arange(int(len(a) * SR / sr)) * sr / SR, np.arange(len(a)), a).astype(np.float32)
        i0 = int((st + LEAD) * SR); v[i0:i0 + len(a)] += a[:len(v) - i0]
    v = v[:int(DUR * SR)]; v /= max(1e-6, np.abs(v).max()) / 0.9
    sf.write(f"{carpeta}/voz.wav", v, SR)
    subprocess.run([sys.executable, "musica.py", ",".join(str(c) for c in cuts[1:-1]), str(DUR), f"{carpeta}/musica.wav"], check=True, stdout=subprocess.DEVNULL)
    d = datetime.date.fromisoformat(fecha); etiqueta = f"{cfg['etiqueta']} · {d.day} {MESES[d.month - 1]}"

    def frame(t):
        i = max(k for k in range(len(cuts) - 1) if cuts[k] <= t)
        fn, acc = escenas[i]; t0, t1 = cuts[i], cuts[i + 1]
        bg = background(t, acc)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        fn(layer, t - t0, durs[i])
        if i < len(escenas) - 1:
            p = clamp((t1 - t) / 0.3); a, dy = ease(p), (1 - p) * -50
            if a < 1:
                l2 = Image.new("RGBA", (W, H), (0, 0, 0, 0)); l2.alpha_composite(layer, (0, int(dy)))
                l2.putalpha(l2.getchannel("A").point(lambda x: int(x * a))); layer = l2
        bg.alpha_composite(layer)
        dd = ImageDraw.Draw(bg)
        dd.rectangle([0, 0, W, 10], fill=(255, 255, 255, 18)); dd.rectangle([0, 0, int(W * t / DUR), 10], fill=GOLD)
        put(bg, text_img("Bursio", "p700", 54, CREAM), 80, 120)
        lab = text_img(etiqueta, 700, 30, GOLD); put(bg, lab, W - 80 - lab.width, 138)
        footer(bg)
        if t < 0.1: bg.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(255 * (1 - t / 0.1)))))
        if t > DUR - 0.5: bg.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (t - (DUR - 0.5)) / 0.5))))
        return bg.convert("RGB")

    mudo = f"{carpeta}/mudo.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", mudo], stdin=subprocess.PIPE)
    for k in range(int(DUR * FPS)): p.stdin.write(frame(k / FPS).tobytes())
    p.stdin.close(); p.wait()
    final = f"{OUT}/{tema}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mudo, "-i", f"{carpeta}/musica.wav", "-i", f"{carpeta}/voz.wav", "-filter_complex",
                    f"[1:a]atrim=0:{DUR},afade=t=out:st={DUR - 1.5}:d=1.5,volume=0.3[m0];"
                    "[2:a]aformat=channel_layouts=stereo,highpass=f=70,acompressor=threshold=-20dB:ratio=2:attack=8:release=120,asplit=2[vk][vm];"
                    "[m0][vk]sidechaincompress=threshold=0.05:ratio=4:attack=20:release=300[md];"
                    "[md][vm]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-shortest",
                    "-movflags", "+faststart", final], check=True)
    return {"video": final, "duracion": DUR, "titulares": [it["titulo"] for it in items],
            "texto": f"{cfg['texto']} Cada mañana, lo que importa en tu correo: bursio.org {cfg['hashtags']} #bursio"}

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(OUT, exist_ok=True)
    datos = leer_datos()
    fecha = datos.get("fecha") or hoy_madrid()
    res = {"fecha": fecha}
    for v in datos.get("videos") or []:
        tema = v.get("id")
        if tema not in TEMAS: continue
        try:
            res[tema] = montar(tema, v.get("segmentos") or [], fecha, f"tmp_{tema}")
            print("Hecho", tema, res[tema]["duracion"], "s", flush=True)
        except Exception as e:
            print("Fallo montando", tema, e, flush=True)
    json.dump(res, open(f"{OUT}/textos.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not any(k in res for k in TEMAS): sys.exit(1)

if __name__ == "__main__":
    main()
