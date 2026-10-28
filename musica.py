"""Música de fondo original (sintetizada) + efectos para el vídeo de Bursio.
Estilo noticias, 128 bpm: bajo pulsante, staccatos, bombo a negras, palmas y charles.
Efectos: whoosh en cada cambio de escena e impacto en el gancho."""
import numpy as np, wave, sys, os

SR = 44100
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
N = int(SR * DUR)
BPM = 96
BEAT = 60 / BPM
rng = np.random.default_rng(7)
t_all = np.arange(N) / SR

def note(f, dur, amp=1.0, kind="pad"):
    n = int(dur * SR); t = np.arange(n) / SR
    if kind == "pad":
        w = sum(np.sin(2*np.pi*f*d*t + p) for d, p in [(1, 0), (1.003, 1.3), (0.997, 2.1), (2.0, .4)]) / 4
        env = np.minimum(1, t / 0.6) * np.minimum(1, (dur - t) / 0.8)
    elif kind == "bass":
        w = np.sin(2*np.pi*f*t) + 0.25*np.sin(2*np.pi*2*f*t)
        env = np.minimum(1, t / 0.02) * np.exp(-t * 1.6)
    else:  # piano / pluck
        w = np.sin(2*np.pi*f*t) + 0.4*np.sin(2*np.pi*2*f*t)*np.exp(-t*6) + 0.15*np.sin(2*np.pi*3*f*t)*np.exp(-t*9)
        env = np.minimum(1, t / 0.005) * np.exp(-t * 2.8)
    return (w * env * amp).astype(np.float32)

def add(buf, x, start):
    i = int(start * SR)
    if i >= len(buf): return
    j = min(len(buf), i + len(x)); buf[i:j] += x[:j-i]

def hz(m): return 440 * 2 ** ((m - 69) / 12)

music = np.zeros(N, np.float32)
# Estilo "breaking news" de los vídeos de noticias: 128 bpm, menor, bajo pulsante en semicorcheas,
# staccatos tipo cuerda, bombo a negras, palmas en 2 y 4, charles en semicorcheas tipo "tic-tac".
BPM = 128; BEAT = 60 / BPM; S16 = BEAT / 4
prog = [[57, 60, 64], [53, 57, 60], [55, 59, 62], [52, 56, 59]]   # Am - F - G - E
roots = [33, 29, 31, 28]
bar = 4 * BEAT
def stab(f, amp):
    n = int(0.16*SR); t = np.arange(n)/SR
    w = sum(np.sign(np.sin(2*np.pi*f*d*t))*0.5 + np.sin(2*np.pi*f*d*t)*0.5 for d in (1, 1.004, 0.996)) / 3
    return (w * np.exp(-t*22) * amp).astype(np.float32)
def sub(f, dur, amp):
    n = int(dur*SR); t = np.arange(n)/SR
    w = np.sin(2*np.pi*f*t) + 0.35*np.sign(np.sin(2*np.pi*f*t))
    return (w * np.minimum(1, t/0.004) * np.exp(-t*9) * amp).astype(np.float32)
k = 0; t0 = 0.0
while t0 < DUR:
    ch = prog[k % 4]
    for m in ch: add(music, note(hz(m), bar + 0.3, 0.025, "pad"), t0)
    for s16 in range(16):
        tt = t0 + s16 * S16
        # bajo pulsante en semicorcheas, con acento en la corchea
        add(music, sub(hz(roots[k % 4] + (12 if s16 % 8 == 6 else 0)), S16 * 0.95, 0.15 if s16 % 2 == 0 else 0.09), tt)
        # staccatos (patrón sincopado)
        if s16 in (0, 3, 6, 8, 11, 14):
            for m in ch: add(music, stab(hz(m + 12), 0.035), tt)
    # motivo agudo cada dos compases, sube la tensión
    if k % 2 == 1:
        for j, m in enumerate([ch[2] + 12, ch[1] + 12, ch[0] + 24, ch[2] + 12]):
            add(music, note(hz(m), 0.3, 0.04, "pluck"), t0 + 2 * BEAT + j * BEAT / 2)
    k += 1; t0 += bar

