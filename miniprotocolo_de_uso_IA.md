# Miniprotocolo de SQListo — Versión en español

Este protocolo describe la forma recomendada de hacer preguntas a SQListo en español utilizando tres moléculas de ejemplo:

- **Azaconazole** — sin isómero
- **Tebuconazole** — sin isómero
- **Metconazole, isómero cis** — molécula con un isómero explícito

Los ejemplos emplean los métodos `PM6` y `uB3LYP`, y la etiqueta energética `ZPEx3`.

---

## 1. Preparación básica

Define la base de datos:

```bash
export DB="/ruta/a/tu/base_de_datos.db"
```

Inicia `llama-server` en otra terminal:

```bash
~/llama.cpp/build/bin/llama-server \
  -m /home/alchemi20/Escritorio/Capitulo_4_SQListo/modelos_IA/qwen2.5-coder-1.5b/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  -c 8192 \
  --parallel 1 \
  --threads 3 \
  --threads-batch 3
```

Comprueba que el servidor está activo:

```bash
curl http://127.0.0.1:8080/health
```

Flags recomendados durante las pruebas:

```bash
--show-plan \
--show-sql \
--show-backend \
--no-llama-fallback \
--lang es
```

---

## 2. Estructura recomendada de las preguntas

Utiliza este orden siempre que sea posible:

```text
[ACCIÓN] + [OBJETO] + [MOLÉCULA/ISÓMERO] +
[MÉTODO] + [ENERGÍA] + [PARÁMETROS] + [SALIDA]
```

Ejemplo:

```text
Busca las trayectorias de PM6 para Metconazole,
isómero cis, a ZPEx3.
```

Para consultas de filas, estos verbos se interpretan de forma parecida:

```text
Lista...
Busca...
Muestra...
Encuentra...
Localiza...
```

Para moléculas con isomería, utiliza preferentemente la forma explícita:

```text
Metconazole, isómero cis
```

La forma abreviada también puede funcionar:

```text
Metconazole cis
```

---

# PARTE I — Consultas generales de la base de datos

## 3. Listar o buscar trayectorias

```bash
python sqlisto_agent.py \
  "$DB" \
  "Busca las trayectorias de PM6 para Metconazole,
  isómero cis, a ZPEx3." \
  --show-plan \
  --show-sql \
  --show-backend \
  --no-llama-fallback \
  --lang es
```

Ruta esperada:

```text
routing: deterministic_sql_bypass
SQL route: deterministic_metadata_trajectory_list
```

Columnas típicas de salida:

```text
traj_uid
traj_code
molecule
isomer
method_label
energy_label
nframes
```

Otros ejemplos:

```text
Lista las trayectorias de uB3LYP para Azaconazole a ZPEx3.
```

```text
Muestra las trayectorias de PM6 para Tebuconazole a ZPEx3.
```

---

## 4. Contar trayectorias

```text
Cuenta las trayectorias de Azaconazole calculadas con PM6 a ZPEx3.
```

```text
Cuenta las trayectorias agrupadas por molécula, isómero,
método y etiqueta energética.
```

---

## 5. Comprobar si existen registros

```text
Comprueba si existen trayectorias de PM6 para Metconazole,
isómero cis, a ZPEx3.
```

---

## 6. Agrupar, ordenar y calcular estadísticas

```text
Para Azaconazole, Tebuconazole y Metconazole cis a ZPEx3,
agrupa las trayectorias por molécula, isómero y método.
Muestra el número de trayectorias y la media,
el mínimo y el máximo número de frames.
```

---

## 7. Resumen general de la base de datos

```text
Dame un resumen general de la base de datos.
```

Ejemplo filtrado:

```text
Dame un resumen de la base de datos para Azaconazole a ZPEx3.
```

Acción del agente:

```text
database_summary
```

---

# PARTE II — Inputs almacenados

## 8. Mostrar el input almacenado de una trayectoria

La acción específica de inputs necesita un `traj_uid` exacto.

```bash
python sqlisto_agent.py \
  "$DB" \
  "Muéstrame el input completo almacenado
  de la trayectoria traj_XXXXXXXX." \
  --show-plan \
  --lang es
```

Acción del agente:

```text
show_input
```

---

## 9. Restaurar el input almacenado como archivo

```bash
python sqlisto_agent.py \
  "$DB" \
  "Restaura el input almacenado
  de la trayectoria traj_XXXXXXXX." \
  --show-plan \
  --lang es
```

Acción del agente:

```text
restore_input
```

La relación utilizada es:

```text
trajectories.input_id -> md_inputs.input_id
```

La tabla de inputs puede contener:

```text
raw_input_text
energy_temperature_K
energy_kcal_mol
zpe_kcal_mol
dof
```

---

# PARTE III — Reacciones almacenadas

## 10. Mostrar las reacciones finales almacenadas más frecuentes

```text
Muestra las 20 reacciones finales almacenadas más frecuentes
para Azaconazole calculado con PM6 a ZPEx3.
```

