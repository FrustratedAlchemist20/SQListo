#!/usr/bin/env python3

import argparse
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd


# ============================================================
# DEFAULT CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DEFAULT_MODEL = str(
    BASE_DIR
    / "modelos_IA"
    / "qwen2.5-coder-1.5b"
    / "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
)

DEFAULT_LLAMA_BIN = str(
    Path.home() / "llama.cpp/build/bin/llama-cli"
)

DEFAULT_KNOWLEDGE_FILE = str(
    Path(__file__).resolve().with_name("sqlisto_knowledge.txt")
)

DEFAULT_MAX_ROWS = 100
DEFAULT_N_TOKENS = 96
DEFAULT_TIMEOUT_SECONDS = 240
DEFAULT_MAX_REPAIRS = 2


DANGEROUS_SQL = [
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "REPLACE",
    "TRUNCATE",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "VACUUM",
    "REINDEX",
]


# ============================================================
# CUSTOM EXCEPTION
# ============================================================

class SQLiteValidationError(ValueError):
    """
    Raised when SQLite rejects a generated query.
    """

    def __init__(self, sql: str, sqlite_error: str):
        self.sql = sql
        self.sqlite_error = sqlite_error

        super().__init__(
            "SQLite rechazó la consulta generada.\n\n"
            f"Consulta:\n{sql}\n\n"
            f"Error:\n{sqlite_error}"
        )


# ============================================================
# PATH VALIDATION
# ============================================================

def validate_paths(
    database: str,
    model: str,
    llama_bin: str,
    knowledge_file: str | None,
) -> tuple[str, str, str, str | None]:
    """
    Validate database, model, llama-cli and knowledge file paths.
    """
    db_path = Path(database).expanduser().resolve()
    model_path = Path(model).expanduser().resolve()
    llama_path = Path(llama_bin).expanduser().resolve()

    if not db_path.exists():
        raise FileNotFoundError(
            f"No existe la base de datos:\n{db_path}"
        )

    if not db_path.is_file():
        raise FileNotFoundError(
            f"La ruta de la base de datos no es un archivo:\n{db_path}"
        )

    if not model_path.exists():
        raise FileNotFoundError(
            f"No existe el modelo GGUF:\n{model_path}"
        )

    if not model_path.is_file():
        raise FileNotFoundError(
            f"La ruta del modelo no es un archivo:\n{model_path}"
        )

    if model_path.suffix.lower() != ".gguf":
        raise ValueError(
            f"El modelo debe ser un archivo .gguf:\n{model_path}"
        )

    if not llama_path.exists():
        raise FileNotFoundError(
            f"No existe llama-cli:\n{llama_path}"
        )

    if not llama_path.is_file():
        raise FileNotFoundError(
            f"La ruta de llama-cli no es un archivo:\n{llama_path}"
        )

    resolved_knowledge: str | None = None

    if knowledge_file:
        knowledge_path = Path(
            knowledge_file
        ).expanduser().resolve()

        if not knowledge_path.exists():
            raise FileNotFoundError(
                "No existe el archivo de conocimiento:\n"
                f"{knowledge_path}"
            )

        if not knowledge_path.is_file():
            raise FileNotFoundError(
                "La ruta del conocimiento no es un archivo:\n"
                f"{knowledge_path}"
            )

        resolved_knowledge = str(knowledge_path)

    return (
        str(db_path),
        str(model_path),
        str(llama_path),
        resolved_knowledge,
    )


# ============================================================
# QUESTION VALIDATION
# ============================================================

def validate_question(question: str) -> None:
    """
    Validate only the basic structure of the question.

    Natural-language interpretation is delegated to the LLM.
    """
    if not question or not question.strip():
        raise ValueError(
            "La pregunta no puede estar vacía."
        )

    if len(question) > 10_000:
        raise ValueError(
            "La pregunta es demasiado larga."
        )


# ============================================================
# SQLITE CONNECTION
# ============================================================

def build_readonly_uri(db_path: str) -> str:
    """
    Build a read-only immutable SQLite URI.
    """
    resolved = Path(db_path).expanduser().resolve()

    return resolved.as_uri() + "?mode=ro&immutable=1"


# ============================================================
# KNOWLEDGE FILE
# ============================================================

def load_knowledge(
    knowledge_file: str | None,
) -> str:
    """
    Load the external XYZ2DB semantic manual.
    """
    if not knowledge_file:
        return ""

    path = Path(knowledge_file)

    return path.read_text(
        encoding="utf-8",
        errors="replace",
    ).strip()


