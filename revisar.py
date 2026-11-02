"""Revisión antes de montar (2 nov). Uso: python3 revisar.py datos.json
Para cada noticia enseña la cifra grande y su flecha tal como saldrán en pantalla, y avisa de
lo que suele fallar. Si sale algún AVISO, se corrige el guion antes de montar."""
import json, re, sys
import generar as G

PROHIBIDAS = ["además", "mientras tanto", "por último"]
avisos = 0
j = json.load(open(sys.argv[1]))
for v in j["videos"]:
    print(f"\n== {v['id']} ==")
    segs = v["segmentos"]
    for k, s in enumerate(segs):
        if s.get("tipo") == "cierre":
            if "?" not in (s.get("texto") or ""):
                print("  AVISO cierre sin pregunta"); avisos += 1
            continue
        if s.get("tipo") != "noticia": continue
        tx = re.sub(r"(\d+) coma (\d+)", r"\1,\2", s.get("texto", ""))
        m = G.NUM.search(tx)
        fl = {"sube": "▲ verde", "baja": "▼ roja", None: "sin flecha (dorada)"}
        if m:
            c = G.cifra({"titulo": tx}) or m.group(0)
            t = G.tendencia_cifra(tx, m.start(), m.end())
            frase = tx[max(0, m.start() - 60):m.end() + 25].replace("\n", " ")
            print(f"  {k}. {s.get('corto')!r}: cifra {c!r} {fl[t]}  «…{frase}…»")
        else:
            print(f"  {k}. {s.get('corto')!r}: sin cifra grande")
        if not s.get("fotos"):
            print("     AVISO sin foto"); avisos += 1
        low = tx.lower()
        for p in PROHIBIDAS:
            if re.search(r"(^|[.!?]\s+)" + p, low):
                print(f"     AVISO transición prohibida: {p!r}"); avisos += 1
        if len(tx.split()) > 48:
            print(f"     AVISO texto largo ({len(tx.split())} palabras)"); avisos += 1
        if re.search(r"\d\.\d{3}", tx) and "audios" not in s:
            print("     AVISO cifra con punto de miles sin pasar por la voz"); avisos += 1
print(f"\n{avisos} avisos")