def kick():
    n = int(0.3*SR); t = np.arange(n)/SR
    f = 48 + 110*np.exp(-t*35)
    return (np.sin(2*np.pi*np.cumsum(f)/SR) * np.exp(-t*10) * 0.6).astype(np.float32)
def hat(a):
    n = int(0.04*SR); t = np.arange(n)/SR
    x = rng.standard_normal(n); x = np.diff(x, prepend=0)
    return (x * np.exp(-t*110) * a).astype(np.float32)
def clap():
    n = int(0.2*SR); t = np.arange(n)/SR
    x = rng.standard_normal(n) * (np.exp(-t*30) + 0.6*np.exp(-np.abs(t-0.012)*400) + 0.5*np.exp(-np.abs(t-0.024)*400)) * 0.14
    return x.astype(np.float32)
def riser(dur):
    n = int(dur*SR); t = np.arange(n)/SR
    x = rng.standard_normal(n).astype(np.float32); y = np.zeros(n, np.float32); p = 0.0
    a = np.linspace(0.03, 0.5, n)
    for i in range(n): p += a[i]*(x[i]-p); y[i] = p
    return (y * (t/dur)**2 * 0.25).astype(np.float32)
drums = np.zeros(N, np.float32)
b = 0; tb = 0.0
while tb < DUR - 2.0:
    add(drums, kick(), tb)
    if b % 2 == 1: add(drums, clap(), tb)
    for q in range(4): add(drums, hat(0.05 if q == 2 else 0.025), tb + q * S16)
    b += 1; tb += BEAT
# pequeño 'riser' antes de cada cambio de noticia
for c in ([float(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 and sys.argv[1] else []):
    if c > 1.2: add(drums, riser(1.0), c - 1.0)

# efectos
fx = np.zeros(N, np.float32)
def whoosh(dur=0.55, amp=0.22):
    n = int(dur*SR); t = np.arange(n)/SR
    x = rng.standard_normal(n).astype(np.float32)
    # filtro paso banda que barre de grave a agudo (aprox. con media móvil variable)
    out = np.zeros(n, np.float32); y = 0.0
    a = np.linspace(0.02, 0.35, n)
    for i in range(n):
        y += a[i] * (x[i] - y); out[i] = y
    out = out - np.convolve(out, np.ones(30)/30, mode="same")
    env = np.sin(np.pi * np.clip(t/dur, 0, 1)) ** 2
    return out * env * amp * 3
def impact():
    n = int(1.2*SR); t = np.arange(n)/SR
    boom = np.sin(2*np.pi*(45 + 60*np.exp(-t*12))*t) * np.exp(-t*3.2) * 0.55
    nz = rng.standard_normal(n) * np.exp(-t*14) * 0.18
    return (boom + nz).astype(np.float32)
def ding(f=1318.5, a=0.08):
    n = int(1.0*SR); t = np.arange(n)/SR
    return ((np.sin(2*np.pi*f*t) + 0.3*np.sin(2*np.pi*2.01*f*t)) * np.exp(-t*4) * a).astype(np.float32)

cuts = [float(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [5, 7.5, 17, 26, 35, 44, 52]
add(fx, impact(), 0.55)
for c in cuts: add(fx, whoosh(), c - 0.3)
for d in cuts[2:7]: add(fx, ding(), d + 1.2)
add(fx, ding(1760, 0.1), cuts[-1] + 1.0)

mix = music * 0.9 + drums * 0.75 + fx
# fundido de entrada/salida
fade_in = np.minimum(1, t_all / 0.4); fade_out = np.minimum(1, (DUR - t_all) / 2.5)
mix *= fade_in * fade_out
# compresión suave + normalización
mix = np.tanh(mix * 1.6) / np.tanh(1.6)
mix /= max(1e-6, np.abs(mix).max()) / 0.85
st = np.stack([mix, np.roll(mix, 220) * 0.96 + mix * 0.04], 1)
with wave.open(sys.argv[3] if len(sys.argv) > 3 else "music.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st * 32767).astype(np.int16).tobytes())
print("ok", DUR)
