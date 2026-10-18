# Estudio Dunlosky

Aplicación de estudio que funciona en tu navegador y se levanta con Docker. Escribís cualquier tema, la app busca la información en enciclopedias, libros de texto, artículos académicos y foros de programación (o usa tus apuntes), genera preguntas a partir del texto, corrige tus respuestas comparándolas con la fuente y te hace practicar justo las partes en las que te equivocaste.

Está organizada alrededor de las 10 técnicas de estudio evaluadas por Dunlosky y colegas (2013), ordenadas por la utilidad que les asignaron. Además incluye un **pomodoro** configurable con sonidos, una **lista de tareas** con aviso de urgencia por color, **niveles de complejidad** para las preguntas, **cuentas con usuario y contraseña**, **bloc de notas**, **mapas conceptuales**, un **juego de plataformas con preguntas**, **videos de YouTube recomendados** para cada tema y **guardado en PDF** del material y de las preguntas.

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

0. **Creá tu cuenta**: la primera vez la app pide un usuario y una contraseña (mínimo 8 caracteres). Cada cuenta tiene sus propios temas, tareas y progreso.
1. **Nuevo tema**: elegís el **área** (Programación, Redes, Matemática, Bases de datos, Sistemas operativos, Ciencias y salud u **Otros** para cualquier tema), escribís lo que querés estudiar y elegís hasta 4 resultados para combinarlos. También podés pegar tus apuntes (si usás títulos con `#`, cada uno se vuelve una sección).
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

## Herramientas de organización

### Pomodoro
- Duración configurable de concentración, descanso corto y descanso largo, y cada cuántos pomodoros toca el largo.
- **Sonidos**: alarma a elegir (campana, marimba, digital, cuenco tibetano, gong) y sonido de fondo opcional mientras te concentrás (lluvia suave, ruido rosa, ruido blanco, tic-tac), con volumen independiente. Todos se generan en el navegador, sin archivos externos.
- Al terminar cada pomodoro: **“¡Seguí así, lo estás logrando!”** y una frase de Albert Einstein. Solo se usan frases con origen documentado (entrevistas, cartas o libros, que se indican), porque circulan muchas atribuidas a él que nunca dijo.
- El temporizador sigue corriendo mientras usás el resto de la app (se ve en el menú) y podés asociarlo a una tarea.
- Opcional: notificación del sistema si estás en otra pestaña.

### Tareas (día, mes, año)
- Cada tarea tiene un periodo (Día, Mes o Año) y el **tiempo disponible** (en días, semanas o meses, o directamente una fecha límite).
- Con 7 días o más se ve en verde. **Con menos de una semana el color pasa de amarillo (6 días) a rojo (vence hoy)**; si se vence queda en rojo intenso. Las urgentes aparecen también en el inicio.
- Muestra una barra con el tiempo transcurrido y cuántos pomodoros le dedicaste.

### Bloc de notas
- En el menú, **Bloc de notas**: notas con título, color, tema asociado y la opción de fijarlas arriba. Se guardan solas mientras escribís (también con `Ctrl + S`).
- Buscador dentro de tus notas y filtro por tema.
- Con `#` al principio de una línea hacés un título y con `-` una lista; así queda prolija al **guardarla en PDF**. También se puede descargar como `.txt`.
- **Nota rápida**: el botón amarillo con el lápiz (abajo a la derecha) está en todas las pantallas. Anotás una duda sin salir de lo que estás haciendo; si estás en un tema, queda asociada a ese tema.
- En cada tema, **Anotar** abre una nota nueva ya asociada.

