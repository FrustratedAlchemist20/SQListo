#!/usr/bin/env python3

import argparse
import csv
import json
import random
import re
import sqlite3
import statistics
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd

import xyz2db_assistant as xyz2db_llm

from xyz2db_assistant import (
    DEFAULT_KNOWLEDGE_FILE,
    DEFAULT_LLAMA_BIN,
    DEFAULT_MODEL,
    DEFAULT_N_TOKENS,
    build_readonly_uri,
    execute_sql,
    generate_valid_sql,
    get_sqlite_schema,
    load_knowledge,
    run_llama_cli,
    validate_paths,
    validate_question,
)

from xyz2db.export import export_frame_data_csv
from xyz2db.fragment_tools.fragments import build_formula, connected_fragments
from xyz2db.kinetics_tools.kinetics_db import (
    compute_and_store_global_kinetics,
    fetch_selected_trajectories,
    iter_frames_for_traj,
)
from xyz2db.reaction_tools.reaction_db import build_reaction_summary
from xyz2db.restore import (
    restore_input_for_trajectory,
    restore_xyz_from_db,
    show_input_from_db,
)
from xyz2db.spectra_tools.spectra import build_spectrum_rows
from xyz2db.spectra_tools.spectra_db import fetch_fragment_rows_for_spectrum


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_TOOLS_FILE = str(BASE_DIR / "sqlisto_tools.txt")
DEFAULT_OUTPUT_DIR = str(BASE_DIR / "outputs")
DEFAULT_ROUTER_TOKENS = 240
DEFAULT_ROUTER_TIMEOUT = 300
DEFAULT_MAX_EXPORTS = 500
DEFAULT_LLAMA_URL = "http://127.0.0.1:8080"
DEFAULT_LLAMA_SERVER_TIMEOUT = 300

# The original CLI function is retained as an automatic fallback.
ORIGINAL_RUN_LLAMA_CLI = run_llama_cli
ACTIVE_LLAMA_URL = DEFAULT_LLAMA_URL
ACTIVE_LLAMA_FALLBACK = True

ALLOWED_ACTIONS = {
    "sql_query",
    "show_input",
    "restore_input",
    "database_summary",
    "reaction_summary",
    "reaction_export_csv",
    "fragment_search",
    "final_fragment_atoms",
    "final_fragment_bond_query",
    "mass_spectrum",
    "mass_spectrum_export_csv",
    "global_kinetics",
    "global_kinetics_export_csv",
    "compare_global_kinetics",
    "stored_kinetics_summary",
    "stored_kinetics_export_csv",
    "stored_kinetics_detailed_export_csv",
    "fragment_first_appearance",
    "export_fragment_event_trajectory",
    "export_trajectory",
    "export_trajectory_with_fragment",
    "export_all_trajectories_with_fragment",
}


TRANSLATIONS = {
    "en": {
        "agent_description": "SQListo Agent: hybrid SQL + XYZ2DB assistant.",
        "agent_plan": "Agent plan",
        "generated_sql": "Generated SQL",
        "stored_input": "Stored trajectory input",
        "restored_input": "Input restored to",
        "traj_uid_required": "A trajectory UID is required.",
        "repairs": "Repairs",
        "result": "Result",
        "no_results": "No results.",
        "database_summary": "Database summary",
        "trajectories": "Trajectories",
        "total_frames": "Total frames",
        "mean_frames": "Mean frames",
        "min_frames": "Minimum frames",
        "max_frames": "Maximum frames",
        "molecules": "Molecules",
        "isomers": "Isomers",
        "methods": "Methods",
        "energies": "Energy labels",
        "fragment_analyses": "Fragment analyses",
        "final_fragments": "Final fragments",
        "by_molecule": "By molecule",
        "by_isomer": "By isomer",
        "by_method": "By method",
        "by_energy": "By energy label",
        "reaction_summary": "Most frequent final reactions",
        "no_reactions": "No reactions were found.",
        "csv_saved": "CSV saved to",
        "fragment_search": "Fragment search",
        "final_fragment_atoms": "Final fragment atom composition",
        "final_fragment_bond_query": "Final-fragment bond participation",
        "bond_not_recognised": (
            "Bond not recognised in the stored analysis. Please check that "
            "the atom labels and numbering are correct."
        ),
        "candidate_bond_note": (
            "Candidate atom pairs are inferred from atoms ending in different "
            "final fragments; initial bonding is not revalidated."
        ),
        "no_matches": "No matches were found.",
        "spectrum": "Theoretical mass spectrum",
        "no_peaks": "No peaks were found.",
        "global_kinetics": "Global disappearance kinetics",
        "stored_kinetics": "Stored kinetic constants",
        "kinetics_comparison": "Global kinetics comparison",
        "comparison_group": "Comparison group",
        "combined_csv": "Combined comparison CSV",
        "detailed_files": "Detailed analysis files",
        "molecule": "Molecule",
        "isomer": "Isomer",
        "method": "Method",
        "energy": "Energy label",
        "persistence_frames": "Persistence frames",
        "window_mode": "Window mode",
        "events": "Events",
        "censored": "Censored",
        "event_fraction": "Event fraction",
        "mean_time": "Mean time / ps",
        "median_time": "Median time / ps",
        "regression_k": "Regression k / ps^-1",
        "regression_half_life": "Regression half-life / ps",
        "mle_k": "MLE k / ps^-1",
        "mle_half_life": "MLE half-life / ps",
        "fragment_appearance": "First persistent fragment appearance",
        "requested_formula": "Requested formula",
        "canonical_formula": "Canonical formula",
        "not_observed": "Not observed",
        "std_time": "Standard deviation / ps",
        "minimum_time": "Minimum / ps",
        "maximum_time": "Maximum / ps",
        "analysing_trajectory": "Analysing trajectory",
        "exported_trajectory": "Exported trajectory",
        "trajectory_code": "Trajectory code",
        "frames": "Frames",
        "event_time": "Event time / ps",
        "xyz": "XYZ",
        "energy_time_csv": "Energy/time CSV",
        "bulk_export": "Bulk export completed",
        "matches": "Matches",
        "exported": "Exported",
        "not_exported": "Not exported",
        "folder": "Folder",
        "manifest": "Manifest",
        "formula_required": "A fragment formula is required.",
        "formula_or_mass_required": "A formula or a mass value is required.",
        "no_trajectories": "No trajectories were found for the selected filters.",
        "fragment_not_found": (
            "The fragment was not detected with the requested criterion "
            "in any trajectory."
        ),
        "unknown_value": "Unknown value for {field}: {value!r}.",
        "available_values": "Available values",
        "file_not_found": "The file does not exist",
        "unsafe_output_folder": "The output folder is not safe.",
        "unsafe_output_path": "The output path is not safe.",
        "nothing_to_export": "There are no results to export.",
        "model_no_plan": "The model did not return a plan.",
        "json_not_found": "No JSON object was found in the model output.",
        "json_invalid": "The JSON plan could not be parsed.",
        "action_not_allowed": "Action not allowed",
        "arguments_must_object": "The arguments field must be a JSON object.",
        "action_not_implemented": "Action not implemented",
        "error": "ERROR",
    },
    "es": {
        "agent_description": "SQListo Agent: asistente híbrido SQL + XYZ2DB.",
        "agent_plan": "Plan del agente",
        "generated_sql": "SQL generado",
        "stored_input": "Input almacenado de la trayectoria",
        "restored_input": "Input restaurado en",
        "traj_uid_required": "Debes indicar un UID de trayectoria.",
        "repairs": "Reparaciones",
        "result": "Resultado",
        "no_results": "Sin resultados.",
        "database_summary": "Resumen de la base",
        "trajectories": "Trayectorias",
        "total_frames": "Frames totales",
        "mean_frames": "Frames promedio",
        "min_frames": "Frames mínimo",
        "max_frames": "Frames máximo",
        "molecules": "Moléculas",
        "isomers": "Isómeros",
        "methods": "Métodos",
        "energies": "Energías",
        "fragment_analyses": "Análisis de fragmentos",
        "final_fragments": "Fragmentos finales",
        "by_molecule": "Por molécula",
        "by_isomer": "Por isómero",
        "by_method": "Por método",
        "by_energy": "Por energía",
        "reaction_summary": "Reacciones finales más frecuentes",
        "no_reactions": "No se encontraron reacciones.",
        "csv_saved": "CSV guardado en",
        "fragment_search": "Búsqueda de fragmentos",
        "final_fragment_atoms": "Composición atómica del fragmento final",
        "final_fragment_bond_query": "Participación del enlace en la fragmentación final",
        "bond_not_recognised": (
            "Enlace no reconocido en el análisis almacenado. Revisa que las "
            "etiquetas y la numeración atómica sean correctas."
        ),
        "candidate_bond_note": (
            "Los pares candidatos se infieren porque sus átomos terminan en "
            "fragmentos finales diferentes; no se revalida el enlace inicial."
        ),
        "no_matches": "No se encontraron coincidencias.",
        "spectrum": "Espectro teórico",
        "no_peaks": "No se encontraron picos.",
        "global_kinetics": "Cinética global de desaparición",
        "stored_kinetics": "Constantes cinéticas almacenadas",
        "kinetics_comparison": "Comparación de cinética global",
        "comparison_group": "Grupo de comparación",
        "combined_csv": "CSV comparativo conjunto",
        "detailed_files": "Archivos de análisis detallado",
        "molecule": "Molécula",
        "isomer": "Isómero",
        "method": "Método",
        "energy": "Energía",
        "persistence_frames": "Persistencia frames",
        "window_mode": "Modo de ventana",
        "events": "Eventos",
        "censored": "Censuradas",
        "event_fraction": "Fracción eventos",
        "mean_time": "Tiempo medio / ps",
        "median_time": "Mediana / ps",
        "regression_k": "k regresión / ps^-1",
        "regression_half_life": "Semivida regresión / ps",
        "mle_k": "k MLE / ps^-1",
        "mle_half_life": "Semivida MLE / ps",
        "fragment_appearance": "Primera aparición persistente del fragmento",
        "requested_formula": "Fórmula solicitada",
        "canonical_formula": "Fórmula canónica",
        "not_observed": "No observado",
        "std_time": "Desviación / ps",
        "minimum_time": "Mínimo / ps",
        "maximum_time": "Máximo / ps",
        "analysing_trajectory": "Analizando trayectoria",
        "exported_trajectory": "Trayectoria exportada",
        "trajectory_code": "Código de trayectoria",
        "frames": "Frames",
        "event_time": "Tiempo evento / ps",
        "xyz": "XYZ",
        "energy_time_csv": "CSV energía/tiempo",
        "bulk_export": "Exportación masiva completada",
        "matches": "Coincidencias",
        "exported": "Exportadas",
        "not_exported": "No exportadas",
        "folder": "Carpeta",
        "manifest": "Manifest",
        "formula_required": "Debes indicar una fórmula.",
        "formula_or_mass_required": "Debes indicar una fórmula o una masa.",
        "no_trajectories": "No se encontraron trayectorias para los filtros.",
        "fragment_not_found": (
            "El fragmento no apareció con el criterio solicitado "
            "en ninguna trayectoria."
        ),
        "unknown_value": "Valor desconocido para {field}: {value!r}.",
        "available_values": "Valores disponibles",
        "file_not_found": "No existe el archivo",
        "unsafe_output_folder": "La carpeta de salida no es segura.",
        "unsafe_output_path": "La ruta de salida no es segura.",
        "nothing_to_export": "No hay resultados para exportar.",
        "model_no_plan": "El modelo no devolvió ningún plan.",
        "json_not_found": "No se encontró un objeto JSON en la salida.",
        "json_invalid": "No se pudo interpretar el plan JSON.",
        "action_not_allowed": "Acción no permitida",
        "arguments_must_object": "El campo arguments debe ser un objeto JSON.",
        "action_not_implemented": "Acción sin implementar",
        "error": "ERROR",
    },
}


CURRENT_LANGUAGE = "en"


def tr(language: str, key: str) -> str:
    selected = language if language in TRANSLATIONS else "en"
    return TRANSLATIONS[selected].get(key, key)


def msg(key: str, **kwargs: Any) -> str:
    template = tr(CURRENT_LANGUAGE, key)
    return template.format(**kwargs)


def load_text_file(path: str | None) -> str:
    if not path:
        return ""
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{msg('file_not_found')}:\n{resolved}")
    return resolved.read_text(encoding="utf-8", errors="replace").strip()


def clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    if text.casefold() in {
        "none", "null", "any", "all",
        "todos", "todas", "cualquiera",
        "ninguno", "ninguna",
        "unknown", "unspecified", "not specified",
        "not available", "n/a",
    }:
        return None

    return text

def safe_int(value: Any, default: int, minimum: int | None = None,
             maximum: int | None = None) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    if minimum is not None:
        result = max(result, minimum)
    if maximum is not None:
        result = min(result, maximum)
    return result


def safe_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().casefold()
    if text in {"true", "yes", "y", "1", "sí", "si", "verdadero"}:
        return True
    if text in {"false", "no", "n", "0", "falso"}:
        return False
    return default


def slugify(value: str | None, fallback: str = "all") -> str:
    if not value:
        return fallback
    text = re.sub(r"[^A-Za-z0-9_.+-]+", "_", str(value).strip())
    text = text.strip("._")
    return text or fallback


def safe_output_folder(output_dir: str, folder_name: str) -> Path:
    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    folder = (root / slugify(folder_name, "result")).resolve()
    if folder.parent != root:
        raise ValueError(msg("unsafe_output_folder"))
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def safe_output_path(output_dir: str, filename: str | None,
                     default_filename: str, required_suffix: str) -> Path:
    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    raw_name = Path(str(filename)).name if filename else default_filename
    safe_name = slugify(raw_name, default_filename)
    if not safe_name.casefold().endswith(required_suffix.casefold()):
        safe_name += required_suffix
    result = (root / safe_name).resolve()
    if result.parent != root:
        raise ValueError(msg("unsafe_output_path"))
    return result


def export_dict_rows_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    if not rows:
        raise ValueError(msg("nothing_to_export"))
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def get_database_catalog(db_path: str) -> dict[str, list[str]]:
    uri = build_readonly_uri(db_path)
    conn = sqlite3.connect(uri, uri=True)
    try:
        catalog: dict[str, list[str]] = {}
        for output_key, column in [
            ("molecules", "molecule"),
            ("isomers", "isomer"),
            ("methods", "method_label"),
            ("energy_labels", "energy_label"),
        ]:
            rows = conn.execute(
                f"""
                SELECT DISTINCT {column}
                FROM trajectories
                WHERE {column} IS NOT NULL
                  AND TRIM(CAST({column} AS TEXT)) <> ''
                ORDER BY {column}
                """
            ).fetchall()
            catalog[output_key] = [str(row[0]) for row in rows]
        return catalog
    finally:
        conn.close()

def validate_explicit_energy_labels(
    question: str,
    catalog: dict[str, list[str]],
) -> None:
    """
    Reject explicit ZPEx labels that are not present in the database.
    """
    requested_labels = re.findall(
        r"\bZPEx\d+(?:\.\d+)?\b",
        question,
        flags=re.IGNORECASE,
    )

    available_labels = {
        value.casefold(): value
        for value in catalog.get("energy_labels", [])
    }

    for requested in requested_labels:
        if requested.casefold() not in available_labels:
            raise ValueError(
                f"Unknown energy label: {requested!r}.\n"
                f"Available values: "
                f"{catalog.get('energy_labels', [])}"
            )        

def resolve_catalog_value(requested: str | None, available: list[str],
                          field_name: str) -> str | None:
    requested = clean_optional_text(requested)
    if requested is None:
        return None
    mapping = {value.casefold(): value for value in available}
    resolved = mapping.get(requested.casefold())
    if resolved is None:
        raise ValueError(
            f"{msg('unknown_value', field=field_name, value=requested)}\n"
            f"{msg('available_values')}: {available}"
        )
    return resolved


def normalize_filters(arguments: dict[str, Any],
                      catalog: dict[str, list[str]]) -> dict[str, str | None]:
    return {
        "molecule": resolve_catalog_value(
            arguments.get("molecule"), catalog["molecules"], "molecule"
        ),
        "isomer": resolve_catalog_value(
            arguments.get("isomer"), catalog["isomers"], "isomer"
        ),
        "method": resolve_catalog_value(
            arguments.get("method"), catalog["methods"], "method"
        ),
        "energy_label": resolve_catalog_value(
            arguments.get("energy_label"), catalog["energy_labels"], "energy_label"
        ),
    }


def canonicalize_formula(formula: str) -> str:
    text = str(formula).strip().replace(" ", "")
    if not text:
        raise ValueError(msg("formula_required"))

    charge_suffix = ""
    if text.endswith("+"):
        charge_suffix = "+"
        text = text[:-1]
    elif text.endswith("-"):
        charge_suffix = "-"
        text = text[:-1]

    tokens = re.findall(r"([A-Z][a-z]?)(\d*)", text)
    reconstructed = "".join(element + count for element, count in tokens)
    if reconstructed != text:
        raise ValueError(f"Unrecognised chemical formula: {formula!r}")

    counts: dict[str, int] = {}
    for element, count_text in tokens:
        counts[element] = counts.get(element, 0) + (
            int(count_text) if count_text else 1
        )

    preferred_order = [
        "C", "H", "Cl", "Br", "N", "O", "S", "Si", "P", "F", "I"
    ]
    ordered = [element for element in preferred_order if element in counts]
    ordered.extend(sorted(element for element in counts if element not in preferred_order))

    parts: list[str] = []
    for element in ordered:
        parts.append(element)
        if counts[element] != 1:
            parts.append(str(counts[element]))
    return "".join(parts) + charge_suffix


