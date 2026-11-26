# xyz2db/merge_tools/merge_db.py

import sqlite3

from ..db import init_db


# Tables in dependency-safe order
TABLES_IN_ORDER = [
    "md_inputs",
    "trajectories",
    "frame_blocks",
    "fragment_analysis",
    "fragments",
    "trajectory_features",
]

# Tables where the internal AUTOINCREMENT id should be regenerated
REGENERATE_ID_TABLES = {
    "frame_blocks",
    "fragments",
}


def table_exists(conn, table_name):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name=?
        """,
        (table_name,),
    )
    return cur.fetchone() is not None


def get_table_columns(conn, table_name):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    rows = cur.fetchall()
    return [row[1] for row in rows]


def build_insert_sql(table_name, columns, source_schema="src"):
    """
    Build INSERT OR IGNORE SQL.
    For some tables we intentionally exclude the 'id' column so SQLite regenerates it.
    """
    target_columns = list(columns)

    if table_name in REGENERATE_ID_TABLES and "id" in target_columns:
        target_columns.remove("id")

    col_list = ", ".join(target_columns)
    sql = f"""
        INSERT OR IGNORE INTO {table_name} ({col_list})
        SELECT {col_list}
        FROM {source_schema}.{table_name}
    """
    return sql, target_columns


def merge_one_source_into_target(source_db, target_db):
    # Ensure target exists and has the full schema
    target_conn = init_db(target_db)
    target_cur = target_conn.cursor()

    # Attach source DB
    target_cur.execute("ATTACH DATABASE ? AS src", (source_db,))

    # Open source separately only to inspect its schema
    source_conn = sqlite3.connect(source_db)

    try:
        for table in TABLES_IN_ORDER:
            if not table_exists(source_conn, table):
                print(f"Skipping table '{table}' from {source_db}: table not found.")
                continue

            if not table_exists(target_conn, table):
                print(f"Skipping table '{table}' in target DB: target table not found.")
                continue

            target_columns = get_table_columns(target_conn, table)
            source_columns = get_table_columns(source_conn, table)

            # Only use columns that exist in both source and target
            common_columns = [col for col in target_columns if col in source_columns]

            if table in REGENERATE_ID_TABLES and "id" in common_columns:
                common_columns.remove("id")

            if not common_columns:
                print(f"Skipping table '{table}' from {source_db}: no compatible columns.")
                continue

            col_list = ", ".join(common_columns)
            sql = f"""
                INSERT OR IGNORE INTO {table} ({col_list})
                SELECT {col_list}
                FROM src.{table}
            """

            try:
                target_cur.execute(sql)
                print(f"Merged table '{table}' from {source_db}")
            except Exception as e:
                print(f"Skipping table '{table}' from {source_db} due to error: {e}")

        target_conn.commit()
        target_cur.execute("DETACH DATABASE src")

    finally:
        source_conn.close()
        target_conn.close()


def merge_databases(source_dbs, output_db):
    # Create output DB with the full schema if it does not exist
    conn = init_db(output_db)
    conn.close()

    for source_db in source_dbs:
        print(f"--- Merging source database: {source_db}")
        merge_one_source_into_target(source_db, output_db)

    print(f"Done. Merged {len(source_dbs)} database(s) into: {output_db}")