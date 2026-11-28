# Prompts de SQListo

- `router.txt`: selección de una acción y sus argumentos en formato JSON.
- `sql_generation.txt`: generación de una consulta SQLite de lectura.
- `sql_repair.txt`: reparación de una consulta rechazada por SQLite.

Edita estos archivos UTF-8 para cambiar las instrucciones de la IA local.
Conserva las variables `${...}`, los delimitadores de conversación y los
formatos JSON o SQL esperados. Las llaves JSON se escriben normalmente;
un dólar literal se escribe `$$`.

`../sqlisto_prompts.py` incorpora el contexto y relee las plantillas en cada
construcción del prompt. Consulta [la guía de edición](../README_prompts.md)
para ver las variables, probar cambios y distinguir las rutas deterministas.
