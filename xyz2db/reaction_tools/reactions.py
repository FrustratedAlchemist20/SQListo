# xyz2db/reaction_tools/reactions.py


from collections import Counter, defaultdict
import hashlib
from ..ids import CODE_MAP

def molecule_to_abbrev(name):
    if name is None:
        return "UNK"
    return CODE_MAP["molecule"].get(name, name)

def make_reaction_uid(reaction_key):
    """
    Build a stable unique identifier from the normalized reaction key.
    The same set of final fragments will always generate the same UID.
    """
    raw = repr(reaction_key).encode("utf-8")
    short = hashlib.sha256(raw).hexdigest()[:12]
    return f"rxn_{short}"

def normalize_reaction_fragments(fragment_rows):
    """
    fragment_rows: list of dicts with keys:
        formula, exact_mass, charge_guess, n_atoms

    Returns a normalized list of fragments sorted in a stable way.
    Sorting rule:
      1) exact_mass descending
      2) formula ascending
    """
    normalized = []
    for frag in fragment_rows:
        normalized.append(
            {
                "formula": frag["formula"],
                "exact_mass": float(frag["exact_mass"]),
                "charge_guess": frag["charge_guess"],
                "n_atoms": frag["n_atoms"],
            }
        )

    normalized.sort(key=lambda x: (-x["exact_mass"], x["formula"]))
    return normalized


def make_reaction_key(fragment_rows):
    """
    Build a hashable reaction key from normalized fragments.
    """
    normalized = normalize_reaction_fragments(fragment_rows)
    key = tuple((frag["formula"], round(frag["exact_mass"], 6)) for frag in normalized)
    return key


def aggregate_reactions(trajectory_fragments):
    """
    trajectory_fragments: list of dicts like:
      {
        "traj_uid": ...,
        "traj_code": ...,
        "method_label": ...,
        "original_run_dir": ...,
        "fragments": [
            {"formula": ..., "exact_mass": ..., "charge_guess": ..., "n_atoms": ...},
            ...
        ]
      }

    Returns aggregated reactions by method:
      {
        method_label: [
            {
                "reaction_key": ...,
                "count": ...,
                "frequency_pct": ...,
                "fragments": [...],
                "members": [...],
            },
            ...
        ]
      }
    """
    grouped_by_method = defaultdict(list)

    for item in trajectory_fragments:
        method_label = item["method_label"] if item["method_label"] is not None else "UNKNOWN"
        grouped_by_method[method_label].append(item)

    result = {}

    for method_label, trajs in grouped_by_method.items():
        total = len(trajs)
        counter = Counter()
        representative = {}
        members = defaultdict(list)

        for traj in trajs:
            key = make_reaction_key(traj["fragments"])
            counter[key] += 1
            members[key].append(
                {
                    "traj_uid": traj["traj_uid"],
                    "traj_code": traj["traj_code"],
                    "original_run_dir": traj["original_run_dir"],
                    "molecule": traj.get("molecule"),
                    "energy_label": traj.get("energy_label"),
                }
            )
            if key not in representative:
                representative[key] = normalize_reaction_fragments(traj["fragments"])
        
        aggregated = []
        for key, count in counter.items():
            freq = 100.0 * count / total if total > 0 else 0.0

            molecule_labels = sorted(
                {
                    molecule_to_abbrev(m["molecule"])
                    for m in members[key]
                    if m.get("molecule") is not None
                }
            )

            energy_labels = sorted(
                {
                    m["energy_label"]
                    for m in members[key]
                    if m.get("energy_label") is not None
                }
            )

            aggregated.append(
                {
                    "reaction_uid": make_reaction_uid(key),
                    "reaction_key": key,
                    "count": count,
                    "frequency_pct": freq,
                    "fragments": representative[key],
                    "members": members[key],
                    "molecule_labels": molecule_labels,
                    "energy_labels": energy_labels,
                }
            )
        
        aggregated.sort(key=lambda x: (-x["frequency_pct"], -x["count"], len(x["fragments"])))
        result[method_label] = aggregated

    return result


def merge_two_methods(method_a_name, method_a_data, method_b_name, method_b_data):
    """
    Merge reactions from two methods into a comparison table.
    """
    map_a = {item["reaction_key"]: item for item in method_a_data}
    map_b = {item["reaction_key"]: item for item in method_b_data}

    all_keys = set(map_a) | set(map_b)
    merged = []

    for key in all_keys:
        item_a = map_a.get(key)
        item_b = map_b.get(key)

        fragments = item_a["fragments"] if item_a is not None else item_b["fragments"]
        source_members = []
        if item_a is not None:
            source_members.extend(item_a["members"])
        if item_b is not None:
            source_members.extend(item_b["members"])

        molecule_labels = sorted(
            {
                molecule_to_abbrev(m["molecule"])
                for m in source_members
                if m.get("molecule") is not None
            }
        )

        energy_labels = sorted(
            {
                m["energy_label"]
                for m in source_members
                if m.get("energy_label") is not None
            }
        )

        merged.append(
            {
                "reaction_uid": make_reaction_uid(key),
                "reaction_key": key,
                "fragments": fragments,
                "freq_a": item_a["frequency_pct"] if item_a else None,
                "freq_b": item_b["frequency_pct"] if item_b else None,
                "count_a": item_a["count"] if item_a else 0,
                "count_b": item_b["count"] if item_b else 0,
                "molecule_labels": molecule_labels,
                "energy_labels": energy_labels,
            }
        )

    merged.sort(
        key=lambda x: (
            -max(x["freq_a"] or 0.0, x["freq_b"] or 0.0),
            -(x["count_a"] + x["count_b"]),
            len(x["fragments"]),
        )
    )

    for i, row in enumerate(merged, start=1):
        row["reaction_index"] = i
        row["method_a_name"] = method_a_name
        row["method_b_name"] = method_b_name

    return merged