# ============================================================
# DATABASE SCHEMA
# ============================================================

def quote_identifier(identifier: str) -> str:
    """
    Safely quote a SQLite identifier.
    """
    return '"' + identifier.replace('"', '""') + '"'


def get_sqlite_schema(db_path: str) -> str:
    """
    Extract the real SQLite schema, including columns and foreign keys.
    """
    db_uri = build_readonly_uri(db_path)
    conn = sqlite3.connect(db_uri, uri=True)

    try:
        cur = conn.cursor()

        tables = [
            row[0]
            for row in cur.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        ]

        if not tables:
            raise ValueError(
                "La base de datos no contiene tablas consultables."
            )

        schema_lines: list[str] = []

        for table_name in tables:
            quoted_table = quote_identifier(table_name)

            schema_lines.append("")
            schema_lines.append(f"TABLE {table_name}")
            schema_lines.append("  COLUMNS:")

            columns = cur.execute(
                f"PRAGMA table_info({quoted_table})"
            ).fetchall()

            for column in columns:
                (
                    _cid,
                    name,
                    column_type,
                    not_null,
                    default_value,
                    primary_key,
                ) = column

                labels = []

                if primary_key:
                    labels.append("PRIMARY KEY")

                if not_null:
                    labels.append("NOT NULL")

                if default_value is not None:
                    labels.append(
                        f"DEFAULT {default_value}"
                    )

                label_text = (
                    " [" + ", ".join(labels) + "]"
                    if labels
                    else ""
                )

                schema_lines.append(
                    f"    - {name}: "
                    f"{column_type or 'UNSPECIFIED'}"
                    f"{label_text}"
                )

            foreign_keys = cur.execute(
                f"PRAGMA foreign_key_list({quoted_table})"
            ).fetchall()

            if foreign_keys:
                schema_lines.append("  FOREIGN KEYS:")

                for foreign_key in foreign_keys:
                    referenced_table = foreign_key[2]
                    source_column = foreign_key[3]
                    target_column = foreign_key[4]

                    schema_lines.append(
                        f"    - {table_name}.{source_column} "
                        f"-> {referenced_table}.{target_column}"
                    )

        return "\n".join(schema_lines).strip()

    finally:
        conn.close()


# ============================================================
# MAIN PROMPT
# ============================================================