def should_route_directly_to_sql(question: str) -> bool:
    """Return True for clearly read-only database questions.

    These requests do not need the LLM router. They are sent directly to the
    SQL generator, saving one complete model inference.
    """
    text = question.casefold().strip()

    # Specialist actions must still go through the router because they invoke
    # Python tools rather than a normal SQL query.
    specialist_signals = (
        "fragment", "fragments",
        "fragment formula",
        "final-fragment",
        "stored final-fragment",
        "fragment records",
        "reaction summary",
        "reaction classes",
        "reaction channel",
        "export", "exporta", "exportar", "extract", "extrae", "extraer",
        "save", "guardar", "write", "xyz",
        "mass spectrum", "spectrum", "espectro",
        "kinetic", "kinetics", "cinética", "cinetica",
        "first appearance", "persistent appearance", "aparición", "aparicion",
        "final fragment atoms", "which atoms make up", "qué átomos componen",
        "que atomos componen", "atom composition",
        "bond", "enlace", "atom pair", "par de átomos", "par de atomos",
        "most frequent final reactions", "most common reaction",
        "reacciones finales más frecuentes", "reacciones mas frecuentes",
        "theoretical spectrum", "espectro teórico", "espectro teorico",
        "stored input", "input file", "input completo", "archivo de input",
        "show input", "restore input", "restaura el input",
        "muéstrame el input", "muestrame el input", "md.in",
    )
    if any(signal in text for signal in specialist_signals):
        return False

    # Broad overview requests are handled by the predefined summary tool.
    summary_signals = (
        "general overview", "database overview", "complete overview",
        "summary of the database", "summarise all", "summarize all",
        "resumen general", "resumen de la base", "resume todos",
    )
    if any(signal in text for signal in summary_signals):
        return False

    # Strong indicators of a normal read-only SQL request.
    sql_signals = (
        "count", "how many", "number of", "records", "rows",
        "average", "mean", "median", "minimum", "maximum", "min ", "max ",
        "group by", "grouped by", "jointly by", "separately by",
        "distinct", "percentage", "percent", "rank", "ranking", "top ",
        "list ", "show ", "check whether", "whether", "does ", "has ",
        "compare", "comparison", "distribution",
        "cuánt", "cuant", "número de", "numero de", "registros", "filas",
        "promedio", "media", "mediana", "mínimo", "minimo", "máximo", "maximo",
        "agrupar", "agrupa", "agrupado", "porcentaje", "comparar", "compara",
        "listar", "lista",
        "mostrar", "muestra", "muéstrame", "muestrame",
        "buscar", "busca", "búscame", "buscame",
        "encuentra", "localiza",
        "comprobar", "tiene ",
    )
    return any(signal in text for signal in sql_signals)


def build_router_prompt(question: str, tools_manual: str,
                        catalog: dict[str, list[str]]) -> str:
    """Build a compact routing prompt.

    The previous prompt repeated the full tools manual and many examples,
    exceeding 4k tokens. This compact version keeps only the routing decisions
    that the model actually needs. The deterministic normalizer still applies
    additional safeguards after routing.
    """
    del tools_manual  # Kept in the signature for backwards compatibility.
    catalog_json = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))

    return f"""<|im_start|>system
You are SQListo Agent, an offline router for a computational-chemistry SQLite database.
Return exactly one JSON object and nothing else.

Allowed actions:
sql_query, show_input, restore_input, database_summary,
reaction_summary, reaction_export_csv,
fragment_search, final_fragment_atoms, final_fragment_bond_query,
mass_spectrum, mass_spectrum_export_csv, global_kinetics,
global_kinetics_export_csv, compare_global_kinetics,
stored_kinetics_summary, stored_kinetics_export_csv,
stored_kinetics_detailed_export_csv,
fragment_first_appearance, export_fragment_event_trajectory,
export_trajectory, export_trajectory_with_fragment,
export_all_trajectories_with_fragment.

Routing rules:
- sql_query: custom counts, lists, filters, GROUP BY, averages, rankings,
  percentages, comparisons, existence checks, and queries over stored columns.
  For sql_query always return arguments={{}}.
- show_input: print the complete stored input associated with an exact traj_uid.
- restore_input: write the stored input associated with an exact traj_uid to a file.
  Include filename only when the user explicitly provides a simple filename.
- database_summary: only a broad predefined overview.
- reaction_summary: top/most frequent stored final reactions.
- reaction_export_csv: same, only when CSV export is explicitly requested.
- fragment_search: find/count stored final fragments by formula or mass; no frame scan.
- final_fragment_atoms: numbered atoms composing a stored final fragment.
- final_fragment_bond_query: numbered atom pair or element pair ending in different
  stored final fragments. User atom numbers are 1-based.
- mass_spectrum: theoretical spectrum from stored fragments.
- mass_spectrum_export_csv: spectrum plus explicit CSV export.
- global_kinetics: calculate and store one kinetic condition on demand.
- global_kinetics_export_csv: calculate/store one condition and export detailed CSV files.
- compare_global_kinetics: calculate and compare kinetic groups.
- stored_kinetics_summary: read previously stored kinetic constants only.
- stored_kinetics_export_csv: export a compact CSV of previously stored kinetic
  constants, including energy metadata from md_inputs. Never rescan frames.
- stored_kinetics_detailed_export_csv: export the complete stored result for one
  or more kinetic conditions as summary, events and survival-point CSV files.
- global_kinetics: calculate and store one kinetic condition on demand.
  Treat "global kinetics", "cinética global" and "k global" as equivalent.
  Never recalculate or rescan frames.
- fragment_first_appearance: scan frames for first persistent fragment appearance.
- export_fragment_event_trajectory: export the trajectory selected by fragment event time.
- export_trajectory: export by exact traj_uid or metadata selection.
- export_trajectory_with_fragment: export one trajectory containing a fragment.
- export_all_trajectories_with_fragment: export every matching trajectory.
- global_kinetics_export_csv: calculate/store one condition and export detailed CSV files.
  Treat "export the global k", "exporta la k global" and
  "exporta la cinética global" as equivalent.

Rules:
1. The user may write in English or Spanish.
2. Use only catalogue values below; matching is case-insensitive.
3. Use null for unspecified filters. Never infer an isomer unless explicitly stated.
4. A value beginning with traj_ is a trajectory UID.
5. Never choose an export action unless export/save/extract is explicit.
6. For stored final-fragment questions, do not choose any-frame scanning.
7. fragment_scope is final_frame, any_frame, or persistent.
8. selection is first, last, random, longest, shortest, earliest, or latest.
9. Keep arguments minimal: include only fields needed for the selected action.

Required JSON form:
{{"action":"action_name","arguments":{{}}}}

Examples:
User: Give me a general overview of the database.
Assistant: {{"action":"database_summary","arguments":{{}}}}
User: Show the 20 most frequent final reactions for Azaconazole at ZPEx3.
Assistant: {{"action":"reaction_summary","arguments":{{"molecule":"Azaconazole","energy_label":"ZPEx3","top_n":20}}}}
User: Which numbered atoms form final fragment C2H3N3 for Azaconazole PM6 ZPEx3?
Assistant: {{"action":"final_fragment_atoms","arguments":{{"formula":"C2H3N3","molecule":"Azaconazole","method":"PM6","energy_label":"ZPEx3"}}}}
User: Export trajectory traj_abc123.
Assistant: {{"action":"export_trajectory","arguments":{{"traj_uid":"traj_abc123"}}}}
User: Show the complete stored input for trajectory traj_abc123.
Assistant: {{"action":"show_input","arguments":{{"traj_uid":"traj_abc123"}}}}
User: Restore the input for trajectory traj_abc123 as azaconazole_md.in.
Assistant: {{"action":"restore_input","arguments":{{"traj_uid":"traj_abc123","filename":"azaconazole_md.in"}}}}
User: Summarise stored kinetic constants for Azaconazole and Tebuconazole at ZPEx3 for PM6 and uB3LYP. Do not recalculate.
Assistant: {{"action":"stored_kinetics_summary","arguments":{{}}}}
User: Export stored kinetic constants for Azaconazole and Tebuconazole at ZPEx3 to CSV. Do not recalculate.
Assistant: {{"action":"stored_kinetics_export_csv","arguments":{{}}}}

AVAILABLE_DATABASE_VALUES={catalog_json}
<|im_end|>
<|im_start|>user
{question}
<|im_end|>
<|im_start|>assistant
"""

def llama_server_healthcheck(
    base_url: str,
    timeout_seconds: int = 5,
) -> bool:
    """Return True when the local llama-server health endpoint is ready."""
    url = base_url.rstrip("/") + "/health"
    request = urllib.request.Request(url=url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("status") == "ok"
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        json.JSONDecodeError,
        OSError,
    ):
        return False


def run_llama_server(
    prompt: str,
    n_tokens: int,
    timeout_seconds: int,
    base_url: str | None = None,
) -> str:
    """Send a raw prompt to the already-loaded local llama-server model."""
    selected_url = (base_url or ACTIVE_LLAMA_URL).rstrip("/")
    endpoint = selected_url + "/completion"

    payload = {
        "prompt": prompt,
        "n_predict": int(n_tokens),
        "temperature": 0.0,
        "stream": False,
        "cache_prompt": True,
        "stop": ["<|im_end|>", "<|im_start|>"],
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url=endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=max(1, int(timeout_seconds)),
        ) as response:
            raw_payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"llama-server returned HTTP {exc.code}: {details}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            f"Could not contact llama-server at {selected_url}: {exc}"
        ) from exc

    try:
        result = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "llama-server returned invalid JSON."
        ) from exc

    content = result.get("content")
    if not isinstance(content, str):
        raise RuntimeError(
            "llama-server response does not contain a text 'content' field."
        )

    return content.strip()


def run_llama_backend(
    model_path: str,
    prompt: str,
    llama_cli: str,
    n_tokens: int,
    timeout_seconds: int,
) -> str:
    """
    Drop-in replacement for run_llama_cli.

    It uses the local llama-server first. If the server is unavailable and
    fallback is enabled, it transparently uses the original llama-cli path.
    """
    try:
        return run_llama_server(
            prompt=prompt,
            n_tokens=n_tokens,
            timeout_seconds=timeout_seconds,
        )
    except RuntimeError as server_error:
        if not ACTIVE_LLAMA_FALLBACK:
            raise

        print(
            "WARNING: llama-server is unavailable; falling back to llama-cli.\n"
            f"Reason: {server_error}",
            file=sys.stderr,
        )

        return ORIGINAL_RUN_LLAMA_CLI(
            model_path=model_path,
            prompt=prompt,
            llama_cli=llama_cli,
            n_tokens=n_tokens,
            timeout_seconds=timeout_seconds,
        )


def configure_llm_backend(
    llama_url: str,
    allow_cli_fallback: bool,
) -> str:
    """Configure SQListo and the imported SQL generator to use llama-server."""
    global ACTIVE_LLAMA_URL, ACTIVE_LLAMA_FALLBACK

    ACTIVE_LLAMA_URL = llama_url.rstrip("/")
    ACTIVE_LLAMA_FALLBACK = bool(allow_cli_fallback)

    # generate_valid_sql() resolves run_llama_cli from the globals of the
    # xyz2db_assistant module. Replacing that global redirects SQL generation
    # and SQL repair calls to the same persistent llama-server backend.
    xyz2db_llm.run_llama_cli = run_llama_backend

    if llama_server_healthcheck(ACTIVE_LLAMA_URL):
        return "llama-server"

    if ACTIVE_LLAMA_FALLBACK:
        return "llama-cli fallback"

    raise RuntimeError(
        f"llama-server is not available at {ACTIVE_LLAMA_URL}. "
        "Start it first or omit --no-llama-fallback."
    )

def extract_json_object(text: str) -> dict[str, Any]:
    if not text or not text.strip():
        raise ValueError(msg("model_no_plan"))
    cleaned = text.replace("\r", "\n")
    fenced = re.findall(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    )
    candidates = fenced or re.findall(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not candidates:
        raise ValueError(
            f"{msg('json_not_found')}\n\n"
            f"Model output:\n{cleaned}"
        )
    last_error: Exception | None = None
    for candidate in reversed(candidates):
        try:
            repaired_candidate = re.sub(
                r'"atom_pair"\s*:\s*([1-9]\d*)\s*,\s*([1-9]\d*)',
                r'"atom_1": \1, "atom_2": \2',
                candidate,
            )

            value = json.loads(repaired_candidate)
            if not isinstance(value, dict):
                raise ValueError("El plan JSON no es un objeto.")
            return value
        except Exception as exc:
            last_error = exc
    raise ValueError(
        f"{msg('json_invalid')}\n"
        f"Last error: {last_error}\n\nModel output:\n{cleaned}"
    )


def validate_plan(plan: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    action = plan.get("action")
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"{msg('action_not_allowed')}: {action!r}")
    arguments = plan.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise ValueError(msg("arguments_must_object"))

    # SQL generation uses the complete natural-language question. Router
    # arguments are irrelevant and small models often fill them with noisy
    # defaults or lists that scalar filter validation cannot accept.
    if action == "sql_query":
        arguments = {}

    return action, arguments


def normalize_agent_plan(
    action: str,
    arguments: dict[str, Any],
    question: str,
    catalog: dict[str, list[str]],
) -> tuple[str, dict[str, Any]]:
    """Apply deterministic safeguards to common small-model routing errors."""
    fixed = dict(arguments)
    question_text = question.strip()
    question_cf = question_text.casefold()

    # ---------------------------------------------------------
    # Normalise common aliases produced by compact local models
    # ---------------------------------------------------------

    alias_map = {
        "fragment": "formula",
        "frame_count": "persist_frames",
        "atom1": "atom_1",
        "atom2": "atom_2",
    }

    for alias, canonical in alias_map.items():
        if fixed.get(canonical) is None and fixed.get(alias) is not None:
            fixed[canonical] = fixed.pop(alias)

    # Accept a valid atom-pair list.
    atom_pair = fixed.pop("atom_pair", None)
    if (
        isinstance(atom_pair, (list, tuple))
        and len(atom_pair) == 2
    ):
        fixed.setdefault("atom_1", atom_pair[0])
        fixed.setdefault("atom_2", atom_pair[1])

    # Remove unsupported values invented by the router.
    fixed.pop("fragment_event_time", None)

    # Convert charge-related aliases into the argument used by the
    # mass-spectrum implementation.
    if fixed.get("charged_only") is None:
        charge_guess = fixed.pop("charge_guess", None)
        charge = fixed.pop("charge", None)

        if charge_guess in (1, "1", "+1", 1.0):
            fixed["charged_only"] = True
        elif charge in (1, "1", "+1", 1.0):
            fixed["charged_only"] = True

    # Recover catalogue values omitted by the small router model.
    # Never use unrestricted substring matching for short labels such as
    # isomer "E" or "Z", because they occur inside ordinary words.
    def mentioned_catalog_value(value: str) -> bool:
        escaped = re.escape(value)
        return re.search(
            rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])",
            question_text,
            flags=re.IGNORECASE,
        ) is not None

    for argument_key, catalog_key in (
        ("molecule", "molecules"),
        ("method", "methods"),
        ("energy_label", "energy_labels"),
    ):
        if clean_optional_text(fixed.get(argument_key)) is None:
            for value in sorted(catalog.get(catalog_key, []), key=len, reverse=True):
                if mentioned_catalog_value(value):
                    fixed[argument_key] = value
                    break

    # Isomers are recovered only when the question explicitly identifies an
    # isomer. This prevents hallucinated filters such as isomer="E".
    if clean_optional_text(fixed.get("isomer")) is None:
        isomer_context = re.search(
            r"(?:isomer|isómero|isomero)\s*[:=]?\s*([A-Za-z0-9_+-]+)",
            question_text,
            flags=re.IGNORECASE,
        )
        if isomer_context:
            requested_isomer = isomer_context.group(1)
            for value in catalog.get("isomers", []):
                if value.casefold() == requested_isomer.casefold():
                    fixed["isomer"] = value
                    break
    else:
        # Remove a router-invented isomer unless it is explicitly present in
        # the user question with an isomer label.
        planned_isomer = clean_optional_text(fixed.get("isomer"))
        explicit_isomer = re.search(
            r"(?:isomer|isómero|isomero)\s*[:=]?\s*"
            + re.escape(planned_isomer or ""),
            question_text,
            flags=re.IGNORECASE,
        )
        if planned_isomer and explicit_isomer is None:
            fixed["isomer"] = None

    # Recover a chemical formula written immediately after the words
    # fragment/fragmento when the router omitted it.
    if clean_optional_text(fixed.get("formula")) is None:
        formula_patterns = (
            r"(?:fragmento|fragment)"
            r"(?:\s+(?:formula|fórmula))?"
            r"\s+([A-Z][A-Za-z0-9]*[+-]?)",

            r"(?:appearance|occurrence)\s+of"
            r"(?:\s+(?:fragment|fragment formula))?"
            r"\s+([A-Z][A-Za-z0-9]*[+-]?)",

            r"(?:aparición|aparicion|ocurrencia)\s+de"
            r"(?:l|l fragmento|la fórmula|la formula)?"
            r"\s*([A-Z][A-Za-z0-9]*[+-]?)",
        )

        for pattern in formula_patterns:
            formula_match = re.search(
                pattern,
                question_text,
                flags=re.IGNORECASE,
            )

            if not formula_match:
                continue

            candidate_formula = formula_match.group(1)

            try:
                fixed["formula"] = canonicalize_formula(
                    candidate_formula
                )
                break
            except ValueError:
                continue
                
        if formula_match:
            candidate_formula = formula_match.group(1)
            try:
                fixed["formula"] = canonicalize_formula(candidate_formula)
            except ValueError:
                pass

    # A trajectory UID is globally unique and must never be treated as metadata.
    uid_match = re.search(r"\btraj_[A-Za-z0-9]+\b", question_text)
    if uid_match:
        traj_uid = uid_match.group(0)
        fixed["traj_uid"] = traj_uid
        for key in ("molecule", "isomer", "method", "energy_label"):
                fixed["traj_uid"] = traj_uid

        export_words = (
            "export", "exporta", "exportar", "extrae", "extraer",
            "guarda", "guardar", "save", "write",
        )
        if any(word in question_cf for word in export_words):
            action = "export_trajectory"
            fixed.pop("selection", None)

    # Exact input requests are unambiguous and can be corrected
    # deterministically when a trajectory UID is present.
    input_words = (
        "input", "md.in", "input file", "archivo de input",
        "fichero de input",
    )
    show_input_words = (
        "show", "display", "print", "muéstr", "muestr",
        "enseña", "ensena", "ver ", "dime",
    )
    restore_input_words = (
        "restore", "restaura", "restaurar", "recover", "recupera",
        "save", "guarda", "guardar", "write", "export", "exporta",
    )

    if uid_match and any(word in question_cf for word in input_words):
        if any(word in question_cf for word in restore_input_words):
            action = "restore_input"
        elif any(word in question_cf for word in show_input_words):
            action = "show_input"

        fixed["traj_uid"] = uid_match.group(0)
        for key in ("molecule", "isomer", "method", "energy_label"):
            fixed.pop(key, None)

    # Normalise common router aliases for kinetic requests.
    # Small local models often emit "frames" instead of "persist_frames"
    # and a Boolean "censor" instead of "window_mode".
    if fixed.get("persist_frames") is None and fixed.get("frames") is not None:
        fixed["persist_frames"] = fixed.pop("frames")

    if fixed.get("window_mode") is None:
        if fixed.get("censor") is True:
            fixed["window_mode"] = "censor"
        elif fixed.get("common") is True:
            fixed["window_mode"] = "common"

    # Deterministic extraction makes the order of these phrases irrelevant.
    number_words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    persist_match = re.search(
        r"(?:usando|con|with|using|requiring)"
        r"\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
        r"\s+(?:consecutive\s+|persistent\s+)?"
        r"(?:frames?|fotogramas?)",
        question_text,
        flags=re.IGNORECASE,
    )
    if persist_match:
        persist_value = persist_match.group(1).casefold()
        
        fixed["persist_frames"] = (
            int(persist_value)
            if persist_value.isdigit()
            else number_words[persist_value]
        )

    min_points_match = re.search(
        r"(?:mínimo|minimo|al\s+menos|minimum|at\s+least)"
        r"(?:\s+de)?\s+(\d+)\s+"
        r"(?:puntos?|points?)",
        question_text,
        flags=re.IGNORECASE,
    )
    if min_points_match:
        fixed["min_points"] = int(min_points_match.group(1))

    if re.search(r"\bmodo\s+censor\b|\bcensor\s+mode\b", question_text, re.I):
        fixed["window_mode"] = "censor"
    elif re.search(r"\bmodo\s+common\b|\bcommon\s+mode\b", question_text, re.I):
        fixed["window_mode"] = "common"

    export_words = (
        "export", "exporta", "exportar", "extrae", "extraer",
        "guarda", "guardar", "save", "write", "xyz",
    )
    explicitly_exports = any(word in question_cf for word in export_words)

    # Never allow the small router to invent an export action when the user
    # only asked to list, show, search or inspect records.
    export_actions = {
        "export_trajectory",
        "export_trajectory_with_fragment",
        "export_all_trajectories_with_fragment",
        "export_fragment_event_trajectory",
    }
    if action in export_actions and not explicitly_exports:
        action = "sql_query"
        fixed = {}

    # Do not scan/export thousands of trajectories for a read-only fragment query.
    if action in {
        "export_trajectory_with_fragment",
        "export_all_trajectories_with_fragment",
    } and not explicitly_exports:
        if clean_optional_text(fixed.get("formula")) is not None or fixed.get("mz") is not None:
            action = "fragment_search"
            for key in (
                "selection", "fragment_scope", "persist_frames",
                "max_exports", "folder_name", "filename",
            ):
                fixed.pop(key, None)

    # Requests for ranked/frequent reaction patterns are reaction summaries.
    reaction_words = ("reaction", "reactions", "reacción", "reacciones")
    ranking_words = (
        "frequent", "frequency", "most common", "top", "final",
        "frecuente", "frecuentes", "más comunes", "finales",
    )
    if (
        any(word in question_cf for word in reaction_words)
        and any(word in question_cf for word in ranking_words)
        and clean_optional_text(fixed.get("formula")) is None
        and fixed.get("mz") is None
    ):
        action = "reaction_export_csv" if explicitly_exports and "csv" in question_cf else "reaction_summary"

    # Stored final-fragment atom composition queries.
    atom_composition_phrases = (
        "qué átomos", "que atomos", "which atoms", "atom composition",
        "átomos componen", "atomos componen", "atoms make up",
    )
    final_fragment_phrases = (
        "fragmento final", "final fragment", "stored fragment",
        "fragmento almacenado", "ruptura del fragmento",
    )
    if (
        any(phrase in question_cf for phrase in atom_composition_phrases)
        and any(phrase in question_cf for phrase in final_fragment_phrases)
        and clean_optional_text(fixed.get("formula")) is not None
    ):
        action = "final_fragment_atoms"
        # Remove spurious defaults copied by the small model from bond examples.
        for key in ("atom_1", "atom_2", "element_1", "element_2"):
            fixed.pop(key, None)

    # Stored final-fragment bond/atom-pair queries.
    bond_words = bond_words = (
        "enlace",
        "bond",
        "atom pair",
        "atom numbers",
        "atoms",
        "par de átomos",
        "par de atomos",
        "números de átomo",
        "numeros de atomo",
    )
    trajectory_words = ("trayectoria", "trayectorias", "trajectory", "trajectories")
    number_pair = re.search(
        r"(?<![A-Za-z0-9])([1-9]\d*)\s*(?:-|–|—|y|and)\s*([1-9]\d*)(?![A-Za-z0-9])",
        question_text,
        flags=re.IGNORECASE,
    )
    element_pair = re.search(
        r"(?<![A-Za-z])([A-Z][a-z]?)\s*(?:-|–|—|y|and)\s*([A-Z][a-z]?)(?![A-Za-z])",
        question_text,
    )
    if any(word in question_cf for word in bond_words) and (
        number_pair or element_pair
    ):
        action = "final_fragment_bond_query"
        if number_pair:
            fixed["atom_1"] = int(number_pair.group(1))
            fixed["atom_2"] = int(number_pair.group(2))
        if element_pair:
            fixed["element_1"] = element_pair.group(1)
            fixed["element_2"] = element_pair.group(2)

    return action, fixed

