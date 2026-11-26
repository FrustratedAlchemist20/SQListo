
#!/usr/bin/env python3

"""
SQListo database schema migration utility.

Adds missing columns required by newer versions of SQListo
without deleting existing data or recalculating scientific results.
"""

import argparse
import sqlite3
from pathlib import Path
from contextlib import closing


MIGRATIONS = {
    "md_inputs": {
        "energy_label_factor": "REAL",
        "energy_temperature_K": "REAL",
        "energy_kcal_mol": "REAL",
        "zpe_kcal_mol": "REAL",
        "dof": "INTEGER",
    },
    "kinetics_global": {
        "min_points": "INTEGER",
    },
}


def get_columns(conn, table):
    return {
        row[1]
        for row in conn.execute(
            f'PRAGMA table_info("{table}")'
        )
    }


def migrate_database(database):
    original_path = Path(database).expanduser()

    if original_path.is_symlink():
        raise ValueError(
            "Refusing to migrate a symbolic link. "
            "Use an independent database copy."
        )

    db_path = original_path.resolve()

    if not db_path.is_file():
        raise FileNotFoundError(db_path)

    print(f"Database: {db_path}")

    with closing(
        sqlite3.connect(
            db_path.as_uri() + "?mode=rw",
            uri=True
        )
    ) as conn:

        conn.execute("PRAGMA foreign_keys = ON")

        tables = {
            row[0]
            for row in conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            )
        }

        missing_tables = set(MIGRATIONS) - tables

        if missing_tables:
            raise ValueError(
                f"Missing required tables: {missing_tables}"
            )

        added_columns = 0

        try:
            conn.execute("BEGIN IMMEDIATE")

            for table, columns in MIGRATIONS.items():

                print(f"\nTable: {table}")

                existing = get_columns(conn, table)

                for column, datatype in columns.items():

                    if column in existing:
                        print(f"  [OK] {column}")
                        continue

                    conn.execute(
                        f'ALTER TABLE "{table}" '
                        f'ADD COLUMN "{column}" {datatype}'
                    )

                    added_columns += 1

                    print(f"  [ADDED] {column}")

            integrity = conn.execute(
                "PRAGMA quick_check"
            ).fetchall()

            if integrity != [("ok",)]:
                raise RuntimeError(
                    f"Integrity check failed: {integrity}"
                )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        print("\nMigration completed successfully.")
        print(f"Columns added: {added_columns}")
        print("Integrity check: OK")
        print("Existing scientific values preserved.")


def main():

    parser = argparse.ArgumentParser(
        description="Update legacy SQListo databases."
    )

    parser.add_argument(
        "database",
        help="Path to an independent SQLite database copy."
    )

    args = parser.parse_args()

    migrate_database(args.database)


if __name__ == "__main__":
    main()