### Mapas conceptuales
En el menú, **Mapas conceptuales** (o el botón **Mapa conceptual** de cada tema):
- **Lienzo libre** con cuadros, cuadros redondeados, óvalos, círculos, rombos, notas adhesivas y texto suelto; colores, tamaño de letra y negrita.
- **Flechas** con **frase de enlace** («es un», «produce», «se divide en»), de una punta, dos puntas o sin puntas, y punteadas.
- **Doble clic** (o doble toque) en el lienzo crea un concepto; arrastrando el **punto azul** de un concepto hasta otro se conectan, y si se suelta en el vacío se crea un concepto nuevo ya conectado. **Tab** agrega un concepto hijo.
- Mover arrastrando, cambiar el tamaño desde la esquina, seleccionar varios con **Shift** + arrastrar, zoom con la rueda (o con dos dedos), deshacer y rehacer (**Ctrl+Z / Ctrl+Y**), duplicar (**Ctrl+D**).
- **Generar desde un tema**: arma un borrador con los conceptos del tema. Con IA, el borrador trae frases de enlace basadas en el texto; sin IA, toma los conceptos clave y usa como enlace las palabras que los unen en una misma oración. Después lo corregís vos: completar y discutir las relaciones es lo que hace que sirva para estudiar.
- Se guarda solo y se descarga como **PNG** o **SVG**.

### Saltá y Aprendé (juego)
Un juego de plataformas original, en un mundo de hojas de cuaderno: un estudiante con birrete corre y salta, junta hojas y esquiva a los «Olvidos» (manchas violetas) y a las «Distracciones» (burbujas rojas), a los que puede pisar.
- Cada **bloque de idea** (amarillo, con una lamparita) es una **pregunta de tus temas** (opción múltiple, verdadero o falso, o completar con opciones). Si acertás ganás puntos y un escudo; si te equivocás perdés una vida.
- Al final de cada nivel está el **examen final**: una pregunta más para pasar al siguiente nivel, que es más largo y difícil.
- **Las respuestas cuentan de verdad**: se corrigen igual que en la práctica y alimentan el repaso espaciado; las que fallás quedan en **Mis errores**, y al terminar podés practicarlas.
- Se eligen los temas y la dificultad de las preguntas; se guarda tu récord por temas.
- Controles: flechas o A/D para moverse, Espacio o ↑ para saltar (mantenerlo para saltar más alto), P para pausa, 1 a 4 para responder. En el celular aparecen botones en pantalla (conviene ponerlo horizontal).

### Videos de YouTube recomendados
En cada tema, la pestaña **Videos** muestra videos que explican el tema (se descartan los Shorts y los de menos de 2 minutos y medio), más enlaces para buscar en YouTube cada parte del tema. La ficha de cada concepto («¿por qué?») tiene un botón **Ver videos en YouTube** y, al buscar un tema nuevo, aparece el enlace a los videos sobre esa búsqueda. Los videos encontrados también se incluyen en el **apunte en PDF**, con su enlace.

Con Docker no hace falta ninguna clave: los videos se buscan con el metabuscador **SearXNG** que se levanta junto con la app. Si querés resultados de la API oficial de YouTube, o usás la app sin Docker, se puede cargar alguna de estas claves (en **Ajustes → Buscadores con clave**); se usa la primera disponible:
1. **YouTube Data API v3** (gratis, 100 búsquedas por día): en https://console.cloud.google.com/apis/library/youtube.googleapis.com activá la API y creá una clave en *Credenciales*. La clave de Gemini sirve solo si le habilitás también esa API.
2. **SerpApi**, **Serper**, **Brave Search** o **Tavily**, si ya tenés alguna.

Sin ninguna clave igual tenés los enlaces de búsqueda en YouTube. Los videos de cada tema se guardan; **Buscar otros** vuelve a buscar.

### Nivel de complejidad de las preguntas
| Nivel | Qué pide |
|---|---|
| Básico | Reconocer: verdadero o falso y opción múltiple. |
| Intermedio | Recordar sin opciones: completar y definir. |
| Avanzado | Explicar causas (“¿por qué?”) y relacionar dos conceptos del texto, sin pistas. |
| Mixto | Todo combinado. |

Se elige en la página de cada tema y en la práctica intercalada; la app lo recuerda. Si no hay suficientes preguntas del nivel pedido, completa con el más cercano.