def validate_explicit_condition_combination(
    db_path: str,
    question: str,
    catalog: dict[str, list[str]],
) -> None:
    question_cf = question.casefold()

    molecules = [
        value
        for value in catalog.get("molecules", [])
        if re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(value)}"
            rf"(?![A-Za-z0-9_])",
            question,
            flags=re.IGNORECASE,
        )
    ]

    methods = [
        value
        for value in catalog.get("methods", [])
        if re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(value)}"
            rf"(?![A-Za-z0-9_])",
            question,
            flags=re.IGNORECASE,
        )
    ]

    energy_match = re.search(
        r"\bZPEx\d+(?:\.\d+)?\b",
        question,
        flags=re.IGNORECASE,
    )

    if not energy_match:
        return

    requested_energy = energy_match.group(0)

    available_energy = {
        value.casefold(): value
        for value in catalog.get("energy_labels", [])
    }

    if requested_energy.casefold() not in available_energy:
        raise ValueError(
            f"Unknown energy label: {requested_energy!r}.\n"
            f"Available values: "
            f"{catalog.get('energy_labels', [])}"
        )

    requested_energy = available_energy[
        requested_energy.casefold()
    ]

    if not molecules or not methods:
        return

    with sqlite3.connect(db_path) as conn:
        exists = conn.execute(
            """
            SELECT EXISTS(
                SELECT 1
                FROM trajectories
                WHERE molecule = ?
                  AND method_label = ?
                  AND energy_label = ?
            )
            """,
            (
                molecules[0],
                methods[0],
                requested_energy,
            ),
        ).fetchone()[0]

    if not exists:
        raise ValueError(
            "No trajectories are available for the requested "
            f"combination: molecule={molecules[0]!r}, "
            f"method={methods[0]!r}, "
            f"energy_label={requested_energy!r}."
        )

def find_catalog_mentions(
    question: str,
    values: list[str],
) -> list[str]:
    """Return catalogue values explicitly mentioned in the question."""
    matches: list[str] = []

    for value in sorted(values, key=len, reverse=True):
        pattern = (
            rf"(?<![A-Za-z0-9_])"
            rf"{re.escape(value)}"
            rf"(?![A-Za-z0-9_])"
        )

        if re.search(pattern, question, flags=re.IGNORECASE):
            matches.append(value)

    return matches


def build_in_clause(
    column: str,
    values: list[str],
    params: list[Any],
) -> str | None:
    """Build a safe parameterised IN clause."""
    if not values:
        return None

    placeholders = ", ".join("?" for _ in values)
    params.extend(values)
    return f"{column} IN ({placeholders})"


def build_fast_metadata_sql(
    question: str,
    catalog: dict[str, list[str]],
) -> tuple[str, list[Any], str] | None:
    """
    Build deterministic SQL for common trajectory-metadata questions.

    This fast path uses only the trajectories table. It deliberately avoids
    fragments, reactions, spectra and kinetics. Complex questions return None
    and are passed to the normal LLM SQL generator.
    """
    text = question.strip()
    text_cf = text.casefold()

    molecules = find_catalog_mentions(
        text,
        catalog.get("molecules", []),
    )
    methods = find_catalog_mentions(
        text,
        catalog.get("methods", []),
    )
    energy_labels = find_catalog_mentions(
        text,
        catalog.get("energy_labels", []),
    )

    # Isomers such as E and Z are only accepted when explicitly introduced
    # by the words isomer/isómero/isomero.
    isomers: list[str] = []
    isomer_match = re.search(
        r"(?:isomer|isómero|isomero)\s*[:=]?\s*([A-Za-z0-9_+-]+)",
        text,
        flags=re.IGNORECASE,
    )

    if isomer_match:
        requested = isomer_match.group(1).casefold()
        for value in catalog.get("isomers", []):
            if value.casefold() == requested:
                isomers.append(value)
                break

    # Also accept a natural shorthand such as "Diniconazole E" or
    # "Diniconazole Z", but only when the letter follows a recognised
    # molecule name. This avoids detecting ordinary E/Z letters in prose.
    if not isomers:
        for molecule in catalog.get("molecules", []):
            shorthand_match = re.search(
                rf"(?<![A-Za-z0-9_]){re.escape(molecule)}"
                rf"\s*[,;:\-]?\s*([EZ])"
                rf"(?![A-Za-z0-9_])",
                text,
                flags=re.IGNORECASE,
            )
            if shorthand_match:
                requested = shorthand_match.group(1).casefold()
                for value in catalog.get("isomers", []):
                    if value.casefold() == requested:
                        isomers.append(value)
                        break
                if isomers:
                    break

    excluded_signals = (
        "fragment",
        "fragmento",
        "reaction",
        "reacción",
        "reacciones",
        "spectrum",
        "spectra",
        "espectro",
        "kinetic",
        "kinetics",
        "cinética",
        "cinetica",
        "mass",
        "masa",
        "bond",
        "enlace",
        "atom",
        "átomo",
        "atomo",
        "export",
        "csv",
        "trajectory uid",
        "traj_uid",
    )

    if any(signal in text_cf for signal in excluded_signals):
        return None

    params: list[Any] = []
    conditions: list[str] = []

    for clause in (
        build_in_clause("t.molecule", molecules, params),
        build_in_clause("t.method_label", methods, params),
        build_in_clause("t.energy_label", energy_labels, params),
        build_in_clause("t.isomer", isomers, params),
    ):
        if clause:
            conditions.append(clause)

    where_sql = (
        "WHERE " + " AND ".join(conditions)
        if conditions
        else ""
    )

    existence_signals = (
        "check whether",
        "whether",
        "does ",
        "do we have",
        "has records",
        "have records",
        "records available",
        "exist",
        "exists",
        "hay registros",
        "tiene registros",
        "existen registros",
        "dispone de registros",
    )

    if any(signal in text_cf for signal in existence_signals):
        sql = f"""
SELECT
    EXISTS(
        SELECT 1
        FROM trajectories AS t
        {where_sql}
        LIMIT 1
    ) AS records_exist;
"""
        return sql.strip(), params, "deterministic_metadata_exists"

    count_signals = (
        "count trajectories",
        "number of trajectories",
        "how many trajectories",
        "trajectory count",
        "cuántas trayectorias",
        "cuantas trayectorias",
        "número de trayectorias",
        "numero de trayectorias",
    )

    asks_count = any(signal in text_cf for signal in count_signals)
    asks_avg = any(
        signal in text_cf
        for signal in (
            "average",
            "mean",
            "promedio",
            "media de frames",
            "frames medios",
        )
    )
    asks_min = any(
        signal in text_cf
        for signal in (
            "minimum",
            "min frames",
            "mínimo",
            "minimo",
        )
    )
    asks_max = any(
        signal in text_cf
        for signal in (
            "maximum",
            "max frames",
            "máximo",
            "maximo",
        )
    )

    grouping_context = (
        "group" in text_cf
        or "jointly by" in text_cf
        or "separately by" in text_cf
        or "agrup" in text_cf

        # English grouping expressions
        or "by molecule" in text_cf
        or "by method" in text_cf
        or "by energy" in text_cf
        or "by isomer" in text_cf

        or "for each molecule" in text_cf
        or "for each method" in text_cf
        or "for each energy" in text_cf
        or "for each isomer" in text_cf

        or "per molecule" in text_cf
        or "per method" in text_cf
        or "per energy" in text_cf
        or "per isomer" in text_cf

        # Spanish grouping expressions
        or "por molécula" in text_cf
        or "por molecula" in text_cf
        or "por método" in text_cf
        or "por metodo" in text_cf
        or "por energía" in text_cf
        or "por energia" in text_cf
        or "por isómero" in text_cf
        or "por isomero" in text_cf

        or "para cada molécula" in text_cf
        or "para cada molecula" in text_cf
        or "para cada método" in text_cf
        or "para cada metodo" in text_cf
        or "para cada energía" in text_cf
        or "para cada energia" in text_cf
        or "para cada isómero" in text_cf
        or "para cada isomero" in text_cf

        or "por cada molécula" in text_cf
        or "por cada molecula" in text_cf
        or "por cada método" in text_cf
        or "por cada metodo" in text_cf
        or "por cada energía" in text_cf
        or "por cada energia" in text_cf
        or "por cada isómero" in text_cf
        or "por cada isomero" in text_cf
    )


    grouping_columns: list[tuple[str, str]] = []

    if grouping_context:
        if (
            "molecule" in text_cf
            or "molécula" in text_cf
            or "molecula" in text_cf
        ):
            grouping_columns.append(("t.molecule", "molecule"))

        if (
            "isomer" in text_cf
            or "isómero" in text_cf
            or "isomero" in text_cf
        ):
            grouping_columns.append(("t.isomer", "isomer"))

        if "method" in text_cf or "método" in text_cf or "metodo" in text_cf:
            grouping_columns.append(("t.method_label", "method_label"))

        if (
            "energy" in text_cf
            or "energía" in text_cf
            or "energia" in text_cf
        ):
            grouping_columns.append(("t.energy_label", "energy_label"))

    if asks_count or asks_avg or asks_min or asks_max:
        select_parts: list[str] = []
        group_parts: list[str] = []

        for column, alias in grouping_columns:
            select_parts.append(f"{column} AS {alias}")
            group_parts.append(column)

        if asks_count:
            select_parts.append("COUNT(*) AS n_trajectories")
        if asks_avg:
            select_parts.append("AVG(t.nframes) AS avg_frames")
        if asks_min:
            select_parts.append("MIN(t.nframes) AS min_frames")
        if asks_max:
            select_parts.append("MAX(t.nframes) AS max_frames")

        if not select_parts:
            select_parts.append("COUNT(*) AS n_trajectories")

        sql_parts = [
            "SELECT",
            "    " + ",\n    ".join(select_parts),
            "FROM trajectories AS t",
        ]

        if where_sql:
            sql_parts.append(where_sql)

        if group_parts:
            sql_parts.append("GROUP BY " + ", ".join(group_parts))
            sql_parts.append("ORDER BY " + ", ".join(group_parts))

        return (
            "\n".join(sql_parts) + ";",
            params,
            "deterministic_metadata_aggregate",
        )

    list_condition_signals = (
        "show available",
        "list available",
        "which methods",
        "which energies",
        "available energy",
        "available methods",
        "qué métodos",
        "que metodos",
        "qué energías",
        "que energias",
    )

    if any(signal in text_cf for signal in list_condition_signals):
        sql = f"""
SELECT DISTINCT
    t.molecule,
    t.isomer,
    t.method_label,
    t.energy_label
FROM trajectories AS t
{where_sql}
ORDER BY
    t.molecule,
    t.isomer,
    t.method_label,
    t.energy_label;
"""
        return (
            sql.strip(),
            params,
            "deterministic_metadata_conditions",
        )

    # ----------------------------------------------------------
    # D. List/search trajectories using stored metadata
    # ----------------------------------------------------------
    trajectory_list_signals = (
        "list trajectories",
        "list the trajectories",
        "show trajectories",
        "show the trajectories",
        "search trajectories",
        "search the trajectories",
        "find trajectories",
        "find the trajectories",
        "lista las trayectorias",
        "listar trayectorias",
        "muestra las trayectorias",
        "mostrar trayectorias",
        "muéstrame las trayectorias",
        "muestrame las trayectorias",
        "busca las trayectorias",
        "buscar trayectorias",
        "búscame las trayectorias",
        "buscame las trayectorias",
        "encuentra las trayectorias",
        "localiza las trayectorias",
    )

    if any(signal in text_cf for signal in trajectory_list_signals):
        sql = f"""
SELECT
    t.traj_uid,
    t.traj_code,
    t.molecule,
    COALESCE(t.isomer, 'None') AS isomer,
    t.method_label,
    t.energy_label,
    t.nframes
FROM trajectories AS t
{where_sql}
ORDER BY
    t.molecule,
    t.isomer,
    t.method_label,
    t.energy_label,
    t.run_id,
    t.traj_uid
LIMIT 500;
"""
        return (
            sql.strip(),
            params,
            "deterministic_metadata_trajectory_list",
        )

    return None