Acción del agente:

```text
reaction_summary
```

---

## 11. Exportar las reacciones finales almacenadas a CSV

```text
Exporta a CSV todas las reacciones finales almacenadas
para Tebuconazole calculado con PM6 a ZPEx3.
```

Acción del agente:

```text
reaction_export_csv
```

---

# PARTE IV — Fragmentos almacenados y participación atómica

## 12. Buscar un fragmento almacenado

Por fórmula molecular:

```text
Busca trayectorias de Azaconazole calculadas con PM6 a ZPEx3
que contengan el fragmento almacenado C2H3N3.
```

Por relación masa/carga:

```text
Busca fragmentos almacenados cerca de m/z 69.0327
con una tolerancia de 0.001
para Tebuconazole calculado con PM6 a ZPEx3.
```

Acción del agente:

```text
fragment_search
```

---

## 13. Identificar los átomos numerados de un fragmento final

```text
Muestra qué átomos numerados forman
el fragmento final almacenado C2H3N3
para Azaconazole calculado con PM6 a ZPEx3.
```

Acción del agente:

```text
final_fragment_atoms
```

---

## 14. Consultar separación de enlaces por números de átomo

```text
Busca las trayectorias en las que los átomos 2 y 3
terminan en fragmentos finales almacenados diferentes
para Azaconazole calculado con PM6 a ZPEx3.
```

Acción del agente:

```text
final_fragment_bond_query
```

---

## 15. Consultar enlaces candidatos por par de elementos

```text
Lista los pares atómicos N-C que terminan
en fragmentos finales almacenados diferentes
para Metconazole, isómero cis,
calculado con PM6 a ZPEx3.
```

Acción del agente:

```text
final_fragment_bond_query
```

---

# PARTE V — Espectros de masas teóricos

## 16. Mostrar un espectro de masas teórico almacenado

```text
Genera el espectro de masas teórico almacenado
para Azaconazole calculado con PM6 a ZPEx3,
usando solo fragmentos cargados
y ordenando por m/z.
```

Acción del agente:

```text
mass_spectrum
```

Filtros opcionales:

```text
solo fragmentos cargados
solo fragmentos neutros
m/z mínimo
m/z máximo
escala de intensidad
ordenar por m/z
ordenar por intensidad
```

---

## 17. Exportar un espectro de masas teórico a CSV

```text
Exporta a CSV el espectro de masas teórico almacenado
para Tebuconazole calculado con uB3LYP a ZPEx3,
usando solo fragmentos cargados
y ordenando por m/z.
```

Acción del agente:

```text
mass_spectrum_export_csv
```

---

# PARTE VI — Cinética global y constante global k

Las siguientes expresiones se consideran equivalentes:

```text
cinética global
k global
constante global
constante cinética
```

Una condición cinética queda identificada por:

```text
molecule
isomer
method
energy_label
persist_frames
window_mode
min_points
```

En la versión actualizada, el orden entre `mínimo de puntos`
y `frames consecutivos` no debería importar.

---

## 18. Calcular y guardar una k global

Ejemplo para una molécula sin isómeros:

```bash
python sqlisto_agent.py \
  "$DB" \
  "Calcula y guarda la cinética global de Azaconazole,
  usando el método PM6 a ZPEx3,
  con 10 frames consecutivos,
  modo censor
  y un mínimo de 5 puntos de ajuste." \
  --show-plan \
  --show-backend \
  --no-llama-fallback \
  --timeout 600 \
  --lang es
```

Formulación equivalente:

```text
Calcula y guarda la k global de Azaconazole...
```

Acción del agente:

```text
global_kinetics
```

El resultado queda almacenado en la base de datos.

---

## 19. Calcular y exportar inmediatamente el resultado cinético completo

```bash
python sqlisto_agent.py \
  "$DB" \
  "Calcula y exporta la cinética global completa
  de Metconazole, isómero cis,
  usando el método uB3LYP a ZPEx3,
  con 10 frames consecutivos,
  modo censor
  y un mínimo de 5 puntos de ajuste.
  Incluye las estadísticas de resumen,
  los eventos individuales
  y todos los puntos de la curva de supervivencia." \
  --show-plan \
  --timeout 600 \
  --lang es
```

Acción del agente:

```text
global_kinetics_export_csv
```

Genera:

```text
*_summary.csv
*_events.csv
*_survival.csv
```

También almacena el resultado en la base de datos.

---

## 20. Regla de sustitución para cálculos cinéticos repetidos

Si coinciden estos campos:

```text
molecule
isomer
method
energy_label
persist_frames
window_mode
min_points
```

el resultado anterior se sustituye.

La sustitución afecta a:

```text
kinetics_global
kinetics_events
kinetics_survival_points
```

Por tanto, repetir exactamente la misma condición actualiza el resultado
almacenado en lugar de crear un duplicado.

---

## 21. Calcular varias condiciones