### Conceptos clicables: «¿por qué?»
En la pestaña **Leer** de cada tema, los conceptos clave aparecen subrayados con puntos. Al tocarlos se abre una ficha con:
- lo que dice la fuente sobre ese concepto (la oración que lo define y dónde más aparece);
- **por qué**: con IA activada, una explicación con qué es, por qué es así, un ejemplo y con qué se relaciona (basada en las oraciones de la fuente y guardada para no volver a gastar); sin IA, las oraciones de la fuente que dan la causa;
- un botón para practicar ese concepto.

Además, después de cada respuesta hay un botón **«¿Por qué es así?»** que explica la respuesta correcta (con IA) o muestra el contexto de la fuente.

### Preguntas escritas por IA (recomendado)
Con una clave de Gemini o Claude, la IA redacta el banco de preguntas de **todo** el tema (en bloques), con reglas de examen: preguntas con sus propias palabras (nunca oraciones copiadas ni espacios para completar), niveles 1 a 3, opciones incorrectas que son errores conceptuales plausibles y una explicación de cada respuesta. Cada pregunta pasa controles automáticos antes de guardarse: la cita que la respalda tiene que existir en la fuente, no puede copiar tramos largos del texto, la opción múltiple tiene que tener 4 opciones distintas con la correcta incluida, sin «todas/ninguna de las anteriores».

Cuando un tema tiene suficientes preguntas de IA, las automáticas se ocultan (sin borrar tu progreso); se puede cambiar en **Ajustes → Qué preguntas mostrar**. En temas creados antes, usá **Generar preguntas con IA** en la página del tema. Para mejores preguntas conviene un modelo más capaz que el «lite» (por ejemplo `gemini-3.6-flash`).

### Preguntas de opción múltiple conceptuales
Además de las de completar (nivel básico), la app arma preguntas que validan ideas completas (nivel intermedio):
- **«¿Cuál de estas afirmaciones es correcta?»** / **«¿cuál es INCORRECTA?»**: las opciones falsas son oraciones reales del tema con un dato cambiado por otro verosímil (por ejemplo, «fase luminosa» por «fase oscura», un año o un nombre por otro).
- **«¿Por qué…?»** con causas reales de otras partes del tema como distractores.
- Con IA: preguntas de aplicación y razonamiento cuyos distractores son errores conceptuales típicos, con explicación incluida.

Para sumar este tipo de preguntas a un tema creado antes, usá **Generar preguntas nuevas** en la pestaña Fuentes (no borra tu progreso).

### Guardar como PDF
Desde cada tema, **Guardar PDF** abre un panel con tres opciones de contenido:
- **Apunte**: todo el material generado o importado, ordenado por secciones con índice; lo que **resaltaste** aparece marcado en amarillo, se agregan **tus resúmenes** y un **glosario** con las explicaciones de los conceptos que abriste con «¿por qué?». Si el material lo escribió la IA, el PDF lo indica.
- **Apunte + preguntas y respuestas**: lo anterior y, al final, las preguntas con su respuesta y la evidencia en la fuente.
- **Solo preguntas y respuestas**, filtradas por nivel, en dos formatos:
  - **Examen**: preguntas con espacio para responder y la clave de respuestas al final (para practicar en papel).
  - **Guía de estudio**: cada pregunta con su respuesta y la oración de la fuente que la respalda.

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

### Áreas de búsqueda
Al buscar, elegís un área y la app consulta las fuentes más útiles para esa área (se pueden ajustar en **Fuentes de esta búsqueda**):

| Área | Dónde busca |
|---|---|
| Programación | Wikipedia, Wikilibros, Stack Overflow (español e inglés), arXiv (computación) y la web |
| Redes | Wikipedia, Wikilibros, Network Engineering y Server Fault (Stack Exchange), arXiv (redes) y la web |
| Matemática | Wikipedia, Wikilibros, Wikiversidad, Mathematics (Stack Exchange) y arXiv (matemática) |
| Bases de datos | Wikipedia, Wikilibros, Stack Overflow, Database Administrators (Stack Exchange) y arXiv (bases de datos) |
| Sistemas operativos | Wikipedia, Wikilibros, Unix & Linux y Super User (Stack Exchange) y arXiv (sistemas operativos) |
| Ciencias y salud | Wikipedia, OpenAlex, Europe PMC y la web |
| Otros | Cualquier tema: enciclopedias, libros de texto, OpenAlex y la web |