def execute_parameterised_sql(
    db_path: str,
    sql: str,
    params: list[Any],
) -> pd.DataFrame:
    """Execute deterministic read-only SQL with bound parameters."""
    uri = build_readonly_uri(db_path)

    conn = sqlite3.connect(
        uri,
        uri=True,
        timeout=60,
    )

    try:
        conn.execute("PRAGMA query_only = ON")
        conn.execute("PRAGMA busy_timeout = 60000")

        return pd.read_sql_query(
            sql,
            conn,
            params=params,
        )
    finally:
        conn.close()

def build_filter_sql(filters: dict[str, str | None],
                     alias: str = "t") -> tuple[str, list[Any]]:
    conditions: list[str] = []
    params: list[Any] = []
    mapping = {
        "molecule": f"{alias}.molecule",
        "isomer": f"{alias}.isomer",
        "method": f"{alias}.method_label",
        "energy_label": f"{alias}.energy_label",
    }
    for key, column in mapping.items():
        value = filters.get(key)
        if value is not None:
            conditions.append(f"{column} = ?")
            params.append(value)
    where_sql = " WHERE " + " AND ".join(conditions) if conditions else ""
    return where_sql, params


def tool_database_summary(
    db_path: str,
    filters: dict[str, str | None],
) -> dict[str, Any]:
    uri = build_readonly_uri(db_path)
    conn = sqlite3.connect(uri, uri=True)

    try:
        where_sql, params = build_filter_sql(filters)

        # --------------------------------------------------------------
        # 1. General trajectory summary
        # --------------------------------------------------------------
        summary = conn.execute(
            f"""
            SELECT
                COUNT(*),
                COALESCE(SUM(t.nframes), 0),
                COALESCE(AVG(t.nframes), 0),
                COALESCE(MIN(t.nframes), 0),
                COALESCE(MAX(t.nframes), 0),
                COUNT(DISTINCT t.molecule),
                COUNT(DISTINCT t.isomer),
                COUNT(DISTINCT t.method_label),
                COUNT(DISTINCT t.energy_label)
            FROM trajectories AS t
            {where_sql}
            """,
            tuple(params),
        ).fetchone()

        # --------------------------------------------------------------
        # 2. Stored fragment summary
        # --------------------------------------------------------------
        fragment_data = conn.execute(
            f"""
            SELECT
                COUNT(DISTINCT fa.traj_uid),
                COALESCE(SUM(fa.fragment_count), 0)
            FROM trajectories AS t
            LEFT JOIN fragment_analysis AS fa
              ON fa.traj_uid = t.traj_uid
            {where_sql}
            """,
            tuple(params),
        ).fetchone()

        # --------------------------------------------------------------
        # 3. Generic trajectory breakdown
        # --------------------------------------------------------------
        def trajectory_breakdown(column: str) -> list[dict[str, Any]]:
            rows = conn.execute(
                f"""
                SELECT
                    {column},
                    COUNT(*) AS n_trajectories
                FROM trajectories AS t
                {where_sql}
                GROUP BY {column}
                ORDER BY n_trajectories DESC, {column}
                """,
                tuple(params),
            ).fetchall()

            return [
                {
                    "label": row[0],
                    "n_trajectories": int(row[1]),
                }
                for row in rows
            ]

        # --------------------------------------------------------------
        # 4. Overall stored reaction summary
        #
        # reaction_members contains one row per:
        #     reaction_uid + traj_uid
        # --------------------------------------------------------------
        reaction_totals = conn.execute(
            f"""
            SELECT
                COUNT(DISTINCT rm.reaction_uid) AS n_distinct_reactions,
                COUNT(DISTINCT rm.traj_uid) AS n_reaction_trajectories
            FROM reaction_members AS rm
            JOIN trajectories AS t
              ON t.traj_uid = rm.traj_uid
            {where_sql}
            """,
            tuple(params),
        ).fetchone()

        # --------------------------------------------------------------
        # 5. Reaction breakdown by one trajectory property
        # --------------------------------------------------------------
        def reaction_breakdown(column: str) -> list[dict[str, Any]]:
            rows = conn.execute(
                f"""
                SELECT
                    {column} AS label,
                    COUNT(DISTINCT rm.reaction_uid) AS n_distinct_reactions,
                    COUNT(DISTINCT rm.traj_uid) AS n_reaction_trajectories
                FROM reaction_members AS rm
                JOIN trajectories AS t
                  ON t.traj_uid = rm.traj_uid
                {where_sql}
                GROUP BY {column}
                ORDER BY
                    n_distinct_reactions DESC,
                    n_reaction_trajectories DESC,
                    {column}
                """,
                tuple(params),
            ).fetchall()

            return [
                {
                    "label": row[0],
                    "n_distinct_reactions": int(row[1]),
                    "n_reaction_trajectories": int(row[2]),
                }
                for row in rows
            ]

        # --------------------------------------------------------------
        # 6. Exact reaction breakdown by complete condition
        # --------------------------------------------------------------
        reaction_conditions = conn.execute(
            f"""
            SELECT
                t.molecule,
                t.isomer,
                t.method_label,
                t.energy_label,
                COUNT(DISTINCT rm.reaction_uid) AS n_distinct_reactions,
                COUNT(DISTINCT rm.traj_uid) AS n_reaction_trajectories
            FROM reaction_members AS rm
            JOIN trajectories AS t
              ON t.traj_uid = rm.traj_uid
            {where_sql}
            GROUP BY
                t.molecule,
                t.isomer,
                t.method_label,
                t.energy_label
            ORDER BY
                t.molecule,
                t.isomer,
                t.method_label,
                t.energy_label
            """,
            tuple(params),
        ).fetchall()

        by_reaction_condition = [
            {
                "molecule": row[0],
                "isomer": row[1],
                "method": row[2],
                "energy_label": row[3],
                "n_distinct_reactions": int(row[4]),
                "n_reaction_trajectories": int(row[5]),
            }
            for row in reaction_conditions
        ]

        return {
            "filters": filters,

            # Trajectories
            "n_trajectories": int(summary[0]),
            "total_frames": int(summary[1]),
            "mean_frames": float(summary[2]),
            "min_frames": int(summary[3]),
            "max_frames": int(summary[4]),
            "n_molecules": int(summary[5]),
            "n_isomers": int(summary[6]),
            "n_methods": int(summary[7]),
            "n_energy_labels": int(summary[8]),

            # Fragments
            "n_fragment_analyses": int(fragment_data[0]),
            "stored_fragments": int(fragment_data[1]),

            # Reactions
            "n_distinct_reactions": int(reaction_totals[0]),
            "n_reaction_trajectories": int(reaction_totals[1]),

            # Trajectory breakdowns
            "by_molecule": trajectory_breakdown("t.molecule"),
            "by_isomer": trajectory_breakdown("t.isomer"),
            "by_method": trajectory_breakdown("t.method_label"),
            "by_energy": trajectory_breakdown("t.energy_label"),

            # Reaction breakdowns
            "reactions_by_molecule": reaction_breakdown("t.molecule"),
            "reactions_by_isomer": reaction_breakdown("t.isomer"),
            "reactions_by_method": reaction_breakdown("t.method_label"),
            "reactions_by_energy": reaction_breakdown("t.energy_label"),
            "reactions_by_condition": by_reaction_condition,
        }

    finally:
        conn.close()


def print_database_summary(
    summary: dict[str, Any],
    language: str = "en",
) -> None:
    print(f"\n--- {tr(language, 'database_summary')} ---")

    # --------------------------------------------------------------
    # General values
    # --------------------------------------------------------------
    general_rows = [
        (tr(language, "trajectories"), "n_trajectories"),
        (tr(language, "total_frames"), "total_frames"),
        (tr(language, "mean_frames"), "mean_frames"),
        (tr(language, "min_frames"), "min_frames"),
        (tr(language, "max_frames"), "max_frames"),
        (tr(language, "molecules"), "n_molecules"),
        (tr(language, "isomers"), "n_isomers"),
        (tr(language, "methods"), "n_methods"),
        (tr(language, "energies"), "n_energy_labels"),
        (tr(language, "fragment_analyses"), "n_fragment_analyses"),
        (tr(language, "final_fragments"), "stored_fragments"),
    ]

    for label, key in general_rows:
        value = summary[key]

        if key == "mean_frames":
            print(f"{label:30s}: {value:.2f}")
        else:
            print(f"{label:30s}: {value}")

    # --------------------------------------------------------------
    # Stored reactions
    # --------------------------------------------------------------
    reactions_title = (
        "Stored reaction patterns"
        if language == "en"
        else "Patrones de reacción almacenados"
    )
    reaction_traj_title = (
        "Trajectories with stored reaction"
        if language == "en"
        else "Trayectorias con reacción almacenada"
    )

    print(f"{reactions_title:30s}: {summary['n_distinct_reactions']}")
    print(f"{reaction_traj_title:30s}: {summary['n_reaction_trajectories']}")

    # --------------------------------------------------------------
    # Trajectory breakdowns
    # --------------------------------------------------------------
    for title, key in [
        (tr(language, "by_molecule"), "by_molecule"),
        (tr(language, "by_isomer"), "by_isomer"),
        (tr(language, "by_method"), "by_method"),
        (tr(language, "by_energy"), "by_energy"),
    ]:
        print(f"\n{title}")
        print("-" * len(title))

        for row in summary[key]:
            label = "None" if row["label"] is None else str(row["label"])
            print(f"{label:30s} {row['n_trajectories']:10d}")

    # --------------------------------------------------------------
    # Reaction breakdown helper
    # --------------------------------------------------------------
    def print_reaction_breakdown(
        title: str,
        rows: list[dict[str, Any]],
    ) -> None:
        print(f"\n{title}")
        print("-" * len(title))

        if not rows:
            no_data = (
                "No stored reactions."
                if language == "en"
                else "No hay reacciones almacenadas."
            )
            print(no_data)
            return

        header_label = "Label" if language == "en" else "Etiqueta"
        header_reactions = (
            "Distinct reactions"
            if language == "en"
            else "Reacciones distintas"
        )
        header_trajectories = (
            "Member trajectories"
            if language == "en"
            else "Trayectorias asociadas"
        )

        print(
            f"{header_label:30s} "
            f"{header_reactions:20s} "
            f"{header_trajectories:22s}"
        )

        for row in rows:
            label = "None" if row["label"] is None else str(row["label"])

            print(
                f"{label:30s} "
                f"{row['n_distinct_reactions']:20d} "
                f"{row['n_reaction_trajectories']:22d}"
            )

    print_reaction_breakdown(
        "Reactions by molecule"
        if language == "en"
        else "Reacciones por molécula",
        summary["reactions_by_molecule"],
    )

    print_reaction_breakdown(
        "Reactions by isomer"
        if language == "en"
        else "Reacciones por isómero",
        summary["reactions_by_isomer"],
    )

    print_reaction_breakdown(
        "Reactions by method"
        if language == "en"
        else "Reacciones por método",
        summary["reactions_by_method"],
    )

    print_reaction_breakdown(
        "Reactions by energy label"
        if language == "en"
        else "Reacciones por energía",
        summary["reactions_by_energy"],
    )

    # --------------------------------------------------------------
    # Full condition table
    # --------------------------------------------------------------
    title = (
        "Reactions by complete condition"
        if language == "en"
        else "Reacciones por condición completa"
    )

    print(f"\n{title}")
    print("-" * len(title))

    rows = summary["reactions_by_condition"]

    if not rows:
        no_data = (
            "No stored reactions."
            if language == "en"
            else "No hay reacciones almacenadas."
        )
        print(no_data)
        return

    print(
        f"{'Molecule':24s} "
        f"{'Isomer':12s} "
        f"{'Method':12s} "
        f"{'Energy':14s} "
        f"{'Reactions':10s} "
        f"{'Trajectories':12s}"
    )

    for row in rows:
        molecule = str(row["molecule"] or "None")
        isomer = str(row["isomer"] or "None")
        method = str(row["method"] or "None")
        energy = str(row["energy_label"] or "None")

        print(
            f"{molecule:24.24s} "
            f"{isomer:12.12s} "
            f"{method:12.12s} "
            f"{energy:14.14s} "
            f"{row['n_distinct_reactions']:10d} "
            f"{row['n_reaction_trajectories']:12d}"
        )

