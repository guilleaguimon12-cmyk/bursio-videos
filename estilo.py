"""Estilo "humano" de los vídeos de Bursio (oct 2026).

- Foto real a pantalla completa por noticia (Wikimedia Commons, con crédito),
  con zoom lento y un golpe de zoom en cada pausa de la voz.
- Gancho en el primer fotograma: etiqueta + titular de la primera noticia
  (también sirve de miniatura).
- Subtítulos grandes palabra a palabra, sincronizados con la voz.
"""
import math, re, io, base64, urllib.request
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from plantilla import W, H, GOLD, GOLD2, CREAM, MUTED, RED, clamp, ease, back, inter, put, text_img, background

AMARILLO = (255, 214, 10)
UA = "BursioBot/1.0 (https://bursio.org; hola@bursio.org)"

# ───────────────────────── fotos ─────────────────────────
def cargar_foto(f):
    """f: {"b64"|"foto_b64": ..., "url"|"foto": ...}"""
    datos = None
    b64 = f.get("b64") or f.get("foto_b64")
    url = f.get("url") or f.get("foto")
    if b64:
        datos = base64.b64decode(b64)
    elif url:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r: datos = r.read()
        except Exception as e:
            print("No se pudo bajar la foto:", e, flush=True)
    if not datos: return None
    try:
        im = Image.open(io.BytesIO(datos)).convert("RGB")
    except Exception:
        return None
    s = max(W * 1.3 / im.width, H * 1.3 / im.height)
    im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    from PIL import ImageEnhance
    im = ImageEnhance.Contrast(im).enhance(1.08); im = ImageEnhance.Color(im).enhance(1.1)
    return im

def fotos_de(seg):
    """Todas las fotos de una noticia (hasta 3), con su crédito."""
    lista = seg.get("fotos") or ([{"b64": seg.get("foto_b64"), "url": seg.get("foto"), "credito": seg.get("credito", "")}] if (seg.get("foto_b64") or seg.get("foto")) else [])
    out = []
    for f in lista:
        im = cargar_foto(f)
        if im is not None: out.append((im, f.get("credito", "")))
    return out

_SOMBRA = None
def sombra():
    """Degradado oscuro arriba y abajo para que se lea el texto."""
    global _SOMBRA
    if _SOMBRA is None:
        a = np.zeros((H, 1), np.float32)
        y = np.arange(H)[:, None].astype(np.float32)
        a += 70  # oscurecido general
        a += np.clip((620 - y) / 620, 0, 1) * 150
        a += np.clip((y - 1000) / 700, 0, 1) * 175
        a = np.clip(a, 0, 235).astype(np.uint8)
        al = Image.fromarray(np.repeat(a, W, axis=1), "L")
        _SOMBRA = Image.new("RGBA", (W, H), (0, 0, 0, 255)); _SOMBRA.putalpha(al)
    return _SOMBRA

def tramo(lt, pausas):
    """En qué plano estamos (cambia en cada pausa de la voz) y desde cuándo."""
    k = sum(1 for p in pausas if lt >= p)
    return k, max([0.0] + [p for p in pausas if lt >= p])

def encuadre(foto, lt, t0):
    """Zoom lento siempre hacia el centro, con un pequeño golpe al entrar."""
    d = lt - t0
    z = 1.0 + 0.03 * d
    if d < 0.35: z *= 1 + 0.08 * (1 - ease(d / 0.35))
    fw, fh = foto.width, foto.height
    cw, ch = min(fw, 1.25 * W / z), min(fh, 1.25 * H / z)
    cx, cy = fw / 2, fh / 2
    caja = (int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2))
    return foto.resize((W, H), Image.BILINEAR, box=caja)

# ───────────────────────── tiempos de palabras ─────────────────────────
def silabas(p):
    p = p.lower()
    if re.search(r"\d", p): return max(2, len(re.sub(r"\D", "", p)) * 1.4)
    return max(1, len(re.findall(r"[aeiouáéíóúü]+", p)))