Con las claves de Serper o SerpApi, cada área suma también **Google** (y Matemática y Ciencias, **Google Académico**); Redes, Matemática, Sistemas operativos y Otros suman **Google Libros**.

En los buscadores web (Google, Tavily, Brave) el área se agrega como contexto a la búsqueda, para que «árbol» en Programación traiga estructuras de datos y no botánica.

### Buscar en toda la web (sin claves)
Al iniciar con Docker (`iniciar.bat` o `docker compose up -d --build`) se levanta también **SearXNG**, un metabuscador libre que corre en tu computadora y consulta **a la vez Google, Bing, DuckDuckGo, Brave, Qwant, Startpage, Mojeek, Wikipedia y muchos más**, sin claves ni cuentas. En el buscador aparece como:
- **Toda la web (SearXNG)**: búsqueda general; cada resultado indica en qué buscadores apareció.
- **Programación en toda la web**: GitHub, Stack Overflow, documentación técnica y más.
- **Ciencia en toda la web**: Google Académico, arXiv, PubMed y más.

También recomienda **videos de YouTube** en cada tema sin necesidad de clave. SearXNG solo es accesible desde la app (no abre ningún puerto en tu red). Su configuración está en `searxng/settings.yml`; si algún buscador interno deja de responder por un rato (Google a veces corta las consultas automáticas), los demás siguen funcionando.

> En Render (plan gratuito) no corre SearXNG porque es un segundo servicio. Ahí se puede usar la variable `SEARXNG_URL` apuntando a una instancia propia de SearXNG con formato JSON activado.

Otras fuentes de toda la web: **Marginalia** (buscador independiente de blogs y apuntes personales), **Hacker News** (artículos de tecnología) y, con clave, **Exa** (búsqueda por significado, US$10 de crédito gratis por mes).

### Fuentes

- **Fuentes integradas** (se buscan todas a la vez, con su API oficial y licencia libre):
  - **Wikipedia** en español e inglés, y **Simple English Wikipedia** (explicaciones más sencillas);
  - **Wikilibros** y **Wikibooks**: libros de texto y manuales escritos de forma colaborativa;
  - **Wikiversidad**: cursos y material didáctico.
- **Académicos (sin clave)**: **OpenAlex** (artículos de todo el mundo: resumen y, si es de acceso abierto, el texto), **Semantic Scholar**, **Crossref**, **DOAJ** (revistas de acceso abierto, con mucho material en español; si la revista publica el texto en la web, se importa completo), **arXiv** (computación, matemática y física: resumen y versión HTML cuando existe) y **Europe PMC** (biología y salud: resumen).
- **Libros (sin clave)**: **Google Libros** y **Open Library** (Internet Archive): se importa la descripción del libro.
- **Programación (sin clave)**: **MDN Web Docs** (documentación web en español), **Stack Overflow en español**, **Stack Overflow** y otros sitios de Stack Exchange: Computer Science, Software Engineering, Code Review, Data Science, Network Engineering, Server Fault, Unix & Linux, Super User, Information Security, Database Administrators, Mathematics, Cross Validated (estadística), Electrical Engineering y Physics. Se importa la pregunta con sus respuestas más votadas (licencia CC BY-SA).
- **Google** (grupo propio en el buscador):
  - **Google (vía Gemini)**: si configuraste una clave de Gemini (ver abajo).
  - **Google (Serper)** y **Google Académico (Serper)**: clave gratuita de https://serper.dev (2.500 búsquedas al registrarte, sin tarjeta).
  - **Google (SerpApi)** y **Google Académico (SerpApi)**: clave gratuita de https://serpapi.com (250 búsquedas por mes, sin tarjeta).
  - **Google Libros**: sin clave; importa la descripción del libro (solo los que tienen una descripción suficiente).
  - La API oficial de Google (*Custom Search JSON API*) no se incluye porque Google la cerró a clientes nuevos y la da de baja en enero de 2027.
