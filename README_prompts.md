# SQListo: instrucciones editables de la IA local

Las instrucciones que SQListo envía al modelo se encuentran en tres archivos
de texto. Puedes editar su redacción, el papel asignado al modelo, los criterios
de selección y los ejemplos sin modificar los módulos científicos de Python.
Esta separación conserva inicialmente el texto de los prompts de `main`
en el commit `f3b557e20cbf2b5cfa2cbd3978600135533dfffa`.

## Qué archivo editar

| Archivo | Función |
|---|---|
| `prompts/router.txt` | Elegir una acción y sus argumentos; devuelve un objeto JSON. |
| `prompts/sql_generation.txt` | Traducir la pregunta a una consulta SQLite de lectura. |
| `prompts/sql_repair.txt` | Corregir una consulta utilizando el error real de SQLite. |
| `sqlisto_knowledge.txt` | Manual semántico que se incluye en generación y reparación de SQL. |
| `sqlisto_tools.txt` | Manual de herramientas que carga el agente; el router compacto no lo incluye en su prompt. |

Para cambiar las instrucciones de selección de herramientas, edita
`prompts/router.txt`. Editar únicamente `sqlisto_tools.txt` no modifica lo que
recibe el router. Las opciones de los manuales se conservan: `--sql-knowledge`
y `--tools-file` en el agente, y `--knowledge` en el asistente SQL.

`sqlisto_prompts.py` lee las plantillas e inserta la pregunta, el catálogo y el
esquema de la base de datos. Las funciones `build_router_prompt()`,
`build_prompt()` y `build_repair_prompt()` siguen disponibles desde sus módulos
originales. El servidor local y la alternativa `llama-cli` reciben los prompts
por las mismas vías que antes.

## Cómo editar las instrucciones

Puedes reformular el rol del modelo, traducir las instrucciones, aclarar cuándo
elegir una herramienta o añadir ejemplos de preguntas y respuestas válidas.
Mantén el formato que espera el programa:

- El router debe devolver un único objeto JSON con `action` y `arguments`.
  Conserva los nombres de las acciones y de sus argumentos.
- Las plantillas SQL deben pedir una única consulta SQLite de lectura que use
  las tablas y columnas del esquema suministrado.
- Conserva las variables `${...}` y los delimitadores de conversación
  `<|im_start|>` y `<|im_end|>`.

El idioma de las instrucciones y de las preguntas puede cambiar; las claves JSON,
los identificadores de acciones y los nombres SQL mantienen su forma técnica.
Las respuestas del router y del generador SQL son entradas para el programa,
por lo que añadir explicaciones o cambiar su formato puede impedir su lectura.

Añadir una acción nueva requiere también implementarla y validarla en Python.
Modificar un prompt no añade una función de análisis ni cambia las operaciones
de fragmentación, cinética, espectros o exportación.

### Variables de cada plantilla

| Plantilla | Variables necesarias |
|---|---|
| `router.txt` | `${catalog_json}`, `${question}` |
| `sql_generation.txt` | `${knowledge_section}`, `${schema}`, `${question}` |
| `sql_repair.txt` | `${knowledge_section}`, `${schema}`, `${question}`, `${rejected_sql}`, `${sqlite_error}` |

Usa archivos UTF-8. Escribe las llaves de los ejemplos JSON normalmente y un
dólar literal como `$$`. La sustitución se realiza una sola vez: los dólares
y las llaves que ya contengan la pregunta, el esquema o el manual se conservan.
El programa comprueba que estén presentes las variables necesarias y que no
haya variables desconocidas antes de enviar el prompt al modelo.

Las plantillas se leen cada vez que se construye un prompt. Su ruta es relativa
a `sqlisto_prompts.py`, no al directorio desde el que ejecutas el comando.
Tras guardar una edición, la siguiente construcción del prompt usa ese texto;
no hace falta reiniciar `llama-server` ni descargar de nuevo el modelo.

## Probar una edición con la base de demostración

Desde la raíz del repositorio, activa el entorno y arranca el servidor local:

```bash
source .venv/bin/activate
bash start_sqlisto_llama_server.sh
```

En otra terminal, situada también en la raíz del repositorio:

```bash
source .venv/bin/activate
python sqlisto_agent.py DBs/azc_dfcz_ub3_z3.db \
  "Muestra las reacciones finales más frecuentes de Azaconazole con método uB3LYP y energía ZPEx3." \
  --force-router --show-plan --show-backend --lang es --no-llama-fallback
```

Esta petición corresponde a `reaction_summary` y usa etiquetas de la base de
demostración. Revisa el plan mostrado para comprobar la acción y los filtros
que propuso el modelo. `--no-llama-fallback` permite comprobar específicamente
la conexión con el servidor que acabas de arrancar.

Algunas preguntas se resuelven mediante rutas deterministas y no utilizan los
prompts del modelo. `--force-router` obliga a consultar al LLM para seleccionar
la acción, pero no obliga a generar SQL con el LLM: una acción `sql_query`
todavía puede resolverse mediante el generador SQL determinista.

El [tutorial práctico](docs/AI_TUTORIAL.md) contiene más ejemplos con la base
de demostración, sus resultados de referencia y los comandos de exportación.

## Distribución y comprobaciones

Las tres plantillas y `sqlisto_prompts.py` forman parte del repositorio y se
obtienen al clonarlo o actualizarlo. `install.sh` utiliza esos mismos archivos;
esta reorganización no añade dependencias ni requiere otra base de datos.

Para ejecutar las comprobaciones de las plantillas:

```bash
python -m unittest discover -s tests -p 'test_prompts.py' -v
```

Para ejecutar todas las pruebas del repositorio:

```bash
python -m unittest discover -s tests -v
```

Las comparaciones con los prompts originales comprueban que la separación de
archivos conserva sus instrucciones. Una edición deliberada de esas
instrucciones puede hacer fallar esa comparación: revisa el cambio de texto y
su comportamiento antes de actualizar la referencia de la prueba.

Para comprobar además la instalación con el modelo y la base de demostración,
usa `bash scripts/smoke_test.sh` y los ejemplos del tutorial.
