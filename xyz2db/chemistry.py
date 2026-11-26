# xyz2db/chemistry.py

# Chemistry parameters and utilities
#This is a basic dictionary to each element and atomic number 

# xyz2db/chemistry.py

SYMBOL_TO_Z = {
    "H": 1, "He": 2,
    "Li": 3, "Be": 4, "B": 5, "C": 6, "N": 7, "O": 8, "F": 9, "Ne": 10,
    "Na": 11, "Mg": 12, "Al": 13, "Si": 14, "P": 15, "S": 16, "Cl": 17, "Ar": 18,
    "K": 19, "Ca": 20, "Sc": 21, "Ti": 22, "V": 23, "Cr": 24, "Mn": 25, "Fe": 26,
    "Co": 27, "Ni": 28, "Cu": 29, "Zn": 30, "Ga": 31, "Ge": 32, "As": 33, "Se": 34,
    "Br": 35, "Kr": 36, "Rb": 37, "Sr": 38, "Y": 39, "Zr": 40, "Nb": 41, "Mo": 42,
    "Tc": 43, "Ru": 44, "Rh": 45, "Pd": 46, "Ag": 47, "Cd": 48, "In": 49, "Sn": 50,
    "Sb": 51, "Te": 52, "I": 53, "Xe": 54,
}

Z_TO_SYMBOL = {v: k for k, v in SYMBOL_TO_Z.items()}

ATOM_MASSES = {
    "H": 1.00782,
    "C": 12.00000,
    "N": 14.00307,
    "O": 15.99491,
    "Cl": 34.96885,
    "S": 31.97207,
    "Si": 27.97692,
    "Br": 78.91833,
    "He": 4.002,
}

VALENCE_ELECTRONS = {
    "H": 1,
    "C": 4,
    "N": 5,
    "O": 6,
    "Cl": 7,
    "S": 6,
    "Si": 4,
    "Br": 7,
    "He": 2,
}

VDW_RADII = {
    "H": 1.20,
    "C": 1.70,
    "N": 1.55,
    "O": 1.52,
    "Cl": 1.75,
    "S": 1.80,
    "Si": 2.10,
    "Br": 1.85,
    "He": 1.40,
}

ATOMIC_RADII = {
    "H": 0.372,
    "C": 0.781,
    "N": 0.807,
    "O": 0.715,
    "Cl": 0.99,
    "S": 0.99,
    "Si": 1.12,
    "Br": 1.15,
    "He": 0.31,
}

FORMULA_ORDER = ["C", "H", "Cl", "Br", "N", "O", "S", "Si"]

BOND_FACTOR = 1.264