- **Web con clave** (se cargan en Ajustes → Buscadores con clave): **Tavily** (1.000 búsquedas gratis por mes, sin tarjeta), **Brave Search** y **Web (vía Claude)**, que usa la búsqueda web de la API de Claude (se cobra aparte: US$10 cada 1.000 búsquedas).
- La app recuerda qué buscadores dejaste marcados.
- **Google** (si configuraste una clave de **Gemini**): la búsqueda usa la herramienta de búsqueda de Google de Gemini y muestra las páginas encontradas para importarlas. Se muestran las sugerencias de búsqueda de Google, como exige su servicio. Google cobra estas búsquedas aparte del modelo (tiene una cuota mensual gratuita).
- **Generar con IA**: escribís el tema, el nivel y un enfoque opcional; la IA busca primero en Wikipedia, Wikilibros y Wikiversidad y escribe un **apunte basado en esos textos**. Las fuentes originales quedan guardadas en el tema y las preguntas se generan tanto del apunte como de las fuentes. El tema queda marcado como «apunte generado con IA».
- **Cualquier página web** por su dirección: documentación, artículos, apuntes publicados. La app sugiere sitios recomendados (MDN, documentación de Python, cppreference, SciELO, Educ.ar, OpenStax). Las páginas que piden iniciar sesión o se arman con JavaScript no se pueden importar; en ese caso, copiá el texto y pegalo como apuntes.
- En los wikis se guarda la **revisión exacta** del artículo, así cada corrección se hace contra ese texto aunque cambie después. Se descartan secciones como Referencias, Enlaces externos o Véase también.
- **Cada pregunta está anclada a una oración** del texto descargado. Al corregir se muestra esa oración como evidencia.
- **Corrección**:
  - opción múltiple y verdadero/falso: exacta;
  - completar: tolera acentos, mayúsculas y errores de tipeo menores; los años y números deben ser exactos;
  - respuestas abiertas: compara los conceptos de tu respuesta con los de la fuente y te dice cuáles faltaron.
- **Tus apuntes**: si estudiás desde texto propio, la app compara contra lo que pegaste. Conviene que esté revisado.

Límites a tener en cuenta: la generación de preguntas y la corrección de respuestas abiertas son automáticas y se basan en el texto, no en entender el significado. Alguna pregunta puede salir rara o una respuesta correcta dicha con otras palabras puede marcarse como parcial; para eso está la autocorrección. Wikipedia es una buena puerta de entrada, pero para un examen siempre contrastá con la bibliografía de la materia.

### Modo IA (opcional): Claude o Gemini

Si tenés una clave de API de **Claude** (Anthropic) o de **Gemini** (Google), cargala en **Ajustes**: elegís el proveedor, pegás la clave, opcionalmente el modelo, y tocás **Probar conexión**. También se puede poner en el archivo `.env` (ver `.env.example`). Con eso:

- las respuestas abiertas se corrigen por significado, siempre contra el fragmento de la fuente;
- al crear un tema se suman preguntas de comprensión generadas por IA. **Cada pregunta debe citar un fragmento literal del artículo; si la cita no aparece en el texto descargado, se descarta.**

Dónde sacar la clave:
- **Claude**: https://platform.claude.com → API Keys. Se paga aparte de la suscripción de claude.ai.
- **Gemini**: https://aistudio.google.com/apikey → Get API key, en un proyecto con facturación activada. La suscripción Google AI Pro no incluye la API.

Los modelos más baratos (`claude-haiku-5-5`, `gemini-3.5-flash-lite`) alcanzan para esta app. Solo se consulta a la IA al corregir respuestas abiertas y al crear temas; las preguntas de opción múltiple, verdadero o falso y completar nunca la usan.

Sin clave, todo lo demás funciona igual.

---