def build_prompt(
    schema: str,
    question: str,
    knowledge: str,
) -> str:
    """
    Build the natural-language-to-SQL prompt.
    """
    knowledge_section = (
        knowledge
        if knowledge
        else "No external semantic manual was provided."
    )

    return f"""<|im_start|>system
You are SQListo, a local offline assistant specialised in translating
scientific natural-language questions into safe SQLite queries for
XYZ2DB molecular-dynamics databases.

The user may ask in Spanish, English, or another language.
Interpret the scientific meaning of the complete question. Do not rely
on exact keywords or one specific language.

Your task is to return exactly one read-only SQLite query.

MANDATORY RULES

1. Use only tables and columns present in the supplied real schema.
2. Never invent tables, columns, relationships, values or results.
3. The real SQLite schema is the final authority for names.
4. Use the semantic manual to understand scientific meaning.
5. Return exactly one SQL statement.
6. The statement must begin with SELECT or WITH.
7. Never generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE,
   REPLACE, TRUNCATE, ATTACH, DETACH, PRAGMA, VACUUM or REINDEX.
8. Return no explanation, Markdown, comments or code fences.
9. End with exactly one semicolon.
10. Prefer explicit columns instead of SELECT *.
11. Use aliases for joins.
12. Qualify ambiguous columns with table aliases.
13. Use COUNT(DISTINCT traj_uid) when a secondary table may contain
    several rows for the same trajectory.
14. Never assume that fragments contains molecule, method_label,
    isomer or energy_label.
15. To obtain metadata for fragments, join:
       fragments.traj_uid = trajectories.traj_uid
16. Prefer trajectory_features for trajectory-level aggregated
    descriptors when the required column exists.
17. Use fragments for specific fragment formulas, exact masses,
    individual fragment records or fragment charges.
18. Do not inspect compressed BLOB payloads using SQL.
19. If frame-by-frame coordinate or connectivity analysis is required,
    return:

SELECT
    'PYTHON_TOOL_REQUIRED' AS status,
    '<tool_name>' AS tool,
    '<brief reason>' AS reason;

20. Do not generate an incorrect SQL query merely to produce an answer.

GROUPING RULES

21. Expressions such as:
       por molécula
       para cada molécula
       agrupado por molécula
       by molecule
       for each molecule
       grouped by molecule
    require one output row per molecule.

22. For "trajectories by molecule", use:
       SELECT molecule, COUNT(*)
       FROM trajectories
       GROUP BY molecule

23. Do not replace "trajectories by molecule" with:
       COUNT(DISTINCT molecule)
    because that only answers how many different molecules exist.

24. Apply the same grouping rule to method, energy_label, isomer
    and other requested categories.

CHARGED-FRAGMENT RULES

25. "Charged fragments", "fragmentos cargados" or equivalent wording
    means any fragment whose charge is non-zero.

26. "Charged fragments" never means Cl+ unless the user explicitly
    mentions the specific Cl+ fragment.

27. For trajectory-level questions about charged fragments, prefer:
       trajectory_features.charged_fragment_count > 0
    when that real column exists.

28. Use fragments.formula = 'Cl+' only when the user explicitly asks
    for Cl+.

29. Do not use formula LIKE 'Cl+' to represent all charged fragments.

SCIENTIFIC COUNTING RULES

30. COUNT(*) counts rows.
31. COUNT(DISTINCT traj_uid) counts different trajectories.
32. COUNT(DISTINCT formula) counts different fragment formulas.
33. Distinguish fragment occurrences from trajectories containing
    a fragment.
34. If one trajectory can produce multiple fragment rows, use
    COUNT(DISTINCT traj_uid) when the user asks for trajectories.

EXAMPLE 1

Question:
¿Cuántas trayectorias hay por molécula?

Answer:
SELECT
    molecule,
    COUNT(*) AS n_trajectories
FROM trajectories
GROUP BY molecule;

EXAMPLE 2

Question:
How many trajectories are there for each molecule?

Answer:
SELECT
    molecule,
    COUNT(*) AS n_trajectories
FROM trajectories
GROUP BY molecule;

EXAMPLE 3

Question:
Cuenta las trayectorias con fragmentos cargados por molécula.

Answer:
SELECT
    molecule,
    COUNT(*) AS n_trajectories_with_charged_fragments
FROM trajectory_features
WHERE charged_fragment_count > 0
GROUP BY molecule;

EXAMPLE 4

Question:
Count trajectories containing charged fragments for each molecule.

Answer:
SELECT
    molecule,
    COUNT(*) AS n_trajectories_with_charged_fragments
FROM trajectory_features
WHERE charged_fragment_count > 0
GROUP BY molecule;

EXAMPLE 5

Question:
How many trajectories contain Cl+ for each molecule?

Answer:
SELECT
    t.molecule,
    COUNT(DISTINCT f.traj_uid) AS n_trajectories_with_cl_plus
FROM fragments AS f
JOIN trajectories AS t
    ON t.traj_uid = f.traj_uid
WHERE f.formula = 'Cl+'
GROUP BY t.molecule;

XYZ2DB SEMANTIC MANUAL

{knowledge_section}

REAL SQLITE SCHEMA

{schema}
<|im_end|>
<|im_start|>user
{question}
<|im_end|>
<|im_start|>assistant
"""


# ============================================================
# REPAIR PROMPT
# ============================================================

def build_repair_prompt(
    schema: str,
    question: str,
    knowledge: str,
    rejected_sql: str,
    sqlite_error: str,
) -> str:
    """
    Build a prompt to repair SQL rejected by SQLite.
    """
    knowledge_section = (
        knowledge
        if knowledge
        else "No external semantic manual was provided."
    )

    return f"""<|im_start|>system
You are SQListo, a local offline SQLite expert for XYZ2DB.

A previous SQL query was rejected by SQLite.

Correct it using:
- the original user question;
- the semantic manual;
- the real SQLite schema;
- the rejected SQL;
- the exact SQLite error.

MANDATORY RULES

1. Return exactly one corrected read-only SQLite query.
2. The query must begin with SELECT or WITH.
3. Use only real tables and real columns.
4. Never invent relationships.
5. Never return explanations, Markdown or code fences.
6. End with exactly one semicolon.
7. Never generate data-changing or schema-changing SQL.
8. Respect the scientific meaning of the original question.
9. "By X" or "for each X" means GROUP BY X.
10. "Charged fragments" does not mean Cl+.
11. Use fragments.formula = 'Cl+' only when Cl+ was explicitly requested.
12. If relational SQL cannot answer the question, return:

SELECT
    'PYTHON_TOOL_REQUIRED' AS status,
    '<tool_name>' AS tool,
    '<brief reason>' AS reason;

XYZ2DB SEMANTIC MANUAL

{knowledge_section}

REAL SQLITE SCHEMA

{schema}

ORIGINAL USER QUESTION

{question}

REJECTED SQL

{rejected_sql}

SQLITE ERROR

{sqlite_error}
<|im_end|>
<|im_start|>assistant
"""