def tiempos(audio, sr, texto):
    """(palabra, inicio, fin) aproximados: anclas en las pausas de la voz y
    reparto por sílabas entre ellas."""
    pals = texto.split()
    if not pals: return []
    dur = len(audio) / sr
    hop = int(sr * 0.01)
    rms = np.array([np.sqrt(np.mean(audio[i:i + hop] ** 2) + 1e-12) for i in range(0, len(audio) - hop, hop)])
    umbral = max(rms.max() * 0.06, 1e-4)
    sil = rms < umbral
    pausas = []  # (centro, largo)
    i = 0
    while i < len(sil):
        if sil[i]:
            j = i
            while j < len(sil) and sil[j]: j += 1
            if j - i >= 9 and i > 5 and j < len(sil) - 5:
                pausas.append(((i + j) / 2 * 0.01, (j - i) * 0.01, i * 0.01, j * 0.01))
            i = j
        else:
            i += 1
    pesos = [silabas(p) for p in pals]
    tot = sum(pesos)
    fronteras = [k for k, p in enumerate(pals[:-1]) if re.search(r"[,.;:?!]$", p)]
    acum = np.cumsum(pesos) / tot
    anclas = {}  # índice de última palabra antes de la pausa -> (fin_habla, inicio_siguiente)
    usadas = set()
    for k in fronteras:
        esperado = acum[k] * dur
        mejor = None
        for n, (c, l, a, b) in enumerate(pausas):
            if n in usadas: continue
            d = abs(c - esperado)
            if d < 0.9 and (mejor is None or d < mejor[0]): mejor = (d, n)
        if mejor:
            usadas.add(mejor[1]); _, _, a, b = pausas[mejor[1]]; anclas[k] = (a, b)
    # tramos entre anclas
    out = []
    ini, k0 = 0.0, 0
    puntos = sorted(anclas) + [len(pals) - 1]
    for k in puntos:
        fin = anclas[k][0] if k in anclas else dur
        tramo = pals[k0:k + 1]; ps = pesos[k0:k + 1]; s = sum(ps)
        t = ini
        for p, w in zip(tramo, ps):
            d = (fin - ini) * w / s
            out.append((p, t, t + d)); t += d
        if k in anclas: ini = anclas[k][1]
        k0 = k + 1
    return out

