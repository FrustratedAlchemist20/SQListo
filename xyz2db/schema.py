# xyz2db/schema.py

# This is only the basic schema definition for the xyz2db SQLite database
# To understand how is the structure of the database and how to use it


# xyz2db/schema.py

# xyz2db/schema.py

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS md_inputs (
    input_id TEXT PRIMARY KEY,
    input_filename TEXT,
    input_sha256 TEXT NOT NULL UNIQUE,
    basis TEXT,
    has_basis INTEGER,
    coordinates_file TEXT,
    charge INTEGER,
    spinmult INTEGER,
    method TEXT,
    dispersion TEXT,
    has_dispersion INTEGER,
    run_type TEXT,
    nstep INTEGER,
    timestep REAL,
    thermostat TEXT,
    rescalefreq INTEGER,
    tinit REAL,
    t0 REAL,
    gpus INTEGER,
    raw_input_text TEXT,
    energy_label_factor REAL,
    energy_temperature_K REAL,
    energy_kcal_mol REAL,
    zpe_kcal_mol REAL,
    dof INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trajectories (
    traj_uid TEXT PRIMARY KEY,
    traj_code TEXT,
    input_id TEXT,
    molecule TEXT,
    isomer TEXT,
    method_label TEXT,
    energy_label TEXT,
    run_id INTEGER,
    original_run_dir TEXT,
    source_filename TEXT NOT NULL,
    source_abspath TEXT,
    sha256 TEXT NOT NULL UNIQUE,
    natoms INTEGER NOT NULL,
    nframes INTEGER NOT NULL,
    atomic_numbers BLOB NOT NULL,
    symbols_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    extra_json TEXT,
    FOREIGN KEY (input_id) REFERENCES md_inputs(input_id)
);

CREATE TABLE IF NOT EXISTS frame_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    traj_uid TEXT NOT NULL,
    block_index INTEGER NOT NULL,
    start_frame INTEGER NOT NULL,
    end_frame INTEGER NOT NULL,
    nframes INTEGER NOT NULL,
    compression TEXT NOT NULL,
    payload BLOB NOT NULL,
    FOREIGN KEY (traj_uid) REFERENCES trajectories(traj_uid) ON DELETE CASCADE,
    UNIQUE(traj_uid, block_index)
);

CREATE INDEX IF NOT EXISTS idx_frame_blocks_traj
ON frame_blocks(traj_uid, block_index);

CREATE INDEX IF NOT EXISTS idx_trajectories_input_id
ON trajectories(input_id);