# ============================================================
# LLAMA.CPP EXECUTION
# ============================================================

def run_llama_cli(
    model_path: str,
    prompt: str,
    llama_cli: str,
    n_tokens: int = DEFAULT_N_TOKENS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """
    Run llama-cli and capture the generated text.
    """
    cmd = [
        llama_cli,
        "-m",
        model_path,
        "-p",
        prompt,
        "-n",
        str(n_tokens),
        "--single-turn",
        "--simple-io",
        "--no-display-prompt",
        "--log-disable",
        "--temp",
        "0",
        "--top-k",
        "1",
    ]

    try:
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )

    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "llama-cli no terminó dentro del límite de "
            f"{timeout_seconds} segundos."
        ) from exc

    if result.returncode != 0:
        raise RuntimeError(
            "llama-cli terminó con error.\n\n"
            f"Código de salida: {result.returncode}\n"
            f"STDOUT: {result.stdout!r}\n"
            f"STDERR: {result.stderr!r}"
        )

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    if stdout:
        return stdout

    if re.search(
        r"\b(?:SELECT|WITH)\b",
        stderr,
        flags=re.IGNORECASE,
    ):
        return stderr

    raise RuntimeError(
        "llama-cli terminó sin producir una salida SQL capturable.\n\n"
        f"STDOUT: {result.stdout!r}\n"
        f"STDERR: {result.stderr!r}"
    )


# ============================================================
# SQL EXTRACTION
# ============================================================

def clean_llama_output(text: str) -> str:
    """
    Remove common llama.cpp terminal noise.
    """
    cleaned = text.replace("\r", "\n")
    cleaned = cleaned.replace("EOF by user", "")

    cleaned = re.sub(
        r"^\s*>\s*",
        "",
        cleaned,
        flags=re.MULTILINE,
    )

    cleaned = re.sub(
        r"^\[ Prompt:.*$",
        "",
        cleaned,
        flags=re.MULTILINE,
    )

    cleaned = re.sub(
        r"^\s*Exiting\.\.\.\s*$",
        "",
        cleaned,
        flags=re.MULTILINE,
    )

    return cleaned


def extract_sql(text: str) -> str:
    """
    Extract the last SELECT or WITH query generated by the model.
    """
    if not text or not text.strip():
        raise ValueError(
            "La salida del modelo está vacía."
        )

    cleaned = clean_llama_output(text)

    fenced_queries = re.findall(
        r"```(?:sql)?\s*((?:SELECT|WITH)\b.*?)```",
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    )

    if fenced_queries:
        sql = fenced_queries[-1].strip()

    else:
        matches = re.findall(
            r"(?ims)"
            r"^[ \t]*((?:SELECT|WITH)\b.*?)"
            r"(?="
            r";\s*(?:$|\n)"
            r"|<\|im_end\|>"
            r"|\n\[ Prompt:"
            r"|\nExiting\.\.\."
            r"|\Z"
            r")",
            cleaned,
        )

        if not matches:
            raise ValueError(
                "No se encontró una consulta SELECT o WITH "
                "en la salida del modelo.\n\n"
                f"Salida recibida:\n{cleaned}"
            )

        sql = matches[-1].strip()

    sql = sql.rstrip(";").strip()

    if not sql:
        raise ValueError(
            "La consulta extraída está vacía."
        )

    return sql + ";"


# ============================================================
# SQL SECURITY
# ============================================================

