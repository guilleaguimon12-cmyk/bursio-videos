# Modelos de vídeo de Bursio

Hay dos modelos. Los dos usan el mismo motor (`generar.py`), la misma voz, la misma música y el mismo cierre con bursio.org. Solo cambian la portada, la cabecera y el número de noticias.

## 1. Noticias del día en 60 segundos (diario)
Son tres vídeos al día: economía, internacional y deportes.
- **Portada:** "Tus noticias en 60 segundos" con la etiqueta roja "SECCIÓN · día mes".
- **Intro hablada:** "Tus noticias en 60 segundos. Economía global, 31 de octubre."
- **Contenido:** 3 o 4 noticias de temas distintos. Cada una lleva su propio titular arriba.
- **Comando:**
  ```
  DATOS=datos.json python3 generar.py
  ```
- **Apps Script (Mantenimiento.gs):** rellenar el objeto `HOY` y ejecutar `tmpHoyEco`, `tmpHoyInt` o `tmpHoyDep`.
- **TikTok:** "Noticias de hoy, {d} de {mes}: {sección} en un minuto. {titular}, y N noticias más. {pregunta} Cada mañana, lo que importa: bursio.org {hashtags}"
- **Título de YouTube:** "Noticias de {sección} hoy, {d} de {mes}: {titular}"

## 2. Noticia individual explicada (una sola historia)
Es un vídeo sobre un único tema, contado en partes.
- **Portada:** el titular propio en grande y la etiqueta roja "EXPLICADO EN 1 MINUTO", NUNCA con fecha (la fecha es solo para las generales). No lleva "Tus noticias en 60 segundos".
- **Intro hablada:** frase propia que engancha. Ejemplo: "El Salvador ha mandado casi 2.000 soldados a Haití. Esto es lo que está pasando."
- **Contenido:** hasta 5 partes. Arriba va siempre el título de la historia y debajo una etiqueta dorada con el apartado ("Qué ha pasado", "La emboscada", "Qué dice X"…).
- **Comando:**
  ```
  UNICA="Título corto fijo" UNICA_PORTADA="Titular grande de portada" MAX_NOTICIAS=5 DATOS=datos.json python3 generar.py
  ```
- **Apps Script (Mantenimiento.gs):** rellenar `HOY_EXPLICA` y ejecutar `tmpHoyExplica`. Usa la sección internacional de la hoja puente; cambiar la sección si el tema es de economía o deportes.
  - Campos: `nombre`, `intro` (frase hablada), `fuente`, `pregunta` y `caps` (de 3 a 5 partes, cada una con `corto`, que es el apartado, `texto` y `fotos`, que son títulos de Wikipedia con etiqueta en VID_LUGARES).
- **TikTok:** "{Titular}: qué está pasando, explicado en un minuto. {pregunta} Cada mañana, lo que importa: bursio.org {hashtags}"
- **Título de YouTube:** "{Titular}: qué está pasando, explicado en 1 minuto"

## Reglas comunes
- **Fotos (regla del 31 de octubre, sustituye a la anterior):** siempre específicas del tema; nada genérico. Por ejemplo, nada de un avión para hablar de Corea del Norte ni de un skyline cualquiera de Abu Dabi.
  - **Empresa:** su logo (Binance → logo de Binance).
  - **País:** su bandera y además algo propio y reconocible del país.
  - **Cripto:** su logo (bitcoin → logo de bitcoin).
  - **Lugares y edificios:** con etiqueta.
  - **Nunca:** personas reconocibles, tiendas ni recortes antiguos.
  - Revisar los fotogramas antes de publicar.
- **Decimales:** se dicen con "coma". La web se dice "bursio punto o erre ge".
- **Hashtags:** los genéricos primero y uno o dos específicos al final.
- **Peso:** recomprimir a menos de 10 MB antes de subir.
