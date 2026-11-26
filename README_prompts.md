# SQListo: prompts separados

Esta versión separa las instrucciones del LLM del código de ejecución.
Parte de `xyz2db_sqllisto_source(1).zip`, compartido el 10 de octubre de 2026.
El texto enviado al modelo, las acciones permitidas y las funciones de análisis
se mantienen. La reorganización no requiere cambiar la base de datos ni el modelo.

## Qué archivo controla cada interacción

| Archivo | Función |
|---|---|
| `prompts/router.txt` | Elegir una acción y sus argumentos; devuelve un objeto JSON. |
| `prompts/sql_generation.txt` | Traducir la pregunta a una consulta SQLite de lectura. |
| `prompts/sql_repair.txt` | Corregir una consulta utilizando el error real de SQLite. |
| `sqlisto_prompts.py` | Leer las plantillas, comprobar sus variables e insertar el contexto. |
| `sqlisto_knowledge.txt` | Manual semántico incluido en generación y reparación de SQL. |
| `sqlisto_tools.txt` | Manual de herramientas que ya cargaba el agente. El router compacto no lo inserta en el prompt. |

Los dos manuales conservan su ubicación y sus opciones de línea de comandos
para mantener la compatibilidad: `--sql-knowledge`, `--knowledge` y `--tools-file`.
Para cambiar las instrucciones que recibe el router, edita `prompts/router.txt`.
Editar únicamente `sqlisto_tools.txt` no cambia esas instrucciones.

## Cómo se conecta con el programa

1. `sqlisto_agent.py` aplica las rutas deterministas existentes o solicita un
   plan al LLM mediante `build_router_prompt()`.
2. El programa valida y normaliza la acción elegida. Los identificadores
   permitidos siguen definidos en `ALLOWED_ACTIONS` y las llamadas a las
   funciones siguen en `execute_action()`.
3. Para consultas SQL que requieren el modelo, `xyz2db_assistant.py` utiliza
   `build_prompt()`. Si SQLite rechaza la consulta, utiliza
   `build_repair_prompt()` y conserva el ciclo de reparación existente.
4. Las operaciones de fragmentación, cinética, espectros y exportación siguen
   ejecutándose en Python. Los prompts no contienen ni ejecutan sus algoritmos.

Los nombres y argumentos de las tres funciones se mantienen. También siguen
disponibles desde los módulos originales para no romper otros scripts que
las importen. Los envíos a `llama-server` y la alternativa `llama-cli` no cambian.

Las copias de `agentes_IA_funcionan/` y el cuaderno son material histórico del
paquete original. No se han modificado y no importan automáticamente los nuevos
prompts. Los puntos de entrada activos son los dos asistentes de la raíz y
`main.py` para las herramientas de XYZ2DB.

## Variables de las plantillas

Las plantillas son archivos UTF-8. Se utiliza la sintaxis `${nombre}`:

| Plantilla | Variables necesarias |
|---|---|
| `router.txt` | `${catalog_json}`, `${question}` |
| `sql_generation.txt` | `${knowledge_section}`, `${schema}`, `${question}` |
| `sql_repair.txt` | `${knowledge_section}`, `${schema}`, `${question}`, `${rejected_sql}`, `${sqlite_error}` |

El programa obtiene el esquema y el catálogo de la base consultada. No hay que
copiarlos manualmente en las plantillas. Las llaves de los ejemplos JSON se
escriben normalmente; un dólar literal en el archivo se escribe `$$`.
La sustitución se realiza una sola vez: las llaves y dólares que ya contenga
la pregunta, el esquema o el manual se conservan literalmente. Esto no añade
una defensa frente a instrucciones maliciosas; los controles de SQL y acciones
siguen siendo los del programa original.

Conserva las variables necesarias y los delimitadores de conversación
`<|im_start|>` / `<|im_end|>`. Si falta una plantilla o hay una variable errónea,
el programa indica el archivo afectado antes de solicitar una respuesta al modelo.
Las plantillas se leen en cada construcción del prompt, tomando su ruta relativa
a `sqlisto_prompts.py`, no al directorio desde el que se ejecuta el comando.
No hace falta reiniciar `llama-server` después de editar el texto.

## Instalar los cambios

El ZIP contiene la carpeta `Capitulo_4_SQListo`. Para actualizar tu instalación,
copia de ella:

- `sqlisto_agent.py` y `xyz2db_assistant.py`, sustituyendo esas dos versiones;
- `sqlisto_prompts.py` y la carpeta `prompts/`, que son nuevos;
- `tests/` y este README, si quieres ejecutar las comprobaciones.

Conserva tus manuales, bases de datos, archivos GGUF y configuración local.
El paquete incluye los demás archivos fuente originales, pero no incorpora
la base de producción ni los pesos del modelo. Se han omitido cachés y
checkpoints automáticos del ZIP de entrega.

Los comandos habituales se mantienen. Ejemplo desde tu directorio de trabajo:

```bash
cd ~/Escritorio/Capitulo_4_SQListo
python sqlisto_agent.py "$SQLISTO_DB" \
  "¿Cuántas trayectorias hay por molécula?" \
  --show-plan --show-sql --lang es
```

Esta consulta puede utilizar la ruta determinista. Para comprobar también
el router con tu modelo ya disponible:

```bash
python sqlisto_agent.py "$SQLISTO_DB" \
  "Busca el fragmento final C2H3N3 de Azaconazole PM6 ZPEx3" \
  --force-router --show-plan --lang es
```

## Verificación realizada

```bash
python -m unittest discover -s tests -v
```

Se ejecutaron 17 pruebas con Python 3.12 y las dependencias del programa.
No se añadió ninguna dependencia de ejecución. Las pruebas utilizan `unittest`,
incluido en Python, junto con NumPy y pandas, ya utilizados por SQListo.

- Siete combinaciones de argumentos generan exactamente los mismos prompts
  que el código original, incluidos saltos de línea, Unicode y ejemplos JSON.
- Se comprobó mediante AST que el resto de la lógica de los dos asistentes
  no cambia. Los módulos científicos de `xyz2db/` se conservan byte a byte.
- Se prueban consultas reales a SQLite y la reparación a partir de un error
  real de columna inexistente; se mantiene el rechazo de SQL de escritura.
- Se comprueba la conexión del router con una búsqueda real de fragmentos y
  con el cálculo cinético sobre tres trayectorias sintéticas comprimidas:
  dos eventos, una censura y un descriptor de 0.2 ps^-1.
- Se verifica el envío del prompt al servidor, la alternativa CLI y el arranque
  desde un directorio distinto.
- Se detectan plantillas ausentes y variables incorrectas antes de llamar al modelo.

Las respuestas del LLM y del servidor se simulan en estas pruebas. La base de
ejemplo y las funciones de análisis son reales. Esto verifica la integración,
pero no evalúa la calidad de las decisiones de Qwen ni sustituye una ejecución
con tu GGUF y tu base de producción.

`tests/fixtures/prompts_original.json` contiene las huellas de los prompts de
la versión de origen. Si cambias deliberadamente las instrucciones, la prueba
de igualdad avisará: ese cambio debe revisarse como un cambio de comportamiento,
no como una simple reorganización.

## Alcance de esta revisión

No se han traducido, ampliado ni corregido las reglas del modelo. Por ejemplo,
el router original repite algunas entradas de cinética y contiene una indicación
contradictoria de no recalcular dentro de la descripción de `global_kinetics`.
Se conserva en esta versión para no alterar simultáneamente la organización y
las decisiones del LLM. Las funciones Python siguen distinguiendo entre calcular
cinética y consultar resultados ya almacenados.
