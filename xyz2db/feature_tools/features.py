# xyz2db/feature_tools/features.py

from collections import Counter
import math
import re

from ..chemistry import ATOM_MASSES

try:
    from ..chemistry import FORMULA_ORDER
except ImportError:
    FORMULA_ORDER = ["C", "H", "N", "O", "Cl", "Br", "S", "Si", "F", "P"]

HALOGENS = {"F", "Cl", "Br", "I"}
HETERO_NO_H = {"N", "O", "S", "P", "Si", "F", "Cl", "Br", "I"}
TRACKED_ELEMENTS = ["C", "H", "N", "O", "Cl", "Br", "S", "Si", "F", "P"]


def safe_mean(values):
    if not values:
        return None
    return sum(values) / len(values)


def safe_std(values):
    if not values:
        return None
    if len(values) == 1:
        return 0.0
    mu = safe_mean(values)
    return math.sqrt(sum((x - mu) ** 2 for x in values) / len(values))


def safe_median(values):
    if not values:
        return None
    vals = sorted(values)
    n = len(vals)
    mid = n // 2
    if n % 2 == 1:
        return vals[mid]
    return 0.5 * (vals[mid - 1] + vals[mid])


def safe_min(values):
    return min(values) if values else None


def safe_max(values):
    return max(values) if values else None


def safe_ratio(num, den):
    if den in (None, 0):
        return None
    return num / den


def is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def compute_parent_mass_from_symbols(symbols):
    mass = 0.0
    for s in symbols:
        mass += ATOM_MASSES.get(s, 0.0)
    return mass


def count_formula(fragment_rows, target_formula):
    return 1 if any((f.get("formula") or "") == target_formula for f in fragment_rows) else 0


def count_formula_occurrences(fragment_rows, target_formula):
    return sum(1 for f in fragment_rows if (f.get("formula") or "") == target_formula)


def normalize_formula_for_parsing(formula: str):
    if formula is None:
        return ""
    txt = str(formula).strip()
    txt = txt.replace(" ", "")
    return txt


def parse_formula_counts(formula: str):
    txt = normalize_formula_for_parsing(formula)
    if not txt:
        return {}

    txt = txt.replace("+", "").replace("-", "")

    pattern = r"([A-Z][a-z]?)(\d*)"
    counts = {}
    for elem, n_txt in re.findall(pattern, txt):
        n = int(n_txt) if n_txt else 1
        counts[elem] = counts.get(elem, 0) + n
    return counts


def infer_formula_charge(formula: str):
    txt = normalize_formula_for_parsing(formula)
    if not txt:
        return 0
    plus = txt.count("+")
    minus = txt.count("-")
    return plus - minus


def build_formula_from_counts(counts):
    if not counts:
        return None

    parts = []
    used = set()

    for elem in FORMULA_ORDER:
        n = counts.get(elem, 0)
        if n > 0:
            parts.append(elem if n == 1 else f"{elem}{n}")
            used.add(elem)

    for elem in sorted(counts):
        if elem in used:
            continue
        n = counts[elem]
        parts.append(elem if n == 1 else f"{elem}{n}")

    return "".join(parts)


def get_parent_element_counts(symbols):
    counts = Counter(symbols)
    out = {}
    for elem in TRACKED_ELEMENTS:
        out[f"parent_n_{elem.lower()}"] = int(counts.get(elem, 0))
    out["parent_n_halogens"] = int(sum(counts.get(x, 0) for x in HALOGENS))
    out["parent_n_hetero_no_h"] = int(sum(counts.get(x, 0) for x in HETERO_NO_H))
    return out


def annotate_fragment(fragment):
    formula = fragment.get("formula")
    counts = parse_formula_counts(formula)

    charge_guess = fragment.get("charge_guess")
    if charge_guess is None:
        charge_guess = infer_formula_charge(formula)

    exact_mass = fragment.get("exact_mass")
    n_atoms = fragment.get("n_atoms")

    return {
        **fragment,
        "_counts": counts,
        "_charge": charge_guess,
        "_exact_mass": exact_mass,
        "_n_atoms": n_atoms,
        "_contains_n": counts.get("N", 0) > 0,
        "_contains_o": counts.get("O", 0) > 0,
        "_contains_s": counts.get("S", 0) > 0,
        "_contains_si": counts.get("Si", 0) > 0,
        "_contains_halogen": any(counts.get(x, 0) > 0 for x in HALOGENS),
        "_contains_cl": counts.get("Cl", 0) > 0,
        "_contains_br": counts.get("Br", 0) > 0,
        "_contains_c": counts.get("C", 0) > 0,
        "_contains_h": counts.get("H", 0) > 0,
    }