def pausas_frase(tw):
    """Momentos (s) en que empieza una frase nueva o tras una coma larga: ahí cambia el plano."""
    r = []
    for i in range(1, len(tw)):
        if re.search(r"[.;:?!]$", tw[i - 1][0]) or (re.search(r",$", tw[i - 1][0]) and tw[i][1] - tw[i - 1][2] > 0.18):
            r.append(tw[i][1])
    # ningún plano dura más de ~3,5 s: si hay un tramo largo, se parte por la palabra más cercana
    fin = tw[-1][2] if tw else 0
    marcas = [tw[0][1] if tw else 0] + r + [fin]
    extra = []
    for a, b in zip(marcas, marcas[1:]):
        n = int((b - a) // 3.5)
        for j in range(1, n + 1):
            obj = a + (b - a) * j / (n + 1)
            extra.append(min((w[1] for w in tw), key=lambda x: abs(x - obj)))
    return sorted(set(r + extra))

# ───────────────────────── subtítulos ─────────────────────────
def trozos(tw, maxp=3, maxc=18):
    """Agrupa palabras en trozos de 1-3 palabras que se leen de un vistazo."""
    out, cur = [], []
    for w in tw:
        cur.append(w)
        txt = " ".join(x[0] for x in cur)
        if len(cur) >= maxp or len(txt) >= maxc or re.search(r"[,.;:?!]$", w[0]):
            out.append(cur); cur = []
    if cur: out.append(cur)
    return out

def dibujar_subs(im, lt, grupos, y=1210):
    g = None
    for gr in grupos:
        if gr[0][1] - 0.05 <= lt < (gr[-1][2] + 0.25): g = gr
    if g is None:
        # entre trozos: deja el último visible hasta que empiece el siguiente
        prev = [gr for gr in grupos if gr[-1][2] <= lt]
        if not prev or lt - prev[-1][-1][2] > 0.6: return
        g = prev[-1]
    fnt = inter(900, 92)
    palabras = [re.sub(r"[«»\"]", "", w[0]) for w in g]
    txt = " ".join(palabras)
    ancho = fnt.getlength(txt)
    esc = 1.0
    if ancho > W - 120: esc = (W - 120) / ancho; fnt = inter(900, int(92 * esc)); ancho = fnt.getlength(txt)
    p = clamp((lt - g[0][1] + 0.05) / 0.12)
    s = 0.86 + 0.14 * back(p)
    capa = Image.new("RGBA", (int(ancho) + 60, 150), (0, 0, 0, 0)); d = ImageDraw.Draw(capa)
    x = 30
    for (w, a, b), pw in zip(g, palabras):
        col = AMARILLO if a - 0.03 <= lt < b + 0.08 else (255, 255, 255)
        d.text((x, 20), pw, font=fnt, fill=col, stroke_width=9, stroke_fill=(0, 0, 0))
        x += fnt.getlength(pw + " ")
    put(im, capa, W // 2, y, 1.0, s, anchor="ct")

# ───────────────────────── titulares ─────────────────────────
def titular_corto(t, maxc=86):
    t = re.sub(r"\s+", " ", t or "").strip().rstrip(".")
    if len(t) <= maxc: return t
    corte = t[:maxc].rsplit(" ", 1)[0].rstrip(",;:")
    return corte + "…"

def etiqueta(texto, fondo=RED, color=(255, 255, 255), size=40):
    fnt = inter(900, size)
    w = int(fnt.getlength(texto)) + 44
    im = Image.new("RGBA", (w, size + 30), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, size + 29], 10, fill=fondo + (255,))
    d.text((22, 11), texto, font=fnt, fill=color)
    return im

def caja_titular(texto, size=74):
    """Titular en blanco con sombra fuerte (sin cajas de IA)."""
    t = text_img(texto, 900, size, (255, 255, 255), maxw=W - 150, lh=1.12)
    sh = Image.new("RGBA", (t.width + 40, t.height + 40), (0, 0, 0, 0))
    a = t.getchannel("A")
    s = Image.new("RGBA", t.size, (0, 0, 0, 255)); s.putalpha(a)
    sh.alpha_composite(s, (20, 24)); sh = sh.filter(ImageFilter.GaussianBlur(9))
    out = Image.new("RGBA", sh.size, (0, 0, 0, 0)); out.alpha_composite(sh); out.alpha_composite(t, (20, 20))
    return out

def credito_img(texto):
    return text_img(texto[:70], 500, 24, (220, 220, 220), maxw=W - 140)

# ───────────────────────── cortes de foto y sonido de transición ─────────────────────────
def cortes(tw, n):
    """Momentos para pasar de una foto a la siguiente (cada foto sale una sola vez, seguidas):
    reparte la noticia en n partes y busca la pausa de la voz más cercana."""
    if n <= 1 or not tw: return []
    ini, fin = tw[0][1], tw[-1][2]
    pref = pausas_frase(tw)
    todas = [w[1] for w in tw[1:]]
    out = []
    for j in range(1, n):
        obj = ini + (fin - ini) * j / n
        c = [p for p in pref if abs(p - obj) < 1.2] or todas
        t = min(c, key=lambda x: abs(x - obj))
        if (not out or t - out[-1] > 1.2) and t - ini > 1.0 and fin - t > 1.0: out.append(t)
    return out

def whoosh(sr, dur=0.45, semilla=0):
    """Barrido de ruido tipo 'swish' (sintetizado, sin derechos)."""
    rng = np.random.default_rng(semilla)
    n = int(sr * dur); x = rng.standard_normal(n).astype(np.float32)
    t = np.linspace(0, 1, n, dtype=np.float32)
    corte = 400 + 5200 * np.clip(np.sin(np.pi * t), 0, 1) ** 1.5  # sube y baja
    a = np.exp(-2 * np.pi * corte / sr)
    y = np.zeros(n, np.float32); prev = 0.0
    for i in range(n):
        prev = (1 - a[i]) * x[i] + a[i] * prev; y[i] = prev
    y = y - np.convolve(y, np.ones(40) / 40, mode="same")  # quita graves
    env = np.sin(np.pi * np.clip(t * 1.15, 0, 1)) ** 2
    y *= env
    return (y / (np.abs(y).max() + 1e-9) * 0.5).astype(np.float32)