CREATE TABLE IF NOT EXISTS fragment_analysis (
    traj_uid TEXT PRIMARY KEY,
    analyzed_frame_idx INTEGER,
    analyzed_frame_number INTEGER,
    fragment_count INTEGER NOT NULL,
    analysis_method TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (traj_uid) REFERENCES trajectories(traj_uid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS fragments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    traj_uid TEXT NOT NULL,
    fragment_index INTEGER NOT NULL,
    formula TEXT,
    exact_mass REAL,
    charge_guess INTEGER,
    n_atoms INTEGER,
    atom_indices_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (traj_uid) REFERENCES trajectories(traj_uid) ON DELETE CASCADE,
    UNIQUE(traj_uid, fragment_index)
);

CREATE INDEX IF NOT EXISTS idx_fragments_traj_uid
ON fragments(traj_uid);

CREATE TABLE IF NOT EXISTS trajectory_features (
    traj_uid TEXT PRIMARY KEY,
    traj_code TEXT,
    molecule TEXT,
    isomer TEXT,
    method_label TEXT,
    energy_label TEXT,
    run_id INTEGER,
    nframes INTEGER,
    natoms INTEGER,
    timestep REAL,
    final_time_ps REAL,
    fragment_count INTEGER,
    largest_fragment_formula TEXT,
    largest_fragment_mass REAL,
    smallest_fragment_formula TEXT,
    smallest_fragment_mass REAL,
    charged_fragment_count INTEGER,
    neutral_fragment_count INTEGER,
    total_fragment_mass REAL,
    mass_balance_error REAL,
    contains_h_plus INTEGER,
    contains_c2h3n3 INTEGER,
    contains_c3h5n3 INTEGER,
    contains_hcl INTEGER,
    contains_h2 INTEGER,
    contains_ch3_plus INTEGER,
    contains_c2h5_plus INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (traj_uid) REFERENCES trajectories(traj_uid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_trajectory_features_method
ON trajectory_features(method_label);

CREATE INDEX IF NOT EXISTS idx_trajectory_features_molecule
ON trajectory_features(molecule);

CREATE TABLE IF NOT EXISTS reaction_summary (
    reaction_uid TEXT PRIMARY KEY,
    method_label TEXT,
    molecule_labels TEXT,
    energy_labels TEXT,
    count INTEGER NOT NULL,
    frequency_pct REAL NOT NULL,
    fragment_count INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reaction_fragments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reaction_uid TEXT NOT NULL,
    fragment_index INTEGER NOT NULL,
    formula TEXT NOT NULL,
    exact_mass REAL NOT NULL,
    FOREIGN KEY (reaction_uid) REFERENCES reaction_summary(reaction_uid) ON DELETE CASCADE,
    UNIQUE(reaction_uid, fragment_index)
);

CREATE TABLE IF NOT EXISTS reaction_members (
    reaction_uid TEXT NOT NULL,
    traj_uid TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reaction_uid) REFERENCES reaction_summary(reaction_uid) ON DELETE CASCADE,
    FOREIGN KEY (traj_uid) REFERENCES trajectories(traj_uid) ON DELETE CASCADE,
    UNIQUE(reaction_uid, traj_uid)
);

CREATE INDEX IF NOT EXISTS idx_reaction_fragments_formula
ON reaction_fragments(formula);

CREATE INDEX IF NOT EXISTS idx_reaction_fragments_mass
ON reaction_fragments(exact_mass);

CREATE INDEX IF NOT EXISTS idx_reaction_members_traj
ON reaction_members(traj_uid);

CREATE INDEX IF NOT EXISTS idx_reaction_members_uid
ON reaction_members(reaction_uid);

CREATE INDEX IF NOT EXISTS idx_reaction_summary_method
ON reaction_summary(method_label);

CREATE TABLE IF NOT EXISTS kinetics_global (
    kinetics_uid TEXT PRIMARY KEY,
    molecule TEXT,
    isomer TEXT,
    method_label TEXT,
    energy_label TEXT,
    persist_frames INTEGER,
    window_mode TEXT,
    min_points INTEGER,
    n_trajectories_total INTEGER,
    n_events INTEGER,
    n_censored INTEGER,
    event_fraction REAL,
    mean_followup_ps REAL,
    median_followup_ps REAL,
    min_followup_ps REAL,
    max_followup_ps REAL,
    mean_event_time_ps REAL,
    median_event_time_ps REAL,
    min_event_time_ps REAL,
    max_event_time_ps REAL,
    common_window_ps REAL,
    k_regression_ps_minus1 REAL,
    k_regression_stderr REAL,
    k_regression_ci95_low REAL,
    k_regression_ci95_high REAL,
    half_life_regression_ps REAL,
    r2 REAL,
    n_fit_points INTEGER,
    k_mle_ps_minus1 REAL,
    k_mle_stderr REAL,
    k_mle_ci95_low REAL,
    k_mle_ci95_high REAL,
    half_life_mle_ps REAL,
    warnings_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kinetics_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kinetics_uid TEXT NOT NULL,
    traj_uid TEXT NOT NULL,
    traj_code TEXT,
    molecule TEXT,
    isomer TEXT,
    method_label TEXT,
    energy_label TEXT,
    event_occurred INTEGER,
    event_time_ps REAL,
    event_frame_idx INTEGER,
    followup_time_ps REAL,
    n_frames_scanned INTEGER,
    max_fragment_count INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(kinetics_uid, traj_uid)
);

CREATE INDEX IF NOT EXISTS idx_kinetics_global_filters
ON kinetics_global(molecule, isomer, method_label, energy_label);

CREATE INDEX IF NOT EXISTS idx_kinetics_events_uid
ON kinetics_events(kinetics_uid);

CREATE INDEX IF NOT EXISTS idx_kinetics_events_traj
ON kinetics_events(traj_uid);
"""