def compute_fragment_feature_dict(
    traj_meta,
    input_meta,
    fragment_rows,
    symbols,
):
    """
    Rich feature dict for one trajectory.
    This does NOT assume storage in SQLite; it simply returns a dict.
    """

    parent_mass = compute_parent_mass_from_symbols(symbols)
    parent_natoms = len(symbols)
    parent_counts = get_parent_element_counts(symbols)

    parent_formula_counts = Counter(symbols)
    parent_formula = build_formula_from_counts(parent_formula_counts)

    parent_h = parent_counts.get("parent_n_h", 0)
    parent_c = parent_counts.get("parent_n_c", 0)
    parent_n = parent_counts.get("parent_n_n", 0)
    parent_o = parent_counts.get("parent_n_o", 0)
    parent_halogens = parent_counts["parent_n_halogens"]
    parent_hetero = parent_counts["parent_n_hetero_no_h"]

    ann = [annotate_fragment(f) for f in fragment_rows]
    fragment_count = len(ann)

    masses = [f["_exact_mass"] for f in ann if f["_exact_mass"] is not None]
    atom_sizes = [f["_n_atoms"] for f in ann if f["_n_atoms"] is not None]

    sorted_by_mass = sorted(
        [f for f in ann if f["_exact_mass"] is not None],
        key=lambda x: x["_exact_mass"],
        reverse=True,
    )

    largest = sorted_by_mass[0] if sorted_by_mass else None
    smallest = sorted_by_mass[-1] if sorted_by_mass else None

    charged_frags = [f for f in ann if (f["_charge"] or 0) != 0]
    neutral_frags = [f for f in ann if (f["_charge"] or 0) == 0]

    charged_masses = [f["_exact_mass"] for f in charged_frags if f["_exact_mass"] is not None]
    neutral_masses = [f["_exact_mass"] for f in neutral_frags if f["_exact_mass"] is not None]

    total_fragment_mass = sum(masses) if masses else 0.0
    mass_balance_error = parent_mass - total_fragment_mass
    mass_balance_error_abs = abs(mass_balance_error)
    mass_balance_error_rel = safe_ratio(mass_balance_error_abs, parent_mass)

    largest_fragment_mass = None if largest is None else largest["_exact_mass"]
    smallest_fragment_mass = None if smallest is None else smallest["_exact_mass"]

    largest_fragment_n_atoms = None if largest is None else largest["_n_atoms"]
    smallest_fragment_n_atoms = None if smallest is None else smallest["_n_atoms"]

    largest_fragment_charge = None if largest is None else largest["_charge"]
    smallest_fragment_charge = None if smallest is None else smallest["_charge"]

    largest_mass_fraction = safe_ratio(largest_fragment_mass, parent_mass)
    smallest_mass_fraction = safe_ratio(smallest_fragment_mass, parent_mass)

    total_charged_mass = sum(charged_masses) if charged_masses else 0.0
    total_neutral_mass = sum(neutral_masses) if neutral_masses else 0.0

    charged_mass_fraction = safe_ratio(total_charged_mass, parent_mass)
    neutral_mass_fraction = safe_ratio(total_neutral_mass, parent_mass)

    n_single_atom_fragments = sum(1 for f in ann if f["_n_atoms"] == 1)
    n_small_fragments_1_3 = sum(1 for f in ann if f["_n_atoms"] is not None and 1 <= f["_n_atoms"] <= 3)
    n_medium_fragments_4_10 = sum(1 for f in ann if f["_n_atoms"] is not None and 4 <= f["_n_atoms"] <= 10)
    n_large_fragments_gt_10 = sum(1 for f in ann if f["_n_atoms"] is not None and f["_n_atoms"] > 10)

    n_n_fragments = sum(1 for f in ann if f["_contains_n"])
    n_o_fragments = sum(1 for f in ann if f["_contains_o"])
    n_s_fragments = sum(1 for f in ann if f["_contains_s"])
    n_si_fragments = sum(1 for f in ann if f["_contains_si"])
    n_halogen_fragments = sum(1 for f in ann if f["_contains_halogen"])
    n_cl_fragments = sum(1 for f in ann if f["_contains_cl"])
    n_br_fragments = sum(1 for f in ann if f["_contains_br"])

    charged_n_fragments = sum(1 for f in ann if f["_contains_n"] and (f["_charge"] or 0) != 0)
    charged_halogen_fragments = sum(1 for f in ann if f["_contains_halogen"] and (f["_charge"] or 0) != 0)

    total_mass_n_fragments = sum(f["_exact_mass"] for f in ann if f["_contains_n"] and f["_exact_mass"] is not None)
    total_mass_halogen_fragments = sum(
        f["_exact_mass"] for f in ann if f["_contains_halogen"] and f["_exact_mass"] is not None
    )

    motif_formulas = [
        "H+",
        "C2H3N3",
        "C3H5N3",
        "HCl",
        "H2",
        "CH3+",
        "C2H5+",
    ]

    motif_features = {}
    for formula in motif_formulas:
        key = formula.lower().replace("+", "_plus").replace("-", "_minus")
        motif_features[f"contains_{key}"] = count_formula(fragment_rows, formula)
        motif_features[f"count_{key}"] = count_formula_occurrences(fragment_rows, formula)

    motif_features["contains_h_plus"] = count_formula(fragment_rows, "H+")
    motif_features["contains_c2h3n3"] = count_formula(fragment_rows, "C2H3N3")
    motif_features["contains_c3h5n3"] = count_formula(fragment_rows, "C3H5N3")
    motif_features["contains_hcl"] = count_formula(fragment_rows, "HCl")
    motif_features["contains_h2"] = count_formula(fragment_rows, "H2")
    motif_features["contains_ch3_plus"] = count_formula(fragment_rows, "CH3+")
    motif_features["contains_c2h5_plus"] = count_formula(fragment_rows, "C2H5+")

    timestep = input_meta.get("timestep")
    nstep = input_meta.get("nstep")
    charge = input_meta.get("charge")
    spinmult = input_meta.get("spinmult")
    method_from_input = input_meta.get("method")
    run_type = input_meta.get("run_type")
    energy_label_factor = input_meta.get("energy_label_factor")
    energy_temperature_K = input_meta.get("energy_temperature_K")
    energy_kcal_mol = input_meta.get("energy_kcal_mol")
    zpe_kcal_mol = input_meta.get("zpe_kcal_mol")
    dof = input_meta.get("dof")

    nframes = traj_meta.get("nframes")

    final_time_ps = input_meta.get("final_time_ps")
    if final_time_ps is None and timestep is not None and nframes is not None:
        final_time_ps = float(timestep) * int(nframes) / 1000.0

    fragment_count_per_100_atoms = safe_ratio(fragment_count * 100.0, parent_natoms)
    charged_fragment_fraction = safe_ratio(len(charged_frags), fragment_count)
    neutral_fragment_fraction = safe_ratio(len(neutral_frags), fragment_count)
    n_fragments_with_n_fraction = safe_ratio(n_n_fragments, fragment_count)
    n_fragments_with_halogen_fraction = safe_ratio(n_halogen_fragments, fragment_count)

    parent_halogen_fraction = safe_ratio(parent_halogens, parent_natoms)
    parent_hetero_fraction = safe_ratio(parent_hetero, parent_natoms)
    parent_h_to_c_ratio = safe_ratio(parent_h, parent_c)
    parent_n_to_c_ratio = safe_ratio(parent_n, parent_c)
    parent_o_to_c_ratio = safe_ratio(parent_o, parent_c)

    charged_sorted_by_mass = sorted(
        [f for f in charged_frags if f["_exact_mass"] is not None],
        key=lambda x: x["_exact_mass"],
        reverse=True,
    )
    largest_charged = charged_sorted_by_mass[0] if charged_sorted_by_mass else None

    feat = {
        "traj_uid": traj_meta["traj_uid"],
        "traj_code": traj_meta.get("traj_code"),
        "molecule": traj_meta.get("molecule"),
        "isomer": traj_meta.get("isomer"),
        "method_label": traj_meta.get("method_label"),
        "energy_label": traj_meta.get("energy_label"),
        "run_id": traj_meta.get("run_id"),

        "nframes": nframes,
        "natoms": traj_meta.get("natoms"),
        "parent_formula": parent_formula,
        "parent_mass": parent_mass,
        "parent_natoms": parent_natoms,
        "timestep": timestep,
        "nstep": nstep,
        "final_time_ps": final_time_ps,
        "charge": charge,
        "spinmult": spinmult,
        "method_from_input": method_from_input,
        "run_type": run_type,
        "energy_label_factor": energy_label_factor,
        "energy_temperature_K": energy_temperature_K,
        "energy_kcal_mol": energy_kcal_mol,
        "zpe_kcal_mol": zpe_kcal_mol,
        "dof": dof,

        **parent_counts,
        "parent_halogen_fraction": parent_halogen_fraction,
        "parent_hetero_fraction": parent_hetero_fraction,
        "parent_h_to_c_ratio": parent_h_to_c_ratio,
        "parent_n_to_c_ratio": parent_n_to_c_ratio,
        "parent_o_to_c_ratio": parent_o_to_c_ratio,

        "fragment_count": fragment_count,
        "fragment_count_per_100_atoms": fragment_count_per_100_atoms,
        "charged_fragment_count": len(charged_frags),
        "neutral_fragment_count": len(neutral_frags),
        "charged_fragment_fraction": charged_fragment_fraction,
        "neutral_fragment_fraction": neutral_fragment_fraction,

        "largest_fragment_formula": None if largest is None else largest["formula"],
        "largest_fragment_mass": largest_fragment_mass,
        "largest_fragment_n_atoms": largest_fragment_n_atoms,
        "largest_fragment_charge": largest_fragment_charge,
        "largest_fragment_mass_fraction": largest_mass_fraction,

        "smallest_fragment_formula": None if smallest is None else smallest["formula"],
        "smallest_fragment_mass": smallest_fragment_mass,
        "smallest_fragment_n_atoms": smallest_fragment_n_atoms,
        "smallest_fragment_charge": smallest_fragment_charge,
        "smallest_fragment_mass_fraction": smallest_mass_fraction,

        "largest_charged_fragment_formula": None if largest_charged is None else largest_charged["formula"],
        "largest_charged_fragment_mass": None if largest_charged is None else largest_charged["_exact_mass"],
        "largest_charged_fragment_n_atoms": None if largest_charged is None else largest_charged["_n_atoms"],
        "largest_charged_fragment_mass_fraction": None if largest_charged is None else safe_ratio(
            largest_charged["_exact_mass"], parent_mass
        ),

        "total_fragment_mass": total_fragment_mass,
        "mass_balance_error": mass_balance_error,
        "mass_balance_error_abs": mass_balance_error_abs,
        "mass_balance_error_rel": mass_balance_error_rel,

        "total_charged_mass": total_charged_mass,
        "total_neutral_mass": total_neutral_mass,
        "charged_mass_fraction": charged_mass_fraction,
        "neutral_mass_fraction": neutral_mass_fraction,

        "mean_fragment_mass": safe_mean(masses),
        "median_fragment_mass": safe_median(masses),
        "std_fragment_mass": safe_std(masses),
        "min_fragment_mass": safe_min(masses),
        "max_fragment_mass": safe_max(masses),
        "mass_range": None if not masses else (max(masses) - min(masses)),

        "mean_fragment_n_atoms": safe_mean(atom_sizes),
        "median_fragment_n_atoms": safe_median(atom_sizes),
        "std_fragment_n_atoms": safe_std(atom_sizes),
        "min_fragment_n_atoms": safe_min(atom_sizes),
        "max_fragment_n_atoms": safe_max(atom_sizes),

        "n_single_atom_fragments": n_single_atom_fragments,
        "n_small_fragments_1_3": n_small_fragments_1_3,
        "n_medium_fragments_4_10": n_medium_fragments_4_10,
        "n_large_fragments_gt_10": n_large_fragments_gt_10,

        "n_n_fragments": n_n_fragments,
        "n_o_fragments": n_o_fragments,
        "n_s_fragments": n_s_fragments,
        "n_si_fragments": n_si_fragments,
        "n_halogen_fragments": n_halogen_fragments,
        "n_cl_fragments": n_cl_fragments,
        "n_br_fragments": n_br_fragments,
        "charged_n_fragments": charged_n_fragments,
        "charged_halogen_fragments": charged_halogen_fragments,
        "total_mass_n_fragments": total_mass_n_fragments,
        "total_mass_halogen_fragments": total_mass_halogen_fragments,
        "n_fragments_with_n_fraction": n_fragments_with_n_fraction,
        "n_fragments_with_halogen_fraction": n_fragments_with_halogen_fraction,

        "has_any_charged_fragment": 1 if charged_frags else 0,
        "has_multiple_charged_fragments": 1 if len(charged_frags) >= 2 else 0,
        "largest_fragment_is_charged": 0 if largest is None else (1 if (largest["_charge"] or 0) != 0 else 0),
        "largest_fragment_contains_n": 0 if largest is None else (1 if largest["_contains_n"] else 0),
        "largest_fragment_contains_halogen": 0 if largest is None else (1 if largest["_contains_halogen"] else 0),

        **motif_features,
    }

    return feat


