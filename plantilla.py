"""Vídeo vertical de Bursio (1080x1920, 30 fps, 60 s): resumen de economía
con texto animado, gráficos propios y música. Escribe fotogramas a ffmpeg."""
import math, subprocess, sys, functools
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, DUR = 1080, 1920, 30, 60.0
F = "fonts/"
def font(name, size): return ImageFont.truetype(F + name, size)
@functools.lru_cache(None)
def inter(w, s): return font(f"inter-latin-{w}-normal.woff", s)
@functools.lru_cache(None)
def play(w, s): return font(f"playfair-display-latin-{w}-normal.woff", s)

BG0, BG1 = (14, 12, 9), (27, 21, 12)
GOLD = (214, 176, 88); GOLD2 = (240, 206, 120)
CREAM = (246, 239, 226); MUTED = (168, 156, 136)
RED = (236, 84, 72); GREEN = (96, 204, 138); BLUE = (110, 160, 240)

CUTS = [0.0, 6.38, 9.1, 15.5, 25.29, 34.93, 41.94, 51.43, 60.0]

# ---------- utilidades ----------
def clamp(x, a=0, b=1): return max(a, min(b, x))
def ease(x): x = clamp(x); return 1 - (1 - x) ** 3
def ease_io(x): x = clamp(x); return 3*x*x - 2*x*x*x
def back(x):
    x = clamp(x); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2

def wrap(text, fnt, maxw):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if fnt.getlength(t) <= maxw or not cur: cur = t
        else: lines.append(cur); cur = w_
    if cur: lines.append(cur)
    return lines

@functools.lru_cache(None)
def text_img(text, fkey, size, fill, maxw=920, lh=1.18, align="left", hl=None, hlfill=None):
    fnt = inter(fkey, size) if isinstance(fkey, int) else play(int(fkey[1:]), size)
    lines = wrap(text, fnt, maxw)
    asc, desc = fnt.getmetrics()
    lhp = int(size * lh)
    wmax = max(int(fnt.getlength(l)) for l in lines) + 8
    im = Image.new("RGBA", (wmax, lhp * (len(lines) - 1) + asc + desc + 6), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    hlw = set(w.strip(".,:«»") for w in (hl or "").lower().split())
    for i, l in enumerate(lines):
        x = 0 if align == "left" else (wmax - fnt.getlength(l)) / 2
        if not hlw:
            d.text((x, i * lhp), l, font=fnt, fill=fill)
        else:
            for w_ in l.split(" "):
                c = hlfill if w_.lower().strip(".,:«»") in hlw else fill
                d.text((x, i * lhp), w_, font=fnt, fill=c)
                x += fnt.getlength(w_ + " ")
    return im

def put(canvas, im, x, y, alpha=1.0, scale=1.0, anchor="lt"):
    if alpha <= 0.01: return
    if scale != 1.0:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
    if alpha < 0.999:
        a = im.getchannel("A").point(lambda v: int(v * alpha))
        im = im.copy(); im.putalpha(a)
    if anchor == "ct": x = x - im.width // 2
    if anchor == "cc": x, y = x - im.width // 2, y - im.height // 2
    canvas.alpha_composite(im, (int(x), int(y)))

def appear(t, start, dur=0.55, dist=60):
    """alpha, desplazamiento y para la entrada de un elemento"""
    p = ease((t - start) / dur)
    return p, (1 - p) * dist

def chip(text, color, size=40, pad=(26, 14), txt=(20, 16, 10)):
    fnt = inter(700, size)
    w_ = int(fnt.getlength(text)) + pad[0] * 2; h_ = size + pad[1] * 2
    im = Image.new("RGBA", (w_, h_), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w_ - 1, h_ - 1], radius=h_ // 2, fill=color)
    d.text((pad[0], pad[1] - size * 0.1), text, font=fnt, fill=txt)
    return im
chip = functools.lru_cache(None)(chip)

# ---------- fondo ----------
@functools.lru_cache(None)
def base_bg():
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(BG0[i] + (BG1[i] - BG0[i]) * k) for i in range(3)))
    # grano fino de líneas de cuadrícula
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(g)
    for x in range(0, W, 90): gd.line([(x, 0), (x, H)], fill=(255, 255, 255, 7))
    for y in range(0, H, 90): gd.line([(0, y), (W, y)], fill=(255, 255, 255, 7))
    im = im.convert("RGBA"); im.alpha_composite(g)
    return im