La acción de cálculo actual está diseñada para una condición cada vez.

Ejecuta por separado:

```text
Azaconazole — PM6 — ZPEx3
Tebuconazole — PM6 — ZPEx3
Metconazole — cis — PM6 — ZPEx3
```

No confíes en una sola frase con varias moléculas
para que se calculen secuencialmente.

---

## 22. Comparar cinéticas globales

Ejemplo comparando métodos:

```text
Compara la cinética global de PM6 y uB3LYP
para Azaconazole a ZPEx3,
usando 10 frames consecutivos,
modo censor
y un mínimo de 5 puntos de ajuste.
```

Acción del agente:

```text
compare_global_kinetics
```

La comparación puede hacerse por un campo disponible,
como método, molécula, isómero o etiqueta energética.

Para pedir salida CSV:

```text
Compara PM6 y uB3LYP para Azaconazole a ZPEx3,
usando 10 frames consecutivos,
modo censor
y un mínimo de 5 puntos de ajuste.
Exporta la comparación a CSV.
```

---

# PARTE VII — Consultar y exportar resultados cinéticos almacenados

Estas acciones no vuelven a analizar los frames.

Utiliza esta frase para dejarlo claro:

```text
No recalcules nada.
```

---

## 23. Mostrar una k almacenada

```bash
python sqlisto_agent.py \
  "$DB" \
  "Muestra la k global almacenada de Azaconazole,
  usando el método PM6 a ZPEx3,
  con 10 frames de persistencia,
  modo censor
  y un mínimo de 5 puntos de ajuste.
  No recalcules nada." \
  --show-plan \
  --lang es
```

Acción del agente:

```text
stored_kinetics_summary
```

---

## 24. Mostrar un resumen cinético almacenado para varias moléculas

Primero calcula cada condición por separado. Después pregunta:

```text
Resume las constantes cinéticas almacenadas para
Azaconazole, Tebuconazole y Metconazole cis,
a ZPEx3, para PM6 y uB3LYP,
usando 10 frames de persistencia,
modo censor
y un mínimo de 5 puntos de ajuste.
No recalcules nada.
```

Acción del agente:

```text
stored_kinetics_summary
```

Posibles columnas de salida:

```text
molecule
isomer
method
energy_label
energy_temperature_K
energy_kcal_mol
persist_frames
window_mode
min_points
n_trajectories
n_events
n_censored
event_fraction
k_primary_ps_minus1
k_primary_method
k_mle_ps_minus1
k_regression_ps_minus1
half_life_mle_ps
r2
input_warning
```

---

## 25. Exportar un catálogo compacto de k almacenadas a CSV

```text
Exporta a CSV las constantes cinéticas almacenadas para
Azaconazole, Tebuconazole y Metconazole cis,
a ZPEx3, para PM6 y uB3LYP,
usando 10 frames de persistencia,
modo censor
y un mínimo de 5 puntos de ajuste.
No recalcules nada.
```

Acción del agente:

```text
stored_kinetics_export_csv
```

El CSV puede contener:

```text
molecule
isomer
method
energy_label
energy_temperature_K
energy_kcal_mol
zpe_kcal_mol
dof
n_distinct_inputs
persist_frames
window_mode
min_points
n_trajectories
n_events
n_censored
event_fraction
k_primary_ps_minus1
k_primary_method
k_mle_ps_minus1
k_mle_ci95_low
k_mle_ci95_high
half_life_mle_ps
k_regression_ps_minus1
r2
input_warning
kinetics_warnings
created_at
```

---

## 26. Exportar todos los detalles cinéticos almacenados sin recalcular

```text
Exporta a CSV todos los detalles cinéticos almacenados
de Azaconazole,
usando el método PM6 a ZPEx3,
con 10 frames de persistencia,
modo censor
y un mínimo de 5 puntos de ajuste.
Incluye estadísticas completas,
eventos individuales
y todos los puntos de supervivencia.
No recalcules nada.
```

Acción del agente:

```text
stored_kinetics_detailed_export_csv
```

Reconstruye desde la base de datos:

```text
*_summary.csv
*_events.csv
*_survival.csv
```

No se vuelven a recorrer los frames de las trayectorias.

---

## 27. Principales magnitudes cinéticas

La constante principal almacenada es:

```text
k_primary_ps_minus1
```

Regla de selección:

```text
Usar k_mle_ps_minus1 cuando esté disponible.
En caso contrario, usar k_regression_ps_minus1.
```

Estadísticas complementarias:

```text
k_mle_stderr
k_mle_ci95_low
k_mle_ci95_high
half_life_mle_ps

k_regression_stderr
k_regression_ci95_low
k_regression_ci95_high
half_life_regression_ps
r2
n_fit_points
```

Metadatos energéticos obtenidos de los inputs:

```text
energy_temperature_K
energy_kcal_mol
zpe_kcal_mol
dof
```

Si se detectan definiciones de input incompatibles para una condición:

```text
input_warning = multiple_input_definitions
```

---

# PARTE VIII — Primera aparición de fragmentos

## 28. Calcular la primera aparición de un fragmento

```text
Calcula la primera aparición persistente del fragmento C2H3N3
para Azaconazole calculado con PM6 a ZPEx3,
requiriendo 10 frames consecutivos.
```

Acción del agente:

```text
fragment_first_appearance
```

Para exportar el resultado, pide explícitamente un nombre CSV:

```text
Calcula la primera aparición persistente del fragmento C2H3N3
para Azaconazole calculado con PM6 a ZPEx3,
requiriendo 10 frames consecutivos,
y guarda los resultados como aza_fragment_events.csv.
```

---

## 29. Exportar una trayectoria seleccionada por un evento de fragmento

```text
Exporta la trayectoria con la aparición persistente más tardía
del fragmento C2H3N3
para Azaconazole calculado con PM6 a ZPEx3,
requiriendo 10 frames consecutivos.
```

Acción del agente:

```text
export_fragment_event_trajectory
```

Palabras de selección:

```text
más temprana
más tardía
primera
última
```

---

# PARTE IX — Exportación de trayectorias

## 30. Exportar una trayectoria por UID exacto

```text
Exporta la trayectoria traj_XXXXXXXX.
```

Acción del agente:

```text
export_trajectory
```

---

## 31. Exportar una trayectoria usando filtros de metadatos

```text
Exporta la primera trayectoria de Tebuconazole
calculada con PM6 a ZPEx3.
```

Acción del agente:

```text
export_trajectory
```

Posibles selecciones:

```text
primera
última
más temprana
más tardía
```

---

## 32. Exportar una trayectoria que contenga un fragmento

```text
Exporta una trayectoria de Azaconazole
calculada con PM6 a ZPEx3
que contenga el fragmento C2H3N3
en algún frame.
```

Acción del agente:

```text
export_trajectory_with_fragment
```

Ámbitos posibles del fragmento:

```text
cualquier frame
frame final
aparición persistente
```

---

## 33. Exportar todas las trayectorias que contengan un fragmento

```text
Exporta todas las trayectorias de Metconazole,
isómero cis, calculadas con PM6 a ZPEx3,
que contengan el fragmento C2H3N3
en el frame final.
Limita la exportación a 100 trayectorias.
```

Acción del agente:

```text
export_all_trajectories_with_fragment
```

Parámetros importantes:

```text
formula
fragment_scope
persist_frames
max_exports
folder_name
```

---

# PARTE X — Referencia completa de acciones del agente

El agente actual admite estas acciones:

```text
sql_query
show_input
restore_input
database_summary
reaction_summary
reaction_export_csv
fragment_search
final_fragment_atoms
final_fragment_bond_query
mass_spectrum
mass_spectrum_export_csv
global_kinetics
global_kinetics_export_csv
compare_global_kinetics
stored_kinetics_summary
stored_kinetics_export_csv
stored_kinetics_detailed_export_csv
fragment_first_appearance
export_fragment_event_trajectory
export_trajectory
export_trajectory_with_fragment
export_all_trajectories_with_fragment
```

---

# PARTE XI — Guía de redacción segura

## Verbos para consultas de solo lectura

```text
Lista
Busca
Muestra
Encuentra
Localiza
Cuenta
Compara
Agrupa
Comprueba si
Resume
```

## Verbos para crear archivos

```text
Exporta
Restaura
Guarda en CSV
Escribe
```

## Expresiones para datos almacenados

```text
resultados almacenados
constantes cinéticas almacenadas
fragmentos finales almacenados
reacciones finales almacenadas
No recalcules nada
```

## Expresiones para cálculos nuevos

```text
Calcula y guarda
Calcula y exporta
Recalcula
Analiza los frames de las trayectorias
```

---

# PARTE XII — Redacción cinética recomendada

Utiliza este orden para obtener el análisis más fiable:

```text
Calcula y guarda/exporta la cinética global de [MOLÉCULA],
[ISÓMERO, si corresponde],
usando el método [MÉTODO] a [ENERGÍA],
con [N] frames consecutivos,
modo [MODO]
y un mínimo de [N] puntos de ajuste.
```

Ejemplos:

```text
Calcula y guarda la k global de Azaconazole,
usando el método PM6 a ZPEx3,
con 10 frames consecutivos,
modo censor
y un mínimo de 5 puntos de ajuste.
```

```text
Calcula y exporta la cinética global completa de Metconazole,
isómero cis, usando el método uB3LYP a ZPEx3,
con 10 frames consecutivos,
modo censor
y un mínimo de 5 puntos de ajuste.
Incluye estadísticas de resumen,
eventos individuales
y todos los puntos de supervivencia.
```

---

# PARTE XIII — Comandos de diagnóstico

Mostrar las columnas de `trajectories`:

```bash
sqlite3 "$DB" "PRAGMA table_info(trajectories);"
```

