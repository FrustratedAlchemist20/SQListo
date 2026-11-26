# SQListo — Practical AI Assistant Tutorial

## 1. Introduction

SQListo provides a natural language interface for querying and analysing molecular dynamics trajectories stored in compressed SQLite databases.

The assistant combines deterministic SQL generation, local large language model inference and specialized computational chemistry tools.

All AI inference is performed locally using Qwen2.5-Coder-1.5B-Instruct and llama.cpp. No external AI service or commercial API is required.

This tutorial uses the demonstration database distributed with SQListo.

## 2. Installation

```bash
git clone https://github.com/FrustratedAlchemist20/SQListo.git

cd SQListo

bash install.sh
```

For systems without administrator privileges, a compatible user-space compiler can be provided through Conda.

## 3. Starting SQListo

Activate the Python environment:

```bash
source .venv/bin/activate
```

Start the local inference server:

```bash
bash start_sqlisto_llama_server.sh
```

Verify that the server is available:

```bash
curl http://127.0.0.1:8080/health
```

Expected response:

```json
{"status":"ok"}
```

Define the demonstration database path:

```bash
DB="DBs/azc_dfcz_ub3_z3.db"
```

This variable will be used throughout the tutorial.

## 4. Demonstration Dataset

The demonstration database contains molecular dynamics trajectories of two protonated triazole fungicides.

| Property | Value |
|---|---:|
| Molecules | 2 |
| Azaconazole trajectories | 313 |
| Difenoconazole trajectories | 325 |
| Total trajectories | 638 |
| Total stored frames | 3,560,058 |
| Fragment analyses | 638 |
| Stored fragments | 1,137 |
| Electronic structure method label | uB3LYP |
| Excitation condition | ZPEx3 |

The dataset includes compressed molecular coordinates, simulation inputs, fragmentation results, reaction classifications and stored kinetic analyses.

## 5. Basic Database Exploration

### Example 1 — Count stored trajectories

```bash
python sqlisto_agent.py "$DB" \
    "How many trajectories are stored in the database?"
```

Expected result:

| n_trajectories |
|---:|
| 638 |

### Example 2 — Count trajectories for each molecule

```bash
python sqlisto_agent.py "$DB" \
    "How many trajectories are stored for each molecule?"
```

Expected result:

| molecule | n_trajectories |
|---|---:|
| Azaconazole | 313 |
| Difenoconazole | 325 |

### Example 3 — Count trajectories for each computational method

```bash
python sqlisto_agent.py "$DB" \
    "How many trajectories are stored for each method?"
```

Expected result:

| method_label | n_trajectories |
|---|---:|
| uB3LYP | 638 |

### Example 4 — Filter trajectories by molecule

```bash
python sqlisto_agent.py "$DB" \
    "How many trajectories are stored for Azaconazole?"
```

Expected result: 313 trajectories.

### Example 5 — Average trajectory length

```bash
python sqlisto_agent.py "$DB" \
    "What is the average number of frames for each molecule?"
```

Expected result, approximately:

| molecule | avg_frames |
|---|---:|
| Azaconazole | 6456.82 |
| Difenoconazole | 4735.61 |

## 6. Understanding Generated SQL

SQListo can display the SQL query used to retrieve information from the database.

```bash
python sqlisto_agent.py "$DB" \
    "How many trajectories are stored for each molecule?" \
    --show-sql \
    --show-plan \
    --show-backend
```

Expected SQL:

```sql
SELECT
    t.molecule AS molecule,
    COUNT(*) AS n_trajectories
FROM trajectories AS t
GROUP BY t.molecule
ORDER BY t.molecule;
```

For supported metadata queries, SQListo uses deterministic query generation rather than requiring the LLM to generate SQL.

This mechanism improves response speed and reproducibility.

## 7. Molecular Fragmentation and Reaction Analysis

### Example 6 — Most frequent final reactions

```bash
python sqlisto_agent.py "$DB" \
    "Show the most frequent fragmentation reactions for Azaconazole." \
    --show-plan \
    --show-backend \
    --no-llama-fallback
```

Previously observed leading results:

| Final products | Count | Frequency (%) |
|---|---:|---:|
| C12H12Cl2N3O2+ | 123 | 39.30 |
| C9H7Cl2O2+ + C3H5N3 | 80 | 25.56 |
| C10H9Cl2O2+ + C2H3N3 | 70 | 22.36 |

The intact precursor is included in the final-product distribution.

Therefore, these results should not be interpreted as frequencies conditioned exclusively on reactive trajectories.

### Example 7 — Analyse Difenoconazole reactions

```bash
python sqlisto_agent.py "$DB" \
    "Show the most frequent fragmentation reactions for Difenoconazole." \
    --show-plan \
    --show-backend
```

### Example 8 — Search for a molecular fragment

```bash
python sqlisto_agent.py "$DB" \
    "Find fragmentation reactions of Azaconazole containing C2H3N3." \
    --show-plan
```

### Example 9 — Search for another fragmentation channel

```bash
python sqlisto_agent.py "$DB" \
    "Find fragmentation reactions of Difenoconazole containing C3H5N3." \
    --show-plan
```

These queries illustrate how natural language can be used to investigate specific fragmentation products.

The fragment-search examples should be checked against the corresponding stored fragmentation records.

## 8. Theoretical Mass Spectra

### Example 10 — Azaconazole theoretical spectrum

```bash
python sqlisto_agent.py "$DB" \
    "Show the theoretical mass spectrum of Azaconazole." \
    --show-plan
```

### Example 11 — Difenoconazole theoretical spectrum

```bash
python sqlisto_agent.py "$DB" \
    "Show the theoretical mass spectrum of Difenoconazole." \
    --show-plan
```

### Example 12 — Export a theoretical mass spectrum

```bash
python sqlisto_agent.py "$DB" \
    "Export the theoretical mass spectrum of Azaconazole to CSV." \
    --show-plan \
    --output-dir outputs/tutorial
```

Inspect the generated CSV files:

```bash
ls -lh outputs/tutorial/
```

The exported data can be used for subsequent visualization and comparison with experimental mass spectra.

These spectra are constructed from simulation-derived fragmentation products. They should not be interpreted as a complete simulation of experimental ion activation and detection.

## 9. Global Unimolecular Fragmentation Kinetics

SQListo can retrieve kinetic constants previously calculated and stored in SQLite without rescanning the molecular trajectory frames.

### Example 13 — Stored kinetics of Azaconazole

```bash
python sqlisto_agent.py "$DB" \
    "Show the stored global kinetic constants for Azaconazole using uB3LYP." \
    --show-plan
```

Previously observed results:

| Parameter | Value |
|---|---:|
| Trajectories | 313 |
| Reactive events | 308 |
| Censored trajectories | 5 |
| Persistence frames | 5 |
| Event fraction | 0.984026 |
| MLE rate constant (ps⁻¹) | 5.433776 |
| Regression rate constant (ps⁻¹) | 2.804460 |
| MLE half-life (ps) | 0.127563 |
| Regression R² | 0.919741 |

### Example 14 — Stored kinetics of Difenoconazole

```bash
python sqlisto_agent.py "$DB" \
    "Show the stored global kinetic constants for Difenoconazole using uB3LYP." \
    --show-plan
```

Previously observed kinetic records:

| Persistence frames | Reactive events | Censored | MLE k (ps⁻¹) |
|---:|---:|---:|---:|
| 5 | 315 | 10 | 10.205900 |
| 100 | 246 | 79 | 0.493806 |

The persistence criterion affects event identification and therefore the resulting kinetic estimates.

### Example 15 — Export stored kinetic constants

```bash
python sqlisto_agent.py "$DB" \
    "Export the stored global kinetic constants for Azaconazole to CSV." \
    --show-plan \
    --output-dir outputs/tutorial
```

### Example 16 — Export detailed kinetic information

```bash
python sqlisto_agent.py "$DB" \
    "Export detailed stored kinetic results for Azaconazole." \
    --show-plan \
    --output-dir outputs/tutorial
```

When comparing kinetic constants, ensure that the computational method, excitation condition, persistence criterion and analysis window are consistent.