@functools.lru_cache(None)
def glow(r, color, a):
    im = Image.new("RGBA", (r * 2, r * 2), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([r * .3, r * .3, r * 1.7, r * 1.7], fill=color + (a,))
    return im.filter(ImageFilter.GaussianBlur(r * 0.35))

def background(t, accent):
    im = base_bg().copy()
    gx = W * 0.5 + math.sin(t * 0.35) * 260; gy = 760 + math.cos(t * 0.27) * 220
    g = glow(520, accent, 70)
    im.alpha_composite(g, (int(gx - 520), int(gy - 520)))
    g2 = glow(380, GOLD, 34)
    im.alpha_composite(g2, (int(W - 200 - 380 + math.cos(t * .4) * 120), int(1500 - 380 + math.sin(t * .3) * 140)))
    return im

# ---------- iconos dibujados ----------
def icon_car(s, col):
    im = Image.new("RGBA", (int(520 * s), int(260 * s)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    k = s; lw = int(10 * k)
    body = [(20, 175), (40, 120), (130, 105), (190, 45), (330, 45), (400, 105), (480, 120), (500, 175)]
    d.line([(x * k, y * k) for x, y in body] + [(20 * k, 175 * k)], fill=col, width=lw, joint="curve")
    d.line([(200 * k, 60 * k), (200 * k, 105 * k)], fill=col, width=int(6 * k))
    d.line([(150 * k, 105 * k), (390 * k, 105 * k)], fill=col, width=int(6 * k))
    for cx in (130, 390):
        d.ellipse([(cx - 48) * k, 140 * k, (cx + 48) * k, 236 * k], fill=BG0 + (255,), outline=col, width=lw)
        d.ellipse([(cx - 14) * k, 174 * k, (cx + 14) * k, 202 * k], fill=col)
    return im

def icon_bank(s, col):
    im = Image.new("RGBA", (int(420 * s), int(380 * s)), (0, 0, 0, 0)); d = ImageDraw.Draw(im); k = s
    d.polygon([(210 * k, 10 * k), (400 * k, 110 * k), (20 * k, 110 * k)], outline=col, width=int(10 * k))
    d.ellipse([190 * k, 58 * k, 230 * k, 98 * k], outline=col, width=int(6 * k))
    for i in range(5):
        x = (60 + i * 75) * k
        d.rounded_rectangle([x - 14 * k, 135 * k, x + 14 * k, 300 * k], radius=int(8 * k), fill=col)
    d.rounded_rectangle([20 * k, 315 * k, 400 * k, 345 * k], radius=int(8 * k), fill=col)
    return im

def icon_house(s, col):
    im = Image.new("RGBA", (int(420 * s), int(380 * s)), (0, 0, 0, 0)); d = ImageDraw.Draw(im); k = s; lw = int(11 * k)
    d.line([(30 * k, 180 * k), (210 * k, 30 * k), (390 * k, 180 * k)], fill=col, width=lw, joint="curve")
    d.line([(80 * k, 140 * k), (80 * k, 340 * k), (340 * k, 340 * k), (340 * k, 140 * k)], fill=col, width=lw, joint="curve")
    d.rounded_rectangle([175 * k, 230 * k, 245 * k, 340 * k], radius=int(10 * k), outline=col, width=int(8 * k))
    d.text((150 * k, 140 * k), "%", font=inter(800, int(70 * k)), fill=col)
    return im

def icon_eu(s, col, t):
    im = Image.new("RGBA", (int(420 * s), int(420 * s)), (0, 0, 0, 0)); d = ImageDraw.Draw(im); k = s
    cx = cy = 210 * k; R = 150 * k
    for i in range(12):
        a = i / 12 * 2 * math.pi + t * 0.25
        x, y = cx + R * math.cos(a), cy + R * math.sin(a); r = 20 * k
        pts = []
        for j in range(10):
            rr = r if j % 2 == 0 else r * 0.42; b = j / 10 * 2 * math.pi - math.pi / 2
            pts.append((x + rr * math.cos(b), y + rr * math.sin(b)))
        d.polygon(pts, fill=col)
    bolt = [(225, 95), (160, 220), (205, 220), (180, 330), (265, 185), (215, 185), (245, 95)]
    d.polygon([(x * k, y * k) for x, y in bolt], fill=GOLD2)
    return im

def arrow(size, col, up=False):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im); s = size
    if up: d.polygon([(s * .5, s * .05), (s * .95, s * .55), (s * .65, s * .55), (s * .65, s * .95), (s * .35, s * .95), (s * .35, s * .55), (s * .05, s * .55)], fill=col)
    else: d.polygon([(s * .5, s * .95), (s * .95, s * .45), (s * .65, s * .45), (s * .65, s * .05), (s * .35, s * .05), (s * .35, s * .45), (s * .05, s * .45)], fill=col)
    return im

# ---------- capas fijas ----------
def header(im, t, total):
    d = ImageDraw.Draw(im)
    # barra de progreso
    d.rectangle([0, 0, W, 10], fill=(255, 255, 255, 18))
    d.rectangle([0, 0, int(W * t / total), 10], fill=GOLD)
    put(im, text_img("Bursio", "p700", 54, CREAM), 80, 120)
    put(im, text_img("ECONOMÍA · 22 OCT", 700, 30, GOLD), W - 80 - text_img("ECONOMÍA · 22 OCT", 700, 30, GOLD).width, 138)

def footer(im):
    put(im, text_img("bursio.org", 600, 34, MUTED), 80, 1560)

def leave(t, end, d=0.35):
    p = clamp((end - t) / d)
    return ease(p), (1 - p) * -50

# ---------- escenas ----------
def scene_hook(im, t):
    a0, y0 = appear(t, 0.15, 0.4)
    put(im, text_img("HOY EN ECONOMÍA", 800, 40, GOLD), W // 2, 470 + y0, a0, anchor="ct")
    a1, y1 = appear(t, 0.35, 0.45)
    put(im, text_img("Volkswagen se hunde", "p800", 104, CREAM, maxw=940, align="center"), W // 2, 560 + y1, a1, anchor="ct")
    # −25% con golpe
    p = clamp((t - 0.55) / 0.5)
    if p > 0:
        sc = 1.0 + (1 - back(p)) * 0.9
        shake = math.sin(t * 70) * 14 * max(0, 1 - (t - 0.55) / 0.5)
        big = text_img("−25%", 900, 300, RED)
        put(im, big, W // 2 + shake, 1000, min(1, p * 2.5), sc, anchor="cc")
    a2, y2 = appear(t, 1.2, 0.45)
    put(im, text_img("en Bolsa, hasta mínimos de 2010", 600, 50, CREAM, maxw=900, align="center"), W // 2, 1200 + y2, a2, anchor="ct")
    a3, y3 = appear(t, 2.6, 0.5)
    put(im, chip("+ 4 noticias que te afectan", GOLD, 44), W // 2, 1330 + y3, a3, anchor="ct")

def scene_intro(im, t, t0):
    lt = t - t0
    a, y = appear(lt, 0.05, 0.45)
    put(im, text_img("Lo que importa hoy,", "p700", 96, CREAM, align="center", maxw=980), W // 2, 650 + y, a, anchor="ct")
    a, y = appear(lt, 0.3, 0.45)
    put(im, text_img("en 60 segundos", "p700", 96, GOLD2, align="center", maxw=980), W // 2, 770 + y, a, anchor="ct")
    for i in range(5):
        a, y = appear(lt, 0.7 + i * 0.12, 0.35, 30)
        d = Image.new("RGBA", (110, 110), (0, 0, 0, 0)); dd = ImageDraw.Draw(d)
        dd.ellipse([0, 0, 109, 109], outline=GOLD, width=5)
        fnt = inter(800, 46); s = str(i + 1)
        dd.text((55 - fnt.getlength(s) / 2, 26), s, font=fnt, fill=CREAM)
        put(im, d, W // 2 - 340 + i * 170, 1010 + y, a, anchor="ct")

def story_frame(im, lt, kicker, title, body, source, hl=None):
    a, y = appear(lt, 0.05, 0.4, 40)
    put(im, text_img(kicker, 800, 36, GOLD), 80, 300 + y, a)
    a, y = appear(lt, 0.2, 0.45)
    put(im, text_img(title, "p800", 92, CREAM, maxw=920), 80, 360 + y, a)
    a, y = appear(lt, 2.4, 0.55)
    put(im, text_img(body, 500, 50, CREAM, maxw=920, lh=1.3, hl=hl, hlfill=GOLD2), 80, 1150 + y, a)
    a, _ = appear(lt, 3.0, 0.6, 0)
    put(im, text_img("Fuente: " + source, 500, 30, MUTED), 80, 1480, a)

def scene_vw(im, t, t0):
    lt = t - t0
    story_frame(im, lt, "01 · BOLSA EUROPEA", "Volkswagen se desploma",
                "Los coches chinos, mucho más baratos, le están ganando la guerra del precio al gigante alemán.",
                "OKDiario", hl="chinos, baratos,")
    p = ease((lt - 0.5) / 0.9)
    car = icon_car(0.95, CREAM + (255,))
    put(im, car, 80 - (1 - p) * 300, 640 + math.sin(lt * 3) * 4, p)
    p2 = clamp((lt - 1.1) / 0.5)
    if p2 > 0:
        put(im, text_img("−25%", 900, 150, RED), 640, 640 + (1 - ease(p2)) * -40, ease(p2))
        put(im, arrow(110, RED), 860, 820 + math.sin(lt * 4) * 10 + (1 - ease(p2)) * -40, ease(p2))
    a, y = appear(lt, 1.6, 0.45, 30)
    put(im, chip("mínimos desde 2010", RED, 40, txt=CREAM), 80, 1000 + y, a)

def scene_bankinter(im, t, t0):
    lt = t - t0
    story_frame(im, lt, "02 · BANCA ESPAÑOLA", "Bankinter gana más",
                "Lo impulsan su negocio comercial y las comisiones, que suben un 12%.",
                "El Mundo", hl="comisiones,")
    p = ease((lt - 0.45) / 0.6)
    put(im, icon_bank(0.62, GOLD + (255,)), 80, 660 + (1 - p) * 40, p)
    c = ease_io((lt - 0.6) / 1.6)
    if lt > 0.6:
        n = int(round(901 * c))
        put(im, text_img(f"{n} M€", 900, 140, CREAM), 380, 660, min(1, (lt - 0.6) * 3))
        put(im, text_img("de beneficio", 600, 44, MUTED), 386, 820, min(1, (lt - 0.6) * 3))
    a, y = appear(lt, 2.0, 0.45, 30)
    put(im, chip("+11% hasta septiembre", GREEN, 40), 80, 1000 + y, a)

def scene_cedulas(im, t, t0):
    lt = t - t0
    story_frame(im, lt, "03 · MERCADOS", "La banca sale a por dinero",
                "Santander, BBVA y Sabadell disparan la venta de cédulas aprovechando el buen momento del mercado.",
                "Expansión", hl="Santander, BBVA Sabadell")
    d = ImageDraw.Draw(im)
    base_y = 1020; x1, x2 = 100, 420
    full = 300; small = full / 3.45  # +245 % => 3,45 veces
    g1 = ease((lt - 0.5) / 0.7); g2 = ease((lt - 0.8) / 1.1)
    if g1 > 0:
        d.rounded_rectangle([x1, base_y - small * g1, x1 + 220, base_y], radius=14, fill=(120, 108, 88))
        put(im, text_img("antes", 600, 38, MUTED), x1 + 110, base_y + 14, g1, anchor="ct")
    if g2 > 0:
        d.rounded_rectangle([x2, base_y - full * g2, x2 + 220, base_y], radius=14, fill=GOLD)
        put(im, text_img("2026", 700, 38, CREAM), x2 + 110, base_y + 14, g2, anchor="ct")
        put(im, text_img("9.500 M€", 900, 64, CREAM), x2 + 110, base_y - full * g2 - 90, g2, anchor="ct")
    p = ease((lt - 1.7) / 0.4)
    if p > 0:
        put(im, chip("+245%", GREEN, 48), 720, 760, p, scale=0.8 + 0.2 * back(clamp((lt - 1.7) / 0.4)))
    a, y = appear(lt, 2.0, 0.45, 20)
    put(im, text_img("máximo en 10 años", 700, 40, GOLD2, maxw=300), 720, 860 + y, a)

def scene_euribor(im, t, t0):
    lt = t - t0
    story_frame(im, lt, "04 · TU HIPOTECA", "El Euríbor afloja",
                "La media de octubre va por el 3,222%. Buena noticia si tu hipoteca es variable.",
                "Expansión", hl="variable.")
    p = ease((lt - 0.45) / 0.6)
    put(im, icon_house(0.7, BLUE + (255,)), 70, 640 + (1 - p) * 40, p)
    p2 = clamp((lt - 0.8) / 0.5)
    if p2 > 0:
        put(im, text_img("3,263%", 900, 140, CREAM), 400, 650 + (1 - ease(p2)) * 40, ease(p2))
        put(im, arrow(80, GREEN), 410, 830 + math.sin(lt * 4) * 6, ease(p2))
        put(im, text_img("−0,028 puntos", 700, 46, GREEN), 510, 840, ease(p2))

def scene_tasazo(im, t, t0):
    lt = t - t0
    story_frame(im, lt, "05 · EUROPA", "Luz verde al «tasazo»",
                "El abogado general de la UE ve legítimo el impuesto extraordinario a las energéticas. No es vinculante, pero suele anticipar la sentencia.",
                "Expansión", hl="legítimo")
    p = ease((lt - 0.45) / 0.7)
    put(im, icon_eu(1.25, (90, 130, 230, 255), lt), W // 2, 560 + (1 - p) * 40, p, anchor="ct")

def scene_cta(im, t, t0):
    lt = t - t0
    a, y = appear(lt, 0.1, 0.5)
    put(im, text_img("Esto es", 600, 52, MUTED), W // 2, 520 + y, a, anchor="ct")
    p = clamp((lt - 0.3) / 0.6)
    put(im, text_img("Bursio", "p800", 200, CREAM), W // 2, 600, ease(p), 0.9 + 0.1 * back(p), anchor="ct")
    a, y = appear(lt, 1.0, 0.5)
    put(im, text_img("Cada mañana, solo las noticias que te importan.", 600, 56, CREAM, maxw=900, align="center", hl="importan.", hlfill=GOLD2), W // 2, 900 + y, a, anchor="ct")
    a, y = appear(lt, 1.6, 0.5)
    put(im, text_img("En tu correo. Sin buscar entre cien medios.", 500, 46, MUTED, maxw=900, align="center"), W // 2, 1080 + y, a, anchor="ct")
    p = clamp((lt - 2.2) / 0.5)
    if p > 0:
        pulse = 1 + 0.04 * math.sin(lt * 5) if lt > 2.8 else 1
        put(im, chip("Apúntate en bursio.org", GOLD, 54, pad=(44, 24)), W // 2, 1260, ease(p), back(p) * pulse, anchor="ct")
    a, y = appear(lt, 3.2, 0.5, 20)
    put(im, text_img("Síguenos para el resumen de cada día", 600, 38, MUTED), W // 2, 1440 + y, a, anchor="ct")

SCENES = [
    (scene_hook, RED), (scene_intro, GOLD), (scene_vw, RED), (scene_bankinter, GREEN),
    (scene_cedulas, GOLD), (scene_euribor, BLUE), (scene_tasazo, BLUE), (scene_cta, GOLD),
]

def frame(t):
    i = max(k for k in range(len(CUTS) - 1) if CUTS[k] <= t)
    fn, accent = SCENES[i]; t0, t1 = CUTS[i], CUTS[i + 1]
    bg = background(t, accent)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if fn is scene_hook: fn(layer, t)
    else: fn(layer, t, t0)
    # salida de escena (menos la última)
    if i < len(SCENES) - 1:
        a, dy = leave(t, t1)
        if a < 1:
            l2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            l2.alpha_composite(layer, (0, int(dy)))
            al = l2.getchannel("A").point(lambda v: int(v * a)); l2.putalpha(al); layer = l2
    bg.alpha_composite(layer)
    header(bg, t, DUR)
    footer(bg)
    # flash blanco en el gancho
    if t < 0.12:
        fl = Image.new("RGBA", (W, H), (255, 255, 255, int(255 * (1 - t / 0.12)))); bg.alpha_composite(fl)
    if t > DUR - 0.6:
        fo = Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (t - (DUR - 0.6)) / 0.6))); bg.alpha_composite(fo)
    return bg.convert("RGB")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stills":
        for s in sys.argv[2:]:
            frame(float(s)).save(f"still_{s}.png")
        sys.exit()
    out = sys.argv[1] if len(sys.argv) > 1 else "video_mudo.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                          "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    n = int(DUR * FPS)
    for k in range(n):
        p.stdin.write(frame(k / FPS).tobytes())
        if k % 150 == 0: print("frame", k, flush=True)
    p.stdin.close(); p.wait(); print("ok", out)
