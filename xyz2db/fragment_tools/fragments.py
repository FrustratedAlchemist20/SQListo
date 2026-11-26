# xyz2db/fragment_tools/fragments.py

import math
from collections import Counter

from ..chemistry import (
    ATOM_MASSES,
    ATOMIC_RADII,
    BOND_FACTOR,
    FORMULA_ORDER,
    VALENCE_ELECTRONS,
)


def distance(x1, y1, z1, x2, y2, z2):
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2)


def build_formula(symbols):
    counts = Counter(symbols)
    formula = ""

    for atom in FORMULA_ORDER:
        if atom in counts and counts[atom] > 0:
            formula += atom
            if counts[atom] > 1:
                formula += str(counts[atom])

    # Add any remaining elements not listed in FORMULA_ORDER
    for atom in sorted(counts):
        if atom not in FORMULA_ORDER and counts[atom] > 0:
            formula += atom
            if counts[atom] > 1:
                formula += str(counts[atom])

    total_electrons = 0
    for atom, n in counts.items():
        total_electrons += VALENCE_ELECTRONS.get(atom, 0) * n

    charge_guess = 1 if total_electrons % 2 != 0 else 0
    if charge_guess == 1:
        formula += "+"

    return formula, charge_guess


def compute_fragment_mass(symbols):
    return sum(ATOM_MASSES[s] for s in symbols)


def build_connectivity(atoms):
    """
    atoms: list of tuples [(sym, x, y, z), ...]
    returns adjacency dict {i: [neighbors]}
    """
    num_atoms = len(atoms)
    adjacency = {i: [i] for i in range(num_atoms)}

    for i in range(num_atoms):
        sym_i, xi, yi, zi = atoms[i]
        for j in range(i + 1, num_atoms):
            sym_j, xj, yj, zj = atoms[j]

            dist = distance(xi, yi, zi, xj, yj, zj)
            cutoff = (ATOMIC_RADII[sym_i] + ATOMIC_RADII[sym_j]) * BOND_FACTOR

            if dist < cutoff:
                adjacency[i].append(j)
                adjacency[j].append(i)

    return adjacency


def connected_fragments(atoms):
    """
    atoms: list of tuples [(sym, x, y, z), ...]
    returns list of fragments, each fragment being a list of atom indices
    """
    adjacency = build_connectivity(atoms)
    num_atoms = len(atoms)

    visited = set()
    fragments = []

    for i in range(num_atoms):
        if i in visited:
            continue

        fragment = [i]
        visited.add(i)

        j = 0
        while j < len(fragment):
            atom_index = fragment[j]
            for neighbor_index in adjacency[atom_index]:
                if neighbor_index not in visited:
                    fragment.append(neighbor_index)
                    visited.add(neighbor_index)
            j += 1

        fragments.append(fragment)

    return fragments


def analyze_last_frame_atoms(atoms):
    """
    atoms: list of tuples [(sym, x, y, z), ...] corresponding to ONE frame
    returns a list of fragment dicts
    """
    fragments_idx = connected_fragments(atoms)
    results = []

    for frag_i, fragment in enumerate(fragments_idx, start=1):
        frag_symbols = [atoms[idx][0] for idx in fragment]
        exact_mass = compute_fragment_mass(frag_symbols)
        formula, charge_guess = build_formula(frag_symbols)

        results.append(
            {
                "fragment_index": frag_i,
                "atom_indices": fragment,
                "n_atoms": len(fragment),
                "formula": formula,
                "exact_mass": exact_mass,
                "charge_guess": charge_guess,
            }
        )

    results.sort(key=lambda x: x["exact_mass"], reverse=True)
    for i, frag in enumerate(results, start=1):
        frag["fragment_index"] = i

    return results

# These functions are extra functions for Kinetics Tools (RRKM analysis)

def count_connected_fragments(atoms):
    return len(connected_fragments(atoms))


def is_precursor_intact(atoms):
    return count_connected_fragments(atoms) == 1


def fragment_sizes(atoms):
    frags = connected_fragments(atoms)
    return sorted((len(f) for f in frags), reverse=True)