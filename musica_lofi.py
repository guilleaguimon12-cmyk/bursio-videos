"""Música de fondo original (sintetizada) + efectos para el vídeo de Bursio.
Lo-fi suave a 96 bpm: pad de acordes, bajo, piano, bombo y charles.
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
# Am7 - Fmaj7 - Cmaj7 - G6 (dos compases cada uno = 8 tiempos)
prog = [[57, 60, 64, 67], [53, 57, 60, 64], [48, 55, 59, 64], [55, 59, 62, 64]]
roots = [45, 41, 48, 43]
bar = 4 * BEAT
chord_len = 2 * bar
k = 0; t0 = 0.0
while t0 < DUR:
    ch = prog[k % 4]
    for m in ch: add(music, note(hz(m), chord_len + 0.6, 0.05, "pad"), t0)
    for b in range(8):  # bajo en 1 y 3
        if b % 2 == 0: add(music, note(hz(roots[k % 4]), BEAT * 1.8, 0.16, "bass"), t0 + b * BEAT)
    # arpegio de piano en corcheas, suave
    arp = [ch[0] + 12, ch[2] + 12, ch[1] + 12, ch[3] + 12]
    for s in range(16):
        if rng.random() < 0.72:
            add(music, note(hz(arp[s % 4]), 1.2, 0.045 + 0.02 * rng.random(), "pluck"), t0 + s * BEAT / 2)
    k += 1; t0 += chord_len

# batería (entra a los 2 s, se va en el cierre)
def kick():
    n = int(0.35*SR); t = np.arange(n)/SR
    f = 50 + 90*np.exp(-t*30)
    return (np.sin(2*np.pi*np.cumsum(f)/SR) * np.exp(-t*9) * 0.5).astype(np.float32)
def hat(a):
    n = int(0.06*SR); t = np.arange(n)/SR
    x = rng.standard_normal(n); x = np.diff(x, prepend=0)
    return (x * np.exp(-t*70) * a).astype(np.float32)
def snare():
    n = int(0.25*SR); t = np.arange(n)/SR
    x = rng.standard_normal(n) * np.exp(-t*22) * 0.16 + np.sin(2*np.pi*190*t)*np.exp(-t*30)*0.12
    return x.astype(np.float32)
drums = np.zeros(N, np.float32)
b = 0; tb = 2.5
while tb < DUR - 4.5:
    if b % 4 in (0,): add(drums, kick(), tb)
    if b % 4 == 2: add(drums, kick()*0.8, tb + BEAT*0.5)
    if b % 4 in (1, 3): add(drums, snare(), tb)
    add(drums, hat(0.05), tb); add(drums, hat(0.03), tb + BEAT/2)
    b += 1; tb += BEAT

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