Mostrar las columnas de `md_inputs`:

```bash
sqlite3 "$DB" "PRAGMA table_info(md_inputs);"
```

Mostrar las columnas de `kinetics_global`:

```bash
sqlite3 "$DB" "PRAGMA table_info(kinetics_global);"
```

Mostrar las condiciones cinéticas almacenadas:

```bash
sqlite3 "$DB" \
  "SELECT molecule, isomer, method_label, energy_label,
          persist_frames, window_mode, min_points, kinetics_uid
   FROM kinetics_global
   ORDER BY molecule, isomer, method_label, energy_label;"
```

Comprobar eventos almacenados:

```bash
sqlite3 "$DB" \
  "SELECT kinetics_uid, COUNT(*)
   FROM kinetics_events
   GROUP BY kinetics_uid;"
```

Comprobar puntos de supervivencia almacenados:

```bash
sqlite3 "$DB" \
  "SELECT kinetics_uid, COUNT(*)
   FROM kinetics_survival_points
   GROUP BY kinetics_uid;"
```

---

# Regla práctica final

```text
Una condición para calcular
    -> global_kinetics

Una condición para calcular y exportar inmediatamente
    -> global_kinetics_export_csv

Una o varias condiciones almacenadas para consultar
    -> stored_kinetics_summary

Una o varias condiciones almacenadas para exportar de forma compacta
    -> stored_kinetics_export_csv

Una o varias condiciones almacenadas para exportar con todos los detalles
    -> stored_kinetics_detailed_export_csv
```

#################################################################################################################

# SQListo Mini Protocol — English Version

This protocol describes the recommended way to ask SQListo questions in English using three example molecules:

- **Azaconazole** — no isomer
- **Tebuconazole** — no isomer
- **Metconazole, cis isomer** — molecule with an explicit isomer

The examples use the methods `PM6` and `uB3LYP`, and the energy label `ZPEx3`.

---

## 1. Basic setup

Define the database:

```bash
export DB="/path/to/your/database.db"
```

Start `llama-server` in a separate terminal:

```bash
~/llama.cpp/build/bin/llama-server \
  -m /home/alchemi20/Escritorio/Capitulo_4_SQListo/modelos_IA/qwen2.5-coder-1.5b/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  -c 8192 \
  --parallel 1 \
  --threads 3 \
  --threads-batch 3
```

Check the server:

```bash
curl http://127.0.0.1:8080/health
```

Recommended flags while testing:

```bash
--show-plan \
--show-sql \
--show-backend \
--no-llama-fallback \
--lang en
```

---

## 2. Recommended question structure

Use this order whenever possible:

```text
[ACTION] + [OBJECT] + [MOLECULE/ISOMER] +
[METHOD] + [ENERGY] + [PARAMETERS] + [OUTPUT]
```

Example:

```text
Find the PM6 trajectories for Metconazole, cis isomer, at ZPEx3.
```

For row queries, these verbs are treated similarly:

```text
List...
Find...
Show...
Search for...
Locate...
```

For isomeric molecules, prefer the explicit form:

```text
Metconazole, cis isomer
```

The shorter form may also work:

```text
Metconazole cis
```

---

# PART I — General database queries

## 3. List or search trajectories

```bash
python sqlisto_agent.py \
  "$DB" \
  "Find the PM6 trajectories for Metconazole, cis isomer, at ZPEx3." \
  --show-plan \
  --show-sql \
  --show-backend \
  --no-llama-fallback \
  --lang en
```

Expected route:

```text
routing: deterministic_sql_bypass
SQL route: deterministic_metadata_trajectory_list
```

Typical output columns:

```text
traj_uid
traj_code
molecule
isomer
method_label
energy_label
nframes
```

Other examples:

```text
List the uB3LYP trajectories for Azaconazole at ZPEx3.
```

```text
Show the PM6 trajectories for Tebuconazole at ZPEx3.
```

---

## 4. Count trajectories

```text
Count the trajectories for Azaconazole using PM6 at ZPEx3.
```

```text
Count the trajectories grouped by molecule, isomer, method and energy label.
```

---

## 5. Check whether records exist

```text
Check whether PM6 trajectories exist for Metconazole, cis isomer, at ZPEx3.
```

---

## 6. Group, rank and calculate summary statistics

```text
For Azaconazole, Tebuconazole and Metconazole cis at ZPEx3,
group the trajectories by molecule, isomer and method.
Show the number of trajectories and the mean, minimum and maximum number of frames.
```

---

## 7. General database summary

```text
Give me a general summary of the database.
```

Filtered example:

```text
Give me a database summary for Azaconazole at ZPEx3.
```

Agent action:

```text
database_summary
```

---

# PART II — Stored inputs

## 8. Show the stored input of one trajectory

A dedicated input action requires an exact `traj_uid`.

```bash
python sqlisto_agent.py \
  "$DB" \
  "Show the complete stored input for trajectory traj_XXXXXXXX." \
  --show-plan \
  --lang en
```

