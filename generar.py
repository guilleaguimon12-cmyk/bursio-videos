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
        "etiqueta": "ECONOMÍA GLOBAL", "acento": GREEN, "corto": "ECONOMÍA", "nombre": "economía",
        "intro_voz": "Esto es lo que mueve hoy la economía.",
        "intro": ("Lo que mueve hoy", "la economía mundial"),
        "hashtags": "#noticiashoy #economia #bolsa #wallstreet",
        "texto": "La economía global que importa hoy, en poco más de un minuto.",
    },
    "internacional": {
        "etiqueta": "POLÍTICA INTERNACIONAL", "acento": BLUE, "corto": "POLÍTICA MUNDIAL", "nombre": "política internacional",
        "intro_voz": "Esto es lo más importante de la política internacional hoy.",
        "intro": ("Lo que importa hoy", "en el mundo"),
        "hashtags": "#noticiashoy #actualidad #internacional #geopolitica",
        "texto": "La política internacional que importa hoy, en poco más de un minuto.",
    },
    "deporte": {
        "etiqueta": "DEPORTES", "acento": GOLD, "corto": "DEPORTES", "nombre": "deportes",
        "intro_voz": "Deportes: lo que importa hoy.",
        "intro": ("Lo que importa hoy", "en el deporte"),
        "hashtags": "#noticiashoy #deportes #futbol #laliga",
        "texto": "Lo que importa hoy en el deporte, en poco más de un minuto.",
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
    # Nunca montar con los textos de otro día: mejor no publicar nada.
    print("No hay vídeos de hoy; no se monta nada.", flush=True)
    return {}

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

def icono(item, t, tema=""):
    s = (item.get("titulo", "") + " " + item.get("resumen", "")).lower()
    if tema == "deporte":
        if re.search(r"maratón|atletism|dopaje|carrera|ciclism|tour|fórmula|f1|motogp|gran premio", s): return lambda: icon_crono(t)
        if re.search(r"premio|trofeo|balón de oro|título|campeón|campeona|copa|legado", s): return lambda: icon_trofeo(t)
        return lambda: icon_balon(t)
    if re.search(r"coche|automo|volkswagen|tesla|vehícul", s): return lambda: icon_car(0.95, CREAM + (255,))
    if re.search(r"hipotec|vivienda|alquiler|euríbor|casa", s): return lambda: icon_house(0.8, BLUE + (255,))
    if re.search(r"europa|\bue\b|bruselas|comisión europea|eurozona|bce", s): return lambda: icon_eu(1.0, (90, 130, 230, 255), t)
    if re.search(r"banc|fed\b|reserva federal|tipos|bolsa|ibex|wall street|beneficio", s): return lambda: icon_bank(0.62, GOLD + (255,))
    if re.search(r"gobierno|congreso|senado|constitucional|tribunal|parlament|elecci|ministr|president", s): return lambda: icon_bank(0.62, BLUE + (255,))
    return lambda: icon_globo(t)

def icon_balon(t, s=1.0):
    """Balón de fútbol que gira despacio."""
    R = int(140 * s); im = Image.new("RGBA", (2 * R + 20, 2 * R + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    c = R + 10
    d.ellipse([c - R, c - R, c + R, c + R], fill=CREAM + (255,), outline=CREAM + (255,))
    def pent(cx, cy, r, rot):
        return [(cx + r * math.cos(rot + k * 2 * math.pi / 5), cy + r * math.sin(rot + k * 2 * math.pi / 5)) for k in range(5)]
    rot = t * 0.8
    d.polygon(pent(c, c, R * 0.36, rot - math.pi / 2), fill=(20, 20, 24, 255))
    for k in range(5):
        a = rot - math.pi / 2 + k * 2 * math.pi / 5
        cx, cy = c + R * 0.82 * math.cos(a), c + R * 0.82 * math.sin(a)
        d.polygon(pent(cx, cy, R * 0.26, a + math.pi / 5), fill=(20, 20, 24, 255))
        x1, y1 = c + R * 0.36 * math.cos(a), c + R * 0.36 * math.sin(a)
        d.line([(x1, y1), (c + R * 0.6 * math.cos(a), c + R * 0.6 * math.sin(a))], fill=(20, 20, 24, 255), width=6)
    m = Image.new("L", im.size, 0); ImageDraw.Draw(m).ellipse([c - R, c - R, c + R, c + R], fill=255)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0)); out.paste(im, (0, 0), m)
    ImageDraw.Draw(out).ellipse([c - R, c - R, c + R, c + R], outline=GOLD + (255,), width=6)
    return out

def icon_trofeo(t, s=1.0):
    """Copa dorada con un brillo que pasa."""
    w, h = int(300 * s), int(300 * s); im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    g = GOLD + (255,); cx = w // 2
    d.pieslice([cx - 95, -60, cx + 95, 170], 0, 180, fill=g)
    d.rectangle([cx - 95, 0, cx + 95, 55], fill=g)
    d.arc([cx - 150, 10, cx - 60, 110], 90, 270, fill=g, width=14)
    d.arc([cx + 60, 10, cx + 150, 110], 270, 90, fill=g, width=14)
    d.rectangle([cx - 16, 165, cx + 16, 225], fill=g)
    d.rounded_rectangle([cx - 80, 225, cx + 80, 260], 8, fill=g)
    d.rounded_rectangle([cx - 105, 260, cx + 105, 295], 8, fill=GOLD2 + (255,))
    x = int((t * 0.7 % 1.6) / 1.6 * (w + 120)) - 60
    d.line([(x, 0), (x - 50, 170)], fill=(255, 255, 255, 110), width=16)
    m = Image.new("L", im.size, 0); m.paste(im.getchannel("A")); im.putalpha(m)
    return im

def icon_crono(t, s=1.0):
    """Cronómetro con la aguja corriendo."""
    R = int(130 * s); im = Image.new("RGBA", (2 * R + 20, 2 * R + 70), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    c, cy = R + 10, R + 60; col = CREAM + (255,)
    d.rounded_rectangle([c - 26, 6, c + 26, 40], 8, fill=GOLD + (255,)); d.rectangle([c - 10, 38, c + 10, 62], fill=GOLD + (255,))
    d.ellipse([c - R, cy - R, c + R, cy + R], outline=col, width=12)
    for k in range(12):
        a = k * math.pi / 6; r1 = R - 22 if k % 3 else R - 38
        d.line([(c + r1 * math.cos(a), cy + r1 * math.sin(a)), (c + (R - 10) * math.cos(a), cy + (R - 10) * math.sin(a))], fill=col, width=6)
    a = t * 2.4 - math.pi / 2
    d.line([(c, cy), (c + (R - 30) * math.cos(a), cy + (R - 30) * math.sin(a))], fill=RED + (255,), width=9)
    d.ellipse([c - 12, cy - 12, c + 12, cy + 12], fill=RED + (255,))
    return im

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

def audio_seg(x, ruta, primero=False):
    """Voz de un bloque. Si viene frase a frase ('audios'), las une con pausas naturales."""
    clips = [c for c in (x.get("audios") or []) if c]
    if not clips: return audio_b64(x["audio"], ruta)
    partes = []
    for k, c in enumerate(clips):
        r = ruta[:-4] + f"_{k}.wav"; audio_b64(c, r)
        a, sr = sf.read(r, dtype="float32"); os.remove(r)
        if sr != SR: a = np.interp(np.arange(int(len(a) * SR / sr)) * sr / SR, np.arange(len(a)), a).astype(np.float32)
        partes.append(a)
        if k < len(clips) - 1: partes.append(np.zeros(int((0.45 if primero and k == 0 else 0.35) * SR), np.float32))
    a = np.concatenate(partes); sf.write(ruta, a, SR)
    return len(a) / SR

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
    marcador = None
    if tema == "deporte":
        num, ten = None, None
        m = re.search(r"(?<![\d.,/])(\d{1,2})\s?-\s?(\d{1,2})(?![\d.,/])", (item.get("titulo", "") + " " + item.get("resumen", "")))
        if m: marcador = f"{m.group(1)} – {m.group(2)}"
    cuerpo = primera_frase(item)
    def dib(im, lt, L):
        fin_t = kicker_title(im, lt, f"0{n} · {fuente}" if fuente else f"0{n}", titulo)
        y0 = max(700, fin_t + 60)
        ic = icono(item, lt, tema)
        bajo = y0 + 120
        if num:
            col = RED if ten == "baja" else GREEN if ten == "sube" else CREAM
            p = clamp((lt - 0.6) / 0.45)
            if p > 0:
                sh = math.sin(lt * 70) * 8 * max(0, 1 - (lt - 0.6) / 0.4)
                timg = text_img(num, 900, 130 if len(num) < 9 else 100, col)
                put(im, timg, 80 + sh, y0 + (1 - ease(p)) * 30, ease(p))
                if ten: put(im, arrow(100, col, up=(ten == "sube")), 80 + timg.width + 30, y0 + 20 + math.sin(lt * 4) * 8, ease(p))
            bajo = y0 + 170
        elif marcador:
            p = clamp((lt - 0.6) / 0.45)
            if p > 0:
                timg = text_img(marcador, 900, 170, CREAM)
                put(im, timg, W // 2, y0 + (1 - ease(p)) * 30, ease(p), 1 + (1 - back(p)) * 0.5, anchor="ct")
            bajo = y0 + 210
        elif ic:
            img = ic(); p = ease((lt - 0.4) / 0.6); put(im, img, W // 2, y0 + (1 - p) * 40, p, anchor="ct")
            bajo = y0 + img.height
        elif ten:
            p = ease((lt - 0.5) / 0.5); put(im, arrow(160, RED if ten == "baja" else GREEN, up=(ten == "sube")), W // 2, y0, p, anchor="ct")
        p = clamp((lt - min(2.2, L * 0.35)) / 0.5)
        if p > 0:
            put(im, text_img(cuerpo, 500, 46, CREAM, maxw=920, lh=1.3), 80, max(1060, bajo + 60) + (1 - ease(p)) * 30, ease(p))
        a, _ = appear(lt, 1.5, 0.5, 0)
        if item.get("fuente"): put(im, text_img("Fuente: " + item["fuente"], 500, 30, MUTED), 80, 1480, a)
    return dib

SERIE = ("Tus noticias", "en 60 segundos")

def escena_intro(tema):
    t1 = text_img(SERIE[0], "p800", 118, CREAM, align="center", maxw=1000)
    t2 = text_img(SERIE[1], "p800", 118, GOLD2, align="center", maxw=1000)
    def dib(im, lt, L):
        # visible desde el primer fotograma (es también la miniatura)
        z = 1 + 0.03 * clamp(lt / L)
        put(im, t1, W // 2, 600, 1.0, z, anchor="ct")
        put(im, t2, W // 2, 745, 1.0, z, anchor="ct")
    return dib

def escena_cta(im, lt, L, pregunta=""):
    import estilo as E
    if pregunta:
        a, y = appear(lt, 0.0, 0.4); put(im, E.titular_serif(pregunta, 96), W // 2, 430 + y, a, anchor="ct")
        p = clamp((lt - 0.8) / 0.4)
        if p > 0: put(im, text_img("Te leo en comentarios", 700, 52, GOLD2), W // 2, 900 + (1 - ease(p)) * 30, ease(p), anchor="ct")
    p = clamp((lt - 1.6) / 0.5)
    if p > 0:
        put(im, text_img("Bursio", "p800", 120, CREAM), W // 2, 1080, ease(p), anchor="ct")
        put(im, text_img("Cada mañana, lo que importa", 600, 46, CREAM), W // 2, 1240, ease(p), anchor="ct")
        put(im, chip("bursio.org", GOLD, 54, pad=(44, 22)), W // 2, 1330, ease(p), back(p) * (1 + 0.04 * math.sin(lt * 5)), anchor="ct")

# ───────────────────────── montaje ─────────────────────────
def montar(tema, segmentos, fecha, carpeta):
    import estilo as E
    os.makedirs(carpeta, exist_ok=True)
    cfg = TEMAS[tema]
    intro = [x for x in segmentos if x.get("tipo") == "intro"][:1]
    cierre = [x for x in segmentos if x.get("tipo") == "cierre"][:1]
    noticias = [x for x in segmentos if x.get("tipo") == "noticia"]
    off = len(intro)
    durs = [audio_b64(intro[0]["audio"], f"{carpeta}/v0.wav")] if intro else []
    items = []
    for x in noticias:  # hasta 4 noticias
        d = audio_seg(x, f"{carpeta}/v{len(durs)}.wav", primero=not items and not intro)
        if len(items) >= 4:  # 4 noticias como mucho
            break
        items.append(x); durs.append(d)
    durs.append(audio_seg(cierre[0], f"{carpeta}/v{len(durs)}.wav"))
    textos = [x.get("texto", "") for x in intro + items] + [cierre[0].get("texto", "")]
    n = len(items)
    cuts = [0.0]
    for d in durs[:-1]: cuts.append(round(cuts[-1] + LEAD + d + GAP, 2))
    DUR = round(cuts[-1] + LEAD + durs[-1] + 1.6, 2); cuts.append(DUR)
    fotos = [E.fotos_de(x) for x in items]
    # Nunca una noticia sin foto: si Apps Script no trajo ninguna, se reutiliza la de otra noticia.
    for i in range(n):
        if not fotos[i]:
            otra = next((f for f in fotos[i - 1::-1] + fotos[i + 1:] if f), None)
            if otra: fotos[i] = [otra[-1]]
    print(tema, "fotos por noticia:", [len(f) for f in fotos], flush=True)
    # pista de voz + tiempos de cada palabra + cortes de foto
    v = np.zeros(int(DUR * SR) + SR, np.float32)
    subs, cortes, tws = [], [], []
    for i, st in enumerate(cuts[:-1]):
        a, sr = sf.read(f"{carpeta}/v{i}.wav", dtype="float32")
        if sr != SR: a = np.interp(np.arange(int(len(a) * SR / sr)) * sr / SR, np.arange(len(a)), a).astype(np.float32)
        i0 = int((st + LEAD) * SR); v[i0:i0 + len(a)] += a[:len(v) - i0]
        tw = [(w, x + LEAD, y + LEAD) for w, x, y in E.tiempos(a, SR, textos[i])]
        subs.append(E.trozos(tw))
        tws.append(tw)
        j = i - off
        cortes.append(E.cortes(tw, len(fotos[j])) if 0 <= j < n else [])
    v = v[:int(DUR * SR)]; v /= max(1e-6, np.abs(v).max()) / 0.9
    sf.write(f"{carpeta}/voz.wav", v, SR)
    # sonido de transición: en cada cambio de escena y en cada cambio de foto
    fx = np.zeros(int(DUR * SR) + SR, np.float32)
    momentos = [c for c in cuts[1:-1]] + [cuts[i] + c for i in range(len(cortes)) for c in cortes[i]]
    for k, m in enumerate(sorted(momentos)):
        w = E.whoosh(SR, semilla=k); i0 = max(0, int((m - 0.22) * SR))
        fx[i0:i0 + len(w)] += w[:len(fx) - i0]
    sf.write(f"{carpeta}/fx.wav", fx[:int(DUR * SR)], SR)
    subprocess.run([sys.executable, "musica.py", ",".join(str(c) for c in cuts[1:-1]), str(DUR), f"{carpeta}/musica.wav"], check=True, stdout=subprocess.DEVNULL)
    titulares = [E.titular_serif(limpiar(x.get("corto")) or E.titular_corto(limpiar(x.get("titulo")))) for x in items]
    def cred(x, c): return E.credito_img(" · ".join(z for z in [("Fuente: " + x["fuente"]) if x.get("fuente") else "", c] if z))
    creditos = [[cred(x, c) for _, c in fotos[i]] or [cred(x, "")] for i, x in enumerate(items)]
    cifras = {}
    for j, x in enumerate(items):
        tx = re.sub(r"(\d+) coma (\d+)", r"\1,\2", x.get("texto", ""))
        m = NUM.search(tx)
        if not m: continue
        lead = re.match(r"\d+", m.group(0).lstrip("−-")).group(0)
        t_w = next((a for w, a, b in tws[j + off] if re.sub(r"\D", "", w).startswith(lead)), None)
        if t_w is None: continue
        c = cifra({"titulo": tx}) or m.group(0)
        cifras[j] = (E.cifra_grande(c, tendencia(x)), max(0.4, t_w - 0.1))
    print(tema, "cifras:", {j: round(v[1], 1) for j, v in cifras.items()}, flush=True)
    marca_bursio = text_img("Bursio", "p700", 40, CREAM)
    d0 = datetime.date.fromisoformat(fecha)
    MES_L = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    fecha_txt = f"{d0.day} de {MES_L[d0.month - 1]}"
    capa_portada = E.portada(cfg["nombre"], fecha_txt)
    pregunta = cierre[0].get("pregunta", "")
    et_intro = E.etiqueta(f"{cfg['etiqueta']} · {d0.day} {MESES[d0.month - 1]}", size=52)
    intro_dib = escena_intro(tema)

    def frame(t):
        i = max(k for k in range(len(cuts) - 1) if cuts[k] <= t)
        lt = t - cuts[i]; j = i - off
        if off and i == 0:
            # introducción hablada sobre la portada: foto de la noticia más importante + 'Tus noticias en 60 segundos'
            f0 = fotos[0][0][0] if n and fotos[0] else None
            if f0 is not None and f0["modo"] == "fit": bg = f0["full"].convert("RGBA")
            elif f0 is not None: bg = E.encuadre(f0, lt, 0.0).convert("RGBA")
            else: bg = background(t, cfg["acento"])
            bg.alpha_composite(E.sombra())
            put(bg, marca_bursio, W // 2, 90, 0.8, anchor="ct")
            bg.alpha_composite(capa_portada)
        elif j < n:
            k = sum(1 for c in cortes[i] if lt >= c)
            t0 = max([0.0] + [c for c in cortes[i] if lt >= c])
            if fotos[j] and j == 0 and not off and lt < 0.6 and fotos[0][0][0]["modo"] == "fit":
                # en la portada, la primera foto a pantalla completa
                bg = fotos[0][0][0]["full"].convert("RGBA")
                bg.alpha_composite(E.sombra())
            elif fotos[j]:
                bg = E.encuadre(fotos[j][min(k, len(fotos[j]) - 1)][0], lt, t0).convert("RGBA")
                bg.alpha_composite(E.sombra())
            else:
                bg = background(t, cfg["acento"])
            put(bg, marca_bursio, W // 2, 90, 0.8, anchor="ct")
            fit = bool(fotos[j]) and fotos[j][min(k, len(fotos[j]) - 1)][0]["modo"] == "fit"
            if j == 0 and not off and lt < 0.6:
                # portada de medio segundo (también es la miniatura); la voz arranca ya con la noticia
                ap = 1.0 if lt < 0.35 else 1 - ease((lt - 0.35) / 0.25)
                pc = capa_portada if ap >= 0.999 else capa_portada.copy()
                if ap < 0.999: pc.putalpha(pc.getchannel("A").point(lambda v: int(v * ap)))
                bg.alpha_composite(pc)
                t_in = 0.3
            else:
                t_in = 0.0
            a = ease((lt - t_in) / 0.25)
            put(bg, titulares[j], 50, 230 + (1 - a) * 30, a)
            ff = fotos[j][min(k, len(fotos[j]) - 1)][0] if fotos[j] else {}
            if ff.get("lugar") and not (j == 0 and not off and lt < 0.6):
                yl = (E.FOTO_Y + ff["fg"].height // 2 - 80) if ff.get("modo") == "fit" else 1100
                put(bg, E.etiqueta_lugar(ff["lugar"]), 50, yl, ease(clamp((lt - t0 - 0.2) / 0.3)))
            if j in cifras and cifras[j][1] <= lt < cifras[j][1] + 2.8:
                ct = lt - cifras[j][1]; ac = min(ease(ct / 0.25), 1 - ease((ct - 2.55) / 0.25))
                put(bg, cifras[j][0], W // 2, 700, ac, 0.85 + 0.15 * back(clamp(ct / 0.35)), anchor="ct")
            if lt >= t_in: E.dibujar_subs(bg, lt, subs[i], y=1500 if fit else 1210)
            put(bg, creditos[j][min(k, len(creditos[j]) - 1)], 70, 1835, 0.55)
        else:
            bg = background(t, GOLD)
            escena_cta(bg, lt, durs[i], pregunta)
        if t > DUR - 0.5: bg.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (t - (DUR - 0.5)) / 0.5))))
        return bg.convert("RGB")

    if os.environ.get("FOTOGRAMAS"):
        for s in os.environ["FOTOGRAMAS"].split(","): frame(float(s)).save(f"{carpeta}/f_{s}.png")
        return {"duracion": DUR}
    mudo = f"{carpeta}/mudo.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", mudo], stdin=subprocess.PIPE)
    for k in range(int(DUR * FPS)): p.stdin.write(frame(k / FPS).tobytes())
    p.stdin.close(); p.wait()
    final = f"{OUT}/{tema}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mudo, "-i", f"{carpeta}/musica.wav", "-i", f"{carpeta}/voz.wav", "-i", f"{carpeta}/fx.wav", "-filter_complex",
                    f"[1:a]atrim=0:{DUR},afade=t=out:st={DUR - 1.5}:d=1.5,volume=0.3[m0];"
                    "[2:a]aformat=channel_layouts=stereo,highpass=f=70,acompressor=threshold=-20dB:ratio=2:attack=8:release=120,asplit=2[vk][vm];"
                    "[m0][vk]sidechaincompress=threshold=0.05:ratio=4:attack=20:release=300[md];"
                    "[3:a]aformat=channel_layouts=stereo,volume=0.55[fx];"
                    "[md][vm][fx]amix=inputs=3:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-shortest",
                    "-movflags", "+faststart", final], check=True)
    t1 = limpiar(items[0].get("corto")) or E.titular_corto(limpiar(items[0].get("titulo")))
    return {"video": final, "duracion": DUR, "titulares": [x.get("titulo", "") for x in items],
            "texto": f"Noticias de hoy, {fecha_txt}: {cfg['nombre']} en un minuto. {t1}, y {n - 1} noticias más. {pregunta} Cada mañana, lo que importa: bursio.org {cfg['hashtags']}".replace("  ", " ")}

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
