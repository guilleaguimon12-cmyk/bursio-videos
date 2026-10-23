# Bursio · vídeos diarios

Cada mañana, sin intervención:

1. **~06:10 (Apps Script de Bursio, `prepararVideosDia`)**: escribe los guiones de dos vídeos —**economía global** (del lote del día, no gasta API) y **política internacional** (una generación propia, ~1 céntimo)— y les pone voz con Google Text-to-Speech (Chirp 3 HD, castellano).
2. **~06:40 (este repositorio, GitHub Actions)**: recoge guiones y voz con `?videos=2`, monta los vídeos verticales (1080×1920, algo más de 1 minuto, 1 s de pausa entre temas, música propia) y los deja en **Releases** con la fecha del día: `economia.mp4`, `internacional.mp4`, `textos.json`.
3. **07:00 (tarea programada de Claude)**: los publica en TikTok @bursio a través de Metricool.

No hace falta ninguna clave en este repositorio: la voz la genera el Apps Script.

Probarlo a mano: pestaña **Actions → Vídeos diarios de Bursio → Run workflow**.

Fuentes: Inter y Playfair Display (SIL Open Font License). Música sintetizada por `musica.py`.