Agent action:

```text
show_input
```

---

## 9. Restore the stored input as a file

```bash
python sqlisto_agent.py \
  "$DB" \
  "Restore the stored input for trajectory traj_XXXXXXXX." \
  --show-plan \
  --lang en
```

Agent action:

```text
restore_input
```

The relationship used is:

```text
trajectories.input_id -> md_inputs.input_id
```

The input table may contain:

```text
raw_input_text
energy_temperature_K
energy_kcal_mol
zpe_kcal_mol
dof
```

---

# PART III — Stored reactions

## 10. Show the most frequent stored final reactions

```text
Show the 20 most frequent stored final reactions for Azaconazole
using PM6 at ZPEx3.
```

Agent action:

```text
reaction_summary
```

---

## 11. Export stored final reactions to CSV

```text
Export to CSV all stored final reactions for Tebuconazole
using PM6 at ZPEx3.
```

Agent action:

```text
reaction_export_csv
```

---

# PART IV — Stored fragments and atom participation

## 12. Search for a stored fragment

By molecular formula:

```text
Find trajectories for Azaconazole using PM6 at ZPEx3
that contain the stored fragment C2H3N3.
```

By mass-to-charge ratio:

```text
Find stored fragments near m/z 69.0327 with a tolerance of 0.001
for Tebuconazole using PM6 at ZPEx3.
```

Agent action:

```text
fragment_search
```

---

## 13. Identify the numbered atoms of a final fragment

```text
Show which numbered atoms form the stored final fragment C2H3N3
for Azaconazole using PM6 at ZPEx3.
```

Agent action:

```text
final_fragment_atoms
```

---

## 14. Query final-fragment bond separation by atom numbers

```text
Find trajectories in which atoms 2 and 3 end in different stored final fragments
for Azaconazole using PM6 at ZPEx3.
```

Agent action:

```text
final_fragment_bond_query
```

---

## 15. Query candidate bonds by element pair

```text
List N-C atom pairs that end in different stored final fragments
for Metconazole, cis isomer, using PM6 at ZPEx3.
```

Agent action:

```text
final_fragment_bond_query
```

---

# PART V — Theoretical mass spectra

## 16. Show a stored theoretical mass spectrum

```text
Generate the stored theoretical mass spectrum for Azaconazole
using PM6 at ZPEx3, using charged fragments only,
sorted by m/z.
```

Agent action:

```text
mass_spectrum
```

Optional filters include:

```text
charged fragments only
neutral fragments only
minimum m/z
maximum m/z
intensity scale
sort by m/z
sort by intensity
```

---

## 17. Export a theoretical mass spectrum to CSV

```text
Export to CSV the stored theoretical mass spectrum for Tebuconazole
using uB3LYP at ZPEx3, using charged fragments only,
sorted by m/z.
```

Agent action:

```text
mass_spectrum_export_csv
```

---

# PART VI — Global kinetics and the global rate constant k

The phrases below are treated as equivalent:

```text
global kinetics
global k
global rate constant
kinetic constant
```

A kinetic condition is identified by:

```text
molecule
isomer
method
energy_label
persist_frames
window_mode
min_points
```

The order of `minimum points` and `consecutive frames` should not matter in the updated version.

---

## 18. Calculate and store one global k

Example for a molecule without isomers:

```bash
python sqlisto_agent.py \
  "$DB" \
  "Calculate and store the global kinetics for Azaconazole,
  using method PM6 at ZPEx3,
  with 10 consecutive frames,
  censor mode,
  and a minimum of 5 fitting points." \
  --show-plan \
  --show-backend \
  --no-llama-fallback \
  --timeout 600 \
  --lang en
```

Equivalent wording:

```text
Calculate and store the global k for Azaconazole...
```

Agent action:

```text
global_kinetics
```

The result is stored in the database.

---

## 19. Calculate and immediately export the complete kinetic result

```bash
python sqlisto_agent.py \
  "$DB" \
  "Calculate and export the complete global kinetics for Metconazole,
  cis isomer, using method uB3LYP at ZPEx3,
  with 10 consecutive frames,
  censor mode,
  and a minimum of 5 fitting points.
  Include the summary statistics, individual events,
  and all survival-curve points." \
  --show-plan \
  --timeout 600 \
  --lang en
```

Agent action:

```text
global_kinetics_export_csv
```

It produces:

```text
*_summary.csv
*_events.csv
*_survival.csv
```

It also stores the result in the database.

---

## 20. Replacement rule for repeated kinetic calculations

If the following fields are identical:

```text
molecule
isomer
method
energy_label
persist_frames
window_mode
min_points
```

the previous result is replaced.

The replacement includes:

```text
kinetics_global
kinetics_events
kinetics_survival_points
```

Therefore, rerunning the exact same condition updates the stored result instead of creating a duplicate.

---

## 21. Calculate several conditions

The current calculation action is designed for one condition at a time.

