# SQListo

### An AI Assistant for the Storage and Analysis of Molecular Dynamics Trajectories

SQListo is a Python-based scientific software platform designed for the efficient storage, retrieval and analysis of molecular dynamics trajectories through compressed SQLite databases and a locally deployed artificial intelligence assistant.

The software combines conventional computational chemistry tools, structured database queries and natural language interaction within a unified framework.

## Main Features

- Compressed storage of multi-frame XYZ trajectories.
- Import of TeraChem and VENUS molecular dynamics simulations.
- Recovery of molecular trajectories and original simulation inputs.
- Molecular fragmentation analysis.
- Identification and classification of reaction products.
- Theoretical mass spectrum construction.
- Molecular and trajectory feature extraction.
- Global unimolecular fragmentation kinetics.
- Maximum likelihood and regression-based kinetic analysis.
- Integration of compatible SQLite databases.
- Natural language database queries in English and Spanish.
- Local LLM inference without external AI APIs.

## Software Architecture

SQListo integrates three main components:

| Component | Description |
|---|---|
| XYZ2DB | Molecular trajectory storage and scientific analysis engine |
| SQLite | Structured and compressed molecular dynamics database |
| SQListo Agent | Hybrid natural language, SQL and scientific tool interface |

The AI assistant combines deterministic query generation, LLM-based routing and specialized Python tools to retrieve and analyse molecular dynamics data.

## Language Model

The local AI assistant uses:

- Model: Qwen2.5-Coder-1.5B-Instruct
- Format: GGUF
- Quantization: Q4_K_M
- Inference engine: llama.cpp
- Configured context size: 8192 tokens

The model is executed locally and does not require a commercial AI API.

## Installation

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/SQListo.git
cd SQListo
```

Create a Python environment and install the dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The AI assistant additionally requires a compatible llama.cpp installation and the corresponding GGUF model.

## Basic Usage

Display the available scientific analysis commands:

```bash
python main.py --help
```

Display a database summary:

```bash
python main.py summary DBs/azc_dfcz_ub3_z3.db
```

Filter trajectories by molecule:

```bash
python main.py summary DBs/azc_dfcz_ub3_z3.db \
    --molecule Azaconazole
```

Start the local inference server:

```bash
bash start_sqlisto_llama_server.sh
```

Query the database using natural language:

```bash
python sqlisto_agent.py DBs/azc_dfcz_ub3_z3.db \
    "How many trajectories are stored for each molecule?"
```

Retrieve stored kinetic constants:

```bash
python sqlisto_agent.py DBs/azc_dfcz_ub3_z3.db \
    "Show the stored global kinetic constants for Azaconazole."
```

## Demonstration Dataset

The demonstration dataset contains molecular dynamics simulations of two triazole fungicides.

| Molecule | Trajectories | Stored frames |
|---|---:|---:|
| Azaconazole | 313 | 2,020,986 |
| Difenoconazole | 325 | 1,539,072 |
| Total | 638 | 3,560,058 |

All trajectories in this dataset are labelled uB3LYP and ZPEx3.

The dataset includes simulation inputs, compressed molecular coordinates, fragmentation results, reaction classifications and kinetic analyses.

Database and model files are distributed separately from the source code.

## Testing

Run the regression tests with:

```bash
python -m unittest discover -s tests -v
```

## Documentation

- `README_sqlisto_agent.md`: AI assistant documentation.
- `README_prompts.md`: prompt examples and usage instructions.
- `docs/tested_environment.md`: tested software configuration.

## Scientific Context

SQListo was developed as part of doctoral research in theoretical and computational chemistry at the Universidad Autónoma de Madrid (UAM).

The software aims to facilitate the reproducible analysis of large molecular dynamics datasets and provide accessible interfaces for computational chemistry research.

## Project Status

Under active development and scientific validation.

## Citation

Citation information will be provided with the first versioned release.