def flatten_reaction_summary(summary: dict[str, list[dict[str, Any]]],
                             top_n: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for method_name, reactions in summary.items():
        selected = reactions[:top_n] if top_n is not None else reactions
        for rank, reaction in enumerate(selected, start=1):
            fragments = reaction.get("fragments", [])
            rows.append({
                "method": method_name,
                "rank": rank,
                "reaction_uid": reaction.get("reaction_uid"),
                "count": reaction.get("count"),
                "frequency_pct": reaction.get("frequency_pct"),
                "molecule_labels": ",".join(reaction.get("molecule_labels", [])),
                "energy_labels": ",".join(reaction.get("energy_labels", [])),
                "fragments": " + ".join(f.get("formula", "") for f in fragments),
                "masses": " + ".join(
                    f"{float(f.get('exact_mass', 0)):.6f}" for f in fragments
                ),
            })
    return rows


def tool_reaction_summary(db_path: str, filters: dict[str, str | None],
                          top_n: int | None = 10) -> list[dict[str, Any]]:
    methods = [filters["method"]] if filters.get("method") else None
    summary = build_reaction_summary(
        db_path=db_path,
        methods=methods,
        molecule=filters.get("molecule"),
        isomer=filters.get("isomer"),
        energy_label=filters.get("energy_label"),
    )
    return flatten_reaction_summary(summary, top_n=top_n)


def print_reaction_rows(
    rows: list[dict[str, Any]],
    language: str = "en",
) -> None:
    print(f"\n--- {tr(language, 'reaction_summary')} ---")
    if not rows:
        print(tr(language, "no_reactions"))
        return
    frame = pd.DataFrame(rows)
    print(frame[
        ["method", "rank", "reaction_uid", "count", "frequency_pct", "fragments"]
    ].to_string(index=False))


def tool_fragment_search(db_path: str, filters: dict[str, str | None],
                         formula: str | None, mz: float | None,
                         tolerance: float) -> pd.DataFrame:
    if formula is None and mz is None:
        raise ValueError(msg("formula_or_mass_required"))

    uri = build_readonly_uri(db_path)
    conn = sqlite3.connect(uri, uri=True)
    try:
        conditions: list[str] = []
        params: list[Any] = []
        if formula is not None:
            conditions.append("f.formula = ?")
            params.append(canonicalize_formula(formula))
        else:
            conditions.append("ABS(f.exact_mass - ?) <= ?")
            params.extend([mz, tolerance])

        filter_where, filter_params = build_filter_sql(filters)
        if filter_where:
            conditions.extend(
                piece.strip()
                for piece in filter_where.replace(" WHERE ", "", 1).split(" AND ")
            )
            params.extend(filter_params)

        query = f"""
            SELECT DISTINCT
                t.traj_uid, t.traj_code, t.molecule, t.isomer,
                t.method_label, t.energy_label, f.formula,
                f.exact_mass, f.charge_guess
            FROM fragments f
            JOIN trajectories t ON t.traj_uid = f.traj_uid
            WHERE {' AND '.join(conditions)}
            ORDER BY t.molecule, t.isomer, t.method_label,
                     t.energy_label, t.run_id, t.traj_uid
        """
        return pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()



def normalize_element_symbol(value: Any) -> str | None:
    text = clean_optional_text(value)
    if text is None:
        return None
    if not re.fullmatch(r"[A-Za-z]{1,2}", text):
        raise ValueError(f"Invalid element symbol: {value!r}")
    return text[0].upper() + text[1:].lower()


def load_json_list(value: Any, field_name: str) -> list[Any]:
    if isinstance(value, list):
        return value
    try:
        loaded = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid JSON stored in {field_name}.") from exc
    if not isinstance(loaded, list):
        raise ValueError(f"Stored value in {field_name} is not a list.")
    return loaded


def fetch_stored_final_fragments(
    db_path: str,
    filters: dict[str, str | None],
    formula: str | None = None,
    traj_uid: str | None = None,
) -> list[dict[str, Any]]:
    uri = build_readonly_uri(db_path)
    conn = sqlite3.connect(uri, uri=True)
    try:
        where_sql, params = build_filter_sql(filters)
        conditions = []
        if where_sql:
            conditions.append(where_sql.replace(" WHERE ", "", 1))
        if formula is not None:
            conditions.append("f.formula = ?")
            params.append(canonicalize_formula(formula))
        if traj_uid is not None:
            conditions.append("t.traj_uid = ?")
            params.append(traj_uid)
        final_where = " WHERE " + " AND ".join(conditions) if conditions else ""
        rows = conn.execute(
            f"""
            SELECT
                t.traj_uid,
                t.traj_code,
                t.molecule,
                t.isomer,
                t.method_label,
                t.energy_label,
                t.symbols_json,
                f.fragment_index,
                f.formula,
                f.exact_mass,
                f.charge_guess,
                f.n_atoms,
                f.atom_indices_json
            FROM trajectories AS t
            JOIN fragments AS f
              ON f.traj_uid = t.traj_uid
            {final_where}
            ORDER BY
                t.molecule,
                t.isomer,
                t.method_label,
                t.energy_label,
                t.run_id,
                t.traj_uid,
                f.fragment_index
            """,
            tuple(params),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            symbols = [str(item) for item in load_json_list(row[6], "symbols_json")]
            indices = [int(item) for item in load_json_list(row[12], "atom_indices_json")]
            if any(index < 0 or index >= len(symbols) for index in indices):
                raise ValueError(
                    f"Stored atom index is outside symbols_json for {row[0]}."
                )
            result.append({
                "traj_uid": row[0],
                "traj_code": row[1],
                "molecule": row[2],
                "isomer": row[3],
                "method_label": row[4],
                "energy_label": row[5],
                "symbols": symbols,
                "fragment_index": int(row[7]),
                "formula": row[8],
                "exact_mass": row[9],
                "charge_guess": row[10],
                "n_atoms": int(row[11]),
                "atom_indices_0based": indices,
                "atom_numbers_1based": [index + 1 for index in indices],
                "atom_labels": [f"{symbols[index]}{index + 1}" for index in indices],
            })
        return result
    finally:
        conn.close()


def tool_final_fragment_atoms(
    db_path: str,
    filters: dict[str, str | None],
    formula: str,
    traj_uid: str | None = None,
) -> list[dict[str, Any]]:
    rows = fetch_stored_final_fragments(db_path, filters, formula=formula, traj_uid=traj_uid,)
    grouped: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in rows:
        key = tuple(row["atom_labels"])
        item = grouped.setdefault(key, {
            "formula": row["formula"],
            "atom_labels": ", ".join(row["atom_labels"]),
            "atom_numbers": ", ".join(str(v) for v in row["atom_numbers_1based"]),
            "stored_indices_0based": ", ".join(
                str(v) for v in row["atom_indices_0based"]
            ),
            "n_atoms": row["n_atoms"],
            "n_trajectories": 0,
            "trajectory_uids": [],
        })
        item["n_trajectories"] += 1
        item["trajectory_uids"].append(row["traj_uid"])

    result = list(grouped.values())
    result.sort(key=lambda item: (-item["n_trajectories"], item["atom_labels"]))
    for rank, item in enumerate(result, start=1):
        item["rank"] = rank
        item["trajectory_uids"] = ", ".join(item["trajectory_uids"])
    return result


def print_final_fragment_atoms(
    rows: list[dict[str, Any]],
    language: str = "en",
) -> None:
    print(f"\n--- {tr(language, 'final_fragment_atoms')} ---")
    if not rows:
        print(tr(language, "no_matches"))
        return
    frame = pd.DataFrame(rows)
    columns = [
        "rank", "formula", "n_atoms", "n_trajectories",
        "atom_labels", "atom_numbers", "stored_indices_0based",
    ]
    print(frame[columns].to_string(index=False))
    if len(rows) > 1:
        print(
            "\nWarning: the same fragment formula has more than one stored "
            "atomic composition across the selected trajectories."
        )


def build_fragment_assignment(
    fragment_rows: list[dict[str, Any]],
) -> tuple[list[str], dict[int, tuple[int, str]]]:
    symbols = fragment_rows[0]["symbols"]
    assignment: dict[int, tuple[int, str]] = {}
    for row in fragment_rows:
        if row["symbols"] != symbols:
            raise ValueError(
                "Inconsistent symbols_json within the same trajectory."
            )
        for index in row["atom_indices_0based"]:
            assignment[index] = (row["fragment_index"], row["formula"])
    return symbols, assignment


def tool_final_fragment_bond_query(
    db_path: str,
    filters: dict[str, str | None],
    atom_1: int | None,
    atom_2: int | None,
    element_1: str | None,
    element_2: str | None,
    traj_uid: str | None = None,
) -> list[dict[str, Any]]:
    if (atom_1 is None) != (atom_2 is None):
        raise ValueError("Both atom numbers are required when one is supplied.")
    if (element_1 is None) != (element_2 is None):
        raise ValueError("Both element symbols are required when one is supplied.")
    if atom_1 is None and element_1 is None:
        raise ValueError(
            "Provide atom numbers, element symbols, or both."
        )
    if atom_1 is not None and (atom_1 < 1 or atom_2 is None or atom_2 < 1):
        raise ValueError("Atom numbers must be positive and 1-based.")
    if atom_1 is not None and atom_1 == atom_2:
        raise ValueError("The two atom numbers must be different.")

    element_1 = normalize_element_symbol(element_1)
    element_2 = normalize_element_symbol(element_2)
    fragments = fetch_stored_final_fragments(db_path, filters,traj_uid=traj_uid,)
    by_trajectory: dict[str, list[dict[str, Any]]] = {}
    for row in fragments:
        by_trajectory.setdefault(row["traj_uid"], []).append(row)

    matches: list[dict[str, Any]] = []
    for traj_uid, fragment_rows in by_trajectory.items():
        symbols, assignment = build_fragment_assignment(fragment_rows)
        first = fragment_rows[0]

        if atom_1 is not None and atom_2 is not None:
            i = atom_1 - 1
            j = atom_2 - 1
            if i >= len(symbols) or j >= len(symbols):
                continue
            actual_1, actual_2 = symbols[i], symbols[j]
            if element_1 is not None and element_2 is not None:
                requested_pair = (element_1, element_2)
                actual_pair = (actual_1, actual_2)
                if actual_pair != requested_pair and actual_pair[::-1] != requested_pair:
                    continue
            if i not in assignment or j not in assignment:
                continue
            frag_i = assignment[i]
            frag_j = assignment[j]
            if frag_i[0] == frag_j[0]:
                continue
            matches.append({
                "traj_uid": traj_uid,
                "traj_code": first["traj_code"],
                "molecule": first["molecule"],
                "isomer": first["isomer"],
                "method": first["method_label"],
                "energy_label": first["energy_label"],
                "atom_1": f"{actual_1}{atom_1}",
                "atom_2": f"{actual_2}{atom_2}",
                "fragment_1": frag_i[1],
                "fragment_2": frag_j[1],
            })
            continue

        # Element-only query: enumerate all numbered element pairs that end
        # in different final fragments. These are candidates, not proof of
        # initial bonding.
        assert element_1 is not None and element_2 is not None
        indices_1 = [idx for idx, symbol in enumerate(symbols) if symbol == element_1]
        indices_2 = [idx for idx, symbol in enumerate(symbols) if symbol == element_2]
        seen_pairs: set[tuple[int, int]] = set()
        for i in indices_1:
            for j in indices_2:
                if i == j:
                    continue
                pair_key = tuple(sorted((i, j)))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                if i not in assignment or j not in assignment:
                    continue
                frag_i = assignment[i]
                frag_j = assignment[j]
                if frag_i[0] == frag_j[0]:
                    continue
                matches.append({
                    "traj_uid": traj_uid,
                    "traj_code": first["traj_code"],
                    "molecule": first["molecule"],
                    "isomer": first["isomer"],
                    "method": first["method_label"],
                    "energy_label": first["energy_label"],
                    "atom_1": f"{symbols[i]}{i + 1}",
                    "atom_2": f"{symbols[j]}{j + 1}",
                    "fragment_1": frag_i[1],
                    "fragment_2": frag_j[1],
                })

    return matches


def print_final_fragment_bond_rows(
    rows: list[dict[str, Any]],
    element_only: bool,
    language: str = "en",
) -> None:
    print(f"\n--- {tr(language, 'final_fragment_bond_query')} ---")
    if not rows:
        print(
            "No final-fragment separation was found for the "
            "requested atom pair."
            if language == "en"
            else
            "No se encontró separación entre fragmentos finales "
            "para el par atómico solicitado."
        )
        return

    frame = pd.DataFrame(rows)
    if element_only:
        grouped = (
            frame.groupby(
                ["atom_1", "atom_2", "fragment_1", "fragment_2"],
                dropna=False,
            )
            .agg(
                n_trajectories=("traj_uid", "nunique"),
                trajectory_uids=("traj_uid", lambda values: ", ".join(sorted(set(values)))),
            )
            .reset_index()
            .sort_values(
                ["n_trajectories", "atom_1", "atom_2"],
                ascending=[False, True, True],
            )
        )
        print(grouped.to_string(index=False))
        print(f"\nNote: {tr(language, 'candidate_bond_note')}")
    else:
        columns = [
            "traj_uid", "traj_code", "molecule", "isomer", "method",
            "energy_label", "atom_1", "atom_2", "fragment_1", "fragment_2",
        ]
        print(frame[columns].to_string(index=False))


def tool_mass_spectrum(db_path: str, filters: dict[str, str | None],
                       charged_only: bool = False,
                       neutral_only: bool = False,
                       mz_min: float | None = None,
                       mz_max: float | None = None,
                       scale: float = 1000.0,
                       sort_by: str = "intensity") -> list[dict[str, Any]]:
    fragment_rows = fetch_fragment_rows_for_spectrum(
        db_path=db_path,
        molecule=filters.get("molecule"),
        isomer=filters.get("isomer"),
        method=filters.get("method"),
        energy_label=filters.get("energy_label"),
    )
    return build_spectrum_rows(
        fragment_rows=fragment_rows,
        charged_only=charged_only,
        neutral_only=neutral_only,
        mz_min=mz_min,
        mz_max=mz_max,
        scale=scale,
        sort_by=sort_by,
    )


def print_spectrum_rows(
    rows: list[dict[str, Any]],
    language: str = "en",
) -> None:
    print(f"\n--- {tr(language, 'spectrum')} ---")
    if not rows:
        print(tr(language, "no_peaks"))
        return
    frame = pd.DataFrame(rows)
    print(frame[["intensity", "mz", "formula", "count"]].to_string(index=False))


def print_kinetics_result(
    summary: dict[str, Any],
    language: str = "en",
) -> None:
    print(f"\n--- {tr(language, 'global_kinetics')} ---")
    fields = [
        (tr(language, "molecule"), "molecule"),
        (tr(language, "isomer"), "isomer"),
        (tr(language, "method"), "method_label"),
        (tr(language, "energy"), "energy_label"),
        (tr(language, "persistence_frames"), "persist_frames"),
        (tr(language, "trajectories"), "n_trajectories_total"),
        (tr(language, "events"), "n_events"),
        (tr(language, "censored"), "n_censored"),
        (tr(language, "event_fraction"), "event_fraction"),
        (tr(language, "mean_time"), "mean_event_time_ps"),
        (tr(language, "median_time"), "median_event_time_ps"),
        (tr(language, "regression_k"), "k_regression_ps^-1"),
        (tr(language, "regression_half_life"), "half_life_regression_ps"),
        ("R²", "r2"),
        (tr(language, "mle_k"), "k_mle_ps^-1"),
        (tr(language, "mle_half_life"), "half_life_mle_ps"),
    ]
    for label, key in fields:
        print(f"{label:30s}: {summary.get(key)}")


def formulas_in_frame(atoms: list[tuple[str, float, float, float]]) -> set[str]:
    formulas: set[str] = set()
    for fragment in connected_fragments(atoms):
        symbols = [atoms[index][0] for index in fragment]
        formula, _charge_guess = build_formula(symbols)
        formulas.add(formula)
    return formulas


def first_persistent_formula_event(conn: sqlite3.Connection,
                                   trajectory: dict[str, Any],
                                   target_formula: str,
                                   persist_frames: int) -> dict[str, Any]:
    streak = 0
    candidate: dict[str, Any] | None = None
    frames_scanned = 0
    last_time_ps = None

    for record in iter_frames_for_traj(
        conn=conn,
        traj_uid=trajectory["traj_uid"],
        symbols=trajectory["symbols"],
        fallback_timestep=trajectory.get("timestep"),
    ):
        frames_scanned += 1
        last_time_ps = record.get("time_ps")
        present = target_formula in formulas_in_frame(record["atoms"])

        if present:
            if streak == 0:
                candidate = {
                    "event_frame_idx": record.get("frame_idx"),
                    "event_frame_number": record.get("frame_number"),
                    "event_time_ps": record.get("time_ps"),
                }
            streak += 1
            if streak >= persist_frames:
                return {
                    "traj_uid": trajectory["traj_uid"],
                    "traj_code": trajectory.get("traj_code"),
                    "molecule": trajectory.get("molecule"),
                    "isomer": trajectory.get("isomer"),
                    "method_label": trajectory.get("method_label"),
                    "energy_label": trajectory.get("energy_label"),
                    "formula": target_formula,
                    "event_occurred": True,
                    **(candidate or {}),
                    "confirmation_frame_idx": record.get("frame_idx"),
                    "confirmation_frame_number": record.get("frame_number"),
                    "confirmation_time_ps": record.get("time_ps"),
                    "persist_frames": persist_frames,
                    "n_frames_scanned": frames_scanned,
                    "followup_time_ps": last_time_ps,
                }
        else:
            streak = 0
            candidate = None

    return {
        "traj_uid": trajectory["traj_uid"],
        "traj_code": trajectory.get("traj_code"),
        "molecule": trajectory.get("molecule"),
        "isomer": trajectory.get("isomer"),
        "method_label": trajectory.get("method_label"),
        "energy_label": trajectory.get("energy_label"),
        "formula": target_formula,
        "event_occurred": False,
        "event_frame_idx": None,
        "event_frame_number": None,
        "event_time_ps": None,
        "confirmation_frame_idx": None,
        "confirmation_frame_number": None,
        "confirmation_time_ps": None,
        "persist_frames": persist_frames,
        "n_frames_scanned": frames_scanned,
        "followup_time_ps": last_time_ps,
    }


def calculate_fragment_events(
    db_path: str,
    filters: dict[str, str | None],
    formula: str,
    persist_frames: int,
    language: str = "en",
) -> tuple[str, list[dict[str, Any]]]:
    target = canonicalize_formula(formula)
    conn = sqlite3.connect(db_path)
    try:
        trajectories = fetch_selected_trajectories(
            conn=conn,
            molecule=filters.get("molecule"),
            isomer=filters.get("isomer"),
            method=filters.get("method"),
            energy_label=filters.get("energy_label"),
        )
        if not trajectories:
            raise ValueError(msg("no_trajectories"))

        rows: list[dict[str, Any]] = []
        for index, trajectory in enumerate(trajectories, start=1):
            print(
                f"{tr(language, 'analysing_trajectory')} "
                f"{index}/{len(trajectories)}: {trajectory['traj_uid']}"
            )
            rows.append(first_persistent_formula_event(
                conn, trajectory, target, persist_frames
            ))
        return target, rows
    finally:
        conn.close()


def summarize_fragment_events(requested_formula: str, canonical_formula: str,
                              filters: dict[str, str | None],
                              persist_frames: int,
                              rows: list[dict[str, Any]]) -> dict[str, Any]:
    times = [
        float(row["event_time_ps"])
        for row in rows
        if row.get("event_occurred") and row.get("event_time_ps") is not None
    ]
    return {
        "formula_requested": requested_formula,
        "formula_canonical": canonical_formula,
        "filters": filters,
        "persist_frames": persist_frames,
        "n_trajectories_total": len(rows),
        "n_events": len(times),
        "n_not_observed": len(rows) - len(times),
        "event_fraction": len(times) / len(rows) if rows else 0.0,
        "mean_first_time_ps": statistics.fmean(times) if times else None,
        "median_first_time_ps": statistics.median(times) if times else None,
        "std_first_time_ps": statistics.stdev(times) if len(times) >= 2 else None,
        "min_first_time_ps": min(times) if times else None,
        "max_first_time_ps": max(times) if times else None,
    }


def print_fragment_appearance(
    summary: dict[str, Any],
    language: str = "en",
) -> None:
    print(f"\n--- {tr(language, 'fragment_appearance')} ---")
    for label, key in [
        (tr(language, "requested_formula"), "formula_requested"),
        (tr(language, "canonical_formula"), "formula_canonical"),
        (tr(language, "persistence_frames"), "persist_frames"),
        (tr(language, "trajectories"), "n_trajectories_total"),
        (tr(language, "events"), "n_events"),
        (tr(language, "not_observed"), "n_not_observed"),
        (tr(language, "event_fraction"), "event_fraction"),
        (tr(language, "mean_time"), "mean_first_time_ps"),
        (tr(language, "median_time"), "median_first_time_ps"),
        (tr(language, "std_time"), "std_first_time_ps"),
        (tr(language, "minimum_time"), "min_first_time_ps"),
        (tr(language, "maximum_time"), "max_first_time_ps"),
    ]:
        print(f"{label:28s}: {summary.get(key)}")


def select_event(rows: list[dict[str, Any]], selection: str) -> dict[str, Any]:
    valid = [
        row for row in rows
        if row.get("event_occurred") and row.get("event_time_ps") is not None
    ]
    if not valid:
        raise ValueError(msg("fragment_not_found"))
    selection = selection.casefold()
    if selection in {"earliest", "minimum", "min", "fastest"}:
        return min(valid, key=lambda row: (float(row["event_time_ps"]), row["traj_uid"]))
    return max(valid, key=lambda row: (float(row["event_time_ps"]), row["traj_uid"]))


def fetch_trajectory_candidates(db_path: str,
                                filters: dict[str, str | None]) -> list[dict[str, Any]]:
    uri = build_readonly_uri(db_path)
    conn = sqlite3.connect(uri, uri=True)
    try:
        where_sql, params = build_filter_sql(filters)
        rows = conn.execute(
            f"""
            SELECT t.traj_uid, t.traj_code, t.molecule, t.isomer,
                   t.method_label, t.energy_label, t.run_id,
                   t.nframes, t.created_at
            FROM trajectories t
            {where_sql}
            ORDER BY
                CASE WHEN t.run_id IS NULL THEN 1 ELSE 0 END,
                t.run_id,
                t.created_at,
                t.traj_uid
            """,
            tuple(params),
        ).fetchall()
        return [
            {
                "traj_uid": row[0],
                "traj_code": row[1],
                "molecule": row[2],
                "isomer": row[3],
                "method_label": row[4],
                "energy_label": row[5],
                "run_id": row[6],
                "nframes": row[7],
                "created_at": row[8],
            }
            for row in rows
        ]
    finally:
        conn.close()


def fetch_trajectory_by_uid(
    db_path: str,
    traj_uid: str,
) -> dict[str, Any]:
    """Fetch exactly one trajectory by its globally unique identifier."""
    uri = build_readonly_uri(db_path)
    conn = sqlite3.connect(uri, uri=True)
    try:
        row = conn.execute(
            """
            SELECT t.traj_uid, t.traj_code, t.molecule, t.isomer,
                   t.method_label, t.energy_label, t.run_id,
                   t.nframes, t.created_at
            FROM trajectories AS t
            WHERE t.traj_uid = ?
            LIMIT 1
            """,
            (traj_uid,),
        ).fetchone()
        if row is None:
            raise ValueError(
                f"Trajectory UID not found in the database: {traj_uid}"
            )
        return {
            "traj_uid": row[0],
            "traj_code": row[1],
            "molecule": row[2],
            "isomer": row[3],
            "method_label": row[4],
            "energy_label": row[5],
            "run_id": row[6],
            "nframes": row[7],
            "created_at": row[8],
        }
    finally:
        conn.close()


def choose_trajectory(candidates: list[dict[str, Any]],
                      selection: str) -> dict[str, Any]:
    if not candidates:
        raise ValueError(msg("no_trajectories"))
    mode = selection.casefold()
    if mode == "last":
        return candidates[-1]
    if mode == "random":
        return random.choice(candidates)
    if mode == "longest":
        return max(candidates, key=lambda row: (row.get("nframes") or 0, row["traj_uid"]))
    if mode == "shortest":
        return min(candidates, key=lambda row: (row.get("nframes") or 0, row["traj_uid"]))
    return candidates[0]


def export_one_trajectory(db_path: str, trajectory: dict[str, Any],
                          output_dir: str, folder_name: str | None = None,
                          prefix: str | None = None) -> dict[str, Any]:
    base = prefix or "_".join([
        slugify(trajectory.get("molecule")),
        slugify(trajectory.get("isomer")),
        slugify(trajectory.get("method_label")),
        slugify(trajectory.get("energy_label")),
        slugify(trajectory.get("traj_code") or trajectory.get("traj_uid")),
    ])
    folder = safe_output_folder(output_dir, folder_name or base)
    xyz_path = folder / f"{base}.xyz"
    frame_csv = folder / f"{base}_frame_data.csv"

    restore_xyz_from_db(db_path, trajectory["traj_uid"], str(xyz_path))
    export_frame_data_csv(db_path, trajectory["traj_uid"], str(frame_csv))

    return {
        **trajectory,
        "output_folder": str(folder),
        "xyz_path": str(xyz_path),
        "frame_csv_path": str(frame_csv),
    }


def final_frame_fragment_matches(db_path: str,
                                 filters: dict[str, str | None],
                                 formula: str) -> list[dict[str, Any]]:
    target = canonicalize_formula(formula)
    uri = build_readonly_uri(db_path)
    conn = sqlite3.connect(uri, uri=True)
    try:
        where_sql, params = build_filter_sql(filters)
        extra = " AND f.formula = ?" if where_sql else " WHERE f.formula = ?"
        params.append(target)
        rows = conn.execute(
            f"""
            SELECT DISTINCT
                t.traj_uid, t.traj_code, t.molecule, t.isomer,
                t.method_label, t.energy_label, t.run_id,
                t.nframes, t.created_at
            FROM trajectories t
            JOIN fragments f ON f.traj_uid = t.traj_uid
            {where_sql}{extra}
            ORDER BY
                CASE WHEN t.run_id IS NULL THEN 1 ELSE 0 END,
                t.run_id, t.created_at, t.traj_uid
            """,
            tuple(params),
        ).fetchall()
        return [
            {
                "traj_uid": row[0],
                "traj_code": row[1],
                "molecule": row[2],
                "isomer": row[3],
                "method_label": row[4],
                "energy_label": row[5],
                "run_id": row[6],
                "nframes": row[7],
                "created_at": row[8],
                "formula": target,
                "event_occurred": True,
                "event_time_ps": None,
                "fragment_scope": "final_frame",
            }
            for row in rows
        ]
    finally:
        conn.close()


def scanned_fragment_matches(db_path: str,
                             filters: dict[str, str | None],
                             formula: str,
                             fragment_scope: str,
                             persist_frames: int) -> list[dict[str, Any]]:
    required = persist_frames if fragment_scope == "persistent" else 1
    target, rows = calculate_fragment_events(
        db_path, filters, formula, required
    )
    matches = [row for row in rows if row.get("event_occurred")]
    for row in matches:
        row["formula"] = target
        row["fragment_scope"] = fragment_scope
    return matches


def find_fragment_matches(db_path: str,
                          filters: dict[str, str | None],
                          formula: str,
                          fragment_scope: str,
                          persist_frames: int) -> list[dict[str, Any]]:
    scope = fragment_scope.casefold()
    if scope == "final_frame":
        return final_frame_fragment_matches(db_path, filters, formula)
    if scope not in {"any_frame", "persistent"}:
        scope = "any_frame"
    return scanned_fragment_matches(
        db_path, filters, formula, scope, persist_frames
    )


def print_export_result(
    result: dict[str, Any],
    language: str = "en",
) -> None:
    print(f"\n--- {tr(language, 'exported_trajectory')} ---")
    for label, key in [
        ("traj_uid", "traj_uid"),
        (tr(language, "trajectory_code"), "traj_code"),
        (tr(language, "molecule"), "molecule"),
        (tr(language, "isomer"), "isomer"),
        (tr(language, "method"), "method_label"),
        (tr(language, "energy"), "energy_label"),
        (tr(language, "frames"), "nframes"),
        (tr(language, "event_time"), "event_time_ps"),
        (tr(language, "xyz"), "xyz_path"),
        (tr(language, "energy_time_csv"), "frame_csv_path"),
    ]:
        print(f"{label:24s}: {result.get(key)}")


def export_all_matches(db_path: str, matches: list[dict[str, Any]],
                       output_dir: str, folder_name: str,
                       max_exports: int) -> dict[str, Any]:
    root = safe_output_folder(output_dir, folder_name)
    manifest: list[dict[str, Any]] = []
    exported_count = 0

    for index, match in enumerate(matches, start=1):
        row = dict(match)
        row["exported"] = False
        row["xyz_path"] = None
        row["frame_csv_path"] = None

        if exported_count < max_exports:
            subfolder = "_".join([
                f"{index:04d}",
                slugify(match.get("molecule")),
                slugify(match.get("isomer")),
                slugify(match.get("method_label")),
                slugify(match.get("energy_label")),
                slugify(match.get("traj_code") or match.get("traj_uid")),
            ])
            exported = export_one_trajectory(
                db_path=db_path,
                trajectory=match,
                output_dir=str(root),
                folder_name=subfolder,
                prefix=subfolder,
            )
            row["exported"] = True
            row["xyz_path"] = exported["xyz_path"]
            row["frame_csv_path"] = exported["frame_csv_path"]
            exported_count += 1

        manifest.append(row)

    manifest_path = root / "manifest.csv"
    export_dict_rows_csv(manifest, manifest_path)

    return {
        "output_folder": str(root),
        "manifest_path": str(manifest_path),
        "n_matches": len(matches),
        "n_exported": exported_count,
        "n_not_exported": len(matches) - exported_count,
    }



def resolve_comparison_values(
    arguments: dict[str, Any],
    catalog: dict[str, list[str]],
) -> tuple[str, list[str]]:
    """Validate and return the category and values used for comparison."""
    compare_by = str(arguments.get("compare_by") or "molecule").strip().casefold()

    category_map = {
        "molecule": ("molecules", "molecule", "molecules"),
        "isomer": ("isomers", "isomer", "isomers"),
        "method": ("methods", "method", "methods"),
        "energy": ("energy_labels", "energy_label", "energy labels"),
        "energy_label": ("energy_labels", "energy_label", "energy labels"),
    }

    if compare_by not in category_map:
        raise ValueError(
            "compare_by must be one of: molecule, isomer, method, energy_label."
        )

    catalog_key, filter_key, label = category_map[compare_by]
    raw_values = arguments.get("values")

    if raw_values is None:
        plural_key = {
            "molecule": "molecules",
            "isomer": "isomers",
            "method": "methods",
            "energy": "energy_labels",
            "energy_label": "energy_labels",
        }[compare_by]
        raw_values = arguments.get(plural_key)

    if raw_values is None:
        singular = clean_optional_text(arguments.get(filter_key))
        raw_values = [singular] if singular else None

    if not isinstance(raw_values, list) or len(raw_values) < 2:
        raise ValueError(
            f"A kinetics comparison requires at least two {label}."
        )

    available = catalog[catalog_key]
    resolved: list[str] = []
    for value in raw_values:
        item = resolve_catalog_value(str(value), available, filter_key)
        if item is not None and item not in resolved:
            resolved.append(item)

    if len(resolved) < 2:
        raise ValueError(
            f"A kinetics comparison requires at least two distinct {label}."
        )

    canonical_compare_by = "energy_label" if compare_by == "energy" else compare_by
    return canonical_compare_by, resolved


def compare_global_kinetics(
    db_path: str,
    base_filters: dict[str, str | None],
    compare_by: str,
    comparison_values: list[str],
    persist_frames: int,
    window_mode: str,
    min_points: int,
    output_dir: str,
    export_csv: bool,
) -> tuple[list[dict[str, Any]], Path | None, list[Path]]:
    """Calculate global kinetics independently for every comparison group."""
    rows: list[dict[str, Any]] = []
    detailed_paths: list[Path] = []

    for value in comparison_values:
        group_filters = dict(base_filters)
        group_filters[compare_by] = value

        summary_csv = events_csv = survival_csv = None
        if export_csv:
            base = (
                f"kinetics_{slugify(group_filters.get('molecule'))}_"
                f"{slugify(group_filters.get('isomer'))}_"
                f"{slugify(group_filters.get('method'))}_"
                f"{slugify(group_filters.get('energy_label'))}_"
                f"persist{persist_frames}"
            )
            summary_csv = safe_output_path(
                output_dir, f"{base}_summary.csv", f"{base}_summary.csv", ".csv"
            )
            events_csv = safe_output_path(
                output_dir, f"{base}_events.csv", f"{base}_events.csv", ".csv"
            )
            survival_csv = safe_output_path(
                output_dir, f"{base}_survival.csv", f"{base}_survival.csv", ".csv"
            )
            detailed_paths.extend([summary_csv, events_csv, survival_csv])

        summary, _, _ = compute_and_store_global_kinetics(
            db_path=db_path,
            molecule=group_filters.get("molecule"),
            isomer=group_filters.get("isomer"),
            method=group_filters.get("method"),
            energy_label=group_filters.get("energy_label"),
            persist_frames=persist_frames,
            window_mode=window_mode,
            min_points=min_points,
            output_summary_csv=str(summary_csv) if summary_csv else None,
            output_events_csv=str(events_csv) if events_csv else None,
            output_survival_csv=str(survival_csv) if survival_csv else None,
        )
        rows.append({"comparison_group": value, **summary})

    combined_csv: Path | None = None
    if export_csv:
        groups_slug = "_vs_".join(slugify(v) for v in comparison_values)
        combined_csv = safe_output_path(
            output_dir,
            f"kinetics_comparison_{compare_by}_{groups_slug}_persist{persist_frames}.csv",
            f"kinetics_comparison_{compare_by}_{groups_slug}_persist{persist_frames}.csv",
            ".csv",
        )
        export_dict_rows_csv(rows, combined_csv)

    return rows, combined_csv, detailed_paths


def print_kinetics_comparison(
    rows: list[dict[str, Any]],
    compare_by: str,
    language: str = "en",
) -> None:
    print(f"\n--- {tr(language, 'kinetics_comparison')} ---")
    if not rows:
        print(tr(language, "no_results"))
        return

    columns = [
        "comparison_group",
        "n_trajectories_total",
        "n_events",
        "n_censored",
        "event_fraction",
        "mean_event_time_ps",
        "median_event_time_ps",
        "k_regression_ps^-1",
        "half_life_regression_ps",
        "r2",
        "k_mle_ps^-1",
        "half_life_mle_ps",
        "warnings",
    ]
    frame = pd.DataFrame(rows)
    available_columns = [column for column in columns if column in frame.columns]
    print(frame[available_columns].to_string(index=False))

def generate_agent_plan(question: str, tools_manual: str,
                        catalog: dict[str, list[str]],
                        model_path: str, llama_cli: str,
                        router_tokens: int,
                        router_timeout: int) -> dict[str, Any]:
    prompt = build_router_prompt(question, tools_manual, catalog)
    raw = run_llama_backend(
        model_path=model_path,
        prompt=prompt,
        llama_cli=llama_cli,
        n_tokens=router_tokens,
        timeout_seconds=router_timeout,
    )
    return extract_json_object(raw)



def find_catalog_mentions_flexible(
    question: str,
    values: list[str],
) -> list[str]:
    """Match catalogue values allowing spaces, underscores and hyphens."""
    matches: list[str] = []

    for value in sorted(values, key=len, reverse=True):
        parts = [p for p in re.split(r"[\s_-]+", value) if p]
        if not parts:
            continue
        pattern = (
            r"(?<![A-Za-z0-9])"
            + r"[\s_-]+".join(re.escape(p) for p in parts)
            + r"(?![A-Za-z0-9])"
        )
        if re.search(pattern, question, flags=re.IGNORECASE):
            matches.append(value)

    return matches


def extract_requested_kinetics_conditions(
    question: str,
    catalog: dict[str, list[str]],
) -> dict[str, Any]:
    """
    Extract molecule/isomer pairs, methods, energy labels, persistence
    and window mode from a stored-kinetics request.
    """
    molecules = find_catalog_mentions_flexible(
        question, catalog.get("molecules", [])
    )
    methods = find_catalog_mentions_flexible(
        question, catalog.get("methods", [])
    )
    energy_labels = find_catalog_mentions_flexible(
        question, catalog.get("energy_labels", [])
    )

    molecule_conditions: list[tuple[str, str | None]] = []

    for molecule in molecules:
        parts = [p for p in re.split(r"[\s_-]+", molecule) if p]
        mol_pattern = r"[\s_-]+".join(re.escape(p) for p in parts)
        chosen_isomer: str | None = None

        for isomer in sorted(catalog.get("isomers", []), key=len, reverse=True):
            iso = re.escape(isomer)

            explicit = (
                rf"(?<![A-Za-z0-9]){mol_pattern}"
                rf"\s*[,;:-]?\s*(?:isomer|isómero|isomero)\s*[:=]?\s*"
                rf"{iso}(?![A-Za-z0-9])"
            )
            shorthand = (
                rf"(?<![A-Za-z0-9]){mol_pattern}"
                rf"\s*[,;:-]?\s+{iso}(?![A-Za-z0-9])"
            )

            if (
                re.search(explicit, question, flags=re.IGNORECASE)
                or re.search(shorthand, question, flags=re.IGNORECASE)
            ):
                chosen_isomer = isomer
                break

        molecule_conditions.append((molecule, chosen_isomer))

    persist_match = re.search(
        r"(\d+)\s*(?:frames?|fotogramas?)"
        r"(?:\s+(?:consecutivos?|persistentes?))?",
        question,
        flags=re.IGNORECASE,
    )

    question_cf = question.casefold()
    window_mode: str | None = None
    if "modo common" in question_cf or "common mode" in question_cf:
        window_mode = "common"
    elif "modo censor" in question_cf or "censor mode" in question_cf:
        window_mode = "censor"

    return {
        "molecule_conditions": molecule_conditions,
        "methods": methods,
        "energy_labels": energy_labels,
        "persist_frames": (
            int(persist_match.group(1))
            if persist_match
            else None
        ),
        "window_mode": window_mode,
    }


def build_stored_kinetics_where(
    request: dict[str, Any],
) -> tuple[str, list[Any]]:
    conditions: list[str] = []
    params: list[Any] = []

    molecule_conditions = request.get("molecule_conditions") or []
    if molecule_conditions:
        subclauses: list[str] = []
        for molecule, isomer in molecule_conditions:
            if isomer is None:
                subclauses.append("kg.molecule = ?")
                params.append(molecule)
            else:
                subclauses.append("(kg.molecule = ? AND kg.isomer = ?)")
                params.extend([molecule, isomer])
        conditions.append("(" + " OR ".join(subclauses) + ")")

    methods = request.get("methods") or []
    if methods:
        placeholders = ", ".join("?" for _ in methods)
        conditions.append(f"kg.method_label IN ({placeholders})")
        params.extend(methods)

    energies = request.get("energy_labels") or []
    if energies:
        placeholders = ", ".join("?" for _ in energies)
        conditions.append(f"kg.energy_label IN ({placeholders})")
        params.extend(energies)

    if request.get("persist_frames") is not None:
        conditions.append("kg.persist_frames = ?")
        params.append(int(request["persist_frames"]))

    if request.get("window_mode") is not None:
        conditions.append("kg.window_mode = ?")
        params.append(request["window_mode"])

    return (
        ("WHERE " + " AND ".join(conditions)) if conditions else "",
        params,
    )


def tool_stored_kinetics_summary(
    db_path: str,
    question: str,
    catalog: dict[str, list[str]],
) -> pd.DataFrame:
    """
    Read stored k values and enrich them with energy metadata from md_inputs.
    No trajectory frames are rescanned.
    """
    request = extract_requested_kinetics_conditions(question, catalog)
    where_sql, params = build_stored_kinetics_where(request)

    uri = build_readonly_uri(db_path)
    conn = sqlite3.connect(uri, uri=True)

    try:
        exists = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'kinetics_global'
            LIMIT 1
            """
        ).fetchone()

        if exists is None:
            return pd.DataFrame()

        sql = f"""
WITH input_summary AS (
    SELECT
        t.molecule,
        t.isomer,
        t.method_label,
        t.energy_label,
        COUNT(DISTINCT t.input_id) AS n_distinct_inputs,
        COUNT(DISTINCT mi.energy_temperature_K) AS n_temperature_values,
        COUNT(DISTINCT mi.energy_kcal_mol) AS n_energy_kcal_values,
        COUNT(DISTINCT mi.zpe_kcal_mol) AS n_zpe_values,
        COUNT(DISTINCT mi.dof) AS n_dof_values,
        MIN(mi.energy_temperature_K) AS energy_temperature_K_min,
        MIN(mi.energy_kcal_mol) AS energy_kcal_mol_min,
        MIN(mi.zpe_kcal_mol) AS zpe_kcal_mol_min,
        MIN(mi.dof) AS dof_min
    FROM trajectories AS t
    LEFT JOIN md_inputs AS mi
      ON mi.input_id = t.input_id
    GROUP BY
        t.molecule,
        t.isomer,
        t.method_label,
        t.energy_label
)
SELECT
    kg.kinetics_uid,
    kg.molecule,
    kg.isomer,
    kg.method_label AS method,
    kg.energy_label,
    CASE WHEN inp.n_temperature_values <= 1
         THEN inp.energy_temperature_K_min END AS energy_temperature_K,
    CASE WHEN inp.n_energy_kcal_values <= 1
         THEN inp.energy_kcal_mol_min END AS energy_kcal_mol,
    CASE WHEN inp.n_zpe_values <= 1
         THEN inp.zpe_kcal_mol_min END AS zpe_kcal_mol,
    CASE WHEN inp.n_dof_values <= 1
         THEN inp.dof_min END AS dof,
    COALESCE(inp.n_distinct_inputs, 0) AS n_distinct_inputs,
    kg.persist_frames,
    kg.window_mode,
    kg.min_points,
    kg.n_trajectories_total AS n_trajectories,
    kg.n_events,
    kg.n_censored,
    kg.event_fraction,
    kg.mean_event_time_ps,
    kg.median_event_time_ps,
    kg.k_mle_ps_minus1,
    kg.k_mle_stderr,
    kg.k_mle_ci95_low,
    kg.k_mle_ci95_high,
    kg.half_life_mle_ps,
    kg.k_regression_ps_minus1,
    kg.k_regression_stderr,
    kg.k_regression_ci95_low,
    kg.k_regression_ci95_high,
    kg.half_life_regression_ps,
    kg.r2,
    kg.n_fit_points,
    COALESCE(
        kg.k_mle_ps_minus1,
        kg.k_regression_ps_minus1
    ) AS k_primary_ps_minus1,
    CASE
        WHEN kg.k_mle_ps_minus1 IS NOT NULL THEN 'MLE'
        WHEN kg.k_regression_ps_minus1 IS NOT NULL THEN 'regression'
        ELSE NULL
    END AS k_primary_method,
    CASE
        WHEN COALESCE(inp.n_distinct_inputs, 0) > 1
          OR COALESCE(inp.n_temperature_values, 0) > 1
          OR COALESCE(inp.n_energy_kcal_values, 0) > 1
          OR COALESCE(inp.n_zpe_values, 0) > 1
          OR COALESCE(inp.n_dof_values, 0) > 1
        THEN 'multiple_input_definitions'
        ELSE ''
    END AS input_warning,
    kg.warnings_json AS kinetics_warnings,
    kg.created_at
FROM kinetics_global AS kg
LEFT JOIN input_summary AS inp
  ON inp.molecule = kg.molecule
 AND inp.isomer IS kg.isomer
 AND inp.method_label = kg.method_label
 AND inp.energy_label = kg.energy_label
{where_sql}
ORDER BY
    kg.molecule,
    kg.isomer,
    kg.method_label,
    kg.energy_label,
    kg.persist_frames,
    kg.window_mode,
    kg.created_at;
"""

        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


def print_stored_kinetics(
    frame: pd.DataFrame,
    language: str = "en",
) -> None:
    print(f"\n--- {tr(language, 'stored_kinetics')} ---")

    if frame.empty:
        print(tr(language, "no_results"))
        return

    columns = [
        "molecule",
        "isomer",
        "method",
        "energy_label",
        "energy_temperature_K",
        "energy_kcal_mol",
        "persist_frames",
        "window_mode",
        "min_points",
        "n_trajectories",
        "n_events",
        "n_censored",
        "event_fraction",
        "k_primary_ps_minus1",
        "k_primary_method",
        "half_life_mle_ps",
        "k_regression_ps_minus1",
        "r2",
        "input_warning",
    ]

    print(frame[[c for c in columns if c in frame.columns]].to_string(index=False))


def export_stored_kinetics_csv(
    frame: pd.DataFrame,
    output_path: Path,
) -> None:
    if frame.empty:
        raise ValueError(msg("nothing_to_export"))

    columns = [
        "molecule",
        "isomer",
        "method",
        "energy_label",
        "energy_temperature_K",
        "energy_kcal_mol",
        "zpe_kcal_mol",
        "dof",
        "n_distinct_inputs",
        "persist_frames",
        "window_mode",
        "min_points",
        "n_trajectories",
        "n_events",
        "n_censored",
        "event_fraction",
        "mean_event_time_ps",
        "median_event_time_ps",
        "k_primary_ps_minus1",
        "k_primary_method",
        "k_mle_ps_minus1",
        "k_mle_stderr",
        "k_mle_ci95_low",
        "k_mle_ci95_high",
        "half_life_mle_ps",
        "k_regression_ps_minus1",
        "k_regression_stderr",
        "k_regression_ci95_low",
        "k_regression_ci95_high",
        "half_life_regression_ps",
        "r2",
        "n_fit_points",
        "input_warning",
        "kinetics_warnings",
        "created_at",
    ]

    frame.to_csv(
        output_path,
        columns=[c for c in columns if c in frame.columns],
        index=False,
    )


def export_stored_kinetics_details(
    db_path: str,
    kinetics_rows: pd.DataFrame,
    output_dir: Path,
) -> list[Path]:
    """
    Export summary, event rows and exact stored survival points for each
    selected kinetics_uid, without recalculation.

    When duplicate records exist for the same kinetic condition, a
    standardised record with a defined min_points value is preferred over
    a legacy record in which min_points is NULL.

    Legacy records without min_points remain exportable when no
    standardised equivalent exists. In that case, the generated filename
    uses the label 'minpointsunknown'.
    """
    if kinetics_rows.empty:
        raise ValueError(msg("nothing_to_export"))

    # Work with a copy so that filtering does not modify the original
    # DataFrame received by the function.
    kinetics_rows = kinetics_rows.copy()

    # Columns defining the same scientific kinetic condition.
    condition_columns = [
        "molecule",
        "isomer",
        "method",
        "energy_label",
        "persist_frames",
        "window_mode",
    ]

    available_condition_columns = [
        column
        for column in condition_columns
        if column in kinetics_rows.columns
    ]

    # Some historical records contain min_points = NULL. If both a legacy
    # record and a standardised record exist for the same condition, keep
    # only the record with a defined min_points value.
    if (
        "min_points" in kinetics_rows.columns
        and available_condition_columns
    ):
        group_has_defined_min_points = (
            kinetics_rows
            .groupby(
                available_condition_columns,
                dropna=False,
            )["min_points"]
            .transform(
                lambda values: values.notna().any()
            )
        )

        kinetics_rows = kinetics_rows.loc[
            (~group_has_defined_min_points)
            | kinetics_rows["min_points"].notna()
        ].copy()

    if kinetics_rows.empty:
        raise ValueError(msg("nothing_to_export"))

    uri = build_readonly_uri(db_path)
    conn = sqlite3.connect(uri, uri=True)
    created: list[Path] = []

    try:
        for _, record in kinetics_rows.iterrows():
            kinetics_uid = str(record["kinetics_uid"])

            persist_value = record.get("persist_frames")
            min_points_value = record.get("min_points")

            # Avoid calling int() directly on NaN or NULL values.
            persist_label = (
                "unknown"
                if pd.isna(persist_value)
                else str(int(persist_value))
            )

            min_points_label = (
                "unknown"
                if pd.isna(min_points_value)
                else str(int(min_points_value))
            )

            base = (
                f"kinetics_{slugify(record.get('molecule'))}_"
                f"{slugify(record.get('isomer'))}_"
                f"{slugify(record.get('method'))}_"
                f"{slugify(record.get('energy_label'))}_"
                f"persist{persist_label}_"
                f"minpoints{min_points_label}_"
                f"{slugify(record.get('window_mode'))}"
            )

            summary_path = safe_output_path(
                output_dir,
                f"{base}_summary.csv",
                f"{base}_summary.csv",
                ".csv",
            )

            events_path = safe_output_path(
                output_dir,
                f"{base}_events.csv",
                f"{base}_events.csv",
                ".csv",
            )

            survival_path = safe_output_path(
                output_dir,
                f"{base}_survival.csv",
                f"{base}_survival.csv",
                ".csv",
            )

            # Export the complete stored global summary.
            pd.DataFrame(
                [record.to_dict()]
            ).to_csv(
                summary_path,
                index=False,
            )

            # Export all trajectory-level event and censoring records
            # associated with the selected kinetics_uid.
            events = pd.read_sql_query(
                """
                SELECT *
                FROM kinetics_events
                WHERE kinetics_uid = ?
                ORDER BY traj_uid
                """,
                conn,
                params=[kinetics_uid],
            )

            events.to_csv(
                events_path,
                index=False,
            )

            # Recover the exact survival points stored during the original
            # calculation. No trajectory frames are rescanned here.
            point_rows = conn.execute(
                """
                SELECT point_json
                FROM kinetics_survival_points
                WHERE kinetics_uid = ?
                ORDER BY point_index
                """,
                (kinetics_uid,),
            ).fetchall()

            survival_records = []

            for row in point_rows:
                point_json = row[0]

                if point_json is None:
                    continue

                try:
                    point_record = json.loads(point_json)
                except (
                    json.JSONDecodeError,
                    TypeError,
                ) as exc:
                    raise ValueError(
                        "Invalid stored survival-point JSON for "
                        f"kinetics_uid={kinetics_uid}: {exc}"
                    ) from exc

                survival_records.append(point_record)

            survival = pd.DataFrame(
                survival_records
            )

            survival.to_csv(
                survival_path,
                index=False,
            )

            created.extend(
                [
                    summary_path,
                    events_path,
                    survival_path,
                ]
            )

    finally:
        conn.close()

    return created

def execute_action(
    action: str,
    arguments: dict[str, Any],
    question: str,
    db_path: str,
    catalog: dict[str, list[str]],
    output_dir: str,
    model_path: str,
    llama_cli: str,
    sql_knowledge: str,
    show_sql: bool,
    show_repairs: bool,
    max_rows: int,
    sql_tokens: int,
    timeout_seconds: int,
    output_language: str = "en",
) -> None:
    # --------------------------------------------------------------
    # Defensive correction for trajectory UIDs misplaced by the router.
    # --------------------------------------------------------------
    traj_uid = clean_optional_text(arguments.get("traj_uid"))
    molecule_value = clean_optional_text(arguments.get("molecule"))

    if (
        traj_uid is None
        and molecule_value is not None
        and molecule_value.startswith("traj_")
    ):
        arguments["traj_uid"] = molecule_value
        arguments["molecule"] = None

    # --------------------------------------------------------------
    # SQL queries use the complete natural-language question.
    #
    # Router arguments are intentionally ignored here because the model
    # may return lists, duplicated defaults or irrelevant fields.
    # --------------------------------------------------------------
    if action == "sql_query":
        # ----------------------------------------------------------
        # First try a deterministic fast path for common questions
        # over trajectory metadata. This avoids both LLM SQL errors
        # and expensive, unnecessary JOIN operations.
        # ----------------------------------------------------------
        fast_query = build_fast_metadata_sql(
            question=question,
            catalog=catalog,
        )

        if fast_query is not None:
            sql, params, fast_route = fast_query

            if show_sql:
                print(f"\n--- {tr(output_language, 'generated_sql')} ---")
                print(sql)

                if params:
                    print(f"\nParameters: {params}")

                print("\nRepairs: 0")
                print(f"SQL route: {fast_route}")

            frame = execute_parameterised_sql(
                db_path=db_path,
                sql=sql,
                params=params,
            )

            print(f"\n--- {tr(output_language, 'result')} ---")
            print(
                tr(output_language, "no_results")
                if frame.empty
                else frame.to_string(index=False)
            )
            return

        # ----------------------------------------------------------
        # Complex questions still use the LLM SQL generator.
        # ----------------------------------------------------------
        schema = get_sqlite_schema(db_path)

        sql, repairs = generate_valid_sql(
            db_path=db_path,
            question=question,
            schema=schema,
            knowledge=sql_knowledge,
            model_path=model_path,
            llama_cli=llama_cli,
            n_tokens=sql_tokens,
            timeout_seconds=timeout_seconds,
            max_rows=max_rows,
            max_repairs=2,
            show_repairs=show_repairs,
        )

        if show_sql:
            print(f"\n--- {tr(output_language, 'generated_sql')} ---")
            print(sql)
            print(f"\n{tr(output_language, 'repairs')}: {repairs}")
            print("SQL route: llama_sql_generator")

        frame = execute_sql(db_path, sql)

        print(f"\n--- {tr(output_language, 'result')} ---")
        print(
            tr(output_language, "no_results")
            if frame.empty
            else frame.to_string(index=False)
        )
        return

    # --------------------------------------------------------------
    # Stored input tools use an exact trajectory UID and do not require
    # molecule, method, energy-label or isomer filters.
    # --------------------------------------------------------------
    if action == "show_input":
        input_traj_uid = clean_optional_text(arguments.get("traj_uid"))
        if input_traj_uid is None:
            raise ValueError(msg("traj_uid_required"))

        print(f"\n--- {tr(output_language, 'stored_input')} ---")
        show_input_from_db(
            db_path=db_path,
            traj_uid=input_traj_uid,
        )
        return

    if action == "restore_input":
        input_traj_uid = clean_optional_text(arguments.get("traj_uid"))
        if input_traj_uid is None:
            raise ValueError(msg("traj_uid_required"))

        default_filename = f"input_{slugify(input_traj_uid)}.in"
        output_path = safe_output_path(
            output_dir=output_dir,
            filename=clean_optional_text(arguments.get("filename")),
            default_filename=default_filename,
            required_suffix=".in",
        )

        restored_path = restore_input_for_trajectory(
            db_path=db_path,
            traj_uid=input_traj_uid,
            output_path=str(output_path),
        )

        print(
            f"\n{tr(output_language, 'restored_input')}:\n"
            f"{Path(restored_path).resolve()}"
        )
        return

    # --------------------------------------------------------------
    # Stored kinetic catalogue: read-only and no frame rescanning.
    # --------------------------------------------------------------
    if action in {
        "stored_kinetics_summary",
        "stored_kinetics_export_csv",
        "stored_kinetics_detailed_export_csv",
    }:
        frame = tool_stored_kinetics_summary(
            db_path=db_path,
            question=question,
            catalog=catalog,
        )

        print_stored_kinetics(frame, language=output_language)

        if action == "stored_kinetics_detailed_export_csv":
            created_paths = export_stored_kinetics_details(
                db_path=db_path,
                kinetics_rows=frame,
                output_dir=output_dir,
            )
            print(f"\n{tr(output_language, 'detailed_files')}:")
            for created_path in created_paths:
                print(created_path)
            return

        if action == "stored_kinetics_export_csv":
            request = extract_requested_kinetics_conditions(
                question,
                catalog,
            )

            molecules = [
                molecule
                for molecule, _isomer
                in request.get("molecule_conditions", [])
            ]
            methods = request.get("methods") or []
            energies = request.get("energy_labels") or []

            default_name = (
                "stored_kinetics_"
                f"{slugify('_'.join(molecules), 'all_molecules')}_"
                f"{slugify('_'.join(methods), 'all_methods')}_"
                f"{slugify('_'.join(energies), 'all_energies')}.csv"
            )

            path = safe_output_path(
                output_dir=output_dir,
                filename=clean_optional_text(arguments.get("filename")),
                default_filename=default_name,
                required_suffix=".csv",
            )

            export_stored_kinetics_csv(frame, path)

            print(
                f"\n{tr(output_language, 'csv_saved')}:\n"
                f"{path}"
            )

        return

    # --------------------------------------------------------------
    # Only predefined actions require validated scalar filters.
    # --------------------------------------------------------------
    filters = normalize_filters(arguments, catalog)

    if action == "database_summary":
        print_database_summary(
            tool_database_summary(db_path, filters),
            language=output_language,
        )
        return

    if action in {"reaction_summary", "reaction_export_csv"}:
        top_n = safe_int(arguments.get("top_n"), 10, 1, 1000)

        rows = tool_reaction_summary(
            db_path,
            filters,
            None if action == "reaction_export_csv" else top_n,
        )

        print_reaction_rows(
            rows[:top_n],
            language=output_language,
        )

        if action == "reaction_export_csv":
            default = (
                f"reactions_{slugify(filters.get('molecule'))}_"
                f"{slugify(filters.get('isomer'))}_"
                f"{slugify(filters.get('method'))}_"
                f"{slugify(filters.get('energy_label'))}.csv"
            )

            path = safe_output_path(
                output_dir,
                arguments.get("filename"),
                default,
                ".csv",
            )

            export_dict_rows_csv(rows, path)

            print(
                f"\n{tr(output_language, 'csv_saved')}:\n"
                f"{path}"
            )

        return

    if action == "fragment_search":
        frame = tool_fragment_search(
            db_path=db_path,
            filters=filters,
            formula=clean_optional_text(arguments.get("formula")),
            mz=safe_float(arguments.get("mz")),
            tolerance=(
                safe_float(arguments.get("tolerance"), 0.001)
                or 0.001
            ),
        )

        print(
            f"\n--- {tr(output_language, 'fragment_search')} ---"
        )

        print(
            tr(output_language, "no_matches")
            if frame.empty
            else frame.to_string(index=False)
        )
        return

    if action == "final_fragment_atoms":
        formula = clean_optional_text(arguments.get("formula"))

        if formula is None:
            raise ValueError(msg("formula_required"))

        rows = tool_final_fragment_atoms(
            db_path=db_path,
            filters=filters,
            formula=formula,
            traj_uid=clean_optional_text(arguments.get("traj_uid")),
        )

        print_final_fragment_atoms(
            rows,
            language=output_language,
        )
        return

    if action == "final_fragment_bond_query":
        atom_1_raw = arguments.get("atom_1")
        atom_2_raw = arguments.get("atom_2")

        atom_1 = (
            safe_int(atom_1_raw, 0, 0)
            if atom_1_raw is not None
            else None
        )

        atom_2 = (
            safe_int(atom_2_raw, 0, 0)
            if atom_2_raw is not None
            else None
        )

        element_1 = clean_optional_text(
            arguments.get("element_1")
        )

        element_2 = clean_optional_text(
            arguments.get("element_2")
        )

        rows = tool_final_fragment_bond_query(
            db_path=db_path,
            filters=filters,
            atom_1=atom_1,
            atom_2=atom_2,
            element_1=element_1,
            element_2=element_2,
            traj_uid=clean_optional_text(arguments.get("traj_uid")),
        )

        print_final_fragment_bond_rows(
            rows,
            element_only=(
                atom_1 is None
                and atom_2 is None
            ),
            language=output_language,
        )
        return

    if action in {
        "mass_spectrum",
        "mass_spectrum_export_csv",
    }:
        rows = tool_mass_spectrum(
            db_path=db_path,
            filters=filters,
            charged_only=safe_bool(
                arguments.get("charged_only")
            ),
            neutral_only=safe_bool(
                arguments.get("neutral_only")
            ),
            mz_min=safe_float(
                arguments.get("mz_min")
            ),
            mz_max=safe_float(
                arguments.get("mz_max")
            ),
            scale=(
                safe_float(
                    arguments.get("scale"),
                    1000.0,
                )
                or 1000.0
            ),
            sort_by=(
                "mz"
                if arguments.get("sort_by") == "mz"
                else "intensity"
            ),
        )

        print_spectrum_rows(
            rows,
            language=output_language,
        )

        if action == "mass_spectrum_export_csv":
            default = (
                f"spectrum_{slugify(filters.get('molecule'))}_"
                f"{slugify(filters.get('isomer'))}_"
                f"{slugify(filters.get('method'))}_"
                f"{slugify(filters.get('energy_label'))}.csv"
            )

            path = safe_output_path(
                output_dir,
                arguments.get("filename"),
                default,
                ".csv",
            )

            export_dict_rows_csv(rows, path)

            print(
                f"\n{tr(output_language, 'csv_saved')}:\n"
                f"{path}"
            )

        return

    if action == "compare_global_kinetics":
        compare_by, comparison_values = (
            resolve_comparison_values(
                arguments,
                catalog,
            )
        )

        base_filters = dict(filters)
        base_filters[compare_by] = None

        persist_frames = safe_int(
            arguments.get("persist_frames"),
            5,
            1,
            10000,
        )

        min_points = safe_int(
            arguments.get("min_points"),
            5,
            2,
            10000,
        )

        window_mode = (
            "common"
            if arguments.get("window_mode") == "common"
            else "censor"
        )

        export_csv = safe_bool(
            arguments.get("export_csv"),
            default=False,
        )

        rows, combined_csv, detailed_paths = (
            compare_global_kinetics(
                db_path=db_path,
                base_filters=base_filters,
                compare_by=compare_by,
                comparison_values=comparison_values,
                persist_frames=persist_frames,
                window_mode=window_mode,
                min_points=min_points,
                output_dir=output_dir,
                export_csv=export_csv,
            )
        )

        print_kinetics_comparison(
            rows,
            compare_by=compare_by,
            language=output_language,
        )

        if combined_csv is not None:
            print(
                f"\n{tr(output_language, 'combined_csv')}:\n"
                f"{combined_csv}"
            )

            print(
                f"\n{tr(output_language, 'detailed_files')}:"
            )

            for path in detailed_paths:
                print(path)

        return

    if action in {
        "global_kinetics",
        "global_kinetics_export_csv",
    }:
        persist_frames = safe_int(
            arguments.get("persist_frames"),
            5,
            1,
            100,
        )

        min_points = safe_int(
            arguments.get("min_points"),
            5,
            2,
            10000,
        )

        window_mode = (
            "common"
            if arguments.get("window_mode") == "common"
            else "censor"
        )

        summary_csv = None
        events_csv = None
        survival_csv = None

        if action == "global_kinetics_export_csv":
            base = (
                f"kinetics_{slugify(filters.get('molecule'))}_"
                f"{slugify(filters.get('isomer'))}_"
                f"{slugify(filters.get('method'))}_"
                f"{slugify(filters.get('energy_label'))}"
            )

            summary_csv = safe_output_path(
                output_dir,
                f"{base}_summary.csv",
                f"{base}_summary.csv",
                ".csv",
            )

            events_csv = safe_output_path(
                output_dir,
                f"{base}_events.csv",
                f"{base}_events.csv",
                ".csv",
            )

            survival_csv = safe_output_path(
                output_dir,
                f"{base}_survival.csv",
                f"{base}_survival.csv",
                ".csv",
            )

        summary, _, _ = compute_and_store_global_kinetics(
            db_path=db_path,
            molecule=filters.get("molecule"),
            isomer=filters.get("isomer"),
            method=filters.get("method"),
            energy_label=filters.get("energy_label"),
            persist_frames=persist_frames,
            window_mode=window_mode,
            min_points=min_points,
            output_summary_csv=(
                str(summary_csv)
                if summary_csv
                else None
            ),
            output_events_csv=(
                str(events_csv)
                if events_csv
                else None
            ),
            output_survival_csv=(
                str(survival_csv)
                if survival_csv
                else None
            ),
        )

        print_kinetics_result(
            summary,
            language=output_language,
        )
        return

    if action == "fragment_first_appearance":
        formula = clean_optional_text(
            arguments.get("formula")
        )

        if formula is None:
            raise ValueError(msg("formula_required"))

        persist_frames = safe_int(
            arguments.get("persist_frames"),
            5,
            1,
            100,
        )

        target, rows = calculate_fragment_events(
            db_path,
            filters,
            formula,
            persist_frames,
            language=output_language,
        )

        summary = summarize_fragment_events(
            formula,
            target,
            filters,
            persist_frames,
            rows,
        )

        print_fragment_appearance(
            summary,
            language=output_language,
        )

        filename = clean_optional_text(
            arguments.get("filename")
        )

        if filename:
            path = safe_output_path(
                output_dir,
                filename,
                (
                    "fragment_first_appearance_"
                    f"{slugify(target)}.csv"
                ),
                ".csv",
            )

            export_dict_rows_csv(rows, path)

            print(
                f"\n{tr(output_language, 'csv_saved')}:\n"
                f"{path}"
            )

        return

    if action == "export_fragment_event_trajectory":
        formula = clean_optional_text(
            arguments.get("formula")
        )

        if formula is None:
            raise ValueError(msg("formula_required"))

        persist_frames = safe_int(
            arguments.get("persist_frames"),
            5,
            1,
            100,
        )

        target, rows = calculate_fragment_events(
            db_path,
            filters,
            formula,
            persist_frames,
            language=output_language,
        )

        selected = select_event(
            rows,
            (
                clean_optional_text(
                    arguments.get("selection")
                )
                or "latest"
            ),
        )

        result = export_one_trajectory(
            db_path=db_path,
            trajectory=selected,
            output_dir=output_dir,
            folder_name=clean_optional_text(
                arguments.get("folder_name")
            ),
            prefix="_".join([
                slugify(selected.get("molecule")),
                slugify(selected.get("isomer")),
                slugify(selected.get("method_label")),
                slugify(selected.get("energy_label")),
                slugify(target),
                slugify(
                    selected.get("traj_code")
                    or selected.get("traj_uid")
                ),
            ]),
        )

        event_csv = (
            Path(result["output_folder"])
            / "selected_event.csv"
        )

        all_events_csv = (
            Path(result["output_folder"])
            / "all_events.csv"
        )

        export_dict_rows_csv(
            [{**selected, **result}],
            event_csv,
        )

        export_dict_rows_csv(
            rows,
            all_events_csv,
        )

        result["selected_event_csv"] = str(
            event_csv
        )

        result["all_events_csv"] = str(
            all_events_csv
        )

        print_export_result(
            result,
            language=output_language,
        )
        return

    if action == "export_trajectory":
        traj_uid = clean_optional_text(
            arguments.get("traj_uid")
        )

        if traj_uid is not None:
            selected = fetch_trajectory_by_uid(
                db_path,
                traj_uid,
            )
        else:
            candidates = fetch_trajectory_candidates(
                db_path,
                filters,
            )

            selected = choose_trajectory(
                candidates,
                (
                    clean_optional_text(
                        arguments.get("selection")
                    )
                    or "first"
                ),
            )

        result = export_one_trajectory(
            db_path=db_path,
            trajectory=selected,
            output_dir=output_dir,
            folder_name=clean_optional_text(
                arguments.get("folder_name")
            ),
        )

        print_export_result(
            result,
            language=output_language,
        )
        return

    if action == "export_trajectory_with_fragment":
        formula = clean_optional_text(
            arguments.get("formula")
        )

        if formula is None:
            raise ValueError(msg("formula_required"))

        scope = (
            clean_optional_text(
                arguments.get("fragment_scope")
            )
            or "any_frame"
        )

        persist_frames = safe_int(
            arguments.get("persist_frames"),
            5,
            1,
            100,
        )

        matches = find_fragment_matches(
            db_path,
            filters,
            formula,
            scope,
            persist_frames,
        )

        selection = (
            clean_optional_text(
                arguments.get("selection")
            )
            or "first"
        )

        if (
            selection in {"latest", "earliest"}
            and scope != "final_frame"
        ):
            selected = select_event(
                matches,
                selection,
            )
        else:
            selected = choose_trajectory(
                matches,
                selection,
            )

        result = export_one_trajectory(
            db_path=db_path,
            trajectory=selected,
            output_dir=output_dir,
            folder_name=clean_optional_text(
                arguments.get("folder_name")
            ),
        )

        print_export_result(
            result,
            language=output_language,
        )
        return

    if action == "export_all_trajectories_with_fragment":
        formula = clean_optional_text(
            arguments.get("formula")
        )

        if formula is None:
            raise ValueError(msg("formula_required"))

        scope = (
            clean_optional_text(
                arguments.get("fragment_scope")
            )
            or "any_frame"
        )

        persist_frames = safe_int(
            arguments.get("persist_frames"),
            1,
            1,
            100,
        )

        max_exports = safe_int(
            arguments.get("max_exports"),
            DEFAULT_MAX_EXPORTS,
            1,
            10000,
        )

        matches = find_fragment_matches(
            db_path,
            filters,
            formula,
            scope,
            persist_frames,
        )

        folder_name = (
            clean_optional_text(
                arguments.get("folder_name")
            )
            or (
                "all_"
                f"{slugify(canonicalize_formula(formula))}"
                "_trajectories"
            )
        )

        result = export_all_matches(
            db_path,
            matches,
            output_dir,
            folder_name,
            max_exports,
        )

        print(
            f"\n--- {tr(output_language, 'bulk_export')} ---"
        )

        print(
            f"{tr(output_language, 'matches'):20s}: "
            f"{result['n_matches']}"
        )

        print(
            f"{tr(output_language, 'exported'):20s}: "
            f"{result['n_exported']}"
        )

        print(
            f"{tr(output_language, 'not_exported'):20s}: "
            f"{result['n_not_exported']}"
        )

        print(
            f"{tr(output_language, 'folder'):20s}: "
            f"{result['output_folder']}"
        )

        print(
            f"{tr(output_language, 'manifest'):20s}: "
            f"{result['manifest_path']}"
        )
        return

    raise ValueError(
        f"{msg('action_not_implemented')}: {action}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=tr("en", "agent_description")
    )
    parser.add_argument("database")
    parser.add_argument("question")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--llama-bin", default=DEFAULT_LLAMA_BIN)
    parser.add_argument(
        "--llama-url",
        default=DEFAULT_LLAMA_URL,
        help=(
            "Local llama-server base URL. Default: "
            f"{DEFAULT_LLAMA_URL}"
        ),
    )
    parser.add_argument(
        "--no-llama-fallback",
        action="store_true",
        help=(
            "Fail if llama-server is unavailable instead of falling back "
            "to llama-cli."
        ),
    )
    parser.add_argument(
        "--show-backend",
        action="store_true",
        help="Print whether SQListo is using llama-server or llama-cli.",
    )
    parser.add_argument("--sql-knowledge", default=DEFAULT_KNOWLEDGE_FILE)
    parser.add_argument("--tools-file", default=DEFAULT_TOOLS_FILE)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--show-plan", action="store_true")
    parser.add_argument(
        "--force-router",
        action="store_true",
        help=(
            "Always use the LLM router. By default, obvious read-only SQL "
            "questions bypass it for faster execution."
        ),
    )
    parser.add_argument("--show-sql", action="store_true")
    parser.add_argument("--show-repairs", action="store_true")
    parser.add_argument("--router-tokens", type=int, default=DEFAULT_ROUTER_TOKENS)
    parser.add_argument("--sql-tokens", type=int, default=DEFAULT_N_TOKENS)
    parser.add_argument("--timeout", type=int, default=DEFAULT_ROUTER_TIMEOUT)
    parser.add_argument("--max-rows", type=int, default=100)
    parser.add_argument(
        "--lang",
        choices=["en", "es"],
        default="en",
        help=(
            "Output language. English is used by default, regardless "
            "of the language of the question."
        ),
    )
    args = parser.parse_args()

    global CURRENT_LANGUAGE
    CURRENT_LANGUAGE = args.lang

    try:
        database, model, llama_bin, sql_knowledge_path = validate_paths(
            database=args.database,
            model=args.model,
            llama_bin=args.llama_bin,
            knowledge_file=args.sql_knowledge,
        )

        backend_name = configure_llm_backend(
            llama_url=args.llama_url,
            allow_cli_fallback=not args.no_llama_fallback,
        )

        if args.show_backend:
            print(f"LLM backend: {backend_name}")

        validate_question(args.question)
        tools_manual = load_text_file(args.tools_file)
        sql_knowledge = load_knowledge(sql_knowledge_path)
        catalog = get_database_catalog(database)

        # Validate explicit energy labels before routing or SQL generation.
        validate_explicit_energy_labels(
            question=args.question,
            catalog=catalog,
        )
        
        # Validate every combination of energy, label, etc...
        validate_explicit_condition_combination(
            db_path=args.database,
            question=args.question,
            catalog=catalog,
        )
        

        question_cf = args.question.casefold()

        kinetics_words = (
            "kinetic", "kinetics","k", "k global", "cinética", "cinetica",
            "constante k", "constantes k", "rate constant", "global k"
        )
        stored_words = (
            "stored", "almacenad", "guardad", "no recalcul",
            "resume", "resumen", "summarise", "summarize",
            "catalogue", "catálogo", "catalogo",
        )

        asks_stored_kinetics = (
            any(word in question_cf for word in kinetics_words)
            and any(word in question_cf for word in stored_words)
        )
        asks_kinetics_csv = (
            asks_stored_kinetics
            and (
                "csv" in question_cf
                or "export" in question_cf
                or "exporta" in question_cf
                or "guarda" in question_cf
            )
        )
        detailed_words = (
            "puntos", "points", "eventos", "events",
            "supervivencia", "survival", "estadísticas completas",
            "estadisticas completas", "full statistics", "complete details",
        )
        asks_detailed_kinetics_export = (
            asks_kinetics_csv
            and any(word in question_cf for word in detailed_words)
        )

        if not args.force_router and asks_stored_kinetics:
            if asks_detailed_kinetics_export:
                action = "stored_kinetics_detailed_export_csv"
            elif asks_kinetics_csv:
                action = "stored_kinetics_export_csv"
            else:
                action = "stored_kinetics_summary"
            arguments: dict[str, Any] = {}
            plan = {
                "action": action,
                "arguments": arguments,
                "routing": "deterministic_stored_kinetics",
            }
        else:
            # Exact input requests can be resolved without the LLM router.
            uid_match = re.search(r"\btraj_[A-Za-z0-9]+\b", args.question)
            asks_about_input = any(
                signal in question_cf
                for signal in (
                    "input", "md.in", "input file", "archivo de input",
                    "fichero de input",
                )
            )
            asks_to_restore_input = any(
                signal in question_cf
                for signal in (
                    "restore", "restaura", "restaurar", "recover", "recupera",
                    "save", "guarda", "guardar", "write", "export", "exporta",
                )
            )

            if not args.force_router and uid_match and asks_about_input:
                action = "restore_input" if asks_to_restore_input else "show_input"
                arguments = {"traj_uid": uid_match.group(0)}
                plan = {
                    "action": action,
                    "arguments": arguments,
                    "routing": "deterministic_input_tool",
                }
            else:
                direct_sql = (
                    not args.force_router
                    and should_route_directly_to_sql(args.question)
                )

                if direct_sql:
                    action = "sql_query"
                    arguments = {}
                    plan = {
                        "action": action,
                        "arguments": arguments,
                        "routing": "deterministic_sql_bypass",
                    }
                else:
                    raw_plan = generate_agent_plan(
                        question=args.question,
                        tools_manual=tools_manual,
                        catalog=catalog,
                        model_path=model,
                        llama_cli=llama_bin,
                        router_tokens=args.router_tokens,
                        router_timeout=args.timeout,
                    )
                    action, arguments = validate_plan(raw_plan)
                    action, arguments = normalize_agent_plan(
                        action=action,
                        arguments=arguments,
                        question=args.question,
                        catalog=catalog,
                    )
                    plan = {
                        "action": action,
                        "arguments": arguments,
                        "routing": "llm_router",
                    }

        if args.show_plan:
            print(f"\n--- {tr(args.lang, 'agent_plan')} ---")
            print(json.dumps(plan, indent=2, ensure_ascii=False))

        execute_action(
            action=action,
            arguments=arguments,
            question=args.question,
            db_path=database,
            catalog=catalog,
            output_dir=args.output_dir,
            model_path=model,
            llama_cli=llama_bin,
            sql_knowledge=sql_knowledge,
            show_sql=args.show_sql,
            show_repairs=args.show_repairs,
            max_rows=args.max_rows,
            sql_tokens=args.sql_tokens,
            timeout_seconds=args.timeout,
            output_language=args.lang,
        )

    except (
        FileNotFoundError,
        ValueError,
        RuntimeError,
        sqlite3.Error,
        pd.errors.DatabaseError,
    ) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