Run separately:

```text
Azaconazole — PM6 — ZPEx3
Tebuconazole — PM6 — ZPEx3
Metconazole — cis — PM6 — ZPEx3
```

Do not rely on one sentence containing several molecules to calculate them sequentially.

---

## 22. Compare global kinetics

Example comparing methods:

```text
Compare the global kinetics of PM6 and uB3LYP
for Azaconazole at ZPEx3,
using 10 consecutive frames,
censor mode,
and a minimum of 5 fitting points.
```

Agent action:

```text
compare_global_kinetics
```

The comparison can be performed by an available grouping field,
such as method, molecule, isomer or energy label.

To request CSV output:

```text
Compare PM6 and uB3LYP for Azaconazole at ZPEx3,
using 10 consecutive frames, censor mode,
and a minimum of 5 fitting points.
Export the comparison to CSV.
```

---

# PART VII — Query and export stored kinetic results

These actions do not rescan trajectory frames.

Use this phrase to make the intention explicit:

```text
Do not recalculate anything.
```

---

## 23. Show one stored k

```bash
python sqlisto_agent.py \
  "$DB" \
  "Show the stored global k for Azaconazole,
  using method PM6 at ZPEx3,
  with 10 persistence frames,
  censor mode,
  and a minimum of 5 fitting points.
  Do not recalculate anything." \
  --show-plan \
  --lang en
```

Agent action:

```text
stored_kinetics_summary
```

---

## 24. Show a stored kinetic summary for several molecules

First calculate each condition separately. Then ask:

```text
Summarise the stored kinetic constants for
Azaconazole, Tebuconazole and Metconazole cis,
at ZPEx3, for PM6 and uB3LYP,
using 10 persistence frames,
censor mode,
and a minimum of 5 fitting points.
Do not recalculate anything.
```

Agent action:

```text
stored_kinetics_summary
```

Possible output columns:

```text
molecule
isomer
method
energy_label
energy_temperature_K
energy_kcal_mol
persist_frames
window_mode
min_points
n_trajectories
n_events
n_censored
event_fraction
k_primary_ps_minus1
k_primary_method
k_mle_ps_minus1
k_regression_ps_minus1
half_life_mle_ps
r2
input_warning
```

---

## 25. Export a compact stored-k catalogue to CSV

```text
Export to CSV the stored kinetic constants for
Azaconazole, Tebuconazole and Metconazole cis,
at ZPEx3, for PM6 and uB3LYP,
using 10 persistence frames,
censor mode,
and a minimum of 5 fitting points.
Do not recalculate anything.
```

Agent action:

```text
stored_kinetics_export_csv
```

The CSV may contain:

```text
molecule
isomer
method
energy_label
energy_temperature_K
energy_kcal_mol
zpe_kcal_mol
dof
n_distinct_inputs
persist_frames
window_mode
min_points
n_trajectories
n_events
n_censored
event_fraction
k_primary_ps_minus1
k_primary_method
k_mle_ps_minus1
k_mle_ci95_low
k_mle_ci95_high
half_life_mle_ps
k_regression_ps_minus1
r2
input_warning
kinetics_warnings
created_at
```

---

## 26. Export complete stored kinetic details without recalculating

```text
Export to CSV all stored kinetic details for Azaconazole,
using method PM6 at ZPEx3,
with 10 persistence frames,
censor mode,
and a minimum of 5 fitting points.
Include complete statistics, individual events,
and all survival points.
Do not recalculate anything.
```

Agent action:

```text
stored_kinetics_detailed_export_csv
```

It reconstructs from the database:

```text
*_summary.csv
*_events.csv
*_survival.csv
```

No trajectory frames are rescanned.

---

## 27. Main kinetic quantities

The primary stored rate constant is:

```text
k_primary_ps_minus1
```

Selection rule:

```text
Use k_mle_ps_minus1 when available.
Otherwise use k_regression_ps_minus1.
```

Supporting statistics include:

```text
k_mle_stderr
k_mle_ci95_low
k_mle_ci95_high
half_life_mle_ps

k_regression_stderr
k_regression_ci95_low
k_regression_ci95_high
half_life_regression_ps
r2
n_fit_points
```

Input-derived energetic metadata include:

```text
energy_temperature_K
energy_kcal_mol
zpe_kcal_mol
dof
```

If incompatible input definitions are detected for one condition:

```text
input_warning = multiple_input_definitions
```

---

# PART VIII — Fragment first-appearance analysis

## 28. Calculate the first appearance of a fragment

```text
Calculate the first persistent appearance of fragment C2H3N3
for Azaconazole using PM6 at ZPEx3,
requiring 10 consecutive frames.
```

Agent action:

```text
fragment_first_appearance
```

To export the result, explicitly request a CSV filename:

```text
Calculate the first persistent appearance of fragment C2H3N3
for Azaconazole using PM6 at ZPEx3,
requiring 10 consecutive frames,
and save the results as aza_fragment_events.csv.
```

