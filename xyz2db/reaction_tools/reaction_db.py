# xyz2db/reaction_tools/reaction_db.py

import csv
import sqlite3
from collections import defaultdict

from .reactions import aggregate_reactions, merge_two_methods


def fetch_trajectory_fragments(
    db_path: str,
    methods=None,
    molecule=None,
    isomer=None,
    energy_label=None,
):
    """
    Read trajectory + fragment data from DB with optional filters.

    methods:
      None -> all methods
      ["uB3LYP"] -> one method
      ["uB3LYP", "PM6"] -> two methods
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    query = """
        SELECT
            t.traj_uid,
            t.traj_code,
            t.molecule,
            t.isomer,
            t.method_label,
            t.energy_label,
            t.original_run_dir,
            f.fragment_index,
            f.formula,
            f.exact_mass,
            f.charge_guess,
            f.n_atoms
        FROM trajectories t
        JOIN fragment_analysis fa ON t.traj_uid = fa.traj_uid
        JOIN fragments f ON t.traj_uid = f.traj_uid
    """

    conditions = []
    params = []

    if methods is not None:
        placeholders = ",".join("?" for _ in methods)
        conditions.append(f"t.method_label IN ({placeholders})")
        params.extend(methods)

    if molecule is not None:
        conditions.append("t.molecule = ?")
        params.append(molecule)

    if isomer is not None:
        conditions.append("t.isomer = ?")
        params.append(isomer)

    if energy_label is not None:
        conditions.append("t.energy_label = ?")
        params.append(energy_label)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += """
        ORDER BY t.method_label, t.run_id, t.created_at, t.traj_uid, f.fragment_index
    """

    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    conn.close()

    grouped = {}
    for (
        traj_uid,
        traj_code,
        molecule,
        isomer,
        method_label,
        energy_label,
        original_run_dir,
        fragment_index,
        formula,
        exact_mass,
        charge_guess,
        n_atoms,
    ) in rows:
        if traj_uid not in grouped:
            grouped[traj_uid] = {
                "traj_uid": traj_uid,
                "traj_code": traj_code,
                "molecule": molecule,
                "isomer": isomer,
                "method_label": method_label,
                "energy_label": energy_label,
                "original_run_dir": original_run_dir,
                "fragments": [],
            }
        grouped[traj_uid]["fragments"].append(
            {
                "fragment_index": fragment_index,
                "formula": formula,
                "exact_mass": exact_mass,
                "charge_guess": charge_guess,
                "n_atoms": n_atoms,
            }
        )

    return list(grouped.values())

def build_reaction_summary(db_path: str, methods=None, molecule=None, isomer=None, energy_label=None):
    trajs = fetch_trajectory_fragments(
        db_path,
        methods=methods,
        molecule=molecule,
        isomer=isomer,
        energy_label=energy_label,
    )
    return aggregate_reactions(trajs)

def print_reaction_table_single(method_name, data):
    if not data:
        print(f"No reactions found for method: {method_name}")
        return

    max_frags = max(len(item["fragments"]) for item in data)

    header = ["Reaction", "ReactionUID", "Molecule", "Energy", f"Freq_{method_name}"]

    for i in range(1, max_frags + 1):
        header.append(f"Frag{i}")

    #widths = [10, 18, 12, 12, 14] + [24] * max_frags
    widths = [10, 18, 12, 12, 14] + [40] * max_frags

    def fmt_row(values):
        return " | ".join(str(v).ljust(w) for v, w in zip(values, widths))

    print(fmt_row(header))
    print("-" * (sum(widths) + 3 * (len(widths) - 1)))

    for i, item in enumerate(data, start=1):
        molecule_txt = ",".join(item.get("molecule_labels", [])) if item.get("molecule_labels") else "-"
        energy_txt = ",".join(item.get("energy_labels", [])) if item.get("energy_labels") else "-"

        row = [i, item["reaction_uid"], molecule_txt, energy_txt, f"{item['frequency_pct']:.2f}"]

        for frag in item["fragments"]:
            row.append(f"{frag['formula']} ({frag['exact_mass']:.6f})")
        while len(row) < len(header):
            row.append("-")
        print(fmt_row(row))


def print_reaction_table_two_methods(merged_rows):
    if not merged_rows:
        print("No reactions found for the selected methods.")
        return

    method_a_name = merged_rows[0]["method_a_name"]
    method_b_name = merged_rows[0]["method_b_name"]

    max_frags = max(len(item["fragments"]) for item in merged_rows)

    header = ["Reaction", "ReactionUID", "Molecule", "Energy", f"Freq_{method_a_name}", f"Freq_{method_b_name}"]

    for i in range(1, max_frags + 1):
        header.append(f"Frag{i}")

    widths = [10, 18, 12, 12, 16, 16] + [24] * max_frags

    def fmt_row(values):
        return " | ".join(str(v).ljust(w) for v, w in zip(values, widths))

    print(fmt_row(header))
    print("-" * (sum(widths) + 3 * (len(widths) - 1)))

    for row_data in merged_rows:
        molecule_txt = ",".join(row_data.get("molecule_labels", [])) if row_data.get("molecule_labels") else "-"
        energy_txt = ",".join(row_data.get("energy_labels", [])) if row_data.get("energy_labels") else "-"

        row = [
            row_data["reaction_index"],
            row_data["reaction_uid"],
            molecule_txt,
            energy_txt,
            "-" if row_data["freq_a"] is None else f"{row_data['freq_a']:.2f}",
            "-" if row_data["freq_b"] is None else f"{row_data['freq_b']:.2f}",
        ]
        for frag in row_data["fragments"]:
            row.append(f"{frag['formula']} ({frag['exact_mass']:.6f})")
        while len(row) < len(header):
            row.append("-")
        print(fmt_row(row))


def export_reactions_csv_single(method_name, data, output_csv):
    max_frags = max((len(item["fragments"]) for item in data), default=0)


    header = ["Reaction", "ReactionUID", "Molecule", "Energy", f"Freq_{method_name}"]
    
    for i in range(1, max_frags + 1):
        header.extend([f"Frag{i}", f"Mass{i}"])

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)

        for i, item in enumerate(data, start=1):

            molecule_txt = ",".join(item.get("molecule_labels", [])) if item.get("molecule_labels") else ""
            energy_txt = ",".join(item.get("energy_labels", [])) if item.get("energy_labels") else ""

            row = [i, item["reaction_uid"], molecule_txt, energy_txt, f"{item['frequency_pct']:.6f}"]

            for frag in item["fragments"]:
                row.extend([frag["formula"], f"{frag['exact_mass']:.6f}"])
            while len(row) < len(header):
                row.append("")
            writer.writerow(row)


def export_reactions_csv_two_methods(merged_rows, output_csv):
    if not merged_rows:
        return

    method_a_name = merged_rows[0]["method_a_name"]
    method_b_name = merged_rows[0]["method_b_name"]
    max_frags = max((len(item["fragments"]) for item in merged_rows), default=0)

    header = ["Reaction", "ReactionUID", "Molecule", "Energy", f"Freq_{method_a_name}", f"Freq_{method_b_name}"]

    for i in range(1, max_frags + 1):
        header.extend([f"Frag{i}", f"Mass{i}"])

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)

        for row_data in merged_rows:
            molecule_txt = ",".join(row_data.get("molecule_labels", [])) if row_data.get("molecule_labels") else ""
            energy_txt = ",".join(row_data.get("energy_labels", [])) if row_data.get("energy_labels") else ""

            row = [
                row_data["reaction_index"],
                row_data["reaction_uid"],
                molecule_txt,
                energy_txt,
                "" if row_data["freq_a"] is None else f"{row_data['freq_a']:.6f}",
                "" if row_data["freq_b"] is None else f"{row_data['freq_b']:.6f}",
            ]

            for frag in row_data["fragments"]:
                row.extend([frag["formula"], f"{frag['exact_mass']:.6f}"])
            while len(row) < len(header):
                row.append("")
            writer.writerow(row)


def latex_escape_formula(formula: str) -> str:
    """
    Keeps the formula mostly as text.
    Later you can improve this to convert into subscripts if desired.
    """
    return formula.replace("_", r"\_")


def export_reactions_latex_single(method_name, data, output_tex, caption="Reaction frequencies", label="tab:reactions"):
    max_frags = max((len(item["fragments"]) for item in data), default=0)
    ncols = 2 + max_frags

    with open(output_tex, "w", encoding="utf-8") as f:
        f.write(r"\begin{longtable}{@{\extracolsep{\fill}}" + " ".join(["c"] * ncols) + r"@{}}" + "\n")
        f.write(rf"\caption{{{caption} — method {method_name}}} \label{{{label}}} \\" + "\n")
        f.write(r"\toprule" + "\n")

        header = [r"\text{Nº Reaction}", rf"$\mathrm{{Freq}}_{{\text{{{method_name}}}}}$"]
        for i in range(1, max_frags + 1):
            header.append(rf"\text{{Frag}}\textsubscript{{{i}}}")

        f.write(" & ".join(header) + r" \\" + "\n")
        f.write(r"\midrule" + "\n")
        f.write(r"\endfirsthead" + "\n")

        f.write(rf"\caption[]{{{caption} — method {method_name}}} \\" + "\n")
        f.write(r"\toprule" + "\n")
        f.write(" & ".join(header) + r" \\" + "\n")
        f.write(r"\midrule" + "\n")
        f.write(r"\endhead" + "\n")
        f.write(r"\midrule" + "\n")
        f.write(rf"\multicolumn{{{ncols}}}{{r}}{{Continued on next page}} \\" + "\n")
        f.write(r"\midrule" + "\n")
        f.write(r"\endfoot" + "\n")
        f.write(r"\bottomrule" + "\n")
        f.write(r"\endlastfoot" + "\n")

        for i, item in enumerate(data, start=1):
            row = [str(i), f"{item['frequency_pct']:.2f}"]
            for frag in item["fragments"]:
                row.append(latex_escape_formula(frag["formula"]))
            while len(row) < ncols:
                row.append("-")
            f.write(" & ".join(row) + r" \\" + "\n")

        f.write(r"\end{longtable}" + "\n")


def export_reactions_latex_two_methods(
    merged_rows,
    output_tex,
    caption="Main unimolecular fragmentation reactions",
    label="tab:reactions_compare",
):
    if not merged_rows:
        return

    method_a_name = merged_rows[0]["method_a_name"]
    method_b_name = merged_rows[0]["method_b_name"]
    max_frags = max((len(item["fragments"]) for item in merged_rows), default=0)
    ncols = 3 + max_frags

    with open(output_tex, "w", encoding="utf-8") as f:
        f.write(r"\begin{longtable}{@{\extracolsep{\fill}}" + " ".join(["c"] * ncols) + r"@{}}" + "\n")
        f.write(rf"\caption{{{caption} — methods {method_a_name}/{method_b_name}}} \label{{{label}}} \\" + "\n")
        f.write(r"\toprule" + "\n")

        header = [
            r"\text{Nº Reaction}",
            rf"$\mathrm{{Freq}}_{{\text{{{method_a_name}}}}}$",
            rf"$\mathrm{{Freq}}_{{\text{{{method_b_name}}}}}$",
        ]
        for i in range(1, max_frags + 1):
            header.append(rf"\text{{Frag}}\textsubscript{{{i}}}")

        f.write(" & ".join(header) + r" \\" + "\n")
        f.write(r"\midrule" + "\n")
        f.write(r"\endfirsthead" + "\n")

        f.write(rf"\caption[]{{{caption} — methods {method_a_name}/{method_b_name}}} \\" + "\n")
        f.write(r"\toprule" + "\n")
        f.write(" & ".join(header) + r" \\" + "\n")
        f.write(r"\midrule" + "\n")
        f.write(r"\endhead" + "\n")
        f.write(r"\midrule" + "\n")
        f.write(rf"\multicolumn{{{ncols}}}{{r}}{{Continued on next page}} \\" + "\n")
        f.write(r"\midrule" + "\n")
        f.write(r"\endfoot" + "\n")
        f.write(r"\bottomrule" + "\n")
        f.write(r"\endlastfoot" + "\n")

        for row_data in merged_rows:
            row = [
                str(row_data["reaction_index"]),
                "-" if row_data["freq_a"] is None else f"{row_data['freq_a']:.2f}",
                "-" if row_data["freq_b"] is None else f"{row_data['freq_b']:.2f}",
            ]
            for frag in row_data["fragments"]:
                row.append(latex_escape_formula(frag["formula"]))
            while len(row) < ncols:
                row.append("-")
            f.write(" & ".join(row) + r" \\" + "\n")

        f.write(r"\end{longtable}" + "\n")


def reaction_list(
    db_path: str,
    methods=None,
    molecule=None,
    isomer=None,
    energy_label=None,
    output_csv=None,
    output_tex=None,
):
    """
    methods:
      None -> all methods in DB (only valid if there is exactly one method)
      [method1] -> single method
      [method1, method2] -> compare two methods
    """
    summary = build_reaction_summary(
        db_path,
        methods=methods,
        molecule=molecule,
        isomer=isomer,
        energy_label=energy_label,
    )

    available_methods = list(summary.keys())
    if not available_methods:
        print("No fragment-based reactions found in the database.")
        print("Run analyze-fragments first.")
        return

    if methods is None:
        if len(available_methods) == 1:
            method_name = available_methods[0]
            data = summary[method_name]
            print_reaction_table_single(method_name, data)
            if output_csv:
                export_reactions_csv_single(method_name, data, output_csv)
                print(f"CSV written to: {output_csv}")
            if output_tex:
                export_reactions_latex_single(method_name, data, output_tex)
                print(f"LaTeX written to: {output_tex}")
            return
        else:
            raise ValueError(
                "The database contains more than one method. Use --method or --methods METHOD1 METHOD2."
            )

    if len(methods) == 1:
        method_name = methods[0]
        data = summary.get(method_name, [])
        print_reaction_table_single(method_name, data)
        if output_csv:
            export_reactions_csv_single(method_name, data, output_csv)
            print(f"CSV written to: {output_csv}")
        if output_tex:
            export_reactions_latex_single(method_name, data, output_tex)
            print(f"LaTeX written to: {output_tex}")
        return

    if len(methods) == 2:
        method_a_name, method_b_name = methods
        data_a = summary.get(method_a_name, [])
        data_b = summary.get(method_b_name, [])
        merged = merge_two_methods(method_a_name, data_a, method_b_name, data_b)
        print_reaction_table_two_methods(merged)
        if output_csv:
            export_reactions_csv_two_methods(merged, output_csv)
            print(f"CSV written to: {output_csv}")
        if output_tex:
            export_reactions_latex_two_methods(merged, output_tex)
            print(f"LaTeX written to: {output_tex}")
        return

    raise ValueError("You can request at most two methods.")