## 10. Trajectory and Input Recovery

SQListo includes tools for recovering individual molecular dynamics trajectories and their associated simulation inputs.

First obtain a trajectory identifier:

```bash
python sqlisto_agent.py "$DB" \
    "Show five trajectory identifiers for Azaconazole." \
    --show-sql
```

Select a valid trajectory UID from the returned results.

### Example 17 — Retrieve a simulation input

```bash
python sqlisto_agent.py "$DB" \
    "Show the stored input for trajectory TRAJECTORY_UID." \
    --show-plan
```

### Example 18 — Export a molecular dynamics trajectory

```bash
python sqlisto_agent.py "$DB" \
    "Export trajectory TRAJECTORY_UID to XYZ." \
    --show-plan \
    --output-dir outputs/tutorial
```

Replace `TRAJECTORY_UID` with an actual identifier from the database.

Recovered XYZ trajectories can subsequently be inspected using compatible molecular visualization software.

## 11. Multilingual Interaction

SQListo supports natural language interaction in English and Spanish.

### Example 19 — Spanish metadata query

```bash
python sqlisto_agent.py "$DB" \
    "¿Cuántas trayectorias hay para cada molécula?" \
    --lang es \
    --show-sql
```

Expected result:

| molecule | n_trajectories |
|---|---:|
| Azaconazole | 313 |
| Difenoconazole | 325 |

### Example 20 — Spanish reaction analysis

```bash
python sqlisto_agent.py "$DB" \
    "Muéstrame las reacciones de fragmentación más frecuentes del Azaconazole." \
    --lang es \
    --show-plan
```

## 12. Inspecting AI Tool Routing

To explicitly test LLM-based scientific tool selection:

```bash
python sqlisto_agent.py "$DB" \
    "Show the most frequent fragmentation reactions for Azaconazole." \
    --force-router \
    --show-plan \
    --show-backend \
    --no-llama-fallback
```

An expected routing decision is:

```json
{
    "action": "reaction_summary",
    "arguments": {
        "molecule": "Azaconazole",
        "top_n": 10
    },
    "routing": "llm_router"
}
```

This illustrates the distinction between LLM-based tool selection and deterministic scientific calculations.

The language model selects a suitable operation, while the underlying Python and SQLite tools retrieve or calculate the scientific results.

## 13. Useful Assistant Options

| Option | Purpose |
|---|---|
| `--show-sql` | Display generated SQL queries |
| `--show-plan` | Display the selected action and arguments |
| `--show-backend` | Display the inference backend |
| `--show-repairs` | Display automatic SQL repairs |
| `--force-router` | Force LLM-based routing |
| `--no-llama-fallback` | Require the local inference server |
| `--lang es` | Display output in Spanish |
| `--lang en` | Display output in English |
| `--output-dir` | Specify the output directory |
| `--max-rows` | Limit returned SQL rows |

Display the complete list of available options:

```bash
python sqlisto_agent.py --help
```

## 14. Installation Validation

Run the unit tests:

```bash
python -m unittest discover -s tests -v
```

Run the end-to-end smoke test:

```bash
bash scripts/smoke_test.sh
```

The smoke test validates the Python environment, database integrity, language model, local inference server, SQL queries, scientific tool routing and retrieval of stored kinetic constants.

## 15. Scientific Considerations

SQListo is designed to assist researchers with molecular dynamics data exploration and scientific analysis.

Users should independently verify:

- Generated SQL queries.
- Selected scientific analysis tools.
- Molecular and computational filters.
- Fragment identification criteria.
- Kinetic analysis parameters.
- Scientific interpretation of the resulting data.

LLM-based routing may produce different responses depending on the input question and inference configuration.

Natural language interaction facilitates scientific analysis but does not replace expert validation of computational results.

## 16. Citation

If you use SQListo in your research, please cite the corresponding software record.

**SQListo: An AI Assistant for the Storage and Analysis of Molecular Dynamics Trajectories**

DOI: https://doi.org/10.5281/zenodo.24568313

GitHub: https://github.com/FrustratedAlchemist20/SQListo
