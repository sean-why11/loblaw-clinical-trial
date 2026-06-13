from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

root = Path(__file__).resolve().parent
csv_path = root / "cell-count.csv"
db_path = root / "cell-count.db"

cell_populations = ("b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte")

def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    return connection

def initialize_database(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        DROP VIEW IF EXISTS sample_cell_frequencies;
        DROP TABLE IF EXISTS cell_counts;
        DROP TABLE IF EXISTS samples;
        DROP TABLE IF EXISTS subjects;
        DROP TABLE IF EXISTS cell_populations;

        CREATE TABLE subjects (
            subject_id TEXT PRIMARY KEY,
            project TEXT NOT NULL,
            indication TEXT NOT NULL,
            age INTEGER,
            gender TEXT
        );

        CREATE TABLE samples (
            sample_id TEXT PRIMARY KEY,
            subject_id TEXT NOT NULL,
            sample_type TEXT NOT NULL,
            treatment TEXT NOT NULL,
            response TEXT,
            time_from_treatment_start INTEGER NOT NULL,
            FOREIGN KEY (subject_id) REFERENCES subjects (subject_id)
        );

        CREATE TABLE cell_populations(
            population_id INTEGER PRIMARY KEY,
            population_name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE cell_counts(
            sample_id TEXT NOT NULL,
            population_id INTEGER NOT NULL,
            cell_count INTEGER NOT NULL CHECK (cell_count >=0),
            PRIMARY KEY (sample_id, population_id),
            FOREIGN KEY(sample_id) REFERENCES samples (sample_id),
            FOREIGN KEY (population_id) REFERENCES cell_populations (population_id)
        );

        CREATE INDEX idx_samples_subject_id ON samples (subject_id);
        CREATE INDEX idx_samples_treatment_time
            ON samples (treatment, time_from_treatment_start);
        CREATE INDEX idx_samples_response ON samples (response);
        """
    )

    connection.executemany(
        "INSERT INTO cell_populations (population_name) VALUES (?)",
        ((population,) for population in cell_populations),
    )

def to_int(value: str) -> int | None:
    stripped = value.strip()
    if not stripped:
        return None
    return int(stripped)

def load_csv(connection: sqlite3.Connection) -> int:
    population_ids = {
        name: population_id
        for population_id, name in connection.execute(
            "SELECT population_id, population_name FROM cell_populations"
        )
    }

    rows_loaded = 0
    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            connection.execute(
                """
                INSERT OR IGNORE INTO subjects (
                    subject_id,
                    project,
                    indication,
                    age,
                    gender
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row["subject"],
                    row["project"],
                    row["condition"],
                    to_int(row["age"]),
                    row["sex"],
                ),
            )

            connection.execute(
                """
                INSERT INTO samples (
                    sample_id,
                    subject_id,
                    sample_type,
                    treatment,
                    response,
                    time_from_treatment_start
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row["sample"],
                    row["subject"],
                    row["sample_type"],
                    row["treatment"],
                    row["response"],
                    to_int(row["time_from_treatment_start"]),
                ),
            )

            connection.executemany(
                """
                INSERT INTO cell_counts (sample_id, population_id, cell_count)
                VALUES (?, ?, ?)
                """,
                (
                    (row["sample"], population_ids[population], to_int(row[population]))
                    for population in cell_populations
                ),
            )
            rows_loaded += 1

    return rows_loaded

def main() -> None:
    if not csv_path.exists():
        raise FileNotFoundError(f"Could not find source CSV {csv_path}")
    with connect() as connection:
        initialize_database(connection)
        rows_loaded = load_csv(connection)

        print(f"created {db_path.name} and loaded {rows_loaded} samples")
    
if __name__ == "__main__":
    main()