def aggregate_condition_feature_rows(rows):
    """
    Build one ML-friendly aggregated row per condition
    (molecule, isomer, method_label, energy_label).
    """
    if not rows:
        return None

    first = rows[0]
    out = {
        "molecule": first.get("molecule"),
        "isomer": first.get("isomer"),
        "method_label": first.get("method_label"),
        "energy_label": first.get("energy_label"),
        "n_trajectories": len(rows),
    }

    # Stable metadata copied from first row when present
    stable_keys = [
        "natoms",
        "parent_formula",
        "parent_mass",
        "parent_natoms",
        "charge",
        "spinmult",
        "method_from_input",
        "run_type",
        "energy_label_factor",
        "energy_temperature_K",
        "energy_kcal_mol",
        "zpe_kcal_mol",
        "dof",
    ]
    for k in stable_keys:
        out[k] = first.get(k)

    # Numeric trajectory-level fields to aggregate
    numeric_keys = [
        "fragment_count",
        "fragment_count_per_100_atoms",
        "final_time_ps",
        "largest_fragment_mass",
        "largest_fragment_mass_fraction",
        "largest_charged_fragment_mass",
        "largest_charged_fragment_mass_fraction",
        "charged_fragment_count",
        "neutral_fragment_count",
        "charged_fragment_fraction",
        "neutral_fragment_fraction",
        "total_fragment_mass",
        "mass_balance_error",
        "mass_balance_error_abs",
        "mass_balance_error_rel",
        "charged_mass_fraction",
        "neutral_mass_fraction",
        "mean_fragment_mass",
        "median_fragment_mass",
        "std_fragment_mass",
        "mean_fragment_n_atoms",
        "median_fragment_n_atoms",
        "std_fragment_n_atoms",
        "n_single_atom_fragments",
        "n_small_fragments_1_3",
        "n_medium_fragments_4_10",
        "n_large_fragments_gt_10",
        "n_n_fragments",
        "n_halogen_fragments",
        "n_fragments_with_n_fraction",
        "n_fragments_with_halogen_fraction",
    ]

    for key in numeric_keys:
        vals = [r.get(key) for r in rows if is_number(r.get(key))]
        out[f"{key}_mean"] = safe_mean(vals)
        out[f"{key}_median"] = safe_median(vals)
        out[f"{key}_std"] = safe_std(vals)
        out[f"{key}_min"] = safe_min(vals)
        out[f"{key}_max"] = safe_max(vals)

    # Fractions of boolean / motif presence
    binary_keys = sorted({
        k for r in rows for k, v in r.items()
        if k.startswith("contains_") or k.startswith("has_")
    })

    for key in binary_keys:
        vals = [r.get(key) for r in rows if r.get(key) in (0, 1)]
        out[f"frac_{key}"] = safe_mean(vals)

    # Reaction richness
    reaction_ids = [r.get("reaction_uid") for r in rows if r.get("reaction_uid")]
    out["n_unique_reactions"] = len(set(reaction_ids)) if reaction_ids else 0
    if reaction_ids:
        c = Counter(reaction_ids)
        dominant_uid, dominant_count = c.most_common(1)[0]
        out["dominant_reaction_uid"] = dominant_uid
        out["dominant_reaction_fraction"] = dominant_count / len(rows)
    else:
        out["dominant_reaction_uid"] = None
        out["dominant_reaction_fraction"] = None

    # Kinetics fields (copied from first non-null if present)
    kinetics_keys = [
        "kinetics_uid",
        "persist_frames",
        "window_mode",
        "n_trajectories_total",
        "n_events",
        "n_censored",
        "event_fraction",
        "common_window_ps",
        "k_regression_ps^-1",
        "half_life_regression_ps",
        "r2",
        "n_fit_points",
        "k_mle_ps^-1",
        "half_life_mle_ps",
        "k_mle_ci95_low",
        "k_mle_ci95_high",
    ]
    for k in kinetics_keys:
        value = None
        for r in rows:
            if r.get(k) is not None:
                value = r.get(k)
                break
        out[k] = value

    # Aggregate event-level kinetics if available per trajectory
    event_cols = ["event_occurred", "event_time_ps", "followup_time_ps", "max_fragment_count"]
    for k in event_cols:
        vals = [r.get(k) for r in rows if is_number(r.get(k))]
        if vals:
            out[f"{k}_mean"] = safe_mean(vals)
            out[f"{k}_median"] = safe_median(vals)
            out[f"{k}_std"] = safe_std(vals)
            out[f"{k}_min"] = safe_min(vals)
            out[f"{k}_max"] = safe_max(vals)

    return out