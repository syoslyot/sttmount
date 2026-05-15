import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "sttmount.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS expeditions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    date_start  TEXT,
    date_end    TEXT,
    county      TEXT,
    region      TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS members (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    expedition_id INTEGER NOT NULL REFERENCES expeditions(id),
    name          TEXT NOT NULL,
    role          TEXT
);

CREATE TABLE IF NOT EXISTS gpx_files (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    expedition_id INTEGER NOT NULL REFERENCES expeditions(id),
    filename      TEXT NOT NULL,
    file_path     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS map_files (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    expedition_id INTEGER NOT NULL REFERENCES expeditions(id),
    filename      TEXT NOT NULL,
    file_path     TEXT NOT NULL,
    file_type     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS records (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    expedition_id INTEGER NOT NULL REFERENCES expeditions(id),
    filename      TEXT NOT NULL,
    content       TEXT NOT NULL
);
"""

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