---

## 29. Export one trajectory selected by a fragment event

```text
Export the trajectory with the latest persistent appearance
of fragment C2H3N3 for Azaconazole using PM6 at ZPEx3,
requiring 10 consecutive frames.
```

Agent action:

```text
export_fragment_event_trajectory
```

Selection keywords may include:

```text
earliest
latest
first
last
```

---

# PART IX — Trajectory export

## 30. Export a trajectory by exact UID

```text
Export trajectory traj_XXXXXXXX.
```

Agent action:

```text
export_trajectory
```

---

## 31. Export one trajectory using metadata filters

```text
Export the first trajectory for Tebuconazole
using PM6 at ZPEx3.
```

Agent action:

```text
export_trajectory
```

Possible selections:

```text
first
last
earliest
latest
```

---

## 32. Export one trajectory containing a fragment

```text
Export one trajectory for Azaconazole using PM6 at ZPEx3
that contains fragment C2H3N3 in any frame.
```

Agent action:

```text
export_trajectory_with_fragment
```

Possible fragment scopes:

```text
any frame
final frame
persistent appearance
```

---

## 33. Export all trajectories containing a fragment

```text
Export all trajectories for Metconazole, cis isomer,
using PM6 at ZPEx3,
that contain fragment C2H3N3 in the final frame.
Limit the export to 100 trajectories.
```

Agent action:

```text
export_all_trajectories_with_fragment
```

Important parameters include:

```text
formula
fragment_scope
persist_frames
max_exports
folder_name
```

---

# PART X — Complete agent action reference

The current agent supports these actions:

```text
sql_query
show_input
restore_input
database_summary
reaction_summary
reaction_export_csv
fragment_search
final_fragment_atoms
final_fragment_bond_query
mass_spectrum
mass_spectrum_export_csv
global_kinetics
global_kinetics_export_csv
compare_global_kinetics
stored_kinetics_summary
stored_kinetics_export_csv
stored_kinetics_detailed_export_csv
fragment_first_appearance
export_fragment_event_trajectory
export_trajectory
export_trajectory_with_fragment
export_all_trajectories_with_fragment
```

---

# PART XI — Safe wording guide

## Use these verbs for read-only queries

```text
List
Find
Show
Search for
Count
Compare
Group
Check whether
Summarise
```

## Use these verbs only when creating files

```text
Export
Restore
Save to CSV
Write
```

## Use these phrases for stored data

```text
stored results
stored kinetic constants
stored final fragments
stored final reactions
Do not recalculate anything
```

## Use these phrases for new calculations

```text
Calculate and store
Calculate and export
Recalculate
Analyse the trajectory frames
```

---

# PART XII — Recommended kinetic wording

Use this exact order for the most reliable parsing:

```text
Calculate and store/export the global kinetics for [MOLECULE],
[ISOMER, if applicable],
using method [METHOD] at [ENERGY],
with [N] consecutive frames,
[MODE] mode,
and a minimum of [N] fitting points.
```

Examples:

```text
Calculate and store the global k for Azaconazole,
using method PM6 at ZPEx3,
with 10 consecutive frames,
censor mode,
and a minimum of 5 fitting points.
```

```text
Calculate and export the complete global kinetics for Metconazole,
cis isomer, using method uB3LYP at ZPEx3,
with 10 consecutive frames,
censor mode,
and a minimum of 5 fitting points.
Include summary statistics, individual events,
and all survival points.
```

---

# PART XIII — Diagnostic commands

Show the columns in `trajectories`:

```bash
sqlite3 "$DB" "PRAGMA table_info(trajectories);"
```

Show the columns in `md_inputs`:

```bash
sqlite3 "$DB" "PRAGMA table_info(md_inputs);"
```

Show the columns in `kinetics_global`:

```bash
sqlite3 "$DB" "PRAGMA table_info(kinetics_global);"
```

Show stored kinetic conditions:

```bash
sqlite3 "$DB" \
  "SELECT molecule, isomer, method_label, energy_label,
          persist_frames, window_mode, min_points, kinetics_uid
   FROM kinetics_global
   ORDER BY molecule, isomer, method_label, energy_label;"
```

Check stored event rows:

```bash
sqlite3 "$DB" \
  "SELECT kinetics_uid, COUNT(*)
   FROM kinetics_events
   GROUP BY kinetics_uid;"
```

Check stored survival points:

```bash
sqlite3 "$DB" \
  "SELECT kinetics_uid, COUNT(*)
   FROM kinetics_survival_points
   GROUP BY kinetics_uid;"
```

---

# Final practical rule

```text
One condition to calculate
    -> global_kinetics

One condition to calculate and export immediately
    -> global_kinetics_export_csv

One or several stored conditions to inspect
    -> stored_kinetics_summary

One or several stored conditions to export compactly
    -> stored_kinetics_export_csv

One or several stored conditions to export with all details
    -> stored_kinetics_detailed_export_csv
```