## Cuentas e inicio de sesión

La app pide **usuario y contraseña**. Cada cuenta tiene su propia base de datos (`data/usuarios/<id>.db`): nadie puede ver los temas, tareas ni el progreso de otro. La primera cuenta que se crea **hereda los temas que ya tenías** antes de que existiera el login.

Cómo se protege:
- **Sin inyección SQL**: todas las consultas usan parámetros (`?`) de SQLite, así que lo que se escribe en usuario o contraseña nunca se mezcla con el SQL. Además, el usuario solo admite letras, números, punto, guion y guion bajo. Hay pruebas automáticas que intentan entrar con `' OR '1'='1`, `admin'--`, `; DROP TABLE users` y otras y verifican que fallan sin romper nada.
- **Contraseñas con scrypt** y sal aleatoria: en la base nunca queda la contraseña, solo un hash lento de calcular.
- **Sesión en cookie `HttpOnly` y `SameSite=Lax`** (y `Secure` cuando se usa https): JavaScript no puede leerla y otros sitios no pueden usarla. En la base se guarda solo el hash del token; dura 30 días o hasta que tocás **Salir**.
- **Límite de intentos**: 5 contraseñas incorrectas seguidas bloquean ese usuario por 15 minutos (y 20 por dirección IP).
- La respuesta tarda lo mismo si el usuario no existe, para no revelar qué cuentas hay.

En **Ajustes → Tu cuenta** podés cambiar la contraseña (cierra las otras sesiones abiertas).

**¿Olvidaste la contraseña?** No hay recuperación por correo. Quien administra el servidor la puede cambiar desde la terminal:

```bash
docker compose exec estudio python -m app.auth usuarios          # lista las cuentas
docker compose exec estudio python -m app.auth reset TU_USUARIO  # pide la nueva contraseña
```

Variables de entorno (en `.env` o en Render):
- `ALLOW_SIGNUP=0`: nadie más puede crear cuentas (la primera siempre se puede crear). Útil si la publicás y querés que sea solo para vos y quienes vos crees.
- `AUTH=0`: desactiva el login (vuelve al funcionamiento anterior, sin cuentas). Solo para uso local.

---

## Subirla a GitHub

