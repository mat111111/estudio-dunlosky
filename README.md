# Estudio Dunlosky

Aplicación de estudio que funciona en tu navegador y se levanta con Docker. Escribís cualquier tema, la app busca la información en Wikipedia (o usa tus apuntes), genera preguntas a partir del texto, corrige tus respuestas comparándolas con la fuente y te hace practicar justo las partes en las que te equivocaste.

Está organizada alrededor de las 10 técnicas de estudio evaluadas por Dunlosky y colegas (2013), ordenadas por la utilidad que les asignaron.

---

## Cómo iniciarla en Windows

1. Instalá **Docker Desktop** (https://www.docker.com/products/docker-desktop/) y abrilo. Esperá a que diga *Engine running*.
2. Descomprimí esta carpeta donde quieras (por ejemplo, `Documentos\estudio-dunlosky`).
3. Hacé doble clic en **`iniciar.bat`**.
   La primera vez descarga la imagen base y tarda unos minutos. Después arranca en segundos.
4. Se abre sola en **http://localhost:8000**.

Para apagarla: doble clic en **`detener.bat`**. Tus temas y tu progreso quedan guardados.

### Desde una terminal (Windows, Linux o Mac)

```bash
docker compose up -d --build     # levantar
docker compose logs -f           # ver qué está pasando
docker compose down              # apagar
```

El contenedor se reinicia solo si reiniciás la computadora (mientras Docker Desktop esté abierto).

---

## Cómo se usa

1. **Nuevo tema**: buscás un tema en Wikipedia (español o inglés) y elegís hasta 4 artículos para combinarlos. También podés pegar tus apuntes (si usás títulos con `#`, cada uno se vuelve una sección).
2. La app descarga el texto, lo divide en secciones y genera preguntas: completar, opción múltiple, verdadero o falso, definiciones y preguntas de “¿por qué?”.
3. Elegís una técnica. Todas terminan en una prueba, porque recuperar la información de memoria es lo que más fija el aprendizaje.
4. Cuando respondés, la app te muestra si está bien, la respuesta correcta escrita “en rojo” y **la oración exacta de la fuente** que lo respalda, con enlace a la versión del artículo que se usó.
5. Si te equivocás:
   - la pregunta vuelve más adelante en la **misma sesión**;
   - queda en **Mis errores**, donde vuelve acompañada de preguntas “hermanas” sobre el **mismo fragmento** del texto (otra palabra en blanco, otro formato), para que practiques esa parte y no solo memorices una respuesta;
   - se programa para el **repaso de hoy** (10 minutos después).
6. Las preguntas que acertás se van espaciando: 1 día, 3 días, una semana y más (práctica distribuida).

En las preguntas abiertas podés **autocorregirte** (“Lo sabía / A medias / No lo sabía”) si la corrección automática no captó tu respuesta. Eso ajusta el calendario de repaso.

Atajos de teclado en la práctica: `1`–`4` eligen una opción, `Enter` pasa a la siguiente, `Ctrl + Enter` envía una respuesta larga.

---

## Las 10 técnicas y qué hace la app con cada una

| Utilidad (Dunlosky, 2013) | Técnica | En la app |
|---|---|---|
| Alta | **Autoevaluación** (practice testing) | Preguntas generadas desde la fuente, corrección con evidencia y reintento de los errores. |
| Alta | **Práctica distribuida** | Calendario por pregunta con algoritmo SM-2: “Repaso de hoy”, calendario de los próximos 7 días por tema. |
| Moderada | **Interrogación elaborativa** | Detecta en el texto relaciones de causa y consecuencia (porque, ya que, por lo tanto…) y pregunta “¿por qué?”. Si faltan, toma las ideas clave y te pide explicarlas. |
| Moderada | **Autoexplicación** | Muestra la sección oración por oración y te pide explicar cada una y conectarla con lo anterior. |
| Moderada | **Práctica intercalada** | Mezcla preguntas de dos o más temas en una misma sesión. |
| Baja | **Resumen** | Ocultás el texto y escribís el resumen; te muestra qué conceptos centrales faltaron y dónde aparecen, y te deja practicar justo esos. |
| Baja | **Subrayado** | Subrayás tocando oraciones; compara con las ideas clave y convierte tus subrayados en preguntas. |
| Baja | **Palabra clave mnemotécnica** | Lista los términos clave con su definición; escribís tu asociación y después te evalúa (tu pista aparece si fallás). |
| Baja | **Imágenes mentales** | Por cada párrafo describís la imagen que te formaste; termina con una prueba de la sección. |
| Baja | **Relectura** | Mide el tiempo de lectura y termina con una prueba corta para contrastar la sensación de “ya lo sé”. |

Referencia: Dunlosky, J., Rawson, K. A., Marsh, E. J., Nathan, M. J. y Willingham, D. T. (2013). *Improving students’ learning with effective learning techniques*. Psychological Science in the Public Interest, 14(1), 4–58.

---

## De dónde sale la información y cómo se comprueba

- **Fuente**: la API oficial de Wikipedia (MediaWiki). Se guarda el número de **revisión exacta** del artículo, así cada corrección se hace contra ese texto aunque el artículo cambie después. Se descartan secciones como Referencias, Enlaces externos o Véase también.
- **Cada pregunta está anclada a una oración** del texto descargado. Al corregir se muestra esa oración como evidencia.
- **Corrección**:
  - opción múltiple y verdadero/falso: exacta;
  - completar: tolera acentos, mayúsculas y errores de tipeo menores; los años y números deben ser exactos;
  - respuestas abiertas: compara los conceptos de tu respuesta con los de la fuente y te dice cuáles faltaron.
- **Tus apuntes**: si estudiás desde texto propio, la app compara contra lo que pegaste. Conviene que esté revisado.

Límites a tener en cuenta: la generación de preguntas y la corrección de respuestas abiertas son automáticas y se basan en el texto, no en entender el significado. Alguna pregunta puede salir rara o una respuesta correcta dicha con otras palabras puede marcarse como parcial; para eso está la autocorrección. Wikipedia es una buena puerta de entrada, pero para un examen siempre contrastá con la bibliografía de la materia.

### Modo IA (opcional)

Si tenés una clave de la API de Anthropic, cargala en **Ajustes** (o en el archivo `.env`, ver `.env.example`). Con eso:

- las respuestas abiertas se corrigen por significado, siempre contra el fragmento de la fuente;
- se suman preguntas de comprensión generadas por IA. **Cada pregunta debe citar un fragmento literal del artículo; si la cita no aparece en el texto descargado, se descarta.**

Sin clave, todo lo demás funciona igual.

---

## Publicarla en internet (Render)

El repositorio incluye `render.yaml`, que Render lee solo. En Render: **New → Blueprint**, elegís este repositorio y confirmás. Queda en un link `https://estudio-dunlosky-xxxx.onrender.com`.

En esa versión se activa el **modo público** (`PUBLIC_MODE=1`):
- cada visitante recibe su propio espacio (cookie + base de datos separada): nadie ve los temas de otro;
- la clave de IA no se puede cargar ni cambiar desde la interfaz (solo como variable de entorno en Render, y la pagarías vos).

Límites del plan gratuito: el servicio se duerme tras unos minutos sin visitas y tarda alrededor de un minuto en despertar, y el disco no es permanente, así que los datos de los visitantes se borran al reiniciarse.

## Tus datos

Se guardan en la carpeta **`data`** (archivo `estudio.db`, SQLite). Para hacer una copia de seguridad, copiá esa carpeta. Borrar el contenedor o la imagen de Docker no borra tus datos.

## Cambiar el puerto

Si el 8000 está ocupado, copiá `.env.example` como `.env` y cambiá `PUERTO=8000` por otro (por ejemplo `8080`). Luego abrí `http://localhost:8080` (el `iniciar.bat` abre el 8000; cambialo ahí también si querés).

---

## Estructura del proyecto

```
estudio-dunlosky/
├── app/
│   ├── main.py        API (FastAPI): temas, sesiones, corrección, técnicas, panel
│   ├── sources.py     Wikipedia (búsqueda y descarga) y apuntes propios
│   ├── textproc.py    Oraciones, normalización, palabras y oraciones clave
│   ├── generator.py   Generación de preguntas ancladas a la fuente
│   ├── grader.py      Corrección de respuestas, resúmenes, subrayados y explicaciones
│   ├── srs.py         Repetición espaciada (SM-2)
│   ├── ai.py          Modo IA opcional (con verificación de citas)
│   ├── db.py          Esquema y acceso a SQLite
│   └── static/        Interfaz: index.html, styles.css, app.js (sin frameworks)
├── tests/             Pruebas automáticas (no necesitan internet)
├── Dockerfile
├── docker-compose.yml
├── iniciar.bat / detener.bat
└── data/              Tu base de datos (se crea sola)
```

### Ejecutar sin Docker (para programar)

```bash
python -m venv .venv
.venv\Scripts\activate            # en Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
set DB_PATH=data\estudio.db       # en Linux/Mac: export DB_PATH=data/estudio.db
uvicorn app.main:app --reload
python -m unittest discover tests
```

---

## Problemas frecuentes

- **“Docker Desktop no está abierto”**: abrilo desde el menú Inicio y esperá a que termine de arrancar.
- **“No se pudo conectar con Wikipedia”**: la app necesita internet para buscar y descargar artículos. Una vez creado el tema, se puede estudiar sin conexión.
- **No abre en el navegador**: entrá a mano a http://localhost:8000. Si sigue sin abrir, ejecutá `docker compose logs` en la carpeta del proyecto para ver el error.
- **Docker pide activar WSL 2 o la virtualización**: seguí el asistente de Docker Desktop; es un requisito de Docker en Windows.