def validate_readonly_sql(sql: str) -> None:
    """
    Ensure that the SQL is exactly one read-only query.
    """
    normalized = sql.strip()
    sql_upper = normalized.upper()

    if not re.match(
        r"^(SELECT|WITH)\b",
        sql_upper,
    ):
        raise ValueError(
            "La consulta debe empezar por SELECT o WITH.\n\n"
            f"Consulta recibida:\n{sql}"
        )

    for word in DANGEROUS_SQL:
        if re.search(
            rf"\b{re.escape(word)}\b",
            sql_upper,
        ):
            raise ValueError(
                "Consulta bloqueada por contener una palabra "
                f"no permitida: {word}"
            )

    if normalized.count(";") != 1:
        raise ValueError(
            "La consulta debe contener exactamente una sentencia SQL."
        )

    if not normalized.endswith(";"):
        raise ValueError(
            "El punto y coma debe estar únicamente al final."
        )

    if "--" in normalized:
        raise ValueError(
            "No se permiten comentarios SQL."
        )

    if "/*" in normalized or "*/" in normalized:
        raise ValueError(
            "No se permiten comentarios SQL."
        )


# ============================================================
# AUTOMATIC LIMIT
# ============================================================

def enforce_result_limit(
    sql: str,
    default_limit: int = DEFAULT_MAX_ROWS,
) -> str:
    """
    Add LIMIT to ordinary row-returning queries.
    """
    if default_limit <= 0:
        return sql

    sql_clean = sql.rstrip(";").strip()
    sql_upper = sql_clean.upper()

    if "PYTHON_TOOL_REQUIRED" in sql_upper:
        return sql_clean + ";"

    has_limit = re.search(
        r"\bLIMIT\s+\d+\b",
        sql_upper,
    )

    aggregate_functions = re.search(
        r"\b(COUNT|AVG|MIN|MAX|SUM|TOTAL|GROUP_CONCAT)\s*\(",
        sql_upper,
    )

    has_group_by = re.search(
        r"\bGROUP\s+BY\b",
        sql_upper,
    )

    if (
        not has_limit
        and not aggregate_functions
        and not has_group_by
    ):
        sql_clean += f"\nLIMIT {int(default_limit)}"

    return sql_clean + ";"


# ============================================================
# SQLITE VALIDATION
# ============================================================

def validate_sql_with_sqlite(
    db_path: str,
    sql: str,
) -> None:
    """
    Parse and plan the query without executing it.
    """
    db_uri = build_readonly_uri(db_path)
    conn = sqlite3.connect(db_uri, uri=True)

    try:
        query = sql.rstrip(";").strip()

        conn.execute(
            "EXPLAIN QUERY PLAN " + query
        ).fetchall()

    except sqlite3.Error as exc:
        raise SQLiteValidationError(
            sql=sql,
            sqlite_error=str(exc),
        ) from exc

    finally:
        conn.close()


# ============================================================
# GENERATION AND REPAIR
# ============================================================

def generate_valid_sql(
    db_path: str,
    question: str,
    schema: str,
    knowledge: str,
    model_path: str,
    llama_cli: str,
    n_tokens: int,
    timeout_seconds: int,
    max_rows: int,
    max_repairs: int,
    show_repairs: bool = False,
) -> tuple[str, int]:
    """
    Generate SQL and automatically repair schema or syntax errors.
    """
    prompt = build_prompt(
        schema=schema,
        question=question,
        knowledge=knowledge,
    )

    raw_output = run_llama_cli(
        model_path=model_path,
        prompt=prompt,
        llama_cli=llama_cli,
        n_tokens=n_tokens,
        timeout_seconds=timeout_seconds,
    )

    sql = extract_sql(raw_output)
    repairs_used = 0

    while True:
        validate_readonly_sql(sql)

        sql = enforce_result_limit(
            sql,
            default_limit=max_rows,
        )

        validate_readonly_sql(sql)

        try:
            validate_sql_with_sqlite(
                db_path=db_path,
                sql=sql,
            )

            return sql, repairs_used

        except SQLiteValidationError as exc:
            if repairs_used >= max_repairs:
                raise

            repairs_used += 1

            if show_repairs:
                print(
                    "\n--- Reparación automática "
                    f"{repairs_used}/{max_repairs} ---"
                )
                print(
                    f"SQLite indicó: {exc.sqlite_error}"
                )

            repair_prompt = build_repair_prompt(
                schema=schema,
                question=question,
                knowledge=knowledge,
                rejected_sql=sql,
                sqlite_error=exc.sqlite_error,
            )

            repaired_output = run_llama_cli(
                model_path=model_path,
                prompt=repair_prompt,
                llama_cli=llama_cli,
                n_tokens=n_tokens,
                timeout_seconds=timeout_seconds,
            )

            sql = extract_sql(repaired_output)


