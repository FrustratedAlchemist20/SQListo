
import sqlite3
import unittest

from sqlisto_agent import build_fast_metadata_sql


class TestMetadataSQL(unittest.TestCase):

    def setUp(self):
        self.catalog = {
            "molecules": ["Azaconazole", "Difenoconazole"],
            "methods": ["uB3LYP"],
            "energy_labels": ["ZPEx3"],
            "isomers": [],
        }

        self.conn = sqlite3.connect(":memory:")

        self.conn.execute("""
            CREATE TABLE trajectories (
                molecule TEXT,
                isomer TEXT,
                method_label TEXT,
                energy_label TEXT,
                nframes INTEGER
            )
        """)

        rows = (
            [("Azaconazole", None, "uB3LYP", "ZPEx3", 100)]
            * 313
            +
            [("Difenoconazole", None, "uB3LYP", "ZPEx3", 100)]
            * 325
        )

        self.conn.executemany(
            "INSERT INTO trajectories VALUES (?, ?, ?, ?, ?)",
            rows,
        )

    def tearDown(self):
        self.conn.close()

    def execute_question(self, question):
        result = build_fast_metadata_sql(
            question,
            self.catalog,
        )

        self.assertIsNotNone(result)

        sql, params, route = result

        return self.conn.execute(sql, params).fetchall()

    def test_total_trajectories(self):
        result = self.execute_question(
            "How many trajectories are stored in the database?"
        )

        self.assertEqual(result, [(638,)])

    def test_count_by_molecule(self):
        result = self.execute_question(
            "How many trajectories are stored for each molecule?"
        )

        self.assertEqual(
            result,
            [
                ("Azaconazole", 313),
                ("Difenoconazole", 325),
            ],
        )

    def test_count_by_molecule_spanish(self):
        result = self.execute_question(
            "¿Cuántas trayectorias hay para cada molécula?"
        )

        self.assertEqual(
            result,
            [
                ("Azaconazole", 313),
                ("Difenoconazole", 325),
            ],
        )

    def test_count_by_method(self):
        result = self.execute_question(
            "How many trajectories are stored for each method?"
        )

        self.assertEqual(result, [("uB3LYP", 638)])

    def test_molecule_filter(self):
        result = self.execute_question(
            "How many trajectories are stored for Azaconazole?"
        )

        self.assertEqual(result, [(313,)])

    def test_count_by_energy(self):
        result = self.execute_question(
            "How many trajectories are stored for each energy?"
        )

        self.assertEqual(result, [("ZPEx3", 638)])

    def test_average_frames(self):
        result = self.execute_question(
            "What is the average number of frames for each molecule?"
        )

        self.assertEqual(
            result,
            [
                ("Azaconazole", 100.0),
                ("Difenoconazole", 100.0),
            ],
        )


if __name__ == "__main__":
    unittest.main()