Necesitás **Git** (https://git-scm.com/download/win) y una cuenta en GitHub. El archivo `.gitignore` ya excluye la carpeta `data/` (tus bases de datos y cuentas) y el archivo `.env` (tus claves): **nunca los subas**.

**Si ya la habías subido antes** (actualizar el repositorio): copiá los archivos nuevos encima de la carpeta del repositorio, y en una terminal dentro de esa carpeta:

```bash
git status                      # revisá que NO aparezcan data/ ni .env
git add .
git commit -m "Login seguro, áreas de búsqueda y apunte en PDF"
git push
```

**Si es la primera vez**: creá un repositorio vacío en https://github.com/new (sin README) y después:

```bash
git init
git add .
git status                      # revisá que NO aparezcan data/ ni .env
git commit -m "Estudio Dunlosky"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/estudio-dunlosky.git
git push -u origin main
```

La primera vez que hagas `push`, Windows abre una ventana para iniciar sesión en GitHub.

Si por error subiste una clave, borrarla del repositorio no alcanza (queda en el historial): **revocala** en la página del proveedor y creá otra.

---

## Publicarla en internet (Render)

El repositorio incluye `render.yaml`, que Render lee solo. En Render: **New → Blueprint**, elegís este repositorio y confirmás. Queda en un link `https://estudio-dunlosky-xxxx.onrender.com`.

Si ya estaba publicada, Render se actualiza sola cada vez que hacés `git push` (tarda unos minutos).

En esa versión se activa el **modo público** (`PUBLIC_MODE=1`):
- cada persona crea su cuenta y tiene su propio espacio: nadie ve los temas de otro;
- la clave de IA no se puede cargar ni cambiar desde la interfaz (solo como variable de entorno en Render, y la pagarías vos), así que no conviene ponerla en una versión abierta a cualquiera;
- si querés que solo entren las personas que vos invites, agregá en Render la variable `ALLOW_SIGNUP=0` después de crear las cuentas.
- para que la versión publicada recomiende videos, agregá en Render (*Environment*) la variable `GOOGLE_API_KEY` con tu clave de YouTube Data API (la cuota diaria es compartida entre todos los que la usen). Lo mismo con `SERPER_API_KEY` o `SERPAPI_API_KEY` para los buscadores de Google.

Límites del plan gratuito: el servicio se duerme tras unos minutos sin visitas y tarda alrededor de un minuto en despertar, y **el disco no es permanente**: cuando Render reinicia el servicio (por ejemplo, en cada `git push`) se borran las cuentas y los temas. Para conservarlos hace falta un plan pago con disco persistente montado en `/data`.

## Tus datos

Se guardan en la carpeta **`data`** (SQLite): `auth.db` tiene las cuentas (contraseñas con hash) y `usuarios/` una base por cuenta con sus temas y progreso. Para hacer una copia de seguridad, copiá esa carpeta. Borrar el contenedor o la imagen de Docker no borra tus datos.

## Cambiar el puerto

Si el 8000 está ocupado, copiá `.env.example` como `.env` y cambiá `PUERTO=8000` por otro (por ejemplo `8080`). Luego abrí `http://localhost:8080` (el `iniciar.bat` abre el 8000; cambialo ahí también si querés).

---

## Estructura del proyecto

```
estudio-dunlosky/
├── app/
│   ├── main.py        API (FastAPI): temas, sesiones, corrección, técnicas, panel
│   ├── auth.py        Cuentas, contraseñas (scrypt), sesiones y límite de intentos
│   ├── sources.py     Wikis (búsqueda y descarga), páginas web por URL y apuntes propios
│   ├── search_providers.py  OpenAlex, arXiv, Europe PMC, Stack Exchange, Google (Serper, SerpApi, Libros), Tavily, Brave y áreas
│   ├── videos.py      Videos de YouTube recomendados (YouTube Data API, SearXNG, SerpApi, Serper, Brave, Tavily)
│   ├── export_pdf.py  Apunte y cuestionarios en PDF
│   ├── textproc.py    Oraciones, normalización, palabras y oraciones clave
│   ├── generator.py   Generación de preguntas ancladas a la fuente
│   ├── grader.py      Corrección de respuestas, resúmenes, subrayados y explicaciones
│   ├── srs.py         Repetición espaciada (SM-2)
│   ├── ai.py          Modo IA opcional (con verificación de citas)
│   ├── db.py          Esquema y acceso a SQLite
│   └── static/        Interfaz sin frameworks: index.html, styles.css, app.js,
│                      pomodoro.js (temporizador y sonidos), tasks.js (tareas), concepts.js (fichas «¿por qué?»)
│                      notes.js (bloc de notas y nota rápida), maps.js (mapas conceptuales)
│                      y game.js (juego Saltá y Aprendé)
├── searxng/           Configuración del buscador de toda la web (SearXNG)
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
- **El Bloc de notas volvía al inicio o no aparecía el botón de nota rápida**: el navegador mezclaba archivos nuevos con otros viejos guardados en caché después de actualizar. Desde esta versión cada archivo lleva su número de versión y se descarga siempre el correcto. Si te pasa con la versión anterior, recargá con `Ctrl + F5`.
- **El pomodoro quedaba en 00:01 o decía que ya estaba iniciado**: corregido en esta versión. Si el navegador había guardado un estado trabado, se limpia solo al abrir la app.
- **Pide iniciar sesión otra vez**: la sesión dura 30 días; también se cierra al cambiar la contraseña. En Render gratis, cada reinicio borra las cuentas (ver más arriba).
- **«Demasiados intentos fallidos»**: esperá 15 minutos o cambiá la contraseña desde la terminal (sección *Cuentas*).
- **Docker pide activar WSL 2 o la virtualización**: seguí el asistente de Docker Desktop; es un requisito de Docker en Windows.
