import argparse

from .config import DEFAULT_BLOCK_SIZE
from .db import (
    list_trajectories,
    show_trajectory,
    summary_db,
)

from .venus_tools.venus_store import store_all_venus_from_sims, store_one_venus_output
from .restore import (
    restore_all_from_db,
    restore_xyz_from_db,
    restore_single_run_from_db,
    show_input_from_db,
    restore_input_for_trajectory,
)

from .storage import store_xyz_in_db
from .batch import store_all_from_runs
from .fragment_tools.fragment_db import (
    analyze_and_store_fragments_for_all,
    analyze_and_store_fragments_for_traj,
    fragment_list,
)
from .reaction_tools.reaction_db import reaction_list
from .reaction_tools.reaction_store import (
    store_reactions,
    reaction_show,
    fragment_search,
)

from .merge_tools.merge_db import merge_databases
from .spectra_tools.spectra_db import spectrum_list

from .kinetics_tools.kinetics_db import compute_and_store_global_kinetics

from .feature_tools.feature_db import (
    extract_features_all,
    extract_features_one,
    feature_export,
    feature_export_all,
    feature_list,
)

def build_parser():
    parser = argparse.ArgumentParser(
        description="Store and restore multi-frame XYZ trajectories in a compressed SQLite database."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -------------------------
    # store TERACHEM coors.xyz
    # -------------------------
    p_store = sub.add_parser("store", help="Store a multi-frame XYZ trajectory in the database.")
    p_store.add_argument("xyz_file", help="Input multi-frame XYZ file")
    p_store.add_argument("db_file", help="SQLite database file or 'auto'")
    p_store.add_argument(
        "--block-size",
        type=int,
        default=DEFAULT_BLOCK_SIZE,
        help=f"Number of frames per compressed block (default: {DEFAULT_BLOCK_SIZE})",
    )
    p_store.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite an existing entry with the same XYZ content",
    )
    p_store.add_argument("--input-file", default=None, help="Path to md.in input file")
    p_store.add_argument("--molecule", default=None, help="Molecule name, e.g. Triticonazole")
    p_store.add_argument("--isomer", default=None, help="Isomer label, e.g. E, Z, cis, trans")
    p_store.add_argument("--method", default=None, help="Method label, e.g. PM6, uB3LYP")
    p_store.add_argument("--energy-label", default=None, help="Energy label, e.g. ZPEx3")
    p_store.add_argument("--run-id", type=int, default=None, help="Trajectory/run number")

    # -------------------------
    # store-all TERACHEM runXXX
    # -------------------------
    p_store_all = sub.add_parser(
        "store-all",
        help="Scan run_XXX folders and store all detected XYZ trajectories."
    )
    p_store_all.add_argument("root_dir", help="Root directory containing run_XXX folders")
    p_store_all.add_argument("db_file", help="SQLite database file or 'auto'")
    p_store_all.add_argument("--input-file", default=None, help="Path to md.in input file")
    p_store_all.add_argument("--molecule", default=None, help="Molecule name, e.g. Triticonazole")
    p_store_all.add_argument("--isomer", default=None, help="Isomer label, e.g. E, Z, cis, trans")
    p_store_all.add_argument("--method", default=None, help="Method label, e.g. PM6, uB3LYP")
    p_store_all.add_argument("--energy-label", default=None, help="Energy label, e.g. ZPEx3")
    p_store_all.add_argument(
        "--block-size",
        type=int,
        default=DEFAULT_BLOCK_SIZE,
        help=f"Number of frames per compressed block (default: {DEFAULT_BLOCK_SIZE})",
    )
    p_store_all.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite an existing entry with the same XYZ content",
    )
    p_store_all.add_argument(
        "--xyz-name",
        default="coors.xyz",
        help="Target XYZ filename to search for",
    )

    # -------------------------
    # store-venus-one - VENUS SIMXXX
    # -------------------------
    p_store_venus_one = sub.add_parser(
        "store-venus-one",
        help="Store trajectories from a single VENUS .out file into the database."
    )
    p_store_venus_one.add_argument(
        "out_file",
        help="Path to one VENUS .out file inside a SIMXXX folder"
    )
    p_store_venus_one.add_argument(
        "db_file",
        help="SQLite database file or 'auto'"
    )
    p_store_venus_one.add_argument(
        "--input-file",
        required=True,
        help="Path to the VENUS .inp input file"
    )
    p_store_venus_one.add_argument(
        "--molecule",
        default=None,
        help="Molecule name"
    )
    p_store_venus_one.add_argument(
        "--isomer",
        default=None,
        help="Isomer label"
    )
    p_store_venus_one.add_argument(
        "--method",
        default=None,
        help="Override method label parsed from the input file"
    )
    p_store_venus_one.add_argument(
        "--energy-label",
        default=None,
        help="Override energy label parsed from the input file"
    )
    p_store_venus_one.add_argument(
        "--block-size",
        type=int,
        default=DEFAULT_BLOCK_SIZE,
        help=f"Number of frames per compressed block (default: {DEFAULT_BLOCK_SIZE})"
    )

    # -------------------------
    # store-all - VENUS SIMXXX
    # -------------------------
    p_store_venus = sub.add_parser(
        "store-venus",
        help="Store VENUS trajectories directly from SIMXXX outputs into the database."
    )
    p_store_venus.add_argument(
        "root_dir",
        help="Root directory containing the VENUS input file and SIMXXX folders"
    )
    p_store_venus.add_argument(
        "db_file",
        help="SQLite database file or 'auto'"
    )
    p_store_venus.add_argument(
        "--input-file",
        default=None,
        help="Path to the VENUS .inp input file (optional if there is a unique .inp in root_dir)"
    )
    p_store_venus.add_argument(
        "--molecule",
        default=None,
        help="Molecule name"
    )
    p_store_venus.add_argument(
        "--isomer",
        default=None,
        help="Isomer label"
    )
    p_store_venus.add_argument(
        "--method",
        default=None,
        help="Override method label parsed from the input file"
    )
    p_store_venus.add_argument(
        "--energy-label",
        default=None,
        help="Override energy label parsed from the input file"
    )
    p_store_venus.add_argument(
        "--block-size",
        type=int,
        default=DEFAULT_BLOCK_SIZE,
        help=f"Number of frames per compressed block (default: {DEFAULT_BLOCK_SIZE})"
    )

    # -------------------------
    # restore
    # -------------------------
    p_restore = sub.add_parser("restore", help="Restore one trajectory into its original run folder.")
    p_restore.add_argument("db_file", help="SQLite database file")
    p_restore.add_argument("traj_uid", help="Unique trajectory identifier")

    # -------------------------
    # restore-all
    # -------------------------
    p_restore_all = sub.add_parser("restore-all", help="Restore all trajectories from the database.")
    p_restore_all.add_argument("db_file", help="SQLite database file")
    p_restore_all.add_argument("output_dir", help="Output directory")
    p_restore_all.add_argument("--molecule", default=None, help="Filter by molecule name")
    p_restore_all.add_argument("--isomer", default=None, help="Filter by isomer label")
    p_restore_all.add_argument("--method", default=None, help="Filter by method_label")
    p_restore_all.add_argument("--energy-label", default=None, help="Filter by energy label")

    # -------------------------
    # list / summary / show / show-input
    # -------------------------
    p_list = sub.add_parser("list", help="List all stored trajectories.")
    p_list.add_argument("db_file", help="SQLite database file")
    p_list.add_argument("--molecule", default=None, help="Filter by molecule name")
    p_list.add_argument("--isomer", default=None, help="Filter by isomer label")
    p_list.add_argument("--method", default=None, help="Filter by method_label")
    p_list.add_argument("--energy-label", default=None, help="Filter by energy label")

    p_summary = sub.add_parser("summary", help="Show a global database summary.")
    p_summary.add_argument("db_file", help="SQLite database file")
    p_summary.add_argument("--molecule", default=None, help="Filter by molecule name")
    p_summary.add_argument("--isomer", default=None, help="Filter by isomer label")
    p_summary.add_argument("--method", default=None, help="Filter by method_label")
    p_summary.add_argument("--energy-label", default=None, help="Filter by energy label")

    p_show = sub.add_parser("show", help="Show detailed information for one trajectory.")
    p_show.add_argument("db_file", help="SQLite database file")
    p_show.add_argument("traj_uid", help="Unique trajectory identifier")

    p_show_input = sub.add_parser(
        "show-input",
        help="Show the stored input associated with one trajectory, including derived energy fields."
    )
    p_show_input.add_argument("db_file", help="SQLite database file")
    p_show_input.add_argument("traj_uid", help="Unique trajectory identifier")

    p_restore_input = sub.add_parser(
        "restore-input",
        help="Restore only the stored input file associated with one trajectory."
    )
    p_restore_input.add_argument("db_file", help="SQLite database file")
    p_restore_input.add_argument("traj_uid", help="Unique trajectory identifier")
    p_restore_input.add_argument(
       "--output",
       default=None,
       help="Optional output path. If omitted, the original stored input filename is used."
    )

    # -------------------------
    # fragment commands
    # -------------------------
    p_analyze_fragments = sub.add_parser(
        "analyze-fragments",
        help="Analyze last-frame fragments for all trajectories in the database."
    )
    p_analyze_fragments.add_argument("db_file", help="SQLite database file")

    p_analyze_fragments_one = sub.add_parser(
        "analyze-fragments-one",
        help="Analyze last-frame fragments for one trajectory."
    )
    p_analyze_fragments_one.add_argument("db_file", help="SQLite database file")
    p_analyze_fragments_one.add_argument("traj_uid", help="Unique trajectory identifier")

    p_fragment_list = sub.add_parser(
        "fragment-list",
        help="List fragment results stored in the database."
    )
    p_fragment_list.add_argument("db_file", help="SQLite database file")

    # -------------------------
    # Reactions commands
    # -------------------------
    p_reaction_list = sub.add_parser(
        "reaction-list",
        help="Build and display final reaction frequencies from stored fragment analysis."
    )
    p_reaction_list.add_argument("db_file", help="SQLite database file")
    p_reaction_list.add_argument(
        "--method",
        default=None,
        help="Use only one method_label from the database"
    )
    p_reaction_list.add_argument(
        "--methods",
        nargs=2,
        default=None,
        help="Compare exactly two method_label values"
    )
    p_reaction_list.add_argument(
        "--csv",
        default=None,
        help="Write the reaction summary to a CSV file"
    )
    p_reaction_list.add_argument(
        "--latex",
        default=None,
        help="Write the reaction summary to a LaTeX file"
    )
    p_reaction_list.add_argument(
        "--molecule",
        default=None,
        help="Filter by molecule name"
    )
    p_reaction_list.add_argument(
        "--isomer",
        default=None,
        help="Filter by isomer label"
    )
    p_reaction_list.add_argument(
        "--energy-label",
        default=None,
        help="Filter by energy label"
    )

    p_store_reactions = sub.add_parser(
        "store-reactions",
        help="Aggregate reactions from stored fragments and persist them in the database."
    )
    p_store_reactions.add_argument("db_file", help="SQLite database file")
    p_store_reactions.add_argument("--method", default=None, help="Use only one method_label")
    p_store_reactions.add_argument("--methods", nargs=2, default=None, help="Use exactly two method_label values")
    p_store_reactions.add_argument("--molecule", default=None, help="Filter by molecule name")
    p_store_reactions.add_argument("--isomer", default=None, help="Filter by isomer label")
    p_store_reactions.add_argument("--energy-label", default=None, help="Filter by energy label")

    p_reaction_show = sub.add_parser(
        "reaction-show",
        help="Show a stored reaction by reaction_uid, including fragments and member trajectories."
    )
    p_reaction_show.add_argument("db_file", help="SQLite database file")
    p_reaction_show.add_argument("reaction_uid", help="Stored reaction unique identifier")

    p_fragment_search = sub.add_parser(
        "fragment-search",
        help="Find stored reactions and trajectories containing a given fragment formula or mass."
    )
    p_fragment_search.add_argument("db_file", help="SQLite database file")
    p_fragment_search.add_argument("--formula", default=None, help="Fragment formula to search for")
    p_fragment_search.add_argument("--mz", type=float, default=None, help="Fragment exact mass to search for")
    p_fragment_search.add_argument("--tol", type=float, default=0.001, help="Mass tolerance for --mz searches")

    # -------------------------
    # Features commands
    # -------------------------
    p_extract_features = sub.add_parser(
        "extract-features",
        help="Compute trajectory features in memory for all selected trajectories (does not store them in the database)."
    )
    p_extract_features.add_argument("db_file", help="SQLite database file")
    p_extract_features.add_argument(
        "--molecule",
        default=None,
        help="Filter by molecule name"
    )
    p_extract_features.add_argument(
        "--isomer",
        default=None,
        help="Filter by isomer label"
    )
    p_extract_features.add_argument(
        "--method",
        default=None,
        help="Filter by method_label"
    )
    p_extract_features.add_argument(
        "--energy-label",
        default=None,
        help="Filter by energy label"
    )
    p_extract_features.add_argument(
        "--no-reactions",
        action="store_true",
        help="Do not include reaction-derived information even if available"
    )
    p_extract_features.add_argument(
        "--no-kinetics",
        action="store_true",
        help="Do not include kinetics-derived information even if available"
    )

    p_extract_features_one = sub.add_parser(
        "extract-features-one",
        help="Compute trajectory features in memory for one trajectory (does not store them in the database)."
    )
    p_extract_features_one.add_argument("db_file", help="SQLite database file")
    p_extract_features_one.add_argument("traj_uid", help="Unique trajectory identifier")
    p_extract_features_one.add_argument(
        "--no-reactions",
        action="store_true",
        help="Do not include reaction-derived information even if available"
    )
    p_extract_features_one.add_argument(
        "--no-kinetics",
        action="store_true",
        help="Do not include kinetics-derived information even if available"
    )

    p_feature_list = sub.add_parser(
        "feature-list",
        help="Compute and list trajectory features directly from the database without storing them."
    )
    p_feature_list.add_argument("db_file", help="SQLite database file")
    p_feature_list.add_argument(
        "--molecule",
        default=None,
        help="Filter by molecule name"
    )
    p_feature_list.add_argument(
        "--isomer",
        default=None,
        help="Filter by isomer label"
    )
    p_feature_list.add_argument(
        "--method",
        default=None,
        help="Filter by method_label"
    )
    p_feature_list.add_argument(
        "--energy-label",
        default=None,
        help="Filter by energy label"
    )
    p_feature_list.add_argument(
        "--no-reactions",
        action="store_true",
        help="Do not include reaction-derived information even if available"
    )
    p_feature_list.add_argument(
        "--no-kinetics",
        action="store_true",
        help="Do not include kinetics-derived information even if available"
    )

    p_feature_export = sub.add_parser(
        "feature-export",
        help="Export computed feature datasets directly from the database to CSV and optionally Parquet."
    )
    p_feature_export.add_argument("db_file", help="SQLite database file")
    p_feature_export.add_argument("output_csv", help="Output CSV file")
    p_feature_export.add_argument(
        "--dataset",
        choices=["trajectory", "condition"],
        default="trajectory",
        help="Dataset type to export: one row per trajectory or one row per condition"
    )
    p_feature_export.add_argument(
        "--parquet",
        default=None,
        help="Optional output Parquet file. If omitted, it is derived automatically from the CSV name."
    )
    p_feature_export.add_argument(
        "--molecule",
        default=None,
        help="Filter by molecule name"
    )
    p_feature_export.add_argument(
        "--isomer",
        default=None,
        help="Filter by isomer label"
    )
    p_feature_export.add_argument(
        "--method",
        default=None,
        help="Filter by method_label"
    )
    p_feature_export.add_argument(
        "--energy-label",
        default=None,
        help="Filter by energy label"
    )
    p_feature_export.add_argument(
        "--no-reactions",
        action="store_true",
        help="Do not include reaction-derived information even if available"
    )
    p_feature_export.add_argument(
        "--no-kinetics",
        action="store_true",
        help="Do not include kinetics-derived information even if available"
    )

    p_feature_export_all = sub.add_parser(
        "feature-export-all",
        help="Export all main feature datasets (trajectory and condition) to CSV and Parquet."
    )
    p_feature_export_all.add_argument("db_file", help="SQLite database file")
    p_feature_export_all.add_argument("output_dir", help="Output directory")
    p_feature_export_all.add_argument(
        "--molecule",
        default=None,
        help="Filter by molecule name"
    )
    p_feature_export_all.add_argument(
        "--isomer",
        default=None,
        help="Filter by isomer label"
    )
    p_feature_export_all.add_argument(
        "--method",
        default=None,
        help="Filter by method_label"
    )
    p_feature_export_all.add_argument(
        "--energy-label",
        default=None,
        help="Filter by energy label"
    )
    p_feature_export_all.add_argument(
        "--no-reactions",
        action="store_true",
        help="Do not include reaction-derived information even if available"
    )
    p_feature_export_all.add_argument(
        "--no-kinetics",
        action="store_true",
        help="Do not include kinetics-derived information even if available"
    )
    # -------------------------
    # Merge dbs commands
    # -------------------------
    p_merge_db = sub.add_parser(
        "merge-db",
        help="Merge two or more compatible SQLite databases into a target database."
    )
    p_merge_db.add_argument(
        "output_db",
        help="Output merged SQLite database"
    )
    p_merge_db.add_argument(
        "source_dbs",
        nargs="+",
        help="Source SQLite database files to merge"
    )

    # -------------------------
    # Mass spectras commands
    # -------------------------
    p_spectra = sub.add_parser(
        "spectra",
        help="Build a mass spectra from stored final fragments."
    )
    p_spectra.add_argument("db_file", help="SQLite database file")
    p_spectra.add_argument("--molecule", default=None, help="Filter by molecule name")
    p_spectra.add_argument("--isomer", default=None, help="Filter by isomer label")
    p_spectra.add_argument("--method", default=None, help="Filter by method_label")
    p_spectra.add_argument("--energy-label", default=None, help="Filter by energy label")
    p_spectra.add_argument(
        "--charged-only",
        action="store_true",
        help="Include only charged fragments"
    )
    p_spectra.add_argument(
        "--neutral-only",
        action="store_true",
        help="Include only neutral fragments"
    )
    p_spectra.add_argument(
        "--mz-min",
        type=float,
        default=None,
        help="Minimum m/z value to include"
    )
    p_spectra.add_argument(
        "--mz-max",
        type=float,
        default=None,
        help="Maximum m/z value to include"
    )
    p_spectra.add_argument(
        "--scale",
        type=float,
        default=1000.0,
        help="Intensity normalization scale (default: 1000)"
    )
    p_spectra.add_argument(
        "--sort",
        choices=["intensity", "mz"],
        default="intensity",
        help="Sort peaks by intensity or mz"
    )
    p_spectra.add_argument(
        "--csv",
        default=None,
        help="Write the spectra table to CSV"
    )

    # -------------------------
    # Kinetics commands
    # -------------------------

    p_kinetics = sub.add_parser(
       "kinetics",
        help="Compute global disappearance kinetics from frame-by-frame connectivity."
    )
    p_kinetics.add_argument("db_file", help="SQLite database file")
    p_kinetics.add_argument("--molecule", default=None, help="Filter by molecule name")
    p_kinetics.add_argument("--isomer", default=None, help="Filter by isomer label")
    p_kinetics.add_argument("--method", default=None, help="Filter by method_label")
    p_kinetics.add_argument("--energy-label", default=None, help="Filter by energy label")
    p_kinetics.add_argument(
        "--persist-frames",
        type=int,
        default=5,
        help="Number of consecutive fragmented frames required to declare disappearance"
    )
    p_kinetics.add_argument(
        "--window-mode",
        choices=["censor", "common"],
        default="censor",
        help="Use individual censoring or truncate to common window"
    )
    p_kinetics.add_argument(
        "--min-points",
        type=int,
        default=5,
        help="Minimum number of points required for the regression fit"
    )
    p_kinetics.add_argument(
        "--summary-csv",
        default=None,
        help="Optional CSV file to write one-row kinetics summary"
    )
    p_kinetics.add_argument(
        "--events-csv",
        default=None,
        help="Optional CSV file to write one row per trajectory/event"
    )
    p_kinetics.add_argument(
        "--survival-csv",
        default=None,
        help="Optional CSV file to write the survival curve table"
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "store":
        store_xyz_in_db(
            xyz_path=args.xyz_file,
            db_path=args.db_file,
            input_path=args.input_file,
            block_size=args.block_size,
            overwrite=args.overwrite,
            molecule=args.molecule,
            isomer=args.isomer,
            method=args.method,
            energy_label=args.energy_label,
            run_id=args.run_id,
        )

    elif args.command == "store-all":
        store_all_from_runs(
            root_dir=args.root_dir,
            db_path=args.db_file,
            input_path=args.input_file,
            molecule=args.molecule,
            isomer=args.isomer,
            method=args.method,
            energy_label=args.energy_label,
            block_size=args.block_size,
            overwrite=args.overwrite,
            xyz_name=args.xyz_name,
        )

    elif args.command == "store-venus-one":
        store_one_venus_output(
            out_path=args.out_file,
            db_path=args.db_file,
            input_path=args.input_file,
            molecule=args.molecule,
            isomer=args.isomer,
            method=args.method,
            energy_label=args.energy_label,
            block_size=args.block_size,
        )

    elif args.command == "store-venus":
        store_all_venus_from_sims(
            root_dir=args.root_dir,
            db_path=args.db_file,
            input_path=args.input_file,
            molecule=args.molecule,
            isomer=args.isomer,
            method=args.method,
            energy_label=args.energy_label,
            block_size=args.block_size,
        )

    elif args.command == "restore":
        restore_single_run_from_db(
            db_path=args.db_file,
            traj_uid=args.traj_uid,
        )

    elif args.command == "restore-all":
        restore_all_from_db(
            db_path=args.db_file,
            output_dir=args.output_dir,
            molecule=args.molecule,
            isomer=args.isomer,
            method=args.method,
            energy_label=args.energy_label,
        )
    
    elif args.command == "restore-input":
        restore_input_for_trajectory(
            db_path=args.db_file,
            traj_uid=args.traj_uid,
            output_path=args.output,
        )

    elif args.command == "list":
        list_trajectories(
            args.db_file,
            molecule=args.molecule,
            isomer=args.isomer,
            method=args.method,
            energy_label=args.energy_label,
        )

    elif args.command == "summary":
        summary_db(
            args.db_file,
            molecule=args.molecule,
            isomer=args.isomer,
            method=args.method,
            energy_label=args.energy_label,
        )

    elif args.command == "show":
        show_trajectory(args.db_file, args.traj_uid)

    elif args.command == "show-input":
        show_input_from_db(args.db_file, args.traj_uid)

    elif args.command == "analyze-fragments":
        analyze_and_store_fragments_for_all(args.db_file)

    elif args.command == "analyze-fragments-one":
        analyze_and_store_fragments_for_traj(args.db_file, args.traj_uid)

    elif args.command == "fragment-list":
        fragment_list(args.db_file)

    elif args.command == "store-reactions":
        selected_methods = None
        if args.methods is not None:
            selected_methods = args.methods
        elif args.method is not None:
            selected_methods = [args.method]

        store_reactions(
            db_path=args.db_file,
            methods=selected_methods,
            molecule=args.molecule,
            isomer=args.isomer,
            energy_label=args.energy_label,
        )

    elif args.command == "reaction-show":
        reaction_show(args.db_file, args.reaction_uid)

    elif args.command == "fragment-search":
        fragment_search(
            db_path=args.db_file,
            formula=args.formula,
            mz=args.mz,
            tol=args.tol,
        )

    elif args.command == "reaction-list":
        selected_methods = None
        if args.methods is not None:
            selected_methods = args.methods
        elif args.method is not None:
            selected_methods = [args.method]

        reaction_list(
            db_path=args.db_file,
            methods=selected_methods,
            molecule=args.molecule,
            isomer=args.isomer,
            energy_label=args.energy_label,
            output_csv=args.csv,
            output_tex=args.latex,
        )

    elif args.command == "extract-features":
        extract_features_all(
            args.db_file,
            molecule=args.molecule,
            isomer=args.isomer,
            method=args.method,
            energy_label=args.energy_label,
            include_reactions=not args.no_reactions,
            include_kinetics=not args.no_kinetics,
        )

    elif args.command == "extract-features-one":
        extract_features_one(
            args.db_file,
            args.traj_uid,
            include_reactions=not args.no_reactions,
            include_kinetics=not args.no_kinetics,
        )

    elif args.command == "feature-list":
        feature_list(
            args.db_file,
            molecule=args.molecule,
            isomer=args.isomer,
            method=args.method,
            energy_label=args.energy_label,
            include_reactions=not args.no_reactions,
            include_kinetics=not args.no_kinetics,
        )

    elif args.command == "feature-export":
        feature_export(
            db_path=args.db_file,
            output_csv=args.output_csv,
            molecule=args.molecule,
            isomer=args.isomer,
            method=args.method,
            energy_label=args.energy_label,
            dataset_type=args.dataset,
            include_reactions=not args.no_reactions,
            include_kinetics=not args.no_kinetics,
            output_parquet=args.parquet,
        )

    elif args.command == "feature-export-all":
        feature_export_all(
            db_path=args.db_file,
            output_dir=args.output_dir,
            molecule=args.molecule,
            isomer=args.isomer,
            method=args.method,
            energy_label=args.energy_label,
            include_reactions=not args.no_reactions,
            include_kinetics=not args.no_kinetics,
        )

    elif args.command == "merge-db":
        merge_databases(
            source_dbs=args.source_dbs,
            output_db=args.output_db,
        )

    elif args.command == "spectra":
        spectrum_list(
            db_path=args.db_file,
            molecule=args.molecule,
            isomer=args.isomer,
            method=args.method,
            energy_label=args.energy_label,
            charged_only=args.charged_only,
            neutral_only=args.neutral_only,
            mz_min=args.mz_min,
            mz_max=args.mz_max,
            scale=args.scale,
            sort_by=args.sort,
            output_csv=args.csv,
        )

    elif args.command == "kinetics":
        compute_and_store_global_kinetics(
            db_path=args.db_file,
            molecule=args.molecule,
            isomer=args.isomer,
            method=args.method,
            energy_label=args.energy_label,
            persist_frames=args.persist_frames,
            window_mode=args.window_mode,
            min_points=args.min_points,
            output_summary_csv=args.summary_csv,
            output_events_csv=args.events_csv,
            output_survival_csv=args.survival_csv,
        )

    else:
        parser.error("Unknown command.")