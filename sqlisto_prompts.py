"""Load SQListo's editable prompt templates and insert their request context.

Instructions live in ``prompts/*.txt``. The existing agent and SQL assistant
import these builders so their public function names remain available.
"""

import json
from pathlib import Path
from string import Template


PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_FIELDS = {
    "router.txt": {"catalog_json", "question"},
    "sql_generation.txt": {"knowledge_section", "schema", "question"},
    "sql_repair.txt": {
        "knowledge_section", "schema", "question", "rejected_sql", "sqlite_error",
    },
}


def _render_prompt(filename: str, **values: str) -> str:
    """Read a UTF-8 template, validate its fields and substitute exactly once."""
    if filename not in _FIELDS:
        raise ValueError(f"Unknown SQListo prompt template: {filename}")

    path = PROMPTS_DIR / filename
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Missing SQListo prompt template: {path}. "
            "Keep the complete prompts directory next to sqlisto_prompts.py."
        ) from exc

    template = Template(text)
    fields = set()
    for match in template.pattern.finditer(text):
        if match.group("invalid") is not None:
            raise ValueError(
                f"Invalid placeholder in {path}. "
                "Use ${name}; write $$ for a literal dollar sign."
            )
        field = match.group("named") or match.group("braced")
        if field:
            fields.add(field)

    expected = _FIELDS[filename]
    if fields != expected:
        missing = ", ".join(sorted(expected - fields)) or "none"
        unknown = ", ".join(sorted(fields - expected)) or "none"
        raise ValueError(
            f"Incorrect placeholders in {path}. "
            f"Missing: {missing}. Unknown: {unknown}."
        )
    if set(values) != expected:
        raise ValueError(f"Incomplete or unexpected context for {filename}.")

    # Context values are inserted literally. Do not render the result again:
    # questions, schemas and manuals may themselves contain dollars or braces.
    return template.substitute(values)


def build_router_prompt(question: str, tools_manual: str,
                        catalog: dict[str, list[str]]) -> str:
    """Build the compact routing prompt using the existing public signature."""
    del tools_manual  # The compact router retains this argument for compatibility.
    catalog_json = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
    return _render_prompt(
        "router.txt", catalog_json=catalog_json, question=question,
    )


def build_prompt(schema: str, question: str, knowledge: str) -> str:
    """Build the natural-language-to-SQL prompt."""
    return _render_prompt(
        "sql_generation.txt",
        knowledge_section=knowledge or "No external semantic manual was provided.",
        schema=schema,
        question=question,
    )


def build_repair_prompt(schema: str, question: str, knowledge: str,
                        rejected_sql: str, sqlite_error: str) -> str:
    """Build the repair prompt from the rejected query and SQLite's error."""
    return _render_prompt(
        "sql_repair.txt",
        knowledge_section=knowledge or "No external semantic manual was provided.",
        schema=schema,
        question=question,
        rejected_sql=rejected_sql,
        sqlite_error=sqlite_error,
    )