# ============================================================
# QUERY EXECUTION
# ============================================================

def execute_sql(
    db_path: str,
    sql: str,
) -> pd.DataFrame:
    """
    Execute a validated query in read-only immutable mode.
    """
    db_uri = build_readonly_uri(db_path)
    conn = sqlite3.connect(db_uri, uri=True)

    try:
        return pd.read_sql_query(
            sql,
            conn,
        )

    finally:
        conn.close()


# ============================================================
# RESULT DISPLAY
# ============================================================

def print_result(df: pd.DataFrame) -> None:
    """
    Print a DataFrame cleanly.
    """
    print("\n--- Resultado ---")

    if df.empty:
        print(
            "La consulta no devolvió resultados."
        )
        return

    print(
        df.to_string(index=False)
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "SQListo: asistente local multilingüe para consultar "
            "bases SQLite generadas por XYZ2DB."
        )
    )

    parser.add_argument(
        "database",
        help="Ruta de la base de datos SQLite.",
    )

    parser.add_argument(
        "question",
        help="Pregunta en lenguaje natural.",
    )

    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Ruta del modelo GGUF.",
    )

    parser.add_argument(
        "--llama-bin",
        default=DEFAULT_LLAMA_BIN,
        help="Ruta de llama-cli.",
    )

    parser.add_argument(
        "--knowledge",
        default=DEFAULT_KNOWLEDGE_FILE,
        help=(
            "Ruta del manual semántico de XYZ2DB."
        ),
    )

    parser.add_argument(
        "--csv",
        default=None,
        help="Ruta opcional para exportar a CSV.",
    )

    parser.add_argument(
        "--show-sql",
        action="store_true",
        help="Mostrar la consulta SQL final.",
    )

    parser.add_argument(
        "--show-repairs",
        action="store_true",
        help="Mostrar las correcciones automáticas.",
    )

    parser.add_argument(
        "--max-rows",
        type=int,
        default=DEFAULT_MAX_ROWS,
        help=(
            "Máximo de filas para consultas ordinarias "
            f"(por defecto: {DEFAULT_MAX_ROWS})."
        ),
    )

    parser.add_argument(
        "--tokens",
        type=int,
        default=DEFAULT_N_TOKENS,
        help=(
            "Máximo de tokens generados "
            f"(por defecto: {DEFAULT_N_TOKENS})."
        ),
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=(
            "Timeout por llamada al modelo "
            f"(por defecto: {DEFAULT_TIMEOUT_SECONDS} s)."
        ),
    )

    parser.add_argument(
        "--max-repairs",
        type=int,
        default=DEFAULT_MAX_REPAIRS,
        help=(
            "Máximo de reparaciones automáticas "
            f"(por defecto: {DEFAULT_MAX_REPAIRS})."
        ),
    )

    args = parser.parse_args()

    try:
        (
            database,
            model,
            llama_bin,
            knowledge_file,
        ) = validate_paths(
            database=args.database,
            model=args.model,
            llama_bin=args.llama_bin,
            knowledge_file=args.knowledge,
        )

        validate_question(
            args.question
        )

        knowledge = load_knowledge(
            knowledge_file
        )

        schema = get_sqlite_schema(
            database
        )

        sql, repairs_used = generate_valid_sql(
            db_path=database,
            question=args.question,
            schema=schema,
            knowledge=knowledge,
            model_path=model,
            llama_cli=llama_bin,
            n_tokens=args.tokens,
            timeout_seconds=args.timeout,
            max_rows=args.max_rows,
            max_repairs=args.max_repairs,
            show_repairs=args.show_repairs,
        )

        if args.show_sql:
            print("\n--- SQL generado ---")
            print(sql)

            print("\nOrigen: modelo local")

            if repairs_used:
                print(
                    "Reparaciones automáticas utilizadas: "
                    f"{repairs_used}"
                )

        df = execute_sql(
            db_path=database,
            sql=sql,
        )

        print_result(df)

        if args.csv:
            csv_path = Path(
                args.csv
            ).expanduser().resolve()

            csv_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            df.to_csv(
                csv_path,
                index=False,
            )

            print(
                f"\nCSV guardado en:\n{csv_path}"
            )

    except (
        FileNotFoundError,
        ValueError,
        RuntimeError,
        sqlite3.Error,
        pd.errors.DatabaseError,
    ) as exc:
        print(
            f"\nERROR: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

